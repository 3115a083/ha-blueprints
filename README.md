# Home Assistant Blueprints

Reusable, documented Home Assistant blueprints maintained by [3115a083](https://github.com/3115a083). Each blueprint has its own folder with the installable YAML and a README.

## Available blueprints

| Blueprint | Description | Install |
| --- | --- | --- |
| [Area Occupancy Manager](blueprints/automation/occupancy/README.md) | Track occupancy with multiple signals, guest/sleep protection, diagnostics, configurable actions, and restart-resilient follow-ups. | [Import into Home Assistant](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2F3115a083%2Fha-blueprints%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Foccupancy%2Farea_occupancy_manager.yaml) |

## Installation

1. Use the direct import link above, or select **Settings → Automations & scenes → Blueprints → Import blueprint** in Home Assistant.
2. Enter the YAML URL: `https://github.com/3115a083/ha-blueprints/blob/main/blueprints/automation/occupancy/area_occupancy_manager.yaml`.
3. Create the required helper and automation as described in the [occupancy setup guide](blueprints/automation/occupancy/README.md).

The occupancy blueprint declares Home Assistant **2024.10.0** as its minimum version and does not require HACS or an additional integration.

## Repository layout

```text
blueprints/
  automation/
    occupancy/
      area_occupancy_manager.yaml
      README.md
.github/workflows/
  validate-blueprints.yml
tests/
  test_blueprint.py
```

Future automation blueprints belong in `blueprints/automation/<topic>/`. Script blueprints can use `blueprints/script/<topic>/`.

## Testing and security

GitHub Actions performs static YAML and Jinja validation and checks selected safety scenarios. A live Home Assistant runtime test is still required before using critical actions such as arming alarms or closing garage doors. See the detailed [documentation](blueprints/automation/occupancy/README.md).
