"""Routes edited from the card: the same stored shape as the options flow makes."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import voluptuous as vol

from .const import (
    CONF_ACCESSIBILITY,
    CONF_EXCLUDED_MODES,
    CONF_EXTRA_INTERCHANGE_TIME,
    CONF_LESS_WALKING,
    CONF_TIME,
    CONF_TIME_ENTITY,
    CONF_TIME_OFFSET,
    CONF_TIMING,
    CONF_WEEKDAYS,
    DEFAULT_TIME,
    ROUTE_ENDS,
    TIMING_NOW,
    TIMINGS,
    WEEKDAYS,
)

_PLACE = vol.Schema(
    {
        vol.Required("id"): vol.All(str, vol.Length(min=1)),
        vol.Required("label"): str,
        vol.Optional("latlong"): vol.Any(None, vol.All([vol.Coerce(float)], vol.Length(min=2, max=2))),
    }
)

ROUTE_INPUT_SCHEMA = vol.Schema(
    {
        vol.Optional("id"): str,
        vol.Required("name"): vol.All(str, vol.Length(min=1)),
        vol.Optional("person"): vol.Any(None, str),
        vol.Required("from"): _PLACE,
        vol.Required("to"): _PLACE,
        vol.Required(CONF_TIMING): vol.In(TIMINGS),
        vol.Optional(CONF_TIME): str,
        vol.Optional(CONF_WEEKDAYS): [vol.In(WEEKDAYS)],
        vol.Optional(CONF_TIME_ENTITY): vol.Any(None, str),
        vol.Optional(CONF_TIME_OFFSET): vol.Coerce(int),
    }
)

# What a route that was made in the card gets for the options only the options flow offers
_DEFAULTS = {
    CONF_EXCLUDED_MODES: [],
    CONF_EXTRA_INTERCHANGE_TIME: 0,
    CONF_ACCESSIBILITY: False,
    CONF_LESS_WALKING: False,
}


def route_from_input(existing: dict | None, data: dict[str, Any]) -> dict:
    """The stored route for card input; an existing route keeps the options the card does not show."""
    route = {**_DEFAULTS, **(existing or {})}
    route["id"] = route.get("id") or uuid4().hex[:8]
    route["name"] = data["name"].strip()

    if data.get("person"):
        route["person"] = data["person"]
    else:
        route.pop("person", None)

    for end in ROUTE_ENDS:
        place = data[end]
        route[end] = place["id"]
        route[f"{end}_label"] = place["label"]
        route[f"{end}_latlong"] = place.get("latlong")

    route[CONF_TIMING] = data[CONF_TIMING]
    for key in (CONF_TIME, CONF_WEEKDAYS, CONF_TIME_ENTITY, CONF_TIME_OFFSET):
        route.pop(key, None)
    if data[CONF_TIMING] != TIMING_NOW:
        route[CONF_TIME] = data.get(CONF_TIME) or DEFAULT_TIME
        route[CONF_WEEKDAYS] = data.get(CONF_WEEKDAYS) or list(WEEKDAYS)
        route[CONF_TIME_OFFSET] = data.get(CONF_TIME_OFFSET, 0)
        if data.get(CONF_TIME_ENTITY):
            route[CONF_TIME_ENTITY] = data[CONF_TIME_ENTITY]
    return route
