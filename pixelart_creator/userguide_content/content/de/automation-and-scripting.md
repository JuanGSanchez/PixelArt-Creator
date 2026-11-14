# Automatisierung, Makros, Skripte und Plugins

Das **Automatisierungssystem** ermöglicht es Ihnen, die eigenen Operationen des Editors aufzunehmen, zu
skripten, abzuspielen und stapelweise auszuführen, Inhalte prozedural zu erzeugen und die Anwendung um
Plugins zu erweitern, denen Sie vertrauen – alles über **eine** Engine, die die GUI und die headless
ausgeführte Befehlszeile `pixelart-run` gemeinsam nutzen. Eine Automatisierung läuft daher
**identisch** ab, ob Sie sie über ein Bedienfeld oder über ein Build-Skript auslösen.

> **Sicherheit durch Entwurf – kein `eval`, niemals.** Skripting ist eine **begrenzte, datengesteuerte
> Befehls-DSL** und kein beliebiges Python. Eine Automatisierung ist eine *validierte Liste von
> Operationen* (`{name, params, seed}`), niemals eine Sprache: Auf diesem Pfad gibt es
> **nirgends `eval` / `exec` / `compile` / `__import__` auf Ihre Eingabe** – es gibt keinen Interpreter,
> aus dem man ausbrechen könnte. Ein einziger vertrauenswürdiger Dispatcher prüft den Namen jeder
> Operation gegen eine **Positivliste** (Allowlist) und ihre Parameter gegen ein deklariertes Schema,
> bevor er den umkehrbaren Befehl aufbaut, auf den sie abgebildet wird.

## Makros – aufnehmen, abspielen und das Format `.pixmacro`

Das Bedienfeld **Makros** nimmt die Operationen auf, die Sie ausführen, und spielt sie später ab:

- **Makro aufnehmen** erfasst die *Eingaben* jedes Schritts – die aufgelösten Parameter und, bei jedem
  Schritt mit Zufallsanteil, den **Startwert** („seed“) – und keinen Pixel-Diff. Das Abspielen führt erneut
  aus, was Sie aufgenommen haben.
- **Abspielen** wendet die aufgenommenen Operationen auf das aktuelle Dokument als **einen einzigen
  Rückgängig-Schritt** erneut an, sodass Sie das gesamte Makro mit einem einzigen Rückgängig auf einmal
  zurücknehmen können.

Ein Makro wird als **`.pixmacro`**-Datei gespeichert – reines JSON mit einer versionierten Hülle:

```
{
  "format": "pixmacro",
  "schema_version": "1",
  "min_app_version": "0.8.0",
  "api_version": "1",
  "ops": [
    { "op": "batch_recolour", "params": { }, "seed": null },
    { "op": "procgen",        "params": { }, "seed": 12345 }
  ]
}
```

- **`schema_version` / `api_version` / `min_app_version`** werden beim Laden geprüft: Eine unbekannte
  oder nicht unterstützte Version **schlägt mit einer klaren Fehlermeldung fehl**, statt falsch
  abgespielt zu werden.
- **`params`** sind JSON-nativ, sodass das Speichern und anschließende Laden eines Makros ein
  **identisches** Makro ergibt – Farben und Index-Zuordnungen werden als Listen übertragen.
- **`seed`** wird für jeden Schritt mit Zufallsanteil aufgenommen, damit das Abspielen reproduzierbar
  ist.

> **Deterministisches Abspielen.** Wenn Sie dasselbe Makro zweimal auf demselben Ausgangsdokument
> abspielen, entsteht jedes Mal ein **zustandsidentisches** Dokument. Jeder Schritt mit Zufallsanteil
> bezieht seine Zufallswerte ausschließlich aus seinem aufgenommenen Startwert – keine Systemuhr, keine
> Zufallswerte ohne Startwert, keine Abhängigkeit vom Gebietsschema. Genau das macht ein Makro in einer
> Build-Pipeline sicher ausführbar.

Das Laden einer `.pixmacro`-Datei ist **abgesichert**: Jedes Feld wird auf Typ, Wertebereich und Version
geprüft, ein fehlerhaftes oder außerhalb der Grenzen liegendes Dokument löst einen klaren Fehler aus, und
der Inhalt wird **niemals** an `eval`/`exec` übergeben.

## Skripte ausführen

Die **Skriptausführung** leitet eine Liste von Operationen über denselben vertrauenswürdigen Dispatcher,
den auch das Abspielen eines Makros verwendet. Ein Skriptlauf ist **atomar**:

1. **Jede Operation wird vorab validiert** – alle Operationsnamen werden gegen die Positivliste und alle
   Parameter gegen ihr Schema geprüft, **bevor irgendetwas angewendet wird**.
2. Der gesamte Lauf wird als **ein gruppierter, umkehrbarer Befehl** angewendet.
3. Schlägt eine Operation mittendrin fehl, werden die bereits angewendeten Operationen **in umgekehrter
   Reihenfolge zurückgenommen**, sodass ein fehlgeschlagener Lauf mit mehreren Operationen das Dokument
   **unverändert** lässt – nie halb angewendet.

Da der Lauf ein gruppierter Befehl ist, ist ein abgeschlossenes Skript **ein einziger Rückgängig-Schritt**.

## Plugins – Verwaltung, Zustimmung und Vertrauensmodell

Das Bedienfeld **Plugins** erkennt, aktiviert und deaktiviert Plugins. Plugins erweitern den Editor,
indem sie neue DSL-Operationen registrieren – und nur das.

- **Das Auffinden hat keine Wirkung.** Installierte Plugins werden *gefunden* (über die
  standardmäßigen Python-Entry-Points), aber **nichts wird geladen oder ausgeführt**, nur weil sie
  installiert sind. Sie sehen sie aufgelistet; sie tun nichts, bis Sie handeln.
- **Standardmäßig verweigert, mit ausdrücklicher Zustimmung.** Beim Aktivieren erhält ein Plugin ein
  **Capability-Objekt, dessen einzige Schnittstelle die DSL-Befehlsregistrierung ist** (ein Objekt, das
  festlegt, was das Plugin über die Anwendung tun darf). Über dieses
  Objekt kann ein Plugin nichts tun, was es nicht deklariert hat – **jede nicht deklarierte Capability
  wird verweigert**. Sie genehmigen die deklarierten Berechtigungen eines Plugins als Ganzes, oder Sie
  aktivieren es nicht. Das Aktivieren eines Plugins im Bedienfeld führt den Code des Plugins nicht selbst
  aus. Seine Operationen liegen im Namensraum des Plugins, sodass ein Plugin keine eingebaute Operation
  überdecken kann. Das begrenzt, was das Plugin *über die Anwendung* tun kann; den eigenen Code des
  Plugins schränkt es nicht ein (siehe den Hinweis unten).
- **Deaktivieren räumt sauber auf.** Beim Deaktivieren eines Plugins werden die von ihm hinzugefügten
  Operationen wieder entfernt.

> **Vertrauen und Zustimmung – in dieser Version.** Weil schon das *Laden* eines Python-Plugins das
> Ausführen von Code ist, ist das prozessinterne Capability-Modell nur ein **unverbindlicher** Schutz
> und keine harte Sicherheitsgrenze: Es begrenzt, was ein Plugin über die Anwendung tun kann, nicht
> aber, was der eigene Code des Plugins tun kann. Es genügt für **Erweiterungen, denen Sie vertrauen,
> die Sie selbst installieren und denen Sie zustimmen**, nicht für beliebigen Code aus einem nicht
> vertrauenswürdigen Marktplatz. Der Code eines Plugins läuft im selben Prozess wie der Editor, mit
> demselben Zugriff auf Ihre Dateien und das Netzwerk wie die Anwendung selbst. Installieren Sie nur
> Plugins, denen Sie vertrauen.

## Stapelumfärbung

Die **Stapelumfärbung** wendet eine Farbzuordnung auf **viele Ziele auf einmal** an, als **ein einziger
transaktionaler, umkehrbarer Befehl**:

- Bei **indizierten** Zielen werden Palettenindizes neu zugeordnet (`old_index → new_index`); bei
  **RGBA**-Zielen werden Farben neu zugeordnet (`old_rgba → new_rgba`). Sie nutzt die vorhandenen
  Umfärbungsoperationen des Editors, sodass ein gestapeltes Ziel **byteidentisch** mit der
  Einzelumfärbung dieses Ziels bei derselben Zuordnung ist.
- Sie ist **transaktional**: Jedes Ziel wird validiert und sein Einzelschritt aufgebaut, **bevor
  irgendetwas angewendet wird**. Ein ungültiges Ziel schlägt unter Nennung des betreffenden Ziels fehl,
  mit **null Änderungen**. Der gesamte Stapel ist **ein Rückgängig-Schritt**.

## Prozedurale Generierung

Das Bedienfeld **Prozedurale Generierung** füllt einen Bereich mit erzeugten Inhalten. Es stehen fünf
hauseigene, **startwertgesteuerte** Generatoren zur Verfügung:

| Generator | Was er erzeugt |
| --- | --- |
| **Value-Rauschen** | Rauschen auf einem Wertraster, mit Startwert. |
| **Gradientenrauschen** | Gradientenrauschen im Perlin-Stil. |
| **OpenSimplex-Rauschen** | Ein patentsicheres Gradientenrauschen auf einem Simplex-Raster. |
| **Zelluläre Automaten** | Muster aus zellulären Automaten. |
| **Farbverlauf mit Dithering** | Ein sanfter Zwei-Farben-Verlauf, per Dithering auf die Dokumentpalette abgebildet, sodass das Ergebnis innerhalb der Palette bleibt. |

Jeder Generator ist eine **reine, deterministische Funktion seiner Parameter und seines Startwerts** –
derselbe Startwert und dieselben Parameter erzeugen immer dieselbe Ausgabe. Erzeugte Inhalte werden über
den **Pfad der umkehrbaren Befehle** geschrieben, daher ist jede Generierung ein einziger
Rückgängig-Schritt. Die Ausgabe ist pro Achse durch die Maximalgröße der Plattform für die prozedurale
Generierung begrenzt.

## Umkehrbarkeit und Reaktionsfähigkeit

Jede Automatisierung – das Abspielen eines Makros, ein Skriptlauf, eine Stapelumfärbung, eine
prozedurale Füllung – landet als **ein Schritt auf dem normalen Rückgängig-Stapel**, sodass Sie jede davon
zurücknehmen können. In der GUI läuft die Automatisierung in einem **Hintergrund-Worker-Thread** mit
deterministischem Aufräumen, sodass ein langer Stapel oder eine große prozedurale Füllung das Fenster
nicht einfrieren lässt.

## Die Befehlszeile `pixelart-run`

Für Automatisierung und CI spielt `pixelart-run` eine `.pixmacro`-Datei auf eine `.pixproj`-Datei
**headless** (ohne GUI) ab, und zwar über **exakt denselben** vertrauenswürdigen Dispatcher, den auch die
GUI verwendet – das entstehende Dokument ist daher **zustandsidentisch** mit dem, das die GUI bei
derselben Automatisierung auf derselben Eingabe erzeugt.

```
pixelart-run --input PROJECT.pixproj --macro MACRO.pixmacro --output OUT.pixproj [options]
```

| Option | Bedeutung |
| --- | --- |
| `--input PATH` | **(erforderlich)** das Quellprojekt `.pixproj`, auf dem das Makro ausgeführt wird. |
| `--macro PATH` | **(erforderlich)** das abzuspielende Makro `.pixmacro`. |
| `--output PATH` | **(erforderlich)** der `.pixproj`-Pfad, in den das Ergebnis geschrieben wird. |
| `--seed N` | den Startwert für Operationen überschreiben, die keinen aufgenommen haben (ein aufgenommener Startwert hat immer Vorrang). |
| `--param KEY=VALUE` | einen Makroparameter einfügen oder überschreiben; wiederholbar. |

**Exit-Codes:** `0` Erfolg; `1` ein Automatisierungsfehler (ein Fehler bei Skript, Makro, Plugin, Stapel
oder prozeduraler Generierung oder ein Schreibfehler); `2` ungültige Argumente oder ein fehlerhaftes bzw.
nicht lesbares Eingabeprojekt oder Makro.

> **Konsolen-Einstiegspunkt.** `pixelart-run` wird bei `pip install` als Konsolenskript installiert.

## Was nicht abgedeckt ist

- **Beliebiges Python-Skripting** – **konstruktionsbedingt nicht unterstützt.** Skripting ist eine
  begrenzte DSL aus Befehlen auf einer Positivliste, kein Allzweck-Interpreter; das ist eine bewusste
  Sicherheitsgrenze, keine Einschränkung, die aufgehoben werden soll.
- **Isolierung nicht vertrauenswürdiger Plugins von Drittanbietern** – **zurückgestellt.** Plugins sind in
  dieser Version auf Ihr Vertrauen und Ihre Zustimmung angewiesen; installieren Sie nur Plugins, denen
  Sie vertrauen.

## Verwandte Themen

- Automatisierungen setzen dieselben Operationen zusammen, die Sie von Hand ausführen – siehe
  [Ebenen](layers.md), [Export](export-and-pipeline.md) und die [Farbzentrale](colour-hub.md).
