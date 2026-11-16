# Cloud: Speichern, Versionen und automatisches Speichern

In dieser Version läuft die **Cloud-Schicht** auf einem integrierten Adapter, der im Arbeitsspeicher
arbeitet, sodass der Versionsverlauf und die automatisch gespeicherte Kopie nur so lange bestehen, bis Sie
die Anwendung schließen; sie schützen Sie nicht vor einem Absturz oder Stromausfall. Speichern Sie eine
lokale Kopie des Projekts für alles, was Sie behalten möchten. Innerhalb dieser Grenze können Sie mit der
Cloud-Schicht eine **Verbindung herstellen**, das aktuelle Projekt **speichern**, es wieder **öffnen**,
einen **Versionsverlauf** durchsuchen, einen früheren Speicherstand **wiederherstellen** und beim Arbeiten
eine **automatisch gespeicherte Arbeitskopie** vorhalten.

Alles in dieser Anleitung wird über das Menü **Cloud** in der Menüleiste bedient.

> **Ein anbieterunabhängiger Port – kein Lock-in.** Die Anwendung spricht nie direkt mit einem bestimmten
> Anbieter. Alle Cloud-Arbeit läuft über **eine anbieterunabhängige Schnittstelle** (den *Cloud-Port*):
> verbinden, speichern, öffnen, Versionen auflisten, wiederherstellen und den Speicher für automatisches
> Speichern und Wiederherstellung. Die Anwendung verhält sich **identisch**, egal welcher Anbieter dahinter
> steht; Sie sind also nicht gebunden, und ein neuer Anbieter ist einfach ein neuer Adapter hinter demselben
> Port.

Was in dieser Version funktioniert: der anbieterunabhängige Port, ein vollständig getesteter integrierter
Adapter, der `.pixproj`-Roundtrip mit der Cloud, Versionsverlauf plus Wiederherstellung und automatisches
Speichern; **geteilte Projekte, Kommentare und Anwesenheit**, die auf einem Adapter im Arbeitsspeicher
innerhalb eines einzelnen Anwendungsfensters laufen (ein anderes Fenster oder die Kopie einer anderen Person kann sie nicht
sehen); und lokales **Branching der Grafik**. Was noch nicht funktioniert: Die **echten Anbieter Google
Drive / OneDrive / Dropbox** sind in der Speicherschicht implementiert, lassen sich aber nicht im Menü Cloud
auswählen, und das **gemeinsame Bearbeiten in Echtzeit mit Live-Cursorn** kann keine Verbindung herstellen.
Alle diese Funktionen zur Zusammenarbeit sind in
[Geteilte Projekte, Kommentare, Anwesenheit und Echtzeit](collaboration.md) beschrieben.

## Einen Cloud-Anbieter verbinden

Cloud-Aktionen sind deaktiviert, bis Sie eine Verbindung herstellen.

1. Öffnen Sie das Menü **Cloud**.
2. Wählen Sie **Verbinden…**. Damit wird der integrierte Adapter über den Cloud-Port verbunden und der Rest
   des Menüs Cloud aktiviert (**In Cloud speichern…**, **Aus Cloud öffnen…**, **Versionsverlauf…** und
   **Verbindung trennen**).
3. Um sich abzumelden, wählen Sie **Cloud ▸ Verbindung trennen**. Damit wird die Verbindung beendet, und
   die Cloud-Aktionen sind wieder deaktiviert, bis Sie erneut eine Verbindung herstellen.

> **Ihre Zugangsdaten verlassen die Speicherschicht nie.** Wenn ein echter Anbieter-Adapter verwendet wird,
> läuft der Anmeldevorgang (OAuth) **vollständig innerhalb der Speicherschicht** – die Anwendung startet für
> Sie nur Ihren System-Browser. Token werden der Benutzeroberfläche **nie** angezeigt, **nie** in eine
> `.pixproj`-Datei geschrieben und **nie** in Protokolle geschrieben. Die Benutzeroberfläche sieht immer nur
> einen einfachen Zustand *verbunden / nicht verbunden*.

> **Der integrierte Adapter.** Die Verbindung in dieser Version ist ein integrierter Adapter im
> Arbeitsspeicher, der deterministisch ist und weder Netzwerk noch Konto braucht – er macht den gesamten
> Ablauf aus Speichern und Versionen innerhalb einer Sitzung nutzbar. Weil er im Arbeitsspeicher lebt, ist
> alles, was er enthält, weg, sobald Sie die Anwendung schließen. Die echten Online-Anbieter sind weiter
> unten unter *Einen echten Cloud-Anbieter verbinden* beschrieben, lassen sich in dieser Version aber nicht
> im Menü Cloud auswählen.

## Einen echten Cloud-Anbieter verbinden

Die Speicherschicht enthält **echte** Anbieter für Google Drive, OneDrive und Dropbox, die hinter
**demselben** Cloud-Port sitzen wie der integrierte Adapter. Wird ein solcher Anbieter verwendet, laufen die
Schritte in dieser Anleitung (Speichern, Öffnen, Versionsverlauf) genauso auf Ihrem Online-Speicher. Diese
Version hat keinen Befehl im Menü Cloud, der einen davon auswählt: **Verbinden…** verbindet den integrierten
Adapter.

> **Funktion, die Zugangsdaten voraussetzt.** Die echten Anbieter sind **an Zugangsdaten gebunden**: Jeder
> bräuchte eine OAuth-**Client-ID** für den gewählten Dienst und einen funktionierenden Netzwerkzugang, daher
> sind sie nicht standardmäßig eingeschaltet, und diese Version hat keinen Befehl im Menü Cloud, der einen
> einschaltet. Der integrierte Adapter oben braucht nichts davon.

### So funktioniert die Anmeldung

1. Die Verwendung eines Anbieters der Speicherschicht startet dessen Anmeldung. **Cloud ▸ Verbinden…** tut
   das in dieser Version nicht: Es verbindet den integrierten Adapter.
2. Die Anmeldung öffnet Ihren **System-Browser** auf der Anmelde- und Zustimmungsseite des Anbieters.
   PixelArt Creator verwendet den standardmäßigen Desktop-Ablauf **OAuth Authorization Code + PKCE über eine
   Loopback-Weiterleitung** – es gibt **keine eingebettete Webansicht** und **kein Client-Secret**, das in
   der Anwendung gespeichert wäre.
3. Genehmigen Sie den Zugriff im Browser. Der Browser leitet zur Anwendung zurück, die die Verbindung
   abschließt. Die Aktionen zum Speichern, Öffnen und für Versionen im Menü Cloud werden dann genauso
   aktiviert wie beim integrierten Adapter.
4. Um sich abzumelden, wählen Sie **Cloud ▸ Verbindung trennen**.

> **Ihre Zugangsdaten verlassen die Speicherschicht nie.** Die gesamte Anmeldung läuft **vollständig
> innerhalb der Speicherschicht**. Ihr **Refresh-Token wird im Schlüsselbund des Betriebssystems
> gespeichert** (pro Anbieter abgelegt); das kurzlebige Zugriffstoken wird nur im Arbeitsspeicher gehalten
> und automatisch erneuert. Token werden der Benutzeroberfläche **nie** angezeigt und nie in eine
> `.pixproj`-Datei oder in Protokolle geschrieben.

> **Gleiches Verhalten, jeder Anbieter.** Weil jeder Anbieter hinter dem einen Cloud-Port sitzt, funktionieren
> Speichern und das Durchsuchen von Versionen gleich, egal ob der integrierte Adapter oder Drive / OneDrive /
> Dropbox dahintersteht. Das ist der Aufbau ohne Lock-in; einen Anbieter im Menü Cloud auszuwählen ist in
> dieser Version nicht möglich.

## Ein Projekt in der Cloud speichern

1. Wählen Sie bei geöffnetem Projekt und verbundenem Anbieter **Cloud ▸ In Cloud speichern…**.
2. Füllen Sie auf Nachfrage das Feld **Name des Cloud-Projekts** aus. Dieser Name ist der Schlüssel, unter dem Ihr Projekt
   gespeichert wird; verwenden Sie denselben Namen erneut, um dem Projekt weitere Versionen hinzuzufügen.
3. Die Anwendung serialisiert das Projekt zu einer `.pixproj`-Datei und speichert es als **neue Version**. Wenn der
   Vorgang abgeschlossen ist, zeigt die Statusleiste *„In der Cloud gespeichert.“*

Jeder Speichervorgang wird als ganze `.pixproj`-Datei übertragen – im **selben** validierten, versionierten
Speicherformat, das für lokale Dateien verwendet wird. Die Cloud-Schicht fügt kein eigenes neues Format
hinzu; sie transportiert die `.pixproj`-Datei einfach als atomare *Synchronisierungseinheit*.

> **Das Speichern friert die Anwendung nie ein.** Das Serialisieren und Hochladen läuft **außerhalb des
> GUI-Threads**, sodass das Fenster auch bei einem großen Projekt (bis zu 8K) bedienbar bleibt – Sie können
> weiterarbeiten, während ein Speichervorgang abgeschlossen wird.

> **Jedes Speichern ist eine neue Version.** Das Speichern überschreibt die vorherige Cloud-Speicherung
> **nicht** – es hängt einen neuen Eintrag an den Versionsverlauf an. Der Verlauf ist auf die letzten **100**
> Versionen pro Projekt begrenzt.

## Ein Projekt aus der Cloud öffnen

1. Wählen Sie **Cloud ▸ Aus Cloud öffnen…**.
2. Geben Sie im Feld **Name des Cloud-Projekts** an, welches Projekt geöffnet werden soll.
3. Die Anwendung ruft die neueste Version des Projekts ab und öffnet sie in einem **neuen Tab**.

Das Öffnen ersetzt oder stört das, woran Sie gerade arbeiten, **nicht** – das Cloud-Projekt kommt als eigener
Tab herein.

> **Cloud-Dateien werden als nicht vertrauenswürdig behandelt.** Eine aus der Cloud abgerufene `.pixproj`-Datei
> wird defensiv validiert, genau wie eine lokale Datei: Jedes Feld wird auf Typ und Grenzen geprüft, die
> Nutzlast ist größenbegrenzt, und eine fehlerhafte, übergroße oder in einer unbekannten Version vorliegende
> Datei wird mit einem **klaren Fehler** abgelehnt – nie durch einen Absturz und **nie**, indem Code aus der
> Datei ausgeführt würde. Lässt sich ein abgerufenes Projekt nicht validieren, erhalten Sie einen
> Warndialog, und Ihre aktuelle Arbeit bleibt unangetastet.

## Versionsverlauf durchsuchen und eine Version wiederherstellen

Jedes Speichern erzeugt eine neue, geordnete Version, und Sie können zu jeder davon zurückgehen. Der
Versionsverlauf besteht nur für die aktuelle Sitzung: Der integrierte Adapter hält ihn im Arbeitsspeicher und
beginnt beim nächsten Start der Anwendung leer. Speichern Sie eine lokale Kopie des Projekts für alles, was
Sie behalten möchten.

1. Wählen Sie **Cloud ▸ Versionsverlauf…** (wenn Sie in dieser Sitzung noch kein Cloud-Projekt geöffnet oder
   gespeichert haben, werden Sie zuerst nach dem Namen des Cloud-Projekts gefragt).
2. Der Dialog **Cloud-Versionsverlauf** listet jede gespeicherte Version von der ältesten bis zur neuesten
   auf, mit diesen Spalten:
    - **Version** – die laufende Nummer bzw. Kennung der Version.
    - **Marker** – der Ordnungsmarker der Version.
    - **Größe (Byte)** – die Größe der gespeicherten `.pixproj`-Datei.
    - **Angeheftet** – ob die Version angeheftet (aufbewahrt) ist – *Ja* / *Nein*.
    - **Vorgänger** – die Version, auf die dieses Speichern folgte.
3. Wählen Sie eine Version aus, um ihre Details im Vorschaubereich unter der Liste zu sehen.
4. Klicken Sie auf **Wiederherstellen** (oder doppelklicken Sie auf die Zeile oder drücken Sie **Enter**),
   um diese Version zurückzuholen.

> **Wiederherstellen ist sicher – es öffnet einen neuen Tab.** Beim Wiederherstellen einer früheren Version
> wird sie abgerufen und validiert und dann in einem **neuen Tab** geöffnet. Sie überschreibt Ihre aktuelle
> Arbeit oder Ihre neueste Cloud-Speicherung **nicht** – Sie entscheiden, was mit der wiederhergestellten
> Kopie geschieht.

Die Versionsliste wird abgerufen, bevor sich der Dialog öffnet, und zwar außerhalb des GUI-Threads, sodass
das Durchsuchen des Verlaufs die Anwendung nie einfriert.

## Automatisches Speichern und der Wiederherstellungsspeicher

Während Sie an einem verbundenen Projekt arbeiten, **speichert** die Anwendung Ihre Arbeitskopie im
Hintergrund automatisch in einem eigenen **Wiederherstellungsspeicher**. In dieser Version wird dieser
Speicher nur im Arbeitsspeicher gehalten und schützt Ihre Arbeit daher innerhalb der Sitzung, nicht über
einen Absturz hinweg.

- Das automatische Speichern läuft in einem festen Takt (Standard: **alle 2 Minuten**) und **nur, wenn das
  Dokument ungespeicherte Änderungen hat** – ein unverändertes Dokument wird nie automatisch gespeichert.
- Der Wiederherstellungsspeicher ist **vom Versionsverlauf getrennt**. Das automatische Speichern erzeugt nie
  eine sichtbare Version und **überschreibt nie Ihre letzte ausdrückliche Cloud-Speicherung**.
- Das automatische Speichern läuft außerhalb des GUI-Threads und unterbricht Ihr Zeichnen daher nie.

### Die Wiederherstellungsabfrage beim Neustart

Die Wiederherstellung beim Neustart steht in dieser Version nicht zur Verfügung. Der integrierte Adapter
behält den Wiederherstellungsspeicher nicht über einen Neustart hinweg, und die Abfrage **Nicht gespeicherte
Arbeit wiederherstellen** wird nur einmal geprüft, beim Start der Anwendung, bevor Sie eine Verbindung
herstellen können. Nach einem Absturz oder Stromausfall erscheint beim nächsten Start der Anwendung keine
Abfrage. Speichern Sie deshalb selbst eine lokale Kopie
des Projekts, bis ein dauerhafter Anbieter ausgewählt werden kann.

Die Abfrage selbst bietet zwei Optionen (in dieser Version sehen Sie sie nicht):

- **Wiederherstellen** – ruft die automatisch gespeicherte Kopie ab, validiert sie und öffnet sie in einem
  **neuen Tab**. Ihre letzte ausdrückliche Speicherung bleibt unberührt.
- **Verwerfen** – schließt die Abfrage und lässt alles, wie es war.

> **Auch die Wiederherstellung wird defensiv dekodiert.** Die wiederhergestellte Kopie durchläuft dieselbe
> Prüfung für nicht vertrauenswürdige Eingaben wie jede Cloud-Datei, sodass ein fehlerhafter
> Wiederherstellungsspeicher mit einem klaren Fehler abgelehnt statt geöffnet wird.

> **Automatisches Speichern braucht eine Verbindung.** Es arbeitet über den Cloud-Port und läuft daher nur,
> solange Sie **verbunden** sind. Es schützt Ihre Arbeit innerhalb der Sitzung, nicht über einen Absturz
> hinweg.

## Der Rest des Meilensteins Cloud und Zusammenarbeit

Diese Seite behandelt die Cloud-Arbeit für einen einzelnen Benutzer – Speichern, Versionen, automatisches
Speichern – sowie die Anbieter der Speicherschicht. Die Funktionen zur Zusammenarbeit (in dieser Version auf
einem eigenen Adapter im Arbeitsspeicher, pro Anwendungsfenster; das gemeinsame Bearbeiten in Echtzeit und
Live-Cursor können keine Verbindung herstellen) – **geteilte Projekte und Mitgliedschaft**, **Kommentare**,
**Anwesenheit**, **deterministische Konvergenz**, **gemeinsames Bearbeiten in Echtzeit und Live-Cursor** und
**Branching der Grafik** – sind alle in
[Geteilte Projekte, Kommentare, Anwesenheit und Echtzeit](collaboration.md) beschrieben.
