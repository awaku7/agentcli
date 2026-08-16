<p align="center">
 <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="720">
</p>

<h1 align="center">1__PHAI align="center">1__PHAI align="center">
 <b>U</b>niversal <b>A</b>I <b>G</b>ateway — Ditt miljø, din frihet.
</p>

<p align="center">
 Filoperasjoner / Web-søk / Bildegenerering og -analyse / PDF- og Excel-ekstraksjon / IoT-kontroll / MCPs integrering / MCPs Parallell verktøykjøring / Agent Skills-markedsplass
</p>

<p align="center">
 <a href="https://github.com/awaku7/agentcli">GitHub</a>
 ·
 <a href="https://pypi.org/project/uag/">Py ·</a>
 <a href="https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md">Les dette på ditt språk</a>
</p>

______________________________________________________________________

## Hvorfor uag?

**Skriv deg fri fra leverandørlås.** De fleste AI-assistenter knytter deg til en bestemt leverandør eller skytjeneste. uag er annerledes.

- **Kjøres lokalt** på maskinen din. Dataene dine forblir hos deg (unntatt API anrop du foretar).
- **Leverandørfrihet**: OpenAI, Claude, Gemini, DeepSeek, Ollama, Azure, Bedrock, Novita, HuggingFace... 24 leverandører, alle tilgjengelige fra ett enkelt grensesnitt. Bytt mellom dem ved å rekonfigurere miljøvariabler — ingen ominstallering, ingen migrering.
- **222 verktøy**: Fil-I/O, nettsøk, bildegenerering, Gmail, BLE-enhetsskanning, MCP serverintegrasjon — **130 er statisk merket som parallell-sikre** (opptil 8 kjøres samtidig via trådpool, konfigurerbar via ALL\_\`UAGENT_KERPAR). Når LLM utløser flere verktøyanrop samtidig, parallelliserer uag dem automatisk.
- **3 brukergrensesnitt + A2A**: CLI, GUI, Web og Agent-to-Agent-protokoll. Samme motor, hvilket som helst grensesnitt.
- **IoT-klar**: SwitchBot, ECHONET Lite, Matter, UPnP — kontroller hjemmeenhetene dine gjennom AI.
- **Agentferdigheter**: Installer fellesskapsbygde ferdigheter fra markedsplassen. Forleng uag uendelig.

uag er **din AI-assistent på dine premisser**. Ikke knyttet til en leverandør, ikke knyttet til et grensesnitt, ikke knyttet til en plattform.

## Hurtigstart

```bash
pip-installasjon uag
uag
```

Ved første oppstart leder oppsettsveiviseren deg gjennom leverandørkonfigurasjonen.
Se \[docs/ENVIRONMENT.md\](https://github.com/awadockub7/agentincli/environment/environment/environment/ variabler.

## Computer Use

Computer Use er opt-in og støtter både en synlig Playwright nettleserkjøring
og en skrivebordskjøring. Når den er aktivert, opprettes og registreres begge kjøretidene;

````bat
set UAGENT_COMPUTER_USE=1
``

desk-skrivebordets kjøretid i stedet. Runtime ressurser er
lukket sammen ved normal utgang, `Ctrl-C` og prosessavslutning. Sett
`UAGENT_COMPUTER_HEADLESS=1` for nettleserbaserte CI- eller røyktester.
Se [docs/COMPUTER_USE_IMPLEMENTATION.md](docs/COMPUTER_USE_IMPLEMENTATION.md)
for integrerings- og sikkerhetsdetaljer.

## Sanntidsstemme og AEC3

Sanntidsstemmemodusen støtter OpenAI Sanntid, Azure OpenAI GPT Sanntid, xAI Grok Stemme API, Google Gemini Multimodal Live API, og Amazon Bedrock Nova Sonic og full-duplex-mikrofon Den påkrevde `pywebrtc-audio` AEC3-backend installeres automatisk, og Bedrocks valgfrie toveis-streaming-SDK installeres automatisk bare når grunnfjellsleverandøren er valgt:

```bash
python scheck.py realtime
````

AEC3-signalet til den faktiske håndmikrofonen og mottar det faktiske håndmikrofonrøret til høyttaleren. (`langt`) slik at assistenten kan lytte mens han snakker. Aktiver diagnostikk bare når du undersøker lydproblemer:

```bat
set UAGENT_REALTIME_AUDIO_DEBUG=1
python scheck.py realtime
```

### OpenAI Sanntidsfunksjonsoppringing

OpenAI Støtte for sikkerhet for anrop i sanntid. Den gjeldende sanntidsadapteren avslører skrivebeskyttet "get_current_time" automatisk. Destruktive verktøy og enhetskontroller avsløres ikke uten en eksplisitt godkjenningsliste og bekreftelsesflyt. Grok sanntid bruker en separat adapter og bruker ikke denne OpenAI-spesifikke funksjonsanropsbanen.

## Funksjoner

### 🧠 Multi-Provider Architecture

OpenAI / PFN (PLaMo) / Azure / Bedrock / OpenRouter / Ollama / llama.cpp / Gemini / Vertex AI / Claude / Claude / Grok /hi / Grok /hi AI) / HuggingFace / Alibaba Cloud (Qwen) / KIMI (Moonshot AI) / Xiaomi MiMo / LM Studio / MiniMax / Sakana AI (Fugu) / SAKURA AI Engine / Together AI / Vercel AI Gateway

Alle leverandører deler samme verktøysett og grensesnitt. Bytt ved å sette `UAGENT_PROVIDER` — ingen kodeendringer, ingen separate installasjoner.

#### Ollama og llama.cpp

Ollama og llama.cpp er separate leverandører. Ollama bruker sin egen tjeneste- og modelladministrasjon, mens `llama.cpp` kobler til et `llama-server` OpenAI-kompatibelt endepunkt:

```bash
# Ollama
UAGENT_PROVIDER=ollama
UAGENT_OLLAMA_BASE_URL=http://localhost:11434/v1
UAGENT_OLLAMA_DEPNAME=llama3.1

# llama.cpp / llama-server
UAGENT_PROVIDER=llama_cpp
UAGENT_LLAMA_CPP_BASE_URL=http://localhost:8080/v1
UAGENT_LLAMA_CPP_DEPNAME=local-model
UAGENT_LLAMA_CPP_API_KEYdum. leverandøren bruker den chatfullføringskompatible banen. Behold `UAGENT_RESPONSES=0` med mindre en kompatibel proxy er konfigurert.

### ⚡ Parallell Tool Execution

Når LLM ber om flere verktøy samtidig, uag **parallellerer automatisk** dem.
130 verktøy er statisk merket med_currente'x' og statisk "safe" `ThreadPoolExecutor` (8 tråder som standard; sett `UAGENT_PARALLEL_WORKERS` for å endre).

**Eksempel**: Spør "Sjekk været i nordiske hovedsteder" → LLM fyrer av `search_web` × 5 land → alle 5 søk kjører parallelt →resultatene samles inn i én gruppe som er basert på en modul. en `TOOL_SPEC` (for øyeblikket 222, inkludert de 2 ruststøttede verktøyene i `src/uagent/tools_rust/`). `http_request` bruker metodesensitiv sikkerhet: `GET`/`HEAD`/`OPTIONS`-anrop kan kjøres parallelt, mens skrivemetodene forblir serielle.

Skrivebeskyttede verktøy (filsøk, hash-beregning, katalogoppføring, oversettelse, DB-spørringer osv.) parallelliseres aggressivt.
⏟___#4 Kompatibel)

uagent implementerer et **Claude kodekompatibelt pluginsystem**. Plugins samler ferdigheter, agenter, MCP-servere, kroker og mer i selvstendige kataloger med et `.claude-plugin/plugin.json`-manifest.

**Støttede komponenter**: Ferdigheter, Sub-agenter, MCP servere, Hooks (12 livssyklushendelser), Slash-kommandoer, Configs, Configs, User Output Marketplaces

**CLI kommandoer**:

```

:plugin list # Liste installerte plugins
:plugin install <source> [--scope] # Install (dir/zip/git/http)
:plugin install <name>@<marketplace> # Install from marketplace

> :plugin remove no <name> Toggle
> :plugin marketplace add/remove/list # Administrer markedsplasser
> :plugin init <name> # Scaffold new plugin

````

Se [DEVELOP_PLUGIN.md](src/uagent/docs/DEVELOP_PLUGIN.md) for full dokumentasjon.# S# ⏄ Kontinuitet

- **Bytt leverandør midt i økten** med `UAGENT_PROVIDER` — samtalehistorikk er bevart.
- **Last inn tidligere økter på nytt** med `:load <indeks>` — fortsett der du slapp.
- **Bufring av verktøyresultater** unngår redundante gjentakelser av verktøyet ⎏ 9🎏##2 Verktøy

| Kategori | Verktøy |
|---|---|
| **Filoperasjoner** | read/write/create/delete/search/grep/hash/zip, file_type, parse_eml (.eml-filer), `path_alias` |
| **Web** | fetch_url, search_web, screenshot, browser_playwright, `url_alias`, `public_transit_route` ([guide](docs/PUBLIC_TRANSIT_ROUTE.md)) |
| **Media** | generer_bilde, analyse_bilde, img2img, audio_speech, audio_transcribe |
| **Dokumenter** | PDF/PPTX/DOCX/RTF/ODT-utvinning, Excel-strukturert utvinning |
| **Værvarsel** | Tidsserieprognoser med 9 modeller (AutoARIMA, Prophet, LightGBM, CatBoost, TimesFM, etc.), automodellvalg, plotgenerering, i18n |
| **Kommunikasjon** | gmail_send, gmail_read, bluesky, discord_channel, teams_webhook, **pybitchat** (BLE Mesh) — se [COMMUNICATION.md](https://github.com/awaku7/agentcli/blob/main/docs/COMMUNICATION.md) og [BITCHAT.md](https://github.com/awaku7/agentcli/blob/main/docs/BITCHAT.md) |
| **IoT** | SwitchBot (Cloud + BLE), ECHONET Lite, Matter, UPnP, reverse_geocode |
| **Cloud APIer** | `aws_api`, `gcp_api`, `azure_api` – generisk AWS, Google Cloud og Azure API operasjoner; skriveoperasjoner krever eksplisitt bekreftelse |
| **Utviklerverktøy** | workspace_status, git_ops, git_review, security_scan, coverage_report, python_compile, lint_format, run_tests, db_query, **29 kildekodenavigatorer (idx-familie)** |
| **MCP** | Koble til eksterne MCP-servere, liste opp verktøy, kjør — [OAuth / Proxy guide](docs/MCP_OAUTH_PROXY_GUIDE.md) |
| **A2A** | Agent-til-agent-kommunikasjon (med andre uag-forekomster eller A2A-kompatible servere) |
| **System** | env vars, systemspesifikasjoner, tid, datoberegning, [quantities](docs/QUANTITIES.md), [geodesic_distance](docs/GEODESIC_DISTANCE.md), uuid_gen, slugify |
| **Kildenav** | **29 idx-verktøy** for Python, PHP, TypeScript, Java, C#, Dart, C/C++, Rust, Go, Swift, Kotlin, COBOL, VBA, LotusScript, Makefile — få en funksjons-/klasseindeks eller spesifikk definisjon uten å lese hele filen arbeidsområdets Git-gren, endringer, oppstrøms synkroniseringstilstand, Python kjøretid og vanlige prosjektmarkører uten å endre filer.
- `git_review`: oppsummer Git-endringer, risikable filer, testkandidater og hemmelige funn uten å avsløre hemmelige verdier.
- `security_scan`: skann arkivfiler og risikofiler for hemmelighetskonfigurasjon. `coverage_report`: kjør og normaliser dekning for Python, TypeScript/JavaScript, Rust, Go, Java/Kotlin, .NET, C/C++, Ruby, PHP, Swift og Dart/Flutter.
- Manglende dekningsavhengigheter kan installeres automatisk når utførelse er forespurt; `dry_run` installerer aldri pakker.

Se [Repository Analysis Tools](docs/REPOSITORY_TOOLS.md) for parametere, utdata og sikkerhetsdetaljer.

Se [Path and URL aliases](docs/PATH_URL_ALIASES.md) for å forkorte URLs.⎏# repeterte filverktøybaner 🖥 4 grensesnitt + VS-kodeutvidelse

| Modus | Kommando | Formål |
|---|---|---|
| **CLI** | `uag` | Rask terminalbasert drift |
| **GUI** | `uagg` | Desktop UI via tkinter |
| **Web** | `uagw` | Nettleserbasert tilgang |
| **A2A Server** | `uaga` | Agent2Agent-protokoll for multi-agent kommunikasjon |
| **VS-kode** | — | [Utvidelse](https://github.com/awaku7/agentcli/blob/main/docs/VSCODE.md) med Chat Panel, Explain, Refactor, Fix Error, og Tools Tree View |

Se [VSCODE.md](https://github.com/awaku7/agentcli/blob/VSCODE) for detaljer om installasjonen av VSdocODE/blob/VSCODE. kommandoer, tastebindinger og konfigurasjon.

### 🏠 IoT-enhetskontroll

- **BACnet**: Les/skriv BACnet/IP-enheter (HVAC, belysning, strømmålere). COV-abonnement for push-varsler
- **Modbus TCP**: Les/skriv holde-/inndataregistre og spoler. Polling-basert endringsovervåking
- **OPC UA**: Bla gjennom adresserom, les/skriv variabler, abonner på dataendringer
- **SwitchBot**: Cloud batchkontroll og BLE skanning/kontroll. Avstemningsbasert abonnement
- **ECHONET Lite**: Oppdag, kontroller og abonner på INF-varsler fra husholdningsapparater (AC, lys, varmtvannsberedere osv.)
- **Saker**: Lese-/skrivekontroll + attributtabonnement for overvåking av tilstandsendringer
- **UPnP**:
Videreoppdaging av enheter og IGD [IOT_USECASE.md](https://github.com/awaku7/agentcli/blob/main/docs/IOT_USECASE.md)

### 🎯 Agent Skills Marketplace

`:skills mp_search` for å bla gjennom [SkillsMP].com/hub)andskillsmplaw for community ferdigheter.
Installer og utvid uags evner på farten.

### 🤖 Autopilot (`:auto`)

uag kan **autonomt forfølge et mål over flere LLM runder**. Perfekt for komplekse, flertrinnsoppgaver som trenger iterativ foredling.

- **Slik fungerer det**: Hver runde har et hovedspørring (trinn A) etterfulgt av en anmelders vurdering (trinn B) som bestemmer "FULLFØRE eller FORTSETTE?"
- **Samme leverandør, samme bruker API**: inkludert svar API-støtte.
- **Separat dommer LLM** (valgfritt): Angi 'UAGENT_AP_PROVIDER' til å bruke en annen leverandør/modell for anmelderen (bruk f.eks. en billigere modell for å bedømme).
- **Avslutt når som helst**: Trykk på 'x'-tasten for å stoppe umiddelbart, selv midt i svaret. Eller la anmelderen avgjøre når målet er nådd.
- **Konfigurerbar**: `--max-rounds N` for å kontrollere budsjettet.

Se [README_AUTO.md](https://github.com/awaku7/agentcli/blob/main/docs/README_AUTO.md) for full dokumentasjon.#
 🏎# Manager

uag kan spore fremgang på tvers av langvarige flerfiloppgaver. Når LLM behandler dusinvis av filer, fortsetter `batch_state` listen over ventende, fullførte og mislykkede filer til disken. Hvis økten avsluttes eller en runde går ut, fortsetter neste kjøring fra der den stoppet — ingenting går tapt.

### 🛡 Human-in-the-Loop

`human_ask` lar LLM pause og be om bekreftelse før de utfører destruktive operasjoner (sletting av filer, overskrivelser). Du beholder kontrollen.

### 🛑 Avbryt (c-tast / stoppknapp)

Stopp generering av LLM-svar når som helst og injiser en stoppkommando tilbake til LLM.

| Grensesnitt | Hvordan avbryte |
|---|---|
| **CLI** | Trykk `c`-tasten under LLM-streaming — gjeldende svar stopper, og `"Stopp"` sendes som en brukermelding slik at LLM svarer tilsvarende |
| **WEB UI** | Klikk på den røde **■ Stopp**-knappen (vises automatisk under LLM-behandling) |
| **Skrivebord GUI** | Klikk på den røde **■**-knappen (vises automatisk under LLM-behandling) |

Avbruddet fungerer som "prompt-injeksjon": i stedet for å bare avbryte, mater den "Stopp" tilbake til LLM som en brukermelding, slik at den elegant kan konkludere eller bekrefte avbruddet til auto-pi-modusen. [README_AUTO.md](https://github.com/awaku7/agentcli/blob/main/docs/README_AUTO.md)).

### 🕵️ Nettleserautomatisering og Web Inspector

To komplementære Playwright⎎⎎nettleserbaserte nettleserbaserte verktøy:⏏** naviger, klikk, fyll ut skjemaer, trekk ut data, håndter flyter på flere sider. Fungerer hodeløst eller med hodet.
- **playwright_inspector**: Ta opp nettleseroverganger, ta DOM-øyeblikksbilder og skjermbilder ved hvert trinn. Nyttig for feilsøking av nettinteraksjoner eller revisjon av sideendringer over tid.

### 🔄 Dynamic Tool Loading

`tool_catalog` og `tool_load` lar deg oppdage og aktivere verktøy under kjøring.
Du trenger ikke å laste inn alt ved oppstart – aktiver bare det du trenger, når du trenger det.## Rustative Tools

`uuid_gen` og `slugify` er implementert i Rust (via PyO3) for ytelse.
De laster direkte fra en forhåndsbygget `.pyd` — **ingen `pip-installasjon` kreves**.

Eksterne utviklere kan også sende Rust-baserte verktøy: plasser en `.pyd-pyd` ved siden av `._`pyra, bruk `._`pyra fra `uagent.tools.rust_helper`, og
brukere får verktøyet uten noen ekstra avhengigheter. Se
[TOOL_CREATOR_GUIDE.md](https://github.com/awaku7/agentcli/blob/main/TOOL_CREATOR_GUIDE.md).

### 🌐 i18n / L10n

日本丞 / English / 简繁體中文 / 한국어 / Español / Français / Русский / og mer.
Sett `UAGENT_LANG` for å bytte. Se [ADD_LOCALE.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/ADD_LOCALE.md) for å legge til en ny lokalitet.

Oversettelser av denne README er tilgjengelig i [docs/README.translations.md](https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md).

### 🔒 Krypterte miljøvariabler

Lagre API-nøkler og hemmeligheter i `.env.`-filen kryptert `uag_envsec`.

## Konfigurasjon og detaljer

- **Miljøvariabler**: [docs/ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/docs/ENVIRONMENT.md)
- **Oppsettsveiviser**: `python -m __cli**`setup_encrypt** `uag_envsec` — krypter `.env` som `.env.sec`
- **Responser API**: Sett `UAGENT_RESPONSES=1` for Responses API-modus (OpenAI/Azure/Bedrock/OpenRouter/Ollama/Alibabanaa/LM Studio/). Automatisk aktivert for Sakana AI (Fugu).
- **Utviklerdokumenter**: [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)
- **Verktøyflyt**: [TOOL_FLOW.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/TOOL_FLOW.md) — hvordan verktøy sendes til LLM-er (sjangermaske, tool_catalog, GPT-5.4+ native tool_search)
- **5_tips**:__PH [SLM_TIPS.md](https://github.com/awaku7/agentcli/blob/main/docs/SLM_TIPS.md)

## Prosjektfilosofi

uag streber etter å være **din AI, på maskinen din, på dine premisser.**

- Ingen SaaS-avhengighet — kjører lokalt
- Ingen leverandørlåsing — bytte når som helst
- Ingen UI-låsing — CLI / A2A_2 / A2A_2 / A2A_2 / A2A_2 / A2A_2 / A2A_2 / A2A_0 og ferdigheter

En gratis AI-agentopplevelse, fri fra leverandørlåsing.

### ✨ Lag dine egne verktøy

Å skrive et nytt verktøy for uag er enkelt – lag en enkelt `.py`-fil med TOOL_SPEC` og `run_tool()_ENT_TOOLS `DEXTERN_T, PLASSER_T. og
det er umiddelbart tilgjengelig. For Rust-utviklere, send en forhåndsbygd `.pyd` med
null ekstra avhengigheter for brukere.

Se [TOOL_CREATOR_GUIDE.md](https://github.com/awaku7/agentcli/blob/main/TOOL_CREATOR_GUIDE.md)
for trinn-for-steg-veiledningen.


## Bidra

Bidrag er velkomne! Feilrapporter, funksjonsforslag, dokumentasjonsforbedringer, oversettelser og pull-forespørsler – alt settes pris på.

- **Problemer**: Åpne et GitHub-problem for feil eller funksjonsforespørsler.
- **Pull-forespørsler**: Fordel repoen, gjør endringer og send inn en PR. Se [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md) for utviklingsoppsett og retningslinjer.
- **Oversettelser**: README oversettelser og lokalitetstillegg er velkomne. Se [ADD_LOCALE.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/ADD_LOCALE.md).
- **Verktøy og ferdigheter**: Nye verktøyplugins og agentferdigheter kan bidra via markedsplassen. avhengigheter først. De holdes utenfor kjøretidsavhengighetslisten:

```bash
python -m pip install -e ".[test]"
python -m pip install black ruff
````

Kjør de samme sjekkene som brukes av GitHub Handlinger før du trykker:
`bash s: `bash
s tests
python -m svart --sjekk src tests
python scripts/tool_json_i18n_batch.py status
python -m pytest -q .

```

For en raskere lokal iterasjon, kjør bare de berørte testene:
`bash
` tests/<affected_area>
```

Ytterligere kontroller når det er relevant:

```bash
python -m py_compile src/uagent/
mypy src/uagent
```

.Pothon) scripts/compile_locales.py`og`python scripts/po_qc_summary.py\`.

Runtime policy (detaljer i [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.);`s helpers raise i stedet for. verktøyverten gjør verktøyet `SystemExit`/`Exception\` til feilstrenger slik at et enkelt verktøy ikke kan drepe prosessen. Oppstartsfeil-raske avslutninger forblir tilsiktet.

## Arkitektur og operasjonelle invarianter

Se [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for varige kontrakter som dekker A2A livssyklus, I18N-kontekster, valgfri avhengighetsinstallasjon, verktøysikkerhet, leverandørfunksjoner, OAuth-tillitsgrenser,⎏ og aksept, strukturerte hendelser.## Enterprise Policy Engine

Retningslinjer på organisasjonsnivå for verktøy, leverandører, legitimasjon, MCP-servere, nettverk, ferdigheter og plugins støttes. Sett `UAGENT_POLICY_FILE` til en JSON/YAML policyfil; se [docs/ENTERPRISE_POLICY.md](docs/ENTERPRISE_POLICY.md) for konfigurasjonseksempler, roller, bekreftelse og godkjenningslister.

### Runtime gjenoppretting og orkestrering

Se [RESTART_RECOVERY.md](docs/RESTART_RECOVERY.md) [DAG_SCHEDULER.md](docs/DAG_SCHEDULER.md) / [MULTI_AGENT_RUNTIME.md](docs/MULTI_AGENT_RUNTIME.md) for varig gjenoppretting, avhengighetsbevisst kjøring, orkestrering av flere agenter og ekstern A2A-bruk.

Se [DISTRIBUTED_COORDINATION.md](docs/DISTRIBUTED_COORDINATION.md) for koordinering av ledere med delt kjøretid.
