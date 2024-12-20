---
title: TimeClocks and NeoPlugs
nav_order: 4
---

TimeClocks and NeoPlugs are modeled as a select entity in Home Assistant.

# TimeClocks

- Mode:
  - Auto - follow the set profile
  - Override On - ignore the profile and turn the output ON for 30 minutes. Return to Auto once the duration has passed
  - Override Off - ignore the profile and turn the output OFF for 30 minutes. Return to Auto once the duration has passed
  - Standby - ignore the profile, output is permantently off
  - Away - ignore the profile. Output is off (If a holiday is set instead, Away will still be displayed but the device will go back to auto at the end of the holiday)
- Active Profile - Can select a different profile for the thermostat.
  - PROFILE_0 is a special profile when the profile is managed directly on the thermostat rather than a shared profile managed in the hub
- Profile Next Time - The next time there is a state change managed by the profile
- Profile State - The profile's current state. There is no next state sensor since it is just the opposite of the current state

  > ##### INFO
  >
  > NOTE: Profile entities are only relevant if the hub is not in non-programmable mode

  > ##### WARNING
  >
  > NOTE: Setting any timeclock to Away will change all thermostats and timers to Away
  > {: .block-warning }

# NeoPlug

NeoPlugs are similar to TimeClocks, but have the ability to be set to ON or OFF indefinitely

- Auto - follow the set profile
- On - profile disabled. Output is ON indefinitely
- Off - profile disabled. Output is OFF indefinitely
- Override On - ignore the profile and turn the output ON for 30 minutes. Return to Auto once the duration has passed
- Override Off - ignore the profile and turn the output OFF for 30 minutes. Return to Auto once the duration has passed

## Helper Sensors/Entities

- Hold Time Remaining - If a hold/override is active, displays the number of minutes left
- Output - shows if the output is on or off

## Diagnostic Entities

- Hold Active - shows if a hold is in place
- Standby - if the device is in standby
- Away - if the hub is away or on holiday
- Device Temperature - NeoStats in TimeClock mode still have access to the temperature
- Identify - A button to flash the screen of a NeoStat in TimeClock mode
