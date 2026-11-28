<!-- surface-only: bundle — Orientierungsinhalt in der Anwendung; im Einleitungstext von index.md der Website nur am Rande behandelt, bewusst ohne eigene Website-Seite -->
# Erste Schritte und der Arbeitsbereich

![PixelArt Creator](pac-logo.png)

Willkommen bei **PixelArt Creator** – einem Desktop-Studio für Pixelart mit einer 8K-Arbeitsfläche,
einem nicht destruktiven Ebenensystem, einer Animationszeitleiste, einem Tileset-/Tilemap-Editor,
einer Export-Pipeline, Automatisierung und Skripting, visuellen Hilfen sowie Cloud- und
Zusammenarbeitswerkzeugen. Dieses Thema führt Sie durch den Arbeitsbereich, damit der Rest des
Handbuchs verständlich wird.

## Das Hauptfenster im Überblick

- **Menüleiste** (oben) – der Einstiegspunkt für jeden Befehl, gegliedert in Menüs wie
  **Datei**, **Bearbeiten**, **Ansicht**, **Cloud** und **Hilfe**. Das integrierte Benutzerhandbuch,
  das Sie gerade lesen, öffnen Sie über **Hilfe ▸ Benutzerhandbuch** (oder mit **F1**).
- **Arbeitsfläche** (Mitte) – die Fläche, auf der Sie zeichnen. Siehe
  [Die Arbeitsfläche: Zoom, Verschieben und Raster](canvas-and-view.md).
- **Andockbare Bedienfelder** (seitlich) – das Ebenenbedienfeld, die Animationszeitleiste, der
  Tileset-Editor sowie die Bedienfelder für Cloud und Zusammenarbeit. Die meisten lassen sich
  ein- oder ausblenden und passend zu Ihrem Arbeitsablauf anordnen.
- **Statusleiste** (unten) – Fortschrittsanzeigen für Hintergrundaufgaben (Exportieren,
  Vorbereitung der Wiedergabe, Cloud-Speicherungen) und kurze Hinweise.

## Dokumente und Tabs

Jede geöffnete Pixelgrafik ist ein **Dokument**, das in einem eigenen **Tab** angezeigt wird.
Ein Dokument hat eine Größe, einen Farbmodus (**RGBA** oder **Indexfarben**), eine Palette, eine
Ebenenstruktur und – falls Sie es animieren – eine Liste von Frames. Sie können mehrere
Dokumente gleichzeitig geöffnet halten; siehe
[Mehrere Arbeitsflächen (Artboards)](multi-canvas.md). Dokumente werden als Projektdateien im
Format **`.pixproj`** gespeichert – dem validierten, versionierten Speicherformat, das die gesamte
Anwendung (und die Cloud-Schicht) verwendet.

## Rückgängig und Wiederholen

Fast jede Bearbeitung – Malen, eine Ebenenänderung, eine Transformation, eine Frame-Bearbeitung,
ein Automatisierungslauf – wird als **genau ein** Schritt auf den **Rückgängig-Stapel** des
Dokuments gelegt. **Rückgängig** nimmt den letzten Schritt zurück und **Wiederholen** wendet ihn
erneut an. Der Rückgängig-Verlauf gilt **pro Tab**, daher greift ein Rückgängigmachen in einem
Dokument nie in ein anderes ein. Einige wenige Aktionen lassen sich bewusst *nicht* rückgängig
machen, weil sie Ansichtszustand und keine Bearbeitungen sind: das Auswählen oder Durchlaufen eines
Frames, das Ein- und Ausschalten der Zwiebelschichten, das Hinzufügen einer Hilfslinie und das Öffnen
der Cloud- und Zusammenarbeits-Bedienfelder.

## Designs (Stil, Hell und Dunkel)

Alles zum Erscheinungsbild der Anwendung finden Sie im Menü **Design**. Jede Auswahl wird sofort
angewendet und beim nächsten Start der Anwendung beibehalten.

- **Stil** – ein Untermenü mit drei visuellen Stilen: **Washi & Kintsugi** (der Standard),
  **Edo Night** und **Arcade Kikko**. Jeder ist ein vollständiges Erscheinungsbild für Bedienfelder,
  Dialoge, Rahmen und die Musterflächen des Fensters.
- **Hell** / **Dunkel** – die Farbvariante, unabhängig vom Stil wählbar. Jedes Bedienfeld, jeder
  Dialog, jede Einblendung und dieses Benutzerhandbuch werden in beiden korrekt dargestellt und
  bleiben lesbar. Farben werden einmal nach Rolle festgelegt, sodass das Design überall einheitlich
  ist.
- **Systemschrift verwenden** – stellt die Oberfläche von der mitgelieferten Pixelschrift (Nifen
  Art) auf die Oberflächenschrift Ihres Betriebssystems um.
- **Pixelgenaue Oberfläche** – standardmäßig eingeschaltet. Sie skaliert die Oberfläche nur
  ganzzahlig, sodass Pixelart auch auf Bildschirmen mit gebrochener Skalierung (zum Beispiel
  125 % oder 150 %) scharf bleibt. Eine Änderung wirkt sich erst beim nächsten Start der
  Anwendung aus.

## Version und Info

Der Fenstertitel lautet immer **PixelArt Creator**, gefolgt von der laufenden Version – der
genauen Nummer Ihres Builds –, sodass Sie sie ohne zusätzlichen Schritt finden. Alle Einzelheiten
erhalten Sie über **Hilfe ▸ Über PixelArt Creator** (unter macOS: im Anwendungsmenü, neben dem
Eintrag zum Beenden – dort legt die Plattform den Eintrag ab). Der Dialog „Über PixelArt Creator“
zeigt den Namen der Anwendung, ihre Version (markierbar, sodass Sie sie von Hand kopieren können),
die Lizenz, Links zum Quell-Repository, zur Dokumentationsseite und zur Seite mit den Releases sowie
die Schaltfläche **Kopieren**, die die Version zusammen mit den Versionen Ihres Betriebssystems, von
Python und von Qt/PySide6 in einer Zeile in die Zwischenablage legt – bereit zum direkten Einfügen
in einen Fehlerbericht.

## Sprache

Die Oberfläche ist vollständig übersetzbar. Wenn Sie die aktive Sprache wechseln, werden alle
Menüs, Beschriftungen und Meldungen sofort neu übersetzt – ein Neustart ist nicht nötig. Der Rahmen
dieses Benutzerhandbuchs (Titel, Abschnittsbeschriftungen, Suchfeld und Navigation) folgt der
aktiven Sprache; die Inhalte des Handbuchs erscheinen in Ihrer Sprache, wenn eine lokalisierte
Version mitgeliefert ist, andernfalls fällt die Anzeige auf den Standardtext (Englisch) zurück.

## Tastenkürzel

Dies ist die vollständige Tabelle der Tastenkürzel der Anwendung: jede Werkzeugtaste, beide
Umschalter, die beiden Wege, den Auswahlinhalt zu löschen, und die wichtigsten Aktionen für Datei,
Bearbeiten und Hilfe. Jede andere Seite dieses Handbuchs, die ein Tastenkürzel erwähnt, verweist auf
diese Tabelle zurück, statt es zu wiederholen.

| Tastenkürzel | Aktion |
| --- | --- |
| **A** | Werkzeug Stift – freihändiges Malen von Pixeln. |
| **Shift+A** | Werkzeug Pipette – eine Farbe von der Arbeitsfläche aufnehmen. |
| **Q** | Werkzeug Radiergummi. |
| **S** | Werkzeug Rechteck. |
| **W** | Werkzeug Linie. |
| **Shift+W** | Werkzeug Ellipse. |
| **D** | Werkzeug Rechteckauswahl. |
| **F** | Werkzeug Füllen. |
| **Shift+F** | Werkzeug Dithering. |
| **E** | Werkzeug Lasso-Auswahl (freihändig). |
| **Shift+E** | Werkzeug Zauberstab (zusammenhängende Farbe). |
| **Shift+S** | **Gefüllte Formen** umschalten, gemeinsam für die Werkzeuge Rechteck und Ellipse. |
| **Shift+R** | **Pixel Perfect** in der Ansicht jedes geöffneten Tabs umschalten. |
| **Shift+Q** | Auswahlinhalt löschen. |
| **Delete** | Auswahlinhalt löschen (ein zweites Tastenkürzel für dieselbe Aktion). |
| **Ctrl+N** | Neues Dokument. |
| **Ctrl+O** | Ein vorhandenes Projekt öffnen. |
| **Ctrl+S** | Das aktive Projekt speichern. |
| **Ctrl+Z** | Den letzten umkehrbaren Vorgang rückgängig machen. |
| **Ctrl+Y** | Den zuletzt rückgängig gemachten Vorgang wiederholen. |
| **F1** | Dieses Benutzerhandbuch öffnen. |

Die elf Werkzeugtasten liegen bewusst in der Grundreihe und ihrer Umgebung, damit Ihre Hand beim
Zeichnen nie die Schreibposition verlassen muss. **Shift+Q** und **Delete** bewirken dasselbe – sie
löschen den Inhalt einer Auswahl –, sodass Sie die Taste verwenden können, die Ihre Hand gerade am
nächsten erreicht.

Einige weitere Tastenkürzel stehen auf der Seite, zu der sie gehören, weil sie erst sinnvoll sind,
wenn man die jeweilige Funktion kennt: **Ctrl+Shift+E** öffnet den Export, siehe
[Export und Pipeline-Integration](export-and-pipeline.md); **Ctrl++** / **Ctrl+-** zoomen die
Arbeitsfläche, und die Zeigergesten zum Verschieben, Zoomen und Auswählen von Farben per Mausrad
oder mittlerer Maustaste stehen unter [Die Arbeitsfläche](canvas-and-view.md); **Ctrl+A** /
**Ctrl+I** / **Ctrl+Shift+A** / **Shift+H** / **Shift+V** und die Ziehgesten der Auswahl stehen
unter [Auswahl und schwebendes Verschieben/Kopieren](selection-and-transform.md);
**Ctrl+wheel**, **Ctrl+middle-click**, **Ctrl+left-click** und **Ctrl+right-click** auf der
Zeitleiste stehen unter [Die Animationszeitleiste](animation-timeline.md). **Space** schaltet
Wiedergabe und Pause der Animation um und ist überhaupt kein Menü-Tastenkürzel – es funktioniert
nur, solange ein Dokument mit mehr als einem Frame geöffnet ist. **Esc** bricht die jeweils laufende
Aktion ab und **Enter** bestätigt sie (meist das Verschieben einer schwebenden Auswahl) – was das
genau umfasst, steht unter
[Auswahl und schwebendes Verschieben/Kopieren](selection-and-transform.md).

## Wie es weitergeht

- Zeichnen Sie auf der [Arbeitsfläche](canvas-and-view.md) und wählen Sie Farben in der
  [Farbzentrale](colour-hub.md).
- Organisieren Sie Ihre Grafik mit [Ebenen](layers.md) und [Mischmodi](blend-modes.md).
- [Wählen Sie Bereiche Ihrer Grafik aus](selection-and-transform.md) und verschieben Sie sie.
- Animieren Sie mit der [Zeitleiste](animation-timeline.md), bauen Sie Levels mit dem
  [Tileset- und Tilemap-Editor](tileset-and-tilemap.md) und liefern Sie Assets über den
  [Export](export-and-pipeline.md) aus.
- Beschleunigen Sie wiederkehrende Arbeit mit [Automatisierung und Skripting](automation-and-scripting.md),
  zeichnen Sie präziser mit [visuellen Hilfen](visual-aids.md) und probieren Sie die Werkzeuge für
  [Cloud](cloud-and-collaboration.md) und [Zusammenarbeit](collaboration.md) innerhalb einer Sitzung
  aus (in dieser Version laufen sie im Arbeitsspeicher innerhalb eines einzelnen Anwendungsfensters
  und stellen keine Verbindung zu anderen Fenstern oder anderen Personen her).
