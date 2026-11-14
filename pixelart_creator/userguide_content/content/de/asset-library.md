# Die Asset-Bibliothek – durchsuchen, taggen und finden

Die **Asset-Bibliothek** ist ein studioweiter Katalog Ihrer wiederverwendbaren Assets – Sprites,
Animationen, Tilesets, Tilemaps und Paletten – an einem Ort. Registrieren Sie die Elemente, die Sie bereits
erstellt haben, als **benannte Assets**, ordnen Sie sie mit frei wählbaren **Tags** und finden Sie das
passende per **Suche und Filter** schnell. Die Bibliothek und ihre drei Bedienfelder erreichen Sie über das
Menü **Bibliothek**.

> **Was ein Asset ist.** Ein Asset ist ein **Katalogeintrag**, der eines der bereits von Ihnen erstellten
> Elemente *referenziert* – er legt keine zweite Kopie Ihrer Grafik an. Jeder Eintrag trägt eine **stabile
> ID**, einen **Typ** (Sprite, Animation, Tileset, Tilemap oder Palette), einen Anzeigenamen (**Name**),
> seine **Tags** und ein paar Metadaten. Der Eintrag verweist auf die maßgebliche gespeicherte Form des
> Elements (dieselben `.pixproj`-Nutzdaten, die der Rest der Anwendung verwendet) – die Bibliothek führt
> für die Grafik selbst kein neues Speicherformat ein.

## Die Bibliothek öffnen

Das Menü **Bibliothek** enthält für jedes dieser drei Bedienfelder einen Eintrag zum Umschalten, der jeweils
ein Bedienfeld ein- oder ausblendet:

| Menüeintrag | Bedienfeld | Wofür es gedacht ist |
| --- | --- | --- |
| **Asset-Bibliothek** | die Katalogliste | Alle Assets nach Name, Typ und Tags durchsuchen. |
| **Asset-Suche** | die Such- und Filtersteuerelemente | Die Liste nach Name, Tag und/oder Typ eingrenzen. |
| **Asset-Tagging** | der Tag-Editor | Tags am ausgewählten Asset hinzufügen und entfernen. |

Jeder Eintrag schaltet ein Bedienfeld ein oder aus (wie bei den anderen Arbeitsablauf-Bedienfeldern der
Anwendung), sodass Sie die drei Bedienfelder beliebig anordnen können. Die Bedienfelder teilen sich
**einen** Katalog im Arbeitsspeicher, sodass eine Änderung in einem Bedienfeld sofort in den anderen
sichtbar ist.

## Ein Asset registrieren

Bevor etwas im Katalog erscheint, muss es **registriert** werden. Drei Stellen der Anwendung starten eine
Registrierung, und alle drei enden im selben gemeinsamen Dialog **Asset registrieren**:

- **Aktives Dokument registrieren** im Menü **Bibliothek** registriert das Dokument, das im aktiven Tab
  geöffnet ist. Wenn Sie dasselbe Dokument später erneut registrieren, wird an den bestehenden
  Katalogeintrag eine neue Revision angehängt, statt ein Duplikat anzulegen – siehe
  [Asset-Versionierung und projektübergreifende Wiederverwendung](asset-versioning.md).
- **Auswahl registrieren**, ebenfalls im Menü **Bibliothek**, registriert nur die Pixel innerhalb Ihrer
  aktuellen Auswahl. Bei einer nicht rechteckigen Auswahl ist alles außerhalb der ausgewählten Pixel im
  registrierten Asset transparent. Ist nichts ausgewählt, gibt es nichts zu registrieren.
- **Auch zur Asset-Bibliothek hinzufügen**, ein Kontrollkästchen im Export-Dialog (siehe
  [Export und Pipeline-Integration](export-and-pipeline.md)), registriert die exportierte Datei im selben
  Schritt wie den Export.

Alle drei öffnen denselben Dialog **Asset registrieren**, der Folgendes abfragt:

| Feld | Was abgefragt wird |
| --- | --- |
| **Name** | Ein Anzeigename für den neuen Katalogeintrag. |
| **Typ** | Einer der fünf Asset-Typen – Sprite, Animation, Tileset, Tilemap, Palette. |
| **Tags** | Eine optionale, durch Kommas getrennte Menge von Tags, die gegen dieselben Grenzen für Länge und Anzahl geprüft wird wie im Tagging-Bedienfeld weiter unten. |

Der Dialog prüft schon während der Eingabe: Ein leerer Name oder eine Tag-Menge über den Grenzen für Länge
und Anzahl deaktiviert die Schaltfläche **Registrieren**, und der Grund wird deutlich angezeigt, bis Sie das Problem
beheben. Wenn Sie den Dialog abbrechen, wird nichts registriert.

## Ein einzelnes Asset importieren und exportieren

Zwei weitere Befehle im Menü **Bibliothek** übertragen eine einzelne Asset-Datei, im Unterschied zu einem
ganzen Projekt:

- **Asset exportieren** exportiert den aktuell ausgewählten Katalogeintrag – oder, wenn nichts ausgewählt
  ist, jeden Eintrag im geöffneten Katalog – als eine importierbare Asset-Datei.
- **Asset importieren** liest eine solche Asset-Datei zurück in die geöffnete Bibliothek und führt sie mit
  dem Katalog zusammen.

Davon getrennt sind **Projektpaket exportieren** / **Projektpaket importieren**, die ein ganzes Projekt samt
allem, was es referenziert, übertragen – siehe
[Asset-Versionierung und projektübergreifende Wiederverwendung](asset-versioning.md).

## Den Katalog durchsuchen

Das Bedienfeld **Asset-Bibliothek** listet den Katalog in vier Spalten auf – **Name**, **Typ**, **Tags** und
**Status**. Es zeigt stets genau das, was der Katalog enthält: Wenn Sie ein Asset hinzufügen, entfernen oder
taggen, wird die Liste sofort aktualisiert. Wenn Sie eine Zeile auswählen, ist dieses Asset gewählt – und
genau dieses bearbeitet dann das Bedienfeld **Asset-Tagging**.

- Die Liste wird vollständig vom gemeinsamen Katalog gesteuert; das Bedienfeld selbst filtert oder
  sortiert nichts.
- Wenn im Bedienfeld **Asset-Suche** eine Suchanfrage aktiv ist, zeigt die Bibliotheksliste nur die
  passenden Einträge (siehe unten); wird die Anfrage gelöscht, erscheint wieder die vollständige Liste.

## Assets taggen

Das Bedienfeld **Asset-Tagging** bearbeitet die Tags des in der Bibliothek ausgewählten Assets. Geben Sie
ein Tag ein und fügen Sie es hinzu; wählen Sie ein Tag aus und entfernen Sie es. Tags sind frei wählbare
Bezeichnungen, zum Beispiel `hero`, `enemy` oder `tileset-a`, mit denen Sie Assets nach Bedeutung ordnen.

- **Tag-Änderungen lassen sich rückgängig machen.** Das Hinzufügen oder Entfernen eines Tags ist ein
  einzelner Schritt auf dem gemeinsamen Rückgängig-Stapel: Mit **Rückgängig** wird exakt die vorherige
  Tag-Menge wiederhergestellt, mit **Wiederholen** wird die Änderung erneut angewendet – dieselben
  Befehle, die Sie überall sonst verwenden (siehe [Erste Schritte und der Arbeitsbereich](app-basics.md)).
- **Ein bereits vorhandenes Tag hinzuzufügen bewirkt nichts**, und das Entfernen eines Tags, das nicht
  vorhanden ist, ist ebenso harmlos.
- **Tags sind begrenzt.** Ein einzelnes Tag hat eine maximale Länge, und jedes Asset hat eine maximale
  Anzahl von Tags. Ein Tag, das zu lang ist oder das Asset über sein Tag-Limit bringen würde, wird **mit
  einer klaren Meldung abgelehnt** und nicht hinzugefügt – nichts wird stillschweigend abgeschnitten.

## Suchen und filtern

Das Bedienfeld **Asset-Suche** grenzt die Bibliotheksliste mit drei Steuerelementen ein, die zusammenwirken:

| Steuerelement | Trifft zu auf |
| --- | --- |
| **Name** | Assets, deren Name den eingegebenen Text *enthält* (Teilzeichenfolge). |
| **Tags** | Assets mit dem oder den eingegebenen Tags (bei mehreren durch Kommas getrennt). |
| **Typ** | Assets des gewählten Typs; der Eintrag **Alle Typen** hebt den Typfilter auf. |

- Die drei Filter **verknüpfen sich mit UND** – ein Treffer muss zum Namen *und* zu den Tags *und* zum Typ
  passen, die Sie festlegen. Lassen Sie ein Steuerelement leer, wird diese Dimension ignoriert.
- **Ergebnisse sind stabil und deterministisch:** Derselbe Katalog und dieselbe Anfrage ergeben immer
  dieselbe Liste in derselben Reihenfolge.
- **Wenn Sie alle Steuerelemente leeren, erscheint wieder der vollständige Katalog**, in seiner normalen
  Reihenfolge.

> **Nach Bedeutung finden, nicht nach Datei.** Weil Assets getaggt und durchsuchbar sind, rufen Sie
> „jedes `enemy`-Sprite“ oder „die mit `dungeon` getaggten Tilesets“ auf, ohne Ordner durchsuchen zu
> müssen. Verwenden Sie für Ihre Assets ein kleines, einheitliches Tag-Vokabular, dann erledigen die Filter den Rest.

## Wie Assets gespeichert werden

Hinter den Bedienfeldern führt die Bibliothek einen **Katalog** der Asset-Einträge und einen
**inhaltsadressierbaren Speicher** für deren Bytes:

- **Einmal gespeichert, nach Inhalt.** Die Bytes jedes Assets werden anhand des *Inhalts* selbst abgelegt,
  sodass das zweimalige Registrieren desselben Inhalts ihn nicht verdoppelt – identische Bytes werden nur
  einmal gehalten (**Deduplizierung**).
- **Über eine stabile ID referenziert, nicht über einen Pfad.** Ein Asset wird durch eine stabile ID
  identifiziert, die ihm folgt, sodass das **Verschieben oder Umbenennen** der zugrunde liegenden Datei den
  Katalogeintrag **nicht** beschädigt.
- **Die Grafik behält ihr normales Speicherformat.** Der Katalog verwendet das vorhandene
  Projektformat `.pixproj` für die Nutzdaten und legt daneben nur Referenzen und Metadaten ab – es gibt
  kein zweites Format für Ihre Grafik, um das Sie sich kümmern müssten.
- **Das Laden ist abgesichert.** Ein Katalog oder seine Metadaten werden beim Laden als nicht
  vertrauenswürdige Eingabe behandelt: Sie werden auf Größe und Struktur geprüft, führen nie etwas aus, und
  jeder referenzierte Pfad wird darauf geprüft, dass er innerhalb der Bibliothek bleibt – ein
  fehlerhafter oder über die Grenzen hinausreichender Katalog wird mit einem klaren Fehler abgelehnt,
  statt abzustürzen oder etwas zu beschädigen.

## Der Rest der Asset-Bibliothek

Die Asset-Bibliothek wurde in Etappen geliefert; der gesamte Meilenstein ist jetzt enthalten. Über Katalog,
Tagging und Suche/Filter oben hinaus gibt es:

- **[Asset-Abhängigkeiten und Erkennung defekter Referenzen](asset-dependencies.md)** – ein abfragbarer
  Graph, wie Assets einander referenzieren (`sprite -> animation -> tileset -> tilemap`), und eine
  passive Warnung, wenn die Änderung eines Assets ein anderes Asset, das darauf verweist, defekt macht.
- **[Asset-Versionierung und projektübergreifende Wiederverwendung](asset-versioning.md)** – ein
  Revisionsverlauf pro Asset, an den nur angehängt wird (ansehen und wiederherstellen); die Wiederverwendung
  eines geteilten Assets über Projekte hinweg per Referenz statt per Kopie; Export und Import der
  referenzierten Assets eines Projekts als in sich geschlossenes Paket; und eine optionale
  Cloud-Anbindung der geteilten Blobs, also der gespeicherten Rohdaten von Assets (in dieser Version nicht angeschlossen).
