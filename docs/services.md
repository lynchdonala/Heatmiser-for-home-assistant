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
