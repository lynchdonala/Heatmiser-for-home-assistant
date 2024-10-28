# SPDX-License-Identifier: Apache-2.0 OR GPL-2.0-only

"""Heatmiser Neo Sensors via Heatmiser Neo-hub."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import Any

from neohubapi.neohub import NeoHub, NeoStat

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import COORDINATOR, DOMAIN, HEATMISER_TEMPERATURE_UNIT_HA_UNIT, HUB
from .entity import HeatmiserNeoEntity, HeatmiserNeoEntityDescription

_LOGGER = logging.getLogger(__name__)

SENSORS_ENABLED = True
OFFLINE_SENSOR_ENABLED = True
ICON_BATTERY_LOW = "mdi:battery-low"
ICON_BATTERY_OFF = "mdi:battery-off"
ICON_BATTERY_FULL = "mdi:battery"
ICON_NETWORK_OFFLINE = "mdi:network-off-outline"
ICON_NETWORK_ONLINE = "mdi:network-outline"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Heatmiser Neo Sensor entities."""
    hub = hass.data[DOMAIN][entry.entry_id][HUB]
    coordinator = hass.data[DOMAIN][entry.entry_id][COORDINATOR]

    if coordinator.data is None:
        _LOGGER.error("Coordinator data is None. Cannot set up sensor entities")
        return

    devices_data, _ = coordinator.data

    neo_devices = {device.name: device for device in devices_data["neo_devices"]}

    _LOGGER.info("Adding Neo Sensors")

    async_add_entities(
        HeatmiserNeoSensor(neodevice, coordinator, hub, description)
        for description in SENSORS
        for neodevice in neo_devices.values()
        if description.setup_filter_fn(neodevice)
    )


@dataclass(frozen=True, kw_only=True)
class HeatmiserNeoSensorEntityDescription(
    HeatmiserNeoEntityDescription, SensorEntityDescription
):
    """Describes a button entity."""

    value_fn: Callable[[NeoStat], Any]
    unit_of_measurement_fn: Callable[[NeoStat, Any], Any] | None = None


SENSORS: tuple[HeatmiserNeoSensorEntityDescription, ...] = (
    HeatmiserNeoSensorEntityDescription(
        key="heatmiser_neo_hold_time_sensor",
        name="Hold Time Remaining",
        value_fn=lambda device: device.hold_time
        if device.hold_on
        else timedelta(seconds=0),
        setup_filter_fn=lambda device: device.device_type in [1, 2, 6, 7, 12, 13],
    ),
    HeatmiserNeoSensorEntityDescription(
        key="heatmiser_neo_temperature_sensor",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        name=None,  # This is the main entity of the device
        value_fn=lambda device: device.temperature,
        setup_filter_fn=lambda device: device.device_type == 14,
        unit_of_measurement_fn=lambda _,
        sys_data: HEATMISER_TEMPERATURE_UNIT_HA_UNIT.get(sys_data.CORF, None),
    ),
    HeatmiserNeoSensorEntityDescription(
        key="heatmiser_neo_stat_current_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        name="Current Temperature",
        value_fn=lambda device: device.temperature,
        setup_filter_fn=lambda device: device.device_type in [1, 2, 7, 12, 13]
        and not device.time_clock_mode,
        unit_of_measurement_fn=lambda _,
        sys_data: HEATMISER_TEMPERATURE_UNIT_HA_UNIT.get(sys_data.CORF, None),
    ),
    HeatmiserNeoSensorEntityDescription(
        key="heatmiser_neo_timer_device_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        name="Device Temperature",
        value_fn=lambda device: device.temperature,
        setup_filter_fn=lambda device: device.device_type in [1, 2, 7, 12, 13]
        and device.time_clock_mode,
        unit_of_measurement_fn=lambda _,
        sys_data: HEATMISER_TEMPERATURE_UNIT_HA_UNIT.get(sys_data.CORF, None),
    ),
    HeatmiserNeoSensorEntityDescription(
        key="heatmiser_neo_stat_floor_temp",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        name="Floor Temperature",
        value_fn=lambda device: device.floor_temperature,
        setup_filter_fn=lambda device: device.device_type in [1, 2, 7, 12, 13]
        and not device.time_clock_mode,
        unit_of_measurement_fn=lambda _,
        sys_data: HEATMISER_TEMPERATURE_UNIT_HA_UNIT.get(sys_data.CORF, None),
    ),
    HeatmiserNeoSensorEntityDescription(
        key="heatmiser_neo_stat_hold_temp",
        device_class=SensorDeviceClass.TEMPERATURE,
        name="Hold Temperature",
        value_fn=lambda device: device.hold_temp,
        setup_filter_fn=lambda device: device.device_type in [1, 2, 7, 12, 13]
        and not device.time_clock_mode,
        unit_of_measurement_fn=lambda _,
        sys_data: HEATMISER_TEMPERATURE_UNIT_HA_UNIT.get(sys_data.CORF, None),
    ),
)


class HeatmiserNeoSensor(HeatmiserNeoEntity, SensorEntity):
    """Heatmiser Neo button entity."""

    def __init__(
        self,
        neostat: NeoStat,
        coordinator: DataUpdateCoordinator,
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
