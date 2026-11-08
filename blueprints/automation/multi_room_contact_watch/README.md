# Multi-Room Contact Watch | Open Doors, Sensor Health & Battery

One **Home Assistant 2026.11.0** automation monitors any number of rooms with a repeatable visual form. It warns about doors and windows left open **and** about sensors that become unavailable, report explicit Zigbee connectivity failures, show a low battery percentage or have an overdue last-seen timestamp.

[Import blueprint](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2F3115a083%2Fha-blueprints%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fmulti_room_contact_watch%2Fmulti_room_contact_watch.yaml) | [Blueprint YAML](multi_room_contact_watch.yaml)

**No additional helpers or duplicate sensor selection are required.** Each contact is configured only within its room. The automation checks configured rooms once per minute, rather than listening to every Home Assistant state change or creating long-running per-contact timers.

## Set up in five steps

1. Import the blueprint and create ONE automation.
2. Under **01 | Rooms and contacts**, click **Add** for each room (Kitchen, Bedroom, Hallway, etc.). Select the physical door/window binary sensors for THIS room.
3. Choose the initial time before warning, per room. The default is **10 minutes**. ON normally means open; an inverted contact can use OFF.
4. Under **02 | Where to send notifications**, select one or more notify entities, such as your phone, or keep **Home Assistant persistent notifications** enabled.
5. Save and test with an open window. For additional Zigbee diagnostics, configure the optional health entities in each room.

### Example configuration

| Room | Contact sensors | First alert | Health entities |
| --- | --- | --- | --- |
| Kitchen | Kitchen window, patio door | 10 min | Battery percentage, Zigbee availability |
| Hallway | Front door | 3 min | Front-door battery, last-seen timestamp |
| Bedroom | Bedroom window | 20 min | Optional |

Each room owns its own sensors. There is no central list that you must repeat in the room form.

## Warnings and intervals

**Left-open contact:** The room name and affected sensor names appear in the notification. When multiple contacts become due in one minute, they produce one combined alert per room. Optional reminders repeat every **30 minutes** (global default). Setting the repeat interval to **0** disables reminders but not the initial alert.

**Unavailable contact:** A contact reporting **unknown or unavailable** for **15 minutes** (configurable) triggers a separate sensor-health warning. This handles lost integration connectivity without treating an unavailable door as closed.

**Explicit Zigbee availability:** Optionally select binary sensors or Input Booleans that report **ON = online, OFF = offline**. Offline/unknown/unavailable states trigger warnings after the same grace time. Be sure your selected availability entities use these exact semantics.

**Low battery:** Optionally select battery percentage sensors in each room. A numeric reading at or below **20%** (configurable) is included in health alerts. Previously low readings are checked on startup/reload; periodic reminders follow the daily schedule and can be delayed when the automation is first installed.

**Last seen:** Optionally select entities whose state contains an ISO date/time or a supported Unix timestamp. Warn if the reported last-seen value is older than **48 hours** (configurable). Choose a threshold appropriate for the Zigbee network and the device's reporting cadence. Invalid timestamps are called out separately at startup/reload.

### Critical Zigbee detection limit

A sleeping contact sensor can silently stop sending Zigbee messages while Home Assistant continues displaying its last known **closed** state. **The contact's state alone cannot prove it is still connected.** To identify this failure, use real availability or last-seen data from your Zigbee integration. Do not use last_changed on an ordinary contact as a reliable heartbeat; a healthy closed window may not change state for months.

A health warning indicates a reporting or data problem, **not a confirmed empty battery**. Check the battery, coordinator, mesh routers and integration.

## Notification destinations

The simplest option is selecting one or more native **notify entities**. This uses the modern Home Assistant **notify.send_message** action. Home Assistant persistent notifications are enabled by default and work even without a phone recipient.

For advanced Companion app features, optionally enter legacy services such as **notify.mobile_app_my_phone**, separated by commas. Only service names matching notify.mobile_app_* are accepted, avoiding arbitrary service execution. They receive **tagged alerts**, a configurable tap URL and **clear_notification** when the corresponding condition has recovered. Generic notify entities cannot remove notifications from phone history by tag, so use the legacy services if that matters.

Do not choose the same phone using both its notify entity and its legacy mobile service, otherwise you may receive duplicate push messages.

Separate stable tags identify the **open** and **health** alert for each room. When all room contacts are reliably closed, the open persistent/mobile alert is cleared. The health alert is cleared independently when all watched contact states, connectivity, battery and last-seen entities are healthy. Cleanup generally occurs within one minute of recovery.

Optional custom actions can run after an open warning or after a health warning, with room-related template variables available. Disabled rooms produce no alerts or cleanup commands.

## Performance and reliability

The blueprint uses ONE **one-minute time pattern trigger** plus Home Assistant start/reload triggers. It performs no per-second polling, no global state_changed event listening and no delay/wait task per sensor. Alert timing and clear operations may lag by up to **59 seconds**. The automation runs in bounded queued mode, with no retry loops.

The first alert and follow-ups use each sensor's last-changed timestamp to avoid extra state helpers. A Home Assistant restart may reset these timestamps, delaying a notification until the configured interval starts again. Persistent alerts may survive a restart; startup reconciliation cleans up resolved conditions.

For Zigbee and other battery-powered sensors, prefer a conservative offline delay (default 15 minutes) and last-seen deadline. Some platforms do not expose a trustworthy availability or last-seen value. The blueprint cannot turn a stale ordinary state into a verified online status.

## Acceptance checklist

1. Leave the kitchen window open past its configured threshold. Confirm one warning and then a reminder after the selected repeat interval.
2. Close the last open contact in that room. Verify that persistent or tagged Companion app warnings clear.
3. Test an unavailable contact and a separate explicit offline availability entity. Confirm a warning after the chosen grace period.
4. Recover the sensor and confirm that its health warning clears without masking other active alerts.
5. Test a low numeric battery percentage and an overdue last-seen date.
6. Check multiple rooms simultaneously, automation reloads, Home Assistant restarts and missing entity states.
7. Inspect Home Assistant automation traces if a notification is missing or late.

Software tests and the Home Assistant 2026.11.0 schema check do not substitute for physical Zigbee troubleshooting.

## References and attribution

The independently implemented design draws on:

- [Neekster: Notification if Door or Window is left open](https://community.home-assistant.io/t/notification-if-door-or-window-is-left-open/402851)
- [Raukze: Contact Sensor Left Open Notification](https://gist.github.com/Raukze/27fe0c6bf6d91b8ae2ab5e11880509ba)

Those examples inspired left-open alerts, reminders, customization and Companion app behavior. Multi-room grouping and sensor-health monitoring are new.

## Canonical import URL

```text
https://github.com/3115a083/ha-blueprints/blob/main/blueprints/automation/multi_room_contact_watch/multi_room_contact_watch.yaml
```

To find updated releases using the optional Blueprints Updater integration, execute the blueprints_updater.reload action after importing.
