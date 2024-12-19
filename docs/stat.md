---
title: Thermostats
nav_order: 3
---

# Thermostat usage guide

The thermostats work like any other Home Assistant climate entity.

## Preset Modes

There are three preset modes:

- Home - The thermostat will follow a profile
- Boost - The thermostat is set to 2 degrees higher for 30 minutes
- Away - The thermostat is in frost protection mode. The thermostat is not following a profile and will only call for heat if the temperature drops below the configured frost protection temperature.
  > ##### WARNING
  >
  > NOTE: Setting any thermostat to Away will change all thermostats and timers to Away. Turning off a single thermostat can be done by changing the mode to off
  > {: .block-warning }

## Helper Sensors/Entities

- Hold Time Remaining - If a hold/override is active, displays the number of minutes left
- Hold Temperature - Shows the hold temperature (only relevant if hold is active)
- Current Temperature - optional sensor that holds the current temperature (can also be obtained as an attribute of the climate entity)
- Floor Temperature - displays the floor temperature if a floor sensor is connected (can also be obtained as an attribute of the climate entity)
- Active Profile - Can select a different profile for the thermostat.
  - PROFILE_0 is a special profile when the profile is managed directly on the thermostat rather than a shared profile managed in the hub
- Profile Next Time - The next time there is a state change managed by the profile
- Profile Current Temeperature - The profile's current temperature
- Profile Next Temeperature - The profile's temperature at the next state change

  > ##### INFO
  >
  > NOTE: Profile entities are only relevant if the hub is not in non-programmable mode

## Configuration Entities

- Frost Temperature - The frost protection temperature when the device is on standby/away/holiday
- Output Delay - delay before the thermostat can call for heat again after switching off
- Optimum Start - maxiumu preheat period
- Switching Differential - How far the temperature has to drop before heat is called for
- Floor Limit Temperature - Thermostat will stop calling for heat if the floor reaches this temperature (only if a floor sensor is in use)

## Diagnostic Entities

- Hold Active - shows if a hold is in place
- Standby - if the device is in standby
- Away - if the hub is away or on holiday
- Device Temperature - NeoStats in TimeClock mode still have access to the temperature
- Identify - A button to flash the screen of a NeoStat in TimeClock mode
- Floor Limit Reached - shows if the output is off because the floor limit temperature has been reached
