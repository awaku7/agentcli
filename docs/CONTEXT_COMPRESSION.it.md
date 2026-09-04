# Compressione del contesto e contesto di modello circoscritto

uag utilizza diversi livelli per mantenere circoscritto il contesto di modello attivo. L'obiettivo è ridurre i token di input non necessari senza rimuovere i file, i risultati degli strumenti o i dati di sessione di cui l'utente potrebbe ancora aver bisogno.

Il presente documento descrive l'implementazione attuale. Distingue inoltre il comportamento deterministico da quello specifico del provider o assistito da LLM.

## 1. Superficie dinamica degli strumenti

Non è necessario inviare ogni definizione di strumento al modello ad ogni turno.

- `tool_catalog` effettua una ricerca tra le funzionalità disponibili.
- `tool_load` abilita solo gli strumenti necessari per l’attività corrente.
- `tool_catalog`, `tool_load` e `unload_tool` rimangono disponibili come strumenti di gestione.
- I flussi Responses API compatibili con GPT-5.4 possono utilizzare il Tool Search nativo lato server.
- La modalità legacy Tool Search restringe le specifiche degli strumenti con `tool_catalog` sul lato client.

Ciò riduce i token di input utilizzati dagli schemi degli strumenti, specialmente nelle installazioni con molti strumenti.

## 2. I risultati testuali di grandi dimensioni degli strumenti diventano artefatti

Quando il risultato testuale di uno strumento supera la soglia di Artifact, uag memorizza il risultato completo come Artifact e invia al modello un riferimento limitato e un’anteprima invece del testo completo.

I limiti predefiniti sono:

```text
UAGENT_TOOL_RESULT_ARTIFACT_THRESHOLD_CHARS=100000
UAGENT_TOOL_RESULT_MAX_CHARS=12000
```

La rappresentazione visibile al modello contiene il nome dello strumento, la lunghezza originale, un riferimento `artifact://`, il percorso di archiviazione e un’anteprima limitata. Il risultato completo rimane disponibile tramite l’archivio Artifact.

La soglia può essere modificata con `UAGENT_TOOL_RESULT_ARTIFACT_THRESHOLD_CHARS`. Un valore pari a `0` disabilita la promozione di Artifact. `UAGENT_TOOL_RESULT_MAX_CHARS` controlla la normale politica dei risultati limitati; `0` disabilita tale limite standard.

## 3. Recupero limitato di `Artifact`

Lo strumento di infrastruttura `artifact_read` recupera solo la porzione richiesta di un `Artifact`:

- `start_line` seleziona la prima riga.
- `max_lines` è limitato a 500.
- `max_chars` è limitato a 50.000 caratteri.
- È possibile utilizzare sia un ID Artifact che un URI `artifact://`.

Ciò consente di esaminare un piccolo intervallo rilevante invece di reimmettere l’intero file o il risultato del comando nel turno successivo del modello.

I nuovi artefatti sono memorizzati qui di seguito:

```text
~/.uag/artifacts/
```

I percorsi Artifact legacy esistenti rimangono leggibili per motivi di compatibilità.

## 4. Isolamento del payload binario

I dati binari inline non vengono inviati come risultato testuale dello strumento al turno successivo del modello. I campi con struttura Base64 vengono sostituiti con un breve indicatore come:

```text
[payload binario omesso dal contesto LLM]
```

L’interfaccia utente e i client remoti possono comunque ricevere allegati in memoria, e i file salvati rimangono disponibili tramite i relativi percorsi o i riferimenti Artifact. Ciò impedisce che immagini, audio, screenshot e altri payload binari ingombro il contesto testuale del modello.

La stessa classe di payload binario viene sanificata prima della persistenza in SQLite e JSONL, impedendo che venga restituita come payload di grandi dimensioni dopo il ricaricamento della sessione.

## 5. Compressione automatica della cronologia

uag può comprimere la cronologia delle conversazioni più vecchie quando il numero di messaggi o il numero stimato di token raggiunge il limite configurato.

La politica di compressione utilizza:

- il numero di messaggi non di sistema;
- la finestra di contesto risolta del modello, quando disponibile;
- `UAGENT_SHRINK_KEEP_LAST` (20 per impostazione predefinita);
- `UAGENT_SHRINK_MAX_TOKENS` o una sovrascrittura specifica del modello;
- `UAGENT_SHRINK_CNT`; e
- `UAGENT_SHRINK_RATIO` (0,5 per impostazione predefinita quando la finestra di contesto è nota).

È possibile specificare un limite specifico per il modello come segue:

```text
UAGENT_SHRINK_MAX_TOKENS_<MODEL_NAME>
```

Un riepilogo precedente non viene rigenerato ad ogni turno. L’isteresi richiede che si accumuli una quantità sufficiente di nuova cronologia, oppure un altro overflow del budget di token, prima che la compressione venga eseguita nuovamente.

## 6. Riepiloghi della cronologia assistiti da LLM

Quando la compressione automatica utilizza LLM, i messaggi più vecchi relativi a utente, assistente e strumento vengono riassunti in un messaggio di sistema a rotazione, mentre la parte più recente viene conservata.

Le cronologie lunghe possono essere riassunte in blocchi. I controlli rilevanti sono:

```text
UAGENT_SHRINK_CHUNK_SIZE=100
UAGENT_SHRINK_SINGLE_SHOT=1
```

Il riepilogo viene ripiegato in avanti anziché creare una sequenza illimitata di messaggi di riepilogo. Si tratta di un'operazione assistita da LLM e può richiedere ulteriori richieste al provider.

## 7. Compressione deterministica di fallback

Se un riepilogo LLM non è disponibile, uag può conservare i messaggi di sistema iniziali e solo i messaggi più recenti. I confini delle chiamate agli strumenti vengono riparati in modo che la cronologia risultante non inizi né finisca con una chiamata allo strumento orfana.

Il caricatore e il sanificatore rimuovono inoltre le voci non rilevanti per il modello o non valide, inclusi i messaggi relativi esclusivamente all’interfaccia utente, i messaggi di controllo interni, le righe di log danneggiate, i ruoli non supportati, i risultati orfani degli strumenti e i blocchi di chiamate agli strumenti incompleti.

Quando una sessione viene ricaricata, viene ripristinato il prompt di sistema corrente e vengono conservati solo i messaggi di sistema iniettati rilevanti, come il contesto delle skill o degli hook.

## 8. Recupero in caso di overflow del contesto

Se un provider segnala che la finestra di contesto è stata superata, uag identifica un messaggio recente di grandi dimensioni nella cronologia e annulla tale messaggio e la cronologia successiva prima di riprovare. Si tratta di un ripiego reattivo, non di una sostituzione della normale gestione delle risorse.

## 9. Continuazione e compattazione lato provider

Laddove supportato, Responses API utilizza `previous_response_id` per continuare una catena di risposte senza inviare nuovamente dal client l’intera cronologia delle risposte gestita dal provider.

I flussi Responses API inviano anche la configurazione di compattazione lato provider utilizzando la stessa soglia di riduzione locale. Il comportamento esatto dipende dal provider; il Artifact locale e le politiche relative alla cronologia rimangono le misure di sicurezza indipendenti dal provider.

## 10. Efficienza nel conteggio dei token

I conteggi dei token utilizzati per le decisioni di compressione vengono memorizzati nella cache e aggiornati in modo incrementale solo quando vengono aggiunti nuovi messaggi. Ciò non riduce direttamente il contesto del modello, ma riduce il carico sulla CPU e la latenza nel decidere quando la compressione è necessaria.

## Cosa non costituisce ancora un livello unificato completo

L’attuale implementazione non fornisce ancora tutti i seguenti elementi come unico gestore indipendente dal provider:

- un `ContextManager` e un `ContextBudget` unificati;
- un `ToolResultRecord` con metadati di importanza ed espulsione;
- riassunti semantici che non richiedono un `LLM`;
- il recupero e la reimmissione automatici degli Artifacts rilevanti;
- un Gestore dei Risultati centrale che garantisca la conversione di `Artifact` per ogni strumento che produce file binari; oppure
- un’eliminazione che tenga conto delle priorità in tutte le categorie relative a sistema, cronologia, schema dello strumento e risultati.

In breve, uag attualmente combina troncamento deterministico, riferimenti a Artifact, isolamento binario, selezione dinamica degli strumenti, sintesi della cronologia, continuazione del provider e recupero in caso di overflow. La roadmap di progettazione per un livello di contesto unificato è documentata in [UAG_CONTEXT_MANAGEMENT_DESIGN.md](UAG_CONTEXT_MANAGEMENT_DESIGN.md).
