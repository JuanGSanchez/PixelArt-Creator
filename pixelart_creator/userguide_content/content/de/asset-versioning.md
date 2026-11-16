# Asset-Versionierung und projektübergreifende Wiederverwendung

Die Asset-Bibliothek führt für jedes Asset einen **Versionsverlauf, an den nur angehängt wird**, lässt Sie
**ein geteiltes Asset in mehreren Projekten wiederverwenden, ohne seine Bytes zu duplizieren**, ermöglicht
**Export und Import** der Assets, die ein Projekt referenziert, als in sich geschlossenes Paket und
funktioniert **vollständig offline**; ein Cloud-gestützter Blob-Speicher existiert in der Speicherschicht,
doch diese Version schließt ihn nicht an (siehe *Optionale Cloud-Anbindung*). Sie erreichen diese Funktionen
über das Menü **Bibliothek**, neben den Bedienfeldern für die [Asset-Bibliothek](asset-library.md) und für
[Abhängigkeiten](asset-dependencies.md), auf denen sie aufbauen.

> **Referenz statt Kopie.** Alles hier beruht auf einer Idee, die die Bibliothek bereits verwendet: Die Bytes
> eines Assets werden **einmal** gespeichert, mit ihrem Inhalt als Schlüssel, in einem
> inhaltsadressierbaren Speicher, und ein Projekt hält nur eine **Referenz** (eine stabile ID plus den
> Inhalts-Hash, den es erwartet). Versionierung und Wiederverwendung verschieben beide Referenzen und
> prüfen Inhalte – sie legen nie eine zweite Kopie Ihrer Grafik an.

## Versionsverlauf

Jedes Mal, wenn Sie einen neuen Zustand eines Assets festhalten, hängt die Bibliothek eine **Revision** an
den Verlauf dieses Assets an:

- **Es wird nur angehängt; Revisionen sind unveränderlich.** Eine Revision wird nie an Ort und Stelle
  geändert oder gelöscht. Wenn Sie einen neuen Zustand festhalten, kommt eine neue aktuelle Revision hinzu;
  die früheren Revisionen bleiben genau so, wie sie waren, sodass der Verlauf ein getreues Protokoll dessen
  ist, wie sich das Asset entwickelt hat.
- **Über den Inhalt adressiert.** Jede Revision wird durch den **Inhalts-Hash** ihrer Bytes identifiziert
  und mit der Revision verknüpft, auf die sie folgte, sodass der Verlauf eine inhaltsadressierte Kette
  bildet. Zwei Revisionen mit identischen Bytes teilen sich einen gespeicherten Blob (Deduplizierung).
- **Denselben Inhalt zweimal festzuhalten bewirkt nichts.** Wenn Sie Inhalt festhalten, dessen Hash mit dem
  der aktuellen Revision übereinstimmt, bleibt das **ohne Wirkung**: Es wird weder eine neue Revision noch
  ein neuer Blob hinzugefügt.
- **Begrenzt.** Ein Asset behält höchstens eine feste Maximalzahl von Revisionen; wird sie überschritten,
  wird das mit einem klaren Fehler gemeldet, statt stillschweigend Verlauf zu verwerfen.

### Revisionen durchsuchen und wiederherstellen

Das Bedienfeld **Asset-Versionen** listet die Revisionen des ausgewählten Assets der Reihe nach auf. Wählen
Sie eine aus, um sie **anzusehen**, oder um eine frühere Revision **wiederherzustellen**, damit sie wieder
die aktuelle ist.

> **Wiederherstellen fügt eine neue Revision hinzu – es schreibt den Verlauf nie um.** Beim
> Wiederherstellen einer früheren Revision werden die Revisionen, die ihr folgten, **nicht** gelöscht.
> Stattdessen hält der Versionsbrowser die (per Inhalts-Hash geprüften) Bytes der gewählten Revision erneut
> als **neue aktuelle Revision** fest. Der Verlauf wächst immer nur, sodass Sie jederzeit wieder einen
> Schritt zurückgehen können.

Beim Wiederherstellen prüft der Versionsbrowser außerdem die Bytes der Revision gegen den Hash, den der Eintrag
erwartet; ein Blob, der nicht mehr zu seinem aufgezeichneten Hash passt, wird **mit einem klaren Fehler
abgelehnt** (Schutz vor Manipulation und Beschädigung), statt geladen zu werden.

## Projektübergreifende Wiederverwendung (referenzieren, nicht kopieren)

Mit dem Bedienfeld **Asset-Wiederverwendung** können Sie **ein vorhandenes geteiltes Asset in einem anderen
Projekt referenzieren**. Weil die Bibliothek Assets referenziert, statt sie zu kopieren, kostet die
Wiederverwendung keinen Speicherplatz:

- **Das Referenzieren kopiert keine Bytes.** Wenn Sie einem Projekt ein geteiltes Asset hinzufügen, wird die
  Referenz festgehalten; die geteilten Bytes bleiben **einmal** im inhaltsadressierbaren Speicher. Die
  Anzahl der gespeicherten Blobs bleibt durch das Referenzieren **unverändert**.
- **Geteilte Assets sind markiert.** Wenn mehr als ein Projekt dasselbe Asset referenziert, zeigt das
  Bedienfeld es als **Geteilt** an, sodass Sie sehen, welche Assets an mehreren Stellen verwendet werden.
- **Das Vorhandensein wird geprüft, nie geschrieben.** Bevor es ein geteiltes Asset referenziert, vergewissert
  sich das Bedienfeld, dass die geteilten Bytes tatsächlich vorhanden sind; fehlen sie, meldet es einen
  klaren Fehler, statt eine ins Leere zeigende Referenz anzulegen. Es liest nur – es schreibt nie eine neue
  Kopie.

> **Warum das sicher ist.** Wiederverwendung und das [Abhängigkeitsdiagramm](asset-dependencies.md)
> arbeiten zusammen: Ein wiederverwendetes Asset ist eine Referenz wie jede andere, sodass die passive
> Anzeige defekter Referenzen eine Wiederverwendung markiert, deren Ziel später fehlt oder sich ändert.

## Wenn sich ein geteiltes Asset ändert

Wenn Sie ein Projekt öffnen, das ein Bibliotheks-Asset referenziert, das inzwischen bearbeitet wurde, zeigt
sich die Abfrage **Bibliotheks-Asset aktualisiert**, einmal pro geändertem Asset:

- **Änderung übernehmen** löst das Asset ab jetzt mit dem aktuellen Inhalt der Bibliothek auf; die Referenz
  des Projekts wechselt zur neuesten Revision der Bibliothek.
- **Referenzierte Version beibehalten** löst weiterhin genau den Inhalt auf, den das Projekt bereits
  referenziert – an der Referenz ändert sich nichts.

Das Abbrechen oder Schließen der Abfrage verhält sich wie **Referenzierte Version beibehalten**. Wenn Sie bei
einer der beiden Optionen **Nicht erneut fragen** aktivieren, merkt sich die Anwendung diese Wahl für
künftige Änderungen an diesem Asset in diesem Projekt; die Abfrage können Sie später über **Bearbeiten ▸
Projektbestätigungen ▸ Wenn sich ein referenziertes Bibliotheks-Asset ändert** wiederherstellen. Die Wahl
wird gespeichert, sobald Sie sie treffen, ob Sie das Kontrollkästchen aktivieren oder nicht – Sie müssen das
Projekt nicht speichern, damit sie bestehen bleibt. Lassen Sie **Nicht erneut fragen** deaktiviert, gilt Ihre
Antwort trotzdem für diese Änderung; bei der nächsten, anderen Änderung an diesem Asset wird erneut gefragt.

## Die Assets eines Projekts exportieren und importieren

**Projektpaket exportieren** bündelt genau die Assets, die ein Projekt referenziert, zu einem **in sich
geschlossenen, portablen Paket**, sodass sich das Projekt auf einem anderen Rechner vollständig öffnet;
**Projektpaket importieren** holt ein solches Paket wieder herein. Beide Befehle erreichen Sie über das Menü
**Bibliothek**.

- **Genau die referenzierten Assets – nicht mehr, nicht weniger.** Der Export ermittelt alle Referenzen des
  Projekts und bündelt genau die Blobs dieser Assets, jeweils einmal nach Inhalt gespeichert, dazu einen
  Katalogindex und Begleitdateien pro Asset.
- **Nutzt das vorhandene Projektformat.** Das Paket baut auf den vorhandenen Katalog- und
  Projektmechanismen auf – es gibt kein neues Format zu lernen.
- **Der Import ist defensiv.** Ein Paket wird als **nicht vertrauenswürdige Eingabe** behandelt: Es wird
  geparst, ohne etwas auszuführen, auf Größe und Struktur geprüft, und **jeder Pfad wird darauf geprüft,
  dass er innerhalb des Pakets bleibt** (Schutz vor Path-Traversal-Angriffen). Jeder Blob wird beim Lesen
  **per Inhalts-Hash verifiziert**, sodass ein manipuliertes oder beschädigtes Paket mit einem klaren Fehler
  abgelehnt wird.

## Optionale Cloud-Anbindung

Die Bibliothek speichert jeden Blob **lokal** und funktioniert **vollständig offline**. Die Speicherschicht
enthält außerdem einen optionalen Cloud-gestützten Blob-Speicher, doch **diese Version schließt ihn nicht
an**: Die Bibliothek ist immer lokal, und weder **Cloud ▸ Verbinden…** (das den integrierten Adapter im
Arbeitsspeicher verbindet, der in
[Cloud: Speichern, Versionen und automatisches Speichern](cloud-and-collaboration.md) beschrieben ist) noch
ein echter Anbieter schaltet ihn ein. Sobald dieser Speicher angeschlossen ist, soll sich an Ihrer Arbeit mit der Bibliothek nichts
ändern:

- **Lokal zuerst.** In dieser Version ist die Bibliothek rein lokal; die Cloud-Anbindung würde **nur dann
  genutzt, wenn ein Anbieter verbunden ist**.
- **Dieselbe Speicherschnittstelle.** Die Cloud-Anbindung ist nur ein weiteres Blob-Backend hinter derselben
  Schnittstelle, die der lokale Speicher verwendet, sodass sich Katalog, Revisionen und Wiederverwendung
  identisch verhalten, ob die Anbindung lokal oder geteilt ist.
- **Cloud-Daten werden verifiziert und zwischengespeichert.** Ein aus der Cloud abgerufener Blob wird vor der
  Verwendung **per Inhalts-Hash verifiziert** und dann lokal zwischengespeichert, sodass spätere
  Lesezugriffe offline bleiben.
- **Keine Anbieterdetails dringen durch.** Kein Anbietername, keine Zugangsdaten und kein SDK-Typ tauchen in
  der Bibliothek auf – die Cloud-Anbindung hängt nur von derselben anbieterunabhängigen
  Cloud-Schnittstelle ab, die der Rest der Anwendung verwendet.

## Barrierefreiheit, Designs und Sprache

Jedes Steuerelement im Versionsbrowser und im Bedienfeld für die Wiederverwendung hat einen zugänglichen
Namen und ist über die Tastatur erreichbar, alle Beschriftungen sind vollständig übersetzbar, und beide
Bedienfelder werden im hellen und im dunklen Design korrekt dargestellt.
