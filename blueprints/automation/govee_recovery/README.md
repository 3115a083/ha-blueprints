# 🔧 Govee Light Recovery | Optional ESPHome Relay & MQTT

A Home Assistant automation blueprint that monitors **any number of Govee2MQTT lights**. Add a separate entry for each lamp; an ESPHome power relay and a Ping reachability sensor are both **optional per lamp**.

When a lamp becomes unavailable, the blueprint can restore a switched-off relay (if present), optionally attempt a tightly guarded power cycle, restart Govee2MQTT once for the entire set, and report the result.

[**Import into Home Assistant**](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2F3115a083%2Fha-blueprints%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fgovee_recovery%2Fgovee_recovery.yaml) · [Blueprint YAML](govee_recovery.yaml) · [All blueprints](../../../README.md)

**Requirements:** Home Assistant **2025.7 or newer** (repeatable object selectors were introduced in 2025.7) and Govee2MQTT lamp entities in the \`light\` domain. **Relays are not required**. Restarting Govee2MQTT requires Home Assistant OS or Supervised, the correct app slug, and Supervisor access.

**Migrating from an earlier version:** The old fixed \`light_1\`, \`relay_1\`, \`light_2\`, \`relay_2\` and \`ping_1\`/\`ping_2\` inputs have been replaced by the single repeatable \`lamp_entries\` input. After updating the blueprint, **edit your existing automation and reselect its lamps**. Old two-device inputs are not migrated automatically.

## 💡 01 | Add as many lights as needed

Choose **Govee lamps (add as many as needed)** and click **Add** for each light. Each row offers:

- **Govee light — required:** Select its \`light.\` entity.
- **Power relay — optional:** Select the \`switch.\` that physically powers that lamp, only if it exists and is normally meant to stay ON.
- **Ping sensor — optional:** Select a \`binary_sensor.\` that reports whether that lamp answers ICMP Ping. Needed only if you want the optional relay power-cycle step.

The Home Assistant input is a repeatable object selector, so it has **no built-in two-light or three-light limit**. Its form presents device rows rather than requiring a manually constructed mapping. <https://www.home-assistant.io/docs/blueprint/selectors/#object-selector>

### Example setups

| Lamp | Relay | Ping | Available repair methods |
| --- | --- | --- | --- |
| Living room ceiling | Sonoff ESPHome switch | Ping sensor | Restore relay, optional guarded power cycle, optional bridge restart |
| Bedroom ceiling | Not configured | Not configured | Optional bridge restart and failure notification |
| Hallway ceiling | Not configured | Ping sensor | Optional bridge restart and failure notification |

An equivalent underlying list looks like this (you normally configure it in the UI):

\`\`\`yaml
lamp_entries:
  - light: light.govee_living_room
    relay: switch.sonoff_living_room
    ping: binary_sensor.govee_living_room_ping
  - light: light.govee_bedroom
  - light: light.govee_hallway
    ping: binary_sensor.govee_hallway_ping
\`\`\`

**No relay selected?** Nothing is switched at the mains: relay restoration and power cycling are automatically skipped for that lamp. It can still be checked and included in an optional shared Govee2MQTT restart. A selected Ping sensor alone never authorizes a power cycle without a matching relay.

## 🛠️ 02 | Recovery steps

A lamp is considered offline when its entity is \`unknown\` or \`unavailable\` for at least the configured period (default **2 minutes**). The normal \`off\` state is **not** an error.

| Recovery step | Default | Conditions and effect |
| --- | --- | --- |
| Turn an OFF power relay ON | **Enabled** | Runs only on entries with a configured relay that actually reports OFF. No power is deliberately cut. |
| Deliberate relay power cycle | **Disabled** | Requires one initially unavailable lamp, a configured relay reporting ON, a dedicated Ping sensor reporting OFF, no relay fault in this attempt, and a persisted cooldown. Turns only that one relay OFF briefly and back ON. |
| Restart Govee2MQTT | **Disabled** | If a light remains unavailable and its relay is ON **or no relay is configured**, restart the shared bridge once, not once per lamp. Requires a persisted cooldown. |
| Notify about failure | **Enabled** | Show a persistent notification listing the status, relay (or “no relay”) and Ping for **every** configured light. Optional extra phone notification. |

When two or more lights fail together, **power cycling is suppressed**. This helps avoid disrupting multiple healthy devices during a shared bridge or network outage.

Relay restoration remains possible during the cooldown because switching an unexpectedly OFF relay ON is less disruptive than restarting it. Disruptive steps are rate-limited by one shared cooldown timestamp.

### Recovery schedule

The automation checks after an offline transition, when a configured relay changes to OFF, after Home Assistant starts (3-minute grace period), and every 30 minutes if a persistent cooldown helper exists. A recovery run stops when all configured lights and relays are healthy.

An aggregated state trigger may not fire again when another lamp becomes unavailable while one remains offline. The periodic retry with a cooldown helper provides a later retry; you can also run the automation manually if troubleshooting.

## 🔄 03 | Optional Govee2MQTT restart

Enable app restart and enter the exact Govee2MQTT add-on/app **slug** shown in Home Assistant's app details. The automation calls \`hassio.app_restart\`, which is available only where the Supervisor is installed.

This works for **lights with no power relay** too. The bridge is restarted **at most once per recovery attempt**, irrespective of the number of lamps. It does not restart Home Assistant, the host or the MQTT broker.

## 📡 04 | Retry protection

Create one Home Assistant \`input_datetime\` helper with both **date and time**, for example \`input_datetime.govee_last_recovery\`. Initialize it to a timestamp older than the default **60-minute cooldown** before the first attempt.

The helper prevents repeated disruptive recovery attempts even after Home Assistant restarts. A valid, recently saved timestamp is required for a deliberate power cycle or bridge restart. Without it, the blueprint can still restore relay power, detect failures and notify, but **cannot** power-cycle, restart the bridge or run periodic retries.

For device-specific Ping information, use Home Assistant's [Ping (ICMP) integration](https://www.home-assistant.io/integrations/ping). Reserve stable IP addresses. A Ping failure can also be caused by firewalls or devices that ignore ICMP and is not definitive proof that the lamp is disconnected.

## 🔔 05 | Notifications

A failed attempt creates a Home Assistant persistent notification with the initial and final state of every selected lamp, relay and Ping entity. A successful recovery dismisses the previous warning. If a \`notify\` entity is provided, the notification may also be sent to a phone or other recipient.

Because device, WLAN, MQTT and bridge failures can look alike, diagnostic snapshots identify **symptoms**, not guaranteed root causes. Available (\`on\`/\`off\`) lights that silently ignore commands require an independent health check; availability alone cannot identify that fault.

## Improve reliability at the source

### ESPHome relay behavior (if you use a power relay)

For **ESP8266 Sonoff** boards, consider \`early_pin_init: false\` to reduce boot-time relay glitches. A GPIO relay with \`restore_mode: ALWAYS_ON\` restores ON after boot. Neither guarantees physically uninterrupted power throughout an OTA update or restart.

\`\`\`yaml
esp8266:
  board: esp01_1m           # Example only; use the correct model/board
  early_pin_init: false

switch:
  - platform: gpio
    id: ceiling_power
    name: "Ceiling lamp power"
    pin: GPIO12             # EXAMPLE: check real pin and inversion
    restore_mode: ALWAYS_ON
\`\`\`

Prefer uninterrupted supply and a detached wall switch where possible. Changes to mains wiring must be performed in accordance with local electrical safety rules by qualified personnel.

Resources: [ESPHome ESP8266](https://esphome.io/components/esp8266/) · [ESPHome switches](https://esphome.io/components/switch/).

### Govee LAN and MQTT reliability

Govee2MQTT can use Govee's local LAN protocol **on models that support it**. Enable LAN control in the Govee app, reserve device IP addresses, allow the required UDP ports, and provide explicit IPs to Govee2MQTT's \`scan\` option when multicast discovery fails. Check its logs when the lamp remains unavailable even though power and Wi-Fi are present.

See [Govee2MQTT](https://github.com/wez/govee2mqtt) and its [LAN documentation](https://github.com/wez/govee2mqtt/blob/main/docs/LAN.md).

## Safety and testing

Begin with relay restoration alone. Only enable power cycling after validating each matching relay and Ping sensor; never enable deliberate cuts for safety-critical lights or during ESPHome firmware flashing. Restarting the bridge may briefly affect **all** lamps controlled by that Govee2MQTT instance.

The repository includes [static regression tests](../../../tests/test_govee_recovery.py). Real-world Home Assistant and hardware testing is still required; this automation cannot prove which network component originally failed.
