# Automatisierung, Makros, Skripte und Plugins

Das **Automatisierungssystem** ermöglicht es Ihnen, die eigenen Operationen des Editors aufzunehmen, zu
skripten, abzuspielen und stapelweise auszuführen sowie Inhalte prozedural zu erzeugen –
alles über **eine** Engine, die die GUI und die headless ausgeführte
Befehlszeile `pixelart-run` gemeinsam nutzen. Eine Automatisierung läuft daher
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

Das Bedienfeld **Plugins** listet Plugins auf, zeigt die Berechtigungen jedes Plugins an, dessen
Manifest Sie geladen haben, und aktiviert und deaktiviert sie. Ein Plugin soll den Editor erweitern,
indem es neue DSL-Operationen registriert. **In dieser Version hat die Anwendung keinen Vorgang, der
den Code eines Plugins lädt oder ausführt:** Das Auffinden eines Plugins, das Laden eines Manifests
sowie das Aktivieren und das Deaktivieren rufen nie ein Plugin auf. Die Berechtigungen, die ein
Manifest deklariert, beschreiben die beabsichtigte Verwendung des Plugins; sie sind keine Begrenzung
dessen, was der Code des Plugins selbst tun kann (siehe den Hinweis unten).

- **Das Auffinden listet Plugins nur auf.** Die Anwendung findet installierte Plugins über die
  standardmäßigen Python-Entry-Points, liest aber nur deren Namen und Versionen: Der Code dieser
  Plugins wird **nicht** geladen oder ausgeführt. Ein gefundenes Plugin zeigt keine Berechtigungen und
  lässt sich nicht aktivieren, weil die Anwendung Berechtigungen nicht aus dem Plugin selbst liest. Die
  Berechtigungen stammen aus einer Manifestdatei, die Sie von einem Datenträger zum Bedienfeld
  hinzufügen und die dort als eigener Eintrag in der Liste erscheint. Die Anwendung prüft nicht, ob ein
  Manifest zu einem Plugin gehört, das Sie installiert haben.
- **Ihre Zustimmung bezieht sich auf das Manifest, nicht auf den Code des Plugins.** **Aktivieren**
  zeigt die Berechtigungen an, die das Manifest deklariert, und bittet Sie um Bestätigung. Sie
  genehmigen die Berechtigungen als Ganzes, oder Sie aktivieren das Plugin nicht. Die Anwendung gleicht
  das Manifest nicht mit dem ab, was der Code des Plugins tatsächlich tut. Das Aktivieren hält die
  Berechtigungen, die Sie genehmigt haben, im Arbeitsspeicher fest und markiert das Plugin als
  aktiviert; es führt den Code des Plugins nicht aus, weil die Anwendung keinen Vorgang hat, der das
  tut. Ihre Zustimmung wird nicht gespeichert: Beim Schließen des Editors ist jedes Plugin wieder
  deaktiviert. Der Plugin-Host ist so programmiert: Gäbe ihm ein Aufrufer Code, der beim Aktivieren
  eines Plugins ausgeführt werden soll, so würde dieser Code ein Berechtigungsobjekt erhalten, und ein
  Aufruf über dieses Objekt, für den keine Berechtigung erteilt wurde, würde abgelehnt; in dieser
  Version übergibt ihm nichts derartigen Code. Über dieses Objekt registrierte Operationen erhalten den
  Namen des Plugins als Präfix, sodass sie nicht mit dem Namen einer eingebauten Operation
  übereinstimmen können, und eine Leseberechtigung über dieses Objekt liefert das übergebene Dokument
  selbst zurück, nicht eine Kopie. Code, der nicht über das Objekt läuft, wird davon nicht begrenzt: Er
  kann Operationen direkt registrieren oder entfernen, auch eingebaute.
- **Deaktivieren entfernt Operationen, nicht den Code des Plugins.** **Deaktivieren** hebt die
  Registrierung der Operationen auf, die über das Berechtigungsobjekt registriert wurden; in dieser
  Version gibt es keine, weil nichts welche registriert. Es macht nichts rückgängig, was der Code eines
  Plugins bereits getan hat.

> **Plugins sind nicht in einer Sandbox gekapselt.** Ein Plugin ist nicht von Ihrem Computer isoliert,
> und die Anwendung bietet in dieser Version für kein Plugin eine Isolierung. Die Installation eines
> Plugins bringt fremden Python-Code auf Ihren Computer, und die Anwendung führt die Installation weder
> durch noch prüft sie diese. Eine Python-Distribution kann Python außerdem darum bitten, bei jedem
> Start von Python in der Umgebung, in der diese Distribution installiert ist und zu der der Editor
> gehört, Code auszuführen, sodass das Installieren eines Plugins genügen kann, damit dessen Code
> ausgeführt wird, auch wenn Sie das Bedienfeld **Plugins** nie öffnen. Code, der im Prozess des
> Editors läuft, hat – gleichgültig, wie er dorthin gelangt ist – denselben Zugriff auf Ihre Dateien
> und das Netzwerk wie der Editor selbst, unabhängig davon, welche Berechtigungen das Plugin
> deklariert hat. Installieren und aktivieren Sie nur Plugins, denen Sie vertrauen.

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

**Exit-Codes:** `0` Erfolg; `1` ein Automatisierungsfehler (ein Fehler bei Skript, Makro, Stapel
oder prozeduraler Generierung oder ein Schreibfehler); `2` ungültige Argumente oder ein fehlerhaftes bzw.
nicht lesbares Eingabeprojekt oder Makro.

> **Konsolen-Einstiegspunkt.** `pixelart-run` wird bei `pip install` als Konsolenskript installiert.

## Was nicht abgedeckt ist

- **Beliebiges Python-Skripting** – **konstruktionsbedingt nicht unterstützt.** Skripting ist eine
  begrenzte DSL aus Befehlen auf einer Positivliste, kein Allzweck-Interpreter; das ist eine bewusste
  Sicherheitsgrenze, keine Einschränkung, die aufgehoben werden soll.
- **Isolierung nicht vertrauenswürdiger Plugins von Drittanbietern** – **zurückgestellt.** Plugins sind in
  dieser Version nicht in einer Sandbox gekapselt; installieren und aktivieren Sie nur Plugins, denen
  Sie vertrauen.

## Verwandte Themen

- Automatisierungen setzen dieselben Operationen zusammen, die Sie von Hand ausführen – siehe
  [Ebenen](layers.md), [Export](export-and-pipeline.md) und die [Farbzentrale](colour-hub.md).
