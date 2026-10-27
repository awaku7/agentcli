<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="680">
</p>

<h1 align="center">uag</h1>

<p align="center">
  <strong>Universal AI Gateway</strong><br>
  Wakala mmoja wa ndani. Muundo wowote. Zana yoyote. Mazingira yako, kanuni zako.
</p>

<p align="center">
  <a href="https://github.com/awaku7/agentcli/actions"><img src="https://img.shields.io/github/actions/workflow/status/awaku7/agentcli/ci.yml?style=flat-square&label=CI" alt="CI status"></a>
  <a href="https://pypi.org/project/uag/"><img src="https://img.shields.io/pypi/v/uag?style=flat-square" alt="PyPI version"></a>
  <a href="https://pypi.org/project/uag/"><img src="https://img.shields.io/pypi/pyversions/uag?style=flat-square" alt="Python versions"></a>
  <a href="https://github.com/awaku7/agentcli/blob/main/LICENSE"><img src="https://img.shields.io/github/license/awaku7/agentcli?style=flat-square" alt="License"></a>
  <a href="https://pepy.tech/projects/uag"><img src="https://static.pepy.tech/personalized-badge/uag?period=total&units=INTERNATIONAL_SYSTEM&left_color=grey&right_color=green&left_text=downloads" alt="PyPI Downloads"></a>
</p>

<p align="center">
  <a href="https://github.com/awaku7/agentcli">GitHub</a> ·
  <a href="https://pypi.org/project/uag/">PyPI</a> ·
  <a href="https://github.com/awaku7/agentcli/discussions">Discussions</a> ·
  <a href="https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md">Translations</a>
</p>

______________________________________________________________________

**Kwa nini uag?**

uag ni wakala wa AI unaotanguliza matumizi ya ndani, unaounganisha muundo unaopendelea na zana unazotumia kwa kweli.
Unakupa mazingira moja yanayoweza kupanuliwa kwa faili, vivinjari, misingi ya msimbo, mawasiliano, API za wingu,
vifaa vya IoT, seva za MCP, na mtiririko wa kazi wa mawakala wengi.

- **Uhuru wa mtoa huduma** — OpenAI, Anthropic, Gemini, Azure, Bedrock, Ollama, llama.cpp, Grok, DeepSeek, na wengine.
- **Utekelezaji wa ndani kwanza** — mazingira ya wakala wako na utekelezaji wa zana hubaki kwenye mashine yako; ni miito ya API unayochagua pekee inayotoka.
- **Tabaka moja la zana** — zana zilezile hufanya kazi kutoka CLI, GUI ya eneo-kazi, kiolesura cha wavuti, VS Code, na A2A.
- **Imeundwa kwa uendeshaji sambamba** — operesheni huru za kusoma pekee zinaweza kuendeshwa kwa wakati mmoja.
- **Inaweza kupanuliwa** — ongeza zana, programu-jalizi, Agent Skills, seva za MCP, na zana zinazoendeshwa na Rust bila kubadilisha msingi.
- **Inazingatia usalama** — vitendo vya uharibifu, vitambulisho, vidhibiti vya vifaa, na uandishi wa mtandao vinaweza kutumia uthibitisho wa wazi na vidhibiti vya sera.

> **Kwa kifupi:** uag ni ndege ya udhibiti kati ya miundo yako ya AI na mazingira yako halisi.

> **🧠 Matokeo ya zana yanayozingatia muktadha** — Matokeo makubwa ya zana huhifadhiwa nje ya muktadha wa modeli inayotumika inapowezekana. uag huzihifadhi kama Artifacts na kumpa mfano muonekano mdogo uliopimwa wenye rejea thabiti ya Artifact badala yake. Hii inaweza kupunguza kwa kiasi kikubwa idadi ya tokeni za ingizo zinazohitajika kwa zamu zinazofuata wakati zana inapotengeneza matokeo makubwa.
> [Mwongozo wa kina wa kubana muktadha](CONTEXT_COMPRESSION.sw.md)

## Anza haraka

**Python 3.11+**

```bash
python -m pip install --upgrade uag
uag
```

Uzinduzi wa kwanza hufungua mchawi wa usanidi. Husaidia kusanidi mtoa huduma na kuhifadhi mipangilio iliyochaguliwa
kwenye mazingira yako ya ndani.

Kwa makundi ya kawaida ya vipengele:

```bash
python -m pip install "uag[core,providers,tools]"
```

> Miunganisho ya mifumo ni ya hiari. Sakinisha tu kile ambacho mfumo wako wa uendeshaji unahitaji; tazama

```text
> What files changed in this repository?
> Search the web for today's AI news and summarize the top five stories.
> :help
```

[Quickstart](QUICKSTART.md) · [Environment](ENVIRONMENT.md)

## Miingiliano

| Interface | Command | Best for |
|---|---|---|
| **CLI** | `uag` | Kazi ya haraka, inayotanguliza kibodi |
| **Desktop GUI** | `uagg` | Uzoefu asilia wa eneo-kazi |
| **Web UI** | `uagw` | Ufikiaji unaotegemea kivinjari |
| **A2A server** | `uaga` | Mawasiliano kati ya mawakala |
| **VS Code** | Extension | Eleza, rekebisha muundo, tatua, na vinjari zana kwenye kihariri |

Miingiliano yote hushiriki usanidi uleule wa mtoa huduma, sajili ya zana, kanuni za usalama, na data ya kikao.

~~~bash
# Desktop GUI
python -m pip install "uag[platform]"

# Web UI
python -m pip install "uag[web]" fastapi uvicorn
~~~

[Interface options](USAGE.md) · [Environment](ENVIRONMENT.md)

## Unachoweza kujenga

Adapta za watoa huduma hushughulikia mazingira ya mbali na ya ndani, ikijumuisha:

**OpenAI · Anthropic · Gemini · Vertex AI · Azure OpenAI · Amazon Bedrock · Grok · DeepSeek · OpenRouter · Ollama · llama.cpp · LM Studio**

- Soma, unda, hariri, tafuta, hesabu hash, hifadhi kwenye kumbukumbu, na kagua faili
- Kagua mabadiliko ya Git, tafuta siri, endesha majaribio, lint, kusanya, na pima coverage
- Vinjari misingi mikubwa ya Python, TypeScript, JavaScript, Go, Rust, C/C++, Java, C#, COBOL, VBA, na mingine
- Otomatisha vivinjari kwa Playwright, ikijumuisha mtiririko wa kurasa nyingi na upakuaji

- **MCP** — unganisha seva za zana za nje, ikijumuisha huduma zilizo na OAuth
- **A2A** — ratibu na mawakala wengine na seva zinazooana
- **Cloud** — ufikiaji wa API za AWS, Google Cloud, na Azure ukiwa na uthibitisho wa uandishi
- **Communication** — Gmail, Bluesky, Discord, Microsoft Teams, na pybitchat
- **IoT** — SwitchBot, ECHONET Lite, Matter, BACnet, Modbus TCP, OPC UA, na UPnP
- **Media** — uundaji/uhariri wa picha, unukuzi/utamkaji wa sauti, kunasa kamera, na misimbo ya QR
- **Documents** — PDF, PowerPoint, Word, Excel, CSV, JSON, YAML, SQL, na uchanganuzi wa logi

- **SwitchBot** — ugunduzi wa Cloud na BLE, hali, udhibiti, batching, na subscriptions
- **ECHONET Lite** — gundua na udhibiti vifaa vya nyumbani vya Japani, ikijumuisha arifa za INF
- **Matter** — endpoints, clusters, attributes, historia ya hali, subscriptions, na udhibiti
- **BACnet / Modbus TCP / OPC UA** — usomaji, uandishi, uvinjari, na ufuatiliaji wa otomatiki za viwandani na majengo
- **UPnP** — ugunduzi wa vifaa, hali ya WAN, na usimamizi wa ramani za bandari za router

### Nafasi ya uag

uag iko kati ya watu na miingiliano upande mmoja, na miundo, zana, pamoja na mifumo ya ulimwengu halisi upande mwingine.
Inaratibu mazungumzo, huchagua uwezo, hutumia kanuni za usalama, na huweka mtiririko wa kazi uweze kuendelezwa.

~~~mermaid
flowchart LR
    UI["CLI · Desktop · Web · VS Code · A2A"] --> UAG["UAG agent runtime"]
    UAG --> MODELS["Hosted & local models"]
    UAG --> TOOLS["Tools & extensions"]
    UAG --> STATE["Sessions & context"]
    TOOLS --> SYSTEMS["Files · Code · Web · MCP · Cloud · IoT"]
    POLICY["Confirmation · Credentials · Policy"] -.-> UAG
~~~

### Programu-jalizi, Agent Skills, na marketplaces

Geuza uag kuwa wakala maalum bila kuigawanya msingi:

- Sakinisha **programu-jalizi zinazooana na Claude Code** kutoka saraka, ZIP, hazina ya Git, chanzo cha HTTP, au marketplace
- Funga pamoja skills, sub-agents, seva za MCP, hooks, slash commands, mitindo ya matokeo, dependencies, na channels
- Vinjari uwezo wa jumuiya kutoka [SkillsMP](https://skillsmp.com) na [ClawHub](https://clawhub.ai)
- Ongeza skills na zana za shirika binafsi kupitia `UAGENT_EXTERNAL_TOOLS_DIR`

```text
:skills mp_search browser automation
:plugin list
:plugin install <source>
:plugin marketplace list
```

Tazama [Plugin Development Guide](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP_PLUGIN.md).

- **Zana 200+** za faili, wavuti, media, nyaraka, msimbo, wingu, mawasiliano, na IoT
- **Ugunduzi na upakiaji wa nguvu** — tumia `tool_catalog` kupata uwezo na `tool_load` kuiwezesha inapohitajika pekee
- **Uelewa wa msimbo** — `code_map`, viongozaji vya `idx` vya lugha mahususi, ukaguzi wa Git, utekelezaji wa majaribio, linting, ukusanyaji, na coverage
- **Programu-jalizi zinazooana na Claude Code** zenye skills, agents, seva za MCP, hooks, commands, na marketplaces
- **Agent Skills** kutoka SkillsMP na ClawHub
- **Zana maalum za Python** zenye `TOOL_SPEC` na `run_tool()`
- **Zana zinazoendeshwa na Rust** kwa viendelezi asilia vyepesi

[Tool Creator Guide](../TOOL_CREATOR_GUIDE.md) · [MCP OAuth / Proxy Guide](MCP_OAUTH_PROXY_GUIDE.md)

## Imeundwa kwa ajili ya mtiririko halisi wa kazi

### 🧠 Matokeo ya zana yanayozingatia muktadha

Matokeo makubwa ya zana huhifadhiwa nje ya muktadha wa modeli inayotumika inapowezekana. uag huzihifadhi kama Artifacts na kumpa mfano muonekano mdogo uliopimwa wenye rejea thabiti ya Artifact badala yake. Hii inaweza kupunguza kwa kiasi kikubwa idadi ya tokeni za ingizo zinazohitajika kwa zamu zinazofuata wakati zana inapotengeneza matokeo makubwa.

Endeleza mazungumzo yaliyotangulia kwa `:load <index>`. Matokeo ya zana yanaweza kuhifadhiwa, na watoa huduma wanaweza kubadilishwa
bila kujenga upya programu.

[Context compression](CONTEXT_COMPRESSION.sw.md) · [Memory](MEMORY.md) · [Session portability](SESSION_PORTABILITY.md)

### Uendeshaji wa kiotomatiki

Tumia `:auto` kwa kazi za raundi nyingi ukiwa na modeli ya mkaguzi ya hiari. Weka kikomo cha raundi kwa `--max-rounds N`.
Bonyeza **F12** kusimamisha uendeshaji wa kiotomatiki au **F12** kusimamisha jibu la sasa.

Operesheni huru za kusoma pekee huendeshwa kwa wakati mmoja inapokuwa salama. Utafutaji wa wavuti, ukaguzi wa faili,
uchanganuzi wa hazina, na kazi kama hizo zinaweza kukamilika sambamba kwa kutumia kundi la wafanyakazi linaloweza
kusanidiwa (`UAGENT_PARALLEL_WORKERS`). Operesheni za kuandika hubaki za mfululizo au huhitaji uthibitisho.

Muendelezo wa vikao, uhifadhi wa matokeo ya zana, hali ya batch, urejeshaji baada ya kuanzisha upya, upangaji wa DAG, na
uratibu wa mawakala wengi hufanya kazi changamano ziweze kuendelea badala ya kuwa za mara moja.

[Auto-pilot](README_AUTO.md) · [Timers](SET_TIMER.md) · [Multi-agent runtime](MULTI_AGENT_RUNTIME.md)

### 🌍 Binafsi, ya lugha nyingi, na inayozingatia sera

`human_ask` husitisha kabla ya vitendo nyeti. Kufuta faili, kuandika juu, amri za shell, vidhibiti vya vifaa,
operesheni za vitambulisho, na uandishi wa mtandao vinaweza kusimamiwa na kanuni za uthibitisho na sera.

Tumia hifadhi ya vitambulisho badala ya kuweka siri za muda mrefu kwenye vidokezo:

UI ya Wavuti inajumuisha kuingia kwa OIDC kwa kutumia Authorization Code + PKCE, tokeni za ID zilizothibitishwa, vikao vya upande wa seva, na udhibiti wa upatikanaji wa mradi/chumba. Dhamana za vikundi zilizothibitishwa za Microsoft Entra ID zinaweza kuingiza sera za upatikanaji zinazotegemea saraka wakati zimewekwa. Usambazaji wa Windows Active Directory, OAuth, na trusted-proxy unaweza kuunganishwa kupitia adapta za utambulisho zilizothibitishwa za kipekee; Windows AD inahitaji kithibitishaji cha Kerberos/Negotiate maalum kwa kila deployment, na hali hii haijawezeshwa kwa chaguo-msingi.

uag inajumuisha kuchagua kuingia, kufuatilia OpenTelemetry bila mtoa huduma na vipimo vya Agent, LLM, zana, Context, Memory na shughuli za kurejesha. Uangalizi umezimwa kwa chaguo-msingi.

Kutanguliza utekelezaji wa ndani hakumaanishi kuwa UAG hufanya kazi bila intaneti kabisa au kuwa zana zote zimetengwa kwa chaguomsingi. Miito kwa modeli na huduma za nje hutegemea usanidi.

- [Enterprise policies](ENTERPRISE_POLICY.md)
- [MXC sandbox](SANDBOX_MXC.md)
- [Remote Web / A2A](REMOTE_MXC_DEFAULT.md)
- [Web identity](WEB_IDENTITY_MEMORY.md)
- [OpenTelemetry](UAG_OPENTELEMETRY_DESIGN.md)

### 🌍 Tafsiri ya lugha nyingi

- `translate_text` inaunga mkono Google Translate na mteja rasmi wa DeepL Python kupitia `provider=auto`, `provider=deepl`, au `provider=google`.
- Ufafanuzi wa zana unapatikana katika lugha 37 pamoja na Kiingereza (jumla 38), huku nafasi za kuweka maandishi na vitambulisho vya kiufundi vikihifadhiwa.

Sauti ya pande mbili inapatikana kupitia OpenAI Realtime, Azure OpenAI, xAI Grok Voice, Gemini Live,
na Bedrock Nova Sonic, ikiwa na uondoaji wa mwangwi wa AEC3 wa hiari na miito ya vitendaji ya wakati halisi yenye mipaka ya usalama.

[Translations](README.translations.md) · [IoT](IOT_USECASE.md) · [Communication](COMMUNICATION.md)

## Nyaraka

| Topic | Documentation |
|---|---|
| Environment variables | [docs/ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/docs/ENVIRONMENT.md) |
| Architecture and invariants | [docs/ARCHITECTURE.md](https://github.com/awaku7/agentcli/blob/main/docs/ARCHITECTURE.md) |
| Computer Use | [docs/COMPUTER_USE_IMPLEMENTATION.md](https://github.com/awaku7/agentcli/blob/main/docs/COMPUTER_USE_IMPLEMENTATION.md) |
| Repository tools | [docs/REPOSITORY_TOOLS.md](https://github.com/awaku7/agentcli/blob/main/docs/REPOSITORY_TOOLS.md) |
| IoT use cases | [docs/IOT_USECASE.md](https://github.com/awaku7/agentcli/blob/main/docs/IOT_USECASE.md) |
| Communication tools | [docs/COMMUNICATION.md](https://github.com/awaku7/agentcli/blob/main/docs/COMMUNICATION.md) |
| Auto-pilot | [docs/README_AUTO.md](https://github.com/awaku7/agentcli/blob/main/docs/README_AUTO.md) |
| MCP OAuth / Proxy | [docs/MCP_OAUTH_PROXY_GUIDE.md](https://github.com/awaku7/agentcli/blob/main/docs/MCP_OAUTH_PROXY_GUIDE.md) |
| VS Code extension | [docs/VSCODE.md](https://github.com/awaku7/agentcli/blob/main/docs/VSCODE.md) |
| Developer guide | [src/uagent/docs/DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md) |
| Tool flow | [src/uagent/docs/TOOL_FLOW.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/TOOL_FLOW.md) |

[Quickstart](QUICKSTART.md) · [Architecture](ARCHITECTURE.md) · [Context management](UAG_CONTEXT_MANAGEMENT_DESIGN.md)

## Maendeleo na uchangiaji

```bash
git clone https://github.com/awaku7/agentcli.git
cd agentcli
python -m pip install -e ".[core,providers,test]"
```

Endesha ukaguzi wa kabla ya PR:

```bash
python -m ruff check src tests
python -m black --check src tests
python -m pytest -q .
```

Kwa mtiririko kamili wa maendeleo, tazama [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md).

Ripoti za hitilafu, mawazo ya vipengele, maboresho ya nyaraka, tafsiri, zana, skills, na pull requests zinakaribishwa.
Tafadhali fungua issue au mjadala kabla ya mabadiliko makubwa. Soma [Developer Guide](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)
na endesha ukaguzi ulio hapo juu kabla ya kutuma pull request.

## Leseni

Imepewa leseni chini ya [Apache License 2.0](https://github.com/awaku7/agentcli/blob/main/LICENSE).
