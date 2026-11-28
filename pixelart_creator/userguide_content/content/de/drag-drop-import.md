# Import per Drag-and-drop

Ziehen Sie eine Datei direkt aus dem Datei-Explorer Ihres Betriebssystems (Windows Explorer, macOS
Finder, Linux Nautilus) **in** das Fenster von PixelArt Creator, und die Anwendung tut für diese Art
von Datei das Naheliegende. Ein Umweg über Datei ▸ Öffnen… ist nicht nötig – legen Sie die Datei
einfach irgendwo im Fenster ab, und die Anwendung leitet sie **nach Dateityp** weiter, nicht danach,
an welcher Stelle des Fensters Sie loslassen.

> **Die Weiterleitung richtet sich nach dem Typ, nie nach dem Ablageort.** Ein Bild öffnet sich
> *immer* als neues Dokument, eine `.pixproj`-Datei *immer* als Projekt, und eine Palettendatei wird
> *immer* in die aktive Palette geladen – unabhängig davon, wo im Fenster Sie sie ablegen. In einem
> einzigen Ablegevorgang können Sie Typen mischen und sogar mehrere Dateien auf einmal ablegen.

## Ein Bild ablegen → ein neuer Dokument-Tab

Legen Sie eine Datei vom Typ **`.png`, `.jpg`, `.jpeg`, `.bmp` oder `.gif`** ab, und sie öffnet sich
als **brandneue Arbeitsfläche / ein neuer Dokument-Tab**, der aktiv wird. Sie wird als neues Dokument
importiert, **nicht** als Ebene des Dokuments, das Sie gerade bearbeiten – Ihr aktuelles Dokument
bleibt unberührt.

- Das neue Dokument ist **RGBA** und hat die Breite und Höhe des Bildes. Ein PNG oder GIF mit Palette
  (indiziert) wird beim Import in RGBA umgewandelt.
- Bei einem **animierten GIF** wird der **erste Frame** importiert.
- Der Import greift auf dem Datenträger **nur lesend** zu – das Ablegen einer Datei verändert die
  Quelle nie.

> **Größenbeschränkung für Bilder.** Ein Bild, das größer ist als das Maximum der Arbeitsfläche
> (**7680 × 4320**), wird mit einer Fehlermeldung **abgelehnt** – es wird nie stillschweigend
> zugeschnitten oder skaliert. Konvertieren Sie es zuerst außerhalb der Anwendung oder ändern Sie
> dort seine Größe.

## Eine `.pixproj`-Datei ablegen → das Projekt öffnen (mit Abfrage bei nicht gespeicherten Änderungen)

Legen Sie eine **`.pixproj`**-Datei ab, und sie öffnet sich als Projekt.

Enthält das Dokument, das Sie gerade bearbeiten, **nicht gespeicherte Änderungen**, zeigt die
Anwendung zuerst eine Abfrage mit **Speichern / Verwerfen / Abbrechen**, damit Sie nie versehentlich
Arbeit verlieren:

| Auswahl | Ergebnis |
| --- | --- |
| **Speichern** | Speichert das aktuelle Dokument und öffnet dann das abgelegte Projekt. |
| **Verwerfen** | Öffnet das abgelegte Projekt ohne Speichern. |
| **Abbrechen** | Bricht das Öffnen ab – nichts ändert sich. |

Hat das aktuelle Dokument **keine** nicht gespeicherten Änderungen (oder ist keines geöffnet), öffnet
sich das Projekt sofort ohne Abfrage.

## Eine Palette ablegen → in die aktive Palette laden (rückgängig zu machen)

Legen Sie eine Palettendatei vom Typ **`.gpl` (GIMP), `.hex` (einfache Hex-Liste) oder `.pal`
(JASC-PAL-Text)** ab, und ihre Farben **ersetzen** die Palette Ihres aktiven Dokuments.

- Der Austausch ist **ein einziger rückgängig zu machender Schritt**: Ein einmaliges **Rückgängig**
  stellt Ihre vorherige Palette exakt wieder her.
- Ist kein Dokument geöffnet, bleibt das Ablegen ohne Wirkung und ist unbedenklich; es erscheint ein
  kurzer Hinweis.

> **Welche Palettenformate?** Unterstützt werden die gängigen **Textformate** für Pixelart: `.gpl`,
> `.hex` und `.pal`. Die Binärformate **`.aco`** (Adobe) und **`.aseprite`** (das eigene Format von
> Aseprite) werden **noch nicht unterstützt** – sie werden vorerst als nicht unterstützter Typ
> gemeldet.

## Mehrere Dateien auf einmal ablegen

Beim Ablegen mehrerer Dateien wird jede Datei **unabhängig, nach ihrem Typ und in der Reihenfolge des
Ablegens** verarbeitet:

- mehrere Bilder → mehrere neue Tabs;
- eine `.pixproj`-Datei wird geöffnet (unter Beachtung ihrer Abfrage bei nicht gespeicherten Änderungen);
- Paletten werden nacheinander geladen – die **zuletzt** abgelegte Palette ist am Ende die aktive
  (jede ist ein eigener Rückgängig-Schritt).

Eine unbekannte oder nicht lesbare Datei im Stapel wird mit einem Hinweis übersprungen; die übrigen
werden weiterhin verarbeitet. Wenn keine Dateien abgelegt werden, passiert nichts.

## Wenn sich eine Datei nicht importieren lässt

Drag-and-drop bringt die Anwendung nie zum Absturz:

- ein **nicht unterstützter Typ** (zum Beispiel eine `.txt`-Datei oder eine Palette vom Typ `.aco` oder
  `.aseprite`) wird mit einem kurzen, nicht blockierenden Hinweis in der Statusleiste **ignoriert**;
- bei einem **beschädigten, nicht dekodierbaren oder zu großen** Bild, einer **fehlerhaften** Palette
  oder einer **ungültigen** `.pixproj`-Datei erscheint eine **Fehlermeldung**, die die Datei und das Problem
  nennt, und Ihre Arbeit bleibt **genau so, wie sie war** – kein halb angelegter Tab, keine halb
  geladene Palette.

Alle Abfragen und Hinweise sind übersetzbar, per Tastatur erreichbar und im hellen wie im dunklen
Design gut lesbar.

## Was nicht abgedeckt ist

- **Import als Ebene** – ein Bild öffnet sich immer als neues Dokument, nie als Ebene des aktuellen.
- **Indizierter Import** eines Quellbilds mit Palette – Bilder werden als RGBA dekodiert; wenden Sie
  anschließend **Palette ▸ In Indexfarben konvertieren** an (siehe
  [Das Ebenenbedienfeld](layers.md)), wenn Sie ein indiziertes Dokument möchten.
- **Import animierter GIFs** – es wird nur der erste Frame importiert.
- Das **Exportieren und Speichern** über die Pipeline – siehe
  [Export und Pipeline-Integration](export-and-pipeline.md).
