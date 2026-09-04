# UTUMIAJI (Chaguo za mstari wa amri)

Hati hii inaelezea chaguo za mstari wa amri zinazopatikana kwa vianzio vya uag.

______________________________________________________________________

## Njia za kuingia

| Amri | Moduli ya Python | Kiolesura |
|---|---|---|
| `uag` | `python -m uagent` | CLI (mzunguko wa stdin) |
| `uagg` | `python -m uagent.gui` | GUI (tkinter) |
| `uagw` | `python -m uagent.web` | Seva ya wavuti (FastAPI) |
| `uaga` | `python -m uagent.a2a.server` | A2A HTTP seva |

______________________________________________________________________

## Chaguzi za kuanzisha CLI (`uag`)

### `--workdir` / `-C <path>`

Saraka ya kazi. Ikiwa haijawekwa, inarudi kwenye kigezo cha mazingira `UAGENT_WORKDIR`, kisha saraka ya sasa.
Saraka huundwa ikiwa haipo.

### `--tool-genre-mask <int>`

Bitmask ya aina ya zana. Inapopewa, ombi la kuchagua aina kwa njia ya mwingiliano linapuuzwa.

| Bit | Aina | Maelezo |
|-----|-------|-------------|
| 1 | basic | Zana muhimu za faili/mawasiliano ya papo kwa papo |
| 2 | comm | Zana za mawasiliano (Bluesky, Teams) |
| 4 | office | Zana za kifurushi cha ofisi (Excel, PDF, PPTX) |
| 8 | maendeleo | Zana za maendeleo (git, lint, compile) |
| 16 | iot | Zana za vifaa vya IoT (SwitchBot, ECHONET, Matter, UPnP) |
| 32 | exec | Zana za utekelezaji wa amri |
| 64 | external | Zana za programu-jalizi za nje |
| 128 | media | Uundaji na uchanganuzi wa picha/sauti |
| 256 | file | Zana za usimamizi wa faili |
| 512 | index | Zana za saraka/vyangavu |
| 1024 | dev | Zana za watengenezaji na hifadhi |
| 2048 | web | Zana za wavuti na vivinjari |
| 4096 | utility | Zana za huduma na usaidizi |
| 8191 | zote | Zana zote |

Mifano:

```
uag --tool-genre-mask 1 # msingi pekee
uag --tool-genre-mask 9 # msingi + maendeleo (1 + 8)
uag --tool-genre-mask 8191    # zana zote
```

### `--use-tool` / `--no-use-tool`

Washa au zima utumaji wa ufafanuzi wa zana kwa LLM. Hupitiliza kigezo cha mazingira cha `UAGENT_USE_TOOL`.

- `--use-tool` inawasha utumaji wa zana.
- `--no-use-tool` inazima utumaji wa zana.

Inapozimwa, LLM haipokei ufafanuzi wowote wa zana na haiwezi kuita zana yoyote.

### `--computer-use` / `--no-computer-use`

Washa au zima Matumizi ya Kompyuta. Inaingilia kigezo cha mazingira `UAGENT_COMPUTER_USE`.

### `--inject-message` / `-M <message>`

Ingiza ujumbe kwenye LLM wakati wa kuanzisha na kutoka baada ya kukamilika. Hii inaashiria `--non-interactive`.

### `--embedded`

Hali ya 'embedded' kwa ajili ya usambazaji wenye vikwazo au unaohitaji utegemezi.

- Inazima hifadhi ya kikao.
- Inaficha zana za usimamizi wa zana (`tool_catalog`, `tool_load`, `unload_tool`) isipokuwa zimewezeshwa waziwazi.
- Hupuuza `--tool-genre-mask`; tumia `--enable-tool` kwa upakiaji wa zana uliobainishwa wazi.

### `--enable-tool <name>`

Pakia zana kwa uwazi wakati wa kuanzisha. Chaguo linaweza kurudiwa, na majina yaliyotenganishwa kwa koma pia yanakubaliwa.

```
uag --embedded --enable-tool handle_mcp_v2 --enable-tool human_ask
uag --embedded --enable-tool handle_mcp_v2,human_ask
```

Mpangilio uliobainishwa unahifadhiwa na unaakisiwa katika mpangilio wa zana unaowasilishwa kwa LLM. Zana zilizowezeshwa waziwazi zimezuiliwa dhidi ya kuondolewa kiotomatiki.

### `--plugin-dir <path>`

Pakia programu-jalizi kutoka kwenye saraka iliyobainishwa. Chaguo linaweza kurudiwa.

______________________________________________________________________

## Chaguzi za CLI pekee

### `--inject-message-auto <goal-options>`

Anzisha auto-pilot kutoka kwa lengo lililoingizwa lisilo la mwingiliano. Thamani inatumia chaguzi zile zile kama `:auto`; nukuu thamani nzima inapojumuisha chaguzi.

```
uag --embedded --enable-tool handle_mcp_v2 --inject-message-auto "Panga vitu --max-rounds 10"
uag --embedded --enable-tool handle_mcp_v2 --inject-message-auto "Sort the items --infinite"
```

Hali ya kawaida hutumia njia ya hukumu ya mkaguzi. Weka `UAGENT_AUTO_SENTINEL=1` ili kuchagua modi ya sentinel ya LLM moja. Katika hali hiyo, lengo LLM lazima limalize kila jibu na moja tu kati ya:

- `<AUTO_CONTINUE>` — endesha raundi nyingine
- `<AUTO_COMPLETE>` — maliza kwa mafanikio

Alama zinazokosekana au zisizofaa husitisha auto-pilot kwa usalama. Hii bado inaendesha LLM lengwa; inazuia tu wito wa LLM mhakiki wa ziada.

### `--non-interactive`

Hali isiyoingiliana. Haianzishi mzunguko wa stdin. Ikiwa njia ya faili itatolewa kama kigezo cha nafasi, inachakatwa na programu inatoka mara moja.

```
uag --non-interactive README.md
uag --non-interactive --workdir /tmp/project
```

______________________________________________________________________

## Chaguo za seva ya wavuti (`uagw`)

### `--host <address>`

Anwani ya kuunganishia seva ya wavuti (chaguo-msingi: `127.0.0.1`, inaweza kubadilishwa na `UAGENT_WEB_HOST`).

Kwa chaguo-msingi, seva ya wavuti husikiliza kwenye localhost pekee (`127.0.0.1`). Ili iweze kupatikana kutoka kwa mashine zingine kwenye mtandao, tumia `--host 0.0.0.0`.

```
uagw --host 0.0.0.0
uagw --host 192.168.1.10
```

### `--tool-genre-mask <int>`

Chagua aina za zana kwa kutumia bitmask ile ile iliyoelezwa hapo juu. Inapobainishwa, ombi la aina ya zana la kiingiliano linapuuzwa.

### `--use-tool` / `--no-use-tool`

Washa au zima utumaji wa ufafanuzi wa zana kwa LLM. Hupitiliza `UAGENT_USE_TOOL`.

### `--computer-use` / `--no-computer-use`

Washa au zima Matumizi ya Kompyuta. Inapuuza `UAGENT_COMPUTER_USE`.

### `--no-frontend`

Endesha API pekee bila kiolezo cha HTML au faili za mbele zisizobadilika.

### `--embedded`

Zima hifadhi ya kikao na kuficha zana za usimamizi wa zana (`tool_catalog`, `tool_load`, `unload_tool`).

______________________________________________________________________

## Chaguzi za seva ya A2A (`uaga`)

### `--host <address>`

Anwani ya kuunganishia seva ya A2A HTTP (kawaida: `0.0.0.0`, inaweza kubadilishwa na `UAGENT_A2A_HOST`).

### `--port <nambari>`

Nambari ya bandari kwa seva ya A2A HTTP (kawaida: `8765`, inaweza kubadilishwa na `UAGENT_A2A_PORT`).

### `--reload`

Wezesha upakiaji moto wakati wa mabadiliko ya msimbo (chaguo-msingi: imezimwa, inaweza kubadilishwa na `UAGENT_A2A_RELOAD`).

```
uaga --host 127.0.0.1 --port 8080 --reload
```

### `--tool-genre-mask <int>`

Chagua aina za zana kwa kutumia bitmask ile ile iliyoelezwa hapo juu. Inapobainishwa, ombi la aina ya zana linaloshirikiana linapuuzwa.

### `--use-tool` / `--no-use-tool`

Washa au zima kutuma ufafanuzi wa zana kwa LLM. Hupitiliza `UAGENT_USE_TOOL`.

### `--computer-use` / `--no-computer-use`

Washa au zima Matumizi ya Kompyuta. Inapuuza `UAGENT_COMPUTER_USE`.

### `--embedded`

Zima hifadhi ya kikao na kuficha zana za usimamizi wa zana (`tool_catalog`, `tool_load`, `unload_tool`).

______________________________________________________________________

## Vigezo vinavyohusiana vya mazingira

| Kigezo | Maelezo |
|---|---|
| `UAGENT_PROVIDER` | Jina la mtoa huduma wa LLM (linahitajika wakati wa kuanzisha) |
| `UAGENT_*_API_KEY` | Ufunguo wa API kwa mtoa huduma aliyechaguliwa |
| `UAGENT_WORKDIR` | Direktori chaguo-msingi ya kazi |
| `UAGENT_WEB_HOST` | Anwani ya seva ya wavuti inayofungwa (kawaida: `127.0.0.1`) |
| `UAGENT_A2A_HOST` | A2A Anwani ya seva inayofungwa (kawaida: `0.0.0.0`) |
| `UAGENT_A2A_PORT` | Bandari ya seva ya A2A (kawaida: `8765`) |
| `UAGENT_A2A_RELOAD` | Washa upakiaji upya wa papo kwa papo wa A2A kwa chaguo-msingi |
| `UAGENT_USE_TOOL` | Zima zana inapowekwa kuwa `0`, `false`, `no`, au `off` |
| `UAGENT_COMPUTER_USE` | Washa au zima Matumizi ya Kompyuta kwa chaguo-msingi |
| `UAGENT_SESSION_STORE` | Washa au zima hifadhi ya kikao; Hali ya kuingizwa inasababisha `0` |
| `UAGENT_PLUGIN_DIRS` | Saraka za ziada za utafutaji za programu-jalizi |
| `UAGENT_AUTO_SENTINEL` | Chagua hali ya sentineli ya kiotomatiki ya LLM-LLM wakati imewekwa kuwa `1` |
| `UAGENT_CONSECUTIVE_TOOL_CALL_LIMIT` | Kikomo cha wito wa zana mpya mfululizo (kawaida: `100`) |
| `UAGENT_MAX_TOOL_ROUNDS` | Idadi kubwa zaidi ya raundi za LLM/zana kwa kila operesheni ya mtumiaji (kawaida: `200`) |
| `UAGENT_SHRINK_CNT` | Kizingiti cha hiari cha kupunguza urefu wa ujumbe (`0`/haijawekwa = imezimwa) |
| `UAGENT_SHRINK_KEEP_LAST` | Ujumbe wa kuhifadhi baada ya kupunguza urefu (kawaida: `20`) |
| `UAGENT_LANG` | Lugha ya kiolesura (`ja`, `en`, n.k.) |

Kwa orodha kamili ya vigezo vya mazingira, tazama [ENVIRONMENT.md](ENVIRONMENT.md).

______________________________________________________________________

## Mifano

### Kuanza kwa kiwango cha chini na OpenAI

```
set UAGENT_PROVIDER=openai
set UAGENT_OPENAI_API_KEY=sk-...
uag
```

### Mfano wa ndani Ollama na zana za msingi tu

```
set UAGENT_PROVIDER=ollama
set UAGENT_OLLAMA_MODEL=qwen2.5:7b
uag --tool-genre-mask 1
```

### Seva ya wavuti kwenye miunganisho yote

```
set UAGENT_WEB_HOST=0.0.0.0
uagw
```

au

```
uagw --host 0.0.0.0
```

### A2A seva kwenye localhost na bandari maalum

```
uaga --host 127.0.0.1 --port 8080
```

### Zima zana kwa mfano mdogo

```
uag --no-use-tool --tool-genre-mask 1
```

### Usindikaji faili usioingiliani

```
uag --non-interactive README.md
```
