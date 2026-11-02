"""Journey planning: next departures for the routes set up in the options."""

from __future__ import annotations

from datetime import timedelta
import logging

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import NineTwoNineTwoClient
from .const import (
    CONF_ROUTES,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    UPCOMING_LIMIT,
)

_LOGGER = logging.getLogger(__name__)

WALKING = "Walking"


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
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            # Without routes there is nothing to refresh
            update_interval=timedelta(minutes=options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL))
            if self.routes
            else None,
        )

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
        try:
            plans = parse_plans(await self._client.async_plans(route))
        except (aiohttp.ClientError, TimeoutError, KeyError, ValueError) as err:
            _LOGGER.warning("Could not fetch 9292 route %s: %s", route["name"], err)
            return None
        # A cancelled journey is no use as "next departure", but stays visible in the list
        plans["next"] = next((j for j in plans["journeys"] if not j["cancelled"]), None)
        plans["upcoming"] = plans["journeys"][:UPCOMING_LIMIT]
        return plans if plans["next"] else None
