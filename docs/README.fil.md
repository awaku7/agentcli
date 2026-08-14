<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="720">
</p>

<h1 align="center">uag — Universal AI Gateway</h1>

<p align="center">
  <b>U</b>niversal <b>A</b>I <b>G</b>ateway — Ang iyong kapaligiran, ang iyong kalayaan.
</p>

<p align="center">
  File ops / Paghahanap sa web / Pagbuo ng imahe at pagsusuri / PDF at Excel extraction / IoT control / MCP integration<br>
  24 provider / 3 UI / Parallel tool execution / marketplace ng Agent Skills
</p>

<p align="center">
  <a href="https://github.com/awaku7/agentcli">GitHub</a>
  ·
  <a href="https://pypi.org/project/uag/">PyPI</a>
  ·
  <a href="https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md">Basahin ito sa iyong wika</a>
</p>

______________________________________________________________________

## Bakit uag?

**Lumabas sa pag-lock-in ng vendor.** Karamihan sa mga AI assistant ay itinatali ka sa isang partikular na provider o serbisyo sa cloud. iba ang uag.

- **Tumatakbo nang lokal** sa iyong makina. Mananatili sa iyo ang iyong data (maliban sa mga tawag sa API na gagawin mo).
- **Kalayaan ng provider**: OpenAI, Claude, Gemini, DeepSeek, Ollama, Azure, Bedrock, Novita, HuggingFace... 24 na provider, lahat ay naa-access mula sa isang interface. Magpalit sa pagitan ng mga ito sa pamamagitan ng muling pag-configure ng mga variable ng kapaligiran — walang muling pag-install, walang paglipat.
- **229 tool**: File I/O, web search, image generation, Gmail, BLE device scanning, MCP server integration — **130 ay statically marked parallel-safe** (hanggang sa 8 ay sabay-sabay na isinasagawa sa pamamagitan ng thread pool, na na-configure sa pamamagitan ng `UAGENT_PARALLEL_WORKERS`). Kapag nagpagana ang LLM ng maraming tool na tawag nang sabay-sabay, awtomatiko silang pinapaparallelize ng uag.
- **3 UI + A2A**: CLI, GUI, Web, at Agent-to-Agent protocol. Parehong makina, anumang interface.
- **IoT ready**: SwitchBot, ECHONET Lite, Matter, UPnP — kontrolin ang iyong mga device sa bahay sa pamamagitan ng AI.
- **Mga Kasanayan sa Ahente**: Mag-install ng mga kasanayang binuo ng komunidad mula sa marketplace. Extend uag walang katapusang.

Ang uag ay **iyong AI assistant sa iyong mga termino**. Hindi nakatali sa isang provider, hindi nakatali sa isang interface, hindi nakatali sa isang platform.

## Mabilis na Pagsisimula

```bash
pip install uag
uag
```

Sa unang paglunsad, gagabayan ka ng setup wizard sa configuration ng provider.
Tingnan ang [docs/ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/docs/ENVIRONMENT.md) para sa lahat ng environment variable.

## Realtime Voice at AEC3

Sinusuportahan ng realtime voice mode ang OpenAI Realtime, Azure OpenAI GPT Realtime, xAI Grok Voice API, Google Gemini Multimodal Live API, at Amazon Bedrock Nova Sonic na may full-duplex na mikropono at speaker I/O. Ang kinakailangang backend ng `pywebrtc-audio` AEC3 ay awtomatikong na-install, at ang opsyonal na bidirectional-streaming SDK ng Bedrock ay awtomatikong na-install lamang kapag napili ang provider ng Bedrock:

```bash
python scheck.py realtime
```

Ang AEC3 pipeline ay tumatanggap ng aktwal na signal ng mikropono (`near`) at ang audio ay aktwal na iniabot sa speaker (`far`) upang ang assistant ay maaaring makinig habang nagsasalita. Paganahin lang ang mga diagnostic kapag nagsisiyasat ng mga isyu sa audio:

```bat
set UAGENT_REALTIME_AUDIO_DEBUG=1
python scheck.py realtime
```

### OpenAI Realtime Function Calling

Sinusuportahan ng OpenAI Realtime ang isang integrasyon ng Function Calling na limitado sa kaligtasan. Ang kasalukuyang realtime adapter ay awtomatikong naglalantad ng read-only na `get_current_time`. Ang mga mapanirang tool at kontrol ng device ay hindi nakalantad nang walang tahasang allowlist at daloy ng kumpirmasyon. Gumagamit ang Grok realtime ng isang hiwalay na adapter at hindi ginagamit itong OpenAI-specific na function-call path.

## Mga Tampok

### 🧠 Arkitekturang Multi-Provider

OpenAI / PFN (PLaMo) / Azure / Bedrock / OpenRouter / Ollama / Gemini / Vertex AI / Claude / Grok / NVIDIA / Novita / DeepSeek / Z.AI (Zhipu AI) / HuggingFace / Alibaba Cloud (Qwen) / KIMI (Moonshot AI) / Xiaomi MiMo / LM Studio / MiniMax / Sakana AI (Frar Gateway Engine) / Vertex AIGU AI

Ang lahat ng mga provider ay nagbabahagi ng parehong toolset at interface. Lumipat sa pamamagitan ng pagtatakda ng `UAGENT_PROVIDER` — walang pagbabago sa code, walang hiwalay na pag-install.

### ⚡ Parallel Tool Execution

Kapag ang LLM ay humiling ng maraming tool nang sabay-sabay, uag **awtomatikong pinapaparallelize** ang mga ito.
Ang 130 tool ay statically minarkahan ng `x_parallel_safe` at sabay-sabay na isinasagawa sa pamamagitan ng isang `ThreadPoolExecutor` (8 thread bilang default; itakda ang `UAGENT_PARALLEL_WORKERS` na baguhin).

**Halimbawa**: Itanong ang "Suriin ang lagay ng panahon sa Nordic capitals" → LLM fires `search_web` × 5 bansa → lahat ng 5 paghahanap ay tumatakbo nang magkatulad → resulta na nakolekta sa isang batch.

Ang kasalukuyang bilang ay batay sa mga module ng tool na tumutukoy sa isang `TOOL_SPEC` (kasalukuyang 229, kasama ang 2 Rust-backed na tool sa `src/uagent/tools_rust/`). Gumagamit ang `http_request` ng kaligtasan na sensitibo sa pamamaraan: Ang mga tawag na `GET`/`HEAD`/`OPTIONS` ay maaaring tumakbo nang magkatulad, habang ang mga paraan ng pagsulat ay nananatiling serial.

Ang mga read-only na tool (paghahanap ng file, pagkalkula ng hash, listahan ng direktoryo, pagsasalin, mga query sa DB, atbp.) ay agresibong pinagkakatulad.

### 🧩 Plugin System (Claude Code Compatible)

ang uagent ay nagpapatupad ng **Claude Code-compatible na plugin system**. Mga kasanayan sa bundle ng plugin, ahente, MCP server, hook, at higit pa sa mga self-contained na direktoryo na may `.claude-plugin/plugin.json` na manifest.

**Mga sinusuportahang bahagi**: Mga Kasanayan, Sub-agents, MCP server, Hooks (12 lifecycle event), Slash command, Output styles, userConfig, Dependencies, Channels, Marketplaces

**Mga utos ng CLI**:

```
:plugin list                         # List installed plugins
:plugin install <source> [--scope]   # Install (dir/zip/git/http)
:plugin install <name>@<marketplace>  # Install from marketplace
:plugin remove <name>                # Uninstall
:plugin enable/disable <name>        # Toggle
:plugin marketplace add/remove/list  # Manage marketplaces
:plugin init <name>                  # Scaffold new plugin
```

Tingnan ang [DEVELOP_PLUGIN.md](src/uagent/docs/DEVELOP_PLUGIN.md) para sa buong dokumentasyon.

### 🔄 Pagpapatuloy ng Session

- **Lumipat ng mga provider sa kalagitnaan ng session** gamit ang `UAGENT_PROVIDER` — pinapanatili ang kasaysayan ng pag-uusap.
- **I-reload ang mga nakaraang session** gamit ang `:load <index>` — ituloy kung saan ka tumigil.
- **Pag-cache ng resulta ng tool** ay iniiwasan ang paulit-ulit na muling pagpapatupad kapag umuulit ang parehong tawag sa tool.

### 🛠 229 Tools

| Kategorya | Mga tool |
|---|---|
| **Mga Operasyon ng File** | magbasa/magsulat/lumikha/magtanggal/maghanap/grep/hash/zip, file_type, parse_eml (.eml file) |
| **Web** | fetch_url, search_web, screenshot, browser_playwright, `public_transit_route` ([gabay](docs/PUBLIC_TRANSIT_ROUTE.md)) |
| **Media** | generate_image, analysis_image, img2img, audio_speech, audio_transcribe |
| **Mga Dokumento** | PDF/PPTX/DOCX/RTF/ODT extraction, Excel structured extraction |
| **Pagtataya** | Pagtataya ng serye ng oras na may 9 na modelo (AutoARIMA, Propeta, LightGBM, CatBoost, TimesFM, atbp.), pagpili ng awtomatikong modelo, pagbuo ng plot, i18n |
| **Komunikasyon** | gmail_send, gmail_read, bluesky, discord_channel, teams_webhook, **pybitchat** (BLE Mesh) — tingnan ang [COMMUNICATION.md](https://github.com/awaku7/agentcli/blob/main/docs/COMMUNICATION.md) at [BITCHAT.md](https://github.com/awaku7/agentcli/blob/main/docs/BITCHAT.md) |
| **IoT** | SwitchBot (Cloud + BLE), ECHONET Lite, Matter, UPnP, reverse_geocode |
| **Mga Cloud API** | `aws_api`, `gcp_api`, `azure_api` — generic na mga pagpapatakbo ng AWS, Google Cloud, at Azure API; ang mga pagpapatakbo ng pagsulat ay nangangailangan ng tahasang kumpirmasyon |
| **Dev Tools** | workspace_status, git_ops, git_review, security_scan, coverage_report, python_compile, lint_format, run_tests, db_query, **29 source code navigators (idx family)** |
| **MCP** | Kumonekta sa mga panlabas na MCP server, maglista ng mga tool, i-execute — [OAuth / Proxy guide](docs/MCP_OAUTH_PROXY_GUIDE.md) |
| **A2A** | Komunikasyon ng ahente-sa-agent (kasama ang iba pang mga uag instance o A2A-compatible na server) |
| **System** | env vars, specs ng system, oras, pagkalkula ng petsa, [mga dami](docs/QUANTITIES.md), [geodesic_distance](docs/GEODESIC_DISTANCE.md), uuid_gen, slugify |
| **Source Nav** | **29 idx tools** para sa Python, PHP, TypeScript, Java, C#, Dart, C/C++, Rust, Go, Swift, Kotlin, COBOL, VBA, LotusScript, Makefile — kumuha ng function/class index o partikular na kahulugan nang hindi binabasa ang buong file |

#### Pagsusuri at saklaw ng repositoryo

- `workspace_status`: Iulat ang aktibong workspace Git branch, mga pagbabago, upstream na estado ng pag-sync, Python runtime, at mga karaniwang marker ng proyekto nang hindi binabago ang mga file.
- `git_review`: ibuod ang mga pagbabago sa Git, mga mapanganib na file, mga kandidato sa pagsubok, at mga lihim na natuklasan nang hindi inilalantad ang mga lihim na halaga.
- `security_scan`: i-scan ang mga repository file para sa malamang na mga lihim at mapanganib na configuration file.
- `coverage_report`: patakbuhin at gawing normal ang coverage para sa Python, TypeScript/JavaScript, Rust, Go, Java/Kotlin, .NET, C/C++, Ruby, PHP, Swift, at Dart/Flutter.
- Ang mga nawawalang dependency sa saklaw ay maaaring awtomatikong mai-install kapag hiniling ang pagpapatupad; Ang `dry_run` ay hindi kailanman nag-i-install ng mga pakete.

Tingnan ang [Mga Tool sa Pagsusuri ng Repository](docs/REPOSITORY_TOOLS.md) para sa mga parameter, output, at mga detalye ng kaligtasan.

### 🖥 4 na Interface + VS Code Extension

| Mode | Utos | Layunin |
|---|---|---|
| **CLI** | `uag` | Mabilis na terminal-based na operasyon |
| **GUI** | `uagg` | Desktop UI sa pamamagitan ng tkinter |
| **Web** | `uagw` | Access na nakabatay sa browser |
| **A2A Server** | `uaga` | Agent2Agent protocol para sa multi-agent na komunikasyon |
| **VS Code** | — | [Extension](https://github.com/awaku7/agentcli/blob/main/docs/VSCODE.md) na may Chat Panel, Explain, Refactor, Fix Error, at Tools Tree View |

Tingnan ang [VSCODE.md](https://github.com/awaku7/agentcli/blob/main/docs/VSCODE.md) para sa mga detalye sa extension ng VS Code — pag-install, mga command, keybinding, at configuration.

### 🏠 IoT Device Control

- **BACnet**: Magbasa/magsulat ng mga BACnet/IP device (HVAC, lighting, power meter). COV subscription para sa mga push notification
- **Modbus TCP**: Read/write holding/input registers at coils. Pagsubaybay sa pagbabago batay sa botohan
- **OPC UA**: Mag-browse ng address space, magbasa/magsulat ng mga variable, mag-subscribe sa mga pagbabago sa data
- **SwitchBot**: Cloud batch control at BLE scan/control. Subskripsyon na nakabatay sa botohan
- **ECHONET Lite**: Tuklasin, kontrolin, at mag-subscribe sa mga notification ng INF mula sa mga appliances sa bahay (AC, ilaw, water heater, atbp.)
- **Matter**: Magbasa/magsulat ng kontrol + subscription sa katangian para sa pagsubaybay sa pagbabago ng estado
- **UPnP**: Pagtuklas ng device at pagpapasa ng IGD port

Tingnan ang [IOT_USECASE.md](https://github.com/awaku7/agentcli/blob/main/docs/IOT_USECASE.md)

### 🎯 Marketplace ng Mga Kasanayan sa Ahente

`:skills mp_search` upang i-browse ang [SkillsMP](https://skillsmp.com) at [ClawHub](https://clawhub.ai) para sa mga kasanayan sa komunidad.
I-install at palawakin ang mga kakayahan ng uag sa mabilisang.

### 🤖 Auto-Pilot (`:auto`)

Ang uag ay maaaring **autonomously ituloy ang isang layunin sa maraming LLM round**. Perpekto para sa kumplikado, maraming hakbang na gawain na nangangailangan ng umuulit na pagpipino.

- **Paano ito gumagana**: Ang bawat pag-ikot ay may pangunahing query (Hakbang A) na sinusundan ng paghatol ng tagasuri (Hakbang B) na nagpapasya na "KUMPLETO o MAGPATULOY?"
- **Parehong provider, parehong API**: Ang paghatol ng reviewer ay gumagamit ng kaparehong code path bilang pangunahing query — kasama ang suporta sa Responses API.
- **Hiwalay na judge LLM** (opsyonal): Itakda ang `UAGENT_AP_PROVIDER` na gumamit ng ibang provider/modelo para sa reviewer (hal. gumamit ng mas murang modelo para sa paghusga).
- **Lumabas anumang oras**: Pindutin ang `x` key upang ihinto kaagad, kahit na sa kalagitnaan ng pagtugon. O hayaan ang tagasuri na magpasya kung kailan naabot ang layunin.
- **Configurable**: `--max-rounds N` para kontrolin ang badyet.

Tingnan ang [README_AUTO.md](https://github.com/awaku7/agentcli/blob/main/docs/README_AUTO.md) para sa buong dokumentasyon.

### 🧩 Batch State Manager

masusubaybayan ng uag ang pag-unlad sa mga matagal nang multi-file na gawain. Kapag nagproseso ang LLM ng dose-dosenang mga file, nagpapatuloy ang `batch_state` sa listahan ng mga nakabinbin, nakumpleto, at nabigong mga file sa disk. Kung matatapos ang session o magtatapos ang isang round, magpapatuloy ang susunod na pagtakbo mula sa kung saan ito huminto — walang mawawala.

### 🛡 Human-in-the-Loop

Hinahayaan ng `human_ask` ang LLM na i-pause at hingin ang iyong kumpirmasyon bago magsagawa ng mga mapanirang operasyon (pagtanggal ng file, pag-overwrite, mga utos ng shell). Manatili kang may kontrol.

### 🛑 Interrupt (c-key / Stop button)

Itigil ang pagbuo ng tugon ng LLM anumang oras at mag-iniksyon ng stop command pabalik sa LLM.

| Interface | Paano makagambala |
|---|---|
| **CLI** | Pindutin ang `c` key habang nag-stream ng LLM — hihinto ang kasalukuyang tugon, at ipinapadala ang `"Stop"` bilang mensahe ng user upang tumugon ang LLM nang naaayon |
| **WEB UI** | I-click ang pulang **■ Stop** button (awtomatikong lilitaw sa panahon ng pagproseso ng LLM) |
| **Desktop GUI** | I-click ang pulang **■** na buton (awtomatikong lumalabas sa panahon ng pagproseso ng LLM) |

Gumagana ang interrupt bilang "prompt injection": sa halip na i-abort lang, ibinabalik nito ang `"Stop"` sa LLM bilang mensahe ng user, na nagbibigay-daan dito na maayos na tapusin o tanggapin ang pagkaantala.

Pindutin ang `x` key upang lumabas sa auto-pilot mode (tingnan ang [README_AUTO.md](https://github.com/awaku7/agentcli/blob/main/docs/README_AUTO.md)).

### 🕵️ Browser Automation at Web Inspector

Dalawang pantulong na tool na nakabatay sa Playwright:

- **browser_playwright**: I-automate ang mga totoong session ng browser — mag-navigate, mag-click, punan ang mga form, kumuha ng data, pangasiwaan ang mga daloy ng maraming pahina. Gumagana nang walang ulo o ulo.
- **playwright_inspector**: Mag-record ng mga transition ng browser, kumuha ng mga snapshot ng DOM at mga screenshot sa bawat hakbang. Kapaki-pakinabang para sa pag-debug ng mga pakikipag-ugnayan sa web o pag-audit ng mga pagbabago sa pahina sa paglipas ng panahon.

### 🔄 Dynamic na Tool Loading

Hinahayaan ka ng `tool_catalog` at `tool_load` na tuklasin at paganahin ang mga tool sa runtime.
Hindi na kailangang i-load ang lahat sa startup — i-activate lang ang kailangan mo, kapag kailangan mo ito.

### 🦀 Rust Native Tools

Ang `uuid_gen` at `slugify` ay ipinatupad sa Rust (sa pamamagitan ng PyO3) para sa pagganap.
Direkta silang naglo-load mula sa isang pre-built na `.pyd` — **walang `pip install` na kinakailangan**.

Ang mga panlabas na developer ay maaari ding magpadala ng mga tool na nakabatay sa Rust: maglagay ng `.pyd` sa tabi ng
wrapper `.py`, gamitin ang `load_rust_pyd()` mula sa `uagent.tools.rust_helper`, at
nakukuha ng mga user ang tool nang walang anumang karagdagang dependencies. Tingnan mo
[TOOL_CREATOR_GUIDE.md](https://github.com/awaku7/agentcli/blob/main/TOOL_CREATOR_GUIDE.md).

### 🌐 i18n / L10n

日本語 / English / 简体中文 / 繁體中文 / 한국어 / Español / Français / Русский / at higit pa.
Itakda ang `UAGENT_LANG` na lumipat. Tingnan ang [ADD_LOCALE.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/ADD_LOCALE.md) upang magdagdag ng bagong lokal.

Available ang mga pagsasalin ng README na ito sa [docs/README.translations.md](https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md).

### 🔒 Mga Variable ng Naka-encrypt na Environment

Mag-imbak ng mga API key at lihim sa `.env.sec` — isang naka-encrypt na `.env` file.
Pamahalaan gamit ang `uag_envsec`.

## Configuration at Mga Detalye

- **Mga variable ng kapaligiran**: [docs/ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/docs/ENVIRONMENT.md)
- **Wizard ng setup**: `python -m uagent.setup_cli`
- **Naka-encrypt na env**: `uag_envsec` — i-encrypt ang `.env` bilang `.env.sec`
- **Responses API**: Itakda ang `UAGENT_RESPONSES=1` para sa Responses API mode (OpenAI/Azure/Bedrock/OpenRouter/Ollama/Alibaba/LM Studio/Sakana AI). Auto-enabled para sa Sakana AI (Fugu).
- **Mga doc ng developer**: [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)
- **Daloy ng tool**: [TOOL_FLOW.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/TOOL_FLOW.md) — kung paano ipinapadala ang mga tool sa mga LLM (genre mask, tool_catalog, GPT-5.4+ native tool_search)
- **Maliliit na tip sa LLM**: [SLM_TIPS.md](https://github.com/awaku7/agentcli/blob/main/docs/SLM_TIPS.md)

## Pilosopiya ng Proyekto

ang uag ay naghahangad na maging **iyong AI, sa iyong makina, sa iyong mga tuntunin.**

- Walang dependency sa SaaS — tumatakbo nang lokal
- Walang lock-in ng provider — lumipat anumang oras
- Walang UI lock-in — CLI / GUI / Web / A2A
- Walang feature na lock-in — i-extend gamit ang mga tool at kasanayan

Isang libreng karanasan sa ahente ng AI, libre mula sa lock-in ng vendor.

### ✨ Lumikha ng Iyong Sariling Mga Tool

Ang pagsusulat ng bagong tool para sa uag ay diretso — gumawa ng isang `.py` file na may
`TOOL_SPEC` at `run_tool()`, ilagay ito sa `UAGENT_EXTERNAL_TOOLS_DIR`, at
ito ay magagamit kaagad. Para sa mga developer ng Rust, magpadala ng pre-built na `.pyd` gamit ang
zero extra dependencies para sa mga user.

Tingnan ang [TOOL_CREATOR_GUIDE.md](https://github.com/awaku7/agentcli/blob/main/TOOL_CREATOR_GUIDE.md)
para sa step-by-step na gabay.

## Nag-aambag

Malugod na tinatanggap ang mga kontribusyon! Mga ulat ng bug, suhestyon sa feature, pagpapahusay ng dokumentasyon, pagsasalin, at pull request — lahat ay pinahahalagahan.

- **Mga Isyu**: Magbukas ng isyu sa GitHub para sa mga bug o mga kahilingan sa feature.
- **Mga kahilingan sa paghila**: I-fork ang repo, gawin ang iyong mga pagbabago, at magsumite ng PR. Tingnan ang [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md) para sa pag-setup at mga alituntunin ng development.
- **Mga Pagsasalin**: Ang mga pagsasalin ng README at lokal na pagdaragdag ay malugod na tinatanggap. Tingnan ang [ADD_LOCALE.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/ADD_LOCALE.md).
- **Mga Tool at Kasanayan**: Ang mga bagong tool na plugin at Kasanayan sa Ahente ay maaaring maiambag sa pamamagitan ng marketplace.

### Mga pagsusuri sa pag-unlad (bago ang PR)

```bash
python -m py_compile src/uagent/
ruff format src/ && ruff check src/
mypy src/uagent
pytest -q tests/<affected_area>
```

Pagkatapos ng locale (`.po`) na mga pag-edit: `python scripts/compile_locales.py` at `python scripts/po_qc_summary.py`.

Patakaran sa runtime (mga detalye sa [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md) §6.1): tumaas ang mga katulong sa halip na `sys.exit`; ginagawang error string ng tool host ang tool na `SystemExit`/`Exception` kaya hindi maaaring patayin ng isang tool ang proseso. Nananatiling sinadya ang mga paglabas na mabilis mabibigo sa startup.

## Arkitektura at mga operational invariant

Tingnan ang [ARCHITECTURE.md](ARCHITECTURE.md) para sa mga permanenteng kontrata sa pagpapatupad na sumasaklaw sa lifecycle ng A2A, mga konteksto ng I18N, pag-install ng opsyonal na dependency, kaligtasan ng tool, mga kakayahan ng provider, mga hangganan ng tiwala sa OAuth, mga structured event, at verification ng pagtanggap.

## Enterprise Policy Engine

Enterprise Policy Engine supports organization-level rules for tools, providers, credentials, MCP servers, networks, skills, and plugins. Configure `UAGENT_POLICY_FILE` with a JSON/YAML policy file. See [ENTERPRISE_POLICY.md](ENTERPRISE_POLICY.md) for examples, roles, confirmation, and allowlists.

### Runtime recovery and orchestration

See [RESTART_RECOVERY.md](RESTART_RECOVERY.md) / [DAG_SCHEDULER.md](DAG_SCHEDULER.md) / [MULTI_AGENT_RUNTIME.md](MULTI_AGENT_RUNTIME.md) for durable recovery, dependency-aware execution, multi-agent orchestration, and remote A2A usage.

See [DISTRIBUTED_COORDINATION.md](DISTRIBUTED_COORDINATION.md) for shared-runtime leader lease coordination.
