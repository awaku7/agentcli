<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="680">
</p>

<h1 align="center">uag</h1>

<p align="center">
  <strong>Universal AI Gateway</strong><br>
  Ein lokaler Agent. Jedes Modell. Jedes Tool. Deine Umgebung, deine Regeln.
</p>

<p align="center">
  <a href="https://github.com/awaku7/agentcli/actions"><img src="https://img.shields.io/github/actions/workflow/status/awaku7/agentcli/ci.yml?style=flat-square&label=CI" alt="CI status"></a>
  <a href="https://pypi.org/project/uag/"><img src="https://img.shields.io/pypi/v/uag?style=flat-square" alt="PyPI version"></a>
  <a href="https://pypi.org/project/uag/"><img src="https://img.shields.io/pypi/pyversions/uag?style=flat-square" alt="Python versions"></a>
  <a href="https://github.com/awaku7/agentcli/blob/main/LICENSE"><img src="https://img.shields.io/github/license/awaku7/agentcli?style=flat-square" alt="License"></a>
  <a href="https://pepy.tech/projects/uag"><img src="https://static.pepy.tech/personalized-badge/uag?period=total&units=INTERNATIONAL_SYSTEM&left_color=grey&right_color=green&left_text=downloads" alt="PyPI Downloads"></a>
</p>

<p align="center">
  <a href="https://github.com/awaku7/agentcli">GitHub</a> ·
  <a href="https://pypi.org/project/uag/">PyPI</a> ·
  <a href="https://github.com/awaku7/agentcli/discussions">Diskussionen</a> ·
  <a href="https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md">Übersetzungen</a>
</p>

______________________________________________________________________

**Warum uag?**

uag ist ein lokal ausgerichteter KI-Agent, der dein bevorzugtes Modell mit den Tools verbindet, die du tatsächlich nutzt.
Er bietet dir eine einheitliche, erweiterbare Laufzeit für Dateien, Browser, Codebasen, Kommunikation, Cloud-APIs,
IoT-Geräte, MCP-Server und Multi-Agenten-Workflows.

- **Freiheit bei den Anbietern** — OpenAI, Anthropic, Gemini, Azure, Bedrock, Ollama, llama.cpp, Grok, DeepSeek und weitere.
- **Lokale Ausführung** — die Laufzeit deines Agents und die Tool-Ausführung bleiben auf deinem Rechner; nur die von dir ausgewählten API-Aufrufe verlassen ihn.
- **Eine Tool-Schicht** — dieselben Tools funktionieren über CLI, Desktop-GUI, Web-UI, VS Code und A2A.
- **Parallelität als Grundprinzip** — unabhängige schreibgeschützte Vorgänge können gleichzeitig ausgeführt werden.
- **Erweiterbar** — füge Tools, Plugins, Agent Skills, MCP-Server und Rust-basierte Tools hinzu, ohne den Kern zu ändern.
- **Sicherheitsbewusst** — destruktive Aktionen, Zugangsdaten, Gerätesteuerungen und Netzwerkschreibvorgänge unterstützen ausdrückliche Bestätigungen und Richtliniensteuerung.

> **Kurz gesagt:** uag ist die Steuerungsebene zwischen deinen KI-Modellen und deiner realen Umgebung.

> **🧠 Kontextbezogene Tool-Ergebnisse** — Umfangreiche Tool-Ergebnisse werden nach Möglichkeit aus dem aktiven Modellkontext herausgehalten. uag speichert sie als Artefakte und übergibt dem Modell stattdessen eine begrenzte Vorschau mit einer stabilen Artifact-Referenz. Dies kann die Anzahl der für nachfolgende Runden erforderlichen Eingabetoken erheblich reduzieren, wenn ein Tool ein umfangreiches Ergebnis liefert.
> [Ausführlicher Leitfaden zur Kontextkomprimierung](CONTEXT_COMPRESSION.de.md)

## Schnellstart

**Python 3.11+**

```bash
python -m pip install --upgrade uag
uag
```

Beim ersten Start wird der Einrichtungsassistent geöffnet. Er hilft bei der Konfiguration eines Anbieters und speichert die ausgewählten Einstellungen
in deiner lokalen Umgebung.

Für die gängigen Funktionsgruppen:

```bash
python -m pip install "uag[core,providers,tools]"
```

> Plattformintegrationen sind optional. Installiere nur, was dein Betriebssystem benötigt; siehe

```text
> What files changed in this repository?
> Search the web for today's AI news and summarize the top five stories.
> :help
```

[Quickstart](QUICKSTART.md) · [Environment](ENVIRONMENT.md)

## Schnittstellen

| Schnittstelle | Befehl | Am besten geeignet für |
|---|---|---|
| **CLI** | `uag` | Schnelles Arbeiten mit Tastaturfokus |
| **Desktop-GUI** | `uagg` | Eine native Desktop-Erfahrung |
| **Web-UI** | `uagw` | Browserbasierten Zugriff |
| **A2A-Server** | `uaga` | Agent-zu-Agent-Kommunikation |
| **VS Code** | Extension | Erklären, Refaktorieren, Beheben und Durchsuchen von Tools im Editor |

Alle Schnittstellen verwenden dieselbe Anbieterkonfiguration, Tool-Registry, Sicherheitsregeln und Sitzungsdaten.

~~~bash
# Desktop GUI
python -m pip install "uag[platform]"

# Web UI
python -m pip install "uag[web]" fastapi uvicorn
~~~

[Interface options](USAGE.md) · [Environment](ENVIRONMENT.md)

## Was du bauen kannst

Anbieteradapter decken gehostete und lokale Laufzeiten ab, darunter:

**OpenAI · Anthropic · Gemini · Vertex AI · Azure OpenAI · Amazon Bedrock · Grok · DeepSeek · OpenRouter · Ollama · llama.cpp · LM Studio**

- Dateien lesen, erstellen, bearbeiten, durchsuchen, hashen, archivieren und prüfen
- Git-Änderungen prüfen, nach Geheimnissen suchen, Tests ausführen, linten, kompilieren und Coverage messen
- Große Python-, TypeScript-, JavaScript-, Go-, Rust-, C/C++-, Java-, C#-, COBOL-, VBA- und andere Codebasen durchsuchen
- Browser mit Playwright automatisieren, einschließlich mehrseitiger Workflows und Downloads

- **MCP** — externe Tool-Server verbinden, einschließlich OAuth-fähiger Dienste
- **A2A** — mit anderen Agents und kompatiblen Servern koordinieren
- **Cloud** — AWS-, Google-Cloud- und Azure-API-Zugriff mit Bestätigung für Schreibvorgänge
- **Kommunikation** — Gmail, Bluesky, Discord, Microsoft Teams und pybitchat
- **IoT** — SwitchBot, ECHONET Lite, Matter, BACnet, Modbus TCP, OPC UA und UPnP
- **Medien** — Bildgenerierung/-bearbeitung, Audiotranskription/-sprache, Kameraaufnahme und QR-Codes
- **Dokumente** — PDF, PowerPoint, Word, Excel, CSV, JSON, YAML, SQL und Log-Analyse

- **SwitchBot** — Cloud- und BLE-Erkennung, Status, Steuerung, Batch-Verarbeitung und Abonnements
- **ECHONET Lite** — japanische Haushaltsgeräte erkennen und steuern, einschließlich INF-Benachrichtigungen
- **Matter** — Endpunkte, Cluster, Attribute, Statusverlauf, Abonnements und Steuerung
- **BACnet / Modbus TCP / OPC UA** — Lesen, Schreiben, Durchsuchen und Überwachen in Industrie- und Gebäudeautomation
- **UPnP** — Geräteerkennung, WAN-Status und Verwaltung von Router-Portzuordnungen

### Wo uag eingesetzt wird

uag liegt auf der einen Seite zwischen Menschen und Schnittstellen und auf der anderen Seite zwischen Modellen, Tools und realen Systemen.
Es koordiniert die Unterhaltung, wählt Fähigkeiten aus, wendet Sicherheitsregeln an und hält den Workflow fortsetzbar.

~~~mermaid
flowchart LR
    UI["CLI · Desktop · Web · VS Code · A2A"] --> UAG["UAG agent runtime"]
    UAG --> MODELS["Hosted & local models"]
    UAG --> TOOLS["Tools & extensions"]
    UAG --> STATE["Sessions & context"]
    TOOLS --> SYSTEMS["Files · Code · Web · MCP · Cloud · IoT"]
    POLICY["Confirmation · Credentials · Policy"] -.-> UAG
~~~

### Plugins, Agent Skills und Marktplätze

Verwandle uag in einen spezialisierten Agenten, ohne den Kern abzuspalten:

- **Mit Claude Code kompatible Plugins** aus einem Verzeichnis, ZIP, Git-Repository, einer HTTP-Quelle oder einem Marktplatz installieren
- Skills, Sub-Agents, MCP-Server, Hooks, Slash-Befehle, Ausgabestile, Abhängigkeiten und Channels bündeln
- Community-Funktionen von [SkillsMP](https://skillsmp.com) und [ClawHub](https://clawhub.ai) durchsuchen
- Private Organisations-Skills und -Tools lokal über `UAGENT_EXTERNAL_TOOLS_DIR` hinzufügen

```text
:skills mp_search browser automation
:plugin list
:plugin install <source>
:plugin marketplace list
```

Siehe den [Leitfaden zur Plugin-Entwicklung](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP_PLUGIN.md).

- **200+ Tools** für Dateien, Web, Medien, Dokumente, Code, Cloud, Kommunikation und IoT
- **Dynamische Erkennung und Aktivierung** — nutze `tool_catalog`, um Fähigkeiten zu finden, und `tool_load`, um sie nur bei Bedarf zu aktivieren
- **Codeintelligenz** — `code_map`, sprachspezifische `idx`-Navigatoren, Git-Review, Testausführung, Linting, Kompilierung und Coverage
- **Mit Claude Code kompatible Plugins** mit Skills, Agents, MCP-Servern, Hooks, Befehlen und Marktplätzen
- **Agent Skills** von SkillsMP und ClawHub
- **Benutzerdefinierte Python-Tools** mit `TOOL_SPEC` und `run_tool()`
- **Rust-basierte Tools** für schlanke native Erweiterungen

[Tool Creator Guide](../TOOL_CREATOR_GUIDE.md) · [MCP OAuth / Proxy Guide](MCP_OAUTH_PROXY_GUIDE.md)

## Für reale Arbeitsabläufe entwickelt

### 🧠 Kontextbezogene Tool-Ergebnisse

Umfangreiche Tool-Ergebnisse werden nach Möglichkeit aus dem aktiven Modellkontext herausgehalten. uag speichert sie als Artefakte und übergibt dem Modell stattdessen eine begrenzte Vorschau mit einer stabilen Artifact-Referenz. Dies kann die Anzahl der für nachfolgende Runden erforderlichen Eingabetoken erheblich reduzieren, wenn ein Tool ein umfangreiches Ergebnis liefert.

Setze frühere Unterhaltungen mit `:load <index>` fort. Tool-Ergebnisse können zwischengespeichert und Anbieter geändert werden,
ohne die Anwendung neu aufzubauen.

[Context compression](CONTEXT_COMPRESSION.de.md) · [Memory](MEMORY.md) · [Session portability](SESSION_PORTABILITY.md)

### Autopilot

Verwende `:auto` für mehrstufige Aufgaben mit einem optionalen Prüfmodell. Lege mit `--max-rounds N` ein Rundenlimit fest.
Drücke **F12**, um den Autopiloten zu stoppen, oder **F12**, um die aktuelle Antwort zu stoppen.

Unabhängige schreibgeschützte Vorgänge werden, sofern sicher, gleichzeitig ausgeführt. Websuchen, Dateiprüfung,
Repository-Analyse und ähnliche Aufgaben können mit einem konfigurierbaren Worker-Pool
(`UAGENT_PARALLEL_WORKERS`) parallel abgeschlossen werden. Schreibvorgänge bleiben serialisiert oder erfordern eine Bestätigung.

Sitzungskontinuität, Caching von Tool-Ergebnissen, Batch-Status, Wiederherstellung nach Neustarts, DAG-Planung und
Multi-Agenten-Orchestrierung machen komplexe Aufgaben fortsetzbar statt einmalig.

[Auto-pilot](README_AUTO.md) · [Timers](SET_TIMER.md) · [Multi-agent runtime](MULTI_AGENT_RUNTIME.md)

### 🌍 Privat, mehrsprachig und richtlinienbewusst

`human_ask` hält vor sensiblen Aktionen an. Dateilöschungen, Überschreibungen, Shell-Befehle, Gerätesteuerungen,
Zugangsdatenoperationen und Netzwerkschreibvorgänge können durch Bestätigungs- und Richtlinienregeln gesteuert werden.

Verwende den Zugangsdaten-Speicher, statt langlebige Geheimnisse in Prompts zu platzieren:

Die Web-Oberfläche beinhaltet die OIDC-Anmeldung mittels Authorization Code + PKCE, verifizierten ID-Tokens, serverseitigen Sitzungen und Zugriffssteuerungen für Projekte/Räume. Verifizierte Microsoft Entra ID-Gruppenansprüche können bei Konfiguration Richtlinien für den zugrundeliegenden Verzeichniszugriff speisen. Windows Active Directory-, OAuth- und trusted-proxy-Bereitstellungen können über explizit verifizierte Identitätsadapter integriert werden; Windows AD benötigt einen bereitstellungsspezifischen Kerberos/Negotiate-Verifizierer und ist standardmäßig nicht aktiviert.

uag umfasst optionales, anbieterneutrales OpenTelemetry Tracing und Metriken für Agent, LLM, Tool, Context, Memory und Abrufvorgänge. Die Beobachtbarkeit ist standardmäßig deaktiviert.

Local-first bedeutet nicht, dass UAG standardmäßig vollständig offline oder isoliert arbeitet. Aufrufe externer Modelle und verbundener Dienste hängen von der Konfiguration ab.

- [Enterprise policies](ENTERPRISE_POLICY.md)
- [MXC sandbox](SANDBOX_MXC.md)
- [Remote Web / A2A](REMOTE_MXC_DEFAULT.md)
- [Web identity](WEB_IDENTITY_MEMORY.md)
- [OpenTelemetry](UAG_OPENTELEMETRY_DESIGN.md)

### 🌍 Mehrsprachige Übersetzung

- `translate_text` unterstützt Google Translate und den offiziellen DeepL-Python-Client über `provider=auto`, `provider=deepl` oder `provider=google`.
- Tool-Definitionen sind in 37 Sprachversionen plus Englisch (insgesamt 38) verfügbar, wobei Platzhalter und technische Bezeichner beibehalten werden.

Vollduplex-Sprache ist über OpenAI Realtime, Azure OpenAI, xAI Grok Voice, Gemini Live
und Bedrock Nova Sonic verfügbar, mit optionaler AEC3-Echounterdrückung und sicherheitsbeschränktem Echtzeit-Funktionsaufruf.

[Translations](README.translations.md) · [IoT](IOT_USECASE.md) · [Communication](COMMUNICATION.md)

## Dokumentation

| Thema | Dokumentation |
|---|---|
| Umgebungsvariablen | [docs/ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/docs/ENVIRONMENT.md) |
| Architektur und Invarianten | [docs/ARCHITECTURE.md](https://github.com/awaku7/agentcli/blob/main/docs/ARCHITECTURE.md) |
| Computer Use | [docs/COMPUTER_USE_IMPLEMENTATION.md](https://github.com/awaku7/agentcli/blob/main/docs/COMPUTER_USE_IMPLEMENTATION.md) |
| Repository-Tools | [docs/REPOSITORY_TOOLS.md](https://github.com/awaku7/agentcli/blob/main/docs/REPOSITORY_TOOLS.md) |
| IoT-Anwendungsfälle | [docs/IOT_USECASE.md](https://github.com/awaku7/agentcli/blob/main/docs/IOT_USECASE.md) |
| Kommunikationstools | [docs/COMMUNICATION.md](https://github.com/awaku7/agentcli/blob/main/docs/COMMUNICATION.md) |
| Autopilot | [docs/README_AUTO.md](https://github.com/awaku7/agentcli/blob/main/docs/README_AUTO.md) |
| MCP OAuth / Proxy | [docs/MCP_OAUTH_PROXY_GUIDE.md](https://github.com/awaku7/agentcli/blob/main/docs/MCP_OAUTH_PROXY_GUIDE.md) |
| VS-Code-Erweiterung | [docs/VSCODE.md](https://github.com/awaku7/agentcli/blob/main/docs/VSCODE.md) |
| Entwicklerleitfaden | [src/uagent/docs/DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md) |
| Tool-Ablauf | [src/uagent/docs/TOOL_FLOW.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/TOOL_FLOW.md) |

[Quickstart](QUICKSTART.md) · [Architecture](ARCHITECTURE.md) · [Context management](UAG_CONTEXT_MANAGEMENT_DESIGN.md)

## Entwicklung und Mitwirkung

```bash
git clone https://github.com/awaku7/agentcli.git
cd agentcli
python -m pip install -e ".[core,providers,test]"
```

Führe die Prüfungen vor einem PR aus:

```bash
python -m ruff check src tests
python -m black --check src tests
python -m pytest -q .
```

Den vollständigen Entwicklungs-Workflow findest du unter [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md).

Fehlerberichte, Funktionsideen, Verbesserungen der Dokumentation, Übersetzungen, Tools, Skills und Pull Requests sind willkommen.
Bitte eröffne vor größeren Änderungen ein Issue oder eine Diskussion. Lies den [Entwicklerleitfaden](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)
und führe die obigen Prüfungen aus, bevor du einen Pull Request einreichst.

## Lizenz

Lizenziert unter der [Apache License 2.0](https://github.com/awaku7/agentcli/blob/main/LICENSE).
