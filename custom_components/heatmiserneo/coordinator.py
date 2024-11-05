# SPDX-License-Identifier: Apache-2.0 OR GPL-2.0-only
"""Coordinator object for the HeatmiserNeo integration."""

import asyncio
from datetime import timedelta
import logging

from neohubapi.neohub import NeoHub

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


class HeatmiserNeoCoordinator(DataUpdateCoordinator[NeoHub]):
    """Coordinator Class for Heatmiser Neo Hub."""

    _device_serial_numbers: dict[int, dict[str, str]]

    def __init__(self, hass: HomeAssistant, hub: NeoHub) -> None:
        """Initialize the HeatmiserNeo Update Coordinator."""
        self.hub = hub
        super().__init__(
            hass,
            _LOGGER,
            name=f"Heatmiser NeoHub : {hub._host}",  # noqa: SLF001
            update_interval=timedelta(seconds=30),
            always_update=True,
        )

    async def _async_setup(self):
        device_serial_numbers = await self.hub.devices_sn()
        _LOGGER.debug("device serial numbers: %s", device_serial_numbers)
        # Convert device_serial_numbers (SimpleNamespace) to a dictionary
        device_serial_numbers_dict = vars(device_serial_numbers)
        self._device_serial_numbers = {
            v[0]: {"name": k, "serial_number": v[1]}
            for (k, v) in device_serial_numbers_dict.items()
        }
        _LOGGER.debug("device serial numbers map: %s", self._device_serial_numbers)

    async def _async_update_data(self):
        """Fetch data from the Hub all at once and make it available for all devices."""
        _LOGGER.info("Executing update_data()")
        async with asyncio.timeout(30):
            system_data = await self.hub.get_system()
            devices_data = await self.hub.get_devices_data()

            _LOGGER.debug("system_data: %s", system_data)
            _LOGGER.debug("devices_data: %s", devices_data)

            ## Adding Serial numbers to device data.
            # Loop through devices and append serial numbers to _simple_attrs
            for device in devices_data["neo_devices"]:
                device_id = (
                    device._data_.DEVICE_ID
                )  # Get the device ID from the _data_ namespace

                # If any matching serials are found, assign the first one, else set to "UNKNOWN"
                serial_number = self._get_device_sn(device_id)

                # Add serial number if it doesn't already exist
                if getattr(device, "serial_number", None) is None:
                    setattr(device, "serial_number", serial_number)

            return devices_data, system_data

    def _get_device_sn(self, device_id: int) -> str:
        """Get a device serial number by its device id."""

        return self._device_serial_numbers.get(device_id, {}).get(
            "serial_number", "UNKNOWN"
        )
