# Changelog

## 2026-11-07 | Optional darkness activation for already-occupied zones

- Added per-zone opt-in to activate at sunset, at a zone-specific lux threshold crossing, or on either event. Existing motion-only behavior remains the default.
- Added a dedicated, entity-filtered list of monitored lux sensors, with a warning if a zone's configured lux trigger sensor is missing from the list.
- Added optional presence sensors inside each zone. Sustained own-zone presence can activate lighting when the room becomes dark and prevents premature automatic switch-off. Linked cross-room occupancy remains a hold-only signal.
- Reused existing time, sun, lux, blocker, availability and manual-ownership guards for every activation event.
- Added tests for threshold crossings, unrelated sensors, unknown values, stationary occupancy, cross-room isolation and Home Assistant execution.

## 2026-11-05 | Initial release

- Added repeatable, unlimited multi-zone motion lighting under one automation.
- Added separate activation and switch-off targets for lights, switches, groups, scenes, and scripts.
- Preserved optional illuminance, sun, local-time and activation-blocker controls from the source blueprint's feature intent.
- Added cross-room occupancy holds and configurable grace periods after linked presence clears.
- Added independent, restart-reconciled off deadlines without per-zone delay scripts or whole-bus state-change listeners.
- Added optional manual-light ownership helpers and safeguards against repeated service calls.
- Added YAML, Jinja, boundary-condition and simulated Home Assistant execution tests.
- Included original community blueprint attribution and a usage guide.

### Known limitations

- Motion entities must be selected in both the master monitoring list and each zone's form row for instant triggering.
- The OFF action can occur up to 15 seconds after the requested deadline.
- A true room occupancy sensor is preferable to a short-lived PIR for cross-room holding.
- Physical lights and the user's own Home Assistant instance have not been tested by repository CI.
