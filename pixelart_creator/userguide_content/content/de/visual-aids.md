# Visuelle Hilfen und Bedienkomfort

Die **visuellen Hilfen** unterstützen Sie dabei, Ihre Arbeit präzise zu *sehen und zu platzieren*,
ohne dass die Grafik selbst je verändert wird. Sie bieten eine **Vorschau in Originalgröße**,
**Hilfslinien und Lineale**, ein **isometrisches Raster**, ein **Perspektivraster**, ein
**Referenzboard** im Stil von PureRef, das **Bearbeiten mit mehreren Ansichten** und die
**Zeitraffer-Aufnahme**.

Jede Hilfe ist **nicht destruktiv**: Das Einschalten eines Rasters, das Setzen einer Hilfslinie, das
Hinzufügen eines Referenzbilds, das Öffnen einer zweiten Ansicht oder eine Zeitraffer-Aufnahme erzeugt
**keinen** Rückgängig-Schritt und berührt Ihre Pixel nie. Nur tatsächliche Zeichenbearbeitungen lassen
sich rückgängig machen, und sie bleiben von den visuellen Hilfen unverändert.

> **Getestete Geometrie, kein Oberflächen-Trick.** Das gesamte Ausrichten, die Teilstriche der Lineale
> und der Maßstab der Originalgröße stammen aus einer **reinen, per Unit-Tests geprüften
> Geometrie-Engine** ganz **ohne Qt**. Die Einblendungen *zeichnen* nur, was die Geometrie liefert –
> die Ausrichtungsberechnung ist derselbe Code, den die Tests ausführen, sodass das Ausrichten korrekt
> und reproduzierbar ist.

## Vorschau in Originalgröße

Das Bedienfeld **Vorschau in Originalgröße** zeigt Ihr Dokument in seiner **tatsächlichen physischen
Größe**, damit Sie beurteilen können, wie ein Sprite oder Icon wirklich aussehen wird.

- Die Vorschau skaliert das Dokument genau um den Faktor `screen_DPI / doc_PPI` – die Pixel pro Zoll des
  Dokuments (Standard: **72**) im Verhältnis zur physischen DPI des Monitors. Sonst wird nichts
  angewendet.
- Sie ist eine **schreibgeschützte** Ansicht des **gemeinsamen** Dokuments und **spiegelt Ihre
  Bearbeitungen live wider** – malen Sie auf der Arbeitsfläche, und die Vorschau wird als Teil
  derselben Bearbeitung aktualisiert, ganz ohne Schaltfläche zum Aktualisieren.

> **Wirkt die Originalgröße falsch, kalibrieren Sie.** Manche Monitore melden eine falsche (oder gar
> keine) physische Größe, sodass die abgefragte DPI nicht stimmt. Klicken Sie auf **Kalibrieren…**,
> halten Sie ein Lineal an den Balken auf dem Bildschirm und geben Sie dessen gemessene Länge ein; die
> Vorschau verwendet dann Ihre gemessene DPI. Der Maßstab wird außerdem automatisch neu berechnet,
> wenn Sie das Fenster auf einen Monitor mit anderer Auflösung verschieben.

> **HiDPI wird für Sie erledigt.** Der Maßstab ist geräteunabhängig, und Qt wendet das
> Geräte-Pixelverhältnis der Anzeige selbst an – die Vorschau multipliziert **nicht** mit dem DPR (das
> würde auf HiDPI-Bildschirmen zu einer doppelten Skalierung führen).

## Hilfslinien und Lineale

Schalten Sie die **Lineale** ein, um ein horizontales und ein vertikales Lineal mit einer
**Koordinatenanzeige** in Echtzeit zu erhalten, und ziehen Sie **Hilfslinien** aus ihnen heraus, um
Elemente auszurichten.

- **Eine Hilfslinie erstellen** – ziehen Sie aus dem oberen Lineal heraus für eine horizontale
  Hilfslinie oder aus dem linken Lineal für eine vertikale Hilfslinie.
- **Ausrichten** – Ihr Cursor richtet sich innerhalb einer kleinen Toleranz an der nächsten Hilfslinie
  aus. Die Toleranz wird in **Bildschirmpixeln** angegeben (Standard: **8 px**) und über den aktuellen
  Zoom in Dokumentkoordinaten umgerechnet, sodass sich die „Anziehungskraft“ bei jeder Zoomstufe
  gleich anfühlt.
- Die Teilstriche der Lineale folgen einer Stufenfolge aus **runden Zahlen**, `1 / 2 / 5 × 10ⁿ`, mit
  einfachen, vom Gebietsschema unabhängigen ganzzahligen Beschriftungen.

Hilfslinien gehören zum Ansichtszustand (bis zu **256** davon). Das Hinzufügen, Verschieben oder
Entfernen einer Hilfslinie lässt sich nie rückgängig machen.

## Isometrisches Raster

Aktivieren Sie das **isometrische Raster**, um auf einem rautenförmigen **2:1-dimetrischen** Gitter zu
zeichnen (dem Standard der Isometrie in der Pixelart).

- Das Raster wird gezeichnet, indem Gitterzellen durch eine **umkehrbare** Umrechnung zwischen
  Welt- und Bildschirmkoordinaten projiziert werden, und Ihr Cursor **richtet sich am nächsten Rasterpunkt aus**
  (mit einer deterministischen Regel, die bei genau halben Werten aufrundet, sodass ein Punkt genau
  zwischen zwei Rasterpunkten stets gleich aufgelöst wird).
- Der Rasterabstand (Tile-Breite) ist auf **2–1024 px** begrenzt.
- **Echte Isometrie** (etwa `1.732:1`, das heißt 1,732 zu 1) lässt sich konfigurieren, falls Sie sie der 2:1-Dimetrie
  vorziehen.
- Öffnen Sie **Visuelle Hilfen ▸ Isometrisches Raster konfigurieren…** direkt neben dem Schalter für
  das isometrische Raster, um genaue Werte festzulegen, statt sie nach Augenmaß zu schätzen: die
  **Tile-Breite**, das **Tile-Verhältnis (B:H)** (2,0 für Dimetrie, etwa 1,732 für echte Isometrie)
  und den **Ursprung** des Gitters (X, Y). Klicken Sie auf **OK**, um die neue Konfiguration auf den
  aktiven Tab anzuwenden, oder auf **Abbrechen**, um sie unverändert zu lassen.

> **Weit herausgezoomte Raster blenden sich aus Leistungsgründen aus.** Wird die Kante eines Tiles auf
> dem Bildschirm kleiner als **32 px**, ist das Gitter zu dicht, um lesbar zu sein; die Einblendung
> **verzichtet dann aufs Zeichnen**, statt das Rendering-Budget von 16 ms zu sprengen. Zoomen Sie
> wieder hinein, und sie erscheint erneut.

## Perspektivraster

Aktivieren Sie das **Perspektivraster**, um mit **1-, 2- oder 3-Punkt-Perspektive** zu zeichnen.

- Sie setzen die **Fluchtpunkte** (bis zu **3**); die Einblendung zeichnet von jedem einen
  deterministischen **Fächer aus Hilfslinien**, dazu die Horizontlinie.
- Ihr Cursor **bindet seine Richtung an die nächste Fluchtlinie**, wenn er innerhalb der
  Ausrichtungstoleranz liegt; außerhalb der Toleranz gibt es **kein Ausrichten**, sodass Sie weiterhin
  frei zeichnen können.

## Referenzboard

Das **Referenzboard** ist ein Board im Stil von PureRef in einem **eigenen** Fenster, in dem Sie neben
Ihrer Arbeitsfläche Inspiration sammeln können.

- Sie können Bilder **hinzufügen** und jedes einzelne **verschieben**, **skalieren** und in der
  **Z-Reihenfolge anordnen**, das gesamte Board verschieben und zoomen sowie das Fenster auf Wunsch
  **immer im Vordergrund** halten.
- Das Board fasst bis zu **256** Bilder und ist **vollständig von Ihrer Grafik getrennt** –
  Referenzbilder werden nie in das Dokument eingerechnet und erscheinen nie in einem Export.
- Ein Board lässt sich als `.pixboard`-Datei **speichern / öffnen**. Das Layout bleibt beim Roundtrip
  exakt erhalten. Eine fehlerhafte Board-Datei führt zu einer klaren Fehlermeldung – es gibt nie einen
  Absturz, und nie wird etwas aus der Datei ausgeführt.

## Bearbeiten mit mehreren Ansichten

Öffnen Sie **mehrere Ansichten desselben Dokuments** gleichzeitig – zum Beispiel eine
hineingezoomte Detailansicht neben einer Übersicht, die ins Fenster eingepasst ist.

- Jede zusätzliche Ansicht stellt das **eine gemeinsame Dokument** dar, sodass eine Bearbeitung in der
  Hauptarbeitsfläche in **jeder** Ansicht (und in der Vorschau in Originalgröße) **sofort und ohne
  manuelles Aktualisieren** erscheint.
- Jede Ansicht behält ihren **eigenen** Zoom und ihre eigene Verschiebung – beides gilt pro Ansicht und
  wird **nicht** synchronisiert.
- Bis zu **8** gleichzeitige Ansichten (die Hauptarbeitsfläche zählt als eine). Zusätzliche Ansichten
  dienen nur der Navigation (Scrollen/Zoomen); das Malen bleibt der Hauptarbeitsfläche vorbehalten.

> **Mehrere *Ansichten* gegenüber mehreren *Arbeitsflächen*.** Das ist etwas anderes als
> [mehrere Arbeitsflächen](multi-canvas.md): Diese sind **isolierte** Tabs, jeweils ein *anderes*
> Dokument mit eigenen Ebenen und eigenem Rückgängig-Verlauf. Die Mehrfachansicht öffnet mehrere
> Fenster auf **ein** Dokument, die synchron bleiben.

## Zeitraffer-Aufnahme

Öffnen Sie das Bedienfeld **Zeitraffer** über **Visuelle Hilfen ▸ Zeitraffer**, um einen Zeitraffer
Ihrer Bearbeitungssitzung aufzunehmen und abzuspielen und so zu zeigen, wie ein Werk entstanden ist.

- Klicken Sie auf **Aufnehmen**, um die Aufnahme zu starten; die Aufnahme hängt **einen Frame pro
  abgeschlossener Bearbeitung** an (jeder rückgängig zu machende Befehl). Drücken Sie die Schaltfläche
  erneut, um die Aufnahme zu beenden.
- Die Aufnahme gehört zum **Ansichts-/Sitzungszustand** – sie lässt sich nie rückgängig machen und
  verändert das Dokument nie.
- Mit **Speichern… / Öffnen…** speichern bzw. öffnen Sie die Sitzung als `.pixtimelapse`-Datei (die
  erste Schaltfläche öffnet den Dateidialog **Zeitraffer speichern**, die zweite den Dateidialog
  **Zeitraffer öffnen**). Die Sitzung speichert ein geordnetes Manifest aus **Befehlsverweisen, nicht
  Pixeln**, sodass sie klein bleibt und **deterministisch wiedergegeben wird**: Dieselbe aufgenommene
  Sitzung liefert, zweimal abgespielt, die **identische** Frame-Sequenz. Sitzungen sind auf **4096**
  Frames begrenzt; eine fehlerhafte Datei führt zu einer dem Benutzer angezeigten Fehlermeldung.

### Wiedergabe

Sobald eine Sitzung aufgenommen oder geöffnet ist, spielt dasselbe Bedienfeld sie ab:

- **Abspielen / Pause** schaltet die Wiedergabe der rekonstruierten Frame-Sequenz um; **Stopp** hält
  sie an. Ein absoluter **Positionsregler** springt direkt zu jedem beliebigen Frame, und eine
  **Geschwindigkeitsauswahl** (0.25x, 0.5x, 1x, 2x, 4x) ändert, wie schnell die Frames voranschreiten –
  nichts davon berührt Ihr Dokument, und solange die Wiedergabe läuft (oder mitten in der Sequenz
  pausiert ist), werden Bearbeitungen des Dokuments abgelehnt, bis Sie anhalten.
- Beim Abspielen einer Sitzung, die Sie aus einer `.pixtimelapse`-Datei **geöffnet** haben (statt einer
  gerade aufgenommenen), erscheint ein Banner **Wieder geöffnete Aufnahme**, das Sie daran erinnert,
  dass die gespeicherte Aufnahme wiedergegeben wird und nicht Ihr aktuelles Dokument.
- Die Wiedergabe kann es ablehnen, einen bestimmten Frame zu rekonstruieren, statt einen falschen zu
  zeigen. Mögliche Meldungen: Die Aufnahme enthält keine rekonstruierbaren Daten; die Daten eines
  Frames sind unvollständig; eine angeforderte Position liegt außerhalb des aufgenommenen Bereichs; die
  Aufnahme stimmt nicht mit dem aktuellen Rückgängig-Verlauf des Dokuments überein; oder einem Frame
  fehlt die stabile Identität, die die Wiedergabe benötigt. Jede Ablehnung wird als klare, konkrete
  Meldung ausgegeben – nie als stilles Überspringen oder Absturz.

> **Der Video-/GIF-Export folgt später.** Diese Version erzeugt die reproduzierbare **Frame-Sequenz**
> und ihre eigene Wiedergabe. Das Kodieren in ein Video oder GIF zum Teilen nutzt später die
> [Export-Pipeline](export-and-pipeline.md) – die aufgenommene Sequenz ist die Eingabe dieser
> Pipeline.

## Barrierefreiheit, Designs und Sprachen

Jedes Steuerelement der visuellen Hilfen stellt einen zugänglichen Namen bereit (und, wo es nicht
offensichtlich ist, eine Beschreibung), ist per Tastatur mit sichtbarem Fokusindikator erreichbar,
wird in beiden Designs, **hell und dunkel**, korrekt dargestellt (die Farben der Einblendungen und
Hilfslinien werden einmal pro Rolle definiert und bleiben über der Grafik lesbar) und hat
**vollständig übersetzbare** Texte, die bei einem Sprachwechsel neu gesetzt werden.

## Was nicht abgedeckt ist

- **Der Export eines Zeitraffers als Video/GIF** – an die Export-Pipeline verschoben; diese Version
  liefert die reproduzierbare Sequenz.
- Eine **gehostete / Cloud-Bibliothek für Referenzbilder** – das Board hier ist lokal.
- **KI-gestützte Erkennung der Perspektive / automatische Fluchtpunkt-Erkennung** – eine spätere Phase.
