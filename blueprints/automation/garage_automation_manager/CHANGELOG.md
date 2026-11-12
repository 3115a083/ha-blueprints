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
