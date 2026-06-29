<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="logo uag" width="720">
</p>

<h1 align="center">uag — Univerzální brána umělé inteligence</h1>

<p align="center">
  <b>U</b>niversal <b>A</b>I <b>G</b>gateway — Vaše prostředí, vaše svoboda.
</p>

<p align="center">
  Operace souborů / Vyhledávání na webu / Generování a analýza obrázků / Extrakce PDF a Excel / Ovládání internetu věcí / Integrace MCP<br>
  Více než 15 poskytovatelů / 3 UI / Paralelní provádění nástrojů / Trh dovedností agentů
</p>

<p align="center">
  <a href="https://github.com/awaku7/agentcli">GitHub</a>
  ·
  <a href="https://pypi.org/project/uag/">PyPI</a>
  ·
  <a href="https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md">Přečtěte si toto ve svém jazyce</a>
</p>

---

## Proč uag?

**Zbavte se uzamčení dodavatele.** Většina asistentů umělé inteligence vás spojí s konkrétním poskytovatelem nebo cloudovou službou. uag je jiný.

- **Běží lokálně** na vašem počítači. Vaše data zůstanou s vámi (s výjimkou volání API, která provedete).
- **Svoboda poskytovatelů**: OpenAI, Claude, Gemini, DeepSeek, Ollama, Azure, Bedrock... 15+ poskytovatelů, vše přístupné z jediného rozhraní. Přepínejte mezi nimi překonfigurováním proměnných prostředí – žádná přeinstalace, žádná migrace.
- **131 nástrojů**: I/O souborů, vyhledávání na webu, generování obrázků, skenování zařízení BLE, integrace serveru MCP – a **76 z nich běží paralelně**. Když LLM spustí více volání nástrojů najednou, uag je automaticky provede prostřednictvím fondu vláken.
- **4 UI + A2A**: CLI, GUI, Web a Agent-to-Agent protokol. Stejný engine, jakékoli rozhraní.
- **IoT ready**: SwitchBot, ECHONET Lite, Matter, UPnP – ovládejte svá domácí zařízení pomocí AI.
- **Schopnosti agentů**: Nainstalujte si dovednosti vytvořené komunitou z trhu. Prodlužujte uag donekonečna.

uag je **váš asistent AI podle vašich podmínek**. Není vázáno na poskytovatele, není vázáno na rozhraní, není vázáno na platformu.

## Rychlý start

```bash
pip install uag
uag
```

Při prvním spuštění vás průvodce nastavením provede konfigurací poskytovatele.
Všechny proměnné prostředí najdete na [ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md).

## Funkce

### 🧠 Architektura s více poskytovateli

OpenAI / Azure / Bedrock / OpenRouter / Ollama / Gemini / Vertex AI / Claude / Grok / NVIDIA / DeepSeek / HuggingFace / Alibaba Cloud (Qwen) / KIMI (Moonshot AI) / Xiaomi MiMo / LM Studio / MiniMax / **Sakana AI (Fugu)**

Všichni poskytovatelé sdílejí stejnou sadu nástrojů a rozhraní. Přepněte nastavením `UAGENT_PROVIDER` — žádné změny kódu, žádné samostatné instalace.

### ⚡ Paralelní provádění nástroje

Když LLM požaduje více nástrojů současně, uag je **automaticky paralelizuje**.
76 nástrojů je označeno `x_parallel_safe` a spouští se souběžně prostřednictvím 4vláknového `ThreadPoolExecutor`.

**Příklad**: Zeptejte se „Zkontrolujte počasí v severských metropolích“ → LLM spustí `search_web` × 5 zemí → všech 5 vyhledávání běží paralelně → výsledky shromážděné v jedné dávce.

Nástroje pouze pro čtení (prohledávání souborů, výpočet hashů, výpis adresářů, překlad, DB dotazy atd.) jsou agresivně paralelizovány.

### 🔄 Kontinuita relace

- **Přepnout poskytovatele uprostřed relace** pomocí „UAGENT_PROVIDER“ – historie konverzace je zachována.
- **Znovu načtěte minulé relace** pomocí `:load <index>` – pokračujte tam, kde jste skončili.
- **Ukládání výsledků nástroje do mezipaměti** zabraňuje nadbytečnému opětovnému spuštění, když se opakuje stejné volání nástroje.

### 🛠 131 nástrojů

| Kategorie | Nástroje |
|---|---|
| **Operace souborů** | čtení/zápis/vytváření/mazání/hledání/grep/hash/zip |
| **Web** | fetch_url, search_web, screenshot, browser_playwright |
| **Média** | generovat_image, analyzovat_obraz, img2img, audio_speech, audio_transscribe |
| **Dokumenty** | Extrakce PDF/PPTX/DOCX/RTF/ODT, strukturovaná extrakce Excel |
| **IoT** | SwitchBot (Cloud + BLE), ECHONET Lite, Matter, UPnP |
| **Nástroje pro vývojáře** | git_ops, python_compile, lint_format, run_tests, db_query, **13 idx tools** |
| **MCP** | Připojte se k externím serverům MCP, vypište nástroje, spusťte |
| **A2A** | Komunikace agent-agent (s jinými instancemi uag nebo servery kompatibilními s A2A) |
| **Systém** | env vars, systémové specifikace, čas, výpočet data |

### 🖥 3 rozhraní + A2A + VS Code

| Režim | Příkaz | Účel |
|---|---|---|
| **CLI** | `uag` | Rychlý terminálový provoz |
| **GUI** | `uagg` | Desktop UI přes tkinter |
| **Web** | `uagw` | Přístup na základě prohlížeče |
| **Server A2A** | `uaga` | Agent2Agent protokol pro multi-agentní komunikaci |
| **VS Code** | — | Extension (Chat Panel, Explain, Refactor, Fix Error, Tools Tree View) — see [VSCODE.md](VSCODE.md) |

### 🏠 Ovládání zařízení IoT

- **SwitchBot**: Cloudové dávkové ovládání a BLE skenování/ovládání
- **ECHONET Lite**: Objevujte a ovládejte domácí spotřebiče (AC, světla, ohřívače vody atd.) v místní síti
- **Záležitost**: Kontrola topologie řadiče/můstku/zařízení pouze pro čtení
- **UPnP**: Zjištění zařízení a přesměrování portů IGD

Viz [IOT_USECASE.md](https://github.com/awaku7/agentcli/blob/main/IOT_USECASE.md)

### 🎯 Trh dovedností agentů

`:skills mp_search` pro procházení [SkillsMP](https://skillsmp.com) a [ClawHub](https://clawhub.ai) pro komunitní dovednosti.
Instalujte a rozšiřujte možnosti uag za běhu.

### 🧩 Batch State Manager

uag může sledovat postup v rámci dlouhodobých úloh s více soubory. Když LLM zpracovává desítky souborů, `batch_state` uchovává seznam nevyřízených, dokončených a neúspěšných souborů na disku. Pokud relace skončí nebo vyprší časový limit kola, další běh bude pokračovat od místa, kde byl zastaven – nic se neztratí.

### 🛡 Human-in-the-Loop

`human_ask` umožňuje LLM pozastavit se a požádat o vaše potvrzení před provedením destruktivních operací (smazání souboru, přepsání, příkazy shellu). Zůstanete pod kontrolou.

### 🛑 Interrupt (c-key / Stop button)

Stop LLM response generation at any time and inject a stop command back to the LLM.

| Interface | How to interrupt |
|---|---|
| **CLI** | Press `c` key during LLM streaming -- the current response stops, and `"Stop"` is sent as a user message so the LLM responds accordingly |
| **WEB UI** | Click the red **■ Stop** button (appears automatically during LLM processing) |
| **Desktop GUI** | Click the red **■** button (appears automatically during LLM processing) |

The interrupt works as "prompt injection": instead of just aborting, it feeds `"Stop"` back to the LLM as a user message, allowing it to gracefully conclude or acknowledge the interruption.

Press `x` key to exit auto-pilot mode (see `:auto` command).

### 🕵️ Automatizace prohlížeče a webový inspektor

Dva doplňkové nástroje založené na Playwrightovi:

- **browser_playwright**: Automatizujte skutečné relace prohlížeče – procházejte, klikejte, vyplňování formulářů, extrahujte data, zvládejte toky na více stránkách. Pracuje bez hlavy nebo s hlavou.
- **playwright_inspector**: Zaznamenávejte přechody prohlížeče, zachycujte snímky DOM a snímky obrazovky v každém kroku. Užitečné pro ladění webových interakcí nebo auditování změn stránky v průběhu času.

### 🔄 Dynamické načítání nástroje

`tool_catalog` a `tool_load` umožňují objevovat a povolit nástroje za běhu.
Není třeba načítat vše při spuštění – aktivujte pouze to, co potřebujete, když to potřebujete.

### 🌐 i18n / L10n

日本語 / anglicky / 简体中文 / 繁體中文 / 한국어 / Español / Français / Русский / a další.
Pro přepnutí nastavte `UAGENT_LANG`. Chcete-li přidat nové národní prostředí, přejděte na [ADD_LOCALE.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/ADD_LOCALE.md).

Překlady tohoto README jsou k dispozici na [docs/README.translations.md] (https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md).

### 🔒 Šifrované proměnné prostředí

Ukládejte klíče API a tajné informace do souboru `.env.sec` — zašifrovaného souboru `.env`.
Spravujte pomocí `uag_envsec`.

## Konfigurace a podrobnosti

- **Proměnné prostředí**: [ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md)
- **Průvodce nastavením**: `python -m uagent.setup_cli`
- **Šifrované env**: `uag_envsec` — šifrovat `.env` jako `.env.sec`
- **Responses API**: Nastavte `UAGENT_RESPONSES=1` pro režim Responses API (OpenAI/Azure/Bedrock/OpenRouter/Ollama/Alibaba/LM Studio/Sakana AI)
- **Dokumenty pro vývojáře**: [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)
- **Malé tipy LLM**: [SLM_TIPS.md](https://github.com/awaku7/agentcli/blob/main/SLM_TIPS.md)

## Filosofie projektu

uag chce být **vaší AI, na vašem počítači, za vašich podmínek.**

- Žádná závislost na SaaS – běží lokálně
- Žádné uzamčení poskytovatele – přepněte kdykoli
- Žádné uzamčení uživatelského rozhraní — CLI / GUI / Web / A2A
- Žádné uzamčení funkcí – rozšíření o nástroje a dovednosti

Bezplatná zkušenost s AI agentem, bez uzamčení dodavatele.