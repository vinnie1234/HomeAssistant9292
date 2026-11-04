from pathlib import Path

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_state_change_event

from .const import DOMAIN, SIGNAL_READY
from .planning import NineTwoNineTwoCoordinator
from .websocket import async_register_websocket

PLATFORMS = ["sensor"]

WWW_URL = f"/{DOMAIN}"
WWW_PATH = Path(__file__).parent / "www"
CARD_FILE = "ov-9292-card.js"
FRONTEND_REGISTERED = f"{DOMAIN}_frontend_registered"


def route_device_identifier(entry: ConfigEntry, route_id: str) -> tuple[str, str]:
    return (DOMAIN, f"{entry.entry_id}_route_{route_id}")


def _card_version() -> int:
    return int((WWW_PATH / CARD_FILE).stat().st_mtime)


async def _async_register_frontend(hass: HomeAssistant) -> None:
    """Serve the card (and Leaflet) and load it in the frontend, once per run."""
    if hass.data.get(FRONTEND_REGISTERED):
        return
    await hass.http.async_register_static_paths(
        [StaticPathConfig(WWW_URL, str(WWW_PATH), cache_headers=False)]
    )
    version = await hass.async_add_executor_job(_card_version)
    # The version in the URL makes browsers pick up a new card after an update
    add_extra_js_url(hass, f"{WWW_URL}/{CARD_FILE}?v={version}")
    async_register_websocket(hass)
    hass.data[FRONTEND_REGISTERED] = True


def _remove_deleted_route_devices(
    hass: HomeAssistant, entry: ConfigEntry, coordinator: NineTwoNineTwoCoordinator
) -> None:
    """Routes removed in the options leave their device behind; drop it."""
    wanted = {route_device_identifier(entry, route["id"]) for route in coordinator.routes}
    prefix = f"{entry.entry_id}_route_"
    registry = dr.async_get(hass)
    for device in dr.async_entries_for_config_entry(registry, entry.entry_id):
        route_identifiers = {i for i in device.identifiers if i[0] == DOMAIN and i[1].startswith(prefix)}
        if route_identifiers and not route_identifiers & wanted:
            registry.async_update_device(device.id, remove_config_entry_id=entry.entry_id)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    coordinator = NineTwoNineTwoCoordinator(hass, entry)

    # A failed first fetch must not block setup: the sensors stay registered
    # (unavailable) and the coordinator retries at the configured interval.
    await coordinator.async_refresh()

    entry.runtime_data = coordinator
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))

    if coordinator.time_entities:

        # @callback keeps this on the event loop; a plain function would run in an executor thread,
        # where creating a task is not allowed
        @callback
        def _time_entity_changed(_event: Event) -> None:
            hass.async_create_task(coordinator.async_request_refresh())

        entry.async_on_unload(
            async_track_state_change_event(hass, coordinator.time_entities, _time_entity_changed)
        )

    _remove_deleted_route_devices(hass, entry, coordinator)
    await _async_register_frontend(hass)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    async_dispatcher_send(hass, SIGNAL_READY)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
