---
title: Hub
nav_order: 6
---

The NeoHub device contains system wide entities and configuration parameters

# Controls

- DST Rule: Select the rule that enables and disables DST automatically. Alternatively set DST on or off permanently. Only UK, EU and NZ rules are supported by heatmiser
- NTP - enable or disable NTP (Network Time Protocol). When enabled, thermostat clocks should be synched automatically
- Time Zone - The base timezone for the system

## Helper Sensors/Entities

- Away - whether the hub is away
- Away End - if the hub is away and this date is set, then the hub will automatically turn off away mode at this time
- Profile Format - The profile format in use
  - Non Programmable - Heating profiles are not used
  - 24HR mode - the same profile levels every day
  - 5/2 Day mode - Different levels for weekdays and weekends
  - 7 Day mode - Different levels every day
- Profile Alt Timer Format - Only populated if the main Profile Format is Non Programmable. This format would be used by timer devices
- Profile Heating Levels - Specifies the number of levels on heating profiles. It can be 4 or 6. Timer profiles are unaffected by this, they always have 4 levels

## Diagnostic Entities

- Identify - A button to flash an led on the hub
- DST - whether DST is currently active or not
- ZigBee Channel - reports the ZigBee channel being used for communication between the hub and devices
