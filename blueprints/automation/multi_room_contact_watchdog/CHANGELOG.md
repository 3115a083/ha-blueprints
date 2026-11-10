# Changelog

## 2026-11-10 | Separate warning/reminder actions and bundled contacts

- Moved editable notification title/message templates and the existing post-warning action editor to Advanced options.
- Added separate visual `on_reminder_actions` for scheduled reminders; preserved `on_alert_actions` for initial alerts and startup replays.
- Bundled overdue contacts of the same alert type using a shared per-automation persistent notification ID and legacy mobile tag. New alerts update the bundle instead of creating unrelated tagged notifications.
- Updated shared persistent/mobile bundles on recovery and cleared the shared tag only after the last overdue contact of that type recovers; preserved legacy per-contact clearing for upgrades.
- Documented the limitation that generic `notify.send_message` providers cannot be guaranteed to replace existing mobile notifications, and added static/integration regression scenarios.

## 2026-11-10 | Custom message templates, post-notification actions and scheduled reminders

- Added editable notification title and message templates with per-contact, per-room and alert-type copyable variables. Kept the existing default wording for unconfigured inputs.
- Moved the existing post-alert custom action selector into Notifications without changing its input key or behavior.
- Added comma-separated reminder offsets (for example `5,15`) measured from the initial alert deadline; supports independent open/offline/silent schedules and ignores invalid values.
- Preserved the existing periodic reminder setting as a fallback when no valid specific offsets are configured. Scheduled offsets take precedence.
- Added static and real Home Assistant regression tests and updated the upgrade documentation.

# Changelog

## 2026-11-08 | Notification picker and independent alert conditions

- Added a multi-select **notify entity picker** using `notify.send_message` for easy recipient setup.
- Added two separate visual condition editors: one for open-contact alerts, one for offline and stale-`last_seen` health alerts.
- Preserved existing legacy `notify_services` and shared `notify_conditions` configuration, along with tagged mobile alert clearing.
- Clarified that conditions gate outgoing alerts only; recovery and existing alert cleanup remain independent.
- Documented the one-shot suppression limitation and the option to enable reminder intervals so conditions are reevaluated.
- Added real Home Assistant 2026.11.0 regression scenarios for the notify picker, condition independence and legacy conditions.


## 2026-11-08 | Initial implementation

- Added a Home Assistant **2026.11.0** multi-room contact watchdog with native repeatable room forms.
- Added per-room contact lists, issue state, open and Zigbee unavailable/unknown thresholds.
- Added optional last_seen attribute silence monitoring for Zigbee integrations that provide a reliable timestamp.
- Added optional comma-separated mobile notify services, companion app notification icon/color/URL and iOS interruption level.
- Added built-in persistent notifications, stable contact/type tags, automatic resolution clearing and optional recovery messages.
- Added independently scheduled optional reminders and extra action/condition inputs.
- Added entity-filtered recovery triggers and one-minute deadline reconciliation without a long per-sensor delay.
- Added Jinja, YAML and real Home Assistant action/script regression tests and documentation.
- Original Neekster and Raukze blueprints are attributed as inspirations; implementation is independent.

### Known limits

- The top-level contact selector and per-room sensor selector must both include each contact for immediate recovery handling.
- The one-minute deadline scan can deliver up to approximately one minute after the configured threshold.
- Neither unavailable/unknown checks nor time since a last state change can prove Zigbee battery failure.
- last_seen silence warnings require a meaningful, parseable last_seen attribute updated by normal device communication.
- Mobile service support and real Zigbee fault detection remain to be verified on physical user devices.
