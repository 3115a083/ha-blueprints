# Changelog

## 2026-11-11 | Initial blueprint

- Added synchronization of Android TV Remote media-player power state with a selected light or switch.
- Added freeform visual Home Assistant conditions with AND/OR groups and optional state-triggered rechecks, plus one-minute reconciliation.
- Turns Ambilight off if conditions stop passing while TV remains on; turns it back on when conditions pass again.
- Added optional maximum-on duration with input_boolean lockout against stale ON states.
- Added direct-off and Companion mobile notification with actionable Turn off modes.
- Added fail-safe behavior for missing helper and missing mobile action, and tests for state/condition/timeout/recovery scenarios.
