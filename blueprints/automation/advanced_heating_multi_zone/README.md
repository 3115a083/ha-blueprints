# 🔥 Advanced Heating Control | Multi-Zone

Manage multiple independently controlled heating zones in **one** Home Assistant automation. The **Räume** section contains every room-specific setting. Global occupancy, guest/party helpers, safety conditions and actions live in a separate section. One dedicated vacation switch controls the entire system.

**Based on the awesome blueprint by [panhans, Advanced Heating Control](https://community.home-assistant.io/t/advanced-heating-control/469873).** Thanks to panhans for the original concept and feature-rich heating controller. The [original YAML is here](https://github.com/panhans/HomeAssistant/blob/main/blueprints/automation/panhans/advanced_heating_control.yaml).

This project is a **focused, independent multi-zone adaptation**, not a line-by-line fork or a complete replacement for AHC V5. Features such as per-room proximity tracking, vendor-specific offset calibration, dynamic valve positioning, liming protection, weather activation and detailed schedule adjustments have **not** been ported. Existing AHC automations should **not** be silently replaced with this blueprint.

[Import blueprint](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2F3115a083%2Fha-blueprints%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fadvanced_heating_multi_zone%2Fadvanced_heating_multi_zone.yaml)

## Minimum requirements

- Home Assistant **2026.10.1 or later**, matching the project's structured multi-object selector version.
- At least one `climate` entity capable of `heat` or `auto` for each room.
- A dedicated `input_boolean` helper for Vacation Mode. It is **required** even when normally off.
- Configured window and motion entities should report reliable binary `on`/`off` states.
- No external script, Python integration, or vendor-specific thermostat service is needed.

## Configure rooms

1. Import the blueprint and create one new automation. Do not replace an existing AHC V5 automation before verifying the feature differences.
2. In **01 | Räume**, click **Add** and configure an entry for every zone: room name, thermostat(s), optional room temperature sensor, windows, window-open delay, schedule, occupancy sensor, target temperatures and HVAC mode.
3. A room can manage multiple thermostats. **Do not list a thermostat in two rooms**, or let a second automation write competing targets.
4. Optional generic calibration alters the target setpoint by the difference between the thermostat temperature and the external room temperature, limited to ±3 °C. Avoid enabling it on top of another calibration controller (for example Better Thermostat).
5. Configure global presence trackers, optional guest and party switches, action delay and safety conditions in **02 | General controls and actions**.
6. Select the required vacation `input_boolean` and its strategy in **03 | Vacation mode**.
7. Leave **Preview only** enabled. Examine the automation trace and optionally enable system logging. After validating your zones, turn preview off and test one thermostat at a time.

### How a room determines normal heating

An enabled zone uses the following sequence:

| Priority | Condition | Desired result |
| --- | --- | --- |
| 1 | Any configured window has been open for its delay | Frost temperature, or safe OFF if explicitly selected |
| 2 | Vacation helper is ON | Vacation strategy for every room |
| 3 | Party helper is ON | Comfort |
| 4 | Everyone tracked is away and guest helper is OFF | Eco |
| 5 | Room schedule is OFF | Eco |
| 6 | Room occupancy sensor is OFF | Eco |
| 7 | Room schedule or room occupancy is active | Comfort |
| 8 | No schedule or motion input | Global unscheduled default, Comfort or Eco |

If both a schedule and a motion sensor exist, **both must be ON** to reach Comfort. A room can be paused independently with an optional binary switch. Setting the global enable switch OFF pauses *writes*, it does not send an OFF command.

If a configured window, schedule, or motion sensor is unknown/unavailable, that room is skipped for the current check rather than assuming the room is safe to heat. Thermostats that are unavailable or do not support heat/auto are skipped. Other rooms continue.

### Vacation, away, and window modes

**Vacation differs from ordinary absence.** An away household uses each room's Eco temperature; an active vacation switch ignores schedules, presence, guest and party state. Window protection still wins. The vacation helper being unavailable pauses all heating writes, rather than silently returning to normal mode.

| Vacation strategy | Per-room setpoint | Behaviour |
| --- | --- | --- |
| **Setback** (default) | Vacation temperature (default 14 °C) | Keep all zones at their setback temperatures |
| **Eco** | Eco temperature (default 17 °C) | Use ordinary Eco temperatures for all zones |
| **Off** (explicit opt-in) | Frost temperature if cold, temperature unknown, or thermostat lacks OFF mode | Otherwise set thermostat HVAC mode to OFF |

The frost minimum is applied to all programmed heating setpoints. For an explicitly selected Off strategy, a known room temperature must be above the frost threshold plus 0.5 °C before switching off. If no reliable temperature can be obtained, it stays in a heating mode at the frost minimum. Thermostat advertised min/max temperature limits are respected. If a thermostat cannot heat/auto, it is skipped rather than sending an unsupported command.

Turning vacation OFF restores the *currently calculated* ordinary state on the next automatic check. It does not restore a stale pre-vacation temperature snapshot.

### Triggers, actions and preview

- Runs every minute, when Home Assistant starts, and as soon as the vacation helper changes. Other sensor changes are applied on the next minute check (up to approximately one minute later, excluding device delays).
- Changes HVAC mode or temperature only if necessary. Multiple zones are processed serially; a paused/unavailable room does not cancel the others.
- Optional **global after-change actions** run once per thermostat with a planned change, after the device commands complete. There is no confirmation of physical valve movement; a successful HA action call is not a hardware acknowledgement.
- Preview is ON by default and suppresses *all* thermostat commands and the after-change actions. Optional system logging may repeat every minute during preview.
- This blueprint controls **heating only**, not cooling, cooling schedules or thermostat vendor calibration entities.

## Example configuration

Use the structured Add form under Räume (values shown for illustration only):

| Room | Thermostats | Room controls | Comfort | Eco | Vacation | Frost |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| Living room | climate.living_room | schedule.living_room, binary_sensor.living_window | 21 | 17 | 14 | 7 |
| Bedroom | climate.bedroom | binary_sensor.bedroom_window, binary_sensor.bedroom_motion | 19 | 16 | 13 | 7 |
| Office | climate.office | schedule.office | 21 | 16 | 12 | 7 |

Select your own actual entities in Home Assistant. These sample entity IDs are not part of the blueprint.

## Install URL for manual import

```text
https://github.com/3115a083/ha-blueprints/blob/main/blueprints/automation/advanced_heating_multi_zone/advanced_heating_multi_zone.yaml
```

The blueprint's canonical `source_url` points to the same `main` YAML file. If you use [Blueprints Updater](https://github.com/luuquangvu/blueprints-updater), run `blueprints_updater.reload` after import; do not point an update integration at a release tag.

## Safety, testing and migration

- Start with Preview mode and test under one room with a safe thermostat. Review the target and HVAC mode in the trace before activating physical heating writes.
- Presence trackers and window contacts can be wrong or unavailable. Review heating fallback behaviour in your own environment, including freezing conditions and Home Assistant restarts.
- OFF is opt-in because it can stop heat. Selecting an OFF policy without a valid temperature measurement falls back to frost heating.
- No access to the user's Home Assistant hardware or room configuration was available during development. Repository CI tests check code and schema, **not physical thermostat behaviour**.
- Migrating from AHC V5 requires reviewing each feature and recreating only the supported settings. Run both automations against different thermostats during evaluation to avoid competing service calls.

## Release notes

See [CHANGELOG.md](CHANGELOG.md). The first public release is an experimental multi-zone adaptation; it does not claim feature parity with panhans AHC V5.
