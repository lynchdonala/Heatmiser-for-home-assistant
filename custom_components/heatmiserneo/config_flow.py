# SPDX-License-Identifier: Apache-2.0 OR GPL-2.0-only

"""Config flow for Heatmiser Neo."""

from copy import deepcopy
import logging
import socket

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.zeroconf import ZeroconfServiceInfo
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv

from . import HeatmiserNeoConfigEntry
from .const import (
    CONF_HVAC_MODES,
    DEFAULT_HOST,
    DEFAULT_PORT,
    DOMAIN,
    HEATMISER_TYPE_IDS_HC,
    AvailableMode,
    GlobalSystemType,
)

_LOGGER = logging.getLogger(__name__)

AVAILABLE_MODE_MAPPING = {
    AvailableMode.AUTO: "Auto",
    AvailableMode.COOL: "Cool",
    AvailableMode.HEAT: "Heat",
    AvailableMode.VENT: "Fan Only",
}

SCHEMA_ATTR_DEVICE = "device"
SCHEMA_ATTR_HVAC_MODES = "hvac_modes"
SCHEMA_ATTR_MORE = "more"


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

    def __init__(self, config_entry: HeatmiserNeoConfigEntry) -> None:
        """Initialize options flow."""
        # self.config_entry = config_entry
        self.config = deepcopy(config_entry.options.get(CONF_HVAC_MODES, {}))

    async def async_step_init(
        self, user_input: dict[str, str] | None = None
    ) -> dict[str, str]:
        """Manage the options for the custom component."""
        errors: dict[str, str] = {}

        devices, _ = self.config_entry.runtime_data.coordinator.data
        system_data = self.config_entry.runtime_data.coordinator.system_data

        devices = sorted(
            [
                k
                for k, v in devices.items()
                if v.device_type in HEATMISER_TYPE_IDS_HC and not v.time_clock_mode
            ]
        )

        if len(devices) == 0:
            # return await self.async_step_none()
            return self.async_abort(reason="no_devices_supported")

        if user_input is not None:
            _LOGGER.debug("user_input: %s", user_input)
            _LOGGER.debug("original config: %s", self.config)

            # Remove any devices where hvac_modes have been unset.
            name = user_input[SCHEMA_ATTR_DEVICE]
            if len(user_input[SCHEMA_ATTR_HVAC_MODES]) == 0:
                self.config.pop(name)
            elif not errors:
                self.config[name] = user_input[SCHEMA_ATTR_HVAC_MODES]

            _LOGGER.debug("updated config: %s", self.config)

            if not errors:
                # If user selected the 'more' tickbox, show this form again
                # so they can configure additional devices.
                if user_input.get(SCHEMA_ATTR_MORE, False):
                    return await self.async_step_init()

                # Value of data will be set on the options property of the config_entry instance.
                return self.async_create_entry(
                    title="", data={CONF_HVAC_MODES: self.config}
                )

        system_modes = []
        if system_data.GLOBAL_SYSTEM_TYPE == GlobalSystemType.HEAT_ONLY:
            system_modes.append(AvailableMode.HEAT)
        elif system_data.GLOBAL_SYSTEM_TYPE == GlobalSystemType.COOL_ONLY:
            system_modes.append(AvailableMode.COOL)
        else:
            system_modes.append(AvailableMode.HEAT)
            system_modes.append(AvailableMode.COOL)
            system_modes.append(AvailableMode.AUTO)
        system_modes.append(AvailableMode.VENT)

        mode_options = {
            k: v for k, v in AVAILABLE_MODE_MAPPING.items() if k in system_modes
        }

        options_schema = vol.Schema(
            {
                vol.Optional(SCHEMA_ATTR_DEVICE, default=devices): vol.In(devices),
                vol.Optional(
                    SCHEMA_ATTR_HVAC_MODES, default=list(mode_options)
                ): cv.multi_select(mode_options),
                vol.Optional(SCHEMA_ATTR_MORE): cv.boolean,
            }
        )

        return self.async_show_form(
            step_id="init", data_schema=options_schema, errors=errors
        )
