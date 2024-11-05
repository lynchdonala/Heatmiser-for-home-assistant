# SPDX-License-Identifier: Apache-2.0 OR GPL-2.0-only
"""Constants used by multiple Heatmiser Neo modules."""

from neohubapi.neohub import NeoStat


def set_away(state: bool, dev: NeoStat) -> None:
    """Set away flag on device."""
    dev.away = state
    if state:
        dev.target_temperature = dev._data_.FROST_TEMP


def cancel_holiday(dev: NeoStat) -> None:
    """Cancel holiday on device."""
    dev.holiday = False
