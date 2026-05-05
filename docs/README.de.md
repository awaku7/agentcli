<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="720">
</p>

# uag (Lokaler KI-Agent)

uag ist ein interaktiver Agent, der **Befehle** ausführt, **Dateien** manipuliert und **verschiedene Datenformate** (PDF/PPTX/Excel usw.) auf Ihrem lokalen PC liest. Er bietet drei Schnittstellen: CLI, GUI und Web.

GitHub: https://github.com/awaku7/agentcli

## Installation

Sie können `uag` über pip installieren:

```bash
pip install uag
```

Nach der Installation wird beim ersten Start von `uag` automatisch ein **interaktiver Einrichtungsassistent** gestartet, um Ihre Umgebungsvariablen zu konfigurieren. Ausführliche Informationen zur Konfiguration und Verschlüsselung finden Sie unter **[ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md)**.

## Hauptmerkmale

- **Praktisches Toolset**: Ausgestattet mit Werkzeugen für Dateimanipulation, Websuche, Datenextraktion (PDF/PPTX/Excel), Bildgenerierung und -analyse, die alle in Ihrer lokalen Umgebung ausgeführt werden können.
- **Unterstützung mehrerer Anbieter**: Unterstützt OpenAI / Azure / Bedrock / OpenRouter / Ollama / Gemini / Vertex AI / Claude / Grok / NVIDIA.
- **Flexible Schnittstellen**: 
  - **CLI**: `uag` / `python -m uagent`
  - **GUI**: `uagg` / `python -m uagent.gui`
  - **Web**: `uagw` / `python -m uagent.web`
- **MCP (Model Context Protocol)**: Unterstützung für die Verbindung zu externen MCP-Tool-Servern.
- **Sitzungskontinuität**: Beibehalten des Konversationskontexts auch beim Wechsel von Anbietern oder Modellen.
- **Web Inspector**: Automatisches Speichern von Browser-Übergängen, DOM und Screenshots mit `playwright_inspector`.
- **Integrierte Dokumentation**: Sofortiger Zugriff auf detaillierte interne Dokumentation mit dem Befehl `uag docs`.

## Nutzung

### Starten und Beenden
Führen Sie `uag` in Ihrem Terminal aus, um zu starten. Geben Sie `:exit` ein, um das Programm zu beenden.

### A2A-Server (Agent2Agent)
Sie können einen A2A-kompatiblen HTTP-Server separat von den bestehenden Schnittstellen starten.
```bash
uaga
# oder python -m uagent.a2a.server
```

### Hinweis zur Responses API

Wenn Sie `UAGENT_RESPONSES=1` setzen, wird die Responses API für unterstützte Anbieter verwendet: OpenAI / Azure / Bedrock / OpenRouter / Ollama.
Gemini / Claude / Vertex AI verwenden ihre nativen API-Pfade und werden nicht von der Responses API abgedeckt.
Für andere Anbieter fällt uag auf den anbieterspezifischen Pfad oder den chat-completions-Pfad zurück.

Siehe [ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md) für `UAGENT_A2A_*`-Einstellungen wie Authentifizierung, Host, Port, Reload, öffentliche Basis-URL, Parallelität und Engine.

### Praktische Tipps (Kontinuität und Kontrolle)
- `:tools`: Liste der geladenen Tools anzeigen.
- `:logs [n]`: Sitzungsprotokolle anzeigen (`n` zur Angabe der Anzahl der Einträge).
- `:load <index>`: Eine vergangene Sitzung laden, um die Konversation fortzusetzen.
- `:skills`: Agent Skills (zusätzliche Rollen oder Anweisungen) auswählen und laden.
- `:shrink [n]`: Verlauf organisieren, um nur die letzten `n` Nachrichten zu behalten und Token zu sparen.

## Konfiguration und Details

### Umgebungsvariablen und Einrichtung
Detaillierte Einstellungen (API-Schlüssel, Anzeigesprache `UAGENT_LANG`, Verlaufsschrumpf-Einstellungen usw.) finden Sie unter **[ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md)**.
- **Setup**: Interaktiv über `python -m uagent.setup_cli` konfigurieren.
- **Verschlüsselung**: Verschlüsseln Sie Ihre `.env`-Datei sicher mit dem Tool `uag_envsec`.
- **Aktualisierung**: Verwenden Sie `uag_envsec add --file .env.sec --key NAME --value VALUE`, um einer vorhandenen verschlüsselten Datei eine Variable hinzuzufügen oder zu aktualisieren.

### Entwickler und Internationalisierung
- **Entwickler-Dokumentation**: [`src/uagent/docs/DEVELOP.md`](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)
- **Hinzufügen von Gebietsschemata**: [`src/uagent/docs/ADD_LOCALE.md`](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/ADD_LOCALE.md)
- **README in anderen Sprachen**: [English](https://github.com/awaku7/agentcli/blob/main/README.md) / [日本語](https://github.com/awaku7/agentcli/blob/main/docs/README.ja.md) / [Deutsch](https://github.com/awaku7/agentcli/blob/main/docs/README.de.md) / [Español](https://github.com/awaku7/agentcli/blob/main/docs/README.es.md) / [Français](https://github.com/awaku7/agentcli/blob/main/docs/README.fr.md) / [Italiano](https://github.com/awaku7/agentcli/blob/main/docs/README.it.md) / [한국어](https://github.com/awaku7/agentcli/blob/main/docs/README.ko.md) / [Português](https://github.com/awaku7/agentcli/blob/main/docs/README.pt_BR.md) / [Русский](https://github.com/awaku7/agentcli/blob/main/docs/README.ru.md) / [ไทย](https://github.com/awaku7/agentcli/blob/main/docs/README.th.md) / [简体中文](https://github.com/awaku7/agentcli/blob/main/docs/README.zh_CN.md) / [繁體中文](https://github.com/awaku7/agentcli/blob/main/docs/README.zh_TW.md) / [Polski](https://github.com/awaku7/agentcli/blob/main/docs/README.pl.md) / [Tiếng Việt](https://github.com/awaku7/agentcli/blob/main/docs/README.vi.md) / [Bahasa Indonesia](https://github.com/awaku7/agentcli/blob/main/docs/README.id.md) / [العربية](https://github.com/awaku7/agentcli/blob/main/docs/README.ar.md) / [हिन्दी](https://github.com/awaku7/agentcli/blob/main/docs/README.hi.md) / [Português](https://github.com/awaku7/agentcli/blob/main/docs/README.pt.md) / [Svenska](https://github.com/awaku7/agentcli/blob/main/docs/README.sv.md) / [Norsk bokmål](https://github.com/awaku7/agentcli/blob/main/docs/README.nb.md) / [Swahili](https://github.com/awaku7/agentcli/blob/main/docs/README.sw.md)
