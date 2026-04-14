# uag (uagent)

uag è un agente di esecuzione di strumenti per scopi generali che viene eseguito nel tuo ambiente locale. Interagisce con gli utenti tramite un'interfaccia a riga di comando (CLI) ed esegue varie attività come operazioni sui file, ricerca web ed esecuzione di script Python secondo le istruzioni.

## Caratteristiche Principali

- **Operazioni sui file locali**: Lettura, scrittura, modifica e ricerca di file.
- **Recupero di informazioni**: Ricerca web con DuckDuckGo ed estrazione del contenuto delle pagine web.
- **Esecuzione di codice**: Esecuzione sicura di script Python e comandi PowerShell.
- **Elaborazione multimediale**: Generazione di immagini, lettura di file PDF/PPTX, screenshot.
- **Supporto multilingue**: Supporta diverse lingue, tra cui italiano, giapponese e inglese.
- **Supporto MCP (Model Context Protocol)**: Può connettersi a server MCP esterni per estendere le sue funzioni.

## Installazione

Puoi installarlo con pip da PyPI:

```bash
pip install uag
```

Al primo avvio, verrà avviata automaticamente una procedura guidata di configurazione.

## Avvio Rapido

Dopo l'installazione, digita semplicemente il seguente comando per iniziare:

```bash
uag
```

Una volta avviato, puoi chiedere all'agente cose come:
- "Leggi il README nella directory corrente e riassumi il suo contenuto."
- "Cerca nel web le ultime notizie sull'IA e fanne un riassunto."
- "Comprimi tutti i file PNG nella cartella 'images' in un file ZIP."

## Configurazione (Variabili d'ambiente)

Il comportamento di uag può essere configurato tramite variabili d'ambiente. Per maggiori dettagli, consulta:
- [ENVIRONMENT.md (English)](ENVIRONMENT.md)

## Documentazione

- [README.md (English)](README.md)
- [README.ja.md (Japanese)](README.ja.md)

## Licenza

Rilasciato sotto la Licenza Apache 2.0.
