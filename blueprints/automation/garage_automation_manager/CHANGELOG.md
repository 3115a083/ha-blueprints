## 2026-11-12 | GPS direction fluctuation tolerance

- Ignore transient Proximity `away_from` states while tracking an approaching car.
- Require a configurable continuous `away_from` period (default 3 minutes) before canceling the trip, using a native state trigger with `for`.
- Preserve the trip across short `towards` / `away_from` oscillations and `stationary` stops; still cancel on observed vehicle disconnect, unknown direction, stale trip, or arrival.
- Added regression tests for transient direction changes and confirmed sustained departure. Documented the native Proximity tolerance-distance setting.

## 2026-11-12 | Calendar permissions, notification targets, Proximity arrival

- Added optional calendar-only person-at-home restriction and visual AND/OR conditions without changing other opening routes.
- Added selectable notify entities for plain closing warnings, alongside existing Companion mobile actions.
- Matched the actual car against connected Bluetooth Connection sensor attributes; supports exact MAC, name, or full entry, plus Android Auto binary sensor.
- Replaced speculative GPS two-point heading with native Proximity `towards` and `arrived` and its per-device distance sensor.
- Added a dedicated input_text trip helper to remember observed car connection time and distance from Home; configurable minimum net approach distance, minimum observed connection duration, GPS accuracy, and optional near-home distance cap.
- Reset trips on disconnect, changed direction, arrival and HA startup. Prevented opening from mere Bluetooth connection or stale/noisy GPS.
- Added simulated Home Assistant tests and updated setup documentation.

## 2026-11-12 | Optional Home Assistant obstruction sensor

- Made the HA obstruction/clearance binary sensor optional, with an empty default.
- Automatic closing, house-door closing, custom closing and Close now work without this sensor. No additional software opt-in is required.
- When an HA sensor is selected, its current CLEAR state is mandatory for every close command; blocked, unknown and unavailable prevent closing.
- Preserved cover OPEN-state checks, user-defined close conditions and persisted timed-close deadlines.
- Documented the requirement for independently functioning garage motor obstruction detection and automatic reversal. Added HA integration regression coverage for sensorless and sensor-backed closing.

# Changelog

## 2026-11-12 | Initial garage automation manager

- Added optional calendar opening with selectable offset, title substring filter (case insensitive), and default exclusion of all-day events.
- Added optional weekly Schedule helper, deliberate custom opening and closing requests, and proximity-based approach gated by a vehicle connection sensor.
- Added freely combined visual open and close conditions.
- Added time-based automatic closing with a persistent input_datetime deadline, bounded overdue window and no unattended restart replay.
- Added independent clearance-sensor enforcement for every closing route, including mobile Close now.
- Added Companion mobile warning with Extend, Close now and Cancel countdown actions; automatic closing does not require confirmation.
- Added post-command optional action hooks, static tests, Home Assistant script/schema tests and a setup/safety guide.
