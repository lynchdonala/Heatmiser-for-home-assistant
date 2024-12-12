# Change Log

## 20241212
- Merged https://github.com/MindrustUK/Heatmiser-for-home-assistant/pull/223 by @ocrease, Bumps NeoHub API version and adds support for repeater and profile features.

## 20241206

- Merged https://github.com/MindrustUK/Heatmiser-for-home-assistant/pull/221 by @ocrease, adds Time / NTP fixes and hub features.
- Merged https://github.com/MindrustUK/Heatmiser-for-home-assistant/pull/222 by @ocrease, adds flag for modified temperatures.

## 20241129

- Merged https://github.com/MindrustUK/Heatmiser-for-home-assistant/pull/220 by @ocrease, fixes for thermostat operation when in standby.

## 20241118

- Merged https://github.com/MindrustUK/Heatmiser-for-home-assistant/pull/219 by @ocrease, Additional floor related parameters.

## 20241115

- Merged https://github.com/MindrustUK/Heatmiser-for-home-assistant/pull/207 by @ocrease, improves away mode.

## 20241113

- Merged https://github.com/MindrustUK/Heatmiser-for-home-assistant/pull/218 by @ocrease, improves icons.

## 20241111

- Merged https://github.com/MindrustUK/Heatmiser-for-home-assistant/pull/213 by @ocrease, improves overall quality.
- Merged https://github.com/MindrustUK/Heatmiser-for-home-assistant/pull/214 by @ocrease, fixing sensor type.
- Merged https://github.com/MindrustUK/Heatmiser-for-home-assistant/pull/216 by @ocrease, improves robustness when devices are no longer avalible.

## 20241105

- Merged https://github.com/MindrustUK/Heatmiser-for-home-assistant/pull/212 by @ocrease, should address NeoStat V1 in timeclock mode behaviours with Standby mode.
- Merged https://github.com/MindrustUK/Heatmiser-for-home-assistant/pull/211 by @ocrease, adds automation and improves consistency of release versions.

## 20241031

- Merged https://github.com/MindrustUK/Heatmiser-for-home-assistant/pull/201 by @ocrease. I would suggest to treat this as a complete re-write. The change list is huge and includes many fixes and new features. I recommend reading the PR for details.

## 20241030

- Merged https://github.com/MindrustUK/Heatmiser-for-home-assistant/pull/203 - Improves diagnostics, thanks ocrease.
- Updated readme (Supporting this project).
- Forked default branch Version 1.6

## 20241029

- Move Dev branch installation notes from readme.md to dev_installation.md

## 20241028

- Merged https://github.com/MindrustUK/Heatmiser-for-home-assistant/pull/200 - Adds diagnostics, thanks @ocrease.

## 20241024

- Merged https://github.com/MindrustUK/Heatmiser-for-home-assistant/pull/191 - Should cleanup dev branch.

## 20241023

- Merged https://github.com/MindrustUK/Heatmiser-for-home-assistant/pull/190 - Should improve hold behaviour.

## 20241022

- Merged https://github.com/MindrustUK/Heatmiser-for-home-assistant/pull/187 should re-introduce version 1 style hold behaviour for timers.

## 20241021

- Updating README.md with improved troubleshooting steps.

## 20241020

- Change hold service behaviour for: https://github.com/MindrustUK/Heatmiser-for-home-assistant/issues/185

## 20241018

- Bumped dependency on neohubapi to 2.2, hopefully addresses wireless sensor behavior and repeaters in issue: https://github.com/MindrustUK/Heatmiser-for-home-assistant/issues/176

## 20241016

- Version 1.5 Release to Main
  - Current Main branch archived to branch Version 1.0
  - Version 1.5 is a fork of the dev branch with the additional hold controls removed. This has been done as the main
    branch is stale and prompting lots of reports for things fixed up stream that haven't made it to main yet. This should
    satisfy many requirements reported or requested recently.
  - Known issues: Heatmiser Neo Plug functionality is broken. I've made the call that the benefits of getting this
    released even with the missing functionality outweighs the missing element. For anyone who desperately needs support
    for the Neo Plug, please use the Version 1.0 branch. This is the top thing on my list to fix at present.

## 20241013

- Allow calling hold service with float temperatures: https://github.com/MindrustUK/Heatmiser-for-home-assistant/issues/175

## 20241003

- Fixes following previous work to avoid entities being added twice when multiple instances of the integration are in use.

## 20240928

- Multiple fixes and enhancements relating to issue: https://github.com/MindrustUK/Heatmiser-for-home-assistant/issues/170 - Multiple Hubs / Instances should now work.
- **Breaking changes:** Unique IDs are now generated based on serial number, this will cause duplicate entries and a bunch of breakage. Please remove and re-add the integration to clear any issues with this.
- Added support for device serial numbers to ensure device ID's are more distinct when multiple hubs and instances of the integration are in use.
- Serial numbers now report in device info.
- Heatmiser NeoHub now appears as a device. The Serial Number is a placeholder for now. Longer term I'll make this configurable or hopefully Heatmiser will add some API support.
- Heatmiser NeoHub does not have a 'real' serial number, issue raised with Heatmiser here: https://dev.heatmiser.com/t/no-method-to-retrive-serial-nubmer-for-neohub-in-api/1298
- Added Heatmiser NeoHub types / models to constants.
- Report Heatmiser NeoHub type / model in device info.
- Relationships between Heatmiser devices and the Hub now work (via_device).

## 20240830

- Better handling of invalid temperatures on hub disconnect as per: https://github.com/MindrustUK/Heatmiser-for-home-assistant/issues/155
- Added switch to control standby on timers as per: https://github.com/MindrustUK/Heatmiser-for-home-assistant/issues/153

## 20240828

- Fix deprecation notice: https://developers.home-assistant.io/blog/2024/06/12/async_forward_entry_setups/
- Handling of 127 and 255 temperatures on hub disconnect as per: https://github.com/MindrustUK/Heatmiser-for-home-assistant/issues/155
- Fix in button.py for Model ID as per: https://github.com/MindrustUK/Heatmiser-for-home-assistant/issues/159
- Fixed HVAC OFF mode for: https://github.com/MindrustUK/Heatmiser-for-home-assistant/issues/157 also improves features per device type. I.e. enable cooling for stats that support it.

## 20231121

- Added support for Temperature Sensors
- Added Support for Window Door Contact Sensors
- Reflect correct firmware, model, manufacturer etc. in device info (Thermostats etc. Hub information to follow).
- Patched behavior of Neostat V1 to only allow for heating due to API bug in Heatmiser Neo Hub.
- Added Battery attribute to devices that are battery powered.
- Reflect battery sensor for battery low in any 'battery powered' device.
- Refactored "device offline" sensor.
- Remapped HVAC action and HVAC modes values to better align with home-assistant intentions.
- Refactor Offline sensor from BinarySensorDeviceClass.PROBLEM to BinarySensorDeviceClass.CONNECTIVITY. See: https://developers.home-assistant.io/docs/core/entity/binary-sensor/
- Refactor Battery sensor BinarySensorDeviceClass.BATTERY. See: https://developers.home-assistant.io/docs/core/entity/binary-sensor/
- Use device_id as unique identifier for all Heatmiser Neo Devices in device registry.
- Flattened all Heatmiser Neo Devices into a single neo_device simple-namespace and class.
- Added time_clock_mode to neo_device class where device_type is thermostat ie 1 - NeoStat , 12 - NeoStat V2
- Added offline handling for all Heatmiser Neo Devices and surfaced this to Home Assistant.
- Fixed hvac_mode vs hvac_action.
- Added Identify button
- Added Hold Active sensors
- Added Input for Hold Hours and Minutes
- Added Hold State Switches (IE hold on or hold off)
- Added Hold Temperature, or Hold by Time depending on Thermostat or TimeClocks / Neoplugs.
- More stuff I forgot and will add later.

## 20231219

- Added HeatmiserNeoTimerOutputActiveSensor to sensors.
