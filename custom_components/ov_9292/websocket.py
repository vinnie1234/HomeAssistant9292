"""Websocket feed for the 9292 card.

The card needs the full journey data of every route, which does not fit in entity
attributes, so it subscribes here instead of reading entity states.
"""

from __future__ import annotations

import logging

import aiohttp
import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import CONF_ROUTES, DOMAIN, SIGNAL_READY
from .planning import NineTwoNineTwoCoordinator
from .routes import ROUTE_INPUT_SCHEMA, route_from_input


_LOGGER = logging.getLogger(__name__)


def _loaded_coordinator(hass: HomeAssistant) -> NineTwoNineTwoCoordinator | None:
    # SETUP_IN_PROGRESS: SIGNAL_READY is sent before Home Assistant marks the entry LOADED
    active = (ConfigEntryState.LOADED, ConfigEntryState.SETUP_IN_PROGRESS)
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.state in active:
            return getattr(entry, "runtime_data", None)
    return None


@callback
def async_register_websocket(hass: HomeAssistant) -> None:
    websocket_api.async_register_command(hass, ws_subscribe)
    websocket_api.async_register_command(hass, ws_journey)
    websocket_api.async_register_command(hass, ws_locations)
    websocket_api.async_register_command(hass, ws_save_route)
    websocket_api.async_register_command(hass, ws_delete_route)


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/locations", vol.Required("query"): str})
@websocket_api.async_response
async def ws_locations(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    """Places matching what is typed in the card's route editor."""
    coordinator = _loaded_coordinator(hass)
    if coordinator is None:
        connection.send_error(msg["id"], "not_loaded", "9292 OV is not loaded")
        return
    try:
        connection.send_result(msg["id"], await coordinator.async_locations(msg["query"].strip()))
    except (aiohttp.ClientError, TimeoutError, KeyError, ValueError) as err:
        connection.send_error(msg["id"], "fetch_failed", str(err))


def _loaded_entry(hass: HomeAssistant):
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.state is ConfigEntryState.LOADED:
            return entry
    return None


def _update_routes(hass: HomeAssistant, entry, routes: list[dict]) -> None:
    # The options update listener reloads the integration, which sends the card the new routes
    hass.config_entries.async_update_entry(
        entry, options={**entry.data, **entry.options, CONF_ROUTES: routes}
    )


@websocket_api.require_admin
@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/save_route", vol.Required("route"): ROUTE_INPUT_SCHEMA})
@callback
def ws_save_route(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    """Add a route, or change the one with the given id, from the card's editor."""
    entry = _loaded_entry(hass)
    if entry is None:
        connection.send_error(msg["id"], "not_loaded", "9292 OV is not loaded")
        return
    routes = list({**entry.data, **entry.options}.get(CONF_ROUTES, []))
    data = msg["route"]
    existing = next((route for route in routes if route["id"] == data.get("id")), None)
    route = route_from_input(existing, data)
    _update_routes(hass, entry, [route if route["id"] == r["id"] else r for r in routes] if existing else [*routes, route])
    connection.send_result(msg["id"], {"id": route["id"]})


@websocket_api.require_admin
@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/delete_route", vol.Required("route_id"): str})
@callback
def ws_delete_route(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    entry = _loaded_entry(hass)
    if entry is None:
        connection.send_error(msg["id"], "not_loaded", "9292 OV is not loaded")
        return
    routes = {**entry.data, **entry.options}.get(CONF_ROUTES, [])
    _update_routes(hass, entry, [route for route in routes if route["id"] != msg["route_id"]])
    connection.send_result(msg["id"])


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/journey", vol.Required("journey_id"): str, vol.Optional("route_id"): str})
@websocket_api.async_response
async def ws_journey(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    """The legs, stops and route of one journey, for the details in the card."""
    coordinator = _loaded_coordinator(hass)
    if coordinator is None:
        connection.send_error(msg["id"], "not_loaded", "9292 OV is not loaded")
        return
    try:
        connection.send_result(msg["id"], await coordinator.async_journey(msg["journey_id"], msg.get("route_id")))
    except (aiohttp.ClientError, TimeoutError, KeyError, ValueError, TypeError) as err:
        _LOGGER.warning("Could not fetch 9292 journey details: %s: %s", type(err).__name__, err)
        connection.send_error(msg["id"], "fetch_failed", f"{type(err).__name__}: {err}")


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/subscribe"})
@callback
def ws_subscribe(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    unsubscribe_coordinator = None

    @callback
    def _attach() -> None:
        # Also runs when the integration is reloaded (options changed): the old
        # coordinator is gone, so move this subscription to the new one.
        nonlocal unsubscribe_coordinator
        if unsubscribe_coordinator:
            unsubscribe_coordinator()
            unsubscribe_coordinator = None
        coordinator = _loaded_coordinator(hass)
        if coordinator is None:
            return

        @callback
        def _send() -> None:
            connection.send_message(websocket_api.event_message(msg["id"], {"routes": coordinator.payload()}))

        unsubscribe_coordinator = coordinator.async_add_listener(_send)
        _send()

    unsubscribe_signal = async_dispatcher_connect(hass, SIGNAL_READY, _attach)

    @callback
    def _unsubscribe() -> None:
        unsubscribe_signal()
        if unsubscribe_coordinator:
            unsubscribe_coordinator()

    connection.subscriptions[msg["id"]] = _unsubscribe
    connection.send_result(msg["id"])
    _attach()
