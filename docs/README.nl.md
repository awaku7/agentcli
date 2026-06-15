<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="720">
</p>

# uag (Lokale AI-agent)

uag is een lokale interactieve agent die **opdrachten** uitvoert, **bestanden** bewerkt en **databestanden** zoals PDF-, PPTX- en Excel-bestanden leest. Het biedt drie gebruikersinterfaces: CLI, GUI en Web.

uag is gebouwd om je **vrij te houden van apps die vastzitten aan een leverancier**: gebruik de interface die bij je workflow past, wissel van provider en houd de controle over je omgeving.

GitHub: https://github.com/awaku7/agentcli

## Installatie

Installeer via PyPI met pip:

```bash
pip install uag
```

Als je een virtuele omgeving gebruikt, activeer die dan eerst en voer daarna het bovenstaande commando uit.

Bij de eerste start controleert `uag` je omgeving en start automatisch de setupwizard wanneer vereiste provider-variabelen ontbreken. Zie [ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md) voor de configuratiegegevens.

## Belangrijkste functies

- **Praktische toolset**: bestandsmanipulatie, webzoekopdrachten, PDF/PPTX/Excel-extractie, beeldgeneratie en beeldanalyse.
- **Ondersteuning voor meerdere providers**: OpenAI / Azure / Bedrock / OpenRouter / Ollama / Gemini / Vertex AI / Claude / Grok / NVIDIA / DeepSeek / Alibaba Cloud (Qwen) / KIMI (Moonshot AI).
- **Drie interfaces**:
  - **CLI**: `uag` / `python -m uagent`
  - **GUI**: `uagg` / `python -m uagent.gui`
  - **Web**: `uagw` / `python -m uagent.web`
  - **A2A-server**: `uaga` / `python -m uagent.a2a.server`
- **MCP-ondersteuning**: verbinding maken met externe MCP-toolservers.
- **Sessiebehoud**: context behouden wanneer je van model of provider wisselt.
- **Web Inspector**: sla browsertransities, DOM-snapshots en screenshots op met `playwright_inspector`.
- **Ingebouwde documentatie**: lees meegeleverde docs met `uag docs`.
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

## Gebruik

### Starten en stoppen

Start door `uag` in je terminal uit te voeren. Typ `:exit` om te stoppen.

### A2A-server

Start een HTTP-server die compatibel is met Agent2Agent:

```bash
uaga
```

Zie [ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md) voor `UAGENT_A2A_*`-instellingen zoals authenticatie, host, poort, herladen, openbare basis-URL, gelijktijdigheid en engine.

### Handige opdrachten

- `:tools`: toon geladen tools
- `:logs [n]`: toon recente sessielogs
- `:load <index>`: laad een eerdere sessie
- `:skills`: selecteer en laad Agent Skills
- `:shrink [n]`: vat de historie samen en behoud de laatste `n` berichten

## Configuratie en details

### Omgevingsvariabelen en setup

Voor API-sleutels, taalinstellingen (`UAGENT_LANG`), instellingen voor het verkleinen van de historie en meer, zie [ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md).

- **Setupwizard**: `python -m uagent.setup_cli`
- **Versleutelde omgeving**: gebruik `uag_envsec` om `.env` te versleutelen als `.env.sec`
- **Versleutelde waarden bijwerken**: `uag_envsec add --file .env.sec --key NAME --value VALUE`

### Opmerking over Responses API

Als je `UAGENT_RESPONSES=1` instelt, wordt Responses API gebruikt voor ondersteunde providers: OpenAI / Azure / Bedrock / OpenRouter / Ollama.
Gemini / Claude / Vertex AI gebruiken hun eigen API-paden en vallen niet onder Responses API.
Voor andere providers valt uag terug op het providerspecifieke pad of chat-completions.

### Documentatie voor ontwikkelaars en vertalingen

- **Ontwikkelaarsdocumentatie**: [`src/uagent/docs/DEVELOP.md`](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)
- **Locales toevoegen**: [`src/uagent/docs/ADD_LOCALE.md`](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/ADD_LOCALE.md)
- **Andere README-vertalingen**: [`docs/README.translations.md`](https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md)

Als je `UAGENT_RESPONSES=1` instelt, wordt Responses API gebruikt voor ondersteunde providers: OpenAI / Azure / Bedrock / OpenRouter / Ollama.
Gemini / Claude / Vertex AI use their native API paths and are not covered by Responses API.
For other providers, uag falls back to the provider-specific or chat-completions path.
