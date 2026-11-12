# Garage Automation Manager

A single Home Assistant automation for **one garage cover**, with independently enabled opening sources, optional automatic closing, an editable calendar event-title filter and a safe closing gate.

- [Blueprint YAML](garage_automation_manager.yaml)
- [Import into Home Assistant](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2F3115a083%2Fha-blueprints%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fgarage_automation_manager%2Fgarage_automation_manager.yaml)
- **Minimum Home Assistant Core:** 2026.11.0.
- **Safety:** This automation cannot replace independent safety hardware, obstruction sensing, automatic motor reverse, or physical commissioning. Do not enable unattended closing before verifying the complete physical closing path.

## Setup

1. Select a true **cover** entity that reliably reports open/closed and provides the native Open cover and Close cover services. Do not use an unconfirmed momentary toggle relay for this blueprint.
2. Enable any combination of opening routes in sections 02 through 05. None is enabled by default.
3. Optionally add opening and closing permission conditions in section 01. Use the Home Assistant visual condition editor, including nested AND/OR groups.
4. To enable **automatic closing after a time**, create a dedicated Date and Time helper with BOTH date and time and select it in section 06. This is not just a timer reset on restart: the deadline is stored for reloads and button extensions.
5. Choose an actual **clearance/obstruction binary sensor** that reports whether the closing path is safe. This is mandatory for ALL closing routes, including the Close now button. Set the state representing CLEAR, normally OFF. Unknown/unavailable, missing, or placeholder means **do not close**.
6. For actionable close-warning notifications, enter a valid Companion app service, such as notify.mobile_app_phone.

## Opening routes

| Route | Enable | Behavior |
| --- | --- | --- |
| Calendar | Section 02 | A native Home Assistant calendar START trigger, with a configurable advance offset and title filter |
| Weekly schedule | Section 03 | Select a Home Assistant Schedule helper, which holds the exact weekdays and time blocks; opens when the helper becomes ON |
| Own conditions | Section 04, plus section 01 | One or more chosen binary_sensor/input_boolean requests becoming ON; all shared opening conditions must pass |
| Driving towards home | Section 05 | Numeric distance crosses from ABOVE a chosen threshold to AT OR BELOW it, direction reports towards, and at least one selected vehicle connection sensor reports ON |

**Calendar title filter:** The default is Garage. Matching ignores case: an event called "GARAGE appointment" matches. "Dentist" does not. Clear the field to accept every title. **All-day events are excluded by default** to avoid surprise opening around midnight; enable them explicitly if required. The filter matches the **summary/title**, not the description. The offset selector defaults to **15 minutes Before**; choose any allowed signed time to suit your use case.

Calendars may be refreshed by Home Assistant only approximately every 15 minutes. Very recently created or changed events might not reliably trigger when their start is near. Calendar triggers only fire for events observed while the automation is running and are not automatically replayed when Home Assistant is off.

**Schedule:** Create a Schedule helper in Settings > Devices & Services > Helpers. Define the desired weekly time blocks for each weekday. The blueprint reacts to the beginning of a block (state OFF to ON); touching blocks where the schedule remains ON do not generate a second open command. Open commands are sent only when the garage currently reports CLOSED.

**Conditions:** The shared opening permission list supports e.g. someone being at home AND (a door is open OR a switch is on), or any other supported native conditions. The custom request in section 04 is a deliberate OFF-to-ON binary sensor/input_boolean edge; this avoids unexpected opens from unrelated sensor updates.

**Vehicle approach:** Choose the corresponding **Proximity distance sensor and direction sensor for the same person/device**. The direction must report towards. Select one or more binary sensors representing Android Auto or Bluetooth connected to your car. At least one must be ON at the moment the distance **crosses** the chosen threshold. The threshold is expressed in the proximity sensor's own native unit (km, miles or meters). Connecting to the car **alone**, or changing Bluetooth while already within the radius, does not open the door. This avoids simple "car connected in the garage" false positives.

## Closing routes

| Route | Behavior |
| --- | --- |
| Time-based closing | After the cover *actually reports OPEN*, start a stored deadline in minutes |
| House door contact | Request closing when a chosen binary_sensor changes to ON (door open) |
| Own closing request | One or more chosen binary_sensor/input_boolean entities switch to ON |
| Companion mobile button | Close now requests immediate closing after all current safety checks |

**All closing routes check the same requirements:** The cover reports OPEN, the selected real obstruction/clearance sensor reports exactly the configured CLEAR state, and every configured shared closing permission condition passes. No closing command is sent while the garage is opening/closing, the sensor is unavailable/unknown, or the pathway is reported blocked.

No unsafe bypass is provided. A sensor state of "clear" is not proof of unobstructed physical space. The garage opener must independently handle beam interruption, load detection, obstruction reversal and local manual control.

**Timing:** The deadline is stored in an input_datetime with both date and time. A once-per-minute reconciliation requests closing when the deadline is reached and is no more than **5 minutes overdue**. Older overdue deadlines are deliberately not executed after a long outage. Blocked closing does NOT produce endless retries; once the 5-minute overdue window passes, that cycle needs manual inspection or a new deliberate request. After sending a close command, the stored deadline is invalidated to prevent repeated close commands. The automation does not claim that a service call proves the physical door completed its movement.

**Recovery:** A new transition to OPEN starts a new deadline, including when opening manually. A Home Assistant startup does not blindly issue a long-overdue close command. No helper is silently created or directly edited in storage.

## Warning and mobile buttons

Optionally send a Companion-app notification shortly before the timed deadline, e.g. 5 minutes in advance, with these buttons:

- **Extend** adds a configurable number of minutes, default 10, to the stored deadline. A new warning can appear at the new deadline.
- **Close now** requests immediate closing, subject to the current clearance sensor and all closing conditions.
- **Cancel automatic closing** invalidates the current countdown. It applies to the current timed close only and does not disable independent house-door/custom close routes. A new physical OPEN transition creates a new countdown.

The warning does **not** require confirmation to close. At the deadline, closing proceeds automatically if all safety checks pass. The Companion app action needs a service such as notify.mobile_app_phone. Without it, time-based closing still works but will not deliver the mobile warning. A valid service can be temporarily unreachable, so warnings are best-effort, not a safety control.

## Configuration and limitations

- **Optional inputs:** Each opening and closing route can be disabled independently. Disabled triggers have valid placeholder entity IDs rather than wildcard event subscriptions; do not use these placeholders as actual sensors.
- **Open/close race protection:** Automation runs are queued. Opening commands are issued only if the cover reports CLOSED; closing commands only if it reports OPEN.
- **Safety sensor requirement:** Any automatic close route without a correctly configured and currently CLEAR sensor is blocked. Timed closing additionally needs the dedicated date-and-time helper.
- **No unbounded polling:** Real changes use calendar, schedule and state triggers; a one-minute reconciliation handles the stored deadline and warning boundaries.
- **Custom actions:** Optional actions run after an open or close command was attempted. These are not proof of final physical position. Cover state feedback must be checked separately.
- **Vehicle direction:** Bluetooth and Android Auto integration sensors vary across phones. Use template binary_sensor helpers when needed. The presence of a car connection is only a gate; the spatial approach comes from a separate Proximity sensor.
- **Security:** Do not expose opening controls over unauthenticated webhook events or public helper toggles. Protect the Home Assistant account used for mobile actionable notifications.

## Test checklist

1. Validate actual hardware motor safety, manual stop, beam interruption and reversal independent of Home Assistant.
2. With automatic closing OFF, test each opening source separately. Verify calendar title filter and all-day exclusion, exact schedule weekdays and distance crossing only while the car is connected and moving towards home.
3. Select a test cover in a safe test environment. Confirm that shared opening conditions suppress unauthorized opens.
4. Set a short close interval and a dedicated date/time helper. Verify deadline and that the cover only closes after the deadline when the clearance sensor reports CLEAR.
5. Force the safety sensor to ON, unknown and unavailable. Verify no close command for timer, house-door trigger or Close now.
6. Verify mobile warning, Extend and Cancel. Verify no automatic close after Cancel, and that safety checks still apply when Close now is used.
7. Restart Home Assistant while a deadline is pending. Verify the helper's deadline persists; a long-overdue deadline must not trigger a surprise close.
8. After any close command, independently check that the cover actually reaches CLOSED. Investigate failures; do not add blind repeated close commands.

Static and Home Assistant 2026.11.0 integration tests use fake entities and fake service handlers. They do not validate a real motor, actual vehicle proximity, Bluetooth, or mobile delivery.

## Update URL

```text
https://github.com/3115a083/ha-blueprints/blob/main/blueprints/automation/garage_automation_manager/garage_automation_manager.yaml
```

After a merge, import the blueprint into Home Assistant. On later changes, reimport/update and reload automations. Blueprints Updater users can refresh discovery with blueprints_updater.reload; an upstream merge does not automatically update an installed blueprint.
