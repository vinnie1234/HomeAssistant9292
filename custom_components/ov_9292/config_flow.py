from __future__ import annotations

from typing import Any
from uuid import uuid4

import aiohttp
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    BooleanSelector,
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TimeSelector,
)

from .api import NineTwoNineTwoClient, parse_lat_long
from .const import (
    CONF_ACCESSIBILITY,
    CONF_EXCLUDED_MODES,
    CONF_EXTRA_INTERCHANGE_TIME,
    CONF_LESS_WALKING,
    CONF_ROUTE_NAME,
    CONF_ROUTE_PERSON,
    CONF_ROUTES,
    CONF_SCAN_INTERVAL,
    CONF_TIME,
    CONF_TIME_ENTITY,
    CONF_TIME_OFFSET,
    CONF_TIMING,
    CONF_WEEKDAYS,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_TIME,
    DOMAIN,
    LOCATION_ROWS,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
    TIME_ENTITY_DOMAINS,
    TIMING_NOW,
    TIMINGS,
    TRAVEL_MODES,
    WEEKDAYS,
)


def _interval_schema(default: int) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_SCAN_INTERVAL, default=default): NumberSelector(
                NumberSelectorConfig(
                    min=MIN_SCAN_INTERVAL,
                    max=MAX_SCAN_INTERVAL,
                    step=1,
                    unit_of_measurement="min",
                    mode=NumberSelectorMode.BOX,
                )
            )
        }
    )


class NineTwoNineTwoConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None) -> FlowResult:
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        if user_input is not None:
            return self.async_create_entry(
                title="9292 OV",
                data={CONF_SCAN_INTERVAL: int(user_input[CONF_SCAN_INTERVAL]), CONF_ROUTES: []},
            )
        return self.async_show_form(step_id="user", data_schema=_interval_schema(DEFAULT_SCAN_INTERVAL))

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        return NineTwoNineTwoOptionsFlow()


class NineTwoNineTwoOptionsFlow(config_entries.OptionsFlow):
    """Menu for settings and routes. A route goes through: options, search + pick the start, search + pick the end."""

    _editing: dict | None = None
    _new_route: dict[str, Any]
    _found: list[dict]

    async def async_step_init(self, user_input=None) -> FlowResult:
        menu = ["settings", "add_route"]
        if self._routes():
            menu += ["edit_route", "remove_route"]
        return self.async_show_menu(step_id="init", menu_options=menu)

    async def async_step_settings(self, user_input=None) -> FlowResult:
        if user_input is not None:
            return self._save({**self._defaults(), CONF_SCAN_INTERVAL: int(user_input[CONF_SCAN_INTERVAL])})
        return self.async_show_form(
            step_id="settings",
            data_schema=_interval_schema(self._defaults().get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)),
        )

    async def async_step_add_route(self, user_input=None) -> FlowResult:
        self._editing = None
        return await self.async_step_route()

    async def async_step_edit_route(self, user_input=None) -> FlowResult:
        """Pick the route to change; it then goes through the same steps as a new one."""
        routes = {route["id"]: route for route in self._routes()}
        if user_input is not None:
            self._editing = routes[user_input["route_id"]]
            return await self.async_step_route()

        options = [SelectOptionDict(value=r["id"], label=r["name"]) for r in routes.values()]
        return self.async_show_form(
            step_id="edit_route",
            data_schema=vol.Schema(
                {
                    vol.Required("route_id"): SelectSelector(
                        SelectSelectorConfig(options=options, mode=SelectSelectorMode.LIST)
                    )
                }
            ),
        )

    async def async_step_route(self, user_input=None) -> FlowResult:
        """Name, owner and travel options; the two places follow in the search steps."""
        editing = self._editing or {}
        if user_input is not None:
            self._new_route = {
                # Keeping the id of an edited route keeps its devices and entities
                "id": editing.get("id") or uuid4().hex[:8],
                CONF_ROUTE_NAME: user_input[CONF_ROUTE_NAME].strip(),
                CONF_EXCLUDED_MODES: user_input.get(CONF_EXCLUDED_MODES, []),
                CONF_EXTRA_INTERCHANGE_TIME: int(user_input[CONF_EXTRA_INTERCHANGE_TIME]),
                CONF_ACCESSIBILITY: user_input[CONF_ACCESSIBILITY],
                CONF_LESS_WALKING: user_input[CONF_LESS_WALKING],
                CONF_TIMING: user_input[CONF_TIMING],
            }
            if person := user_input.get(CONF_ROUTE_PERSON):
                self._new_route[CONF_ROUTE_PERSON] = person
            if user_input[CONF_TIMING] != TIMING_NOW:
                return await self.async_step_timing()
            return await self.async_step_from_search()

        def default(key: str, fallback: Any = vol.UNDEFINED) -> Any:
            return editing.get(key, fallback)

        return self.async_show_form(
            step_id="route",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ROUTE_NAME, default=default(CONF_ROUTE_NAME)): str,
                    vol.Optional(
                        CONF_ROUTE_PERSON,
                        description={"suggested_value": editing.get(CONF_ROUTE_PERSON)},
                    ): EntitySelector(EntitySelectorConfig(domain="person")),
                    vol.Optional(
                        CONF_EXCLUDED_MODES, default=default(CONF_EXCLUDED_MODES, [])
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=list(TRAVEL_MODES),
                            translation_key=CONF_EXCLUDED_MODES,
                            multiple=True,
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                    vol.Required(
                        CONF_EXTRA_INTERCHANGE_TIME, default=default(CONF_EXTRA_INTERCHANGE_TIME, 0)
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=0, max=30, step=1, unit_of_measurement="min", mode=NumberSelectorMode.BOX
                        )
                    ),
                    vol.Required(CONF_TIMING, default=default(CONF_TIMING, TIMING_NOW)): SelectSelector(
                        SelectSelectorConfig(
                            options=TIMINGS, translation_key=CONF_TIMING, mode=SelectSelectorMode.LIST
                        )
                    ),
                    vol.Required(CONF_ACCESSIBILITY, default=default(CONF_ACCESSIBILITY, False)): BooleanSelector(),
                    vol.Required(CONF_LESS_WALKING, default=default(CONF_LESS_WALKING, False)): BooleanSelector(),
                }
            ),
        )

    async def async_step_timing(self, user_input=None) -> FlowResult:
        """The time of a route that is not live: a fixed time on some weekdays, or the time of an entity."""
        editing = self._editing or {}
        if user_input is not None:
            for key in (CONF_TIME, CONF_WEEKDAYS, CONF_TIME_ENTITY, CONF_TIME_OFFSET):
                if (value := user_input.get(key)) not in (None, ""):
                    self._new_route[key] = int(value) if key == CONF_TIME_OFFSET else value
            return await self.async_step_from_search()

        return self.async_show_form(
            step_id="timing",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_TIME, default=editing.get(CONF_TIME, DEFAULT_TIME)): TimeSelector(),
                    vol.Required(CONF_WEEKDAYS, default=editing.get(CONF_WEEKDAYS, WEEKDAYS)): SelectSelector(
                        SelectSelectorConfig(
                            options=WEEKDAYS,
                            translation_key=CONF_WEEKDAYS,
                            multiple=True,
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                    vol.Optional(
                        CONF_TIME_ENTITY,
                        description={"suggested_value": editing.get(CONF_TIME_ENTITY)},
                    ): EntitySelector(EntitySelectorConfig(domain=TIME_ENTITY_DOMAINS)),
                    vol.Required(CONF_TIME_OFFSET, default=editing.get(CONF_TIME_OFFSET, 0)): NumberSelector(
                        NumberSelectorConfig(
                            min=-240, max=240, step=1, unit_of_measurement="min", mode=NumberSelectorMode.BOX
                        )
                    ),
                }
            ),
            description_placeholders={"name": self._new_route[CONF_ROUTE_NAME]},
        )

    async def async_step_from_search(self, user_input=None) -> FlowResult:
        return await self._async_search("from", user_input)

    async def async_step_from_pick(self, user_input=None) -> FlowResult:
        return await self._async_pick("from", user_input)

    async def async_step_to_search(self, user_input=None) -> FlowResult:
        return await self._async_search("to", user_input)

    async def async_step_to_pick(self, user_input=None) -> FlowResult:
        return await self._async_pick("to", user_input)

    async def _async_search(self, end: str, user_input: dict | None) -> FlowResult:
        """Type (part of) a place, station or address; 9292 suggests matches to pick from."""
        current = (self._editing or {}).get(f"{end}_label") or (self._editing or {}).get(end)
        errors = {}
        if user_input is not None:
            query = user_input.get("query", "").strip()
            if not query and self._editing:
                # Editing: leaving the search empty keeps the place as it is
                self._keep_end(end)
                return await self._async_after_end(end)
            if not query:
                errors["base"] = "no_results"
            else:
                try:
                    client = NineTwoNineTwoClient(async_get_clientsession(self.hass))
                    self._found = await client.async_locations(query, LOCATION_ROWS)
                except (aiohttp.ClientError, TimeoutError):
                    errors["base"] = "cannot_connect"
                else:
                    if self._found:
                        return await self._async_pick(end, None)
                    errors["base"] = "no_results"

        field = vol.Optional("query") if self._editing else vol.Required("query")
        return self.async_show_form(
            step_id=f"{end}_search",
            data_schema=vol.Schema({field: TextSelector()}),
            description_placeholders={"name": self._new_route[CONF_ROUTE_NAME], "current": current or "-"},
            errors=errors,
        )

    async def _async_pick(self, end: str, user_input: dict | None) -> FlowResult:
        if user_input is not None:
            location = next(item for item in self._found if item["id"] == user_input["location"])
            self._new_route[end] = location["id"]
            self._new_route[f"{end}_label"] = location.get("displayLabel") or location["label"]
            self._new_route[f"{end}_latlong"] = parse_lat_long(location.get("latLong"))
            return await self._async_after_end(end)

        options = [
            SelectOptionDict(
                value=item["id"],
                label=f"{item.get('displayLabel') or item['label']} ({item.get('category', '')}, {item.get('place', '')})",
            )
            for item in self._found
        ]
        return self.async_show_form(
            step_id=f"{end}_pick",
            data_schema=vol.Schema(
                {
                    vol.Required("location"): SelectSelector(
                        SelectSelectorConfig(options=options, mode=SelectSelectorMode.LIST)
                    )
                }
            ),
            description_placeholders={"name": self._new_route[CONF_ROUTE_NAME]},
        )

    def _keep_end(self, end: str) -> None:
        for suffix in ("", "_label", "_latlong"):
            if (value := (self._editing or {}).get(f"{end}{suffix}")) is not None:
                self._new_route[f"{end}{suffix}"] = value

    async def _async_after_end(self, end: str) -> FlowResult:
        if end == "from":
            return await self.async_step_to_search()
        return self._save({**self._defaults(), CONF_ROUTES: self._with_route(self._new_route)})

    def _with_route(self, route: dict) -> list[dict]:
        """The routes with this one added, or replacing the edited one."""
        routes = self._routes()
        if self._editing:
            return [route if r["id"] == route["id"] else r for r in routes]
        return [*routes, route]

    async def async_step_remove_route(self, user_input=None) -> FlowResult:
        if user_input is not None:
            removed = set(user_input[CONF_ROUTES])
            return self._save({**self._defaults(), CONF_ROUTES: [r for r in self._routes() if r["id"] not in removed]})

        options = [SelectOptionDict(value=r["id"], label=r["name"]) for r in self._routes()]
        return self.async_show_form(
            step_id="remove_route",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ROUTES): SelectSelector(
                        SelectSelectorConfig(options=options, multiple=True, mode=SelectSelectorMode.LIST)
                    )
                }
            ),
        )

    def _defaults(self) -> dict:
        return {**self.config_entry.data, **self.config_entry.options}

    def _routes(self) -> list[dict]:
        return self._defaults().get(CONF_ROUTES, [])

    def _save(self, data: dict) -> FlowResult:
        return self.async_create_entry(data=data)
