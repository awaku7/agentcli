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
- **Støtte for flere leverandører**: OpenAI / Azure / Bedrock / OpenRouter / Ollama / Gemini / Vertex AI / Claude / Grok / NVIDIA.
- **Tre grensesnitt**:
  - **CLI**: `uag` / `python -m uagent`
  - **GUI**: `uagg` / `python -m uagent.gui`
  - **Web**: `uagw` / `python -m uagent.web`
  - **A2A-server**: `uaga` / `python -m uagent.a2a.server`
- **MCP-støtte**: Koble til eksterne MCP-verktøyservere.
- **Sesjonskontinuitet**: Behold konteksten når du bytter modell eller leverandør.
- **Web Inspector**: Lagre nettleseroverganger, DOM-snapshots og skjermbilder med `playwright_inspector`.
- **Innebygd dokumentasjon**: Les medfølgende dokumentasjon med `uag docs`.

## Bruk

### Start og avslutt
Kjør `uag` i terminalen for å starte. Skriv `:exit` for å avslutte.

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
- `:skills`: velg og last inn Agent Skills
- `:shrink [n]`: oppsummer historikken og behold de siste `n` meldingene

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
- **Andre README-oversettelser**: [English](https://github.com/awaku7/agentcli/blob/main/README.md) / [日本語](https://github.com/awaku7/agentcli/blob/main/docs/README.ja.md) / [Deutsch](https://github.com/awaku7/agentcli/blob/main/docs/README.de.md) / [Español](https://github.com/awaku7/agentcli/blob/main/docs/README.es.md) / [Français](https://github.com/awaku7/agentcli/blob/main/docs/README.fr.md) / [Italiano](https://github.com/awaku7/agentcli/blob/main/docs/README.it.md) / [한국어](https://github.com/awaku7/agentcli/blob/main/docs/README.ko.md) / [Português](https://github.com/awaku7/agentcli/blob/main/docs/README.pt_BR.md) / [Русский](https://github.com/awaku7/agentcli/blob/main/docs/README.ru.md) / [ไทย](https://github.com/awaku7/agentcli/blob/main/docs/README.th.md) / [简体中文](https://github.com/awaku7/agentcli/blob/main/docs/README.zh_CN.md) / [繁體中文](https://github.com/awaku7/agentcli/blob/main/docs/README.zh_TW.md) / [Polski](https://github.com/awaku7/agentcli/blob/main/docs/README.pl.md) / [Tiếng Việt](https://github.com/awaku7/agentcli/blob/main/docs/README.vi.md) / [Bahasa Indonesia](https://github.com/awaku7/agentcli/blob/main/docs/README.id.md) / [العربية](https://github.com/awaku7/agentcli/blob/main/docs/README.ar.md) / [हिन्दी](https://github.com/awaku7/agentcli/blob/main/docs/README.hi.md) / [Português](https://github.com/awaku7/agentcli/blob/main/docs/README.pt.md) / [Svenska](https://github.com/awaku7/agentcli/blob/main/docs/README.sv.md) / [Norsk bokmål](https://github.com/awaku7/agentcli/blob/main/docs/README.nb.md) / [Swahili](https://github.com/awaku7/agentcli/blob/main/docs/README.sw.md)

Hvis du setter `UAGENT_RESPONSES=1`, brukes Responses API for støttede leverandører: OpenAI / Azure / Bedrock / OpenRouter / Ollama.
Gemini / Claude / Vertex AI use their native API paths and are not covered by Responses API.
For other providers, uag falls back to the provider-specific or chat-completions path.
