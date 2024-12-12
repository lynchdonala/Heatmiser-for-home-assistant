# SPDX-License-Identifier: Apache-2.0 OR GPL-2.0-only
"""The Heatmiser Neo base entity definitions."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from functools import partial
import logging
from typing import Any

from neohubapi.neohub import ATTR_SYSTEM, NeoHub, NeoStat

from homeassistant.core import ServiceCall
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    HEATMISER_HUB_PRODUCT_LIST,
    HEATMISER_PRODUCT_LIST,
    HEATMISER_TYPE_IDS_AWAY,
)
from .coordinator import HeatmiserNeoCoordinator
from .helpers import cancel_holiday, set_away

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class HeatmiserNeoEntityDescription(EntityDescription):
    """Describes Heatmiser Neo entity."""

    setup_filter_fn: Callable[[NeoStat, Any], bool] = lambda dev, sys_data: True
    availability_fn: Callable[[NeoStat], bool] = lambda device: not device.offline
    icon_fn: Callable[[NeoStat], str | None] | None = None
    # extra_attrs: list[str] | None = None
    custom_functions: (
        dict[str, Callable[[type[HeatmiserNeoEntity], ServiceCall], Awaitable[None]]]
        | None
    ) = None


@dataclass(frozen=True, kw_only=True)
class HeatmiserNeoHubEntityDescription(EntityDescription):
    """Describes Heatmiser Neo Hub entity."""

    setup_filter_fn: Callable[[HeatmiserNeoCoordinator], bool] = (
        lambda coordinator: True
    )
    icon_fn: Callable[[NeoStat], str | None] | None = None
    # extra_attrs: list[str] | None = None
    custom_functions: (
        dict[str, Callable[[type[HeatmiserNeoEntity], ServiceCall], Awaitable[None]]]
        | None
    ) = None


class HeatmiserNeoEntity(CoordinatorEntity[HeatmiserNeoCoordinator]):
    """Defines a base HeatmiserNeo entity."""

    entity_description: HeatmiserNeoEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        neodevice: NeoStat,
        coordinator: HeatmiserNeoCoordinator,
        hub: NeoHub,
        entity_description: HeatmiserNeoEntityDescription,
    ) -> None:
        """Initialize the HeatmiserNeo entity."""
        super().__init__(coordinator)
        _LOGGER.debug(
            "Creating %s-%s for %s %s",
            type(self).__name__,
            entity_description.key,
            neodevice.name,
            neodevice.device_id,
        )
        self._key = entity_description.key
        self._neodevice = neodevice
        self._hub = hub
        self.entity_description = entity_description

    @property
    def data(self) -> NeoStat | None:
        """Helper to get the data for the current device."""
        (neo_devices, _) = self.coordinator.data
        return neo_devices.get(self._neodevice.name, None)

    @property
    def system_data(self):
        """Helper to get the data for the current device."""
        (_, all_data) = self.coordinator.data
        return all_data[ATTR_SYSTEM]

    @property
    def available(self):
        """Returns whether the entity is available or not."""
        if self.data:
            return self.entity_description.availability_fn(self.data)
        return False

    @property
    def unique_id(self) -> str:
        """Return the unique ID for this entity."""
        return f"{self._neodevice.name}_{self.coordinator.serial_number}_{self._neodevice.serial_number}_{self._key}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this Heatmiser Neo instance."""
        return DeviceInfo(
            identifiers={
                (
                    DOMAIN,
                    f"{self.coordinator.serial_number}_{self._neodevice.serial_number}",
                )
            },
            name=self._neodevice.name,
            manufacturer="Heatmiser",
            model=f"{HEATMISER_PRODUCT_LIST[self.data.device_type]}",
            suggested_area=self._neodevice.name,
            serial_number=self._neodevice.serial_number,
            sw_version=self.data.stat_version,
            via_device=(DOMAIN, self.coordinator.serial_number),
        )

    @property
    def extra_state_attributes(self):
        """Return the additional state attributes."""
        return {
            "device_id": self._neodevice.device_id,
            "device_type": self._neodevice.device_type,
            "offline": self.data.offline,
        }

    @property
    def should_poll(self) -> bool:
        """Don't poll - we fetch the data from the hub all at once."""
        return False

    @property
    def icon(self) -> str | None:
        """Call icon function if defined."""
        if self.entity_description.icon_fn:
            return self.entity_description.icon_fn(self.data)
        return None

    async def call_custom_action(self, service_call: ServiceCall) -> None:
        """Call a custom action specified in the entity description."""
        if service_call.service not in self.entity_description.custom_functions:
            _LOGGER.debug(
                "%s not defined in custom functions for entity %s",
                service_call.service,
                self.entity_id,
            )
            return
        await self.entity_description.custom_functions.get(service_call.service)(
            self, service_call
        )

    async def async_cancel_away_or_holiday(self) -> None:
        """Cancel away/holiday mode."""
        if _device_supports_away(self.data):
            dev = self.data
            if dev.away:
                await self._hub.set_away(False)
                self.coordinator.update_in_memory_state(
                    partial(set_away, False),
                    _device_supports_away,
                )
            if dev.holiday:
                await self._hub.cancel_holiday(False)
                self.coordinator.update_in_memory_state(
                    cancel_holiday,
                    _device_supports_away,
                )

    async def async_set_away_mode(self) -> None:
        """Set away mode."""
        if _device_supports_away(self.data):
            dev = self.data
            if not (dev.away or dev.holiday):
                await self._hub.set_away(True)
                self.coordinator.update_in_memory_state(
                    partial(set_away, True), _device_supports_away
                )


class HeatmiserNeoHubEntity(CoordinatorEntity[HeatmiserNeoCoordinator]):
    """Defines a base HeatmiserNeoHub entity."""

    entity_description: HeatmiserNeoHubEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: HeatmiserNeoCoordinator,
        hub: NeoHub,
        entity_description: HeatmiserNeoHubEntityDescription,
    ) -> None:
        """Initialize the HeatmiserNeoHub entity."""
        super().__init__(coordinator)
        _LOGGER.debug(
            "Creating %s-%s",
            type(self).__name__,
            entity_description.key,
        )
        self._key = entity_description.key
        self._hub = hub
        self.entity_description = entity_description

    @property
    def available(self):
        """Returns whether the entity is available or not."""
        return True

    @property
    def unique_id(self) -> str:
        """Return the unique ID for this entity."""
        return f"{self.coordinator.serial_number}_{self._key}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this Heatmiser Neo instance."""
        return DeviceInfo(
            identifiers={
                (
                    DOMAIN,
                    f"{self.coordinator.serial_number}",
                )
            },
            name=f"NeoHub - {self._hub._host}",  # noqa: SLF001
            manufacturer="Heatmiser",
            model=f"{HEATMISER_HUB_PRODUCT_LIST[self.coordinator.system_data.HUB_TYPE]}",
            serial_number=self.coordinator.serial_number,
            sw_version=self.coordinator.system_data.HUB_VERSION,
        )

    @property
    def should_poll(self) -> bool:
        """Don't poll - we fetch the data from the hub all at once."""
        return False

    @property
    def icon(self) -> str | None:
        """Call icon function if defined."""
        if self.entity_description.icon_fn:
            return self.entity_description.icon_fn(self.data)
        return None


async def call_custom_action(
    entity: HeatmiserNeoEntity, service_call: ServiceCall
) -> None:
    """Call a custom action specified in the entity description."""
    await entity.call_custom_action(service_call)


def _device_supports_away(dev: NeoStat) -> bool:
    return dev.device_type in HEATMISER_TYPE_IDS_AWAY
