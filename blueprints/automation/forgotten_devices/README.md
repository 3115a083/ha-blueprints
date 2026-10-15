# 💡 Forgotten Devices | Energy-Saving Shutoff

Turn off forgotten devices after a configurable maximum runtime, when your shutoff conditions permit it. Configure any number of device entries in one automation, using forms instead of YAML. Each entry has its own conditions and an optional runtime override. A single entry can select individual entities, an existing entity group, a list of entities, or all lights in a room, with exceptions.

[Import blueprint](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2F3115a083%2Fha-blueprints%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fforgotten_devices%2Fforgotten_devices.yaml)

Requires Home Assistant **2026.10.1 or newer**. Automated schema and execution tests run against Core 2026.10.1. Physical devices have not been tested.

## What it does

| Target | Action | Considered active |
| --- | --- | --- |
| Light, switch, fan, humidifier, input boolean | Target domain's `turn_off` | `on` |
| Climate / thermostat | `climate.set_hvac_mode` with `off` | `heat`, `cool`, `heat_cool`, `auto`, `dry`, `fan_only` |
| Media player | Stop, pause or power off, selected per entry | `playing`, `paused`, `buffering`, `on`; also `idle` when power-off is selected |

Thermostats must advertise the `off` HVAC mode. There is no automatic switch to another mode or setpoint. Media defaults to stopping playback; power-off is an explicit choice. Select the actual Music Assistant player entity if it supports the chosen standard media-player action. Vendor-specific services are not called.

## Setup

1. Import the blueprint and create an automation from it.
2. Create one **Date and/or time** helper per entry in **Settings → Devices & services → Helpers**. Enable **both date and time**. Set the initial value to a past date, such as yesterday. This is the last-attempt marker, not a future shutoff deadline. A whole room/group shares one helper; do not share it between different entries or automations.
3. Under **Devices**, add entries using **Add**. Select an individual entity/group, additional entities/groups, or rooms, and one dedicated date/time helper. An optional entry name identifies room-based entries.
4. Set **Default maximum runtime**, for example 30 minutes. Leave an entry's optional runtime unset to inherit it. A supplied individual runtime always overrides the global value.
5. Add local rules, global conditions, or both. Rules use raw state values such as `on` and `off`, rather than translated UI labels. Each local rule can require its source state to remain unchanged for a number of minutes.
6. Choose how each entry uses global conditions. Local rules can independently use ALL or ANY.
7. Add always-required safety conditions if needed, for example energy-saving enabled and guest mode off.
8. Leave **Preview only** enabled at first. Once the runtime expires and conditions pass, a persistent notification identifies the target. It sends no device command and does not consume an attempt.
9. After checking the preview, disable **Preview only**. The next eligible check can issue the shutdown command. Preview notices remain until you dismiss them.

No devices are controlled merely by importing this blueprint. You must create and enable an automation, configure entries, and disable preview.

## 🏠 Rooms, groups and exceptions

One entry can combine these selections:

| Field | Meaning |
| --- | --- |
| Individual entity or existing group | The original `entity` input remains supported; `group.*` and groups exposing `entity_id` members are also accepted. |
| Additional entities or groups | Select several individual devices or groups without creating a group helper. |
| Rooms / areas | Select one or more existing Home Assistant areas. Room selection defaults to lights only. |
| Types selected from rooms | Explicitly opt into switches, fans, thermostats, media players, humidifiers or input booleans where needed. It applies to room selections, not explicitly selected groups. |
| Exceptions | Exclude individual entities or all leaf members of a selected group. Exceptions take precedence over every inclusion method in this entry. |

**Example: all living-room lights except one lamp**

1. Add one entry and name it **Living room lights**.
2. Choose **Living room** under Rooms / areas. Leave the room type selection at **Lights**.
3. Under Exceptions, select the lamp that should stay untouched.
4. Select one date-and-time helper for this entire entry. Configure its common runtime and conditions.

Alternatively, select an existing living-room light group and the same exception. You can also select the lamps together under Additional entities or groups. Every method subtracts the exceptions before computing runtime or sending commands.

Groups are resolved recursively into concrete leaf entities. The automation never sends an off command to the original group entity, because that could control excluded members. Empty groups and unresolved/missing members are skipped. Repeated members within one entry are deduplicated. Recursion uses a visited set and at most 32 levels; deeper unresolved inclusion groups are skipped without falling back to an aggregate service call. If an exception group cannot be fully resolved, including a missing known group or a depth limit, the entire entry is blocked rather than risking an excluded member. Missing individual exception IDs remain explicitly excluded.

Room selection requires the leaf entities (or their devices) to be assigned to the selected Home Assistant areas. A group merely assigned to the living room does not import its kitchen members through room selection. If group members have no area assignment, select that group explicitly instead. Supported group membership must be exposed in `entity_id`; proprietary linked-speaker behavior such as `group_members` is not interpreted as standard entity-group membership. A media integration may still affect linked playback when a player receives a standard command.

Selections are resolved again before each member command. A lamp removed from the selected group/room or newly included in an exception group is skipped. A member switched off and on during dispatch is skipped for that batch; a new member is not added mid-batch. Commands are sequential and not transactional, so a changing safety condition can stop the remaining commands after some members have already been controlled.

If two entries select the same expanded leaf entity after their own exceptions, that overlapping member is skipped in **both** entries. Their non-overlapping members can still be processed. Exceptions are local to their entry: a separately configured entry can intentionally control a lamp excluded from a room entry. Do not share attempt helpers between entries.

Existing single-entity entries, their rules, runtime overrides, helper assignments and source URL remain valid. No recreation is needed after the blueprint update.

## Maximum runtime and rechecking

The time is a **maximum runtime before checking conditions**, not a period for which the shutoff conditions must continuously pass. A device with a 30-minute runtime is never switched off by this automation before those 30 minutes expire. If conditions fail at that point, its attempt marker is untouched and later checks may switch it off when they pass.

There is one shared check per minute. A device normally becomes eligible within 60 seconds after its runtime expires. Service latency and a large batch can add delay; this is not an exact-deadline timer. Sequential execution prevents overlapping sweeps. A check is skipped if the previous sweep is still running. There are no per-second loops or one long-running delay per device.

For a single target, runtime is calculated from its **latest state change**, using timezone-aware timestamps. A group waits for the most recent state change among its included, currently active members, so every active member gets at least the chosen runtime. Off, unavailable and excluded members do not delay the group. Examples:

- Light `off → on`: starts a new runtime.
- Brightness, volume or temperature attribute update without a state change: does not restart it.
- Thermostat `heat → cool`, or player `playing → paused`: starts a new runtime. This is deliberately state-based, rather than tracking time since a service command.
- Unavailable/unknown target: never switched off. Returning to an active state starts a new runtime.
- Home Assistant restart: restored/recreated states receive new timestamps, so allow a full fresh runtime. The blueprint does not infer time spent on while HA was offline.
- Automation reload: does not itself rewrite entity timestamps or clear attempt helpers. A pending eligible device is reconsidered at the next minute check.

For a condition such as **room vacant for 10 minutes**, use `binary_sensor.room_presence`, expected state `off`, hold time `10`. The target runtime and this hold time are independent. Changing from one away zone to another restarts an away rule's hold period because the source state changed.

## Global conditions per entry

The standard Home Assistant condition editor is available for global conditions, including nested AND/OR, time, numeric and template conditions. All top-level global conditions must pass.

| Entry mode | Rule |
| --- | --- |
| Required | Every configured global condition AND the local rule group must pass. An empty side is neutral. |
| Alternative | A nonempty passing global group OR a nonempty passing local group is sufficient. |
| Ignore | Only the local rule group applies. Global shutoff conditions are not used. |

An **empty global group is never a passing OR alternative**. When no applicable conditions exist, nothing happens unless that entry explicitly enables **Allow runtime-only shutoff**. This option only applies to empty conditions; it does not override configured failing conditions.

**Always-required safety conditions** are separate. They apply in every mode, including Ignore and Alternative, and are checked again just before sending the command. Use these for protections that must never be bypassed by OR logic. A failed safety check does not enable any fallback action.

Local rules support:

- **State equals**: one entity's exact state, optionally held for a duration.
- **Away from home**: a person or device tracker in any known non-home state, optionally held for a duration. `unknown`, `unavailable`, and missing sources never count as away.
- **ALL / ANY** across the local rules.

For more complex per-device logic, create a **Template Binary Sensor** helper, then use its `on` state as a local rule. A native condition-selector list stored inside a repeated object cannot be executed as dynamic script configuration by a standard blueprint. This implementation evaluates its explicit local-rule fields; it does not treat a nonempty condition list as a boolean or pretend arbitrary stored YAML has been executed.

## Examples

### Living-room light or room group after 30 minutes, only if the room is vacant

- Global runtime: 30 minutes.
- Target: your living-room light, or the Living room area with exceptions, using one attempt helper for this entry.
- Global mode: Ignore.
- Local rule: room presence sensor equals `off` for 10 minutes.
- Result: each included active light must have been on for 30 minutes and the room must have been vacant for 10 minutes. If people are still present at minute 30, later checks continue without consuming the attempt.

### Forgotten plug after 2 hours, only when everyone is away

- Target: a nonessential plug.
- Individual runtime: 120 minutes, overriding the global 30 minutes.
- Global mode: Required; no local rules needed.
- Global conditions: your household-away condition. Make sure unknown trackers cannot satisfy it, for example by checking a reliable household occupancy binary sensor equals `off`.
- Do not select refrigerators, medical equipment, network infrastructure or other equipment that must stay powered.

### Speaker after 45 minutes, either nobody home or room vacant

- Target: your media player.
- Individual runtime: 45 minutes.
- Media action: Stop playback.
- Global mode: Alternative.
- Global group: household-away condition.
- Local rule: room presence sensor equals `off` for 15 minutes.
- Either group can permit stopping playback after the runtime expires. Guest/sleep protection belongs in always-required safety conditions if it must block both groups.

### Thermostat

- Select the thermostat itself, not a power relay supplying it.
- Choose a suitable runtime and reliable absence rules.
- Add independent always-required heating/frost protections.
- The device must support HVAC mode `off`. This changes real heating/cooling. It does not set an eco temperature or automatically resume heating later. Use a native schedule or a separate explicitly designed automation for resumption.

## One attempt per entry activation period

Before dispatching a batch, the automation writes the current timestamp to the entry's dedicated helper. It then checks every member's state timestamp, current membership, exclusions, conditions and safety guards before that member's command. A failed helper write prevents the batch without blocking other entries. A helper without both date and time, or an unavailable or shared helper, blocks its affected entries.

Once a marker is recorded, the automation does not issue another batch for the same entry activation period, even if a service fails or a device ignores it. For an individual target this retains the original one-attempt behavior. For a group, a member entering a new active state after the marker can start a new group period. Once all included active members have matured, a new batch can include older members that remained active after a failed command. There is no automatic retry for an unchanged group period. Editing membership or exceptions alone does not clear the marker; a newly selected device that was already active before the last attempt may need a new active period or an explicitly reset helper before another batch.

Inspect **automation traces and Home Assistant logs** for failures. A changed final safety/rule check or group membership may consume the reserved batch without sending some or all commands. To deliberately retry, inspect the devices and set the entry's helper to a past time, or begin a new active period. Helper-write failures can be checked again at the next sweep, but cannot cause device commands without a confirmed marker write.

A service returning successfully does not prove physical shutdown. This blueprint does not power-cycle devices, turn anything back on, run arbitrary user-selected services, or silently fall back to a relay. For a WLED no-flash setup, target your configured Entity Proxy light instead of the physical light/relay.

## Testing and maintenance

```bash
# Existing static suite, with its documented PyYAML/Jinja2 dependencies:
python -m unittest discover -s tests -v

# Separate Python 3.14 environment:
python -m pip install -r integration_tests/requirements.txt
python -m pytest integration_tests -q
```

The real-HA suite validates the blueprint and nested object selectors, runs its actual script actions with simulated states/services, and tests runtime overrides, global modes, state hold times, away states, preview, unavailable inputs, duplicate configuration, one-attempt behavior, failures, rechecks and reactivation races. Group tests additionally cover nested/cyclic groups, room-domain filters, exceptions, overlapping entries, shared timers, membership/area changes during dispatch and leaf-only service targets. No physical-device behavior is inferred from these tests. Test your own sensors and devices before relying on shutdown behavior.

## Import URL and updates

Copy this URL into Home Assistant's **Import blueprint** dialog. On GitHub, the code block has a built-in copy button.

```text
https://github.com/3115a083/ha-blueprints/blob/main/blueprints/automation/forgotten_devices/forgotten_devices.yaml
```

This is also the blueprint's `source_url`. [Blueprints Updater](https://github.com/luuquangvu/blueprints-updater) can track changes at this stable `main` URL without a GitHub Release or version tag. Keep `source_url` in the installed YAML. After import, refresh the integration with `blueprints_updater.reload` if necessary, and check its tracking filters. See the [repository update instructions](../../../README.md#updates-with-blueprints-updater).
