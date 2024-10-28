# SPDX-License-Identifier: Apache-2.0 OR GPL-2.0-only
"""Heatmiser Neo Button platform."""

from dataclasses import dataclass
import logging

from neohubapi.neohub import NeoHub, NeoStat

from homeassistant.components.button import (
    ButtonDeviceClass,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import COORDINATOR, DOMAIN, HUB
from .entity import HeatmiserNeoEntity, HeatmiserNeoEntityDescription


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Heatmiser Neo button entities."""
    hub = hass.data[DOMAIN][entry.entry_id][HUB]
    coordinator = hass.data[DOMAIN][entry.entry_id][COORDINATOR]

    if coordinator.data is None:
        _LOGGER.error("Coordinator data is None. Cannot set up button entities")
        return

    devices_data, _ = coordinator.data

    neo_devices = {device.name: device for device in devices_data["neo_devices"]}
    _LOGGER.info("Adding Neo Device Buttons")

    async_add_entities(
        HeatmiserNeoButton(neodevice, coordinator, hub, description)
        for description in BUTTONS
        for neodevice in neo_devices.values()
        if description.setup_filter_fn(neodevice)
    )


_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class HeatmiserNeoButtonEntityDescription(
    HeatmiserNeoEntityDescription, ButtonEntityDescription
):
    """Describes a button entity."""


BUTTONS: tuple[HeatmiserNeoButtonEntityDescription, ...] = (
    HeatmiserNeoButtonEntityDescription(
        key="heatmiser_neo_identify_button",
        device_class=ButtonDeviceClass.IDENTIFY,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


class HeatmiserNeoButton(HeatmiserNeoEntity, ButtonEntity):
    """Heatmiser Neo button entity."""

    def __init__(
        self,
        neostat: NeoStat,
        coordinator: DataUpdateCoordinator,
        hub: NeoHub,
        entity_description: HeatmiserNeoButtonEntityDescription,
    ) -> None:
        """Initialize Heatmiser Neo button entity."""
        super().__init__(
            neostat,
            coordinator,
            hub,
            entity_description,
        )

    async def async_press(self) -> None:
        """Handle the button press."""
        await self._neodevice.identify()
