# SPDX-License-Identifier: Apache-2.0 OR GPL-2.0-only

"""Heatmiser Neo Binary Sensors via Heatmiser Neo-hub."""

from collections.abc import Callable
from dataclasses import dataclass
import logging

from neohubapi.neohub import NeoHub, NeoStat

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from . import HeatmiserNeoConfigEntry
from .const import (
    HEATMISER_TYPE_IDS_AWAY,
    HEATMISER_TYPE_IDS_HOLD,
    HEATMISER_TYPE_IDS_STANDBY,
    HEATMISER_TYPE_IDS_THERMOSTAT,
    HEATMISER_TYPE_IDS_TIMER,
)
from .entity import HeatmiserNeoEntity, HeatmiserNeoEntityDescription

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HeatmiserNeoConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Heatmiser Neo Binary Sensor entities."""
    hub = entry.runtime_data.hub
    coordinator = entry.runtime_data.coordinator

    if coordinator.data is None:
        _LOGGER.error("Coordinator data is None. Cannot set up sensor entities")
        return

    neo_devices, system_data = coordinator.data

    _LOGGER.info("Adding Neo Binary Sensors")

    async_add_entities(
        HeatmiserNeoBinarySensor(neodevice, coordinator, hub, description)
        for description in BINARY_SENSORS
        for neodevice in neo_devices.values()
        if description.setup_filter_fn(neodevice, system_data)
    )


@dataclass(frozen=True, kw_only=True)
class HeatmiserNeoBinarySensorEntityDescription(
    HeatmiserNeoEntityDescription, BinarySensorEntityDescription
):
    """Describes a button entity."""

    value_fn: Callable[[NeoStat], bool]


BINARY_SENSORS: tuple[HeatmiserNeoBinarySensorEntityDescription, ...] = (
    HeatmiserNeoBinarySensorEntityDescription(
        key="device_offline_sensor",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        availability_fn=lambda _: True,
        value_fn=lambda device: not device.offline,
    ),
    HeatmiserNeoBinarySensorEntityDescription(
        key="heatmiser_neo_contact_sensor",
        device_class=BinarySensorDeviceClass.OPENING,
        name=None,  # This is the main entity of the device
        value_fn=lambda device: bool(device.window_open),
        setup_filter_fn=lambda device, _: device.device_type == 5,
    ),
    HeatmiserNeoBinarySensorEntityDescription(
        key="heatmiser_neo_device_hold_active",
        entity_category=EntityCategory.DIAGNOSTIC,
        name="Hold Active",
        value_fn=lambda device: device.hold_on,
        setup_filter_fn=lambda device, _: (
            device.device_type in HEATMISER_TYPE_IDS_HOLD,
        ),
    ),
    HeatmiserNeoBinarySensorEntityDescription(
        key="heatmiser_neo_battery_level_sensor",
        device_class=BinarySensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda device: device.low_battery,
        setup_filter_fn=lambda device, _: device.battery_powered,
    ),
    HeatmiserNeoBinarySensorEntityDescription(
        key="heatmiser_neo_device_timer_output_active",
        name="Output",
        value_fn=lambda device: device.timer_on,
        setup_filter_fn=lambda device, _: (
            device.device_type in HEATMISER_TYPE_IDS_TIMER and device.time_clock_mode
        ),
    ),
    HeatmiserNeoBinarySensorEntityDescription(
        key="heatmiser_neo_device_away",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        name="Away",
        value_fn=lambda device: device.away,
        setup_filter_fn=lambda device, _: (
            device.device_type in HEATMISER_TYPE_IDS_AWAY
        ),
    ),
    HeatmiserNeoBinarySensorEntityDescription(
        key="heatmiser_neo_device_standby",
        entity_category=EntityCategory.DIAGNOSTIC,
        name="Standby",
        value_fn=lambda device: device.standby,
        setup_filter_fn=lambda device, _: (
            device.device_type in HEATMISER_TYPE_IDS_STANDBY
        ),
    ),
    HeatmiserNeoBinarySensorEntityDescription(
        key="heatmiser_neo_device_holiday",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        name="Holiday",
        value_fn=lambda device: device.holiday,
        setup_filter_fn=lambda device, _: (
            device.device_type in HEATMISER_TYPE_IDS_AWAY
        ),
    ),
    HeatmiserNeoBinarySensorEntityDescription(
        key="heatmiser_neo_floor_limit",
        entity_category=EntityCategory.DIAGNOSTIC,
        name="Floor Limit Reached",
        value_fn=lambda device: device.floor_limit,
        setup_filter_fn=lambda device, _: (
            device.device_type in HEATMISER_TYPE_IDS_THERMOSTAT
            and not device.time_clock_mode
            and device.current_floor_temperature < 127
        ),
    ),
    HeatmiserNeoBinarySensorEntityDescription(
        key="heatmiser_neo_temporary_set",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        name="Temporary Set",
        value_fn=lambda device: device.temporary_set_flag,
        setup_filter_fn=lambda device, _: (
            device.device_type in HEATMISER_TYPE_IDS_THERMOSTAT
        ),
    ),
)


class HeatmiserNeoBinarySensor(HeatmiserNeoEntity, BinarySensorEntity):
    """Heatmiser Neo button entity."""

    def __init__(
        self,
        neostat: NeoStat,
        coordinator: DataUpdateCoordinator,
        hub: NeoHub,
        entity_description: HeatmiserNeoBinarySensorEntityDescription,
    ) -> None:
        """Initialize Heatmiser Neo button entity."""
        super().__init__(
            neostat,
            coordinator,
            hub,
            entity_description,
        )

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        return self.entity_description.value_fn(self.data)
