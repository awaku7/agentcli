<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="720">
</p>

<h1 align="center">uag – Universelles KI-Gateway</h1>

<p align="center">
  <b>U</b>niversal <b>A</b>I <b>G</b>ateway — Your environment, your freedom.
</p>

<p align="center">
  File ops / Web search / Image generation &amp; analysis / PDF &amp; Excel extraction / IoT control / MCP integration<br>
  15+ providers / 3 UIs / Parallel tool execution / Agent Skills marketplace
</p>

<p align="center">
  <a href="https://github.com/awaku7/agentcli">GitHub</a>
  ·
  <a href="https://pypi.org/project/uag/">PyPI</a>
  ·
  <a href="https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md">Read this in your language</a>
</p>

---

## Warum uag?

**Befreien Sie sich von der Anbieterbindung.** Die meisten KI-Assistenten binden Sie an einen bestimmten Anbieter oder Cloud-Dienst. uag ist anders.

- **Läuft lokal** auf Ihrem Computer. Ihre Daten bleiben bei Ihnen (mit Ausnahme von API-Aufrufen, die Sie tätigen).
- **Anbieterfreiheit**: OpenAI, Claude, Gemini, DeepSeek, Ollama, Azure, Bedrock, HuggingFace... 15+ Anbieter, alle über eine einzige Schnittstelle zugänglich. Wechseln Sie zwischen ihnen, indem Sie Umgebungsvariablen neu konfigurieren – keine Neuinstallation, keine Migration.
- **131 Tools**: Datei-E/A, Websuche, Bildgenerierung, Gmail, BLE-Gerätescan, MCP-Serverintegration – **76 sind parallelsicher** (bis zu 8 werden gleichzeitig über Thread-Pool ausgeführt, konfigurierbar über „UAGENT_PARALLEL_WORKERS“). Wenn das LLM mehrere Tool-Aufrufe gleichzeitig auslöst, parallelisiert uag diese automatisch.
- **3 UIs + A2A**: CLI, GUI, Web und Agent-to-Agent-Protokoll. Gleiche Engine, beliebige Schnittstelle.
- **IoT-fähig**: SwitchBot, ECHONET Lite, Matter, UPnP – steuern Sie Ihre Heimgeräte durch KI.
- **Agentenfähigkeiten**: Installieren Sie von der Community entwickelte Fähigkeiten vom Marktplatz. Verlängern Sie uag endlos.

uag ist **Ihr KI-Assistent zu Ihren Bedingungen**. Keine Bindung an einen Anbieter, keine Bindung an eine Schnittstelle, keine Bindung an eine Plattform.

## Schnellstart

```bash
pip install uag
uag
```

Beim ersten Start führt Sie der Einrichtungsassistent durch die Anbieterkonfiguration.
Alle Umgebungsvariablen finden Sie unter [ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md).

## Merkmale

### 🧠 Multi-Provider-Architektur

OpenAI / Azure / Bedrock / OpenRouter / Ollama / Gemini / Vertex AI / Claude / Grok / NVIDIA / DeepSeek / Z.AI (Zhipu AI) / HuggingFace / Alibaba Cloud (Qwen) / KIMI (Moonshot AI) / Xiaomi MiMo / LM Studio / MiniMax / **Sakana AI (Fugu)**

Alle Anbieter nutzen das gleiche Toolset und die gleiche Schnittstelle. Wechseln Sie durch die Einstellung „UAGENT_PROVIDER“ – keine Codeänderungen, keine separaten Installationen.

### ⚡ Parallele Werkzeugausführung

Wenn das LLM mehrere Tools gleichzeitig anfordert, werden diese von uag automatisch parallelisiert.
76 Tools sind mit „x_parallel_safe“ gekennzeichnet und werden gleichzeitig über einen „ThreadPoolExecutor“ ausgeführt (8 Threads standardmäßig; setzen Sie „UAGENT_PARALLEL_WORKERS“ auf Änderung).

**Beispiel**: Fragen Sie „Überprüfen Sie das Wetter in den nordischen Hauptstädten“ → LLM löst „search_web“ × 5 Länder aus → alle 5 Suchanfragen werden parallel ausgeführt → Ergebnisse werden in einem Stapel gesammelt.

Schreibgeschützte Tools (Dateisuche, Hash-Berechnung, Verzeichnisliste, Übersetzung, DB-Abfragen usw.) werden aggressiv parallelisiert.

### 🔄 Sitzungskontinuität

- **Switch providers mid-session** with `UAGENT_PROVIDER` — conversation history is preserved.
- **Reload past sessions** with `:load <index>` — pick up where you left off.
- **Tool result caching** avoids redundant re-execution when the same tool call repeats.

### 🛠 131 Werkzeuge

| Kategorie | Werkzeuge |
|---|---|
| **Dateioperationen** | lesen/schreiben/erstellen/löschen/suchen/grep/hash/zip, parse_eml (.eml-Dateien) |
| **Web** | fetch_url, search_web, Screenshot, browser_playwright |
| **Medien** | generieren_image, analysieren_image, img2img, audio_speech, audio_transcribe |
| **Dokumente** | PDF/PPTX/DOCX/RTF/ODT-Extraktion, strukturierte Excel-Extraktion |
| **Kommunikation** | gmail_send, gmail_read, bluesky, discord_channel, teams_webhook – siehe [COMMUNICATION.md](https://github.com/awaku7/agentcli/blob/main/docs/COMMUNICATION.md) |
| **IoT** | SwitchBot (Cloud + BLE), ECHONET Lite, Matter, UPnP |
| **Entwicklungstools** | git_ops, python_compile, lint_format, run_tests, db_query, **13 Quellcode-Navigatoren (IDX-Familie)** |
| **MCP** | Mit externen MCP-Servern verbinden, Tools auflisten, ausführen |
| **A2A** | Agent-zu-Agent-Kommunikation (mit anderen UAG-Instanzen oder A2A-kompatiblen Servern) |
| **System** | Umgebungsvariablen, Systemspezifikationen, Uhrzeit, Datumsberechnung |
| **Quellennavigation** | **13 idx-Tools** für Python, PHP, TypeScript, Java, C#, Dart, C/C++, Rust, Go, Swift, Kotlin, COBOL – erhalten Sie einen Funktions-/Klassenindex oder eine spezifische Definition, ohne die gesamte Datei zu lesen |

### 🖥 4 Schnittstellen + VS-Code-Erweiterung

| Modus | Befehl | Zweck |
|---|---|---|
| **CLI** | `uag` | Schnelle terminalbasierte Bedienung |
| **GUI** | `uagg` | Desktop-Benutzeroberfläche über tkinter |
| **Web** | `uagw` | Browserbasierter Zugriff |
| **A2A-Server** | `uaga` | Agent2Agent-Protokoll für Multiagentenkommunikation |
| **VS-Code** | — | [Erweiterung](https://github.com/awaku7/agentcli/blob/main/VSCODE.md) mit Chat-Panel, Erläuterung, Umgestaltung, Fehler beheben und Tools-Strukturansicht |

Weitere Informationen zur VS Code-Erweiterung – Installation, Befehle, Tastenkombinationen und Konfiguration – finden Sie unter [VSCODE.md](https://github.com/awaku7/agentcli/blob/main/VSCODE.md).

### 🏠 IoT-Gerätesteuerung

- **SwitchBot**: Cloud-Batch-Steuerung und BLE-Scan/-Steuerung
- **ECHONET Lite**: Entdecken und steuern Sie Haushaltsgeräte (Klimaanlage, Lichter, Warmwasserbereiter usw.) im lokalen Netzwerk
- **Matter**: Nur-Lese-Inspektion der Controller-/Bridge-/Gerätetopologie
- **UPnP**: Geräteerkennung und IGD-Portweiterleitung

Siehe [IOT_USECASE.md](https://github.com/awaku7/agentcli/blob/main/IOT_USECASE.md)

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

Die vollständige Dokumentation finden Sie unter [README_AUTO.md](https://github.com/awaku7/agentcli/blob/main/README_AUTO.md).

### 🧩 Batch-Statusmanager

uag kann den Fortschritt über lang laufende Aufgaben mit mehreren Dateien verfolgen. Wenn das LLM Dutzende Dateien verarbeitet, speichert „batch_state“ die Liste der ausstehenden, abgeschlossenen und fehlgeschlagenen Dateien auf der Festplatte. Wenn die Sitzung endet oder eine Runde abläuft, wird der nächste Lauf an der Stelle fortgesetzt, an der er gestoppt wurde – es geht nichts verloren.

### 🛡 Human-in-the-Loop

„human_ask“ lässt das LLM anhalten und um Ihre Bestätigung bitten, bevor es destruktive Operationen ausführt (Löschen von Dateien, Überschreiben, Shell-Befehle). Sie behalten die Kontrolle.

### 🛑 Unterbrechen (C-Taste / Stopp-Taste)

Stoppen Sie die LLM-Antwortgenerierung jederzeit und geben Sie einen Stoppbefehl zurück an das LLM.

| Schnittstelle | So unterbrechen Sie |
|---|---|
| **CLI** | Drücken Sie während des LLM-Streamings die Taste „c“ – die aktuelle Reaktion stoppt und „Stopp“ wird als Benutzernachricht gesendet, sodass das LLM entsprechend reagiert |
| **WEB-UI** | Klicken Sie auf die rote Schaltfläche **■ Stopp** (erscheint automatisch während der LLM-Verarbeitung) |
| **Desktop-GUI** | Klicken Sie auf die rote Schaltfläche **■** (erscheint automatisch während der LLM-Verarbeitung) |

Der Interrupt funktioniert als „Prompt-Injektion“: Anstatt nur abzubrechen, gibt er „Stopp“ als Benutzernachricht an den LLM zurück, sodass dieser die Unterbrechung ordnungsgemäß abschließen oder bestätigen kann.

Drücken Sie die Taste „x“, um den Autopilot-Modus zu verlassen (siehe [README_AUTO.md](https://github.com/awaku7/agentcli/blob/main/README_AUTO.md)).

### 🕵️ Browser-Automatisierung und Web-Inspektor

Zwei komplementäre Playwright-basierte Tools:

- **browser_playwright**: Automatisieren Sie echte Browsersitzungen – navigieren, klicken, Formulare ausfüllen, Daten extrahieren, mehrseitige Abläufe verwalten. Funktioniert kopflos oder mit Kopf.
- **playwright_inspector**: Browserübergänge aufzeichnen, DOM-Snapshots und Screenshots bei jedem Schritt erfassen. Nützlich zum Debuggen von Webinteraktionen oder zum Überwachen von Seitenänderungen im Laufe der Zeit.

### 🔄 Dynamisches Laden von Werkzeugen

Mit „tool_catalog“ und „tool_load“ können Sie Tools zur Laufzeit erkennen und aktivieren.
Sie müssen beim Start nicht alles laden – aktivieren Sie nur das, was Sie brauchen, und zwar dann, wenn Sie es brauchen.

### 🌐 i18n / L10n

日本語 / Englisch / 简体中文 / 繁體中文 / 한국어 / Spanisch / Französisch / Russisch / und mehr.
Legen Sie „UAGENT_LANG“ fest, um zu wechseln. Siehe [ADD_LOCALE.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/ADD_LOCALE.md), um ein neues Gebietsschema hinzuzufügen.

Übersetzungen dieser README-Datei sind unter [docs/README.translations.md](https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md) verfügbar.

### 🔒 Verschlüsselte Umgebungsvariablen

Speichern Sie API-Schlüssel und Geheimnisse in „.env.sec“ – einer verschlüsselten „.env“-Datei.
Verwalten Sie mit „uag_envsec“.

## Konfiguration und Details

- **Umgebungsvariablen**: [ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md)
- **Setup-Assistent**: `python -m uagent.setup_cli`
- **Verschlüsselte Env**: „uag_envsec“ – „.env“ als „.env.sec“ verschlüsseln
- **Antwort-API**: Legen Sie „UAGENT_RESPONSES=1“ für den Antwort-API-Modus fest (OpenAI/Azure/Bedrock/OpenRouter/Ollama/Alibaba/LM Studio/Sakana AI). Automatisch aktiviert für Sakana AI (Fugu).
- **Entwicklerdokumente**: [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)
- **Kleine LLM-Tipps**: [SLM_TIPS.md](https://github.com/awaku7/agentcli/blob/main/SLM_TIPS.md)

## Projektphilosophie

uag möchte **Ihre KI sein, auf Ihrer Maschine, zu Ihren Bedingungen.**

- Keine SaaS-Abhängigkeit – läuft lokal
- Keine Anbieterbindung – Wechsel jederzeit möglich
- Keine UI-Sperre – CLI / GUI / Web / A2A
- Keine Bindung an bestimmte Funktionen – erweitern Sie Ihre Möglichkeiten mit Tools und Fertigkeiten

Ein kostenloses KI-Agenten-Erlebnis, frei von Anbieterbindung.
