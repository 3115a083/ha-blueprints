# 🔥 Advanced Heating Control | Multi-Zone

Control multiple rooms in **one apartment** with a single Home Assistant automation. All room settings, including thermostats, schedules, windows and target temperatures, are under **01 | Rooms**. Shared people and presence sensors, guests and actions are under **02 | General controls and actions**.

**Based on the awesome blueprint by [panhans, Advanced Heating Control](https://community.home-assistant.io/t/advanced-heating-control/469873).** Thanks to panhans for the original concept and work. [Original YAML](https://github.com/panhans/HomeAssistant/blob/main/blueprints/automation/panhans/advanced_heating_control.yaml).

This is a focused multi-zone adaptation, **not** a feature-complete replacement for AHC V5. Vendor-specific calibration, liming protection, dynamic valve positioning and complex proximity/schedule adjustments have not been ported.

[Import blueprint](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2F3115a083%2Fha-blueprints%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fadvanced_heating_multi_zone%2Fadvanced_heating_multi_zone.yaml)

## Requirements and setup

Home Assistant **2026.10.1 or newer** is required. Each room needs one or more `climate` entities supporting heat/auto. A dedicated Vacation Mode `input_boolean` helper is mandatory.

1. **01 | Rooms:** Add as many rooms as needed. Configure each climate entity, optional room temperature sensor, window contacts, **window-open delay in seconds**, per-room schedule, temperatures and pause switch. Avoid controlling the same climate entity from multiple rooms or automations.
2. **02 | General controls and actions:** Select people or device trackers, optional **multiple apartment presence sensors**, the apartment-wide occupancy hold time, guest/party helpers and shared actions.
3. **03 | Summer mode:** Enable summer cutoff (OFF by default), select an outdoor temperature sensor, and configure the cutoff and resume temperatures.
4. **04 | Vacation mode:** Select the dedicated vacation helper and its Setback, Eco or safe Off strategy.
5. **05 | Preview and diagnostics:** Preview is ON by default. Review calculated decisions in automation traces and only then enable physical device writes.

## Apartment-wide occupancy instead of room motion heating

A room's motion sensor **no longer directly changes its thermostat target** when someone enters or leaves. Room heating is too slow for such immediate adjustments. A room remains on its own schedule while the **apartment** is occupied.

Occupancy is true when any selected person/tracker is home, **or** any configured apartment presence sensor is ON, **or** a sensor switched OFF within the global hold period (default **120 minutes**). If every person is away and no sensor reports recent occupancy, each room switches to Eco unless guest or higher-priority mode is active.

| Presence evidence | Effect |
| --- | --- |
| Person at home | Apartment occupied, normal room schedules |
| All people away, presence sensor ON | Apartment occupied, normal schedules |
| All people away, last sensor OFF but within hold | Apartment occupied until hold expires |
| All people away, all sensors OFF and hold expired | Eco in every room |
| Guest mode ON | Automatic away setback is suppressed |
| Vacation mode ON | Vacation overrides apartment occupancy |

With neither people nor apartment sensors selected, presence does not force an Eco setback. With only sensors selected, those sensors determine apartment occupancy. An unavailable sensor does not count as occupied. PIR sensors cannot reliably detect sleeping or motionless people, so use true occupancy sensors or an appropriately long hold.

**Migration:** The former per-room `motion` setting is deliberately ignored. Select relevant sensors under **Apartment presence sensors** in General controls instead.

## Window delay: seconds

The per-room **Window must remain open for (seconds)** input accepts 0 to 7200 seconds. For example, 30 means half a minute and 90 means one and a half minutes. Sensor evaluations occur once per minute, so the actual reaction can happen up to roughly one minute after the configured threshold.

Existing configured per-room `window_delay` values from the old minute-based interface are still converted to seconds automatically when the new `window_open_seconds` key is missing. A newly configured seconds value overrides the legacy value.

## Summer mode

Summer mode is optional and disabled by default. Enable it only with a valid outdoor temperature sensor.

| Setting | Default |
| --- | ---: |
| Stop normal heating at or above | 20 °C outside |
| Resume normal heating below | 17 °C outside |

At or above 20 °C, a thermostat capable of HVAC OFF is turned off when the room is safely warmer than its frost minimum; otherwise it uses frost-only heating **if it supports HEAT mode**. Thermostats supporting only AUTO and no safe HEAT mode are skipped for this OFF/frost operation, since setting a low AUTO target might activate cooling. Between 17 °C and 20 °C, each thermostat **keeps its prior OFF or frost-only state**, using its HVAC mode/setpoint as a simple hysteresis memory. Below 17 °C normal heating resumes. Configure the resume threshold lower than the cutoff.

A missing, unavailable or nonnumeric outdoor reading means normal rules apply rather than falsely assuming summer. If room temperature is unknown or near the frost minimum, a safe OFF request becomes frost heating instead. Window protection takes precedence over summer. Summer suppresses normal, party and vacation heating when it applies.

## Decision priority

| Priority | Condition | Result |
| --- | --- | --- |
| 1 | Open room window after its configured seconds | Room frost target or explicitly safe OFF |
| 2 | Summer cutoff active | OFF or frost-only heating |
| 3 | Vacation mode ON | Setback, Eco or safe OFF |
| 4 | Party mode ON | Comfort in each room |
| 5 | Apartment unoccupied and Guest mode OFF | Eco in each room |
| 6 | Room schedule OFF | Eco in that room |
| 7 | Room schedule ON | Comfort in that room |
| 8 | No room schedule | Global unscheduled Comfort/Eco setting |

Unknown window contacts still block writes for their room; unavailable thermostats are skipped. **Vacation setback does not require a valid room schedule**, because vacation overrides schedules. During normal heating, an unavailable schedule still prevents that room's commands. An invalid room does not stop other rooms. The global enable switch pauses writes, not climate operation. Vacation helper unavailability also pauses writes. Heating updates run every minute, on startup, and on vacation switch change.

The frost temperature is the minimum requested heating setpoint, subject to each physical thermostat's supported range. No hardware response is guaranteed solely because a Home Assistant service call succeeds.

## Example apartment

| Room | Climate | Room inputs | Comfort | Eco | Vacation | Frost |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| Living room | climate.living_room | schedule.living_room, binary_sensor.living_window | 21 | 17 | 14 | 7 |
| Bedroom | climate.bedroom | binary_sensor.bedroom_window | 19 | 16 | 13 | 7 |
| Office | climate.office | schedule.office | 21 | 16 | 12 | 7 |

In General controls you could select `person.resident` plus `binary_sensor.hall_motion` and `binary_sensor.living_presence`, with a 120-minute hold. These are illustrative entity IDs, not defaults in the blueprint.

## Troubleshooting: vacation targets do not change

If Vacation mode is ON with **Setback**, each room normally requests its configured vacation target (14 °C by default), not its Comfort setpoint. Check the climate entity's **target temperature** (`temperature`) separately from its **current measured temperature** (`current_temperature`): a measured room temperature can stay near 19 °C for hours after the target was lowered.

In an automation trace, check `vacation_valid`, `vacation_active`, `window_unknown`, `schedule_valid`, `desired_profile`, `effective_profile`, `proposed_mode`, `new_temperature` and `temperature_change`. Vacation now intentionally overrides unavailable schedules, but not unavailable window contacts. Verify that **Preview only** is OFF, the global enable input is not OFF, and the automation actually runs. With automatic Summer mode ON, warm outdoor temperatures may intentionally choose OFF/frost rather than 14 °C. Other thermostats or automations can overwrite requested targets, so compare the climate entity history with the trace. A change to this repository does not automatically update an already imported local blueprint.

## Manual thermostat overrides (optional)

A user may turn a physical radiator thermostat dial or change its target in the Home Assistant frontend. By default, the blueprint resumes its calculated target at the next evaluation. To **keep a manual adjustment temporarily and then resume automatic heating**, use the following setup:

1. Under **Settings → Devices & services → Helpers**, create **one Input Text helper per room** with a **maximum length of at least 100 characters**, no fixed initial value and no pattern restriction. The blueprint stores only its own last confirmed mode, target and timing information, not credentials.
2. In **01 | Rooms**, select that helper in each room's **Manual override memory (Input Text helper)** field.
3. In **02 | General controls and actions**, set **Manual thermostat override duration (minutes)**, for example 60 or 120. Default **0** disables manual holds.
4. Save and reload the imported automation. Allow it to send/confirm the ordinary setpoint at least once. Thereafter, a change at the physical thermostat or in the HA climate UI can be recognized as a manual override when it differs from the last **confirmed** automation command.
5. The new manual target is kept until the hold expires. At expiry, the automation restores the currently applicable rule (Vacation, scheduled Comfort/Eco, etc.), **not a saved historical target**.

The optional memory helper is **supported only for rooms with exactly one climate entity**; rooms with multiple thermostats still use standard automatic heating. Use a **different Input Text helper for every room**. Do not edit the helper value manually. The state is retained across Home Assistant restarts unless the helper is configured with an overriding initial state. The first run initializes control memory rather than interpreting a pre-existing value as manual.

A 90-second settling period after a confirmed command prevents slow thermostat state echoes from being mistaken for a manual change. Detection uses the existing approximately once-per-minute check, so it is **not instantaneous**. Repeated changes during a hold do not extend its deadline automatically.

**Priority:** Open-window protection, Summer mode and frost safety may override an active manual hold. A manual hold temporarily takes precedence over Vacation and individual room schedules when those safety controls are not active. A competing external thermostat automation can look like a manual override: avoid multiple controllers writing to the same thermostat. Tracking and the hold are disabled in Preview mode; enabling this option without a valid Input Text helper does not activate manual detection.

## Optional fault notifications and command verification

Under **05 | Preview and diagnostics**, enable **Optional heating fault notifications** (OFF by default). Home Assistant's built-in **Persistent Notifications** are created for the following conditions:

- **Window contact unavailable:** an entity is unknown/unavailable or a selected contact is missing. Heating commands for that room remain paused. Notification IDs are stable per room; recent state failures can trigger a notification promptly, with ongoing reminders at most every 30 minutes.
- **Thermostat unavailable:** the configured climate entity is unknown/offline, so the room cannot be controlled. The ongoing issue is reported on Home Assistant startup or at a 30-minute reminder boundary.
- **Setpoint change not confirmed:** after sending mode/target actions the automation waits (default **15 seconds**, configurable from 5 to 60) until Home Assistant reports the requested HVAC mode and target (within 0.4 °C), then marks the command confirmed. If the state does not reflect the request in time, a stable per-thermostat notification identifies the requested and reported targets. Subsequent checks may retry the command; stable notification IDs prevent multiple separate notification cards for the same issue.

Command **state verification runs even when notifications are OFF**, ensuring the blueprint only runs **global after-change actions** after the reported target matches. Commands that throw a service error are handled without aborting other rooms; failures can then be reported. However, a Home Assistant target attribute changing does **not** prove the physical valve moved or the heating device actually reached that temperature. Persistent notifications stay in the Home Assistant interface until dismissed or updated and are **not push notifications**.

On existing installations, enable notifications first and check for competing automations before enabling manual hold. A thermostat repeatedly reverting to another temperature could indicate another automation or a thermostat's internal schedule.

## Safety and migration checks

- Start with **Preview only ON**. Test schedules, window-open durations, vacation ON/OFF, summer cutoff/resume, temporary sensor unavailability, apartment presence hold, thermostat OFF availability, and Home Assistant restart before enabling physical control.
- Test an unresponsive room, a paused room and another normally working room in the same automation.
- The old per-room `motion` input is not used. Review your occupancy sensors in General controls.
- The old `window_delay` (minutes) remains a compatibility fallback. Set `window_open_seconds` to explicitly override.
- Summer is OFF by default to avoid an unexpected change on upgrade.
- Live thermostat hardware has **not** been tested. Successful CI only verifies templates, configuration and Home Assistant schema.

## Manual import and updates

```text
https://github.com/3115a083/ha-blueprints/blob/main/blueprints/automation/advanced_heating_multi_zone/advanced_heating_multi_zone.yaml
```

The canonical `blueprint.source_url` points to this file on `main`. If using [Blueprints Updater](https://github.com/luuquangvu/blueprints-updater), run `blueprints_updater.reload` after import, and do not switch to a release tag.

See [CHANGELOG.md](CHANGELOG.md) for the English release notes.
