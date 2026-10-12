# 🔧 Govee Light Recovery | ESPHome Relay & MQTT

A Home Assistant automation blueprint for **up to two Govee lights** controlled through **Govee2MQTT** and powered by **ESPHome Sonoff relays**. It checks unavailable lamp entities, restores accidentally switched-off relays, optionally tries cautious recovery steps, and notifies the user if the problem persists.

[Import the blueprint into Home Assistant](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2F3115a083%2Fha-blueprints%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fgovee_recovery%2Fgovee_recovery.yaml) · [Blueprint YAML](govee_recovery.yaml) · [Blueprint catalog](../../../README.md)

**Requirements:** Home Assistant 2024.10 or newer, Govee lights already exposed as Home Assistant light entities, and their normally powered ESPHome relay switches. Optional app restarting needs Home Assistant OS or Supervised, administrative access, and a configured Govee2MQTT app slug.

## Improve reliability before enabling automatic recovery

### ESPHome relays and updates

If your Sonoff uses an **ESP8266**, first review its ESPHome firmware configuration. ESPHome documents that early_pin_init set to false can prevent relay toggling during firmware updates/restarts. restore_mode ALWAYS_ON initializes the switch logically ON, but **does not guarantee uninterrupted power during boot, flashing, or actual power loss**.

Example fragment only. Verify your hardware board, GPIO, electrical logic/inversion and existing ESPHome configuration before using it:

    esp8266:
      board: esp01_1m          # Example only; replace with actual board
      early_pin_init: false

    switch:
      - platform: gpio
        id: ceiling_light_power
        name: "Ceiling light power"
        pin: GPIO12            # EXAMPLE ONLY, not a universal relay pin
        restore_mode: ALWAYS_ON

The most reliable setup for a networked smart ceiling lamp is generally a permanent power supply and a detached wall-switch input that sends control events without disconnecting the lamp. Any mains wiring change must comply with local electrical regulations and be performed by a qualified electrician.

ESPHome documentation: [ESP8266 early_pin_init](https://esphome.io/components/esp8266/) and [switch restore_mode](https://esphome.io/components/switch/).

### Local Govee control

**Govee2MQTT already supports LAN-first control** when the particular Govee model and requested functionality support the LAN API. Some Govee models or features depend instead on cloud/IoT/BLE transports. Check the exact model before assuming an entirely offline setup is possible.

For supported models, enable LAN Control separately in the Govee Home app, reserve a stable IP address for each lamp, and add those addresses to the Govee2MQTT **scan** configuration if multicast discovery is unreliable. The **broadcast_all** option may also help some setups. The LAN protocol uses UDP 4001 and 4003 on the lamp, UDP 4002 on the bridge host, and multicast group 239.255.255.250 for discovery. Ensure the Wi-Fi access point, VLANs and firewall do not block these flows.

See [Govee2MQTT configuration](https://github.com/wez/govee2mqtt/blob/main/docs/CONFIG.md) and [LAN requirements](https://github.com/wez/govee2mqtt/blob/main/docs/LAN.md).

## Configure the recovery blueprint

### 💡 01 | Lights and ESPHome relays

Choose **Govee light 1** and the Sonoff/ESPHome **relay 1** feeding it. Optionally select **light 2** and **relay 2** as a complete second pair. Do not leave only one of the two fields configured. Both relay entities are assumed to be normally ON.

Light state **off** means that the lamp is connected but not illuminated; it is not treated as an error. Only **unavailable** or **unknown** indicates a detected connectivity problem. This automation does not change Govee on/off, brightness or colors.

### 🛠️ 02 | Recovery steps

The blueprint waits a configurable time, default two minutes, after a lamp becomes unavailable. A Sonoff relay that stays OFF for one minute also triggers recovery. After Home Assistant starts, it waits three minutes before checking to avoid startup false alarms.

| Step | Default | Behavior |
| --- | --- | --- |
| Restore switched-off power relay | **ON** | Turn the affected relay ON, then wait for reconnection. This step never switches power OFF. |
| Deliberate single-lamp power cycle | **OFF** | Only if exactly one lamp was unavailable, its relay is known ON, its dedicated Ping sensor is OFF, and a persistent cooldown timestamp was successfully updated. Turns that relay OFF briefly, then ON once. |
| Govee2MQTT app restart | **OFF** | If a light is still unavailable while its relay is ON, restart the selected Govee2MQTT app once and allow reconnection time. |
| Report failure | **ON** | Write a persistent Home Assistant notification with observed lamp, relay and Ping states. |

**Safety:** Never enable an automatic mains power cycle for safety-critical lighting, during ESPHome OTA/firmware updates, or if a brief power loss is unsafe. When both lamps disappear together, automated relay power cycling is suppressed to avoid disrupting a likely shared MQTT/bridge/network outage.

### 🔄 03 | Optional Govee2MQTT app restart

Enable app restart only after verifying the slug in **Settings → Apps → Govee2MQTT**. Enter the slug, not the title. The blueprint uses the official Supervisor action:

    action: hassio.app_restart
    data:
      app: YOUR_GOVEE2MQTT_APP_SLUG

This restarts Govee2MQTT, not the MQTT broker, Home Assistant, or the host. It is available only on Home Assistant OS or Supervised and requires an appropriate administrator account.

### 📡 04 | Reachability and retry limits

Optional **Ping (ICMP)** binary sensors can test each lamp's reserved IP address. Configure the [Ping integration](https://www.home-assistant.io/integrations/ping), then select the sensors here. **ON** indicates a successful Ping; **OFF** may also occur if a device or firewall simply blocks ICMP, so confirm real behavior before enabling power cycling.

A single optional Home Assistant **input_datetime with both date and time** records the last recovery attempt for both lamps. Example name: input_datetime.govee_last_recovery. Initialize it to a past time older than your chosen cooldown. The default cooldown is **60 minutes**.

The helper is required for automatic power cycling and periodic retries. With no helper, the blueprint can react to new outages and restore switched-off relays, but periodic retries and deliberate power cycling are disabled. Even during cooldown, a relay found OFF can be safely restored ON; disruptive operations are still blocked.

### 🔔 05 | Notifications

A failed recovery creates a persistent Home Assistant notification with a diagnostic snapshot of both lamps, power relays and Ping sensors. A new successful repair clears the previous failure notification. Optionally choose an available **notify entity** for an additional push/message destination. Success notifications are disabled by default.

## Recovery sequence

    Lamp unavailable for 2 minutes OR power relay OFF for 1 minute
                            |
                 Check setup and cooldown
                            |
                  Relay OFF? Turn it ON
                            |
               Wait for light reconnection
                            |
            One lamp still unavailable + Ping OFF?
                            |
              Optional single power cycle
                            |
                  Lamp still unavailable?
                            |
              Optional one Govee2MQTT restart
                            |
                Re-check current statuses
                     /              \
                 Recovered         Failed
                    |                |
             Clear warning     Notify with details

The blueprint also checks at Home Assistant startup; periodic checks every 30 minutes are available only when the persistent cooldown helper has been selected. The actual minimum time between full attempts is the configured cooldown.

## Limits and troubleshooting

A Home Assistant light entity alone cannot conclusively differentiate among power loss, Wi-Fi failure, LAN discovery, MQTT connectivity, bridge state and Govee cloud fallback. **The notification is a diagnostic clue, not a proven root-cause analysis.** Inspect Govee2MQTT logs and router device status to investigate the cause.

If an entity remains available and shows on/off but commands no longer work, a simple availability-based automation will not detect the silent failure. Device-specific acknowledgements or a reliable independent health sensor would be necessary.

Before enabling power cycles or app restarts, test each stage with controlled interruptions. Verify the correct relay is paired with its light. The blueprint includes static regression tests, but has not been tested on your exact Sonoff and Govee models or on a live Home Assistant instance.
