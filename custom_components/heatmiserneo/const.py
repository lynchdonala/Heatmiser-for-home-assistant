# SPDX-License-Identifier: Apache-2.0 OR GPL-2.0-only
"""Constants used by multiple Heatmiser Neo modules."""

import enum

from homeassistant.components.climate import (
    FAN_AUTO,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    UnitOfTemperature,
)

DOMAIN = "heatmiserneo"

DEFAULT_HOST = "Neo-Hub"
DEFAULT_PORT = 4242
DEFAULT_TOKEN = ""

DEFAULT_TIMER_HOLD_DURATION = 30
DEFAULT_PLUG_HOLD_DURATION = 30
DEFAULT_NEOSTAT_HOLD_DURATION = 30
DEFAULT_NEOSTAT_TEMPERATURE_BOOST = 2

CONF_HVAC_MODES = "hvac_modes"

SERVICE_HOLD_ON = "hold_on"
SERVICE_HOLD_OFF = "hold_off"
SERVICE_TIMER_HOLD_ON = "timer_hold_on"
SERVICE_HUB_AWAY = "set_away_mode"
ATTR_HOLD_DURATION = "hold_duration"
ATTR_HOLD_STATE = "hold_state"
ATTR_HOLD_TEMPERATURE = "hold_temperature"
ATTR_AWAY_STATE = "away"
# ATTR_AWAY_START = "start"
ATTR_AWAY_END = "end"

PROFILE_0 = "PROFILE_0"

HEATMISER_HUB_PRODUCT_LIST = [
    "NULL",
    "NeoHub Version 1",
    "NeoHub Version 2",
    "NeoHub Mini",
]

HEATMISER_PRODUCT_LIST = [
    "NULL",
    "NeoStat V1",
    "SmartStat",
    "CoolSwitch",
    "TCM RH",
    "Contact Sensor",
    "Neo Plug",
    "NeoAir",
    "SmartStat HC",
    "NeoAir HW",
    "Repeater",
    "NeoStat HC",
    "NeoStat V2",
    "NeoAir V2",
    "Air Sensor",
    "NeoAir V2 Combo",
    "RF Switch Wifi",
    "Edge WiFi",
]

HEATMISER_TYPE_IDS_THERMOSTAT = {1, 2, 7, 8, 9, 11, 12, 13, 15, 17}
HEATMISER_TYPE_IDS_TIMER = {1, 2, 6, 7, 8, 9, 11, 12, 13, 15, 17}
HEATMISER_TYPE_IDS_PLUG = {6}
HEATMISER_TYPE_IDS_HC = {8, 11}
HEATMISER_TYPE_IDS_REPEATER = {10}
HEATMISER_TYPE_IDS_THERMOSTAT_NOT_HC = HEATMISER_TYPE_IDS_THERMOSTAT.difference(
    HEATMISER_TYPE_IDS_HC
)
HEATMISER_TYPE_IDS_AWAY = HEATMISER_TYPE_IDS_THERMOSTAT.union(HEATMISER_TYPE_IDS_TIMER)
HEATMISER_TYPE_IDS_STANDBY = HEATMISER_TYPE_IDS_AWAY.difference(HEATMISER_TYPE_IDS_PLUG)
HEATMISER_TYPE_IDS_HOLD = HEATMISER_TYPE_IDS_THERMOSTAT.union(HEATMISER_TYPE_IDS_TIMER)
HEATMISER_TYPE_IDS_IDENTIFY = HEATMISER_TYPE_IDS_THERMOSTAT.union(
    HEATMISER_TYPE_IDS_TIMER
).difference(HEATMISER_TYPE_IDS_PLUG)


# This should be in the neohubapi.neohub enums code
class AvailableMode(str, enum.Enum):
    """Operating mode options for NeoStats."""

    HEAT = "heat"
    COOL = "cool"
    VENT = "vent"
    AUTO = "auto"


class ModeSelectOption(str, enum.Enum):
    """Operating mode options for NeoPlugs and NeoStats in timer mode."""

    AUTO = "auto"
    OVERRIDE_OFF = "override_off"
    OVERRIDE_ON = "override_on"
    STANDBY = "standby"
    MANUAL_ON = "on"
    MANUAL_OFF = "off"
    AWAY = "away"


HEATMISER_TEMPERATURE_UNIT_HA_UNIT = {
    "F": UnitOfTemperature.FAHRENHEIT,
    "C": UnitOfTemperature.CELSIUS,
}

HEATMISER_FAN_SPEED_HA_FAN_MODE = {
    "High": FAN_HIGH,
    "Medium": FAN_MEDIUM,
    "Low": FAN_LOW,
    "Auto": FAN_AUTO,
}


class FanControl(str, enum.Enum):
    """Fan control mode options for NeoStat HC."""

    MANUAL = "Manual"
    AUTOMATIC = "Automatic"
