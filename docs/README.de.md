<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="UAG — Universal AI Gateway" width="620">
</p>
<h1 align="center">UAG</h1>
<p align="center"><strong>Universal AI Gateway</strong><br>Ihre KI-Modelle. Ihre Werkzeuge. Ihre Umgebung.</p>

<p align="center">
  <a href="https://github.com/awaku7/agentcli/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/awaku7/agentcli/ci.yml?style=flat-square&label=CI" alt="CI"></a>
  <a href="https://pypi.org/project/uag/"><img src="https://img.shields.io/pypi/v/uag?style=flat-square" alt="PyPI"></a>
  <a href="https://pypi.org/project/uag/"><img src="https://img.shields.io/pypi/pyversions/uag?style=flat-square" alt="Python versions"></a>
  <a href="../LICENSE"><img src="https://img.shields.io/github/license/awaku7/agentcli?style=flat-square" alt="License"></a>
  <a href="https://pepy.tech/projects/uag"><img src="https://static.pepy.tech/personalized-badge/uag?period=total&units=INTERNATIONAL_SYSTEM&left_color=grey&right_color=green&left_text=downloads" alt="Downloads"></a>
</p>
<p align="center"><a href="../README.md">English</a> · <a href="README.translations.md">Weitere Sprachen</a></p>

---

**UAG ist eine quelloffene, lokal ausgerichtete Laufzeitumgebung für KI-Agenten.** Sie verbindet das Sprachmodell Ihrer Wahl mit den Werkzeugen und Systemen, die Sie verwenden. Code, Dateien, Browser, Dienste und Geräte lassen sich über eine einheitliche Oberfläche bedienen, ohne einen bestimmten Modellanbieter vorauszusetzen.

| **Eigenes Modell wählen** | **Werkzeuge verbinden** | **Kontrolle behalten** |
| :--- | :--- | :--- |
| Cloud- und lokale Modelle wie OpenAI, Claude, Gemini, Grok, Bedrock und Ollama | Dateien, Code, Web, MCP, Agent Skills, Plugins, Cloud-Dienste und IoT | Lokale Ausführung, menschliche Bestätigung, sichere Zugangsdatenablage und konfigurierbare Richtlinien |

> UAG ist **die Ausführungsschicht für Agenten, kein Modellanbieter**. Aufrufe externer Modelle und verbundener Dienste hängen von Ihrer Konfiguration ab. „Local-first“ bedeutet nicht, dass UAG standardmäßig vollständig offline oder isoliert arbeitet.

## Schnellstart
<!-- README-SYNC:quick-start -->

Sie benötigen **Python 3.11 oder neuer**. Installieren Sie UAG über [PyPI](https://pypi.org/project/uag/) und starten Sie die interaktive Kommandozeile:

~~~bash
python -m pip install --upgrade uag
uag
~~~

Beim ersten Start hilft der Einrichtungsassistent bei der Auswahl des Modellanbieters und der Einrichtung der Zugangsdaten. Alternativ können Sie Umgebungsvariablen oder den Zugangsdaten-Speicher nutzen. Für einen größeren Satz von Provider- und Werkzeug-Abhängigkeiten installieren Sie das folgende Extra:

~~~bash
python -m pip install "uag[core,providers,tools]"
~~~

Anschließend können Sie beispielsweise fragen:

~~~text
> Welche Änderungen gibt es in diesem Git-Repository? Fasse die Risiken zusammen.
> Suche die aktuelle Dokumentation dieser Bibliothek und erläutere die Migrationsschritte.
> Untersuche diese Dateien und erstelle einen knappen Bericht.
> :help
~~~

Für den Einstieg finden Sie eine Windows-Installationsanleitung samt Git- und virtueller Umgebung sowie die Konfigurationsreferenz unter [Quickstart (Windows)](QUICKSTART.md) · [Environment](ENVIRONMENT.md).

## Oberflächen
<!-- README-SYNC:interfaces -->

Alle Einstiegspunkte verwenden dieselbe Agentenlaufzeit und dasselbe Werkzeugregister.

| Oberfläche | Start | Geeignet für |
| :--- | :--- | :--- |
| **CLI** | `uag` | Terminal-Arbeit und Automatisierung |
| **Desktop** | `uagg` | Native Desktop-Unterhaltungen |
| **Web** | `uagw` | Unterhaltungen und Räume im Browser |
| **A2A** | `uaga` | Kommunikation zwischen Agenten |
| **VS Code** | [Erweiterungsleitfaden](VSCODE.md) | Arbeit direkt neben dem Quellcode |

Desktop- und Web-Oberfläche benötigen zusätzliche Abhängigkeiten, die nicht im Schnellstart-Extra `uag[core,providers,tools]` enthalten sind:

~~~bash
# Desktop GUI (PySide6 and platform integrations)
python -m pip install "uag[platform]"

# Web UI (authentication dependencies, FastAPI, and Uvicorn)
python -m pip install "uag[web]" fastapi uvicorn
~~~

Der Webserver kann FastAPI und Uvicorn auch beim Start nachinstallieren. Mit einer vorherigen Installation entfällt die Abhängigkeit von der automatischen Nachinstallation. Weitere Hinweise: [CLI usage](USAGE.md) · [Environment](ENVIRONMENT.md).

## Was Sie mit UAG umsetzen können
<!-- README-SYNC:capabilities -->

| Fähigkeit | Was UAG bereitstellt |
| :--- | :--- |
| **Modellunabhängige Abläufe** | Anbieter für lokale und gehostete Modelle mit `UAGENT_PROVIDER` wechseln, ohne Werkzeuge neu zu schreiben |
| **Code- und Dateiverarbeitung** | Repository-Navigation, Git-Prüfung, Linting, Tests, Dateizugriff und Browser-Automatisierung |
| **Erweiterbare Werkzeuge** | Über 200 Werkzeuge, dynamische Suche mit `tool_catalog` und `tool_load`, eigene Python- und Rust-Werkzeuge |
| **Vernetzte Agenten** | MCP, A2A, Claude-Code-kompatible Plugins, Agent Skills und Sub-Agenten |
| **Lang laufende Aufgaben** | Auto-Pilot, parallele unabhängige Leseoperationen, Zeitpläne, Wiederherstellung und gespeicherte Sitzungen |
| **Mehr als Terminal** | Cloud- und Kommunikationsdienste, Dokumente, Medien, Echtzeit-Sprache und unterstützte IoT-Protokolle |

### Eine Laufzeit, viele Integrationen
<!-- README-SYNC:integrations -->

~~~mermaid
flowchart LR
    UI["CLI · Desktop · Web · VS Code · A2A"] --> UAG["UAG agent runtime"]
    UAG --> MODELS["Hosted & local models"]
    UAG --> TOOLS["Tools & extensions"]
    UAG --> STATE["Sessions & context"]
    TOOLS --> SYSTEMS["Files · Code · Web · MCP · Cloud · IoT"]
    POLICY["Confirmation · Credentials · Policy"] -.-> UAG
~~~

**Beispiele unterstützter Anbieter** sind nachstehend aufgeführt; spezifische Einstellungen erläutert die Konfigurationsreferenz.

### Mit Skills und Plugins anpassen
<!-- README-SYNC:extensions -->

Erweitern Sie UAG, ohne den Kern zu verändern: Installieren Sie Agent Skills über SkillsMP oder ClawHub, verbinden Sie MCP-Server oder laden Sie Claude-Code-kompatible Plugins mit Werkzeugen, Skills, Agenten und Hooks.

~~~text
:skills mp_search browser automation
:plugin list
:plugin install <source>
:plugin marketplace list
~~~

Eigene Werkzeuge können `TOOL_SPEC` und `run_tool()` bereitstellen; auch Rust-basierte Werkzeuge werden unterstützt. Einstiegspunkte: [Tool Creator Guide](../TOOL_CREATOR_GUIDE.md) · [Plugin Development Guide](../src/uagent/docs/DEVELOP_PLUGIN.md) · [MCP OAuth / Proxy](MCP_OAUTH_PROXY_GUIDE.md).

## Für echte Arbeitsabläufe entwickelt
<!-- README-SYNC:workflows -->

### Kontext und Gedächtnis
<!-- README-SYNC:context-memory -->

Um den aktiven Modellkontext nicht mit großen Werkzeugergebnissen zu überfrachten, kann UAG sie als **Artefakte** speichern. Mit `artifact_read` lassen sich später relevante Ausschnitte abrufen. Sitzungen werden standardmäßig in SQLite gespeichert; außerdem gibt es Verlaufssuche und explizite Prüfungen des Gedächtnisses.

- [Context compression](CONTEXT_COMPRESSION.de.md)
- [Memory](MEMORY.md)
- [Session portability](SESSION_PORTABILITY.md)

### Automatisierung und Zusammenarbeit
<!-- README-SYNC:automation -->

UAG unterstützt parallele unabhängige Leseoperationen, die Koordination mehrerer Agenten, Wiederaufnahme nach einem Neustart und den mehrstufigen Auto-Pilot. Starten Sie ihn mit `:auto`. Mit **F12** unterbrechen Sie die aktuelle Antwort und fordern das Beenden des Auto-Piloten an.

- [Auto-pilot](README_AUTO.md)
- [Timers and scheduled tasks](SET_TIMER.md)
- [Multi-agent runtime](MULTI_AGENT_RUNTIME.md)

### Sicherheit und Beobachtbarkeit
<!-- README-SYNC:security -->

Sensible Aktionen können eine Bestätigung mit `human_ask` erfordern. Zugangsdaten lassen sich im Anmeldedatenspeicher des Betriebssystems oder in verschlüsselten Dateien ablegen. Die Weboberfläche unterstützt bei entsprechender Konfiguration OIDC-Anmeldung und Zugriffskontrollen. OpenTelemetry-Traces und -Metriken sind **optional und standardmäßig deaktiviert**.

- [Enterprise policies](ENTERPRISE_POLICY.md)
- [MXC sandbox](SANDBOX_MXC.md)
- [Remote Web / A2A MXC defaults](REMOTE_MXC_DEFAULT.md)
- [Web identity and rooms](WEB_IDENTITY_MEMORY.md)
- [OpenTelemetry design](UAG_OPENTELEMETRY_DESIGN.md)
- [Developer observability](../src/uagent/docs/DEVELOP_OBSERVABILITY.md)

Diese Kontrollen sind konfigurierbar und **keine pauschale Garantie**, dass beliebige Werkzeuge in einer Sandbox isoliert sind. Lesen Sie die Bereitstellungs- und Richtlinienanleitungen, bevor Sie UAG nicht vertrauenswürdigen Benutzern oder Netzwerken zugänglich machen.

### Sprachen, Geräte und Spracheingabe
<!-- README-SYNC:languages -->

UAG bietet Ressourcen für **38 Sprachvarianten** (Englisch und 37 Übersetzungen), optionale Vollduplex-Sprachintegration sowie Werkzeuge für SwitchBot, Matter, ECHONET Lite, BACnet, Modbus TCP und OPC UA.

- [Translations](README.translations.md)
- [IoT use cases](IOT_USECASE.md)
- [Communication tools](COMMUNICATION.md)

## Dokumentation
<!-- README-SYNC:documentation -->

Beginnen Sie mit den folgenden Anleitungen und vertiefen Sie anschließend die jeweiligen Themen.

| Erste Schritte | Vertiefung |
| :--- | :--- |
| [Quickstart (Windows)](QUICKSTART.md) | [Architecture](ARCHITECTURE.md) |
| [CLI usage](USAGE.md) | [Context management](UAG_CONTEXT_MANAGEMENT_DESIGN.md) |
| [Environment and providers](ENVIRONMENT.md) | [Enterprise policy](ENTERPRISE_POLICY.md) |
| [Agent Skills and plugins](../src/uagent/docs/DEVELOP_PLUGIN.md) | [Tool flow](../src/uagent/docs/TOOL_FLOW.md) |
| [MCP and OAuth](MCP_OAUTH_PROXY_GUIDE.md) | [Computer Use](COMPUTER_USE_IMPLEMENTATION.md) |
| [VS Code extension](VSCODE.md) | [Developer guide](../src/uagent/docs/DEVELOP.md) |

Weitere Anleitungen finden Sie im Dokumentationsverzeichnis und in den Übersetzungen: [Documentation](./) · [Other languages](README.translations.md).

## Entwicklung und Beiträge
<!-- README-SYNC:contributing -->

~~~bash
git clone https://github.com/awaku7/agentcli.git
cd agentcli
python -m pip install -e ".[core,providers,test]"
~~~

Führen Sie vor einem Pull Request mit **Python-Codeänderungen** die relevanten Tests und Projektprüfungen aus:

~~~bash
python -m ruff check src tests
python -m black --check src tests
python -m pytest -q .
~~~

Die Beitragsregeln und den Entwicklungsleitfaden finden Sie hier; Issues, Dokumentationsverbesserungen, Tools, Übersetzungen und fokussierte Pull Requests sind willkommen: [AGENTS.md](../AGENTS.md) · [Developer guide](../src/uagent/docs/DEVELOP.md).

## Lizenz
<!-- README-SYNC:license -->

UAG wird unter der folgenden Lizenz veröffentlicht: [Apache License 2.0](../LICENSE).
