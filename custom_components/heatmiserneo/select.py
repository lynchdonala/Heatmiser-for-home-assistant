# SPDX-License-Identifier: Apache-2.0 OR GPL-2.0-only

"""Heatmiser Neo Select entities via Heatmiser Neo-hub."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import Final

from neohubapi.neohub import NeoHub, NeoStat
import voluptuous as vol

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import entity_platform
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from . import HeatmiserNeoConfigEntry, hold_duration_validation
from .const import (
    ATTR_HOLD_DURATION,
    ATTR_HOLD_STATE,
    DEFAULT_PLUG_HOLD_DURATION,
    DEFAULT_TIMER_HOLD_DURATION,
    HEATMISER_TYPE_IDS_PLUG,
    HEATMISER_TYPE_IDS_THERMOSTAT,
    HEATMISER_TYPE_IDS_TIMER,
    SERVICE_TIMER_HOLD_ON,
    ModeSelectOption,
)
from .coordinator import HeatmiserNeoCoordinator
from .entity import (
    HeatmiserNeoEntity,
    HeatmiserNeoEntityDescription,
    HeatmiserNeoHubEntity,
    HeatmiserNeoHubEntityDescription,
    call_custom_action,
)

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class HeatmiserNeoSelectEntityDescription(
    HeatmiserNeoEntityDescription, SelectEntityDescription
):
    """Class to describe an Heatmiser Neo select entity."""

    options: list[str]
    value_fn: Callable[[NeoStat], str]
    set_value_fn: Callable[[str, HeatmiserNeoSelectEntity], Awaitable[None]]


@dataclass(frozen=True, kw_only=True)
class HeatmiserNeoHubSelectEntityDescription(
    HeatmiserNeoHubEntityDescription, SelectEntityDescription
):
    """Class to describe an Heatmiser Neo select entity."""

    options: list[str]
    value_fn: Callable[[HeatmiserNeoCoordinator], str]
    set_value_fn: Callable[[str, HeatmiserNeoHubSelectEntity], Awaitable[None]]


async def set_timer_auto(entity: HeatmiserNeoSelectEntity):
    """Set device back to auto based on its current state."""
    dev = entity.data
    if dev.standby:
        await set_timer_standby(entity, False)
    if dev.hold_on:
        await set_timer_override(entity, dev.hold_temp == 1, 0)
    await entity.async_cancel_away_or_holiday()


async def set_timer_away(entity: HeatmiserNeoSelectEntity):
    """Set device back to auto based on its current state."""
    dev = entity.data
    if dev.standby:
        await set_timer_standby(entity, False)
    if dev.hold_on:
        await set_timer_override(entity, dev.hold_temp == 1, 0)
    await entity.async_set_away_mode()


async def set_timer_override(
    entity: HeatmiserNeoSelectEntity,
    on: bool,
    duration: int = DEFAULT_TIMER_HOLD_DURATION,
):
    """Set timer override."""
    dev = entity.data
    state = duration > 0
    if state:
        await entity.async_cancel_away_or_holiday()
        if on and dev.standby:
            await set_timer_standby(entity, False)
    await dev.set_timer_hold(on, duration)
    dev.hold_on = state
    if state:
        dev.timer_on = on
        dev.hold_temp = 1 if on else 0
    dev.hold_time = timedelta(minutes=duration)


async def set_timer_standby(entity: HeatmiserNeoSelectEntity, state: bool = True):
    """Set standby mode. Disable hold if set."""
    dev = entity.data
    if state and dev.hold_on:
        await set_timer_override(entity, dev.hold_temp == 1, 0)
    await dev.set_frost(state)
    dev.standby = state
    if dev.standby:
        dev.timer_on = False


async def set_plug_auto(entity: HeatmiserNeoSelectEntity):
    """Set device back to auto based on its current state."""
    dev = entity.data
    set_plug_override(entity, dev.hold_temp == 1, 0)
    await entity.async_cancel_away_or_holiday()


# async def set_plug_away(entity: HeatmiserNeoSelectEntity):
#     """Set device back to auto based on its current state."""
#     dev = entity.data
#     set_plug_override(entity, dev.hold_temp == 1, 0)
#     await entity.async_set_away_mode()


async def set_plug_override(
    entity: HeatmiserNeoSelectEntity,
    on: bool,
    duration: int = DEFAULT_PLUG_HOLD_DURATION,
    turn_off_manual: bool = True,
):
    """Set timer override. Disable manual if set."""
    dev = entity.data
    hub = entity.coordinator.hub
    state = duration > 0
    if turn_off_manual and not dev.manual_off:
        await hub.set_manual(False, [dev])
        dev.manual_off = True
    if state:
        await entity.async_cancel_away_or_holiday()
    await dev.set_timer_hold(on, duration)
    dev.hold_on = state
    if state:
        dev.timer_on = on
        dev.hold_temp = 1 if on else 0
    dev.hold_time = timedelta(minutes=duration)


async def set_plug_manual(entity: HeatmiserNeoSelectEntity, on: bool):
    """Set standby mode. Disable hold if set."""
    dev = entity.data
    hub = entity.coordinator.hub
    set_plug_override(entity, dev.hold_temp == 1, 0, False)
    if dev.manual_off:
        await hub.set_manual(True, [dev])
        dev.manual_off = False
    if on != dev.timer_on:
        await hub.set_timer(on, [dev])
        dev.timer_on = on


def _timer_mode(device: NeoStat) -> ModeSelectOption:
    """Decode the timer mode."""
    # If Hub Away, Device can be on standby
    # Else if device on Standby, Hold can be enabled
    if device.away or device.holiday:
        if device.standby:
            return ModeSelectOption.STANDBY
        return ModeSelectOption.AWAY
    if device.hold_on:
        if device.hold_temp == 1:
            return ModeSelectOption.OVERRIDE_ON
        return ModeSelectOption.OVERRIDE_OFF
    if device.standby:
        return ModeSelectOption.STANDBY
    return ModeSelectOption.AUTO


def _dst_mode(coordinator: HeatmiserNeoCoordinator) -> str:
    tzstr = coordinator.system_data.TIMEZONESTR
    if not coordinator.system_data.DST_AUTO or tzstr == "":
        if coordinator.system_data.DST_ON:
            return "On"
        return "Off"
    tzstr = coordinator.system_data.TIMEZONESTR
    if not tzstr:
        return "UK"
    return tzstr


async def async_set_dst_mode(coordinator: HeatmiserNeoCoordinator, option: str):
    """Update the DST mode."""
    if option in ("Off", "On"):
        dst_on = option == "On"
        await async_set_dst(coordinator)
        await coordinator.hub.manual_dst(dst_on)
        setattr(coordinator.system_data, "DST_AUTO", False)
        setattr(coordinator.system_data, "DST_ON", dst_on)
        setattr(coordinator.system_data, "TIMEZONESTR", "")
    else:
        await async_set_dst(coordinator, option)
        setattr(coordinator.system_data, "DST_AUTO", True)
        setattr(coordinator.system_data, "TIMEZONESTR", option)


def _timer_icon(device: NeoStat) -> str | None:
    if device.away or device.holiday:
        if device.standby:
            return "mdi:timer-off-outline"
        return "mdi:account-arrow-right"
    if device.hold_on:
        if device.hold_temp == 1:
            return "mdi:timer-stop"
        return "mdi:timer-stop-outline"
    if device.standby:
        return "mdi:timer-off-outline"
    return "mdi:timer" if device.timer_on else "mdi:timer-outline"


def _plug_mode(device: NeoStat) -> ModeSelectOption:
    if not device.manual_off:
        if device.timer_on:
            return ModeSelectOption.MANUAL_ON
        return ModeSelectOption.MANUAL_OFF
    # if device.away or device.holiday:
    #     return ModeSelectOption.AWAY
    if device.hold_on:
        if device.hold_temp == 1:
            return ModeSelectOption.OVERRIDE_ON
        return ModeSelectOption.OVERRIDE_OFF
    return ModeSelectOption.AUTO


def _plug_icon(device: NeoStat) -> str | None:
    if not device.manual_off:
        if device.timer_on:
            return "mdi:toggle-switch-variant"
        return "mdi:toggle-switch-variant-off"
    if device.hold_on:
        if device.hold_temp == 1:
            return "mdi:timer-stop"
        return "mdi:timer-stop-outline"
    return "mdi:timer" if device.timer_on else "mdi:timer-outline"


async def async_timer_hold(entity: HeatmiserNeoSelectEntity, service_call: ServiceCall):
    """Set override with custom duration."""
    duration = service_call.data[ATTR_HOLD_DURATION]
    state = service_call.data[ATTR_HOLD_STATE]
    hold_minutes = int(duration.total_seconds() / 60)
    hold_minutes = min(hold_minutes, 60 * 99)
    await set_timer_override(entity, state, hold_minutes)
    entity.coordinator.async_update_listeners()


async def async_plug_hold(entity: HeatmiserNeoSelectEntity, service_call: ServiceCall):
    """Set override with custom duration."""
    duration = service_call.data[ATTR_HOLD_DURATION]
    state = service_call.data[ATTR_HOLD_STATE]
    hold_minutes = int(duration.total_seconds() / 60)
    hold_minutes = min(hold_minutes, 60 * 99)
    await set_plug_override(entity, state, hold_minutes)
    entity.coordinator.async_update_listeners()


async def async_set_switching_differential(
    val: str, entity: HeatmiserNeoEntity
) -> None:
    """Set the switching differential on a device."""
    message = {"SET_DIFF": [int(val), [entity.data.name]]}
    # TODO this should be in the API
    await entity.coordinator.hub._send(message)  # noqa: SLF001
    setattr(entity.data._data_, "SWITCHING DIFFERENTIAL", int(val))


async def async_set_preheat(
    val: str,
    entity: HeatmiserNeoEntity,
) -> None:
    """Set the maximum preheat time on a device."""
    message = {"SET_PREHEAT": [int(val), [entity.data.name]]}
    # TODO this should be in the API
    await entity.coordinator.hub._send(message)  # noqa: SLF001
    setattr(entity.data._data_, "MAX_PREHEAT", int(val))


TIMER_SET_MODE = {
    ModeSelectOption.AUTO: set_timer_auto,
    ModeSelectOption.OVERRIDE_ON: lambda entity: set_timer_override(entity, True),
    ModeSelectOption.OVERRIDE_OFF: lambda entity: set_timer_override(entity, False),
    ModeSelectOption.STANDBY: set_timer_standby,
    ModeSelectOption.AWAY: set_timer_away,
}

PLUG_SET_MODE = {
    ModeSelectOption.AUTO: set_plug_auto,
    ModeSelectOption.OVERRIDE_ON: lambda entity: set_plug_override(entity, True),
    ModeSelectOption.OVERRIDE_OFF: lambda entity: set_plug_override(entity, False),
    ModeSelectOption.MANUAL_ON: lambda entity: set_plug_manual(entity, True),
    ModeSelectOption.MANUAL_OFF: lambda entity: set_plug_manual(entity, False),
    # ModeSelectOption.AWAY: set_plug_away,
}

SELECT: Final[tuple[HeatmiserNeoSelectEntityDescription, ...]] = (
    HeatmiserNeoSelectEntityDescription(
        key="heatmiser_neo_timer_mode_select",
        name=None,  # This is the main entity of the device
        options=[c.value.lower() for c in TIMER_SET_MODE],
        setup_filter_fn=lambda device, _: (
            device.device_type
            in HEATMISER_TYPE_IDS_TIMER.difference(HEATMISER_TYPE_IDS_PLUG)
            and device.time_clock_mode
        ),
        value_fn=lambda dev: _timer_mode(dev).value,
        set_value_fn=lambda mode, entity: TIMER_SET_MODE.get(ModeSelectOption(mode))(
            entity
        ),
        icon_fn=_timer_icon,
        translation_key="timer_mode",
        custom_functions={SERVICE_TIMER_HOLD_ON: async_timer_hold},
    ),
    HeatmiserNeoSelectEntityDescription(
        key="heatmiser_neo_plug_mode_select",
        name=None,  # This is the main entity of the device
        options=[c.value.lower() for c in PLUG_SET_MODE],
        setup_filter_fn=lambda device, _: device.device_type in HEATMISER_TYPE_IDS_PLUG,
        value_fn=lambda dev: _plug_mode(dev).value,
        set_value_fn=lambda mode, entity: PLUG_SET_MODE.get(ModeSelectOption(mode))(
            entity
        ),
        icon_fn=_plug_icon,
        translation_key="plug_mode",
        custom_functions={SERVICE_TIMER_HOLD_ON: async_plug_hold},
    ),
    HeatmiserNeoSelectEntityDescription(
        key="heatmiser_neo_switching_differential",
        options=[str(n) for n in range(4)],
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        setup_filter_fn=lambda device, _: (
            device.device_type in HEATMISER_TYPE_IDS_THERMOSTAT
            and not device.time_clock_mode
        ),
        value_fn=lambda dev: str(getattr(dev._data_, "SWITCHING DIFFERENTIAL")),
        set_value_fn=async_set_switching_differential,
        translation_key="switching_differential",
    ),
    HeatmiserNeoSelectEntityDescription(
        key="heatmiser_neo_preheat_time",
        options=[str(n) for n in range(4)],
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        setup_filter_fn=lambda device, _: (
            device.device_type in HEATMISER_TYPE_IDS_THERMOSTAT
            and not device.time_clock_mode
        ),
        value_fn=lambda dev: str(dev._data_.MAX_PREHEAT),
        set_value_fn=async_set_preheat,
        translation_key="preheat_time",
    ),
)

HUB_SELECT: Final[tuple[HeatmiserNeoHubSelectEntityDescription, ...]] = (
    HeatmiserNeoHubSelectEntityDescription(
        key="heatmiser_neohub_dst_rule",
        name="DST Rule",
        options=["UK", "EU", "NZ", "Off", "On"],
        value_fn=_dst_mode,
        set_value_fn=lambda mode, entity: async_set_dst_mode(entity.coordinator, mode),
    ),
    HeatmiserNeoHubSelectEntityDescription(
        key="heatmiser_neohub_time_zone",
        # name="DST Rule",
        options=[
            "tz-12",
            "tz-11",
            "tz-10",
            "tz-9.5",
            "tz-9",
            "tz-8",
            "tz-7",
            "tz-6",
            "tz-5",
            "tz-4",
            "tz-3.5",
            "tz-3",
            "tz-2",
            "tz-1",
            "tz0",
            "tz1",
            "tz2",
            "tz3",
            "tz3.5",
            "tz4",
            "tz4.5",
            "tz5",
            "tz5.5",
            "tz5.75",
            "tz6",
            "tz6.5",
            "tz7",
            "tz8",
            "tz8.75",
            "tz9",
            "tz9.5",
            "tz10",
            "tz10.5",
            "tz11",
            "tz12",
            "tz12.75",
            "tz13",
            "tz14",
        ],
        value_fn=lambda coordinator: f"tz{coordinator.system_data.TIME_ZONE:g}",
        set_value_fn=lambda timezone, entity: async_set_timezone(
            entity.coordinator, timezone
        ),
        translation_key="time_zone",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HeatmiserNeoConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Heatmiser Neo select entities."""
    hub = entry.runtime_data.hub
    coordinator = entry.runtime_data.coordinator

    if coordinator.data is None:
        _LOGGER.error("Coordinator data is None. Cannot set up button entities")
        return

    neo_devices, _ = coordinator.data
    system_data = coordinator.system_data

    _LOGGER.info("Adding Neo Select entities")

    async_add_entities(
        HeatmiserNeoSelectEntity(neodevice, coordinator, hub, description)
        for description in SELECT
        for neodevice in neo_devices.values()
        if description.setup_filter_fn(neodevice, system_data)
    )

    async_add_entities(
        HeatmiserNeoHubSelectEntity(coordinator, hub, description)
        for description in HUB_SELECT
        if description.setup_filter_fn(coordinator)
    )
    platform = entity_platform.async_get_current_platform()

    platform.async_register_entity_service(
        SERVICE_TIMER_HOLD_ON,
        {
            vol.Required(ATTR_HOLD_DURATION, default=1): hold_duration_validation,
            vol.Optional(ATTR_HOLD_STATE, default=True): cv.boolean,
        },
        call_custom_action,
    )


class HeatmiserNeoSelectEntity(HeatmiserNeoEntity, SelectEntity):
    """Define an Heatmiser Neo select."""

    entity_description: HeatmiserNeoSelectEntityDescription

    def __init__(
        self,
        neostat: NeoStat,
        coordinator: DataUpdateCoordinator,
        hub: NeoHub,
        entity_description: HeatmiserNeoSelectEntityDescription,
    ) -> None:
        """Initialize Heatmiser Neo select entity."""
        super().__init__(
            neostat,
            coordinator,
            hub,
            entity_description,
        )
        self._attr_current_option = entity_description.value_fn(neostat)

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        await self.entity_description.set_value_fn(option, self)
        self.coordinator.async_update_listeners()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._attr_current_option = self.entity_description.value_fn(self.data)
        super()._handle_coordinator_update()


class HeatmiserNeoHubSelectEntity(HeatmiserNeoHubEntity, SelectEntity):
    """Define an Heatmiser Neo Hub select."""

    entity_description: HeatmiserNeoHubSelectEntityDescription

    def __init__(
        self,
        coordinator: HeatmiserNeoCoordinator,
        hub: NeoHub,
        entity_description: HeatmiserNeoHubSelectEntityDescription,
    ) -> None:
        """Initialize Heatmiser Neo select entity."""
        super().__init__(
            coordinator,
            hub,
            entity_description,
        )
        self._attr_current_option = entity_description.value_fn(coordinator)

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        await self.entity_description.set_value_fn(option, self)
        self.coordinator.async_update_listeners()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._attr_current_option = self.entity_description.value_fn(self.coordinator)
        super()._handle_coordinator_update()


async def async_set_dst(
    coordinator: HeatmiserNeoCoordinator, region: str | None = None
) -> None:
    """Set DST mode."""
    message = {"DST_ON" if region else "DST_OFF": region if region else 0}
    # TODO API implementation is broken. Doesn't work for DST_OFF
    await coordinator.hub._send(message)  # noqa: SLF001


async def async_set_timezone(
    coordinator: HeatmiserNeoCoordinator, timezone: str
) -> None:
    """Set DST mode."""
    # need to strip the leading 'tz'
    message = {"TIME_ZONE": float(timezone[2:])}
    # TODO Should be added to API
    await coordinator.hub._send(message)  # noqa: SLF001
