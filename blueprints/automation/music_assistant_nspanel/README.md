# 🎵 Music Assistant | NSPanel Presets & Speakers

This companion blueprint adds **radio stations, playlists and Music Assistant speaker selection** to [Blackymas' NSPanel HA Blueprint](https://github.com/Blackymas/NSPanel_HA_Blueprint), **without changing its firmware or existing NSPanel automation**.

[Import into Home Assistant](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2F3115a083%2Fha-blueprints%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fmusic_assistant_nspanel%2Fmusic_assistant_nspanel.yaml) · [Blueprint YAML](music_assistant_nspanel.yaml) · [Repository catalog](../../../README.md)

**Requirements:** Home Assistant 2025.7+, the official [Music Assistant integration](https://www.music-assistant.io/integration/installation/) with one or more Music Assistant media_player entities, and Blackymas NSPanel HA Blueprint with four free button positions.

## What you can control

| NSPanel button | Result |
| --- | --- |
| **📻 Next preset** | Cycles through configured favorite radio stations and playlists |
| **🔊 Next speaker** | Cycles through configured Music Assistant speakers |
| **▶️ Play** | Starts the selected radio/playlist on the selected speaker |
| **🔀 Move music** | Transfers the active queue from another configured playing speaker to the selected speaker |

Two Home Assistant Dropdown helpers show the current preset and speaker, also usable on an NSPanel **Entities Page** as state displays.

**Display limitation:** This is a button-driven favorites selector, **not a native Music Assistant library browser, touchscreen dropdown or custom Nextion UI**. Blackymas' built-in Media Player page stays attached to its own, statically configured media_player entity. Speaker selection here affects **Play** and **Move music**, not the panel's existing Media Player long-press page.

## Setup: six helpers and four NSPanel buttons

1. In Home Assistant, go to **Settings → Devices & services → Helpers → Create helper**.
2. Create **two Dropdown helpers** (input_select): one called **NSPanel selected music**, one **NSPanel selected speaker**. Give each one placeholder option, for example *Select music* and *Select speaker*.
3. Create **four Button helpers** (input_button): **NSPanel next preset**, **NSPanel next speaker**, **NSPanel play**, **NSPanel move music**.
4. Import this companion blueprint and create a **second automation** alongside Blackymas' existing NSPanel automation.
5. In **📻 01 | Radios and playlists**, add your favorite stations/playlists. Each row has a distinct display label, a type of Radio or Playlist and an MA **name or URI**.
6. In **🔊 02 | Available speakers**, add the available Music Assistant speakers. Each row has a distinct label and its actual Music Assistant media_player entity.
7. In **🎛️ 03 | NSPanel selection and action buttons**, assign the two Dropdown helpers and four Button helpers.
8. Edit your **original NSPanel HA Blueprint automation** and assign the four input_button entities to four Button Page positions. Optionally assign the two input_select entities to an Entities Page to display the selected names.

The companion automation automatically populates the two Dropdown option lists on Home Assistant startup/reload and when a button is pressed. You do not need to maintain these options twice. **Use unique labels within each list.** The helpers also work from the HA UI, allowing you to test before using the actual panel.

### Example preset list

| Label | Type | MA name / URI |
| --- | --- | --- |
| BBC 6 Music | Radio | BBC Radio 6 Music |
| Jazz FM | Radio | Jazz FM |
| Morning Mix | Playlist | Morning Mix |
| Relax Playlist | Playlist | library://playlist/42 (illustrative — replace with your actual URI) |

### Example speaker list

| Label | HA player |
| --- | --- |
| Living room | media_player.ma_living_room |
| Kitchen | media_player.ma_kitchen |
| Bedroom | media_player.ma_bedroom |

Add radio stations to the Music Assistant Radio library first, for example using Radio Browser, TuneIn or a custom URL. For playlists, use a library playlist or a playlist from a configured provider. **When names are ambiguous, use the item's Music Assistant URI.**

## Test on the panel

1. Press **Next preset**: the selected music Dropdown changes to the following station or playlist.
2. Press **Next speaker**: the selected speaker Dropdown advances.
3. Press **Play**: Music Assistant calls music_assistant.play_media with the selected type (radio or playlist), name/URI and speaker; playback starts only after this button is pressed.
4. With music already playing elsewhere, select a different speaker and press **Move music**. This calls music_assistant.transfer_queue with auto_play enabled.
5. The choices are visible as text on an NSPanel Entities Page, subject to the display's label-length limits.

**Move music** selects the first configured speaker currently in the playing state, excluding the chosen destination. It does nothing when no other configured speaker is playing. If several are playing, the source is the first one in the blueprint's speaker list. You do not need to replace the existing NSPanel blueprint to use this feature.

## Integration actions used

- **music_assistant.play_media** with media_type radio/playlist, media_id name/URI, and enqueue play.
- **music_assistant.transfer_queue** with source_player, target player and auto_play true.
- Standard Home Assistant input_button triggers and input_select selection/option actions.
- No time polling, Govee controls, special ESPHome firmware, custom MQTT commands or unofficial Music Assistant API calls.

Music Assistant players must be exposed by the Music Assistant HA integration. If playback fails, test the same radio name or URI through **Developer tools → Actions** with music_assistant.play_media, verify permissions to the Music Assistant instance and inspect its logs.

## Known limitations

- There is **no full browse/search interface on NSPanel**; users cycle through a curated favorite list.
- Speaker selection does **not** dynamically redirect Blackymas' native Media Player details page. Assign specific players separately to NSPanel media buttons if you also need their built-in playback controls.
- Transfer works only when another **configured** speaker is actively playing; it is not automatic on every speaker change.
- No streaming-service-specific configuration is embedded in the blueprint.
- Long display labels might be truncated by the small NSPanel display.

References: [Blackymas NSPanel HA Blueprint](https://github.com/Blackymas/NSPanel_HA_Blueprint), [Music Assistant play media](https://www.music-assistant.io/faq/massplaymedia/), [Music Assistant queue transfer](https://www.home-assistant.io/actions/music_assistant.transfer_queue/), [Home Assistant input_button](https://www.home-assistant.io/integrations/input_button/) and [Input select](https://www.home-assistant.io/integrations/input_select/).

The repository contains [static tests](../../../tests/test_music_assistant_nspanel.py). This companion has **not been tested on a live NSPanel or Music Assistant instance**.

## Import URL and updates

Copy this URL into Home Assistant's **Import blueprint** dialog. On GitHub, the code block has a built-in copy button.

```text
https://github.com/3115a083/ha-blueprints/blob/main/blueprints/automation/music_assistant_nspanel/music_assistant_nspanel.yaml
```

This is also the blueprint's `source_url`. [Blueprints Updater](https://github.com/luuquangvu/blueprints-updater) can track changes at this stable `main` URL without a GitHub Release or version tag. Keep `source_url` in the installed YAML. After import, refresh the integration with `blueprints_updater.reload` if necessary, and check its tracking filters. See the [repository update instructions](../../../README.md#updates-with-blueprints-updater).
