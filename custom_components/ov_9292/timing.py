"""When a route should travel: now, or around a time that is fixed or comes from an entity."""

from __future__ import annotations

from datetime import datetime, time, timedelta

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .const import (
    CONF_TIME,
    CONF_TIME_ENTITY,
    CONF_TIME_OFFSET,
    CONF_TIMING,
    CONF_WEEKDAYS,
    DEFAULT_TIME,
    DEPARTURE_GRACE_MIN,
    TIMING_ARRIVAL,
    TIMING_NOW,
    WEEKDAYS,
)


def _local(value: datetime) -> datetime:
    """A datetime from a state; one without a time zone is in the Home Assistant time zone."""
    if value.tzinfo is None:
        return value.replace(tzinfo=dt_util.DEFAULT_TIME_ZONE)
    return dt_util.as_local(value)


def _next_occurrence(at: time, weekdays: set[int], now: datetime, grace: timedelta) -> datetime | None:
    """Today at `at` while it is not longer than `grace` ago, else the next selected weekday."""
    for days in range(8):
        candidate = datetime.combine((now + timedelta(days=days)).date(), at, tzinfo=dt_util.DEFAULT_TIME_ZONE)
        if candidate.weekday() in weekdays and candidate + grace >= now:
            return candidate
    return None


def entity_time(hass: HomeAssistant, entity_id: str) -> datetime | time | None:
    """The moment an entity stands for: a datetime, or just a time of day. None when it has none."""
    state = hass.states.get(entity_id)
    if state is None or state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE, ""):
        return None
    domain = entity_id.split(".", 1)[0]
    if domain == "calendar":
        start = state.attributes.get("start_time")
        parsed = dt_util.parse_datetime(start) if start else None
        return _local(parsed) if parsed else None
    parsed = dt_util.parse_datetime(state.state)
    if parsed is not None:
        return _local(parsed)
    return dt_util.parse_time(state.state)


def target_time(hass: HomeAssistant, route: dict, now: datetime | None = None) -> datetime | None:
    """The moment to plan the route around, or None when it is not known (yet).

    Live routes have no target. A time of day (fixed, or from a time entity) is the next selected weekday
    it has not passed on; a full date and time (date entity, timestamp sensor, calendar event) is used as it is.
    """
    mode = route.get(CONF_TIMING, TIMING_NOW)
    if mode == TIMING_NOW:
        return None
    now = dt_util.as_local(now or dt_util.now())
    # Arriving by a time is over once it has passed; leaving around a time is still useful a while after
    grace = timedelta(0) if mode == TIMING_ARRIVAL else timedelta(minutes=DEPARTURE_GRACE_MIN)

    source = entity_time(hass, route[CONF_TIME_ENTITY]) if route.get(CONF_TIME_ENTITY) else None
    if route.get(CONF_TIME_ENTITY) and source is None:
        return None
    if source is None:
        source = dt_util.parse_time(route.get(CONF_TIME) or DEFAULT_TIME)

    offset = timedelta(minutes=int(route.get(CONF_TIME_OFFSET, 0)))
    if isinstance(source, datetime):
        target = source + offset
        return target if target + grace >= now else None

    weekdays = {WEEKDAYS.index(day) for day in route.get(CONF_WEEKDAYS, WEEKDAYS)}
    occurrence = _next_occurrence(source, weekdays, now, grace)
    return occurrence + offset if occurrence else None
