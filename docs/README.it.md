<p align="center">
 <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="720">
</p>

<h1 align="center">uag — Gateway AI universale</h1>

<p align="center">
 <b>U</b>niversal <b>A</b>I <b</b>Gateway — Il tuo ambiente, la tua libertà.
</p>

<p align="center">
 Operazioni sui file / Ricerca Web / Generazione e analisi di immagini / Estrazione di PDF ed Excel / Controllo IoT / Integrazione MCP<br>
 24 fornitori / 3 UI / Esecuzione di strumenti paralleli / Mercato delle competenze degli agenti
</p>

<p align="center">
 <a href="https://github.com/awaku7/agentcli">GitHub</a>
 ·
 <a href="https://pypi.org/project/uag/">PyPI</a>
 ·
 <a href="https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md">Read this in your language</a>
</p>

______________________________________________________________________

## Perché uag?

**Liberati dai vincoli del fornitore.** La maggior parte degli assistenti IA ti lega a un provider o servizio cloud specifico. uag è diverso.

- **Funziona localmente** sul tuo computer. I tuoi dati rimangono con te (eccetto API chiamate effettuate).
- **Libertà dei fornitori**: OpenAI, Claude, Gemini, DeepSeek, Ollama, Azure, Bedrock, Novita, HuggingFace... 24 fornitori, tutti accessibili da un'unica interfaccia. Passa dall'uno all'altro riconfigurando le variabili di ambiente: nessuna reinstallazione, nessuna migrazione.
- **222 strumenti**: I/O file, ricerca Web, generazione di immagini, Gmail, scansione dispositivi BLE, integrazione server MCP — **130 sono contrassegnati staticamente come sicuri per il parallelo** (fino a 8 eseguiti contemporaneamente tramite pool di thread, configurabile tramite `UAGENT_PARALLEL_WORKERS`). Quando LLM attiva più chiamate allo strumento contemporaneamente, uag le parallelizza automaticamente.
- **3 UI + A2A**: CLI, GUI, Web e protocollo da agente ad agente. Stesso motore, qualsiasi interfaccia.
- **IoT ready**: SwitchBot, ECHONET Lite, Matter, UPnP: controlla i tuoi dispositivi domestici tramite l'intelligenza artificiale.
- **Agent Skills**: installa competenze create dalla community dal marketplace. Estendi uag all'infinito.

uag è **il tuo assistente AI alle tue condizioni**. Non legato a un provider, non legato a un'interfaccia, non legato a una piattaforma.

## Avvio rapido

```bash
pip install uag
uag
```

Al primo avvio, la procedura guidata di installazione guida l'utente attraverso la configurazione del provider.
Vedi [docs/ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/docs/ENVIRONMENT.md) per tutti gli ambienti variabili.

## Computer Use

Computer Use è attivabile e supporta sia un runtime del browser Playwright visibile
sia un runtime del desktop. Quando abilitato, entrambi i runtime vengono creati e registrati;

```bat
set UAGENT_COMPUTER_USE=1
```

Utilizzare `desktop` per selezionare invece il runtime del desktop del sistema operativo. Le risorse Runtime vengono
chiuse insieme all'uscita normale, `Ctrl-C` e all'arresto del processo. Imposta
`UAGENT_COMPUTER_HEADLESS=1` per CI basati su browser o test del fumo.
Vedi [docs/COMPUTER_USE_IMPLEMENTATION.md](docs/COMPUTER_USE_IMPLEMENTATION.md)
per i dettagli sull'integrazione e sulla sicurezza.

## Voce in tempo reale e AEC3

La modalità vocale in tempo reale supporta OpenAI Realtime, Azure OpenAI GPT Realtime, xAI Grok Voice API, Google Gemini Multimodal Live API e Amazon Bedrock Nova Sonic con microfono full-duplex e I/O altoparlante. Il backend AEC3 `pywebrtc-audio` richiesto viene installato automaticamente e l'SDK di streaming bidirezionale opzionale di Bedrock viene installato automaticamente solo quando viene selezionato il provider Bedrock:

```bash
python scheck.py realtime
```

La pipeline AEC3 riceve il segnale effettivo del microfono (`near`) e l'audio effettivamente trasmesso all'oratore (`far`) in modo che l'assistente possa ascoltare mentre parlando. Abilita la diagnostica solo quando si esaminano i problemi audio:

```bat
set UAGENT_REALTIME_AUDIO_DEBUG=1
python scheck.py realtime
```

### OpenAI Chiamata di funzione in tempo reale

OpenAI Realtime supporta un'integrazione di chiamata di funzione con sicurezza limitata. L'adattatore in tempo reale corrente espone automaticamente `get_current_time` di sola lettura. Gli strumenti distruttivi e i controlli dei dispositivi non vengono esposti senza una lista consentita e un flusso di conferma espliciti. Grok realtime utilizza un adattatore separato e non utilizza questo percorso di chiamata di funzione specifico di OpenAI.

## Caratteristiche

### 🧠 Architettura multi-provider

OpenAI / PFN (PLaMo) / Azure / Bedrock / OpenRouter / Ollama / llama.cpp / Gemini / Vertex AI / Claude / Grok / NVIDIA / Novita / DeepSeek / Z.AI (Zhipu AI) / HuggingFace / Alibaba Cloud (Qwen) / KIMI (Moonshot AI) / Xiaomi MiMo / LM Studio / MiniMax / Sakana AI (Fugu) / SAKURA AI Engine / Together AI / Vercel AI Gateway

Tutti i provider condividono lo stesso set di strumenti e la stessa interfaccia. Cambia impostando `UAGENT_PROVIDER`: nessuna modifica al codice, nessuna installazione separata.

#### Ollama e llama.cpp

Ollama e llama.cpp sono fornitori separati. Ollama utilizza il proprio servizio e la gestione dei modelli, mentre `llama.cpp` si connette a un endpoint compatibile con `llama-server` OpenAI:

```bash
# llama.cpp / llama-server
UAGENT_PROVIDER=llama_cpp
UAGENT_LLAMA_CPP_BASE_URL=http://localhost:8080/v1
UAGENT_LLAMA_CPP_DEPNAME=local-model
UAGENT_LLAMA_CPP_API_KEY=dummy
```

Il provider llama.cpp utilizza la chat Percorso compatibile con i completamenti. Mantieni `UAGENT_RESPONSES=0` a meno che non sia configurato un proxy compatibile.

### ⚡ Esecuzione parallela degli strumenti

Quando LLM richiede più strumenti contemporaneamente, uag li **lizza automaticamente in parallelo**.
130 strumenti sono contrassegnati staticamente come `x_parallel_safe` ed vengono eseguiti contemporaneamente tramite un `ThreadPoolExecutor` (8 thread per impostazione predefinita; imposta `UAGENT_PARALLEL_WORKERS` per cambiare).

**Esempio**: Chiedi "Controlla il tempo nelle capitali nordiche" → LLM attiva `search_web` × 5 paesi → tutte e 5 le ricerche vengono eseguite in parallelo → risultati raccolti in un unico batch.

Il conteggio attuale si basa sui moduli dello strumento che definiscono un `TOOL_SPEC` (attualmente 222, inclusi i 2 strumenti supportati da Rust in `src/uagent/tools_rust/`). `http_request` utilizza una sicurezza sensibile al metodo: le chiamate `GET`/`HEAD`/`OPTIONS` possono essere eseguite in parallelo, mentre i metodi di scrittura rimangono seriali.

Gli strumenti di sola lettura (ricerca di file, calcolo hash, elenco di directory, traduzione, query DB, ecc.) sono fortemente parallelizzati.

### 🧩 Il sistema di plugin (compatibile con il codice Claude)

uagent implementa un **Claude Sistema plugin compatibile con codice**. I plugin raggruppano competenze, agenti, server MCP, hook e altro in directory autonome con un manifest `.claude-plugin/plugin.json`.

**Componenti supportati**: competenze, agenti secondari, server MCP, hook (12 eventi del ciclo di vita), comandi slash, stili di output, userConfig, dipendenze, canali, marketplace

**CLI comandi**:

```
:elenco plugin # Elenca i plugin installati
:plugin install <source> [--scope] # Installa (dir/zip/git/http)
:plugin install <nome>@<marketplace> # Installa dal marketplace
:plugin rimuovi <nome> # Disinstalla
:plugin abilita/disabilita <nome> # Attiva/disattiva
:plugin marketplace aggiungi/rimuovi/elenco # Gestisci marketplaces
:plugin init <name> # Scaffold new plugin
```

Vedi [DEVELOP_PLUGIN.md](src/uagent/docs/DEVELOP_PLUGIN.md) per la documentazione completa.

### 🔄 Continuità della sessione

- **Cambia provider durante la sessione** con `UAGENT_PROVIDER` — conversazione la cronologia viene preservata.
- **Ricarica le sessioni precedenti** con `:load <index>` — riprendi da dove avevi interrotto.
- **La memorizzazione nella cache dei risultati dello strumento** evita la riesecuzione ridondante quando la stessa chiamata dello strumento si ripete.

### 🛠 229 Strumenti

| Categoria | Strumenti |
|---|---|
| **Operazioni sui file** | leggi/scrivi/crea/elimina/cerca/grep/hash/zip, tipo_file, parse_eml (file .eml), `alias_percorso` |
| **Web** | fetch_url, search_web, screenshot, browser_playwright, `url_alias`, `public_transit_route` ([guida](docs/PUBLIC_TRANSIT_ROUTE.md)) |
| **Media** | genera_immagine, analizza_immagine, img2img, audio_speech, audio_transcribe |
| **Documenti** | Estrazione PDF/PPTX/DOCX/RTF/ODT, estrazione strutturata Excel |
| **Previsione** | Previsione delle serie temporali con 9 modelli (AutoARIMA, Prophet, LightGBM, CatBoost, TimesFM, ecc.), selezione automatica del modello, generazione di grafici, i18n |
| **Comunicazione** | gmail_send, gmail_read, bluesky, discord_channel, teams_webhook, **pybitchat** (BLE Mesh) — vedi [COMMUNICATION.md](https://github.com/awaku7/agentcli/blob/main/docs/COMMUNICATION.md) e [BITCHAT.md](https://github.com/awaku7/agentcli/blob/main/docs/BITCHAT.md) |
| **IoT** | SwitchBot (Cloud + BLE), ECHONET Lite, Matter, UPnP, reverse_geocode |
| **API cloud** | `aws_api`, `gcp_api`, `azure_api`: operazioni generiche AWS, Google Cloud e Azure API; le operazioni di scrittura richiedono una conferma esplicita |
| **Strumenti di sviluppo** | workspace_status, git_ops, git_review, security_scan, cover_report, python_compile, lint_format, run_tests, db_query, **29 navigatori del codice sorgente (famiglia idx)** |
| **MCP** | Connettiti a server MCP esterni, elenca gli strumenti, esegui — [Guida OAuth/Proxy](docs/MCP_OAUTH_PROXY_GUIDE.md) |
| **A2A** | Comunicazione da agente ad agente (con altre istanze uag o server compatibili con A2A) |
| **Sistema** | variabili di ambiente, specifiche di sistema, ora, calcolo della data, [quantità](docs/QUANTITIES.md), [geodesic_distance](docs/GEODESIC_DISTANCE.md), uuid_gen, slugify |
| **Nav sorgente** | **29 strumenti idx** per Python, PHP, TypeScript, Java, C#, Dart, C/C++, Rust, Go, Swift, Kotlin, COBOL, VBA, LotusScript, Makefile — ottieni un indice di funzione/classe o una definizione specifica senza leggere l'intero file |

#### Revisione e copertura del repository

- `workspace_status`: segnala il ramo Git dello spazio di lavoro attivo, modifiche, stato di sincronizzazione upstream, runtime Python e indicatori comuni di progetto senza modificare i file.
- `git_review`: riepiloga modifiche Git, file rischiosi, candidati al test e risultati segreti senza esporre valori segreti.
- `security_scan`: scansiona i file del repository per probabili segreti e file di configurazione rischiosi.
- `coverage_report`: esegui e normalizza la copertura per Python, TypeScript/JavaScript, Rust, Go, Java/Kotlin, .NET, C/C++, Ruby, PHP, Swift e Dart/Flutter.
- Le dipendenze di copertura mancanti possono essere installate automaticamente quando viene richiesta l'esecuzione; `dry_run` non installa mai pacchetti.

Vedi [Strumenti di analisi del repository](docs/REPOSITORY_TOOLS.md) per parametri, output e dettagli sulla sicurezza.

Vedi [Alias percorso e URL](docs/PATH_URL_ALIASES.md) per abbreviare percorsi di file ripetuti e URL negli argomenti dello strumento.

### 🖥 4 interfacce + codice VS Estensione

| Modalità | Comando | Scopo |
|---|---|---|
| **CLI** | `uag` | Funzionamento rapido basato su terminale |
| **GUI** | `uagg` | Interfaccia utente desktop tramite tkinter |
| **Web** | `uagw` | Accesso basato sul browser |
| **A2AServer** | `uaga` | Protocollo Agent2Agent per comunicazione multi-agente |
| **Codice VS** | — | [Estensione](https://github.com/awaku7/agentcli/blob/main/docs/VSCODE.md) con pannello chat, spiegazione, refactoring, correzione errori e visualizzazione struttura ad albero degli strumenti |

Vedi [VSCODE.md](https://github.com/awaku7/awaku7/agentcli/blob/main/docs/VSCODE.md) per i dettagli sull'estensione VS Code — installazione, comandi, combinazioni di tasti e configurazione.

### 🏠 Controllo dispositivi IoT

- **BACnet**: lettura/scrittura di dispositivi BACnet/IP (HVAC, illuminazione, contatori di potenza). Abbonamento COV per notifiche push
- **Modbus TCP**: lettura/scrittura di registri e bobine di mantenimento/immissione. Monitoraggio delle modifiche basato su polling
- **OPC UA**: navigazione nello spazio degli indirizzi, lettura/scrittura di variabili, iscrizione alle modifiche dei dati
- **SwitchBot**: controllo batch nel cloud e scansione/controllo BLE. Abbonamento basato su polling
- **ECHONET Lite**: rilevamento, controllo e abbonamento alle notifiche INF dagli elettrodomestici (aria condizionata, luci, scaldabagni, ecc.)
- **Matter**: controllo lettura/scrittura + abbonamento attributi per il monitoraggio del cambiamento di stato
- **UPnP**: rilevamento dispositivi e inoltro porta IGD

Vedi [IOT_USECASE.md](https://github.com/awaku7/agentcli/blob/main/docs/IOT_USECASE.md)

### 🎯 Mercato delle competenze dell'agente

`:skills mp_search` per sfogliare [SkillsMP](https://skillsmp.com) e [ClawHub](https://clawhub.ai) per competenze della community.
Installa ed estendi le funzionalità di uag al volo.

### 🤖 Il pilota automatico (`:auto`)

uag può **perseguire autonomamente un obiettivo in più round di LLM**. Perfetto per attività complesse in più passaggi che richiedono un perfezionamento iterativo.

- **Come funziona**: ogni round ha una query principale (Passaggio A) seguita da un giudizio del revisore (Passaggio B) che decide "COMPLETO o CONTINUA?"
- **Stesso fornitore, stesso API**: il giudizio del revisore utilizza lo stesso percorso del codice come query principale, incluso il supporto per le risposte API.
- **Giudice separato LLM** (opzionale): imposta `UAGENT_AP_PROVIDER` per utilizzare un fornitore/modello diverso per il revisore (ad esempio, utilizza un modello più economico per giudicare).
- **Esci in qualsiasi momento**: premi il tasto "x" per interrompere immediatamente, anche a metà risposta. Oppure lascia che sia il revisore a decidere quando l'obiettivo viene raggiunto.
- **Configurabile**: `--max-rounds N` per controllare il budget.

Vedi [README_AUTO.md](https://github.com/awaku7/agentcli/blob/main/docs/README_AUTO.md) per la documentazione completa.

### 🧩 Stato del batch Manager

uag può tenere traccia dei progressi nelle attività multifile di lunga durata. Quando LLM elabora dozzine di file, `batch_state` mantiene su disco l'elenco dei file in sospeso, completati e non riusciti. Se la sessione termina o un round scade, l'esecuzione successiva riprende da dove si era interrotta: nulla va perso.

### 🛡 Human-in-the-Loop

`human_ask` consente a LLM di fermarsi e chiedere conferma prima di eseguire operazioni distruttive (cancellazione di file, sovrascritture, comandi di shell). Mantieni il controllo.

### 🛑 Interrompi (tasto C/pulsante Stop)

Interrompi la generazione della risposta LLM in qualsiasi momento e invia un comando di arresto a LLM.

| Interfaccia | Come interrompere |
|---|---|
| **CLI** | Premi il tasto F12 durante lo streaming LLM: la risposta corrente si interrompe e `"Stop"` viene inviato come messaggio utente in modo che LLM risponda di conseguenza |
| **UI WEB** | Fai clic sul pulsante rosso \*\*\*\*\* Interrompi\*\* (appare automaticamente durante l'elaborazione LLM) |
| **Desktop GUI** | Fare clic sul pulsante rosso \*\*\*\*\*\*\* (appare automaticamente durante l'elaborazione LLM) |

L'interruzione funziona come "prompt injection": invece di limitarsi ad abortire, invia `"Stop"` a LLM come messaggio utente, consentendogli di concludere o riconoscere l'interruzione con garbo.

Premi il tasto F11 per uscire dalla modalità pilota automatico (vedi [README_AUTO.md](https://github.com/awaku7/agentcli/blob/main/docs/README_AUTO.md)).

### 🕵️ Automazione del browser e Web Inspector

Due strumenti complementari basati su Playwright:

- **browser_playwright**: automatizza le sessioni reali del browser: naviga, cliccare, compilare moduli, estrarre dati, gestire flussi multipagina. Funziona senza testa o con testa.
- **playwright_inspector**: registra le transizioni del browser, acquisisci istantanee e screenshot del DOM a ogni passaggio. Utile per eseguire il debug delle interazioni web o controllare le modifiche delle pagine nel tempo.

### 🔄 Caricamento dinamico degli strumenti

`tool_catalog` e `tool_load` ti consentono di scoprire e abilitare gli strumenti in fase di runtime.
Non è necessario caricare tutto all'avvio: attiva solo ciò che ti serve, quando ne hai bisogno.

### 🦀 Rust Native Tools

`uuid_gen` e `slugify` sono implementati in Rust (tramite PyO3) per migliorare le prestazioni.
Si caricano direttamente da un `.pyd` precostruito — **non è richiesta `pip install`**.

Gli sviluppatori esterni possono anche fornire strumenti basati su Rust: posiziona un `.pyd` accanto al
wrapper `.py`, usa `load_rust_pyd()` da `uagent.tools.rust_helper`, e
gli utenti ottengono lo strumento senza dipendenze aggiuntive. Vedi
[TOOL_CREATOR_GUIDE.md](https://github.com/awaku7/agentcli/blob/main/TOOL_CREATOR_GUIDE.md).

### 🌐 i18n / L10n

日本語 / Inglese / 简体中文 /繁體中文 / 한국어 / Español / Français / Русский / e altro ancora.
Imposta "UAGENT_LANG" per cambiare. Vedi [ADD_LOCALE.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/ADD_LOCALE.md) per aggiungere una nuova lingua.

Le traduzioni di questo README sono disponibili in [docs/README.translations.md](https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md).

### 🔒 Variabili di ambiente crittografate

Memorizza chiavi e segreti API in `.env.sec`: un file `.env` crittografato.
Gestisci con `uag_envsec`.

## Configurazione e dettagli

- **Variabili d'ambiente**: [docs/ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/docs/ENVIRONMENT.md)
- **Procedura guidata di configurazione**: `python -m uagent.setup_cli`
- **Encrypted env**: `uag_envsec` — crittografa `.env` come `.env.sec`
- **Risposte API**: imposta `UAGENT_RESPONSES=1` per la modalità Risposte API (OpenAI/Azure/Bedrock/OpenRouter/Ollama/Alibaba/LM Studio/Sakana AI). Abilitato automaticamente per Sakana AI (Fugu).
- **Documenti per sviluppatori**: [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)
- **Flusso dello strumento**: [TOOL_FLOW.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/TOOL_FLOW.md) — come gli strumenti vengono inviati ai LLM (maschera di genere, tool_catalog, GPT-5.4+ native tool_search)
- **Piccoli LLM suggerimenti**: [SLM_TIPS.md](https://github.com/awaku7/agentcli/blob/main/docs/SLM_TIPS.md)

## La filosofia del progetto

uag aspira ad essere **la tua intelligenza artificiale, sul tuo computer, alle tue condizioni.**

- Nessuna dipendenza SaaS: funziona localmente
- Nessun vincolo al provider: cambia in qualsiasi momento
- Nessun vincolo all'interfaccia utente: CLI / GUI / Web / A2A
- Nessun vincolo alle funzionalità: estendi con strumenti e competenze

Un'esperienza di agente AI gratuita, libera dai vincoli del fornitore.

### ✨ Crea i tuoi strumenti

Scrivere un nuovo strumento per uag è semplice: crea un singolo file `.py` con
`TOOL_SPEC` e `run_tool()`, inseriscilo in `UAGENT_EXTERNAL_TOOLS_DIR` e
è immediatamente disponibile. Per gli sviluppatori Rust, fornire un `.pyd` predefinito con
zero dipendenze aggiuntive per gli utenti.

Vedi [TOOL_CREATOR_GUIDE.md](https://github.com/awaku7/agentcli/blob/main/TOOL_CREATOR_GUIDE.md)
per la guida passo passo.

## Contribuire

I contributi sono benvenuti! Segnalazioni di bug, suggerimenti di funzionalità, miglioramenti della documentazione, traduzioni e richieste pull: tutto apprezzato.

- **Problemi**: apri un problema GitHub per bug o richieste di funzionalità.
- **Richieste pull**: esegui il fork del repository, apporta le modifiche e invia un PR. Vedi [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md) per la configurazione e le linee guida per lo sviluppo.
- **Traduzioni**: traduzioni di README e aggiunte locali sono benvenute. Vedi [ADD_LOCALE.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/ADD_LOCALE.md).
- **Strumenti e competenze**: nuovi plug-in degli strumenti e competenze dell'agente possono essere forniti tramite il marketplace.

### Controlli di sviluppo (prima del PR)

Installa prima le dipendenze di solo test. Vengono tenuti fuori dall'elenco delle dipendenze di runtime:

```bash
python -m pip install -e ".[test]"
python -m pip install black ruff
```

Esegui gli stessi controlli utilizzati da GitHub Azioni prima di eseguire il push:

```bash
python -m ruff check src tests
python -m black --check src tests
python scripts/tool_json_i18n_batch.py status
python -m pytest -q .
```

Per un'iterazione locale più veloce, esegui solo i test interessati:

```bash
pytest -q tests/<area_interessata>
```

Controlli aggiuntivi quando rilevanti:

```bash
python -m py_compile src/uagent/
mypy src/uagent
```

Dopo le modifiche locali (`.po`): `python scripts/compile_locales.py` e `python scripts/po_qc_summary.py`.

Runtime policy (dettagli in [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md) §6.1): gli helper sollevano invece di `sys.exit`; l'host dello strumento trasforma lo strumento "SystemExit"/"Exception" in stringhe di errore in modo che un singolo strumento non possa terminare il processo. Le uscite fail-fast all'avvio rimangono intenzionali.

## Architettura e invarianti operative

Vedi [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) per i contratti durevoli che coprono il ciclo di vita A2A, i contesti I18N, l'installazione opzionale delle dipendenze, la sicurezza degli strumenti, le funzionalità del provider, i limiti di attendibilità OAuth, gli eventi strutturati e la verifica dell'accettazione.

## Enterprise Policy Engine

Sono supportati i criteri a livello di organizzazione per strumenti, fornitori, credenziali, server MCP, reti, competenze e plug-in. Imposta `UAGENT_POLICY_FILE` su un file di criteri JSON/YAML; vedi [docs/ENTERPRISE_POLICY.md](docs/ENTERPRISE_POLICY.md) per esempi di configurazione, ruoli, conferma e liste consentite.

### Runtime ripristino e orchestrazione

Vedi [RESTART_RECOVERY.md](docs/RESTART_RECOVERY.md) / [DAG_SCHEDULER.md](docs/DAG_SCHEDULER.md) / [MULTI_AGENT_RUNTIME.md](docs/MULTI_AGENT_RUNTIME.md) per ripristino durevole, esecuzione sensibile alle dipendenze, orchestrazione multi-agente e utilizzo remoto di A2A.

Vedi [DISTRIBUTED_COORDINATION.md](docs/DISTRIBUTED_COORDINATION.md) per il coordinamento del lease del leader a runtime condiviso.
