# Multi-Zone Motion Lights | Cross-Room Presence

Manage **any number of independent motion-light zones in one automation**, using a repeatable Home Assistant form. Every zone has its own motion sensors, lights, off delay, optional lux/sun/time conditions, and optional occupancy hold from a nearby room.

[Import blueprint](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2F3115a083%2Fha-blueprints%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fmulti_zone_motion_lights%2Fmulti_zone_motion_lights.yaml) | [Blueprint YAML](multi_zone_motion_lights.yaml)

Minimum Home Assistant: **2026.10.1**. Inspired by [freakshock88's original motion/illuminance/sun blueprint](https://community.home-assistant.io/t/turn-on-light-switch-scene-script-or-group-based-on-motion-illuminance-sun-more-conditions/257085). This is a separate multi-zone implementation, not an unchanged copy.

## Quick setup

1. Import the blueprint, then create ONE automation.
2. In **01 | Sensor monitoring**, choose **all motion entities used in any zone**. This is a one-time registration of sensors for immediate, entity-filtered ON triggers.
3. In **02 | Lighting zones**, click Add for every room or hallway. Select motion sensors (from the registered list), activation entities, and the independent off delay.
4. For a hallway adjoining a bathroom, configure the bathroom presence sensor in the **hallway** zone's Cross-room presence field.
5. Save and test each zone, first without cross-room presence, then with it.

The form supports adding any number of zones. Each zone sensor is assigned again within its zone after being registered at the top. This is necessary because Home Assistant blueprints cannot dynamically create entity-filtered state triggers from repeatable form entries. Duplicating that selection is preferable to listening for every state change in Home Assistant.

## Hallway and bathroom example

| Field | Hallway zone | Bathroom zone |
| --- | --- | --- |
| Motion sensors | Hall motion | Bath motion |
| Turn ON | Hall lights | Bath lights |
| Off delay | 90 seconds | 180 seconds |
| Cross-room presence | Bath occupancy sensor | None |
| Grace after presence clears | 180 seconds | Not used |

Both motion sensors must also appear in the top-level monitoring list.

When someone enters the hallway, its light starts immediately. After they enter the bathroom, the bathroom occupancy sensor holds the hallway light ON even after the hallway's ordinary motion timer expires. When bathroom presence becomes OFF, the hallway remains lit for another 180 seconds. New hallway motion postpones the deadline again.

**Use reliable occupancy:** A PIR in the bathroom may go OFF while someone is motionless. For long visits, prefer a mmWave presence sensor, a sustained occupancy helper, or a suitable room occupancy entity. Cross-room sensors do not independently switch ON the hallway: they only delay its switch-off.

## Form fields

The input sections are grouped as follows.

**01 | Sensor monitoring:** A combined list of observed motion entities and an optional master enable switch. When the master is OFF, pending switch-off commands still work.

**02 | Lighting zones:** Each repeated row contains a name, enable switch, zone motion sensors, one or more ON entities (lights, switches, groups, scenes, scripts), optional explicit OFF entities, motion timeout, linked-room occupancy entities, grace time, optional lux sensor and threshold, sun/daylight rule, start/end local time, activation blocker, and optional ownership Input Boolean.

**03 | Diagnostics:** Optional logging of actual ON/OFF commands and a startup warning when a zone sensor was omitted from the monitoring list.

### ON and OFF targets

- ON entities may be lights, switches, groups, scenes or scripts. Mixed domains are supported through the generic Home Assistant turn-on action.
- If ON entities are only lights/switches/groups, leaving the OFF target empty automatically selects the same entities for switch-off.
- When ON includes a scene or script, configure explicit light/switch/group OFF entities. Otherwise automatic switch-off is disabled for that zone to avoid partial or accidental shutdowns.
- Setting the zone off delay to 0 disables automatic switch-off.
- Avoid assigning the same OFF entity to multiple independent zones unless you intentionally allow either zone to control it. For one shared hallway lamp, use a single zone with several motion entities.

### Manual control and ownership

A light already ON before motion can be impossible to distinguish from a light activated by the automation. For a room that is also controlled manually, the optional **ownership helper** is recommended: create an Input Boolean for that zone, initially OFF, and select it in the form.

The automation sets that helper ON only after it sends its own activation. It sends OFF only when the helper remains ON, then resets the helper. When lights are turned OFF manually, the reconciliation will clear the helper. Without a helper, a timestamp safeguard avoids repeatedly switching OFF a light that was turned ON later by hand, but cannot always protect a light already ON before motion starts.

### Sun, time, illuminance, blockers

Sun, time window, illuminance threshold, master switch and per-zone blocking switch are checked only for a NEW ON command. They do not prevent an existing automatic OFF when the room becomes unoccupied. The local time window supports crossing midnight. Unknown lux, blocker or master states block new activations.

## Cross-room timing

OFF is allowed only if every configured motion sensor and linked-room presence sensor is OFF and available. Any ON, unknown, unavailable or missing entity blocks OFF, rather than assuming a room is empty.

The target deadline is the later of:

- Latest zone motion OFF timestamp plus the zone inactivity timeout.
- Latest linked-room presence OFF timestamp plus its configured grace period.

When the linked-room presence remains ON, the target will not switch OFF at any deadline. Grace = 0 means hold only while linked presence is ON; it does not add time after it becomes OFF.

The ON trigger is **immediate and entity-filtered**. A single lightweight time-pattern reconciliation runs every **15 seconds** for OFF, with no separate timer per zone, no high-frequency motion polling and no event listener watching all Home Assistant entities. OFF can occur up to 15 seconds after its deadline.

Home Assistant start and automation reload also reconcile overdue OFF actions. This avoids relying on nonpersistent time-based trigger-for timers. After a restart, sensor last-changed timestamps may reset and extend the countdown. Queued automation mode (max 50) serializes ON/OFF decisions, preventing two zones from issuing overlapping commands within this automation; slow device services may delay subsequent queued work.

## Safety and troubleshooting

The blueprint fails closed when a motion or linked-presence sensor becomes unavailable, which can leave lights ON during sensor outages. Choose reliable sensors, or remove the dependency if this is unacceptable. Avoid scenes/scripts with unrelated side effects. No unconditional retries or relay cycling are performed.

If the light does not turn ON, check that its motion entity is registered in both places, then inspect lux, time, sun, blocker and master enable inputs. If it will not turn OFF, inspect every motion/linked-presence sensor, the OFF targets, and any optional ownership helper. The automation trace shows all computed zone variables, deadlines and guards.

Test the hallway/bathroom traversal, motion retriggers, manual ON and OFF, unknown/unavailable sensors, restart during occupation, overnight time windows and several simultaneous zones. Static and simulated Home Assistant tests do not substitute for checking actual lights and motion sensors.

## Attribution and updates

Feature inspiration: [freakshock88's Home Assistant motion, illuminance and sun blueprint](https://community.home-assistant.io/t/turn-on-light-switch-scene-script-or-group-based-on-motion-illuminance-sun-more-conditions/257085). This implementation adds repeated zone configuration, independent cross-room holds, native form fields and restart-safe off-deadline reconciliation.

Canonical import URL:

https://github.com/3115a083/ha-blueprints/blob/main/blueprints/automation/multi_zone_motion_lights/multi_zone_motion_lights.yaml

Reimport/update the blueprint on your Home Assistant instance after GitHub changes. Updating GitHub does not replace the locally installed file. With the optional Blueprints Updater integration, refresh its registry using the blueprints_updater.reload action.
