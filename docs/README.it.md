<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="720">
</p>

# uag (Agente IA locale)

uag è un agente interattivo che esegue **comandi**, manipola **file** e legge **vari formati di dati** (PDF/PPTX/Excel, ecc.) sul tuo PC locale. Offre tre interfacce: CLI, GUI e Web.

uag è progettato per **liberarti dalle app bloccate su un fornitore**: usa l’interfaccia più adatta al tuo flusso di lavoro, cambia provider e mantieni il controllo del tuo ambiente.

GitHub: https://github.com/awaku7/agentcli

## Installazione

Puoi installare `uag` tramite pip:

```bash
pip install uag
```

Dopo l'installazione, il primo avvio di `uag` avvierà automaticamente una **procedura guidata di configurazione interattiva** per configurare le variabili d'ambiente. Per informazioni dettagliate sulla configurazione e la crittografia, consulta **[ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md)**.

## Caratteristiche principali

- **Set di strumenti pratici**: Dotato di strumenti per la manipolazione di file, ricerca web, estrazione dati (PDF/PPTX/Excel), generazione di immagini e analisi, tutti eseguibili nel tuo ambiente locale.
- **Supporto multi-provider**: Supporta OpenAI / Azure / Bedrock / OpenRouter / Ollama / Gemini / Vertex AI / Claude / Grok / NVIDIA.
- **Interfacce flessibili**: 
  - **CLI**: `uag` / `python -m uagent`
  - **GUI**: `uagg` / `python -m uagent.gui`
  - **Web**: `uagw` / `python -m uagent.web`
- **MCP (Model Context Protocol)**: Supporto per la connessione a server di strumenti MCP esterni.
- **Continuità di sessione**: Mantiene il contesto della conversazione anche quando si cambiano provider o modelli.
- **Web Inspector**: Salva automaticamente transizioni del browser, DOM e screenshot con `playwright_inspector`.
- **Documentazione integrata**: Accedi istantaneamente a documentazione interna dettagliata usando il comando `uag docs`.

## Utilizzo

### Avvio e uscita
Esegui `uag` dal tuo terminale per iniziare. Digita `:exit` per uscire.

### Server A2A (Agent2Agent)
Puoi avviare un server HTTP compatibile con A2A separato dalle interfacce esistenti.
```bash
uaga
# o python -m uagent.a2a.server
```

### Nota su Responses API

Se imposti `UAGENT_RESPONSES=1`, Responses API viene usata per i provider supportati: OpenAI / Azure / Bedrock / OpenRouter / Ollama.
Gemini / Claude / Vertex AI usano i rispettivi percorsi API nativi e non sono coperti da Responses API.
Per altri provider, uag torna al percorso specifico del provider o al flusso chat-completions.

Vedi [ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md) per le impostazioni `UAGENT_A2A_*` come autenticazione, host, porta, ricaricamento, URL base pubblico, concorrenza e motore.

### Suggerimenti pratici (continuità e controllo)
- `:tools`: Visualizza un elenco degli strumenti caricati.
- `:logs [n]`: Mostra i log di sessione (`n` per specificare il numero di voci).
- `:load <index>`: Carica una sessione passata per riprendere la conversazione.
- `:skills`: Seleziona e carica le abilità dell'agente (ruoli o istruzioni aggiuntive).
- `:shrink [n]`: Organizza la cronologia per mantenere solo gli ultimi `n` messaggi per risparmiare token.

## Configurazione e dettagli

### Variabili d'ambiente e configurazione
Per impostazioni dettagliate (chiavi API, lingua di visualizzazione `UAGENT_LANG`, impostazioni di riduzione cronologia, ecc.), consulta **[ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md)**.
- **Setup**: Configura in modo interattivo tramite `python -m uagent.setup_cli`.
- **Crittografia**: Cripta i tuoi file `.env` in modo sicuro usando lo strumento `uag_envsec`.
- **Aggiornamento**: Usa `uag_envsec add --file .env.sec --key NAME --value VALUE` per aggiungere o aggiornare una variabile in un file crittografato esistente.

### Sviluppatori e internazionalizzazione
- **Documentazione sviluppatore**: [`src/uagent/docs/DEVELOP.md`](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)
- **Aggiunta di locali**: [`src/uagent/docs/ADD_LOCALE.md`](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/ADD_LOCALE.md)
- **README in altre lingue**: [English](https://github.com/awaku7/agentcli/blob/main/README.md) / [日本語](https://github.com/awaku7/agentcli/blob/main/docs/README.ja.md) / [Deutsch](https://github.com/awaku7/agentcli/blob/main/docs/README.de.md) / [Español](https://github.com/awaku7/agentcli/blob/main/docs/README.es.md) / [Français](https://github.com/awaku7/agentcli/blob/main/docs/README.fr.md) / [Italiano](https://github.com/awaku7/agentcli/blob/main/docs/README.it.md) / [한국어](https://github.com/awaku7/agentcli/blob/main/docs/README.ko.md) / [Português](https://github.com/awaku7/agentcli/blob/main/docs/README.pt_BR.md) / [Русский](https://github.com/awaku7/agentcli/blob/main/docs/README.ru.md) / [ไทย](https://github.com/awaku7/agentcli/blob/main/docs/README.th.md) / [简体中文](https://github.com/awaku7/agentcli/blob/main/docs/README.zh_CN.md) / [繁體中文](https://github.com/awaku7/agentcli/blob/main/docs/README.zh_TW.md) / [Polski](https://github.com/awaku7/agentcli/blob/main/docs/README.pl.md) / [Tiếng Việt](https://github.com/awaku7/agentcli/blob/main/docs/README.vi.md) / [Bahasa Indonesia](https://github.com/awaku7/agentcli/blob/main/docs/README.id.md) / [العربية](https://github.com/awaku7/agentcli/blob/main/docs/README.ar.md) / [हिन्दी](https://github.com/awaku7/agentcli/blob/main/docs/README.hi.md) / [Português](https://github.com/awaku7/agentcli/blob/main/docs/README.pt.md) / [Svenska](https://github.com/awaku7/agentcli/blob/main/docs/README.sv.md) / [Norsk bokmål](https://github.com/awaku7/agentcli/blob/main/docs/README.nb.md) / [Suomi](https://github.com/awaku7/agentcli/blob/main/docs/README.fi.md) / [Nederlands](https://github.com/awaku7/agentcli/blob/main/docs/README.nl.md) / [Čeština](https://github.com/awaku7/agentcli/blob/main/docs/README.cs.md) / [Українська](https://github.com/awaku7/agentcli/blob/main/docs/README.uk.md) / [Swahili](https://github.com/awaku7/agentcli/blob/main/docs/README.sw.md) / [Bengali](https://github.com/awaku7/agentcli/blob/main/docs/README.bn.md) / [Persian](https://github.com/awaku7/agentcli/blob/main/docs/README.fa.md) / [Mongolian](https://github.com/awaku7/agentcli/blob/main/docs/README.mn.md) / [Marathi](https://github.com/awaku7/agentcli/blob/main/docs/README.mr.md)
