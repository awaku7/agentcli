<p align="center">
 <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="720">
</p>

⎏

</h1 __PHAI align="center">1__PHAI align="center"> align="center">
 <b>U</b>niversal <b>A</b>I <b>G</b>ateway — Dit miljø, din frihed.
</p>

<p align="center">
 Filfunktioner / Web-søgning / Billedgenerering og -analyse / PDF- og Excel-ekstraktion / IoT-kontrol / MCP-integration / MCPs Parallel værktøjsudførelse / Agent Skills marketplace
</p>

<p align="center">
 <a href="https://github.com/awaku7/agentcli">GitHub</a>
 ·
 <a href="https://pypi.org/project/uag/">Py ·</a>
 <a href="https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md">Læs dette på dit sprog</a>
</p>

______________________________________________________________________

## Hvorfor uag?

**Slip fri fra leverandørens låsning.** De fleste AI-assistenter binder dig til en bestemt udbyder eller cloud-tjeneste. uag er anderledes.

- **Kører lokalt** på din maskine. Dine data bliver hos dig (undtagen API opkald, du foretager).
- **Udbyderfrihed**: OpenAI, Claude, Gemini, DeepSeek, Ollama, Azure, Bedrock, Novita, HuggingFace... 24 udbydere, alle tilgængelige fra en enkelt grænseflade. Skift mellem dem ved at omkonfigurere miljøvariabler — ingen geninstallation, ingen migrering.
- **222 værktøjer**: Fil-I/O, websøgning, billedgenerering, Gmail, BLE-enhedsscanning, MCP serverintegration — **130 er statisk markeret parallelt-sikre** (op til 8 udføres samtidigt via trådpulje, kan konfigureres via ALL_WENT_KERS). Når LLM udløser flere værktøjsopkald på én gang, paralleliserer uag dem automatisk.
- **3 UI'er + A2A**: CLI, GUI, Web og Agent-to-Agent-protokollen. Samme motor, enhver grænseflade.
- **IoT-klar**: SwitchBot, ECHONET Lite, Matter, UPnP — styr dine hjemmeenheder gennem AI.
- **Agentfærdigheder**: Installer fællesskabsbyggede færdigheder fra markedspladsen. Forlæng uag uendeligt.

uag er **din AI-assistent på dine vilkår**. Ikke bundet til en udbyder, ikke bundet til en grænseflade, ikke bundet til en platform.

## Hurtig start

```bash
pip install uag
uag
```

Ved den første lancering fører opsætningsguiden dig gennem udbyderkonfigurationen.
Se \[docs/ENVIRONMENT.md\](https://github.com/awadockub7/agentincli/environment/environment/environment/ variabler.

## Computer Use

Computer Use er opt-in og understøtter både en synlig Playwright browser runtime
og en desktop runtime. Når det er aktiveret, oprettes og registreres begge kørselstider;

````bat
set UAGENT_COMPUTER_USE=1
``U` for at vælge 'desk-køretid på skrivebordet. Runtime ressourcer
lukkes sammen ved normal exit, `Ctrl-C` og procesnedlukning. Indstil
`UAGENT_COMPUTER_HEADLESS=1` til browserbaserede CI- eller røgtests.
Se [docs/COMPUTER_USE_IMPLEMENTATION.md](docs/COMPUTER_USE_IMPLEMENTATION.md)
for integration og sikkerhedsdetaljer.

## Realtime Voice og AEC3

Stemmetilstanden i realtid understøtter OpenAI Realtime, Azure OpenAI GPT Realtime, xAI Grok Voice API, Google Gemini Multimodal Live API og Amazon Bedrock Nova Sonic. Den påkrævede `pywebrtc-audio` AEC3-backend installeres automatisk, og Bedrocks valgfri tovejs-streaming-SDK installeres kun automatisk, når Bedrock-udbyderen er valgt:

```bash
python scheck.py realtime
````

AEC3-signalet til den faktiske håndmikrofon) og modtager den faktiske håndmikrofon-pipeline (`langt`), så assistenten kan lytte, mens han taler. Aktiver kun diagnostik, når du undersøger lydproblemer:

```bat
set UAGENT_REALTIME_AUDIO_DEBUG=1
python scheck.py realtime
```

### OpenAI Realtidsfunktion Opkald

OpenAI Realtids-integration understøtter funktion a sikkerhed. Den aktuelle realtidsadapter afslører skrivebeskyttet "get_current_time" automatisk. Destruktive værktøjer og enhedskontroller afsløres ikke uden en eksplicit tilladelsesliste og bekræftelsesflow. Grok realtime bruger en separat adapter og bruger ikke denne OpenAI-specifikke funktionsopkaldssti.

## Funktioner

### 🧠 Multi-Provider Arkitektur

OpenAI / PFN (PLaMo) / Azure / Bedrock / OpenRouter / Ollama / llama.cpp / Gemini / Vertex AI / Claude / Claude / DeGrok /hi / Grok /hi AI) / HuggingFace / Alibaba Cloud (Qwen) / KIMI (Moonshot AI) / Xiaomi MiMo / LM Studio / MiniMax / Sakana AI (Fugu) / SAKURA AI Engine / Together AI / Vercel AI Gateway

Alle udbydere deler det samme værktøjssæt og interface. Skift ved at indstille `UAGENT_PROVIDER` — ingen kodeændringer, ingen separate installationer.

#### Ollama og llama.cpp

Ollama og llama.cpp er separate udbydere. Ollama bruger sin egen service- og modelstyring, mens `llama.cpp` opretter forbindelse til et `llama-server` OpenAI-kompatibelt slutpunkt:

```bash
# Ollama
UAGENT_PROVIDER=ollama
UAGENT_OLLAMA_BASE_URL=http://localhost:11434/v1
UAGENT_OLLAMA_DEPNAME=llama3.1

# llama.cpp / llama-server
UAGENT_PROVIDER=llama_cpp
UAGENT_LLAMA_CPP_BASE_URL=http://localhost:8080/v1
UAGENT_LLAMA_CPP_DEPNAME=local-model
UAGENT_LLAMA_CPP_API_KEYdum=`llama_API_KEYdum. udbyder bruger den Chat-afslutninger-kompatible sti. Behold `UAGENT_RESPONSES=0`, medmindre der er konfigureret en kompatibel proxy.

### ⚡ Parallel værktøjsudførelse

Når LLM anmoder om flere værktøjer samtidigt, uag **parallellerer automatisk** dem.
130_x-værktøjer er alle statisk markeret med en "safe"-værktøjer. `ThreadPoolExecutor` (8 tråde som standard; indstil `UAGENT_PARALLEL_WORKERS` til at ændre).

**Eksempel**: Spørg "Tjek vejret i nordiske hovedstæder" → LLM affyrer `search_web` × 5 lande → alle 5 søgninger kører parallelt →resultaterne er samlet i ét batch. en `TOOL_SPEC` (i øjeblikket 222, inklusive de 2 ruststøttede værktøjer i `src/uagent/tools_rust/`). `http_request` bruger metodefølsom sikkerhed: `GET`/`HEAD`/`OPTIONS`-kald kan køre parallelt, mens skrivemetoder forbliver serielle.

Skrivebeskyttede værktøjer (filsøgning, hash-beregning, katalogliste, oversættelse, DB-forespørgsler osv.) paralleliseres aggressivt.

__#4 Plugin-system (🏟__#4 Kompatibel)

uagent implementerer et **Claude kodekompatibelt plugin-system**. Plugins samler færdigheder, agenter, MCP-servere, hooks og mere i selvstændige mapper med et `.claude-plugin/plugin.json`-manifest.

**Understøttede komponenter**: Færdigheder, underagenter, MCP-servere, hooks (12 livscyklushændelser), skråstreg, kanalafhængige kommandoer, brugeroutput, output Markedspladser

**CLI kommandoer**:

```

:plugin list # Liste over installerede plugins
:plugin install <source> [--scope] # Installer (dir/zip/git/http)
:plugin install <name>@<marketplace> # Installer fra markedsplads

> :plugin remove en <name>:plugin remove en Toggle
> :plugin marketplace add/remove/list # Administrer markedspladser
> :plugin init <name> # Scaffold new plugin

````

Se [DEVELOP_PLUGIN.md](src/uagent/docs/DEVELOP_PLUGIN.md) for fuld dokumentation.# Session 🏄 Kontinuitet

- **Skift udbyder midt i sessionen** med `UAGENT_PROVIDER` — samtalehistorikken bevares.
- **Genindlæs tidligere sessioner** med `:load <indeks>` — fortsæt, hvor du slap.
- **Caching af værktøjsresultater** undgår redundante genudførelser, når det samme værktøj kaldes, når det samme værktøj 9 Værktøjer

| Kategori | Værktøjer |
|---|---|
| **Filhandlinger** | read/write/create/delete/search/grep/hash/zip, file_type, parse_eml (.eml-filer), `path_alias` |
| **Web** | fetch_url, search_web, screenshot, browser_playwright, `url_alias`, `public_transit_route` ([guide](docs/PUBLIC_TRANSIT_ROUTE.md)) |
| **Medie** | generer_billede, analyse_billede, img2img, audio_speech, audio_transcribe |
| **Dokumenter** | PDF/PPTX/DOCX/RTF/ODT-udtræk, Excel-struktureret udtræk |
| **Vejrudsigt** | Tidsserieprognoser med 9 modeller (AutoARIMA, Prophet, LightGBM, CatBoost, TimesFM osv.), automodelvalg, plotgenerering, i18n |
| **Kommunikation** | gmail_send, gmail_read, bluesky, discord_channel, teams_webhook, **pybitchat** (BLE Mesh) — se [COMMUNICATION.md](https://github.com/awaku7/agentcli/blob/main/docs/COMMUNICATION.md) og [BITCHAT.md](https://github.com/awaku7/agentcli/blob/main/docs/BITCHAT.md) |
| **IoT** | SwitchBot (Cloud + BLE), ECHONET Lite, Matter, UPnP, reverse_geocode |
| **Cloud API'er** | `aws_api`, `gcp_api`, `azure_api` — generiske AWS, Google Cloud og Azure API operationer; skriveoperationer kræver eksplicit bekræftelse |
| **Udviklerværktøjer** | workspace_status, git_ops, git_review, security_scan, coverage_report, python_compile, lint_format, run_tests, db_query, **29 kildekodenavigatorer (idx-familie)** |
| **MCP** | Opret forbindelse til eksterne MCP-servere, liste værktøjer, kør — [OAuth / Proxy guide](docs/MCP_OAUTH_PROXY_GUIDE.md) |
| **A2A** | Agent-til-agent kommunikation (med andre uag forekomster eller A2A-kompatible servere) |
| **System** | env vars, systemspecifikationer, tid, datoberegning, [quantities](docs/QUANTITIES.md), [geodesic_distance](docs/GEODESIC_DISTANCE.md), uuid_gen, slugify |
| **Kilde Nav** | **29 idx-værktøjer** til Python, PHP, TypeScript, Java, C#, Dart, C/C++, Rust, Go, Swift, Kotlin, COBOL, VBA, LotusScript, Makefile — få et funktions-/klasseindeks eller en specifik definition uden at læse hele filen arbejdsområdets Git-gren, ændringer, upstream-synkroniseringstilstand, Python runtime og almindelige projektmarkører uden at ændre filer.
- `git_review`: opsummerer Git-ændringer, risikable filer, testkandidater og hemmelige fund uden at afsløre hemmelige værdier.
- `security_scan`: scanning af repository-filer og risikofiler for hemmeligheder. `coverage_report`: kør og normaliser dækning for Python, TypeScript/JavaScript, Rust, Go, Java/Kotlin, .NET, C/C++, Ruby, PHP, Swift og Dart/Flutter.
- Manglende dækningsafhængigheder kan installeres automatisk, når der anmodes om udførelse; `dry_run` installerer aldrig pakker.

Se [Repository Analysis Tools](docs/REPOSITORY_TOOLS.md) for parametre, output og sikkerhedsdetaljer.

Se [Sti- og URL-aliaser](docs/PATH_URL_ALIASES.md) for at forkorte URL-adresser i gentagne værktøjsstier.# 🖥 4 grænseflader + VS-kodeudvidelse

| Tilstand | Kommando | Formål |
|---|---|---|
| **CLI** | `uag` | Hurtig terminalbaseret drift |
| **GUI** | `uagg` | Desktop UI via tkinter |
| **Web** | `uagw` | Browserbaseret adgang |
| **A2A Server** | `uaga` | Agent2Agent protokol til multi-agent kommunikation |
| **VS-kode** | — | [Udvidelse](https://github.com/awaku7/agentcli/blob/main/docs/VSCODE.md) med Chat Panel, Explain, Refactor, Fix Error og Tools Tree View |

Se [VSCODE.md](https://github.com/awaku7/agentcli/blob/VSCODE for detaljer i installationen af VSdocODE/blob/VSCODE, udvidelsen. kommandoer, tastebindinger og konfiguration.

### 🏠 IoT-enhedskontrol

- **BACnet**: Læs/skriv BACnet/IP-enheder (HVAC, belysning, strømmålere). COV-abonnement til push-meddelelser
- **Modbus TCP**: Læs/skriv hold-/inputregistre og spoler. Polling-baseret ændringsovervågning
- **OPC UA**: Gennemse adresserum, læs/skriv variabler, abonner på dataændringer
- **SwitchBot**: Cloud batchkontrol & BLE-scanning/kontrol. Afstemningsbaseret abonnement
- **ECHONET Lite**: Opdag, kontroller og abonner på INF-meddelelser fra husholdningsapparater (AC, lys, vandvarmere osv.)
- **Sagen**: Læse-/skrivekontrol + attributabonnement til overvågning af tilstandsændringer
- **UPnP**:⎏ Videresendelse af enhedssøgning og IGD [IOT_USECASE.md](https://github.com/awaku7/agentcli/blob/main/docs/IOT_USECASE.md)

### 🎯 Agent Skills Marketplace

`:skills mp_search` for at gennemse [SkillsMP].com](https://skillsmplaw-fællesskabet)(Hub) og(skillsmplaw.) færdigheder.
Installer og udvid uag's muligheder på farten.

### 🤖 Auto-pilot (`:auto`)

uag kan **autonomt forfølge et mål på tværs af flere LLM runder**. Perfekt til komplekse opgaver med flere trin, der kræver iterativ forfining.

- **Sådan fungerer det**: Hver runde har en hovedforespørgsel (trin A) efterfulgt af en korrekturbedømmelse (trin B), der beslutter "FULDSTÆNDIG eller FORTSÆT?"
- **Samme udbyder, samme bruger API** hovedforespørgslen - API**: inklusive svar API support.
- **Separat dommer LLM** (valgfrit): Indstil `UAGENT_AP_PROVIDER` til at bruge en anden udbyder/model for anmelderen (brug f.eks. en billigere model til bedømmelse).
- **Afslut når som helst**: Tryk på tasten F11 for at stoppe med det samme, selv midt i svaret. Eller lad anmelderen bestemme, hvornår målet er nået.
- **Konfigurerbar**: `--max-rounds N` for at kontrollere budgettet.

Se [README_AUTO.md](https://github.com/awaku7/agentcli/blob/main/docs/README_AUTO.md) for fuld dokumentation.#
ch Manager

uag kan spore fremskridt på tværs af langvarige opgaver med flere filer. Når LLM behandler dusinvis af filer, fortsætter `batch_state` listen over afventende, afsluttede og mislykkede filer til disken. Hvis sessionen slutter, eller en runde udløber, genoptages den næste kørsel fra det sted, hvor den stoppede — intet går tabt.

### 🛡 Human-in-the-Loop

`human_ask' lader LLM pause og bede om din bekræftelse, før de udfører destruktive handlinger (sletning af filer, overskrivninger). Du bevarer kontrollen.

### 🛑 Afbryd (c-tast/stopknap)

Stop LLM-svargenerering når som helst og injicer en stopkommando tilbage til LLM.

| Interface | Sådan afbrydes |
|---|---|
| **CLI** | Tryk på F12-tasten under LLM-streaming — det aktuelle svar stopper, og `"Stop"` sendes som en brugermeddelelse, så LLM svarer i overensstemmelse hermed |
| **WEB UI** | Klik på den røde **■ Stop**-knap (vises automatisk under LLM-behandling) |
| **Desktop GUI** | Klik på den røde **■**-knap (vises automatisk under LLM-behandling) |

Tryk på **F11** for at afslutte Auto-Pilot. **F12** stopper kun det aktuelle LLM-svar (se [README_AUTO.md](https://github.com/awaku7/agentcli/blob/main/docs/README_AUTO.md)).

### 🕵️ Browserautomatisering og Web Inspector

To komplementære Playwright⎎⎯-browser-baserede browser-spilværktøjer:-** navigere, klik, udfyld formularer, udtræk data, håndtere flersidede flows. Fungerer uden hoved eller hoved.
- **playwright_inspector**: Optag browserovergange, optag DOM-snapshots og skærmbilleder ved hvert trin. Nyttigt til fejlretning af webinteraktioner eller revision af sideændringer over tid.

### 🔄 Dynamic Tool Loading

`tool_catalog` og `tool_load` giver dig mulighed for at opdage og aktivere værktøjer under kørsel.
Ingen grund til at indlæse alt ved opstart - aktiver kun det, du har brug for, når du har brug for det.## Rustative Værktøjer

`uuid_gen` og `slugify` er implementeret i Rust (via PyO3) til ydeevne.
De indlæses direkte fra en forudbygget `.pyd` — **ingen `pip-installation` påkrævet**.

Eksterne udviklere kan også sende Rust-baserede værktøjer: placer en `.pyd-pyd` ved siden af `._`py` ved siden af `._`pyr' fra `uagent.tools.rust_helper`, og
brugere får værktøjet uden nogen ekstra afhængigheder. Se
[TOOL_CREATOR_GUIDE.md](https://github.com/awaku7/agentcli/blob/main/TOOL_CREATOR_GUIDE.md).

### 🌐 i18n / L10n

日本丞 / Engelsk / 简繁體中文 / 한국어 / Español / Français / Русский / og mere.
Indstil `UAGENT_LANG` for at skifte. Se [ADD_LOCALE.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/ADD_LOCALE.md) for at tilføje en ny landestandard.

Oversættelser af denne README er tilgængelige i [docs/README.translations.md](https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md) `uag_envsec`.

## Konfiguration og detaljer

- **Miljøvariabler**: [docs/ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/docs/ENVIRONMENT.md)
- **Opsætningsguide**: `python -m __cli**encrypted_v_2. `uag_envsec` — krypter `.env` som `.env.sec`
- **Responser API**: Indstil `UAGENT_RESPONSES=1` til svar API-tilstand (OpenAI/Azure/Bedrock/OpenRouter/Ollama/Alibabana/LM Studio/AI). Automatisk aktiveret for Sakana AI (Fugu).
- **Udviklerdokumenter**: [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)
- **Værktøjsflow**: [TOOL_FLOW.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/TOOL_FLOW.md) — hvordan værktøjer sendes til LLM'er (genremaske, tool_catalog, GPT-5.4+ native tool_search)
- **Små tips**:__PH [SLM_TIPS.md](https://github.com/awaku7/agentcli/blob/main/docs/SLM_TIPS.md)

## Projektfilosofi

uag stræber efter at være **din AI, på din maskine, på dine præmisser.**

- Ingen SaaS-afhængighed — kører lokalt
- Ingen udbyderlåsning — skift når som helst
- Ingen UI-låsning — CLI / A2A_2 / A2A_2 / A2A_2 / A2A_2 / A2A_3 / A2A_3 og færdigheder

En gratis AI-agentoplevelse, fri for leverandørlåsning.

### ✨ Opret dine egne værktøjer

Det er ligetil at skrive et nyt værktøj til uag - opret en enkelt `.py`-fil med
`TOOL_SPEC` og `run_tool()_ENT_TOOL()`, placer den i S `EXTERN_T_T. og
det er tilgængeligt med det samme. For Rust-udviklere skal du sende en forudbygget `.pyd` med
nul ekstra afhængigheder for brugere.

Se [TOOL_CREATOR_GUIDE.md](https://github.com/awaku7/agentcli/blob/main/TOOL_CREATOR_GUIDE.md)
for trin-for-trin-vejledningen.


.## Bidrag

Bidrag er velkomne! Fejlrapporter, forslag til funktioner, dokumentationsforbedringer, oversættelser og pull-anmodninger - alt sammen værdsat.

- **Problemer**: Åbn et GitHub-problem for fejl eller funktionsanmodninger.
- **Træk anmodninger**: Forlad repoen, foretag dine ændringer, og indsend en PR. Se [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md) for udviklingsopsætning og retningslinjer.
- **Oversættelser**: README oversættelser og tilføjelser til lokalitet er velkomne. Se [ADD_LOCALE.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/ADD_LOCALE.md).
- **Værktøjer og færdigheder**: Nye værktøjs-plugins og agentfærdigheder kan bidrages via markedspladsen. afhængigheder først. De holdes uden for runtime
afhængighedslisten:

```bash
python -m pip install -e ".[test]"
python -m pip install black ruff
````

Kør de samme kontroller, som bruges af GitHub Actions, før du trykker:
`bash s: `bash
s tests
python -m sort --tjek src tests
python scripts/tool_json_i18n_batch.py status
python -m pytest -q .

```

For en hurtigere lokal iteration skal du kun køre de berørte tests:
`bash
` tests/<affected_area>
```

Yderligere checks, når det er relevant:

```bash
python -m py_compile src/uagent/
mypy src/uagent
```

.potyhon. scripts/compile_locales.py`og`python scripts/po_qc_summary.py\`.

Runtime politik (detaljer i [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.%60s) helpers raise i stedet for. Værktøjsværten forvandler værktøjet `SystemExit`/`Exception` til fejlstrenge, så et enkelt værktøj ikke kan dræbe processen. Opstartsfejl-hurtige afslutninger forbliver med vilje.

## Arkitektur og operationelle invarianter

Se [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for de varige kontrakter, der dækker A2A livscyklus, I18N-kontekster, valgfri afhængighedsinstallation, værktøjssikkerhed, udbyderkapacitet, OAuth-tillidsgrænser,⎏ og accept, strukturerede begivenheder.## Enterprise Policy Engine

Politikker på organisationsniveau for værktøjer, udbydere, legitimationsoplysninger, MCP-servere, netværk, færdigheder og plugins understøttes. Indstil `UAGENT_POLICY_FILE` til en JSON/YAML politikfil; se [docs/ENTERPRISE_POLICY.md](docs/ENTERPRISE_POLICY.md) for konfigurationseksempler, roller, bekræftelse og tilladelseslister.

### Runtime gendannelse og orkestrering

Se [RESTART_RECOVERY.md](docs/RESTART_RECOVERY.md) [DAG_SCHEDULER.md](docs/DAG_SCHEDULER.md) / [MULTI_AGENT_RUNTIME.md](docs/MULTI_AGENT_RUNTIME.md) til holdbar gendannelse, afhængighedsbevidst udførelse, multi-agent orkestrering og fjernbrug af A2A.

Se [DISTRIBUTED_COORDINATION.md](docs/DISTRIBUTED_COORDINATION.md) til koordinering af leasingkontrakter med delt runtime.
