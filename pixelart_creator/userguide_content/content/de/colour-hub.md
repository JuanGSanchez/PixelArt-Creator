<!-- surface-only: bundle — Orientierungsinhalt in der Anwendung; bewusst ohne Website-Seite -->
# Die Farbzentrale per Rechtsklick

Die **Farbzentrale** ist ein Kontextmenü, das Sie **genau dort aufrufen, wo Sie arbeiten**: Führen
Sie auf der Arbeitsfläche einen **Rechtsklick** aus, und sie öffnet sich am Cursor. Sie bietet zwei
schnelle Wege, eine Farbe zu wählen – eine kuratierte Liste mit **Favoriten** und ein vollständiges
**Farbrad** mit **Farbharmonien** in Echtzeit – und wendet Ihre Wahl sofort an.

## Die Farbzentrale öffnen

Klicken Sie irgendwo auf der [Arbeitsfläche](canvas-and-view.md) mit der rechten Maustaste. Die
Farbzentrale erscheint am Cursor, sodass Sie nie zu einem weit entfernten Bedienfeld wandern müssen,
um die Farbe zu wechseln. Wählen Sie eine Farbe, und sie wird sofort zur **aktiven Farbe**; das aktive
Farbfeld wird entsprechend aktualisiert. Ein **erneuter Rechtsklick bei geöffneter Farbzentrale
schließt sie** ohne Auswahl, sodass Sie abbrechen und genau dort weitermalen können, wo Sie waren.

## Favoriten

**Favoriten** ist Ihre persönliche, dauerhaft gespeicherte Liste bevorzugter Farben.

- **Zu Favoriten hinzufügen** speichert die aktuelle Farbe in den Favoriten, sodass sie beim nächsten
  Mal nur einen Klick entfernt ist.
- Mit **Entfernen** nehmen Sie eine Farbe heraus, die Sie nicht mehr brauchen.
- **Nach oben** / **Nach unten** ordnen die Favoriten um, sodass die am häufigsten verwendeten Farben
  zuerst stehen.

Ihre Favoritenliste **bleibt zwischen Sitzungen erhalten**, sodass Ihre Arbeitspalette beim erneuten
Öffnen der Anwendung immer bereitsteht. Ein Klick auf einen Favoriten wendet ihn sofort an.

Es gibt außerdem eine Geste, die Favoriten erreicht, ohne die Farbzentrale überhaupt zu öffnen:

| Geste | Ergebnis |
| --- | --- |
| **Middle-click** | Wählt den ersten Eintrag der Favoriten und macht ihn auf der Stelle zur aktiven Farbe, unabhängig davon, ob die Farbzentrale geöffnet ist. |

## Das Farbrad

Das **Farbrad** ist ein RGB-Rad im Canva-Stil, mit dem Sie jede Farbe über Farbton und Sättigung
wählen, mit einem Regler für den Hellwert (die Helligkeit). Wenn Sie sich über das Rad bewegen, wird
die aktive Farbe live aktualisiert.

## Farbharmonien in Echtzeit

Während Sie auf dem Rad wählen, zeigt die Farbzentrale **Harmonie-Farbfelder** an, die nach der
gängigen Farbtheorie aus Ihrer aktuellen Farbe abgeleitet werden, sodass Sie eine stimmige Palette
aufbauen können, ohne zu raten:

| Harmonie | Beziehung zu Ihrer Farbe |
| --- | --- |
| **Komplementär** | Der gegenüberliegende Farbton (+180°) – maximaler Kontrast. |
| **Analog** | Die Nachbarn (±30°) – ruhige, stimmige Farbschemata. |
| **Triadisch** | Zwei Farbtöne im Abstand von 120° (±120°) – ausgewogen und lebendig. |
| **Tetradisch** | Drei Farbtöne in gleichmäßigen Abständen von 90° – vierfarbig, kontrastreich. |
| **Split-Komplementär** | Die beiden Farbtöne beiderseits des Komplements (±150°). |
| **Schattierungen** und **Tönungen** | **Schattierungen** sind dunklere Stufen Ihrer Farbe; **Tönungen** sind hellere Stufen. Das Bedienfeld **Schattierungsverläufe** (zu öffnen über das Menü **Palette**) legt ganze Verläufe aus Schattierungen, Tönungen und Abtönungen für Ihre aktive Farbe aus, jeweils mit einer Schaltfläche **Zur Palette hinzufügen**. |

Das Rad selbst und die Harmonie-Farbfelder – die kleinen Kreise rund um das Rad – verhalten sich
unterschiedlich, und es lohnt sich, beides auseinanderzuhalten:

- **Die Radfläche ist kein Farbfeld.** Wenn Sie darauf ziehen, setzen Sie die Farbe des Harmoniekreises,
  der gerade ausgewählt ist; einen eigenen Doppelklick hat sie nicht.
- **Ein einzelner Klick auf einen Harmoniekreis malt sofort mit der Farbe dieses Kreises** und lässt
  die eigene Farbe des Kreises unverändert – am Rad und am Kreis ändert sich nichts, nur Ihre
  Arbeitsfläche.
- **Doppelklicken Sie stattdessen auf einen Kreis, um seine Farbe zu übernehmen** – dadurch wird sie
  zu Ihrer aktiven Farbe, ohne dass etwas gemalt wird. Die Tastaturaktivierung bewirkt dasselbe:
  Fokussieren Sie einen Kreis mit Tab und drücken Sie **Space** oder **Enter**, um ihn zu übernehmen.

Ein einzelner Klick dient also dazu, im Vorbeigehen mit einer Harmoniefarbe zu malen, ohne Ihre
aktive Farbe zu verändern, und ein Doppelklick (oder Space / Enter auf einem fokussierten Kreis)
dazu, sie als aktive Farbe festzulegen. Die Harmonien werden live neu berechnet, während Sie sich
über das Rad bewegen.

## Anwenden und Speichern

- **Farbe wählen** – die gewählte Farbe wird sofort aktiv, und das aktive Farbfeld spiegelt sie
  wider, sodass Ihr nächster Strich sie verwendet.
- **Zu Favoriten hinzufügen** – eine Farbe, die Ihnen gefällt, für später aufbewahren.

## Paletten und indizierte Dokumente

Die Farbzentrale arbeitet mit der **Palette** Ihres Dokuments zusammen. Bei einem **indizierten**
Dokument ist die Palette der feste Satz von Farben, den die Grafik verwendet; Sie können Paletten
laden, indem Sie eine Datei vom Typ `.gpl`, `.hex` oder `.pal` auf das Fenster ziehen (siehe
[Import per Drag-and-drop](drag-drop-import.md)). Das Ersetzen der Palette ist ein einzelner
rückgängig zu machender Schritt.

## Verwandte Themen

- Malen Sie mit Ihrer gewählten Farbe auf [der Arbeitsfläche](canvas-and-view.md).
- Wechseln Sie über das Menü **Palette** zwischen RGBA und Indexfarben (**In Indexfarben konvertieren** / **In RGBA konvertieren**); was dabei mit den Ebenen geschieht, steht unter [Das Ebenenbedienfeld](layers.md).
