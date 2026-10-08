# Area Occupancy Manager

A configurable Home Assistant automation blueprint for determining whether a home, garage, or other area is **occupied** or **vacant**. Choose people/device trackers as direct presence sources, or optionally publish the computed area state to an `input_boolean` for dashboards and other automations. Detection rules, guards, and actions are configured in the Home Assistant UI.

- **Install:** [Import into Home Assistant](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2F3115a083%2Fha-blueprints%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Foccupancy%2Farea_occupancy_manager.yaml)
- **Blueprint:** [area_occupancy_manager.yaml](area_occupancy_manager.yaml)
- **Minimum declared version:** Home Assistant 2024.10.0
- No HACS or custom component required.

## Quick start

1. [Import the blueprint](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2F3115a083%2Fha-blueprints%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Foccupancy%2Farea_occupancy_manager.yaml), or paste [the YAML URL](https://github.com/3115a083/ha-blueprints/blob/main/blueprints/automation/occupancy/area_occupancy_manager.yaml) under **Settings -> Automations & scenes -> Blueprints -> Import blueprint**.
2. In **01 | Presence and absence triggers**, select at least one `person` entity (recommended standard), or a device tracker. A tracked person leaving `home` is the normal absence signal; returning `home` signals occupancy. Choose motion/presence sensors only if needed.
3. In **02 | Optional door and custom triggers**, configure extra triggers only if you need them.
4. In **03 | Actions on occupied / vacant**, choose your occupied and vacant actions. This is the main setup.
5. Expand **04-09** only for optional timed routines, safeguards, a published occupancy switch, or diagnostics. For simple tracker-based actions, **no Boolean helper is required**.

**Recommended for whole-home occupancy:** Enable the optional output switch under **08 | Optional occupancy status output** and let the blueprint set it. Other automations can then depend on a single occupied/vacant entity. For direct tracker-only workflows, leave the switch empty.

## 01 | Presence and absence triggers

| Source | Vacancy evidence | Occupancy evidence |
| --- | --- | --- |
| Person/device trackers | All selected trackers away long enough | Any selected tracker at `home` |
| Motion/presence sensors | All selected sensors OFF long enough | Any selected sensor ON |
| Two-door sequence | Door 1 opens, then door 2 | Door 2 opens, then door 1 |
| Selected smart lock | Not used for vacancy | Unlock event |
| Custom Home Assistant triggers | Trigger ID `custom_away` | Trigger ID `custom_home` |
| Guest mode | ON, unknown or unavailable blocks vacancy | ON restores occupancy |
| Sleep mode | ON, unknown or unavailable blocks vacancy | ON restores occupancy |
| Additional presence sensors | ON, unknown or unavailable blocks vacancy | ON restores occupancy |

Choose **ALL** (default) to require agreement from every selected tracker and activity sensor, or **ANY** to accept one qualifying vacancy source. In both cases, known occupants, active activity sensors, unavailable sensors, guest mode, sleep mode, and active safety blockers **always prevent automatic vacancy**.

A selected tracker in a different zone, such as work, counts as away. A selected tracker in an unknown or unavailable state does not.

A PIR motion sensor cannot reliably detect still or sleeping people. For guests, choose an explicit guest-presence switch or a reliable presence detector such as mmWave/bed occupancy. No automation can infer undetected people with certainty.

## 02 | Optional door and custom triggers

Select two binary door contacts. Opening **door 1 followed by door 2** within the configured interval counts as a possible exit, while the reverse sequence counts as entry. Contacts that remain open or ambiguous traffic patterns will not provide dependable direction detection.

Custom trigger editors accept any supported Home Assistant trigger. Set its **trigger ID** to `custom_away` or `custom_home` as appropriate. In ALL mode, configured tracker and activity evidence must still confirm any custom vacancy trigger. Always add extra conditions for security-sensitive scenarios.

## 03 | Actions on occupied / vacant

Use the built-in action editor for any Home Assistant actions or scripts. Vacancy actions might turn off lights/media, arm an alarm, and lock doors. Occupancy actions might disarm an alarm, enable lighting, or start audio.

For example, to turn on lights only after dark, add an **If/Then** block with a sun or lux condition *inside the occupancy actions*, not as a condition on the occupancy state transition itself.

With a published switch, actions fire on actual occupancy-helper transitions. Without a switch, direct tracker transitions fire actions when the selected guards pass.

## 04-06 | Optional independent timed actions

The blueprint includes **three independent timed action profiles** in sections **04, 05, and 06**. All can start from the **same occupancy transition**, each with its own:

- **Enable switch**, start conditions, and immediately executed Home Assistant actions.
- **Delay** (1 to 1440 minutes), independent from the other profiles.
- **Follow-up safety conditions** and follow-up Home Assistant actions.
- Optional **dedicated deadline and pending helpers** for restart-resilient scheduling.

The first profile keeps all its existing input IDs and default delay (40 minutes), so previously saved automations remain compatible. The second profile defaults to 30 minutes, the third to 15 minutes; all delays are editable.

### Example: garage and front door

| Configuration | Timed action 1: Garage | Timed action 2: Front door |
| --- | --- | --- |
| Start condition | Phone connected to the car, arrival authorized | Door lock is currently locked and unlocking is authorized |
| Immediate action | `cover.open_cover` | `lock.unlock` |
| Delay | **40 minutes** | **30 minutes** |
| Follow-up checks | No obstruction, cover can safely close | Door safely closed, no conflicting access condition |
| Follow-up action | `cover.close_cover` | `lock.lock` |
| Dedicated timer helpers | Garage deadline + garage pending | Door deadline + door pending |

Each enabled profile runs **independently**: both may start together, and one completing or failing a safety check does not cancel the other. Each profile also has its own pending flag and expiry timestamp, so a new arrival replaces the old schedule **only for that same profile**.

Avoid automatically unlocking external doors based solely on a tracker entering the home zone. Use explicit authorization and suitable security conditions.

### Restart-resilient timers for each profile

For **each enabled profile**, create two **unique** Home Assistant helpers:

1. One `input_datetime` with **both date and time**, for example `input_datetime.garage_due` and `input_datetime.door_due`.
2. One `input_boolean`, initially **OFF**, for example `input_boolean.garage_pending` and `input_boolean.door_pending`.

Assign the pair in the corresponding profile. **Never reuse the same deadline or pending helper across two profiles.** If any helper is shared between profiles, timed operations stop for safety until the configuration is corrected.

Saved deadlines are checked roughly once per minute, including after Home Assistant restarts and automation reloads. If two profiles are due together, their follow-ups are executed in parallel. Their pending flags are cleared before evaluating end conditions, preventing repeated execution if a safety check fails. If a deadline is invalid or a helper is unavailable, the follow-up is not executed.

**Fallback:** If *both* helpers of an enabled profile are left empty, that profile uses a normal in-memory delay. This is compatible with earlier installations, but the delayed follow-up does **not** survive Home Assistant restarts/reloads. If *only one* helper is selected, that profile does not start.

For all garage/lock automations, provide independent safety sensors and end-condition checks. Home Assistant automations are not a substitute for a garage motor's built-in obstruction safety or for lock security policies.

## 07 | Optional occupancy safeguards

A guest-presence helper and a sleep-mode helper are optional `input_boolean` switches. Turning either one ON restores occupied status and blocks automatic vacancy. Unknown and unavailable states also block vacancy conservatively.

Additional ON-state presence-protection sensors (for example, bed occupancy) also restore occupied status. Only select sensors where ON truly means detected presence.

When these protections turn off, a still-valid away or inactivity source can result in vacancy during the next five-minute reconciliation. One-shot door or custom triggers are not retained indefinitely and need to fire again if an earlier attempt was blocked.

## 08 | Optional occupancy status output

**An occupancy helper is no longer mandatory.** Home Assistant `person` entities already expose `home`, `not_home`, and named zone states. A person at `home` is present; other known zones mean away. The blueprint never requires you to flip a Boolean manually when somebody enters or leaves.

| Mode | Configuration | How transitions work | When to use |
| --- | --- | --- | --- |
| **Direct person / device tracking** | Select one or more people/device trackers. Leave the occupancy switch empty. | Arrival actions run when the first tracked entity becomes `home`. Vacancy actions run once all selected trackers are away for the configured delay **and all safety guards pass**. | Simple person-based presence, without creating a helper. |
| **Automatically published occupancy** | Select trackers and/or other presence sources, and an `input_boolean` under **08 | Optional occupancy status output**. | Sensors and rules **set the switch automatically** to ON (occupied) or OFF (vacant). Home/vacancy actions fire on its actual transition. | Homes with guests, sleep mode, motion detection, custom triggers, door sequences, shared state, or other automations that need one stable status. |
| **Boolean-only/manual override** | Select a switch, leave trackers empty if desired. | Manually changing the switch runs the configured actions; automatic updates need qualifying sensors/triggers. | Intentionally manual or externally managed state. |

When **any tracker is still at `home`**, automatic vacancy is blocked, even in the ANY evidence policy. Multiple people can be selected, so a house stays occupied until the last selected person leaves (subject to guest/motion guards).

A blueprint cannot create an entity on its own. If you want an independent `home_occupied` state for other automations to reference, create an `input_boolean` once and **let this blueprint write it**. In the direct mode no such shared computed state is created; automations may refer to the original `person` states instead.

**Direct-mode limitation:** Other sensor triggers, door sequences, and arbitrary custom triggers cannot reliably establish a reusable state without a helper. In direct mode, only tracker transitions run occupancy/vacancy actions. Guest/sleep/protection sensors and extra conditions are still applied as safety gates. A blocked departure is not queued for later, so if a guest leaves after the tracker went away, use a published switch mode for automatic re-evaluation. Likewise, start and end conditions that do not pass at the tracker transition can suppress that event without retriggering it. For complex occupancy, use the published switch.

## 09 | Optional diagnostics and debug

Optionally enable diagnostics in section **09 | Optional diagnostics and debug**. Automation traces contain evaluated signals and decisions. You can also create and select an `input_text` helper (up to 255 characters) to show a status line in a dashboard, such as `OCCUPIED | Vacancy blocked: Guest mode=on` or `VACANT | No active blockers`.

Optional logging writes blocked vacancy attempts to the system log. Missing or unavailable diagnostic text helpers are skipped and do not stop occupancy processing. User-provided extra conditions are checked after the standard sensor guards and are not individually explained by the diagnostic line.

## Reliability, safety and tests

The blueprint reconciles current signals after Home Assistant starts and every five minutes. State-change timestamps are used for conservative stability checks. A fresh sensor state after a restart can restart the minimum waiting period. Template-trigger `for` timers themselves do not persist across a restart.

Concurrent triggers may overlap due to the parallel automation mode. Place safety-critical checks in the final actions and devices. Status and dashboard text are informative, not a safety certification.

The repository includes [static regression tests](../../../tests/test_blueprint.py) and GitHub Actions validation for YAML, Jinja, input references, and important guard scenarios. **A real Home Assistant installation test has not been performed here.**

