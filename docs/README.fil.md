<p align="center">
 <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="720">
</p>

<h1> Universal align="AI_center" Gateway</h1>

<p align="center">
 <b>U</b>niversal <b>A</b>I <b>G</b>ateway — Ang iyong kapaligiran, ang iyong kalayaan.
</p>

<p align="center">
 File ops / Web search / Pagbuo ng PDF at Paggawa ng larawan at Pagsusuri ng PH_3 pagsasama<br>
 24 provider / 3 UI / Parallel tool execution / Agent Skills marketplace
</p>

<p align="center">
 <a href="https://github.com/awaku7/agentcli">GitHub</a>
 ·
 <a> href="https://pypi.org/project/uag/">PyPI</a>
 ·
 <a href="https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md">Basahin ito sa iyong wika</a>
</p>
________________

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_## Bakit uag?

**Lumabas sa vendor lock-in.** Karamihan sa mga AI assistant ay itinatali ka sa isang partikular na provider o cloud service. Iba ang uag.

- **Tumatakbo nang lokal** sa iyong makina. Mananatili sa iyo ang iyong data (maliban sa API na tawag na gagawin mo).
- **Kalayaan ng provider**: OpenAI, Claude, Gemini, DeepSeek, Ollama, Azure, Bedrock, Novita, HuggingFace... 24 na provider, lahat ay naa-access mula sa isang interface. Magpalit sa pagitan ng mga ito sa pamamagitan ng muling pag-configure ng mga variable sa kapaligiran — walang muling pag-install, walang paglilipat.
- **222 na tool**: File I/O, paghahanap sa web, pagbuo ng larawan, Gmail, BLE device scanning, MCP server integration — **130 ay statically marked parallel-safe** (hanggang 8 execute nang sabay-sabay sa pamamagitan ng thread pool`EL`GENT_WORK). Kapag ang LLM ay nagpagana ng maraming tool call nang sabay-sabay, uag ay awtomatikong ipapaparallelize ang mga ito.
- **3 UI + A2A**: CLI, GUI, Web, at Agent-to-Agent protocol. Parehong engine, anumang interface.
- **IoT ready**: SwitchBot, ECHONET Lite, Matter, UPnP — kontrolin ang iyong mga device sa bahay sa pamamagitan ng AI.
- **Agent Skills**: Mag-install ng mga kasanayang binuo ng komunidad mula sa marketplace. Palawakin ang uag nang walang hanggan.

uag ay **iyong AI assistant sa iyong mga tuntunin**. Hindi nakatali sa isang provider, hindi nakatali sa isang interface, hindi nakatali sa isang platform.

## Mabilis na Pagsisimula

```bash
pip install uag
uag
```

Sa unang paglunsad, gagabayan ka ng setup wizard sa configuration ng provider.
Tingnan ang [docs/ENVIRONMENT.md](https://github.com/awaku7/enRONclidoc.mblob/agentRONclidoc.mblo) mga variable.

## Computer Use

Computer Use ay nag-opt-in at sumusuporta sa parehong nakikitang Playwright browser runtime
at isang desktop runtime. Kapag pinagana, ang parehong mga runtime ay ginawa at nairehistro;

````bat
set UAGENT_COMPUTER_USE=1
`top` sa halip ay piliin ang desktop na runtime`
`top`
. Ang Runtime na mapagkukunan ay
sarado sa normal na paglabas, `Ctrl-C`, at pagsara ng proseso. Itakda ang
`UAGENT_COMPUTER_HEADLESS=1` para sa CI o smoke test na nakabatay sa browser.
Tingnan ang [docs/COMPUTER_USE_IMPLEMENTATION.md](docs/COMPUTER_USE_IMPLEMENTATION.md)
para sa mga detalye ng pagsasama at kaligtasan.

## Realtime Voice at AEC3

Sinusuportahan ng realtime voice mode ang OpenAI Realtime, Azure OpenAI GPT Realtime, xAI Grok Voice API, Google Gemini Multimodal Live API, at Amazon Bedrock Nova Sonic at speaker na I-duplex na may full-duplex na I-duplex. Awtomatikong na-install ang kinakailangang `pywebrtc-audio` AEC3 backend, at ang opsyonal na bidirectional-streaming SDK ng Bedrock ay awtomatikong na-install lamang kapag napili ang provider ng Bedrock:

```bash
python scheck.py realtime
````

Ang AEC3 na pipeline ng mikropono ay tumatanggap ng aktwal na signal ng audio ng mikropono (`neaktwal na mikropono) (`malayo\`) para makinig ang katulong habang nagsasalita. I-enable lang ang diagnostics kapag nagsisiyasat ng mga isyu sa audio:

```bat
set UAGENT_REALTIME_AUDIO_DEBUG=1
python scheck.py realtime
```

### OpenAI Realtime Function Calling

OpenAI Realtime na Function Calling

OpenAI Sinusuportahan ng Realtime na Pagsasama ng Function ang Realtime na Pagsasama. Ang kasalukuyang realtime adapter ay awtomatikong naglalantad ng read-only na `get_current_time`. Ang mga mapanirang tool at kontrol ng device ay hindi nakalantad nang walang tahasang allowlist at daloy ng kumpirmasyon. Gumagamit ang Grok realtime ng hiwalay na adapter at hindi ginagamit ang path na ito ng OpenAI na partikular na function-call.

## Mga Tampok

### 🧠 Multi-Provider Architecture

OpenAI / PFN (PLaMo) / Azure / Bedrock / OpenRouter / Ollama / llama.cpp / Gemini / Vertex AI / Claude / Grok / NVIDIA / Novita. Cloud (Qwen) / KIMI (Moonshot AI) / Xiaomi MiMo / LM Studio / MiniMax / Sakana AI (Fugu) / SAKURA AI Engine / Together AI / Vercel AI Gateway

Ang lahat ng provider ay nagbabahagi ng parehong toolset at interface. Lumipat sa pamamagitan ng pagtatakda ng `UAGENT_PROVIDER` — walang pagbabago sa code, walang hiwalay na pag-install.

#### Ollama at llama.cpp

Ollama at llama.cpp ay magkahiwalay na provider. Gumagamit si Ollama ng sarili nitong serbisyo at pamamahala ng modelo, habang kumokonekta ang `llama.cpp` sa isang `llama-server` OpenAI-compatible na endpoint:

```bash
# Ollama
UAGENT_PROVIDER=ollama
UAGENT_OLLAMA_BASE_URL=http://localhost:11434/v1
UAGENT_OLLAMA_DEPNAME=llama3.1

# llama.cpp / llama-server
UAGENT_PROVIDER=llama_cpp
UAGENT_LLAMA_CPP_BASE_URL=http://localhost:8080/v1
UAGENT_LLAMA_CPP_DEPNAME=local-model
UAGENT_LLAMA_CPP_API_KEY`=`dummy
 ang provider. Completions-compatible path. Panatilihin ang `UAGENT_RESPONSES=0` maliban kung ang isang katugmang proxy ay na-configure.

### ⚡ Parallel Tool Execution

Kapag ang LLM ay humiling ng maramihang mga tool nang sabay-sabay, uag **awtomatikong ipinaparallelize** ang mga ito. 
130 `parallel na tool ay stax_safety_marked_tools sabay-sabay sa pamamagitan ng `ThreadPoolExecutor` (8 thread bilang default; itakda ang `UAGENT_PARALLEL_WORKERS` upang baguhin).

**Halimbawa**: Itanong ang "Suriin ang lagay ng panahon sa Nordic capitals" → LLM fires `search_web` × 5 bansa → lahat ng 5 pangkat → parallel na paghahanap ay tumatakbo sa mga resulta ng 
 → parallel → para sa kasalukuyang paghahanap. ang bilang ay batay sa mga module ng tool na tumutukoy sa isang `TOOL_SPEC` (kasalukuyang 222, kasama ang 2 Rust-backed na tool sa `src/uagent/tools_rust/`). Gumagamit ang `http_request` ng kaligtasan na sensitibo sa pamamaraan: Ang mga tawag na `GET`/`HEAD`/`OPTIONS` ay maaaring tumakbo nang magkatulad, habang ang mga paraan ng pagsulat ay nananatiling serial.

Read-only na mga tool (paghahanap ng file, pagkalkula ng hash, listahan ng direktoryo, pagsasalin, mga query sa DB, atbp.) ay agresibong parallelized.### 
 System ng Plugin Compatible)

uagent ay nagpapatupad ng **Claude Code-compatible na plugin system**. Mga kasanayan sa bundle ng plugin, ahente, MCP server, hook, at higit pa sa mga self-contained na direktoryo na may manifest na `.claude-plugin/plugin.json`.

**Mga sinusuportahang bahagi**: Mga Kasanayan, Sub-agents, MCP server, Hooks (12 mga kaganapan sa lifecycle ng user), Mga utos ng Slash sa istilo ng Output, Mga utos ng Output na Channel Marketplaces

**CLI commands**:

```

:listahan ng plugin # Listahan ng mga naka-install na plugin
:plugin install <source> [--scope] # Install (dir/zip/git/http)
:plugin install <name>@<marketplace> # <install from marketplace
:plugin remove> I-toggle
:plugin marketplace add/remove/list # Manage marketplaces
:plugin init <name> # Scaffold new plugin

````

Tingnan ang [DEVELOP_PLUGIN.md](src/uagent/docs/DEVELOP_PLUGIN.md) para sa buong dokumentasyon. Continuity

- **Lumipat ng mga provider sa kalagitnaan ng session** gamit ang `UAGENT_PROVIDER` — pinapanatili ang history ng pag-uusap.
- **I-reload ang mga nakaraang session** gamit ang `:load <index>` — ituloy kung saan ka huminto.
- **Pag-cache ng resulta ng tool** ay iniiwasan ang paulit-ulit na muling pagpapatupad kapag umuulit ang parehong tool call⛠9





2###. Mga tool

| Kategorya | Mga Tool |
|---|---|
| **Pagpapatakbo ng File** | magbasa/magsulat/lumikha/magtanggal/maghanap/grep/hash/zip, file_type, parse_eml (.eml file), `path_alias` |
| **Web** | fetch_url, search_web, screenshot, browser_playwright, `url_alias`, `public_transit_route` ([gabay](docs/PUBLIC_TRANSIT_ROUTE.md)) |
| **Media** | generate_image, analysis_image, img2img, audio_speech, audio_transcribe |
| **Mga Dokumento** | PDF/PPTX/DOCX/RTF/ODT extraction, Excel structured extraction |
| **Pagtataya** | Pagtataya ng serye ng oras na may 9 na modelo (AutoARIMA, Propeta, LightGBM, CatBoost, TimesFM, atbp.), pagpili ng awtomatikong modelo, pagbuo ng plot, i18n |
| **Komunikasyon** | gmail_send, gmail_read, bluesky, discord_channel, teams_webhook, **pybitchat** (BLE Mesh) — tingnan ang [COMMUNICATION.md](https://github.com/awaku7/agentcli/blob/main/docs/COMMUNICATION.md) at [BITCHAT.md](https://github.com/awaku7/agentcli/blob/main/docs/BITCHAT.md) |
| **IoT** | SwitchBot (Cloud + BLE), ECHONET Lite, Matter, UPnP, reverse_geocode |
| **Mga Cloud API** | `aws_api`, `gcp_api`, `azure_api` — generic na operasyon ng AWS, Google Cloud, at Azure API; ang mga pagpapatakbo ng pagsulat ay nangangailangan ng tahasang kumpirmasyon |
| **Dev Tools** | workspace_status, git_ops, git_review, security_scan, coverage_report, python_compile, lint_format, run_tests, db_query, **29 source code navigators (idx family)** |
| **MCP** | Kumonekta sa mga panlabas na MCP server, listahan ng mga tool, i-execute — [OAuth / Proxy guide](docs/MCP_OAUTH_PROXY_GUIDE.md) |
| **A2A** | Komunikasyon ng ahente-sa-agent (kasama ang iba pang uag instance o A2A-compatible na server) |
| **System** | env vars, specs ng system, oras, pagkalkula ng petsa, [mga dami](docs/QUANTITIES.md), [geodesic_distance](docs/GEODESIC_DISTANCE.md), uuid_gen, slugify |
| **Source Nav** | **29 idx tools** para sa Python, PHP, TypeScript, Java, C#, Dart, C/C++, Rust, Go, Swift, Kotlin, COBOL, VBA, LotusScript, Makefile — kumuha ng function/class index o partikular na kahulugan nang hindi binabasa ang buong file |

#### Repository na pagsusuri at saklaw ng workspace `:
 branch, mga pagbabago, upstream na estado ng pag-sync, Python runtime, at karaniwang mga marker ng proyekto nang hindi binabago ang mga file.
- `git_review`: ibuod ang mga pagbabago sa Git, mga mapanganib na file, mga kandidato sa pagsubok, at mga lihim na natuklasan nang hindi inilalantad ang mga lihim na halaga.
- `security_scan`: i-scan ang mga repositoryo ng mga file para sa malamang na mga lihim at mapanganib na configuration file`, at 
-PH_report sa normal na mga file ng configuration. TypeScript/JavaScript, Rust, Go, Java/Kotlin, .NET, C/C++, Ruby, PHP, Swift, at Dart/Flutter.
- Maaaring awtomatikong mai-install ang mga nawawalang dependency sa coverage kapag hiniling ang pagpapatupad; Ang `dry_run` ay hindi kailanman nag-i-install ng mga package.

Tingnan ang [Repository Analysis Tools](docs/REPOSITORY_TOOLS.md) para sa mga parameter, output, at mga detalye ng kaligtasan.

Tingnan ang [Path at URL aliases](docs/PATH_URL_ALIASES.md) para sa paikliin sa mga paulit-ulit na file path ▎ at URL.## 4 na Interface + VS Code Extension

| Mode | Utos | Layunin |
|---|---|---|
| **CLI** | `uag` | Mabilis na terminal-based na operasyon |
| **GUI** | `uagg` | Desktop UI sa pamamagitan ng tkinter |
| **Web** | `uagw` | Browser-based na access |
| **A2A Server** | `uaga` | Agent2Agent protocol para sa multi-agent na komunikasyon |
| **VS Code** | — | [Extension](https://github.com/awaku7/agentcli/blob/main/docs/VSCODE.md) na may Chat Panel, Explain, Refactor, Fix Error, at Tools Tree View |

Tingnan ang [VSCODE.md](https://github.com/awaku7/agent/docsm/blob) extension — pag-install, mga command, keybinding, at configuration.

### 🏠 IoT Device Control

- **BACnet**: Magbasa/magsulat ng mga BACnet/IP device (HVAC, lighting, power meter). COV subscription para sa mga push notification
- **Modbus TCP**: Magbasa/magsulat ng mga holding/input register at coils. Pagsubaybay sa pagbabago na nakabatay sa botohan
- **OPC UA**: Mag-browse ng address space, magbasa/magsulat ng mga variable, mag-subscribe sa mga pagbabago sa data
- **SwitchBot**: Cloud batch control at BLE scan/control. Subscription na nakabatay sa botohan
- **ECHONET Lite**: Tuklasin, kontrolin, at mag-subscribe sa mga notification ng INF mula sa mga appliances sa bahay (AC, ilaw, water heater, atbp.)
- **Bagay**: Kontrol sa pagbasa/sulat + subscription sa attribute para sa pagsubaybay sa pagbabago ng estado
- **UPnP**: Pagtuklas ng device at pagpapasa ng IGD port

Tingnan [IOT_USECASE.md](https://github.com/awaku7/agentcli/blob/main/docs/IOT_USECASE.md)

### 🎯 Agent Skills Marketplace

`:skills mp_search` para mag-browse sa [SkillsMP](https://skillsmp.comlawHub)](https://skillsmp.comlawHub) kasanayan.
I-install at palawakin ang mga kakayahan ng uag sa mabilisang.

### 🤖 Auto-Pilot (`:auto`)

uag ay maaaring **awtonomyang ituloy ang isang layunin sa maraming LLM round**. Tamang-tama para sa mga kumplikado, maraming hakbang na gawain na nangangailangan ng umuulit na pagpipino.

- **Paano ito gumagana**: Ang bawat round ay may pangunahing query (Hakbang A) na sinusundan ng paghatol ng reviewer (Hakbang B) na nagpapasya sa "KUMPLETO o MAGPATULOY?"
- **Parehong provider, parehong API**: Ang paghuhusga ng reviewer ay gumagamit ng kaparehong query code na path_3 — kasama ang path ng suporta sa query_3 — kabilang ang path ng suporta sa query_3. **Hiwalay na hukom LLM** (opsyonal): Itakda ang `UAGENT_AP_PROVIDER` na gumamit ng ibang provider/modelo para sa reviewer (hal. gumamit ng mas murang modelo para sa paghusga).
- **Lumabas anumang oras**: Pindutin ang F11 upang ihinto kaagad, kahit sa kalagitnaan ng pagtugon. O hayaan ang reviewer na magpasya kung kailan natugunan ang layunin.
- **Configurable**: `--max-rounds N` para kontrolin ang badyet.

Tingnan ang [README_AUTO.md](https://github.com/awaku7/agentcli/blob/main/docs/README_AUTO.md) 
 
 
 Estado para sa buong dokumentasyon. Maaaring subaybayan ng Manager

uag ang pag-unlad sa mga matagal nang multi-file na gawain. Kapag ang LLM ay nagpoproseso ng dose-dosenang mga file, ang `batch_state` ay nagpapatuloy sa listahan ng mga nakabinbin, nakumpleto, at nabigong mga file sa disk. Kung matatapos ang session o magtatapos ang isang round, magpapatuloy ang susunod na pagtakbo mula sa kung saan ito huminto — walang mawawala.

### 🛡 Human-in-the-Loop

`human_ask` hinahayaan ang LLM na i-pause at hingin ang iyong kumpirmasyon bago magsagawa ng mga mapanirang operasyon (pagtanggal ng file, pag-overwrite, mga shell). Mananatili kang may kontrol.

### 🛑 Interrupt (F12 / Stop button)

Stop LLM response generation anumang oras at mag-inject ng stop command pabalik sa LLM.

| Interface | Paano matakpan |
|---|---|
| **CLI** | Pindutin ang F12 habang nag-stream ng LLM — hihinto ang kasalukuyang tugon, at ipapadala ang `"Stop"` bilang mensahe ng user upang tumugon nang naaayon ang LLM |
| **WEB UI** | I-click ang pulang **■ Stop** button (awtomatikong lilitaw sa panahon ng pagproseso ng LLM) |
| **Desktop GUI** | I-click ang pulang **■** na buton (awtomatikong lilitaw sa panahon ng pagpoproseso ng LLM) |

Gumagana ang interrupt bilang "prompt injection": sa halip na i-abort lang, ibinabalik nito ang `"Stop"` pabalik sa LLM bilang isang mensahe ng user, na nagbibigay-daan dito na maayos na tapusin o kilalanin ang pagkaantala.
 
 
 
 
 
 
 
 
 
 [README_AUTO.md](https://github.com/awaku7/agentcli/blob/main/docs/README_AUTO.md)).

### 🕵️ Browser Automation at Web Inspector

Dalawang pantulong na Playwright
nakabatay sa mga tool sa paglalaro ng browser:

 — mag-navigate, mag-click, punan ang mga form, kunin ang data, pangasiwaan ang mga daloy ng maraming pahina. Gumagana nang walang ulo o ulo.
- **playwright_inspector**: Mag-record ng mga transition ng browser, kumuha ng mga snapshot at screenshot ng DOM sa bawat hakbang. Kapaki-pakinabang para sa pag-debug ng mga pakikipag-ugnayan sa web o pag-audit ng mga pagbabago sa page sa paglipas ng panahon.

### 🔄 Dynamic na Tool Loading

`tool_catalog` at `tool_load` ay nagbibigay-daan sa iyong matuklasan at paganahin ang mga tool sa runtime.
Hindi na kailangang i-load ang lahat sa startup — i-activate lang ang kailangan mo, kapag kailangan mo ito.### 
⏦ Ang mga tool

`uuid_gen` at `slugify` ay ipinapatupad sa Rust (sa pamamagitan ng PyO3) para sa pagganap. 
Naglo-load ang mga ito nang direkta mula sa isang pre-built na `.pyd` — **walang kinakailangang `pip install`**.

Maaari ding ipadala ng mga external na developer ang Rust-based na mga tool: maglagay ng `.pyd`ra sa tabi ng `.pyd`w `load_rust_pyd()` mula sa `uagent.tools.rust_helper`, at
nakukuha ng mga user ang tool nang walang anumang karagdagang dependency. Tingnan ang
[TOOL_CREATOR_GUIDE.md](https://github.com/awaku7/agentcli/blob/main/TOOL_CREATOR_GUIDE.md).

### 🌐 i18n / L10n

日本語 / English / 简䖇 / 中文 /中文한국어 / Español / Français / Русский / at higit pa.
Itakda ang `UAGENT_LANG` upang lumipat. Tingnan ang [ADD_LOCALE.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/ADD_LOCALE.md) para magdagdag ng bagong locale.

Ang mga pagsasalin nitong README ay available sa [docs/README.translations.md](https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md) file.
Pamahalaan gamit ang `uag_envsec`.

## Configuration at Mga Detalye

- **Mga variable ng kapaligiran**: [docs/ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/docs/ENVIRONMENT.md)
- **Setup wizard**: `python -m uagent⎏edcryptv __uagent. `uag_envsec` — i-encrypt ang `.env` bilang `.env.sec`
- **Mga Tugon API**: Itakda ang `UAGENT_RESPONSES=1` para sa Mga Tugon API mode (OpenAI/Azure/Bedrock/OpenRouter/Ollama/Alibaba/LM Studio/Sakana AI). Auto-enabled para sa Sakana AI (Fugu).
- **Developer docs**: [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)
- **Tool flow**: [TOOL_FLOW.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/TOOL_FLOW.md) — kung paano ipinapadala ang mga tool sa LLMs (genre mask, tool_catalog, GPT-5.4+ native tool_search)
- **Maliit**:LLM [SLM_TIPS.md](https://github.com/awaku7/agentcli/blob/main/docs/SLM_TIPS.md)

## Project Philosophy

uag ay naghahangad na maging **iyong AI, sa iyong makina, ayon sa iyong mga tuntunin.**

- Walang pagpapalawig ng dependency — lokal na tumatakbo
- Walang provider lock-in — lumipat anumang oras
- Walang UI lock-in — CLI / GUI / A2A
 feature na walang lock-in kasanayan

Isang libreng karanasan sa ahente ng AI, libre mula sa pag-lock-in ng vendor.

### ✨ Lumikha ng Iyong Sariling Mga Tool

Ang pagsusulat ng bagong tool para sa uag ay diretso — gumawa ng iisang `.py` file na may
`TOOL_SPEC` at `run_tool()`, ilagay ito sa , _EX_`DUAGTOENT()`, ilagay ito sa _EX_`DUAGTOENT()` ito magagamit kaagad. Para sa mga Rust developer, magpadala ng pre-built na `.pyd` na may
zero extra dependencies para sa mga user.

Tingnan ang [TOOL_CREATOR_GUIDE.md](https://github.com/awaku7/agentcli/blob/main/TOOL_CREATOR_GUIDE.md)
para sa hakbang-hakbang
## Pag-aambag

Ang mga kontribusyon ay malugod na tinatanggap! Mga ulat sa bug, suhestyon sa feature, pagpapahusay sa dokumentasyon, pagsasalin, at pull request — lahat ay pinahahalagahan.

- **Mga Isyu**: Magbukas ng GitHub na isyu para sa mga bug o mga kahilingan sa feature.
- **Pull request**: Fork the repo, gawin ang iyong mga pagbabago, at magsumite ng PR. Tingnan ang [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md) para sa pag-setup at mga alituntunin ng development.
- **Mga Pagsasalin**: README ang mga pagsasalin at lokal na pagdaragdag ay tinatanggap. Tingnan ang [ADD_LOCALE.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/ADD_LOCALE.md).
- **Tools & Skills**: Maaaring mag-ambag ang mga bagong tool plugin at Agent Skills sa pamamagitan ng marketplace.


#
e Development checks test-only dependencies muna. Ang mga ito ay hindi kasama sa listahan ng runtime
dependency:

```bash
python -m pip install -e ".[test]"
python -m pip install black ruff
````

Patakbuhin ang parehong mga pagsusuri na ginamit ng GitHub Actions bago itulak:
\`thba
⎎
tests
python -m black --check src tests
python scripts/tool_json_i18n_batch.py status
python -m pytest -q .

````

Para sa mas mabilis na lokal na pag-ulit, patakbuhin lamang ang mga apektadong pagsubok:
test -
```bash
 mga pagsubok/<affected_area>
````

Mga karagdagang pagsusuri kapag may kaugnayan:

```bash
python -m py_compile src/uagent/
mypy src/uagent
```

Pagkatapos ng lokal na pag-edit (`:po`) scripts/compile_locales.py`at`python scripts/po_qc_summary.py\`.

Runtime patakaran (mga detalye sa [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP6ises.md) sa halip. `sys.exit`; ginagawa ng tool host ang tool na `SystemExit`/`Exception` sa mga error string para hindi mapatay ng isang tool ang proseso. Nananatiling sinadya ang mga paglabas na mabilis mabibigo sa startup.

## Mga invariant sa arkitektura at pagpapatakbo

Tingnan ang [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) para sa mga matibay na kontrata na sumasaklaw sa A2A lifecycle, mga konteksto ng I18N, opsyonal na pag-install ng dependency, kaligtasan ng tool, mga kakayahan ng provider, mga hangganan ng tiwala sa OAuth, mga kaganapan sa pag-verify ng pagtanggap
, at pagtanggap ng mga kaganapan sa pag-verify.## Enterprise Policy Engine

Mga patakaran sa antas ng organisasyon para sa mga tool, provider, kredensyal, MCP server, network, kasanayan, at plugin ay suportado. Itakda ang `UAGENT_POLICY_FILE` sa isang JSON/YAML na file ng patakaran; tingnan ang [docs/ENTERPRISE_POLICY.md](docs/ENTERPRISE_POLICY.md) para sa mga halimbawa ng configuration, mga tungkulin, kumpirmasyon, at mga allowlist.

### Runtime pagbawi at orkestrasyon

Tingnan ang [RESTART_RECOVERY.md](docs/RESTART_d)RECOVER [DAG_SCHEDULER.md](docs/DAG_SCHEDULER.md) / [MULTI_AGENT_RUNTIME.md](docs/MULTI_AGENT_RUNTIME.md) para sa matibay na pag-recover, dependency-aware execution, multi-agent orchestration, at remote A2A na paggamit. [DISTRIBUTED_COORDINATION.md](docs/DISTRIBUTED_COORDINATION.md) para sa shared-runtime leader lease coordination.
