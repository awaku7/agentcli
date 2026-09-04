# POUŽITÍ (Parametry příkazového řádku)

Tento dokument popisuje parametry příkazového řádku dostupné pro vstupní body uag.

______________________________________________________________________

## Vstupní body

| Příkaz | Modul Pythonu | Rozhraní |
|---|---|---|
| `uag` | `python -m uagent` | CLI (smyčka stdin) |
| `uagg` | `python -m uagent.gui` | GUI (tkinter) |
| `uagw` | `python -m uagent.web` | Webový server (FastAPI) |
| `uaga` | `python -m uagent.a2a.server` | Server A2A HTTP |

______________________________________________________________________

## Spouštěcí volby CLI (`uag`)

### `--workdir` / `-C <cesta>`

Pracovní adresář. Pokud není nastaven, použije se proměnná prostředí \`UAGENT_WORKDIR, a pokud ta není nastavena, použije se aktuální adresář.
Adresář se vytvoří, pokud neexistuje.

### `--tool-genre-mask <int>`

Bitová maska žánru nástroje. Je-li zadána, přeskočí se interaktivní výzva k výběru žánru.

| Bit | Žánr | Popis |
|-----|-------|-------------|
| 1 | basic | Základní nástroje pro práci se soubory a chat |
| 2 | comm | Komunikační nástroje (Bluesky, Teams) |
| 4 | office | Nástroje kancelářského balíku (Excel, PDF, PPTX) |
| 8 | devel | Vývojové nástroje (git, lint, compile) |
| 16 | iot | Nástroje pro zařízení IoT (SwitchBot, ECHONET, Matter, UPnP) |
| 32 | exec | Nástroje pro spouštění příkazů |
| 64 | external | Nástroje pro externí pluginy |
| 128 | media | Generování a analýza obrazu/zvuku |
| 256 | file | Nástroje pro správu souborů |
| 512 | index | Nástroje pro procházení zdrojů a indexů |
| 1024 | dev | Nástroje pro vývojáře a repozitáře |
| 2048 | web | Nástroje pro web a prohlížeče |
| 4096 | utility | Pomocné a podpůrné nástroje |
| 8191 | all | Všechny nástroje |

Příklady:

```
uag --tool-genre-mask 1 # pouze základní
uag --tool-genre-mask 9 # základní + vývoj (1 + 8)
uag --tool-genre-mask 8191    # všechny nástroje
```

### `--use-tool` / `--no-use-tool`

Zapne nebo vypne odesílání definic nástrojů do proměnné LLM. Přepíše proměnnou prostředí `UAGENT_USE_TOOL`.

- `--use-tool` vynutí odesílání nástrojů.
- `--no-use-tool` vynutí vypnutí odesílání nástrojů.

Je-li tato volba zakázána, LLM neobdrží žádné definice nástrojů a nemůže žádný nástroj vyvolat.

### `--computer-use` / `--no-computer-use`

Zapne nebo vypne funkci „Použití počítače“. Přepíše proměnnou prostředí `UAGENT_COMPUTER_USE`.

### `--inject-message` / `-M <message>`

Vloží zprávu do LLM při spuštění a ukončí se po dokončení. To implikuje `--non-interactive`.

### `--embedded`

Vestavěný režim pro nasazení s omezeními nebo citlivá na reprodukovatelnost.

- Zakáže úložiště relací.
- Skryje nástroje pro správu nástrojů (`tool_catalog`, `tool_load`, `unload_tool`), pokud nejsou výslovně povoleny.
- Ignoruje `--tool-genre-mask`; pro explicitní načtení nástroje použijte `--enable-tool`.

### `--enable-tool <název>`

Explicitně načte nástroj při spuštění. Tuto volbu lze opakovat a jsou povoleny i názvy oddělené čárkami.

```
uag --embedded --enable-tool handle_mcp_v2 --enable-tool human_ask
uag --embedded --enable-tool handle_mcp_v2,human_ask
```

Zadané pořadí je zachováno a promítá se do pořadí nástrojů prezentovaného v LLM. Explicitně povolené nástroje jsou chráněny před automatickým odinstalováním.

### `--plugin-dir <path>`

Načte pluginy ze zadaného adresáře. Tuto volbu lze opakovat.

______________________________________________________________________

## Volby pouze pro CLI

### `--inject-message-auto <goal-options>`

Spustí automatický režim z neinteraktivního vloženého cíle. Hodnota používá stejné volby jako `:auto`; pokud obsahuje volby, uveďte celou hodnotu v uvozovkách.

```
uag --embedded --enable-tool handle_mcp_v2 --inject-message-auto "Seřadit položky --max-rounds 10"
uag --embedded --enable-tool handle_mcp_v2 --inject-message-auto "Seřadit položky --infinite"
```

Normální režim využívá cestu založenou na úsudku recenzenta. Nastavte `UAGENT_AUTO_SENTINEL=1`, chcete-li přepnout do režimu s jedním sentinelem LLM. V tomto režimu musí cíl LLM ukončit každou odpověď přesně jedním z následujících:

- `<AUTO_CONTINUE>` — spustit další kolo
- `<AUTO_COMPLETE>` — úspěšně dokončit

Chybějící nebo neplatné značky bezpečně zastaví automatický režim. Cílový LLM se i tak spustí; pouze se vynechá dodatečné volání recenzenta LLM.

### `--non-interactive`

Neinteraktivní režim. Nespustí smyčku stdin. Je-li jako poziční argument zadána cesta k souboru, je tento soubor zpracován a program se okamžitě ukončí.

```
uag --non-interactive README.md
uag --non-interactive --workdir /tmp/project
```

______________________________________________________________________

## Možnosti webového serveru (`uagw`)

### `--host <address>`

Adresa, na kterou se webový server připojuje (výchozí: `127.0.0.1`, lze přepsat proměnnou `UAGENT_WEB_HOST`).

Ve výchozím nastavení webový server naslouchá pouze na localhostu (`127.0.0.1`). Chcete-li jej zpřístupnit z jiných počítačů v síti, použijte `--host 0.0.0.0`.

```
uagw --host 0.0.0.0
uagw --host 192.168.1.10
```

### `--tool-genre-mask <int>`

Vyberte žánry nástrojů pomocí stejné bitové masky, jaká byla popsána výše. Je-li zadáno, přeskočí se interaktivní výzva k výběru žánru.

### `--use-tool` / `--no-use-tool`

Zapne nebo vypne odesílání definic nástrojů do LLM. Přepíše `UAGENT_USE_TOOL`.

### `--computer-use` / `--no-computer-use`

Zapne nebo vypne použití počítače. Přepíše `UAGENT_COMPUTER_USE`.

### `--no-frontend`

Spustí pouze API bez HTML šablon nebo statických frontendových souborů.

### `--embedded`

Zakáže úložiště relací a skryje nástroje pro správu nástrojů (`tool_catalog`, `tool_load`, `unload_tool`).

______________________________________________________________________

## Možnosti serveru A2A (`uaga`)

### `--host <address>`

Adresa pro vazbu serveru A2A HTTP (výchozí: `0.0.0.0`, lze přepsat proměnnou `UAGENT_A2A_HOST`).

### `--port <číslo>`

Číslo portu pro server A2A HTTP (výchozí: `8765`, lze přepsat proměnnou `UAGENT_A2A_PORT`).

### `--reload`

Zapne automatické načtení změn kódu za běhu (výchozí: vypnuto, lze přepsat proměnnou `UAGENT_A2A_RELOAD`).

```
uaga --host 127.0.0.1 --port 8080 --reload
```

### `--tool-genre-mask <int>`

Výběr žánrů nástrojů pomocí výše popsané bitové masky. Je-li zadáno, přeskočí se interaktivní výzva k výběru žánru.

### `--use-tool` / `--no-use-tool`

Zapne nebo vypne odesílání definic nástrojů do LLM. Přepíše `UAGENT_USE_TOOL`.

### `--computer-use` / `--no-computer-use`

Zapne nebo vypne funkci „Computer Use“. Přepíše proměnnou `UAGENT_COMPUTER_USE`.

### `--embedded`

Zakáže úložiště relací a skryje nástroje pro správu nástrojů (`tool_catalog`, `tool_load`, `unload_tool`).

______________________________________________________________________

## Související proměnné prostředí

| Proměnná | Popis |
|---|---|
| `UAGENT_PROVIDER` | Název poskytovatele LLM (vyžadováno při spuštění) |
| `UAGENT_*_API_KEY` | Klíč API pro vybraného poskytovatele |
| `UAGENT_WORKDIR` | Výchozí pracovní adresář |
| `UAGENT_WEB_HOST` | Adresa, na kterou se váže webový server (výchozí: `127.0.0.1`) |
| `UAGENT_A2A_HOST` | Adresa, na kterou se váže server A2A (výchozí: `0.0.0.0`) |
| `UAGENT_A2A_PORT` | Port serveru A2A (výchozí: `8765`) |
| `UAGENT_A2A_RELOAD` | Ve výchozím nastavení povolit automatické znovu načtení serveru A2A |
| `UAGENT_USE_TOOL` | Zakázat nástroje při nastavení na `0`, `false`, `no` nebo `off` |
| `UAGENT_COMPUTER_USE` | Ve výchozím nastavení povolit nebo zakázat funkci „Computer Use“ |
| `UAGENT_SESSION_STORE` | Zapnout nebo vypnout úložiště relací; V zabudovaném režimu je vynucena hodnota `0` |
| `UAGENT_PLUGIN_DIRS` | Další adresáře pro vyhledávání pluginů |
| `UAGENT_AUTO_SENTINEL` | Při nastavení na `1` se zapne režim jediného automatického strážce LLM |
| `UAGENT_CONSECUTIVE_TOOL_CALL_LIMIT` | Maximální počet po sobě jdoucích nových volání nástrojů (výchozí: `100`) |
| `UAGENT_MAX_TOOL_ROUNDS` | Maximální počet kol LLM/nástroje na jednu operaci uživatele (výchozí: `200`) |
| `UAGENT_SHRINK_CNT` | Volitelná prahová hodnota pro automatické zmenšování zpráv (`0`/nenastaveno = zakázáno) |
| `UAGENT_SHRINK_KEEP_LAST` | Počet zpráv, které se mají po zmenšení zachovat (výchozí: `20`) |
| `UAGENT_LANG` | Jazyk rozhraní (`ja`, `en` atd.) |

Úplný seznam proměnných prostředí najdete v souboru [ENVIRONMENT.md](ENVIRONMENT.md).

______________________________________________________________________

## Příklady

### Minimální spuštění s OpenAI

```
set UAGENT_PROVIDER=openai
set UAGENT_OPENAI_API_KEY=sk-...
uag
```

### Lokální Ollama pouze se základními nástroji

```
set UAGENT_PROVIDER=ollama
set UAGENT_OLLAMA_MODEL=qwen2.5:7b
uag --tool-genre-mask 1
```

### Webový server na všech rozhraních

```
set UAGENT_WEB_HOST=0.0.0.0
uagw
```

nebo

```
uagw --host 0.0.0.0
```

### Server A2A na localhostu s vlastním portem

```
uaga --host 127.0.0.1 --port 8080
```

### Zakázat nástroje pro malý model

```
uag --no-use-tool --tool-genre-mask 1
```

### Neinteraktivní zpracování souboru

```
uag --non-interactive README.md
```
