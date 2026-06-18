<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="720">
</p>

# uag (Lokal AI-agent)

uag er en lokal interaktiv agent som kjører **kommandoer**, håndterer **filer** og leser **datafiler** som PDF, PPTX og Excel. Den tilbyr tre brukergrensesnitt: CLI, GUI og Web.

uag er laget for å **holde deg fri fra leverandørlåste apper**: bruk grensesnittet som passer arbeidsflyten din, bytt leverandør og behold kontrollen over miljøet ditt.

GitHub: https://github.com/awaku7/agentcli

## Installasjon

Installer fra PyPI med pip:

```bash
pip install uag
```

Hvis du bruker et virtuelt miljø, aktiver det først og kjør deretter kommandoen over.

Ved første oppstart sjekker `uag` miljøet ditt og starter automatisk oppsettsveiviseren hvis nødvendige provider-variabler mangler. For konfigurasjonsdetaljer, se [ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md).

## Viktige funksjoner

- **Praktisk verktøysett**: Filhåndtering, nettsøk, PDF/PPTX/Excel-ekstraksjon, bildegenerering og bildeanalyse.
- **Støtte for flere leverandører**: OpenAI / Azure / Bedrock / OpenRouter / Ollama / Gemini / Vertex AI / Claude / Grok / NVIDIA / DeepSeek / Alibaba Cloud (Qwen) / Moonshot AI.
- **Tre grensesnitt**:
  - **CLI**: `uag` / `python -m uagent`
  - **GUI**: `uagg` / `python -m uagent.gui`
  - **Web**: `uagw` / `python -m uagent.web`
  - **A2A-server**: `uaga` / `python -m uagent.a2a.server`
- **MCP-støtte**: Koble til eksterne MCP-verktøyservere.
- **Sesjonskontinuitet**: Behold konteksten når du bytter modell eller leverandør.
- **Agent Skills-markedsplass**: Bla gjennom og installer fellesskaps Agent Skills fra [SkillsMP](https://skillsmp.com) eller [ClawHub](https://clawhub.ai) med `:skills mp_search`.
- **Web Inspector**: Lagre nettleseroverganger, DOM-snapshots og skjermbilder med `playwright_inspector`.
- **Innebygd dokumentasjon**: Les medfølgende dokumentasjon med `uag docs`.
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

## Bruk

### Start og avslutt

Kjør `uag` i terminalen for å starte. Skriv `:exit` for å avslutte.

For all command-line options, see [USAGE.md](USAGE.md).

### A2A-server

Start en HTTP-server som er kompatibel med Agent2Agent:

```bash
uaga
```

Se [ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md) for `UAGENT_A2A_*`-innstillinger som autentisering, vert, port, omlasting, offentlig basis-URL, samtidighet og motor.

### Nyttige kommandoer

- `:tools`: vis lastede verktøy
- `:logs [n]`: vis de nyeste sesjonsloggene
- `:load <index>`: last inn en tidligere sesjon
- `:skills`: velg og last Agent Skills (bruk `:skills mp_search` for å bla gjennom [SkillsMP](https://skillsmp.com)- eller [ClawHub](https://clawhub.ai)-markedsplasser)
- `:shrink [n]`: oppsummer historikken og behold de siste `n` meldingene
- Small LLM tips: see [SLM_TIPS.md](SLM_TIPS.md).

## Innstillinger og detaljer

### Miljøvariabler og oppsett

For API-nøkler, språkinnstilling `UAGENT_LANG`, innstillinger for historikk-komprimering og mer, se [ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md).

- **Oppsettsveiviser**: `python -m uagent.setup_cli`
- **Kryptert miljø**: bruk `uag_envsec` til å kryptere `.env` som `.env.sec`
- **Oppdater krypterte verdier**: `uag_envsec add --file .env.sec --key NAME --value VALUE`

### Merknad om Responses API

Hvis du setter `UAGENT_RESPONSES=1`, brukes Responses API for støttede leverandører: OpenAI / Azure / Bedrock / OpenRouter / Ollama.
For andre leverandører faller uag tilbake til leverandørens egen vei eller ChatCompletions.

### Utviklerdokumentasjon og oversettelser

- **Utviklerdokumentasjon**: [`src/uagent/docs/DEVELOP.md`](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)
- **Legg til lokaler**: [`src/uagent/docs/ADD_LOCALE.md`](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/ADD_LOCALE.md)
- **Andre README-oversettelser**: [`docs/README.translations.md`](https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md)

Hvis du setter `UAGENT_RESPONSES=1`, brukes Responses API for støttede leverandører: OpenAI / Azure / Bedrock / OpenRouter / Ollama.
Gemini / Claude / Vertex AI use their native API paths and are not covered by Responses API.
For other providers, uag falls back to the provider-specific or chat-completions path.
