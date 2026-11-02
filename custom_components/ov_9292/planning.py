"""Journey planning: next departures for the routes set up in the options."""

from __future__ import annotations

from datetime import timedelta
import logging
import time

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import NineTwoNineTwoClient, parse_lat_long
from .timing import target_time
from .geometry import parse_linestring, simplify_path
from .const import (
    CONF_ROUTES,
    CONF_SCAN_INTERVAL,
    CONF_TIME,
    CONF_TIME_ENTITY,
    CONF_TIME_OFFSET,
    CONF_TIMING,
    CONF_WEEKDAYS,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    LOCATION_ROWS,
    TIMING_ARRIVAL,
    TIMING_NOW,
    UPCOMING_LIMIT,
)

_LOGGER = logging.getLogger(__name__)

WALKING = "Walking"
# Seconds a journey's details are reused; the card asks again when the real-time data may have changed
DETAIL_TTL = 60


def _minutes_between(start: str | None, end: str | None) -> int:
    first, second = dt_util.parse_datetime(start or ""), dt_util.parse_datetime(end or "")
    if first is None or second is None:
        return 0
    return round((second - first).total_seconds() / 60)


def parse_journey(preview: dict) -> dict:
    """One option of the response, with delay and transfers worked out."""
    meta = preview.get("metaData", {})
    lines = iter(meta.get("lineNumbers", []))
    # The line numbers belong to the non-walking legs, in order
    legs = [
        {
            "mode": icon["name"],
            "line": None if icon["name"] == WALKING else next(lines, None),
            "cancelled": bool(icon.get("cancelled")),
        }
        for icon in preview.get("icons", [])
    ]
    modes = [leg["mode"] for leg in legs if leg["mode"] != WALKING]
    planned = preview["departureTime"]
    # Without a real-time departure the planned time is all there is
    actual = preview.get("departureRealTime") or planned
    return {
        # Opaque id the details of this journey are fetched with
        "id": preview.get("id"),
        "departure": planned,
        "departure_actual": actual,
        "arrival": preview["arrivalTime"],
        "duration_min": preview.get("durationInMinutes"),
        "delay_min": max(_minutes_between(planned, actual), 0),
        "transfers": max(len(modes) - 1, 0),
        "modes": modes,
        "legs": legs,
        "lines": meta.get("lineNumbers", []),
        "operators": meta.get("operators", []),
        "price": round(preview["priceEuroCents"] / 100, 2) if preview.get("priceEuroCents") else None,
        "occupancy": preview.get("occupancy"),
        "cancelled": bool(preview.get("cancelled")),
        "detour": bool(preview.get("detour")),
    }


def parse_plans(raw: dict) -> dict:
    """The upcoming journeys in the order the API gives them, plus the resolved place names."""
    meta = raw.get("metaData", {})
    return {
        "from_place": (meta.get("fromLocation") or {}).get("place"),
        "to_place": (meta.get("toLocation") or {}).get("name") or (meta.get("toLocation") or {}).get("place"),
        "journeys": [parse_journey(preview) for preview in raw.get("previews", [])],
    }


def _call(call: dict) -> dict:
    """A stop of a leg: where, when planned, when real-time, and the platform."""
    return {
        "id": call.get("id"),
        "name": call.get("displayName"),
        "category": call.get("category"),
        "time": call.get("time"),
        "real": call.get("realTime") or call.get("time"),
        "platform": call.get("platform"),
        "latlong": parse_lat_long((call.get("location") or {}).get("latLong")),
    }


def _disruptions(leg: dict) -> list[str]:
    """Messages of the operator for this leg. The API's own title lists every affected place, so it is left out."""
    messages = []
    for disruption in leg.get("disruptions", []):
        message = disruption.get("operatorMessage") or " ".join(
            part
            for part in (disruption.get("effect"), disruption.get("measure"), disruption.get("advice"))
            if part
        )
        if message and message not in messages:
            messages.append(message.strip())
    return messages


def parse_detail(raw: dict) -> dict:
    """The legs of one journey with stops, platforms, real-time, disruptions and the route on the map."""
    legs = []
    for leg in raw.get("legs", []):
        legs.append(
            {
                "mode": leg.get("icon"),
                "description": leg.get("modalityDescription"),
                "line": leg.get("service") or None,
                "destination": leg.get("destination") or None,
                "from": _call(leg["departureCall"]),
                "to": _call(leg["arrivalCall"]),
                "stops": [_call(stop) for stop in leg.get("stops", [])],
                "distance_m": (leg.get("route") or {}).get("distance"),
                "disruptions": _disruptions(leg),
                "cancelled": leg.get("status") == "Cancelled",
                "path": simplify_path(parse_linestring((leg.get("route") or {}).get("routeGeometry"))),
            }
        )
    return {"legs": legs, "duration_min": raw.get("durationInMinutes"), "changes": raw.get("numberOfChanges")}


def _editable(route: dict) -> dict:
    """The settings of a route the card's editor shows."""
    return {
        key: route[key]
        for key in (CONF_TIMING, CONF_TIME, CONF_WEEKDAYS, CONF_TIME_ENTITY, CONF_TIME_OFFSET)
        if key in route
    }


def _end(route: dict, end: str) -> dict:
    """One end of a route as the card needs it; routes made before the search have no label."""
    return {
        "id": route[end],
        "label": route.get(f"{end}_label") or route[end],
        "latlong": route.get(f"{end}_latlong"),
    }


class NineTwoNineTwoCoordinator(DataUpdateCoordinator[dict[str, dict | None]]):
    """Data per route id: {"from_place", "to_place", "journeys"}, or None if it failed."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        options = {**entry.data, **entry.options}
        self.routes: list[dict] = options.get(CONF_ROUTES, [])
        self._client = NineTwoNineTwoClient(async_get_clientsession(hass))
        self._details: dict[str, tuple[float, dict]] = {}
        # Routes that follow an entity re-plan as soon as that entity changes
        self.time_entities = sorted({route[CONF_TIME_ENTITY] for route in self.routes if route.get(CONF_TIME_ENTITY)})
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            # Without routes there is nothing to refresh
            update_interval=timedelta(minutes=options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL))
            if self.routes
            else None,
        )

    async def async_locations(self, query: str) -> list[dict]:
        """Places matching what is typed, for the search in the card."""
        return [
            {
                "id": item["id"],
                "label": item.get("displayLabel") or item["label"],
                "category": item.get("category"),
                "place": item.get("place"),
                "latlong": parse_lat_long(item.get("latLong")),
            }
            for item in await self._client.async_locations(query, LOCATION_ROWS)
        ]

    async def async_journey(self, journey_id: str) -> dict:
        """Details of one journey, fetched when the card asks for it and kept briefly."""
        now = time.monotonic()
        self._details = {key: value for key, value in self._details.items() if now - value[0] < DETAIL_TTL}
        if journey_id not in self._details:
            self._details[journey_id] = (now, parse_detail(await self._client.async_journey(journey_id)))
        return self._details[journey_id][1]

    def payload(self) -> list[dict]:
        """What the 9292 card receives over the websocket."""
        payload = []
        for route in self.routes:
            result = (self.data or {}).get(route["id"])
            payload.append(
                {
                    "id": route["id"],
                    "name": route["name"],
                    "person": route.get("person"),
                    "from": _end(route, "from"),
                    "to": _end(route, "to"),
                    "config": _editable(route),
                    "timing": result["timing"] if result else {"mode": route.get(CONF_TIMING, TIMING_NOW), "target": None},
                    "error": result is None,
                    "next": result["next"] if result else None,
                    "upcoming": result["upcoming"] if result else [],
                }
            )
        return payload

    async def _async_update_data(self) -> dict[str, dict | None]:
        if not self.routes:
            return {}
        results = {route["id"]: await self._async_fetch(route) for route in self.routes}
        if not any(results.values()):
            raise UpdateFailed("None of the 9292 routes could be fetched")
        return results

    async def _async_fetch(self, route: dict) -> dict | None:
        mode = route.get(CONF_TIMING, TIMING_NOW)
        target = target_time(self.hass, route)
        if mode != TIMING_NOW and target is None:
            _LOGGER.debug("Route %s has no time to plan around right now", route["name"])
            return None
        request_type = "Arrival" if mode == TIMING_ARRIVAL else "Departure"
        try:
            plans = parse_plans(await self._client.async_plans(route, target, request_type))
        except (aiohttp.ClientError, TimeoutError, KeyError, ValueError) as err:
            _LOGGER.warning("Could not fetch 9292 route %s: %s", route["name"], err)
            return None
        # A cancelled journey is no use as "next departure", but stays visible in the list
        plans["timing"] = {"mode": mode, "target": target.isoformat() if target else None}
        plans["next"] = next((j for j in plans["journeys"] if not j["cancelled"]), None)
        plans["upcoming"] = plans["journeys"][:UPCOMING_LIMIT]
        return plans if plans["next"] else None
