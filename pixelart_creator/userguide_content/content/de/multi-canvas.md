# Mehrere Arbeitsflächen (Artboards)

Sie können mehrere Dokumente / Artboards gleichzeitig öffnen, jedes in einem eigenen **Tab**.

## Isolierte Tabs

Jede geöffnete Arbeitsfläche ist vollständig **zustandsisoliert**. Jeder Tab besitzt für sich allein:

- Ebenenstruktur (Ebenen, Gruppen, Masken, Referenz- und Smart-Ebenen);
- Palette und Farbmodus;
- Rückgängig- und Wiederholen-Verlauf;
- zusammengesetzte Ansicht und Geometrie der Arbeitsfläche.

Der Wechsel zu einem Tab macht diese Arbeitsfläche zum aktiven Kontext: Die Ebenenstruktur, die Palette,
der Rückgängig-Stapel und das zusammengesetzte Ergebnis dieser Arbeitsfläche werden aktuell, und das
Ebenenbedienfeld füllt sich passend dazu neu.

Da die Tabs isoliert sind, wirkt sich ein Vorgang in einer Arbeitsfläche **nie** auf eine andere aus:
Malen, Ändern von Ebenenattributen, Umordnen, Gruppieren oder Rückgängigmachen in Tab A lässt
Struktur, Ergebnis und Rückgängig-Verlauf von Tab B unberührt.

## Arbeiten mit mehreren Artboards

- Jedes Artboard kann eine andere Größe, eine andere Palette und einen anderen Farbmodus haben.
- Rückgängig gilt pro Tab: Rückgängigmachen greift nicht über Artboards hinweg.
- Beim Speichern eines Dokuments wird die eigene Ebenenstruktur dieses Tabs in die zugehörige
  `.pixproj`-Datei geschrieben.

> **Tipp.** Verwenden Sie getrennte Artboards für Varianten desselben Sprites (zum Beispiel
> Farbvarianten oder Posen), damit ihre Bearbeitungsverläufe unabhängig bleiben.

## Mehrere *Arbeitsflächen* gegenüber mehreren *Ansichten*

Mehrere Arbeitsflächen sind **isolierte** Tabs – jeder ein *anderes* Dokument. Das ist etwas anderes
als die **Mehrfachansicht**, die mehrere Fenster auf **ein** gemeinsames Dokument öffnet, die
synchron bleiben. Zur Bearbeitung mit mehreren Ansichten siehe
[Visuelle Hilfen und Bedienkomfort](visual-aids.md).
