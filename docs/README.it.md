<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="UAG — Universal AI Gateway" width="620">
</p>
<h1 align="center">UAG</h1>
<p align="center"><strong>Universal AI Gateway</strong><br>I tuoi modelli di IA. I tuoi strumenti. Il tuo ambiente.</p>

<p align="center">
  <a href="https://github.com/awaku7/agentcli/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/awaku7/agentcli/ci.yml?style=flat-square&label=CI" alt="CI"></a>
  <a href="https://pypi.org/project/uag/"><img src="https://img.shields.io/pypi/v/uag?style=flat-square" alt="PyPI"></a>
  <a href="https://pypi.org/project/uag/"><img src="https://img.shields.io/pypi/pyversions/uag?style=flat-square" alt="Python versions"></a>
  <a href="../LICENSE"><img src="https://img.shields.io/github/license/awaku7/agentcli?style=flat-square" alt="License"></a>
  <a href="https://pepy.tech/projects/uag"><img src="https://static.pepy.tech/personalized-badge/uag?period=total&units=INTERNATIONAL_SYSTEM&left_color=grey&right_color=green&left_text=downloads" alt="Downloads"></a>
</p>
<p align="center"><a href="../README.md">English</a> · <a href="README.translations.md">Altre lingue</a></p>

---

**UAG è un runtime open source per agenti IA che privilegia l'esecuzione locale.** Collega il modello linguistico scelto agli strumenti e ai sistemi utilizzati ogni giorno. Puoi lavorare con codice, file, browser, servizi e dispositivi tramite un'interfaccia coerente, senza vincolare i flussi di lavoro a un unico fornitore di modelli.

| **Scegli il modello** | **Collega strumenti concreti** | **Mantieni il controllo** |
| :--- | :--- | :--- |
| Modelli cloud e locali, tra cui OpenAI, Claude, Gemini, Grok, Bedrock e Ollama | File, codice, Web, MCP, Agent Skills, plugin, servizi cloud e IoT | Esecuzione locale, conferma umana, archiviazione delle credenziali e criteri configurabili |

> UAG è **un livello di esecuzione per agenti, non un fornitore di modelli**. Le richieste ai modelli esterni e ai servizi collegati dipendono dalla configurazione. «Local-first» non significa che tutto funzioni offline né che ogni strumento sia isolato per impostazione predefinita.

## Avvio rapido
<!-- README-SYNC:quick-start -->

È richiesto **Python 3.11 o successivo**. Installa UAG da [PyPI](https://pypi.org/project/uag/) e avvia la CLI interattiva:

~~~bash
python -m pip install --upgrade uag
uag
~~~

Al primo avvio, la procedura guidata aiuta a scegliere il provider e configurare le credenziali. Puoi usare anche variabili d'ambiente o l'archivio delle credenziali. Per installare in anticipo più dipendenze per provider e strumenti:

~~~bash
python -m pip install "uag[core,providers,tools]"
~~~

Poi prova a chiedere:

~~~text
> Che cosa è cambiato in questo repository Git? Riassumi i rischi.
> Trova la documentazione più recente di questa libreria e spiega i passaggi di migrazione.
> Esamina questi file e prepara un rapporto conciso.
> :help
~~~

Per iniziare, consulta la guida d'installazione per Windows, che include Git e gli ambienti virtuali, e il riferimento di configurazione: [Quickstart (Windows)](QUICKSTART.md) · [Environment](ENVIRONMENT.md).

## Interfacce
<!-- README-SYNC:interfaces -->

Tutti i punti di accesso usano lo stesso runtime dell'agente e lo stesso registro degli strumenti.

| Interfaccia | Avvio | Uso consigliato |
| :--- | :--- | :--- |
| **CLI** | `uag` | Lavoro nel terminale e automazione |
| **Desktop** | `uagg` | Conversazioni in un'applicazione nativa |
| **Web** | `uagw` | Conversazioni e stanze dal browser |
| **A2A** | `uaga` | Integrazione tra agenti |
| **VS Code** | [Guida all'estensione](VSCODE.md) | Lavorare accanto al codice |

Le interfacce Desktop e Web richiedono dipendenze aggiuntive non incluse nell'installazione iniziale `uag[core,providers,tools]`:

~~~bash
# Desktop GUI (PySide6 and platform integrations)
python -m pip install "uag[platform]"

# Web UI (authentication dependencies, FastAPI, and Uvicorn)
python -m pip install "uag[web]" fastapi uvicorn
~~~

Il server Web può tentare di installare FastAPI e Uvicorn all'avvio. Installandoli prima non sarà necessario affidarsi all'installazione automatica. Per i dettagli: [CLI usage](USAGE.md) · [Environment](ENVIRONMENT.md).

## Cosa puoi realizzare con UAG
<!-- README-SYNC:capabilities -->

| Funzionalità | Cosa offre UAG |
| :--- | :--- |
| **Flussi indipendenti dal modello** | Cambiare provider cloud o locali con `UAGENT_PROVIDER` senza riscrivere gli strumenti |
| **Codice e file** | Navigazione nei repository, analisi Git, lint, test, operazioni sui file e automazione del browser |
| **Strumenti estensibili** | Oltre 200 strumenti, ricerca dinamica con `tool_catalog` / `tool_load`, strumenti personalizzati Python e Rust |
| **Agenti connessi** | MCP, A2A, plugin compatibili con Claude Code, Agent Skills e sottoagenti |
| **Attività di lunga durata** | Pilota automatico, letture indipendenti parallele, pianificazione, ripristino dopo riavvio e sessioni persistenti |
| **Oltre il terminale** | Servizi cloud e di comunicazione, documenti, media, voce in tempo reale e protocolli IoT supportati |

### Un unico runtime, molte integrazioni
<!-- README-SYNC:integrations -->

~~~mermaid
flowchart LR
    UI["CLI · Desktop · Web · VS Code · A2A"] --> UAG["UAG agent runtime"]
    UAG --> MODELS["Hosted & local models"]
    UAG --> TOOLS["Tools & extensions"]
    UAG --> STATE["Sessions & context"]
    TOOLS --> SYSTEMS["Files · Code · Web · MCP · Cloud · IoT"]
    POLICY["Confirmation · Credentials · Policy"] -.-> UAG
~~~

**Esempi di provider supportati** sono riportati qui sotto; per le impostazioni specifiche consulta la documentazione dell'ambiente.

**OpenAI · Anthropic · Gemini · Vertex AI · Azure OpenAI · Amazon Bedrock · Grok · DeepSeek · OpenRouter · Ollama · llama.cpp · LM Studio**

[ENVIRONMENT.md](ENVIRONMENT.md)

### Personalizzazione con skill e plugin
<!-- README-SYNC:extensions -->

Estendi UAG senza cambiare il nucleo: installa Agent Skills da SkillsMP o ClawHub, collega server MCP oppure carica plugin compatibili con Claude Code che includono strumenti, skill, agenti e hook.

~~~text
:skills mp_search browser automation
:plugin list
:plugin install <source>
:plugin marketplace list
~~~

Gli strumenti personalizzati possono esporre `TOOL_SPEC` e `run_tool()`; sono supportati anche strumenti basati su Rust. Guide utili: [Tool Creator Guide](../TOOL_CREATOR_GUIDE.md) · [Plugin Development Guide](../src/uagent/docs/DEVELOP_PLUGIN.md) · [MCP OAuth / Proxy](MCP_OAUTH_PROXY_GUIDE.md).

## Progettato per flussi di lavoro reali
<!-- README-SYNC:workflows -->

### Contesto e memoria
<!-- README-SYNC:context-memory -->

I risultati voluminosi degli strumenti possono essere salvati come **artefatti** anziché occupare il contesto attivo del modello. In seguito l'agente può recuperare la porzione necessaria con `artifact_read`. Per impostazione predefinita le sessioni vengono archiviate in SQLite, con ricerca nella cronologia e revisione esplicita della memoria.

- [Context compression](CONTEXT_COMPRESSION.it.md)
- [Memory](MEMORY.md)
- [Session portability](SESSION_PORTABILITY.md)

### Automazione e collaborazione
<!-- README-SYNC:automation -->

UAG supporta letture indipendenti parallele, coordinamento di più agenti, recupero delle sessioni e pilota automatico per lavori su più turni. Avvialo con `:auto`; premi **F12** per interrompere la risposta corrente e richiedere l'arresto del pilota automatico.

- [Auto-pilot](README_AUTO.md)
- [Timers and scheduled tasks](SET_TIMER.md)
- [Multi-agent runtime](MULTI_AGENT_RUNTIME.md)

### Sicurezza e osservabilità
<!-- README-SYNC:security -->

Le operazioni sensibili possono richiedere la conferma `human_ask`. Le credenziali possono essere conservate nel gestore del sistema operativo o in file cifrati. L'interfaccia Web supporta accesso OIDC e controlli degli accessi quando configurati. Le tracce e le metriche OpenTelemetry sono **facoltative**.

- [Enterprise policies](ENTERPRISE_POLICY.md)
- [MXC sandbox](SANDBOX_MXC.md)
- [Remote Web / A2A MXC defaults](REMOTE_MXC_DEFAULT.md)
- [Web identity and rooms](WEB_IDENTITY_MEMORY.md)
- [OpenTelemetry design](UAG_OPENTELEMETRY_DESIGN.md)
- [Developer observability](../src/uagent/docs/DEVELOP_OBSERVABILITY.md)

Questi controlli sono configurabili e **non garantiscono** che qualsiasi strumento venga eseguito in una sandbox isolata. Leggi le guide di distribuzione e i criteri prima di esporre UAG a utenti o reti non attendibili.

### Lingue, dispositivi e voce
<!-- README-SYNC:languages -->

UAG include risorse per **38 impostazioni locali** (inglese più 37 traduzioni), integrazioni vocali full-duplex opzionali e strumenti per SwitchBot, Matter, ECHONET Lite, BACnet, Modbus TCP e OPC UA.

- [Translations](README.translations.md)
- [IoT use cases](IOT_USECASE.md)
- [Communication tools](COMMUNICATION.md)

## Documentazione
<!-- README-SYNC:documentation -->

Parti da queste guide e approfondisci gli argomenti di interesse:

| Da dove iniziare | Approfondimenti |
| :--- | :--- |
| [Quickstart (Windows)](QUICKSTART.md) | [Architecture](ARCHITECTURE.md) |
| [CLI usage](USAGE.md) | [Context management](UAG_CONTEXT_MANAGEMENT_DESIGN.md) |
| [Environment and providers](ENVIRONMENT.md) | [Enterprise policy](ENTERPRISE_POLICY.md) |
| [Agent Skills and plugins](../src/uagent/docs/DEVELOP_PLUGIN.md) | [Tool flow](../src/uagent/docs/TOOL_FLOW.md) |
| [MCP and OAuth](MCP_OAUTH_PROXY_GUIDE.md) | [Computer Use](COMPUTER_USE_IMPLEMENTATION.md) |
| [VS Code extension](VSCODE.md) | [Developer guide](../src/uagent/docs/DEVELOP.md) |

Puoi anche sfogliare tutta la documentazione e le altre traduzioni: [Documentation](./) · [Other languages](README.translations.md).

## Sviluppo e contributi
<!-- README-SYNC:contributing -->

~~~bash
git clone https://github.com/awaku7/agentcli.git
cd agentcli
python -m pip install -e ".[core,providers,test]"
~~~

Prima di una pull request che modifica **codice Python**, esegui i test pertinenti e le verifiche del progetto:

~~~bash
python -m ruff check src tests
python -m black --check src tests
python -m pytest -q .
~~~

Le istruzioni per contribuire e la guida per sviluppatori sono disponibili qui. Sono benvenuti segnalazioni, miglioramenti della documentazione, strumenti, traduzioni e pull request mirate: [AGENTS.md](../AGENTS.md) · [Developer guide](../src/uagent/docs/DEVELOP.md).

## Licenza
<!-- README-SYNC:license -->

UAG è distribuito con la licenza: [Apache License 2.0](../LICENSE).
