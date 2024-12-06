# SPDX-License-Identifier: Apache-2.0 OR GPL-2.0-only

"""Heatmiser Neo Sensors via Heatmiser Neo-hub."""

from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import Any

from neohubapi.neohub import NeoHub, NeoStat

from homeassistant.components.climate import (
    FAN_AUTO,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    FAN_OFF,
)
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HeatmiserNeoConfigEntry
from .const import (
    HEATMISER_FAN_SPEED_HA_FAN_MODE,
    HEATMISER_TEMPERATURE_UNIT_HA_UNIT,
    HEATMISER_TYPE_IDS_HC,
    HEATMISER_TYPE_IDS_HOLD,
    HEATMISER_TYPE_IDS_THERMOSTAT,
    HEATMISER_TYPE_IDS_THERMOSTAT_NOT_HC,
)
from .coordinator import HeatmiserNeoCoordinator
from .entity import (
    HeatmiserNeoEntity,
    HeatmiserNeoEntityDescription,
    HeatmiserNeoHubEntity,
    HeatmiserNeoHubEntityDescription,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HeatmiserNeoConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Heatmiser Neo Sensor entities."""
    hub = entry.runtime_data.hub
    coordinator = entry.runtime_data.coordinator

    if coordinator.data is None:
        _LOGGER.error("Coordinator data is None. Cannot set up sensor entities")
        return

    neo_devices, _ = coordinator.data
    system_data = coordinator.system_data

    _LOGGER.info("Adding Neo Sensors")

    async_add_entities(
        HeatmiserNeoSensor(neodevice, coordinator, hub, description)
        for description in SENSORS
        for neodevice in neo_devices.values()
        if description.setup_filter_fn(neodevice, system_data)
    )

    async_add_entities(
        HeatmiserNeoHubSensor(coordinator, hub, description)
        for description in HUB_SENSORS
        if description.setup_filter_fn(coordinator)
    )


@dataclass(frozen=True, kw_only=True)
class HeatmiserNeoSensorEntityDescription(
    HeatmiserNeoEntityDescription, SensorEntityDescription
):
    """Describes a button entity."""

    value_fn: Callable[[NeoStat], Any]
    unit_of_measurement_fn: Callable[[NeoStat, Any], Any] | None = None


@dataclass(frozen=True, kw_only=True)
class HeatmiserNeoHubSensorEntityDescription(
    HeatmiserNeoHubEntityDescription, SensorEntityDescription
):
    """Describes a button entity."""

    value_fn: Callable[[HeatmiserNeoCoordinator], Any]


SENSORS: tuple[HeatmiserNeoSensorEntityDescription, ...] = (
    HeatmiserNeoSensorEntityDescription(
        key="heatmiser_neo_hold_time_sensor",
        name="Hold Time Remaining",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        value_fn=lambda device: (
            int(device.hold_time.total_seconds() / 60) if device.hold_on else 0
        ),
        setup_filter_fn=lambda device, _: (
            device.device_type in HEATMISER_TYPE_IDS_HOLD
        ),
    ),
    HeatmiserNeoSensorEntityDescription(
        key="heatmiser_neo_temperature_sensor",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        name=None,  # This is the main entity of the device
        value_fn=lambda device: device.temperature,
        setup_filter_fn=lambda device, _: device.device_type == 14,
        unit_of_measurement_fn=lambda _, sys_data: (
            HEATMISER_TEMPERATURE_UNIT_HA_UNIT.get(sys_data.CORF, None)
        ),
    ),
    HeatmiserNeoSensorEntityDescription(
        key="heatmiser_neo_stat_current_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        name="Current Temperature",
        value_fn=lambda device: device.temperature,
        setup_filter_fn=lambda device, _: (
            device.device_type in HEATMISER_TYPE_IDS_THERMOSTAT
            and not device.time_clock_mode
        ),
        unit_of_measurement_fn=lambda _, sys_data: (
            HEATMISER_TEMPERATURE_UNIT_HA_UNIT.get(sys_data.CORF, None)
        ),
    ),
    HeatmiserNeoSensorEntityDescription(
        key="heatmiser_neo_timer_device_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        name="Device Temperature",
        value_fn=lambda device: device.temperature,
        setup_filter_fn=lambda device, _: (
            device.device_type in HEATMISER_TYPE_IDS_THERMOSTAT
            and device.time_clock_mode
        ),
        unit_of_measurement_fn=lambda _, sys_data: (
            HEATMISER_TEMPERATURE_UNIT_HA_UNIT.get(sys_data.CORF, None)
        ),
    ),
    HeatmiserNeoSensorEntityDescription(
        key="heatmiser_neo_stat_floor_temp",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        name="Floor Temperature",
        value_fn=lambda device: device.current_floor_temperature,
        setup_filter_fn=lambda device, _: (
            device.device_type in HEATMISER_TYPE_IDS_THERMOSTAT
            and not device.time_clock_mode
            and device.current_floor_temperature < 127
        ),
        unit_of_measurement_fn=lambda _, sys_data: (
            HEATMISER_TEMPERATURE_UNIT_HA_UNIT.get(sys_data.CORF, None)
        ),
    ),
    HeatmiserNeoSensorEntityDescription(
        key="heatmiser_neo_stat_hold_temp",
        device_class=SensorDeviceClass.TEMPERATURE,
        name="Hold Temperature",
        value_fn=lambda device: device.hold_temp,
        setup_filter_fn=lambda device, sys_data: (
            (
                device.device_type in HEATMISER_TYPE_IDS_THERMOSTAT_NOT_HC
                or (
                    device.device_type in HEATMISER_TYPE_IDS_HC
                    and sys_data.GLOBAL_SYSTEM_TYPE != "CoolOnly"
                )
            )
            and not device.time_clock_mode
        ),
        unit_of_measurement_fn=lambda _, sys_data: (
            HEATMISER_TEMPERATURE_UNIT_HA_UNIT.get(sys_data.CORF, None)
        ),
    ),
    HeatmiserNeoSensorEntityDescription(
        key="heatmiser_neo_stat_hold_temp_cool",
        device_class=SensorDeviceClass.TEMPERATURE,
        name="Hold Cooling Temperature",
        value_fn=lambda device: device.hold_cool,
        setup_filter_fn=lambda device, sys_data: (
            device.device_type in HEATMISER_TYPE_IDS_HC
            and not device.time_clock_mode
            and sys_data.GLOBAL_SYSTEM_TYPE != "HeatOnly"
        ),
        unit_of_measurement_fn=lambda _, sys_data: (
            HEATMISER_TEMPERATURE_UNIT_HA_UNIT.get(sys_data.CORF, None)
        ),
    ),
    HeatmiserNeoSensorEntityDescription(
        key="heatmiser_neo_stat_hc_fan_speed",
        device_class=SensorDeviceClass.ENUM,
        options=[FAN_OFF, FAN_HIGH, FAN_MEDIUM, FAN_LOW, FAN_AUTO],
        name="Fan Speed",
        value_fn=lambda device: HEATMISER_FAN_SPEED_HA_FAN_MODE.get(device.fan_speed),
        setup_filter_fn=lambda device, _: (
            device.device_type in HEATMISER_TYPE_IDS_HC and not device.time_clock_mode
        ),
    ),
)

HUB_SENSORS: tuple[HeatmiserNeoHubSensorEntityDescription, ...] = (
    HeatmiserNeoHubSensorEntityDescription(
        key="heatmiser_neohub_zigbee_channel",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        name="ZigBee Channel",
        value_fn=lambda coordinator: coordinator.system_data.ZIGBEE_CHANNEL,
    ),
)


class HeatmiserNeoSensor(HeatmiserNeoEntity, SensorEntity):
    """Heatmiser Neo button entity."""

    def __init__(
        self,
        neostat: NeoStat,
        coordinator: HeatmiserNeoCoordinator,
        hub: NeoHub,
        entity_description: HeatmiserNeoSensorEntityDescription,
    ) -> None:
        """Initialize Heatmiser Neo button entity."""
        super().__init__(
            neostat,
            coordinator,
            hub,
            entity_description,
        )

    @property
    def native_value(self):
        """Return the sensors temperature value."""
        return self.entity_description.value_fn(self.data)

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the unit of measurement."""
        if self.entity_description.unit_of_measurement_fn:
            return self.entity_description.unit_of_measurement_fn(
                self.data, self.system_data
            )

        return self.entity_description.native_unit_of_measurement


class HeatmiserNeoHubSensor(HeatmiserNeoHubEntity, SensorEntity):
    """Heatmiser Neo button entity."""

    def __init__(
        self,
        coordinator: HeatmiserNeoCoordinator,
        hub: NeoHub,
        entity_description: HeatmiserNeoSensorEntityDescription,
    ) -> None:
        """Initialize Heatmiser Neo button entity."""
        super().__init__(
            coordinator,
            hub,
            entity_description,
        )

    @property
    def native_value(self):
        """Return the sensors temperature value."""
        return self.entity_description.value_fn(self.coordinator)
