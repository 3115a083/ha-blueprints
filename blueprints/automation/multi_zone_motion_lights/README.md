# Multi-Zone Motion Lights | Cross-Room Presence

Manage **any number of independent motion-light zones in one automation**, using a repeatable Home Assistant form. Every zone has its own motion sensors, lights, off delay, optional lux/sun/time conditions, and optional occupancy hold from a nearby room. A zone can also turn ON **when the sun sets or its lux level drops below a threshold, even if no new motion is detected**, provided that zone is still occupied.

[Import blueprint](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2F3115a083%2Fha-blueprints%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fmulti_zone_motion_lights%2Fmulti_zone_motion_lights.yaml) | [Blueprint YAML](multi_zone_motion_lights.yaml)

Minimum Home Assistant: **2026.10.1**. Inspired by [freakshock88's original motion/illuminance/sun blueprint](https://community.home-assistant.io/t/turn-on-light-switch-scene-script-or-group-based-on-motion-illuminance-sun-more-conditions/257085). This is a separate multi-zone implementation, not an unchanged copy.

## Quick setup

1. Import the blueprint, then create ONE automation.
2. In **01 | Sensor monitoring**, choose **all motion entities used in any zone**. This is a one-time registration of sensors for immediate, entity-filtered ON triggers. If you want **lux-crossing** activation, also register the corresponding lux sensors in the separate illuminance monitoring list. Sunset-only activation needs no lux registration.
3. In **02 | Lighting zones**, click Add for every room or hallway. Select motion sensors (from the registered list), activation entities, and the independent off delay.
4. To keep the **hallway lights** ON while someone uses the bathroom or kitchen, edit the **Hallway** row and select the **Bathroom** and **Kitchen** occupancy sensors under **Hold THIS zone's lights ON: presence sensors in OTHER rooms**. Do **not** put the hallway sensor into the bathroom/kitchen rows unless you also want their lights held ON.
5. To activate already-occupied rooms at dusk, select **Switch ON when it becomes dark while THIS zone is occupied** in that zone. Choose **At sunset**, **Lux crossing**, or **Both**. Add a **Presence sensor INSIDE THIS zone** if the room's motion sensor may go OFF while someone is still present.
6. Save and test each zone, first without cross-room presence, then with it.

The form supports adding any number of zones. Each zone sensor is assigned again within its zone after being registered at the top. This is necessary because Home Assistant blueprints cannot dynamically create entity-filtered state triggers from repeatable form entries. Duplicating that selection is preferable to listening for every state change in Home Assistant.

## Already occupied at sunset or when illuminance drops

**Scenario:** Someone enters a room while it is bright. The motion sensor switches ON, but the sun/lux condition prevents the light from coming on. They remain in the room. Later the sun sets or the room becomes dark, and no new motion event occurs.

The zone has an opt-in **Switch ON when it becomes dark while THIS zone is occupied** selector:

| Option | Behavior |
| --- | --- |
| **Disabled** (default) | Existing motion-only behavior. No automatic illumination on changing daylight. |
| **At sunset** | When `sun.sun` becomes `below_horizon`, check this zone for *current* occupancy and normal activation conditions. |
| **When this zone's lux value crosses its threshold** | When the zone's registered lux sensor changes **from above** its lux threshold to **at or below** the threshold, recheck occupancy and conditions. |
| **At sunset OR when lux crosses its threshold** | Try at either event, without switching ON twice. |

**Presence is checked in THIS zone, not in the linked rooms.** The blueprint accepts a zone's own motion sensor that is currently ON, or any optional **Presence sensors INSIDE THIS zone** that are currently ON. A bathroom presence sensor configured as a *cross-room hold for the hallway* does **not** switch on the hallway lights by itself at sunset. This keeps the two functions separate.

If an ordinary PIR switches OFF while someone is sitting still, the blueprint cannot know that the room is occupied unless a separate, sustained occupancy sensor/helper is configured inside that zone. A mmWave presence sensor or suitable occupancy helper is ideal. An own-zone presence sensor also prevents automatic switch-off while it remains ON.

### Lux setup

1. Register the sensor under **01 | Sensor monitoring → Lux sensors for occupied-room darkness activation**.
2. Select the **same lux entity** in the relevant zone's **Optional illuminance sensor** field.
3. Set that zone's **Only switch ON at or below this lux level** (for example 80 lx).
4. Set **Switch ON when it becomes dark while THIS zone is occupied** to Lux or Both.

The lux sensor's actual state must cross a threshold numerically, for example 95 lx → 75 lx with an 80 lx threshold. Repeated reports of 75 lx, nonnumeric states such as `unavailable` → 75 lx, and changes to an unrelated room's sensor do not start lights. Registering a lux sensor does not enable darkness activation in zones where it is disabled.

### Sunset setup

Set a zone to **At sunset** or **Both**. Home Assistant watches `sun.sun` directly; no extra monitoring input is necessary. Sunset uses the location configured in your Home Assistant instance.

**Existing ON conditions still apply:** Sun mode, lux threshold, clock window, global enable switch, zone blocker, and already-on/ownership guards are evaluated on sunset and lux events exactly as on motion events. For example, if a zone has a lux sensor reporting 200 lx at sunset and an 80 lx threshold, the sunset event does not turn its lights ON. Choosing **Both** lets a later lux threshold crossing try again.

**Compatibility:** Existing zones default to Disabled, so updating the blueprint does not silently activate lights at sunset. After updating, opt in per zone.

## Which zone gets the other room's presence sensor?

**Configure the rule on the zone whose LIGHTS you want to protect.** Cross-room presence uses sensors from OTHER rooms to delay that zone's automatic switch-off.

| You want to keep these lights ON | Edit this lighting zone | Select these OTHER rooms' occupancy sensors |
| --- | --- | --- |
| Hallway lights while somebody is in the bathroom or kitchen | **Hallway** | **Bathroom**, **Kitchen** |
| Bathroom lights while somebody is in the hallway (only if desired) | **Bathroom** | **Hallway** |
| Kitchen lights while somebody is in the hallway (only if desired) | **Kitchen** | **Hallway** |

For the usual hallway use case, **only the first row applies**. You do not configure the hallway in the bathroom or kitchen zones.

When either Bathroom **or** Kitchen occupancy is ON, the Hallway lights remain ON. Only when **all** selected linked rooms become vacant does the configured extra grace period begin. The hold **does not switch the hallway lights ON** by itself. Hallway motion must first activate the lights.

This is a one-way relationship unless you deliberately configure the opposite direction in another zone. The field uses **presence entities** (binary sensors, occupancy helpers or compatible groups), **not** zone names or light entities.

## Hallway and bathroom example

| Field | Hallway zone | Bathroom zone |
| --- | --- | --- |
| Motion sensors | Hall motion | Bath motion |
| Turn ON | Hall lights | Bath lights |
| Off delay | 90 seconds | 180 seconds |
| Hold THIS zone's lights ON: OTHER rooms | Bath occupancy sensor (also Kitchen if wanted) | None |
| Grace after presence clears | 180 seconds | Not used |

Both motion sensors must also appear in the top-level monitoring list.

When someone enters the hallway, its light starts immediately. After they enter the bathroom, the bathroom occupancy sensor holds the hallway light ON even after the hallway's ordinary motion timer expires. When bathroom presence becomes OFF and every other linked room is also vacant, the hallway remains lit for another 180 seconds. New hallway motion postpones the deadline again.

**Use reliable occupancy:** A PIR in the bathroom may go OFF while someone is motionless. For long visits, prefer a mmWave presence sensor, a sustained occupancy helper, or a suitable room occupancy entity. Cross-room sensors do not independently switch ON the hallway: they only delay its switch-off.

## Form fields

The input sections are grouped as follows.

**01 | Sensor monitoring:** A combined list of observed motion entities, an optional separate list of monitored lux entities, and an optional master enable switch. When the master is OFF, pending switch-off commands still work.

**02 | Lighting zones:** Each repeated row contains a name, enable switch, zone motion sensors, optional **own-zone occupancy sensors**, one or more ON entities (lights, switches, groups, scenes, scripts), optional explicit OFF entities, motion timeout, linked-room occupancy entities, grace time, optional lux sensor and threshold, **darkness-activation mode**, sun/daylight rule, start/end local time, activation blocker, and optional ownership Input Boolean.

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

Sun, time window, illuminance threshold, master switch and per-zone turn-on blocker are checked on every NEW ON command, whether caused by motion, sunset or a lux threshold crossing. The blocker accepts a light, switch, binary sensor or Input Boolean. For example, set the bathroom zone's **Optional turn-on blocker** to `light.night_lamp`: while that light reports `on`, bathroom motion cannot switch on its configured lights. When the blocker reports `off`, motion is allowed again (subject to the other conditions). `unknown`, `unavailable` and missing blocker entities fail closed. The blocker does not turn the selected light off, and it does not prevent an existing automatic OFF when the room becomes unoccupied. The local time window supports crossing midnight.

After updating the imported blueprint, reopen the automation and confirm that the intended `light.*` entity is saved in **Optional turn-on blocker** for the correct zone. Check its actual state in Developer Tools, then test motion with the blocker ON and OFF. The GitHub update alone does not update an existing Home Assistant import.

## Cross-room timing

OFF is allowed only if every configured motion sensor, **own-zone presence sensor** and linked-room presence sensor is OFF and available. Any ON, unknown, unavailable or missing entity blocks OFF, rather than assuming a room is empty.

The target deadline is the later of:

- Latest own-zone motion **or own-zone presence** OFF timestamp plus the zone inactivity timeout.
- Latest linked-room presence OFF timestamp plus its configured grace period.

When the linked-room presence remains ON, the target will not switch OFF at any deadline. Grace = 0 means hold only while linked presence is ON; it does not add time after it becomes OFF.

Motion ON triggers and registered lux changes are **immediate and entity-filtered**. The sunset state change also triggers directly. A single lightweight time-pattern reconciliation runs every **15 seconds** for OFF, with no separate timer per zone, no high-frequency motion polling and no event listener watching all Home Assistant entities. OFF can occur up to 15 seconds after its deadline.

Home Assistant start and automation reload also reconcile overdue OFF actions. This avoids relying on nonpersistent time-based trigger-for timers. After a restart, sensor last-changed timestamps may reset and extend the countdown. Queued automation mode (max 50) serializes ON/OFF decisions, preventing two zones from issuing overlapping commands within this automation; slow device services may delay subsequent queued work.

## Safety and troubleshooting

The blueprint fails closed when a motion or linked-presence sensor becomes unavailable, which can leave lights ON during sensor outages. Choose reliable sensors, or remove the dependency if this is unacceptable. Avoid scenes/scripts with unrelated side effects. No unconditional retries or relay cycling are performed.

If the light does not turn ON, check that its motion entity is registered in both places, then inspect lux, time, sun, blocker and master enable inputs. For sunset activation, check that THIS zone is still occupied and opted in. For lux activation, confirm that the zone's lux sensor is also registered under Sensor monitoring and actually crossed the threshold. If it will not turn OFF, inspect every motion/linked-presence sensor, the OFF targets, and any optional ownership helper. The automation trace shows all computed zone variables, deadlines and guards.

Test the hallway/bathroom traversal, motion retriggers, occupied-zone sunset, lux threshold crossing, stationary occupancy with PIR OFF, manual ON and OFF, unknown/unavailable sensors, restart during occupation, overnight time windows and several simultaneous zones. Static and simulated Home Assistant tests do not substitute for checking actual lights and motion sensors.

## Attribution and updates

Feature inspiration: [freakshock88's Home Assistant motion, illuminance and sun blueprint](https://community.home-assistant.io/t/turn-on-light-switch-scene-script-or-group-based-on-motion-illuminance-sun-more-conditions/257085). This implementation adds repeated zone configuration, independent cross-room holds, native form fields and restart-safe off-deadline reconciliation.

Canonical import URL:

```text
https://github.com/3115a083/ha-blueprints/blob/main/blueprints/automation/multi_zone_motion_lights/multi_zone_motion_lights.yaml
```

Reimport/update the blueprint on your Home Assistant instance after GitHub changes. Updating GitHub does not replace the locally installed file. With the optional Blueprints Updater integration, refresh its registry using the blueprints_updater.reload action.
