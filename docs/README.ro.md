<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="720">
</p>

<h1 align="center">uag — Universal AI Gateway</h1>

<p align="center">
  <b>U</b>niversal <b>A</b>I <b>G</b>ateway — Mediul tău, libertatea ta.
</p>

<p align="center">
  Operațiuni de fișiere / Căutare pe web / Generare și analiză de imagini / Extragere PDF și Excel / Control IoT / Integrare MCP<br>
  Peste 15 furnizori / 3 UI / Execuție paralelă a instrumentelor / Piața de abilități de agent
</p>

<p align="center">
  <a href="https://github.com/awaku7/agentcli">GitHub</a>
  ·
  <a href="https://pypi.org/project/uag/">PyPI</a>
  ·
  <a href="https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md">Citiți acest lucru în limba dvs.</a>
</p>

---

## De ce uag?

**Eliberați-vă de blocarea furnizorului.** Majoritatea asistenților AI vă leagă de un anumit furnizor sau serviciu cloud. uag este diferit.

- **Rulează local** pe computer. Datele tale rămân cu tine (cu excepția apelurilor API pe care le faci).
- **Libertatea furnizorilor**: OpenAI, Claude, Gemini, DeepSeek, Ollama, Azure, Bedrock... Peste 15 furnizori, toți accesibili dintr-o singură interfață. Schimbați între ele prin reconfigurarea variabilelor de mediu - fără reinstalare, fără migrare.
- **131 instrumente**: I/O fișiere, căutare web, generare de imagini, scanare dispozitiv BLE, integrare server MCP - și **76 dintre ele rulează în paralel**. Când LLM declanșează mai multe apeluri de instrumente simultan, uag le execută automat printr-un pool de fire.
- **4 interfețe de utilizare + A2A**: CLI, GUI, Web și protocol Agent-to-Agent. Același motor, orice interfață.
- **Pregătit pentru IoT**: SwitchBot, ECHONET Lite, Matter, UPnP — controlați-vă dispozitivele de acasă prin AI.
- **Abilități de agent**: Instalați abilități create de comunitate de pe piață. Extinde uag la nesfârșit.

uag este **asistentul tău AI conform condițiilor tale**. Nu este legat de un furnizor, nu este legat de o interfață, nu este legat de o platformă.

## Pornire rapidă

```bash
pip install uag
uag
```

La prima lansare, asistentul de configurare vă ghidează prin configurarea furnizorului.
Consultați [ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md) pentru toate variabilele de mediu.

## Caracteristici

### 🧠 Arhitectură cu mai mulți furnizori

OpenAI / Azure / Bedrock / OpenRouter / Ollama / Gemini / Vertex AI / Claude / Grok / NVIDIA / DeepSeek / Alibaba Cloud (Qwen) / KIMI (Moonshot AI) / Xiaomi MiMo / LM Studio / MiniMax / **Sakana AI (Fugu)**

Toți furnizorii au același set de instrumente și interfață. Comutați setând „UAGENT_PROVIDER” — fără modificări de cod, fără instalări separate.

### ⚡ Execuție paralelă a instrumentului

Când LLM solicită mai multe instrumente simultan, uag **le paralelizează automat**.
76 de instrumente sunt marcate `x_parallel_safe` și se execută simultan printr-un `ThreadPoolExecutor` cu 4 fire.

**Exemplu**: Întrebați „Verificați vremea în capitalele nordice” → LLM declanșează `search_web` × 5 țări → toate cele 5 căutări se desfășoară în paralel → rezultate colectate într-un singur lot.

Instrumentele numai pentru citire (căutarea fișierelor, calculul hash, listarea directoarelor, traducerea, interogările DB etc.) sunt paralelizate agresiv.

### 🔄 Continuitatea sesiunii

- **Schimbați furnizorul la mijlocul sesiunii** cu `UAGENT_PROVIDER` — istoricul conversațiilor este păstrat.
- **Reîncărcați sesiunile anterioare** cu `:load <index>` — reluați de unde ați rămas.
- **Memorizarea în cache a rezultatelor instrumentului** evită reexecuția redundantă atunci când se repetă același apel de instrument.

### 🛠 131 Instrumente

| Categoria | Instrumente |
|---|---|
| **Operațiuni cu fișiere** | citește/scrie/creează/șterge/căută/grep/hash/zip |
| **Web** | fetch_url, search_web, screenshot, browser_playwright |
| **Media** | genera_imagine, analizează_imagine, img2img, vorbire_audio, transcriere_audio |
| **Documente** | Extracție PDF/PPTX/DOCX/RTF/ODT, extracție structurată Excel |
| **IoT** | SwitchBot (Cloud + BLE), ECHONET Lite, Matter, UPnP |
| **Instrumente de dezvoltare** | git_ops, python_compile, lint_format, run_tests, db_query, **13 idx tools** |
| **MCP** | Conectați-vă la servere MCP externe, listați instrumentele, executați |
| **A2A** | Comunicare agent la agent (cu alte instanțe uag sau servere compatibile A2A) |
| **Sistem** | env vars, specificații de sistem, ora, calculul datei |

### 🖥 3 interfețe + A2A + VS Code

| Modul | Comanda | Scop |
|---|---|---|
| **CLI** | `uag` | Operare rapidă bazată pe terminal |
| **GUI** | `uagg` | Interfața de utilizare pentru desktop prin tkinter |
| **Web** | `uagw` | Acces bazat pe browser |
| **Server A2A** | `uaga` | Protocol Agent2Agent pentru comunicare multi-agent |
| **VS Code** | — | Extension (Chat Panel, Explain, Refactor, Fix Error, Tools Tree View) — see [VSCODE.md](VSCODE.md) |

### 🏠 Controlul dispozitivelor IoT

- **SwitchBot**: controlul loturilor în cloud și scanarea/controlul BLE
- **ECHONET Lite**: Descoperiți și controlați aparatele electrocasnice (AC, lumini, încălzitoare de apă etc.) în rețeaua locală
- **Materia**: inspecție numai în citire a topologiei controlerului/puntului/dispozitivului
- **UPnP**: Descoperirea dispozitivului și redirecționarea portului IGD

Vezi [IOT_USECASE.md](https://github.com/awaku7/agentcli/blob/main/IOT_USECASE.md)

### 🎯 Piața abilităților de agenți

`:skills mp_search` pentru a căuta [SkillsMP](https://skillsmp.com) și [ClawHub](https://clawhub.ai) pentru abilitățile comunității.
Instalați și extindeți capacitățile uag din mers.

### 🧩 Manager de stat lot

uag poate urmări progresul în sarcinile cu mai multe fișiere de lungă durată. Când LLM procesează zeci de fișiere, `batch_state` persistă pe disc lista fișierelor în așteptare, finalizate și eșuate. Dacă sesiunea se termină sau expiră o rundă, următoarea rulare reia de unde s-a oprit - nimic nu se pierde.

### 🛡 Human-in-the-Loop

`human_ask` permite LLM să întrerupă și să solicite confirmarea dumneavoastră înainte de a efectua operațiuni distructive (ștergerea fișierelor, suprascrieri, comenzi shell). Tu rămâi în control.

### 🛑 Interrupt (c-key / Stop button)

Stop LLM response generation at any time and inject a stop command back to the LLM.

| Interface | How to interrupt |
|---|---|
| **CLI** | Press `c` key during LLM streaming -- the current response stops, and `"Stop"` is sent as a user message so the LLM responds accordingly |
| **WEB UI** | Click the red **■ Stop** button (appears automatically during LLM processing) |
| **Desktop GUI** | Click the red **■** button (appears automatically during LLM processing) |

The interrupt works as "prompt injection": instead of just aborting, it feeds `"Stop"` back to the LLM as a user message, allowing it to gracefully conclude or acknowledge the interruption.

Press `x` key to exit auto-pilot mode (see `:auto` command).

### 🕵️ Automatizare browser și inspector web

Două instrumente complementare bazate pe dramaturg:

- **browser_playwright**: automatizați sesiunile reale de browser - navigați, faceți clic, completați formulare, extrageți date, gestionați fluxurile cu mai multe pagini. Funcționează fără cap sau cu cap.
- **playwright_inspector**: Înregistrați tranzițiile browserului, capturați instantanee și capturi de ecran DOM la fiecare pas. Util pentru depanarea interacțiunilor web sau pentru auditarea modificărilor paginii în timp.

### 🔄 Încărcare dinamică a instrumentului

`tool_catalog` și `tool_load` vă permit să descoperiți și să activați instrumente în timpul execuției.
Nu este nevoie să încărcați totul la pornire - activați doar ceea ce aveți nevoie, atunci când aveți nevoie.

### 🌐 i18n / L10n

日本語 / English / 简体中文 / 繁體中文 / 한국어 / Español / Français / Русский / și multe altele.
Setați `UAGENT_LANG` pentru a comuta. Consultați [ADD_LOCALE.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/ADD_LOCALE.md) pentru a adăuga o nouă localitate.

Traducerile acestui README sunt disponibile în [docs/README.translations.md](https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md).

### 🔒 Variabile de mediu criptate

Stocați cheile și secretele API în `.env.sec` — un fișier criptat `.env`.
Gestionați cu `uag_envsec`.

## Configurație și detalii

- **Variabile de mediu**: [ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md)
- **Setup wizard**: `python -m uagent.setup_cli`
- **Env criptat**: `uag_envsec` — criptează `.env` ca `.env.sec`
- **Responses API**: setați `UAGENT_RESPONSES=1` pentru modul Responses API (OpenAI/Azure/Bedrock/OpenRouter/Ollama/Alibaba/LM Studio/Sakana AI)
- **Documente pentru dezvoltatori**: [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)
- **Sfaturi mici LLM**: [SLM_TIPS.md](https://github.com/awaku7/agentcli/blob/main/SLM_TIPS.md)

## Filosofia proiectului

uag aspiră să fie **AI ta, pe mașina ta, în condițiile tale.**

- Fără dependență de SaaS - rulează local
- Fără blocare a furnizorului - comutați oricând
- Fără blocare UI - CLI / GUI / Web / A2A
- Fără blocare a funcției - extindeți-vă cu instrumente și abilități

O experiență gratuită de agent AI, fără blocarea furnizorului.