# Das Ebenenbedienfeld

Das **Ebenenbedienfeld** listet die Ebenen und Gruppen des aktiven Dokuments für den aktuellen Frame
auf und stellt jedes Steuerelement pro Ebene bereit. Es ist die wichtigste Oberfläche für
nicht destruktives Bearbeiten.

## Die Liste lesen

- Ebenen werden **von oben nach unten in Z-Reihenfolge** angezeigt: Die Zeile **ganz oben in der Liste
  ist die oberste im Stapel** (zuletzt gezeichnet / im Vordergrund).
- Genau eine Zeile ist die **aktive Ebene** – sie ist das Ziel der Malwerkzeuge.
- **Gruppen** erscheinen als auf- und zuklappbare Knoten, die ihre untergeordneten Elemente enthalten.

## Steuerelemente pro Ebene

Jede Ebenenzeile bietet:

| Steuerelement | Funktion |
| --- | --- |
| **Deckkraftregler** | Legt die Deckkraft der Ebene von **0–100 %** fest. Gilt für jeden Mischmodus, nicht nur für Normal. |
| **Sichtbarkeitsschalter** | Blendet die Ebene ein oder aus. Eine ausgeblendete Ebene trägt nichts zum zusammengesetzten Ergebnis bei. |
| **Sperrschalter** | Schützt die Ebene vor Änderungen an den **Pixeln**. Malen, Füllen und Löschen auf einer gesperrten Ebene bewirken nichts; Deckkraft, Sichtbarkeit, Mischmodus und Reihenfolge lassen sich weiterhin ändern. |
| **Mischmodus-Auswahlliste** | Wählt einen der zwölf [Mischmodi](blend-modes.md). |

> **Die Sperre schützt nur Pixel.** Sie können eine gesperrte Ebene weiterhin fokussieren, ihre
> Deckkraft ändern, sie aus- und einblenden und sie umordnen. Das Sperren verhindert lediglich das
> Malen in ihre Pixel.

## Ebenen verwalten

- **Ebene hinzufügen** – fügt oberhalb der aktiven Ebene eine neue leere Ebene ein.
- **Ebene entfernen** – löscht die aktive Ebene. Das Entfernen der **letzten** Ebene eines Frames wird
  verweigert.
- **Ebene duplizieren** – fügt oberhalb der Quelle eine pixelgenaue Kopie mit kopierten Attributen ein.
- **Zum Umordnen ziehen** – ziehen Sie eine Zeile an eine neue Position, um die Z-Reihenfolge zu
  ändern; die Arbeitsfläche wird in der neuen Reihenfolge neu zusammengesetzt. Das Ziehen in eine
  Gruppe hinein oder aus ihr heraus ordnet die Ebene einem anderen übergeordneten Element zu.

## Gruppen

- **Gruppe** fasst die ausgewählten Ebenen der obersten Hierarchiestufe in einem neuen Gruppenknoten
  zusammen.
- **Gruppierung aufheben** löst eine Gruppe auf und stellt ihre untergeordneten Elemente an der Position
  der Gruppe in das übergeordnete Element.

Eine Gruppe setzt **zuerst ihre untergeordneten Elemente zusammen** und mischt dieses zu einer Ebene
reduzierte Ergebnis dann mit **ihrer eigenen** Deckkraft und **ihrem eigenen** Mischmodus über den
Stapel. Eine Gruppe mit Standardattributen (Normal, 100 %) wird genauso zusammengesetzt wie ihre
nicht gruppierten untergeordneten Ebenen. Das Ausblenden einer Gruppe blendet ihren gesamten
Teilbaum aus. Die Verschachtelungstiefe von Gruppen ist begrenzt.

## Masken

Hängen Sie eine **Maske** an eine Ebene an, um ihr Alpha nicht destruktiv zu modulieren:

1. Wählen Sie **Maske hinzufügen** für die ausgewählte Ebene.
2. Schalten Sie **Maske bearbeiten** ein, um die Maske zum Malziel zu machen – das Malen bearbeitet
   nun den Maskenpuffer und nicht die Pixel der Ebene.
3. Wo die Maske 0 ist, ist die Ebene unsichtbar; wo sie den Höchstwert hat, ist die Ebene vollständig
   sichtbar; Zwischenwerte wirken proportional.

Eine Maske mit durchgehend maximalem Wert entspricht keiner Maske, und das Bearbeiten einer Maske
verändert nie die eigenen Pixel der Ebene. Das Anhängen und Entfernen einer Maske lässt sich
rückgängig machen.

## Referenzebenen

Schalten Sie **Referenz** ein, um eine Ebene als **Referenzebene** zu markieren, die Sie
nachzeichnen können: Sie bleibt im zusammengesetzten Ergebnis sichtbar, **lehnt aber das Malen ab**
(Malwerkzeuge bewirken auf ihr nichts), ähnlich einer dauerhaften Sperre mit festem Zweck. Die
Kennzeichnung ist umkehrbar.

## Smart-Ebenen

Verwenden Sie **Smart-Ebene**, um aus einer ausgewählten Quellebene eine **Smart-Ebene** zu
erstellen. Die Smart-Ebene ist eine nicht destruktive Instanz, die **die Pixel der Quelle spiegelt**
(schreibgeschützt) und dabei ihre eigene Deckkraft, Sichtbarkeit und ihren eigenen Mischmodus
mitbringt. Das Bearbeiten der Quelle aktualisiert jede Smart-Instanz beim nächsten Neuzusammensetzen;
die Smart-Ebene hat keine eigenständig bearbeitbaren Pixel.

## Alles ist ein Rückgängig-Schritt

Jede Ebenenoperation, die das Bedienfeld anbietet, wird als **genau ein** Rückgängig-Befehl
abgelegt: Deckkraft, Sichtbarkeit, Sperre oder Mischmodus festlegen, Ebene hinzufügen, entfernen,
duplizieren oder umordnen, gruppieren oder die Gruppierung aufheben, Maske anhängen oder entfernen,
Referenz oder Smart festlegen. Rückgängig stellt den exakt vorherigen Zustand der Ebenenstruktur
wieder her.

## Farbmodus und indizierte Dokumente

Der Ebenenstapel und die Mischmodi gelten für **RGBA**-Dokumente. **Indizierte** Dokumente haben
bauartbedingt nur eine Ebene – die Zusammensetzung arbeitet ausschließlich mit RGBA.

- Das Umwandeln eines **RGBA-Dokuments mit mehreren Ebenen** in ein indiziertes
  (**Palette ▸ In Indexfarben konvertieren**) **reduziert das zusammengesetzte Ergebnis (pro Frame)
  auf eine einzige indizierte Ebene**. Das lässt sich rückgängig machen: Rückgängig stellt die
  vollständige RGBA-Struktur mit mehreren Ebenen – Gruppen, Masken, Deckkraft, Mischmodi, Referenzen
  und Smart-Verknüpfungen – exakt wieder her.
- Die Rückumwandlung in RGBA macht aus der einzelnen indizierten Ebene eine RGBA-Ebene.

Der Farbmodus des Dokuments ist die einzige maßgebliche Quelle, sodass das, was die Arbeitsfläche
zeigt, was in `.pixproj` gespeichert wird und die Modusanzeige stets übereinstimmen.

## Verwandte Themen

- Wie der Stapel zusammengesetzt wird, erklärt [Mischmodi](blend-modes.md).
- Jeder Animations-Frame hat seinen eigenen Ebenenstapel – siehe die
  [Animationszeitleiste](animation-timeline.md).
