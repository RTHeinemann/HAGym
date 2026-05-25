"""Button platform for HA Fitness Tracker."""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import HAFitnessCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up HA Fitness buttons from a config entry."""
    coordinator: HAFitnessCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            HAFitnessStartWorkoutButton(coordinator, entry),
            HAFitnessFinishWorkoutButton(coordinator, entry),
            HAFitnessSaveSetButton(coordinator, entry),
        ]
    )


class _HAFitnessButtonBase(ButtonEntity):
    """Base class for HA Fitness buttons."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: HAFitnessCoordinator, entry: ConfigEntry
    ) -> None:
        self._coordinator = coordinator
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=coordinator.display_name,
            manufacturer="HA Fitness",
            model="Fitness Tracker",
            entry_type="service",
        )


class HAFitnessStartWorkoutButton(_HAFitnessButtonBase):
    """Button to start a workout."""

    _attr_translation_key = "start_workout"

    def __init__(
        self, coordinator: HAFitnessCoordinator, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_start_workout"

    async def async_press(self) -> None:
        await self._coordinator.start_workout(context_user_id=None)


class HAFitnessFinishWorkoutButton(_HAFitnessButtonBase):
    """Button to finish a workout."""

    _attr_translation_key = "finish_workout"

    def __init__(
        self, coordinator: HAFitnessCoordinator, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_finish_workout"

    async def async_press(self) -> None:
        await self._coordinator.finish_workout(context_user_id=None)


class HAFitnessSaveSetButton(_HAFitnessButtonBase):
    """Button to save the current set using coordinator runtime state."""

    _attr_translation_key = "save_set"

    def __init__(
        self, coordinator: HAFitnessCoordinator, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_save_set"

    async def async_press(self) -> None:
        await self._coordinator.save_current_set(context_user_id=None)
