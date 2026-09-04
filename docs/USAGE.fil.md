# PAGGAMIT (Mga opsyon sa command-line)

Inilalarawan ng dokumentong ito ang mga opsyon sa command-line na magagamit para sa mga entry point ng uag.

______________________________________________________________________

## Mga entry point

| Utos | Python module | Interface |
|---|---|---|
| `uag` | `python -m uagent` | CLI (stdin loop) |
| `uagg` | `python -m uagent.gui` | GUI (tkinter) |
| `uagw` | `python -m uagent.web` | Web server (FastAPI) |
| `uaga` | `python -m uagent.a2a.server` | A2A HTTP server |

______________________________________________________________________

## Mga opsyon sa pagsisimula ng CLI (`uag`)

### `--workdir` / `-C <path>`

Direktoryo ng trabaho. Kung hindi ito itinakda, babalik ito sa `UAGENT_WORKDIR` na env var, at pagkatapos ay sa kasalukuyang direktoryo.
Lilikhain ang direktoryo kung hindi ito umiiral.

### `--tool-genre-mask <int>`

Bitmask ng genre ng tool. Kapag itinakda, hindi ipinapakita ang interaktibong prompt para sa pagpili ng genre.

| Bit | Genre | Deskripsyon |
|-----|-------|-------------|
| 1 | basic | Mga pangunahing kagamitan sa file/chat |
| 2 | comm | Mga kagamitan sa komunikasyon (Bluesky, Teams) |
| 4 | office | Mga kagamitan sa office suite (Excel, PDF, PPTX) |
| 8 | devel | Mga kasangkapan sa pag-develop (git, lint, compile) |
| 16 | iot | Mga kasangkapan para sa device na IoT (SwitchBot, ECHONET, Matter, UPnP) |
| 32 | exec | Mga kasangkapan sa pagpapatupad ng utos |
| 64 | external | Mga kasangkapan para sa panlabas na plugin |
| 128 | media | Paglikha at pagsusuri ng imahe/audio |
| 256 | file | Mga kasangkapan sa pamamahala ng file |
| 512 | index | Mga kasangkapan sa pag-navigate ng source/index |
| 1024 | dev | Mga kasangkapan para sa developer at repositoryo |
| 2048 | web | Mga kasangkapan para sa web at browser |
| 4096 | utility | Mga utility at suportang kasangkapan |
| 8191 | all | Lahat ng kasangkapan |

Mga Halimbawa:

```
uag --tool-genre-mask 1 # pangunahing lamang
uag --tool-genre-mask 9 # pangunahing + devel (1 + 8)
uag --tool-genre-mask 8191    # lahat ng mga tool
```

### `--use-tool` / `--no-use-tool`

Pinapagana o pinapatay ang pagpapadala ng mga depinisyon ng tool sa LLM. Pinapawalang-bisa nito ang `UAGENT_USE_TOOL` na environment variable.

- `--use-tool` ay pinipilit ang pagpapadala ng tool.
- `--no-use-tool` ay pinipilit ang hindi pagpapadala ng tool.

Kapag naka-disable, ang LLM ay hindi tumatanggap ng anumang tool definitions at hindi makatawag ng anumang tool.

### `--computer-use` / `--no-computer-use`

I-enable o i-disable ang Computer Use. Pinapawalang-bisa ang `UAGENT_COMPUTER_USE` na environment variable.

### `--inject-message` / `-M <message>`

Mag-inject ng mensahe sa LLM sa pagsisimula at lumabas pagkatapos ng pagkumpleto. Ito ay nangangahulugang `--non-interactive`.

### `--embedded`

Embedded mode para sa mga deployment na may limitasyon o sensitibo sa reproducibility.

- Pinapatay ang session store.
- Itinatago ang mga tool para sa pamamahala (`tool_catalog`, `tool_load`, `unload_tool`) maliban kung tahasang pinagana.
- Hindi pinapansin ang `--tool-genre-mask`; gamitin ang `--enable-tool` para sa tahasang pag-load ng tool.

### `--enable-tool <name>`

Eksplisit na mag-load ng tool sa pagsisimula. Maaaring ulitin ang opsyon, at tinatanggap din ang mga pangalang pinaghiwalay ng kuwit.

```
uag --embedded --enable-tool handle_mcp_v2 --enable-tool human_ask
uag --embedded --enable-tool handle_mcp_v2,human_ask
```

Napapanatili ang tinukoy na pagkakasunod-sunod at makikita ito sa pagkakasunod-sunod ng mga tool na ipinapakita sa LLM. Ang mga tool na tahasang pinagana ay hindi awtomatikong inaalis.

### `--plugin-dir <path>`

Mag-load ng mga plugin mula sa tinukoy na direktoryo. Maaaring ulitin ang opsyon.

______________________________________________________________________

## Mga opsyon para sa CLI lamang

### `--inject-message-auto <goal-options>`

Simulan ang auto-pilot mula sa isang hindi interaktibong injected goal. Gumagamit ang halaga ng parehong mga opsyon gaya ng `:auto`; i-quote ang buong halaga kapag naglalaman ito ng mga opsyon.

```
uag --embedded --enable-tool handle_mcp_v2 --inject-message-auto "Sort the items --max-rounds 10"
uag --embedded --enable-tool handle_mcp_v2 --inject-message-auto "Sort the items --infinite"
```

Ang normal na mode ay gumagamit ng landas ng paghuhusga ng tagasuri. Itakda ang `UAGENT_AUTO_SENTINEL=1` upang makilahok sa single-LLM sentinel mode. Sa mode na iyon, ang target LLM ay dapat tapusin ang bawat tugon na may eksaktong isa sa mga sumusunod:

- `<AUTO_CONTINUE>` — magpatuloy sa susunod na round
- `<AUTO_COMPLETE>` — matagumpay na matapos

Ang nawawala o hindi wastong mga marker ay ligtas na hihinto sa auto-pilot. Patuloy pa rin nitong pinapatakbo ang target na LLM; iniiwasan lamang nito ang karagdagang tawag sa reviewer na LLM.

### `--non-interactive`

Hindi interaktibong mode. Hindi sinisimulan ang stdin loop. Kung ang landas ng file ay ibinigay bilang posisyunal na argumento, ito ay pinoproseso at agad na lumalabas ang programa.

```
uag --non-interactive README.md
uag --non-interactive --workdir /tmp/project
```

______________________________________________________________________

## Mga opsyon ng Web server (`uagw`)

### `--host <address>`

Address na ikakabit para sa Web server (default: `127.0.0.1`, maaaring baguhin gamit ang `UAGENT_WEB_HOST`).

Sa default, nakikinig lamang ang Web server sa localhost (`127.0.0.1`). Upang maging naa-access ito mula sa ibang mga makina sa network, gamitin ang `--host 0.0.0.0`.

```
uagw --host 0.0.0.0
uagw --host 192.168.1.10
```

### `--tool-genre-mask <int>`

Pumili ng mga genre ng tool gamit ang parehong bitmask na inilarawan sa itaas. Kapag tinukoy, hindi ipinapakita ang interactive na prompt para sa genre.

### `--use-tool` / `--no-use-tool`

I-enable o i-disable ang pagpapadala ng mga tool definition sa LLM. Pinapawalang-bisa ang `UAGENT_USE_TOOL`.

### `--computer-use` / `--no-computer-use`

I-enable o i-disable ang Computer Use. Pinapawalang-bisa ang `UAGENT_COMPUTER_USE`.

### `--no-frontend`

Patakbuhin lamang ang API nang walang mga HTML template o mga static na frontend file.

### `--embedded`

I-disable ang session store at itago ang mga tool-management na tool (`tool_catalog`, `tool_load`, `unload_tool`).

______________________________________________________________________

## Mga pagpipilian ng A2A server (`uaga`)

### `--host <address>`

Address ng pag-bind para sa A2A HTTP server (default: `0.0.0.0`, maaaring baguhin ng `UAGENT_A2A_HOST`).

### `--port <bilang>`

Numero ng port para sa A2A HTTP server (default: `8765`, maaaring baguhin gamit ang `UAGENT_A2A_PORT`).

### `--reload`

Pinapagana ang hot reload sa mga pagbabago sa code (default: naka-off, maaaring baguhin gamit ang `UAGENT_A2A_RELOAD`).

```
uaga --host 127.0.0.1 --port 8080 --reload
```

### `--tool-genre-mask <int>`

Pumili ng mga genre ng tool gamit ang bitmask na inilarawan sa itaas. Kapag tinukoy, hindi ipinapakita ang interactive na genre prompt.

### `--use-tool` / `--no-use-tool`

I-enable o i-disable ang pagpapadala ng mga tool definition sa LLM. Pinapawalang-bisa ang `UAGENT_USE_TOOL`.

### `--computer-use` / `--no-computer-use`

I-enable o i-disable ang Paggamit ng Kompyuter. Pinapawalang-bisa ang `UAGENT_COMPUTER_USE`.

### `--embedded`

I-disable ang session store at itago ang mga tool para sa pamamahala (`tool_catalog`, `tool_load`, `unload_tool`).

______________________________________________________________________

## Mga kaugnay na environment variable

| Variable | Deskripsyon |
|---|---|
| `UAGENT_PROVIDER` | LLM pangalan ng provider (kinakailangan sa pagsisimula) |
| `UAGENT_*_API_KEY` | API susi para sa napiling provider |
| `UAGENT_WORKDIR` | Default na direktoryo ng trabaho |
| `UAGENT_WEB_HOST` | Address ng web server na ikinakabit (default: `127.0.0.1`) |
| `UAGENT_A2A_HOST` | A2A Address ng server na ikinakabit (default: `0.0.0.0`) |
| `UAGENT_A2A_PORT` | A2A port ng server (default: `8765`) |
| `UAGENT_A2A_RELOAD` | I-enable ang A2A hot reload bilang default |
| `UAGENT_USE_TOOL` | I-disable ang mga tool kapag nakatakda sa `0`, `false`, `no`, o `off` |
| `UAGENT_COMPUTER_USE` | I-enable o i-disable ang Paggamit ng Kompyuter bilang default |
| `UAGENT_SESSION_STORE` | I-enable o i-disable ang session store; Pinipilit ng embedded mode na `0` |
| `UAGENT_PLUGIN_DIRS` | Karagdagang direktoryo ng paghahanap ng plugin |
| `UAGENT_AUTO_SENTINEL` | Sumali sa single-LLM auto-pilot sentinel mode kapag nakatakda sa `1` |
| `UAGENT_CONSECUTIVE_TOOL_CALL_LIMIT` | Pinakamataas na magkakasunod na pagtawag sa bagong tool (default: `100`) |
| `UAGENT_MAX_TOOL_ROUNDS` | Pinakamataas na LLM/tool rounds kada operasyon ng gumagamit (default: `200`) |
| `UAGENT_SHRINK_CNT` | Opsyonal na threshold para sa auto-shrink sa mga mensahe (`0`/hindi nakatakda = naka-disable) |
| `UAGENT_SHRINK_KEEP_LAST` | Mga mensaheng panatilihin pagkatapos ng shrink (default: `20`) |
| `UAGENT_LANG` | Wika ng interface (`ja`, `en`, atbp.) |

Para sa buong listahan ng mga environment variable, tingnan ang [ENVIRONMENT.md](ENVIRONMENT.md).

______________________________________________________________________

## Mga Halimbawa

### Pinakamababang pagsisimula gamit ang OpenAI

```
set UAGENT_PROVIDER=openai
set UAGENT_OPENAI_API_KEY=sk-...
uag
```

### Lokal na Ollama na may mga pangunahing tool lamang

```
set UAGENT_PROVIDER=ollama
set UAGENT_OLLAMA_MODEL=qwen2.5:7b
uag --tool-genre-mask 1
```

### Web server sa lahat ng interface

```
set UAGENT_WEB_HOST=0.0.0.0
uagw
```

o

```
uagw --host 0.0.0.0
```

### A2A server sa localhost na may pasadyang port

```
uaga --host 127.0.0.1 --port 8080
```

### I-disable ang mga tool para sa maliit na modelo

```
uag --no-use-tool --tool-genre-mask 1
```

### Hindi interaktibong pagpoproseso ng file

```
uag --non-interactive README.md
```
