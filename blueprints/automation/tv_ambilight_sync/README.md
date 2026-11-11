# TV Ambilight Sync | Conditional Lighting & Timeout Guard

This blueprint follows the **power state of the official Android TV Remote media player** and controls a **single retrofit Ambilight light or switch**. It supports arbitrarily combined Home Assistant conditions and an optional maximum-on safeguard for televisions whose reported state occasionally gets stuck at ON.

- [Blueprint YAML](tv_ambilight_sync.yaml)
- [Import into Home Assistant](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2F3115a083%2Fha-blueprints%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Ftv_ambilight_sync%2Ftv_ambilight_sync.yaml)
- **Minimum Home Assistant Core:** 2026.11.0.

## Quick setup

1. Under **01 | Television and Ambilight**, choose the **media_player** entity from Home Assistant's official **Android TV Remote** integration, and the retrofit Ambilight **light** or **switch** entity.
2. Under **02 | Freely combined permission conditions**, add any conditions in the **visual condition editor**. An empty list means the Ambilight follows the TV with no additional restrictions. Top-level conditions use **AND**. Use the editor's **AND** and **OR** groups to create other combinations.
3. Add **the entities referenced by your conditions** to **Recheck immediately when these entities change**, especially lux and occupancy sensors. The default includes `sun.sun`. Keep at least one selected. The automation also checks once per minute, including time windows.
4. Optional: Set a maximum-on duration and configure the dedicated input_boolean helper as described below.

## Freely combined conditions

These are examples, **not hardcoded rules or fixed sensor choices**:

| Desired behavior | Add this condition in the visual editor |
| --- | --- |
| Only after sunset | **Sun**, after sunset, before sunrise; or **State**, `sun.sun` is `below_horizon` |
| Only when it is dark | **Numeric state** of your chosen lux sensor, **below** 20 |
| Only from 18:00 to 23:30 | **Time**, after 18:00, before 23:30 |
| Only if the living room is occupied | **State** of the chosen occupancy sensor, `on` |
| Dark and (occupied or movie mode) | Numeric state **AND** an **OR** group containing occupancy and your chosen movie-mode helper |

Nothing is preselected beyond the TV and the Ambilight entities. Conditions use Home Assistant's native editor, so you can choose and combine supported condition types yourself.

**Changing conditions are active restrictions, not merely start conditions.** With the TV ON, if the lux rises above the selected threshold, a person leaves, or a time window ends, the Ambilight is switched OFF. If the TV remains ON and the combined conditions later become true again, the Ambilight is switched ON unless a maximum-on lockout is active.

**Reaction time:** The TV and Ambilight entities, plus selected **Recheck** entities, are monitored using native state triggers. Other changes, and the passage of a time boundary, are reconciled with a one-minute time pattern. Depending on timing, those changes can take up to approximately one minute. Conditions on entities not listed under Recheck are still checked each minute.

## TV state handling

| TV media-player state | Ambilight behavior |
| --- | --- |
| `on`, `playing`, `paused`, `idle`, `buffering` | Allowed only if all selected conditions pass |
| `off`, `standby`, `unknown`, `unavailable` | Switched OFF |

This automation checks the **reported Home Assistant state**, not the physical TV's power consumption. If the Android TV Remote integration freezes at `on`, the Ambilight may remain on until the optional maximum-on watchdog intervenes. A TV stuck at `off` cannot be distinguished from a genuinely switched-off TV without another sensor.

The automation also synchronizes state at Home Assistant startup and when the Ambilight is toggled manually. With no lockout, manually turning it off while the TV is active and conditions pass will normally make it turn back on.

## Maximum-on safeguard

**Disabled by default.** Set **Maximum continuous Ambilight ON time** to a number of minutes to enable it. It measures continuous ON time using the Ambilight entity's `last_changed` timestamp. Changing the TV's playback application does not reset this time.

### Dedicated helper required

For any nonzero maximum, create one `input_boolean` helper **per automation**:

1. Open **Settings > Devices & services > Helpers > Create helper**.
2. Choose **Toggle**, name it e.g. `Ambilight timeout lockout`.
3. Select it in **Dedicated timeout lockout helper** in the blueprint.

The helper persists the watchdog lockout between automation runs. When the time limit is reached it is switched ON. **Automatic Ambilight turn-on stays blocked until the TV reports OFF**, at which point the helper resets. This is necessary because a TV stuck at `on` otherwise causes the automation to turn the light straight back on after an automatic safety shutdown.

If a duration is configured but the helper is missing, the blueprint **fails safely**: it keeps Ambilight OFF and shows a persistent configuration warning on TV changes/startup. To disable the watchdog, set the duration back to zero. The blueprint does not create helpers itself and does not modify unrelated entities.

### Action at the time limit

- **Turn Ambilight off immediately** (default): Sets the lockout helper, switches the Ambilight off, and prevents reactivation until the TV reports OFF.
- **Notify with a Turn off button:** Sets the lockout helper, sends a Companion-app mobile notification, and leaves the Ambilight ON until the button is tapped. Enter the mobile action ID such as `notify.mobile_app_phone` in **Companion mobile notification action**. The button sends `mobile_app_notification_action`; only a matching action ID scoped to this automation is accepted. This mode relies on mobile push delivery and your response; it does **not** force the light off if the notification goes unanswered.

If the mobile action name is missing or invalid, **notification mode falls back to directly turning Ambilight OFF**, with a persistent warning. A valid but temporarily unreachable notification service may still fail to deliver, so prefer direct OFF for a safety-critical cap.

### Timing and restart limits

The deadline check runs on each automation evaluation and at least once per minute. It is based on the Ambilight entity state transition, not a wall-clock counter stored in the blueprint. Home Assistant restarts can reset `last_changed` for restored states, so the full elapsed time may not survive an HA restart. The separate lockout helper persists its ON state until the TV reports OFF, but when HA restarts *before* the first timeout, the deadline may begin again. This is a safeguard against a stuck TV state, **not** a hard electrical cut-off or fire-safety mechanism.

The built-in notification action can switch off only the selected Ambilight. It does not turn off the TV.

## Verification checklist

- Select a test light, then turn the TV ON and OFF. Confirm the Ambilight follows and does not react to `unknown` or `unavailable` by turning on.
- Combine occupancy ON and lux below a threshold, and add both to Recheck. With the TV ON, toggle occupancy or cross the lux threshold. Confirm Ambilight switches off and on in response.
- Configure a time window. Check a boundary while the TV stays ON; it may take up to one minute.
- For the watchdog, set a small duration and a dedicated helper. Confirm it turns off only the Ambilight and stays off while TV remains ON. Turn TV OFF and ON to reset.
- In notification mode, check the phone's notification contains the **Turn off Ambilight** action and that tapping it switches off the correct light.
- Test behavior after Home Assistant restart and after the TV integration becomes unavailable. Real device testing is required to verify push delivery and physical power state.

## Updates

Import URL:

```text
https://github.com/3115a083/ha-blueprints/blob/main/blueprints/automation/tv_ambilight_sync/tv_ambilight_sync.yaml
```

After repository updates, reimport/update the blueprint and reload the automation in Home Assistant. Blueprints Updater users can call `blueprints_updater.reload` to rescan. A merge into `main` does not automatically update an already imported blueprint.
