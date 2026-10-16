# 🌅 Sunrise Alarm | Custom Light Wake-Up

A customizable sunrise-style light alarm for Home Assistant. It reads an existing **next-alarm timestamp sensor**, starts selected lights before that alarm, and optionally runs any Home Assistant actions or scripts during the wake-up routine.

[**Import into Home Assistant**](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2F3115a083%2Fha-blueprints%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Falarm_light%2Falarm_light.yaml) · [Blueprint YAML](alarm_light.yaml)

**Requirements:** Home Assistant 2024.10.0 or newer; an enabled sensor with the **timestamp** device class that reports the next alarm time, a configured **person** entity, and one or more controllable lights. No HACS or custom integration is required. The alarm sensor itself is usually provided by a phone integration; this blueprint does not create alarms.

## Quick setup

1. Import the blueprint using the link above, then create an automation from it.
2. In **⏰ 01 | Alarm & start time**, select your next-alarm timestamp sensor and person entity. Set **Start lights this many minutes before the alarm** (0–180 minutes) and choose the active days.
3. In **💡 02 | Light & brightness**, select the target lights, brightness curve, start/target brightness, and when the fade should finish. For a gentler wake-up, set **Reach target brightness minutes AFTER the alarm** to e.g. `15`.
4. Optionally open **🎵 03 | Additional actions** to configure start, finish and alarm-time actions.
5. Optionally open **🛡️ 04 | Optional conditions** to adjust darkness checking or add any Home Assistant conditions.
6. For an exact-time start, open **⏱️ 05 | Optional precise scheduling**, enable native exact-time start, and enter an offset such as `-00:05:00`. **The offset must not start earlier than the lead time in section 01.** If it would, the automation safely falls back to the section 01 lead time.

**Default:** The lights start **30 minutes** before the alarm, brighten **linearly** over **30 minutes** from **1%** to **85%**, run **every day**, and only start when the selected person is **home** and the sun is **below the horizon**.

**Efficient scheduling:** The normal start uses a minute-based template that fires only when the chosen lead time is reached. Native precise scheduling uses an event-based timestamp trigger when the configured offset does not exceed the allowed lead time. A conflicting offset automatically enables the standard template schedule instead. Both paths verify the current timestamp before turning on the lights. Alarm-time actions use their own native trigger.

## Timing and brightness options

| Option | Behavior |
| --- | --- |
| **Start before alarm (section 01)** | 0 to 180 minutes before the timestamp, in one-minute increments. **Always the earliest permitted light start**, also in precise mode. |
| **Precise native start (optional)** | Enter a negative `-HH:MM:SS` offset. It can start at or *later* than the section 01 start, but never earlier. If the offset exceeds the section 01 lead time, the standard minute trigger takes over. |
| **Linear** | Increases brightness evenly over the selected fade duration |
| **Ramp-up / Ease-in** | Increases slowly at first and increasingly quickly toward the target; uses a quadratic curve |
| **Instant** | Turns on directly at target brightness and does not wait for the fade duration |
| **Brightening duration** | 1 to 180 minutes. Used when the post-alarm completion delay is **0**. |
| **Reach target brightness by alarm time** | **On by default**, when the post-alarm delay is **0**. With this enabled, a 5-minute lead and 30-minute fade setting finishes in 5 minutes. Turning it off allows the configured fade to extend beyond the alarm. |
| **🌄 Reach target brightness minutes AFTER the alarm** | **0–120 minutes, default 0.** A positive number sets an **explicit completion time** after the alarm, overriding the fade duration and the preceding switch in Linear and Ease-in modes. E.g. 5-minute lead and `15` means a 20-minute fade, ending 15 minutes after the alarm. |
| **Starting / target brightness** | 1 to 100%; the starting level cannot exceed the target (it is clamped) |
| **Fade update interval** | 15 to 120 seconds per brightness command, subject to a cap of 240 total steps |

Gradual modes send plain Home Assistant **light.turn_on** commands with `brightness_pct` at each configured interval. They **no longer force a `transition` parameter**, which is not consistently supported by all light integrations, including some Govee2MQTT configurations. This improves compatibility but some lamps may show discrete brightness steps rather than perfectly smooth transitions. Multiple selected lights may not synchronize perfectly. <https://www.home-assistant.io/actions/light.turn_on/>

### Example: morning alarm at 07:00

| Setting | Linear example | Ease-in example | Instant example |
| --- | --- | --- | --- |
| Start before alarm | 30 min | 40 min | 10 min |
| Lights start | 06:30 | 06:20 | 06:50 |
| Brightening time | 30 min | 40 min | Ignored |
| Target | 85% at 07:00 | 85% at 07:00 | 85% at 06:50 |

**The lead time limits the default fade duration.** With **Reach target brightness by alarm time** enabled and the after-alarm delay at `0`, the ramp finishes no later than the scheduled wake-up.

**For a gentler wake-up**, set a positive **Reach target brightness minutes AFTER the alarm** value. The ramp then spreads the increase across the period from when the light turns on until the selected time *after* the alarm, irrespective of the shorter fade duration setting or the finish-by-alarm switch. The **Instant** brightness mode is an exception: it still jumps to target immediately. Alarm-time actions remain scheduled at the actual alarm time, even while the lights continue to brighten.

### Example: reach full target brightness *after* the alarm

For a **07:00** alarm, choose:

| Input | Value |
| --- | --- |
| Start lights before alarm | **10 minutes** |
| How brightness increases | **Linear** or **Ramp-up / Ease-in** |
| Starting brightness | **1%** |
| Target brightness | **75%** (your comfortable maximum) |
| Reach target brightness minutes AFTER the alarm | **15 minutes** |

**Result:** Lights start at **06:50** with 1% brightness; they are still at a gentle intermediate level when the alarm rings at **07:00**, and rise gradually to **75% by 07:15**. Choosing **30 minutes** instead finishes at **07:30**.

If you prefer a gentler curve with less light at the alarm time, use **Ramp-up / Ease-in**. The goal is the configured **target brightness**, not necessarily the device's physical 100% maximum.

A phone may change its next-alarm sensor to tomorrow after the alarm rings. The fade now allows an alarm-sensor rollover at or after the original alarm time and continues until the planned completion time. If the scheduled alarm was changed **before** it rang, the existing fade is cancelled instead.

### Fixed: lights staying dim instead of brightening

Prior releases could leave the light dim with a short lead time and longer fade duration. For example, with a 07:00 alarm, five-minute lead, 30-minute linear fade and 1% → 85% brightness, the light would still be around **15%** at 07:00 and the fade could stop if a phone updated its next-alarm sensor. The fixed default shortens the fade to the remaining five minutes, reaching **85% at 07:00**.

The updated loop waits between successive brightness commands, rechecks the selected person and alarm, and allows the fade to continue when the phone's next-alarm timestamp rolls over **at or after the actual scheduled alarm time**, up to the planned finish time. If the alarm changes before that time, the remaining steps are cancelled as a safeguard.

For Govee/Govee2MQTT and other lights without reliable hardware fade support, the blueprint now uses plain `brightness_pct` commands rather than assuming the light supports `transition`. **An integration still needs to support brightness changes**; check that changing brightness manually from 10% to 80% in Home Assistant actually works on that entity.

### 📈 Brightness curve example

Suppose brightness rises from **1%** to **81%** over 40 minutes:

| Elapsed time | Linear | Ramp-up / Ease-in | Instant |
| --- | ---: | ---: | ---: |
| 0 min | 1% | 1% | 81% |
| 10 min | ~21% | ~6% | 81% |
| 20 min | ~41% | ~21% | 81% |
| 30 min | ~61% | ~46% | 81% |
| 40 min | 81% | 81% | 81% |

The figures are illustrative; commands are quantized to whole brightness percentages and scheduled update intervals.

## ⏱️ Native precise scheduling: accuracy without extra polling

If you want more accurate wake-up timing, **do not increase polling frequency in the morning**. Home Assistant supports an **entity-based native time trigger** with an offset. Its scheduler registers a timestamp-based future event, and recalculates the schedule when the alarm sensor changes.

To enable it, expand **05 | Optional precise scheduling** and set:

- **Enable native exact-time start:** ON.
- **Exact offset before the alarm:** Enter a valid negative time duration, for example `-00:30:00` (30 minutes), `-00:05:30` (5 minutes 30 seconds), or `00:00:00` (at the alarm time).

**Important safety rule:** The numeric **Start lights this many minutes before the alarm** value in section 01 always sets the **earliest allowed start**. The precise offset may be equal to this value or closer to the alarm. If the precise offset would start earlier, Home Assistant automatically uses the section 01 minute-based start instead; the precise trigger is disabled. If you change either input, save/reload the automation so Home Assistant registers the updated triggers. Existing installations still default to the minute-based mode.

| | Standard minutes mode | Native precise mode |
| --- | --- | --- |
| Start-time configuration | 0–180 minutes (number input) | Exact offset such as `-00:05:00` **bounded by** the section 01 lead |
| Time monitoring | Lightweight template evaluated every minute | Native scheduled event when offset is safe; automatic minute-based fallback when not |
| Automation executions before sunrise | None | None |
| Expected precision | Up to roughly 1 minute | Seconds on the native path; about one minute on automatic fallback |
| Changing phone alarm | Re-evaluates the template | Reschedules the native event |
| Restart while sunrise is running | Stops existing fade | Stops existing fade |

### Fixed: avoiding an unexpectedly early alarm

In previous releases, enabling native precise scheduling caused the `precise_start_offset` default (`-00:30:00`) to **override** the section 01 `lead_minutes` value. For example, a 07:00 alarm with a 5-minute lead could turn the lights on at **06:30 instead of 06:55**.

The corrected blueprint uses the following behavior:

| Alarm | Lead (section 01) | Precise offset | Actual light start |
| --- | --- | --- | --- |
| 07:00 | 5 min | `-00:30:00` | **06:55**, via automatic safe fallback |
| 07:00 | 5 min | `-00:05:00` | **06:55**, via native precise trigger |
| 07:00 | 30 min | `-00:10:00` | **06:50**, via native precise trigger |
| 07:00 | 30 min | `00:00:00` | **07:00**, via native precise trigger |

The light-start action also rejects a trigger that arrives outside its intended time window or before the earliest allowed lead time. This protects against stale or unexpectedly fired events; it does not correct an incorrect timestamp published by the alarm sensor itself.

Home Assistant needs a **valid offset syntax** for this mode because it is a native trigger configuration, not a text expression evaluated in the actions. An invalid offset can prevent the automation from loading, so verify the format after editing.

The light's brightness update interval is independent of the alarm start trigger. Gradual fades intentionally send commands at the configured interval. Increasing that interval, such as from 15 to 60 seconds, reduces brightness commands but may make the steps more visible.

## 🎵 Additional actions

Each slot accepts the standard Home Assistant **action selector**, including services, scripts, scenes, choose/if blocks, and conditions:

- **Sunrise start actions:** Run in parallel with the first light command. Example: start a gentle playlist or adjust the thermostat.
- **Sunrise complete actions:** Run after the gradual brightening finishes (including a configured post-alarm fade), or immediately after instant-on. They are skipped if the alarm changes before it rings, or the person leaves home before completion.
- **Alarm-time actions:** Run **at the actual alarm timestamp**. Example: gradually increase music volume, announce today's weather, or open smart blinds. They have their own time trigger and do not wait for the light fade to finish.

The same person-at-home, active-day, and custom additional conditions apply to both triggers. **Darkness is checked only when lights begin**, so alarm-time actions can still run after sunrise.

### Example: wake up with light, music, and blinds

Set the alarm sensor to your phone's next alarm, lead time to **35 minutes**, brightness to **Linear**, and duration to **30 minutes**. In the action editors:

- Sunrise start: media player volume to 10%, play gentle audio.
- Sunrise complete: optionally enable bedside lighting or a scene.
- Alarm time: open blinds and play a spoken announcement.

Choose the specific entities and automation actions directly in Home Assistant. No device or media service is hard-coded in this blueprint.

## Safety, scheduling, and known limitations

- **Timing precision and efficiency:** Standard mode uses a once-per-minute evaluated template, not a 15-second periodic trigger. Safe native precise mode schedules the timestamp and negative offset directly. Conflicting earlier precise offsets automatically revert to the standard lead. Missed starts during downtime are not executed retroactively.
- **Rescheduling:** Changing the alarm time before the current alarm sounds stops the remaining fade steps. When a phone rolls over to the next alarm **at or after** the original alarm time, the current ramp is allowed to finish at the chosen post-alarm completion time (with up to 60 seconds' scheduling grace). A new valid future alarm schedules its own start.
- **Restarts:** Home Assistant restarts or automation reloads cancel any fade currently running. Later alarm starts are evaluated normally. This blueprint does **not** save and restore in-progress brightness curves.
- **Presence:** The selected person must be at **home** for the sunrise to begin. During a gradual fade, leaving home stops subsequent brightness commands. At the alarm timestamp, alarm-time actions require the person to be home.
- **Sun check:** The default checks \`sun.sun\` is \`below_horizon\` when the lights begin; disable the condition for daytime/light alarms.
- **Day selection:** Weekdays and weekends are checked against the **local date of the actual alarm**, even when the lights start before midnight the previous day.
- **Next alarm:** The source must provide a valid future datetime as a timestamp sensor. Invalid, unavailable or past timestamps are ignored by the start scheduler.
- **Multiple alarm events:** Use one automation instance per person/alarm source. Home Assistant's parallel mode lets alarm-time actions run while a fade is still active.
- **Device capabilities:** Standard brightness updates are used, without forced transition support. A lamp still needs working Home Assistant brightness control. Test manual brightness changes and try a short fade before relying on the automation to wake you.

The test suite validates blueprint structure, Jinja syntax, timing-window calculations, active-day rollover, brightness curves, and action branches. **A live Home Assistant runtime test is still recommended.**

## Credits

Inspired by [r3mcos3's Alarm Light blueprint](https://github.com/r3mcos3/blueprints/blob/main/alarm_light/alarm_light.yaml), particularly its timestamp-sensor, person-at-home, darkness and active-day approach. This implementation adds independently configured lead time and fade duration, three brightness behaviors, independent actions, and current blueprint/automation syntax.

For other available blueprints, return to the [repository catalog](../../../README.md).

## Import URL and updates

Copy this URL into Home Assistant's **Import blueprint** dialog. On GitHub, the code block has a built-in copy button.

```text
https://github.com/3115a083/ha-blueprints/blob/main/blueprints/automation/alarm_light/alarm_light.yaml
```

This is also the blueprint's `source_url`. [Blueprints Updater](https://github.com/luuquangvu/blueprints-updater) can track changes at this stable `main` URL without a GitHub Release or version tag. Keep `source_url` in the installed YAML. After import, refresh the integration with `blueprints_updater.reload` if necessary, and check its tracking filters. See the [repository update instructions](../../../README.md#updates-with-blueprints-updater).
