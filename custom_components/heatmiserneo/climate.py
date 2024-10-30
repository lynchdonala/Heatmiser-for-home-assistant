# SPDX-License-Identifier: Apache-2.0 OR GPL-2.0-only
"""Heatmiser NeoStat control via Heatmiser Neo-hub."""

import asyncio
from collections import OrderedDict
from dataclasses import dataclass
from datetime import timedelta
import logging

from neohubapi.neohub import HCMode, NeoHub, NeoStat
from propcache import cached_property
import voluptuous as vol

from homeassistant.components.climate import (
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    FAN_AUTO,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    FAN_OFF,
    PRESET_AWAY,
    PRESET_BOOST,
    PRESET_HOME,
    ClimateEntity,
    ClimateEntityDescription,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
    UnitOfTemperature,
)
from homeassistant.const import ATTR_TEMPERATURE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from . import HeatmiserNeoConfigEntry, hold_duration_validation
from .const import (
    ATTR_HOLD_DURATION,
    ATTR_HOLD_TEMPERATURE,
    CONF_HVAC_MODES,
    DEFAULT_NEOSTAT_HOLD_DURATION,
    DEFAULT_NEOSTAT_TEMPERATURE_BOOST,
    HEATMISER_FAN_SPEED_HA_FAN_MODE,
    HEATMISER_TEMPERATURE_UNIT_HA_UNIT,
    HEATMISER_TYPE_IDS_HC,
    HEATMISER_TYPE_IDS_THERMOSTAT,
    SERVICE_HOLD_OFF,
    SERVICE_HOLD_ON,
)
from .entity import HeatmiserNeoEntity, HeatmiserNeoEntityDescription

_LOGGER = logging.getLogger(__name__)


SUPPORT_FLAGS = 0
THERMOSTATS = "thermostats"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HeatmiserNeoConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Heatmiser Neo Climate entities."""
    hub = entry.runtime_data.hub
    coordinator = entry.runtime_data.coordinator

    if coordinator.data is None:
        _LOGGER.error("Coordinator data is None. Cannot set up climate entities")
        return

    devices_data, system_data = coordinator.data
    thermostats = {device.name: device for device in devices_data["neo_devices"]}

    hvac_config = entry.options.get(CONF_HVAC_MODES, {})

    _LOGGER.debug("hvac_config: %s", hvac_config)
    for config in hvac_config:
        _LOGGER.debug(
            "Overriding the default HVAC modes from %s to %s for the %s climate entity",
            thermostats[config].available_modes,
            hvac_config[config],
            config,
        )
        thermostats[config].available_modes = hvac_config[config]

    temperature_unit = HEATMISER_TEMPERATURE_UNIT_HA_UNIT.get(
        system_data.CORF, UnitOfTemperature.CELSIUS
    )
    temperature_step = await hub.target_temperature_step

    _LOGGER.info("Adding Neo Climate Entities")

    async_add_entities(
        NeoStatEntity(
            neodevice,
            coordinator,
            hub,
            description,
            temperature_unit,
            float(temperature_step),
        )
        for description in CLIMATE
        for neodevice in thermostats.values()
        if description.setup_filter_fn(neodevice, system_data)
    )

    platform = entity_platform.async_get_current_platform()

    platform.async_register_entity_service(
        SERVICE_HOLD_ON,
        {
            vol.Required(ATTR_HOLD_DURATION, default=1): hold_duration_validation,
            vol.Required(ATTR_HOLD_TEMPERATURE, default=20): vol.All(
                vol.Coerce(float), vol.Range(min=0, max=35)
            ),
        },
        "set_hold",
    )

    platform.async_register_entity_service(
        SERVICE_HOLD_OFF,
        {},
        "unset_hold",
    )


@dataclass(frozen=True, kw_only=True)
class HeatmiserNeoClimateEntityDescription(
    HeatmiserNeoEntityDescription, ClimateEntityDescription
):
    """Describes a button entity."""


CLIMATE: tuple[HeatmiserNeoClimateEntityDescription, ...] = (
    HeatmiserNeoClimateEntityDescription(
        key="heatmiser_neostat",
        name=None,  # Use device name
        setup_filter_fn=lambda device, _: (
            device.device_type in HEATMISER_TYPE_IDS_THERMOSTAT
            and not device.time_clock_mode
        ),
    ),
)


class NeoStatEntity(HeatmiserNeoEntity, ClimateEntity):
    """Represents a Heatmiser neoStat thermostat."""

    _enable_turn_on_off_backwards_compatibility = False

    def __init__(
        self,
        neostat: NeoStat,
        coordinator: DataUpdateCoordinator,
        hub: NeoHub,
        entity_descriptor: HeatmiserNeoClimateEntityDescription,
        unit_of_measurement: UnitOfTemperature,
        temperature_step: float,
    ) -> None:
        """Initialize Heatmiser Neo Climate entity."""
        super().__init__(
            neostat,
            coordinator,
            hub,
            entity_descriptor,
        )

        self._attr_temperature_unit = unit_of_measurement
        self._attr_target_temperature_step = temperature_step
        self._attr_max_temp = neostat.max_temperature_limit
        self._attr_min_temp = neostat.min_temperature_limit
        self._attr_preset_modes = [PRESET_HOME, PRESET_BOOST, PRESET_AWAY]
        self._attr_fan_modes = [FAN_OFF, FAN_LOW, FAN_MEDIUM, FAN_HIGH, FAN_AUTO]

        hvac_modes = []
        if hasattr(neostat, "standby"):
            hvac_modes.append(HVACMode.OFF)
        # The following devices support Heating modes
        if self.data.device_type in HEATMISER_TYPE_IDS_HC:
            if self.system_data.GLOBAL_SYSTEM_TYPE == "HeatOnly":
                hvac_modes.append(HVACMode.HEAT)
            elif self.system_data.GLOBAL_SYSTEM_TYPE == "CoolOnly":
                hvac_modes.append(HVACMode.COOL)
            else:
                hvac_modes.append(HVACMode.HEAT)
                hvac_modes.append(HVACMode.COOL)
                hvac_modes.append(HVACMode.HEAT_COOL)
            hvac_modes.append(HVACMode.FAN_ONLY)
        else:
            hvac_modes.append(HVACMode.HEAT)

        self._attr_hvac_modes = hvac_modes

    async def async_set_hvac_mode(self, hvac_mode):
        """Set hvac mode."""
        _LOGGER.info("%s : Executing set_hvac_mode() with: %s", self.name, hvac_mode)
        _LOGGER.debug("self.data: %s", self.data)

        hc_mode: HCMode = None
        if hvac_mode == HVACMode.HEAT:
            hc_mode = HCMode.HEATING
        elif hvac_mode == HVACMode.COOL:
            hc_mode = HCMode.COOLING
        elif hvac_mode == HVACMode.HEAT_COOL:
            hc_mode = HCMode.AUTO
        elif hvac_mode == HVACMode.FAN_ONLY:
            hc_mode = HCMode.VENT

        if hvac_mode != HVACMode.OFF:
            frost_mode = False  # Standby Mode False

            set_frost_task = asyncio.create_task(self.data.set_frost(frost_mode))
            response = await set_frost_task
            _LOGGER.info(
                "%s : Called set_frost() with: %s (response: %s)",
                self.name,
                frost_mode,
                response,
            )
            if self.data.standby:
                self.data.standby = False

            set_hc_mode_task = asyncio.create_task(self.data.set_hc_mode(hc_mode))
            response = await set_hc_mode_task
            _LOGGER.info(
                "%s : Called set_hc_mode() with: %s (response: %s)",
                self.name,
                hc_mode,
                response,
            )
            self.data.hc_mode = hc_mode
        else:
            frost_mode = True  # Turn on Standby Mode
            set_frost_task = asyncio.create_task(self.data.set_frost(frost_mode))
            response = await set_frost_task
            _LOGGER.info(
                "%s : Called set_frost() with: %s (response: %s)",
                self.name,
                frost_mode,
                response,
            )
            if not self.data.standby:
                self.data.standby = True
        self.coordinator.async_update_listeners()
        await self.coordinator.async_request_refresh()

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        _LOGGER.info("%s : Executing set_temperature() with:  %s", self.name, kwargs)
        _LOGGER.debug("self.data:  %s", self.data)

        low_temp = kwargs.get(ATTR_TEMPERATURE) or kwargs.get(ATTR_TARGET_TEMP_LOW)
        high_temp = kwargs.get(ATTR_TARGET_TEMP_HIGH)

        set_target_temperature_task = asyncio.create_task(
            self.data.set_target_temperature(low_temp)
        )
        response = await set_target_temperature_task
        if response:
            _LOGGER.info(
                "%s : Called set_target_temperature with: %s (response: %s)",
                self.name,
                low_temp,
                response,
            )

        set_target_cool_temperature_task = asyncio.create_task(
            self.data.set_cool_temp(high_temp)
        )
        response = await set_target_cool_temperature_task
        if response:
            _LOGGER.info(
                "%s : Called set_cool_temp with: %s (response: %s)",
                self.name,
                high_temp,
                response,
            )

        # The change of target temperature may trigger a change in the current hvac_action
        # so we schedule a refresh to get new data asap.
        await self.coordinator.async_request_refresh()

    @property
    def current_temperature(self):
        """Returns the current temperature."""
        if self.data.offline:
            return None

        # Checking for unreasonable temperatures, happens on hub disconnection.
        # Centigrade
        if (
            float(self.data.temperature) < -50.0 or float(self.data.temperature) > 70.0
        ) and self._unit_of_measurement == "C":
            _LOGGER.error(
                "Error: Climate entity '%s' has an invalid current_temperature value: %s degrees Centigrade, Hub lost connection?",
                self.data.name,
                self.data.temperature,
            )
            return None

        # Fahrenheit
        if (
            float(self.data.temperature) < -58.0 or float(self.data.temperature) > 158.0
        ) and self._unit_of_measurement == "F":
            _LOGGER.error(
                "Error: Climate entity '%s' has an invalid current_temperature value: %s degrees Fahrenheit, Hub lost connection?",
                self.data.name,
                self.data.temperature,
            )
            return None

        return float(self.data.temperature)

    @property
    def extra_state_attributes(self):
        """Return the additional state attributes."""
        attributes = OrderedDict()

        attributes["device_type"] = self.data.device_type
        attributes["low_battery"] = self.data.low_battery
        attributes["offline"] = self.data.offline
        attributes["standby"] = self.data.standby
        attributes["hold_on"] = self.data.hold_on
        attributes["hold_time"] = ":".join(str(self.data.hold_time).split(":")[:2])
        attributes["hold_temp"] = self.data.hold_temp
        attributes["floor_temperature"] = self.data.current_floor_temperature
        attributes["preheat_active"] = self.data.preheat_active
        attributes["hc_mode"] = self.data.hc_mode
        attributes["sensor_mode"] = self.data.sensor_mode

        return attributes

    @property
    def hvac_action(self):
        # See: https://developers.home-assistant.io/docs/core/entity/climate/
        """The current HVAC action (heating, cooling)."""
        if self.data.standby:
            return HVACAction.OFF
        if self.data.preheat_active:
            return HVACAction.PREHEATING
        if self.data.cool_on:
            return HVACAction.COOLING
        if self.data.heat_on:
            return HVACAction.HEATING
        if self.data.fan_speed != "Off":
            return HVACAction.FAN  # Should fan be combined? Ie can you have fan on and other functions together?
        return HVACAction.IDLE

    @property
    def hvac_mode(self):
        """Return The current operation (e.g. heat, cool, idle). Used to determine state."""
        if self.data.standby:
            return HVACMode.OFF
        if self.data.device_type in HEATMISER_TYPE_IDS_HC:
            if self.data.hc_mode == "COOLING":
                return HVACMode.COOL
            if self.data.hc_mode == "AUTO":
                return HVACMode.HEAT_COOL
            if self.data.hc_mode == "VENT":
                return HVACMode.FAN_ONLY
        return HVACMode.HEAT

    async def set_hold(self, hold_duration: timedelta, hold_temperature: float):
        """Set Hold for Zone."""
        _LOGGER.warning(
            "%s : Executing set_hold() with duration: %s, temperature: %s",
            self.name,
            hold_duration,
            hold_temperature,
        )
        _LOGGER.debug("self.data: %s", self.data)

        hold_minutes = int(hold_duration.total_seconds() / 60)
        hold_minutes = min(hold_minutes, 60 * 99)
        hold_hours, hold_minutes = divmod(hold_minutes, 60)

        result = await self._hub.set_hold(
            hold_temperature, hold_hours, hold_minutes, [self.data]
        )

        # Optimistically update the mode so that the UI feels snappy.
        # The value will be confirmed next time we get new data.

        self.data.hold_on = True
        self.data.hold_time = timedelta(hours=hold_hours, minutes=hold_minutes)
        self.data.hold_temp = hold_temperature
        self.coordinator.async_update_listeners()
        await self.coordinator.async_request_refresh()

        return result

    async def unset_hold(self):
        """Unsets Hold for Zone."""
        result = await self._hub.set_hold(self.data.hold_temp, 0, 0, [self.data])

        # Optimistically update the mode so that the UI feels snappy.
        # The value will be confirmed next time we get new data.
        self.data.hold_on = False
        self.data.hold_time = timedelta(minutes=0)
        self.coordinator.async_update_listeners()
        await self.coordinator.async_request_refresh()

        return result

    @cached_property
    def supported_features(self):
        """Return the list of supported features."""
        # Do this based on device type

        # All thermostats should have on and off
        supported_features = (
            ClimateEntityFeature.TURN_ON
            | ClimateEntityFeature.TURN_OFF
            | ClimateEntityFeature.PRESET_MODE
        )

        if self.data.device_type in HEATMISER_TYPE_IDS_HC:
            # neoStat-HC
            if self.system_data.GLOBAL_SYSTEM_TYPE not in ["HeatOnly", "CoolOnly"]:
                supported_features = (
                    supported_features | ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
                )
            else:
                supported_features = (
                    supported_features | ClimateEntityFeature.TARGET_TEMPERATURE
                )
            supported_features = supported_features | ClimateEntityFeature.FAN_MODE
        else:
            supported_features = (
                supported_features | ClimateEntityFeature.TARGET_TEMPERATURE
            )

        return supported_features

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return float(self.data.target_temperature)

    @property
    def target_temperature_high(self):
        """Return the temperature we try to reach."""
        return float(self.data.cool_temp)

    @property
    def target_temperature_low(self):
        """Return the temperature we try to reach."""
        return float(self.data.target_temperature)

    @property
    def preset_mode(self) -> str:
        """Return the preset_mode."""
        if self.data.away or self.data.holiday:
            return PRESET_AWAY
        if self.data.hold_on:
            return PRESET_BOOST
        return PRESET_HOME

    @property
    def fan_mode(self) -> str | None:
        """Return the fan setting."""
        if self.data.fan_control != "Manual":
            return FAN_AUTO
        return HEATMISER_FAN_SPEED_HA_FAN_MODE.get(self.data.fan_speed, FAN_OFF)

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set the fan mode/speed."""
        mode = "OFF"
        if fan_mode == FAN_HIGH:
            mode = "HIGH"
        elif fan_mode == FAN_MEDIUM:
            mode = "MED"
        elif fan_mode == FAN_LOW:
            mode = "LOW"
        elif fan_mode == FAN_AUTO:
            mode = "AUTO"
        message = {"SET_FAN_SPEED": [mode, [self.name]]}
        # TODO this should be in the API
        await self._hub._send(message)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set preset mode."""
        device = self.data
        if preset_mode == PRESET_AWAY:
            await self._hub.set_away(True)
            device.away = True
        elif device.away:
            await self._hub.set_away(False)
            device.away = False

        if device.holiday:
            await self._hub.cancel_holiday()
            device.holiday = False
        hold_temp = float(device.target_temperature)
        hold_duration = 0
        hold_on = False
        if preset_mode == PRESET_BOOST:
            hold_temp = hold_temp + DEFAULT_NEOSTAT_TEMPERATURE_BOOST
            hold_duration = DEFAULT_NEOSTAT_HOLD_DURATION
            hold_on = True

        if device.hold_on != hold_on:
            hold_hours, hold_minutes = divmod(hold_duration, 60)
            await self._hub.set_hold(hold_temp, hold_hours, hold_minutes, [device])
            device.hold_temp = hold_temp
            device.hold_on = hold_on
            device.hold_time = timedelta(minutes=hold_duration)

        self.coordinator.async_update_listeners()
        await self.coordinator.async_request_refresh()
