# SPDX-License-Identifier: Apache-2.0 OR GPL-2.0-only
"""Constants used by multiple Heatmiser Neo modules."""

from neohubapi.enums import ScheduleFormat, Weekday
from neohubapi.neohub import NeoStat

from .coordinator import HeatmiserNeoCoordinator


def set_away(state: bool, dev: NeoStat) -> None:
    """Set away flag on device."""
    dev.away = state
    if state:
        dev.target_temperature = dev._data_.FROST_TEMP


def cancel_holiday(dev: NeoStat) -> None:
    """Cancel holiday on device."""
    dev.holiday = False


def _profile_current_day_key(
    current_weekday: Weekday, format: ScheduleFormat
) -> Weekday:
    match format:
        case ScheduleFormat.ONE:
            return Weekday.SUNDAY
        case ScheduleFormat.TWO:
            match current_weekday:
                case Weekday.SATURDAY | Weekday.SUNDAY:
                    return Weekday.SUNDAY
                case _:
                    return Weekday.MONDAY
    return current_weekday


def _profile_next_day_key(current_weekday: str, format: ScheduleFormat) -> Weekday:
    match format:
        case ScheduleFormat.ONE:
            return Weekday.SUNDAY
        case ScheduleFormat.TWO:
            match current_weekday:
                case Weekday.FRIDAY | Weekday.SATURDAY:
                    return Weekday.SUNDAY
                case _:
                    return Weekday.MONDAY
        case _:
            match current_weekday:
                case Weekday.MONDAY:
                    return Weekday.TUESDAY
                case Weekday.TUESDAY:
                    return Weekday.WEDNESDAY
                case Weekday.WEDNESDAY:
                    return Weekday.THURSDAY
                case Weekday.THURSDAY:
                    return Weekday.FRIDAY
                case Weekday.FRIDAY:
                    return Weekday.SATURDAY
                case Weekday.SATURDAY:
                    return Weekday.SUNDAY
                case _:
                    return Weekday.MONDAY


def _profile_previous_day_key(current_weekday: str, format: ScheduleFormat) -> Weekday:
    match format:
        case ScheduleFormat.ONE:
            return Weekday.SUNDAY
        case ScheduleFormat.TWO:
            match current_weekday:
                case Weekday.SUNDAY | Weekday.MONDAY:
                    return Weekday.SUNDAY
                case _:
                    return Weekday.MONDAY
        case _:
            match current_weekday:
                case Weekday.MONDAY:
                    return Weekday.SUNDAY
                case Weekday.TUESDAY:
                    return Weekday.MONDAY
                case Weekday.WEDNESDAY:
                    return Weekday.TUESDAY
                case Weekday.THURSDAY:
                    return Weekday.WEDNESDAY
                case Weekday.FRIDAY:
                    return Weekday.THURSDAY
                case Weekday.SATURDAY:
                    return Weekday.FRIDAY
                case _:
                    return Weekday.SATURDAY


def _profile_levels(profile, key: Weekday) -> list:
    info = None
    if hasattr(profile, "info"):
        info = profile.info
    else:
        # Profile 0
        info = profile.profiles[0]
    key_val = key.value
    levels = getattr(info, key_val)
    levels = [lv for lv in levels.__dict__.values() if lv[0] != "24:00"]
    return sorted(levels, key=lambda lv: lv[0])


def _flatten_timer_levels(levels):
    levels = [[[lv[0], True], [lv[1], False]] for lv in levels]
    return [x for lvs in levels for x in lvs]


def _current_level(time: str, levels):
    current = None
    for lv in levels:
        if time < lv[0]:
            return current
        current = lv
    return current


def _next_level(time: str, levels):
    previous_time = None
    for lv in levels:
        if previous_time and lv[0] < previous_time:
            return lv
        if time < lv[0]:
            return lv
        previous_time = lv[0]
    return None


def profile_level(
    profile_id, data: NeoStat, coordinator: HeatmiserNeoCoordinator, next: bool = False
) -> str | None:
    """Convert a profile id to a name."""
    profile_format = coordinator.system_data.FORMAT
    device_time = data._data_.TIME
    device_weekday = data.weekday
    if len(device_time) == 4:
        device_time = f"0{device_time}"
    profile = None
    if profile_id == 0:
        profile = coordinator.profiles_0.get(data.device_id)
    else:
        profile = coordinator.profiles.get(int(profile_id))
    flatten_fn = None
    if not profile:
        if profile_format == ScheduleFormat.ZERO:
            profile_format = coordinator.system_data.ALT_TIMER_FORMAT

        if profile_id == 0:
            profile = coordinator.timer_profiles_0.get(data.device_id)
        else:
            profile = coordinator.timer_profiles.get(int(profile_id))
        flatten_fn = _flatten_timer_levels
    if profile:
        current_day_key = _profile_current_day_key(device_weekday, profile_format)
        levels = _profile_levels(profile, current_day_key)
        if flatten_fn:
            levels = flatten_fn(levels)
        current_level = (
            _next_level(device_time, levels)
            if next
            else _current_level(device_time, levels)
        )
        if not current_level:
            alt_key = (
                _profile_next_day_key(device_weekday, profile_format)
                if next
                else _profile_previous_day_key(device_weekday, profile_format)
            )
            levels = _profile_levels(profile, alt_key)
            current_level = levels[0 if next else -1]
        return current_level
    return None
