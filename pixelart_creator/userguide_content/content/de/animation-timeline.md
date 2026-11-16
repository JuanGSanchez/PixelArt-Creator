# Die Animationszeitleiste

Das **Animationssystem** macht aus der Frame-Liste eines Dokuments eine *Zeitleiste*: Sie können
Frames hinzufügen, entfernen, umordnen und duplizieren; jedem Frame eine eigene Anzeigedauer auf dem
Bildschirm geben; die Sequenz in einem von vier Modi abspielen; mit Zwiebelschichten benachbarte
Frames sehen; und Frame-Bereiche mit Frame-Tags zu **benannten Animationen** zusammenfassen. Jede
Bearbeitung von Frames und Tags ist ein einziger Rückgängig-Schritt.

Damit erreicht die Anwendung bei Zeitleiste, Wiedergabe, Zwiebelschichten und Tags den
Funktionsumfang von **Aseprite** und geht darüber hinaus: Über Frame-Tags lassen sich **mehrere
unabhängige benannte Animationen in einer Datei** verwalten (walk, run, idle).

> **Unabhängige Ebenen pro Frame.** Jeder Frame besitzt seinen **eigenen** Ebenenstapel, der mit
> demselben [Ebenensystem](layers.md) zusammengesetzt wird (Sichtbarkeit / Deckkraft / Mischmodus /
> Gruppen / Masken werden pro Frame alle berücksichtigt). In einem **indizierten** Dokument ist ein
> Frame eine einzige indizierte Ebene, und die Zwiebelschichten werden nicht angezeigt (der
> Compositor arbeitet ausschließlich mit RGBA).

## Die Frame-Leiste

Das Bedienfeld **Zeitleiste** zeigt das Dokument als horizontale Leiste aus Frames in
Wiedergabereihenfolge (von links nach rechts); jede Zelle trägt ein Vorschaubild, ihre Frame-Nummer
und alle Tag-Markierungen, die sie überspannen. Das Ebenenbedienfeld zeigt die Ebenen des Frames, der
gerade aktiv ist.

- **Einen Frame auswählen** – klicken Sie darauf (oder verwenden Sie die Pfeiltasten). Die
  Arbeitsfläche zeigt den zusammengesetzten Ebenenstapel dieses Frames. Das Auswählen ist eine
  Ansichtsaktion und daher **nicht** rückgängig zu machen.
- **Scrubben** – drücken Sie die Maustaste und ziehen Sie an der Leiste entlang; die Arbeitsfläche zeigt
  fortlaufend den Frame unter dem Cursor. Auch das Scrubben ist **nicht** rückgängig zu machen.

## Frames verwalten

Die Werkzeugleiste der Zeitleiste bearbeitet die Sequenz. Jede Aktion ist **genau ein
Rückgängig-Schritt**:

| Aktion | Was sie bewirkt |
| --- | --- |
| **Frame hinzufügen** | Fügt nach dem aktiven Frame einen neuen Frame mit leerer Ebene ein. |
| **Frame entfernen** | Löscht den aktiven Frame. **Nicht verfügbar, wenn nur noch ein Frame übrig ist** – ein Dokument behält immer mindestens einen Frame. |
| **Frame duplizieren** | Fügt nach dem Original eine **tiefe, unabhängige Kopie** ein (ihre Ebenen und ihre Dauer werden mitkopiert). Das Bearbeiten der Kopie ändert das Original nie. |
| **Frame ziehen** | Ziehen Sie eine Zelle an eine neue Position, um sie **umzuordnen**. Wiedergabe und Scrubben folgen der neuen Reihenfolge. |

Rückgängig stellt die exakte vorherige Sequenz wieder her – Inhalte, Reihenfolge und Dauern.

## Dauer pro Frame

Jeder Frame hat seine eigene **Dauer** in Millisekunden, die im Dauerfeld der Leiste angezeigt wird
(neue Frames erhalten standardmäßig die Standard-Frame-Dauer). Geben Sie einen neuen Wert ein und
bestätigen Sie ihn (Enter / Fokusverlust), um die Anzeigedauer dieses Frames als einen
Rückgängig-Schritt festzulegen. Dauern müssen **positiv** sein – ein Wert kleiner oder gleich null
wird abgelehnt. Ein Frame mit 500 ms bleibt bei der Wiedergabe etwa fünfmal so lange stehen wie ein
Frame mit 100 ms.

> **Einheitliche Bildrate.** Eine einheitliche FPS-Zahl ist nichts anderes als dieselbe Dauer für
> jeden Frame (`duration_ms = round(1000 / fps)`). Die Millisekunden pro Frame bleiben stets die
> einzige Quelle für das Wiedergabetiming.

## Wiedergabe

Die **Wiedergabesteuerung** bestimmt den angezeigten Frame über die Zeit:

- **Abspielen** startet die Wiedergabe über das gesamte Dokument (oder setzt sie nach einer Pause
  fort).
- **Pause** hält beim aktuellen Frame an.
- **Stopp** beendet die Wiedergabe und kehrt zu dem Frame zurück, der aktiv war, als Sie auf
  Abspielen geklickt haben.
- **Space** schaltet zwischen Abspielen und Pause um.

Die **Modusauswahl** legt fest, wie die Sequenz voranschreitet (Standard: **Schleife**):

| Modus | Verhalten bei einem Bereich von 4 Frames |
| --- | --- |
| **Schleife** | `0,1,2,3,0,1,2,3,…` – beginnt endlos von vorn. |
| **Einmal** | `0,1,2,3`, dann **hält** sie beim letzten Frame an. |
| **Rückwärts** | `3,2,1,0,3,2,1,0,…` – beginnt rückwärts immer wieder von vorn. |
| **Ping-Pong** | `0,1,2,3,2,1,0,1,2,3,…` – pendelt hin und her; die **Endpunkte werden nicht verdoppelt**. |

Die Wiedergabe berücksichtigt die Dauer jedes einzelnen Frames; eine geänderte Dauer ändert daher
die Anzeigedauer dieses Frames beim nächsten Durchlauf.

> **Das erste Abspielen einer großen Animation wird außerhalb des Haupt-Threads vorbereitet.** Wenn
> Sie zum ersten Mal einen Bereich eines großen (zum Beispiel 8K-)Dokuments mit mehreren Ebenen
> abspielen, muss das auf eine Ebene reduzierte Gesamtbild jedes Frames einmal aufgebaut werden. Das geschieht
> **außerhalb des GUI-Threads** mit einer kleinen, **abbrechbaren** Fortschrittsanzeige in der
> Statusleiste – das Fenster bleibt bedienbar, und die Wiedergabe **streamt** die Frames, sobald sie
> bereit sind, statt einzufrieren. Sind die Frames einmal vorbereitet, werden sie zwischengespeichert,
> sodass erneutes Abspielen und Scrubben mit 60 fps laufen.

## Zwiebelschichten

Zwiebelschichten (Onion Skinning) zeigen **benachbarte Frames** hinter dem Frame, den Sie gerade
bearbeiten, damit Sie Bewegungen aufeinander abstimmen können.

- **Aktivieren** Sie sie mit dem Kontrollkästchen **Zwiebelschichten aktivieren** im Bedienfeld
  Zwiebelschichten. Geisterbilder werden hinter dem aktiven Frame gezeichnet; der aktive Frame selbst
  bleibt unverändert.
- Legen Sie fest, wie viele **vorherige** und **nächste** Frames angezeigt werden (jeweils `0`
  deaktiviert diese Seite; Standard ist **1 vorheriger / 1 nächster**).
- Legen Sie für jede Seite die **Tönung** fest – standardmäßig **Rot** für vorherige und **Blau**
  für nächste Frames. Weiter entfernte Frames blenden zunehmend aus.

Anzahl und Tönung der Zwiebelschichten sind **Ansichtseinstellungen** – ihre Änderung aktualisiert die
Einblendung sofort und erzeugt **keinen** Rückgängig-Schritt. Die Zwiebelschichten werden **während
der Wiedergabe unterdrückt** (sie sind eine Bearbeitungshilfe, keine Vorschau) und ebenso beim
Scrubben.

## Frame-Tags (benannte Animationen)

Ein **Frame-Tag** benennt einen Bereich von Frames als eigene Animation. Eine Datei kann mehrere Tags
enthalten – zum Beispiel `walk` über die Frames 1–4, `idle` über Frame 0 – und sie dürfen sich
überlappen.

Im Bedienfeld **Frame-Tags**:

- **Tag hinzufügen / Tag bearbeiten** – öffnen jeweils einen Dialog mit den Feldern **Name**,
  **Von Frame / Bis Frame** (einschließlich der Grenzen), **Modus** (der Wiedergabemodus),
  **Wiederholungen** (`0` = endlos bei Schleifenmodi) und **Farbe**. **Tag entfernen** löscht das
  ausgewählte Tag sofort, ohne Dialog, und ist nur verfügbar, solange ein Tag ausgewählt ist. Jede
  Änderung ist **ein Rückgängig-Schritt**. Ein Tag wird als Spanne über den Frames angezeigt, die es
  abdeckt.
- **Tag abspielen** spielt das ausgewählte Tag als eigene benannte Animation ab: Es lässt den Bereich
  des Tags mit dem **eigenen** Wiedergabemodus und der eigenen Wiederholung des Tags laufen,
  unabhängig vom globalen Wiedergabemodus. Ein Tag im Modus **Einmal** mit 3 Wiederholungen spielt
  seinen Bereich dreimal ab und hält dann an.

Wenn Sie Frames hinzufügen oder entfernen, bleiben die Tag-Bereiche automatisch gültig (sie werden auf
die neue Frame-Anzahl begrenzt); Rückgängig stellt sowohl die Frame-Änderung als auch die
ursprünglichen Tag-Bereiche gemeinsam wieder her.

## Rasteransicht (das Cel-Raster)

Der Schalter **Rasteransicht** in der Werkzeugleiste der Zeitleiste wechselt von der horizontalen
Frame-Leiste zu einem **Cel-Raster**: Frames als Spalten, Ebenenspuren als Zeilen, im gleichen Stil wie
das Cel-Raster von Aseprite. Es zeigt dasselbe Dokument wie die Leiste – das Hin- und Herwechseln
lässt Ihre aktuelle Position nie verloren gehen.

- **Cel verschieben / kopieren** – ziehen Sie eine Zelle, die ein Cel enthält, auf einen neuen
  Frame bzw. eine neue Spur, um es zu verschieben; halten Sie beim Ziehen **Ctrl** gedrückt, um es
  stattdessen zu kopieren, wobei die Quelle an Ort und Stelle bleibt. Beides ist ein einziger
  Rückgängig-Schritt. Das ist eine **andere** Geste als **Ctrl+Ziehen** auf der Arbeitsfläche; Letzteres
  kopiert weiterhin eine schwebende Auswahl (siehe
  [Auswahl und schwebendes Verschieben/Kopieren](selection-and-transform.md#copy-instead-of-move-hold-ctrl)):
  Der Modifikator ist derselbe, aber welche Geste gilt, hängt davon ab, wo Sie ziehen.
- **Überschreibbestätigung** – wenn Sie auf eine Zelle ablegen, die bereits ein Cel enthält, öffnet
  sich der Dialog **Vorhandenes Cel überschreiben?** – aktivieren Sie dort das Kontrollkästchen
  **„Für dieses Projekt nicht erneut fragen“**, um für den Rest dieses Projekts nicht mehr gefragt
  zu werden; unter [Projektbestätigungen](#project-confirmations) weiter unten erfahren Sie, wie Sie
  diese Bestätigung wieder einschalten.
- **Sichtbarkeit pro Zelle umschalten** – klicken Sie auf die Sichtbarkeitsanzeige einer Zelle, um die
  Ebene dieses Frames ein- oder auszublenden; das ist ein Rückgängig-Schritt, genau wie das Umschalten
  der Sichtbarkeit an jeder anderen Stelle.
- **Hier ein Cel erstellen** – klicken Sie mit der rechten Maustaste (oder drücken Sie die
  Kontextmenütaste der Tastatur) auf eine leere Zelle, um die Aktion **„Cel hier erstellen“** zu
  erhalten. Sie wird gar nicht erst angeboten, wenn die Zelle bereits belegt ist oder wenn der Frame
  bereits die maximale Ebenenanzahl erreicht hat – das Menü bietet nie eine Aktion an, die nur
  abgelehnt würde.
- **Scrubben** – ziehen Sie über leere Rasterzellen, um den angezeigten Frame zu scrubben, genau wie
  beim Ziehen an der Leiste entlang.
- **Spalten umordnen** – ziehen Sie einen Spaltenkopf, um Frames umzuordnen; das ist das Gegenstück
  des Rasters zum Ziehen einer Zelle der Leiste.

### Projektbestätigungen

Die Überschreibbestätigung der Rasteransicht ist eine der projektbezogenen Einstellungen der
Anwendung: Wurde sie mit „Für dieses Projekt nicht erneut fragen“ unterdrückt, bleibt sie für dieses
Projekt ausgeschaltet, bis Sie sie über **Bearbeiten ▸ Projektbestätigungen** wiederherstellen; dort
sind alle unterdrückten Bestätigungen aufgelistet, und jede lässt sich einzeln wieder einschalten.

## Zeigergesten

Die Frame-Leiste reagiert zusätzlich zu den Schaltflächen der Werkzeugleiste unter
[Frames verwalten](#managing-frames) weiter oben auf vier Zeigergesten mit **Ctrl**:

| Geste | Ergebnis |
| --- | --- |
| **Ctrl+wheel** | Wechselt im aktiven Dokument zum nächsten / vorherigen Frame. |
| **Ctrl+middle-click** | Springt direkt zu Frame 1 des aktiven Dokuments. |
| **Ctrl+left-click** | Fügt nach dem aktiven Frame einen Frame hinzu – dieselbe rückgängig zu machende Aktion wie die Schaltfläche **Frame hinzufügen**. |
| **Ctrl+right-click** | Entfernt den aktiven Frame – dieselbe rückgängig zu machende Aktion wie die Schaltfläche **Frame entfernen**, und **nur in der Zeitleiste**: Sie hat in der Rasteransicht keine Entsprechung. Wie die Schaltfläche wird sie beim letzten verbleibenden Frame eines Dokuments abgelehnt, denn ein Dokument behält immer mindestens einen Frame. |

## Speicherung

Frames, Dauern pro Frame und Frame-Tags werden alle verlustfrei in `.pixproj` gespeichert und wieder
geladen. Wenn Sie eine mit Tags versehene Animation speichern und wieder öffnen, werden die
Frame-Reihenfolge, die Dauer jedes Frames und alle Tags identisch
wiederhergestellt. Projekte, die mit früheren Versionen gespeichert wurden (bevor es Tags gab), lassen
sich weiterhin öffnen – sie werden ohne Tags geladen.

## Rückgängig, Wiederholen und was *nicht* rückgängig zu machen ist

- **Rückgängig zu machen (jeweils ein Schritt):** Frame hinzufügen / entfernen / umordnen /
  duplizieren, die Dauer eines Frames festlegen, ein Tag erstellen / bearbeiten / löschen und – in der
  Rasteransicht – ein Cel verschieben / kopieren, die Sichtbarkeit eines Cels umschalten und ein Cel
  erstellen.
- **Nicht rückgängig zu machen (Ansichtszustand):** einen Frame auswählen oder scrubben, abspielen /
  pausieren / anhalten, die Anzahl oder Tönung der Zwiebelschichten ändern und zwischen der Leiste und
  der Rasteransicht wechseln.

## Verwandte Themen

- Exportieren Sie Ihre Animation als GIF, Sprite Sheet oder Atlas unter
  [Export und Pipeline-Integration](export-and-pipeline.md).
- Nehmen Sie eine Sitzung beim Animieren mit dem Zeitraffer-Werkzeug auf – siehe
  [Visuelle Hilfen und Bedienkomfort](visual-aids.md).
