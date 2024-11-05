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

from homeassistant.components.select import SelectEntity
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
    HEATMISER_TYPE_IDS_TIMER,
    SERVICE_TIMER_HOLD_ON,
    ModeSelectOption,
)
from .entity import (
    HeatmiserNeoEntity,
    HeatmiserNeoEntityDescription,
    call_custom_action,
)

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class HeatmiserNeoSelectEntityDescription(HeatmiserNeoEntityDescription):
    """Class to describe an Heatmiser Neo select entity."""

    options: list[str]
    value_fn: Callable[[NeoStat], str]
    set_value_fn: Callable[[str, HeatmiserNeoSelectEntity], Awaitable[None]]


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
    if state and (dev.away or dev.holiday):
        # Can't enable hold while away/holiday
        return
    if state and on and dev.standby:
        await set_timer_standby(dev, False)
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
        await set_timer_override(dev, dev.hold_temp == 1, 0)
    await dev.set_frost(state)
    dev.standby = state
    if dev.standby:
        dev.timer_on = False


async def set_plug_auto(entity: HeatmiserNeoSelectEntity):
    """Set device back to auto based on its current state."""
    dev = entity.data
    set_plug_override(entity, dev.hold_temp == 1, 0)
    await entity.async_cancel_away_or_holiday()


async def set_plug_away(entity: HeatmiserNeoSelectEntity):
    """Set device back to auto based on its current state."""
    dev = entity.data
    set_plug_override(entity, dev.hold_temp == 1, 0)
    await entity.async_set_away_mode()


async def set_plug_override(
    entity: HeatmiserNeoSelectEntity,
    on: bool,
    duration: int = DEFAULT_PLUG_HOLD_DURATION,
    turn_off_manual: bool = True,
):
    """Set timer override. Disable manual if set."""
    dev = entity.data
    hub = entity.coordinator.hub
    if turn_off_manual and not dev.manual_off:
        await hub.set_manual(False, [dev])
        dev.manual_off = True
    desired_state = duration > 0
    if dev.hold_on != desired_state:
        await dev.set_timer_hold(on, duration)
        state = duration > 0
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


def _timer_icon(device: NeoStat) -> str | None:
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
    if device.hold_on:
        if device.hold_temp == 1:
            return ModeSelectOption.OVERRIDE_ON
        return ModeSelectOption.OVERRIDE_OFF
    # if device.away or device.holiday:
    #     return ModeSelectOption.AWAY
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


async def async_plug_hold(entity: HeatmiserNeoSelectEntity, service_call: ServiceCall):
    """Set override with custom duration."""
    duration = service_call.data[ATTR_HOLD_DURATION]
    state = service_call.data[ATTR_HOLD_STATE]
    hold_minutes = int(duration.total_seconds() / 60)
    hold_minutes = min(hold_minutes, 60 * 99)
    await set_plug_override(entity, state, hold_minutes)


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

    neo_devices, system_data = coordinator.data

    _LOGGER.info("Adding Neo Device Buttons")

    async_add_entities(
        HeatmiserNeoSelectEntity(neodevice, coordinator, hub, description)
        for description in SELECT
        for neodevice in neo_devices.values()
        if description.setup_filter_fn(neodevice, system_data)
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
