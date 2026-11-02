from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .planning import NineTwoNineTwoCoordinator


def _person_suffix(hass: HomeAssistant, person: str | None) -> str:
    """' (Vincent)' for the device name, so the owner shows in the device list."""
    if not person:
        return ""
    state = hass.states.get(person)
    name = state.name if state else person.split(".", 1)[-1].replace("_", " ").title()
    return f" ({name})"


def _journey_attributes(journey: dict) -> dict:
    return {key: journey[key] for key in ("lines", "operators", "modes", "price", "occupancy", "detour")}


def _summary_attributes(result: dict) -> dict:
    return {
        **_journey_attributes(result["next"]),
        "from": result["from_place"],
        "to": result["to_place"],
        "upcoming": [
            {key: journey[key] for key in ("departure_actual", "arrival", "duration_min", "delay_min", "transfers", "lines", "cancelled")}
            for journey in result["upcoming"]
        ],
    }


@dataclass(frozen=True, kw_only=True)
class RouteSensorDescription(SensorEntityDescription):
    value_fn: Callable[[dict], float | int | str | datetime | None]
    attributes_fn: Callable[[dict], dict] | None = None


ROUTE_SENSORS: tuple[RouteSensorDescription, ...] = (
    RouteSensorDescription(
        key="departure",
        translation_key="departure",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda result: dt_util.parse_datetime(result["next"]["departure_actual"]),
        attributes_fn=lambda result: {"planned_departure": result["next"]["departure"]},
    ),
    RouteSensorDescription(
        key="arrival",
        translation_key="arrival",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda result: dt_util.parse_datetime(result["next"]["arrival"]),
    ),
    RouteSensorDescription(
        key="duration",
        translation_key="duration",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda result: result["next"]["duration_min"],
    ),
    RouteSensorDescription(
        key="delay",
        translation_key="delay",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:timer-sand",
        value_fn=lambda result: result["next"]["delay_min"],
    ),
    RouteSensorDescription(
        key="transfers",
        translation_key="transfers",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:transfer",
        value_fn=lambda result: result["next"]["transfers"],
    ),
    RouteSensorDescription(
        key="lines",
        translation_key="lines",
        icon="mdi:train-bus",
        value_fn=lambda result: " · ".join(result["next"]["lines"]) or None,
        attributes_fn=_summary_attributes,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: NineTwoNineTwoCoordinator = entry.runtime_data
    async_add_entities(
        NineTwoNineTwoRouteSensor(coordinator, entry, route, description)
        for route in coordinator.routes
        for description in ROUTE_SENSORS
    )


class NineTwoNineTwoRouteSensor(CoordinatorEntity[NineTwoNineTwoCoordinator], SensorEntity):
    """One value of the next journey between two places."""

    entity_description: RouteSensorDescription
    _attr_has_entity_name = True
    # The upcoming list changes every refresh and is of no use in history
    _unrecorded_attributes = frozenset({"upcoming"})

    def __init__(
        self,
        coordinator: NineTwoNineTwoCoordinator,
        entry: ConfigEntry,
        route: dict,
        description: RouteSensorDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._route_id = route["id"]
        self._person = route.get("person")
        self._attr_unique_id = f"{entry.entry_id}_route_{route['id']}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.entry_id}_route_{route['id']}")},
            name=f"9292 {route['name']}{_person_suffix(coordinator.hass, self._person)}",
            manufacturer="9292",
            entry_type=DeviceEntryType.SERVICE,
            configuration_url="https://9292.nl",
        )

    @property
    def _result(self) -> dict | None:
        return (self.coordinator.data or {}).get(self._route_id)

    @property
    def available(self) -> bool:
        # A single route can fail (e.g. an unknown place) while the others work
        return super().available and self._result is not None

    @property
    def native_value(self):
        result = self._result
        return self.entity_description.value_fn(result) if result else None

    @property
    def extra_state_attributes(self) -> dict | None:
        result = self._result
        if not result:
            return None
        attributes = self.entity_description.attributes_fn(result) if self.entity_description.attributes_fn else {}
        if self._person:
            attributes["person"] = self._person
        return attributes or None
