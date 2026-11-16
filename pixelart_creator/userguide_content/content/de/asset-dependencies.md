# Asset-Abhängigkeiten und Erkennung defekter Referenzen

Das **Abhängigkeitsdiagramm** hält fest, wie Ihre Assets einander referenzieren – ein Sprite ist ein Frame
*in* einer Animation, ein Sprite ist das Quellbild *für* ein Tileset, ein Tileset wird *von* einer Tilemap
verwendet –, und die **Anzeige defekter Referenzen** warnt Sie passiv, wenn die Änderung eines Assets ein
anderes, das darauf verweist, defekt machen würde. Beides erreichen Sie über das Menü **Bibliothek**,
neben den Bedienfeldern der [Asset-Bibliothek](asset-library.md), auf denen es aufbaut.

> **Was eine Abhängigkeit ist.** Eine Abhängigkeit ist eine **gerichtete Referenz** von einem
> Katalog-Asset auf ein anderes: Das *referenzierende* Asset (die Quelle) verweist auf das *referenzierte*
> Asset (das Ziel). Die Referenz merkt sich außerdem den Inhalt des Ziels zum Zeitpunkt ihrer Erstellung,
> sodass die Bibliothek später feststellen kann, ob sich das Ziel geändert hat. Abhängigkeiten bilden einen
> **gerichteten azyklischen Graphen** – die Bibliothek weigert sich, eine Referenz festzuhalten, die einen
> Zyklus erzeugen würde (ein Asset kann nicht, weder direkt noch transitiv, von sich selbst abhängen).

## Das Abhängigkeitsdiagramm öffnen

Das Menü **Bibliothek** enthält zusätzlich den Eintrag **Abhängigkeitsdiagramm**, der das Bedienfeld ein-
oder ausblendet. Die Ansicht **Abhängigkeitsdiagramm** visualisiert die Referenzen für den gesamten
Katalog oder für das einzelne Asset, das aktuell im Bedienfeld [Asset-Bibliothek](asset-library.md)
ausgewählt ist, in zwei Richtungen:

| Beziehung | Lesart | Zeigt |
| --- | --- | --- |
| **Abhängigkeiten (hängt ab von)** | was dieses Asset *referenziert* | die Assets, auf die das ausgewählte Asset verweist |
| **Abhängige Assets (referenziert von)** | was auf dieses Asset *verweist* | die Assets, die auf das ausgewählte Asset verweisen |

Beide Beziehungen werden als stabile, alphabetisch sortierte Listen angezeigt. Standardmäßig zeigt die
Ansicht die **direkten** Nachbarn; dieselben Beziehungen lassen sich auch transitiv lesen (die gesamte
Kette – zum Beispiel alle Assets, auf die eine Tilemap letztlich über ihre Tilesets und deren Quell-Sprites
zurückgreift).

> **Warum der Graph nie hängen bleibt.** Weil der gespeicherte Graph stets zyklenfrei ist, listet die
> Ansicht nur die direkten Nachbarn auf, die das Modell liefert – sie führt keine eigene rekursive
> Traversierung durch. Selbst eine absichtlich verworrene Menge von Referenzen kann die Ansicht nicht in
> eine Endlosschleife schicken: Ein Zyklus wird beim Festhalten der Referenz erkannt und eindeutig
> gemeldet, und eine sehr tiefe Kette wird begrenzt, statt endlos verfolgt zu werden.

## Die passive Anzeige defekter Referenzen

Wenn Sie ein Asset ändern, kann alles, was darauf verweist, nun auf Inhalt zeigen, der nicht mehr passt.
Die Bibliothek macht das **passiv** sichtbar – sie markiert das Problem, sie **blockiert** Ihre Änderung
nicht:

- **Defekte Referenzen werden markiert, nie blockiert.** Sie können die Änderung immer vornehmen; die
  Anzeige sagt Ihnen lediglich, dass eine Referenz nun defekt ist, damit Sie entscheiden können, was zu tun
  ist. Nichts wird verhindert, und kein modaler Dialog unterbricht Sie.
- **Sie aktualisiert sich bei Katalogänderungen.** Die Anzeige bewertet neu, sobald sich der Katalog oder
  der Graph ändert, und gibt daher stets den aktuellen Stand wieder – Sie müssen sie nie auffordern,
  erneut zu prüfen.
- **Sie erscheint an Ort und Stelle.** Die Ansicht Abhängigkeitsdiagramm zeigt eine Zusammenfassung der
  defekten Referenzen und den Status je Referenz, und die Liste der [Asset-Bibliothek](asset-library.md)
  hat eine Spalte **Status**, sodass ein defektes Asset genau dort sichtbar ist, wo Sie die Bibliothek durchsuchen.

Eine Referenz wird aus einem von zwei Gründen als defekt gemeldet:

| Grund | Bedeutung |
| --- | --- |
| **fehlendes Ziel** | das referenzierte Asset ist nicht mehr im Katalog (es wurde entfernt). Das Abhängigkeitsdiagramm zeigt es als „Defekt (fehlendes Ziel)“ an. |
| **geändertes Ziel** | das referenzierte Asset ist noch vorhanden, aber sein Inhalt hat sich seit dem Erstellen der Referenz geändert. Das Abhängigkeitsdiagramm zeigt es als „Defekt (geändertes Ziel)“ an. |

Ein Asset, dessen Referenzen alle noch gültig sind, zeigt keine Markierung; nur eine tatsächlich defekte
Referenz wird markiert, sodass die Warnung aussagekräftig bleibt (keine Fehlalarme).

## Barrierefreiheit, Designs und Sprache

Die Steuerelemente der Ansicht Abhängigkeitsdiagramm haben jeweils einen zugänglichen Namen und sind über
die Tastatur erreichbar, jede Beschriftung ist vollständig übersetzbar, und die Ansicht sowie die Spalte
Status werden im hellen und im dunklen Design korrekt dargestellt.

## Verwandtes

Die Abhängigkeitsverfolgung und die Erkennung defekter Referenzen bauen auf dem Katalog der
[Asset-Bibliothek](asset-library.md) auf. Die ergänzende Fähigkeit – ein
**Versionsverlauf** pro Asset, an den nur angehängt wird, sowie **projektübergreifende Wiederverwendung**, **Export/Import** und
**optionale Cloud-Anbindung** (in dieser Version nicht angeschlossen) – ist in
[Asset-Versionierung und projektübergreifende Wiederverwendung](asset-versioning.md) dokumentiert. Ein
wiederverwendetes Asset ist eine Referenz wie jede andere, sodass die hier beschriebene Anzeige eine
Wiederverwendung markiert, deren Ziel später fehlt oder sich ändert.
