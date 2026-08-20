<p align="center">
 <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logotyp" width="720">
</p>

<h1 align="center">1__PHAI align="center">1__PHAI align="center"> align="center">
 <b>U</b>niversal <b>A</b>I <b>G</b>ateway — Din miljö, din frihet.
</p>

<p align="center">
 Filoperationer / Webbsökning / Bildgenerering och analys / PDF- och Excel-extraktion / IoT-kontroll / MCP-verktyg / MCP-integration MCP ell 234 utförande / Agent Skills marketplace
</p>

<p align="center">
 <a href="https://github.com/awaku7/agentcli">GitHub</a>
 ·
 <a href="https://pypi.org/project/uag/">PyPI</a>
 ·
 <a href="https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md">Read this in your language</a>
</p>

______________________________________________________________________

## Varför uag?

**Skjuta dig från leverantörslåsning.** De flesta AI-assistenter knyter dig till en specifik leverantör eller molntjänst. uag är annorlunda.

- **Körs lokalt** på din dator. Din data stannar hos dig (förutom API samtal du gör).
- **Frihet av leverantörer**: OpenAI, Claude, Gemini, DeepSeek, Ollama, Azure, Bedrock, Novita, HuggingFace... 24 leverantörer, alla tillgängliga från ett enda gränssnitt. Byt mellan dem genom att konfigurera om miljövariabler — ingen ominstallation, ingen migrering.
- **222 verktyg**: Fil-I/O, webbsökning, bildgenerering, Gmail, BLE-enhetsskanning, MCP serverintegrering — **130 är statiskt markerade parallellt säkra** (upp till 8 exekveras samtidigt via trådpool, konfigurerbar via ALL_WENT_KERPAR). När LLM aktiverar flera verktygsanrop samtidigt, parallelliserar uag dem automatiskt.
- **3 användargränssnitt + A2A**: CLI, GUI, Web och Agent-to-Agent-protokoll. Samma motor, vilket gränssnitt som helst.
- **IoT redo**: SwitchBot, ECHONET Lite, Matter, UPnP — styr dina hemenheter via AI.
- **Agent Skills**: Installera community-byggda färdigheter från marknaden. Förläng uag oändligt.

uag är **din AI-assistent på dina villkor**. Inte bunden till en leverantör, inte bunden till ett gränssnitt, inte bunden till en plattform.

## Snabbstart

```bash
pip install uag
uag
```

Grundinstallationen håller leverantörs- och verktygsintegrationer valfria. Saknade paket installeras automatiskt när den valda leverantören eller det valda verktyget behöver dem. Installera huvudfunktionerna i förväg:

```bash
pip install "uag[core,providers,tools,development,platform,web]"
```

Installera den fullständiga utvecklings- och testmiljön för arkivet:

```bash
pip install -r requirements.txt
```

Vid första starten guidar installationsguiden dig genom leverantörskonfigurationen.
Se alla miljövariabler i [https://github.com/awaku7/agentcli/blob/main/docs/ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/docs/ENVIRONMENT.md).

## Datoranvändning

Datoranvändning är opt-in och stöder både en synlig Playwright webbläsarruntime
och en skrivbordskörning. När det är aktiverat skapas och registreras båda körtiderna;

````bat
set UAGENT_COMPUTER_USE=1
``
 för att välja operativsystemet körtid för skrivbordet istället. Körtidsresurser
stängs samman vid normal avslutning, `Ctrl-C` och processavstängning. Ställ in
`UAGENT_COMPUTER_HEADLESS=1` för webbläsarbaserade CI- eller röktester.
Se [docs/COMPUTER_USE_IMPLEMENTATION.md](docs/COMPUTER_USE_IMPLEMENTATION.md)
för integrerings- och säkerhetsdetaljer.

## Realtime Voice och AEC3

Röstläget i realtid stöder OpenAI Realtime, Azure OpenAI GPT Realtime, xAI Grok Voice API, Google Gemini Multimodal Live API, och Amazon Bedrock Nova Sonic med full-duplex-mikrofon. Den erforderliga "pywebrtc-audio" AEC3-backend installeras automatiskt, och Bedrocks valfria dubbelriktade streaming-SDK installeras automatiskt endast när Bedrock-leverantören är vald:

```bash
python scheck.py realtime
````

AEC3-signalen till den faktiska ljudmikrofonen (den faktiska handmikrofonledningen) (`långt`) så att assistenten kan lyssna medan han talar. Aktivera diagnostik endast när du undersöker ljudproblem:

```bat
set UAGENT_REALTIME_AUDIO_DEBUG=1
python scheck.py realtime
```

### OpenAI Realtidsfunktion Calling

OpenAI Realtidsintegreringsstöd funktion a säkerhet. Den aktuella realtidsadaptern exponerar skrivskyddad "get_current_time" automatiskt. Destruktiva verktyg och enhetskontroller exponeras inte utan en explicit godkännandelista och bekräftelseflöde. Grok realtid använder en separat adapter och använder inte denna OpenAI-specifika funktionsanropssökväg.

## Funktioner

### 🧠 Multi-Provider Architecture

OpenAI / PFN (PLaMo) / Azure / Bedrock / OpenRouter / Ollama / llama.cpp / Gemini / Vertex AI / Claude / Grok / NVIDIA / Novita / DeepZhipu Z.AI / DeepZhipu Z.AI) (Qwen) / KIMI (Moonshot AI) / Xiaomi MiMo / LM Studio / MiniMax / Sakana AI (Fugu) / SAKURA AI Engine / Together AI / Vercel AI Gateway
Alla leverantörer delar samma verktygsuppsättning och gränssnitt. Byt genom att ställa in `UAGENT_PROVIDER` — inga kodändringar, inga separata installationer.

#### Ollama och llama.cpp

Ollama och llama.cpp är separata leverantörer. Ollama använder sin egen tjänst och modellhantering, medan `llama.cpp` ansluter till en `llama-server` OpenAI-kompatibel slutpunkt:

```bash
# llama.cpp / llama-server
UAGENT_PROVIDER=llama_cpp
UAGENT_LLAMA_CPP_BASE_URL=http://localhost:8080/v1
UAGENT_LLAMA_CPP_DEPNAME=local-model
UAGENT_LLAMA_CPP_API_KEY=dummy
```

:plugin list # Lista installerade plugins
:plugin install <source> [--scope] # Install (dir/zip/git/http)
:plugin install <name>@<marketplace> # Installera från marketplace
:plugin remove <name> #uninstallable market en
:plugin-plugin en
:plugin add/remove/list # Hantera marknadsplatser
:plugin init <namn> # Ställning nytt plugin

````
Se [DEVELOP_PLUGIN.md](src/uagent/docs/DEVELOP_PLUGIN.md) för fullständig dokumentation.
### 🎄-tinuity‑session-sessions-session `UAGENT_PROVIDER` — konversationshistoriken bevaras.
- **Ladda om tidigare sessioner** med `:load <index>` — fortsätt där du slutade.
- **Caching av verktygsresultat** undviker redundant omkörning när samma verktygsanrop upprepas.
### 🛠 229 Verktyg
| Kategori | Verktyg |
|---|---|
| **Filoperationer** | read/write/create/delete/search/grep/hash/zip, file_type, parse_eml (.eml-filer), `path_alias` |
| **Webb** | fetch_url, search_web, screenshot, browser_playwright, `url_alias`, `public_transit_route` ([guide](docs/PUBLIC_TRANSIT_ROUTE.md)) |
| **Media** | generera_bild, analysera_bild, img2img, audio_speech, audio_transcribe |
| **Dokument** | PDF/PPTX/DOCX/RTF/ODT-extraktion, Excel-strukturerad extrahering |
| **Prognos** | Tidsserieprognos med 9 modeller (AutoARIMA, Prophet, LightGBM, CatBoost, TimesFM, etc.), automodellval, plotgenerering, i18n |
| **Kommunikation** | gmail_send, gmail_read, bluesky, discord_channel, teams_webhook, **pybitchat** (BLE Mesh) — se [COMMUNICATION.md](https://github.com/awaku7/agentcli/blob/main/docs/COMMUNICATION.md) och [BITCHAT.md](https://github.com/awaku7/agentcli/blob/main/docs/BITCHAT.md) |
| **IoT** | SwitchBot (moln + BLE), ECHONET Lite, Matter, UPnP, reverse_geocode |
| **Cloud API: er** | `aws_api`, `gcp_api`, `azure_api` — generiska AWS, Google Cloud och Azure API operationer; skrivoperationer kräver explicit bekräftelse |
| **Utvecklarverktyg** | workspace_status, git_ops, git_review, security_scan, coverage_report, python_compile, lint_format, run_tests, db_query, **29 källkodsnavigatorer (idx-familjen)** |
| **MCP** | Anslut till externa MCP-servrar, lista verktyg, kör — [OAuth/Proxyguide](docs/MCP_OAUTH_PROXY_GUIDE.md) |
| **A2A** | Agent-till-agent-kommunikation (med andra uag-instanser eller A2A-kompatibla servrar) |
| **System** | env vars, systemspecifikationer, tid, datumberäkning, [quantities](docs/QUANTITIES.md), [geodesic_distance](docs/GEODESIC_DISTANCE.md), uuid_gen, slugify |
| **Källnavigering** | **29 idx-verktyg** för Python, PHP, TypeScript, Java, C#, Dart, C/C++, Rust, Go, Swift, Kotlin, COBOL, VBA, LotusScript, Makefile — få ett funktions-/klassindex eller en specifik definition utan att läsa hela filen |
#### Repository granskning och täckning
'-rapportera den aktiva grenen syncstatus, uppför grenen syncstatus, state, Python runtime och vanliga projektmarkörer utan att ändra filer.
- `git_review`: sammanfatta Git-ändringar, riskabla filer, testkandidater och hemliga fynd utan att avslöja hemliga värden.
- `security_scan`: skanna arkivfiler för troliga hemligheter och riskfyllda konfigurationsfiler.
- coverage för run och TypeScript/JavaScript, Rust, Go, Java/Kotlin, .NET, C/C++, Ruby, PHP, Swift och Dart/Flutter.
- Saknade täckningsberoenden kan installeras automatiskt när exekvering begärs; `dry_run` installerar aldrig paket.
Se [Repository Analysis Tools](docs/REPOSITORY_TOOLS.md) för parametrar, utdata och säkerhetsdetaljer.
Se [Sökväg och URL-alias](docs/PATH_URL_ALIASES.md) för att förkorta upprepade filsökvägar och URL:er i # 4 verktygsargument # 🎥# Förlängning
| Läge | Kommando | Syfte |
|---|---|---|
| **CLI** | `uag` | Snabb terminalbaserad drift |
| **GUI** | `uagg` | Desktop UI via tkinter |
| **Webb** | `uagw` | Webbläsarbaserad åtkomst |
| **A2A Server** | `uaga` | Agent2Agent-protokoll för kommunikation med flera agenter |
| **VS-kod** | — | [Tillägg](https://github.com/awaku7/agentcli/blob/main/docs/VSCODE.md) med Chat Panel, Explain, Refactor, Fix Error, och Tools Tree View |
Se [VSCODE.md](https://github.com/awaku7/agentcli/blob/VSCODE/docs) för detaljer om installationen av kommandot.mds, VSSCODE/docs) tangentbindningar och konfiguration.
### 🏠 IoT-enhetskontroll
- **BACnet**: Läs/skriv BACnet/IP-enheter (HVAC, belysning, effektmätare). COV-abonnemang för push-meddelanden
- **Modbus TCP**: Läs/skriv håll/indataregister och spolar. Pollingbaserad ändringsövervakning
- **OPC UA**: Bläddra i adressutrymmet, läs/skriv variabler, prenumerera på dataändringar
- **SwitchBot**: Molnbatchkontroll och BLE-skanning/kontroll. Polling-baserad prenumeration
- **ECHONET Lite**: Upptäck, kontrollera och prenumerera på INF-aviseringar från hushållsapparater (AC, lampor, varmvattenberedare, etc.)
- **Ärende**: Läs-/skrivkontroll + attributprenumeration för övervakning av tillståndsändringar
- **UPnP**: Upptäcka vidarebefordran av enheter och IGD [IOT_USECASE.md](https://github.com/awaku7/agentcli/blob/main/docs/IOT_USECASE.md)
### 🎯 Agent Skills Marketplace
`:skills mp_search` för att bläddra i [SkillsMP](https://skillsmp.com) och [Claw-communityt. färdigheter.
Installera och utöka uags kapacitet i farten.
### 🤖 Autopilot (`:auto`)
uag kan **autonomt sträva efter ett mål över flera LLM omgångar**. Perfekt för komplexa uppgifter i flera steg som kräver iterativ förfining.
- **Hur det fungerar**: Varje omgång har en huvudfråga (steg A) följt av en granskarbedömning (steg B) som avgör "SLUTFÖR eller FORTSÄTT?"
- **Samma leverantör, samma API**: Granskarens bedömning använder den identiska kodsökvägen som huvudfrågan - inklusive två svar __PH-_ LLM** (valfritt): Ställ in "UAGENT_AP_PROVIDER" för att använda en annan leverantör/modell för granskaren (använd t.ex. en billigare modell för att bedöma).
- **Avsluta när som helst**: Tryck på tangenten "x" för att stoppa omedelbart, även mitt i svaret. Eller låt granskaren bestämma när målet är uppfyllt.
- **Konfigurerbart**: `--max-rounds N` för att styra budgeten.
Se [README_AUTO.md](https://github.com/awaku7/agentcli/blob/main/docs/README_AUTO.md) för fullständig dokumentation.
## State Manager kan spåra batch__# över långvariga flerfilsuppgifter. När LLM bearbetar dussintals filer, kvarstår `batch_state` listan över väntande, slutförda och misslyckade filer till disken. Om sessionen slutar eller en omgång tar slut, återupptas nästa körning där den slutade — ingenting går förlorat.
### 🛡 Human-in-the-Loop
`human_ask` låter LLM pausa och be om din bekräftelse innan de utför destruktiva operationer (filradering, överskrivningar, skalkommandon). Du behåller kontrollen.
### 🛑 Avbryt (c-knapp / stoppknapp)
Stoppa LLM-svarsgenerering när som helst och injicera ett stoppkommando tillbaka till LLM.
| Gränssnitt | Hur man avbryter |
|---|---|
| **CLI** | Tryck på F12-tangenten under LLM-strömning — det aktuella svaret stoppar, och `"Stopp"` skickas som ett användarmeddelande så att LLM svarar i enlighet därmed |
| **WEB UI** | Klicka på den röda **■ Stopp**-knappen (visas automatiskt under LLM-bearbetning) |
| **GUI för skrivbord** | Klicka på den röda **■**-knappen (visas automatiskt under LLM-bearbetning) |
Avbrottet fungerar som "promptinjektion": istället för att bara avbryta, matar det tillbaka "Stopp" till LLM som ett användarmeddelande, vilket gör att den på ett elegant sätt kan avsluta eller bekräfta avbrottet.
Tryck på "autopilot" [README_AUTO.md](https://github.com/awaku7/agentcli/blob/main/docs/README_AUTO.md)).
### 🕵️ Webbläsarautomatisering och webbinspektör
Två kompletterande Playwright-baserade verktyg:
- **extrahera webbläsarsession, klicka på formuläret, klicka på data, klicka flersidiga flöden. Fungerar utan huvud eller huvud.
- **playwright_inspector**: Spela in webbläsarövergångar, ta DOM-ögonblicksbilder och skärmdumpar vid varje steg. Användbar för att felsöka webbinteraktioner eller granska sidändringar över tid.
### 🔄 Dynamic Tool Loading
`tool_catalog` och `tool_load` låter dig upptäcka och aktivera verktyg vid körning.
Ingen behov av att ladda allt vid start – aktivera bara det du behöver när du behöver det.
#_#`n Tool `slugify` är implementerade i Rust (via PyO3) för prestanda.
De laddas direkt från en förbyggd `.pyd` — **ingen `pip-installation` krävs**.
Externa utvecklare kan också skicka Rust-baserade verktyg: placera en `.pyd` bredvid
wrapper `.py`, använd `load_rust_pyd.(_)_`help. rust_pyd, och
användare får verktyget utan några extra beroenden. Se
[TOOL_CREATOR_GUIDE.md](https://github.com/awaku7/agentcli/blob/main/TOOL_CREATOR_GUIDE.md).
### 🌐 i18n / L10n
日本語 / English / 箁佫锇 /且한국어 / Español / Français / Русский / och mer.
Ställ in `UAGENT_LANG` för att byta. Se [ADD_LOCALE.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/ADD_LOCALE.md) för att lägga till en ny språkversion.
Översättningar av denna README finns i [docs/README.translations.md](https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md).
### 🔒 Krypterade miljövariabler
Lagra API nycklar och hemligheter i `.env.sec` — en man krypterad.
fil. `uag_envsec`.
## Konfiguration & detaljer

- **Miljövariabler**: [docs/ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/docs/ENVIRONMENT.md)
- **Installationsguide**: `python -m __cli**`setup encrypted_PH_2. `uag_envsec` — kryptera `.env` som `.env.sec`
- **Responser API**: Ställ in `UAGENT_RESPONSES=1` för läget Responses API (OpenAI/Azure/Bedrock/OpenRouter/Ollama/Alibabanaa/LM Studio/AI). Autoaktiverad för Sakana AI (Fugu).
- **Utvecklardokument**: [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)
- **Verktygsflöde**: [TOOL_FLOW.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/TOOL_FLOW.md) — hur verktyg skickas till LLM:er (genremask, tool_catalog, GPT-5.4+ inbyggt verktygssökning)
- **Små tips**:__PH [SLM_TIPS.md](https://github.com/awaku7/agentcli/blob/main/docs/SLM_TIPS.md)

## Projektfilosofi

uag strävar efter att vara **din AI, på din maskin, på dina villkor.**

- Inget SaaS-beroende — körs lokalt
- Ingen leverantörslåsning — byt när som helst
- Ingen UI-låsning — CLI / GUI / Web / ⎏ Ingen funktionslåsning och-in. AI-agenterfarenhet, fri från inlåsning av leverantörer.

### ✨ Skapa dina egna verktyg

Det är enkelt att skriva ett nytt verktyg för uag – skapa en enda `.py`-fil med TOOL_SPEC och `run_tool()`, placera den i `UAGENT_TOOL_S_DIR_D's och omedelbart tillgänglig. För Rust-utvecklare, skicka en förbyggd `.pyd` med
noll extra beroenden för användare.

Se [TOOL_CREATOR_GUIDE.md](https://github.com/awaku7/agentcli/blob/main/TOOL_CREATOR_GUIDE.md)
för steg-för-steg-guiden.

## Att bidra

Bidrag är välkomna! Felrapporter, funktionsförslag, dokumentationsförbättringar, översättningar och pull-förfrågningar – alla uppskattas.

- **Problem**: Öppna ett GitHub-problem för buggar eller funktionsförfrågningar.
- **Pull-förfrågningar**: Fördela repo, gör dina ändringar och skicka in en PR. Se [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md) för utvecklingsinställningar och riktlinjer.
- **Översättningar**: README-översättningar och språktillägg är välkomna. Se [ADD_LOCALE.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/ADD_LOCALE.md).
- **Verktyg och färdigheter**: Nya verktygsplugin-program och agentfärdigheter kan bidra via marknadsplatsen. beroenden först. De hålls borta från runtime
beroendelistan:

```bash
python -m pip install -e ".[test]"
python -m pip install black ruff
````

Kör samma kontroller som används av GitHub Actions innan du trycker på:
`bash s: `bash
s tests
python -m black --check src tests
python scripts/tool_json_i18n_batch.py status
python -m pytest -q .

```

För en snabbare lokal iteration, kör endast de berörda testerna:
`test
` tests/<affected_area>
```

Ytterligare kontroller när det är relevant:

```bash
python -m py_compile src/uagent/
mypy src/uagent
```

.Pothon) scripts/compile_locales.py`och`python scripts/po_qc_summary.py\`.

Runtime policy (detaljer i [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md) raiser §.sy verktygsvärden förvandlar verktyget `SystemExit`/`Exception` till felsträngar så att ett enda verktyg inte kan döda processen. Uppstart misslyckade avslut förblir avsiktliga.

## Arkitektur och operationella invarianter

Se [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) för varaktiga kontrakt som täcker A2A livscykel, I18N-kontexter, valfri beroendeinstallation, verktygssäkerhet, leverantörskapacitet, OAuth-förtroendegränser,⎏ och acceptans, strukturerade händelser.## Enterprise Policy Engine

Policyer på organisationsnivå för verktyg, leverantörer, referenser, MCP-servrar, nätverk, färdigheter och plugins stöds. Ställ in `UAGENT_POLICY_FILE` till en JSON/YAML policyfil; se [docs/ENTERPRISE_POLICY.md](docs/ENTERPRISE_POLICY.md) för konfigurationsexempel, roller, bekräftelse och godkännandelistor.

### Runtime-återställning och orkestrering

Se [RESTART_RECOVERY.md](docs/RESTART_RECOVERY.md) / [DAG_SCHEDULER.md](docs/DAG_SCHEDULER.md) / [MULTI_AGENT_RUNTIME.md](docs/MULTI_AGENT_RUNTIME.md) för hållbar återställning, beroendemedveten körning, orkestrering av flera agenter och fjärranvändning av A2A.

Se [DISTRIBUTED_COORDINATION.md](docs/DISTRIBUTED_COORDINATION.md) för samordning av leasingavtal med delad körtid.

## Installation and optional dependencies

The base installation keeps provider and tool integrations optional. Missing
packages are installed automatically when a selected provider or tool needs
one. To install the main feature groups in advance:

```bash
pip install "uag[core,providers,tools,development,platform,web]"
```

For a repository checkout with the full development and test environment:

```bash
pip install -r requirements.txt
```
