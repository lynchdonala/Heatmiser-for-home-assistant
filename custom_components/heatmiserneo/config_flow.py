# SPDX-License-Identifier: Apache-2.0 OR GPL-2.0-only

"""Config flow for Heatmiser Neo."""

from copy import deepcopy
import logging
from typing import Any

from neohubapi.neohub import NeoHub, NeoHubConnectionError
import voluptuous as vol

from homeassistant.components.climate import UnitOfTemperature
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_API_TOKEN, CONF_HOST, CONF_PORT
from homeassistant.core import callback
from homeassistant.data_entry_flow import section
from homeassistant.helpers.selector import (
    DurationSelector,
    DurationSelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from . import HeatmiserNeoConfigEntry, hold_duration_validation
from .const import (
    CONF_CONN_METHOD_LEGACY,
    CONF_CONN_METHOD_WEBSOCKET,
    CONF_DEFAULTS,
    CONF_HVAC_MODES,
    CONF_STAT_HOLD_DURATION,
    CONF_STAT_HOLD_TEMP,
    CONF_THERMOSTAT_OPTIONS,
    CONF_TIMER_HOLD_DURATION,
    CONF_TIMER_OPTIONS,
    DEFAULT_HOST,
    DEFAULT_NEOSTAT_HOLD_DURATION,
    DEFAULT_NEOSTAT_TEMPERATURE_BOOST,
    DEFAULT_PORT,
    DEFAULT_TIMER_HOLD_DURATION,
    DEFAULT_WEBSOCKET_PORT,
    DOMAIN,
    HEATMISER_TEMPERATURE_UNIT_HA_UNIT,
    HEATMISER_TYPE_IDS_HC,
    AvailableMode,
    GlobalSystemType,
)

_LOGGER = logging.getLogger(__name__)


class FlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 1
    MINOR_VERSION = 1

    def __init__(self) -> None:
        """Initialize Heatmiser Neo options flow."""
        self._host = None
        self._port = None
        self._token = None

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle zeroconf discovery."""
        _LOGGER.debug("Zeroconfig discovered %s", discovery_info)
        self._host = discovery_info.host
        self._port = DEFAULT_PORT

        await self.async_set_unique_id(f"{self._host}:{self._port}")
        self._abort_if_unique_id_configured()
        return await self.async_step_zeroconf_confirm()

    async def async_step_zeroconf_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by zeroconf."""
        _LOGGER.debug("context %s", self.context)
        if user_input is not None:
            conn_error = await self.try_connection()
            if not conn_error:
                return self._async_get_entry()
            return self.async_abort(reason="cannot_connect")

        return self.async_show_form(
            step_id="zeroconf_confirm",
            description_placeholders={"name": self._host},
        )

    async def try_connection(self):
        """Try connection to NeoHub."""
        _LOGGER.debug("Trying connection to NeoHub")
        try:
            hub = NeoHub(self._host, self._port, token=self._token)
            await hub.firmware()
        except NeoHubConnectionError:
            return "cannot_connect"
        _LOGGER.debug("Connection Worked!")
        return None

    @callback
    def _async_get_entry(self) -> ConfigFlowResult:
        data = {CONF_HOST: self._host, CONF_PORT: self._port}
        if self._token:
            data[CONF_API_TOKEN] = self._token
        return self.async_create_entry(
            title=f"{self._host}:{self._port}",
            data=data,
        )

    async def _configure_entry(
        self, user_input: dict[str, Any] | None = None
    ) -> tuple[ConfigFlowResult, dict[str, str]]:
        errors = {}
        self._host = user_input[CONF_HOST]
        self._port = user_input[CONF_PORT]
        self._token = user_input.get(CONF_API_TOKEN)

        await self.async_set_unique_id(f"{self._host}:{self._port}")
        self._abort_if_unique_id_configured()

        conn_error = await self.try_connection()
        if not conn_error:
            return self._async_get_entry(), None

        errors["base"] = conn_error
        return None, errors

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        return self.async_show_menu(
            step_id="user",
            menu_options=[CONF_CONN_METHOD_WEBSOCKET, CONF_CONN_METHOD_LEGACY],
        )

    async def async_step_conn_method_websocket(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""

        errors = {}
        if user_input is not None:
            result, errors = await self._configure_entry(user_input)
            if not errors:
                return result
        return self.async_show_form(
            step_id=CONF_CONN_METHOD_WEBSOCKET,
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_HOST, default=self._host if self._host else DEFAULT_HOST
                    ): str,
                    vol.Required(
                        CONF_PORT,
                        default=self._port if self._port else DEFAULT_WEBSOCKET_PORT,
                    ): int,
                    vol.Required(CONF_API_TOKEN, default=self._token): str,
                }
            ),
            errors=errors,
        )

    async def async_step_conn_method_legacy(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        errors = {}
        if user_input is not None:
            result, errors = await self._configure_entry(user_input)
            if not errors:
                return result

        return self.async_show_form(
            step_id=CONF_CONN_METHOD_LEGACY,
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_HOST, default=self._host if self._host else DEFAULT_HOST
                    ): str,
                    vol.Required(
                        CONF_PORT, default=self._port if self._port else DEFAULT_PORT
                    ): int,
                }
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(OptionsFlow):
    """Handles options flow for the component."""

    def __init__(self, config_entry: HeatmiserNeoConfigEntry) -> None:
        """Initialize options flow."""
        self._hvac_config = deepcopy(config_entry.options.get(CONF_HVAC_MODES, {}))
        self._defaults_config = deepcopy(
            config_entry.options.get(
                CONF_DEFAULTS,
                {
                    CONF_STAT_HOLD_DURATION: {"minutes": DEFAULT_NEOSTAT_HOLD_DURATION},
                    CONF_STAT_HOLD_TEMP: DEFAULT_NEOSTAT_TEMPERATURE_BOOST,
                    CONF_TIMER_HOLD_DURATION: {"minutes": DEFAULT_TIMER_HOLD_DURATION},
                },
            )
        )

        devices, _ = config_entry.runtime_data.coordinator.data
        system_data = config_entry.runtime_data.coordinator.system_data

        self.neostat_hcs = sorted(
            [
                k
                for k, v in devices.items()
                if v.device_type in HEATMISER_TYPE_IDS_HC and not v.time_clock_mode
            ]
        )

        mandatory_modes = []
        system_modes = []
        if system_data.GLOBAL_SYSTEM_TYPE == GlobalSystemType.HEAT_ONLY:
            mandatory_modes.append(AvailableMode.HEAT)
        elif system_data.GLOBAL_SYSTEM_TYPE == GlobalSystemType.COOL_ONLY:
            mandatory_modes.append(AvailableMode.COOL)
        else:
            system_modes.append(AvailableMode.HEAT)
            system_modes.append(AvailableMode.COOL)
            system_modes.append(AvailableMode.AUTO)
        system_modes.append(AvailableMode.VENT)

        self._system_modes = {k.value for k in system_modes}
        self._mandatory_modes = {k.value for k in mandatory_modes}
        self._unit_of_measurement = HEATMISER_TEMPERATURE_UNIT_HA_UNIT.get(
            system_data.CORF, UnitOfTemperature.CELSIUS
        )

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the flow initiated by the user."""
        if len(self.neostat_hcs) == 0:
            return await self.async_step_defaults(user_input=user_input)

        return await self.async_step_choose_options(user_input=user_input)

    async def async_step_choose_options(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle local vs cloud mode selection step."""
        return self.async_show_menu(
            step_id="choose_options",
            menu_options={
                CONF_DEFAULTS: "Configure default settings for devices",
                CONF_HVAC_MODES: "Configure HVAC modes for NeoStatHC",
            },
        )

    async def async_step_hvac_modes(
        self, user_input: dict[str, str] | None = None
    ) -> ConfigFlowResult:
        """Manage the options for the custom component."""
        errors: dict[str, str] = {}

        if user_input is not None:
            _LOGGER.debug("user_input: %s", user_input)
            _LOGGER.debug("original config: %s", self._hvac_config)

            # Remove any devices where hvac_modes have been unset.
            for d in self.neostat_hcs:
                modes = set(user_input.get(d, []))
                if len(modes) == len(self._system_modes):
                    if d in self._hvac_config:
                        del self._hvac_config[d]
                elif not errors:
                    self._hvac_config[d] = sorted(modes.union(self._mandatory_modes))

            _LOGGER.debug("updated config: %s", self._hvac_config)

            if not errors:
                # Value of data will be set on the options property of the config_entry instance.
                return self.async_create_entry(
                    title="",
                    data={
                        CONF_HVAC_MODES: self._hvac_config,
                        CONF_DEFAULTS: self._defaults_config,
                    },
                )

        options_schema = vol.Schema(
            {
                vol.Required(
                    d,
                    default=set(self._hvac_config.get(d, self._system_modes))
                    - self._mandatory_modes,
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=sorted(self._system_modes),
                        multiple=True,
                        mode=SelectSelectorMode.LIST,
                        translation_key="available_mode_selector",
                    )
                )
                for d in self.neostat_hcs
            }
        )

        return self.async_show_form(
            step_id=CONF_HVAC_MODES, data_schema=options_schema, errors=errors
        )

    async def async_step_defaults(
        self, user_input: dict[str, str] | None = None
    ) -> ConfigFlowResult:
        """Manage the defaults for the custom component."""
        errors: dict[str, str] = {}

        if user_input is not None:
            _LOGGER.debug("user_input: %s", user_input)
            _LOGGER.debug("original config: %s", self._defaults_config)

            self._defaults_config = user_input
            self._defaults_config[CONF_THERMOSTAT_OPTIONS][CONF_STAT_HOLD_DURATION] = (
                int(
                    hold_duration_validation(
                        user_input.get(CONF_THERMOSTAT_OPTIONS, {}).get(
                            CONF_STAT_HOLD_DURATION,
                            {"minutes": DEFAULT_NEOSTAT_HOLD_DURATION},
                        )
                    ).total_seconds()
                    / 60
                )
            )
            self._defaults_config[CONF_TIMER_OPTIONS][CONF_TIMER_HOLD_DURATION] = int(
                hold_duration_validation(
                    user_input.get(CONF_TIMER_OPTIONS, {}).get(
                        CONF_TIMER_HOLD_DURATION,
                        {"minutes": DEFAULT_TIMER_HOLD_DURATION},
                    )
                ).total_seconds()
                / 60
            )

            _LOGGER.debug("updated config: %s", self._defaults_config)

            if not errors:
                # Value of data will be set on the options property of the config_entry instance.
                return self.async_create_entry(
                    title="",
                    data={
                        CONF_HVAC_MODES: self._hvac_config,
                        CONF_DEFAULTS: self._defaults_config,
                    },
                )
        temperature_step = (
            await self.config_entry.runtime_data.coordinator.hub.target_temperature_step
        )
        options_schema = vol.Schema(
            {
                vol.Required(CONF_THERMOSTAT_OPTIONS): section(
                    vol.Schema(
                        {
                            vol.Required(
                                CONF_STAT_HOLD_DURATION,
                                default={
                                    "minutes": self._defaults_config.get(
                                        CONF_THERMOSTAT_OPTIONS, {}
                                    ).get(
                                        CONF_STAT_HOLD_DURATION,
                                        DEFAULT_NEOSTAT_HOLD_DURATION,
                                    )
                                },
                            ): DurationSelector(
                                DurationSelectorConfig(
                                    enable_day=False,
                                    enable_millisecond=False,
                                    allow_negative=False,
                                )
                            ),
                            vol.Required(
                                CONF_STAT_HOLD_TEMP,
                                default=self._defaults_config.get(
                                    CONF_THERMOSTAT_OPTIONS, {}
                                ).get(
                                    CONF_STAT_HOLD_TEMP,
                                    DEFAULT_NEOSTAT_TEMPERATURE_BOOST,
                                ),
                            ): NumberSelector(
                                NumberSelectorConfig(
                                    min=1,
                                    max=10,
                                    step=temperature_step,
                                    mode=NumberSelectorMode.BOX,
                                    unit_of_measurement=self._unit_of_measurement,
                                )
                            ),
                        }
                    )
                ),
                vol.Required(CONF_TIMER_OPTIONS): section(
                    vol.Schema(
                        {
                            vol.Required(
                                CONF_TIMER_HOLD_DURATION,
                                default={
                                    "minutes": self._defaults_config.get(
                                        CONF_TIMER_OPTIONS, {}
                                    ).get(
                                        CONF_TIMER_HOLD_DURATION,
                                        DEFAULT_TIMER_HOLD_DURATION,
                                    )
                                },
                            ): DurationSelector(
                                DurationSelectorConfig(
                                    enable_day=False,
                                    enable_millisecond=False,
                                    allow_negative=False,
                                )
                            ),
                        }
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id=CONF_DEFAULTS, data_schema=options_schema, errors=errors
        )
