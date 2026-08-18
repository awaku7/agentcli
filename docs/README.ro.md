<p align="center">
 <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="720">
</p>

<h1 align="center">uag"> Gateway</h1>

<p align="center">
 <b>U</b>niversal <b>A</b>I <b>G</b>ateway — Mediul tău, libertatea ta.
</p>

<p align="center">
 Operațiuni de fișiere / Căutare web / Control de imagini Excel / extracție / analiză I_oT / I_oT_1 integrare<br>
 24 de furnizori / 3 interfețe de utilizare / Execuție paralelă a instrumentelor / Piața abilităților agentului
</p>

<p align="center">
 <a href="https://github.com/awaku7/agentcli">GitHub</a>
 ·
 <a href="https://pypi.org/project/uag/">PyPI</a>
 ·
 <a href="https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md">Read this in your language</a>
</p>
________________________________
___________________________## De ce uag?

**Eliberați-vă de blocarea furnizorului.** Majoritatea asistenților AI vă leagă de un anumit furnizor sau serviciu cloud. uag este diferit.

- **Rulează local** pe computer. Datele dvs. rămân cu dvs. (cu excepția API apeluri pe care le efectuați).
- **Libertatea furnizorului**: OpenAI, Claude, Gemini, DeepSeek, Ollama, Azure, Bedrock, Novita, HuggingFace... 24 de furnizori, toți accesibili dintr-o singură interfață. Schimbați între ele prin reconfigurarea variabilelor de mediu — fără reinstalare, fără migrare.
- **222 de instrumente**: I/O fișiere, căutare web, generare de imagini, Gmail, scanare dispozitiv BLE, integrare server MCP — **130 sunt marcate static ca sigure în paralel** (până la 8 se execută simultan prin pool-ul de fire, configurabil prin ENTOR_PAR\`ELUA, configurabil). Când LLM declanșează mai multe apeluri de instrumente simultan, uag le paralelizează automat.
- **3 interfețe de utilizare + A2A**: CLI, GUI, Web și protocol de la agent la agent. Același motor, orice interfață.
- **Pregătit pentru IoT**: SwitchBot, ECHONET Lite, Matter, UPnP — controlați-vă dispozitivele de acasă prin AI.
- **Abilități de agent**: Instalați abilități create de comunitate de pe piață. Extinde uag la nesfârșit.

uag este **asistentul tău AI conform condițiilor tale**. Nu este legat de un furnizor, nu este legat de o interfață, nu este legat de o platformă.

## Pornire rapidă

```bash
pip install uag
uag
```

La prima lansare, vrăjitorul de configurare vă ghidează prin configurarea furnizorului.
Consultați \[docs/ENVIRONMENT.md\](https://github.com/awaku7/RO/maindoc. variabile de mediu.

## Utilizarea computerului

Utilizarea computerului este înscrisă și acceptă atât un timp de rulare vizibil al browserului Playwright
, cât și un timp de rulare pentru desktop. Când sunt activate, ambele runtime sunt create și înregistrate;

```bat
set UAGENT_COMPUTER_USE=1
```

`````




```bat
````

```Use. Resursele de rulare sunt
închise împreună la ieșirea normală, `Ctrl-C` și închiderea procesului. Setați
`UAGENT_COMPUTER_HEADLESS=1` pentru CI bazate pe browser sau teste de fum.
Consultați [docs/COMPUTER_USE_IMPLEMENTATION.md](docs/COMPUTER_USE_IMPLEMENTATION.md)
pentru detalii despre integrare și siguranță.

## Voce în timp real și AEC3

Modul vocal în timp real acceptă OpenAI În timp real, Azure OpenAI GPT În timp real, xAI Grok Voce API, Google Gemini Multimodal Live API și Sonic cu microfon Amazon Bed-Duplex I/Fullplex. Backend-ul AEC3 `pywebrtc-audio` necesar este instalat automat, iar SDK-ul opțional de streaming bidirecțional de la Bedrock este instalat automat numai atunci când este selectat furnizorul Bedrock:

```bash
python scheck.py realtime
```

Conducta AEC3 și primește semnalul audio de aproape de microfon) (`far`) astfel încât asistentul să poată asculta în timp ce vorbește. Activați diagnosticarea numai atunci când investigați problemele audio:

```bat
set UAGENT_REALTIME_AUDIO_DEBUG=1
python scheck.py realtime
```

### OpenAI Funcție de apelare în timp real

OpenAI Apeluri de siguranță-integrare în timp real suportate limitate. Actualul adaptor în timp real expune automat `get_current_time` numai în citire. Instrumentele distructive și controalele dispozitivului nu sunt expuse fără o listă de permise explicită și un flux de confirmare. Grok în timp real folosește un adaptor separat și nu utilizează această cale de apelare a funcției specifice OpenAI.

## Caracteristici
### 🧠 Arhitectură Multi-Provider
OpenAI / PFN (PLaMo) / Azure / Bedrock / OpenRouter / Ollama / llama.cpp / Gemini / Vertex AI / Claude / Grok / NVIDIA / Novita / Z. AIZpuce / Deep) (Qwen) / KIMI (Moonshot AI) / Xiaomi MiMo / LM Studio / MiniMax / Sakana AI (Fugu) / SAKURA AI Engine / Together AI / Vercel AI Gateway
Toți furnizorii au același set de instrumente și interfață. Comutați setând `UAGENT_PROVIDER` — fără modificări de cod, fără instalări separate.
#### Ollama și llama.cpp
Ollama și llama.cpp sunt furnizori separați. Ollama folosește propriul serviciu și managementul modelului, în timp ce `llama.cpp` se conectează la un punct final compatibil OpenAI cu `llama-server`:
```bash
# Ollama
UAGENT_PROVIDER=ollama
UAGENT_OLLAMA_BASE_URL=http://localhost:11434/v1
UAGENT_OLLAMA_DEPNAME=llama3.1
# llama.cpp / llama-server
UAGENT_PROVIDER=llama_cpp
UAGENT_LLAMA_CPP_BASE_URL=http://localhost:8080/v1
UAGENT_LLAMA_CPP_DEPNAME=local-model
UAGENT_LLAMA_CPP_API_KEY=dummy-compatible oferă chat-compatible. calea. Păstrați `UAGENT_RESPONSES=0` cu excepția cazului în care este configurat un proxy compatibil.
### ⚡ Execuție paralelă a instrumentului
Când LLM solicită mai multe instrumente simultan, uag **le paralelizează automat**. `ThreadPoolExecutor` (8 fire în mod implicit; setați `UAGENT_PARALLEL_WORKERS` să se schimbe).
**Exemplu**: Întrebați „Verificați vremea în capitalele nordice” → LLM declanșează `search_web` × 5 țări → toate cele 5 căutări rulează în paralel → rezultatele culese într-un singur lot. `TOOL_SPEC` (în prezent 222, inclusiv cele 2 instrumente cu suport Rust din `src/uagent/tools_rust/`). `http_request` folosește siguranța sensibilă la metode: apelurile `GET`/`HEAD`/`OPTIONS` pot rula în paralel, în timp ce metodele de scriere rămân seriale.
Uneltele numai pentru citire (căutare fișiere, calcul hash, listare directoare, traducere, interogări DB etc.) sunt paralelizate agresiv.
#PH#_2 Codul de sistem Compatibil)
uagent implementează un sistem de plugin **Claude compatibil cu cod**. Pluginurile reunesc abilități, agenți, servere MCP, hook-uri și multe altele în directoare autonome cu un manifest `.claude-plugin/plugin.json`.
**Componente acceptate**: Skills, Sub-agents, MCP servers, Hooks (12 evenimente ciclului de viață), Output, Slash comenzi, fig. Marketplaces
**Comenzi CLI**:
```
:listă de pluginuri # Listă pluginuri instalate
:plugin install <source> [--scope] # Instalare (dir/zip/git/http)
:plugin install <name>@<marketplace> # Instalare din marketplace
:plugin remove <name> # Uninstall
:disableplugin
:plugin
:plugin name add/remove/list # Manage marketplaces
:plugin init <name> # Scaffold new plugin
```
Consultați [DEVELOP_PLUGIN.md](src/uagent/docs/DEVELOP_PLUGIN.md) pentru documentația completă.
### 🔄 Sesiune cu continuitate**-
-r** `UAGENT_PROVIDER` — istoricul conversațiilor este păstrat.
- **Reîncărcați sesiunile anterioare** cu `:load <index>` — reluați de unde ați rămas.
- **Memorizarea rezultatelor instrumentului** evită reexecuția redundantă atunci când același apel de instrument se repetă.
### 🛠 229 Instrumente
| Categoria | Instrumente |
|---|---|
| **Operațiuni cu fișiere** | citiți/scrieți/creați/ștergeți/căutarea/grep/hash/zip, tip_fișier, parse_eml (fișiere .eml), `path_alias` |
| **Web** | fetch_url, search_web, screenshot, browser_playwright, `url_alias`, `public_transit_route` ([guide](docs/PUBLIC_TRANSIT_ROUTE.md)) |
| **Media** | genera_imagine, analizează_imagine, img2img, audio_speech, audio_transcribe |
| **Documente** | Extracție PDF/PPTX/DOCX/RTF/ODT, extracție structurată Excel |
| **Prognoză** | Prognoza serii cronologice cu 9 modele (AutoARIMA, Prophet, LightGBM, CatBoost, TimesFM, etc.), selectare automată a modelului, generare plot, i18n |
| **Comunicare** | gmail_send, gmail_read, bluesky, discord_channel, teams_webhook, **pybitchat** (BLE Mesh) — vezi [COMMUNICATION.md](https://github.com/awaku7/agentcli/blob/main/docs/COMMUNICATION.md) și [BITCHAT.md](https://github.com/awaku7/agentcli/blob/main/docs/BITCHAT.md) |
| **IoT** | SwitchBot (Cloud + BLE), ECHONET Lite, Matter, UPnP, reverse_geocode |
| **API-uri cloud** | `aws_api`, `gcp_api`, `azure_api` — operațiuni generice AWS, Google Cloud și Azure API; operațiunile de scriere necesită confirmare explicită |
| **Instrumente de dezvoltare** | workspace_status, git_ops, git_review, security_scan, coverage_report, python_compile, lint_format, run_tests, db_query, **29 navigatoare de cod sursă (familia idx)** |
| **MCP** | Conectați-vă la servere externe MCP, listați instrumente, executați — [Ghid OAuth / Proxy](docs/MCP_OAUTH_PROXY_GUIDE.md) |
| **A2A** | Comunicare de la agent la agent (cu alte instanțe uag sau servere compatibile cu A2A) |
| **Sistem** | vars env, specificații de sistem, ora, calculul datei, [cantități](docs/QUANTITIES.md), [distanța_geodezică](docs/DISTANTA_GEODEZIC.md), uuid_gen, slugify |
| **Sursa Nav** | **29 de instrumente idx** pentru Python, PHP, TypeScript, Java, C#, Dart, C/C++, Rust, Go, Swift, Kotlin, COBOL, VBA, LotusScript, Makefile — obțineți un index de funcție/clasă sau o definiție specifică fără a citi întregul fișier |
#### Revizuirea și acoperirea depozitului
- `` raportarea spațiului de lucru, ramuri, spațiu de lucru activ starea de sincronizare în amonte, timpul de execuție Python și marcatorii obișnuiți ai proiectelor fără modificarea fișierelor.
- `git_review`: rezumați modificările Git, fișierele riscante, candidații de testare și descoperirile secrete fără a expune valorile secrete.
- `security_scan`: scanați fișierele de depozit pentru secrete probabile și fișiere de configurare riscante`: acoperire și raportare normalizare`: acoperire și raportare normalizare.
 TypeScript/JavaScript, Rust, Go, Java/Kotlin, .NET, C/C++, Ruby, PHP, Swift și Dart/Flutter.
- Dependențele de acoperire lipsă pot fi instalate automat când se solicită execuția; `dry_run` nu instalează niciodată pachete.
Consultați [Instrumente de analiză a depozitului](docs/REPOSITORY_TOOLS.md) pentru parametri, rezultate și detalii de siguranță.
Consultați [Aliasuri de cale și URL](docs/PATH_URL_ALIASES.md) pentru scurtarea căilor de fișiere repetate și a URL-urilor. Interfețe + VS Code Extension
| Modul | Comanda | Scop |
|---|---|---|
| **CLI** | `uag` | Operare rapidă bazată pe terminal |
| **GUI** | `uagg` | Interfața de utilizare pentru desktop prin tkinter |
| **Web** | `uagw` | Acces bazat pe browser |
| **A2A Server** | `uaga` | Protocol Agent2Agent pentru comunicare multi-agent |
| **Codul VS** | — | [Extensie](https://github.com/awaku7/agentcli/blob/main/docs/VSCODE.md) cu Panoul de chat, Explain, Refactor, Fix Error și Tools Tree View |
Vedeți [VSCODE.md](https://github.com/awaku7/agentcli/blob/blob/main/main/docs/VSCODE Cod de instalare, extensia codului VSCODE pe extensia thedVS) legături de taste și configurare.
### 🏠 Controlul dispozitivelor IoT
- **BACnet**: citire/scriere dispozitive BACnet/IP (HVAC, iluminat, contoare de putere). Abonament COV pentru notificări push
- **Modbus TCP**: Citiți/scrieți registre și bobine de reținere/intrare. Monitorizarea modificărilor bazată pe sondaje
- **OPC UA**: Răsfoiți spațiul de adrese, citiți/scrieți variabile, abonați-vă la modificările datelor
- **SwitchBot**: Controlul loturilor în cloud și scanarea/controlul BLE. Abonament bazat pe sondaje
- **ECHONET Lite**: Descoperiți, controlați și abonați-vă la notificările INF de la aparatele electrocasnice (AC, lumini, încălzitoare de apă etc.)
- **Materia**: control citire/scriere + abonament atribut pentru monitorizarea schimbării stării
- **UPnP**: Descoperire dispozitiv și redirecționare IGDSe [IOT_USECASE.md](https://github.com/awaku7/agentcli/blob/main/docs/IOT_USECASE.md)
### 🎯 Agent Skills Marketplace
`:skills mp_search` pentru a răsfoi [SkillsMP](https://skillsmp.com) și comunitatea [https://skillsmp.com)whub. abilități.
Instalați și extindeți capacitățile lui uag din mers.
### 🤖 Auto-Pilot (`:auto`)
uag poate **să urmărească în mod autonom un obiectiv în mai multe LLM runde**. Perfect pentru sarcini complexe, cu mai mulți pași, care necesită o rafinare iterativă.
- **Cum funcționează**: Fiecare rundă are o interogare principală (Pasul A) urmată de o judecată a recenzentului (Pasul B) care decide „COMPLETĂ sau CONTINUA?”
- **Același furnizor, același API**: Judecata recenzentului folosește calea de cod identică ca interogarea principală — inclusiv răspunsurile .API suport .API**Separate .API** LLM** (opțional): setați `UAGENT_AP_PROVIDER` să folosească un alt furnizor/model pentru examinator (de exemplu, utilizați un model mai ieftin pentru evaluare).
- **Ieșiți oricând**: apăsați tasta F11 pentru a opri imediat, chiar și la mijlocul răspunsului. Sau lăsați recenzentul să decidă când este îndeplinit obiectivul.
- **Configurabil**: `--max-rounds N` pentru a controla bugetul.
Consultați [README_AUTO.md](https://github.com/awaku7/agentcli/blob/main/docs/README_AUTO.md) pentru documentația completă.
⏩## Batch State Manager. poate urmări progresul în sarcinile cu mai multe fișiere de lungă durată. Când LLM procesează zeci de fișiere, `batch_state` persistă pe disc lista fișierelor în așteptare, finalizate și eșuate. Dacă sesiunea se termină sau expiră o rundă, următoarea rulare reia de unde s-a oprit — nimic nu se pierde.
### 🛡 Human-in-the-Loop
`human_ask` permite LLM să întrerupă și să solicite confirmarea înainte de a efectua operațiuni distructive (ștergerea fișierelor, suprascrieri, comenzi shell). Rămâneți sub control.
### 🛑 Întrerupeți (tasta C / Butonul Stop)
Opriți generarea răspunsului LLM în orice moment și injectați o comandă de oprire înapoi în LLM.
| Interfață | Cum se întrerupe |
|---|---|
| **CLI** | Apăsați tasta F12 în timpul streamingului LLM — răspunsul curent se oprește și `"Stop"` este trimis ca mesaj de utilizator, astfel încât LLM să răspundă în consecință |
| **Interfață de utilizare WEB** | Faceți clic pe butonul roșu **■ Stop** (apare automat în timpul procesării LLM) |
| **Interfață grafică pentru desktop** | Faceți clic pe butonul roșu **■** (apare automat în timpul procesării LLM) |
Întreruperea funcționează ca „injectare promptă”: în loc să se anuleze, transmite „Stop”” înapoi către LLM sub formă de mesaj de utilizator, permițându-i să încheie cu grație sau să recunoască întreruperea tastei.
**F11** pentru a ieși din Auto-Pilot. **F12** oprește doar răspunsul LLM curent (consultați [README_AUTO.md](https://github.com/awaku7/agentcli/blob/main/docs/README_AUTO.md)).
### 🕵️ Browser Automation & Web Inspector
Două instrumente complementare bazate pe Playwright:
- ****browser-extras, automate sesiune de navigare: browser_play, automate sesiune de navigare, clic real-play** date, gestionează fluxuri cu mai multe pagini. Funcționează fără cap sau cu cap.
- **playwright_inspector**: înregistrați tranzițiile browserului, capturați instantanee și capturi de ecran DOM la fiecare pas. Util pentru depanarea interacțiunilor web sau pentru auditarea modificărilor paginii de-a lungul timpului.
### 🔄 Încărcarea dinamică a instrumentelor
`tool_catalog` și `tool_load` vă permit să descoperiți și să activați instrumente în timpul execuției.
Nu este nevoie să încărcați totul la pornire — activați doar ceea ce aveți nevoie, atunci când aveți nevoie.
##gent și `slugify` sunt implementate în Rust (prin PyO3) pentru performanță.
Se încarcă direct dintr-un `.pyd` pre-construit — **nu este necesară `pip install`**. `uagent.tools.rust_helper` și
utilizatorii primesc instrumentul fără dependențe suplimentare. Vezi
[TOOL_CREATOR_GUIDE.md](https://github.com/awaku7/agentcli/blob/main/TOOL_CREATOR_GUIDE.md).
### 🌐 i18n / L10n
日本語 / English / 简佔 /中恖間 /中恖間 /中恖齔 /中恖齔 / 한국어 / Español / Français / Русский / și multe altele.
Setați `UAGENT_LANG` pentru a comuta. Consultați [ADD_LOCALE.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/ADD_LOCALE.md) pentru a adăuga o nouă localitate.
Traducerile acestui README sunt disponibile în [docs/README.translations.md](https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md).
### 🔒 Variabile de mediu criptate
Pastrați cheile și secretele API în `.env.sec`` — un fișier criptat ..
Managed. `uag_envsec`.
## Configurație și detalii

- **Variabile de mediu**: [docs/ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/docs/ENVIRONMENT.md)
- **Asistent de configurare**: `python -m uagent.setup-_** **Encrypted-_cli: `uag_envsec` — criptați `.env` ca `.env.sec`
- **Răspunsuri API**: Setați `UAGENT_RESPONSES=1` pentru modul Răspunsuri API (OpenAI/Azure/Bedrock/OpenRouter/Ollama/Alibaba/Ollama Studio/Alibaba). Activat automat pentru Sakana AI (Fugu).
- **Documente pentru dezvoltatori**: [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)
- **Flux de instrumente**: [TOOL_FLOW.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/TOOL_FLOW.md) — cum sunt trimise instrumentele către LLM (mască de gen, catalog de instrumente, GPT-5.4+ căutare de instrumente native)
- **Sfaturi mici: **PH_5 [SLM_TIPS.md](https://github.com/awaku7/agentcli/blob/main/docs/SLM_TIPS.md)

## Filosofia proiectului

uag aspiră să fie **AI-ul tău, pe mașina ta, în condițiile tale.**

- Fără dependență de SaaS — rulează local
- Fără blocare a furnizorului — comută oricând
- Fără blocare UI — CLI / GUI / Web / _-_PH_0 și instrument de extindere abilități

O experiență gratuită de agent AI, fără blocarea furnizorului.

### ✨ Creați-vă propriile instrumente

Scrieți un nou instrument pentru uag este simplu - creați un singur fișier `.py` cu 
`TOOL_SPEC` și `run_tool`, plasați-l în () `UAGENT_EXTERNAL_TOOLS_DIR` și
este disponibil imediat. Pentru dezvoltatorii Rust, trimiteți un `.pyd` pre-construit cu
zero dependențe suplimentare pentru utilizatori.

Consultați [TOOL_CREATOR_GUIDE.md](https://github.com/awaku7/agentcli/blob/main/TOOL_CREATOR_GUIDE.md)
pentru ghidul pas cu pas.


## Contribuție

Contribuțiile sunt binevenite! Rapoarte de erori, sugestii de funcții, îmbunătățiri ale documentației, traduceri și solicitări de extragere — toate sunt apreciate.

- **Probleme**: deschideți o problemă GitHub pentru erori sau solicitări de funcții.
- **Solicitări de extragere**: deblocați repo, faceți modificările și trimiteți un PR. Consultați [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md) pentru configurarea și instrucțiunile de dezvoltare.
- **Traduceri**: traducerile README și adăugările de localități sunt binevenite. Consultați [ADD_LOCALE.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/ADD_LOCALE.md).
- **Instrumente și abilități**: Noile pluginuri de instrumente și abilități de agent pot fi contribuite prin intermediul pieței.




















 mai întâi dependențele de testare. Acestea sunt ținute în afara listei de dependențe
de execuție:

```bash
python -m pip install -e ".[test]"
python -m pip install black ruff
```

Rulați aceleași verificări folosite de GitHub Acțiuni înainte de a apăsa:
``ffbash -
``
m src tests
python -m black --check src tests
python scripts/tool_json_i18n_batch.py status
python -m pytest -q .
```

Pentru o iterație locală mai rapidă, rulați numai testele afectate:
``testbatch -
```

 teste/<zona_afectată>
```

Verificări suplimentare atunci când este relevant:

```bash
python -m py_compile src/uagent/
mypy src/uagent
```

După editarea localizării (`on: . scripts/compile_locales.py` și `python scripts/po_qc_summary.py`.

Politica de execuție (detalii în [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md):`s raise §ys instead of.md): gazda instrumentului transformă instrumentul `SystemExit`/`Exception` în șiruri de eroare, astfel încât un singur instrument nu poate ucide procesul. Ieșirile rapide de eșuare la pornire rămân intenționate.

## Arhitectură și invariante operaționale

Consultați [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) pentru contractele durabile care acoperă ciclul de viață A2A, contexte I18N, instalarea opțională a dependenței, siguranța instrumentelor, capabilitățile furnizorului, limitele de încredere OAuth, evenimentele structurate și verificarea acceptării

.## Enterprise Policy Engine

Politicile la nivel de organizație pentru instrumente, furnizori, acreditări, servere MCP, rețele, competențe și pluginuri sunt acceptate. Setați `UAGENT_POLICY_FILE` la un fișier de politică JSON/YAML; consultați [docs/ENTERPRISE_POLICY.md](docs/ENTERPRISE_POLICY.md) pentru exemple de configurare, roluri, confirmare și liste de permisiuni.

### Recuperare și orchestrare în timpul execuției

Consultați [RESTART_RECOVERY.md](docs/RESTART_RECOVERY.md) / [DAG_SCHEDULER.md](docs/DAG_SCHEDULER.md) / [MULTI_AGENT_RUNTIME.md](docs/MULTI_AGENT_RUNTIME.md) pentru recuperare durabilă, execuție în funcție de dependență, orchestrare cu mai mulți agenți și utilizare de la distanță A2A.



 [DISTRIBUTED_COORDINATION.md](docs/DISTRIBUTED_COORDINATION.md) pentru coordonarea închirierii liderului în timp partajat.
`````
