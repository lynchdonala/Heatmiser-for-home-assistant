---
title: Services
nav_order: 7
---

# Thermostat Services

## Hold

You can apply a hold using the `heatmiserneo.hold_on` service. This can be used to target an entity, device or area and also accepts the following parameters:

- `hold_duration` - how long to hold the specified temperature. This is given in Home Assistant duration format (hh:mm e.g. `hold_duration: 01:30`) and can go up to 99:59.
- `hold_temperature` - sets the temperature to hold. Specified as an integer (e.g. `hold_temperature: 20`).

If there is an existing hold on any device targeted by the service call, it is replaced by the new hold.

```yaml
action: heatmiserneo.hold_on
data:
  hold_duration:
    hours: 0
    minutes: 45
    seconds: 0
  hold_temperature: 21.5
target:
  entity_id: climate.kitchen
```

## Release Hold

You can release any existing hold on a NeoStat specified by entity, device or area. There are no other parameters.

```yaml
action: heatmiserneo.hold_off
data: {}
target:
  entity_id: climate.kitchen
```

# Timeclock Services (NeoStats in TimeClock mode or NeoPlugs)

## Hold

Setting a custom timer hold can be done using the `heatmiserneo.timer_hold_on` service.

- `hold_duration` - how long to hold the specified temperature. This is given in Home Assistant duration format (hh:mm e.g. `hold_duration: 01:30`) and can go up to 99:59.
- `hold_state` - a boolean that specifies if the output should be held on or off (eg if a profile currently has the output on, it is possible to turn it off).

```yaml
action: heatmiserneo.timer_hold_on
data:
  hold_duration:
    hours: 0
    minutes: 45
    seconds: 0
  hold_state: true
target:
  entity_id: select.hot_water
```

Note that an override can also be set by calling the built in `select.select_option` service, but a default duration of 30 minutes is used instead:

```yaml
action: select.select_option
data:
  option: override_off
target:
  entity_id: select.hot_water
```

Use `override_off` or `override_on` to set the hold off or on.

The TimeClock will automatically go back to `Auto` once the duration has passed. But one can also use the `select.select_option` service to end it early by setting the option to `auto` (or `standaby`). Note that NeoPlugs have additional options of `manual_on` and `manual_off`.

# Hub Services

## Away

You can control the away/holiday state of the hub (and all attached devices) using the `heatmiserneo.set_away_mode` service. There are three general use cases:

- Turn off away/holiday mode
- Turn on away mode (with no end date)
- Turn on holiday mode (away with and end date)

You should target the NeoHub device itself or the Away entity of the hub. The `end` parameter is optional. It should not be supplied if `away` is `false`, and it can optionally be supplied when `away` is `true`

```
action: heatmiserneo.set_away_mode
data:
  away: true
  end: "2025-01-01 15:00:00"
target:
  entity_id: binary_sensor.neohub_192_168_1_10_away
```

## Profile Services

### Rename Profile

Change the name of an existing profile using the `heatmiserneo.rename_profile` action. You should target the NeoHub device itself or the Profile Format entity of the hub.

```
action: heatmiserneo.rename_profile
data:
  old_name: Old Profile
  new_name: New Profile
target:
  entity_id: sensor.neohub_192_168_1_10_profile_format
```

### Delete Profile

Delete an existing profile using the `heatmiserneo.delete_profile` action. You should target the NeoHub device itself or the Profile Format entity of the hub. Note, if any devices are using the profile, they will be moved to PROFILE_0 (eg profile managed on the device itself).

```
action: heatmiserneo.delete_profile
data:
  name: Profile Name
target:
  entity_id: sensor.neohub_192_168_1_10_profile_format
```

### Create/Update Profile

This action allows creating or updating a heating profile. There are three versions of it, depending on the profile format being used in the hub:

- For 24HR format (same levels every day) use `heatmiserneo.create_profile_one`
- For 5/2 Day format (different levels for weekdays vs weekends) use `heatmiserneo.create_profile_two`
- For 7 Day format (different levels every day) use `heatmiserneo.create_profile_seven`

These have the following parameters in common:

- Name - The name of the profile to create or update
- Update - If set to `false` (the default) the service will be in create mode and the supplied name must not exist already. If set to `true`, the supplied name must exist and it must be for a heating profile
- Times and Temperatures - Supply the times and temperatures for a particular weekday
  - Times must be supplied in `HH:MM` 24h format
  - Temperatures can be in 0.5 degree increments
  - For 24HR mode, supply `sunday_times` and `sunday_temperatures`
  - For 5/2 Day mode, additionally supply `monday_times` and `monday_temperatures`
  - For 7 Day mode, supply times and temperatures for every day of the week
  - The maximum number of levels allowed is dependent on the hub configuration. It will be either 4 or 6. The sensor `sensor.neohub_192_168_1_10_profile_heating_levels` has the current configuration. You can supply less levels but not more

You should target the NeoHub device itself or the Profile Format entity of the hub.

```
action: heatmiserneo.create_profile_two
data:
  name: Existing Profile
  update: true
  monday_times:
    - "06:45"
    - "09:00"
    - "17:00"
    - "22:00"
  monday_temperatures:
    - 19.5
    - 17
    - 20.5
    - 16
  sunday_times:
    - "06:45"
    - "22:00"
  sunday_temperatures:
    - 19.5
    - 16
target:
  entity_id: sensor.neohub_192_168_1_10_profile_format
```

### Create/Update Timer Profile

This action allows creating or updating a timer profile. There are three versions of it, depending on the profile format being used in the hub:

- For 24HR format (same levels every day) use `heatmiserneo.create_timer_profile_one`
- For 5/2 Day format (different levels for weekdays vs weekends) use `heatmiserneo.create_timer_profile_two`
- For 7 Day format (different levels every day) use `heatmiserneo.create_timer_profile_seven`

These have the following parameters in common:

- Name - The name of the profile to create or update
- Update - If set to `false` (the default) the service will be in create mode and the supplied name must not exist already. If set to `true`, the supplied name must exist and it must be for a heating profile
- On Times and Off Times - Supply the times to turn on and off
  - Times must be supplied in `HH:MM` 24h format
  - For 24HR mode, supply `sunday_on_times` and `sunday_off_times`
  - For 5/2 Day mode, additionally supply `monday_on_times` and `monday_off_times`. Monday times will be used for weekdays and sunday times for weekends
  - For 7 Day mode, supply times and temperatures for every day of the week
  - Unlike heating profiles, the maximum number of timer levels is always 4. You can supply less levels but not more

You should target the NeoHub device itself or the Profile Format entity of the hub.

```
action: heatmiserneo.create_timer_profile_two
data:
  name: Existing Profile
  update: true
  monday_on_times:
    - "06:45"
    - "09:00"
    - "17:00"
    - "22:00"
  monday_off_times:
    - "07:45"
    - "10:30"
    - "19:00"
    - "01:00"
  sunday_on_times:
    - "06:45"
    - "22:00"
  sunday_off_times:
    - "07:45"
    - "01:00"
target:
  entity_id: sensor.neohub_192_168_1_10_profile_format
```

### Get Profile Definitions

Use this action to retrieve all profiles defined in the hub. It has one optional parameter:

- Friendly Mode - By default (or when set to false), the returned format closely matches the format of the create/update service calls, so it can be used to copy the format, make the necessary changes and then upload it using the relevant service. When set to true, the result is a bit easier to read.

You should target the NeoHub device itself or the Profile Format entity of the hub.

```
action: heatmiserneo.get_profile_definitions
data:
  friendly_mode: false
target:
  entity_id: sensor.neohub_192_168_1_10_profile_format
```

### Get Device Profile Definition

This is very similar to the hub level service, but instead you can get the definition of the profile that a particular device is using. Target the device itself or the Active Profile entity of the device.

```
action: heatmiserneo.get_device_profile_definition
data:
  friendly_mode: true
target:
  entity_id: select.landing_active_profile
```
