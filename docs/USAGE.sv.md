# ANVÄNDNING (Kommandoradsalternativ)

Detta dokument beskriver de kommandoradsalternativ som finns tillgängliga för uag-ingångspunkter.

______________________________________________________________________

## Startpunkter

| Kommando | Python-modul | Gränssnitt |
|---|---|---|
| `uag` | `python -m uagent` | CLI (stdin-loop) |
| `uagg` | `python -m uagent.gui` | GUI (tkinter) |
| `uagw` | `python -m uagent.web` | Webbserver (FastAPI) |
| `uaga` | `python -m uagent.a2a.server` | A2A HTTP-server |

______________________________________________________________________

## CLI startalternativ (`uag`)

### `--workdir` / `-C <sökväg>`

Arbetskatalog. Om den inte anges används miljövariabeln `UAGENT_WORKDIR` som standard, därefter den aktuella katalogen.
Katalogen skapas om den inte finns.

### `--tool-genre-mask <int>`

Bitmask för verktygsgenre. När detta anges hoppas den interaktiva genervalsprompten över.

| Bit | Genre | Beskrivning |
|-----|-------|-------------|
| 1 | basic | Väsentliga fil- och chattverktyg |
| 2 | comm | Kommunikationsverktyg (Bluesky, Teams) |
| 4 | office | Kontorspaketverktyg (Excel, PDF, PPTX) |
| 8 | devel | Utvecklingsverktyg (git, lint, kompilering) |
| 16 | iot | IoT-enhetsverktyg (SwitchBot, ECHONET, Matter, UPnP) |
| 32 | exec | Verktyg för kommandokörning |
| 64 | external | Externa plugin-verktyg |
| 128 | media | Bild- och ljudgenerering samt analys |
| 256 | file | Verktyg för filhantering |
| 512 | index | Verktyg för källkods- och indexnavigering |
| 1024 | dev | Verktyg för utvecklare och repositorier |
| 2048 | web | Verktyg för webben och webbläsare |
| 4096 | utility | Verktyg för allmänna ändamål och support |
| 8191 | all | Alla verktyg |

Exempel:

```
uag --tool-genre-mask 1 # endast grundläggande
uag --tool-genre-mask 9 # grundläggande + utveckling (1 + 8)
uag --tool-genre-mask 8191    # alla verktyg
```

### `--use-tool` / `--no-use-tool`

Aktivera eller inaktivera sändning av verktygsdefinitioner till LLM. Åsidosätter miljövariabeln `UAGENT_USE_TOOL`.

- `--use-tool` tvingar på sändning av verktyg.
- `--no-use-tool` tvingar av sändning av verktyg.

När funktionen är inaktiverad tar LLM inte emot några verktygsdefinitioner och kan inte anropa något verktyg.

### `--computer-use` / `--no-computer-use`

Aktivera eller inaktivera datoranvändning. Åsidosätter miljövariabeln `UAGENT_COMPUTER_USE`.

### `--inject-message` / `-M <message>`

Infogar ett meddelande i LLM vid start och avslutar efter avslutad körning. Detta innebär `--non-interactive`.

### `--embedded`

Inbäddat läge för begränsade eller reproducerbarhetskänsliga distributioner.

- Inaktiverar sessionslagret.
- Döljer verktygshanteringsverktygen (`tool_catalog`, `tool_load`, `unload_tool`) om de inte uttryckligen aktiveras.
- Ignorerar `--tool-genre-mask`; använd `--enable-tool` för att uttryckligen ladda verktyg.

### `--enable-tool <namn>`

Laddar ett verktyg explicit vid uppstart. Alternativet kan upprepas, och namn separerade med kommatecken accepteras också.

```
uag --embedded --enable-tool handle_mcp_v2 --enable-tool human_ask
uag --embedded --enable-tool handle_mcp_v2,human_ask
```

Den angivna ordningen bevaras och återspeglas i den verktygsordning som presenteras för LLM. Verktyg som uttryckligen aktiverats skyddas mot automatisk avlastning.

### `--plugin-dir <sökväg>`

Ladda in plugins från den angivna katalogen. Alternativet kan upprepas.

______________________________________________________________________

## Alternativ som endast gäller för CLI

### `--inject-message-auto <målalternativ>`

Starta autopiloten från ett icke-interaktivt injicerat mål. Värdet använder samma alternativ som `:auto`; sätt värdet inom citattecken om det innehåller alternativ.

```
uag --embedded --enable-tool handle_mcp_v2 --inject-message-auto "Sortera objekten --max-rounds 10"
uag --embedded --enable-tool handle_mcp_v2 --inject-message-auto "Sortera objekten --infinite"
```

I normalt läge används granskarens bedömningsväg. Ställ in `UAGENT_AUTO_SENTINEL=1` för att välja läget med en enda LLM-sentinel. I det läget måste målet LLM avsluta varje svar med exakt ett av följande:

- `<AUTO_CONTINUE>` — kör en ny omgång
- `<AUTO_COMPLETE>` — avsluta framgångsrikt

Saknade eller ogiltiga markörer avbryter autopiloten på ett säkert sätt. Detta kör fortfarande målet LLM; det undviker endast det ytterligare anropet till granskaren LLM.

### `--non-interactive`

Icke-interaktivt läge. Startar inte stdin-slingan. Om en filväg anges som ett positionsargument bearbetas den och programmet avslutas omedelbart.

```
uag --non-interactive README.md
uag --non-interactive --workdir /tmp/project
```

______________________________________________________________________

## Webbserveralternativ (`uagw`)

### `--host <address>`

Bindningsadress för webbservern (standard: `127.0.0.1`, kan åsidosättas av `UAGENT_WEB_HOST`).

Som standard lyssnar webbservern endast på localhost (`127.0.0.1`). För att göra den tillgänglig från andra datorer i nätverket, använd `--host 0.0.0.0`.

```
uagw --host 0.0.0.0
uagw --host 192.168.1.10
```

### `--tool-genre-mask <int>`

Välj verktygsgenrer med hjälp av samma bitmask som beskrivs ovan. När detta anges hoppas den interaktiva genreförfrågan över.

### `--use-tool` / `--no-use-tool`

Aktivera eller inaktivera sändning av verktygsdefinitioner till LLM. Åsidosätter `UAGENT_USE_TOOL`.

### `--computer-use` / `--no-computer-use`

Aktivera eller inaktivera datoranvändning. Åsidosätter `UAGENT_COMPUTER_USE`.

### `--no-frontend`

Kör endast API utan HTML-mallar eller statiska frontend-filer.

### `--embedded`

Inaktivera sessionslagret och dölj verktygshanteringsverktygen (`tool_catalog`, `tool_load`, `unload_tool`).

______________________________________________________________________

## A2A-serveralternativ (`uaga`)

### `--host <address>`

Bindningsadress för A2A- och HTTP-servern (standard: `0.0.0.0`, kan åsidosättas av `UAGENT_A2A_HOST`).

### `--port <nummer>`

Portnummer för A2A- och HTTP-servern (standard: `8765`, kan ändras med `UAGENT_A2A_PORT`).

### `--reload`

Aktivera automatisk omladdning vid kodändringar (standard: av, kan ändras med `UAGENT_A2A_RELOAD`).

```
uaga --host 127.0.0.1 --port 8080 --reload
```

### `--tool-genre-mask <int>`

Välj verktygsgenrer med hjälp av samma bitmask som beskrivs ovan. När detta anges hoppas den interaktiva genremeddelandet över.

### `--use-tool` / `--no-use-tool`

Aktivera eller inaktivera sändning av verktygsdefinitioner till LLM. Åsidosätter `UAGENT_USE_TOOL`.

### `--computer-use` / `--no-computer-use`

Aktivera eller inaktivera datoranvändning. Åsidosätter `UAGENT_COMPUTER_USE`.

### `--embedded`

Inaktiverar sessionslagret och döljer verktygshanteringsverktygen (`tool_catalog`, `tool_load`, `unload_tool`).

______________________________________________________________________

## Relaterade miljövariabler

| Variabel | Beskrivning |
|---|---|
| `UAGENT_PROVIDER` | LLM-leverantörsnamn (krävs vid uppstart) |
| `UAGENT_*_API_KEY` | API-nyckel för den valda leverantören |
| `UAGENT_WORKDIR` | Standardarbetskatalog |
| `UAGENT_WEB_HOST` | Webbserverns bindningsadress (standard: `127.0.0.1`) |
| `UAGENT_A2A_HOST` | A2A serverns bindningsadress (standard: `0.0.0.0`) |
| `UAGENT_A2A_PORT` | A2A-serverport (standard: `8765`) |
| `UAGENT_A2A_RELOAD` | Aktivera A2A-hot reload som standard |
| `UAGENT_USE_TOOL` | Inaktivera verktyg när inställt på `0`, `false`, `no` eller `off` |
| `UAGENT_COMPUTER_USE` | Aktivera eller inaktivera datoranvändning som standard |
| `UAGENT_SESSION_STORE` | Aktivera eller inaktivera sessionslagringen; Inbäddat läge tvingar fram `0` |
| `UAGENT_PLUGIN_DIRS` | Ytterligare sökkataloger för plugin-program |
| `UAGENT_AUTO_SENTINEL` | Välj att använda automatiskt sentinel-läge för enstaka LLM när inställt på `1` |
| `UAGENT_CONSECUTIVE_TOOL_CALL_LIMIT` | Maximalt antal på varandra följande nya verktygsanrop (standard: `100`) |
| `UAGENT_MAX_TOOL_ROUNDS` | Maximalt antal LLM/verktygsrundor per användaroperation (standard: `200`) |
| `UAGENT_SHRINK_CNT` | Valfritt tröskelvärde för automatisk komprimering av meddelanden (`0`/ej inställt = inaktiverat) |
| `UAGENT_SHRINK_KEEP_LAST` | Antal meddelanden som ska behållas efter komprimering (standard: `20`) |
| `UAGENT_LANG` | Gränssnittsspråk (`ja`, `en`, etc.) |

För en fullständig lista över miljövariabler, se [ENVIRONMENT.md](ENVIRONMENT.md).

______________________________________________________________________

## Exempel

### Minimal start med OpenAI

```
set UAGENT_PROVIDER=openai
set UAGENT_OPENAI_API_KEY=sk-...
uag
```

### Lokalt Ollama med endast grundläggande verktyg

```
set UAGENT_PROVIDER=ollama
set UAGENT_OLLAMA_MODEL=qwen2.5:7b
uag --tool-genre-mask 1
```

### Webbserver på alla gränssnitt

```
set UAGENT_WEB_HOST=0.0.0.0
uagw
```

eller

```
uagw --host 0.0.0.0
```

### A2A-server på localhost med anpassad port

```
uaga --host 127.0.0.1 --port 8080
```

### Inaktivera verktyg för en liten modell

```
uag --no-use-tool --tool-genre-mask 1
```

### Icke-interaktiv filbearbetning

```
uag --non-interactive README.md
```
