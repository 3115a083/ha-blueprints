# 🔧 Govee Light Recovery | MQTT → Add-on Restart → Relay Hard Reset

Home Assistant recovery blueprint for **any number of Govee2MQTT lamps**, each with an optional ESPHome power relay and Ping sensor. The automation now uses a clear, gentle-first sequence: **restart Govee2MQTT first**, wait for lamps to reconnect, **restore an OFF relay** if necessary, and **only then consider a deliberate relay OFF/ON hard reset**.

[**Import into Home Assistant**](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2F3115a083%2Fha-blueprints%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fgovee_recovery%2Fgovee_recovery.yaml) · [Blueprint YAML](govee_recovery.yaml) · [All blueprints](../../../README.md)

**Requirements:** Home Assistant **2025.7+** for repeatable device lists, existing Govee2MQTT \`light\` entities, and optional \`switch\` relays and \`binary_sensor\` Ping entities. The app restart step uses **Home Assistant OS / Supervisor**.

## What changed and why

Earlier versions tried relay recovery or hard resets before restarting Govee2MQTT. App restarting could also be silently disabled if no \`input_datetime\` helper was selected, even when the restart checkbox and add-on slug were configured. In addition, a single aggregate availability trigger does not retrigger when more lamps go offline while one is already offline.

The revised version:

- First tries **one Govee2MQTT restart** when the first light outage is detected, if enabled and a valid app slug is selected.
- Works **without a cooldown helper for a one-shot add-on restart**. For longer-term automatic retry and relay hard resets, use the helper.
- Waits for reconnection, then turns ON any power relay still reported OFF (without deliberately cutting its power).
- Only after the bridge-restart stage, optionally **hard-resets still-unavailable lamps one at a time**, each using its own configured relay.
- Limits the number of hard resets in one run (default **2**) and each relay is switched OFF at most once per run.
- Adds periodic reconciliation **every 10 minutes** if a cooldown helper is selected; the global cooldown (default **60 minutes**) still protects from repeated disruptive operations.
- Provides readable, per-lamp diagnostics in **English or German**, including what was requested and why a recovery step was skipped.

**Important:** Reloading or importing a new blueprint does not necessarily update an already imported local file. After updating, review and save the existing automation, and reload automations if necessary.

## 💡 01 | Lights and optional hardware

Use **Add** to include as many Govee lights as needed. Each entry requires a \`light\` entity; its power relay and Ping sensor are optional.

| Lamp | Relay | Ping | Possible operations |
| --- | --- | --- | --- |
| Ceiling light with Sonoff | Optional Sonoff/ESPHome switch | Optional | Restart Govee2MQTT; restore relay; optionally hard reset |
| Lamp without a power relay | None | Optional | Restart Govee2MQTT and notify; **no power cycling** |
| Several failed lamps | Various | Optional | One bridge restart, then at most the configured number of individual hard resets |

Connected lamps with state \`off\` are considered available; **off** does not mean connectivity failure. Only states \`unknown\` and \`unavailable\` trigger offline recovery.

## 🔄 02 and 03 | Repair order

<details>
<summary>Exact recovery sequence</summary>

1. Wait until one or more lamps have been unavailable for the configured time (default 2 minutes), until a power relay has been OFF for 1 minute, or perform periodic/startup reconciliation.
2. Check whether a recovery is allowed by the shared cooldown.
3. **Restart Govee2MQTT** once, if enabled and its exact slug has been provided. Wait for reconnection (default 150 seconds).
4. If any configured relay is still OFF and **Restore a relay found OFF** is enabled, turn it ON; wait for the affected lamps (default 90 seconds).
5. If one or more lamps remain unavailable, and **Allow one targeted power cycle** is explicitly enabled, select only lamps with a configured relay known to be ON. If a persistent cooldown helper is configured, power-cycle them sequentially, up to the configured limit (default 2). Wait after each cycle.
6. Recheck every lamp and relay. Clear the previous warning if recovered, otherwise send one clear diagnostic notification.

</details>

**Hard resets are disabled by default** and require all of the following: Govee2MQTT app restart enabled, a nonempty app slug, a valid persistent cooldown helper, a currently unavailable lamp, and its own available **ON** relay. **If multiple configured lamps share the same relay, that relay will never be deliberately power-cycled**; otherwise one reset could interrupt a second lamp that is working normally. Devices without a relay cannot be hard-reset. Power cycling does not require a Ping sensor by default, because some Govee devices may not respond to ICMP even when healthy.

If you wish to restrict hard resets to devices that fail Ping, enable **Require failed Ping before hard reset** and configure that lamp's Ping sensor. This will skip devices with no Ping sensor, Ping ON, or unknown Ping state.

**Relay ON vs. hard reset:** When the relay is OFF, the automation only requests ON. Deliberately switching it OFF and ON is a separate, explicitly enabled step. Relay cycles are only considered **after** the add-on restart and initial relay restoration checks.

### Govee2MQTT app settings

In **03 | Govee2MQTT restart (first)**, set:

- **Allow restarting the Govee2MQTT app:** **ON**.
- **Govee2MQTT app or add-on slug:** Enter the **exact slug** from Home Assistant's app/add-on details.
- **Wait after restarting Govee2MQTT:** e.g. **150 seconds**.

The automation uses the official Home Assistant Supervisor action \`hassio.app_restart\`, not a host reboot or MQTT broker restart. This action requires Home Assistant OS and administrator privileges. If disabled or the slug is missing, the notification explains that the add-on restart was skipped; an automatic hard reset is also skipped, to preserve the requested order.

Official documentation: [Restart app](https://www.home-assistant.io/actions/hassio.app_restart/).

## 🛡️ 04 | Safe retry limits

For persistent retries and hard resets, create one \`input_datetime\` helper **with date and time**, for example \`input_datetime.govee_last_recovery\`. Initialize its value to a date older than the configured cooldown (default 60 minutes).

- **No helper:** Newly detected outages may trigger a single enabled app restart, and OFF relays can be restored. Periodic retries and automatic hard resets stay disabled.
- **With helper:** Repeated attempts are guarded across HA restarts. The blueprint checks for lingering outages every 10 minutes but restarts/cycles only when the cooldown has elapsed.
- OFF relays can be restored to ON during a cooldown; this never deliberately cuts power.
- If the helper cannot be updated, the automation does not proceed to a hard reset.

**Electrical safety:** An HA automation cannot guarantee that a relay always returns ON if Home Assistant restarts or loses power during the intentional OFF delay. Use this option only when a brief power cut is acceptable. Prefer \`restore_mode: ALWAYS_ON\` and \`early_pin_init: false\` (on supported ESP8266 hardware) to prevent unwanted power cycling in the first place.

## 🔔 05 | Readable notifications

Select **Notification language: English or Deutsch**. On failure, Home Assistant shows a clear **per-lamp summary** instead of a raw state snapshot. The report separates **observed results** from **attempted recovery commands**.

Example, with German selected:

> **Govee-Verbindungsprüfung**
>
> **Ergebnis:** 1/2 Lampen erreichbar.
>
> **Betroffene Lampen:**
> - **Deckenlampe Wohnzimmer:** nicht erreichbar · Relais EIN · Ping ohne Antwort. WLAN/Stromversorgung prüfen (Ping allein ist nicht eindeutig).
>
> **Wiederherstellungsversuche (Reihenfolge):**
> 1. Govee2MQTT: Neustart angefordert; Erfolg bitte im Automations-Trace prüfen
> 2. Relais: keine ausgeschalteten Relais
> 3. Hard-Reset: für folgende Lampen vorgesehen (nicht unbedingt ausgeführt): Deckenlampe Wohnzimmer
>
> **Nächster Schritt:** Add-on-Kennung, Automations-Trace und Govee2MQTT-Protokoll prüfen.

If a recovery is blocked by the cooldown, the failure remains visible; however, repeated 10-minute periodic checks do not repeatedly push the same warning to your phone. The text records that a command was **requested** or a hard reset was **planned**, not that the service definitely succeeded. A lamp may reconnect before its scheduled hard reset, in which case its power is not interrupted. For failed or slow commands, inspect the automation trace and Govee2MQTT logs. The old failure notification is dismissed when all configured lamps become available again. Optional \`notify\` entities can also receive the report.

## Limitations and troubleshooting

A lamp can remain in state \`on\` or \`off\` but ignore commands; an availability-based automation cannot prove control or connectivity health in that case. Checking ping, LAN discovery, Govee2MQTT logs, MQTT broker state, router Wi-Fi status and local UDP reachability can help identify the cause.

The trigger for "some lamp offline" changes from false to true at the **first** offline lamp. If another lamp fails while one is already unavailable, a separate fresh event may not fire; the 10-minute reconciliation addresses this **when the cooldown helper is configured**. Only one recovery run can execute at once, to prevent conflicting power cuts and bridge restarts.

For Govee LAN-capable models, enable LAN control, reserve stable lamp IPs, review Govee2MQTT \`scan\`/multicast settings and check your VLAN/firewall UDP settings. [Govee2MQTT](https://github.com/wez/govee2mqtt) · [LAN documentation](https://github.com/wez/govee2mqtt/blob/main/docs/LAN.md).

### Updating an existing automation

1. Update/re-import the Govee recovery blueprint from GitHub, then open and **save** the existing automation.
2. Ensure the old fixed light slots have been migrated to the repeatable **Govee lamps** list.
3. Verify the exact **Govee2MQTT app slug** in section 03. The restart toggle now defaults to **ON**, but no restart occurs unless the slug is configured. Previously saved automation inputs may still contain an explicit OFF value.
4. Set the desired language in **05 | Notifications**.
5. Initially leave deliberate relay hard resets disabled. Confirm the bridge restarts and reconnects the lamps first.
6. If appropriate, add a date+time cooldown helper and enable power cycling only after checking your relay wiring and safety.
7. Check Home Assistant automation **Traces** while simulating a short disconnection.

Tests in [tests/test_govee_recovery.py](../../../tests/test_govee_recovery.py) cover input references, trigger paths, the restart-before-relay sequence, cooldown, safe hard-reset selection and readable notifications. **A test on actual Govee2MQTT/Sonoff hardware is still required.**
