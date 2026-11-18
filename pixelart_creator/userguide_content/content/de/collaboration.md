# Geteilte Projekte, Kommentare, Anwesenheit und Echtzeit

In dieser Version arbeitet die **Zusammenarbeitsschicht** innerhalb eines einzigen laufenden Fensters der Anwendung,
vollständig im Arbeitsspeicher (siehe den Hinweis unten). In diesem Fenster können Sie **ein Projekt teilen**
– mit einem benannten Kreis von Mitgliedern, jedes mit einer Rolle –, **Kommentare** dazu hinterlassen und
erledigen, sehen, **wer sonst anwesend ist**, und die Grafik wie Quellcode **verzweigen**. **Das gemeinsame
Bearbeiten in Echtzeit und Live-Cursor können in dieser Version keine Verbindung herstellen**: **Echtzeit
starten…** tritt keiner Sitzung bei, sodass die Abschnitte zur Echtzeit unten beschreiben, wie eine Sitzung
funktioniert, sobald eine Verbindung besteht. Die Schicht ist dafür ausgelegt, dass mehrere Personen an einem
Cloud-Projekt zusammenarbeiten, und folgt dem anbieterunabhängigen Aufbau der
[Cloud-Schicht](cloud-and-collaboration.md), aber in dieser Version speichern oder öffnen die Bedienfelder
keine `.pixproj`-Datei; sie verwalten nur die Mitgliederliste, die Kommentare und die Anwesenheit.

> **Womit sich diese Version verbindet.** Die Bedienfelder **Geteilte Projekte**, **Kommentare** und
> **Anwesenheit** verwenden einen integrierten Adapter, der alles im Arbeitsspeicher innerhalb des einen
> Anwendungsfensters hält, das ihn erzeugt hat. Jedes Fenster hat seinen eigenen; ein zweites Fenster der
> Anwendung auf demselben Computer kann daher die Projekte, Mitglieder, Kommentare oder die Anwesenheit des
> ersten nicht sehen, und die Kopie einer anderen Person ebenso wenig. Es wird nichts über ein Netzwerk
> gesendet oder auf den Datenträger geschrieben, und alles ist weg, sobald Sie die Anwendung schließen.
> **Echtzeit starten…** kann in dieser Version keiner Sitzung beitreten (siehe *Gemeinsames Bearbeiten in
> Echtzeit* unten). Branching ist eine lokale Funktion innerhalb der Sitzung.

Alles in dieser Anleitung wird über das Menü **Cloud** bedient, das unter dem Eintrag für den
Versionsverlauf die andockbaren Bedienfelder zur Zusammenarbeit und die Steuerung für Echtzeit enthält:

- **Cloud ▸ Geteilte Projekte** – das aktuelle Projekt teilen und seine Mitglieder verwalten.
- **Cloud ▸ Kommentare** – Kommentare hinzufügen, beantworten und erledigen.
- **Cloud ▸ Anwesenheit** – sehen, wer anwesend ist, und sich selbst als anwesend anzeigen.
- **Cloud ▸ Echtzeit starten… / Echtzeit beenden** – einer Live-Sitzung zum gemeinsamen Bearbeiten beitreten
  oder sie verlassen (in dieser Version nicht verbindbar).
- **Cloud ▸ Live-Cursor anzeigen** – die Live-Cursor anderer Mitwirkender auf Ihrer Arbeitsfläche ein- oder
  ausblenden (es gibt keine anzuzeigenden, bis eine Echtzeit-Sitzung eine Verbindung herstellen kann).
- **Cloud ▸ Branching** – das Bedienfeld zum Verzweigen, Wechseln und Zusammenführen öffnen.

Jeder dieser Einträge blendet das jeweilige Bedienfeld ein oder aus, sodass Sie die Bedienfelder neben den
Bedienfeldern für Ebenen und Zeitleiste sowie anderen Arbeitsablauf-Bedienfeldern anordnen können.

> **Ein anbieterunabhängiger Port – kein Lock-in.** Genau wie das Speichern in der Cloud für eine einzelne
> Person spricht auch die Zusammenarbeit nie direkt mit einem bestimmten Anbieter. Teilen, Mitgliedschaft,
> Kommentare und Anwesenheit laufen alle über **dieselbe anbieterunabhängige Schnittstelle** (die Familie
> der *Cloud-Ports*), sodass sich die Anwendung identisch verhält, egal welcher Anbieter dahintersteht. In
> dieser Version wird diese Schnittstelle vom oben beschriebenen integrierten Adapter im Arbeitsspeicher
> bedient.

## Ein Projekt teilen und die Mitgliederliste verwalten

Ein Projekt wird über das Bedienfeld **Geteilte Projekte** geteilt. Öffnen Sie es mit **Cloud ▸ Geteilte
Projekte**.

### Ein Projekt erstellen (teilen)

1. Geben Sie im Feld **Name des geteilten Projekts** den Namen ein, unter dem Ihr geteiltes Projekt abgelegt
   wird (zum Beispiel `team-sprite`). Verwenden Sie später denselben Namen erneut, um am selben geteilten
   Projekt weiterzuarbeiten.
2. Stellen Sie mit der Zeile zum Hinzufügen von Mitgliedern die **Mitgliederliste zum Teilen** zusammen:
    - Geben Sie im Feld *Mitglieds-ID zum Einladen* eine **Mitglieds-ID** ein (die Kennung der
      mitwirkenden Person).
    - Wählen Sie im Rollenwähler eine **Rolle** – **Besitzer**, **Bearbeiter** oder **Betrachter**.
    - Klicken Sie auf **Mitglied hinzufügen**. Das Mitglied erscheint mit seiner Rolle in der
      bearbeitbaren Liste *Mitgliederliste zum Teilen*.
3. Wiederholen Sie Schritt 2 für jede mitwirkende Person. Um jemanden vor dem Teilen wieder zu entfernen,
   wählen Sie die Zeile aus und klicken auf **Entfernen**.
4. Wenn die Mitgliederliste fertig ist, klicken Sie auf **Teilen / Aktualisieren**. Das Projekt wird genau
   mit dieser Mitgliederliste geteilt, und die übernommenen Mitglieder erscheinen unten in der
   schreibgeschützten Liste *Aktuelle Mitglieder*.

> **Rollen.** Eine Rolle ist eine anbieterunabhängige Berechtigungsmarkierung, die jedem Mitglied zugeordnet
> ist: **Besitzer** – volle Kontrolle über das geteilte Projekt; **Bearbeiter** – kann die Grafik bearbeiten
> und kommentieren; **Betrachter** – kann ansehen und kommentieren. Rollen werden mit der Mitgliedschaft
> gespeichert und sowohl in der bearbeitbaren Mitgliederliste als auch in der Liste der aktuellen Mitglieder
> angezeigt.

> **Die Obergrenze für Mitglieder.** Ein geteiltes Projekt darf höchstens **32** Mitglieder haben. Das
> Bedienfeld weigert sich, ein Mitglied über diese Obergrenze hinaus hinzuzufügen, und zeigt eine klare
> Meldung; die Speicherschicht erzwingt dieselbe Grenze als zweite Verteidigungslinie. Doppelte
> Mitglieds-IDs werden ebenfalls abgelehnt.

### Die Mitgliederliste aktualisieren

Um zu ändern, wer an einem geteilten Projekt beteiligt ist, passen Sie die bearbeitbare Mitgliederliste an
(Mitglieder hinzufügen oder entfernen) und klicken erneut auf **Teilen / Aktualisieren**. Das erneute Teilen
**ersetzt** die Mitgliederliste durch den aktuellen Entwurf – es gibt keinen eigenen Schritt „ein Mitglied
hinzufügen“, achten Sie also darauf, dass der Entwurf alle aufführt, die Zugriff haben sollen, bevor Sie ihn
übernehmen.

### Ein geteiltes Projekt öffnen

Geben Sie den Namen eines vorhandenen geteilten Projekts ein und teilen Sie es (oder teilen Sie es erneut
mit derselben Mitgliederliste), um es zum **aktiven geteilten Projekt** zu machen. Die Bedienfelder
Kommentare und Anwesenheit beziehen sich immer auf das aktive geteilte Projekt; wenn Sie hier eines öffnen,
werden daher alle drei Bedienfelder auf einmal mit demselben Projekt verbunden.

## Kommentare hinzufügen und ansehen

Kommentare gehören zum aktiven geteilten Projekt. Öffnen Sie den Kommentarverlauf mit **Cloud ▸ Kommentare**.

### Den Kommentarverlauf lesen

Die Kommentaransicht ist ein **Kommentarverlauf** in Baumform mit drei Spalten:

- **Autor** – die Mitglieds-ID, die den Kommentar geschrieben hat.
- **Kommentar** – der Text des Kommentars.
- **Status** – **Offen** oder **Erledigt**.

Antworten sind unter dem Kommentar eingerückt, auf den sie antworten, sodass sich eine Diskussion als
eingerückter Verlauf liest.

### Einen Kommentar hinzufügen

1. Geben Sie **Ihre Mitglieds-ID** im Feld *Ihre Mitglieds-ID* ein (sie wird als Autor des Kommentars
   festgehalten).
2. Geben Sie Ihren Kommentar in das Textfeld unten ein. Die **Bytezahl** zeigt live, wie viel des Budgets
   pro Kommentar Sie verbraucht haben (zum Beispiel `18 / 4096 bytes`).
3. *(Optional)* Um auf einen vorhandenen Kommentar zu antworten, wählen Sie ihn im Kommentarverlauf aus und aktivieren
   **Auf Auswahl antworten** – Ihr neuer Kommentar wird darunter eingeordnet.
4. Klicken Sie auf **Kommentar hinzufügen**. Der Kommentar erscheint im Kommentarverlauf (unter seinem übergeordneten
   Kommentar eingeordnet, wenn er eine Antwort war) mit dem Status **Offen**.

### Einen Kommentar erledigen

Wählen Sie einen Kommentar im Kommentarverlauf aus und klicken Sie auf **Erledigen**. Sein Status wechselt zu
**Erledigt**. Das Erledigen ist eine nicht zurücknehmbare Markierung dafür, dass ein Kommentar abgehandelt wurde; der
Kommentar bleibt zur Dokumentation im Kommentarverlauf.

> **Grenzen für Kommentare.** Es gelten zwei Grenzen, beide direkt bei der Eingabe im Bedienfeld mit Rückmeldung
> durchgesetzt und von der Speicherschicht erneut geprüft: **Größe des Kommentars** – ein einzelner Kommentar
> darf höchstens **4096 Bytes** umfassen (gemessen an der **Byte-Länge in UTF-8**, sodass Text mit Akzenten
> oder nicht lateinischen Schriftzeichen seinen tatsächlichen Platzbedarf in Bytes zählt); und **Anzahl der
> Kommentare** – ein geteiltes Projekt darf höchstens **1024** Kommentare enthalten.

> **Kommentare werden validiert, nie ausgeführt.** Kommentartext wird als **nicht vertrauenswürdige
> Eingabe** behandelt: Er wird vor dem Speichern auf Schema und Größe geprüft und **nie** als Code
> ausgewertet oder ausgeführt. Eine fehlerhafte oder übergroße Nutzlast wird mit einem klaren Fehler
> abgelehnt und führt nie zu einem Absturz.

## Sehen, wer anwesend ist

Das Bedienfeld **Anwesenheit** zeigt eine Live-Liste dessen, *wer gerade anwesend ist*, im aktiven geteilten
Projekt. Öffnen Sie es mit **Cloud ▸ Anwesenheit**.

1. Geben Sie **Ihre Mitglieds-ID** im Anwesenheitsfeld ein.
2. Klicken Sie auf **Beitreten**, um sich als anwesend anzuzeigen. Ihre ID erscheint in der Liste der
   anwesenden Mitglieder.
3. Klicken Sie auf **Verlassen**, um Ihre Anwesenheit zurückzusetzen, wenn Sie sich entfernen.

> **Anwesenheit ist flüchtig.** Die Anwesenheit wird **nie in der Projektdatei** oder in ihrem Zustand zur
> Zusammenarbeit gespeichert – sie ist ein Live-Signal im Arbeitsspeicher dafür, wer gerade da ist. Das
> Schließen eines geteilten Projekts oder das Verlassen setzt Ihre Anwesenheit zurück.

> **Anwesenheitsliste gegenüber Live-Cursorn.** Das Bedienfeld Anwesenheit zeigt die **Anwesenheitsliste** –
> die Liste derer, die anwesend sind. Das Zeichnen der **Live-Cursor und Auswahlen** anderer Mitwirkender
> auf Ihrer Arbeitsfläche ist eine eigene Funktion – siehe *Gemeinsames Bearbeiten in Echtzeit* unten.

## Wie gleichzeitige Änderungen konvergieren

Wenn mehrere Mitglieder ein geteiltes Projekt bearbeiten, werden ihre Änderungen durch ein
**deterministisches hybrides Konvergenzmodell** abgeglichen, sodass am Ende alle **dasselbe** Projekt haben,
unabhängig von der Reihenfolge, in der die Änderungen eintreffen:

- **Strukturierte Metadaten** – der Ebenenbaum, die Ebenenattribute (Name, Deckkraft, Sichtbarkeit, Sperre)
  und die Ebenenreihenfolge pro Frame – konvergieren über ein **Sequenz-/Baum-CRDT**.
- **Pixel des Rasterbilds** konvergieren über **Last-Writer-Wins pro Tile**: Die Arbeitsfläche wird in Tiles
  von 64 Pixeln unterteilt, und gleichzeitige Änderungen an *verschiedenen* Tiles bleiben beide erhalten,
  während gleichzeitige Änderungen am *selben* Tile durch einen deterministischen Entscheid nach logischer
  Uhr und Site-ID aufgelöst werden.

Das Ergebnis ist **deterministisch**: Bei derselben Menge von Änderungen konvergiert jede teilnehmende Person
zu einem byteidentischen Projekt – die Zusammenführung liest weder eine Systemuhr noch Zufallswerte noch das
Gebietsschema. Dies ist das **Stapel**-Abgleichmodell; das **Live**-Anwenden von Änderungen, während sie
geschehen, ist der als Nächstes beschriebene Echtzeit-Pfad.

## Gemeinsames Bearbeiten in Echtzeit

Beim gemeinsamen Bearbeiten in Echtzeit werden die Änderungen jeder teilnehmenden Person auf die
Arbeitsfläche **jeder** anderen teilnehmenden Person angewendet, während sie geschehen, und konvergieren mit demselben
deterministischen Modell wie die Stapel-Zusammenführung oben. Die Änderungen laufen über ein eigenes
**Echtzeit-Sync-Backend** (siehe den Betriebshinweis am Ende).

> **In dieser Version nicht verbindbar.** Die Desktop-Anwendung hat keine Echtzeit-Verbindung konfiguriert,
> sodass **Cloud ▸ Echtzeit starten…** (nachdem Sie eine Mitglieds-ID eingegeben haben) keiner Sitzung
> beitritt: Die Statusleiste zeigt eine Meldung, die auf „kein Echtzeit-Transport konfiguriert“ endet, und es
> ergeben sich weder weitere Teilnehmende noch Live-Cursor noch ein Nachholen für später Beitretende. Die Schritte unten
> beschreiben, wie eine Sitzung funktioniert, sobald eine Verbindung besteht.

### Eine Sitzung starten oder ihr beitreten

1. Öffnen Sie das Dokument, das Sie gemeinsam bearbeiten möchten (ein geteiltes Projekt oder einen beliebigen
   geöffneten Tab).
2. Wählen Sie **Cloud ▸ Echtzeit starten…**.
3. Geben Sie auf Nachfrage **Ihre Mitglieds-ID** ein – so sehen die anderen Teilnehmenden Sie (und das beschriftet Ihren
   Live-Cursor). Die Anwendung tritt der Echtzeit-Weiterleitung des Dokuments bei.
4. Wenn Sie verbunden sind, wird die Einblendung **Live-Cursor anzeigen** automatisch eingeschaltet.

Alle, die Echtzeit für **dasselbe Dokument** starten, treten derselben Sitzung bei. Ist ein geteiltes
Projekt geöffnet, ist die Sitzung diesem geteilten Projekt zugeordnet, sodass das ganze Team auf einem
Dokument konvergiert; andernfalls ist sie Ihrem lokalen Dokument zugeordnet.

Um die Sitzung zu verlassen, wählen Sie **Cloud ▸ Echtzeit beenden**. Sie können sich jederzeit erneut
verbinden; das Verlassen löscht die Live-Cursor.

> **Später Beitretende holen automatisch auf.** Das Sync-Backend **speichert** den Strom der Änderungen jedes
> Dokuments dauerhaft, sodass eine mitwirkende Person, die beitritt, nachdem das Bearbeiten begonnen hat,
> **den Rückstand nachspielt** und beim selben konvergierten Dokument wie alle anderen ankommt.

> **Echtzeit bleibt reaktionsschnell.** Eingehende Änderungen werden in einem Hintergrund-Worker empfangen
> und im UI-Thread auf das Live-Dokument angewendet, wobei **nur die geänderten Tiles** neu gezeichnet werden
> (ein Neuzeichnen nur der geänderten Rechtecke). Eine einzelne eingehende Änderung kostet die Größe dieser
> Änderung, nicht die ganze Arbeitsfläche, sodass das gemeinsame Bearbeiten auch bei der Arbeitsflächengröße
> 8K flüssig bleibt.

> **Eingehende Daten gelten konstruktionsbedingt als nicht vertrauenswürdig.** Jede eingehende Änderung und jede Cursor-Nutzlast wird vor
> der Anwendung auf **Schema und Größe validiert** und **nie** als Code ausgeführt. Eine fehlerhafte oder
> übergroße Nachricht wird mit einem Hinweis in der Statusleiste abgelehnt und führt nie zu einem
> Absturz.

### Live-Cursor und Auswahl

Solange Echtzeit verbunden ist, schaltet **Cloud ▸ Live-Cursor anzeigen** eine Einblendung ein oder aus, die
die Cursor und Auswahlen anderer Mitwirkender auf Ihrer Arbeitsfläche zeichnet, jeweils mit der Mitglieds-ID
der jeweiligen Person beschriftet.

- Cursor sind **flüchtig** – sie sind nur ein Live-Signal und werden **nie** in die `.pixproj`-Datei oder in den
  gespeicherten Zustand des Projekts geschrieben.
- Schalten Sie die Einblendung jederzeit aus, um aufzuräumen; Ihr eigenes Bearbeiten bleibt unberührt.

## Branching der Grafik

Mit Branching verzweigen Sie das aktuelle Projekt in eine unabhängige Linie von Änderungen, arbeiten daran,
ohne den Hauptzweig zu stören, und fügen sie per **Zusammenführung** wieder ein, **ohne manuelle
Konfliktlösung** – dasselbe CRDT-/Last-Writer-Wins-Modell, das die Konvergenz antreibt, führt die beiden
Linien automatisch zusammen. Öffnen Sie das Bedienfeld mit **Cloud ▸ Branching**.

### Einen Branch erstellen

1. Klicken Sie bei geöffnetem Projekt im Bedienfeld Branching auf **Neuer Branch**.
2. Tragen Sie im Feld **Branch-Name** eine Bezeichnung ein (zum Beispiel `experiment`). Der Branch wird vom aktuellen Dokument
   abgezweigt und erscheint in der Branch-Liste; der **Hauptzweig** ist immer vorhanden.

### Branches wechseln

Wählen Sie einen Branch in der Liste aus und klicken Sie auf **Wechseln**. Das Dokument des ausgewählten
Branches wird in den aktiven Tab geladen, sodass Sie die unabhängige Kopie dieses Branches bearbeiten. Der
Wechsel zum **Hauptzweig** bringt Sie zurück zum Stamm.

### Vor dem Zusammenführen prüfen

Wählen Sie einen Feature-Branch aus und klicken Sie auf **Vergleich öffnen** – ein eigenes Bedienelement,
getrennt von **Zusammenführen** und unter denselben Bedingungen aktiviert. Es öffnet einen **nicht modalen,
schreibgeschützten** Vergleichsdialog, der die Abweichung zwischen dem Branch und dem Hauptzweig einmal
berechnet, wenn er sich öffnet, und die Liste **Betroffene Bereiche** zeigt – jeden geänderten Bereich,
gemeldet in einer festen Granularität von Pixel-Tiles, sodass selbst eine Änderung von einem Pixel als
ganzes Tile erscheint – sowie eine Prüfwarnung, wenn eine zutrifft. Der Dialog führt selbst keine
Zusammenführung durch; über ihn wählen Sie **Weiter zur Zusammenführung** (was dieselbe unten beschriebene
Zusammenführung ausführt) oder **Schließen**, um ohne Zusammenführung zurückzugehen.

### Einen Branch zusammenführen

Wählen Sie einen Feature-Branch aus und klicken Sie auf **Zusammenführen**. Seine Änderungen werden
konfliktfrei in den **Hauptzweig** zusammengeführt, das zusammengeführte Dokument wird in den aktiven Tab
geladen, und das Bedienfeld zeigt eine Zeile **Ergebnis der Zusammenführung** an, die zusammenfasst, was
geschehen ist (zum Beispiel *Branch „experiment“ (12 Bearbeitungen) konfliktfrei in den Hauptzweig
zusammengeführt.*).

> **Zusammenführungen verlangen nie, dass Sie einen Konflikt lösen.** Weil das zugrunde liegende Modell
> kommutativ und deterministisch ist, gelingt eine Zusammenführung immer und liefert immer dasselbe
> Ergebnis, unabhängig von der Reihenfolge, in der die Änderungen gemacht wurden – es gibt keinen manuellen
> Schritt zur Konfliktlösung. Branching gehört zum Sitzungszustand und ist **kein** Rückgängig-Schritt im
> Rückgängig-Stapel. **Vergleich öffnen** ist optional – Sie können direkt zusammenführen, ohne den
> Vergleich vorher anzusehen.

<!-- split-with: docs/site/pages/en/usage/hosting.md (that page extracts and expands this section's deployment detail; this section stays the bundle's single mention) -->

## Betriebshinweis: das Sync-Backend betreiben

Das gemeinsame Bearbeiten in Echtzeit braucht ein **Sync-Backend** – einen kleinen, eigenständigen Dienst, der
Änderungen zwischen den Mitwirkenden weiterleitet und dauerhaft speichert. Es ist **nicht** Teil des
Drei-Schichten-Kerns der Desktop-Anwendung; es liegt in einem eigenen Paket `sync_backend/` auf oberster Ebene
und spricht mit Clients nur über den Echtzeit-Transport.

- Das Backend importiert **keinen** UI-, Daten- oder Qt-Code, und es empfängt oder speichert **nie** die
  Token Ihres Cloud-Anbieters – diese bleiben im Schlüsselbund des Desktop-Clients.
- Für die lokale Entwicklung und die automatisierte Testsuite wird das Backend **im selben Prozess auf einem
  dynamisch zugewiesenen Loopback-Port** gestartet, sodass der gesamte Ablauf zwischen Client und Backend über
  `127.0.0.1` läuft, ohne externes Netzwerk und ohne Konten.
- Das Backend als eigenständigen, über das Netzwerk erreichbaren Dienst für ein verteiltes Team zu betreiben
  ist eine **Deployment-Aufgabe** (Host, Port und Prozessverwaltung), getrennt von der Desktop-Anwendung.
- Die Desktop-Anwendung hat in dieser Version keine Verbindung zu einem Sync-Backend konfiguriert, sodass
  sich die Anwendung noch nicht mit einem laufenden Backend verbinden kann.

Die [Cloud-Anleitung](cloud-and-collaboration.md) erklärt, dass die echten Cloud-Anbieter in dieser Version
nicht im Menü Cloud ausgewählt werden können.
