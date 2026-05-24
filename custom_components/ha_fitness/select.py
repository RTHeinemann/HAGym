"""Select platform for HA Fitness Tracker."""
from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, EXERCISES
from .coordinator import HAFitnessCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up HA Fitness select entities from a config entry."""
    coordinator: HAFitnessCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([HAFitnessActiveExerciseSelect(coordinator, entry)])


class HAFitnessActiveExerciseSelect(SelectEntity):
    """Select entity for choosing the active exercise."""

    _attr_has_entity_name = True
    _attr_translation_key = "active_exercise"
    _attr_options = EXERCISES

    def __init__(
        self, coordinator: HAFitnessCoordinator, entry: ConfigEntry
    ) -> None:
        self._coordinator = coordinator
        self._attr_unique_id = f"{entry.entry_id}_active_exercise"
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
    def current_option(self) -> str | None:
        return self._coordinator.active_exercise

    async def async_select_option(self, option: str) -> None:
        """Handle option selection."""
        self._coordinator.set_active_exercise(option)
