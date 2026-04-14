# uag (uagent)

uag ist ein universeller Tool-Ausführungsagent, der in Ihrer lokalen Umgebung läuft. Er interagiert mit Benutzern über eine Befehlszeilenschnittstelle (CLI) und führt verschiedene Aufgaben wie Dateioperationen, Websuche und Python-Skriptausführung gemäß den Anweisungen aus.

## Hauptfunktionen

- **Lokale Dateioperationen**: Lesen, Schreiben, Bearbeiten und Suchen von Dateien.
- **Informationsbeschaffung**: Websuche mit DuckDuckGo und Extrahieren von Webseiteninhalten.
- **Code-Ausführung**: Sicheres Ausführen von Python-Skripten und PowerShell-Befehlen.
- **Multimedia-Verarbeitung**: Bildgenerierung, Lesen von PDF/PPTX-Dateien, Screenshots.
- **Mehrsprachige Unterstützung**: Unterstützt mehrere Sprachen, einschließlich Deutsch, Japanisch und Englisch.
- **MCP (Model Context Protocol) Unterstützung**: Kann mit externen MCP-Servern verbunden werden, um die Funktionen zu erweitern.

## Installation

Sie können es mit pip von PyPI installieren:

```bash
pip install uag
```

Beim ersten Start wird automatisch ein Einrichtungsassistent gestartet.

## Schnellstart

Geben Sie nach der Installation einfach den folgenden Befehl ein, um zu starten:

```bash
uag
```

Nach dem Start können Sie den Agenten beispielsweise um Folgendes bitten:
- "Lies die README im aktuellen Verzeichnis und fasse ihren Inhalt zusammen."
- "Suche im Web nach den neuesten KI-Nachrichten und erstelle eine Zusammenfassung."
- "Komprimiere alle PNG-Dateien im Ordner 'images' in eine ZIP-Datei."

## Konfiguration (Umgebungsvariablen)

Das Verhalten von uag kann über Umgebungsvariablen konfiguriert werden. Weitere Details finden Sie unter:
- [ENVIRONMENT.md (English)](ENVIRONMENT.md)

## Dokumentation

- [README.md (English)](README.md)
- [README.ja.md (Japanese)](README.ja.md)

## Lizenz

Veröffentlicht unter der Apache License 2.0.
