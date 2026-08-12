<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="720">
</p>

<h1 align="center">uag – Universelles KI-Gateway</h1>

<p align="center">
  <b>U</b>niversal <b>A</b>I <b>G</b>ateway — Deine Umgebung, deine Freiheit.
</p>

<p align="center">
  Dateioperationen / Websuche / Bildgenerierung und -analyse / PDF & Excel Extraktion / IoT Steuerung / MCP Integration<br>
  24 providers / 3 UIs / Parallele Toolausführung / Agent Skills Marktplatz
</p>

<p align="center">
  <a href="https://github.com/awaku7/agentcli">GitHub</a>
  ·
  <a href="https://pypi.org/project/uag/">PyPI</a>
  ·
  <a href="README.translations.md">Read this in your language</a>
</p>

______________________________________________________________________

## Warum uag?

**Befreien Sie sich von der Anbieterbindung.** Die meisten KI-Assistenten binden Sie an einen bestimmten Anbieter oder Cloud-Dienst. uag ist anders.

- **Läuft lokal** auf Ihrem Computer. Ihre Daten bleiben bei Ihnen (mit Ausnahme von API-Aufrufen, die Sie tätigen).
- **Anbieterfreiheit**: OpenAI, Claude, Gemini, DeepSeek, Ollama, Azure, Bedrock, HuggingFace... 21+ Anbieter, alle über eine einzige Schnittstelle zugänglich. Wechseln Sie zwischen ihnen, indem Sie Umgebungsvariablen neu konfigurieren – keine Neuinstallation, keine Migration.
- **222 Tools**: Datei-E/A, Websuche, Bildgenerierung, Gmail, BLE-Gerätescan, MCP-Serverintegration – **130 sind parallelsicher** (bis zu 8 werden gleichzeitig über Thread-Pool ausgeführt, konfigurierbar über „UAGENT_PARALLEL_WORKERS“). Wenn das LLM mehrere Tool-Aufrufe gleichzeitig auslöst, parallelisiert uag diese automatisch.
- **3 UIs + A2A**: CLI, GUI, Web und Agent-to-Agent-Protokoll. Gleiche Engine, beliebige Schnittstelle.
- **Agentenfähigkeiten**: Installieren Sie von der Community entwickelte Fähigkeiten vom Marktplatz. Verlängern Sie uag endlos.

uag ist **Ihr KI-Assistent zu Ihren Bedingungen**. Keine Bindung an einen Anbieter, keine Bindung an eine Schnittstelle, keine Bindung an eine Plattform.

## Schnellstart

```bash
pip install uag
uag
```

Beim ersten Start führt Sie der Einrichtungsassistent durch die Anbieterkonfiguration.
Alle Umgebungsvariablen finden Sie unter [docs/ENVIRONMENT.md](ENVIRONMENT.md).

## Merkmale

### 🧠 Multi-Provider-Architektur

OpenAI / PFN (PLaMo) / Azure / Bedrock / OpenRouter / Ollama / Gemini / Vertex AI / Claude / Grok / NVIDIA / Novita / DeepSeek / Z.AI (Zhipu AI) / HuggingFace / Alibaba Cloud (Qwen) / KIMI (Moonshot AI) / Xiaomi MiMo / LM Studio / MiniMax / Sakana AI (Fugu) / SAKURA AI Engine / Together AI / Vercel AI Gateway

Alle Anbieter nutzen das gleiche Toolset und die gleiche Schnittstelle. Wechseln Sie durch die Einstellung „UAGENT_PROVIDER“ – keine Codeänderungen, keine separaten Installationen.

### ⚡ Parallele Werkzeugausführung

Wenn das LLM mehrere Tools gleichzeitig anfordert, werden diese von uag automatisch parallelisiert.
130 Tools sind mit „x_parallel_safe“ gekennzeichnet und werden gleichzeitig über einen „ThreadPoolExecutor“ ausgeführt (8 Threads standardmäßig; setzen Sie „UAGENT_PARALLEL_WORKERS“ auf Änderung).

**Beispiel**: Fragen Sie „Überprüfen Sie das Wetter in den nordischen Hauptstädten“ → LLM löst „search_web“ × 5 Länder aus → alle 5 Suchanfragen werden parallel ausgeführt → Ergebnisse werden in einem Stapel gesammelt.

Schreibgeschützte Tools (Dateisuche, Hash-Berechnung, Verzeichnisliste, Übersetzung, DB-Abfragen usw.) werden aggressiv parallelisiert.

### 🧩 Plugin-System (Claude Code-kompatibel)

uagent implementiert ein **Claude Code-kompatibles Plugin-System**. Plugins bündeln Fähigkeiten, Agenten, MCP-Server, Hooks und mehr in eigenständigen Verzeichnissen mit dem Manifest `.claude-plugin/plugin.json`.

**Unterstützte Komponenten**: Skills, Subagenten, MCP-Server, Hooks (12 Lebenszyklusereignisse), Slash-Befehle, Ausgabestile, userConfig, Abhängigkeiten, Kanäle, Marktplätze

**CLI commands**:

```
:plugin list                         # Installierte Plugins auflisten
:plugin install <source> [--scope]
:plugin install <name>@<marketplace>  # Vom Marktplatz installieren
:plugin remove <name>                # Deinstallieren
:plugin enable/disable <name>        # Umschalten
:plugin marketplace add/remove/list  # Marktplätze verwalten
:plugin init <name>                  # Neues Plugin-Gerüst erstellen
```

Einzelheiten finden Sie in der vollständigen Dokumentation [DEVELOP_PLUGIN.md](../src/uagent/docs/DEVELOP_PLUGIN.md).

### 🔄 Sitzungskontinuität

- **Anbieter während der Sitzung wechseln**: `UAGENT_PROVIDER` — der Gesprächsverlauf bleibt erhalten.
- **Vergangene Sitzungen erneut laden**: `:load <index>` — dort weitermachen, wo Sie aufgehört haben.

### 🛠 222 Werkzeuge

| Kategorie | Werkzeuge |
|---|---|
| **Dateioperationen** | lesen/schreiben/erstellen/löschen/suchen/grep/hash/zip, file_type, parse_eml (.eml-Dateien) |
| **Web** | fetch_url, search_web, Screenshot, browser_playwright |
| **Medien** | generieren_image, analysieren_image, img2img, audio_speech, audio_transcribe |
| **Dokumente** | PDF/PPTX/DOCX/RTF/ODT-Extraktion, strukturierte Excel-Extraktion |
| **Prognose** | Zeitreihenprognose mit 9 Modellen (AutoARIMA, Prophet, LightGBM, CatBoost, TimesFM usw.), automatische Modellauswahl, Diagrammerstellung, i18n |
| **Kommunikation** | gmail_send, gmail_read, bluesky, discord_channel, teams_webhook, **pybitchat** (BLE Mesh) – siehe [COMMUNICATION.md](COMMUNICATION.md) und [BITCHAT.md](BITCHAT.md)|
| **IoT** | BACnet、Modbus TCP、OPC UA、SwitchBot（Cloud + BLE）、ECHONET Lite、Matter、UPnP、reverse_geocode |
| **Cloud-APIs** | `aws_api`, `gcp_api`, `azure_api` — AWS, Google Cloud, and Azure API operations; write operations require explicit confirmation |
| **Entwicklungstools** | git_ops, python_compile, lint_format, run_tests, db_query, **29 Quellcode-Navigatoren (IDX-Familie)** |
| **MCP** | Mit externen MCP-Servern verbinden, Tools auflisten, ausführen — [OAuth / Proxy guide](MCP_OAUTH_PROXY_GUIDE.md) |
| **A2A** | Agent-zu-Agent-Kommunikation (mit anderen UAG-Instanzen oder A2A-kompatiblen Servern) |
| **System** | Umgebungsvariablen, Systemspezifikationen, Uhrzeit, Datumsberechnung, uuid_gen, slugify, quantities ||
| **Quellennavigation** | **29 idx-Tools** für Python, PHP, TypeScript, Java, C#, Dart, C/C++, Rust, Go, Swift, Kotlin, COBOL, VBA, LotusScript, Makefile – erhalten Sie einen Funktions-/Klassenindex oder eine spezifische Definition, ohne die gesamte Datei zu lesen |

#### Repository-Überprüfung und -Abdeckung

- „git_review“: Git-Änderungen, riskante Dateien, Testkandidaten und geheime Ergebnisse zusammenfassen, ohne geheime Werte preiszugeben.
- „security_scan“: Repository-Dateien nach wahrscheinlichen Geheimnissen und riskanten Konfigurationsdateien durchsuchen.
- „coverage_report“: Abdeckung für Python, TypeScript/JavaScript, Rust, Go, Java/Kotlin, .NET, C/C++ ausführen und normalisieren, Ruby, PHP, Swift und Dart/Flutter.
 – Fehlende Abdeckungsabhängigkeiten können automatisch installiert werden, wenn die Ausführung angefordert wird; „dry_run“ installiert niemals Pakete.

Siehe [Repository-Analysetools](REPOSITORY_TOOLS.md) für Parameter, Ausgabe und Sicherheitsdetails.

### 🖥 4 Schnittstellen + VS-Code-Erweiterung

| Modus | Befehl | Zweck |
|---|---|---|
| **CLI** | `uag` | Schnelle terminalbasierte Bedienung |
| **GUI** | `uagg` | Desktop-Benutzeroberfläche über tkinter |
| **Web** | `uagw` | Browserbasierter Zugriff |
| **A2A-Server** | `uaga` | Agent2Agent-Protokoll für Multiagentenkommunikation |
| **VS-Code** | — | [Erweiterung](VSCODE.md) mit Chat-Panel, Erläuterung, Umgestaltung, Fehler beheben und Tools-Strukturansicht |

Weitere Informationen zur VS Code-Erweiterung – Installation, Befehle, Tastenkombinationen und Konfiguration – finden Sie unter [VSCODE.md](VSCODE.md).

### 🏠 IoT-Gerätesteuerung

Siehe [IOT_USECASE.md](IOT_USECASE.md)

### 🎯 Marktplatz für Agentenkompetenzen

`:skills mp_search`, um [SkillsMP](https://skillsmp.com) und [ClawHub](https://clawhub.ai) nach Community-Fähigkeiten zu durchsuchen.
Installieren und erweitern Sie die Funktionen von uag im Handumdrehen.

### 🤖 Autopilot (`:auto`)

uag kann **autonom über mehrere LLM-Runden hinweg ein Ziel verfolgen**. Perfekt für komplexe, mehrstufige Aufgaben, die eine iterative Verfeinerung erfordern.

- **So funktioniert es**: Jede Runde besteht aus einer Hauptabfrage (Schritt A), gefolgt von einem Gutachterurteil (Schritt B), das über „ABSCHLUSS oder WEITER?“ entscheidet.
- **Gleicher Anbieter, gleiche API**: Das Gutachterurteil verwendet den identischen Codepfad wie die Hauptabfrage – einschließlich Responses-API-Unterstützung.
- **Separater Richter-LLM** (optional): Legen Sie „UAGENT_AP_PROVIDER“ fest, um einen anderen Anbieter/ein anderes Modell für den Prüfer zu verwenden (z. B. ein günstigeres Modell für die Beurteilung verwenden).
- **Jederzeit beenden**: Drücken Sie die Taste „x“, um sofort anzuhalten, auch mitten in der Reaktion. Oder lassen Sie den Prüfer entscheiden, wann das Ziel erreicht ist.
- **Konfigurierbar**: „--max-rounds N“ zur Kontrolle des Budgets.

Die vollständige Dokumentation finden Sie unter [README_AUTO.md](README_AUTO.md).

### 🧩 Batch-Statusmanager

uag kann den Fortschritt über lang laufende Aufgaben mit mehreren Dateien verfolgen. Wenn das LLM Dutzende Dateien verarbeitet, speichert „batch_state“ die Liste der ausstehenden, abgeschlossenen und fehlgeschlagenen Dateien auf der Festplatte. Wenn die Sitzung endet oder eine Runde abläuft, wird der nächste Lauf an der Stelle fortgesetzt, an der er gestoppt wurde – es geht nichts verloren.

### 🛡 Mensch im Regelkreis

„human_ask“ lässt das LLM anhalten und um Ihre Bestätigung bitten, bevor es destruktive Operationen ausführt (Löschen von Dateien, Überschreiben, Shell-Befehle). Sie behalten die Kontrolle.

### 🛑 Unterbrechen (C-Taste / Stopp-Taste)

Stoppen Sie die LLM-Antwortgenerierung jederzeit und geben Sie einen Stoppbefehl zurück an das LLM.

| Schnittstelle | So unterbrechen Sie |
|---|---|
| **CLI** | Drücken Sie während des LLM-Streamings die Taste „c“ – die aktuelle Reaktion stoppt und „Stopp“ wird als Benutzernachricht gesendet, sodass das LLM entsprechend reagiert |
| **WEB-UI** | Klicken Sie auf die rote Schaltfläche **■ Stopp** (erscheint automatisch während der LLM-Verarbeitung) |
| **Desktop-GUI** | Klicken Sie auf die rote Schaltfläche **■** (erscheint automatisch während der LLM-Verarbeitung) |

Der Interrupt funktioniert als „Prompt-Injektion“: Anstatt nur abzubrechen, gibt er „Stopp“ als Benutzernachricht an den LLM zurück, sodass dieser die Unterbrechung ordnungsgemäß abschließen oder bestätigen kann.

Drücken Sie die Taste „x“, um den Autopilot-Modus zu verlassen (siehe [README_AUTO.md](README_AUTO.md)).

### 🕵️ Browser-Automatisierung und Web-Inspektor

Zwei komplementäre Playwright-basierte Tools:

- **browser_playwright**: Automatisieren Sie echte Browsersitzungen – navigieren, klicken, Formulare ausfüllen, Daten extrahieren, mehrseitige Abläufe verwalten. Funktioniert kopflos oder mit Kopf.
- **playwright_inspector**: Browserübergänge aufzeichnen, DOM-Snapshots und Screenshots bei jedem Schritt erfassen. Nützlich zum Debuggen von Webinteraktionen oder zum Überwachen von Seitenänderungen im Laufe der Zeit.

### 🔄 Dynamisches Laden von Werkzeugen

Mit „tool_catalog“ und „tool_load“ können Sie Tools zur Laufzeit erkennen und aktivieren.
Sie müssen beim Start nicht alles laden – aktivieren Sie nur das, was Sie brauchen, und zwar dann, wenn Sie es brauchen.

### 🦀 Rust Native Tools

`uuid_gen` und `slugify` sind für bessere Leistung in Rust (über PyO3) implementiert.

### 🌐 i18n / L10n

日本語 / Englisch / 简体中文 / 繁體中文 / 한국어 / Spanisch / Französisch / Russisch / und mehr.
Legen Sie „UAGENT_LANG“ fest, um zu wechseln. Siehe [ADD_LOCALE.md](../src/uagent/docs/DEVELOP_I18N.md), um ein neues Gebietsschema hinzuzufügen.

Übersetzungen dieser README-Datei sind unter [docs/README.translations.md](README.translations.md) verfügbar.

### 🔒 Verschlüsselte Umgebungsvariablen

Speichern Sie API-Schlüssel und Geheimnisse in „.env.sec“ – einer verschlüsselten „.env“-Datei.
Verwalten Sie mit „uag_envsec“.

## Konfiguration und Details

- **Umgebungsvariablen**: [docs/ENVIRONMENT.md](ENVIRONMENT.md)
- **Setup-Assistent**: `python -m uagent.setup_cli`
- **Verschlüsselte Env**: „uag_envsec“ – „.env“ als „.env.sec“ verschlüsseln
- **Antwort-API**: Legen Sie „UAGENT_RESPONSES=1“ für den Antwort-API-Modus fest (OpenAI/Azure/Bedrock/OpenRouter/Ollama/Alibaba/LM Studio/Sakana AI). Automatisch aktiviert für Sakana AI (Fugu).
- **Entwicklerdokumente**: [DEVELOP.md](../src/uagent/docs/DEVELOP.md)
- **Tool flow**: [TOOL_FLOW.md](../src/uagent/docs/TOOL_FLOW.md)
- **Kleine LLM-Tipps**: [SLM_TIPS.md](SLM_TIPS.md)

## Projektphilosophie

uag möchte **Ihre KI sein, auf Ihrer Maschine, zu Ihren Bedingungen.**

- Keine SaaS-Abhängigkeit – läuft lokal
- Keine Anbieterbindung – Wechsel jederzeit möglich
- Keine UI-Sperre – CLI / GUI / Web / A2A
- Keine Bindung an bestimmte Funktionen – erweitern Sie Ihre Möglichkeiten mit Tools und Fertigkeiten

Ein kostenloses KI-Agenten-Erlebnis, frei von Anbieterbindung.

### ✨ Erstellen Sie Ihre eigenen Werkzeuge

[de.md](TOOL_CREATOR_GUIDE.de.md)
Eine Schritt-für-Schritt-Anleitung finden Sie hier.

## Mitwirken

Beiträge sind willkommen! Fehlerberichte, Funktionsvorschläge, Dokumentationsverbesserungen, Übersetzungen und Pull-Requests – alles willkommen.

- **Issues**: Öffnen Sie ein GitHub-Problem für Fehler oder Funktionsanfragen.
- **Pull Requests**: Forken Sie das Repository, nehmen Sie Ihre Änderungen vor und senden Sie einen PR. Hinweise zur Entwicklungsumgebung und Richtlinien finden Sie unter [DEVELOP.md](../src/uagent/docs/DEVELOP.md).

Realtime Stimme und AEC3

## Der Sprachmodus Realtime unterstützt Vollduplex-Mikrofon- und Lautsprecher-Ein-/Ausgabe. Wenn das AEC3-Backend fehlt, installiert uag automatisch pywebrtc-audio.

**Echtzeitanbieter**: OpenAI Realtime, Azure OpenAI GPT Realtime, Google Gemini Live, xAI Grok Voice und Amazon Bedrock Nova Sonic. Das bidirektionale Streaming-SDK von Bedrock wird nur dann automatisch installiert, wenn Bedrock ausgewählt ist.

```bat
python scheck.py realtime
```

AEC3 verwendet das tatsächliche Mikrofonsignal (nah) und den tatsächlich an den Lautsprecher gesendeten Ton (fern). Aktivieren Sie die Diagnose nur, wenn Sie Audioprobleme untersuchen.

```bat
set UAGENT_REALTIME_AUDIO_DEBUG=1
python scheck.py realtime
```

### OpenAI Realtime Function Calling

OpenAI Realtime unterstützt eine sicherheitsbegrenzte Function Calling-Integration. Der aktuelle Adapter macht die schreibgeschützte Funktion get_current_time automatisch verfügbar. Zerstörerische Tools und Gerätekontrollen erfordern eine explizite Zulassungsliste und einen Bestätigungsablauf. Grok Realtime verwendet einen separaten Adapter und verwendet nicht diesen OpenAI-spezifischen Function Calling-Pfad.
