# Home Assistant Blueprints

A collection of reusable, configurable **Home Assistant blueprints** maintained by [3115a083](https://github.com/3115a083). Each blueprint lives in its own directory, with an installable YAML file and a dedicated README that covers setup, examples, limitations, and safety notes.

## Blueprint catalog

| Blueprint | Description | Documentation | Install |
| --- | --- | --- | --- |
| **Area Occupancy Manager** | Detect occupied/vacant areas using people, devices, and optional sensors. Run configurable actions, with guest/sleep protections and independent timed routines. | [Setup and examples](blueprints/automation/occupancy/README.md) | [Import blueprint](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2F3115a083%2Fha-blueprints%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Foccupancy%2Farea_occupancy_manager.yaml) |

## How to install a blueprint

1. Choose a blueprint from the catalog and open its **Documentation** for prerequisites and configuration.
2. Click **Import blueprint** or open **Home Assistant -> Settings -> Automations & scenes -> Blueprints -> Import blueprint** and provide the YAML URL.
3. Create an automation from the imported blueprint and configure its inputs.
4. Test with non-critical actions before enabling alarms, locks, motors, or similar devices.

The catalog is a starting point. **Blueprint-specific settings and use cases are documented in the linked README inside each blueprint folder**, rather than in this repository overview.

## Repository structure

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

New automation blueprints belong in `blueprints/automation/<topic>/`; script blueprints can use `blueprints/script/<topic>/`.

## Validation

Static tests are provided in [tests](tests/) and configured in [GitHub Actions](.github/workflows/validate-blueprints.yml). Static validation does not replace testing on a live Home Assistant instance, particularly for safety-critical actions.
