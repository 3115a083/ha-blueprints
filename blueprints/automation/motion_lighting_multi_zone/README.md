# Motion Lighting | Multi-Zone with Linked Presence

One Home Assistant automation controls **any number of independent motion-lighting zones**. Each zone can use its own sensors, lights, scene/script, lux threshold, sun/time condition and off timer. Linked presence in another area can keep a light on or extend its lifetime.

Inspired by [freakshock88's original motion + illuminance blueprint](https://community.home-assistant.io/t/turn-on-light-switch-scene-script-or-group-based-on-motion-illuminance-sun-more-conditions/257085). This is a separately implemented multi-zone variant with a different scheduler.

- [Blueprint YAML](motion_lighting_multi_zone.yaml)
- [Import directly into Home Assistant](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2F3115a083%2Fha-blueprints%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fmotion_lighting_multi_zone%2Fmotion_lighting_multi_zone.yaml)
- Minimum Home Assistant version: **2026.10.1** (repeatable field-based object selectors).

## Configure the automation

### 01 | Fast motion triggers

Select **all** motion and occupancy binary sensors used by the lighting zones. These sensors use one native state trigger for immediate light-on response. Add each sensor to its specific lighting zone in step 02 as well.

**Why select twice?** Home Assistant cannot automatically expand a dynamic collection of nested object entries into an arbitrary number of native state triggers. This two-step configuration avoids listening to every unrelated state change in Home Assistant. A sensor included only in a zone, but not in the first trigger list, cannot turn a light on.

### 02 | Lighting zones

Click **Add** for as many independent zones as needed, then configure the following fields for each.

| Setting | Effect |
| --- | --- |
| Zone name / enabled | Identify and enable this zone |
| Motion / occupancy sensors | Select the sensor(s) assigned to this zone, also selected under section 01 |
| Turn on light, switch, group, scene or script | Control an entity on motion |
| Actual lights/switches/groups to turn off | Required for scenes/scripts; optional for direct lights and switches |
| Automatically turn off | Enable or disable automatic switch-off |
| Seconds with no motion | Per-zone off delay, default 120 seconds |
| Illuminance sensor and threshold | Turn on only when sufficiently dark; optional input_number threshold helper |
| Sun and time restrictions | Per-zone above/below horizon, time window, including overnight |
| Linked-area presence | One or more binary sensors or input_boolean helpers from adjacent areas |
| Linked presence effect | Hold while occupied or extend the regular no-motion delay |
| Hold grace / extended delay | Additional seconds, default 120 seconds |
| Turn-on / turn-off blockers | Optional independent, per-zone safety conditions |

**Use unique physical light targets in each zone.** Do not make two zones independently control the same bulb unless you intend the resulting interaction. For multiple bulbs in a zone, use a Home Assistant light group or a scene with explicit off targets.

### 03 | Shared controls

An optional global enable helper, global turn-on blocker and global turn-off blocker apply to all zones. The default manual-on protection avoids turning off lights that were switched on after the local motion sensors stopped detecting activity.

## Hallway / bathroom example

| Field | Hallway | Bathroom |
| --- | --- | --- |
| Motion | binary_sensor.hallway_motion | binary_sensor.bathroom_motion |
| Turn on | light.hallway | light.bathroom |
| No-motion delay | 60 seconds | 180 seconds |
| Linked-area presence | binary_sensor.bathroom_occupancy | None |
| Linked behavior | **Hold** | None |
| Grace after occupancy ends | **120 seconds** | None |

Also select both hallway and bathroom motion sensors under **01 | Fast motion triggers**.

When the hallway detector sees someone, the hallway light turns on immediately. When the person enters the bathroom, its dedicated occupancy sensor stays on and **blocks hallway auto-off**. After bathroom occupancy becomes off, the hallway can turn off only after both the local inactivity delay and a 120-second additional grace period have elapsed. This prevents short repeated on/off cycles in the hallway.

For a bathroom where a motion detector turns off while a person is stationary, use a proper occupancy sensor or helper. A transient PIR motion state alone cannot guarantee a room remains occupied.

### Hold vs extend

**Hold:** Keep the hallway light on for as long as any linked sensor is on. Once the linked sensors are all off, wait the configured grace time after the most recently cleared linked sensor. The regular local no-motion delay must also have elapsed.

**Extend:** Add the configured duration to the normal local off delay when linked presence is currently active or has recently ended. This **does not guarantee the light remains on throughout a long bathroom visit**. Select Hold if your main goal is to avoid cycling the hallway lamp.

Linked occupancy does **not** turn on the neighboring light. It only affects its off decision.

## Lights, switches, scenes and scripts

The Turn on entity may be a light, switch, group, scene or script. Use a scene to set brightness and color. With a scene or script, also select the actual lights, switches or groups in the turn-off entities field because the scene or script itself cannot be turned off. Ordinary lights/switches/groups automatically use their own entity as the off target if nothing else was chosen.

## Efficiency and safety

- **Fast activation:** A native state trigger reacts to a fresh sensor transition to on. No polling is used to turn a light on.
- **Nonblocking off checks:** A 15-second time-pattern check evaluates the deadlines of every zone. There is no delay or wait-for-trigger running in the automation. Off actions may run up to approximately 15 seconds after their threshold.
- **Independent zones:** A long no-motion delay in one area does not block motion detection in another.
- **Skip unnecessary commands:** Already-on targets are not activated again. Already-off targets are not switched off again.
- **Ambient-light feedback:** Lux is checked when the room is about to be lit, not when it is already lit.
- **Fail closed:** Unknown/unavailable motion, linked presence or off-target entities suspend automatic off. Invalid lux data or blocker helper states prevent unsafe activation.
- **Manual-on protection:** If a light changes to on after the most recent motion sensor went off, the automation normally preserves it. This best-effort timestamp check is **not** a durable ownership system. HA restarts may reset last-changed timestamps.
- **Queued mode:** Runs contain no intentional waits and use an event-driven activation plus a small shared reconciliation pass.

Changes to the configured sensor list require re-saving/reloading the automation. Do not configure the same physical light in multiple zones if their off timers might compete.

## Practical validation

1. Configure two zones with separate bulbs and include both motion entities under section 01.
2. Trigger motion in one zone. The other zone must remain unaffected.
3. Verify lux cutoff, sun condition, time window and each blocker.
4. Turn the hallway light on by motion, then set bathroom occupancy on. Its normal off time must pass without the hallway light switching off.
5. Set bathroom occupancy off. Confirm the extra grace period and local no-motion timeout.
6. Test Extend independently. It is time-limited rather than a hard keep-on.
7. Confirm no unexpected off command while any configured sensor is unavailable.
8. Test a scene with an explicit off entity and a manually activated light.

Tests validate YAML, selectors, trigger routing, behavior under simulated state changes and the real Home Assistant script action engine. They cannot substitute for testing your actual lamps or presence sensors.

## Import URL

```text
https://github.com/3115a083/ha-blueprints/blob/main/blueprints/automation/motion_lighting_multi_zone/motion_lighting_multi_zone.yaml
```

## Blueprint updates

After a repository update, re-import the blueprint or use a configured updater. The canonical **source_url** always points to main. If using the optional Blueprints Updater integration, run **blueprints_updater.reload** when required to refresh tracking. Updating GitHub alone does not replace the local blueprint file in Home Assistant.
