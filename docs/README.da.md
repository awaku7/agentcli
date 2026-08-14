<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="720">
</p>

<h1 align="center">uag — Universal AI Gateway</h1>

<p align="center">
  <b>U</b>niversal <b>A</b>I <b>G</b>ateway — Dit miljø, din frihed.
</p>

<p align="center">
  Filops / Websøgning / Billedgenerering og analyse / PDF- og Excel-udtrækning / IoT-kontrol / MCP-integration<br>
  24 udbydere / 3 UI'er / Parallel værktøjsudførelse / Agent Skills markedsplads
</p>

<p align="center">
  <a href="https://github.com/awaku7/agentcli">GitHub</a>
  ·
  <a href="https://pypi.org/project/uag/">PyPI</a>
  ·
  <a href="https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md">Læs dette på dit sprog</a>
</p>

______________________________________________________________________

## Hvorfor uag?

**Slip fri fra leverandørens låsning.** De fleste AI-assistenter binder dig til en bestemt udbyder eller cloud-tjeneste. uag er anderledes.

- **Kører lokalt** på din maskine. Dine data forbliver hos dig (undtagen API-kald, du foretager).
- **Udbyderfrihed**: OpenAI, Claude, Gemini, DeepSeek, Ollama, Azure, Bedrock, Novita, HuggingFace... 24 udbydere, alle tilgængelige fra en enkelt grænseflade. Skift mellem dem ved at omkonfigurere miljøvariabler - ingen geninstallation, ingen migrering.
- **229 værktøjer**: Fil-I/O, websøgning, billedgenerering, Gmail, BLE-enhedsscanning, MCP-serverintegration — **130 er statisk markeret parallelt-sikre** (op til 8 udføres samtidigt via trådpulje, konfigureres via `UAGENT_PARALLEL_WORKERS`). Når LLM udløser flere værktøjsopkald på én gang, paralleliserer uag dem automatisk.
- **3 UI'er + A2A**: CLI, GUI, Web og Agent-to-Agent protokol. Samme motor, enhver grænseflade.
- **IoT klar**: SwitchBot, ECHONET Lite, Matter, UPnP — styr dine hjemmeenheder gennem AI.
- **Agent færdigheder**: Installer fællesskabsbyggede færdigheder fra markedspladsen. Forlæng uag uendeligt.

uag er **din AI-assistent på dine vilkår**. Ikke bundet til en udbyder, ikke bundet til en grænseflade, ikke bundet til en platform.

## Hurtig start

```bash
pip install uag
uag
```

Ved første lancering fører opsætningsguiden dig gennem udbyderkonfigurationen.
Se [docs/ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/docs/ENVIRONMENT.md) for alle miljøvariabler.

## Realtime Voice og AEC3

Realtime stemmetilstanden understøtter OpenAI Realtime, Azure OpenAI GPT Realtime, xAI Grok Voice API, Google Gemini Multimodal Live API og Amazon Bedrock Nova Sonic med fuld-dupleks mikrofon og højttaler I/O. Den påkrævede `pywebrtc-audio` AEC3-backend installeres automatisk, og Bedrocks valgfri tovejs-streaming-SDK installeres kun automatisk, når Bedrock-udbyderen er valgt:

```bash
python scheck.py realtime
```

AEC3-pipelinen modtager det faktiske mikrofonsignal (`near`) og lyden, der rent faktisk afleveres til højttaleren (`far`), så assistenten kan lytte, mens han taler. Aktiver kun diagnostik, når du undersøger lydproblemer:

```bat
set UAGENT_REALTIME_AUDIO_DEBUG=1
python scheck.py realtime
```

### OpenAI Realtime Function Calling

OpenAI Realtime understøtter en sikkerhedsbegrænset funktionsopkaldsintegration. Den aktuelle realtidsadapter afslører skrivebeskyttet `get_current_time` automatisk. Destruktive værktøjer og enhedskontroller afsløres ikke uden en eksplicit tilladelsesliste og bekræftelsesflow. Grok realtime bruger en separat adapter og bruger ikke denne OpenAI-specifikke funktionsopkaldssti.

## Funktioner

### 🧠 Multi-Provider Arkitektur

OpenAI / PFN (PLaMo) / Azure / Bedrock / OpenRouter / Ollama / Gemini / Vertex AI / Claude / Grok / NVIDIA / Novita / DeepSeek / Z.AI (Zhipu AI) / HuggingFace / Alibaba Cloud (Qwen) / KIMI (Moonshot AI) / Xiaomi Studio / MiKUMax (FLM) AI Engine / Together AI / Vercel AI Gateway

Alle udbydere deler det samme værktøjssæt og interface. Skift ved at indstille `UAGENT_PROVIDER` — ingen kodeændringer, ingen separate installationer.

### ⚡ Parallel værktøjsudførelse

Når LLM anmoder om flere værktøjer samtidigt, uag **paralliserer automatisk** dem.
130 værktøjer er statisk mærket `x_parallel_safe` og udføres samtidigt via en `ThreadPoolExecutor` (8 tråde som standard; indstil `UAGENT_PARALLEL_WORKERS` til at ændre).

**Eksempel**: Spørg "Tjek vejret i nordiske hovedstæder" → LLM affyrer `search_web` × 5 lande → alle 5 søgninger kører parallelt → resultater samlet i én batch.

Den aktuelle optælling er baseret på værktøjsmoduler, der definerer en `TOOL_SPEC` (i øjeblikket 229, inklusive de 2 ruststøttede værktøjer i `src/uagent/tools_rust/`). `http_request` bruger metodefølsom sikkerhed: `GET`/`HEAD`/`OPTIONS` opkald kan køre parallelt, mens skrivemetoder forbliver serielle.

Skrivebeskyttede værktøjer (filsøgning, hash-beregning, katalogliste, oversættelse, DB-forespørgsler osv.) paralleliseres aggressivt.

### 🧩 Plugin-system (Claude Code Compatible)

uagent implementerer et **Claude Code-kompatibelt plugin-system**. Plugins samler færdigheder, agenter, MCP-servere, hooks og mere i selvstændige mapper med et `.claude-plugin/plugin.json`-manifest.

**Understøttede komponenter**: Færdigheder, Sub-agenter, MCP-servere, Hooks (12 livscyklushændelser), Slash-kommandoer, Outputstile, UserConfig, Dependencies, Channels, Marketplaces

**CLI-kommandoer**:

```
:plugin list                         # List installed plugins
:plugin install <source> [--scope]   # Install (dir/zip/git/http)
:plugin install <name>@<marketplace>  # Install from marketplace
:plugin remove <name>                # Uninstall
:plugin enable/disable <name>        # Toggle
:plugin marketplace add/remove/list  # Manage marketplaces
:plugin init <name>                  # Scaffold new plugin
```

Se [DEVELOP_PLUGIN.md](src/uagent/docs/DEVELOP_PLUGIN.md) for fuld dokumentation.

### 🔄 Sessionskontinuitet

- **Skift udbyder midt i sessionen** med `UAGENT_PROVIDER` — samtalehistorikken bevares.
- **Genindlæs tidligere sessioner** med `:load <index>` — fortsæt, hvor du slap.
- **Caching af værktøjsresultat** undgår redundant genudførelse, når det samme værktøjskald gentages.

### 🛠 229 værktøjer

| Kategori | Værktøjer |
|---|---|
| **Filhandlinger** | read/write/create/delete/search/grep/hash/zip, file_type, parse_eml (.eml-filer) |
| **Web** | fetch_url, search_web, screenshot, browser_playwright, `public_transit_route` ([guide](docs/PUBLIC_TRANSIT_ROUTE.md)) |
| **Medie** | generere_billede, analyse_billede, img2img, audio_tale, audio_transskribering |
| **Dokumenter** | PDF/PPTX/DOCX/RTF/ODT-ekstraktion, Excel-struktureret ekstraktion |
| **Vejrudsigt** | Tidsserieprognoser med 9 modeller (AutoARIMA, Prophet, LightGBM, CatBoost, TimesFM osv.), automodelvalg, plotgenerering, i18n |
| **Kommunikation** | gmail_send, gmail_read, bluesky, discord_channel, teams_webhook, **pybitchat** (BLE Mesh) — se [COMMUNICATION.md](https://github.com/awaku7/agentcli/blob/main/docs/COMMUNICATION.md) og [BITCHAT.md](https://github.com/awaku7/agentcli/blob/main/docs/BITCHAT.md) |
| **IoT** | SwitchBot (Cloud + BLE), ECHONET Lite, Matter, UPnP, reverse_geocode |
| **Cloud API'er** | `aws_api`, `gcp_api`, `azure_api` — generiske AWS-, Google Cloud- og Azure API-operationer; skriveoperationer kræver eksplicit bekræftelse |
| **Udviklerværktøjer** | workspace_status, git_ops, git_review, security_scan, coverage_report, python_compile, lint_format, run_tests, db_query, **29 kildekodenavigatorer (idx-familie)** |
| **MCP** | Opret forbindelse til eksterne MCP-servere, liste værktøjer, udfør — [OAuth / Proxy guide](docs/MCP_OAUTH_PROXY_GUIDE.md) |
| **A2A** | Agent-til-agent-kommunikation (med andre uag-instanser eller A2A-kompatible servere) |
| **System** | env vars, systemspecifikationer, tid, datoberegning, [quantities](docs/QUANTITIES.md), [geodesic_distance](docs/GEODESIC_DISTANCE.md), uuid_gen, slugify |
| **Kilde Nav** | **29 idx-værktøjer** til Python, PHP, TypeScript, Java, C#, Dart, C/C++, Rust, Go, Swift, Kotlin, COBOL, VBA, LotusScript, Makefile — få et funktions-/klasseindeks eller en specifik definition uden at læse hele filen |

#### Gennemgang af repository og dækning

- `workspace_status`: Rapporter det aktive arbejdsområde Git-gren, ændringer, upstream-synkroniseringstilstand, Python runtime og almindelige projektmarkører uden at ændre filer.
- `git_review`: opsummer Git-ændringer, risikable filer, testkandidater og hemmelige fund uden at afsløre hemmelige værdier.
- `security_scan`: scan lagerfiler for sandsynlige hemmeligheder og risikable konfigurationsfiler.
- `coverage_report`: Kør og normaliser dækning for Python, TypeScript/JavaScript, Rust, Go, Java/Kotlin, .NET, C/C++, Ruby, PHP, Swift og Dart/Flutter.
- Manglende dækningsafhængigheder kan installeres automatisk, når der anmodes om udførelse; `dry_run` installerer aldrig pakker.

Se [Værktøjer til repository-analyse](docs/REPOSITORY_TOOLS.md) for parametre, output og sikkerhedsdetaljer.

### 🖥 4 grænseflader + VS-kodeudvidelse

| Tilstand | Kommando | Formål |
|---|---|---|
| **CLI** | `uag` | Hurtig terminalbaseret drift |
| **GUI** | `uagg` | Desktop UI via tkinter |
| **Web** | `uagw` | Browserbaseret adgang |
| **A2A-server** | `uaga` | Agent2Agent protokol til multi-agent kommunikation |
| **VS-kode** | — | [Udvidelse](https://github.com/awaku7/agentcli/blob/main/docs/VSCODE.md) med Chat Panel, Explain, Refactor, Fix Error og Tools Tree View |

Se [VSCODE.md](https://github.com/awaku7/agentcli/blob/main/docs/VSCODE.md) for detaljer om VS-kodeudvidelsen — installation, kommandoer, tastebindinger og konfiguration.

### 🏠 IoT-enhedskontrol

- **BACnet**: Læs/skriv BACnet/IP-enheder (HVAC, belysning, strømmålere). COV-abonnement for push-meddelelser
- **Modbus TCP**: Læs/skriv hold/input registre og spoler. Afstemningsbaseret forandringsovervågning
- **OPC UA**: Gennemse adresserum, læs/skriv variabler, abonner på dataændringer
- **SwitchBot**: Cloud batchkontrol & BLE-scanning/kontrol. Afstemningsbaseret abonnement
- **ECHONET Lite**: Opdag, kontroller og abonner på INF-meddelelser fra husholdningsapparater (AC, lys, vandvarmere osv.)
- **Materie**: Læse-/skrivekontrol + attributabonnement til overvågning af tilstandsændringer
- **UPnP**: Enhedsopdagelse og IGD-portvideresendelse

Se [IOT_USECASE.md](https://github.com/awaku7/agentcli/blob/main/docs/IOT_USECASE.md)

### 🎯 Agent Skills Marketplace

`:skills mp_search` for at gennemse [SkillsMP](https://skillsmp.com) og [ClawHub](https://clawhub.ai) for fællesskabsfærdigheder.
Installer og udvid uag's muligheder på farten.

### 🤖 Auto-pilot (`:auto`)

uag kan **autonomt forfølge et mål på tværs af flere LLM-runder**. Perfekt til komplekse opgaver med flere trin, der kræver iterativ forfining.

- **Sådan fungerer det**: Hver runde har en hovedforespørgsel (trin A) efterfulgt af en anmelders bedømmelse (trin B), der afgør "Fuldfør eller FORTSÆT?"
- **Samme udbyder, samme API**: Bedømmelsesbedømmelsen bruger den identiske kodesti som hovedforespørgslen - inklusive Responses API-understøttelse.
- **Separat dommer LLM** (valgfrit): Indstil `UAGENT_AP_PROVIDER` til at bruge en anden udbyder/model for anmelderen (brug f.eks. en billigere model til bedømmelse).
- **Afslut når som helst**: Tryk på tasten `x` for at stoppe med det samme, selv midt i svaret. Eller lad anmelderen bestemme, hvornår målet er nået.
- **Konfigurerbar**: `--max-rounds N` til at styre budgettet.

Se [README_AUTO.md](https://github.com/awaku7/agentcli/blob/main/docs/README_AUTO.md) for fuld dokumentation.

### 🧩 Batch State Manager

uag kan spore fremskridt på tværs af langvarige multi-fil opgaver. Når LLM behandler dusinvis af filer, bevarer `batch_state` listen over afventende, afsluttede og mislykkede filer på disken. Hvis sessionen slutter, eller en runde udløber, genoptages det næste løb fra det sted, hvor det stoppede - intet går tabt.

### 🛡 Menneske-i-løkken

`human_ask` lader LLM pause og bede om din bekræftelse, før de udfører destruktive handlinger (sletning af filer, overskrivninger, shell-kommandoer). Du bevarer kontrollen.

### 🛑 Afbrydelse (c-tast / stop-knap)

Stop generering af LLM-svar til enhver tid, og injicer en stopkommando tilbage til LLM.

| Interface | Sådan afbrydes |
|---|---|
| **CLI** | Tryk på `c`-tasten under LLM-streaming — det aktuelle svar stopper, og `"Stop"` sendes som en brugermeddelelse, så LLM svarer i overensstemmelse hermed |
| **WEB UI** | Klik på den røde **■ Stop** knap (vises automatisk under LLM-behandling) |
| **Desktop GUI** | Klik på den røde **■** knap (vises automatisk under LLM-behandling) |

Afbrydelsen fungerer som "prompt indsprøjtning": I stedet for blot at afbryde, sender den `"Stop"` tilbage til LLM'en som en brugermeddelelse, så den på en yndefuld måde kan afslutte eller anerkende afbrydelsen.

Tryk på tasten `x` for at afslutte autopilottilstand (se [README_AUTO.md](https://github.com/awaku7/agentcli/blob/main/docs/README_AUTO.md)).

### 🕵️ Browserautomatisering og webinspektør

To komplementære dramatikerbaserede værktøjer:

- **browser_playwright**: Automatiser rigtige browsersessioner - naviger, klik, udfyld formularer, udtræk data, håndter flersidede flows. Virker hovedløst eller med hoved.
- **playwright_inspector**: Optag browserovergange, optag DOM-snapshots og skærmbilleder ved hvert trin. Nyttigt til fejlretning af webinteraktioner eller revision af sideændringer over tid.

### 🔄 Dynamisk værktøjsindlæsning

`tool_catalog` og `tool_load` giver dig mulighed for at opdage og aktivere værktøjer under kørsel.
Ingen grund til at indlæse alt ved opstart - aktiver kun det, du har brug for, når du har brug for det.

### 🦀 Rust Native Tools

`uuid_gen` og `slugify` er implementeret i Rust (via PyO3) for ydeevne.
De indlæses direkte fra en forudbygget `.pyd` — **ingen `pip install` påkrævet**.

Eksterne udviklere kan også sende Rust-baserede værktøjer: Placer en `.pyd` ved siden af
indpakning `.py`, brug `load_rust_pyd()` fra `uagent.tools.rust_helper`, og
brugere får værktøjet uden nogen ekstra afhængigheder. Se
[TOOL_CREATOR_GUIDE.md](https://github.com/awaku7/agentcli/blob/main/TOOL_CREATOR_GUIDE.md).

### 🌐 i18n / L10n

日本語 / Engelsk / 简体中文 / 繁體中文 / 한국어 / Español / Français / Русский / og mere.
Indstil `UAGENT_LANG` for at skifte. Se [ADD_LOCALE.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/ADD_LOCALE.md) for at tilføje en ny lokalitet.

Oversættelser af denne README er tilgængelige i [docs/README.translations.md](https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md).

### 🔒 Krypterede miljøvariabler

Gem API-nøgler og -hemmeligheder i `.env.sec` - en krypteret `.env`-fil.
Administrer med `uag_envsec`.

## Konfiguration og detaljer

- **Miljøvariabler**: [docs/ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/docs/ENVIRONMENT.md)
- **Opsætningsguide**: `python -m uagent.setup_cli`
- **Krypteret env**: `uag_envsec` — krypter `.env` som `.env.sec`
- **Responses API**: Indstil `UAGENT_RESPONSES=1` til Responses API-tilstand (OpenAI/Azure/Bedrock/OpenRouter/Ollama/Alibaba/LM Studio/Sakana AI). Automatisk aktiveret for Sakana AI (Fugu).
- **Udviklerdokumenter**: [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)
- **Værktøjsflow**: [TOOL_FLOW.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/TOOL_FLOW.md) — hvordan værktøjer sendes til LLM'er (genremaske, tool_catalog, GPT-5.4+ native tool_search)
- **Små LLM-tip**: [SLM_TIPS.md](https://github.com/awaku7/agentcli/blob/main/docs/SLM_TIPS.md)

## Projektfilosofi

uag stræber efter at være **din AI, på din maskine, på dine præmisser.**

- Ingen SaaS-afhængighed - kører lokalt
- Ingen udbyder-låsning - skift når som helst
- Ingen UI-låsning - CLI / GUI / Web / A2A
- Ingen funktionslåsning - udvid med værktøjer og færdigheder

En gratis AI-agentoplevelse, fri for leverandørlåsning.

### ✨ Opret dine egne værktøjer

At skrive et nyt værktøj til uag er ligetil - opret en enkelt `.py`-fil med
`TOOL_SPEC` og `run_tool()`, placer den i `UAGENT_EXTERNAL_TOOLS_DIR`, og
den er tilgængelig med det samme. For Rust-udviklere, send en præbygget `.pyd` med
nul ekstra afhængigheder for brugere.

Se [TOOL_CREATOR_GUIDE.md](https://github.com/awaku7/agentcli/blob/main/TOOL_CREATOR_GUIDE.md)
for trin-for-trin guiden.

## Bidrager

Bidrag er velkomne! Fejlrapporter, forslag til funktioner, dokumentationsforbedringer, oversættelser og pull-anmodninger - alt sammen værdsat.

- **Problemer**: Åbn et GitHub-problem for fejl eller funktionsanmodninger.
- **Træk anmodninger**: Forkast repoen, foretag dine ændringer, og send en PR. Se [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md) for udviklingsopsætning og retningslinjer.
- **Oversættelser**: README-oversættelser og tilføjelser til lokalitet er velkomne. Se [ADD_LOCALE.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/ADD_LOCALE.md).
- **Værktøjer og færdigheder**: Nye værktøjs-plugins og agentfærdigheder kan bidrages via markedspladsen.

### Udviklingstjek (før PR)

```bash
python -m py_compile src/uagent/
ruff format src/ && ruff check src/
mypy src/uagent
pytest -q tests/<affected_area>
```

Efter lokalitet (`.po`) redigeringer: `python scripts/compile_locales.py` og `python scripts/po_qc_summary.py`.

Runtime-politik (detaljer i [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md) §6.1): hjælpere hæver i stedet for `sys.exit`; Værktøjsværten forvandler værktøjet `SystemExit`/`Exception` til fejlstrenge, så et enkelt værktøj ikke kan dræbe processen. Opstartsfejl-hurtige afslutninger forbliver med vilje.

## Arkitektur og driftsinvarianter

Se [ARCHITECTURE.md](ARCHITECTURE.md) for de varige implementeringskontrakter, der dækker A2A-livscyklus, I18N-kontekster, installation af valgfrie afhængigheder, værktøjssikkerhed, udbyderfunktioner, OAuth-tillidsgrænser, strukturerede hændelser og acceptverifikation.

## Enterprise Policy Engine

Enterprise Policy Engine supports organization-level rules for tools, providers, credentials, MCP servers, networks, skills, and plugins. Configure `UAGENT_POLICY_FILE` with a JSON/YAML policy file. See [ENTERPRISE_POLICY.md](ENTERPRISE_POLICY.md) for examples, roles, confirmation, and allowlists.
