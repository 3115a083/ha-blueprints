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
5. **Optional:** Select a Home Assistant clearance/obstruction binary sensor. Leave it empty if your garage opener has its own independently functioning physical obstacle detection and automatic reversal. Automatic closing works without a Home Assistant sensor. If one is selected, the state representing CLEAR (normally OFF) is required for every close command. Blocked, unknown or unavailable always prevents closing.
6. For close-warning notifications, select one or more Home Assistant **notify entities** in section 07. For **Extend / Close now / Cancel** buttons, additionally provide a Companion service such as `notify.mobile_app_phone`. Avoid selecting the same phone both ways unless duplicate messages are acceptable.
7. For vehicle arrival, select the **Proximity direction** (`towards` / `arrived`) and **matching Proximity distance sensor** for the same driver and Home zone, plus the driver's Companion GPS tracker for adjustable accuracy. Choose the Companion Bluetooth Connection sensor and the exact car name/MAC, or a matching Android Auto binary sensor. Create one **Text helper** (`input_text`) for the remembered trip.

## Opening routes

| Route | Enable | Behavior |
| --- | --- | --- |
| Calendar | Section 02 | Native calendar START trigger with lead time and title filter, plus optional person-at-home and calendar-only AND/OR conditions |
| Weekly schedule | Section 03 | Select a Home Assistant Schedule helper, which holds the exact weekdays and time blocks; opens when the helper becomes ON |
| Own conditions | Section 04, plus section 01 | One or more chosen binary_sensor/input_boolean requests becoming ON; all shared opening conditions must pass |
| Driving towards home | Section 05 | Native Proximity reports **`towards`**, then **`arrived`** after a measured net approach (default 300m), with car Bluetooth/Android Auto observed for at least 2 minutes and current GPS accuracy passing your selected limit |

**Calendar title filter:** The default is Garage. Matching ignores case: an event called "GARAGE appointment" matches. "Dentist" does not. Clear the field to accept every title. **All-day events are excluded by default** to avoid surprise opening around midnight; enable them explicitly if required. The filter matches the **summary/title**, not the description. The offset selector defaults to **15 minutes Before**.

**Additional calendar permissions:** Optionally select one **person entity that must currently report `home`**. For example, your calendar entry will open the garage only if that person is home. Calendar-only visual permission conditions also support any combination of AND/OR groups, including presence, sun and time. Both permission types apply **only to calendar openings**. The general opening conditions in section 01 still apply to every opening route.

Calendars may be refreshed by Home Assistant only approximately every 15 minutes. Very recently created or changed events might not reliably trigger when their start is near. Calendar triggers only fire for events observed while the automation is running and are not automatically replayed when Home Assistant is off.

**Schedule:** Create a Schedule helper in Settings > Devices & Services > Helpers. Define the desired weekly time blocks for each weekday. The blueprint reacts to the beginning of a block (state OFF to ON); touching blocks where the schedule remains ON do not generate a second open command. Open commands are sent only when the garage currently reports CLOSED.

**Conditions:** The shared opening permission list supports e.g. someone being at home AND (a door is open OR a switch is on), or any other supported native conditions. The custom request in section 04 is a deliberate OFF-to-ON binary sensor/input_boolean edge; this avoids unexpected opens from unrelated sensor updates.

### Vehicle arrival with Home Assistant Proximity and car Bluetooth

The native [Proximity integration](https://www.home-assistant.io/integrations/proximity/) has **Direction of travel** values `towards` (approaching) and `arrived` (inside the Home zone), plus a **Distance** sensor for each tracked person/device. Proximity distance is measured **from the zone boundary**, so its value becomes zero on arrival. The blueprint uses these native signals instead of trying to guess direction from two GPS points.

An arrival alone **never opens the garage**. The user-configurable controls work as follows:

1. In **Approaching home by car**, select the driver's **Proximity direction sensor for Home** and the **matching Proximity distance sensor**, using the same tracked driver (not the generic nearest-person sensor). Select the phone's actual **GPS device_tracker** so its `gps_accuracy` and coordinates can be checked.
2. Select the Companion App's Bluetooth Connection **sensor** (`sensor.*_bluetooth_connection`). The attribute `connected_paired_devices` shows only currently connected paired devices. Copy your exact car device name in parentheses, MAC address or full entry from **Developer Tools > States**. The editor offers a dropdown of the attribute **names**, but native Blueprint selectors cannot dynamically populate the individual car device **values**. You can alternatively select an Android Auto binary sensor.
3. Create a dedicated **Text helper** under **Settings > Devices & services > Helpers** with a maximum length of at least **100 characters** and select it under **Trip session storage**. It remembers when a valid car connection was first observed **while Proximity reported `towards`** and the distance from the Home zone at that point.
4. Set **Minimum measured approach towards home** (default **300m**) and **Car connected for at least** (default **2 minutes**). Once Proximity reports `arrived`, the blueprint requires the stored approach distance to have decreased by the configured minimum **and** the observed trip to have lasted at least the chosen time. The distance is a **net reduction towards home**, not an odometer distance.
5. Set **Maximum permitted phone GPS uncertainty** freely (default **25m**, selectable 5–250m). At arrival, GPS must have a numeric accuracy within this limit and a tracker update no more than five minutes old. Set **Home Assistant distance units** (km or mi) to match the unit system of your Proximity sensors.
6. By default, a qualifying `arrived` event opens the garage when the car has completed the verified approach. Home zones can be large. If you want the garage to open only extremely close to the house, set **Optional extra distance limit** (e.g. **25m**) to require the GPS position to be within that distance of the Home center **at the arrived event**. If GPS reports the zone arrival before reaching that small distance, no command is sent for that event.

**Trip reset:** The record is cleared when the selected car connection reports disconnected, Proximity changes to `away_from` or `unknown` (short `stationary` stops do not reset the trip), after an `arrived` event, and on Home Assistant restart. Old trips expire after the selected maximum duration (default 90 minutes). Connected-car and direction sensor updates can be delayed or skipped by Android, Bluetooth and GPS. The blueprint cannot prove continuous real-world driving or car identity from these signals alone. A phone left in a car could also satisfy Bluetooth detection.

**Safety:** Keep the Home zone appropriately small, adjust GPS accuracy and, when appropriate, use the extra center-distance limit. Verify the arrival behavior with the door in view before granting unattended opening. The built-in opener obstruction protections remain independently required.

## Closing routes

| Route | Behavior |
| --- | --- |
| Time-based closing | After the cover *actually reports OPEN*, start a stored deadline in minutes |
| House door contact | Request closing when a chosen binary_sensor changes to ON (door open) |
| Own closing request | One or more chosen binary_sensor/input_boolean entities switch to ON |
| Companion mobile button | Close now requests immediate closing after all current safety checks |

**All closing routes check the same requirements:** The cover reports OPEN and every configured shared closing permission condition passes. If a Home Assistant obstruction sensor was selected, it must also report the configured CLEAR state. **Without a selected sensor, automatic closing is allowed**, provided the opener's own physical obstruction detection and automatic reversal have been independently verified. No close command is sent while the cover reports opening, closing or an unavailable state. With a configured sensor, blocked, unknown and unavailable states prevent closing.

A Home Assistant sensor is supplementary to the opener's built-in protection. A sensor state of "clear" does not prove the closing path is unobstructed. The opener must independently handle beam interruption, load detection, obstruction reversal and local manual control. Do not use this blueprint to replace or disable those functions.

**Timing:** The deadline is stored in an input_datetime with both date and time. A once-per-minute reconciliation requests closing when the deadline is reached and is no more than **5 minutes overdue**. Older overdue deadlines are deliberately not executed after a long outage. Blocked closing does NOT produce endless retries; once the 5-minute overdue window passes, that cycle needs manual inspection or a new deliberate request. After sending a close command, the stored deadline is invalidated to prevent repeated close commands. The automation does not claim that a service call proves the physical door completed its movement.

**Recovery:** A new transition to OPEN starts a new deadline, including when opening manually. A Home Assistant startup does not blindly issue a long-overdue close command. No helper is silently created or directly edited in storage.

## Warning and mobile buttons

Use the **Notification recipients** picker to send a plain-text warning to one or more `notify` entities shortly before the timed deadline. To also include actionable buttons, configure a Companion app `notify.mobile_app_*` service separately. Generic notify entities do not guarantee support for buttons. The Companion app notification includes:

- **Extend** adds a configurable number of minutes, default 10, to the stored deadline. A new warning can appear at the new deadline.
- **Close now** requests immediate closing, subject to any selected clearance sensor and all closing conditions.
- **Cancel automatic closing** invalidates the current countdown. It applies to the current timed close only and does not disable independent house-door/custom close routes. A new physical OPEN transition creates a new countdown.

The warning does **not** require confirmation to close. At the deadline, closing proceeds automatically if all safety checks pass. Without any notification target, time-based closing still works but does not send a warning. A notify entity receives a regular warning; a valid Companion service additionally delivers Extend / Close now / Cancel buttons. A temporarily unreachable service may not deliver, so warnings are best-effort, not a safety control.

## Configuration and limitations

- **Optional inputs:** Each opening and closing route can be disabled independently. Disabled triggers have valid placeholder entity IDs rather than wildcard event subscriptions; do not use these placeholders as actual sensors.
- **Open/close race protection:** Automation runs are queued. Opening commands are issued only if the cover reports CLOSED; closing commands only if it reports OPEN.
- **Optional Home Assistant safety sensor:** The field can be empty, with no additional software opt-in. If selected, the sensor must currently report CLEAR. Timed closing additionally needs the dedicated date-and-time helper. The opener's built-in collision detection and auto-reverse must remain independently functional.
- **No unbounded polling:** Real changes use calendar, schedule and state triggers; a one-minute reconciliation handles the stored deadline and warning boundaries.
- **Custom actions:** Optional actions run after an open or close command was attempted. These are not proof of final physical position. Cover state feedback must be checked separately.
- **Vehicle trip evidence:** The car Bluetooth/Android Auto connection is only a gate, and the separate GPS tracker must demonstrate a minimum net approach towards home over the configured time. The Text helper stores trip state. This cannot authenticate the vehicle or guarantee continuous travel if the phone skips sensor updates.
- **Security:** Do not expose opening controls over unauthenticated webhook events or public helper toggles. Protect the Home Assistant account used for mobile actionable notifications.

## Test checklist

1. Validate actual hardware motor safety, manual stop, beam interruption and reversal independent of Home Assistant.
2. With automatic closing OFF, test each opening source separately. Verify calendar title filter and all-day exclusion, person-not-home and calendar-only conditions, exact schedule weekdays, and the Proximity transition `towards` to `arrived` after enough distance reduction and connected-car time.
3. Select a test cover in a safe test environment. Confirm that shared opening conditions suppress unauthorized opens. Test Bluetooth connecting while already home, incorrect Bluetooth identity, car disconnect mid-trip, insufficient distance, insufficient connection time, and poor GPS accuracy. None should send an opening command. Test zone radius versus optional tighter distance cap.
4. Set a short close interval and a dedicated date/time helper. Verify that the cover closes after the deadline with **no Home Assistant safety sensor selected**, relying on the garage opener's built-in protection.
5. Optionally select a Home Assistant sensor, then force it to ON, unknown and unavailable. Verify no close command for timer, house-door trigger or Close now. Restore CLEAR and verify closing is possible.
6. Verify mobile warning, Extend and Cancel. Verify no automatic close after Cancel, and that safety checks still apply when Close now is used.
7. Restart Home Assistant while a deadline is pending. Verify the helper's deadline persists; a long-overdue deadline must not trigger a surprise close.
8. After any close command, independently check that the cover actually reaches CLOSED. Investigate failures; do not add blind repeated close commands.

Static and Home Assistant 2026.11.0 integration tests use fake entities and fake service handlers. They do not validate a real motor, actual vehicle proximity, Bluetooth, or mobile delivery.

## Update URL

```text
https://github.com/3115a083/ha-blueprints/blob/main/blueprints/automation/garage_automation_manager/garage_automation_manager.yaml
```

After a merge, import the blueprint into Home Assistant. On later changes, reimport/update and reload automations. Blueprints Updater users can refresh discovery with blueprints_updater.reload; an upstream merge does not automatically update an installed blueprint.
