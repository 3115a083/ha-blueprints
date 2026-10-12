# 🌅 Sunrise Alarm | Custom Light Wake-Up

A customizable sunrise-style light alarm for Home Assistant. It reads an existing **next-alarm timestamp sensor**, starts selected lights before that alarm, and optionally runs any Home Assistant actions or scripts during the wake-up routine.

[**Import into Home Assistant**](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2F3115a083%2Fha-blueprints%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Falarm_light%2Falarm_light.yaml) · [Blueprint YAML](alarm_light.yaml)

**Requirements:** Home Assistant 2024.10.0 or newer; an enabled sensor with the **timestamp** device class that reports the next alarm time, a configured **person** entity, and one or more controllable lights. No HACS or custom integration is required. The alarm sensor itself is usually provided by a phone integration; this blueprint does not create alarms.

## Quick setup

1. Import the blueprint using the link above, then create an automation from it.
2. In **⏰ 01 | Alarm & start time**, select your next-alarm timestamp sensor and person entity. Set **Start lights this many minutes before the alarm** (0–180 minutes) and choose the active days.
3. In **💡 02 | Light & brightness**, select the target lights, brightness curve, start/target brightness, and how many minutes the fade takes.
4. Optionally open **🎵 03 | Additional actions** to configure start, finish and alarm-time actions.
5. Optionally open **🛡️ 04 | Optional conditions** to adjust darkness checking or add any Home Assistant conditions.
6. For a more exact start without minute-based checks, open **⏱️ 05 | Optional precise scheduling**, enable native exact-time start, and enter a negative offset such as `-00:30:00`. This overrides the normal lead-minutes setting while enabled.

**Default:** The lights start **30 minutes** before the alarm, brighten **linearly** over **30 minutes** from **1%** to **85%**, run **every day**, and only start when the selected person is **home** and the sun is **below the horizon**.

**Efficient scheduling:** The default sunrise automation does not execute every few seconds: a template is checked at minute boundaries and starts the automation only when the scheduled window is reached. **Native precise scheduling** instead uses Home Assistant's event-driven time trigger on the alarm sensor with a negative offset. That allows exact scheduled timing without regularly checking the current time. The alarm-time actions already use a separate native timestamp trigger.

## Timing and brightness options

| Option | Behavior |
| --- | --- |
| **Start before alarm (standard mode)** | 0 to 180 minutes before the timestamp, in one-minute increments; independent of fade duration; start checked at minute resolution |
| **Precise native start (optional)** | Enter a valid negative `-HH:MM:SS` offset. Example: `-00:30:00` schedules exactly 30 minutes before the sensor time. This overrides the standard lead setting and avoids clock polling. |
| **Linear** | Increases brightness evenly over the selected fade duration |
| **Ramp-up / Ease-in** | Increases slowly at first and increasingly quickly toward the target; uses a quadratic curve |
| **Instant** | Turns on directly at target brightness and does not wait for the fade duration |
| **Brightening duration** | 1 to 180 minutes, used only by the two gradual curves |
| **Starting / target brightness** | 1 to 100%; the starting level cannot exceed the target (it is clamped) |
| **Fade update interval** | 15 to 120 seconds per brightness command, subject to a cap of 240 total steps |

The gradual modes use Home Assistant's normal **light.turn_on** brightness and **transition** options. Devices with native transition support should fade smoothly between updates. Lights without transition support may visibly jump between intermediate levels. Multiple selected lights may not synchronize perfectly due to device behavior. <https://www.home-assistant.io/actions/light.turn_on/>

### Example: morning alarm at 07:00

| Setting | Linear example | Ease-in example | Instant example |
| --- | --- | --- | --- |
| Start before alarm | 30 min | 40 min | 10 min |
| Lights start | 06:30 | 06:20 | 06:50 |
| Brightening time | 30 min | 40 min | Ignored |
| Target | 85% at 07:00 | 85% at 07:00 | 85% at 06:50 |

**The lead time and fade time are independent.** If the fade duration exceeds the lead time, it may continue *after* the actual alarm while optional alarm-time actions run separately.

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

This mode uses the offset field *instead of* the numeric **Start lights this many minutes before the alarm** setting. If you later adjust the offset, save/reload the automation so Home Assistant registers the changed schedule. **Existing installations default to standard scheduling** until you enable this optional mode.

| | Standard minutes mode | Native precise mode |
| --- | --- | --- |
| Start-time configuration | 0–180 minutes (number input) | Signed time offset, e.g. `-00:30:00` |
| Time monitoring | Lightweight template evaluated every minute | Native scheduled event, **no repeating clock checks** |
| Automation executions before sunrise | None | None |
| Expected precision | Up to roughly 1 minute | Home Assistant scheduler resolution (typically seconds; not a hard real-time guarantee) |
| Changing phone alarm | Re-evaluates the template | Reschedules the native event |
| Restart while sunrise is running | Stops existing fade | Stops existing fade |

Home Assistant needs a **valid offset syntax** for this mode because it is a native trigger configuration, not a text expression evaluated in the actions. An invalid offset can prevent the automation from loading, so verify the format after editing.

The light's brightness update interval is independent of the alarm start trigger. Gradual fades intentionally send commands at the configured interval. Increasing that interval, such as from 15 to 60 seconds, reduces brightness commands but may make the steps more visible.

## 🎵 Additional actions

Each slot accepts the standard Home Assistant **action selector**, including services, scripts, scenes, choose/if blocks, and conditions:

- **Sunrise start actions:** Run in parallel with the first light command. Example: start a gentle playlist or adjust the thermostat.
- **Sunrise complete actions:** Run after the gradual brightening finishes, or immediately after instant-on. These are skipped if the alarm timestamp changes or the person is no longer home before completion.
- **Alarm-time actions:** Run **at the actual alarm timestamp**. Example: gradually increase music volume, announce today's weather, or open smart blinds. They have their own time trigger and do not wait for the light fade to finish.

The same person-at-home, active-day, and custom additional conditions apply to both triggers. **Darkness is checked only when lights begin**, so alarm-time actions can still run after sunrise.

### Example: wake up with light, music, and blinds

Set the alarm sensor to your phone's next alarm, lead time to **35 minutes**, brightness to **Linear**, and duration to **30 minutes**. In the action editors:

- Sunrise start: media player volume to 10%, play gentle audio.
- Sunrise complete: optionally enable bedside lighting or a scene.
- Alarm time: open blinds and play a spoken announcement.

Choose the specific entities and automation actions directly in Home Assistant. No device or media service is hard-coded in this blueprint.

## Safety, scheduling, and known limitations

- **Timing precision and efficiency:** Standard mode uses a template trigger updated at minute boundaries, not a 15-second periodic trigger, so start precision is approximately one minute. Native precise mode schedules the timestamp plus its negative offset directly instead. Missed starts during downtime are not executed retroactively.
- **Rescheduling:** A changed alarm timestamp prevents the remaining steps and completion actions of an already running gradual fade. A new valid future alarm will schedule its own start.
- **Restarts:** Home Assistant restarts or automation reloads cancel any fade currently running. Later alarm starts are evaluated normally. This blueprint does **not** save and restore in-progress brightness curves.
- **Presence:** The selected person must be at **home** for the sunrise to begin. During a gradual fade, leaving home stops subsequent brightness commands. At the alarm timestamp, alarm-time actions require the person to be home.
- **Sun check:** The default checks \`sun.sun\` is \`below_horizon\` when the lights begin; disable the condition for daytime/light alarms.
- **Day selection:** Weekdays and weekends are checked against the **local date of the actual alarm**, even when the lights start before midnight the previous day.
- **Next alarm:** The source must provide a valid future datetime as a timestamp sensor. Invalid, unavailable or past timestamps are ignored by the start scheduler.
- **Multiple alarm events:** Use one automation instance per person/alarm source. Home Assistant's parallel mode lets alarm-time actions run while a fade is still active.
- **Device capabilities:** Different lights may implement transitions differently. Try a short fade with your chosen lights before relying on the result for waking up.

The test suite validates blueprint structure, Jinja syntax, timing-window calculations, active-day rollover, brightness curves, and action branches. **A live Home Assistant runtime test is still recommended.**

## Credits

Inspired by [r3mcos3's Alarm Light blueprint](https://github.com/r3mcos3/blueprints/blob/main/alarm_light/alarm_light.yaml), particularly its timestamp-sensor, person-at-home, darkness and active-day approach. This implementation adds independently configured lead time and fade duration, three brightness behaviors, independent actions, and current blueprint/automation syntax.

For other available blueprints, return to the [repository catalog](../../../README.md).
