# Multi-Room Door & Window Watchdog

One Home Assistant automation monitors any number of independent rooms, with as many individual door/window contact sensors per room as you need. It sends per-sensor notifications for contacts left open, sensors that report unknown/unavailable, and optionally devices whose last_seen attribute stopped updating.

- [Blueprint YAML](multi_room_contact_watchdog.yaml)
- [Import into Home Assistant](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2F3115a083%2Fha-blueprints%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fmulti_room_contact_watchdog%2Fmulti_room_contact_watchdog.yaml)
- **Minimum version: Home Assistant Core 2026.11.0**.
- Inspired by [Neekster's contact-left-open blueprint](https://community.home-assistant.io/t/notification-if-door-or-window-is-left-open/402851) and [Raukze's contact notification blueprint](https://gist.github.com/Raukze/27fe0c6bf6d91b8ae2ab5e11880509ba). This is a fresh, event-driven multi-room implementation, not a verbatim copy.

## Quick setup

1. Under **01 | Sensor monitoring**, select **every individual contact sensor** that should be watched.
2. Under **02 | Rooms and contacts**, click **Add** for each room. Give it a name and select the contact sensors belonging to it. **Use the same entities as in step 1.** Defaults: ON means open, open alert after 10 minutes, unavailable alert after 20 minutes. These defaults can be overridden individually per room.
3. Under **03 | Notifications**, choose your notification recipients using the **notify entity picker**. Persistent notifications remain enabled by default. Enter optional reminder offsets (such as `5,15`). Under **05 | Advanced options**, edit the prefilled title/message templates and configure separate visual **Actions AFTER an initial warning** and **Actions AFTER each reminder**. For older Companion apps, use the optional legacy `notify.mobile_app_*` action field under Advanced options.
4. Under **04 | When to send warnings**, optionally add **separate conditions** for open contacts and for unavailable/silent sensors. If left empty, each warning type operates normally.

Example layout:

| Room | Contacts | Open threshold | Offline threshold |
| --- | --- | --- | --- |
| Bathroom | Bathroom window, bathroom door | 15 min | 20 min |
| Kitchen | Kitchen window | Shared 10 min | 20 min |
| Living room | Patio door, two windows | 5 min | 30 min |

Every notification identifies **the exact contacts and rooms**. Multiple overdue contacts of the same alert type appear together. When a new contact becomes due, the bundle is updated with all unresolved contacts of that type.

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

Open contacts share one stable notification ID/tag per automation, as do offline and silent contacts. When a second sensor of the same alert type becomes due, its alert **updates the same bundled persistent notification** and, for legacy Companion-app notification actions, reuses the same mobile tag. The most recent message contains the triggering contact plus all other currently overdue contacts of that type. Duplicate assignments of the same entity in multiple rooms are shown once. Bundling is **per alert type** to preserve independent open/health notification conditions.

**Important provider limitation:** Modern `notify.send_message` entity recipients cannot universally replace or dismiss an earlier push. Each outgoing update still contains the current combined list, but the notification provider may display multiple separate notifications. For replaceable mobile notifications, use a legacy `notify.mobile_app_*` action, configured only once, and verify tag support on the actual phone.

On recovery, the persistent bundle is updated to show remaining overdue contacts. Tagged legacy mobile notifications are updated when others remain or cleared when the last contact of that type recovers. Recovery updates do not send a separate `notify.send_message` push unless explicit recovery notifications are enabled. Provider errors do not block later custom actions.

**Automatic clear** is enabled by default. It dismisses the matching persistent Home Assistant notification and sends `clear_notification` to configured `notify.mobile_app_*` services. Other notification providers are not sent the clear command because they may treat it as a literal message. Optionally enable a **recovery notification** so the phone explicitly says the contact is closed or online again.

**Reminders** are disabled by default. Enter **Additional reminders after first alert (minutes)** as comma-separated offsets, for example `5,15`, to send one warning at the initial deadline, then additional warnings 5 and 15 minutes after that deadline. For a contact configured with an initial 10-minute delay, alerts are due after 10, 15 and 25 minutes of being open. To alert at 5 and 15 minutes of being open, set the initial open delay to 5 and the reminder offset to `10`. Each contact and alert type is scheduled independently.

Only whole positive minutes between 1 and 1440 are accepted; at most the first 12 comma-separated entries are considered. Invalid entries are ignored, duplicates have no extra effect, and an empty field disables this schedule. If no valid specific offsets are supplied, the pre-existing **Legacy periodic reminder interval** (under Advanced options) still works, e.g. `30` for periodic alerts. Specific offsets take precedence over the periodic interval, so they will not combine into surprise extra notifications.

The first alert is sent once per unresolved incident in normal operation. Each reminder is evaluated in its one-minute due window; skipped windows are not replayed later. HA startup/reload checks overdue incidents to avoid silent missed alerts, but may generate a replacement notification during a restart. Mobile tags reduce visual duplication but do not guarantee suppression of vibration or sound.

### Customize notification text and actions

Both **Notification title** and **Notification message** are editable **Jinja template** fields with working English defaults for open contacts, unavailable/unknown contacts and silent last_seen warnings. Copy these snippets into either field as needed:

| Snippet | Meaning |
| --- | --- |
| `{{ contact_label }}` | Friendly name of the sensor that triggered the alert |
| `{{ contact_id }}` | Entity ID, for example `binary_sensor.window` |
| `{{ room_name }}` | Room name from the room entry |
| `{{ alert_type }}` | `open`, `offline` or `silent` |
| `{{ contact_state }}` | Current Home Assistant sensor state |
| `{{ elapsed_minutes }}` | Minutes elapsed since the triggering state or last_seen timestamp |
| `{{ issue_state }}` | Contact state configured as open for that room |
| `{{ alert_tag }}` | Stable notification tag for the sensor and alert type |

For example, replace the message with `Attention: {{ contact_label }} in {{ room_name }}. Type: {{ alert_type }}. Duration: {{ elapsed_minutes }} min.` This applies to persistent notifications, modern notify entities and legacy mobile notifications alike. Existing automations that omit the new inputs retain the previous default title/message wording.

Under **05 | Advanced options**, the editable title/message templates and the two visual action editors are grouped together. **Actions AFTER an initial warning** retains the existing `on_alert_actions` input key, so saved actions continue working for initial warnings. **Actions AFTER each reminder** uses the new `on_reminder_actions` input key, defaulting to no actions. Scheduled reminders do not execute the initial-warning actions. Both execute only after all notification delivery attempts (provider failures are tolerated), and neither runs if the relevant conditions suppress the warning. Startup replays count as initial warnings. Recovery actions remain a separate control.

### Independent notification conditions

The two condition fields in **04 | When to send warnings** use Home Assistant's **visual condition editor**. You can select real sensors, people and numeric thresholds without writing YAML.

| Rule | Example | Affects |
| --- | --- | --- |
| **Open door/window warnings: send only when** | Numeric state, outdoor temperature sensor, **Below 17** | Only **open** alerts |
| **Unavailable / silent sensor warnings: send only when** | State, person entity, **not_home** | Only **offline** and **silent last_seen** alerts |

Use either rule, both rules or neither. Conditions inside each list are **AND** by default. For example, adding outdoor temperature below 17 and a person set to `not_home` means that **both** must be true. Use an **OR** group in the visual editor if either condition should be enough.

Conditions are checked when a scheduled alert is due. They **do not stop sensor monitoring** and they **never block automatic clearing or recovery**. An unavailable sensor is still detected while an open-contact-only condition is false.

**Important one-shot behavior:** When a condition is false at the initial warning deadline and reminders are disabled (the default), an alert may be missed even if the condition later becomes true. Configure specific reminder offsets (for example `5,15`) or the legacy periodic interval to reevaluate notification eligibility at the next due time. This does not create an immediate threshold-crossing event: it checks again on the reminder schedule. The existing optional **Legacy shared conditions for BOTH warning types** is still respected for migrated automations, in addition to these two new lists.

Custom initial-warning, reminder and recovery actions are in Advanced options. Both use `room_name`, `contact_id`, `contact_label`, `alert_type` and the corresponding title/message/tag variables.

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

## Notification recipients and legacy mobile options

- **Recommended:** Use **Notification recipients (select one or more)** to choose available `notify` entities, which the blueprint addresses with `notify.send_message`. Home Assistant supports multiple notify entities in a single call.
- **Legacy mobile support:** Existing `notify_services` settings are not removed. They now appear under **05 | Advanced options** as optional comma-separated `notify.*` service names for integrations that still expose service actions but no notify entity.
- **Avoid duplicates:** Do not configure the same phone using both the picker and its legacy mobile action.
- **Tags and clearing:** A `notify` entity receives standard message/title data, but this generic action has no tag-based removal mechanism. Tagged mobile notifications and `clear_notification` remain supported only via the legacy `notify.mobile_app_*` service when configured. Home Assistant persistent notifications can still clear on recovery.
- **Mobile-only settings:** The click URL, Android icon/color and iOS interruption level apply to legacy Companion app actions. A generic notify entity may ignore or lack those features.
- Persistent Home Assistant notifications work even without a phone configured. Ensure at least one notification destination is enabled. Shared tags are unique per automation entity ID and alert type.
- Initial-warning custom actions, reminder custom actions and recovery custom actions run at their respective events, not on every sensor update. Multiple sensors due within the same minute can each cause an update to the same notification tag; some phones may vibrate more than once. Review custom actions before allowing them to operate devices.

## Performance, timing and restart behavior

The blueprint uses:
- One **entity-filtered state trigger** for all listed contacts, to handle resolution immediately.
- One **time-pattern trigger per minute** for open/offline/silence deadlines and optional reminders, irrespective of the number of rooms.
- A startup/reload check so already-overdue sensors can be surfaced after downtime.
- **Independent condition checks** only when an alert becomes due, not a new global event listener for temperature or presence.
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
- Configure reminder offsets `5,15` and verify the initial notification and both later reminders for the same contact; confirm no further periodic alerts after the last offset. Test old periodic interval settings separately.
- Edit the title/message templates under Advanced options and confirm sensor/room substitution for open, offline and silent warnings. Add separate warning and reminder custom actions and verify only the correct one runs after notification attempts.
- Trigger two different windows in sequence and verify the second notification updates the shared tag with BOTH contacts, and the first closure updates the persistent bundle while the last closure removes it.
- Test same-minute warnings, provider-specific tag replacement, automatic clearing, and separate conditions for open/offline alerts.
- Verify the existing `on_alert_actions` key still works after moving it to Advanced options, while `on_reminder_actions` is separate.
- Test Home Assistant restart and automation reload with an already-open contact.
- Validate push and tag deletion on each configured mobile app; notification service implementations differ.

Static and real Home Assistant **action/schema simulation tests** are provided in the repository. Hardware-based Zigbee disconnect and mobile app delivery still require testing on your own setup.

## Attribution and upgrades

Inspirational sources, maintained separately by their authors:
- [Notification if Door or Window is left open](https://community.home-assistant.io/t/notification-if-door-or-window-is-left-open/402851) by Neekster
- [Contact Sensor Left Open Notification](https://gist.github.com/Raukze/27fe0c6bf6d91b8ae2ab5e11880509ba) by Raukze

Canonical import URL:

```text
https://github.com/3115a083/ha-blueprints/blob/main/blueprints/automation/multi_room_contact_watchdog/multi_room_contact_watchdog.yaml
```

After repository updates, update/reimport the blueprint and reload automations on Home Assistant. An upstream GitHub merge alone does not change the local installed blueprint. Blueprints Updater users can refresh discovery through the `blueprints_updater.reload` action.
