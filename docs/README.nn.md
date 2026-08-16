<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="720">
</p>

<h1 align="center">uag — Universal AI Gateway</h1>

<p align="center">
  <b>U</b>niversal <b>A</b>I <b>G</b>ateway — Ditt miljø, din frihet.
</p>

<p align="center">
  Filoperasjonar / Nettsøk / Bildegenerering og analyse / PDF & Excel ekstraksjon / IoT kontroll / MCP integrasjon<br>
  24 leverandører / 3 brukargrensesnitt / parallell verktøykøyring / Markedsplass for agentkompetanse
</p>

<p align="center">
  <a href="https://github.com/awaku7/agentcli">GitHub</a>
  ·
  <a href="https://pypi.org/project/uag/">PyPI</a>
  ·
  <a href="README.translations.md">Read this in your language</a>
</p>

______________________________________________________________________

## Hvorfor uag?

**Slipp deg løs frå leverandørlås.** De fleste AI-assistenter knytter deg til en bestemt leverandør eller skytjeneste. uag er annerledes.

- **Kjører lokalt** på maskinen din. Dataene dine forblir hos deg (unntatt API-anrop du foretar).
- **Leverandørfrihet**: OpenAI, Claude, Gemini, DeepSeek, Ollama, Azure, Bedrock, HuggingFace... 21+ leverandører, alle tilgjengelege frå ett enkelt grensesnitt. Bytt mellom dem ved å rekonfigurere miljøvariabler – ingen reinstallering, ingen migrering.
- **229 verktøy**: Fil-I/O, nettsøk, bildegenerering, Gmail, BLE-enhetsskanning, MCP-serverintegrasjon — **130 er parallellsikre** (opptil 8 kjøres samtidig via trådpool, konfigurerbar via `UAGENT_PARALLEL_WORKERS`). Når LLM utløser flere verktøyanrop samtidig, parallelliserer uag dem automatisk.
- **3 brukergrensesnitt + A2A**: CLI, GUI, Web og Agent-to-Agent-protokoll. Samme motor, hvilket som helst grensesnitt.
- **Agentferdigheter**: Installer fellesskapsbygde ferdigheter frå markedsplassen. Utvid uag uendelig.

uag er **din AI-assistent på dine vilkår**. Ikke knyttet til en leverandør, ikke knyttet til et grensesnitt, ikke knyttet til en plattform.

## Hurtigstart

```bash
pip install uag
uag
```

Ved første oppstart leder oppsettsveiviseren deg gjennom leverandørkonfigurasjonen.
Se [docs/ENVIRONMENT.md](ENVIRONMENT.md) for alle miljøvariabler.

## Computer Use

Computer Use er valfritt og støttar ein synleg Playwright-nettlesar-Runtime og ein desktop-Runtime. Når funksjonen blir aktivert, blir begge oppretta og registrerte; valet blir gjort med `UAGENT_COMPUTER_ENVIRONMENT`.

Runtime-ressursar blir frigjorde ved normal avslutning, `Ctrl-C` eller når prosessen sluttar.

## Sanntidslyd og AEC3

Sanntidsmodus for lyd støttar full-dupleks mikrofon- og høyttalarlyd. Dersom AEC3-bakenden manglar, installerer uag automatisk `pywebrtc-audio`.

**Sanntidsleverandørar**: OpenAI Realtime, Azure OpenAI GPT Realtime, Google Gemini Live, xAI Grok Voice og Amazon Bedrock Nova Sonic. SDK-en for tovegsskøyring i Bedrock blir installert automatisk berre når Bedrock er valt.

```bat
python scheck.py realtime
```

AEC3 brukar det faktiske mikrofonsignalet (`near`) og lyden som faktisk blir sendt til høgtalaren (`far`). Aktiver diagnostikk berre når du undersøker lydproblem.

```bat
set UAGENT_REALTIME_AUDIO_DEBUG=1
python scheck.py realtime
```

### Funksjonskall i OpenAI Realtime

OpenAI Realtime støttar ei sikkerheitsavgrensa funksjonskall-integrering. Den gjeldande adapteren eksponerer den skrivebeskytta `get_current_time`-funksjonen automatisk. Farlege verktøy og einingskontroll krev ei uttrykkeleg godkjenningsliste og ein stadfestingsflyt. Grok sanntid brukar ein separat adapter.

## Funksjoner

### 🧠 Arkitektur med flere leverandører

OpenAI / PFN (PLaMo) / Azure / Bedrock / OpenRouter / Ollama / Gemini / Vertex AI / Claude / Grok / NVIDIA / Novita / DeepSeek / Z.AI (Zhipu AI) / HuggingFace / Alibaba Cloud (Qwen) / KIMI (Moonshot AI) / Xiaomi MiMo / LM Studio / MiniMax / Sakana AI (Fugu) / SAKURA AI Engine / Together AI / Vercel AI Gateway

#### Ollama og llama.cpp

Ollama og llama.cpp er separate leverandørar. Ollama brukar sin eigen teneste, medan llama.cpp koplar til eit OpenAI-kompatibelt endepunkt.

Alle leverandører deler samme verktøysett og grensesnitt. Bytt ved å sette 'UAGENT_PROVIDER' — ingen kodeendringer, ingen separate installasjoner.

### ⚡ Parallell verktøyutførelse

Når LLM ber om flere verktøy samtidig, uag **paralliserer automatisk** dem.
130 verktøy er merket 'x_parallel_safe' og kjøres samtidig via en 'ThreadPoolExecutor' (8 tråder som standard; sett 'UAGENT_PARALLEL_WORKERS' for å endre).

**Eksempel**: Spør "Sjekk været i nordiske hovedsteder" → LLM avfyrer `search_web` × 5 land → alle 5 søkene kjøres parallelt → resultater samlet i én batch.

Skrivebeskyttede verktøy (filsøk, hash-beregning, katalogoppføring, oversettelse, DB-spørringer osv.) parallelliseres aggressivt.

### 🧩 Plugin-system (Claude Code-kompatibelt)

uagent implementerer eit Claude Code-kompatibelt plugin-system. Pluginar samlar ferdigheiter, agentar, MCP-serverar, krokar og meir i sjølvstendige katalogar med eit `.claude-plugin/plugin.json`-manifest.

**Støtta komponentar: ferdigheiter, underagentar, MCP-serverar, krokar (12 livssyklushendingar), skråstrekkommandoar, utstilingsstilar, userConfig, avhengnader, kanalar, marknadsplassar**

**CLI commands**:

```
:plugin list                         # List opp installerte pluginar
:plugin install <source> [--scope]
:plugin install <name>@<marketplace>  # Installer frå marknadsplassen
:plugin remove <name>                # Avinstaller
:plugin enable/disable <name>        # Slå av eller på
:plugin marketplace add/remove/list  # Administrer marknadsplassar
:plugin init <name>                  # Opprett eit nytt plugin-skjelett
```

Sjå den fullstendige dokumentasjonen for meir informasjon. [DEVELOP_PLUGIN.md](../src/uagent/docs/DEVELOP_PLUGIN.md)

### 🔄 Øktkontinuitet

- **Byt leverandør midt i økta** med `UAGENT_PROVIDER` — samtalehistorikken blir bevart.
- **Last inn tidlegare økter på nytt** med `:load <index>` — hald fram der du slapp.

### 🛠 229 verktøy

| Kategori | Verktøy |
|---|---|
| **Filoperasjoner** | read/write/create/delete/search/grep/hash/zip, file_type, parse_eml (.eml-filer) |
| **Nett** | fetch_url, search_web, screenshot, browser_playwright |
| **Media** | generere_bilde, analyse_bilde, img2img, audio_tale, audio_transkribering |
| **Dokumenter** | PDF/PPTX/DOCX/RTF/ODT-utvinning, Excel-strukturert utvinning |
| **Prognose** | Tidsserieprognose med 9 modeller (AutoARIMA, Prophet, LightGBM, CatBoost, TimesFM, etc.), automatisk modellvalg, plotgenerering, i18n |
| **Kommunikasjon** | gmail_send, gmail_read, bluesky, discord_channel, teams_webhook , **pybitchat** (BLE Mesh) — se [COMMUNICATION.md](COMMUNICATION.md) and [BITCHAT.md](BITCHAT.md)|
| **IoT** | BACnet、Modbus TCP、OPC UA、SwitchBot（Cloud + BLE）、ECHONET Lite、Matter、UPnP、reverse_geocode |
| **Sky-API-ar** | `aws_api`, `gcp_api`, `azure_api` — AWS, Google Cloud, and Azure API operations; write operations require explicit confirmation |
| **Utviklerverktøy** | workspace_status, git_ops, python_compile, lint_format, run_tests, db_query, **29 kildekodenavigatorer (idx-familie)** |
| **MCP** | Koble til eksterne MCP-servere, liste opp verktøy, kjør — [OAuth / Proxy guide](MCP_OAUTH_PROXY_GUIDE.md) |
| **A2A** | Agent-til-agent-kommunikasjon (med andre uag-instanser eller A2A-kompatible servere) |
| **System** | env vars, systemspesifikasjoner, klokkeslett, datoberegning, uuid_gen, slugify, quantities ||
| **Kildenav** | **29 idx-verktøy** for Python, PHP, TypeScript, Java, C#, Dart, C/C++, Rust, Go, Swift, Kotlin, COBOL, VBA, LotusScript, Makefile — få en funksjon/klasseindeks eller spesifikk definisjon utan å lese hele filen |

#### Repositorygjennomgang og dekning

- `workspace_status`: Rapporter det aktive arbeidsområdet Git-gren, endringer, oppstrømssynkroniseringstilstand, Python-kjøretid og vanlige prosjektmarkører uten å endre filer.
  "git_review": oppsummer Git-endringer, risikofylte filer, testkandidater og hemmelige funn uten å eksponere hemmelige verdier. "security_scan": skann depotfiler for sannsynlige hemmeligheter og risikofylte konfigurasjonsfiler. "coverage_report": Kjør og normaliser dekning for Python, TypeScript/JavaScript, Rust, Go, Java/Kotlin, .NET, C/C++, Ruby, php, Swift og Dart/Flutter.Manglende dekningsavhengighet kan væreinstallert automatisk når utføring er forespurt; `dry_run` installerer aldri pakker.Se[Verktøy for analyse av depot](REPOSITORY_TOOLS.md) for parametere, utdata og sikkerhetsdetaljer.

### 🖥 4 grensesnitt + VS-kodeutvidelse

| Modus | Kommando | Formål |
|---|---|---|
| **CLI** | `uag` | Rask terminalbasert drift |
| **GUI** | `uagg` | Desktop UI via tkinter |
| **Nett** | `uagw` | Nettleserbasert tilgang |
| **A2A-server** | `uaga` | Agent2Agent-protokoll for multi-agent kommunikasjon |
| **VS-kode** | — | [Utvidelse](VSCODE.md) med Chat Panel, Explain, Refactor, Fix Error og Tools Tree View |

Se [VSCODE.md](VSCODE.md) for detaljer om VS Code-utvidelsen – installasjon, kommandoer, tastebindinger og konfigurasjon.

### 🏠 IoT-enhetskontroll

- **Materie**: Skrivebeskyttet inspeksjon av kontroller/bro/enhetstopologi

Se [IOT_USECASE.md](IOT_USECASE.md)

### 🎯 Agent Skills Marketplace

`:skills mp_search` for å bla gjennom [SkillsMP](https://skillsmp.com) og [ClawHub](https://clawhub.ai) for fellesskapsferdigheter.
Installer og utvid uags muligheter på farten.

### 🤖 Auto-pilot (`:auto`)

uag kan **autonomt forfølge et mål på tvers av flere LLM-runder**. Perfekt for komplekse, flertrinnsoppgaver som trenger iterativ foredling.

- **Korleis fungerer det**: Hver runde har et hovedspørsmål (trinn A) etterfulgt av en anmelders vurdering (trinn B) som bestemmer "FULLT eller FORTSETT?"
- **Samme leverandør, samme API**: Kontrollørens vurdering brukar den identiske kodebanen som hovedspørringen - inkludert Responses API-støtte.
- **Separat dommer LLM** (valgfritt): Angi «UAGENT_AP_PROVIDER» til å bruke en annen leverandør/modell for anmelderen (bruk f.eks. en billigere modell for å bedømme).
- **Avslutt når som helst**: Trykk 'x'-tasten for å stoppe umiddelbart, selv midt i responsen. Eller la anmelderen bestemme når målet er nådd.
- **Konfigurerbar**: `--max-runder N` for å kontrollere budsjettet.

Se [README_AUTO.md](README_AUTO.md) for full dokumentasjon.

### 🧩 Batch State Manager

uag kan spore fremgang på tvers av langvarige flerfiloppgaver. Når LLM behandler dusinvis av filer, vedvarer `batch_state` listen over ventende, fullførte og mislykkede filer til disken. Hvis økten avsluttes eller en runde går ut, fortsetter neste kjøring frå der den stoppet – ingenting går tapt.

### 🛡 Menneske-i-løkken

`human_ask` lar LLM pause og be om din bekreftelse før de utfører destruktive operasjoner (sletting av filer, overskriving, shell-kommandoer). Du beholder kontrollen.

### 🛑 Avbryt (c-tast / Stopp-knapp)

Stopp generering av LLM-svar når som helst og injiser en stoppkommando tilbake til LLM.

| Grensesnitt | Korleis avbryte |
|---|---|
| **CLI** | Trykk `c`-tasten under LLM-streaming — gjeldende svar stopper, og `"Stopp"` sendes som en brukermelding slik at LLM svarer tilsvarende |
| **WEB UI** | Klikk på den røde **■ Stopp**-knappen (vises automatisk under LLM-behandling) |
| **GUI for skrivebord** | Klikk på den røde **■**-knappen (vises automatisk under LLM-behandling) |

Avbruddet fungerer som en "prompt injeksjon": i staden for å berre avbryte, mater den "Stopp" tilbake til LLM som en brukermelding, slik at den elegant kan konkludere eller bekrefte avbruddet.

Trykk `x`-tasten for å avslutte autopilotmodus (se [README_AUTO.md](README_AUTO.md)).

### 🕵️ Nettleserautomatisering og nettinspektør

To komplementære dramatikerbaserte verktøy:

- **browser_playwright**: Automatiser ekte nettleserøkter - naviger, klikk, fyll ut skjemaer, trekk ut data, håndter flyter på flere sider. Fungerer hodeløst eller med hodet.
- **playwright_inspector**: Ta opp nettleseroverganger, ta DOM-øyeblikksbilder og skjermbilder ved hvert trinn. Nyttig for feilsøking av nettinteraksjoner eller revisjon av sideendringer over tid.

### 🔄 Dynamisk verktøyinnlasting

`tool_catalog` og `tool_load` lar deg oppdage og aktivere verktøy under kjøring.
Du trenger ikke å laste alt ved oppstart - aktiver berre det du trenger, når du trenger det.

### 🦀 Rust Native Tools

### 🌐 i18n / L10n

日本語 / Engelsk / 简体中文 / 繁體中文 / 한국어 / Español / Français / Русский / og mer.
Sett «UAGENT_LANG» for å bytte. Se [ADD_LOCALE.md](../src/uagent/docs/DEVELOP_I18N.md) for å legge til en ny lokalitet.

Oversettelser av denne README er tilgjengeleg i [docs/README.translations.md](README.translations.md).

### 🔒 Krypterte miljøvariabler

Lagre API-nøkler og hemmeligheter i `.env.sec` – en kryptert `.env`-fil.
Administrer med `uag_envsec`.

## Konfigurasjon og detaljer

- **Miljøvariabler**: [docs/ENVIRONMENT.md](ENVIRONMENT.md)
- **Konfigurasjonsveiviser**: `python -m uagent.setup_cli`
- **Kryptert env**: `uag_envsec` — krypter `.env` som `.env.sec`
- **Responses API**: Sett `UAGENT_RESPONSES=1` for Responses API-modus (OpenAI/Azure/Bedrock/OpenRouter/Ollama/Alibaba/LM Studio/Sakana AI). Automatisk aktivert for Sakana AI (Fugu).
- **Utviklerdokumenter**: [DEVELOP.md](../src/uagent/docs/DEVELOP.md)
- **Tool flow**: [TOOL_FLOW.md](../src/uagent/docs/TOOL_FLOW.md)
- **Små LLM-tips**: [SLM_TIPS.md](SLM_TIPS.md)

## Prosjektfilosofi

uag ønsker å være **din AI, på maskinen din, på dine premisser.**

- Ingen SaaS-avhengighet - kjører lokalt
- Ingen leverandørlåsing - bytt når som helst
- Ingen UI-låsing - CLI / GUI / Web / A2A
- Ingen funksjonslåsing - utvide med verktøy og ferdigheter

En gratis AI-agentopplevelse, fri frå leverandørlåsing.

### ✨ Lag dine eigne verktøy

Det er enkelt å lage eit nytt verktøy for uag – opprett éi `.py`-fil med `TOOL_SPEC` og `run_tool()`, plasser henne i `UAGENT_EXTERNAL_TOOLS_DIR`, så blir verktøyet straks tilgjengeleg. Rust-utviklarar kan levere ein førehandsbygd `.pyd` utan ekstra avhengnader for brukarane.

[nb.md](TOOL_CREATOR_GUIDE.nb.md)
Sjå den trinnvise rettleiinga her.

## Bidra

Bidrag er velkomne! Feilrapportar, funksjonsforslag, dokumentasjonsforbetringar, omsetjingar og pull-førespurnader – alt blir sett pris på.

- **Issues**: Åpne et GitHub-problem for feil eller funksjonsforespørsler.
- **Pull-førespurnader**: Lag ein fork av repositoriet, gjer endringane dine og send inn ein PR. Sjå [DEVELOP.md](../src/uagent/docs/DEVELOP.md) for utviklingsoppsett og retningslinjer.

Realtime Stemme og AEC3

### Utviklingskontrollar (før PR)

Køyr syntakssjekk, linting, formatering og relevante testar før du sender inn ein pull request.

## Arkitektur og driftsinvariantar

Sjå [ARCHITECTURE.md](ARCHITECTURE.md) for varige implementasjonskontraktar som dekkjer A2A-livssyklus, I18N-kontekstar, installasjon av valfrie avhengnader, verktøysikkerheit, leverandørfunksjonar, OAuth-tillitsgrenser, strukturerte hendingar og akseptanseverifisering.

## Verksemdas policy-motor

Verksemdas policy-motor støttar organisasjonsreglar for verktøy, leverandørar, legitimasjonar, MCP-serverar, nettverk, ferdigheiter og pluginar. Konfigurer `UAGENT_POLICY_FILE` med ei JSON/YAML-policyfil. Sjå [ENTERPRISE_POLICY.md](ENTERPRISE_POLICY.md) for døme, roller, stadfesting og tillatelseslister.

### Gjenoppretting og orkestrering av runtime

Sjå [RESTART_RECOVERY.md](RESTART_RECOVERY.md) / [DAG_SCHEDULER.md](DAG_SCHEDULER.md) / [MULTI_AGENT_RUNTIME.md](MULTI_AGENT_RUNTIME.md) for varig gjenoppretting, avhengnadsmedviten køyring, multiagent-orkestrering og ekstern A2A-bruk.

Sjå [DISTRIBUTED_COORDINATION.md](DISTRIBUTED_COORDINATION.md) for koordinering av leiarleige i delt runtime.
