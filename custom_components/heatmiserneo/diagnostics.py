# SPDX-License-Identifier: Apache-2.0 OR GPL-2.0-only
"""Diagnostics support for Heatmiser Neo."""

from __future__ import annotations

import logging
from typing import Any

from neohubapi.neohub import NeoStat

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from .const import COORDINATOR, DOMAIN, HUB

_LOGGER = logging.getLogger(__name__)

TO_REDACT_CONFIG = {CONF_HOST, "title", "unique_id", "token"}
TO_REDACT_RAW_DATA = {"PIN_NUMBER"}
TO_REDACT_DEVICES = {"pin_number", "serial_number"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id][COORDINATOR]
    hub = hass.data[DOMAIN][entry.entry_id][HUB]
    devices_data, system_data = coordinator.data
    engineers_data = await hub.get_engineers()
    # devices = await hub.get_devices()
    # zones = {device._data_.ZONE_NAME for device in devices_data["neo_devices"]}
    # _LOGGER.debug("Zones %s", zones)
    # device_list = {z: await retrieve_zone_device_list(z, hub) for z in zones}
    # _LOGGER.debug("device_list %s", device_list)
    return {
        "config_entry": async_redact_data(entry.as_dict(), TO_REDACT_CONFIG),
        "devices_data": {
            device.name: convert_to_dict(device)
            for device in devices_data["neo_devices"]
        },
        "system_data": vars(system_data),
        "engineers": {
            name: vars(device) for name, device in engineers_data.__dict__.items()
        },
        # "devices": devices,
        # "device_list": device_list,
    }


def convert_to_dict(device: NeoStat) -> dict:
    """Convert a NeoStat entity to a redacted dict."""

    dev_diagnostics = device.__dict__.copy()
    dev_diagnostics["raw_data"] = async_redact_data(
        dict(vars(device._data_)), TO_REDACT_RAW_DATA
    )
    del dev_diagnostics["_hub"]
    del dev_diagnostics["_logger"]
    del dev_diagnostics["_data_"]
    del dev_diagnostics["_simple_attrs"]
    return async_redact_data(dict(dev_diagnostics), TO_REDACT_DEVICES)


# async def retrieve_zone_device_list(zone: str, hub):
#     """Get device list for each zone."""
#     response = await hub._send({"GET_DEVICE_LIST": zone})
#     return dict(vars(response)).get(zone, {})
