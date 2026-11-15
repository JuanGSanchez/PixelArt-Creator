# Export und Pipeline-Integration

Das **Exportsystem** macht aus einem Projekt die Assets, die eine Spiele-Pipeline weiterverarbeitet: ein
einzelnes **PNG**, ein **animiertes GIF**, ein **Sprite Sheet** oder einen dicht gepackten **Texturatlas**,
jeweils mit optionalen **JSON-Metadaten im Aseprite-Stil** und sofort einsetzbaren
**Engine-Voreinstellungen** für **Unity** und **Godot**. Sie können ein Ziel über den Export-Dialog
exportieren, mehrere über das Stapelexport-Bedienfeld in eine Warteschlange stellen oder alles ohne
grafische Oberfläche über die Befehlszeile `pixelart-export` ausführen – und jeder Weg erzeugt
**dieselben Bytes**. Den Export-Dialog öffnen Sie über **Datei ▸ Exportieren…** oder mit **Ctrl+Shift+E**.

> **Bytegenau reproduzierbarer Export.** Der Export ist **deterministisch**: Für ein unverändertes
> Eingabedokument und dieselben Parameter sind die Ausgabe-Bytes jedes Mal identisch – die Frames werden
> in fest vorgegebener Reihenfolge durchlaufen, das GIF verwendet eine feste, gemeinsame Palette ohne
> Dithering, und die Encoder sind auf feste Versionen festgelegt. GUI und CLI steuern **dieselbe**
> Export-Engine an, daher sind ein GUI-Export und ein CLI-Export desselben Dokuments
> **byteidentisch**. Die Garantie gilt *nur innerhalb derselben Umgebung* (festgelegte Toolchain), nicht
> über verschiedene Rechner hinweg.

| Tastenkürzel | Aktion |
| --- | --- |
| **Ctrl+Shift+E** | Den Export-Dialog öffnen. |

## Bildexport (PNG / GIF)

- **PNG** exportiert **Frame 0** (den ersten Frame) als einzelnes RGBA-Bild – das Ziel für Standbilder.
- **GIF** exportiert die Animation: jeden Frame der Reihe nach, jeweils für seine eigene
  **Dauer pro Frame** angezeigt (die Dauern, die Sie auf der [Animationszeitleiste](animation-timeline.md)
  festlegen), wobei die Anzahl der Wiederholungen, das Frame-Disposal und die Transparenz in die Datei
  geschrieben werden. Alle Frames teilen sich **eine feste Palette** (eine Farbreduktion nach dem
  Median-Cut-Verfahren über die gesamte Animation), und das Dithering ist **aus**, wodurch das GIF
  bytegenau reproduzierbar bleibt.

> **Anzahl der Wiederholungen beim GIF.** Die Option `--loop` (CLI) bzw. das Feld **Anzahl der
> Wiederholungen** (Dialog) legt fest, wie oft sich das GIF wiederholt; **`0` bedeutet: endlos
> wiederholen**.

## Sprite Sheets und Texturatlanten

- Ein **Sprite Sheet** legt jeden Frame zeilenweise auf einem **gleichmäßigen Raster** aus – Frame `k`
  liegt in Spalte `k % columns` und Zeile `k // columns`, mit einstellbarem **Abstand** zwischen den
  Sprites und ohne äußeren Rand. Mit der Spaltenzahl steuern Sie die Form des Sheets.
- Ein **Texturatlas** packt die Frames mit dem gemeinsamen **MaxRects**-Packer dicht aneinander (die
  Drehung ist ausgeschaltet, die Sprites bleiben also stets achsenparallel). Der Atlas ist die
  platzsparende Option, wenn sich die Frames in ihrem Inhalt unterscheiden.

> **Obergrenze der Atlasgröße.** Der Atlas ist auf die **8K**-Maximalabmessung der Plattform begrenzt.
> Passt ein Satz von Sprites nicht in diese Obergrenze, **bricht der Export sauber ab** und meldet einen
> klaren Atlas-Fehler (nie mit stiller Überlappung, abgeschnittenen Sprites oder einem Absturz) –
> verringern Sie den Abstand, die Frame-Größe oder die Anzahl der Frames und versuchen Sie es erneut.

## JSON-Metadaten

Exporte als Sprite Sheet und als Atlas können eine **JSON-Metadaten-Begleitdatei** im Format **Aseprite
*Array*** erzeugen: ein `frames[]`-Array (Rechteck, Quellgröße und Dauer jedes Frames) sowie einen
`meta{}`-Block mit den Frame-**Tags** und den Dauern pro Frame. Das JSON ist **deterministisch**:
Schlüssel sind sortiert, Trennzeichen fest und Koordinaten ganzzahlig. Dadurch übersteht es einen
Roundtrip und lässt sich sauber mit Diff-Werkzeugen vergleichen. Schalten Sie es mit dem
Kontrollkästchen **JSON-Metadaten schreiben** im Dialog ein oder aus oder verwenden Sie `--json` /
`--no-json` in der CLI (standardmäßig eingeschaltet).

## Engine-Voreinstellungen (Unity / Godot)

Neben dem Bild und dem JSON kann der Export eine **einsatzfertige Engine-Voreinstellung** schreiben,
sodass sich das Asset direkt in ein Projekt übernehmen lässt:

| Voreinstellung | Was geschrieben wird |
| --- | --- |
| **Unity** | Eine `.meta`-Begleitdatei für das Sprite – Sprite-Modus **Multiple**, `pixelsPerUnit`, Pivot und `filterMode = Point` (scharfe Pixel, keine bilineare Glättung). |
| **Godot** | Eine `SpriteFrames`-Ressource als `.tres`-Datei (Godot 4.2), aus den exportierten Frames aufgebaut. |

Wählen Sie die Voreinstellung im Dialog oder übergeben Sie `--preset unity` / `--preset godot` in der
CLI (`--preset none` – der Standard – schreibt keine Voreinstellung). Die Voreinstellungsdateien werden
deterministisch aus denselben Layout-Metadaten aufgebaut wie das Bild.

## Stapelexport

Das Bedienfeld **Stapelexport** stellt **mehrere Ziele auf einmal** in eine Warteschlange – zum Beispiel
ein PNG, ein GIF und einen Unity-Atlas aus einem Projekt in einem einzigen Durchlauf. Der Stapelexport
**läuft bei Fehlern weiter**: Schlägt ein Ziel fehl (etwa ein Atlas, der nicht passt), werden die
übrigen Ziele trotzdem exportiert, und der Fehler wird nur für dieses Ziel gemeldet – ein fehlerhaftes
Ziel bricht den Stapel also nie ab. Die Schaltfläche **Alle exportieren** exportiert das Dokument im
aktiven Tab in einem Durchlauf in alle Exportziele der Warteschlange.

## Eine exportierte Datei in der Bibliothek registrieren

Der Export-Dialog enthält das Kontrollkästchen **Auch zur Asset-Bibliothek hinzufügen**, das die
exportierte Datei im selben Schritt wie den Export in der [Asset-Bibliothek](asset-library.md)
registriert – eine Option zum Zuschalten, nicht die Standardeinstellung. Wenn Sie es aktivieren, öffnet
sich nach einem erfolgreichen Export der gemeinsame Dialog **Asset registrieren** (Name, Typ, Tags);
lassen Sie es deaktiviert, wird exportiert, ohne die Bibliothek überhaupt zu berühren – genau wie vor
Einführung dieser Option.

## Reaktionsfähigkeit

Die gesamte Exportarbeit läuft **außerhalb des GUI-Threads** in einem Hintergrund-Worker, hinter einer
**Fortschrittsanzeige mit Abbruchmöglichkeit** – das Exportieren einer großen Animation oder eines großen
Atlas friert das Fenster also nie ein. Der Export greift nur **lesend** auf Ihr Dokument zu: Er
verändert es nie und legt keinen Rückgängig-Schritt an.

> **Abbruch bei einem einzelnen großen Ziel.** Ein Abbruch greift zwischen den Zielen zügig; ein Abbruch
> **mitten in der Kodierung eines einzelnen großen Ziels** ist gröber – die gerade laufende Kodierung
> wird zu Ende geführt, bevor der Abbruch bemerkt wird.

## Die Befehlszeile `pixelart-export`

Für Automatisierung und CI führt `pixelart-export` **exakt denselben** Exportweg ohne grafische
Oberfläche aus – seine Ausgabe ist byteidentisch mit dem GUI-Export desselben Dokuments und derselben
Parameter. Es lädt die `.pixproj`-Datei über denselben abgesicherten, validierenden Projektlader, den
auch die Anwendung verwendet.

```
pixelart-export --input PROJECT.pixproj --format FORMAT --output OUT [options]
```

| Option | Bedeutung |
| --- | --- |
| `--input PATH` | **(erforderlich)** das zu exportierende `.pixproj`-Quellprojekt. |
| `--format FORMAT` | **(erforderlich)** eines von `png`, `gif`, `sprite-sheet`, `atlas`. |
| `--output PATH` | **(erforderlich)** der Pfad der Ausgabebilddatei. |
| `--preset PRESET` | Engine-Voreinstellung: `none` (Standard), `unity`, `godot`. |
| `--columns N` | Spaltenzahl des Sprite Sheets. |
| `--padding N` | Abstand zwischen den Sprites in Pixeln. |
| `--loop N` | Anzahl der GIF-Wiederholungen (`0` = endlos wiederholen). |
| `--tag NAME` | nur den Bereich eines benannten Frame-Tags exportieren (Standard: das gesamte Dokument). |
| `--json` / `--no-json` | die JSON-Begleitdatei für Sprite Sheet und Atlas ausgeben (Standard: an). |

**Exit-Codes:** `0` Erfolg; `1` ein Export-, Packing- oder Schreibfehler (zum Beispiel ein Atlas, der
nicht passt, oder ein Schreibfehler im Dateisystem); `2` ungültige Argumente oder ein fehlerhaftes bzw.
nicht lesbares Eingabeprojekt.

> **Derselbe Weg wie in der GUI.** Da CLI und Dialog dieselbe Engine aufrufen, können Sie einen Export
> interaktiv ausprobieren und ihn dann in einem Build-Skript exakt nachbilden, indem Sie dieselben
> Parameter als Optionen übergeben.

## Was nicht abgedeckt ist

- **APNG** (animiertes PNG) – **zurückgestellt**; diese Version exportiert PNG als Standbild (Frame 0)
  und animierte GIFs.
- **Maschinenübergreifend byteidentische** Ausgabe – die Garantie der Bytegenauigkeit gilt *nur innerhalb
  derselben Umgebung* (festgelegte Toolchain); die Toolchain eines anderen Rechners kann andere Bytes
  erzeugen.
- **Feingranularer Abbruch mitten in der Kodierung** eines einzelnen großen Ziels – ein Abbruch wird
  zwischen den Zielen bemerkt, nicht mitten in der Kodierung eines Ziels.

## Verwandte Themen

- Automatisieren Sie Exporte als Teil einer skriptgesteuerten Pipeline unter
  [Automatisierung und Skripting](automation-and-scripting.md).
