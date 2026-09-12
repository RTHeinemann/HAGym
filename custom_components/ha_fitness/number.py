"""Number platform for HAGym."""
from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfLength, UnitOfMass
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
    """Set up HAGym number entities from a config entry."""
    coordinator: HAFitnessCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[NumberEntity] = [
        HAFitnessWeightNumber(coordinator, entry),
        HAFitnessRepsNumber(coordinator, entry),
        HAFitnessDurationMinutesNumber(coordinator, entry),
        HAFitnessDistanceKmNumber(coordinator, entry),
        HAFitnessCaloriesNumber(coordinator, entry),
        HAFitnessStepsNumber(coordinator, entry),
        HAFitnessAverageHeartRateNumber(coordinator, entry),
        HAFitnessMaxHeartRateNumber(coordinator, entry),
        HAFitnessAddedWeightNumber(coordinator, entry),
    ]

    # Per-user bodyweight number entities
    try:
        persons = await coordinator.list_persons()
        for person in persons:
            if person.get("in_hagym"):
                entities.append(HAFitnessUserBodyweightNumber(coordinator, entry, person))
    except Exception:
        pass

    async_add_entities(entities)


class _HAFitnessNumberBase(NumberEntity):
    """Base class for HAGym number entities."""

    _attr_has_entity_name = True
    _attr_mode = NumberMode.BOX

    def __init__(
        self, coordinator: HAFitnessCoordinator, entry: ConfigEntry
    ) -> None:
        self._coordinator = coordinator
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=coordinator.display_name,
            manufacturer="HAGym",
            model="HAGym Tracker",
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


class HAFitnessDurationMinutesNumber(_HAFitnessNumberBase):
    """Number entity for activity duration input in minutes."""

    _attr_translation_key = "duration_minutes"
    _attr_native_min_value = 0
    _attr_native_max_value = 600
    _attr_native_step = 0.5
    _attr_native_unit_of_measurement = "min"

    def __init__(self, coordinator: HAFitnessCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_duration_minutes"

    @property
    def native_value(self) -> float:
        return self._coordinator.duration_minutes

    async def async_set_native_value(self, value: float) -> None:
        self._coordinator.set_duration_minutes(value)


class HAFitnessDistanceKmNumber(_HAFitnessNumberBase):
    """Number entity for activity distance input in kilometers."""

    _attr_translation_key = "distance_km"
    _attr_native_min_value = 0
    _attr_native_max_value = 500
    _attr_native_step = 0.1
    _attr_native_unit_of_measurement = UnitOfLength.KILOMETERS

    def __init__(self, coordinator: HAFitnessCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_distance_km"

    @property
    def native_value(self) -> float:
        return self._coordinator.distance_km

    async def async_set_native_value(self, value: float) -> None:
        self._coordinator.set_distance_km(value)


class HAFitnessCaloriesNumber(_HAFitnessNumberBase):
    """Number entity for calories input."""

    _attr_translation_key = "calories"
    _attr_native_min_value = 0
    _attr_native_max_value = 5000
    _attr_native_step = 1
    _attr_native_unit_of_measurement = "kcal"

    def __init__(self, coordinator: HAFitnessCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_calories"

    @property
    def native_value(self) -> float:
        return self._coordinator.calories

    async def async_set_native_value(self, value: float) -> None:
        self._coordinator.set_calories(value)


class HAFitnessStepsNumber(_HAFitnessNumberBase):
    """Number entity for steps input."""

    _attr_translation_key = "steps"
    _attr_native_min_value = 0
    _attr_native_max_value = 100000
    _attr_native_step = 100
    _attr_native_unit_of_measurement = "steps"

    def __init__(self, coordinator: HAFitnessCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_steps"

    @property
    def native_value(self) -> float:
        return float(self._coordinator.steps)

    async def async_set_native_value(self, value: float) -> None:
        self._coordinator.set_steps(int(value))


class HAFitnessAverageHeartRateNumber(_HAFitnessNumberBase):
    """Number entity for average heart rate input."""

    _attr_translation_key = "avg_heart_rate"
    _attr_native_min_value = 0
    _attr_native_max_value = 240
    _attr_native_step = 1
    _attr_native_unit_of_measurement = "bpm"

    def __init__(self, coordinator: HAFitnessCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_avg_heart_rate"

    @property
    def native_value(self) -> float:
        return self._coordinator.avg_heart_rate

    async def async_set_native_value(self, value: float) -> None:
        self._coordinator.set_avg_heart_rate(value)


class HAFitnessMaxHeartRateNumber(_HAFitnessNumberBase):
    """Number entity for maximum heart rate input."""

    _attr_translation_key = "max_heart_rate"
    _attr_native_min_value = 0
    _attr_native_max_value = 240
    _attr_native_step = 1
    _attr_native_unit_of_measurement = "bpm"

    def __init__(self, coordinator: HAFitnessCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_max_heart_rate"

    @property
    def native_value(self) -> float:
        return self._coordinator.max_heart_rate

    async def async_set_native_value(self, value: float) -> None:
        self._coordinator.set_max_heart_rate(value)


class HAFitnessAddedWeightNumber(_HAFitnessNumberBase):
    """Number entity for optional bodyweight added load."""

    _attr_translation_key = "added_weight"
    _attr_native_min_value = 0
    _attr_native_max_value = 300
    _attr_native_step = 0.5
    _attr_native_unit_of_measurement = UnitOfMass.KILOGRAMS

    def __init__(self, coordinator: HAFitnessCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_added_weight"

    @property
    def native_value(self) -> float:
        return self._coordinator.added_weight

    async def async_set_native_value(self, value: float) -> None:
        self._coordinator.set_added_weight(value)


class HAFitnessUserBodyweightNumber(_HAFitnessNumberBase):
    """Writable number entity for a single user's bodyweight (kg)."""

    _attr_translation_key = "user_bodyweight"
    _attr_native_min_value = 20
    _attr_native_max_value = 300
    _attr_native_step = 0.1
    _attr_native_unit_of_measurement = UnitOfMass.KILOGRAMS

    def __init__(
        self,
        coordinator: HAFitnessCoordinator,
        entry: ConfigEntry,
        user: dict[str, Any],
    ) -> None:
        super().__init__(coordinator, entry)
        self._user_id = user["id"]
        self._attr_unique_id = f"{entry.entry_id}_user_{self._user_id}_bodyweight"

    @property
    def native_value(self) -> float | None:
        return self._coordinator.get_user_bodyweight(self._user_id)

    async def async_set_native_value(self, value: float) -> None:
        await self._coordinator.async_set_user_bodyweight(self._user_id, value, "number_entity")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"user_id": self._user_id}
