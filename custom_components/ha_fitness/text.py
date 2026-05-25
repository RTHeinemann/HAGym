"""Text platform for HA Fitness Tracker."""
from __future__ import annotations

from homeassistant.components.text import TextEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import HAFitnessCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up HA Fitness text entities from a config entry."""
    coordinator: HAFitnessCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[TextEntity] = [HAFitnessNotesText(coordinator, entry)]
    for equipment_id in coordinator.enabled_equipment_ids:
        entities.append(HAFitnessEquipmentNotesText(coordinator, entry, equipment_id))
    async_add_entities(entities)


class HAFitnessNotesText(TextEntity):
    """Text entity for optional set notes."""

    _attr_has_entity_name = True
    _attr_translation_key = "notes"
    _attr_native_max = 255

    def __init__(
        self, coordinator: HAFitnessCoordinator, entry: ConfigEntry
    ) -> None:
        self._coordinator = coordinator
        self._attr_unique_id = f"{entry.entry_id}_notes"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=coordinator.display_name,
            manufacturer="HA Fitness",
            model="Fitness Tracker",
            entry_type="service",
        )

    async def async_added_to_hass(self) -> None:
        """Subscribe to coordinator updates."""
        self.async_on_remove(
            self._coordinator.async_add_listener(self._handle_coordinator_update)
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        self.async_write_ha_state()

    @property
    def native_value(self) -> str:
        return self._coordinator.notes

    async def async_set_value(self, value: str) -> None:
        self._coordinator.set_notes(value)


class HAFitnessEquipmentNotesText(TextEntity):
    """Text entity for equipment-specific optional set notes."""

    _attr_has_entity_name = True
    _attr_translation_key = "notes"
    _attr_native_max = 255

    def __init__(
        self, coordinator: HAFitnessCoordinator, entry: ConfigEntry, equipment_id: str
    ) -> None:
        self._coordinator = coordinator
        self._equipment_id = equipment_id
        self._attr_unique_id = f"{entry.entry_id}_{equipment_id}_notes"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id, equipment_id)},
            name=coordinator.equipment_display_name(equipment_id),
            manufacturer="HA Fitness",
            model="Fitness Equipment",
            suggested_area=coordinator.equipment_location(equipment_id),
            entry_type="service",
        )

    async def async_added_to_hass(self) -> None:
        """Subscribe to coordinator updates."""
        self.async_on_remove(
            self._coordinator.async_add_listener(self._handle_coordinator_update)
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        return self._coordinator.equipment_enabled(self._equipment_id)

    @property
    def native_value(self) -> str:
        return self._coordinator.get_equipment_notes(self._equipment_id)

    async def async_set_value(self, value: str) -> None:
        self._coordinator.set_equipment_notes(self._equipment_id, value)
