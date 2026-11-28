# Tilesets, Tilemaps und Auto-Tiling

Das **Tilemap-System** macht aus einem Quellbild ein wiederverwendbares **Tileset** und lässt Sie mit
diesen Tiles große Levels auf einer **unendlichen Map mit mehreren Ebenen** malen: Sie teilen ein
Bild in indizierte Tiles auf, stempeln / radieren / füllen Zellen, lassen **Auto-Tiling** die Ränder
für Sie bestimmen, spiegeln und drehen Tiles beim Platzieren und **exportieren / importieren** die
gesamte Map als Tiled-kompatibles JSON. Jede Bearbeitung der Map ist ein einziger
Rückgängig-Schritt.

> **Logische gegenüber angezeigten Tiles.** Auto-Tiling trennt das Tile, das Sie *platzieren* (das
> **logische** Tile), von dem Tile, das *angezeigt* wird (dem **Anzeige-Tile**). Sie malen ein
> einziges „Wand“-Tile, und die Map wählt anhand der Nachbarn die passende Kanten- bzw. Eckvariante;
> die logische Platzierung ist das, was gespeichert wird und einen Roundtrip übersteht, sodass das
> Ergebnis **deterministisch und umkehrbar** ist. Wenn Sie Auto-Tiling ausschalten, wird direkt das
> logische Tile angezeigt.

## Tilesets

Ein **Tileset** ist ein Quellbild, das in ein Raster gleich großer Tiles aufgeteilt wird. Öffnen Sie
das Bedienfeld **Tileset-Editor** (Menü Tilemap) und fügen Sie mit **Tilemap ▸ Neues Tileset aus
Bild…** ein Tileset hinzu; beim Aufteilen liest die Anwendung das Bild mit Ihrer **Tile-Breite und Tile-Höhe**,
einem optionalen äußeren **Tile-Rand** und dem **Tile-Abstand** zwischen den Tiles und nummeriert die
entstehenden Tiles von links nach rechts und von oben nach unten, beginnend bei `0`.

- Jedes Tile ist ein Bereich des Quellpuffers, sodass einem Tileset **ein einziges Bild zugrunde
  liegt** statt vieler Kopien.
- **Das Bearbeiten eines Quell-Tiles überträgt sich** auf jede platzierte Instanz dieses Tiles in
  jeder Ebene – malen Sie das Tile einmal neu, und das ganze Level wird aktualisiert.
- Das Bedienfeld zeigt die aufgeteilten Tiles als Auswahlraster; das ausgewählte Tile ist dasjenige,
  das das Stempelwerkzeug malt.

> **Tile-Rand und Tile-Abstand.** `margin` (Tile-Rand) ist der Rand, der um das gesamte Bild herum übersprungen wird;
> `spacing` (Tile-Abstand) ist die Lücke, die **zwischen** den Tiles übersprungen wird. Tileset-Bilder, die
> mit einem 1 px breiten Zwischenraum exportiert wurden, brauchen in der Regel `spacing = 1` (und
> `margin = 1`, wenn der Zwischenraum auch den Bildrand umschließt), damit die Aufteilung genau auf
> jedem Tile landet.

## Eine Tilemap malen

Die **Tilemap-Arbeitsfläche** malt Zellen auf einem Raster, ein Tile pro Zelle. Wählen Sie im
Bedienfeld Tileset-Editor ein Tile aus und verwenden Sie dann die Map-Werkzeuge:

| Werkzeug | Was es bewirkt |
| --- | --- |
| **Stempelwerkzeug** | Platziert das ausgewählte Tile in der Zelle unter dem Cursor (ziehen, um eine Reihe zu malen). |
| **Tile-Radiergummi** | Leert die Zelle wieder. |
| **Rechteckfüllung** | Füllt ein aufgezogenes Rechteck mit dem ausgewählten Tile. |

Jedes Stempeln / Radieren / Füllen eines Rechtecks ist **genau ein Rückgängig-Schritt**, und
Rückgängig stellt die exakten vorherigen Zellen wieder her. Beim Malen neben bereits vorhandenen Tiles
wird die Nachbarschaft für **Auto-Tiling** neu bestimmt, sodass die Ränder beim Zeichnen korrekt
bleiben.

### Spiegeln und Drehen

Vor dem Stempeln können Sie das Tile transformieren: **Stempel horizontal spiegeln** und **Stempel
vertikal spiegeln** spiegeln es, und **Stempel 90° rechts drehen** schaltet es durch die vier
rechtwinkligen Ausrichtungen. Die Transformation wird pro platzierter Zelle als kompaktes Flag am Tile
gespeichert, sodass das Spiegeln oder Drehen eines Tiles **keine zusätzlichen Tileset-Einträge**
kostet und verlustfrei einen Roundtrip übersteht. Transformationen werden in fester Reihenfolge
kombiniert (erst diagonal, dann horizontal, dann vertikal), damit eine bestimmte Kombination immer
identisch dargestellt wird.

## Auto-Tiling

**Auto-Tiling** bestimmt das *angezeigte* Tile jeder Zelle anhand ihrer **acht Nachbarn** (das
Blob-47-Schema: eine Bitmaske über 8 Nachbarn, bei der eine Ecke nur zählt, wenn die angrenzenden
Kanten gesetzt sind, mit 47 verschiedenen Tiles). Malen Sie ein einziges „Gelände“-Tile, und die Map
füllt automatisch die passenden geraden Kanten sowie inneren und äußeren Ecken auf.

- **Schalten** Sie Auto-Tiling mit dem Kontrollkästchen **Auto-Tile (Blob-47)** im Bedienfeld
  Tilemap-Ebenen ein oder aus. Ist es **eingeschaltet**, werden beim Malen, Radieren oder Füllen eines
  Rechtecks auch die betroffenen Zellen **und deren Nachbarn** neu bestimmt, sodass der Rand stets
  konsistent ist – alles innerhalb desselben einen Rückgängig-Schritts.
- Die Bestimmung ist eine **reine, deterministische Funktion** der logischen Platzierung und der
  Nachbarn, sodass dieselbe Map stets dieselben Anzeige-Tiles darstellt.
- Wenn Sie Auto-Tiling **ausschalten**, wird direkt das von Ihnen platzierte logische Tile angezeigt,
  ohne Randbestimmung.

## Ebenen und unendliche Maps

Eine Tilemap hat **mehrere Ebenen** – stapeln Sie eine Hintergrund-, eine Gelände- und eine
Detailebene, die jeweils unabhängig bemalt werden – mit demselben Ebenenmodell wie der Rest des
Editors (hinzufügen / entfernen / umordnen / ein- und ausblenden). Das Bedienfeld **Tilemap-Ebenen**
verwaltet den Stapel; sichtbare Ebenen werden für die Anzeige zusammengesetzt.

Die Map selbst ist **unendlich**: Zellen werden als **dünn besetztes Raster aus 16×16-Chunks**
gespeichert, sodass nur die Bereiche Speicher belegen, die Sie tatsächlich bemalen. Sie können weit
vom Ursprung entfernt (in jede Richtung) stempeln, ohne die Map vorab zu dimensionieren, und leere
Bereiche kosten nichts. Jede Zelle ist eine 32-Bit-Tile-ID (GID), die den Tile-Index und die Flags zum
Spiegeln/Drehen trägt.

> **Darstellung großer Maps.** Jeder sichtbare Chunk wird einmal gerendert und zwischengespeichert;
> beim Verschieben der Ansicht werden die zwischengespeicherten Chunks wiederverwendet, statt sie neu
> zu zeichnen, sodass das Scrollen durch eine große Map flüssig bleibt. Das **erste** Zeichnen eines
> frisch sichtbaren Bereichs wird im Hintergrund vorgewärmt (außerhalb des GUI-Threads), damit das
> Fenster bedienbar bleibt, während es aufholt.

## Export und Import von Tiled-JSON

Die Map wird als **Tiled-kompatibles JSON** exportiert und lässt sich **verlustfrei** wieder
importieren – ein Roundtrip erhält die Ebenen, jede Zelle samt ihren Flags zum Spiegeln/Drehen sowie
alle Felder, die der Editor selbst nicht verwendet (unbekannte Felder werden unverändert
durchgereicht).

- **Export** (**Tilemap ▸ Tiled-JSON exportieren…**) schreibt eine gültige Tiled-Map, deren
  Ebenendaten als **CSV** vorliegen.
- **Import** (**Tilemap ▸ Tiled-JSON importieren…**) liest Tiled-Maps, die mit CSV oder mit
  Base64-Ebenendaten geschrieben wurden, welche unkomprimiert, mit gzip oder mit zlib komprimiert sind,
  und akzeptiert Verweise auf **externe Tilesets im Format `.tsj`**.
- Der Import ist ein **defensives, validiertes Laden**: Eine fehlerhafte Map, eine nicht unterstützte,
  mit **zstd** komprimierte Ebene oder ein Verweis auf **externe Tilesets im Format `.tsx`** werden mit
  einer klaren Fehlermeldung abgelehnt, statt abzustürzen oder Daten unbemerkt zu beschädigen.

> **Roundtrip-Treue.** Da unbekannte Felder den Roundtrip überstehen und die Flags zum Spiegeln/Drehen
> bitgenau erhalten bleiben, können Sie eine Map zwischen PixelArt Creator und Tiled hin- und
> herbewegen, ohne Daten zu verlieren, die das jeweils andere Programm hinzugefügt hat.

## Speicherung

Tilesets und Tilemaps werden verlustfrei in `.pixproj` gespeichert und wieder geladen. Wenn Sie ein
Projekt speichern und wieder öffnen, werden jedes Tileset (mit Quelle und Aufteilungskonfiguration)
und jede Tilemap (mit Ebenen, Zellen und den Flags zum Spiegeln/Drehen pro Zelle) identisch
wiederhergestellt. Projekte, die mit früheren Versionen gespeichert wurden (bevor es Tilemaps gab),
lassen sich weiterhin öffnen – sie werden einfach ohne Tilesets oder Tilemaps geladen.

## Rückgängig, Wiederholen und was *nicht* rückgängig zu machen ist

- **Rückgängig zu machen (jeweils ein Schritt):** eine Zelle stempeln / radieren, einen Bereich mit
  einer Rechteckfüllung füllen (einschließlich jeder Neubestimmung der Auto-Tile-Nachbarn) sowie eine
  Tilemap-Ebene hinzufügen / entfernen / umordnen / ein- und ausblenden.
- **Nicht rückgängig zu machen (Ansichtszustand):** ein Tile im Bedienfeld Tileset-Editor auswählen,
  Auto-Tiling umschalten, für den nächsten Stempel eine Spiegelung / Drehung wählen und die Map
  verschieben.

## Was nicht abgedeckt ist

- Mit **zstd komprimierte** Tiled-Ebenendaten und **externe Tilesets im Format `.tsx`** beim Import –
  bewusst abgelehnt (der Import akzeptiert CSV und Base64 (unkomprimiert, gzip oder zlib) sowie externe
  Tilesets im Format `.tsj`); verwenden Sie eine der unterstützten Kodierungen.
- **Wang-Tilesets für Ecken / Kanten** über das Blob-47-Schema mit 8 Nachbarn hinaus – die
  Auto-Tiling-Logik ist so entworfen, dass sie in einer späteren Phase darauf erweitert werden kann.
- **Animierte Tiles** und **Objektebenen** – für eine spätere Phase vorgesehen; diese Version deckt
  Tile-Ebenen ab.
