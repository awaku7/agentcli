<p align="center">
 <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="720">
</p>

<h1 align="center">uag – Universelles KI-Gateway</h1>

<p align="center">
 <b>U</b>niversal <b>A</b>I <b>I <b>G</b>ateway – Ihre Umgebung, Ihre Freiheit.
</p>

<p align="center">
 Dateioperationen / Web-Suche / Bildgenerierung und -analyse / PDF- und Excel-Extraktion / IoT-Steuerung / MCP-Integration<br>
 24 Anbieter / 3 UIs / Parallele Toolausführung / Agent Marktplatz für Kompetenzen
</p>

<p align="center">
 <a href="https://github.com/awaku7/agentcli">GitHub</a>
 ·
 <a href="https://pypi.org/project/uag/">PyPI</a>
 ·
 <a href="https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md">Lesen Sie dies in Ihrer Sprache</a>
</p>

______________________________________________________________________

## Warum uag?

**Befreien Sie sich von der Anbieterbindung.** Die meisten KI-Assistenten binden Sie an einen bestimmten Anbieter oder Cloud-Dienst. uag ist anders.

- **Läuft lokal** auf Ihrem Computer. Ihre Daten bleiben bei Ihnen (außer API Anrufe, die Sie tätigen).
- **Anbieterfreiheit**: OpenAI, Claude, Gemini, DeepSeek, Ollama, Azure, Bedrock, Novita, HuggingFace... 24 Anbieter, alle über eine einzige Schnittstelle zugänglich. Wechseln Sie zwischen ihnen, indem Sie Umgebungsvariablen neu konfigurieren – keine Neuinstallation, keine Migration.
- **222 Tools**: Datei-E/A, Websuche, Bildgenerierung, Gmail, BLE-Gerätescan, MCP-Serverintegration – **130 sind statisch als parallelsicher gekennzeichnet** (bis zu 8 werden gleichzeitig über den Thread-Pool ausgeführt, konfigurierbar über „UAGENT_PARALLEL_WORKERS“). Wenn LLM mehrere Tool-Aufrufe gleichzeitig auslöst, parallelisiert uag diese automatisch.
- **3 UIs + A2A**: CLI, GUI, Web und Agent-zu-Agent-Protokoll. Gleiche Engine, beliebige Schnittstelle.
- **IoT-fähig**: SwitchBot, ECHONET Lite, Matter, UPnP – Steuern Sie Ihre Heimgeräte durch KI.
- **Agentenfähigkeiten**: Installieren Sie von der Community entwickelte Fähigkeiten vom Marktplatz. Erweitern Sie uag endlos.

uag ist **Ihr KI-Assistent zu Ihren Bedingungen**. Nicht an einen Anbieter gebunden, nicht an eine Schnittstelle gebunden, nicht an eine Plattform gebunden.

## Schnellstart

```bash
pip install uag
uag
```

Beim ersten Start führt Sie der Setup-Assistent durch die Anbieterkonfiguration.
Siehe [docs/ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/docs/ENVIRONMENT.md) für alle Umgebungen Variablen.

## Computer Use

Computer Use ist Opt-in und unterstützt sowohl eine sichtbare Playwright Browser-Laufzeitumgebung
als auch eine Desktop-Laufzeitumgebung. Wenn diese Option aktiviert ist, werden beide Laufzeiten erstellt und registriert.

```bat
set UAGENT_COMPUTER_USE=1
```

Verwenden Sie stattdessen „desktop“, um die Betriebssystem-Desktop-Laufzeit auszuwählen. Runtime Ressourcen werden bei normalem Beenden, „Ctrl-C“ und Herunterfahren des Prozesses geschlossen. Legen Sie
`UAGENT_COMPUTER_HEADLESS=1` für browserbasierte CI- oder Smoke-Tests fest.
Siehe [docs/COMPUTER_USE_IMPLEMENTATION.md](docs/COMPUTER_USE_IMPLEMENTATION.md)
für die Integrations- und Sicherheitsdetails.

## Realtime Voice und AEC3

Der Echtzeit-Voice-Modus unterstützt OpenAI Realtime, Azure OpenAI GPT Realtime, xAI Grok Voice API, Google Gemini Multimodal Live API und Amazon Bedrock Nova Sonic mit Vollduplex-Mikrofon und Lautsprecher-I/O. Das erforderliche AEC3-Backend „pywebrtc-audio“ wird automatisch installiert, und das optionale bidirektionale Streaming-SDK von Bedrock wird nur dann automatisch installiert, wenn der Bedrock-Anbieter ausgewählt ist:

```bash
python scheck.py realtime
```

Die AEC3-Pipeline empfängt das tatsächliche Mikrofonsignal („near“) und das tatsächlich an den Lautsprecher weitergeleitete Audio („far“), damit der Assistent zuhören kann beim Sprechen. Aktivieren Sie die Diagnose nur, wenn Sie Audioprobleme untersuchen:

```bat
set UAGENT_REALTIME_AUDIO_DEBUG=1
python scheck.py realtime
```

### OpenAI Realtime Function Calling

OpenAI Realtime unterstützt eine sicherheitsbegrenzte Function Calling-Integration. Der aktuelle Echtzeitadapter stellt „get_current_time“ automatisch schreibgeschützt bereit. Zerstörerische Tools und Gerätekontrollen werden ohne eine explizite Zulassungsliste und einen Bestätigungsfluss nicht offengelegt. Grok Realtime verwendet einen separaten Adapter und verwendet nicht diesen OpenAI-spezifischen Funktionsaufrufpfad.

## Features

### 🧠 Multi-Provider-Architektur

OpenAI / PFN (PLaMo) / Azure / Bedrock / OpenRouter / Ollama / llama.cpp / Gemini / Vertex AI / Claude / Grok / NVIDIA / Novita / DeepSeek / Z.AI (Zhipu AI) / HuggingFace / Alibaba Cloud (Qwen) / KIMI (Moonshot AI) / Xiaomi MiMo / LM Studio / MiniMax / Sakana AI (Fugu) / SAKURA AI Engine / Together AI / Vercel AI Gateway

Alle Anbieter nutzen das gleiche Toolset und die gleiche Schnittstelle. Wechseln Sie, indem Sie „UAGENT_PROVIDER“ festlegen – keine Codeänderungen, keine separaten Installationen.

#### Ollama und llama.cpp

Ollama und llama.cpp sind separate Anbieter. Ollama verwendet seine eigene Dienst- und Modellverwaltung, während „llama.cpp“ eine Verbindung zu einem „llama-server“ OpenAI-kompatiblen Endpunkt herstellt:

```bash
# Ollama
UAGENT_PROVIDER=ollama
UAGENT_OLLAMA_BASE_URL=http://localhost:11434/v1
UAGENT_OLLAMA_DEPNAME=llama3.1

# llama.cpp / llama-server
UAGENT_PROVIDER=llama_cpp
UAGENT_LLAMA_CPP_BASE_URL=http://localhost:8080/v1
UAGENT_LLAMA_CPP_DEPNAME=local-model
UAGENT_LLAMA_CPP_API_KEY=dummy
```

Der Anbieter llama.cpp verwendet den Chat Vervollständigungskompatibler Pfad. Behalten Sie „UAGENT_RESPONSES=0“ bei, es sei denn, ein kompatibler Proxy ist konfiguriert.

### ⚡ Parallele Tool-Ausführung

Wenn LLM mehrere Tools gleichzeitig anfordert, **parallelisiert** uag diese automatisch.
130 Tools sind statisch mit „x_parallel_safe“ gekennzeichnet und werden gleichzeitig über einen „ThreadPoolExecutor“ ausgeführt (standardmäßig 8 Threads; Setzen Sie „UAGENT_PARALLEL_WORKERS“, um sich zu ändern.

**Beispiel**: Fragen Sie „Überprüfen Sie das Wetter in den nordischen Hauptstädten“ → LLM löst „search_web“ × 5 Länder aus → alle 5 Suchvorgänge werden parallel ausgeführt → Ergebnisse werden in einem Stapel gesammelt.

Die aktuelle Zählung basiert auf Toolmodulen, die eine „TOOL_SPEC“ definieren (derzeit 222, einschließlich der 2 Rust-gestützten Tools in `src/uagent/tools_rust/`). `http_request` verwendet methodensensitive Sicherheit: `GET`/`HEAD`/`OPTIONS`-Aufrufe können parallel ausgeführt werden, während Schreibmethoden seriell bleiben.

Nur-Lese-Tools (Dateisuche, Hash-Berechnung, Verzeichnisliste, Übersetzung, DB-Abfragen usw.) werden aggressiv parallelisiert.

### 🧩 Plugin-System (Claude-Code-kompatibel)

uagent implementiert einen **Claude Codekompatibles Plugin-System**. Plugins bündeln Fertigkeiten, Agenten, MCP-Server, Hooks und mehr in eigenständigen Verzeichnissen mit einem „.claude-plugin/plugin.json“-Manifest.

**Unterstützte Komponenten**: Fertigkeiten, Unteragenten, MCP-Server, Hooks (12 Lebenszyklusereignisse), Slash-Befehle, Ausgabestile, userConfig, Abhängigkeiten, Kanäle, Marktplätze

**CLI Befehle**:

```
:plugin list # Installierte Plugins auflisten
:plugin install <Quelle> [--scope] # Installieren (dir/zip/git/http)
:plugin install <Name>@<Marktplatz> # Von Marktplatz installieren
:plugin entfernen <Name> # Deinstallieren
:plugin aktivieren/deaktivieren <Name> # Toggle
:plugin Marketplace hinzufügen/entfernen/Liste # Verwalten Marketplaces
:plugin init <Name> # Gerüst für neues Plugin
```

Siehe [DEVELOP_PLUGIN.md](src/uagent/docs/DEVELOP_PLUGIN.md) für eine vollständige Dokumentation.

### 🔄 Sitzungskontinuität

- **Anbieter während der Sitzung wechseln** mit „UAGENT_PROVIDER“ – Konversation Der Verlauf bleibt erhalten.
- **Vergangene Sitzungen neu laden** mit `:load <index>` – dort weitermachen, wo Sie aufgehört haben.
- **Tool-Ergebnis-Caching** vermeidet redundante Neuausführung, wenn derselbe Tool-Aufruf wiederholt wird.

### 🛠 229 Tools

| Kategorie | Werkzeuge |
|---|---|
| **Dateioperationen** | lesen/schreiben/erstellen/löschen/suchen/grep/hash/zip, file_type, parse_eml (.eml-Dateien), `path_alias` |
| **Web** | fetch_url, search_web, Screenshot, browser_playwright, „url_alias“, „public_transit_route“ ([guide](docs/PUBLIC_TRANSIT_ROUTE.md)) |
| **Medien** | generieren_bild, analysieren_bild, img2img, audio_speech, audio_transcribe |
| **Dokumente** | PDF/PPTX/DOCX/RTF/ODT-Extraktion, strukturierte Excel-Extraktion |
| **Prognose** | Zeitreihenvorhersage mit 9 Modellen (AutoARIMA, Prophet, LightGBM, CatBoost, TimesFM usw.), automatische Modellauswahl, Plotgenerierung, i18n |
| **Kommunikation** | gmail_send, gmail_read, bluesky, discord_channel, teams_webhook, **pybitchat** (BLE Mesh) – siehe [COMMUNICATION.md](https://github.com/awaku7/agentcli/blob/main/docs/COMMUNICATION.md) und [BITCHAT.md](https://github.com/awaku7/agentcli/blob/main/docs/BITCHAT.md) |
| **IoT** | SwitchBot (Cloud + BLE), ECHONET Lite, Matter, UPnP, reverse_geocode |
| **Cloud-APIs** | „aws_api“, „gcp_api“, „azure_api“ – generische AWS-, Google Cloud- und Azure API-Operationen; Schreibvorgänge erfordern eine explizite Bestätigung |
| **Entwicklungstools** | workspace_status, git_ops, git_review, security_scan, Coverage_report, python_compile, lint_format, run_tests, db_query, **29 Quellcode-Navigatoren (IDX-Familie)** |
| **MCP** | Mit externen MCP-Servern verbinden, Tools auflisten, ausführen – [OAuth-/Proxy-Anleitung](docs/MCP_OAUTH_PROXY_GUIDE.md) |
| **A2A** | Agent-zu-Agent-Kommunikation (mit anderen uag-Instanzen oder A2A-kompatiblen Servern) |
| **System** | Umgebungsvariablen, Systemspezifikationen, Uhrzeit, Datumsberechnung, [Mengen](docs/QUANTITIES.md), [geodesic_distance](docs/GEODESIC_DISTANCE.md), uuid_gen, slugify |
| **Quellennavigation** | **29 IDX-Tools** für Python, PHP, TypeScript, Java, C#, Dart, C/C++, Rust, Go, Swift, Kotlin, COBOL, VBA, LotusScript, Makefile – erhalten Sie einen Funktions-/Klassenindex oder eine spezifische Definition, ohne die gesamte Datei zu lesen |

#### Repository-Überprüfung und -Abdeckung

- `workspace_status`: Git-Zweig des aktiven Arbeitsbereichs, Änderungen, Upstream melden Synchronisierungsstatus, Python-Laufzeit und allgemeine Projektmarkierungen, ohne Dateien zu ändern.
- „git_review“: Git-Änderungen, riskante Dateien, Testkandidaten und geheime Ergebnisse zusammenfassen, ohne geheime Werte preiszugeben.
- „security_scan“: Repository-Dateien nach wahrscheinlichen Geheimnissen und riskanten Konfigurationsdateien durchsuchen.
- „coverage_report“: Abdeckung für Python, TypeScript/JavaScript, Rust ausführen und normalisieren, Go, Java/Kotlin, .NET, C/C++, Ruby, PHP, Swift und Dart/Flutter.
- Fehlende Abdeckungsabhängigkeiten können automatisch installiert werden, wenn die Ausführung angefordert wird; „dry_run“ installiert niemals Pakete.

Siehe [Repository-Analysetools](docs/REPOSITORY_TOOLS.md) für Parameter, Ausgabe und Sicherheitsdetails.

Siehe [Pfad- und URL-Aliase](docs/PATH_URL_ALIASES.md) für die Verkürzung wiederholter Dateipfade und URLs in Tool-Argumenten.

### 🖥 4 Schnittstellen + VS Code-Erweiterung

| Modus | Befehl | Zweck |
|---|---|---|
| **CLI** | `uag` | Schnelle terminalbasierte Bedienung |
| **GUI** | `uagg` | Desktop-Benutzeroberfläche über tkinter |
| **Web** | `uagw` | Browserbasierter Zugriff |
| **A2A Server** | `uaga` | Agent2Agent-Protokoll für Multiagentenkommunikation |
| **VS-Code** | — | [Erweiterung](https://github.com/awaku7/agentcli/blob/main/docs/VSCODE.md) mit Chat-Panel, Erklärung, Umgestaltung, Fehler beheben und Tools-Baumansicht |

Siehe [VSCODE.md](https://github.com/awaku7/agentcli/blob/main/docs/VSCODE.md) für Details zur VS Code-Erweiterung – Installation, Befehle, Tastenkombinationen und Konfiguration.

### 🏠 IoT-Gerätesteuerung

- **BACnet**: Lesen/Schreiben von BACnet/IP-Geräten (HLK, Beleuchtung, Stromzähler). COV-Abonnement für Push-Benachrichtigungen
- **Modbus TCP**: Halte-/Eingaberegister und Spulen lesen/schreiben. Abfragebasierte Änderungsüberwachung
- **OPC UA**: Adressraum durchsuchen, Variablen lesen/schreiben, Datenänderungen abonnieren
- **SwitchBot**: Cloud-Batch-Steuerung und BLE-Scan/Steuerung. Abfragebasiertes Abonnement
- **ECHONET Lite**: Entdecken, steuern und abonnieren Sie INF-Benachrichtigungen von Haushaltsgeräten (Klimaanlage, Lichter, Warmwasserbereiter usw.)
- **Matter**: Lese-/Schreibsteuerung + Attributabonnement für die Überwachung von Zustandsänderungen
- **UPnP**: Geräteerkennung und IGD-Portweiterleitung

Siehe [IOT_USECASE.md](https://github.com/awaku7/agentcli/blob/main/docs/IOT_USECASE.md)

### 🎯 Agent Skills Marketplace

`:skills mp_search` zum Durchsuchen von [SkillsMP](https://skillsmp.com) und [ClawHub](https://clawhub.ai) nach Community Fähigkeiten.
Installieren und erweitern Sie die Fähigkeiten von uag im Handumdrehen.

### 🤖 Auto-Pilot (`:auto`)

uag kann **autonom ein Ziel über mehrere LLM-Runden verfolgen**. Perfekt für komplexe, mehrstufige Aufgaben, die eine iterative Verfeinerung erfordern.

- **So funktioniert es**: Jede Runde besteht aus einer Hauptabfrage (Schritt A), gefolgt von einem Prüferurteil (Schritt B), das über „ABSCHLUSS oder WEITER?“ entscheidet.
- **Gleicher Anbieter, dasselbe API**: Das Prüferurteil verwendet den gleichen Codepfad wie die Hauptabfrage – einschließlich Antworten API-Unterstützung.
- **Separater Richter LLM** (optional): Legen Sie „UAGENT_AP_PROVIDER“ fest, um einen anderen Anbieter/ein anderes Modell für den Prüfer zu verwenden (z. B. ein günstigeres Modell für die Beurteilung).
- **Jederzeit beenden**: Drücken Sie **F11**, um den Auto-Pilot zu stoppen. **F12** stoppt nur die aktuelle LLM-Antwort. Oder lassen Sie den Prüfer entscheiden, wann das Ziel erreicht ist.
- **Konfigurierbar**: „--max-rounds N“, um das Budget zu kontrollieren.

Siehe [README_AUTO.md](https://github.com/awaku7/agentcli/blob/main/docs/README_AUTO.md) für eine vollständige Dokumentation.

### 🧩 Batch State Manager

uag kann den Fortschritt über lang laufende Aufgaben mit mehreren Dateien verfolgen. Wenn der LLM Dutzende Dateien verarbeitet, speichert „batch_state“ die Liste der ausstehenden, abgeschlossenen und fehlgeschlagenen Dateien auf der Festplatte. Wenn die Sitzung endet oder eine Runde abläuft, wird der nächste Lauf dort fortgesetzt, wo er aufgehört hat – nichts geht verloren.

### 🛡 Human-in-the-Loop

`human_ask` lässt den LLM anhalten und um Ihre Bestätigung bitten, bevor destruktive Vorgänge (Löschen von Dateien, Überschreiben, Shell-Befehle) ausgeführt werden. Sie behalten die Kontrolle.

### 🛑 Unterbrechen (C-Taste / Stopp-Taste)

Stoppen Sie die Generierung der LLM-Antwort jederzeit und geben Sie einen Stoppbefehl zurück an LLM.

| Schnittstelle | So unterbrechen Sie |
|---|---|
| **CLI** | Drücken Sie während des LLM-Streamings die Taste „c“ – die aktuelle Reaktion stoppt und „Stop“ wird als Benutzernachricht gesendet, sodass der LLM entsprechend reagiert |
| **WEB-UI** | Klicken Sie auf die rote Schaltfläche **■ Stopp** (erscheint automatisch während der LLM-Verarbeitung) |
| **Desktop GUI** | Klicken Sie auf die rote Schaltfläche **■** (erscheint automatisch während der LLM-Verarbeitung). |

Die Unterbrechung funktioniert als „prompte Injektion“: Anstatt nur abzubrechen, wird „Stop“ als Benutzermeldung an den LLM zurückgegeben, sodass dieser die Unterbrechung ordnungsgemäß abschließen oder bestätigen kann.

**F11** beendet den Autopilot-Modus. **F12** stoppt nur die aktuelle LLM-Antwort (siehe [README_AUTO.md](https://github.com/awaku7/agentcli/blob/main/docs/README_AUTO.md)).

### 🕵️ Browser-Automatisierung & Web Inspector

Zwei komplementäre Playwright-basierte Tools:

- **browser_playwright**: Automatisieren Sie echte Browsersitzungen – navigieren, klicken, füllen Formulare bearbeiten, Daten extrahieren, mehrseitige Abläufe verarbeiten. Funktioniert kopflos oder kopfüber.
- **playwright_inspector**: Zeichnen Sie Browserübergänge auf, erfassen Sie DOM-Schnappschüsse und Screenshots bei jedem Schritt. Nützlich zum Debuggen von Webinteraktionen oder zum Überwachen von Seitenänderungen im Laufe der Zeit.

### 🔄 Dynamisches Laden von Tools

Mit „tool_catalog“ und „tool_load“ können Sie Tools zur Laufzeit erkennen und aktivieren.
Sie müssen nicht alles beim Start laden – aktivieren Sie nur das, was Sie brauchen, wenn Sie es brauchen.

### 🦀 Rust Native Tools

`uuid_gen` und „slugify“ ist aus Leistungsgründen in Rust (über PyO3) implementiert.
Sie laden direkt aus einer vorgefertigten „.pyd“ – **keine „Pip-Installation“ erforderlich**.

Externe Entwickler können auch Rust-basierte Tools liefern: Platzieren Sie eine „.pyd“ neben dem
Wrapper „.py“, verwenden Sie „load_rust_pyd()“ aus „uagent.tools.rust_helper“, und
Benutzer erhalten das Tool ohne zusätzliche Abhängigkeiten. Siehe
[TOOL_CREATOR_GUIDE.md](https://github.com/awaku7/agentcli/blob/main/TOOL_CREATOR_GUIDE.md).

### 🌐 i18n / L10n

日本語 / Englisch / 简体中文 /繁體中文 / 한국어 / Español / Français / Русский / und mehr.
Stellen Sie „UAGENT_LANG“ zum Umschalten ein. Siehe [ADD_LOCALE.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/ADD_LOCALE.md), um ein neues Gebietsschema hinzuzufügen.

Übersetzungen dieses README sind verfügbar in [docs/README.translations.md](https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md).

### 🔒 Verschlüsselte Umgebungsvariablen

Speichern Sie API Schlüssel und Geheimnisse in „.env.sec“ – einer verschlüsselten „.env“-Datei.
Verwalten mit `uag_envsec`.

## Konfiguration und Details

- **Umgebungsvariablen**: [docs/ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/docs/ENVIRONMENT.md)
- **Setup-Assistent**: `python -m uagent.setup_cli`
- **Verschlüsselte Umgebung**: `uag_envsec` — „.env“ als „.env.sec“ verschlüsseln
- **Antworten API**: Legen Sie „UAGENT_RESPONSES=1“ für den Antwortmodus API fest (OpenAI/Azure/Bedrock/OpenRouter/Ollama/Alibaba/LM Studio/Sakana AI). Automatisch aktiviert für Sakana AI (Fugu).
- **Entwicklerdokumente**: [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)
- **Toolablauf**: [TOOL_FLOW.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/TOOL_FLOW.md) – wie Werkzeuge an LLMs gesendet werden (Genre-Maske, Werkzeugkatalog, GPT-5.4+ native Werkzeugsuche)
- **Kleine LLM-Tipps**: [SLM_TIPS.md](https://github.com/awaku7/agentcli/blob/main/docs/SLM_TIPS.md)

## Projektphilosophie

uag strebt danach, **Ihre KI, auf Ihrem Computer, zu Ihren Bedingungen zu sein.**

- Keine SaaS-Abhängigkeit – läuft lokal
- Keine Anbieterbindung – jederzeit wechseln
- Keine UI-Bindung – CLI / GUI / Web / A2A
- Keine Funktionsbindung – erweitern Sie mit Tools und Fähigkeiten

Ein kostenloses KI-Agent-Erlebnis, frei von Anbieterbindung.

### ✨ Erstellen Sie Ihre eigenen Tools

Das Schreiben eines neuen Tools für uag ist unkompliziert – erstellen Sie eine einzelne „.py“-Datei mit „TOOL_SPEC“ und „run_tool()“, legen Sie sie in „UAGENT_EXTERNAL_TOOLS_DIR“ ab und
es ist sofort verfügbar. Für Rust-Entwickler: Versenden Sie eine vorgefertigte „.pyd“-Datei ohne zusätzliche Abhängigkeiten für Benutzer.

Siehe [TOOL_CREATOR_GUIDE.md](https://github.com/awaku7/agentcli/blob/main/TOOL_CREATOR_GUIDE.md)
für die Schritt-für-Schritt-Anleitung.

## Mitwirken

Beiträge sind willkommen! Fehlerberichte, Funktionsvorschläge, Dokumentationsverbesserungen, Übersetzungen und Pull-Anfragen – alles willkommen.

- **Probleme**: Öffnen Sie ein GitHub-Problem für Fehler oder Funktionsanfragen.
- **Pull-Anfragen**: Forken Sie das Repo, nehmen Sie Ihre Änderungen vor und reichen Sie eine PR ein. Siehe [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md) für Entwicklungseinstellungen und Richtlinien.
- **Übersetzungen**: README-Übersetzungen und Gebietsschema-Ergänzungen sind willkommen. Siehe [ADD_LOCALE.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/ADD_LOCALE.md).
- **Tools & Skills**: Neue Tool-Plugins und Agent Skills können über den Marktplatz beigesteuert werden.

### Entwicklungsprüfungen (vor PR)

Installieren Sie zuerst die reinen Testabhängigkeiten. Sie werden aus der Laufzeitabhängigkeitsliste herausgehalten:

```bash
python -m pip install -e ".[test]"
python -m pip install black ruff
```

Führen Sie dieselben Prüfungen aus, die von GitHub-Aktionen verwendet werden, bevor Sie Folgendes drücken:

```bash
python -m ruff check src Tests
python -m black --check src Tests
python scripts/tool_json_i18n_batch.py Status
python -m pytest -q .
```

Führen Sie für eine schnellere lokale Iteration nur die betroffenen Tests aus:

```bash
pytest -q tests/<affected_area>
```

Zusätzliche Prüfungen, falls relevant:

```bash
python -m py_compile src/uagent/
mypy src/uagent
```

Nach Änderungen am Gebietsschema (`.po`): `python scripts/compile_locales.py` und „python scripts/po_qc_summary.py“.

Runtime-Richtlinie (Details in [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md) §6.1): Helfer erhöhen anstelle von „sys.exit“; Der Tool-Host wandelt „SystemExit“/„Exception“ des Tools in Fehlerzeichenfolgen um, sodass ein einzelnes Tool den Prozess nicht beenden kann. Start-Fail-Fast-Exits bleiben beabsichtigt.

## Architektur und Betriebsinvarianten

Siehe [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) für die dauerhaften Verträge, die den A2A-Lebenszyklus, I18N-Kontexte, optionale Abhängigkeitsinstallation, Toolsicherheit, Anbieterfunktionen, OAuth-Vertrauensgrenzen, strukturierte Ereignisse und Akzeptanzüberprüfung abdecken.

## Enterprise Policy Engine

Richtlinien auf Organisationsebene für Tools, Anbieter, Anmeldeinformationen, MCP-Server, Netzwerke, Fähigkeiten und Plugins werden unterstützt. Legen Sie „UAGENT_POLICY_FILE“ auf eine JSON/YAML-Richtliniendatei fest; siehe [docs/ENTERPRISE_POLICY.md](docs/ENTERPRISE_POLICY.md) für Konfigurationsbeispiele, Rollen, Bestätigung und Zulassungslisten.

### Runtime Wiederherstellung und Orchestrierung

Siehe [RESTART_RECOVERY.md](docs/RESTART_RECOVERY.md) / [DAG_SCHEDULER.md](docs/DAG_SCHEDULER.md) / [MULTI_AGENT_RUNTIME.md](docs/MULTI_AGENT_RUNTIME.md) für dauerhafte Wiederherstellung, abhängigkeitsbewusste Ausführung, Multi-Agent-Orchestrierung und Remote-A2A-Nutzung.

Siehe [DISTRIBUTED_COORDINATION.md](docs/DISTRIBUTED_COORDINATION.md) für die Leader-Lease-Koordination zur gemeinsamen Laufzeit.
