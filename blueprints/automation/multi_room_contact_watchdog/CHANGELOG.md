# Changelog

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
