<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="720">
</p>

<h1 align="center">uag: gateway AI universale</h1>

<p align="center">
  <b>U</b>niversal <b>A</b>I <b>G</b>ateway — Il tuo ambiente, la tua libertà.
</p>

<p align="center">
  Operazioni sui file / Ricerca web / Generazione e analisi delle immagini / Estrazione PDF e Excel / Controllo IoT / Integrazione MCP<br>
  24 providers / 3 UI / Esecuzione di strumenti paralleli / Agent Skills marketplace
</p>

<p align="center">
  <a href="https://github.com/awaku7/agentcli">GitHub</a>
  ·
  <a href="https://pypi.org/project/uag/">PyPI</a>
  ·
  <a href="README.translations.md">Read this in your language</a>
</p>

______________________________________________________________________

## Perché uag?

**Liberati dai vincoli del fornitore.** La maggior parte degli assistenti IA ti lega a un provider o servizio cloud specifico. uag è diverso.

- **Funziona localmente** sul tuo computer. I tuoi dati rimangono con te (ad eccezione delle chiamate API che effettui).
- **Libertà dei provider**: OpenAI, Claude, Gemini, DeepSeek, Ollama, Azure, Bedrock, HuggingFace... 24 provider, tutti accessibili da un'unica interfaccia. Passa dall'uno all'altro riconfigurando le variabili di ambiente: nessuna reinstallazione, nessuna migrazione.
- **229 strumenti**: I/O file, ricerca Web, generazione di immagini, Gmail, scansione dispositivi BLE, integrazione server MCP — **130 sono sicuri in parallelo** (fino a 8 eseguiti contemporaneamente tramite pool di thread, configurabile tramite `UAGENT_PARALLEL_WORKERS`). Quando LLM attiva più chiamate di strumenti contemporaneamente, uag le parallelizza automaticamente.
- **3 UI + A2A**: CLI, GUI, Web e protocollo da agente ad agente. Stesso motore, qualsiasi interfaccia.
- **Competenze agente**: installa competenze sviluppate dalla comunità dal mercato. Estendi uag all'infinito.

uag è **il tuo assistente AI alle tue condizioni**. Non legato a un provider, non legato a un'interfaccia, non legato a una piattaforma.

## Avvio rapido

```bash
pip install uag
uag
```

Al primo avvio, la procedura guidata di installazione ti guida attraverso la configurazione del provider.
Vedi [docs/ENVIRONMENT.md](ENVIRONMENT.md) per tutte le variabili di ambiente.

## Caratteristiche

### 🧠 Architettura multi-provider

OpenAI / PFN (PLaMo) / Azure / Bedrock / OpenRouter / Ollama / Gemini / Vertex AI / Claude / Grok / NVIDIA / Novita / DeepSeek / Z.AI (Zhipu AI) / HuggingFace / Alibaba Cloud (Qwen) / KIMI (Moonshot AI) / Xiaomi MiMo / LM Studio / MiniMax / Sakana AI (Fugu) / SAKURA AI Engine / Together AI / Vercel AI Gateway

Tutti i fornitori condividono lo stesso set di strumenti e la stessa interfaccia. Cambia impostando `UAGENT_PROVIDER`: nessuna modifica al codice, nessuna installazione separata.

### ⚡ Esecuzione di strumenti paralleli

Quando LLM richiede più strumenti contemporaneamente, uag li **parallelizza automaticamente**.
130 strumenti sono contrassegnati come `x_parallel_safe` e vengono eseguiti contemporaneamente tramite un `ThreadPoolExecutor` (8 thread per impostazione predefinita; imposta `UAGENT_PARALLEL_WORKERS` per modificare).

**Esempio**: chiedi "Controlla il tempo nelle capitali nordiche" → LLM attiva `search_web` × 5 paesi → tutte e 5 le ricerche vengono eseguite in parallelo → risultati raccolti in un unico batch.

Gli strumenti di sola lettura (ricerca di file, calcolo hash, elenco di directory, traduzione, query DB, ecc.) sono fortemente parallelizzati.

### 🧩 Sistema di plug-in (compatibile con Claude Code)

uagent implementa un **sistema di plug-in compatibile con Claude Code**. I plugin raggruppano competenze, agenti, server MCP, hook e altro in directory autonome con il manifest `.claude-plugin/plugin.json`.

**Componenti supportati**: competenze, agenti secondari, server MCP, hook (12 eventi del ciclo di vita), comandi slash, stili di output, userConfig, dipendenze, canali, marketplace

**CLI commands**:

```
:plugin list                         # Elenca i plugin installati
:plugin install <source> [--scope]
:plugin install <name>@<marketplace>  # Installa dal marketplace
:plugin remove <name>                # Disinstalla
:plugin enable/disable <name>        # Attiva/disattiva
:plugin marketplace add/remove/list  # Gestisci i marketplace
:plugin init <name>                  # Crea la struttura di un nuovo plugin
```

Consulta la documentazione completa in [DEVELOP_PLUGIN.md](../src/uagent/docs/DEVELOP_PLUGIN.md).

### 🔄 Continuità delle sessioni

- **Cambiare provider durante la sessione**: `UAGENT_PROVIDER` — la cronologia delle conversazioni viene conservata.
- **Ricaricare le sessioni precedenti**: `:load <index>` — riprendi da dove avevi interrotto.

### 🛠 229 Strumenti

| Categoria | Strumenti |
|---|---|
| **Operazioni sui file** | leggi/scrivi/crea/elimina/ricerca/grep/hash/zip, file_type, parse_eml (file .eml) |
| **Web** | fetch_url, search_web, screenshot, browser_playwright |
| **Media** | genera_immagine, analizza_immagine, img2img, audio_speech, audio_transcribe |
| **Documenti** | Estrazione PDF/PPTX/DOCX/RTF/ODT, estrazione strutturata Excel |
| **Previsione** | Previsione di serie temporali con 9 modelli (AutoARIMA, Prophet, LightGBM, CatBoost, TimesFM, ecc.), selezione automatica del modello, generazione di grafici, i18n |
| **Comunicazione** | gmail_send, gmail_read, bluesky, discord_channel, team_webhook , **pybitchat** (BLE Mesh) — vedi [COMMUNICATION.md](COMMUNICATION.md) and [BITCHAT.md](BITCHAT.md)|
| **IoT** | BACnet、Modbus TCP、OPC UA、SwitchBot（Cloud + BLE）、ECHONET Lite、Matter、UPnP、reverse_geocode |
| **API cloud** | `aws_api`, `gcp_api`, `azure_api` — AWS, Google Cloud, and Azure API operations; write operations require explicit confirmation |
| **Strumenti di sviluppo** | workspace_status, git_ops, python_compile, lint_format, run_tests, db_query, **29 navigatori del codice sorgente (famiglia idx)** |
| **MCP** | Connettersi a server MCP esterni, elencare gli strumenti, eseguire — [OAuth / Proxy guide](MCP_OAUTH_PROXY_GUIDE.md) |
| **A2A** | Comunicazione da agente ad agente (con altre istanze uag o server compatibili con A2A) |
| **Sistema** | variabili di ambiente, specifiche di sistema, ora, calcolo della data, uuid_gen, slugify, quantities ||
| **Nav sorgente** | **29 strumenti idx** per Python, PHP, TypeScript, Java, C#, Dart, C/C++, Rust, Go, Swift, Kotlin, COBOL, VBA, LotusScript, Makefile — ottieni un indice di funzione/classe o una definizione specifica senza leggere l'intero file |

#### Revisione e copertura del repository

- `workspace_status`: Segnala il ramo Git dell'area di lavoro attiva, le modifiche, lo stato di sincronizzazione upstream, il runtime Python e gli indicatori di progetto comuni senza modificare i file.
- `git_review`: riepiloga modifiche Git, file rischiosi, candidati ai test e risultati segreti senza esporre valori segreti.
- `security_scan`: scansiona i file del repository per probabili segreti e file di configurazione rischiosi.
- `coverage_report`: esegui e normalizza la copertura per Python, TypeScript/JavaScript, Rust, Go, Java/Kotlin, .NET, C/C++, Ruby, PHP, Swift e Dart/Flutter.
- Le dipendenze della copertura mancante possono essere installate automaticamente quando viene richiesta l'esecuzione; `dry_run` non installa mai pacchetti.

Vedi [Strumenti di analisi del repository](REPOSITORY_TOOLS.md) per parametri, output e dettagli sulla sicurezza.

### 🖥 4 interfacce + estensione VS Code

| Modalità | Comando | Scopo |
|---|---|---|
| **CLI** | `uag` | Funzionamento rapido basato su terminale |
| **GUI** | `uagg` | Interfaccia utente desktop tramite tkinter |
| **Web** | `uagw` | Accesso basato su browser |
| **Server A2A** | `uaga` | Protocollo Agent2Agent per comunicazione multi-agente |
| **Codice VS** | — | [Estensione](VSCODE.md) con pannello chat, spiegazione, refactoring, correzione errori e visualizzazione ad albero degli strumenti |

Vedi [VSCODE.md](VSCODE.md) per i dettagli sull'estensione VS Code: installazione, comandi, combinazioni di tasti e configurazione.

### 🏠 Controllo dei dispositivi IoT

- **Importanza**: ispezione in sola lettura della topologia controller/bridge/dispositivo

Vedere [IOT_USECASE.md](IOT_USECASE.md)

### 🏠 Controllo dispositivi IoT

- **BACnet**: lettura/scrittura di dispositivi BACnet/IP (HVAC, illuminazione, contatori di potenza). Abbonamento COV per notifiche push
- **Modbus TCP**: lettura/scrittura registri e bobine di mantenimento/input. Monitoraggio delle modifiche basato su polling
- **OPC UA**: navigazione nello spazio degli indirizzi, lettura/scrittura di variabili, iscrizione alle modifiche dei dati
- **SwitchBot**: controllo batch nel cloud e scansione/controllo BLE. Abbonamento basato su polling
- **ECHONET Lite**: rilevamento, controllo e iscrizione alle notifiche INF dagli elettrodomestici (aria condizionata, luci, scaldabagni, ecc.)
- **Matter**: controllo lettura/scrittura + abbonamento attributi per il monitoraggio del cambiamento di stato
- **UPnP**: rilevamento dispositivi e inoltro porta IGD

Vedi [IOT_USECASE.md](IOT_USECASE.md)

### 🎯 Mercato delle competenze degli agenti

`:skills mp_search` per sfogliare [SkillsMP](https://skillsmp.com) e [ClawHub](https://clawhub.ai) per le competenze della community.
Installa ed estendi le funzionalità di uag al volo.

### 🤖 Pilota automatico (`:auto`)

uag può **perseguire autonomamente un obiettivo in più round LLM**. Perfetto per attività complesse in più fasi che richiedono un perfezionamento iterativo.

- **Come funziona**: Ogni round prevede una domanda principale (Passaggio A) seguita da un giudizio del revisore (Passaggio B) che decide "COMPLETO o CONTINUA?"
- **Stesso provider, stessa API**: il giudizio del revisore utilizza lo stesso percorso del codice della query principale, incluso il supporto dell'API Responses.
- **LLM giudice separato** (opzionale): imposta "UAGENT_AP_PROVIDER" per utilizzare un fornitore/modello diverso per il revisore (ad esempio, utilizza un modello più economico per giudicare).
- **Esci in qualsiasi momento**: premi il tasto "x" per interrompere immediatamente, anche a metà risposta. Oppure lascia che sia il revisore a decidere quando l'obiettivo viene raggiunto.
- **Configurabile**: `--max-rounds N` per controllare il budget.

Vedi [README_AUTO.md](README_AUTO.md) per la documentazione completa.

### 🧩Gestore stato batch

uag può tenere traccia dei progressi nelle attività multi-file di lunga durata. Quando LLM elabora dozzine di file, "batch_state" mantiene su disco l'elenco dei file in sospeso, completati e con errori. Se la sessione termina o un round scade, la corsa successiva riprende da dove si era interrotta: nulla va perso.

### 🛡 Intervento umano nel ciclo

"human_ask" consente a LLM di fermarsi e chiedere conferma prima di eseguire operazioni distruttive (cancellazione di file, sovrascritture, comandi di shell). Mantieni il controllo.

### 🛑 Interruzione (tasto C/pulsante Stop)

Interrompi la generazione della risposta LLM in qualsiasi momento e inserisci un comando di arresto nel LLM.

| Interfaccia | Come interrompere |
|---|---|
| **CLI** | Premi il tasto "c" durante lo streaming LLM: la risposta corrente si interrompe e "Stop" viene inviato come messaggio utente in modo che LLM risponda di conseguenza |
| **UI WEB** | Fare clic sul pulsante rosso \*\*\*\*\* Interrompi\*\* (appare automaticamente durante l'elaborazione LLM) |
| **GUI del desktop** | Fare clic sul pulsante rosso \*\*\*\*\*\*\* (appare automaticamente durante l'elaborazione LLM) |

L'interruzione funziona come "prompt injection": invece di limitarsi ad abortire, restituisce "Stop"\` all'LLM come messaggio utente, consentendogli di concludere o riconoscere con garbo l'interruzione.

Premere il tasto "x" per uscire dalla modalità pilota automatico (vedere [README_AUTO.md](README_AUTO.md)).

### 🕵️ Automazione del browser e controllo web

Due strumenti complementari basati sul drammaturgo:

- **browser_playwright**: automatizza le sessioni reali del browser: naviga, fai clic, compila moduli, estrai dati, gestisci flussi multipagina. Funziona senza testa o con testa.
- **playwright_inspector**: registra le transizioni del browser, acquisisci istantanee DOM e screenshot ad ogni passaggio. Utile per eseguire il debug delle interazioni web o controllare le modifiche alle pagine nel tempo.

### 🔄 Caricamento dinamico degli strumenti

"tool_catalog" e "tool_load" ti consentono di scoprire e abilitare gli strumenti in fase di runtime.
Non è necessario caricare tutto all'avvio: attiva solo ciò che ti serve, quando ne hai bisogno.

### 🦀 Rust Native Tools

`uuid_gen` e `slugify` sono implementati in Rust (tramite PyO3) per garantire prestazioni migliori.

### 🌐 i18n/L10n

日本語 / Inglese / 简体中文 / 繁體中文 / 한국어 / Español / Français / Русский / e altro ancora.
Imposta "UAGENT_LANG" per cambiare. Vedi [ADD_LOCALE.md](../src/uagent/docs/DEVELOP_I18N.md) per aggiungere una nuova locale.

Le traduzioni di questo README sono disponibili in [docs/README.translations.md](README.translations.md).

### 🔒 Variabili d'ambiente crittografate

Memorizza le chiavi API e i segreti in ".env.sec" — un file ".env" crittografato.
Gestisci con `uag_envsec`.

## Configurazione e dettagli

- **Variabili d'ambiente**: [docs/ENVIRONMENT.md](ENVIRONMENT.md)
- **Procedura guidata di configurazione**: `python -m uagent.setup_cli`
- **Env crittografato**: `uag_envsec` — crittografa `.env` come `.env.sec`
- **API di risposta**: impostare `UAGENT_RESPONSES=1` per la modalità API di risposta (OpenAI/Azure/Bedrock/OpenRouter/Ollama/Alibaba/LM Studio/Sakana AI). Abilitazione automatica per Sakana AI (Fugu).
- **Documenti per sviluppatori**: [DEVELOP.md](../src/uagent/docs/DEVELOP.md)
- **Tool flow**: [TOOL_FLOW.md](../src/uagent/docs/TOOL_FLOW.md)
- **Piccoli suggerimenti LLM**: [SLM_TIPS.md](SLM_TIPS.md)

## Filosofia del progetto

uag aspira a essere **la tua IA, sulla tua macchina, alle tue condizioni.**

- Nessuna dipendenza SaaS: viene eseguito localmente
- Nessun vincolo al provider: cambia in qualsiasi momento
- Nessun blocco dell'interfaccia utente: CLI/GUI/Web/A2A
- Nessuna funzione vincolata: estendila con strumenti e competenze

Un'esperienza di agente AI gratuita, libera dai vincoli del fornitore.

### ✨ Crea i tuoi strumenti

[it.md](TOOL_CREATOR_GUIDE.it.md)
Consulta qui la guida dettagliata.

## Contribuire

I contributi sono benvenuti! Segnalazioni di bug, suggerimenti di funzionalità, miglioramenti alla documentazione, traduzioni e richieste pull: tutto apprezzato.

- **Issues**: Apri un problema GitHub per bug o richieste di funzionalità.
- **Pull request**: Crea un fork del repository, apporta le modifiche e invia una PR. Consulta [DEVELOP.md](../src/uagent/docs/DEVELOP.md) per la configurazione dello sviluppo e le linee guida.

Realtime Voce e AEC3

## La modalità vocale Realtime supporta microfono full duplex e ingresso/uscita altoparlante. Se manca il backend AEC3, uag installa automaticamente pywebrtc-audio.

**Provider in tempo reale**: OpenAI Realtime, Azure OpenAI GPT Realtime, Google Gemini Live, xAI Grok Voice e Amazon Bedrock Nova Sonic. L'SDK di streaming bidirezionale di Bedrock viene installato automaticamente solo quando viene selezionato Bedrock.

```bat
python scheck.py realtime
```

AEC3 utilizza il segnale effettivo del microfono (vicino) e l'audio effettivamente inviato all'altoparlante (lontano). Abilita la diagnostica solo quando si esaminano i problemi audio.

```bat
set UAGENT_REALTIME_AUDIO_DEBUG=1
python scheck.py realtime
```

### OpenAI Realtime Function Calling

OpenAI Realtime supporta un'integrazione Function Calling con sicurezza limitata. L'adattatore corrente espone automaticamente la funzione get_current_time di sola lettura. Gli strumenti distruttivi e i controlli dei dispositivi richiedono una lista consentita e un flusso di conferma espliciti. Grok realtime utilizza un adattatore separato e non utilizza questo percorso Function Calling specifico di OpenAI.

## Architettura e invarianti operative

Consulta [ARCHITECTURE.md](ARCHITECTURE.md) per i contratti di implementazione permanenti che coprono il ciclo di vita A2A, i contesti I18N, l’installazione delle dipendenze opzionali, la sicurezza degli strumenti, le capacità dei provider, i confini di fiducia OAuth, gli eventi strutturati e la verifica di accettazione.
