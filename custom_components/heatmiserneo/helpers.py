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


def set_holiday(state: bool, dev: NeoStat) -> None:
    """Cancel holiday on device."""
    dev.holiday = state


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


def _profile_levels(profile, key: Weekday, filter) -> list:
    info = None
    if hasattr(profile, "info"):
        info = profile.info
    else:
        # Profile 0
        info = profile.profiles[0]
    key_val = key.value
    levels = getattr(info, key_val)
    levels = [lv for lv in levels.__dict__.values() if filter(lv)]
    return sorted(levels, key=lambda lv: lv[0])


def _timer_level_filter(level):
    if not _is_valid_time(level[0]):
        return False
    if level[0] == level[1]:
        return False
    return True


def _heating_level_filter(level):
    if not _is_valid_time(level[0]):
        return False
    if level[1] < 5:
        return False
    if len(level) > 2:
        if level[2] < 5 and level[3]:
            return False
    return True


def _is_valid_time(time) -> bool:
    return time == "24:00" or time > "24:00"


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
    flatten_fn = None
    levels_filter = _heating_level_filter
    if data.time_clock_mode:
        if profile_format == ScheduleFormat.ZERO:
            profile_format = coordinator.system_data.ALT_TIMER_FORMAT

        if profile_id == 0:
            profile = coordinator.timer_profiles_0.get(data.device_id)
        else:
            profile = coordinator.timer_profiles.get(int(profile_id))

        flatten_fn = _flatten_timer_levels
        levels_filter = _timer_level_filter
    else:
        if profile_format == ScheduleFormat.ZERO:
            return None
        if profile_id == 0:
            profile = coordinator.profiles_0.get(data.device_id)
        else:
            profile = coordinator.profiles.get(int(profile_id))

    if hasattr(profile, "error") or not profile:
        return None

    current_day_key = _profile_current_day_key(device_weekday, profile_format)
    levels = _profile_levels(profile, current_day_key, levels_filter)
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
        levels = _profile_levels(profile, alt_key, levels_filter)
        if flatten_fn:
            levels = flatten_fn(levels)
        if len(levels) == 0:
            return None
        current_level = levels[0 if next else -1]
        if data.time_clock_mode and not next:
            previous_level = levels[-2]
            if current_level[0] < previous_level[0] and current_level[0] > device_time:
                ## Its just after midnight and we haven't reached the last profile time
                ## so look at the one before
                current_level = previous_level
    elif data.time_clock_mode and next and current_level[0] == levels[0][0]:
        ## need to check previous day as well if its the first level
        alt_key = _profile_previous_day_key(device_weekday, profile_format)
        levels = _profile_levels(profile, alt_key, levels_filter)
        if flatten_fn:
            levels = flatten_fn(levels)
        previous_level = levels[-1]
        if previous_level[0] < current_level[0] and previous_level[0] > device_time:
            ## Its just after midnight and we haven't reached the last profile time
            ## so that is the next level
            current_level = previous_level
    return current_level


def to_dict(item):
    """Convert an arbitrary object to a dict."""
    match item:
        case dict():
            return {key: to_dict(value) for key, value in item.items()}
        case list() | tuple():
            return [to_dict(x) for x in item]
        case object(__dict__=_):
            return {key: to_dict(value) for key, value in vars(item).items()}
        case _:
            return item


def get_profile_definition(
    profile_id: int,
    coordinator: HeatmiserNeoCoordinator,
    friendly_mode: bool = False,
    device_id: int = 0,
):
    """Set override with custom duration."""
    profile_format = coordinator.system_data.FORMAT
    profile = None
    p0 = False
    timer = False
    if profile_id == 0:
        profile = coordinator.profiles_0.get(device_id)
        p0 = True
    else:
        profile = coordinator.profiles.get(profile_id)
    if not profile:
        if profile_format == ScheduleFormat.ZERO:
            profile_format = coordinator.system_data.ALT_TIMER_FORMAT

        if profile_id == 0:
            profile = coordinator.timer_profiles_0.get(device_id)
        else:
            profile = coordinator.timer_profiles.get(profile_id)
        if profile:
            timer = True
    if not profile:
        return None
    profile_dict = to_dict(profile)

    levels = None
    info = None
    if p0:
        info = profile_dict.get("profiles")[0]
        del info["device"]
    else:
        info = profile_dict.get("info")

    result = {"id": profile_id, "name": "PROFILE_0" if p0 else profile_dict["name"]}

    if friendly_mode:
        result["format"] = profile_format
        result["type"] = "timer" if timer else "heating"

    if timer:
        if friendly_mode:
            levels = {
                wd: [
                    {"time_on": e[0], "time_off": e[1]}
                    for e in sorted(lv.values(), key=lambda x: x[0])
                    if _is_valid_time(e[0])
                ]
                for wd, lv in info.items()
            }

            result["info"] = levels
        else:
            on_times = {
                wd + "_on_times": [
                    e[0]
                    for e in sorted(lv.values(), key=lambda x: x[0])
                    if _is_valid_time(e[0])
                ]
                for wd, lv in info.items()
            }
            off_times = {
                wd + "_off_times": [
                    e[1]
                    for e in sorted(lv.values(), key=lambda x: x[0])
                    if _is_valid_time(e[0])
                ]
                for wd, lv in info.items()
            }
            times = on_times | off_times
            times = dict(sorted(times.items(), reverse=True))

            result = result | times
    elif friendly_mode:
        levels = {
            wd: [
                {"time": e[0], "temperature": e[1]}
                for e in sorted(lv.values(), key=lambda x: x[0])
                if _is_valid_time(e[0])
            ]
            for wd, lv in info.items()
        }
        result["info"] = levels
    else:
        times = {
            wd + "_times": [
                e[0]
                for e in sorted(lv.values(), key=lambda x: x[0])
                if _is_valid_time(e[0])
            ]
            for wd, lv in info.items()
        }
        temperatures = {
            wd + "_temperatures": [
                e[1]
                for e in sorted(lv.values(), key=lambda x: x[0])
                if _is_valid_time(e[0])
            ]
            for wd, lv in info.items()
        }
        levels = times | temperatures
        levels = dict(sorted(levels.items(), reverse=True))
        result = result | levels

    return result
