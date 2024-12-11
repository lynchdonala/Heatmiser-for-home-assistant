# SPDX-License-Identifier: Apache-2.0 OR GPL-2.0-only

"""Heatmiser Neo Sensors via Heatmiser Neo-hub."""

from collections.abc import Callable
from dataclasses import dataclass
import datetime
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
from .helpers import profile_level

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

    value_fn: Callable[[HeatmiserNeoEntity], Any]
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
            int(device.data.hold_time.total_seconds() / 60)
            if device.data.hold_on
            else None
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
        value_fn=lambda device: device.data.temperature,
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
        value_fn=lambda device: device.data.temperature,
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
        value_fn=lambda device: device.data.temperature,
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
        value_fn=lambda device: device.data.current_floor_temperature,
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
        value_fn=lambda device: device.data.hold_temp,
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
        value_fn=lambda device: device.data.hold_cool,
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
        value_fn=lambda device: HEATMISER_FAN_SPEED_HA_FAN_MODE.get(
            device.data.fan_speed
        ),
        setup_filter_fn=lambda device, _: (
            device.device_type in HEATMISER_TYPE_IDS_HC and not device.time_clock_mode
        ),
    ),
    HeatmiserNeoSensorEntityDescription(
        key="heatmiser_neo_profile_current_temp",
        device_class=SensorDeviceClass.TEMPERATURE,
        name="Profile Current Temperature",
        value_fn=lambda device: _profile_current_temp(
            device.data.active_profile, device
        ),
        setup_filter_fn=lambda device, _: (
            device.device_type in HEATMISER_TYPE_IDS_THERMOSTAT_NOT_HC
            and not device.time_clock_mode
        ),
        unit_of_measurement_fn=lambda _, sys_data: (
            HEATMISER_TEMPERATURE_UNIT_HA_UNIT.get(sys_data.CORF, None)
        ),
    ),
    HeatmiserNeoSensorEntityDescription(
        key="heatmiser_neo_profile_next_temp",
        device_class=SensorDeviceClass.TEMPERATURE,
        name="Profile Next Temperature",
        value_fn=lambda device: _profile_next_temp(device.data.active_profile, device),
        setup_filter_fn=lambda device, _: (
            device.device_type in HEATMISER_TYPE_IDS_THERMOSTAT_NOT_HC
            and not device.time_clock_mode
        ),
        unit_of_measurement_fn=lambda _, sys_data: (
            HEATMISER_TEMPERATURE_UNIT_HA_UNIT.get(sys_data.CORF, None)
        ),
    ),
    HeatmiserNeoSensorEntityDescription(
        key="heatmiser_neo_profile_next_time",
        name="Profile Next Time",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda device: _profile_next_time(device.data.active_profile, device),
        setup_filter_fn=lambda device, _: (
            device.device_type in HEATMISER_TYPE_IDS_THERMOSTAT_NOT_HC
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
    HeatmiserNeoHubSensorEntityDescription(
        key="heatmiser_neohub_holiday_end",
        device_class=SensorDeviceClass.TIMESTAMP,
        name="Holiday End",
        value_fn=lambda coordinator: _holiday_end(coordinator),
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
        return self.entity_description.value_fn(self)

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


def _profile_current_temp(profile_id, entity: HeatmiserNeoSensor) -> float | None:
    """Convert a profile id to current temperature."""
    level = profile_level(profile_id, entity.data, entity.coordinator)
    if level:
        return float(level[1])
    return None


def _profile_next_temp(profile_id, entity: HeatmiserNeoSensor) -> float | None:
    _, temp = _profile_next_level(profile_id, entity)
    if temp:
        return float(temp)
    return None


def _profile_next_time(profile_id, entity: HeatmiserNeoSensor) -> str | None:
    t, _ = _profile_next_level(profile_id, entity)
    if not t:
        return None
    device_time = entity.data._data_.TIME
    if len(device_time) == 4:
        device_time = f"0{device_time}"
    profile_time = datetime.datetime.strptime(t, "%H:%M")
    tz = entity.coordinator.system_data.TIME_ZONE
    if entity.coordinator.system_data.DST_ON:
        tz = tz + 1
    profile_datetime = datetime.datetime.now().replace(
        hour=profile_time.hour,
        minute=profile_time.minute,
        tzinfo=datetime.timezone(datetime.timedelta(minutes=tz * 60)),
    )
    if t < device_time:
        return profile_datetime + datetime.timedelta(days=1)
    return profile_datetime


def _profile_next_level(profile_id, entity: HeatmiserNeoSensor):
    """Convert a profile id to next level."""
    lv = profile_level(profile_id, entity.data, entity.coordinator, True)
    if lv:
        return lv[0], lv[1]
    return None, None


def _holiday_end(coordinator: HeatmiserNeoCoordinator) -> datetime.datetime | None:
    """Convert the holiday end to a datetime."""
    holiday = coordinator.live_data.HUB_HOLIDAY
    holiday_end = coordinator.live_data.HOLIDAY_END

    if not holiday:
        return None

    try:
        parsed_datetime = datetime.datetime.strptime(
            holiday_end, "%a %b %d %H:%M:%S %Y\n"
        )
        return parsed_datetime.replace(
            tzinfo=datetime.timezone(
                datetime.timedelta(minutes=coordinator.system_data.TIME_ZONE * 60)
            )
        )
    except ValueError:
        _LOGGER.exception("Failed to parse hub holiday end - %s", holiday_end)
        return None
