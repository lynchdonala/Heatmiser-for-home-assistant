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
    set_value_fn: Callable[[str, NeoStat, NeoHub], Awaitable[None]]


async def set_timer_auto(dev: NeoStat):
    """Set device back to auto based on its current state."""
    if dev.standby:
        await set_timer_standby(dev, False)
    else:
        await set_timer_override(dev, dev.hold_temp == 1, 0)


async def set_timer_override(
    dev: NeoStat, on: bool, duration: int = DEFAULT_TIMER_HOLD_DURATION
):
    """Set timer override."""
    state = duration > 0
    await dev.set_timer_hold(on, duration)
    dev.hold_on = state
    if state:
        dev.timer_on = on
    dev.hold_time = timedelta(minutes=duration)


async def set_timer_standby(dev: NeoStat, state: bool = True):
    """Set standby mode. Disable hold if set."""
    if dev.hold_on:
        await set_timer_override(dev, dev.hold_temp == 1, 0)
    await dev.set_frost(state)
    dev.standby = state
    if dev.standby:
        dev.timer_on = False


async def set_plug_auto(dev: NeoStat, hub: NeoHub):
    """Set device back to auto based on its current state."""
    set_plug_override(dev, hub, dev.hold_temp == 1, 0)


async def set_plug_override(
    dev: NeoStat,
    hub: NeoHub,
    on: bool,
    duration: int = DEFAULT_PLUG_HOLD_DURATION,
    turn_off_manual: bool = True,
):
    """Set timer override. Disable manual if set."""
    if turn_off_manual and not dev.manual_off:
        await hub.set_manual(False, [dev])
        dev.data.manual_off = True
    desired_state = duration > 0
    if dev.hold_on != desired_state:
        await dev.set_timer_hold(on, duration)
        state = duration > 0
        dev.hold_on = state
        if state:
            dev.timer_on = on
        dev.hold_time = timedelta(minutes=duration)


async def set_plug_manual(dev: NeoStat, hub: NeoHub, on: bool):
    """Set standby mode. Disable hold if set."""
    set_plug_override(dev, hub, dev.hold_temp == 1, 0, False)
    if dev.manual_off:
        await hub.set_manual(True, [dev])
        dev.manual_off = False
    if on != dev.timer_on:
        await hub.set_timer(on, [dev])
        dev.timer_on = on


def _timer_mode(device: NeoStat) -> ModeSelectOption:
    if device.hold_on:
        if device.hold_temp == 1:
            return ModeSelectOption.OVERRIDE_ON
        return ModeSelectOption.OVERRIDE_OFF
    if device.standby:
        return ModeSelectOption.STANDBY
    return ModeSelectOption.AUTO


def _plug_mode(device: NeoStat) -> ModeSelectOption:
    if not device.manual_off:
        if device.timer_on:
            return ModeSelectOption.MANUAL_ON
        return ModeSelectOption.MANUAL_OFF
    if device.hold_on:
        if device.hold_temp == 1:
            return ModeSelectOption.OVERRIDE_ON
        return ModeSelectOption.OVERRIDE_OFF
    return ModeSelectOption.AUTO


async def async_timer_hold(device: NeoStat, hub: NeoHub, service_call: ServiceCall):
    """Set override with custom duration."""
    duration = service_call.data[ATTR_HOLD_DURATION]
    state = service_call.data[ATTR_HOLD_STATE]
    hold_minutes = int(duration.total_seconds() / 60)
    hold_minutes = min(hold_minutes, 60 * 99)
    await set_timer_override(device, state, hold_minutes)


async def async_plug_hold(device: NeoStat, hub: NeoHub, service_call: ServiceCall):
    """Set override with custom duration."""
    duration = service_call.data[ATTR_HOLD_DURATION]
    state = service_call.data[ATTR_HOLD_STATE]
    hold_minutes = int(duration.total_seconds() / 60)
    hold_minutes = min(hold_minutes, 60 * 99)
    await set_plug_override(device, hub, state, hold_minutes)


TIMER_SET_MODE = {
    ModeSelectOption.AUTO: lambda dev, _: set_timer_auto(dev),
    ModeSelectOption.OVERRIDE_ON: lambda dev, _: set_timer_override(dev, True),
    ModeSelectOption.OVERRIDE_OFF: lambda dev, _: set_timer_override(dev, False),
    ModeSelectOption.STANDBY: lambda dev, _: set_timer_standby(dev),
}

PLUG_SET_MODE = {
    ModeSelectOption.AUTO: set_plug_auto,
    ModeSelectOption.OVERRIDE_ON: lambda dev, hub: set_plug_override(dev, hub, True),
    ModeSelectOption.OVERRIDE_OFF: lambda dev, hub: set_plug_override(dev, hub, False),
    ModeSelectOption.MANUAL_ON: lambda dev, hub: set_plug_manual(dev, hub, True),
    ModeSelectOption.MANUAL_OFF: lambda dev, hub: set_plug_manual(dev, hub, False),
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
        set_value_fn=lambda mode, dev, hub: TIMER_SET_MODE.get(ModeSelectOption(mode))(
            dev, hub
        ),
        translation_key="timer_mode",
        custom_functions={SERVICE_TIMER_HOLD_ON: async_timer_hold},
    ),
    HeatmiserNeoSelectEntityDescription(
        key="heatmiser_neo_plug_mode_select",
        name=None,  # This is the main entity of the device
        options=[c.value.lower() for c in PLUG_SET_MODE],
        setup_filter_fn=lambda device, _: device.device_type in HEATMISER_TYPE_IDS_PLUG,
        value_fn=lambda dev: _plug_mode(dev).value,
        set_value_fn=lambda mode, dev, hub: PLUG_SET_MODE.get(ModeSelectOption(mode))(
            dev, hub
        ),
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

    devices_data, system_data = coordinator.data

    neo_devices = {device.name: device for device in devices_data["neo_devices"]}
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

    @property
    def current_option(self) -> str | None:
        """Return the selected entity option to represent the entity state."""
        return self.entity_description.value_fn(self.data)

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        await self.entity_description.set_value_fn(option, self.data, self._hub)
        self.coordinator.async_update_listeners()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._attr_current_option = self.entity_description.value_fn(self.data)
        super()._handle_coordinator_update()


def _timer_mode(device: NeoStat) -> str:
    if device.hold_on:
        if device.hold_temp == 1:
            return ModeSelectOption.OVERRIDE_ON
        return ModeSelectOption.OVERRIDE_OFF
    if device.standby:
        return ModeSelectOption.STANDBY
    return ModeSelectOption.AUTO


def _plug_mode(device: NeoStat) -> str:
    if not device.manual_off:
        if device.timer_on:
            return ModeSelectOption.MANUAL_ON
        return ModeSelectOption.MANUAL_OFF
    if device.hold_on:
        if device.hold_temp == 1:
            return ModeSelectOption.OVERRIDE_ON
        return ModeSelectOption.OVERRIDE_OFF
    return ModeSelectOption.AUTO
