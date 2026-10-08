# Area Occupancy Manager

A configurable Home Assistant automation blueprint for determining whether a home, garage, or other area is **occupied** or **vacant**. Each area uses its own `input_boolean` occupancy helper. Detection rules, guards, and all actions are configurable in the Home Assistant UI.

- **Install:** [Import into Home Assistant](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2F3115a083%2Fha-blueprints%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Foccupancy%2Farea_occupancy_manager.yaml)
- **Blueprint:** [area_occupancy_manager.yaml](area_occupancy_manager.yaml)
- **Minimum declared version:** Home Assistant 2024.10.0
- No HACS or custom component required.

## Detection and safety

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

## Installation

1. [Import the blueprint](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2F3115a083%2Fha-blueprints%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Foccupancy%2Farea_occupancy_manager.yaml), or open **Settings → Automations & scenes → Blueprints → Import blueprint** and paste this URL: `https://github.com/3115a083/ha-blueprints/blob/main/blueprints/automation/occupancy/area_occupancy_manager.yaml`.
2. Create a **Toggle** helper (`input_boolean`) for the area, for example `input_boolean.home_occupied`. Set its initial state correctly: **ON = occupied**, **OFF = vacant**.
3. Create an automation from the blueprint and choose the helper.
4. Select trackers, activity sensors, optional guest and sleep helpers, and additional protection sensors.
5. Configure custom conditions and actions. Start with notifications until the detection works reliably, then enable critical controls.

Manually changing the occupancy helper is an **intentional override**. It runs the corresponding actions even when the automatic vacancy guards would block a transition. Restrict access to dashboards that expose this helper.

## Diagnostics

Optionally enable diagnostics in section **04 | Diagnostics**. Automation traces contain evaluated signals and decisions. You can also create and select an `input_text` helper (up to 255 characters) to show a status line in a dashboard, such as `OCCUPIED | Vacancy blocked: Guest mode=on` or `VACANT | No active blockers`.

Optional logging writes blocked vacancy attempts to the system log. Missing or unavailable diagnostic text helpers are skipped and do not stop occupancy processing. User-provided extra conditions are checked after the standard sensor guards and are not individually explained by the diagnostic line.

## Guest and sleep modes

A guest-presence helper and a sleep-mode helper are optional `input_boolean` switches. Turning either one ON restores occupied status and blocks automatic vacancy. Unknown and unavailable states also block vacancy conservatively.

Additional ON-state presence-protection sensors (for example, bed occupancy) also restore occupied status. Only select sensors where ON truly means detected presence.

When these protections turn off, a still-valid away or inactivity source can result in vacancy during the next five-minute reconciliation. One-shot door or custom triggers are not retained indefinitely and need to fire again if an earlier attempt was blocked.

## Doors and custom triggers

Select two binary door contacts. Opening **door 1 followed by door 2** within the configured interval counts as a possible exit, while the reverse sequence counts as entry. Contacts that remain open or ambiguous traffic patterns will not provide dependable direction detection.

Custom trigger editors accept any supported Home Assistant trigger. Set its **trigger ID** to `custom_away` or `custom_home` as appropriate. In ALL mode, configured tracker and activity evidence must still confirm any custom vacancy trigger. Always add extra conditions for security-sensitive scenarios.

## Actions

Use the built-in action editor for any Home Assistant actions or scripts. Vacancy actions might turn off lights/media, arm an alarm, and lock doors. Occupancy actions might disarm an alarm, enable lighting, or start audio.

For example, to turn on lights only after dark, add an **If/Then** block with a sun or lux condition *inside the occupancy actions*, not as a condition on the occupancy state transition itself.

Actions only fire when the occupancy helper genuinely changes state.

## Temporary arrival actions

Example: open a garage when the returning person's phone is connected to their car, then consider closing it after **40 minutes**:

1. Enable temporary actions.
2. Choose start conditions requiring a valid car Bluetooth connection and suitable authorization.
3. Choose safe start actions, e.g. `cover.open_cover`.
4. Set the duration to **40 minutes**.
5. Add independent end safety checks for obstruction detection, door state, etc. Configure `cover.close_cover` as the follow-up action.

### Restart-resilient follow-up

Create **both** helpers:
- `input_datetime` with **date and time**, for example `input_datetime.garage_close_due`.
- `input_boolean`, initially **OFF**, for example `input_boolean.garage_close_pending`.

Select both in section **07 | Temporary arrival actions**. The deadline and pending flag are saved before the initial action. After a Home Assistant restart or automation reload, the blueprint checks for due follow-ups about every minute. The pending flag is cleared before the follow-up runs, so failed safety conditions cause the action to be **skipped**, not endlessly retried. A new arrival replaces the previously pending due time.

Without both helpers, the original in-memory delay remains supported but **does not survive a restart**. If exactly one helper is configured, temporary actions do not run. Unavailable or invalid saved deadlines do not cause automatic closing; inspect and reset pending state manually when needed.

**Important:** Never rely on automation alone for a motorized garage door's obstacle protection. Use built-in motor safety systems and independently verified sensors. Test the setup before enabling automatic closing.

## Restart behavior, limitations, and tests

The blueprint reconciles current signals after Home Assistant starts and every five minutes. State-change timestamps are used for conservative stability checks. A fresh sensor state after a restart can restart the minimum waiting period. Template-trigger `for` timers themselves do not persist across a restart.

Concurrent triggers may overlap due to the parallel automation mode. Place safety-critical checks in the final actions and devices. Status and dashboard text are informative, not a safety certification.

The repository includes [static regression tests](../../../tests/test_blueprint.py) and GitHub Actions validation for YAML, Jinja, input references, and important guard scenarios. **A real Home Assistant installation test has not been performed here.**
