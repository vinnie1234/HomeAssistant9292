from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN
from .planning import NineTwoNineTwoCoordinator

PLATFORMS = ["sensor"]


def route_device_identifier(entry: ConfigEntry, route_id: str) -> tuple[str, str]:
    return (DOMAIN, f"{entry.entry_id}_route_{route_id}")


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

    _remove_deleted_route_devices(hass, entry, coordinator)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
