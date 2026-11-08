# Changelog

## 2026-11-08 | Initial version

- Introduced one automation with unlimited repeatable room entries and per-room contact sensors and open-alert times.
- Added repeatable left-open reminders and a global repeat-off control.
- Added separate Zigbee/contact health warnings for unknown or unavailable states, explicit connectivity binary sensors, low battery percentages and stale last-seen timestamp entities.
- Supported native notify entities, persistent Home Assistant notifications, optional validated legacy Companion app actions with stable tags and recovery clearing.
- Added optional custom actions for open and health warnings.
- Implemented low-overhead once-per-minute scheduling and finite queued handling without per-sensor delay scripts or any global state-change listener.
- Added sensor safety, versioned integration tests and source attribution.
- Pinned integration validation against Home Assistant 2026.11.0.

### Known limitations

- Contact state alone cannot detect a silently disconnected Zigbee device whose old closed state remains visible. Availability or last-seen reporting from the integration is required.
- Notifications and recovery clearing can lag by up to one minute.
- A restart may reset sensor last_changed timestamps and postpone the first warning.
- Tags can clear Companion mobile notifications only when a legacy mobile_app service is configured. Generic notify entities do not expose a compatible clear-by-tag action.
- Real Zigbee device and mobile push delivery tests are not part of repository CI.
