<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="720">
</p>

# uag (Lokal AI-agent)

uag är en lokal interaktiv agent som kör **kommandon**, hanterar **filer** och läser **datafiler** som PDF, PPTX och Excel. Den erbjuder tre användargränssnitt: CLI, GUI och Web.

GitHub: https://github.com/awaku7/agentcli

## Installation

Installera från PyPI med pip:

```bash
pip install uag
```

Om du använder en virtuell miljö, aktivera den först och kör sedan kommandot ovan.

Vid första start kontrollerar `uag` din miljö och startar automatiskt installationsguiden om nödvändiga provider-variabler saknas. För konfigurationsdetaljer, se [ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md).

## Viktiga funktioner

- **Praktisk verktygssamling**: Filhantering, webbsökning, PDF/PPTX/Excel-extrahering, bildgenerering och bildanalys.
- **Stöd för flera leverantörer**: OpenAI / Azure / Bedrock / OpenRouter / Ollama / Gemini / Vertex AI / Claude / Grok / NVIDIA.
- **Tre gränssnitt**:
  - **CLI**: `uag` / `python -m uagent`
  - **GUI**: `uagg` / `python -m uagent.gui`
  - **Web**: `uagw` / `python -m uagent.web`
  - **A2A-server**: `uaga` / `python -m uagent.a2a.server`
- **MCP-stöd**: Anslut till externa MCP-verktygsservrar.
- **Sessionskontinuitet**: Behåll kontext när du byter modell eller leverantör.
- **Web Inspector**: Spara webbläsarövergångar, DOM-snapshots och skärmbilder med `playwright_inspector`.
- **Inbyggd dokumentation**: Läs medföljande dokumentation med `uag docs`.

## Användning

### Start och avsluta
Kör `uag` i terminalen för att starta. Skriv `:exit` för att avsluta.

### A2A-server
Starta en HTTP-server som är kompatibel med Agent2Agent:

```bash
uaga
```

Se [ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md) för `UAGENT_A2A_*`-inställningar som autentisering, värd, port, omladdning, offentlig bas-URL, samtidighet och motor.

### Praktiska kommandon
- `:tools`: visa laddade verktyg
- `:logs [n]`: visa senaste sessionsloggarna
- `:load <index>`: läs in en tidigare session
- `:skills`: välj och ladda Agent Skills
- `:shrink [n]`: sammanfatta historiken och behåll de senaste `n` meddelandena

## Inställningar och detaljer

### Miljövariabler och uppstart
För API-nycklar, språkinställning `UAGENT_LANG`, inställningar för historikkomprimering och mer, se [ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md).

- **Installationsguide**: `python -m uagent.setup_cli`
- **Krypterad miljö**: använd `uag_envsec` för att kryptera `.env` som `.env.sec`
- **Uppdatera krypterade värden**: `uag_envsec add --file .env.sec --key NAME --value VALUE`

### Notis om Responses API
Om du sätter `UAGENT_RESPONSES=1` används Responses API för stödjande leverantörer: OpenAI / Azure / Bedrock / OpenRouter / Ollama.
För andra leverantörer faller uag tillbaka till leverantörens egna flöde eller ChatCompletions.

### Utvecklardokumentation och översättningar
- **Utvecklardokumentation**: [`src/uagent/docs/DEVELOP.md`](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)
- **Lägg till lokaler**: [`src/uagent/docs/ADD_LOCALE.md`](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/ADD_LOCALE.md)
- **Andra README-översättningar**: [English](https://github.com/awaku7/agentcli/blob/main/README.md) / [日本語](https://github.com/awaku7/agentcli/blob/main/README.ja.md) / [Deutsch](https://github.com/awaku7/agentcli/blob/main/README.de.md) / [Español](https://github.com/awaku7/agentcli/blob/main/README.es.md) / [Français](https://github.com/awaku7/agentcli/blob/main/README.fr.md) / [Italiano](https://github.com/awaku7/agentcli/blob/main/README.it.md) / [한국어](https://github.com/awaku7/agentcli/blob/main/README.ko.md) / [Português](https://github.com/awaku7/agentcli/blob/main/README.pt_BR.md) / [Русский](https://github.com/awaku7/agentcli/blob/main/README.ru.md) / [ไทย](https://github.com/awaku7/agentcli/blob/main/README.th.md) / [简体中文](https://github.com/awaku7/agentcli/blob/main/README.zh_CN.md) / [繁體中文](https://github.com/awaku7/agentcli/blob/main/README.zh_TW.md) / [Polski](https://github.com/awaku7/agentcli/blob/main/README.pl.md) / [Tiếng Việt](https://github.com/awaku7/agentcli/blob/main/README.vi.md) / [Bahasa Indonesia](https://github.com/awaku7/agentcli/blob/main/README.id.md) / [العربية](https://github.com/awaku7/agentcli/blob/main/README.ar.md) / [हिन्दी](https://github.com/awaku7/agentcli/blob/main/README.hi.md) / [Português](https://github.com/awaku7/agentcli/blob/main/README.pt.md) / [Svenska](https://github.com/awaku7/agentcli/blob/main/README.sv.md) / [Norsk bokmål](https://github.com/awaku7/agentcli/blob/main/README.nb.md) / [Swahili](https://github.com/awaku7/agentcli/blob/main/README.sw.md)

Om du sätter `UAGENT_RESPONSES=1` används Responses API för stödjande leverantörer: OpenAI / Azure / Bedrock / OpenRouter / Ollama.
Gemini / Claude / Vertex AI use their native API paths and are not covered by Responses API.
For other providers, uag falls back to the provider-specific or chat-completions path.
