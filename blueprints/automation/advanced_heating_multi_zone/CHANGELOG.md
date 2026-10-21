# Release notes

## v0.1.0, initial multi-zone preview (2026-10-21)

### Highlights

- **One automation for multiple heating zones.** Add as many named rooms as needed using the structured Rooms (`Räume`) editor. Each room independently configures its own thermostat list, comfort, eco, vacation and frost temperatures, room sensor, schedule, occupancy, window contacts and optional calibration.
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
