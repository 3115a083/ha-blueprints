# Release notes

## v0.3.0, fault notifications and manual thermostat hold (2026-10-21)

### Changes

- **Optional persistent fault notifications (default OFF).** Alert about unavailable room window contacts, offline climate entities, and thermostat mode/target commands not confirmed within a configurable 5–60-second timeout (default 15). Reused notification IDs avoid duplicate cards and ongoing device availability reminders are throttled.
- **Thermostat acknowledgement and independent rooms.** Validate Home Assistant's reported HVAC mode and requested target (0.4 °C tolerance) after each command. Service errors no longer cancel other rooms; global after-change actions require a confirmed state. This does not constitute a physical valve acknowledgement.
- **Optional manual hold (default OFF).** One dedicated Input Text helper per single-thermostat room stores the blueprint's last confirmed command and override deadline. A later manual setpoint change from the dial or HA UI holds the new setting for the configured 0–1440-minute duration, then restores currently applicable rules.
- **Safety and compatibility.** Window and summer protection and frost requirements always outrank a manual hold. A settling guard prevents immediate state echoes from being mistaken for user changes. Existing blueprints without manual helpers continue their normal temperature regulation.
- **English UI and docs.** All new controls, messages, setup steps and release notes remain in English.
- **Regression tests** cover manual detection, hold expiry, window/summer/frost precedence, service verification and stable notification IDs.

### Migration

No new helpers are needed for the existing automatic heating behavior. For manual override, create a distinct Input Text helper (at least 100 characters maximum, no forced initial value) per room with **one** thermostat and configure the room helper + global duration. Enable persistent fault notifications separately. Imported Home Assistant blueprints must be updated locally after pulling this change.

## v0.2.1, vacation schedule availability fix (2026-10-21)

- **Vacation mode no longer depends on room schedule availability.** An unknown or unavailable room schedule cannot prevent a valid Vacation setback from sending commands. This fixes one possible cause of unchanged thermostat setpoints during vacation.
- **Window sensor safety unchanged.** Unknown or unavailable room window sensors continue to prevent heating writes for that room until their status is reliable.
- Added regression coverage for vacation precedence, invalid schedules, and window sensor protection.
- Documentation distinguishes thermostat targets from current room temperatures and lists relevant Home Assistant trace variables for diagnosis.

## v0.2.0, apartment occupancy and automatic summer cutoff (2026-10-21)

### Improvements

- **English-only blueprint interface.** The room section is now called **Rooms**. All section headings, field labels and help texts are in English.
- **Window-open delay in seconds.** Each room accepts a 0–7200-second delay. Previously saved `window_delay` minute values remain a compatibility fallback when a new `window_open_seconds` value is not configured.
- **Summer mode.** Optional outdoor-temperature cutoff (default 20 °C), lower resume threshold (default 17 °C), per-thermostat hysteresis using current HVAC mode or frost-only setpoint, and frost-safe OFF fallback. Disabled by default.
- **Whole-apartment presence.** Select multiple global presence or motion binary sensors. Any ON sensor or a sensor whose last OFF transition is inside a configurable hold period (default 120 minutes) keeps the apartment occupied even if all selected people are away. Room schedules continue without individual room-motion heating changes.
- **No direct room-motion setbacks.** The old per-room `motion` setting is ignored; reselect relevant sensors under **General controls / Apartment presence sensors**. Person tracking, guest, party and vacation retain their defined priorities.
- **Regression coverage.** Added hold-time, second/minute migration, hysteresis, UI language and priority tests.

### Migration

Review existing automations before updating. Room `motion` inputs are not transferred automatically. Explicit new seconds settings override legacy minute delays; without the new setting the old minute delay still works. Summer mode requires opt-in and a reliable outdoor sensor. Vacation and frost protections remain active.

### Attribution

**Based on the awesome blueprint by [panhans: Advanced Heating Control](https://community.home-assistant.io/t/advanced-heating-control/469873).** Thank you for the original inspiration and extensive community work.

## v0.1.0, initial multi-zone preview (2026-10-21)

### Highlights

- **One automation for multiple heating zones.** Add as many named rooms as needed using the structured Rooms (`Rooms`) editor. Each room independently configures its own thermostat list, comfort, eco, vacation and frost temperatures, room sensor, schedule, occupancy, window contacts and optional calibration.
- **Separate general controls.** Shared people presence, guest and party modes, safety conditions, optional automation enable, call delay and post-change actions are managed in one global section.
- **Clear whole-home vacation mode.** A required Input Boolean is the single source of truth. Choose a per-room setback temperature, Eco temperatures or explicit safe OFF. Vacation overrides schedules, presence and party mode; open-window protection has higher priority. Unknown vacation state pauses writes.
- **Temperature and command safeguards.** Frost-protection floor, support checks for HVAC modes, min/max temperature bounds, per-room pause, no-action behaviour for unavailable sensors and thermostats, and setpoint-change detection.
- **Safe rollout.** Preview-only defaults to ON. Optional logging and automation traces support commissioning. A bounded once-per-minute check plus an immediate vacation switch trigger balance responsiveness and resource use.
- **Regression coverage.** Tests cover room iteration, template syntax, structured inputs, priority order, freeze protection and canonical update URL.

### Compatibility and limitations

- Requires Home Assistant 2026.10.1 or newer for the room editor.
- This release is a newly implemented, **focused multi-zone adaptation**, not feature parity with Advanced Heating Control V5. Existing automation settings do not migrate automatically.
- Unsupported upstream features include proximity and weather activation, vendor-specific calibration, liming protection, valve-positioning logic and granular adjustment schedules.
- Static/schema validation does not constitute testing with physical thermostat hardware.

### Credits

**Based on the awesome blueprint by [panhans: Advanced Heating Control](https://community.home-assistant.io/t/advanced-heating-control/469873).** Sincere thanks to panhans for the original design and extensive work on the Home Assistant heating community. Original source: [Advanced Heating Control V5](https://github.com/panhans/HomeAssistant/blob/main/blueprints/automation/panhans/advanced_heating_control.yaml).
