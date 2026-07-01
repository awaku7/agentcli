<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="720">
</p>

<h1 align="center">uag — Univerzální brána AI</h1>

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

## Proč uag?

**Zbavte se uzamčení dodavatele.** Většina asistentů umělé inteligence vás spojí s konkrétním poskytovatelem nebo cloudovou službou. uag je jiný.

- **Běží lokálně** na vašem počítači. Vaše data zůstanou s vámi (s výjimkou volání API, která provedete).
- **Svoboda poskytovatelů**: OpenAI, Claude, Gemini, DeepSeek, Ollama, Azure, Bedrock, HuggingFace... 15+ poskytovatelů, vše přístupné z jediného rozhraní. Přepínejte mezi nimi překonfigurováním proměnných prostředí – žádná přeinstalace, žádná migrace.
- **131 nástrojů**: I/O souborů, vyhledávání na webu, generování obrázků, Gmail, skenování zařízení BLE, integrace serveru MCP — **76 je paralelně bezpečných** (až 8 spouští souběžně prostřednictvím fondu vláken, konfigurovatelné pomocí `UAGENT_PARALLEL_WORKERS`). Když LLM spustí více volání nástrojů najednou, uag je automaticky paralelizuje.
- **3 UI + A2A**: CLI, GUI, Web a Agent-to-Agent protokol. Stejný engine, jakékoli rozhraní.
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

OpenAI / Azure / Bedrock / OpenRouter / Ollama / Gemini / Vertex AI / Claude / Grok / NVIDIA / DeepSeek / Z.AI (Zhipu AI) / HuggingFace / Alibaba Cloud (Qwen) / KIMI (Moonshot AI) / Xiaomi MiMo / LM Studio / MiniMax / **Sakana AI (**Sakana AI)

Všichni poskytovatelé sdílejí stejnou sadu nástrojů a rozhraní. Přepněte nastavením `UAGENT_PROVIDER` — žádné změny kódu, žádné samostatné instalace.

### ⚡ Paralelní provádění nástroje

Když LLM požaduje více nástrojů současně, uag je **automaticky paralelizuje**.
76 nástrojů je označeno `x_parallel_safe` a spouští se souběžně prostřednictvím `ThreadPoolExecutor` (ve výchozím nastavení 8 vláken; pro změnu nastavte `UAGENT_PARALLEL_WORKERS`).

**Příklad**: Zeptejte se „Zkontrolujte počasí v severských metropolích“ → LLM spustí `search_web` × 5 zemí → všech 5 vyhledávání běží paralelně → výsledky shromážděné v jedné dávce.

Nástroje pouze pro čtení (prohledávání souborů, výpočet hashů, výpis adresářů, překlad, DB dotazy atd.) jsou agresivně paralelizovány.

### 🔄 Kontinuita relace

- **Switch providers mid-session** with `UAGENT_PROVIDER` — conversation history is preserved.
- **Reload past sessions** with `:load <index>` — pick up where you left off.
- **Tool result caching** avoids redundant re-execution when the same tool call repeats.

### 🛠 131 nástrojů

| Kategorie | Nástroje |
|---|---|
| **Operace souborů** | číst/zapisovat/vytvářet/mazat/hledat/grep/hash/zip, parse_eml (soubory .eml) |
| **Web** | fetch_url, search_web, screenshot, browser_playwright |
| **Média** | generovat_image, analyzovat_obraz, img2img, audio_speech, audio_transscribe |
| **Dokumenty** | Extrakce PDF/PPTX/DOCX/RTF/ODT, strukturovaná extrakce Excel |
| **Komunikace** | gmail_send, gmail_read, bluesky, discord_channel, teamy_webhook — viz [COMMUNICATION.md](https://github.com/awaku7/agentcli/blob/main/docs/COMMUNICATION.md) |
| **IoT** | SwitchBot (Cloud + BLE), ECHONET Lite, Matter, UPnP |
| **Nástroje pro vývojáře** | git_ops, python_compile, lint_format, run_tests, db_query, **13 navigátorů zdrojového kódu (rodina idx)** |
| **MCP** | Připojte se k externím serverům MCP, vypište nástroje, spusťte |
| **A2A** | Komunikace agent-agent (s jinými instancemi uag nebo servery kompatibilními s A2A) |
| **Systém** | env vars, systémové specifikace, čas, výpočet data |
| **Zdroj Nav** | **13 nástrojů idx** pro Python, PHP, TypeScript, Java, C#, Dart, C/C++, Rust, Go, Swift, Kotlin, COBOL — získat index funkce/třídy nebo konkrétní definici bez čtení celého souboru |

### 🖥 4 rozhraní + rozšíření VS kódu

| Režim | Příkaz | Účel |
|---|---|---|
| **CLI** | "uag" | Rychlý terminálový provoz |
| **GUI** | "uagg" | Desktop UI přes tkinter |
| **Web** | "uagw" | Přístup na základě prohlížeče |
| **Server A2A** | "uaga" | Agent2Agent protokol pro multi-agentní komunikaci |
| **VS kód** | — | [Rozšíření](https://github.com/awaku7/agentcli/blob/main/VSCODE.md) s panelem chatu, vysvětlením, refaktorem, opravou chyb a stromovým zobrazením nástrojů |

Podrobnosti o rozšíření VS Code – instalace, příkazy, klávesové zkratky a konfigurace najdete na [VSCODE.md](https://github.com/awaku7/agentcli/blob/main/VSCODE.md).

### 🏠 Ovládání zařízení IoT

- **SwitchBot**: Cloudové dávkové ovládání a BLE skenování/ovládání
- **ECHONET Lite**: Objevujte a ovládejte domácí spotřebiče (AC, světla, ohřívače vody atd.) v místní síti
- **Záležitost**: Kontrola topologie řadiče/můstku/zařízení pouze pro čtení
- **UPnP**: Zjištění zařízení a přesměrování portů IGD

Viz [IOT_USECASE.md](https://github.com/awaku7/agentcli/blob/main/IOT_USECASE.md)

### 🎯 Trh dovedností agentů

`:skills mp_search` pro procházení [SkillsMP](https://skillsmp.com) a [ClawHub](https://clawhub.ai) pro komunitní dovednosti.
Instalujte a rozšiřujte možnosti uag za běhu.

### 🤖 Auto-Pilot (`:auto`)

uag může **autonomně sledovat cíl ve více kolech LLM**. Ideální pro složité, vícekrokové úkoly, které vyžadují iterativní upřesňování.

- **Jak to funguje**: Každé kolo má hlavní dotaz (krok A) následovaný posudkem recenzenta (krok B), který rozhodne "DOKONČIT, nebo POKRAČOVAT?"
- **Stejný poskytovatel, stejné API**: Posudek recenzenta používá identickou cestu kódu jako hlavní dotaz – včetně podpory Responses API.
- **Samostatný soudce LLM** (volitelné): Nastavte `UAGENT_AP_PROVIDER` pro použití jiného poskytovatele/modelu pro recenzenta (např. použijte levnější model pro posuzování).
- **Ukončit kdykoli**: Stisknutím tlačítka „x“ okamžitě zastavíte, dokonce i uprostřed odezvy. Nebo nechte recenzenta rozhodnout, kdy bude cíl splněn.
- **Konfigurovatelné**: `--max-rounds N` pro kontrolu rozpočtu.

Úplnou dokumentaci naleznete na [README_AUTO.md](https://github.com/awaku7/agentcli/blob/main/README_AUTO.md).

### 🧩 Batch State Manager

uag může sledovat pokrok v dlouhodobých úlohách s více soubory. Když LLM zpracovává desítky souborů, `batch_state` uchovává seznam nevyřízených, dokončených a neúspěšných souborů na disku. Pokud relace skončí nebo vyprší časový limit kola, další běh pokračuje od místa, kde byl zastaven – nic se neztratí.

### 🛡 Human-in-the-Loop

`human_ask` umožňuje LLM pozastavit se a požádat o vaše potvrzení před provedením destruktivních operací (smazání souboru, přepsání, příkazy shellu). Zůstanete pod kontrolou.

### 🛑 Přerušení (klávesa c / tlačítko Stop)

Kdykoli zastavte generování odezvy LLM a vložte příkaz stop zpět do LLM.

| Rozhraní | Jak přerušit |
|---|---|
| **CLI** | Stiskněte klávesu `c` během streamování LLM — aktuální odpověď se zastaví a `"Stop"` se odešle jako uživatelská zpráva, takže LLM odpovídajícím způsobem odpoví |
| **WEBOVÉ ROZHRANÍ** | Klikněte na červené tlačítko **■ Stop** (zobrazí se automaticky během zpracování LLM) |
| **GUI pro stolní počítače** | Klikněte na červené tlačítko **■** (objeví se automaticky během zpracování LLM) |

Přerušení funguje jako "promptní vložení": namísto pouhého přerušení odešle "Stop"` zpět do LLM jako uživatelskou zprávu, která mu umožňuje ladně uzavřít nebo potvrdit přerušení.

Stisknutím klávesy `x` ukončíte režim autopilota (viz [README_AUTO.md](https://github.com/awaku7/agentcli/blob/main/README_AUTO.md)).

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
- **Responses API**: Nastavte `UAGENT_RESPONSES=1` pro režim Responses API (OpenAI/Azure/Bedrock/OpenRouter/Ollama/Alibaba/LM Studio/Sakana AI). Automaticky povoleno pro Sakana AI (Fugu).
- **Dokumenty pro vývojáře**: [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)
- **Malé tipy LLM**: [SLM_TIPS.md](https://github.com/awaku7/agentcli/blob/main/SLM_TIPS.md)

## Filosofie projektu

uag chce být **vaší AI, na vašem počítači, za vašich podmínek.**

- Žádná závislost na SaaS – běží lokálně
- Žádné uzamčení poskytovatele – přepněte kdykoli
- Žádné uzamčení uživatelského rozhraní — CLI / GUI / Web / A2A
- Žádné uzamčení funkcí – rozšíření o nástroje a dovednosti

Bezplatná zkušenost s AI agentem, bez uzamčení dodavatele.
