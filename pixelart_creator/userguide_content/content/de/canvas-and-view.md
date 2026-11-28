<!-- surface-only: bundle — Orientierungsinhalt in der Anwendung; bewusst ohne Website-Seite -->
# Die Arbeitsfläche: Zoom, Verschieben und Raster

Die **Arbeitsfläche** ist die wichtigste Fläche zum Zeichnen – eine große Szene, die Dokumente bis zum
Plattformmaximum von **7680 × 4320 (8K)** unterstützt. Sie stellt Ihre Grafik mit
**Nearest-Neighbor**-Skalierung und **ausgeschalteter Kantenglättung** dar, sodass Pixel bei jedem
Zoom scharf und quadratisch bleiben – genau so, wie Pixelart aussehen soll.

## Navigieren: Zoom und Verschieben

- **Zoom** – zoomen Sie hinein, um einzelne Pixel zu bearbeiten, und heraus, um das gesamte Motiv zu
  sehen. Das Zoomen ist zentriert, sodass der Punkt unter dem Cursor an seiner Stelle bleibt; so
  behalten Sie beim Vergrößern und Verkleinern die Orientierung. Zoom ist eine **Ansichtsaktion**:
  Sie verändert nie Ihre Grafik und ist kein Rückgängig-Schritt.
- **100 % ist die niedrigste Zoomstufe.** Sie können nicht mehr unter 1:1 herauszoomen, auch nicht bei
  einem Dokument, das größer als das Fenster ist. Unter 100 % kann ein einzelnes Dokumentpixel
  zwischen die Abtastpunkte des Bildschirms fallen und einfach nicht gezeichnet werden – Striche
  verschwanden scheinbar beim Herauszoomen. Erkunden Sie ein großes Dokument stattdessen durch
  **Verschieben**: So lässt sich jede Ecke der Arbeitsfläche in die Mitte der Ansicht bringen.
- **Verschieben** – scrollen Sie die Ansicht horizontal und vertikal, um jeden Teil einer großen
  Arbeitsfläche zu erreichen. Da die Szene einmal für die volle Dokumentgröße vorbereitet wird, bleibt
  das Verschieben über eine 8K-Arbeitsfläche flüssig – gezeichnet wird nur der Teil, der in der
  Ansicht sichtbar ist, sodass das Vorbeiscrollen an Bereichen außerhalb des Bildschirms nichts kostet.
- **Hineinzoomen / Herauszoomen** – **Ctrl++** und **Ctrl+-** springen zwischen denselben festen
  Voreinstellungsstufen (100 %, 200 %, 400 %, 800 %, 1600 %, 3200 %, 6400 %): **Ctrl++** rastet auf
  der nächsthöheren Stufe ein und **Ctrl+-** auf der vorherigen. Das ist ein Sprung zwischen festen
  Stufen, anders als der stufenlose, am Cursor verankerte Zoom mit **Shift+wheel** weiter unten.

> **Große Arbeitsflächen bleiben reaktionsschnell.** Der Renderer zeichnet nur den Bereich, der
> gerade in der Ansicht sichtbar ist, und zeichnet nur die kleine Fläche neu, die eine Bearbeitung
> tatsächlich ändert, sodass das Malen auf einer 8K-Arbeitsfläche innerhalb des
> Rendering-Budgets von 60 fps bleibt.

## Das Schachbrettmuster ist die Grenze Ihrer Arbeitsfläche

Das Transparenzmuster ist keine Dekoration hinter der Grafik – es **ist die Pixelstruktur selbst**:
Ein einzelnes Karo des Schachbrettmusters entspricht genau einem Dokumentpixel. Das Muster ist außerdem begrenzt: Es
endet genau am Rand der Arbeitsfläche, eine einheitliche Hintergrundfarbe der Ansicht füllt die
Umgebung, und ein dünner Rahmen zeichnet die Grenze zwischen beiden nach, sodass Sie jederzeit sehen
können, wo die Arbeitsfläche endet. Früher lief das Muster über den Rand hinaus, ohne dass er
markiert war, wodurch man leicht ein Karo mit einem Pixel verwechselte.

## Das Pixelraster

Das **Pixelraster** hilft Ihnen, Pixel präzise zu platzieren, und ist für ein neues Dokument
**standardmäßig eingeschaltet**.

- **Schalten Sie das Raster um** mit **Ansicht ▸ Raster anzeigen**. Es ist eine Einblendung, die über
  der Grafik gezeichnet wird – es wird nie Teil Ihrer Pixel und erscheint nie in einem Export.
- Das Raster ist im hellen wie im dunklen Design gut lesbar und so gezeichnet, dass es sich über jeder
  Farbe der Grafik klar abhebt.
- **Eingeschaltet heißt nicht gezeichnet.** Das Raster erscheint erst, wenn ein
  Dokumentpixel auf dem Bildschirm mindestens 8 Bildschirmpixel breit dargestellt wird. Bei 100 % Zoom ist ein Dokumentpixel kleiner, sodass
  Sie auch bei eingeschaltetem Raster keine Rasterlinien sehen – zoomen Sie hinein, dann erscheinen
  sie. Wenn Sie das Raster einschalten und sich nichts ändert, liegt es daran; es ist kein Fehler.
- Wenn Sie weit herausgezoomt haben, wäre ein dichtes Raster unlesbar, daher stellt die Einblendung
  das Zeichnen automatisch ein, bis Sie wieder hineinzoomen.

## Ausrichten am Raster

Bei eingeschaltetem **Ansicht ▸ Am Raster ausrichten** richten sich die Werkzeuge am Raster aus, sodass
ein Strich exakt auf Pixelgrenzen landet. Das ist besonders nützlich beim Platzieren von Tiles oder
beim Ausrichten von Formen. Das Ausrichten ist eine Ansichts- oder Werkzeugeinstellung, keine
Bearbeitung.

## Auf der Arbeitsfläche malen

- **Linksklick** (und Ziehen) malt mit dem aktiven Werkzeug und der aktiven Farbe. Die aktive Farbe
  stammt aus der [Farbzentrale](colour-hub.md) oder der Palette. Jeder Strich wird als ein
  Rückgängig-Schritt abgelegt.
- **Rechtsklick** öffnet die kontextbezogene [Farbzentrale](colour-hub.md) am Cursor, sodass Sie Ihre
  Farbe wählen oder ändern können, ohne die Arbeitsfläche zu verlassen.

## Die Größe der Arbeitsfläche ändern

**Bild ▸ Arbeitsflächengröße…** ändert die Abmessungen der Arbeitsfläche selbst – dabei wird kein
einziges Pixel neu berechnet. Geben Sie eine neue Breite und Höhe ein (jeweils bis zur
Plattformgrenze von **7680 × 4320**, also 8K) und klicken Sie auf **OK**; jede Ebene und Maske in
jedem Frame wird auf die neue Größe zugeschnitten oder aufgefüllt, verankert oben links, sodass
vorhandene Grafik nie verrutscht und jeder neu freigelegte Bereich transparent ist. Klicken Sie auf
**Abbrechen**, um das Dokument genau so zu belassen, wie es war. Die Größenänderung wird als ein
rückgängig zu machender Schritt angewendet.

Das ist etwas anderes, als die Grafik auf eine neue Größe neu zu berechnen – die Arbeitsflächengröße
ändert nur, wie viel Arbeitsfläche vorhanden ist; die Pixel, die Sie bereits haben, werden dabei nie
gestreckt oder gestaucht.

## Tastatur- und Zeigerkürzel

Diese stehen hier und nicht nur in der Tabelle unter [Grundlagen der Anwendung](app-basics.md), weil
sie Operationen der Ansicht sind und keine Werkzeuge:

| Tastenkürzel | Aktion |
| --- | --- |
| **Ctrl++** | In die Ansicht der aktiven Arbeitsfläche um eine Voreinstellungsstufe hineinzoomen. |
| **Ctrl+-** | Aus der Ansicht der aktiven Arbeitsfläche um eine Voreinstellungsstufe herauszoomen. |

Die Arbeitsfläche reagiert außerdem auf einige Zeigergesten, die Ihre Grafik nie berühren – jede ist
eine **Ansichtsaktion**, genau wie Zoom, daher ist keine davon ein Rückgängig-Schritt:

| Geste | Ergebnis |
| --- | --- |
| **Wheel** | Rückt in der Liste der **Favoriten**, die auch die [Farbzentrale](colour-hub.md) verwendet, die aktuelle Position weiter und setzt die aktive Farbe – eine Möglichkeit, Ihre Lieblingsfarben durchzugehen, ohne die Farbzentrale überhaupt zu öffnen. |
| **Shift+wheel** | Der oben erwähnte stufenlose, am Cursor verankerte Zoom – der Punkt unter dem Cursor bleibt an seiner Stelle, während Sie hinein- oder herauszoomen. |
| **Shift+middle-click** | Passt die Ansicht an die gemalten Pixel an, sodass ein Motiv, von dem Sie weggescrollt oder weggezoomt haben, nur eine Geste von der Rückkehr in die Ansicht entfernt ist. |

## Verwandte Themen

- Wählen und verwalten Sie Farben in [Die Farbzentrale per Rechtsklick](colour-hub.md).
- Stapeln und setzen Sie Ihre Arbeit mit [Ebenen](layers.md) zusammen.
- Wählen Sie Bereiche aus und positionieren Sie sie neu unter
  [Auswahl und schwebendes Verschieben/Kopieren](selection-and-transform.md).
- Fügen Sie nicht destruktive [Raster, Hilfslinien und weitere visuelle Hilfen](visual-aids.md) für
  präzises Platzieren hinzu.
