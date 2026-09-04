# UTILIZZO (Opzioni della riga di comando)

Il presente documento descrive le opzioni della riga di comando disponibili per i punti di ingresso uag.

______________________________________________________________________

## Punti di ingresso

| Comando | Modulo Python | Interfaccia |
|---|---|---|
| `uag` | `python -m uagent` | CLI (ciclo stdin) |
| `uagg` | `python -m uagent.gui` | GUI (tkinter) |
| `uagw` | `python -m uagent.web` | Server web (FastAPI) |
| `uaga` | `python -m uagent.a2a.server` | server A2A HTTP |

______________________________________________________________________

## Opzioni di avvio della CLI (`uag`)

### `--workdir` / `-C <percorso>`

Directory di lavoro. Se non specificata, si ricorre alla variabile d’ambiente `UAGENT_WORKDIR`, quindi alla directory corrente.
La directory viene creata se non esiste.

### `--tool-genre-mask <int>`

Maschera di bit del genere dello strumento. Se specificata, viene saltata la richiesta interattiva di selezione del genere.

| Bit | Genere | Descrizione |
|-----|-------|-------------|
| 1 | basic | Strumenti essenziali per file e chat |
| 2 | comm | Strumenti di comunicazione (Bluesky, Teams) |
| 4 | office | Strumenti della suite per l’ufficio (Excel, PDF, PPTX) |
| 8 | devel | Strumenti di sviluppo (git, lint, compilazione) |
| 16 | iot | Strumenti per dispositivi IoT (SwitchBot, ECHONET, Matter, UPnP) |
| 32 | exec | Strumenti per l’esecuzione di comandi |
| 64 | external | Strumenti per plugin esterni |
| 128 | media | Generazione e analisi di immagini/audio |
| 256 | file | Strumenti per la gestione dei file |
| 512 | index | Strumenti di navigazione tra sorgenti e indici |
| 1024 | dev | Strumenti per sviluppatori e repository |
| 2048 | web | Strumenti web e per browser |
| 4096 | utility | Strumenti di utilità e supporto |
| 8191 | all | Tutti gli strumenti |

Esempi:

```
uag --tool-genre-mask 1 # solo base
uag --tool-genre-mask 9 # base + sviluppo (1 + 8)
uag --tool-genre-mask 8191    # tutti gli strumenti
```

### `--use-tool` / `--no-use-tool`

Abilita o disabilita l’invio delle definizioni degli strumenti a LLM. Sovrascrive la variabile d’ambiente `UAGENT_USE_TOOL`.

- `--use-tool` forza l’invio degli strumenti.
- `--no-use-tool` disabilita l’invio degli strumenti.

Quando è disabilitato, il LLM non riceve alcuna definizione di strumento e non può chiamare alcuno strumento.

### `--computer-use` / `--no-computer-use`

Abilita o disabilita l’uso del computer. Sovrascrive la variabile d’ambiente `UAGENT_COMPUTER_USE`.

### `--inject-message` / `-M <message>`

Inserisce un messaggio in `LLM` all’avvio e termina al completamento. Ciò implica l’opzione `--non-interactive`.

### `--embedded`

Modalità incorporata per distribuzioni soggette a vincoli o sensibili alla riproducibilità.

- Disabilita l’archivio delle sessioni.
- Nasconde gli strumenti di gestione degli strumenti (`tool_catalog`, `tool_load`, `unload_tool`) a meno che non siano esplicitamente abilitati.
- Ignora `--tool-genre-mask`; utilizzare `--enable-tool` per il caricamento esplicito degli strumenti.

### `--enable-tool <nome>`

Carica esplicitamente uno strumento all’avvio. L’opzione può essere ripetuta e sono accettati anche nomi separati da virgole.

```
uag --embedded --enable-tool handle_mcp_v2 --enable-tool human_ask
uag --embedded --enable-tool handle_mcp_v2,human_ask
```

L’ordine specificato viene mantenuto e si riflette nell’ordine degli strumenti presentato a LLM. Gli strumenti abilitati esplicitamente vengono bloccati per impedire lo scaricamento automatico.

### `--plugin-dir <percorso>`

Carica i plugin dalla directory specificata. L’opzione può essere ripetuta.

______________________________________________________________________

## Opzioni solo per la CLI

### `--inject-message-auto <opzioni-obiettivo>`

Avvia la modalità automatica da un obiettivo iniettato non interattivo. Il valore utilizza le stesse opzioni di `:auto`; racchiudere tra virgolette il valore completo se contiene opzioni.

```
uag --embedded --enable-tool handle_mcp_v2 --inject-message-auto "Ordina gli elementi --max-rounds 10"
uag --embedded --enable-tool handle_mcp_v2 --inject-message-auto "Ordina gli elementi --infinite"
```

La modalità normale utilizza il percorso di valutazione del revisore. Impostare `UAGENT_AUTO_SENTINEL=1` per attivare la modalità con un unico sentinella `LLM`. In tale modalità, il LLM di destinazione deve terminare ogni risposta con esattamente uno dei seguenti:

- `<AUTO_CONTINUE>` — esegui un altro round
- `<AUTO_COMPLETE>` — termina con successo

L’assenza o la presenza di marcatori non validi interrompe il pilota automatico in modo sicuro. Il LLM di destinazione viene comunque eseguito; si evita solo la chiamata aggiuntiva al LLM del revisore.

### `--non-interactive`

Modalità non interattiva. Non avvia il ciclo stdin. Se viene specificato un percorso di file come argomento posizionale, questo viene elaborato e il programma termina immediatamente.

```
uag --non-interactive README.md
uag --non-interactive --workdir /tmp/project
```

______________________________________________________________________

## Opzioni del server Web (`uagw`)

### `--host <address>`

Indirizzo di binding per il server Web (predefinito: `127.0.0.1`, sovrascrivibile tramite `UAGENT_WEB_HOST`).

Per impostazione predefinita, il server Web ascolta solo su localhost (`127.0.0.1`). Per renderlo accessibile da altre macchine sulla rete, utilizzare `--host 0.0.0.0`.

```
uagw --host 0.0.0.0
uagw --host 192.168.1.10
```

### `--tool-genre-mask <int>`

Seleziona i generi di strumenti utilizzando la stessa maschera di bit descritta sopra. Se specificato, la richiesta interattiva relativa al genere viene saltata.

### `--use-tool` / `--no-use-tool`

Abilita o disabilita l'invio delle definizioni degli strumenti a LLM. Sovrascrive `UAGENT_USE_TOOL`.

### `--computer-use` / `--no-computer-use`

Abilita o disabilita l’uso del computer. Sovrascrive `UAGENT_COMPUTER_USE`.

### `--no-frontend`

Esegue solo API senza modelli HTML o file frontend statici.

### `--embedded`

Disabilita l’archivio delle sessioni e nasconde gli strumenti di gestione (`tool_catalog`, `tool_load`, `unload_tool`).

______________________________________________________________________

## Opzioni del server A2A (`uaga`)

### `--host <address>`

Indirizzo di binding per il server A2A HTTP (impostazione predefinita: `0.0.0.0`, sovrascrivibile tramite `UAGENT_A2A_HOST`).

### `--port <numero>`

Numero di porta per il server A2A HTTP (impostazione predefinita: `8765`, sovrascrivibile tramite `UAGENT_A2A_PORT`).

### `--reload`

Abilita il ricaricamento a caldo in caso di modifiche al codice (impostazione predefinita: disabilitato, sovrascrivibile tramite `UAGENT_A2A_RELOAD`).

```
uaga --host 127.0.0.1 --port 8080 --reload
```

### `--tool-genre-mask <int>`

Seleziona i generi di strumenti utilizzando la maschera di bit descritta sopra. Se specificato, viene saltata la richiesta interattiva relativa al genere.

### `--use-tool` / `--no-use-tool`

Abilita o disabilita l’invio delle definizioni degli strumenti a LLM. Sovrascrive `UAGENT_USE_TOOL`.

### `--computer-use` / `--no-computer-use`

Abilita o disabilita l’uso del computer. Sovrascrive `UAGENT_COMPUTER_USE`.

### `--embedded`

Disabilita l'archivio delle sessioni e nasconde gli strumenti di gestione degli strumenti (`tool_catalog`, `tool_load`, `unload_tool`).

______________________________________________________________________

## Variabili d’ambiente correlate

| Variabile | Descrizione |
|---|---|
| `UAGENT_PROVIDER` | Nome del provider `LLM` (richiesto all’avvio) |
| `UAGENT_*_API_KEY` | Chiave `API` per il provider selezionato |
| `UAGENT_WORKDIR` | Directory di lavoro predefinita |
| `UAGENT_WEB_HOST` | Indirizzo di binding del server web (predefinito: `127.0.0.1`) |
| `UAGENT_A2A_HOST` | Indirizzo di binding del server A2A (predefinito: `0.0.0.0`) |
| `UAGENT_A2A_PORT` | Porta del server A2A (predefinita: `8765`) |
| `UAGENT_A2A_RELOAD` | Abilita il ricaricamento a caldo di A2A per impostazione predefinita |
| `UAGENT_USE_TOOL` | Disattiva gli strumenti se impostato su `0`, `false`, `no` o `off` |
| `UAGENT_COMPUTER_USE` | Abilita o disabilita l’uso del computer per impostazione predefinita |
| `UAGENT_SESSION_STORE` | Abilita o disabilita l’archivio delle sessioni; La modalità incorporata impone il valore `0` |
| `UAGENT_PLUGIN_DIRS` | Directory aggiuntive per la ricerca dei plugin |
| `UAGENT_AUTO_SENTINEL` | Attiva la modalità sentinella “single-LLM auto-pilot” se impostato su `1` |
| `UAGENT_CONSECUTIVE_TOOL_CALL_LIMIT` | Numero massimo di chiamate consecutive a tool aggiornato (impostazione predefinita: `100`) |
| `UAGENT_MAX_TOOL_ROUNDS` | Numero massimo di cicli di LLM/tool per operazione utente (impostazione predefinita: `200`) |
| `UAGENT_SHRINK_CNT` | Soglia opzionale di riduzione automatica nei messaggi (`0`/non impostato = disabilitato) |
| `UAGENT_SHRINK_KEEP_LAST` | Messaggi da conservare dopo la riduzione (impostazione predefinita: `20`) |
| `UAGENT_LANG` | Lingua dell’interfaccia (`ja`, `en`, ecc.) |

Per l’elenco completo delle variabili d’ambiente, vedere [ENVIRONMENT.md](ENVIRONMENT.md).

______________________________________________________________________

## Esempi

### Avvio minimo con OpenAI

```
set UAGENT_PROVIDER=openai
set UAGENT_OPENAI_API_KEY=sk-...
uag
```

### Ollama locale con solo strumenti di base

```
imposta UAGENT_PROVIDER=ollama
imposta UAGENT_OLLAMA_MODEL=qwen2.5:7b
uag --tool-genre-mask 1
```

### Server web su tutte le interfacce

```
imposta UAGENT_WEB_HOST=0.0.0.0
uagw
```

oppure

```
uagw --host 0.0.0.0
```

### Server A2A su localhost con porta personalizzata

```
uaga --host 127.0.0.1 --port 8080
```

### Disabilitare gli strumenti per un modello di piccole dimensioni

```
uag --no-use-tool --tool-genre-mask 1
```

### Elaborazione file non interattiva

```
uag --non-interactive README.md
```
