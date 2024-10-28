# SPDX-License-Identifier: Apache-2.0 OR GPL-2.0-only
"""The Heatmiser Neo base entity definitions."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
import logging

from neohubapi.neohub import NeoHub, NeoStat

from homeassistant.core import ServiceCall
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, HEATMISER_PRODUCT_LIST
from .coordinator import HeatmiserNeoCoordinator

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class HeatmiserNeoEntityDescription(EntityDescription):
    """Describes Heatmiser Neo entity."""

    setup_filter_fn: Callable[[NeoStat], bool] = lambda _: True
    availability_fn: Callable[[NeoStat], bool] = lambda device: not device.offline
    # extra_attrs: list[str] | None = None
    custom_functions: (
        dict[str, Callable[[NeoStat, NeoHub, ServiceCall], Awaitable[None]]] | None
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
        (devices, _) = self.coordinator.data
        neo_devices = {device.name: device for device in devices["neo_devices"]}
        return neo_devices[self._neodevice.name]

    @property
    def system_data(self):
        """Helper to get the data for the current device."""
        (_, system_data) = self.coordinator.data
        return system_data

    @property
    def available(self):
        """Returns whether the entity is available or not."""
        return self.entity_description.availability_fn(self.data)

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
            self.data, self._hub, service_call
        )


async def call_custom_action(
    entity: HeatmiserNeoEntity, service_call: ServiceCall
) -> None:
    """Call a custom action specified in the entity description."""
    await entity.call_custom_action(service_call)
