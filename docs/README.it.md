<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="680">
</p>

<h1 align="center">uag</h1>

<p align="center">
  <strong>Universal AI Gateway</strong><br>
  Un agente locale. Qualsiasi modello. Qualsiasi strumento. Il tuo ambiente, le tue regole.
</p>

<p align="center">
  <a href="https://github.com/awaku7/agentcli/actions"><img src="https://img.shields.io/github/actions/workflow/status/awaku7/agentcli/ci.yml?style=flat-square&label=CI" alt="CI status"></a>
  <a href="https://pypi.org/project/uag/"><img src="https://img.shields.io/pypi/v/uag?style=flat-square" alt="PyPI version"></a>
  <a href="https://pypi.org/project/uag/"><img src="https://img.shields.io/pypi/pyversions/uag?style=flat-square" alt="Python versions"></a>
  <a href="https://github.com/awaku7/agentcli/blob/main/LICENSE"><img src="https://img.shields.io/github/license/awaku7/agentcli?style=flat-square" alt="License"></a>
  <a href="https://pepy.tech/projects/uag"><img src="https://static.pepy.tech/personalized-badge/uag?period=total&units=INTERNATIONAL_SYSTEM&left_color=grey&right_color=green&left_text=downloads" alt="PyPI Downloads"></a>
</p>

<p align="center">
  <a href="https://github.com/awaku7/agentcli">GitHub</a> ·
  <a href="https://pypi.org/project/uag/">PyPI</a> ·
  <a href="https://github.com/awaku7/agentcli/discussions">Discussioni</a> ·
  <a href="https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md">Traduzioni</a>
</p>

______________________________________________________________________

**Perché uag?**

uag è un agente AI local-first che collega il modello che preferisci agli strumenti che usi davvero.
Ti offre un unico runtime estensibile per file, browser, codebase, comunicazione, API cloud,
dispositivi IoT, server MCP e flussi di lavoro multi-agente.

- **Libertà di scelta del provider** — OpenAI, Anthropic, Gemini, Azure, Bedrock, Ollama, llama.cpp, Grok, DeepSeek e altri.
- **Esecuzione local-first** — il runtime dell'agente e l'esecuzione degli strumenti restano sulla tua macchina; ne escono solo le chiamate API che scegli.
- **Un unico livello di strumenti** — gli stessi strumenti funzionano dalla CLI, dalla GUI desktop, dall'interfaccia web, da VS Code e da A2A.
- **Parallelismo nativo** — le operazioni indipendenti in sola lettura possono essere eseguite contemporaneamente.
- **Estensibile** — aggiungi strumenti, plugin, Agent Skills, server MCP e strumenti basati su Rust senza modificare il core.
- **Consapevole della sicurezza** — azioni distruttive, credenziali, controlli dei dispositivi e scritture di rete supportano conferme esplicite e controlli tramite policy.

> **In breve:** uag è il piano di controllo tra i tuoi modelli AI e il tuo ambiente reale.

> **🧠 Risultati degli strumenti sensibili al contesto** — I risultati degli strumenti di grandi dimensioni vengono tenuti fuori dal contesto del modello attivo, quando possibile. uag li memorizza come artefatti e fornisce al modello un’anteprima limitata con un riferimento Artifact stabile. Ciò può ridurre sostanzialmente il numero di token di input necessari per i turni successivi quando uno strumento produce un risultato di grandi dimensioni.
> [Guida dettagliata alla compressione del contesto](CONTEXT_COMPRESSION.it.md)

## Avvio rapido

**Python 3.11+**

```bash
python -m pip install --upgrade uag
uag
```

Al primo avvio si apre la procedura guidata di configurazione. Ti aiuta a configurare un provider e salva le impostazioni selezionate
nel tuo ambiente locale.

Per i gruppi di funzionalità più comuni:

```bash
python -m pip install "uag[core,providers,tools]"
```

> Le integrazioni specifiche della piattaforma sono opzionali. Installa solo ciò che richiede il tuo sistema operativo; vedi

```text
> What files changed in this repository?
> Search the web for today's AI news and summarize the top five stories.
> :help
```

[Quickstart](QUICKSTART.md) · [Environment](ENVIRONMENT.md)

## Interfacce

| Interfaccia | Comando | Ideale per |
|---|---|---|
| **CLI** | `uag` | Lavoro rapido, incentrato sulla tastiera |
| **GUI desktop** | `uagg` | Un'esperienza desktop nativa |
| **Interfaccia web** | `uagw` | Accesso tramite browser |
| **Server A2A** | `uaga` | Comunicazione tra agenti |
| **VS Code** | Estensione | Spiegare, ristrutturare, correggere e consultare gli strumenti nell'editor |

Tutte le interfacce condividono la stessa configurazione dei provider, il registro degli strumenti, le regole di sicurezza e i dati delle sessioni.

~~~bash
# Desktop GUI
python -m pip install "uag[platform]"

# Web UI
python -m pip install "uag[web]" fastapi uvicorn
~~~

[Interface options](USAGE.md) · [Environment](ENVIRONMENT.md)

## Cosa puoi creare

Gli adapter dei provider coprono runtime hosted e locali, tra cui:

**OpenAI · Anthropic · Gemini · Vertex AI · Azure OpenAI · Amazon Bedrock · Grok · DeepSeek · OpenRouter · Ollama · llama.cpp · LM Studio**

- Leggere, creare, modificare, cercare, calcolare hash, archiviare e ispezionare file
- Esaminare le modifiche Git, cercare segreti, eseguire test, fare linting, compilare e misurare la coverage
- Esplorare codebase estese in Python, TypeScript, JavaScript, Go, Rust, C/C++, Java, C#, COBOL, VBA e altri linguaggi
- Automatizzare browser con Playwright, inclusi flussi multipagina e download

- **MCP** — collega server di strumenti esterni, inclusi i servizi con OAuth
- **A2A** — coordina altri agenti e server compatibili
- **Cloud** — accesso alle API di AWS, Google Cloud e Azure con conferma per le scritture
- **Comunicazione** — Gmail, Bluesky, Discord, Microsoft Teams e pybitchat
- **IoT** — SwitchBot, ECHONET Lite, Matter, BACnet, Modbus TCP, OPC UA e UPnP
- **Media** — generazione/modifica di immagini, trascrizione/sintesi vocale, acquisizione dalla fotocamera e codici QR
- **Documenti** — analisi di PDF, PowerPoint, Word, Excel, CSV, JSON, YAML, SQL e log

- **SwitchBot** — individuazione Cloud e BLE, stato, controllo, batching e sottoscrizioni
- **ECHONET Lite** — individua e controlla gli elettrodomestici giapponesi, incluse le notifiche INF
- **Matter** — endpoint, cluster, attributi, cronologia dello stato, sottoscrizioni e controllo
- **BACnet / Modbus TCP / OPC UA** — letture, scritture, esplorazione e monitoraggio per l'automazione industriale e degli edifici
- **UPnP** — individuazione dei dispositivi, stato WAN e gestione del port mapping del router

### Dove si colloca uag

uag si trova tra le persone e le interfacce da un lato, e modelli, strumenti e sistemi del mondo reale dall'altro.
Coordina la conversazione, seleziona le funzionalità, applica le regole di sicurezza e mantiene il flusso di lavoro riprendibile.

~~~mermaid
flowchart LR
    UI["CLI · Desktop · Web · VS Code · A2A"] --> UAG["UAG agent runtime"]
    UAG --> MODELS["Hosted & local models"]
    UAG --> TOOLS["Tools & extensions"]
    UAG --> STATE["Sessions & context"]
    TOOLS --> SYSTEMS["Files · Code · Web · MCP · Cloud · IoT"]
    POLICY["Confirmation · Credentials · Policy"] -.-> UAG
~~~

### Plugin, Agent Skills e marketplace

Trasforma uag in un agente specializzato senza fare fork del core:

- Installa **plugin compatibili con Claude Code** da una directory, uno ZIP, un repository Git, una sorgente HTTP o un marketplace
- Raggruppa skill, sotto-agenti, server MCP, hook, comandi slash, stili di output, dipendenze e canali
- Esplora le funzionalità della community da [SkillsMP](https://skillsmp.com) e [ClawHub](https://clawhub.ai)
- Aggiungi skill e strumenti privati dell'organizzazione localmente tramite `UAGENT_EXTERNAL_TOOLS_DIR`

```text
:skills mp_search browser automation
:plugin list
:plugin install <source>
:plugin marketplace list
```

Vedi la [Guida allo sviluppo dei plugin](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP_PLUGIN.md).

- **Oltre 200 strumenti** per file, web, media, documenti, codice, cloud, comunicazione e IoT
- **Individuazione e caricamento dinamici** — usa `tool_catalog` per trovare le funzionalità e `tool_load` per abilitarle solo quando servono
- **Intelligenza del codice** — `code_map`, navigatori `idx` specifici per linguaggio, revisione Git, esecuzione dei test, linting, compilazione e misurazione della coverage
- **Plugin compatibili con Claude Code** con skill, agenti, server MCP, hook, comandi e marketplace
- **Agent Skills** da SkillsMP e ClawHub
- **Strumenti Python personalizzati** con `TOOL_SPEC` e `run_tool()`
- **Strumenti basati su Rust** per estensioni native leggere

[Tool Creator Guide](../TOOL_CREATOR_GUIDE.md) · [MCP OAuth / Proxy Guide](MCP_OAUTH_PROXY_GUIDE.md)

## Progettato per flussi di lavoro reali

### 🧠 Risultati degli strumenti sensibili al contesto

I risultati degli strumenti di grandi dimensioni vengono tenuti fuori dal contesto del modello attivo, quando possibile. uag li memorizza come artefatti e fornisce al modello un’anteprima limitata con un riferimento Artifact stabile. Ciò può ridurre sostanzialmente il numero di token di input necessari per i turni successivi quando uno strumento produce un risultato di grandi dimensioni.

Riprendi le conversazioni precedenti con `:load <index>`. I risultati degli strumenti possono essere memorizzati nella cache e i provider possono essere cambiati
senza ricostruire l'applicazione.

[Context compression](CONTEXT_COMPRESSION.it.md) · [Memory](MEMORY.md) · [Session portability](SESSION_PORTABILITY.md)

### Pilota automatico

Usa `:auto` per lavori a più cicli con un modello revisore opzionale. Imposta un limite di cicli con `--max-rounds N`.
Premi **F12** per arrestare il pilota automatico o **F12** per arrestare la risposta corrente.

Le operazioni indipendenti in sola lettura vengono eseguite contemporaneamente quando è sicuro farlo. Ricerche web, ispezione dei file,
analisi dei repository e carichi di lavoro simili possono essere completati in parallelo con un pool di worker
configurabile (`UAGENT_PARALLEL_WORKERS`). Le operazioni di scrittura restano serializzate o richiedono conferma.

La continuità delle sessioni, la cache dei risultati degli strumenti, lo stato dei batch, il recupero dopo i riavvii,
la pianificazione DAG e l'orchestrazione multi-agente rendono riprendibili i lavori complessi invece di limitarli a una sola esecuzione.

[Auto-pilot](README_AUTO.md) · [Timers](SET_TIMER.md) · [Multi-agent runtime](MULTI_AGENT_RUNTIME.md)

### 🌍 Privato, multilingue e consapevole delle policy

`human_ask` mette in pausa l'esecuzione prima delle azioni sensibili. L'eliminazione e la sovrascrittura di file, i comandi shell, i controlli dei dispositivi,
le operazioni sulle credenziali e le scritture di rete possono essere disciplinati da regole di conferma e policy.

Usa l'archivio delle credenziali invece di inserire segreti a lunga durata nei prompt:

L'interfaccia Web include l'accesso OIDC utilizzando Authorization Code + PKCE, token ID verificati, sessioni lato server e controlli di accesso a progetti/stanze. Le rivendicazioni di gruppo Microsoft Entra ID verificate possono alimentare la policy di accesso basata su directory quando configurate. Le distribuzioni Windows Active Directory, OAuth e trusted-proxy possono integrarsi tramite adattatori di identità verificati espliciti; Windows AD richiede un verificatore Kerberos/Negotiate specifico per la distribuzione e non è abilitato di default.

uag include tracciamento e metriche OpenTelemetry indipendenti dal fornitore e di attivazione per Agent, LLM, strumento, Context, Memory e operazioni di recupero. L'osservabilità è disabilitata per impostazione predefinita.

Local-first non significa che UAG funzioni completamente offline o che tutti gli strumenti siano isolati per impostazione predefinita. Le chiamate a modelli e servizi esterni dipendono dalla configurazione.

- [Enterprise policies](ENTERPRISE_POLICY.md)
- [MXC sandbox](SANDBOX_MXC.md)
- [Remote Web / A2A](REMOTE_MXC_DEFAULT.md)
- [Web identity](WEB_IDENTITY_MEMORY.md)
- [OpenTelemetry](UAG_OPENTELEMETRY_DESIGN.md)

### 🌍 Traduzione multilingue

- `translate_text` supporta Google Translate e il client Python ufficiale di DeepL tramite `provider=auto`, `provider=deepl` o `provider=google`.
- Le definizioni degli strumenti sono disponibili in 37 lingue oltre all’inglese (38 in totale), con il mantenimento dei segnaposto e degli identificatori tecnici.

La voce full-duplex è disponibile tramite OpenAI Realtime, Azure OpenAI, xAI Grok Voice, Gemini Live
e Bedrock Nova Sonic, con cancellazione dell'eco AEC3 opzionale e chiamate di funzione realtime limitate dalle regole di sicurezza.

[Translations](README.translations.md) · [IoT](IOT_USECASE.md) · [Communication](COMMUNICATION.md)

## Documentazione

| Argomento | Documentazione |
|---|---|
| Variabili d'ambiente | [docs/ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/docs/ENVIRONMENT.md) |
| Architettura e invarianti | [docs/ARCHITECTURE.md](https://github.com/awaku7/agentcli/blob/main/docs/ARCHITECTURE.md) |
| Computer Use | [docs/COMPUTER_USE_IMPLEMENTATION.md](https://github.com/awaku7/agentcli/blob/main/docs/COMPUTER_USE_IMPLEMENTATION.md) |
| Strumenti del repository | [docs/REPOSITORY_TOOLS.md](https://github.com/awaku7/agentcli/blob/main/docs/REPOSITORY_TOOLS.md) |
| Casi d'uso IoT | [docs/IOT_USECASE.md](https://github.com/awaku7/agentcli/blob/main/docs/IOT_USECASE.md) |
| Strumenti di comunicazione | [docs/COMMUNICATION.md](https://github.com/awaku7/agentcli/blob/main/docs/COMMUNICATION.md) |
| Pilota automatico | [docs/README_AUTO.md](https://github.com/awaku7/agentcli/blob/main/docs/README_AUTO.md) |
| MCP OAuth / Proxy | [docs/MCP_OAUTH_PROXY_GUIDE.md](https://github.com/awaku7/agentcli/blob/main/docs/MCP_OAUTH_PROXY_GUIDE.md) |
| Estensione VS Code | [docs/VSCODE.md](https://github.com/awaku7/agentcli/blob/main/docs/VSCODE.md) |
| Guida per sviluppatori | [src/uagent/docs/DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md) |
| Flusso degli strumenti | [src/uagent/docs/TOOL_FLOW.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/TOOL_FLOW.md) |

[Quickstart](QUICKSTART.md) · [Architecture](ARCHITECTURE.md) · [Context management](UAG_CONTEXT_MANAGEMENT_DESIGN.md)

## Sviluppo e contributi

```bash
git clone https://github.com/awaku7/agentcli.git
cd agentcli
python -m pip install -e ".[core,providers,test]"
```

Esegui i controlli preliminari alla PR:

```bash
python -m ruff check src tests
python -m black --check src tests
python -m pytest -q .
```

Per il flusso di sviluppo completo, vedi [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md).

Segnalazioni di bug, idee per funzionalità, miglioramenti alla documentazione, traduzioni, strumenti, skill e pull request sono benvenuti.
Apri un issue o una discussione prima di apportare modifiche rilevanti. Leggi la [Guida per sviluppatori](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)
e esegui i controlli sopra indicati prima di inviare una pull request.

## Licenza

Distribuito con licenza [Apache License 2.0](https://github.com/awaku7/agentcli/blob/main/LICENSE).
