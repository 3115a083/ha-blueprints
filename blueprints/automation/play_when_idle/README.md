# Play When Idle | Speaker Fallback Actions

Detect an **observable Play request** on one or more Home Assistant media players and perform a selected fallback action only while that player is **idle**. Normal playback, buffering and paused playback are left untouched.

- **Blueprint:** [play_when_idle.yaml](play_when_idle.yaml)
- **Import:** [Open My Home Assistant](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2F3115a083%2Fha-blueprints%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fplay_when_idle%2Fplay_when_idle.yaml)
- **Minimum Home Assistant version:** 2025.7.0
- **Music Assistant:** Optional for standard media or custom actions; required for MA radio and strict MA queue checking.

## Important hardware limitation

The standard Home Assistant **Sonos integration does not expose a general event when someone presses the physical Sonos Play/Pause button**. If a button press while stopped has no observable Home Assistant service call, event, event entity, or state change, **no blueprint can tell that it happened**. The blueprint does not claim otherwise.

The default triggers listen for **Home Assistant** calls to \`media_player.media_play\` and \`media_player.media_play_pause\`, typically from the HA frontend or another script/automation. A physical hardware button does **not** normally emit such a \`call_service\` event. If your device or a third-party integration exposes a button press as a device trigger, event entity or event-bus event, configure it in **02 | Play detection → Additional button or event triggers**.

This blueprint **does not automatically start radio just because a player becomes idle**. An actual detectable Play request is required. If native Sonos hardware button detection is essential and nothing exposes its presses to Home Assistant, the missing capability must be added outside this blueprint. An HA dashboard button or compatible remote is a reliable alternative.

## Quick setup: Music Assistant radio

1. Install the blueprint and create a new automation.
2. Under **01 | Players**, select your Music Assistant \`media_player\` entity or entities. Music Assistant exposes a separate player entity from the Sonos/native integration, generally identified by its \`mass_player_type\` attribute.
3. Leave **Watch Play requests from the Home Assistant UI** enabled.
4. Under **03 | Playback and queue safety**, choose **Player is idle (recommended)** for stopped MA sessions.
5. Under **04 | Fallback action**, choose **Play a Music Assistant radio station** and enter a radio station name in your MA library, or its URI.
6. Save. Stop the player so its state is \`idle\`, then press **Play in the Home Assistant UI for that selected Music Assistant player**. The radio should start. Verify its automation trace.
7. Pause a currently playing stream and press Play again. The blueprint must not replace it, because the state is \`paused\`, not \`idle\`.

Music Assistant calls use \`music_assistant.play_media\`, \`media_type: radio\`, and \`enqueue: replace\`. It starts the chosen station only when the fallback guard succeeds. For a multi-speaker setup, an HA Play command that explicitly targets one selected entity triggers only that speaker; a command listing several selected entities can trigger all those idle players.

**Music Assistant and native Sonos entities are different.** For the MA radio action, the monitored entity must be the MA entity. Pressing Play on a separate native Sonos \`media_player\` entity does not automatically target the matching MA entity. If needed, create a separate automation per hardware/button source with a custom trigger and an explicit **Fallback speaker for custom triggers** set to the desired MA entity.

## Triggers and multi-speaker safety

**Built-in HA Play commands:** The automation listens to the \`call_service\` event with \`domain: media_player\` and \`service: media_play\` or \`media_play_pause\`. The command must explicitly identify a selected entity via \`service_data.entity_id\`. This prevents unscoped play commands, broad area/device targets and Play requests for unrelated players from starting the wrong speaker. These are service requests, including those from automations, not evidence of a physical button press.

**Extra Play triggers:** Set **Additional button or event triggers** to any supported HA trigger that fires *only* for an actual Play press. Some integrations expose an event entity and provide the **Event received** trigger; others expose device or event-bus triggers. Trigger IDs are not fixed. When an extra trigger identifies a selected \`media_player\` via \`trigger.entity_id\` or \`trigger.event.data.entity_id\`, that entity is used. If it cannot be matched:

- With exactly one monitored player, that player is chosen.
- With multiple monitored players and a configured **Fallback speaker for custom triggers**, only the configured speaker is chosen.
- With multiple monitored players and **no** matching or fallback entity, no action is taken. This deliberately avoids launching radio on every idle speaker after one button press.

For independent physical button sources on several speakers that do not provide a player entity ID, create separate blueprint automations with their own custom trigger and fallback speaker.

Custom triggers **must be press-specific**. A generic state change to \`idle\` would trigger on ordinary end-of-playback, violating the intended behavior.

## Which queue check should I choose?

| Setting | When it runs | Trade-off |
| --- | --- | --- |
| **Player is idle (default)** | An observable Play event targets a selected player in \`idle\` | Handles stopped MA sessions; \`idle\` is not proof that the queue has zero items |
| **Idle and no media metadata is loaded** | \`idle\` and neither \`media_content_id\` nor \`media_title\` is set | Rejects stale/retained media metadata, but can miss genuinely stopped sessions |
| **Idle and Music Assistant queue has zero items** | \`idle\`, MA player, and \`music_assistant.get_queue\` returns \`items: 0\` | Strict; requires the integration; rejects failed/missing queue information and stopped-but-populated queues |

The \`paused\`, \`playing\`, \`buffering\`, \`off\`, \`unknown\` and \`unavailable\` states never qualify. Music Assistant documentation notes that a long pause can eventually change the queue state to stopped. If it appears as \`idle\`, the default test cannot always distinguish it from a true stop. Select the stricter queue mode if your devices need that protection, and verify its response in **Developer tools → Actions → Music Assistant: Get queue details**. Its response is keyed by MA player entity ID and includes an \`items\` count. Strict mode **fails closed** if the count cannot be read.

No polling is used. The chosen custom action is not executed automatically when a queue naturally finishes.

## Other actions

Use **04 | Fallback action** to select one of:

- **Music Assistant radio:** Play a station by library name or URI, replacing the stopped queue.
- **Standard media:** \`media_player.play_media\` with a URL/media ID and the configured content type. Works with compatible HA players; the player must support the content.
- **Custom actions:** Build any Home Assistant actions, such as \`script.turn_on\`, \`scene.turn_on\`, a notification, or a selected playlist service call. The variable \`play_target_player\` identifies the eligible player, so custom actions can target \`{{ play_target_player }}\`. For safety, the same player-state and optional queue checks gate every custom action.

If a configured station/media ID is blank, or MA radio mode is selected without a Music Assistant entity, no media command is made. The optional **Log each executed fallback** setting adds an informational log on eligible attempts. **Duplicate-press cooldown** defaults to 3 seconds. Long-running custom actions and multiple independent HA event requests may still need their own de-duplication.

## Testing checklist

In **Developer tools → Events**, listen for \`call_service\` and press Play in the Home Assistant UI to verify that a matching \`media_player.media_play\` request is emitted. To investigate physical devices, listen for their documented integration-specific events or inspect event entities; do not assume the Sonos hardware key reports a \`call_service\` event.

Inspect the automation trace and verify \`candidate_players\`, \`play_target_player\`, \`playback_idle\`, \`is_ma_player\`, and \`queue_allowed\`. A trace that has an empty \`candidate_players\` list means there was no safely identified speaker. A populated list with \`playback_idle: false\` means the player was not idle at evaluation time.

The blueprint is checked by automated YAML/Jinja regression tests. These tests do not confirm physical button events, Sonos firmware behavior or a live Music Assistant installation.

## Import URL

Copy this exact URL into Home Assistant's **Import blueprint** dialog:

```text
https://github.com/3115a083/ha-blueprints/blob/main/blueprints/automation/play_when_idle/play_when_idle.yaml
```
