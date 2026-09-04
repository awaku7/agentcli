# BRUG (Kommandolinjeindstillinger)

Dette dokument beskriver de kommandolinjeindstillinger, der er tilgængelige for uag-indgangspunkter.

______________________________________________________________________

## Indgangspunkter

| Kommando | Python-modul | Grænseflade |
|---|---|---|
| `uag` | `python -m uagent` | CLI (stdin-loop) |
| `uagg` | `python -m uagent.gui` | GUI (tkinter) |
| `uagw` | `python -m uagent.web` | Webserver (FastAPI) |
| `uaga` | `python -m uagent.a2a.server` | A2A HTTP-server |

______________________________________________________________________

## CLI-startindstillinger (`uag`)

### `--workdir` / `-C <sti>`

Arbejdsmappe. Hvis den ikke er angivet, bruges miljøvariablen `UAGENT_WORKDIR` som standard, ellers den aktuelle mappe.
Mappen oprettes, hvis den ikke findes.

### `--tool-genre-mask <int>`

Bitmaske for værktøjstype. Når denne angives, springes den interaktive prompt til valg af værktøjstype over.

| Bit | Type | Beskrivelse |
|-----|-------|-------------|
| 1 | basic | Væsentlige fil-/chatværktøjer |
| 2 | comm | Kommunikationsværktøjer (Bluesky, Teams) |
| 4 | office | Kontorpakkeværktøjer (Excel, PDF, PPTX) |
| 8 | devel | Udviklingsværktøjer (git, lint, compile) |
| 16 | iot | Værktøjer til IoT-enheder (SwitchBot, ECHONET, Matter, UPnP) |
| 32 | exec | Værktøjer til kommandokørsel |
| 64 | external | Eksterne plugin-værktøjer |
| 128 | media | Generering og analyse af billeder/lyd |
| 256 | file | Værktøjer til filhåndtering |
| 512 | index | Værktøjer til navigation i kildekode/indeks |
| 1024 | dev | Værktøjer til udvikling og repositorier |
| 2048 | web | Web- og browserværktøjer |
| 4096 | utility | Hjælpeprogrammer og supportværktøjer |
| 8191 | all | Alle værktøjer |

Eksempler:

```
uag --tool-genre-mask 1 # kun grundlæggende
uag --tool-genre-mask 9 # grundlæggende + udvikling (1 + 8)
uag --tool-genre-mask 8191    # alle værktøjer
```

### `--use-tool` / `--no-use-tool`

Aktiverer eller deaktiverer afsendelse af værktøjsdefinitioner til LLM. Tilsidesætter miljøvariablen `UAGENT_USE_TOOL`.

- `--use-tool` tvinger værktøjssendelse til at være aktiveret.
- `--no-use-tool` tvinger værktøjssendelse til at være deaktiveret.

Når funktionen er deaktiveret, modtager LLM ingen værktøjsdefinitioner og kan ikke kalde noget værktøj.

### `--computer-use` / `--no-computer-use`

Aktiverer eller deaktiverer Computer Use. Tilsidesætter miljøvariablen `UAGENT_COMPUTER_USE`.

### `--inject-message` / `-M <message>`

Indsætter en besked i LLM ved opstart og afslutter efter færdiggørelse. Dette indebærer `--non-interactive`.

### `--embedded`

Indlejret tilstand til begrænsede eller reproducerbarhedsfølsomme installationer.

- Deaktiverer sessionslageret.
- Skjuler værktøjsstyringsværktøjerne (`tool_catalog`, `tool_load`, `unload_tool`), medmindre de udtrykkeligt er aktiveret.
- Ignorerer `--tool-genre-mask`; brug `--enable-tool` til eksplicit indlæsning af værktøjer.

### `--enable-tool <navn>`

Indlæser eksplicit et værktøj ved opstart. Indstillingen kan gentages, og navne adskilt med komma accepteres også.

```
uag --embedded --enable-tool handle_mcp_v2 --enable-tool human_ask
uag --embedded --enable-tool handle_mcp_v2,human_ask
```

Den angivne rækkefølge bevares og afspejles i den værktøjsrækkefølge, der præsenteres for LLM. Eksplicit aktiverede værktøjer er beskyttet mod automatisk afinstallation.

### `--plugin-dir <sti>`

Indlæs plugins fra det angivne bibliotek. Indstillingen kan gentages.

______________________________________________________________________

## Indstillinger, der kun gælder for CLI

### `--inject-message-auto <goal-options>`

Start autopilot fra et ikke-interaktivt indsat mål. Værdien bruger de samme indstillinger som `:auto`; sæt den komplette værdi i anførselstegn, når den indeholder indstillinger.

```
uag --embedded --enable-tool handle_mcp_v2 --inject-message-auto "Sorter emnerne --max-rounds 10"
uag --embedded --enable-tool handle_mcp_v2 --inject-message-auto "Sorter emnerne --infinite"
```

Den normale tilstand bruger bedømmerens vurderingsvej. Indstil `UAGENT_AUTO_SENTINEL=1` for at vælge tilstand med en enkelt LLM-sentinel. I denne tilstand skal målet LLM afslutte hvert svar med nøjagtigt én af følgende:

- `<AUTO_CONTINUE>` — kør endnu en runde
- `<AUTO_COMPLETE>` — afslut med succes

Manglende eller ugyldige markører stopper autopiloten på en sikker måde. Dette kører stadig mål-LLM; det undgår blot det ekstra opkald til korrekturlæserens LLM.

### `--non-interactive`

Ikke-interaktiv tilstand. Starter ikke stdin-løkken. Hvis der angives en filsti som et positionelt argument, behandles den, og programmet afsluttes straks.

```
uag --non-interactive README.md
uag --non-interactive --workdir /tmp/project
```

______________________________________________________________________

## Webserverindstillinger (`uagw`)

### `--host <address>`

Bindingsadresse for webserveren (standard: `127.0.0.1`, kan overskrives af `UAGENT_WEB_HOST`).

Som standard lytter webserveren kun på localhost (`127.0.0.1`). For at gøre den tilgængelig fra andre maskiner på netværket skal du bruge `--host 0.0.0.0`.

```
uagw --host 0.0.0.0
uagw --host 192.168.1.10
```

### `--tool-genre-mask <int>`

Vælg værktøjsgenrer ved hjælp af den samme bitmaske, der er beskrevet ovenfor. Når dette angives, springes den interaktive genreprompt over.

### `--use-tool` / `--no-use-tool`

Aktiver eller deaktiver afsendelse af værktøjsdefinitioner til LLM. Tilsidefører `UAGENT_USE_TOOL`.

### `--computer-use` / `--no-computer-use`

Aktiver eller deaktiver computerbrug. Tilsidesætter `UAGENT_COMPUTER_USE`.

### `--no-frontend`

Kør kun API uden HTML-skabeloner eller statiske frontend-filer.

### `--embedded`

Deaktiverer sessionslageret og skjuler værktøjsadministrationsværktøjerne (`tool_catalog`, `tool_load`, `unload_tool`).

______________________________________________________________________

## A2A-serverindstillinger (`uaga`)

### `--host <address>`

Bindingsadresse for A2A HTTP-serveren (standard: `0.0.0.0`, kan overskrives af `UAGENT_A2A_HOST`).

### `--port <nummer>`

Portnummer for A2A HTTP-serveren (standard: `8765`, kan overskrives af `UAGENT_A2A_PORT`).

### `--reload`

Aktiver hot reload ved kodændringer (standard: slået fra, kan overskrives af `UAGENT_A2A_RELOAD`).

```
uaga --host 127.0.0.1 --port 8080 --reload
```

### `--tool-genre-mask <int>`

Vælg værktøjsgenrer ved hjælp af den ovenfor beskrevne bitmaske. Når dette angives, springes den interaktive genreprompt over.

### `--use-tool` / `--no-use-tool`

Aktiver eller deaktiver afsendelse af værktøjsdefinitioner til LLM. Tilsidesætter `UAGENT_USE_TOOL`.

### `--computer-use` / `--no-computer-use`

Aktiverer eller deaktiverer Computer Use. Tilsidesætter `UAGENT_COMPUTER_USE`.

### `--embedded`

Deaktiverer sessionslageret og skjuler værktøjsstyringsværktøjerne (`tool_catalog`, `tool_load`, `unload_tool`).

______________________________________________________________________

## Relaterede miljøvariabler

| Variabel | Beskrivelse |
|---|---|
| `UAGENT_PROVIDER` | LLM-udbydernavn (påkrævet ved opstart) |
| `UAGENT_*_API_KEY` | API-nøgle til den valgte udbyder |
| `UAGENT_WORKDIR` | Standardarbejdsmappe |
| `UAGENT_WEB_HOST` | Webserverens bindingsadresse (standard: `127.0.0.1`) |
| `UAGENT_A2A_HOST` | A2A-serverens bindingsadresse (standard: `0.0.0.0`) |
| `UAGENT_A2A_PORT` | A2A-serverport (standard: `8765`) |
| `UAGENT_A2A_RELOAD` | Aktiver A2A-hotreload som standard |
| `UAGENT_USE_TOOL` | Deaktiver værktøjer, når indstillet til `0`, `false`, `no` eller `off` |
| `UAGENT_COMPUTER_USE` | Aktiver eller deaktiver computerbrug som standard |
| `UAGENT_SESSION_STORE` | Aktiver eller deaktiver sessionslageret; Indbygget tilstand tvinger `0` |
| `UAGENT_PLUGIN_DIRS` | Yderligere søgemapper til plugins |
| `UAGENT_AUTO_SENTINEL` | Vælg tilkobling af enkelt-LLM auto-pilot sentinel-tilstand, når indstillet til `1` |
| `UAGENT_CONSECUTIVE_TOOL_CALL_LIMIT` | Maksimalt antal på hinanden følgende nye værktøjsopkald (standard: `100`) |
| `UAGENT_MAX_TOOL_ROUNDS` | Maksimalt antal LLM/værktøjsrunder pr. brugerhandling (standard: `200`) |
| `UAGENT_SHRINK_CNT` | Valgfri tærskel for automatisk komprimering af meddelelser (`0`/ikke indstillet = deaktiveret) |
| `UAGENT_SHRINK_KEEP_LAST` | Beskeder, der skal bevares efter komprimering (standard: `20`) |
| `UAGENT_LANG` | Grænsefladesprog (`ja`, `en` osv.) |

Se [ENVIRONMENT.md](ENVIRONMENT.md) for den fulde liste over miljøvariabler.

______________________________________________________________________

## Eksempler

### Minimal opstart med OpenAI

```
set UAGENT_PROVIDER=openai
set UAGENT_OPENAI_API_KEY=sk-...
uag
```

### Lokal Ollama med kun grundlæggende værktøjer

```
set UAGENT_PROVIDER=ollama
set UAGENT_OLLAMA_MODEL=qwen2.5:7b
uag --tool-genre-mask 1
```

### Webserver på alle grænseflader

```
set UAGENT_WEB_HOST=0.0.0.0
uagw
```

eller

```
uagw --host 0.0.0.0
```

### A2A-server på localhost med brugerdefineret port

```
uaga --host 127.0.0.1 --port 8080
```

### Deaktiver værktøjer til en lille model

```
uag --no-use-tool --tool-genre-mask 1
```

### Ikke-interaktiv filbehandling

```
uag --non-interactive README.md
```
