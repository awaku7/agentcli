# HASZNÁLAT (Parancssori opciók)

Ez a dokumentum a uag belépési pontokhoz rendelkezésre álló parancssori opciókat ismerteti.

______________________________________________________________________

## Belépési pontok

| Parancs | Python modul | Interfész |
|---|---|---|
| `uag` | `python -m uagent` | CLI (stdin hurok) |
| `uagg` | `python -m uagent.gui` | GUI (tkinter) |
| `uagw` | `python -m uagent.web` | Webszerver (FastAPI) |
| `uaga` | `python -m uagent.a2a.server` | A2A HTTP szerver |

______________________________________________________________________

## CLI indítási opciók (`uag`)

### `--workdir` / `-C <path>`

Munkakönyvtár. Ha nincs beállítva, akkor a `UAGENT_WORKDIR` környezeti változóra, majd az aktuális könyvtárra esik vissza.
Ha a könyvtár nem létezik, akkor létrehozásra kerül.

### `--tool-genre-mask <int>`

Eszközműfaj-bitmaszk. Ha megadják, az interaktív műfajválasztási felhívás kihagyásra kerül.

| Bit | Műfaj | Leírás |
|-----|-------|-------------|
| 1 | basic | Alapvető fájlkezelő és csevegő eszközök |
| 2 | comm | Kommunikációs eszközök (Bluesky, Teams) |
| 4 | office | Irodai csomag eszközök (Excel, PDF, PPTX) |
| 8 | devel | Fejlesztői eszközök (git, lint, compile) |
| 16 | iot | IoT-eszközökhöz szükséges eszközök (SwitchBot, ECHONET, Matter, UPnP) |
| 32 | exec | Parancsok végrehajtásához szükséges eszközök |
| 64 | external | Külső bővítményekhez szükséges eszközök |
| 128 | media | Kép- és hangfájlok létrehozása és elemzése |
| 256 | file | Fájlkezelő eszközök |
| 512 | index | Forrás- és indexnavigációs eszközök |
| 1024 | dev | Fejlesztői és repository-eszközök |
| 2048 | web | Web- és böngészőeszközök |
| 4096 | utility | Segédprogramok és támogató eszközök |
| 8191 | all | Minden eszköz |

Példák:

```
uag --tool-genre-mask 1 # csak alapvető
uag --tool-genre-mask 9 # alapvető + fejlesztés (1 + 8)
uag --tool-genre-mask 8191    # összes eszköz
```

### `--use-tool` / `--no-use-tool`

Engedélyezi vagy letiltja az eszközdefiníciók elküldését a LLM-be. Felülírja a `UAGENT_USE_TOOL` környezeti változót.

- `--use-tool`: kényszeríti az eszközök küldését.
- `--no-use-tool`: letiltja az eszközök küldését.

Letiltás esetén a LLM nem kap eszközdefiníciókat, és nem tud semmilyen eszközt meghívni.

### `--computer-use` / `--no-computer-use`

A számítógép használatának engedélyezése vagy letiltása. Felülírja a `UAGENT_COMPUTER_USE` környezeti változót.

### `--inject-message` / `-M <message>`

Üzenetet illeszt be a LLM-be indításkor, és a feladat befejezése után kilép. Ez magában foglalja a `--non-interactive` opciót is.

### `--embedded`

Beágyazott mód korlátozott vagy reprodukálhatóságra érzékeny telepítésekhez.

- Letiltja a munkamenet-tárolót.
- Elrejti az eszközkezelő eszközöket (`tool_catalog`, `tool_load`, `unload_tool`), hacsak azokat kifejezetten nem engedélyezik.
- Figyelmen kívül hagyja a `--tool-genre-mask` opciót; az eszközök kifejezett betöltéséhez használja a `--enable-tool` opciót.

### `--enable-tool <név>`

Egy eszköz kifejezett betöltése indításkor. Az opció megismételhető, és vesszővel elválasztott nevek is elfogadottak.

```
uag --embedded --enable-tool handle_mcp_v2 --enable-tool human_ask
uag --embedded --enable-tool handle_mcp_v2,human_ask
```

A megadott sorrend megmarad, és tükröződik a LLM-nek átadott eszközsorrendben. A kifejezetten engedélyezett eszközök védve vannak az automatikus eltávolítás ellen.

### `--plugin-dir <path>`

A bővítmények betöltése a megadott könyvtárból. Az opció többször is megadható.

______________________________________________________________________

## Csak a parancssorban használható opciók

### `--inject-message-auto <goal-options>`

Indítsa el az Auto-Pilotot egy nem interaktív, beillesztett célból. Az érték ugyanazokat az opciókat használja, mint a `:auto`; ha az érték opciókat tartalmaz, akkor az egész értéket idézőjelek közé kell tenni.

```
uag --embedded --enable-tool handle_mcp_v2 --inject-message-auto "Rendezze az elemeket --max-rounds 10"
uag --embedded --enable-tool handle_mcp_v2 --inject-message-auto "Rendezze az elemeket --infinite"
```

A normál mód a felülvizsgáló döntési útvonalát használja. Állítsd be a `UAGENT_AUTO_SENTINEL=1` értéket az egyetlen LLM őrjelző mód bekapcsolásához. Ebben a módban a cél LLM-nek minden válaszát pontosan az alábbiak egyikével kell befejeznie:

- `<AUTO_CONTINUE>` — újabb kör futtatása
- `<AUTO_COMPLETE>` — sikeres befejezés

A hiányzó vagy érvénytelen jelölők biztonságosan leállítják az automatikus üzemmódot. Ez továbbra is futtatja a cél LLM-et; csupán elkerüli a további felülvizsgáló LLM-hívást.

### `--non-interactive`

Nem interaktív mód. Nem indítja el a stdin-hurkot. Ha fájlútvonalat adnak meg pozíciós argumentumként, azt feldolgozza, és a program azonnal kilép.

```
uag --non-interactive README.md
uag --non-interactive --workdir /tmp/project
```

______________________________________________________________________

## Webszerver opciók (`uagw`)

### `--host <address>`

A webszerver kötési címe (alapértelmezett: `127.0.0.1`, felülírható a `UAGENT_WEB_HOST`-gyel).

Alapértelmezés szerint a webszerver csak a localhost-on (`127.0.0.1`) figyel. Ha a hálózat más gépeiről is elérhetővé szeretné tenni, használja a `--host 0.0.0.0` parancsot.

```
uagw --host 0.0.0.0
uagw --host 192.168.1.10
```

### `--tool-genre-mask <int>`

Válassza ki az eszközműfajokat a fent leírt bitmaszk segítségével. Ha megadja, a rendszer kihagyja az interaktív műfajkérdést.

### `--use-tool` / `--no-use-tool`

Engedélyezi vagy letiltja az eszközdefiníciók elküldését a LLM-be. Felülírja a `UAGENT_USE_TOOL` beállítást.

### `--computer-use` / `--no-computer-use`

Engedélyezi vagy letiltja a számítógépes használatot. Felülírja a `UAGENT_COMPUTER_USE` beállítást.

### `--no-frontend`

A API-ot futtatja HTML-sablonok és statikus frontend-fájlok nélkül.

### `--embedded`

Letiltja a munkamenet-tárolót és elrejti az eszközkezelő eszközöket (`tool_catalog`, `tool_load`, `unload_tool`).

______________________________________________________________________

## A2A szerveropciók (`uaga`)

### `--host <address>`

A A2A HTTP szerver címhez való kötése (alapértelmezett: `0.0.0.0`, felülírható a `UAGENT_A2A_HOST` opcióval).

### `--port <szám>`

A A2A HTTP szerver portszáma (alapértelmezett: `8765`, felülírható a `UAGENT_A2A_PORT` paranccsal).

### `--reload`

A kódváltozások esetén történő forró újratöltés engedélyezése (alapértelmezett: ki, felülírható a `UAGENT_A2A_RELOAD` paranccsal).

```
uaga --host 127.0.0.1 --port 8080 --reload
```

### `--tool-genre-mask <int>`

Az eszközműfajok kiválasztása a fent leírt bitmaszk segítségével. Ha megadják, az interaktív műfajkérés kihagyásra kerül.

### `--use-tool` / `--no-use-tool`

Engedélyezi vagy letiltja az eszközdefiníciók elküldését a `LLM`-hez. Felülírja a `UAGENT_USE_TOOL` értéket.

### `--computer-use` / `--no-computer-use`

Engedélyezi vagy letiltja a számítógép-használatot. Felülírja a `UAGENT_COMPUTER_USE` környezeti változót.

### `--embedded`

Letiltja a munkamenet-tárolót és elrejti az eszközkezelő eszközöket (`tool_catalog`, `tool_load`, `unload_tool`).

______________________________________________________________________

## Kapcsolódó környezeti változók

| Változó | Leírás |
|---|---|
| `UAGENT_PROVIDER` | LLM szolgáltató neve (indításkor kötelező) |
| `UAGENT_*_API_KEY` | API kulcs a kiválasztott szolgáltatóhoz |
| `UAGENT_WORKDIR` | Alapértelmezett munkakönyvtár |
| `UAGENT_WEB_HOST` | Webszerver kapcsolódási címe (alapértelmezett: `127.0.0.1`) |
| `UAGENT_A2A_HOST` | A2A szerver kapcsolódási címe (alapértelmezett: `0.0.0.0`) |
| `UAGENT_A2A_PORT` | A `A2A` szerver portja (alapértelmezett: `8765`) |
| `UAGENT_A2A_RELOAD` | A `A2A` forró újratöltésének alapértelmezett engedélyezése |
| `UAGENT_USE_TOOL` | Az eszközök letiltása, ha az érték `0`, `false`, `no` vagy `off` |
| `UAGENT_COMPUTER_USE` | A számítógép használatának alapértelmezett engedélyezése vagy letiltása |
| `UAGENT_SESSION_STORE` | A munkamenet-tároló engedélyezése vagy letiltása; Beágyazott mód esetén `0` értékre van állítva |
| `UAGENT_PLUGIN_DIRS` | További bővítménykeresési könyvtárak |
| `UAGENT_AUTO_SENTINEL` | `1` értékre állítva bekapcsolja az egyetlen LLM-es autopilóta őrszolgálati módot |
| `UAGENT_CONSECUTIVE_TOOL_CALL_LIMIT` | A legfeljebb egymást követő friss eszközhívások száma (alapértelmezett: `100`) |
| `UAGENT_MAX_TOOL_ROUNDS` | Felhasználónkénti műveletenkénti maximális LLM/eszköz-körök száma (alapértelmezett: `200`) |
| `UAGENT_SHRINK_CNT` | Opcionális automatikus üzenet-összezsugorítási küszöbérték (`0`/beállítatlan = letiltva) |
| `UAGENT_SHRINK_KEEP_LAST` | A zsugorítás után megőrzendő üzenetek száma (alapértelmezett: `20`) |
| `UAGENT_LANG` | Felület nyelve (`ja`, `en` stb.) |

A környezeti változók teljes listájáért lásd [ENVIRONMENT.md](ENVIRONMENT.md).

______________________________________________________________________

## Példák

### Minimális beállítás a OpenAI használatával

```
set UAGENT_PROVIDER=openai
set UAGENT_OPENAI_API_KEY=sk-...
uag
```

### Helyi Ollama, kizárólag alapvető eszközökkel

```
set UAGENT_PROVIDER=ollama
set UAGENT_OLLAMA_MODEL=qwen2.5:7b
uag --tool-genre-mask 1
```

### Webszerver minden interfészen

```
set UAGENT_WEB_HOST=0.0.0.0
uagw
```

vagy

```
uagw --host 0.0.0.0
```

### A2A szerver a localhost-on egyéni porttal

```
uaga --host 127.0.0.1 --port 8080
```

### Eszközök letiltása egy kis méretű modell esetében

```
uag --no-use-tool --tool-genre-mask 1
```

### Nem interaktív fájlfeldolgozás

```
uag --non-interactive README.md
```
