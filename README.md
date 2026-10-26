# Home Assistant Blueprints

A collection of reusable, configurable **Home Assistant blueprints** maintained by [3115a083](https://github.com/3115a083). Each blueprint lives in its own directory, with an installable YAML file and a dedicated README that covers setup, examples, limitations, and safety notes.

## Blueprint catalog

| Blueprint | Description | Documentation | Install | Manual import URL |
| --- | --- | --- | --- | --- |
| **🔐 Unlock Sequence** | Detect ordered button/event/MQTT sequences with independent time limits, optional persistent lockout and explicit authorization checks. | [Setup and security](blueprints/automation/unlock_sequence/README.md) | [Import blueprint](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2F3115a083%2Fha-blueprints%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Funlock_sequence%2Funlock_sequence.yaml) | `https://github.com/3115a083/ha-blueprints/blob/main/blueprints/automation/unlock_sequence/unlock_sequence.yaml` · [Copy URL](#copy-unlock-sequence-url) |
| **🏠 Area Occupancy Manager** | Detect occupied/vacant areas using people, devices, and optional sensors. Run configurable actions, with guest/sleep protections and independent timed routines. | [Setup and examples](blueprints/automation/occupancy/README.md) | [Import blueprint](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2F3115a083%2Fha-blueprints%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Foccupancy%2Farea_occupancy_manager.yaml) | `https://github.com/3115a083/ha-blueprints/blob/main/blueprints/automation/occupancy/area_occupancy_manager.yaml` · [Copy URL](#copy-area-occupancy-manager-url) |
| **🌅 Sunrise Alarm / Light Wake-Up** | Start lights a configurable time before a phone alarm. Linear, ramp-up or instant brightening, with optional start, completion and alarm-time actions. | [Setup and examples](blueprints/automation/alarm_light/README.md) | [Import blueprint](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2F3115a083%2Fha-blueprints%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Falarm_light%2Falarm_light.yaml) | `https://github.com/3115a083/ha-blueprints/blob/main/blueprints/automation/alarm_light/alarm_light.yaml` · [Copy URL](#copy-sunrise-alarm-light-wake-up-url) |
| **🔧 Govee Light Recovery** | Diagnose Govee2MQTT light unavailability and ESPHome relay power issues for any number of lamps, each with an optional relay and Ping sensor; guarded restoration, optional app restart and notifications. | [Setup and safety](blueprints/automation/govee_recovery/README.md) | [Import blueprint](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2F3115a083%2Fha-blueprints%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fgovee_recovery%2Fgovee_recovery.yaml) | `https://github.com/3115a083/ha-blueprints/blob/main/blueprints/automation/govee_recovery/govee_recovery.yaml` · [Copy URL](#copy-govee-light-recovery-url) |
| **🎵 Music Assistant / NSPanel Presets** | Start favorite radios/playlists, cycle speakers and transfer playback from NSPanel buttons without changing Blackymas firmware. | [Setup and examples](blueprints/automation/music_assistant_nspanel/README.md) | [Import blueprint](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2F3115a083%2Fha-blueprints%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fmusic_assistant_nspanel%2Fmusic_assistant_nspanel.yaml) | `https://github.com/3115a083/ha-blueprints/blob/main/blueprints/automation/music_assistant_nspanel/music_assistant_nspanel.yaml` · [Copy URL](#copy-music-assistant-nspanel-presets-url) |
| **🔥 Advanced Heating Control Multi-Zone** | Manage any number of independent heating zones in one automation, with room-specific inputs, global controls and a clear vacation override. Based on the awesome blueprint by [panhans](https://community.home-assistant.io/t/advanced-heating-control/469873). | [Setup and examples](blueprints/automation/advanced_heating_multi_zone/README.md) | [Import blueprint](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2F3115a083%2Fha-blueprints%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fadvanced_heating_multi_zone%2Fadvanced_heating_multi_zone.yaml) | `https://github.com/3115a083/ha-blueprints/blob/main/blueprints/automation/advanced_heating_multi_zone/advanced_heating_multi_zone.yaml` · [Copy URL](#copy-advanced-heating-control-multi-zone-url) |
| **💡 Forgotten Devices / Energy Saver** | Shut down forgotten devices, groups or room lights with exceptions, shared entry rules, individual/global runtimes and a preview. | [Setup and examples](blueprints/automation/forgotten_devices/README.md) | [Import blueprint](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2F3115a083%2Fha-blueprints%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fforgotten_devices%2Fforgotten_devices.yaml) | `https://github.com/3115a083/ha-blueprints/blob/main/blueprints/automation/forgotten_devices/forgotten_devices.yaml` · [Copy URL](#copy-forgotten-devices-energy-saver-url) |

## Copy an import URL

Paste a **blueprint YAML URL**, not a My Home Assistant redirect, into **Settings → Automations & scenes → Blueprints → Import blueprint**. The table shows each URL directly. Its **Copy URL** link jumps to the matching code block below; hover over the block and use GitHub's built-in copy button. On mobile, open the code block's copy control or select its single URL. No browser script or external clipboard service is needed.

### Copy Unlock Sequence URL

```text
https://github.com/3115a083/ha-blueprints/blob/main/blueprints/automation/unlock_sequence/unlock_sequence.yaml
```

### Copy Area Occupancy Manager URL

```text
https://github.com/3115a083/ha-blueprints/blob/main/blueprints/automation/occupancy/area_occupancy_manager.yaml
```

### Copy Sunrise Alarm Light Wake-Up URL

```text
https://github.com/3115a083/ha-blueprints/blob/main/blueprints/automation/alarm_light/alarm_light.yaml
```

### Copy Govee Light Recovery URL

```text
https://github.com/3115a083/ha-blueprints/blob/main/blueprints/automation/govee_recovery/govee_recovery.yaml
```

### Copy Music Assistant NSPanel Presets URL

```text
https://github.com/3115a083/ha-blueprints/blob/main/blueprints/automation/music_assistant_nspanel/music_assistant_nspanel.yaml
```

### Copy Advanced Heating Control Multi-Zone URL

```text
https://github.com/3115a083/ha-blueprints/blob/main/blueprints/automation/advanced_heating_multi_zone/advanced_heating_multi_zone.yaml
```

### Copy Forgotten Devices Energy Saver URL

```text
https://github.com/3115a083/ha-blueprints/blob/main/blueprints/automation/forgotten_devices/forgotten_devices.yaml
```

## How to install a blueprint

1. Choose a blueprint from the catalog and open its **Documentation** for prerequisites and configuration.
2. Click **Import blueprint** or open **Home Assistant -> Settings -> Automations & scenes -> Blueprints -> Import blueprint** and provide the YAML URL.
3. Create an automation from the imported blueprint and configure its inputs.
4. Test with non-critical actions before enabling alarms, locks, motors, or similar devices.

The catalog is a starting point. **Blueprint-specific settings and use cases are documented in the linked README inside each blueprint folder**, rather than in this repository overview.

## Updates with Blueprints Updater

All seven blueprints contain a canonical `blueprint.source_url` pointing to their own YAML file on this repository's `main` branch. The URLs in the catalog and copy blocks match those metadata values. Keep this metadata when importing or copying a file manually.

[Blueprints Updater](https://github.com/luuquangvu/blueprints-updater) uses the source URL to retrieve the upstream file and compares normalized content hashes. It accepts GitHub `blob/main` URLs and converts them to raw downloads. **A GitHub Release, tag, release asset, or blueprint version field is not required.** A short hash shown as a blueprint's update version is normal for this integration; it is not the HACS release version of the updater integration itself. Adding a `version` key to blueprint metadata is unnecessary and may violate Home Assistant's blueprint schema.

1. Import a blueprint using its canonical URL above. Install and configure **Blueprints Updater** separately in Home Assistant.
2. Make sure its tracking filters include the imported blueprint. Choose manual update approval or auto-updates in the integration's options.
3. After adding a blueprint, run **Developer Tools → Actions → `blueprints_updater.reload`**, or reload the integration, to refresh its scan. Use the blueprint's native update entity when a change is detected.
4. Retain `source_url` and the original blueprint file path. Do not replace the source with a commit SHA, fixed tag, release attachment, README URL or My Home Assistant redirect if you want future `main` updates.
5. Review the change and the updater's compatibility report before installing; use its backup option where appropriate. Each blueprint still requires its own declared minimum Home Assistant version. The updater's compatibility guard may block an incompatible update.

The repository checks canonical source URLs, catalog/import links, copy blocks and Home Assistant blueprint schemas in CI. This establishes the source metadata needed for tracking; it does not claim that the updater was installed or tested on your own Home Assistant instance. Verification reference: upstream `luuquangvu/blueprints-updater` commit `ff76efac1667ead0db50fcef7469c416700b469e`, inspected 2026-10-15 (`README.md`, `providers.py`, `blueprint_validation.py` and `update.py`).

## Repository structure

```text
blueprints/
  automation/
    unlock_sequence/
      unlock_sequence.yaml
      helpers-package.example.yml
      README.md
    occupancy/
      area_occupancy_manager.yaml
      README.md
    alarm_light/
      alarm_light.yaml
      README.md
    govee_recovery/
      govee_recovery.yaml
      README.md
    music_assistant_nspanel/
      music_assistant_nspanel.yaml
      README.md
    forgotten_devices/
      forgotten_devices.yaml
      README.md
      CHANGELOG.md
    advanced_heating_multi_zone/
      advanced_heating_multi_zone.yaml
      README.md
      CHANGELOG.md
.github/workflows/
  validate-blueprints.yml
tests/
  test_unlock_sequence.py
  test_blueprint.py
  test_alarm_light.py
  test_govee_recovery.py
  test_music_assistant_nspanel.py
  test_advanced_heating_multi_zone.py
```

New automation blueprints belong in `blueprints/automation/<topic>/`; script blueprints can use `blueprints/script/<topic>/`.

## Validation

Static tests are provided in [tests](tests/) and configured in [GitHub Actions](.github/workflows/validate-blueprints.yml). Static validation does not replace testing on a live Home Assistant instance, particularly for safety-critical actions.

Unlock Sequence includes [security and compatibility details](blueprints/automation/unlock_sequence/README.md) and [release notes](blueprints/automation/unlock_sequence/CHANGELOG.md). Review its conservative trigger rules and persistent-helper requirements before importing.
