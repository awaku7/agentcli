# GEBRUIK (Opdrachtregelopties)

Dit document beschrijft de opdrachtregelopties die beschikbaar zijn voor uag-toegangspunten.

______________________________________________________________________

## Startpunten

| Commando | Python-module | Interface |
|---|---|---|
| `uag` | `python -m uagent` | CLI (stdin-lus) |
| `uagg` | `python -m uagent.gui` | GUI (tkinter) |
| `uagw` | `python -m uagent.web` | Webserver (FastAPI) |
| `uaga` | `python -m uagent.a2a.server` | A2A HTTP-server |

______________________________________________________________________

## CLI-opstartopties (`uag`)

### `--workdir` / `-C <pad>`

Werkmap. Indien niet ingesteld, wordt teruggevallen op de omgevingsvariabele `UAGENT_WORKDIR`, daarna op de huidige map.
De map wordt aangemaakt als deze niet bestaat.

### `--tool-genre-mask <int>`

Bitmasker voor het type tool. Indien opgegeven, wordt de interactieve prompt voor genrekeuze overgeslagen.

| Bit | Genre | Beschrijving |
|-----|-------|-------------|
| 1 | basic | Essentiële bestands- en chattools |
| 2 | comm | Communicatietools (Bluesky, Teams) |
| 4 | office | Kantoorsuite-tools (Excel, PDF, PPTX) |
| 8 | devel | Ontwikkelingstools (git, lint, compile) |
| 16 | iot | Hulpmiddelen voor IoT-apparaten (SwitchBot, ECHONET, Matter, UPnP) |
| 32 | exec | Hulpmiddelen voor het uitvoeren van opdrachten |
| 64 | external | Hulpmiddelen voor externe plug-ins |
| 128 | media | Genereren en analyseren van beeld en geluid |
| 256 | file | Hulpmiddelen voor bestandsbeheer |
| 512 | index | Hulpmiddelen voor navigatie door bronnen en indexen |
| 1024 | dev | Hulpmiddelen voor ontwikkelaars en repositories |
| 2048 | web | Web- en browserhulpmiddelen |
| 4096 | utility | Hulpprogramma’s en ondersteuningshulpmiddelen |
| 8191 | all | Alle hulpmiddelen |

Voorbeelden:

```
uag --tool-genre-mask 1 # alleen basis
uag --tool-genre-mask 9 # basis + ontwikkeling (1 + 8)
uag --tool-genre-mask 8191    # alle hulpmiddelen
```

### `--use-tool` / `--no-use-tool`

Schakelt het verzenden van tooldefinities naar de LLM in of uit. Overschrijft de omgevingsvariabele `UAGENT_USE_TOOL`.

- `--use-tool` dwingt het verzenden van tools in.
- `--no-use-tool` dwingt het verzenden van tools uit.

Wanneer uitgeschakeld, ontvangt de LLM geen tooldefinities en kan hij geen enkele tool aanroepen.

### `--computer-use` / `--no-computer-use`

Schakel computergebruik in of uit. Overschrijft de omgevingsvariabele `UAGENT_COMPUTER_USE`.

### `--inject-message` / `-M <bericht>`

Voeg bij het opstarten een bericht toe aan de `LLM` en sluit af na voltooiing. Dit impliceert `--non-interactive`.

### `--embedded`

Ingebedde modus voor implementaties met beperkingen of waarbij reproduceerbaarheid van belang is.

- Schakelt de sessieopslag uit.
- Verbergt tools voor toolbeheer (`tool_catalog`, `tool_load`, `unload_tool`) tenzij deze expliciet zijn ingeschakeld.
- Negeert `--tool-genre-mask`; gebruik `--enable-tool` voor het expliciet laden van tools.

### `--enable-tool <naam>`

Laadt een tool expliciet bij het opstarten. De optie kan worden herhaald en er worden ook door komma’s gescheiden namen geaccepteerd.

```
uag --embedded --enable-tool handle_mcp_v2 --enable-tool human_ask
uag --embedded --enable-tool handle_mcp_v2,human_ask
```

De opgegeven volgorde blijft behouden en wordt weergegeven in de volgorde van tools die aan de LLM wordt gepresenteerd. Expliciet ingeschakelde tools worden vastgezet tegen automatisch verwijderen.

### `--plugin-dir <pad>`

Laad plug-ins vanuit de opgegeven map. De optie kan worden herhaald.

______________________________________________________________________

## Opties alleen voor de CLI

### `--inject-message-auto <goal-options>`

Start de automatische piloot vanuit een niet-interactief geïnjecteerd doel. De waarde gebruikt dezelfde opties als `:auto`; zet de volledige waarde tussen aanhalingstekens als deze opties bevat.

```
uag --embedded --enable-tool handle_mcp_v2 --inject-message-auto "Sorteer de items --max-rounds 10"
uag --embedded --enable-tool handle_mcp_v2 --inject-message-auto "Sorteer de items --infinite"
```

De normale modus maakt gebruik van het beoordelingspad van de recensent. Stel `UAGENT_AUTO_SENTINEL=1` in om de modus met één LLM-sentinel te activeren. In die modus moet het doel LLM elk antwoord afsluiten met precies één van de volgende:

- `<AUTO_CONTINUE>` — voer nog een ronde uit
- `<AUTO_COMPLETE>` — succesvol afronden

Ontbrekende of ongeldige markeringen stoppen de automatische modus op veilige wijze. Het doel-LLM wordt hierdoor nog steeds uitgevoerd; alleen de extra aanroep van de beoordelaar-LLM wordt vermeden.

### `--non-interactive`

Niet-interactieve modus. Start de stdin-lus niet. Als een bestandspad als positioneel argument wordt opgegeven, wordt dit verwerkt en wordt het programma onmiddellijk afgesloten.

```
uag --non-interactive README.md
uag --non-interactive --workdir /tmp/project
```

______________________________________________________________________

## Opties voor de webserver (`uagw`)

### `--host <address>`

Bindadres voor de webserver (standaard: `127.0.0.1`, kan worden overschreven door `UAGENT_WEB_HOST`).

Standaard luistert de webserver alleen op localhost (`127.0.0.1`). Om de webserver toegankelijk te maken vanaf andere computers in het netwerk, gebruik je `--host 0.0.0.0`.

```
uagw --host 0.0.0.0
uagw --host 192.168.1.10
```

### `--tool-genre-mask <int>`

Selecteer toolgenres met behulp van hetzelfde bitmasker als hierboven beschreven. Indien opgegeven, wordt de interactieve genre-prompt overgeslagen.

### `--use-tool` / `--no-use-tool`

Schakel het verzenden van tooldefinities naar de LLM in of uit. Overschrijft `UAGENT_USE_TOOL`.

### `--computer-use` / `--no-computer-use`

Schakel computergebruik in of uit. Overschrijft `UAGENT_COMPUTER_USE`.

### `--no-frontend`

Voer alleen API uit zonder HTML-sjablonen of statische frontend-bestanden.

### `--embedded`

Schakel de sessieopslag uit en verberg de tools voor toolbeheer (`tool_catalog`, `tool_load`, `unload_tool`).

______________________________________________________________________

## A2A-serveropties (`uaga`)

### `--host <address>`

Bindadres voor de A2A HTTP-server (standaard: `0.0.0.0`, kan worden overschreven door `UAGENT_A2A_HOST`).

### `--port <getal>`

Poortnummer voor de A2A HTTP-server (standaard: `8765`, kan worden overschreven door `UAGENT_A2A_PORT`).

### `--reload`

Hot reload inschakelen bij wijzigingen in de code (standaard: uitgeschakeld, kan worden overschreven door `UAGENT_A2A_RELOAD`).

```
uaga --host 127.0.0.1 --port 8080 --reload
```

### `--tool-genre-mask <int>`

Selecteer toolgenres met behulp van het hierboven beschreven bitmasker. Indien opgegeven, wordt de interactieve genre-prompt overgeslagen.

### `--use-tool` / `--no-use-tool`

Schakel het verzenden van tooldefinities naar de LLM in of uit. Overschrijft `UAGENT_USE_TOOL`.

### `--computer-use` / `--no-computer-use`

Schakel computergebruik in of uit. Overschrijft `UAGENT_COMPUTER_USE`.

### `--embedded`

Schakel de sessieopslag uit en verberg hulpmiddelen voor toolbeheer (`tool_catalog`, `tool_load`, `unload_tool`).

______________________________________________________________________

## Gerelateerde omgevingsvariabelen

| Variabele | Beschrijving |
|---|---|
| `UAGENT_PROVIDER` | Naam van de LLM-provider (vereist bij het opstarten) |
| `UAGENT_*_API_KEY` | API-sleutel voor de geselecteerde provider |
| `UAGENT_WORKDIR` | Standaard werkdirectory |
| `UAGENT_WEB_HOST` | Bindadres van de webserver (standaard: `127.0.0.1`) |
| `UAGENT_A2A_HOST` | Bindadres van de A2A-server (standaard: `0.0.0.0`) |
| `UAGENT_A2A_PORT` | Poort van de A2A-server (standaard: `8765`) |
| `UAGENT_A2A_RELOAD` | Standaard hot reload voor A2A inschakelen |
| `UAGENT_USE_TOOL` | Schakel tools uit wanneer ingesteld op `0`, `false`, `no` of `off` |
| `UAGENT_COMPUTER_USE` | Schakel Computergebruik standaard in of uit |
| `UAGENT_SESSION_STORE` | Schakel de sessieopslag in of uit; In de embedded-modus is `0` verplicht |
| `UAGENT_PLUGIN_DIRS` | Extra zoekmappen voor plug-ins |
| `UAGENT_AUTO_SENTINEL` | Schakel de single-LLM auto-pilot sentinel-modus in wanneer ingesteld op `1` |
| `UAGENT_CONSECUTIVE_TOOL_CALL_LIMIT` | Maximaal aantal opeenvolgende aanroepen van nieuwe tools (standaard: `100`) |
| `UAGENT_MAX_TOOL_ROUNDS` | Maximaal aantal LLM/tool-rondes per gebruikersbewerking (standaard: `200`) |
| `UAGENT_SHRINK_CNT` | Optionele drempel voor automatisch verkleinen in berichten (`0`/niet ingesteld = uitgeschakeld) |
| `UAGENT_SHRINK_KEEP_LAST` | Aantal berichten dat na het inkrimpen bewaard moet blijven (standaard: `20`) |
| `UAGENT_LANG` | Taal van de interface (`ja`, `en`, enz.) |

Zie [ENVIRONMENT.md](ENVIRONMENT.md) voor de volledige lijst met omgevingsvariabelen.

______________________________________________________________________

## Voorbeelden

### Minimale opstart met OpenAI

```
set UAGENT_PROVIDER=openai
set UAGENT_OPENAI_API_KEY=sk-...
uag
```

### Lokale Ollama met alleen basisfuncties

```
set UAGENT_PROVIDER=ollama
set UAGENT_OLLAMA_MODEL=qwen2.5:7b
uag --tool-genre-mask 1
```

### Webserver op alle interfaces

```
set UAGENT_WEB_HOST=0.0.0.0
uagw
```

of

```
uagw --host 0.0.0.0
```

### A2A-server op localhost met aangepaste poort

```
uaga --host 127.0.0.1 --port 8080
```

### Hulpprogramma’s uitschakelen voor een klein model

```
uag --no-use-tool --tool-genre-mask 1
```

### Niet-interactieve bestandsverwerking

```
uag --non-interactive README.md
```
