<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="720">
</p>

<h1 align="center">uag: gateway AI universale</h1>

<p align="center">
  <b>U</b>niversal <b>A</b>I <b>Gateway — Il tuo ambiente, la tua libertà.
</p>

<p align="center">
  Operazioni sui file/Ricerca Web/Generazione e analisi di immagini/Estrazione di PDF ed Excel/Controllo IoT/Integrazione MCP<br>
  Oltre 15 fornitori / 3 interfacce utente / Esecuzione di strumenti paralleli / Marketplace delle competenze degli agenti
</p>

<p align="center">
  <a href="https://github.com/awaku7/agentcli">GitHub</a>
  ·
  <a href="https://pypi.org/project/uag/">PyPI</a>
  ·
  <a href="https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md">Leggi questo nella tua lingua</a>
</p>

---

## Perché uag?

**Liberati dai vincoli del fornitore.** La maggior parte degli assistenti IA ti lega a un provider o servizio cloud specifico. uag è diverso.

- **Funziona localmente** sul tuo computer. I tuoi dati rimangono con te (ad eccezione delle chiamate API che effettui).
- **Libertà dei provider**: OpenAI, Claude, Gemini, DeepSeek, Ollama, Azure, Bedrock... Oltre 15 provider, tutti accessibili da un'unica interfaccia. Passa dall'uno all'altro riconfigurando le variabili di ambiente: nessuna reinstallazione, nessuna migrazione.
- **131 strumenti**: I/O di file, ricerca web, generazione di immagini, scansione di dispositivi BLE, integrazione del server MCP e **76 di essi vengono eseguiti in parallelo**. Quando LLM attiva più chiamate a strumenti contemporaneamente, uag le esegue automaticamente tramite un pool di thread.
- **4 UI + A2A**: CLI, GUI, Web e protocollo da agente ad agente. Stesso motore, qualsiasi interfaccia.
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

OpenAI / Azure / Bedrock / OpenRouter / Ollama / Gemini / Vertex AI / Claude / Grok / NVIDIA / DeepSeek / HuggingFace / Alibaba Cloud (Qwen) / KIMI (Moonshot AI) / Xiaomi MiMo / LM Studio / MiniMax / **Sakana AI (Fugu)**

Tutti i fornitori condividono lo stesso set di strumenti e la stessa interfaccia. Cambia impostando `UAGENT_PROVIDER`: nessuna modifica al codice, nessuna installazione separata.

### ⚡ Esecuzione di strumenti paralleli

Quando LLM richiede più strumenti contemporaneamente, uag li **parallelizza automaticamente**.
76 strumenti sono contrassegnati come "x_parallel_safe" e vengono eseguiti contemporaneamente tramite un "ThreadPoolExecutor" a 4 thread.

**Esempio**: chiedi "Controlla il tempo nelle capitali nordiche" → LLM attiva `search_web` × 5 paesi → tutte e 5 le ricerche vengono eseguite in parallelo → risultati raccolti in un unico batch.

Gli strumenti di sola lettura (ricerca di file, calcolo hash, elenco di directory, traduzione, query DB, ecc.) sono fortemente parallelizzati.

### 🔄 Continuità delle sessioni

- **Cambia fornitore durante la sessione** con `UAGENT_PROVIDER`: la cronologia delle conversazioni viene conservata.
- **Ricarica le sessioni precedenti** con `:load <index>` — riprendi da dove avevi interrotto.
- La **caching dei risultati dello strumento** evita la riesecuzione ridondante quando si ripete la stessa chiamata dello strumento.

### 🛠 131 Strumenti

| Categoria | Strumenti |
|---|---|
| **Operazioni sui file** | leggi/scrivi/crea/elimina/cerca/grep/hash/zip |
| **Web** | fetch_url, search_web, screenshot, browser_playwright |
| **Media** | genera_immagine, analizza_immagine, img2img, audio_speech, audio_transcribe |
| **Documenti** | Estrazione PDF/PPTX/DOCX/RTF/ODT, estrazione strutturata Excel |
| **IoT** | SwitchBot (Cloud + BLE), ECHONET Lite, Materia, UPnP |
| **Strumenti di sviluppo**, ****13 strumenti idx** (Python, PHP, TypeScript, Java, C#, Dart, C/C++, Rust, Go, Swift, Kotlin, COBOL) — ottieni un indice di funzioni/classi o una definizione specifica senza leggere l'intero file** | git_ops, python_compile, lint_format, run_tests, db_query, ****13 strumenti idx** (Python, PHP, TypeScript, Java, C#, Dart, C/C++, Rust, Go, Swift, Kotlin, COBOL) — ottieni un indice di funzioni/classi o una definizione specifica senza leggere l'intero file** |
| **MCP** | Connettersi a server MCP esterni, elencare gli strumenti, eseguire |
| **A2A** | Comunicazione da agente ad agente (con altre istanze uag o server compatibili con A2A) |
| **Sistema** | variabili di ambiente, specifiche di sistema, ora, calcolo della data |
| **Navigazione del codice** | **13 strumenti idx** (Python, PHP, TypeScript, Java, C#, Dart, C/C++, Rust, Go, Swift, Kotlin, COBOL) — ottieni un indice di funzioni/classi o una definizione specifica senza leggere l'intero file |

### 🖥 3 Interfacce + A2A + VS Code

| Modalità | Comando | Scopo |
|---|---|---|
| **CLI** | `uag` | Funzionamento rapido basato su terminale |
| **GUI** | `uagg` | Interfaccia utente desktop tramite tkinter |
| **Web** | `uagw` | Accesso basato su browser |
| **Server A2A** | `uaga` | Protocollo Agent2Agent per comunicazione multi-agente |
| **VS Code** | — | Extension (Chat Panel, Explain, Refactor, Fix Error, Tools Tree View) — see [VSCODE.md](VSCODE.md) |

### 🏠 Controllo dei dispositivi IoT

- **SwitchBot**: controllo batch nel cloud e scansione/controllo BLE
- **ECHONET Lite**: scopri e controlla gli elettrodomestici (aria condizionata, luci, scaldabagni, ecc.) sulla rete locale
- **Importanza**: ispezione in sola lettura della topologia controller/bridge/dispositivo
- **UPnP**: rilevamento dispositivi e port forwarding IGD

Vedere [IOT_USECASE.md](https://github.com/awaku7/agentcli/blob/main/IOT_USECASE.md)

### 🎯 Mercato delle competenze degli agenti

`:skills mp_search` per sfogliare [SkillsMP](https://skillsmp.com) e [ClawHub](https://clawhub.ai) per le competenze della community.
Installa ed estendi le funzionalità di uag al volo.

### 🧩Gestore stato batch

uag può tenere traccia dei progressi nelle attività multi-file di lunga durata. Quando LLM elabora dozzine di file, "batch_state" mantiene su disco l'elenco dei file in sospeso, completati e con errori. Se la sessione termina o un round scade, la corsa successiva riprende da dove si era interrotta: nulla va perso.

### 🛡 Human-in-the-Loop

"human_ask" consente a LLM di fermarsi e chiedere conferma prima di eseguire operazioni distruttive (cancellazione di file, sovrascritture, comandi di shell). Mantieni il controllo.

### 🛑 Interrupt (c-key / Stop button)

Stop LLM response generation at any time and inject a stop command back to the LLM.

| Interface | How to interrupt |
|---|---|
| **CLI** | Press `c` key during LLM streaming -- the current response stops, and `"Stop"` is sent as a user message so the LLM responds accordingly |
| **WEB UI** | Click the red **■ Stop** button (appears automatically during LLM processing) |
| **Desktop GUI** | Click the red **■** button (appears automatically during LLM processing) |

The interrupt works as "prompt injection": instead of just aborting, it feeds `"Stop"` back to the LLM as a user message, allowing it to gracefully conclude or acknowledge the interruption.

Press `x` key to exit auto-pilot mode (see `:auto` command).

### 🕵️ Automazione del browser e controllo web

Due strumenti complementari basati sul drammaturgo:

- **browser_playwright**: automatizza le sessioni reali del browser: naviga, fai clic, compila moduli, estrai dati, gestisci flussi multipagina. Funziona senza testa o con testa.
- **playwright_inspector**: registra le transizioni del browser, acquisisci istantanee e screenshot DOM ad ogni passaggio. Utile per eseguire il debug delle interazioni web o controllare le modifiche alle pagine nel tempo.

### 🔄 Caricamento dinamico degli strumenti

"tool_catalog" e "tool_load" ti consentono di scoprire e abilitare gli strumenti in fase di runtime.
Non è necessario caricare tutto all'avvio: attiva solo ciò che ti serve, quando ne hai bisogno.

### 🌐 i18n/L10n

日本語 / inglese / 简体中文 / 繁體中文 / 한국어 / spagnolo / francese / Русский / e altro ancora.
Imposta "UAGENT_LANG" per cambiare. Vedi [ADD_LOCALE.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/ADD_LOCALE.md) per aggiungere una nuova locale.

Le traduzioni di questo README sono disponibili in [docs/README.translations.md](https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md).

### 🔒 Variabili d'ambiente crittografate

Memorizza le chiavi API e i segreti in ".env.sec" — un file ".env" crittografato.
Gestisci con `uag_envsec`.

## Configurazione e dettagli

- **Variabili d'ambiente**: [ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md)
- **Procedura guidata di configurazione**: `python -m uagent.setup_cli`
- **Env crittografato**: `uag_envsec` — crittografa `.env` come `.env.sec`
- **API di risposta**: impostare `UAGENT_RESPONSES=1` per la modalità API di risposta (OpenAI/Azure/Bedrock/OpenRouter/Ollama/Alibaba/LM Studio/Sakana AI)
- **Documenti per sviluppatori**: [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)
- **Piccoli suggerimenti LLM**: [SLM_TIPS.md](https://github.com/awaku7/agentcli/blob/main/SLM_TIPS.md)

## Filosofia del progetto

uag aspira a essere **la tua IA, sulla tua macchina, alle tue condizioni.**

- Nessuna dipendenza SaaS: viene eseguito localmente
- Nessun vincolo al provider: cambia in qualsiasi momento
- Nessun blocco dell'interfaccia utente: CLI/GUI/Web/A2A
- Nessuna funzione vincolata: estendila con strumenti e competenze

Un'esperienza di agente AI gratuita, libera dai vincoli del fornitore.