# BRUK (Kommandolinjealternativer)

Dette dokumentet beskriver kommandolinjealternativene som er tilgjengelige for uag-inngangspunkter.

______________________________________________________________________

## Inngangspunkter

| Kommando | Python-modul | Grensesnitt |
|---|---|---|
| `uag` | `python -m uagent` | CLI (stdin-løkke) |
| `uagg` | `python -m uagent.gui` | GUI (tkinter) |
| `uagw` | `python -m uagent.web` | Webserver (FastAPI) |
| `uaga` | `python -m uagent.a2a.server` | A2A HTTP-server |

______________________________________________________________________

## CLI oppstartsalternativer (`uag`)

### `--workdir` / `-C <sti>`

Arbeidskatalog. Hvis ikke angitt, faller systemet tilbake til miljøvariabelen `UAGENT_WORKDIR`, deretter den gjeldende katalogen.
Katalogen opprettes hvis den ikke finnes.

### `--tool-genre-mask <int>`

Bitmaske for verktøysjanger. Når dette angis, hoppes den interaktive spørsmålsruten for sjangervalg over.

| Bit | Sjanger | Beskrivelse |
|-----|-------|-------------|
| 1 | basic | Viktige fil- og chatverktøy |
| 2 | comm | Kommunikasjonsverktøy (Bluesky, Teams) |
| 4 | office | Kontorpakkeverktøy (Excel, PDF, PPTX) |
| 8 | devel | Utviklingsverktøy (git, lint, compile) |
| 16 | iot | Verktøy for IoT-enheter (SwitchBot, ECHONET, Matter, UPnP) |
| 32 | exec | Verktøy for kjøring av kommandoer |
| 64 | external | Verktøy for eksterne plugins |
| 128 | media | Generering og analyse av bilder/lyd |
| 256 | file | Verktøy for filhåndtering |
| 512 | index | Verktøy for navigering i kildekode/indeks |
| 1024 | dev | Verktøy for utviklere og repositorier |
| 2048 | web | Verktøy for nett og nettlesere |
| 4096 | utility | Hjelpe- og støtteverktøy |
| 8191 | all | Alle verktøy |

Eksempler:

```
uag --tool-genre-mask 1 # kun grunnleggende
uag --tool-genre-mask 9 # grunnleggende + utvikling (1 + 8)
uag --tool-genre-mask 8191    # alle verktøy
```

### `--use-tool` / `--no-use-tool`

Aktiverer eller deaktiverer sending av verktøydfinisjoner til LLM. Overstyrer miljøvariabelen `UAGENT_USE_TOOL`.

- `--use-tool` tvinger på sending av verktøy.
- `--no-use-tool` tvinger av sending av verktøy.

Når den er deaktivert, mottar LLM ingen verktøydfinisjoner og kan ikke kalle opp noe verktøy.

### `--computer-use` / `--no-computer-use`

Aktiver eller deaktiver Computer Use. Overstyrer miljøvariabelen `UAGENT_COMPUTER_USE`.

### `--inject-message` / `-M <message>`

Injiserer en melding i LLM ved oppstart og avslutter etter fullføring. Dette innebærer `--non-interactive`.

### `--embedded`

Innebygd modus for distribusjoner med begrensninger eller der reproduserbarhet er viktig.

- Deaktiverer sesjonslagringen.
- Skjuler verktøy for verktøyadministrasjon (`tool_catalog`, `tool_load`, `unload_tool`) med mindre de er eksplisitt aktivert.
- Ignorerer `--tool-genre-mask`; bruk `--enable-tool` for eksplisitt innlasting av verktøy.

### `--enable-tool <navn>`

Laster et verktøy eksplisitt ved oppstart. Alternativet kan gjentas, og navn atskilt med komma aksepteres også.

```
uag --embedded --enable-tool handle_mcp_v2 --enable-tool human_ask
uag --embedded --enable-tool handle_mcp_v2,human_ask
```

Den angitte rekkefølgen beholdes og gjenspeiles i verktøyrekkefølgen som presenteres for LLM. Verktøy som er eksplisitt aktivert, beskyttes mot automatisk avlasting.

### `--plugin-dir <path>`

Laster inn plugins fra den angitte katalogen. Alternativet kan gjentas.

______________________________________________________________________

## Alternativer kun for CLI

### `--inject-message-auto <goal-options>`

Start autopilot fra et ikke-interaktivt injisert mål. Verdien bruker de samme alternativene som `:auto`; sett hele verdien i anførselstegn når den inneholder alternativer.

```
uag --embedded --enable-tool handle_mcp_v2 --inject-message-auto "Sorter elementene --max-rounds 10"
uag --embedded --enable-tool handle_mcp_v2 --inject-message-auto "Sorter elementene --infinite"
```

Normalmodus bruker vurderingsveien til anmelderen. Sett `UAGENT_AUTO_SENTINEL=1` for å velge enkel-LLM vaktmodus. I denne modusen må målet LLM avslutte hvert svar med nøyaktig én av følgende:

- `<AUTO_CONTINUE>` — kjør en ny runde
- `<AUTO_COMPLETE>` — fullfør med suksess

Manglende eller ugyldige markører stopper autopiloten på en sikker måte. Dette kjører fortsatt målet `LLM`; det unngår bare det ekstra `LLM`-kallet til granskeren.

### `--non-interactive`

Ikke-interaktiv modus. Starter ikke stdin-sløyfen. Hvis en filbane angis som et posisjonsargument, behandles den, og programmet avsluttes umiddelbart.

```
uag --non-interactive README.md
uag --non-interactive --workdir /tmp/project
```

______________________________________________________________________

## Webserveralternativer (`uagw`)

### `--host <address>`

Bindingsadresse for webserveren (standard: `127.0.0.1`, kan overstyres med `UAGENT_WEB_HOST`).

Som standard lytter webserveren kun på localhost (`127.0.0.1`). For å gjøre den tilgjengelig fra andre maskiner på nettverket, bruk `--host 0.0.0.0`.

```
uagw --host 0.0.0.0
uagw --host 192.168.1.10
```

### `--tool-genre-mask <int>`

Velg verktøysjangre ved hjelp av den samme bitmasken som beskrevet ovenfor. Når dette er angitt, hoppes den interaktive sjangerprompten over.

### `--use-tool` / `--no-use-tool`

Aktiver eller deaktiver sending av verktøydefinisjoner til LLM. Overstyrer `UAGENT_USE_TOOL`.

### `--computer-use` / `--no-computer-use`

Aktiver eller deaktiver Computer Use. Overstyrer `UAGENT_COMPUTER_USE`.

### `--no-frontend`

Kjør kun API uten HTML-maler eller statiske frontend-filer.

### `--embedded`

Deaktiver sesjonslagringen og skjule verktøy for verktøyadministrasjon (`tool_catalog`, `tool_load`, `unload_tool`).

______________________________________________________________________

## A2A-serveralternativer (`uaga`)

### `--host <address>`

Bindingsadresse for A2A HTTP-serveren (standard: `0.0.0.0`, kan overstyres av `UAGENT_A2A_HOST`).

### `--port <tall>`

Portnummer for A2A HTTP-serveren (standard: `8765`, kan overstyres med `UAGENT_A2A_PORT`).

### `--reload`

Aktiver automatisk oppdatering ved endringer i koden (standard: av, kan overstyres av `UAGENT_A2A_RELOAD`).

```
uaga --host 127.0.0.1 --port 8080 --reload
```

### `--tool-genre-mask <int>`

Velg verktøysjangre ved hjelp av den samme bitmasken som beskrevet ovenfor. Når dette angis, hoppes den interaktive sjangerprompten over.

### `--use-tool` / `--no-use-tool`

Aktiver eller deaktiver sending av verktøydfinisjoner til LLM. Overstyrer `UAGENT_USE_TOOL`.

### `--computer-use` / `--no-computer-use`

Aktiverer eller deaktiverer Computer Use. Overstyrer `UAGENT_COMPUTER_USE`.

### `--embedded`

Deaktiverer sesjonslagringen og skjuler verktøyene for verktøyadministrasjon (`tool_catalog`, `tool_load`, `unload_tool`).

______________________________________________________________________

## Relaterte miljøvariabler

| Variabel | Beskrivelse |
|---|---|
| `UAGENT_PROVIDER` | Navn på LLM-leverandør (påkrevd ved oppstart) |
| `UAGENT_*_API_KEY` | Nøkkel for den valgte leverandøren i API |
| `UAGENT_WORKDIR` | Standard arbeidskatalog |
| `UAGENT_WEB_HOST` | Webserverens bindingsadresse (standard: `127.0.0.1`) |
| `UAGENT_A2A_HOST` | A2A-serverens bindingsadresse (standard: `0.0.0.0`) |
| `UAGENT_A2A_PORT` | A2A-serverport (standard: `8765`) |
| `UAGENT_A2A_RELOAD` | Aktiver A2A-hot reload som standard |
| `UAGENT_USE_TOOL` | Deaktiver verktøy når satt til `0`, `false`, `no` eller `off` |
| `UAGENT_COMPUTER_USE` | Aktiver eller deaktiver Computer Use som standard |
| `UAGENT_SESSION_STORE` | Aktiver eller deaktiver sesjonslagring; Innebygd modus tvinger `0` |
| `UAGENT_PLUGIN_DIRS` | Ekstra søkemapper for plugins |
| `UAGENT_AUTO_SENTINEL` | Velg å bruke enkelt-LLM autopilot-sentinel-modus når satt til `1` |
| `UAGENT_CONSECUTIVE_TOOL_CALL_LIMIT` | Maksimalt antall påfølgende nye verktøykall (standard: `100`) |
| `UAGENT_MAX_TOOL_ROUNDS` | Maksimalt antall LLM/verktøyrunder per brukeroperasjon (standard: `200`) |
| `UAGENT_SHRINK_CNT` | Valgfri terskel for automatisk komprimering av meldinger (`0`/ikke angitt = deaktivert) |
| `UAGENT_SHRINK_KEEP_LAST` | Meldinger som skal beholdes etter komprimering (standard: `20`) |
| `UAGENT_LANG` | Grensesnittspråk (`ja`, `en`, osv.) |

For en fullstendig liste over miljøvariabler, se [ENVIRONMENT.md](ENVIRONMENT.md).

______________________________________________________________________

## Eksempler

### Minimal oppstart med OpenAI

```
set UAGENT_PROVIDER=openai
set UAGENT_OPENAI_API_KEY=sk-...
uag
```

### Lokal Ollama med kun grunnleggende verktøy

```
sett UAGENT_PROVIDER=ollama
sett UAGENT_OLLAMA_MODEL=qwen2.5:7b
uag --tool-genre-mask 1
```

### Webserver på alle grensesnitt

```
sett UAGENT_WEB_HOST=0.0.0.0
uagw
```

eller

```
uagw --host 0.0.0.0
```

### A2A-server på localhost med egendefinert port

```
uaga --host 127.0.0.1 --port 8080
```

### Deaktiver verktøy for en liten modell

```
uag --no-use-tool --tool-genre-mask 1
```

### Ikke-interaktiv filbehandling

```
uag --non-interactive README.md
```
