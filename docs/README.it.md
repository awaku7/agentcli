<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="720">
</p>

<h1 align="center">uag: gateway AI universale</h1>

<p align="center">
  <b>U</b>niversal <b>A</b>I <b>G</b>ateway — Your environment, your freedom.
</p>

<p align="center">
  File ops / Web search / Image generation &amp; analysis / PDF &amp; Excel extraction / IoT control / MCP integration<br>
  15+ providers / 3 UIs / Parallel tool execution / Agent Skills marketplace
</p>

<p align="center">
  <a href="https://github.com/awaku7/agentcli">GitHub</a>
  ·
  <a href="https://pypi.org/project/uag/">PyPI</a>
  ·
  <a href="https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md">Read this in your language</a>
</p>

---

## Perché uag?

**Liberati dai vincoli del fornitore.** La maggior parte degli assistenti IA ti lega a un provider o servizio cloud specifico. uag è diverso.

- **Funziona localmente** sul tuo computer. I tuoi dati rimangono con te (ad eccezione delle chiamate API che effettui).
- **Libertà dei provider**: OpenAI, Claude, Gemini, DeepSeek, Ollama, Azure, Bedrock, HuggingFace... Oltre 15 provider, tutti accessibili da un'unica interfaccia. Passa dall'uno all'altro riconfigurando le variabili di ambiente: nessuna reinstallazione, nessuna migrazione.
- **131 strumenti**: I/O file, ricerca Web, generazione di immagini, Gmail, scansione dispositivi BLE, integrazione server MCP — **76 sono sicuri in parallelo** (fino a 8 eseguiti contemporaneamente tramite pool di thread, configurabile tramite `UAGENT_PARALLEL_WORKERS`). Quando LLM attiva più chiamate di strumenti contemporaneamente, uag le parallelizza automaticamente.
- **3 UI + A2A**: CLI, GUI, Web e protocollo da agente ad agente. Stesso motore, qualsiasi interfaccia.
- **IoT ready**: SwitchBot, ECHONET Lite, Matter, UPnP: controlla i tuoi dispositivi domestici tramite l'intelligenza artificiale.
- **Competenze agente**: installa competenze sviluppate dalla comunità dal mercato. Estendi uag all'infinito.

uag è **il tuo assistente AI alle tue condizioni**. Non legato a un provider, non legato a un'interfaccia, non legato a una piattaforma.

## Avvio rapido

```bash
pip install uag
uag
```

Al primo avvio, la procedura guidata di installazione ti guida attraverso la configurazione del provider.
Vedi [ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md) per tutte le variabili di ambiente.

## Caratteristiche

### 🧠 Architettura multi-provider

OpenAI / Azure / Bedrock / OpenRouter / Ollama / Gemini / Vertex AI / Claude / Grok / NVIDIA / DeepSeek / Z.AI (Zhipu AI) / HuggingFace / Alibaba Cloud (Qwen) / KIMI (Moonshot AI) / Xiaomi MiMo / LM Studio / MiniMax / **Sakana AI (Fugu)**

Tutti i fornitori condividono lo stesso set di strumenti e la stessa interfaccia. Cambia impostando `UAGENT_PROVIDER`: nessuna modifica al codice, nessuna installazione separata.

### ⚡ Esecuzione di strumenti paralleli

Quando LLM richiede più strumenti contemporaneamente, uag li **parallelizza automaticamente**.
76 strumenti sono contrassegnati come `x_parallel_safe` e vengono eseguiti contemporaneamente tramite un `ThreadPoolExecutor` (8 thread per impostazione predefinita; imposta `UAGENT_PARALLEL_WORKERS` per modificare).

**Esempio**: chiedi "Controlla il tempo nelle capitali nordiche" → LLM attiva `search_web` × 5 paesi → tutte e 5 le ricerche vengono eseguite in parallelo → risultati raccolti in un unico batch.

Gli strumenti di sola lettura (ricerca di file, calcolo hash, elenco di directory, traduzione, query DB, ecc.) sono fortemente parallelizzati.

### 🔄 Continuità delle sessioni

- **Switch providers mid-session** with `UAGENT_PROVIDER` — conversation history is preserved.
- **Reload past sessions** with `:load <index>` — pick up where you left off.
- **Tool result caching** avoids redundant re-execution when the same tool call repeats.

### 🛠 131 Strumenti

| Categoria | Strumenti |
|---|---|
| **Operazioni sui file** | leggi/scrivi/crea/elimina/ricerca/grep/hash/zip, parse_eml (file .eml) |
| **Web** | fetch_url, search_web, screenshot, browser_playwright |
| **Media** | genera_immagine, analizza_immagine, img2img, audio_speech, audio_transcribe |
| **Documenti** | Estrazione PDF/PPTX/DOCX/RTF/ODT, estrazione strutturata Excel |
| **Comunicazione** | gmail_send, gmail_read, bluesky, discord_channel, team_webhook — vedi [COMMUNICATION.md](https://github.com/awaku7/agentcli/blob/main/docs/COMMUNICATION.md) |
| **IoT** | SwitchBot (Cloud + BLE), ECHONET Lite, Materia, UPnP |
| **Strumenti di sviluppo** | git_ops, python_compile, lint_format, run_tests, db_query, **13 navigatori del codice sorgente (famiglia idx)** |
| **MCP** | Connettersi a server MCP esterni, elencare gli strumenti, eseguire |
| **A2A** | Comunicazione da agente ad agente (con altre istanze uag o server compatibili con A2A) |
| **Sistema** | variabili di ambiente, specifiche di sistema, ora, calcolo della data |
| **Nav sorgente** | **13 strumenti idx** per Python, PHP, TypeScript, Java, C#, Dart, C/C++, Rust, Go, Swift, Kotlin, COBOL — ottieni un indice di funzione/classe o una definizione specifica senza leggere l'intero file |

### 🖥 4 interfacce + estensione VS Code

| Modalità | Comando | Scopo |
|---|---|---|
| **CLI** | `uag` | Funzionamento rapido basato su terminale |
| **GUI** | `uagg` | Interfaccia utente desktop tramite tkinter |
| **Web** | `uagw` | Accesso basato su browser |
| **Server A2A** | `uaga` | Protocollo Agent2Agent per comunicazione multi-agente |
| **Codice VS** | — | [Estensione](https://github.com/awaku7/agentcli/blob/main/VSCODE.md) con pannello chat, spiegazione, refactoring, correzione errori e visualizzazione ad albero degli strumenti |

Vedi [VSCODE.md](https://github.com/awaku7/agentcli/blob/main/VSCODE.md) per i dettagli sull'estensione VS Code: installazione, comandi, combinazioni di tasti e configurazione.

### 🏠 Controllo dei dispositivi IoT

- **SwitchBot**: controllo batch nel cloud e scansione/controllo BLE
- **ECHONET Lite**: scopri e controlla gli elettrodomestici (aria condizionata, luci, scaldabagni, ecc.) sulla rete locale
- **Importanza**: ispezione in sola lettura della topologia controller/bridge/dispositivo
- **UPnP**: rilevamento dispositivi e port forwarding IGD

Vedere [IOT_USECASE.md](https://github.com/awaku7/agentcli/blob/main/IOT_USECASE.md)

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

Vedi [README_AUTO.md](https://github.com/awaku7/agentcli/blob/main/README_AUTO.md) per la documentazione completa.

### 🧩Gestore stato batch

uag può tenere traccia dei progressi nelle attività multi-file di lunga durata. Quando LLM elabora dozzine di file, "batch_state" mantiene su disco l'elenco dei file in sospeso, completati e con errori. Se la sessione termina o un round scade, la corsa successiva riprende da dove si era interrotta: nulla va perso.

### 🛡 Human-in-the-Loop

"human_ask" consente a LLM di fermarsi e chiedere conferma prima di eseguire operazioni distruttive (cancellazione di file, sovrascritture, comandi di shell). Mantieni il controllo.

### 🛑 Interruzione (tasto C/pulsante Stop)

Interrompi la generazione della risposta LLM in qualsiasi momento e inserisci un comando di arresto nel LLM.

| Interfaccia | Come interrompere |
|---|---|
| **CLI** | Premi il tasto "c" durante lo streaming LLM: la risposta corrente si interrompe e "Stop" viene inviato come messaggio utente in modo che LLM risponda di conseguenza |
| **UI WEB** | Fare clic sul pulsante rosso ***** Interrompi** (appare automaticamente durante l'elaborazione LLM) |
| **GUI del desktop** | Fare clic sul pulsante rosso ******* (appare automaticamente durante l'elaborazione LLM) |

L'interruzione funziona come "prompt injection": invece di limitarsi ad abortire, restituisce "Stop"` all'LLM come messaggio utente, consentendogli di concludere o riconoscere con garbo l'interruzione.

Premere il tasto "x" per uscire dalla modalità pilota automatico (vedere [README_AUTO.md](https://github.com/awaku7/agentcli/blob/main/README_AUTO.md)).

### 🕵️ Automazione del browser e controllo web

Due strumenti complementari basati sul drammaturgo:

- **browser_playwright**: automatizza le sessioni reali del browser: naviga, fai clic, compila moduli, estrai dati, gestisci flussi multipagina. Funziona senza testa o con testa.
- **playwright_inspector**: registra le transizioni del browser, acquisisci istantanee DOM e screenshot ad ogni passaggio. Utile per eseguire il debug delle interazioni web o controllare le modifiche alle pagine nel tempo.

### 🔄 Caricamento dinamico degli strumenti

"tool_catalog" e "tool_load" ti consentono di scoprire e abilitare gli strumenti in fase di runtime.
Non è necessario caricare tutto all'avvio: attiva solo ciò che ti serve, quando ne hai bisogno.

### 🌐 i18n/L10n

日本語 / Inglese / 简体中文 / 繁體中文 / 한국어 / Español / Français / Русский / e altro ancora.
Imposta "UAGENT_LANG" per cambiare. Vedi [ADD_LOCALE.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/ADD_LOCALE.md) per aggiungere una nuova locale.

Le traduzioni di questo README sono disponibili in [docs/README.translations.md](https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md).

### 🔒 Variabili d'ambiente crittografate

Memorizza le chiavi API e i segreti in ".env.sec" — un file ".env" crittografato.
Gestisci con `uag_envsec`.

## Configurazione e dettagli

- **Variabili d'ambiente**: [ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md)
- **Procedura guidata di configurazione**: `python -m uagent.setup_cli`
- **Env crittografato**: `uag_envsec` — crittografa `.env` come `.env.sec`
- **API di risposta**: impostare `UAGENT_RESPONSES=1` per la modalità API di risposta (OpenAI/Azure/Bedrock/OpenRouter/Ollama/Alibaba/LM Studio/Sakana AI). Abilitazione automatica per Sakana AI (Fugu).
- **Documenti per sviluppatori**: [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)
- **Piccoli suggerimenti LLM**: [SLM_TIPS.md](https://github.com/awaku7/agentcli/blob/main/SLM_TIPS.md)

## Filosofia del progetto

uag aspira a essere **la tua IA, sulla tua macchina, alle tue condizioni.**

- Nessuna dipendenza SaaS: viene eseguito localmente
- Nessun vincolo al provider: cambia in qualsiasi momento
- Nessun blocco dell'interfaccia utente: CLI/GUI/Web/A2A
- Nessuna funzione vincolata: estendila con strumenti e competenze

Un'esperienza di agente AI gratuita, libera dai vincoli del fornitore.
