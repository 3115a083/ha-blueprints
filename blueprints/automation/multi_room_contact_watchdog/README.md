# Multi-Room Door & Window Watchdog

One Home Assistant automation monitors any number of independent rooms, with as many individual door/window contact sensors per room as you need. It sends per-sensor notifications for contacts left open, sensors that report unknown/unavailable, and optionally devices whose last_seen attribute stopped updating.

- [Blueprint YAML](multi_room_contact_watchdog.yaml)
- [Import into Home Assistant](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2F3115a083%2Fha-blueprints%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fmulti_room_contact_watchdog%2Fmulti_room_contact_watchdog.yaml)
- **Minimum version: Home Assistant Core 2026.11.0**.
- Inspired by [Neekster's contact-left-open blueprint](https://community.home-assistant.io/t/notification-if-door-or-window-is-left-open/402851) and [Raukze's contact notification blueprint](https://gist.github.com/Raukze/27fe0c6bf6d91b8ae2ab5e11880509ba). This is a fresh, event-driven multi-room implementation, not a verbatim copy.

## Quick setup (the three steps that matter)

1. Under **01 | Sensor monitoring**, select **every individual contact sensor** that should be watched.
2. Under **02 | Rooms and contacts**, click **Add** for each room. Give it a name and select the contact sensors belonging to it. **Use the same entities as in step 1.** Defaults: ON means open, open alert after 10 minutes, unavailable alert after 20 minutes. These defaults can be overridden individually per room.
3. Under **03 | Notifications**, keep **persistent Home Assistant notifications** enabled for immediate operation without a phone integration. For push notifications, add your existing mobile app service name, e.g. a service under the `notify.mobile_app_` namespace. More than one service can be entered, comma-separated.

Example layout:

| Room | Contacts | Open threshold | Offline threshold |
| --- | --- | --- | --- |
| Bathroom | Bathroom window, bathroom door | 15 min | 20 min |
| Kitchen | Kitchen window | Shared 10 min | 20 min |
| Living room | Patio door, two windows | 5 min | 30 min |

A message identifies **the exact contact and the room**, not just "a window somewhere is open".

### Why select each sensor twice?

Home Assistant's repeated object-form fields are perfect for adding rooms, but the blueprint cannot dynamically turn repeated list entries into entity-filtered state triggers. The top list registers all sensors for **immediate recovery handling**. The room entries assign each sensor its settings. **No wildcard state_changed listener and no per-sensor automation are required.**

Do not select a binary-sensor group instead of the individual contacts. A group may report a valid aggregate state even when one Zigbee member has disconnected, masking the failure.

## Notification behavior

For each sensor, the automation distinguishes these independent alert types:

| Problem | Trigger | Default | Resolution |
| --- | --- | --- | --- |
| **Left open** | Sensor stays ON (or OFF if configured inverted) | 10 min | Sensor leaves that state |
| **Unavailable / unknown** | HA contact state remains unknown/unavailable | 20 min | Contact reports ON or OFF |
| **Silent last_seen** | Valid contact still shows ON/OFF but its last_seen attribute is old | Disabled | last_seen becomes fresh again |

Each item has a distinct, stable notification ID/tag. Multiple rooms and contacts produce independent messages. Persistent notifications are created/updated by ID. Mobile app notifications reuse their tags so repeated alerts can replace prior phone notifications rather than creating a list of unrelated warnings, subject to app behavior.

**Automatic clear** is enabled by default. It dismisses the matching persistent Home Assistant notification and sends `clear_notification` to configured `notify.mobile_app_*` services. Other notification providers are not sent the clear command because they may treat it as a literal message. Optionally enable a **recovery notification** so the phone explicitly says the contact is closed or online again.

**Reminders** are disabled by default. Set **Repeat unresolved alerts every N minutes** to e.g. 30 to receive an alert at the initial deadline and approximately every 30 minutes thereafter. The initial alert is sent once per unresolved incident in normal operation. HA startup/reload also checks overdue incidents to avoid silent missed alerts after downtime, but may generate a replacement notification during a restart. Mobile tags reduce visual duplication but do not guarantee suppression of vibration or sound.

**Advanced extra conditions** can restrict when warnings are delivered; recovery and clearing remain unconditional. If a one-shot warning is suppressed by a condition, it will not automatically be retried until reminders are enabled or HA restarts. Custom alert and recovery actions are available in Advanced options, using `room_name`, `contact_id`, `contact_label`, `alert_type` and the corresponding title/message/tag variables.

## Zigbee failure detection: exact limits

### 1. Unknown or unavailable, enabled by default

When Home Assistant exposes a contact as `unknown` or `unavailable`, the blueprint starts a **separate offline deadline**. It waits 20 minutes by default to avoid false alarms during coordinator startup, networking hiccups or Home Assistant restarts. Each room can override the threshold or disable this alert entirely. The message advises checking the battery and Zigbee connectivity.

**This does not prove the battery is empty.** The contact could be out of range, unpaired, or affected by a coordinator or integration problem.

### 2. Optional silent-device / last_seen check

Some Zigbee integrations leave the last ON/OFF state in Home Assistant even when a battery dies, so the first method never fires. **For compatible sensors only**, set the room field **Optional last_seen silence alert (hours; 0 = OFF)** to e.g. 24. The blueprint reads the `last_seen` attribute of the **contact binary sensor** and warns if its timestamp becomes that old.

Requirements:
- Your contact entity exposes an actual parseable `last_seen` attribute, not a separate entity named `sensor.*_last_seen`. Check **Developer Tools → States → Attributes** for each contact.
- The timestamp represents normal, periodic reporting and should update with real Zigbee communication. If it only updates when the door opens or closes, silence cannot distinguish an idle door from a dead battery. In that case, **leave the feature off**.
- If the attribute is absent or invalid, this check is safely skipped. It cannot infer missing radio packets from an unchanged state.

Device reporting time is **not equivalent to link health** unless your integration documents a heartbeat or suitable reporting behavior. For stronger device-level monitoring when last_seen is unavailable, use an explicit Zigbee availability/watchdog integration or dedicated connectivity entity instead. This blueprint does not read Zigbee mesh traffic, guarantee detection of battery failure, or create device-level keepalive packets.

### 3. Open and offline warnings can coexist

If a contact remains open and subsequently stops updating, an existing open alert may still be visible while a separate offline/silence warning is added. Once its contact state becomes unknown/unavailable, the original open alert is cleared if it had reached its threshold, and the offline timer begins.

## Advanced mobile notification options

- Multiple `notify.*` services may be supplied, separated by commas; only a `notify.<letters_numbers_underscores>` name is accepted for dynamic calls.
- Phone click URL, Android notification icon/color, and iOS interruption level are selectable. Their actual behavior depends on the app/platform. The critical interruption level is intentionally not offered by default.
- Persistent Home Assistant notifications are available even with no phone configured. Use at least one delivery method or your blueprint will be silent.
- Optional custom actions are executed **only for due issues** or qualified recoveries. These actions may themselves send notifications or operate devices, so review them.

## Performance, timing and restart behavior

The blueprint uses:
- One **entity-filtered state trigger** for all listed contacts, to handle resolution immediately.
- One **time-pattern trigger per minute** for open/offline/silence deadlines and optional reminders, irrespective of the number of rooms.
- A startup/reload check so already-overdue sensors can be surfaced after downtime.
- **Queued mode** to serialize notification updates and prevent conflicting clear/create actions across rooms.

It does **not** create delayed tasks per contact, poll Zigbee hardware, process every entity event, or send a notification on every minute tick. The deadline checks read a contact's `last_changed` or `last_seen` timestamp and only send a warning in a **single one-minute window** at the threshold and each configured reminder interval. With a one-minute time pattern, normal delivery may be up to approximately one minute later than the configured threshold.

Because contact state timestamps reset on HA restarts, a still-open or still-unavailable sensor may receive a fresh grace period after startup. This is safer than assuming it was open or disconnected before restart. A parseable `last_seen` attribute may represent an absolute earlier timestamp and therefore survive restarts.

The blueprint relies on contact sensor states, not on event-based battery-telemetry assumptions. It does not install helpers, add scheduled automations per room, or require an MQTT broker.

## Tests / acceptance checklist

- Start with one sensor, then two rooms with multiple contacts and different delays.
- Open a window for a shorter interval than the configured threshold, then for longer; check exact room and contact labels.
- Temporarily set a test contact state to `unavailable`, wait beyond the offline grace, and restore it. Verify only the matching alert is cleared.
- Check `unknown` separately from `unavailable`, and avoid misclassifying sensor startup transitions.
- If last_seen is supported, simulate a stale timestamp and a fresh update. If unsupported, confirm silence detection is inert.
- Turn on reminders for testing and verify their interval and stable tags. Turn reminders back off afterward.
- Test Home Assistant restart and automation reload with an already-open contact.
- Validate push and tag deletion on each configured mobile app; notification service implementations differ.

Static and real Home Assistant **action/schema simulation tests** are provided in the repository. Hardware-based Zigbee disconnect and mobile app delivery still require testing on your own setup.

## Attribution and upgrades

Inspirational sources, maintained separately by their authors:
- [Notification if Door or Window is left open](https://community.home-assistant.io/t/notification-if-door-or-window-is-left-open/402851) by Neekster
- [Contact Sensor Left Open Notification](https://gist.github.com/Raukze/27fe0c6bf6d91b8ae2ab5e11880509ba) by Raukze

Canonical import URL:

~~~text
https://github.com/3115a083/ha-blueprints/blob/main/blueprints/automation/multi_room_contact_watchdog/multi_room_contact_watchdog.yaml
~~~

After repository updates, update/reimport the blueprint and reload automations on Home Assistant. An upstream GitHub merge alone does not change the local installed blueprint. Blueprints Updater users can refresh discovery through the `blueprints_updater.reload` action.
