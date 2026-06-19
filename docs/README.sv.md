<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="720">
</p>

# uag (Lokal AI-agent)

uag är en lokal interaktiv agent som kör **kommandon**, hanterar **filer** och läser **datafiler** som PDF, PPTX och Excel. Den erbjuder tre användargränssnitt: CLI, GUI och Web.

uag är byggt för att **hålla dig fri från leverantörslåsta appar**: använd det gränssnitt som passar ditt arbetsflöde, byt leverantör och behåll kontrollen över din miljö.

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
- **Stöd för flera leverantörer**: OpenAI / Azure / Bedrock / OpenRouter / Ollama / Gemini / Vertex AI / Claude / Grok / NVIDIA / DeepSeek / Alibaba Cloud (Qwen) / Moonshot AI / MiMo / LM Studio.
- **Tre gränssnitt**:
  - **CLI**: `uag` / `python -m uagent`
  - **GUI**: `uagg` / `python -m uagent.gui`
  - **Web**: `uagw` / `python -m uagent.web`
  - **A2A-server**: `uaga` / `python -m uagent.a2a.server`
- **MCP-stöd**: Anslut till externa MCP-verktygsservrar.
- **Sessionskontinuitet**: Behåll kontext när du byter modell eller leverantör.
- **Agent Skills-marknadsplats**: Bläddra och installera community-Agent Skills från [SkillsMP](https://skillsmp.com) eller [ClawHub](https://clawhub.ai) med `:skills mp_search`.
- **Web Inspector**: Spara webbläsarövergångar, DOM-snapshots och skärmbilder med `playwright_inspector`.
- **Inbyggd dokumentation**: Läs medföljande dokumentation med `uag docs`.
- **Verktygskatalog (Ny!)**: Upptäck och ladda verktyg dynamiskt med `tool_catalog`/`tool_load`. Fungerar med alla leverantörer som stöds — inga leverantörsspecifika API:er krävs.
- **IoT device support**: Control SwitchBot, ECHONET Lite, Matter, and UPnP devices. See [IOT_USECASE.md](IOT_USECASE.md).

## IoT Device Support

Control smart home and IoT devices through multiple interfaces:

- **SwitchBot Cloud**: List, control, and batch-operate SwitchBot devices (TV, air conditioner, lights, etc.).
  - Infrared remote devices (on/off, brightness, temperature)
  - Air conditioner mode and fan speed control
  - Batch execution of multiple commands
- **SwitchBot BLE**: Scan and control nearby SwitchBot BLE devices.
- **ECHONET Lite**: Discover and control ECHONET Lite home appliances over the local network.
- **Matter**: Inspect Matter controller/bridge/device structure (read-only).
- **UPnP**: Discover UPnP devices and manage IGD port forwarding.

For detailed usage, see [IOT_USECASE.md](IOT_USECASE.md).

## Användning

### Start och avsluta

Kör `uag` i terminalen för att starta. Skriv `:exit` för att avsluta.

For all command-line options, see [USAGE.md](USAGE.md).

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
- `:skills`: välj och ladda Agent Skills (använd `:skills mp_search` för att bläddra på [SkillsMP](https://skillsmp.com)- eller [ClawHub](https://clawhub.ai)-marknadsplatserna)
- `:shrink [n]`: sammanfatta historiken och behåll de senaste `n` meddelandena
- Small LLM tips: see [SLM_TIPS.md](SLM_TIPS.md).

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
- **Andra README-översättningar**: [`docs/README.translations.md`](https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md)

Om du sätter `UAGENT_RESPONSES=1` används Responses API för stödjande leverantörer: OpenAI / Azure / Bedrock / OpenRouter / Ollama.
Gemini / Claude / Vertex AI use their native API paths and are not covered by Responses API.
For other providers, uag falls back to the provider-specific or chat-completions path.
