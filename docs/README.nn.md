<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="720">
</p>

<h1 align="center">uag — Universal AI Gateway</h1>

<p align="center">
  <b>U</b>niversal <b>A</b>I <b>G</b>ateway — Your environment, your freedom.
</p>

<p align="center">
  File ops / Web search / Image generation &amp; analysis / PDF &amp; Excel extraction / IoT control / MCP integration<br>
  24 providers / 3 UIs / Parallel tool execution / Agent Skills marketplace
</p>

<p align="center">
  <a href="https://github.com/awaku7/agentcli">GitHub</a>
  ·
  <a href="https://pypi.org/project/uag/">PyPI</a>
  ·
  <a href="https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md">Read this in your language</a>
</p>

______________________________________________________________________

## Hvorfor uag?

**Slipp deg løs frå leverandørlås.** De fleste AI-assistenter knytter deg til en bestemt leverandør eller skytjeneste. uag er annerledes.

- **Kjører lokalt** på maskinen din. Dataene dine forblir hos deg (unntatt API-anrop du foretar).
- **Leverandørfrihet**: OpenAI, Claude, Gemini, DeepSeek, Ollama, Azure, Bedrock, HuggingFace... 21+ leverandører, alle tilgjengelege frå ett enkelt grensesnitt. Bytt mellom dem ved å rekonfigurere miljøvariabler – ingen reinstallering, ingen migrering.
- **195 verktøy**: Fil-I/O, nettsøk, bildegenerering, Gmail, BLE-enhetsskanning, MCP-serverintegrasjon — **111 er parallellsikre** (opptil 8 kjøres samtidig via trådpool, konfigurerbar via `UAGENT_PARALLEL_WORKERS`). Når LLM utløser flere verktøyanrop samtidig, parallelliserer uag dem automatisk.
- **3 brukergrensesnitt + A2A**: CLI, GUI, Web og Agent-to-Agent-protokoll. Samme motor, hvilket som helst grensesnitt.
- **Agentferdigheter**: Installer fellesskapsbygde ferdigheter frå markedsplassen. Utvid uag uendelig.

uag er **din AI-assistent på dine vilkår**. Ikke knyttet til en leverandør, ikke knyttet til et grensesnitt, ikke knyttet til en plattform.

## Hurtigstart

```bash
pip install uag
uag
```

Ved første oppstart leder oppsettsveiviseren deg gjennom leverandørkonfigurasjonen.
Se [docs/ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/docs/ENVIRONMENT.md) for alle miljøvariabler.

## Funksjoner

### 🧠 Arkitektur med flere leverandører

OpenAI / PFN (PLaMo) / Azure / Bedrock / OpenRouter / Ollama / Gemini / Vertex AI / Claude / Grok / NVIDIA / DeepSeek / Z.AI (Zhipu AI) / HuggingFace / Alibaba Cloud (Qwen) / KIMI (Moonshot AI) / Xiaomi MiMo / LM Studio / MiniMax / **Fuguana** / **Together AI** / **Vercel AI Gateway**

Alle leverandører deler samme verktøysett og grensesnitt. Bytt ved å sette 'UAGENT_PROVIDER' — ingen kodeendringer, ingen separate installasjoner.

### ⚡ Parallell verktøyutførelse

Når LLM ber om flere verktøy samtidig, uag **paralliserer automatisk** dem.
111 verktøy er merket 'x_parallel_safe' og kjøres samtidig via en 'ThreadPoolExecutor' (8 tråder som standard; sett 'UAGENT_PARALLEL_WORKERS' for å endre).

**Eksempel**: Spør "Sjekk været i nordiske hovedsteder" → LLM avfyrer `search_web` × 5 land → alle 5 søkene kjøres parallelt → resultater samlet i én batch.

Skrivebeskyttede verktøy (filsøk, hash-beregning, katalogoppføring, oversettelse, DB-spørringer osv.) parallelliseres aggressivt.

### 🧩 Plugin System (Claude Code Compatible)

uagent implements a **Claude Code-compatible plugin system**. Plugins bundle skills, agents, MCP servers, hooks, and more into self-contained directories with a `.claude-plugin/plugin.json` manifest.

**Supported components**: Skills, Sub-agents, MCP servers, Hooks (12 lifecycle events), Slash commands, Output styles, userConfig, Dependencies, Channels, Marketplaces

**CLI commands**:

```
:plugin list                         # List installed plugins
:plugin install <source> [--scope]   # Install (dir/zip/git/http)
:plugin install <name>@<marketplace>  # Install from marketplace
:plugin remove <name>                # Uninstall
:plugin enable/disable <name>        # Toggle
:plugin marketplace add/remove/list  # Manage marketplaces
:plugin init <name>                  # Scaffold new plugin
```

See [DEVELOP_PLUGIN.md](src/uagent/docs/DEVELOP_PLUGIN.md) for full documentation.

### 🔄 Øktkontinuitet

- **Switch providers mid-session** with `UAGENT_PROVIDER` — conversation history is preserved.
- **Reload past sessions** with `:load <index>` — pick up where you left off.
- **Tool result caching** avoids redundant re-execution when the same tool call repeats.

### 🛠 195 verktøy

| Kategori | Verktøy |
|---|---|
| **Filoperasjoner** | read/write/create/delete/search/grep/hash/zip, file_type, parse_eml (.eml-filer) |
| **Nett** | fetch_url, search_web, screenshot, browser_playwright |
| **Media** | generere_bilde, analyse_bilde, img2img, audio_tale, audio_transkribering |
| **Dokumenter** | PDF/PPTX/DOCX/RTF/ODT-utvinning, Excel-strukturert utvinning |
| **Prognose** | Tidsserieprognose med 9 modeller (AutoARIMA, Prophet, LightGBM, CatBoost, TimesFM, etc.), automatisk modellvalg, plotgenerering, i18n |
| **Kommunikasjon** | gmail_send, gmail_read, bluesky, discord_channel, teams_webhook , **pybitchat** (BLE Mesh) — se [COMMUNICATION.md](https://github.com/awaku7/agentcli/blob/main/docs/COMMUNICATION.md) and [BITCHAT.md](https://github.com/awaku7/agentcli/blob/main/docs/BITCHAT.md)|
| **IoT** | BACnet、Modbus TCP、OPC UA、SwitchBot（Cloud + BLE）、ECHONET Lite、Matter、UPnP、reverse_geocode |
| **Utviklerverktøy** | git_ops, python_compile, lint_format, run_tests, db_query, **26 kildekodenavigatorer (idx-familie)** |
| **MCP** | Koble til eksterne MCP-servere, liste opp verktøy, kjør |
| **A2A** | Agent-til-agent-kommunikasjon (med andre uag-instanser eller A2A-kompatible servere) |
| **System** | env vars, systemspesifikasjoner, klokkeslett, datoberegning, uuid_gen, slugify ||
| **Kildenav** | **26 idx-verktøy** for Python, PHP, TypeScript, Java, C#, Dart, C/C++, Rust, Go, Swift, Kotlin, COBOL — få en funksjon/klasseindeks eller spesifikk definisjon utan å lese hele filen |

### 🖥 4 grensesnitt + VS-kodeutvidelse

| Modus | Kommando | Formål |
|---|---|---|
| **CLI** | `uag` | Rask terminalbasert drift |
| **GUI** | `uagg` | Desktop UI via tkinter |
| **Nett** | `uagw` | Nettleserbasert tilgang |
| **A2A-server** | `uaga` | Agent2Agent-protokoll for multi-agent kommunikasjon |
| **VS-kode** | — | [Utvidelse](https://github.com/awaku7/agentcli/blob/main/docs/VSCODE.md) med Chat Panel, Explain, Refactor, Fix Error og Tools Tree View |

Se [VSCODE.md](https://github.com/awaku7/agentcli/blob/main/docs/VSCODE.md) for detaljer om VS Code-utvidelsen – installasjon, kommandoer, tastebindinger og konfigurasjon.

### 🏠 IoT-enhetskontroll

- **Materie**: Skrivebeskyttet inspeksjon av kontroller/bro/enhetstopologi

Se [IOT_USECASE.md](https://github.com/awaku7/agentcli/blob/main/docs/IOT_USECASE.md)

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

Se [README_AUTO.md](https://github.com/awaku7/agentcli/blob/main/docs/README_AUTO.md) for full dokumentasjon.

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

Trykk `x`-tasten for å avslutte autopilotmodus (se [README_AUTO.md](https://github.com/awaku7/agentcli/blob/main/docs/README_AUTO.md)).

### 🕵️ Nettleserautomatisering og nettinspektør

To komplementære dramatikerbaserte verktøy:

- **browser_playwright**: Automatiser ekte nettleserøkter - naviger, klikk, fyll ut skjemaer, trekk ut data, håndter flyter på flere sider. Fungerer hodeløst eller med hodet.
- **playwright_inspector**: Ta opp nettleseroverganger, ta DOM-øyeblikksbilder og skjermbilder ved hvert trinn. Nyttig for feilsøking av nettinteraksjoner eller revisjon av sideendringer over tid.

### 🔄 Dynamisk verktøyinnlasting

`tool_catalog` og `tool_load` lar deg oppdage og aktivere verktøy under kjøring.
Du trenger ikke å laste alt ved oppstart - aktiver berre det du trenger, når du trenger det.

### 🦀 Rust Native Tools

`uuid_gen` and `slugify` are implemented in Rust (via PyO3) for performance.
They load directly from a pre-built `.pyd` — **no `pip install` required**.

External developers can also ship Rust-based tools: place a `.pyd` next to the
wrapper `.py`, use `load_rust_pyd()` from `uagent.tools.rust_helper`, and
users get the tool without any extra dependencies. See
[TOOL_CREATOR_GUIDE.nb.md](TOOL_CREATOR_GUIDE.nb.md).

### 🌐 i18n / L10n

日本語 / Engelsk / 简体中文 / 繁體中文 / 한국어 / Español / Français / Русский / og mer.
Sett «UAGENT_LANG» for å bytte. Se [ADD_LOCALE.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/ADD_LOCALE.md) for å legge til en ny lokalitet.

Oversettelser av denne README er tilgjengeleg i [docs/README.translations.md](https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md).

### 🔒 Krypterte miljøvariabler

Lagre API-nøkler og hemmeligheter i `.env.sec` – en kryptert `.env`-fil.
Administrer med `uag_envsec`.

## Konfigurasjon og detaljer

- **Miljøvariabler**: [docs/ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/docs/ENVIRONMENT.md)
- **Konfigurasjonsveiviser**: `python -m uagent.setup_cli`
- **Kryptert env**: `uag_envsec` — krypter `.env` som `.env.sec`
- **Responses API**: Sett `UAGENT_RESPONSES=1` for Responses API-modus (OpenAI/Azure/Bedrock/OpenRouter/Ollama/Alibaba/LM Studio/Sakana AI). Automatisk aktivert for Sakana AI (Fugu).
- **Utviklerdokumenter**: [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)
- **Tool flow**: [TOOL_FLOW.md](../src/uagent/docs/TOOL_FLOW.md)
- **Små LLM-tips**: [SLM_TIPS.md](https://github.com/awaku7/agentcli/blob/main/docs/SLM_TIPS.md)

## Prosjektfilosofi

uag ønsker å være **din AI, på maskinen din, på dine premisser.**

- Ingen SaaS-avhengighet - kjører lokalt
- Ingen leverandørlåsing - bytt når som helst
- Ingen UI-låsing - CLI / GUI / Web / A2A
- Ingen funksjonslåsing - utvide med verktøy og ferdigheter

En gratis AI-agentopplevelse, fri frå leverandørlåsing.

### ✨ Create Your Own Tools

Writing a new tool for uag is straightforward — create a single `.py` file with
`TOOL_SPEC` and `run_tool()`, place it in `UAGENT_EXTERNAL_TOOLS_DIR`, and
it's immediately available. For Rust developers, ship a pre-built `.pyd` with
zero extra dependencies for users.

See [TOOL_CREATOR_GUIDE.nb.md](TOOL_CREATOR_GUIDE.nb.md)
for the step-by-step guide.

## Contributing

Contributions are welcome! Bug reports, feature suggestions, documentation improvements, translations, and pull requests — all appreciated.

- **Issues**: Open a GitHub issue for bugs or feature requests.
- **Pull requests**: Fork the repo, make your changes, and submit a PR. See [DEVELOP.md](../src/uagent/docs/DEVELOP.md) for development setup and guidelines.
- **Translations**: README translations and locale additions are welcome. See [ADD_LOCALE.md](../src/uagent/docs/ADD_LOCALE.md).
- **Tools & Skills**: New tool plugins and Agent Skills can be contributed via the marketplace.

Realtime Stemme og AEC3

## Realtime stemmemodus støtter full-dupleks mikrofon og høyttalerinngang/utgang. Hvis AEC3-backend mangler, installerer uag automatisk pywebrtc-audio.

**Realtime providers:** OpenAI Realtime, Azure OpenAI GPT Realtime, Google Gemini Live, xAI Grok Voice, and Amazon Bedrock Nova Sonic. The Bedrock bidirectional-streaming SDK is installed automatically only when Bedrock is selected.

```bat
python scheck.py realtime
```

AEC3 brukar det faktiske mikrofonsignalet (nær) og lyden som faktisk sendes til høyttaleren (fjern). Aktiver diagnostikk berre når du undersøker lydproblemer.

```bat
set UAGENT_REALTIME_AUDIO_DEBUG=1
python scheck.py realtime
```

### OpenAI Realtime Function Calling

OpenAI Realtime støtter en sikkerhetsbegrenset Function Calling-integrasjon. Den gjeldende adapteren viser den skrivebeskyttede get_current_time-funksjonen automatisk. Destruktive verktøy og enhetskontroller krever en eksplisitt godkjenningsliste og bekreftelsesflyt. Grok sanntid brukar en separat adapter og brukar ikke denne OpenAI-spesifikke Function Calling-banen.
