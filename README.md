# Home Assistant Blueprints

Wiederverwendbare Home-Assistant-Blueprints von [3115a083](https://github.com/3115a083). Jeder Blueprint erhält einen eigenen Ordner mit YAML-Datei und Dokumentation.

## Blueprints

| Blueprint | Zweck | Installation |
|---|---|---|
| [Area Occupancy Manager](blueprints/automation/occupancy/README.md) | Anwesenheit/Abwesenheit mit Gäste-/Schlafschutz, Diagnose, frei wählbaren Aktionen und neustartfesten Zeitabläufen | [In Home Assistant importieren](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2F3115a083%2Fha-blueprints%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Foccupancy%2Farea_occupancy_manager.yaml) |

## Installation

1. Auf **In Home Assistant importieren** klicken oder in Home Assistant **Einstellungen → Automatisierungen & Szenen → Blueprints → Blueprint importieren** öffnen.
2. Bei manueller Installation diese URL einfügen:

   `https://github.com/3115a083/ha-blueprints/blob/main/blueprints/automation/occupancy/area_occupancy_manager.yaml`

3. Vorschau prüfen, importieren und über **Automatisierung erstellen** konfigurieren.
4. Der Occupancy-Blueprint benötigt pro Bereich einen zuvor angelegten `input_boolean`-Helfer für den Belegungsstatus. Optional kommen ein Schlaf-Umschalter, ein Diagnose-Texthelfer und für neustartfeste Zeitaktionen ein `input_datetime` plus ein weiterer `input_boolean` hinzu.

Die URL zeigt auf eine echte YAML-Datei und lässt sich über den Home-Assistant-Blueprint-Import laden. Mindestversion: **Home Assistant 2024.10.0**.

## Repository-Struktur

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

Neue Automations-Blueprints gehören unter `blueprints/automation/<thema>/`, Script-Blueprints entsprechend unter `blueprints/script/<thema>/`.

## Qualität und Sicherheit

Der CI-Test prüft YAML-Struktur, Blueprint-Eingaben und typische Schutzszenarien. Eine **echte Ausführung auf einer Home-Assistant-Instanz** ist damit nicht ersetzt. Automatische Verriegelung, Scharfschaltung und das Schließen von Garagentoren sollten erst nach einem Praxistest und mit unabhängigen Sicherheitssensoren freigegeben werden.

Weitere Hinweise und konkrete Beispiele stehen in der [Occupancy-Dokumentation](blueprints/automation/occupancy/README.md).
