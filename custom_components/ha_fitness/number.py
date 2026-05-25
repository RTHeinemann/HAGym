"""Number platform for HA Fitness Tracker."""
from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfMass
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
    """Set up HA Fitness number entities from a config entry."""
    coordinator: HAFitnessCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[NumberEntity] = [
        HAFitnessWeightNumber(coordinator, entry),
        HAFitnessRepsNumber(coordinator, entry),
    ]
    for equipment_id in coordinator.enabled_equipment_ids:
        entities.append(HAFitnessEquipmentWeightNumber(coordinator, entry, equipment_id))
        entities.append(HAFitnessEquipmentRepsNumber(coordinator, entry, equipment_id))
    async_add_entities(entities)


class _HAFitnessNumberBase(NumberEntity):
    """Base class for HA Fitness number entities."""

    _attr_has_entity_name = True
    _attr_mode = NumberMode.BOX

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

    async def async_added_to_hass(self) -> None:
        """Subscribe to coordinator updates."""
        self.async_on_remove(
            self._coordinator.async_add_listener(self._handle_coordinator_update)
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        self.async_write_ha_state()


class HAFitnessWeightNumber(_HAFitnessNumberBase):
    """Number entity for workout set weight."""

    _attr_translation_key = "weight"
    _attr_native_min_value = 0
    _attr_native_max_value = 500
    _attr_native_step = 0.5
    _attr_native_unit_of_measurement = UnitOfMass.KILOGRAMS

    def __init__(
        self, coordinator: HAFitnessCoordinator, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_weight"

    @property
    def native_value(self) -> float:
        return self._coordinator.weight

    async def async_set_native_value(self, value: float) -> None:
        self._coordinator.set_weight(value)


class HAFitnessRepsNumber(_HAFitnessNumberBase):
    """Number entity for workout set reps."""

    _attr_translation_key = "reps"
    _attr_native_min_value = 0
    _attr_native_max_value = 999
    _attr_native_step = 1

    def __init__(
        self, coordinator: HAFitnessCoordinator, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_reps"

    @property
    def native_value(self) -> float:
        return float(self._coordinator.reps)

    async def async_set_native_value(self, value: float) -> None:
        self._coordinator.set_reps(int(value))


class _HAFitnessEquipmentNumberBase(NumberEntity):
    """Base class for equipment-specific number entities."""

    _attr_has_entity_name = True
    _attr_mode = NumberMode.BOX

    def __init__(
        self, coordinator: HAFitnessCoordinator, entry: ConfigEntry, equipment_id: str
    ) -> None:
        self._coordinator = coordinator
        self._equipment_id = equipment_id
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


class HAFitnessEquipmentWeightNumber(_HAFitnessEquipmentNumberBase):
    """Number entity for equipment-specific workout set weight."""

    _attr_translation_key = "weight"
    _attr_native_min_value = 0
    _attr_native_max_value = 500
    _attr_native_step = 0.5
    _attr_native_unit_of_measurement = UnitOfMass.KILOGRAMS

    def __init__(
        self, coordinator: HAFitnessCoordinator, entry: ConfigEntry, equipment_id: str
    ) -> None:
        super().__init__(coordinator, entry, equipment_id)
        self._attr_unique_id = f"{entry.entry_id}_{equipment_id}_weight"

    @property
    def native_value(self) -> float:
        return self._coordinator.get_equipment_weight(self._equipment_id)

    async def async_set_native_value(self, value: float) -> None:
        self._coordinator.set_equipment_weight(self._equipment_id, value)


class HAFitnessEquipmentRepsNumber(_HAFitnessEquipmentNumberBase):
    """Number entity for equipment-specific workout set reps."""

    _attr_translation_key = "reps"
    _attr_native_min_value = 0
    _attr_native_max_value = 999
    _attr_native_step = 1

    def __init__(
        self, coordinator: HAFitnessCoordinator, entry: ConfigEntry, equipment_id: str
    ) -> None:
        super().__init__(coordinator, entry, equipment_id)
        self._attr_unique_id = f"{entry.entry_id}_{equipment_id}_reps"

    @property
    def native_value(self) -> float:
        return float(self._coordinator.get_equipment_reps(self._equipment_id))

    async def async_set_native_value(self, value: float) -> None:
        self._coordinator.set_equipment_reps(self._equipment_id, int(value))
