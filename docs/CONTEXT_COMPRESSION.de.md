# Kontextkomprimierung und begrenzter Modellkontext

uag nutzt mehrere Ebenen, um den aktiven Modellkontext begrenzt zu halten. Das Ziel besteht darin, unnötige Eingabetoken zu reduzieren, ohne dabei Dateien, Werkzeugergebnisse oder Sitzungsdaten zu entfernen, die der Benutzer möglicherweise noch benötigt.

Dieses Dokument beschreibt die aktuelle Implementierung. Es unterscheidet zudem zwischen deterministischem Verhalten und anbieterspezifischem oder durch LLM unterstütztem Verhalten.

## 1. Dynamische Tool-Oberfläche

Nicht jede Tool-Definition muss in jedem Durchlauf an das Modell gesendet werden.

- `tool_catalog` durchsucht die verfügbaren Funktionen.
- `tool_load` aktiviert nur die für die aktuelle Aufgabe erforderlichen Tools.
- `tool_catalog`, `tool_load` und `unload_tool` stehen weiterhin als Verwaltungstools zur Verfügung.
- GPT-5.4-kompatible Responses API-Abläufe können natives serverseitiges Tool Search nutzen.
- Der Legacy-Modus für Tool Search schränkt die Werkzeugspezifikationen mit `tool_catalog` auf der Client-Seite ein.

Dies reduziert die von Werkzeugschemata verwendeten Eingabetoken, insbesondere in Installationen mit vielen Werkzeugen.

## 2. Umfangreiche textbasierte Tool-Ergebnisse werden zu Artefakten

Wenn ein textbasiertes Tool-Ergebnis den Artifact-Schwellenwert überschreitet, speichert uag das vollständige Ergebnis als Artifact und sendet dem Modell anstelle des Volltexts eine begrenzte Referenz sowie eine Vorschau.

Die Standardgrenzwerte lauten:

```text
UAGENT_TOOL_RESULT_ARTIFACT_THRESHOLD_CHARS=100000
UAGENT_TOOL_RESULT_MAX_CHARS=12000
```

Die für das Modell sichtbare Darstellung enthält den Tool-Namen, die ursprüngliche Länge, eine `artifact://`-Referenz, den Speicherpfad und eine begrenzte Vorschau. Das vollständige Ergebnis bleibt über den Artifact-Speicher verfügbar.

Der Schwellenwert kann mit `UAGENT_TOOL_RESULT_ARTIFACT_THRESHOLD_CHARS` geändert werden. Ein Wert von `0` deaktiviert die Artifact-Beförderung. `UAGENT_TOOL_RESULT_MAX_CHARS` steuert die übliche Richtlinie für begrenzte Ergebnisse; `0` deaktiviert diese übliche Begrenzung.

## 3. Begrenztes Abrufen von `Artifact`

Das Infrastruktur-Tool `artifact_read` ruft nur den angeforderten Teil eines `Artifact` ab:

- `start_line` wählt die erste Zeile aus.
- `max_lines` ist auf 500 begrenzt.
- `max_chars` ist auf 50.000 Zeichen begrenzt.
- Es können sowohl eine Artifact-ID als auch eine `artifact://`-URI verwendet werden.

Dies ermöglicht es, einen kleinen relevanten Bereich zu untersuchen, anstatt eine gesamte Datei oder ein Befehlsergebnis in den nächsten Modelldurchlauf erneut einzuspeisen.

Neue Artefakte werden darunter gespeichert:

```text
~/.uag/artifacts/
```

Bestehende ältere Artifact-Pfade bleiben aus Kompatibilitätsgründen lesbar.

## 4. Isolierung binärer Nutzdaten

Inline-Binärdaten werden nicht als textuelles Tool-Ergebnis an den nächsten Modelldurchlauf gesendet. Felder im Format Base64 werden durch einen kurzen Marker ersetzt, beispielsweise:

```text
[Binärdaten aus dem LLM-Kontext ausgelassen]
```

Die Benutzeroberfläche und Remote-Clients können weiterhin Anhänge im Arbeitsspeicher empfangen, und gespeicherte Dateien bleiben über ihre Pfade oder Artifact-Referenzen verfügbar. Dadurch wird verhindert, dass Bilder, Audiodateien, Screenshots und andere binäre Nutzdaten den textuellen Modellkontext übermäßig vergrößern.

Die gleiche Klasse von binären Nutzdaten wird vor der Persistenz in SQLite und JSONL bereinigt, wodurch verhindert wird, dass sie nach einem Neuladen der Sitzung als große Nutzdaten zurückgegeben werden.

## 5. Automatische Komprimierung des Verlaufs

uag kann ältere Konversationsverläufe komprimieren, wenn die Anzahl der Nachrichten oder die geschätzte Tokenanzahl das konfigurierte Limit erreicht.

Die Komprimierungsrichtlinie berücksichtigt:

- die Anzahl der Nicht-System-Nachrichten;
- das aufgelöste Kontextfenster des Modells, sofern verfügbar;
- `UAGENT_SHRINK_KEEP_LAST` (standardmäßig 20);
- `UAGENT_SHRINK_MAX_TOKENS` oder eine modellspezifische Überschreibung;
- `UAGENT_SHRINK_CNT`; und
- `UAGENT_SHRINK_RATIO` (standardmäßig 0,5, wenn ein Kontextfenster bekannt ist).

Ein modellspezifischer Grenzwert kann wie folgt angegeben werden:

```text
UAGENT_SHRINK_MAX_TOKENS_<MODEL_NAME>
```

Eine bereits erstellte Zusammenfassung wird nicht bei jedem Durchlauf neu generiert. Die Hysterese erfordert, dass sich genügend neue Historie ansammelt oder ein weiterer Token-Budget-Überlauf auftritt, bevor die Komprimierung erneut ausgeführt wird.

## 6. LLM-gestützte Verlaufszusammenfassungen

Wenn die automatische Komprimierung LLM verwendet, werden ältere Benutzer-, Assistenten- und Werkzeugmeldungen zu einer fortlaufenden Systemmeldung zusammengefasst, während der aktuelle Teil beibehalten wird.

Lange Verlaufsdaten können in Blöcken zusammengefasst werden. Die entsprechenden Steuerungen lauten:

```text
UAGENT_SHRINK_CHUNK_SIZE=100
UAGENT_SHRINK_SINGLE_SHOT=1
```

Die Zusammenfassung wird nach vorne verschoben, anstatt eine unbegrenzte Folge von Zusammenfassungsmeldungen zu erzeugen. Dies ist ein LLM-gestützter Vorgang und kann zusätzliche Anfragen an den Provider erfordern.

## 7. Deterministische Fallback-Komprimierung

Wenn eine LLM-Zusammenfassung nicht verfügbar ist, kann uag die führenden Systemmeldungen und nur die allerneuesten Meldungen beibehalten. Tool-Aufrufgrenzen werden korrigiert, damit der resultierende Verlauf nicht mit einem verwaisten Tool-Aufruf beginnt oder endet.

Der Loader und der Sanitizer entfernen zudem modellirrelevante oder ungültige Einträge, darunter reine UI-Meldungen, interne Steuerungsmeldungen, fehlerhafte Protokollzeilen, nicht unterstützte Rollen, verwaiste Tool-Ergebnisse und unvollständige Tool-Aufrufblöcke.

Beim Neuladen einer Sitzung wird die aktuelle Systemaufforderung wiederhergestellt und es werden nur relevante, eingefügte Systemmeldungen, wie z. B. Skill- oder Hook-Kontext, beibehalten.

## 8. Wiederherstellung nach Kontextüberlauf

Wenn ein Anbieter meldet, dass das Kontextfenster überschritten wurde, identifiziert uag eine große Meldung aus dem jüngsten Verlauf und macht diese Meldung sowie den darauf folgenden Verlauf rückgängig, bevor ein erneuter Versuch unternommen wird. Dies ist ein reaktiver Fallback und kein Ersatz für die normale Budgetierung.

## 9. Anbieterseitige Fortsetzung und Komprimierung

Sofern unterstützt, verwendet Responses API die `previous_response_id`, um eine Antwortkette fortzusetzen, ohne den gesamten vom Anbieter verwalteten Antwortverlauf vom Client erneut senden zu müssen.

Responses API-Abläufe senden zudem eine anbieterseitige Komprimierungskonfiguration unter Verwendung desselben lokalen Schrumpfungsschwellenwerts. Das genaue Verhalten ist anbieterabhängig; lokale Artifact- und Verlaufsrichtlinien bleiben die anbieterunabhängigen Sicherheitsvorkehrungen.

## 10. Effizienz bei der Token-Zählung

Token-Zählwerte, die für Komprimierungsentscheidungen verwendet werden, werden zwischengespeichert und inkrementell aktualisiert, wenn nur neue Nachrichten hinzugefügt wurden. Dies reduziert zwar nicht direkt den Modellkontext, senkt jedoch den CPU-Aufwand und die Latenz bei der Entscheidung, wann eine Komprimierung erforderlich ist.

## Was noch keine vollständig einheitliche Ebene ist

Die aktuelle Implementierung bietet noch nicht alle der folgenden Funktionen als einen einzigen anbieterneutralen Manager:

- ein einheitliches `ContextManager` und `ContextBudget`;
- ein `ToolResultRecord` mit Metadaten zu Wichtigkeit und Verdrängung;
- semantische Zusammenfassungen, die kein `LLM` erfordern;
- automatisches Abrufen und erneutes Einfügen relevanter Artefakte;
- einen zentralen Ergebnis-Manager, der die `Artifact`-Konvertierung für jedes binärproduzierende Tool gewährleistet; oder
- prioritätsbewusste Verdrängung über alle System-, Verlaufs-, Tool-Schema- und Ergebniskategorien hinweg.

Kurz gesagt kombiniert uag derzeit deterministische Trunkierung, Artifact-Referenzen, Binärisolierung, dynamische Toolauswahl, Verlaufszusammenfassungen, Anbieterfortführung und Überlaufwiederherstellung. Die Entwurfs-Roadmap für eine einheitliche Kontextschicht ist in [UAG_CONTEXT_MANAGEMENT_DESIGN.md](UAG_CONTEXT_MANAGEMENT_DESIGN.md) dokumentiert.
