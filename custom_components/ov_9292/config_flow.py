from __future__ import annotations

from typing import Any
from uuid import uuid4

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
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
)

from .const import (
    CONF_ACCESSIBILITY,
    CONF_EXCLUDED_MODES,
    CONF_EXTRA_INTERCHANGE_TIME,
    CONF_LESS_WALKING,
    CONF_ROUTE_FROM,
    CONF_ROUTE_NAME,
    CONF_ROUTE_PERSON,
    CONF_ROUTE_TO,
    CONF_ROUTES,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
    TRAVEL_MODES,
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
    _editing: dict | None = None

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
        """Pick the route to change; it then uses the same form as a new one."""
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
        editing = self._editing or {}
        errors = {}
        if user_input is not None:
            if not user_input[CONF_ROUTE_FROM].strip() or not user_input[CONF_ROUTE_TO].strip():
                errors["base"] = "place_required"
            else:
                route: dict[str, Any] = {
                    # Keeping the id of an edited route keeps its devices and entities
                    "id": editing.get("id") or uuid4().hex[:8],
                    CONF_ROUTE_NAME: user_input[CONF_ROUTE_NAME].strip(),
                    CONF_ROUTE_FROM: user_input[CONF_ROUTE_FROM].strip(),
                    CONF_ROUTE_TO: user_input[CONF_ROUTE_TO].strip(),
                    CONF_EXCLUDED_MODES: user_input.get(CONF_EXCLUDED_MODES, []),
                    CONF_EXTRA_INTERCHANGE_TIME: int(user_input[CONF_EXTRA_INTERCHANGE_TIME]),
                    CONF_ACCESSIBILITY: user_input[CONF_ACCESSIBILITY],
                    CONF_LESS_WALKING: user_input[CONF_LESS_WALKING],
                }
                if person := user_input.get(CONF_ROUTE_PERSON):
                    route[CONF_ROUTE_PERSON] = person
                return self._save({**self._defaults(), CONF_ROUTES: self._with_route(route)})

        def default(key: str, fallback: Any = vol.UNDEFINED) -> Any:
            return editing.get(key, fallback)

        return self.async_show_form(
            step_id="route",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ROUTE_NAME, default=default(CONF_ROUTE_NAME)): str,
                    vol.Required(CONF_ROUTE_FROM, default=default(CONF_ROUTE_FROM)): TextSelector(),
                    vol.Required(CONF_ROUTE_TO, default=default(CONF_ROUTE_TO)): TextSelector(),
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
                    vol.Required(CONF_ACCESSIBILITY, default=default(CONF_ACCESSIBILITY, False)): BooleanSelector(),
                    vol.Required(CONF_LESS_WALKING, default=default(CONF_LESS_WALKING, False)): BooleanSelector(),
                }
            ),
            errors=errors,
        )

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
