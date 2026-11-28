# Mischmodi

Jede Ebene (und Gruppe) wird mit einem **Mischmodus** zusammengesetzt, den Sie in der Auswahlliste
der jeweiligen Ebene im [Ebenenbedienfeld](layers.md) wählen. PixelArt Creator bringt **zwölf**
Modi mit – **Normal** sowie die elf übrigen **separablen** Modi aus der W3C-Spezifikation
*Compositing and Blending Level 1* (dieselbe Auswahl und dieselben Ergebnisse wie in
Photoshop / Krita / SVG).

Das Mischen erfolgt mit **direktem (nicht vormultipliziertem) Alpha** in einem normalisierten
Gleitkomma-Arbeitsraum und wird anschließend als 8-Bit-RGBA zurückgeschrieben. **Normal** ist
direktes Source-over-Alpha-Compositing.

## Die zwölf Modi

| Modus | Wirkung |
| --- | --- |
| **Normal** | Direktes Alpha-Source-over. Eine vollständig deckende Ebene ersetzt, was darunter liegt; eine vollständig transparente Ebene lässt es unverändert. |
| **Multiplizieren** | Multipliziert die Ebene mit dem darunter Liegenden – macht immer dunkler. Weiß ist neutral; Schwarz ergibt Schwarz. |
| **Bildschirm** | Umkehrung des Multiplizierens – macht immer heller. Schwarz ist neutral; Weiß ergibt Weiß. |
| **Overlay** | Wirkt in den dunklen Tönen wie Multiplizieren und in den hellen Tönen wie Bildschirm – verstärkt den Kontrast (relativ zum darunter Liegenden). |
| **Abdunkeln** | Behält den dunkleren der beiden Kanalwerte. |
| **Aufhellen** | Behält den helleren der beiden Kanalwerte. |
| **Farbig abwedeln** | Hellt das darunter Liegende auf, um die Ebene widerzuspiegeln; starke Aufhellung. |
| **Farbig nachbelichten** | Dunkelt das darunter Liegende ab, um die Ebene widerzuspiegeln; starke Abdunklung. |
| **Hartes Licht** | Overlay mit vertauschten Rollen von Ebene und Hintergrund – ein hartes Spotlicht. |
| **Weiches Licht** | Eine sanftere Variante des Modus Hartes Licht – weiches Abwedeln oder Nachbelichten, je nach Wert der Ebene. |
| **Differenz** | Absolute Differenz der beiden Werte – gleiche Farben löschen sich zu Schwarz aus. |
| **Ausschluss** | Wie Differenz, aber mit geringerem Kontrast in den Mitteltönen. |

> **Deckkraft und Mischmodus wirken zusammen.** Die Deckkraft einer Ebene skaliert ihren Beitrag
> **bei jedem** Mischmodus, nicht nur bei Normal. Eine ausgeblendete Ebene trägt unabhängig vom
> Modus nichts bei.

## Wie der Ebenenstapel zusammengesetzt wird

Ebenen werden **von unten nach oben** über einem laufenden Ergebnis zusammengesetzt: Die Pixel jeder
sichtbaren Ebene werden mit dem Mischmodus und der Deckkraft dieser Ebene (und ihrer Maske, falls
vorhanden) über das darunter Liegende gemischt. Ein Stapel aus Ebenen im Modus Normal entspricht
genau dem schrittweisen Anwenden von direktem Source-over-Alpha von unten nach oben. Das
Zusammensetzen verändert nie die Quellpuffer der Ebenen – es ist nicht destruktiv.

Eine einzelne Bearbeitung setzt nur den **betroffenen Bereich** neu zusammen, sodass das Malen auf
einer großen Arbeitsfläche reaktionsschnell bleibt.

## Leistung

Auf einer 8K-Arbeitsfläche (7680 × 4320) setzt das Malen eines einzelnen Pixels seinen kleinen
geänderten Bereich in etwa **1 ms** neu zusammen – bequem innerhalb des Rendering-Budgets von
16 ms / 60 fps. Einige aufwendigere Interaktionen bei niedrigem Zoom – das Ziehen des
Deckkraftreglers oder eine Attributänderung, die einen großen Ansichtsbereich über viele Ebenen neu
zeichnet – sind derzeit CPU-gebunden und können das Budget überschreiten; vollständiges
GPU-Shader-Compositing ist als spätere Erweiterung geplant.

## Verwandte Themen

- Legen Sie Mischmodus und Deckkraft einer Ebene im [Ebenenbedienfeld](layers.md) fest.
