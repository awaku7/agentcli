<p align="center">
 <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="720">
</p>

<h1 align="center">uag — Universele AI Gateway</h1>

<p align="center">
 <b>U</b>universeel <b>A</b>I <b>G</b>ateway — Uw omgeving, uw vrijheid.
</p>

<p align="center">
 Bestandsbeheer / Web zoeken / Afbeelding genereren en analyseren / PDF- en Excel-extractie / IoT-controle / MCP-integratie<br>
 24 providers / 3 UI's / Parallelle uitvoering van tools / Agent Vaardighedenmarktplaats
</p>

<p align="center">
 <a href="https://github.com/awaku7/agentcli">GitHub</a>
 ·
 <a href="https://pypi.org/project/uag/">PyPI</a>
 ·
 <a href="https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md">Read this in your language</a>
</p>

______________________________________________________________________

## Waarom uag?

**Ontsnap aan de leverancierlock-in.** De meeste AI-assistenten binden u aan een specifieke provider of cloudservice. uag is anders.

- **Wordt lokaal uitgevoerd** op uw computer. Je gegevens blijven bij je (behalve API oproepen die je doet).
- **Providervrijheid**: OpenAI, Claude, Gemini, DeepSeek, Ollama, Azure, Bedrock, Novita, HuggingFace... 24 providers, allemaal toegankelijk via één enkele interface. Wissel ertussen door de omgevingsvariabelen opnieuw te configureren - geen herinstallatie, geen migratie.
- **222 tools**: bestands-I/O, zoeken op internet, afbeeldingen genereren, Gmail, scannen van BLE-apparaten, MCP serverintegratie — **130 zijn statisch gemarkeerd parallel-veilig** (maximaal 8 worden gelijktijdig uitgevoerd via threadpool, configureerbaar via `UAGENT_PARALLEL_WORKERS`). Wanneer de LLM meerdere tooloproepen tegelijk activeert, parallelliseert uag deze automatisch.
- **3 UI's + A2A**: CLI, GUI, Web en Agent-to-Agent-protocol. Dezelfde engine, elke interface.
- **IoT gereed**: SwitchBot, ECHONET Lite, Matter, UPnP — bedien uw thuisapparaten via AI.
- **Agentvaardigheden**: Installeer door de community ontwikkelde vaardigheden van de markt. Breid uag eindeloos uit.

uag is **uw AI-assistent op uw voorwaarden**. Niet gebonden aan een provider, niet gebonden aan een interface, niet gebonden aan een platform.

## Snelle start

```bash
pip install uag
uag
```

Bij de eerste start leidt de installatiewizard u door de providerconfiguratie.
Zie [docs/ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/docs/ENVIRONMENT.md) voor alle omgevingsvariabelen.

## Computer Use

Computer Use is opt-in en ondersteunt zowel een zichtbare Playwright browserruntime
en een desktopruntime. Indien ingeschakeld, worden beide runtimes gemaakt en geregistreerd;

```bat
set UAGENT_COMPUTER_USE=1
```

Gebruik `desktop` om in plaats daarvan de desktopruntime van het besturingssysteem te selecteren. Runtime bronnen zijn
samengesloten bij normaal afsluiten, `Ctrl-C` en afsluiten van processen. Stel
`UAGENT_COMPUTER_HEADLESS=1` in voor browsergebaseerde CI- of rooktests.
Zie [docs/COMPUTER_USE_IMPLEMENTATION.md](docs/COMPUTER_USE_IMPLEMENTATION.md)
voor de integratie- en veiligheidsdetails.

## Realtime Voice en AEC3

De realtime voice-modus ondersteunt OpenAI Realtime, Azure OpenAI GPT Realtime, xAI Grok Voice API, Google Gemini Multimodal Live API en Amazon Bedrock Nova Sonic met full-duplex microfoon en luidspreker-I/O. De vereiste `pywebrtc-audio` AEC3-backend wordt automatisch geïnstalleerd, en Bedrock's optionele bidirectionele streaming SDK wordt alleen automatisch geïnstalleerd wanneer de Bedrock-provider is geselecteerd:

```bash
python scheck.py realtime
```

De AEC3-pijplijn ontvangt het feitelijke microfoonsignaal (`dichtbij`) en de audio die daadwerkelijk aan de spreker wordt doorgegeven (`ver`), zodat de assistent kan luisteren terwijl spreken. Schakel diagnostiek alleen in bij het onderzoeken van audioproblemen:

```bat
set UAGENT_REALTIME_AUDIO_DEBUG=1
python scheck.py realtime
```

### OpenAI Realtime Function Calling

OpenAI Realtime ondersteunt een veiligheidsbeperkte Function Calling-integratie. De huidige realtime adapter stelt automatisch alleen-lezen `get_current_time` beschikbaar. Destructieve tools en apparaatcontroles worden niet zichtbaar zonder een expliciete toelatingslijst en bevestigingsstroom. Grok realtime gebruikt een afzonderlijke adapter en maakt geen gebruik van dit OpenAI-specifieke functieaanroeppad.

## Kenmerken

### 🧠 Architectuur met meerdere providers

OpenAI / PFN (PLaMo) / Azure / Bedrock / OpenRouter / Ollama / llama.cpp / Gemini / Vertex AI / Claude / Grok / NVIDIA / Novita / DeepSeek / Z.AI (Zhipu AI) / HuggingFace / Alibaba Cloud (Qwen) / KIMI (Moonshot AI) / Xiaomi MiMo / LM Studio / MiniMax / Sakana AI (Fugu) / SAKURA AI Engine / Together AI / Vercel AI Gateway

Alle providers delen dezelfde toolset en interface. Schakel over door `UAGENT_PROVIDER` in te stellen — geen codewijzigingen, geen afzonderlijke installaties.

#### Ollama en llama.cpp

Ollama en llama.cpp zijn afzonderlijke providers. Ollama gebruikt zijn eigen service- en modelbeheer, terwijl `llama.cpp` verbinding maakt met een `llama-server` OpenAI-compatibel eindpunt:

```bash
# Ollama
UAGENT_PROVIDER=ollama
UAGENT_OLLAMA_BASE_URL=http://localhost:11434/v1
UAGENT_OLLAMA_DEPNAME=llama3.1

# llama.cpp / llama-server
UAGENT_PROVIDER=llama_cpp
UAGENT_LLAMA_CPP_BASE_URL=http://localhost:8080/v1
UAGENT_LLAMA_CPP_DEPNAME=local-model
UAGENT_LLAMA_CPP_API_KEY=dummy
```

De llama.cpp-provider gebruikt de chat Completions-compatibel pad. Behoud `UAGENT_RESPONSES=0` tenzij een compatibele proxy is geconfigureerd.

### ⚡ Parallelle tooluitvoering

Wanneer de LLM meerdere tools tegelijkertijd opvraagt, parallelliseert uag ze automatisch\*\*.
130 tools zijn statisch gemarkeerd met `x_parallel_safe` en worden gelijktijdig uitgevoerd via een `ThreadPoolExecutor` (standaard 8 threads; ingesteld `UAGENT_PARALLEL_WORKERS` om te wijzigen).

**Voorbeeld**: Vraag "Check het weer in Scandinavische hoofdsteden" → LLM activeert `search_web` × 5 landen → alle 5 zoekopdrachten worden parallel uitgevoerd → resultaten verzameld in één batch.

De huidige telling is gebaseerd op toolmodules die een `TOOL_SPEC` definiëren (momenteel 222, inclusief de 2 door Rust ondersteunde tools in `src/uagent/tools_rust/`). `http_request` maakt gebruik van methodegevoelige veiligheid: `GET`/`HEAD`/`OPTIONS`-aanroepen kunnen parallel worden uitgevoerd, terwijl schrijfmethoden serieel blijven.

Alleen-lezen tools (zoeken naar bestanden, hash-berekening, directorylijst, vertaling, DB-query's, enz.) worden agressief geparallelliseerd.

### 🧩 Plug-insysteem (Claude codecompatibel)

uagent implementeert een **Claude Code-compatibel plug-insysteem**. Plug-ins bundelen vaardigheden, agenten, MCP servers, hooks en meer in op zichzelf staande mappen met een `.claude-plugin/plugin.json` manifest.

**Ondersteunde componenten**: vaardigheden, subagenten, MCP servers, hooks (12 levenscyclusgebeurtenissen), Slash-opdrachten, uitvoerstijlen, userConfig, afhankelijkheden, kanalen, Marktplaatsen

**CLI commando's**:

```
:plugin list # Lijst met geïnstalleerde plug-ins
:plugin install <bron> [--scope] # Installeren (dir/zip/git/http)
:plugin install <naam>@<marketplace> # Installeren vanaf marktplaats
:plugin verwijderen <naam> # Verwijderen
:plugin inschakelen/uitschakelen <naam> # Toggle
:plugin marktplaats toevoegen/verwijderen/lijst # Marktplaatsen beheren
:plugin init <naam> # Nieuwe plug-in scaffold
```

Zie [DEVELOP_PLUGIN.md](src/uagent/docs/DEVELOP_PLUGIN.md) voor volledige documentatie.

### 🔄 Sessiecontinuïteit

- **Van provider wisselen middensessie** met `UAGENT_PROVIDER` — de gespreksgeschiedenis blijft behouden.
- **Herlaad eerdere sessies** met `:load <index>` — ga verder waar u was gebleven.
- **Cache van toolresultaten** voorkomt overbodige heruitvoering wanneer dezelfde toolaanroep wordt herhaald.

### 🛠 229 Tools

| Categorie | Hulpmiddelen |
|---|---|
| **Bestandsbewerkingen** | lezen/schrijven/maken/verwijderen/zoeken/grep/hash/zip, file_type, parse_eml (.eml-bestanden), `path_alias` |
| **Web** | fetch_url, search_web, screenshot, browser_playwright, `url_alias`, `public_transit_route` ([gids](docs/PUBLIC_TRANSIT_ROUTE.md)) |
| **Media** | genereer_afbeelding, analyseer_afbeelding, img2img, audio_speech, audio_transcribe |
| **Documenten** | PDF/PPTX/DOCX/RTF/ODT-extractie, gestructureerde extractie in Excel |
| **Voorspelling** | Tijdreeksvoorspelling met 9 modellen (AutoARIMA, Prophet, LightGBM, CatBoost, TimesFM, etc.), automatische modelselectie, plotgeneratie, i18n |
| **Communicatie** | gmail_send, gmail_read, bluesky, discord_channel, teams_webhook, **pybitchat** (BLE Mesh) — zie [COMMUNICATION.md](https://github.com/awaku7/agentcli/blob/main/docs/COMMUNICATION.md) en [BITCHAT.md](https://github.com/awaku7/agentcli/blob/main/docs/BITCHAT.md) |
| **IoT** | SwitchBot (Cloud + BLE), ECHONET Lite, Matter, UPnP, reverse_geocode |
| **Cloud-API's** | `aws_api`, `gcp_api`, `azure_api` — generieke AWS-, Google Cloud- en Azure API-bewerkingen; schrijfbewerkingen vereisen expliciete bevestiging |
| **Ontwikkeltools** | workspace_status, git_ops, git_review, security_scan, dekkingsrapport, python_compile, lint_format, run_tests, db_query, **29 broncode-navigators (idx-familie)** |
| **MCP** | Maak verbinding met externe MCP-servers, geef tools weer, voer uit: [OAuth / Proxy-handleiding](docs/MCP_OAUTH_PROXY_GUIDE.md) |
| **A2A** | Communicatie tussen agenten (met andere uag-instanties of A2A-compatibele servers) |
| **Systeem** | env vars, systeemspecificaties, tijd, datumberekening, [quantities](docs/QUANTITIES.md), [geodesic_distance](docs/GEODESIC_DISTANCE.md), uuid_gen, slugify |
| **Bronnavigatie** | **29 idx-tools** voor Python, PHP, TypeScript, Java, C#, Dart, C/C++, Rust, Go, Swift, Kotlin, COBOL, VBA, LotusScript, Makefile — krijg een functie/klasse-index of specifieke definitie zonder het hele bestand te lezen |

#### Repository review en dekking

- `workspace_status`: rapporteer de Git-branch van de actieve werkruimte, wijzigingen, upstream synchronisatiestatus, Python runtime en algemene projectmarkeringen zonder bestanden te wijzigen.
- `git_review`: vat Git-wijzigingen, risicovolle bestanden, testkandidaten en geheime bevindingen samen zonder geheime waarden bloot te leggen.
- `security_scan`: scan repositorybestanden op waarschijnlijke geheimen en risicovolle configuratiebestanden.
- `coverage_report`: voer en normaliseer de dekking voor Python, TypeScript/JavaScript, Rust, Go, Java/Kotlin, .NET, C/C++, Ruby, PHP, Swift en Dart/Flutter.
- Ontbrekende dekkingsafhankelijkheden kunnen automatisch worden geïnstalleerd wanneer uitvoering wordt gevraagd; `dry_run` installeert nooit pakketten.

Zie [Repository Analysis Tools](docs/REPOSITORY_TOOLS.md) voor parameters, uitvoer en veiligheidsdetails.

Zie [Pad- en URL-aliassen](docs/PATH_URL_ALIASES.md) voor het inkorten van herhaalde bestandspaden en URL's in toolargumenten.

### 🖥 4 Interfaces + VS-code-extensie

| Modus | Commando | Doel |
|---|---|---|
| **CLI** | `uag` | Snelle terminalgebaseerde bediening |
| **GUI** | `uagg` | Desktop-UI via tkinter |
| **Web** | `uagw` | Browsergebaseerde toegang |
| **A2A Server** | `uaga` | Agent2Agent-protocol voor communicatie met meerdere agenten |
| **VS-code** | — | [Extensie](https://github.com/awaku7/agentcli/blob/main/docs/VSCODE.md) met Chat Panel, Leg uit, Refactor, Fix Error en Tools Tree View |

Zie [VSCODE.md](https://github.com/awaku7/agentcli/blob/main/docs/VSCODE.md) voor details over de VS Code-extensie – installatie, opdrachten, sneltoetsen en configuratie.

### 🏠 IoT-apparaatbeheer

- **BACnet**: BACnet/IP-apparaten lezen/schrijven (HVAC, verlichting, energiemeters). COV-abonnement voor pushmeldingen
- **Modbus TCP**: registers en spoelen lezen/schrijven/invoeren. Op peilingen gebaseerde wijzigingsmonitoring
- **OPC UA**: Blader door adresruimte, lees/schrijf variabelen, abonneer u op gegevenswijzigingen
- **SwitchBot**: Cloud batchcontrole en BLE-scan/controle. Op peilingen gebaseerd abonnement
- **ECHONET Lite**: ontdek, beheer en abonneer u op INF-meldingen van huishoudelijke apparaten (airconditioning, verlichting, waterverwarmers, enz.)
- **Kwestie**: lees-/schrijfcontrole + attribuutabonnement voor monitoring van statuswijzigingen
- **UPnP**: apparaatdetectie en IGD-poortdoorsturen

Zie [IOT_USECASE.md](https://github.com/awaku7/agentcli/blob/main/docs/IOT_USECASE.md)

### 🎯 Agent Skills Marketplace

`:skills mp_search` om door [SkillsMP](https://skillsmp.com) en [ClawHub](https://clawhub.ai) te bladeren voor de community vaardigheden.
Installeer en breid de mogelijkheden van uag direct uit.

### 🤖 Auto-Pilot (`:auto`)

uag kan **autonoom een doel nastreven in meerdere LLM ronden**. Perfect voor complexe taken die uit meerdere stappen bestaan en die iteratieve verfijning nodig hebben.

- **Hoe het werkt**: elke ronde heeft een hoofdquery (stap A) gevolgd door een oordeel van de recensent (stap B) die beslist: "COMPLETE or CONTINUE?"
- **Dezelfde provider, dezelfde API**: het oordeel van de recensent gebruikt hetzelfde codepad als de hoofdquery, inclusief ondersteuning voor antwoorden API.
- **Afzonderlijke rechter LLM** (optioneel): stel `UAGENT_AP_PROVIDER` in om een andere provider/model te gebruiken voor de recensent (gebruik bijvoorbeeld een goedkoper model voor beoordeling).
- **Op elk gewenst moment afsluiten**: druk op de F11-toets om onmiddellijk te stoppen, zelfs halverwege de reactie. Of laat de recensent beslissen wanneer het doel is bereikt.
- **Configureerbaar**: `--max-rounds N` om het budget te controleren.

Zie [README_AUTO.md](https://github.com/awaku7/agentcli/blob/main/docs/README_AUTO.md) voor volledige documentatie.

### 🧩 Batchstatus Manager

uag kan de voortgang van langlopende taken met meerdere bestanden volgen. Wanneer de LLM tientallen bestanden verwerkt, bewaart `batch_state` de lijst met openstaande, voltooide en mislukte bestanden op schijf. Als de sessie eindigt of er een time-out optreedt, wordt de volgende run hervat vanaf het punt waarop deze is gestopt. Er gaat niets verloren.

### 🛡 Human-in-the-Loop

`human_ask` laat de LLM pauzeren en om uw bevestiging vragen voordat hij destructieve bewerkingen uitvoert (bestand verwijderen, overschrijven, shell-opdrachten). Jij behoudt de controle.

### 🛑 Onderbreken (c-toets / stopknop)

Stop het genereren van LLM-reacties op elk gewenst moment en injecteer een stopcommando terug naar de LLM.

| Interface | Onderbreken |
|---|---|
| **CLI** | Druk op de F12-toets tijdens het streamen van LLM - het huidige antwoord stopt en `"Stop"` wordt verzonden als een gebruikersbericht, zodat de LLM overeenkomstig reageert |
| **WEBUI** | Klik op de rode knop **■ Stoppen** (verschijnt automatisch tijdens de verwerking van LLM) |
| **Bureaublad GUI** | Klik op de rode **■** knop (verschijnt automatisch tijdens de verwerking van LLM) |

De interrupt werkt als "prompt injection": in plaats van alleen maar af te breken, wordt `"Stop"` teruggestuurd naar de LLM als een gebruikersbericht, zodat deze de onderbreking netjes kan beëindigen of bevestigen.

Druk op de F11-toets om de automatische pilootmodus te verlaten (zie [README_AUTO.md](https://github.com/awaku7/agentcli/blob/main/docs/README_AUTO.md)).

### 🕵️ Browserautomatisering en Web Inspector

Twee aanvullende op Playwright gebaseerde tools:

- **browser_playwright**: Automatiseer echte browsersessies: navigeren, klikken, formulieren invullen, uitpakken gegevens, omgaan met stromen van meerdere pagina's. Werkt zonder hoofd of zonder hoofd.
- **playwright_inspector**: Neem browserovergangen op, maak bij elke stap DOM-snapshots en schermafbeeldingen. Handig voor het debuggen van webinteracties of het controleren van paginawijzigingen in de loop van de tijd.

### 🔄 Met het dynamisch laden van tools

`tool_catalog` en `tool_load` kunt u tools tijdens runtime ontdekken en inschakelen.
Het is niet nodig om alles bij het opstarten te laden: activeer alleen wat u nodig heeft, wanneer u het nodig heeft.

### 🦀 Rust Native Tools

`uuid_gen` en `slugify` is geïmplementeerd in Rust (via PyO3) voor betere prestaties.
Ze laden rechtstreeks vanuit een vooraf gebouwde `.pyd` — **geen `pip install` vereist**.

Externe ontwikkelaars kunnen ook op Rust gebaseerde tools leveren: plaats een `.pyd` naast de
wrapper `.py`, gebruik `load_rust_pyd()` van `uagent.tools.rust_helper`, en
gebruikers krijgen de tool zonder extra afhankelijkheden. Zie
[TOOL_CREATOR_GUIDE.md](https://github.com/awaku7/agentcli/blob/main/TOOL_CREATOR_GUIDE.md).

### 🌐 i18n / L10n

日本語 / Engels / 简体中文 /繁體中文 / 한국어 / Español / Français / Русский / en meer.
Stel `UAGENT_LANG` in om te schakelen. Zie [ADD_LOCALE.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/ADD_LOCALE.md) om een nieuwe landinstelling toe te voegen.

Vertalingen van deze README zijn beschikbaar in [docs/README.translations.md](https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md).

### 🔒 Gecodeerde omgevingsvariabelen

Sla API sleutels en geheimen op in `.env.sec` — een gecodeerd `.env`-bestand.
Beheren met `uag_envsec`.

## Configuratie en details

- **Omgevingsvariabelen**: [docs/ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/docs/ENVIRONMENT.md)
- **Installatiewizard**: `python -m uagent.setup_cli`
- **Gecodeerde env**: `uag_envsec` — versleutelen `.env` als `.env.sec`
- **Responses API**: Stel `UAGENT_RESPONSES=1` in voor de modus Responses API (OpenAI/Azure/Bedrock/OpenRouter/Ollama/Alibaba/LM Studio/Sakana AI). Automatisch ingeschakeld voor Sakana AI (Fugu).
- **Ontwikkelaarsdocumenten**: [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)
- **Toolstroom**: [TOOL_FLOW.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/TOOL_FLOW.md) — hoe tools naar LLM's worden verzonden (genremasker, tool_catalog, GPT-5.4+ native tool_search)
- **Kleine LLM tips**: [SLM_TIPS.md](https://github.com/awaku7/agentcli/blob/main/docs/SLM_TIPS.md)

## Projectfilosofie

uag streeft ernaar **uw AI te zijn, op uw machine, op uw voorwaarden.**

- Geen SaaS-afhankelijkheid — draait lokaal
- Geen provider-lock-in — op elk gewenst moment overstappen
- Geen UI-lock-in — CLI / GUI / Web / A2A
- Geen feature-lock-in — uit te breiden met tools en vaardigheden

Een gratis AI-agent-ervaring, vrij van leverancierlock-in.

### ✨ Maak je eigen tools

Het schrijven van een nieuwe tool voor uag is eenvoudig: maak een enkel `.py`-bestand met
`TOOL_SPEC` en `run_tool()`, plaats het in `UAGENT_EXTERNAL_TOOLS_DIR`, en
het is onmiddellijk beschikbaar. Voor Rust-ontwikkelaars: stuur een vooraf gebouwde `.pyd` met
nul extra afhankelijkheden voor gebruikers.

Zie [TOOL_CREATOR_GUIDE.md](https://github.com/awaku7/agentcli/blob/main/TOOL_CREATOR_GUIDE.md)
voor de stapsgewijze handleiding.

## Bijdragen

Bijdragen zijn welkom! Bugrapporten, functiesuggesties, documentatieverbeteringen, vertalingen en pull-verzoeken: allemaal gewaardeerd.

- **Problemen**: open een GitHub issue voor bugs of functieverzoeken.
- **Pull-verzoeken**: splits de opslagplaats, breng uw wijzigingen aan en dien een PR in. Zie [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md) voor ontwikkelingsinstellingen en richtlijnen.
- **Vertalingen**: README vertalingen en lokale toevoegingen zijn welkom. Zie [ADD_LOCALE.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/ADD_LOCALE.md).
- **Tools en vaardigheden**: Nieuwe toolplug-ins en Agent-vaardigheden kunnen worden bijgedragen via de marktplaats.

### Ontwikkelingscontroles (vóór PR)

Installeer eerst de alleen-testafhankelijkheden. Ze worden buiten de runtime-afhankelijkheidslijst gehouden:

```bash
python -m pip install -e ".[test]"
python -m pip install black ruff
```

Voer dezelfde controles uit als GitHub Actions voordat u pusht:

```bash
python -m ruff check src tests
python -m black --check src tests
python scripts/tool_json_i18n_batch.py status
python -m pytest -q .
```

Voor een snellere lokale iteratie voert u alleen de betreffende tests uit:

```bash
pytest -q tests/<affected_area>
```

Aanvullende controles indien relevant:

```bash
python -m py_compile src/uagent/
mypy src/uagent
```

Na wijzigingen in de locale (`.po`): `python scripts/compile_locales.py` en `python scripts/po_qc_summary.py`.

Runtime beleid (details in [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md) §6.1): helpers raisen in plaats van `sys.exit`; de toolhost verandert tool `SystemExit`/`Exception` in foutreeksen, zodat een enkele tool het proces niet kan beëindigen. Het mislukte opstarten bij het opstarten blijft opzettelijk.

## Architectuur en operationele invarianten

Zie [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) voor de duurzame contracten die de levenscyclus van A2A, I18N-contexten, optionele afhankelijkheidsinstallatie, toolveiligheid, providermogelijkheden, OAuth-vertrouwensgrenzen, gestructureerde gebeurtenissen en acceptatieverificatie bestrijken.

## Enterprise Policy Engine

Beleid op organisatieniveau voor tools, providers, inloggegevens, MCP servers, netwerken, vaardigheden en plug-ins wordt ondersteund. Stel `UAGENT_POLICY_FILE` in op een JSON/YAML beleidsbestand; zie [docs/ENTERPRISE_POLICY.md](docs/ENTERPRISE_POLICY.md) voor configuratievoorbeelden, rollen, bevestiging en toelatingslijsten.

### Runtime herstel en orkestratie

Zie [RESTART_RECOVERY.md](docs/RESTART_RECOVERY.md) / [DAG_SCHEDULER.md](docs/DAG_SCHEDULER.md) / [MULTI_AGENT_RUNTIME.md](docs/MULTI_AGENT_RUNTIME.md) voor duurzaam herstel, uitvoering met afhankelijkheidsbewustzijn, orkestratie door meerdere agenten en gebruik van A2A op afstand.

Zie [DISTRIBUTED_COORDINATION.md](docs/DISTRIBUTED_COORDINATION.md) voor lease-coördinatie van gedeelde runtime-leaders.
