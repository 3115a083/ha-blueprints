# Release notes

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
