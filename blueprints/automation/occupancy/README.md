# Area Occupancy Manager

Verwaltet den Belegungszustand eines frei definierten Bereichs in Home Assistant. Kann für ein ganzes Haus, eine Garage oder einen einzelnen Raum mehrfach eingerichtet werden. Statt fester Geräteaktionen entscheidet der Nutzer selbst, was beim Statuswechsel passiert.

**Blueprint:** [`area_occupancy_manager.yaml`](area_occupancy_manager.yaml)  
**Home Assistant:** ab 2024.10.0  
**Installation:** [Blueprint direkt importieren](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2F3115a083%2Fha-blueprints%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Foccupancy%2Farea_occupancy_manager.yaml)

## Grundprinzip

Ein `input_boolean`-Helfer ist die einzige Quelle des Belegungsstatus: `on` bedeutet **belegt**, `off` **leer**. Der Blueprint setzt ihn auf Basis konfigurierter Signale, sofern keine Sperre greift. Die Aktionen laufen **nur bei einem tatsächlichen Zustandswechsel**. Der Helfer kann auch manuell geschaltet werden, etwa über ein Dashboard; das löst dieselben Belegungs-/Leer-Aktionen aus.

- **Abwesenheitssignale:** Alle gewählten Personen-/Gerätetracker sind fort, alle gewählten Bewegungs-/Präsenzsensoren bleiben für eine einstellbare Zeit ruhig, Tür 1 gefolgt von Tür 2 oder beliebige eigene Trigger.
- **Ankunftssignale:** Ein Tracker kehrt nach `home` zurück, Bewegung/Präsenz wird erkannt, ein gewähltes Schloss wird entriegelt, Tür 2 gefolgt von Tür 1 oder ein eigener Trigger.
- **Kombination:** Mit `ALLE` (Standard) müssen alle konfigurierten Tracker und Aktivitätssensoren Abwesenheit bestätigen. Mit `EINES` genügt ein Abwesenheitsnachweis, **aber** ein bekannter anwesender Tracker sowie aktive oder ausgefallene Aktivitätssensoren blockieren immer. Nicht konfigurierte Signalquellen zählen nicht mit.
- **Zusätzliche Sperren:** Gastmodus-`input_boolean`, weitere Präsenzsensoren und vollständig frei konfigurierbare Home-Assistant-Bedingungen. Unbekannte/nicht erreichbare Sicherheitssensoren verhindern Abwesenheit.
- **Aktionen:** Die Action-Editoren akzeptieren beliebige Home-Assistant-Aktionen, Skripte und Bedingungen; keine feste Bindung an Lichter, Alarmanlagen oder Medienplayer.
- **Zeitaktionen:** Bei Ankunft kann eine bedingte Aktion ausgelöst und nach N Minuten eine Folgeaktion ausgeführt werden. Auch dafür können separate Bedingungen hinterlegt werden.
- **Neustart/Reload:** Alle fünf Minuten sowie beim HA-Start werden bereits stabile Signalzustände erneut abgeglichen. Aktionen für abgebrochene temporäre Delays werden jedoch **nicht** wiederhergestellt.

## Installation und Einrichtung

1. [Import-Link](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2F3115a083%2Fha-blueprints%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Foccupancy%2Farea_occupancy_manager.yaml) öffnen, oder in HA unter **Einstellungen → Automatisierungen & Szenen → Blueprints → Blueprint importieren** die [GitHub-YAML-URL](https://github.com/3115a083/ha-blueprints/blob/main/blueprints/automation/occupancy/area_occupancy_manager.yaml) einfügen.
2. Unter **Einstellungen → Geräte & Dienste → Helfer** einen **Umschalter** für den Bereich anlegen, z. B. `input_boolean.haus_belegt`. Vor dem Start auf den tatsächlichen Zustand setzen.
3. Blueprint-Automatisierung anlegen und den Umschalter in **01 | Belegungsstatus** auswählen. Es empfiehlt sich, zuerst nur harmlose Aktionen oder Benachrichtigungen einzurichten.
4. Tracker und/oder Bewegung-/Präsenzsensoren zuordnen. Für ein gesamtes Haus alle regulären Bewohner auswählen und einen separaten Gastmodus-Helfer anlegen.
5. Zusätzliche Präsenzsperren, Abwesenheits- und Ankunftsaktionen konfigurieren. Mit tatsächlicher Bewegung, An- und Abwesenheit sowie bei nicht verfügbaren Sensoren testen.

### Türfolge konfigurieren

In **04 | Türen** zwei `binary_sensor`-Türkontakte wählen. `Tür 1 → Tür 2` innerhalb von 30 s (änderbar) gilt als Abgang; `Tür 2 → Tür 1` als Ankunft. Entscheidend ist, dass **der zweite Kontakt erst nach dem ersten auslöst**. Nicht geeignet für Türen, die normalerweise offen stehen, oder bei denen die Bewegungsrichtung nicht eindeutig ist. Ein alleiniger Öffnungsimpuls gilt nicht als abgeschlossene Folge.

### Eigene Trigger

Der Blueprint bietet getrennte Trigger-Editoren. Die Trigger-ID muss in den *Einstellungen des jeweiligen Triggers* ausdrücklich gesetzt sein:

- **Eigene Abwesenheits-Trigger:** `custom_away`
- **Eigene Ankunfts-Trigger:** `custom_home`

Mehrere eigene Trigger mit gleicher ID sind zulässig. Für eine komplexere Tür-/Alarm-/BLE-Sequenz können beliebige Trigger von Home Assistant verwendet werden. Bei Custom-Abwesenheit werden stets die gewählten Sicherheitsbedingungen geprüft. Wer `ALLE` gewählt hat, muss weiterhin alle eingerichteten Tracker-/Aktivitätssignale für Abwesenheit erfüllen.

## Konfigurationsbeispiele

### Haus verlassen, Gast bleibt

- `input_boolean.haus_belegt` steht auf EIN.
- `person.bewohner` verlässt die Home-Zone.
- `input_boolean.gaeste_da` steht auf EIN **oder** ein zuverlässiger Präsenzsensor im Gästezimmer meldet EIN.
- Ergebnis: Der Bereich bleibt **belegt**, keine Alarm-/Licht-aus-/Verriegelungsaktionen.
- Sobald die Sperren entfernt sind, wird der Abwesenheitszustand bei fortdauernder stabiler Abwesenheit innerhalb von höchstens ungefähr fünf Minuten neu bewertet.

**Einschränkung:** Eine Person, die keine ausgewählten Sensoren auslöst und für die kein Gastmodus aktiviert ist, kann technisch nicht erkannt werden. **PIR allein ist keine sichere Anwesenheitserkennung für schlafende Personen.**

### Licht nur bei Dunkelheit einschalten

In **Aktionen bei belegt** im Aktionseditor einen **Wenn/Dann**-Block hinzufügen. Als Bedingung **Sonne: unter Horizont** oder einen Lux-Sensor mit Grenzwert verwenden; im Dann-Abschnitt `light.turn_on` hinzufügen. Andere Ankunftsaktionen laufen unabhängig davon.

### Bei Ankunft Garage öffnen, nach 40 Minuten schließen

Unter **06 | Zeitlich begrenzte Ankunftsaktionen**:

1. **Aktivieren:** EIN.
2. **Startbedingungen:** Das zugehörige `binary_sensor`/`device_tracker` meldet die Bluetooth-Verbindung von Handy und Auto; idealerweise zusätzlich bestätigen, dass das Auto gerade heimkehrt.
3. **Startaktionen:** `cover.open_cover` für das Garagentor.
4. **Dauer:** `40` Minuten.
5. **Folgebedingungen:** Mindestens Torstatus und vorhandene Hindernis-/Lichtschrankensensoren prüfen. Bei ungeklärtem Zustand nicht schließen.
6. **Folgeaktionen:** `cover.close_cover` für das Garagentor.

Die Folgeaktion einer **früheren Ankunft** wird übersprungen, falls dazwischen ein neuer Belegungswechsel auf EIN stattfand. Ist der Bereich inzwischen leer, darf die Folgeaktion nach Ablauf weiterhin erfolgen, wenn ihre Sicherheitsbedingungen zutreffen. Aktive Verzögerungen laufen nicht über einen Home-Assistant-Neustart/Automations-Reload hinweg. Für eine neustartfeste Garagentor-Schließung einen eigenen `timer`-/`input_datetime`-basierten Ablauf verwenden. Für sicherheitskritische Motoren ausschließlich Geräte mit eigenständigem Hindernisschutz verwenden.

## Wichtige Sicherheitsregeln

- `unknown`/`unavailable` bei einem gewählten Tracker, Aktivitäts- oder Sperrsensor darf **nicht** als positive Abwesenheit gewertet werden. Deshalb bleibt das System in diesem Fall eher belegt.
- Gewählte Tracker auf `home` und erkannte Bewegung/Präsenz blockieren **auch bei Kombinationsmodus `EINES`** das automatische Leerschalten.
- Ein **Gastmodus** ist nötig, wenn Personen außerhalb der regulär getrackten Bewohner im Bereich bleiben können und Sensoren deren Anwesenheit nicht dauerhaft melden.
- Eine **manuelle** Umschaltung des Belegungshelfers ist bewusst ein explizites Override und führt trotz Gastmodus zu Aktionen. Den Helfer nicht ungeschützt auf öffentlichen Dashboards platzieren.
- Bei verschlossener Tür oder aktivierter Alarmanlage nach Möglichkeit Tür-/Fensterkontakte, Riegelstatus und konkrete Alarmbedingungen **in den Aktionen** prüfen.
- Blueprint-Automationen bieten keine harte Garantie gegen konkurrierende Statuswechsel bei zeitgleichen Signalen. Schutzaktionen zuerst mit Benachrichtigungen testen.
- Das `for` von Triggern übersteht Neustarts nicht; der periodische Abgleich berücksichtigt dafür den Zeitpunkt der letzten Entitätszustandsänderung, soweit Home Assistant ihn bereitstellt.

## Geplante Erweiterungen

Mögliche Folgefeatures: Diagnosemodus mit Gründen für jeden blockierten Wechsel, getrennte Modi *Zuhause/Schlaf/Gast/Urlaub*, längere Türsequenzen und regelbasierte Kombinationen im UI, neustartfeste Zeitaktionen über `timer`, Push-Bestätigung vor Alarmaktivierung, sowie ein eigener Blueprint für gerichtete Tür-/Schleusensequenzen.
