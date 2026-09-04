# UTILIZARE (Opțiuni de linie de comandă)

Acest document descrie opțiunile de linie de comandă disponibile pentru punctele de intrare uag.

______________________________________________________________________

## Puncte de intrare

| Comandă | Modul Python | Interfață |
|---|---|---|
| `uag` | `python -m uagent` | CLI (buclă stdin) |
| `uagg` | `python -m uagent.gui` | GUI (tkinter) |
| `uagw` | `python -m uagent.web` | Server web (FastAPI) |
| `uaga` | `python -m uagent.a2a.server` | serverul A2A și HTTP |

______________________________________________________________________

## Opțiuni de pornire CLI (`uag`)

### `--workdir` / `-C <cale>`

Director de lucru. Dacă nu este setat, se utilizează variabila de mediu `UAGENT_WORKDIR`, apoi directorul curent.
Directorul este creat dacă nu există.

### `--tool-genre-mask <int>`

Masca de biți pentru genul de instrument. Când este specificată, se omite solicitarea interactivă de selectare a genului.

| Bit | Gen | Descriere |
|-----|-------|-------------|
| 1 | basic | Instrumente esențiale pentru fișiere/chat |
| 2 | comm | Instrumente de comunicare (Bluesky, Teams) |
| 4 | office | Instrumente pentru suita Office (Excel, PDF, PPTX) |
| 8 | devel | Instrumente de dezvoltare (git, lint, compile) |
| 16 | iot | Instrumente pentru dispozitive IoT (SwitchBot, ECHONET, Matter, UPnP) |
| 32 | exec | Instrumente de execuție a comenzilor |
| 64 | external | Instrumente pentru pluginuri externe |
| 128 | media | Generare și analiză de imagini/audio |
| 256 | file | Instrumente de gestionare a fișierelor |
| 512 | index | Instrumente de navigare în surse/index |
| 1024 | dev | Instrumente pentru dezvoltatori și depozite |
| 2048 | web | Instrumente web și pentru browser |
| 4096 | utility | Instrumente utilitare și de asistență |
| 8191 | all | Toate instrumentele |

Exemple:

```
uag --tool-genre-mask 1 # doar instrumente de bază
uag --tool-genre-mask 9 # instrumente de bază + de dezvoltare (1 + 8)
uag --tool-genre-mask 8191    # toate instrumentele
```

### `--use-tool` / `--no-use-tool`

Activează sau dezactivează trimiterea definițiilor instrumentelor către LLM. Suprascrie variabila de mediu `UAGENT_USE_TOOL`.

- `--use-tool` forțează activarea trimiterii instrumentelor.
- `--no-use-tool` forțează dezactivarea trimiterii instrumentelor.

Când este dezactivată, fișierul LLM nu primește nicio definiție de instrument și nu poate apela niciun instrument.

### `--computer-use` / `--no-computer-use`

Activează sau dezactivează utilizarea computerului. Înlocuiește variabila de mediu `UAGENT_COMPUTER_USE`.

### `--inject-message` / `-M <message>`

Injectează un mesaj în LLM la pornire și se închide după finalizare. Aceasta implică opțiunea `--non-interactive`.

### `--embedded`

Modul încorporat pentru implementări cu restricții sau sensibile la reproductibilitate.

- Dezactivează stocarea sesiunilor.
- Ascunde instrumentele de gestionare a instrumentelor (`tool_catalog`, `tool_load`, `unload_tool`) dacă nu sunt activate în mod explicit.
- Ignoră `--tool-genre-mask`; utilizați `--enable-tool` pentru încărcarea explicită a instrumentelor.

### `--enable-tool <nume>`

Încarcă explicit un instrument la pornire. Opțiunea poate fi repetată, iar numele separate prin virgulă sunt, de asemenea, acceptate.

```
uag --embedded --enable-tool handle_mcp_v2 --enable-tool human_ask
uag --embedded --enable-tool handle_mcp_v2,human_ask
```

Ordinea specificată este păstrată și se reflectă în ordinea instrumentelor prezentată către LLM. Instrumentele activate explicit sunt blocate împotriva descărcării automate.

### `--plugin-dir <cale>`

Încărcați pluginurile din directorul specificat. Opțiunea poate fi repetată.

______________________________________________________________________

## Opțiuni exclusive pentru CLI

### `--inject-message-auto <opțiuni-obiectiv>`

Pornește pilotul automat dintr-un obiectiv injectat neinteractiv. Valoarea utilizează aceleași opțiuni ca `:auto`; puneți între ghilimele valoarea completă atunci când aceasta conține opțiuni.

```
uag --embedded --enable-tool handle_mcp_v2 --inject-message-auto "Sortează elementele --max-rounds 10"
uag --embedded --enable-tool handle_mcp_v2 --inject-message-auto "Sortează elementele --infinite"
```

Modul normal utilizează calea de judecată a evaluatorului. Setați `UAGENT_AUTO_SENTINEL=1` pentru a activa modul cu un singur sentinel LLM. În acest mod, ținta LLM trebuie să încheie fiecare răspuns cu exact unul dintre următoarele:

- `<AUTO_CONTINUE>` — execută o altă rundă
- `<AUTO_COMPLETE>` — finalizează cu succes

Marcatorii lipsă sau nevalizi opresc pilotul automat în condiții de siguranță. Acest lucru execută în continuare ținta LLM; evită doar apelul suplimentar al revizorului LLM.

### `--non-interactive`

Modul neinteractiv. Nu pornește bucla stdin. Dacă se specifică o cale de fișier ca argument pozițional, aceasta este procesată, iar programul se închide imediat.

```
uag --non-interactive README.md
uag --non-interactive --workdir /tmp/project
```

______________________________________________________________________

## Opțiuni ale serverului web (`uagw`)

### `--host <address>`

Adresă de legare pentru serverul web (implicit: `127.0.0.1`, poate fi suprascrisă prin `UAGENT_WEB_HOST`).

În mod implicit, serverul web ascultă numai pe localhost (`127.0.0.1`). Pentru a-l face accesibil de pe alte mașini din rețea, utilizați `--host 0.0.0.0`.

```
uagw --host 0.0.0.0
uagw --host 192.168.1.10
```

### `--tool-genre-mask <int>`

Selectați genurile de instrumente folosind aceeași mască de biți descrisă mai sus. Când este specificată, solicitarea interactivă privind genul este omisă.

### `--use-tool` / `--no-use-tool`

Activează sau dezactivează trimiterea definițiilor instrumentelor către LLM. Suprascrie `UAGENT_USE_TOOL`.

### `--computer-use` / `--no-computer-use`

Activează sau dezactivează utilizarea computerului. Suprascrie `UAGENT_COMPUTER_USE`.

### `--no-frontend`

Rulează doar API fără șabloane HTML sau fișiere frontend statice.

### `--embedded`

Dezactivează stocarea sesiunilor și ascunde instrumentele de gestionare a instrumentelor (`tool_catalog`, `tool_load`, `unload_tool`).

______________________________________________________________________

## Opțiuni server A2A (`uaga`)

### `--host <address>`

Adresă de legare pentru serverul A2A HTTP (implicit: `0.0.0.0`, poate fi suprascrisă de `UAGENT_A2A_HOST`).

### `--port <număr>`

Numărul portului pentru serverul A2A HTTP (implicit: `8765`, poate fi suprascris prin `UAGENT_A2A_PORT`).

### `--reload`

Activează reîncărcarea din mers la modificările de cod (implicit: dezactivat, poate fi suprascris de `UAGENT_A2A_RELOAD`).

```
uaga --host 127.0.0.1 --port 8080 --reload
```

### `--tool-genre-mask <int>`

Selectează genurile de instrumente folosind masca de biți descrisă mai sus. Când este specificată, solicitarea interactivă privind genul este omisă.

### `--use-tool` / `--no-use-tool`

Activează sau dezactivează trimiterea definițiilor instrumentelor către LLM. Suprascrie `UAGENT_USE_TOOL`.

### `--computer-use` / `--no-computer-use`

Activează sau dezactivează „Utilizarea computerului”. Suprascrie `UAGENT_COMPUTER_USE`.

### `--embedded`

Dezactivează stocarea sesiunilor și ascunde instrumentele de gestionare a instrumentelor (`tool_catalog`, `tool_load`, `unload_tool`).

______________________________________________________________________

## Variabile de mediu asociate

| Variabilă | Descriere |
|---|---|
| `UAGENT_PROVIDER` | Numele furnizorului LLM (obligatoriu la pornire) |
| `UAGENT_*_API_KEY` | Cheia API pentru furnizorul selectat |
| `UAGENT_WORKDIR` | Directorul de lucru implicit |
| `UAGENT_WEB_HOST` | Adresa de legare a serverului web (implicit: `127.0.0.1`) |
| `UAGENT_A2A_HOST` | Adresa de legare a serverului A2A (implicit: `0.0.0.0`) |
| `UAGENT_A2A_PORT` | Portul serverului A2A (implicit: `8765`) |
| `UAGENT_A2A_RELOAD` | Activează reîncărcarea la cald a A2A în mod implicit |
| `UAGENT_USE_TOOL` | Dezactivează instrumentele când este setat la `0`, `false`, `no` sau `off` |
| `UAGENT_COMPUTER_USE` | Activează sau dezactivează utilizarea computerului în mod implicit |
| `UAGENT_SESSION_STORE` | Activează sau dezactivează stocarea sesiunilor; Modul încorporat impune valoarea `0` |
| `UAGENT_PLUGIN_DIRS` | Directoare suplimentare de căutare a pluginurilor |
| `UAGENT_AUTO_SENTINEL` | Activează modul sentinelă automată single-LLM atunci când este setat la `1` |
| `UAGENT_CONSECUTIVE_TOOL_CALL_LIMIT` | Numărul maxim de apeluri consecutive către instrumente noi (implicit: `100`) |
| `UAGENT_MAX_TOOL_ROUNDS` | Numărul maxim de runde LLM/instrument per operațiune a utilizatorului (implicit: `200`) |
| `UAGENT_SHRINK_CNT` | Prag opțional de reducere automată a dimensiunii mesajelor (`0`/nesetat = dezactivat) |
| `UAGENT_SHRINK_KEEP_LAST` | Numărul de mesaje care se păstrează după reducere (implicit: `20`) |
| `UAGENT_LANG` | Limba interfeței (`ja`, `en`, etc.) |

Pentru lista completă a variabilelor de mediu, consultați [ENVIRONMENT.md](ENVIRONMENT.md).

______________________________________________________________________

## Exemple

### Configurare minimă cu OpenAI

```
set UAGENT_PROVIDER=openai
set UAGENT_OPENAI_API_KEY=sk-...
uag
```

### Ollama local, numai cu instrumente de bază

```
set UAGENT_PROVIDER=ollama
set UAGENT_OLLAMA_MODEL=qwen2.5:7b
uag --tool-genre-mask 1
```

### Server web pe toate interfețele

```
set UAGENT_WEB_HOST=0.0.0.0
uagw
```

sau

```
uagw --host 0.0.0.0
```

### Serverul A2A pe localhost cu port personalizat

```
uaga --host 127.0.0.1 --port 8080
```

### Dezactivare instrumente pentru un model mic

```
uag --no-use-tool --tool-genre-mask 1
```

### Prelucrare neinteractivă a fișierelor

```
uag --non-interactive README.md
```
