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

from . import HeatmiserNeoConfigEntry
from .const import (
    HEATMISER_TYPE_IDS_AWAY,
    HEATMISER_TYPE_IDS_HOLD,
    HEATMISER_TYPE_IDS_STANDBY,
    HEATMISER_TYPE_IDS_THERMOSTAT,
    HEATMISER_TYPE_IDS_THERMOSTAT_NOT_HC,
    HEATMISER_TYPE_IDS_TIMER,
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
    """Set up Heatmiser Neo Binary Sensor entities."""
    hub = entry.runtime_data.hub
    coordinator = entry.runtime_data.coordinator

    if coordinator.data is None:
        _LOGGER.error("Coordinator data is None. Cannot set up sensor entities")
        return

    neo_devices, _ = coordinator.data
    system_data = coordinator.system_data

    _LOGGER.info("Adding Neo Binary Sensors")

    async_add_entities(
        HeatmiserNeoBinarySensor(neodevice, coordinator, hub, description)
        for description in BINARY_SENSORS
        for neodevice in neo_devices.values()
        if description.setup_filter_fn(neodevice, system_data)
    )

    async_add_entities(
        HeatmiserNeoHubBinarySensor(coordinator, hub, description)
        for description in HUB_BINARY_SENSORS
        if description.setup_filter_fn(coordinator)
    )


@dataclass(frozen=True, kw_only=True)
class HeatmiserNeoBinarySensorEntityDescription(
    HeatmiserNeoEntityDescription, BinarySensorEntityDescription
):
    """Describes a button entity."""

    value_fn: Callable[[HeatmiserNeoEntity], bool]


@dataclass(frozen=True, kw_only=True)
class HeatmiserNeoHubBinarySensorEntityDescription(
    HeatmiserNeoHubEntityDescription, BinarySensorEntityDescription
):
    """Describes a button entity."""

    value_fn: Callable[[HeatmiserNeoCoordinator], bool]


BINARY_SENSORS: tuple[HeatmiserNeoBinarySensorEntityDescription, ...] = (
    HeatmiserNeoBinarySensorEntityDescription(
        key="device_offline_sensor",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        availability_fn=lambda _: True,
        value_fn=lambda device: not device.data.offline,
    ),
    HeatmiserNeoBinarySensorEntityDescription(
        key="heatmiser_neo_contact_sensor",
        device_class=BinarySensorDeviceClass.OPENING,
        name=None,  # This is the main entity of the device
        value_fn=lambda device: bool(device.data.window_open),
        setup_filter_fn=lambda device, _: device.device_type == 5,
    ),
    HeatmiserNeoBinarySensorEntityDescription(
        key="heatmiser_neo_device_hold_active",
        entity_category=EntityCategory.DIAGNOSTIC,
        name="Hold Active",
        value_fn=lambda device: device.data.hold_on,
        setup_filter_fn=lambda device, _: (
            device.device_type in HEATMISER_TYPE_IDS_HOLD,
        ),
    ),
    HeatmiserNeoBinarySensorEntityDescription(
        key="heatmiser_neo_battery_level_sensor",
        device_class=BinarySensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda device: device.data.low_battery,
        setup_filter_fn=lambda device, _: device.battery_powered,
    ),
    HeatmiserNeoBinarySensorEntityDescription(
        key="heatmiser_neo_device_timer_output_active",
        name="Output",
        value_fn=lambda device: device.data.timer_on,
        setup_filter_fn=lambda device, _: (
            device.device_type in HEATMISER_TYPE_IDS_TIMER and device.time_clock_mode
        ),
    ),
    HeatmiserNeoBinarySensorEntityDescription(
        key="heatmiser_neo_device_away",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        name="Away",
        value_fn=lambda device: device.data.away,
        setup_filter_fn=lambda device, _: (
            device.device_type in HEATMISER_TYPE_IDS_AWAY
        ),
    ),
    HeatmiserNeoBinarySensorEntityDescription(
        key="heatmiser_neo_device_standby",
        entity_category=EntityCategory.DIAGNOSTIC,
        name="Standby",
        value_fn=lambda device: device.data.standby,
        setup_filter_fn=lambda device, _: (
            device.device_type in HEATMISER_TYPE_IDS_STANDBY
        ),
    ),
    HeatmiserNeoBinarySensorEntityDescription(
        key="heatmiser_neo_device_holiday",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        name="Holiday",
        value_fn=lambda device: device.data.holiday,
        setup_filter_fn=lambda device, _: (
            device.device_type in HEATMISER_TYPE_IDS_AWAY
        ),
    ),
    HeatmiserNeoBinarySensorEntityDescription(
        key="heatmiser_neo_floor_limit",
        entity_category=EntityCategory.DIAGNOSTIC,
        name="Floor Limit Reached",
        value_fn=lambda device: device.data.floor_limit,
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
        value_fn=lambda device: device.data.temporary_set_flag,
        setup_filter_fn=lambda device, _: (
            device.device_type in HEATMISER_TYPE_IDS_THERMOSTAT
        ),
    ),
    HeatmiserNeoBinarySensorEntityDescription(
        key="heatmiser_neo_profile_current_state",
        name="Profile State",
        value_fn=lambda device: _profile_current_state(
            device.data.active_profile, device
        ),
        setup_filter_fn=lambda device, _: (
            device.device_type in HEATMISER_TYPE_IDS_THERMOSTAT_NOT_HC
            and device.time_clock_mode
        ),
    ),
)

HUB_BINARY_SENSORS: tuple[HeatmiserNeoHubBinarySensorEntityDescription, ...] = (
    HeatmiserNeoHubBinarySensorEntityDescription(
        key="heatmiser_neohub_dst_on",
        name="DST",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda coordinator: coordinator.system_data.DST_ON,
    ),
    HeatmiserNeoHubBinarySensorEntityDescription(
        key="heatmiser_neohub_away",
        name="Away",
        value_fn=lambda coordinator: coordinator.live_data.HUB_AWAY,
    ),
    HeatmiserNeoHubBinarySensorEntityDescription(
        key="heatmiser_neohub_holiday",
        name="Holiday",
        value_fn=lambda coordinator: coordinator.live_data.HUB_HOLIDAY,
    ),
)


class HeatmiserNeoBinarySensor(HeatmiserNeoEntity, BinarySensorEntity):
    """Heatmiser Neo binary entity."""

    def __init__(
        self,
        neostat: NeoStat,
        coordinator: HeatmiserNeoCoordinator,
        hub: NeoHub,
        entity_description: HeatmiserNeoBinarySensorEntityDescription,
    ) -> None:
        """Initialize Heatmiser Neo binary entity."""
        super().__init__(
            neostat,
            coordinator,
            hub,
            entity_description,
        )

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        return self.entity_description.value_fn(self)


class HeatmiserNeoHubBinarySensor(HeatmiserNeoHubEntity, BinarySensorEntity):
    """Heatmiser Neo binary entity."""

    def __init__(
        self,
        coordinator: HeatmiserNeoCoordinator,
        hub: NeoHub,
        entity_description: HeatmiserNeoHubBinarySensorEntityDescription,
    ) -> None:
        """Initialize Heatmiser Neo binary entity."""
        super().__init__(
            coordinator,
            hub,
            entity_description,
        )

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        return self.entity_description.value_fn(self.coordinator)


def _profile_current_state(profile_id, entity: HeatmiserNeoEntity) -> bool | None:
    """Convert a profile id to current temperature."""
    level = profile_level(profile_id, entity.data, entity.coordinator)
    if level:
        return level[1]
    return None
