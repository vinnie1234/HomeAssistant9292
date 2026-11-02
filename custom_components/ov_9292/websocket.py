"""Websocket feed for the 9292 card.

The card needs the full journey data of every route, which does not fit in entity
attributes, so it subscribes here instead of reading entity states.
"""

from __future__ import annotations

import aiohttp
import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import DOMAIN, SIGNAL_READY
from .planning import NineTwoNineTwoCoordinator


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


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/journey", vol.Required("journey_id"): str})
@websocket_api.async_response
async def ws_journey(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    """The legs, stops and route of one journey, for the details in the card."""
    coordinator = _loaded_coordinator(hass)
    if coordinator is None:
        connection.send_error(msg["id"], "not_loaded", "9292 OV is not loaded")
        return
    try:
        connection.send_result(msg["id"], await coordinator.async_journey(msg["journey_id"]))
    except (aiohttp.ClientError, TimeoutError, KeyError, ValueError) as err:
        connection.send_error(msg["id"], "fetch_failed", str(err))


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
