# VERWENDUNG (Befehlszeilenoptionen)

Dieses Dokument beschreibt die für uag-Einstiegspunkte verfügbaren Befehlszeilenoptionen.

______________________________________________________________________

## Einstiegspunkte

| Befehl | Python-Modul | Schnittstelle |
|---|---|---|
| `uag` | `python -m uagent` | CLI (stdin-Schleife) |
| `uagg` | `python -m uagent.gui` | GUI (tkinter) |
| `uagw` | `python -m uagent.web` | Webserver (FastAPI) |
| `uaga` | `python -m uagent.a2a.server` | A2A HTTP-Server |

______________________________________________________________________

## CLI-Startoptionen (`uag`)

### `--workdir` / `-C <Pfad>`

Arbeitsverzeichnis. Falls nicht festgelegt, wird auf die Umgebungsvariable `UAGENT_WORKDIR` zurückgegriffen, andernfalls auf das aktuelle Verzeichnis.
Das Verzeichnis wird erstellt, falls es nicht existiert.

### `--tool-genre-mask <int>`

Bitmaske für Tool-Kategorien. Wenn angegeben, wird die interaktive Auswahlaufforderung für Kategorien übersprungen.

| Bit | Kategorie | Beschreibung |
|-----|-------|-------------|
| 1 | basic | Grundlegende Datei- und Chat-Tools |
| 2 | comm | Kommunikationstools (Bluesky, Teams) |
| 4 | office | Office-Suite-Tools (Excel, PDF, PPTX) |
| 8 | devel | Entwicklungswerkzeuge (git, lint, compile) |
| 16 | iot | Werkzeuge für IoT-Geräte (SwitchBot, ECHONET, Matter, UPnP) |
| 32 | exec | Werkzeuge zur Befehlsausführung |
| 64 | external | Externe Plugin-Tools |
| 128 | media | Bild-/Audioerzeugung und -analyse |
| 256 | file | Dateiverwaltungstools |
| 512 | index | Tools zur Quellcode-/Index-Navigation |
| 1024 | dev | Entwickler- und Repository-Tools |
| 2048 | web | Web- und Browser-Tools |
| 4096 | utility | Dienstprogramme und Support-Tools |
| 8191 | all | Alle Werkzeuge |

Beispiele:

```
uag --tool-genre-mask 1 # nur „basic“
uag --tool-genre-mask 9 # „basic“ + „devel“ (1 + 8)
uag --tool-genre-mask 8191    # alle Tools
```

### `--use-tool` / `--no-use-tool`

Aktiviert oder deaktiviert das Senden von Tool-Definitionen an das LLM. Überschreibt die Umgebungsvariable `UAGENT_USE_TOOL`.

- `--use-tool` erzwingt das Senden von Tool-Definitionen.
- `--no-use-tool` unterbindet das Senden von Tool-Definitionen.

Wenn diese Option deaktiviert ist, erhält die `LLM` keine Tool-Definitionen und kann kein Tool aufrufen.

### `--computer-use` / `--no-computer-use`

Aktiviert oder deaktiviert die Computernutzung. Überschreibt die Umgebungsvariable `UAGENT_COMPUTER_USE`.

### `--inject-message` / `-M <message>`

Fügt beim Start eine Nachricht in den LLM ein und beendet sich nach Abschluss. Dies impliziert `--non-interactive`.

### `--embedded`

Eingebetteter Modus für eingeschränkte oder reproduzierbarkeitskritische Bereitstellungen.

- Deaktiviert den Sitzungsspeicher.
- Blendet Tools zur Tool-Verwaltung (`tool_catalog`, `tool_load`, `unload_tool`) aus, sofern sie nicht explizit aktiviert sind.
- Ignoriert `--tool-genre-mask`; verwende `--enable-tool` zum expliziten Laden von Tools.

### `--enable-tool <Name>`

Lädt ein Tool beim Start explizit. Die Option kann wiederholt werden, und durch Kommas getrennte Namen werden ebenfalls akzeptiert.

```
uag --embedded --enable-tool handle_mcp_v2 --enable-tool human_ask
uag --embedded --enable-tool handle_mcp_v2,human_ask
```

Die angegebene Reihenfolge bleibt erhalten und spiegelt sich in der Reihenfolge der Tools wider, die dem LLM übergeben wird. Explizit aktivierte Tools werden gegen automatisches Entladen gesichert.

### `--plugin-dir <Pfad>`

Lädt Plugins aus dem angegebenen Verzeichnis. Die Option kann wiederholt werden.

______________________________________________________________________

## Nur für die Befehlszeile

### `--inject-message-auto <Zieloptionen>`

Startet den Autopiloten aus einem nicht-interaktiven, eingefügten Ziel. Der Wert verwendet dieselben Optionen wie `:auto`; setzen Sie den vollständigen Wert in Anführungszeichen, wenn er Optionen enthält.

```
uag --embedded --enable-tool handle_mcp_v2 --inject-message-auto "Sortiere die Elemente --max-rounds 10"
uag --embedded --enable-tool handle_mcp_v2 --inject-message-auto "Elemente sortieren --infinite"
```

Der normale Modus nutzt den Beurteilungspfad des Prüfers. Setzen Sie `UAGENT_AUTO_SENTINEL=1`, um den Single-LLM-Sentinel-Modus zu aktivieren. In diesem Modus muss das Ziel LLM jede Antwort mit genau einem der folgenden Befehle beenden:

- `<AUTO_CONTINUE>` — weitere Runde ausführen
- `<AUTO_COMPLETE>` — erfolgreich abschließen

Fehlende oder ungültige Marker stoppen den Autopiloten auf sichere Weise. Das Ziel-LLM wird dabei weiterhin ausgeführt; lediglich der zusätzliche Aufruf des Prüfer-LLM wird vermieden.

### `--non-interactive`

Nicht-interaktiver Modus. Die stdin-Schleife wird nicht gestartet. Wird ein Dateipfad als Positionsargument angegeben, wird dieser verarbeitet und das Programm wird sofort beendet.

```
uag --non-interactive README.md
uag --non-interactive --workdir /tmp/project
```

______________________________________________________________________

## Webserver-Optionen (`uagw`)

### `--host <address>`

Bind-Adresse für den Webserver (Standard: `127.0.0.1`, kann durch `UAGENT_WEB_HOST` überschrieben werden).

Standardmäßig lauscht der Webserver nur auf localhost (`127.0.0.1`). Um ihn von anderen Rechnern im Netzwerk aus erreichbar zu machen, verwenden Sie `--host 0.0.0.0`.

```
uagw --host 0.0.0.0
uagw --host 192.168.1.10
```

### `--tool-genre-mask <int>`

Wählen Sie Werkzeuggenres mithilfe derselben Bitmaske aus, die oben beschrieben wurde. Wenn diese Option angegeben wird, wird die interaktive Genre-Abfrage übersprungen.

### `--use-tool` / `--no-use-tool`

Aktiviert oder deaktiviert das Senden von Tool-Definitionen an den LLM. Überschreibt `UAGENT_USE_TOOL`.

### `--computer-use` / `--no-computer-use`

Aktiviert oder deaktiviert die Computernutzung. Überschreibt `UAGENT_COMPUTER_USE`.

### `--no-frontend`

Führt API ausschließlich ohne HTML-Vorlagen oder statische Frontend-Dateien aus.

### `--embedded`

Deaktiviert den Sitzenspeicher und blendet die Tools zur Tool-Verwaltung aus (`tool_catalog`, `tool_load`, `unload_tool`).

______________________________________________________________________

## A2A-Serveroptionen (`uaga`)

### `--host <address>`

Bind-Adresse für den A2A-HTTP-Server (Standard: `0.0.0.0`, überschreibbar durch `UAGENT_A2A_HOST`).

### `--port <Zahl>`

Portnummer für den A2A- und HTTP-Server (Standard: `8765`, kann durch `UAGENT_A2A_PORT` überschrieben werden).

### `--reload`

Hot-Reload bei Codeänderungen aktivieren (Standard: deaktiviert, kann durch `UAGENT_A2A_RELOAD` überschrieben werden).

```
uaga --host 127.0.0.1 --port 8080 --reload
```

### `--tool-genre-mask <int>`

Wählt Tool-Genres anhand der oben beschriebenen Bitmaske aus. Wenn angegeben, wird die interaktive Genre-Abfrage übersprungen.

### `--use-tool` / `--no-use-tool`

Aktiviert oder deaktiviert das Senden von Tool-Definitionen an den LLM. Überschreibt `UAGENT_USE_TOOL`.

### `--computer-use` / `--no-computer-use`

Aktiviert oder deaktiviert die Computernutzung. Überschreibt `UAGENT_COMPUTER_USE`.

### `--embedded`

Deaktiviert den Sitzungsspeicher und blendet die Tools zur Tool-Verwaltung aus (`tool_catalog`, `tool_load`, `unload_tool`).

______________________________________________________________________

## Zugehörige Umgebungsvariablen

| Variable | Beschreibung |
|---|---|
| `UAGENT_PROVIDER` | LLM-Anbietername (beim Start erforderlich) |
| `UAGENT_*_API_KEY` | API-Schlüssel für den ausgewählten Anbieter |
| `UAGENT_WORKDIR` | Standard-Arbeitsverzeichnis |
| `UAGENT_WEB_HOST` | Bind-Adresse des Webservers (Standard: `127.0.0.1`) |
| `UAGENT_A2A_HOST` | Bind-Adresse des A2A-Servers (Standard: `0.0.0.0`) |
| `UAGENT_A2A_PORT` | Port des A2A-Servers (Standard: `8765`) |
| `UAGENT_A2A_RELOAD` | Hot-Reload für A2A standardmäßig aktivieren |
| `UAGENT_USE_TOOL` | Tools deaktivieren, wenn auf `0`, `false`, `no` oder `off` gesetzt |
| `UAGENT_COMPUTER_USE` | „Computer Use“ standardmäßig aktivieren oder deaktivieren |
| `UAGENT_SESSION_STORE` | Sitzungsspeicher aktivieren oder deaktivieren; Im Embedded-Modus ist der Wert `0` erzwungen |
| `UAGENT_PLUGIN_DIRS` | Zusätzliche Suchverzeichnisse für Plugins |
| `UAGENT_AUTO_SENTINEL` | Aktiviert den Single-LLM-Autopilot-Sentinel-Modus, wenn auf `1` gesetzt |
| `UAGENT_CONSECUTIVE_TOOL_CALL_LIMIT` | Maximale Anzahl aufeinanderfolgender neuer Tool-Aufrufe (Standard: `100`) |
| `UAGENT_MAX_TOOL_ROUNDS` | Maximale Anzahl von LLM-/Tool-Runden pro Benutzeroperation (Standard: `200`) |
| `UAGENT_SHRINK_CNT` | Optionaler Schwellenwert für die automatische Verkleinerung von Nachrichten (`0`/nicht gesetzt = deaktiviert) |
| `UAGENT_SHRINK_KEEP_LAST` | Anzahl der nach der Verkleinerung beizubehaltenden Nachrichten (Standard: `20`) |
| `UAGENT_LANG` | Sprache der Benutzeroberfläche (`ja`, `en` usw.) |

Die vollständige Liste der Umgebungsvariablen finden Sie unter [ENVIRONMENT.md](ENVIRONMENT.md).

______________________________________________________________________

## Beispiele

### Minimaler Start mit OpenAI

```
set UAGENT_PROVIDER=openai
set UAGENT_OPENAI_API_KEY=sk-...
uag
```

### Lokales Ollama nur mit grundlegenden Tools

```
set UAGENT_PROVIDER=ollama
set UAGENT_OLLAMA_MODEL=qwen2.5:7b
uag --tool-genre-mask 1
```

### Webserver auf allen Schnittstellen

```
set UAGENT_WEB_HOST=0.0.0.0
uagw
```

oder

```
uagw --host 0.0.0.0
```

### A2A-Server auf localhost mit benutzerdefiniertem Port

```
uaga --host 127.0.0.1 --port 8080
```

### Tools für ein kleines Modell deaktivieren

```
uag --no-use-tool --tool-genre-mask 1
```

### Nicht-interaktive Dateiverarbeitung

```
uag --non-interactive README.md
```
