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

## Diagnostic Entities

- Identify - A button to flash an led on the hub
- DST - whether DST is currently active or not
- ZigBee Channel - reports the ZigBee channel being used for communication between the hub and devices
