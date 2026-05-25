"""Button platform for HA Fitness Tracker."""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity
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
    """Set up HA Fitness buttons from a config entry."""
    coordinator: HAFitnessCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[ButtonEntity] = [
        HAFitnessStartWorkoutButton(coordinator, entry),
        HAFitnessFinishWorkoutButton(coordinator, entry),
        HAFitnessSaveSetButton(coordinator, entry),
    ]
    for equipment_id in coordinator.enabled_equipment_ids:
        entities.append(HAFitnessEquipmentSelectButton(coordinator, entry, equipment_id))
    async_add_entities(entities)


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
        await self._coordinator.start_workout(context_user_id=self._context.user_id)


class HAFitnessFinishWorkoutButton(_HAFitnessButtonBase):
    """Button to finish a workout."""

    _attr_translation_key = "finish_workout"

    def __init__(
        self, coordinator: HAFitnessCoordinator, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_finish_workout"

    async def async_press(self) -> None:
        await self._coordinator.finish_workout(context_user_id=self._context.user_id)


class HAFitnessSaveSetButton(_HAFitnessButtonBase):
    """Button to save the current set using coordinator runtime state."""

    _attr_translation_key = "save_set"

    def __init__(
        self, coordinator: HAFitnessCoordinator, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_save_set"

    async def async_press(self) -> None:
        await self._coordinator.save_current_set(context_user_id=self._context.user_id)


class HAFitnessEquipmentSelectButton(ButtonEntity):
    """Button to set this equipment as the active equipment."""

    _attr_has_entity_name = True
    _attr_translation_key = "select_equipment"

    def __init__(
        self, coordinator: HAFitnessCoordinator, entry: ConfigEntry, equipment_id: str
    ) -> None:
        self._coordinator = coordinator
        self._equipment_id = equipment_id
        self._attr_unique_id = f"{entry.entry_id}_{equipment_id}_select_equipment"
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

    async def async_press(self) -> None:
        self._coordinator.set_active_equipment(self._equipment_id)
