# SPDX-License-Identifier: Apache-2.0 OR GPL-2.0-only

"""Heatmiser Neo Binary Sensors via Heatmiser Neo-hub."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
import logging
from typing import Any

from neohubapi.neohub import NeoHub, NeoStat

from homeassistant.components.lock import LockEntity, LockEntityDescription
from homeassistant.const import ATTR_CODE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HeatmiserNeoConfigEntry
from .const import HEATMISER_TYPE_IDS_LOCK
from .coordinator import HeatmiserNeoCoordinator
from .entity import HeatmiserNeoEntity, HeatmiserNeoEntityDescription

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HeatmiserNeoConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Heatmiser Neo Switch entities."""
    hub = entry.runtime_data.hub
    coordinator = entry.runtime_data.coordinator

    if coordinator.data is None:
        _LOGGER.error("Coordinator data is None. Cannot set up lock entities")
        return

    neo_devices, _ = coordinator.data
    system_data = coordinator.system_data

    _LOGGER.info("Adding Neo Locks")

    async_add_entities(
        HeatmiserNeoLockEntity(neodevice, coordinator, hub, description)
        for description in LOCKS
        for neodevice in neo_devices.values()
        if description.setup_filter_fn(neodevice, system_data)
    )


async def async_lock_device(entity: HeatmiserNeoEntity, **kwargs):
    """Lock a thermostat."""
    await entity.data.set_lock(int(kwargs.get(ATTR_CODE, 0)))


async def async_unlock_device(entity: HeatmiserNeoEntity):
    """Unlock a thermostat."""
    await entity.data.unlock()


@dataclass(frozen=True, kw_only=True)
class HeatmiserNeoLockEntityDescription(
    HeatmiserNeoEntityDescription, LockEntityDescription
):
    """Describes a button entity."""

    value_fn: Callable[[HeatmiserNeoEntity], bool]
    default_pin_fn: Callable[[HeatmiserNeoEntity], int]
    lock_fn: Callable[[HeatmiserNeoEntity, Any], Awaitable[None]]
    unlock_fn: Callable[[HeatmiserNeoEntity], Awaitable[None]]


LOCKS: tuple[HeatmiserNeoLockEntityDescription, ...] = (
    HeatmiserNeoLockEntityDescription(
        key="heatmiser_neo_stat_lock",
        translation_key="lock",
        value_fn=lambda entity: entity.data.lock,
        default_pin_fn=lambda entity: entity.data.pin_number,
        lock_fn=async_lock_device,
        unlock_fn=async_unlock_device,
        setup_filter_fn=lambda device, _: (
            device.device_type in HEATMISER_TYPE_IDS_LOCK
        ),
    ),
)


class HeatmiserNeoLockEntity(HeatmiserNeoEntity, LockEntity):
    """Heatmiser Neo switch entity."""

    def __init__(
        self,
        neostat: NeoStat,
        coordinator: HeatmiserNeoCoordinator,
        hub: NeoHub,
        entity_description: HeatmiserNeoLockEntityDescription,
    ) -> None:
        """Initialize Heatmiser Neo lock entity."""
        super().__init__(
            neostat,
            coordinator,
            hub,
            entity_description,
        )
        self._update()

    async def async_lock(self, **kwargs):
        """Turn the entity on."""
        await self.entity_description.lock_fn(self, **kwargs)
        self.data.lock = True
        self.coordinator.async_update_listeners()

    async def async_unlock(self, **kwargs):
        """Turn the entity off."""
        await self.entity_description.unlock_fn(self)
        self.data.lock = False
        self.coordinator.async_update_listeners()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._update()
        super()._handle_coordinator_update()

    def _update(self):
        if self.entity_description.default_pin_fn:
            self._lock_option_default_code = self.entity_description.default_pin_fn(
                self
            )
        self._attr_is_locked = self.entity_description.value_fn(self)
