# SPDX-License-Identifier: Apache-2.0 OR GPL-2.0-only
"""Constants used by multiple Heatmiser Neo modules."""

import enum

from homeassistant.const import UnitOfTemperature

DOMAIN = "heatmiserneo"

HUB = "Hub"
COORDINATOR = "Coordinator"

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
ATTR_HOLD_DURATION = "hold_duration"
ATTR_HOLD_STATE = "hold_state"
ATTR_HOLD_TEMPERATURE = "hold_temperature"

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


HEATMISER_TEMPERATURE_UNIT_HA_UNIT = {
    "F": UnitOfTemperature.FAHRENHEIT,
    "C": UnitOfTemperature.CELSIUS,
}
