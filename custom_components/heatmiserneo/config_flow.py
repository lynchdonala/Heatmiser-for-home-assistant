# SPDX-License-Identifier: Apache-2.0 OR GPL-2.0-only

"""Config flow for Heatmiser Neo."""

from copy import deepcopy
import logging
import socket

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.climate import HVACMode
from homeassistant.components.zeroconf import ZeroconfServiceInfo
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_registry import (
    async_entries_for_config_entry,
    async_get,
)

from .const import CONF_HVAC_MODES, DEFAULT_HOST, DEFAULT_PORT, DOMAIN, AvailableMode

_LOGGER = logging.getLogger(__name__)

modes = {
    AvailableMode.AUTO: HVACMode.HEAT_COOL,
    AvailableMode.COOL: HVACMode.COOL,
    AvailableMode.HEAT: HVACMode.HEAT,
    AvailableMode.VENT: HVACMode.FAN_ONLY,
}
default_modes = [HVACMode.HEAT]


@config_entries.HANDLERS.register("heatmiserneo")
class FlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    def __init__(self) -> None:
        """Initialize Heatmiser Neo options flow."""
        self._host = DEFAULT_HOST
        self._port = DEFAULT_PORT
        self._errors = None

    async def async_step_zeroconf(self, discovery_info: ZeroconfServiceInfo):
        """Handle zeroconf discovery."""
        _LOGGER.debug("Zeroconfig discovered %s", discovery_info)
        self._host = discovery_info.host

        await self.async_set_unique_id(f"{self._host}:{self._port}")
        self._abort_if_unique_id_configured()
        return await self.async_step_zeroconf_confirm()

    async def async_step_zeroconf_confirm(self, user_input=None):
        """Handle a flow initiated by zeroconf."""
        _LOGGER.debug("context %s", self.context)
        if user_input is not None:
            self._errors = await self.try_connection()
            if not self._errors:
                return self._async_get_entry()
            return await self.async_step_user()

        return self.async_show_form(
            step_id="zeroconf_confirm",
            description_placeholders={"name": self._host},
        )

    async def try_connection(self):
        """Try connection to NeoHub."""
        _LOGGER.debug("Trying connection to NeoHub")
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        try:
            sock.connect((self._host, self._port))
        except OSError:
            return "cannot_connect"
        sock.close()
        _LOGGER.debug("Connection Worked!")
        return None

    @callback
    def _async_get_entry(self):
        return self.async_create_entry(
            title=f"{self._host}:{self._port}",
            data={CONF_HOST: self._host, CONF_PORT: self._port},
        )

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        _LOGGER.debug("User Input %s", user_input)

        if user_input is not None:
            self._host = user_input[CONF_HOST]
            self._port = user_input[CONF_PORT]

            await self.async_set_unique_id(f"{self._host}:{self._port}")
            self._abort_if_unique_id_configured()

            self._errors = await self.try_connection()
            if not self._errors:
                return self._async_get_entry()

            _LOGGER.error("Error: %s", self._errors)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=self._host): str,
                    vol.Required(CONF_PORT, default=self._port): int,
                }
            ),
            errors=self._errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handles options flow for the component."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry
        self.config = (
            deepcopy(config_entry.options[CONF_HVAC_MODES])
            if CONF_HVAC_MODES in self.config_entry.options
            else {}
        )

    async def async_step_init(
        self, user_input: dict[str, str] | None = None
    ) -> dict[str, str]:
        """Manage the options for the custom component."""
        errors: dict[str, str] = {}

        # Grab all devices from the entity registry so we can populate the
        # dropdown list that will allow a user to configure a device.
        entity_registry = async_get(self.hass)
        devices = async_entries_for_config_entry(
            entity_registry, self.config_entry.entry_id
        )
        stats = {
            e.unique_id: e.capabilities
            for e in devices
            if e.entity_id.startswith("climate.")
        }

        if user_input is not None:
            _LOGGER.debug("user_input: %s", user_input)
            _LOGGER.debug("original config: %s", self.config)

            # Remove any devices where hvac_modes have been unset.
            remove_devices = [
                unique_id
                for unique_id in stats
                if unique_id == user_input["device"]
                if len(user_input["hvac_modes"]) == 0
            ]
            for unique_id in remove_devices:
                if unique_id in self.config:
                    self.config.pop(unique_id)

            if len(user_input["hvac_modes"]) != 0:
                if not errors:
                    # Add the new device config.
                    self.config[user_input["device"]] = user_input["hvac_modes"]

            _LOGGER.debug("updated config: %s", self.config)

            if not errors:
                # If user selected the 'more' tickbox, show this form again
                # so they can configure additional devices.
                if user_input.get("more", False):
                    return await self.async_step_init()

                # Value of data will be set on the options property of the config_entry instance.
                return self.async_create_entry(
                    title="", data={CONF_HVAC_MODES: self.config}
                )

        options_schema = vol.Schema(
            {
                vol.Optional("device", default=list(stats.keys())): vol.In(
                    stats.keys()
                ),
                vol.Optional(
                    "hvac_modes", default=list(default_modes)
                ): cv.multi_select(modes),
                vol.Optional("more"): cv.boolean,
            }
        )

        return self.async_show_form(
            step_id="init", data_schema=options_schema, errors=errors
        )
