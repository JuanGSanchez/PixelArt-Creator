# Auswahl und schwebendes Verschieben/Kopieren

Mit einer Auswahl können Sie nur einen Teil Ihrer Grafik bearbeiten – und eine **schwebende Auswahl**
lässt Sie die Farben innerhalb einer aktiven Auswahl aufnehmen und verschieben – oder kopieren –,
als **nicht destruktive Live-Vorschau**. Die Pixel *unter* der schwebenden Auswahl werden **nicht
verändert**, bis Sie bestätigen, sodass sich ein Verschieben jederzeit gefahrlos neu positionieren
oder verwerfen lässt.

Dieses Verhalten kennen Sie von Aseprite, Pro Motion NG, Pixelorama und Krita: anheben, ziehen,
ablegen.

> **Nur die aktive Ebene.** Ein schwebendes Verschieben/Kopieren wirkt auf die **aktive Ebene** (siehe
> [das Ebenenbedienfeld](layers.md)). Bei einem indizierten Dokument ist das die einzige indizierte
> Ebene. Andere Ebenen bleiben unberührt.

## Eine Auswahl erstellen

Legen Sie mit den Auswahlwerkzeugen den Bereich fest, an dem Sie arbeiten möchten:

| Werkzeug | Was es auswählt |
| --- | --- |
| **Rechteckauswahl** | Ein rechteckiger Bereich, den Sie aufziehen. |
| **Lasso-Auswahl** | Ein freihändiger Bereich, den Sie umfahren. |
| **Zauberstab** | Ein zusammenhängender Bereich ähnlicher Farbe unter dem Klick. |

**Lebensdauer der Auswahl.** Der Wechsel zu einem der drei oben genannten Auswahlwerkzeuge **verwirft**
immer die aktuelle Auswahl und beginnt neu – eine neue Auswahl erbt nie die Form der vorherigen. Der
Wechsel zu einem beliebigen anderen Werkzeug (Stift, Radiergummi, Füllen, …) **behält** die aktuelle
Auswahl dagegen bei, sodass das durch eine Maske begrenzte Zeichnen weiter funktioniert: Ihre Striche
bleiben auf die Auswahl beschnitten, während Sie mit einem anderen Werkzeug malen.

Solange eines der drei oben genannten Auswahlwerkzeuge aktiv ist, haben **Shift** und **Alt** eine
andere Bedeutung als überall sonst auf der Arbeitsfläche – siehe
[Ansicht verschieben und Auswahl aufbauen](#panning-vs-building-a-selection) weiter unten:

| Modifikator | Ergebnis, solange ein Auswahlwerkzeug aktiv ist |
| --- | --- |
| **Shift**+Ziehen | Zur aktuellen Auswahl **hinzufügen**. |
| **Alt**+Ziehen | Von der aktuellen Auswahl **abziehen**. |

### Ansicht verschieben und Auswahl aufbauen

| Geste | Ergebnis |
| --- | --- |
| **Shift+left-drag** | Verschiebt die Arbeitsfläche – **außer** bei aktivem Auswahlwerkzeug: Dort **fügt** es stattdessen weiterhin zur Auswahl **hinzu**, genau wie die Tabelle oben beschreibt. |

### Die gesamte Arbeitsfläche auswählen, die Auswahl umkehren und aufheben

| Tastenkürzel | Aktion |
| --- | --- |
| **Ctrl+A** | Die gesamte Arbeitsfläche auswählen. |
| **Ctrl+I** | Die aktuelle Auswahl umkehren. |
| **Ctrl+Shift+A** | Auswahl aufheben (die aktuelle Auswahl entfernen). |

Das Löschen des **Auswahlinhalts** (statt der Auswahl selbst) ist eine eigene Aktion mit eigenen
Tastenkürzeln, **Shift+Q** und **Delete** – siehe die Tabelle unter
[Grundlagen der Anwendung](app-basics.md).

## Anheben und Verschieben (Ziehen)

Die schwebende Auswahl entsteht aus der bereits aktiven Auswahl: Sie erstellt **keine** neue Auswahlform, sondern
verwendet die Maske, die Sie schon haben.

1. Drücken Sie bei aktivem Auswahlwerkzeug (Rechteckauswahl, Lasso-Auswahl oder Zauberstab) die
   Maustaste **innerhalb** der aktiven Auswahl. Die maskierten Pixel werden zu einer schwebenden
   Vorschau angehoben.
2. **Ziehen Sie.** Die schwebenden Farben folgen dem Cursor; der Ursprungsbereich erscheint in der
   Live-Vorschau **auf transparent gesetzt** (Index 0 im Modus Indexfarben).
3. Die zugrunde liegenden Pixel sind **noch nicht verändert** – nur die Vorschau ändert sich.

Drücken Sie die Maustaste **außerhalb** der aktiven Auswahl, wird **nicht** angehoben; stattdessen
beginnt wie gewohnt eine neue Auswahl.

## Kopieren statt Verschieben: Ctrl gedrückt halten

Halten Sie **Ctrl** beim Ziehen gedrückt, um die schwebende Auswahl auf **Kopieren** umzuschalten:

- der **Ursprung bleibt unverändert** (nichts wird geräumt), und
- eine **Kopie** der Farben schwebt zum Cursor.

Ein Cursor oder eine andere Anzeige für den Kopiermodus zeigt an, dass Sie kopieren. Sie können
**während** des Ziehens zwischen Verschieben und Kopieren wechseln, indem Sie Ctrl drücken oder
loslassen.

> **Ctrl ist der einzige Kopiermodifikator – nicht Alt.** Kopieren geht **nur mit Ctrl**. **Alt ist
> kein Kopiermodifikator**: Ein Alt-Ziehen im Inneren ist die Geste zum **Abziehen** beim Aufbau
> einer Auswahl und behält diese Bedeutung. Halten Sie **Ctrl+Alt** bei einem Ziehen im Inneren
> gedrückt, wird es als Alt-Abziehen gewertet, nicht als Kopieren – verwenden Sie zum Kopieren
> einfach **Ctrl**.

| Ziehen im Inneren | Ergebnis |
| --- | --- |
| *kein Modifikator* | Die Auswahl anheben / **verschieben** (der Ursprung wird beim Bestätigen geräumt) |
| **Ctrl** | Die Auswahl **kopieren** (der Ursprung bleibt erhalten) |
| **Alt** | Von der Auswahl **abziehen** (Aufbau-Geste) |
| **Shift** | Zur Auswahl **hinzufügen** (Aufbau-Geste) – außerhalb eines aktiven Auswahlwerkzeugs verschiebt **Shift+left-drag** stattdessen die Ansicht, anstatt etwas hinzuzufügen; siehe [Ansicht verschieben und Auswahl aufbauen](#panning-vs-building-a-selection) oben. |

## Bestätigen oder abbrechen

Die schwebende Auswahl wird **bestätigt**, sobald eines der folgenden Ereignisse eintritt:

- das **Loslassen** der Maustaste,
- das Drücken von **Enter / Return** oder
- das **Wechseln des Werkzeugs** (oder des Tabs).

Beim Bestätigen wird die Änderung als **genau ein rückgängig zu machender Schritt** angewendet:

- **Verschieben** – der Ursprung wird transparent geschrieben (Index 0 im Modus Indexfarben), und die
  Farben werden am Ziel eingesetzt.
- **Kopieren** – die Farben werden am Ziel eingesetzt, und der Ursprung bleibt unverändert.

Nach dem Bestätigen **folgt die Auswahlmaske zum Ziel**.

Drücken Sie **Esc**, um **abzubrechen**. Da die schwebende Auswahl nie in den Puffer geschrieben wurde, stellt das
Abbrechen die Arbeitsfläche vor dem Verschieben **exakt** wieder her und legt **keinen**
Rückgängig-Eintrag an; die Auswahlmaske kehrt an ihre Position vor dem Anheben zurück.

> **Ein Klick ohne Ziehen kostet nichts.** Das Bestätigen mit dem Versatz null (ein Klick in die
> Auswahl ohne Verschieben) bewirkt nichts – es erzeugt keinen Rückgängig-Schritt.

Sind am Ziel bereits Pixel vorhanden, fragt zunächst ein Dialog **Vorhandene Pixel überschreiben?**
nach: **Weiter** wendet das Bestätigen wie üblich an, **Abbrechen** wendet nichts an und lässt die
schwebende Auswahl mit ihrem aktuellen Versatz aktiv. Das Ankreuzen von
**„Für dieses Projekt nicht erneut fragen“** speichert die Unterdrückung erst, wenn Sie tatsächlich
zustimmen – Ankreuzen und Abbrechen speichert nichts.

## Ränder außerhalb der Arbeitsfläche

Sie können eine schwebende Auswahl **teilweise oder ganz über die Arbeitsfläche hinaus** ziehen. Beim
Bestätigen werden die Pixel außerhalb der Arbeitsfläche **verworfen** (nie auf der gegenüberliegenden Seite wieder eingefügt), sodass Sie
Grafik ohne Fehler bis an den Rand schieben können. Bei einem Verschieben wird der gesamte
Ursprung innerhalb der Grenzen weiterhin geräumt, unabhängig davon, wie weit Sie gezogen haben.

## Rückgängig, Wiederholen und Darstellung

- Ein bestätigtes Verschieben oder Kopieren ist **ein** Rückgängig-Schritt: **Rückgängig** stellt den
  Puffer vor dem Verschieben exakt wieder her; **Wiederholen** wendet es erneut an.
- Die schwebende Vorschau wird bei jedem Zoom mit **Nearest-Neighbor und ausgeschalteter
  Kantenglättung** dargestellt und ist im **hellen** wie im **dunklen** Design gut lesbar.
- Die Live-Vorschau beim Ziehen aktualisiert nur den Bereich, den die schwebende Auswahl berührt,
  sodass sie selbst auf einer 8K-Arbeitsfläche innerhalb des Rendering-Budgets von 16 ms / 60 fps
  bleibt.

## Transformationen des gesamten Dokuments

**Bild ▸ Skalieren…**, die beiden Vierteldrehungen und die beiden Spiegelungen wirken alle auf das
**gesamte Dokument** – jede Ebene und Maske, über alle Frames hinweg –, solange nichts ausgewählt ist.
Bei einer aktiven Auswahl transformieren dieselben Aktionen weiterhin nur den maskierten Bereich der
aktiven Ebene, genau wie bisher.

| Tastenkürzel | Aktion |
| --- | --- |
| **Shift+H** | Die Auswahl (oder das gesamte Dokument) horizontal spiegeln. |
| **Shift+V** | Die Auswahl (oder das gesamte Dokument) vertikal spiegeln. |

RotSprite ist die einzige Ausnahme: Es transformiert immer nur die aktive Ebene, mit oder ohne
Auswahl, weil seine Drehung die Abmessungen des Puffers nie ändert und den weiteren Geltungsbereich nie
brauchte.

> **Große Transformationen fragen zuerst nach.** Würden das neu berechnete Ergebnis und die für
> Rückgängig aufbewahrten Puffer zusammen 506,25 MiB überschreiten (die RGBA-Daten von vier
> vollständigen 8K-Arbeitsflächen), nennt ein Dialog **Große Transformation bestätigen** vor dem
> Start den genauen voraussichtlichen Speicherbedarf. **Abbrechen** ist die Standardschaltfläche,
> sodass das Drücken von Return die Transformation **nicht** startet – Sie müssen bewusst auf
> **Fortfahren** klicken. Das Ablehnen lässt das Dokument völlig unberührt und legt nichts auf den
> Rückgängig-Stapel. Unterhalb dieser Schwelle erscheint überhaupt kein Dialog.

Sobald eine Transformation des gesamten Dokuments läuft, verfolgt ein Fortschrittsdialog
**Dokument wird transformiert** sie Puffer für Puffer und lässt sich jederzeit abbrechen – die
Schaltfläche **Abbrechen**, Escape oder das eigene Schließen-Symbol des Fensters funktionieren alle.
Das Abbrechen ist atomar: Das Dokument bleibt genau so, wie es war, und nichts gelangt auf den
Rückgängig-Stapel, egal wie viele Puffer bereits neu berechnet wurden.

## Was nicht abgedeckt ist

- Das **Drehen oder Skalieren** der Auswahl, *während* sie schwebt – bestätigen Sie zuerst das
  Verschieben und verwenden Sie dann die Transformationswerkzeuge.
- Eine Variante **Alle Ebenen verschieben** – die schwebende Auswahl betrifft nur die aktive Ebene.
- Das **dokumentübergreifende** Ziehen einer schwebenden Auswahl oder das Speichern einer
  schwebenden Auswahl in einer `.pixproj`-Datei – eine schwebende Auswahl ist ein flüchtiger
  Bearbeitungszustand, der immer zuerst bestätigt oder abgebrochen wird.
