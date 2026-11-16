<!-- site-counterpart: docs/site/pages/en/usage/ai-assistant.md (derived FROM this bundle file, reverse direction) -->
# Der KI-Assistent – den Editor per Chat steuern

Der **KI-Assistent** lässt Sie den Editor in **natürlicher Sprache** steuern. Sie tippen in einem
Chat-Bedienfeld, was Sie möchten, und der Assistent führt es aus, indem er die **eigenen** Operationen der
Anwendung ausführt – dieselben Befehle der [Automatisierung](automation-and-scripting.md), die Sie auch von
Hand aufnehmen, skripten und stapelweise ausführen können. Er ist **modellunabhängig**: Sie richten ihn auf einen
beliebigen KI-Anbieter Ihrer Wahl und hinterlegen Ihren eigenen Schlüssel. Er ist außerdem **optional** – die
Anwendung ist uneingeschränkt nutzbar, ohne ihn je zu konfigurieren.

> **Der Assistent handelt über die sichere Automatisierungsschicht – es wird nichts Neues zugänglich
> gemacht.** Jede Aktion des Assistenten ist eine gewöhnliche Editor-Operation auf der Positivliste, die
> über **dieselbe vertrauenswürdige, `eval`-freie Befehlsschicht** ausgeführt wird wie bei Makros und
> Skripten. Er kann keinen beliebigen Code ausführen, nicht über diese Befehlsschicht hinaus zugreifen und
> sich keine neuen Fähigkeiten ausdenken – eine Chat-Nachricht ist **Daten**, niemals ein Freibrief, etwas
> zu tun, was der Editor nicht ohnehin sicher kann.

## Den Assistenten öffnen

Öffnen Sie das Chat-Bedienfeld über **Hilfe ▸ KI-Assistent**. Es erscheint als **andockbares Bedienfeld**, das
Sie neben der Arbeitsfläche platzieren können, sodass Sie dem Assistenten bei der Arbeit zusehen und Ihr Werk
im Blick behalten. Das Bedienfeld zeigt den laufenden Gesprächsverlauf – Ihre Nachrichten, die Antworten des
Assistenten und die Änderungen, die er am Dokument vornimmt.

Bevor der Assistent mit einem Anbieter sprechen kann, müssen Sie zuerst **einen konfigurieren** (siehe
unten). Bis dahin befindet er sich in einem klar erkennbaren Zustand **ohne konfigurierten Anbieter**, statt
zu scheitern – das Konfigurieren eines Anbieters ist ein einmaliger Schritt.

## Anbieter und Schlüssel konfigurieren

Öffnen Sie den Dialog zur Anbieterkonfiguration über die Schaltfläche **Konfigurieren…** im Bedienfeld
KI-Assistent. Da der Assistent **modellunabhängig** ist, wählen Sie den Dienst und das Modell, die zu Ihnen
passen, und geben Folgendes ein:

| Feld | Was Sie eingeben |
| --- | --- |
| **Anbieter** | Entweder einen **OpenAI-kompatiblen** Dienst oder **Anthropic (Claude)**. Die OpenAI-kompatible Option deckt eine breite Palette von Endpunkten ab (OpenAI selbst, den OpenAI-kompatiblen Endpunkt von Gemini sowie lokale Laufzeitumgebungen wie Ollama oder llama.cpp); die Anthropic-Option spricht Claude nativ an. |
| **Endpunkt-URL** | Den API-Endpunkt des Dienstes. Richten Sie ihn auf einen gehosteten Anbieter oder auf einen lokalen Modellserver auf Ihrem eigenen Rechner. |
| **Modell** | Den zu verwendenden Modellnamen, so benannt, wie Ihr gewählter Anbieter ihn führt. |
| **API-Schlüssel** | Ihren Schlüssel für den Anbieter. Auch für einen lokalen Modellserver muss ein Schlüssel gespeichert werden: Der Assistent zählt einen Anbieter nur dann als konfiguriert, wenn sowohl ein Endpunkt als auch ein nicht leerer Schlüssel gespeichert sind, und er sendet alles, was Sie eingeben, ungeprüft. Wenn Ihr lokaler Server Schlüssel nicht prüft, geben Sie einen beliebigen nicht leeren Text ein, den er akzeptiert. |

Klicken Sie auf **Speichern**, um die Anbietereinstellungen zu speichern.

> **Ihr Schlüssel wird sicher gespeichert – nie in Ihrem Projekt.** Der von Ihnen eingegebene API-Schlüssel
> wird an den **sicheren Speicher für Zugangsdaten des Betriebssystems (den Schlüsselbund des
> Betriebssystems)** übergeben. Er wird **nie in Ihre `.pixproj`-Projektdatei geschrieben, nie protokolliert
> und wandert nie mit einem geteilten oder exportierten Projekt mit**. Das Teilen eines Projekts teilt Ihren
> Schlüssel daher nie. Der Zugriff auf den Schlüssel im laufenden Betrieb nutzt ein optionales Extra
> (`pip install ".[assistant_live]"`); siehe die README.

> **Der Assistent ist optional.** Die Nutzung ist vollständig freiwillig. Wenn Sie nie einen Anbieter
> konfigurieren, ändert sich am restlichen Editor nichts – Sie nutzen den Assistenten einfach nicht. Es gibt
> keine Pflicht zur Anmeldung, und für die Nutzung von PixelArt Creator ist kein Schlüssel nötig.

## Per Chat den Arbeitsablauf steuern

Sobald Sie die Einstellungen eines Anbieters gespeichert haben (einen Endpunkt und einen API-Schlüssel im
Schlüsselbund), tippen Sie eine Anfrage in natürlicher Sprache ein – etwa die Bitte an den Assistenten, einen
Bereich umzufärben oder prozedurale Inhalte zu erzeugen – und senden sie ab. Der Assistent deutet Ihre
Anfrage, entscheidet, welche Editor-Operationen sie erfüllen, führt sie aus und berichtet im Gesprächsverlauf,
was er getan hat. Da er die **echten** Editor-Operationen ausführt, entsprechen die Ergebnisse genau dem, was
Sie erhielten, wenn Sie diese Schritte selbst ausführten.

Ein Austausch mit dem Modell läuft in einem **Hintergrund-Worker**, sodass das Fenster reaktionsfähig
bleibt, während der Assistent nachdenkt.

## Gestufte Absicherung – umkehrbare Aktionen laufen sofort, destruktive fragen zuerst

Der Assistent ordnet jede Aktion, die er ausführen möchte, einer von zwei Stufen zu, und die Stufe
entscheidet, ob Ihre Bestätigung nötig ist. Diese Schranke liegt im Code der Anwendung selbst – sie wird
**nicht** vom KI-Modell entschieden, und keine Formulierung in einer Chat-Nachricht kann den Editor davon
abbringen.

- **Umkehrbare Aktionen werden sofort angewendet.** Eine Aktion, die als einzelner, sauber rückgängig zu
  machender Schritt auf den normalen [Rückgängig-Stapel](app-basics.md) gelegt wird (etwa eine
  Stapelumfärbung oder eine prozedurale Füllung), wird **ohne Nachfrage angewendet**. Sie sehen sie im
  Dokument geschehen und können sie wie jede andere Änderung **rückgängig machen**.
- **Destruktive Aktionen fragen zuerst.** Alles, was nicht auf der Liste der umkehrbaren Aktionen steht,
  gilt standardmäßig als **destruktiv**, und der Assistent **hält an und fragt Sie** unter Nennung der
  genauen Aktion. Sie wird **nur** ausgeführt, wenn Sie bestätigen, und andernfalls abgebrochen – eine
  destruktive Aktion wird nie stillschweigend angewendet.

> **Standardmäßig sicher.** Die Schranke steht standardmäßig auf *Nachfragen*, und zwar für alles,
> was nicht sicher als sauber umkehrbar erkannt wird. Eine neue oder ungewöhnliche Aktion kann also nie durchrutschen und automatisch laufen,
> nur weil sie niemand eingestuft hat – die umkehrbare Stufe ist eine kleine, ausdrückliche Menge, und alles
> andere bekommt eine Bestätigungsabfrage.

## Was der Assistent nicht tut

- **Er kann keinen beliebigen Code ausführen.** Der Assistent steuert nur die Operationen des Editors auf
  der Positivliste über die vertrauenswürdige Befehlsschicht; auf diesem Pfad gibt es kein `eval`/`exec`,
  genau wie bei [Makros und Skripten](automation-and-scripting.md).
- **Er kann die Bestätigungsschranke nicht umgehen.** Keine Anweisung – auch keine, die innerhalb eines
  Werkzeugergebnisses eintrifft – kann eine destruktive Aktion dazu bringen, ihre Bestätigung zu
  überspringen, und keine nicht zugelassene Operation lässt sich ausführen, nur weil die Unterhaltung es
  verlangt.
- **Er gibt Ihren Schlüssel nie preis.** Ihre Zugangsdaten bleiben im Schlüsselbund des Betriebssystems und
  werden nur verwendet, um mit dem von Ihnen konfigurierten Anbieter zu sprechen.

## Barrierefreiheit, Designs und Sprache

Jedes Steuerelement im Assistenten-Bedienfeld und im Anbieterdialog hat einen zugänglichen Namen und ist
über die Tastatur erreichbar, alle Beschriftungen sind vollständig übersetzbar und werden beim Umschalten
der Sprache sofort aktualisiert, und beide Oberflächen werden im hellen und im dunklen Design korrekt
dargestellt.

## Verwandte Themen

- Der Assistent steuert dieselben Operationen wie das übrige
  [Automatisierungssystem](automation-and-scripting.md) – Makros, Skripte, Stapelumfärbung und prozedurale
  Generierung.
- Die Konfiguration eines Anbieters entspricht dem Muster der echten Anbieter in der
  Schicht für die [Cloud-Speicherung](cloud-and-collaboration.md) – mit optionalen Zugangsdaten und
  Ablage im Schlüsselbund (in dieser Version nicht über das Menü Cloud auswählbar).
