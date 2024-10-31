# SPDX-License-Identifier: Apache-2.0 OR GPL-2.0-only
"""The Heatmiser Neo integration."""

import asyncio
from dataclasses import dataclass
from datetime import timedelta
import logging

from neohubapi.neohub import NeoHub
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, HEATMISER_HUB_PRODUCT_LIST
from .coordinator import HeatmiserNeoCoordinator

_LOGGER = logging.getLogger(__name__)


type HeatmiserNeoConfigEntry = ConfigEntry[HeatmiserNeoData]


@dataclass
class HeatmiserNeoData:
    """Class to store Heatmiser Neo runtime data."""

    hub: NeoHub
    coordinator: HeatmiserNeoCoordinator


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Heatmiser Neo components."""
    hass.data.setdefault(DOMAIN, {})

    return True


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HeatmiserNeoConfigEntry,
) -> bool:
    """Set up Heatmiser Neo from a config entry."""

    # Set the Hub up to use and save
    host = entry.data[CONF_HOST]
    port = entry.data[CONF_PORT]
    # Make this configurable or retrieve from an API later.
    hub_serial_number = f"NEOHUB-SN:000000-{host}"
    hub = NeoHub(host, port)

    # TODO: Split this out to it's own HUB / Bridge thing.
    _LOGGER.debug("Attempting to setup Heatmiser Neo Hub Device: %s:%s", host, port)
    init_system_data = await hub.get_system()
    _LOGGER.debug("system_data: %s", init_system_data)

    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, hub_serial_number)},
        manufacturer="Heatmiser",
        model=f"{HEATMISER_HUB_PRODUCT_LIST[init_system_data.HUB_TYPE]}",
        name=f"NeoHub - {host}",
        serial_number=hub_serial_number,
        sw_version=init_system_data.HUB_VERSION,
    )

    # TODO: NTP Fixes as per below.
    """"
    TODO: Make this configurable, and move it from here
    workaround to re-enable NTP after a power outage (or any other reason)
    where WAN connectivity will not have been restored by the time the NeoHub has fully started.
    """
    if getattr(init_system_data, "NTP_ON") != "Running":
        """ Enable NTP """
        _LOGGER.warning("NTP disabled. Enabling")

        set_ntp_enabled_task = asyncio.create_task(hub.set_ntp(True))
        response = await set_ntp_enabled_task
        if response:
            _LOGGER.info("Enabled NTP (response: %s)", response)
    else:
        _LOGGER.debug("NTP enabled")

    coordinator = HeatmiserNeoCoordinator(hass, hub)

    coordinator.serial_number = hub_serial_number

    entry.runtime_data = HeatmiserNeoData(hub, coordinator)

    await coordinator.async_config_entry_first_refresh()
    await hass.config_entries.async_forward_entry_setups(
        entry, ["binary_sensor", "button", "climate", "select", "sensor"]
    )

    return True


async def options_update_listener(
    hass: HomeAssistant, config_entry: config_entries.ConfigEntry
):
    """Handle options update."""
    await hass.config_entries.async_reload(config_entry.entry_id)


def time_period_minutes(value: float | str) -> timedelta:
    """Validate and transform minutes to a time offset."""
    try:
        return timedelta(minutes=float(value))
    except (ValueError, TypeError) as err:
        raise vol.Invalid(f"Expected minutes, got {value}") from err


hold_duration_validation = vol.All(
    vol.Any(cv.time_period_str, time_period_minutes, timedelta, cv.time_period_dict),
    cv.positive_timedelta,
)
