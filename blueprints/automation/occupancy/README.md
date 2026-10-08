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
- **Zusätzliche Sperren:** Gastmodus, Schlafmodus, weitere Präsenzsensoren und frei konfigurierbare Bedingungen. Unbekannte/nicht erreichbare Sicherheitssensoren verhindern Abwesenheit. Wenn der Schlafmodus aktiviert wird, setzt er den Bereich auf **belegt**.
- **Aktionen:** Die Action-Editoren akzeptieren beliebige Home-Assistant-Aktionen, Skripte und Bedingungen; keine feste Bindung an Lichter, Alarmanlagen oder Medienplayer.
- **Zeitaktionen:** Bei Ankunft kann eine bedingte Aktion ausgelöst und nach N Minuten eine Folgeaktion ausgeführt werden. Mit zwei optionalen Helfern übersteht der Auftrag einen Home-Assistant-Neustart.
- **Diagnose:** Optionaler `input_text`-Helfer zeigt an, warum Abwesenheit blockiert ist (z. B. Gästemodus, Tracker zu Hause, Sensor nicht verfügbar oder Mindestzeit noch nicht erreicht). Dazu existieren Automations-Traces und optional Systemlogeinträge für abgelehnte Abwesenheitsereignisse.
- **Neustart/Reload:** Alle fünf Minuten sowie beim HA-Start wird der Belegungszustand abgeglichen. Persistente Folgeaktionen werden zusätzlich einmal pro Minute auf Fälligkeit geprüft. Ohne die zwei Helfer bleibt die bisherige, nicht neustartfeste `delay`-Variante verfügbar.

## Installation und Einrichtung

1. [Import-Link](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2F3115a083%2Fha-blueprints%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Foccupancy%2Farea_occupancy_manager.yaml) öffnen, oder in HA unter **Einstellungen → Automatisierungen & Szenen → Blueprints → Blueprint importieren** die [GitHub-YAML-URL](https://github.com/3115a083/ha-blueprints/blob/main/blueprints/automation/occupancy/area_occupancy_manager.yaml) einfügen.
2. Unter **Einstellungen → Geräte & Dienste → Helfer** einen **Umschalter** für den Bereich anlegen, z. B. `input_boolean.haus_belegt`. Vor dem Start auf den tatsächlichen Zustand setzen.
3. Blueprint-Automatisierung anlegen und den Umschalter in **01 | Belegungsstatus** auswählen. Es empfiehlt sich, zuerst nur harmlose Aktionen oder Benachrichtigungen einzurichten.
4. Tracker und/oder Bewegung-/Präsenzsensoren zuordnen. Für ein gesamtes Haus alle regulären Bewohner auswählen und einen separaten Gastmodus-Helfer anlegen.
5. Zusätzliche Präsenzsperren, Abwesenheits- und Ankunftsaktionen konfigurieren. Mit tatsächlicher Bewegung, An- und Abwesenheit sowie bei nicht verfügbaren Sensoren testen.
6. Optional die Helfer und Einstellungen für Schlafmodus, Diagnose und persistente Zeitaktionen ergänzen. Die neuen Eingaben haben Standardwerte, bestehende Blueprint-Instanzen funktionieren daher ohne Nachkonfiguration weiter.

### Schlafmodus für bewegungslose oder schlafende Personen

Unter **03 | Schutz vor Fehlentscheidungen** optional einen zusätzlichen `input_boolean` wählen, z. B. `input_boolean.schlafen`. Diesen Helfer durch eine eigene Bettzeit-Automation, einen Bettsensor oder manuell setzen:

- **EIN:** Bereich bleibt automatisch belegt. Einschalten stellt den Belegungsstatus her, auch wenn sonst kein Tracker bzw. Bewegungsmelder eine Person erkennt.
- **AUS:** Die normalen Abwesenheitsregeln greifen wieder. Es erfolgt **kein** automatischer Leer-Status allein durch das Ausschalten des Schlafmodus. Die Signale müssen weiterhin ausreichen.
- **unknown/unavailable:** Abwesenheit wird sicherheitshalber gesperrt. Der Status wird aber nicht als neue Ankunft gewertet.

Der Schlafmodus ist eine explizite Sperre, keine automatische Erkennung von Schlaf. Wenn du keinen Schlafmodus einschaltest und ausschließlich PIR-Sensoren verwendest, lässt sich unbewegte Anwesenheit technisch nicht sicher erkennen.

### Diagnosemodus

Unter **04 | Diagnose** den Diagnosemodus aktivieren. Optional zuvor einen **Text-Helfer (`input_text`)** mit maximal **255 Zeichen** anlegen und auswählen, z. B. `input_text.belegung_diagnose`. Den Helfer auf einem Dashboard anzeigen. Der Text aktualisiert sich bei Änderungen relevanter Zustände, beim periodischen Abgleich und bei relevanten Triggern, sofern er sich verändert hat. Die angezeigten Gründe enthalten zum Beispiel:

- `BELEGT | Abwesenheit gesperrt: Gästemodus=on`
- `BELEGT | Abwesenheit gesperrt: person.gast=home`
- `BELEGT | Abwesenheit gesperrt: binary_sensor.schlafzimmer=unavailable`
- `BELEGT | Abwesenheit gesperrt: Inaktivitätsdauer läuft`

In den Automations-Traces erscheinen außerdem die berechneten Variablen (`diagnostic_line`, `absence_evidence_ok`, `sleep_clear` usw.). Optional können abgewiesene Abwesenheitstrigger ins Systemprotokoll geschrieben werden. **Grenze:** Frei definierte `away_conditions` lassen sich nicht automatisch einzeln als Grund aufschlüsseln. Die Diagnose kann also "Abwesenheit möglich" anzeigen, obwohl eine Zusatzbedingung die finale Statusänderung verhindert.

### Türfolge konfigurieren

In **05 | Türen** zwei `binary_sensor`-Türkontakte wählen. `Tür 1 → Tür 2` innerhalb von 30 s (änderbar) gilt als Abgang; `Tür 2 → Tür 1` als Ankunft. Entscheidend ist, dass **der zweite Kontakt erst nach dem ersten auslöst**. Nicht geeignet für Türen, die normalerweise offen stehen, oder bei denen die Bewegungsrichtung nicht eindeutig ist. Ein alleiniger Öffnungsimpuls gilt nicht als abgeschlossene Folge.

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

### Bei Ankunft Garage öffnen, nach 40 Minuten schließen, auch nach Neustart

Unter **07 | Zeitlich begrenzte Ankunftsaktionen**:

1. Zwei Helfer unter **Einstellungen → Geräte & Dienste → Helfer** anlegen: `input_datetime.garage_schliesszeit` **mit Datum UND Uhrzeit**, dazu `input_boolean.garage_zeitaktion_aktiv` (anfänglich **AUS**). Beide in **Neustartfest: Ablaufzeitpunkt** und **Vorgang aktiv** auswählen.
2. **Temporäre Aktionen aktivieren** auf EIN setzen.
3. **Startbedingungen:** z. B. Handy ist per Bluetooth mit dem Auto verbunden. Am besten zusätzlich die Heimfahrt mit einem Tracker bestätigen lassen.
4. **Startaktionen:** `cover.open_cover` für das Garagentor.
5. **Dauer:** `40` Minuten.
6. **Folgebedingungen:** Mindestens Torstatus und Hindernis-/Lichtschrankensensoren prüfen. Bei ungeklärtem Zustand nicht schließen.
7. **Folgeaktionen:** `cover.close_cover` für das Garagentor.

**Ablauf:** Bei einer gültigen Ankunft speichert der Blueprint **vor** der Startaktion den Zeitpunkt `jetzt + 40 Minuten` im `input_datetime` und setzt den Vorgang-Helfer EIN. Nach dem Ablauf wird der Auftrag maximal ungefähr eine Minute später verarbeitet, auch wenn Home Assistant inzwischen neu gestartet wurde. Ist HA während der Fälligkeit offline, wird die Aktion nach dem nächsten HA-Start nachgeholt. Bevor die Folgeaktion beginnt, wird der Auftrag AUS geschaltet und werden die konfigurierten Sicherheitsbedingungen erneut geprüft. Sind diese **nicht** erfüllt, wird die Folgeaktion **einmalig übersprungen** und der Auftrag nicht automatisch wiederholt. Eine erneute Ankunft während eines offenen Auftrags setzt den Ablaufzeitpunkt neu.

Beide Helfer gemeinsam und **pro Blueprint-Instanz getrennt** konfigurieren. Ist nur einer angegeben, startet der Blueprint **keine** temporäre Aktion. Lässt du **beide** leer, bleibt die bisherige `delay`-Variante aus Kompatibilitätsgründen verfügbar. Diese ist **nicht** neustartfest. Für eine sicherheitskritische Garage unbedingt unabhängigen Hindernisschutz nutzen. Das Hantieren mit `input_datetime`/`input_boolean` im Dashboard kann aktive Aufträge überschreiben, daher beide Helfer vor ungewollten Eingriffen schützen.

Die Wiederherstellung des Helferzustands setzt voraus, dass die Helfer **ohne feste `initial`-Werte** angelegt wurden. Das `input_datetime` muss Datum und Uhrzeit enthalten. Ein aktiver Auftrag kann durch manuelles Ausschalten des Vorgang-Helfers bewusst abgebrochen werden.

## Wichtige Sicherheitsregeln

- `unknown`/`unavailable` bei einem gewählten Tracker, Aktivitäts- oder Sperrsensor darf **nicht** als positive Abwesenheit gewertet werden. Deshalb bleibt das System in diesem Fall eher belegt.
- Gewählte Tracker auf `home` und erkannte Bewegung/Präsenz blockieren **auch bei Kombinationsmodus `EINES`** das automatische Leerschalten.
- Ein **Gastmodus** ist nötig, wenn Personen außerhalb der regulär getrackten Bewohner im Bereich bleiben können und Sensoren deren Anwesenheit nicht dauerhaft melden.
- **Schlafmodus** und Gastmodus verhindern automatische Abwesenheit auch dann, wenn alle Bewegungsmelder ruhig sind.
- Eine **manuelle** Umschaltung des Belegungshelfers ist bewusst ein explizites Override und führt trotz Gastmodus zu Aktionen. Den Helfer nicht ungeschützt auf öffentlichen Dashboards platzieren.
- Bei verschlossener Tür oder aktivierter Alarmanlage nach Möglichkeit Tür-/Fensterkontakte, Riegelstatus und konkrete Alarmbedingungen **in den Aktionen** prüfen.
- Blueprint-Automationen bieten keine harte Garantie gegen konkurrierende Statuswechsel oder doppelte Aktionsausführung bei genau gleichzeitigen Signalen. Bei einem neustartfesten Termin wird das `pending`-Flag vor der Folgeaktion gelöscht. Für gefährliche Aktoren eine zusätzliche Verriegelung oder ein dediziertes Skript verwenden. Schutzaktionen zuerst mit Benachrichtigungen testen.
- Das `for` von Triggern übersteht Neustarts nicht; der periodische Abgleich berücksichtigt dafür den Zeitpunkt der letzten Entitätszustandsänderung, soweit Home Assistant ihn bereitstellt.

## Mögliche Erweiterungen

Längere Türsequenzen, detaillierte Diagnosen für benutzerdefinierte Bedingungen, regelbasierte Verknüpfungen im UI, Urlaubmodus, Push-Bestätigung vor Alarmaktivierung sowie ein eigener Blueprint für gerichtete Tür-/Schleusensequenzen.
