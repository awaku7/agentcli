<p align="center">
 <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="720">
</p>

<h1 align="center">
1<h1 align="center">__AIP_4 brána align="center">
 <b>U</b>niversal <b>A</b>I <b>G</b>gateway — Vaše prostředí, vaše svoboda.
</p>

<p align="center">
 Operace souborů / Web vyhledávání / Generování a analýza obrázků / Extrakce PDF a Excel / Poskytovatelé IoT / Ovládání 2 uag / _3 PH_4 Paralelní provádění nástrojů / tržiště dovedností agentů
</p>

<p align="center">
 <a href="https://github.com/awaku7/agentcli">GitHub</a>
 ·
 <a href="https://pypi.org/project/ <uag/">Py ·a</a> href="https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md">Přečtěte si toto jazyk</a>
</p>

______________________________________________________________________

## Proč uag?

**Zbavte se vazby na dodavatele.** Většina asistentů umělé inteligence vás spojuje s konkrétním poskytovatelem nebo cloudovou službou. uag je jiný.

- **Běží místně** na vašem počítači. Vaše data zůstanou s vámi (kromě API hovorů, které provedete).
- **Svoboda poskytovatelů**: OpenAI, Claude, Gemini, DeepSeek, Ollama, Azure, Bedrock, Novita, HuggingFace... 24 poskytovatelů, vše přístupné z jediného rozhraní. Přepínejte mezi nimi překonfigurováním proměnných prostředí – žádná přeinstalace, žádná migrace.
  – **222 nástrojů**: File I/O, vyhledávání na webu, generování obrázků, Gmail, skenování zařízení BLE, integrace serveru MCP — **130 je staticky označeno jako paralelně bezpečné** (až 8 spouští souběžně prostřednictvím fondu vláken, konfigurovatelné přes `EL_UAGENT_`). Když LLM spustí více volání nástrojů najednou, uag je automaticky paralelizuje.
- **3 UI + A2A**: CLI, GUI, Web a protokol Agent-to-Agent. Stejný engine, jakékoli rozhraní.
- **Připraveno pro IoT**: SwitchBot, ECHONET Lite, Matter, UPnP – ovládejte svá domácí zařízení pomocí AI.
- **Schopnosti agentů**: Nainstalujte si dovednosti vytvořené komunitou z trhu. Rozšiřujte uag donekonečna.

uag je **váš asistent AI podle vašich podmínek**. Není vázáno na poskytovatele, není vázáno na rozhraní, není vázáno na platformu.

## Rychlý start

```bash
pip instalace uag
uag
```

Při prvním spuštění vás průvodce nastavením provede konfigurací poskytovatele.
Viz \[docs/ENVIRONMENT.md\](https://github.com/awaku7/ENagent environment/VI proměnné.

## Computer Use

Computer Use je přihlášeno a podporuje viditelné Playwright běhové prostředí prohlížeče
i běhové prostředí pro stolní počítače. Když je tato možnost povolena, vytvoří se a zaregistrují obě runtime;

```bat
set UAGENT_COMPUTER_USE=1
```

Namísto toho vyberte desktop\`\`\`\`

U`U Prostředky Runtime jsou uzavřeny dohromady při normálním ukončení, `Ctrl-C`a vypnutí procesu. Nastavte`UAGENT_COMPUTER_HEADLESS=1\` pro CI nebo kouřové testy založené na prohlížeči.
Podrobnosti o integraci a bezpečnosti najdete na [docs/COMPUTER_USE_IMPLEMENTATION.md](docs/COMPUTER_USE_IMPLEMENTATION.md)
.

## Hlas v reálném čase a AEC3

Režim hlasu v reálném čase podporuje OpenAI v reálném čase, Azure OpenAI GPT v reálném čase, xAI Grok hlas API, Google Gemini Multimodal Live Gemini reproduktor s plným mikrofonem Amazon Irock Nova-Sonic. Požadovaný backend AEC3 `pywebrtc-audio` se nainstaluje automaticky a volitelná sada SDK pro obousměrné streamování společnosti Bedrock se nainstaluje automaticky pouze v případě, že je vybrán poskytovatel Bedrock:

```bash
python scheck.py realtime
```

Potrubí AEC3 skutečně přijímá skutečný zvukový signál (zvukový signál z mikrofonu) a do ručního asistenta. může poslouchat při mluvení. Diagnostiku povolte pouze při vyšetřování problémů se zvukem:

```bat
set UAGENT_REALTIME_AUDIO_DEBUG=1
python scheck.py realtime
```

### OpenAI Funkce volání v reálném čase

OpenAI Integrace volání v reálném čase podporuje bezpečnostní funkci Aktuální adaptér v reálném čase automaticky zpřístupňuje `get_current_time` pouze pro čtení. Destruktivní nástroje a ovládací prvky zařízení nejsou vystaveny bez explicitního seznamu povolených a potvrzovacího toku. Grok realtime používá samostatný adaptér a nepoužívá tuto cestu volání funkce specifickou pro OpenAI.

## Funkce

### 🧠 Architektura pro více poskytovatelů

OpenAI / PFN (PLaMo) / Azure / Bedrock / OpenRouter / Ollama / llama.cpp / Gemini / Vertex AI / audio_speech / NVID Seek / NVID Zita \_.PH (Zhipu AI) / HuggingFace / Alibaba Cloud (Qwen) / KIMI (Moonshot AI) / Xiaomi MiMo / LM Studio / MiniMax / Sakana AI (Fugu) / SAKURA AI Engine / Together AI / Vercel AI Gateway

Všichni poskytovatelé sdílejí stejnou sadu nástrojů a rozhraní. Přepínejte nastavením `UAGENT_PROVIDER` — žádné změny kódu, žádné samostatné instalace.

#### Ollama a llama.cpp

Ollama a llama.cpp jsou samostatní poskytovatelé. Ollama používá vlastní správu služeb a modelů, zatímco `llama.cpp` se připojuje ke koncovému bodu kompatibilnímu s `llama-server` OpenAI:

```bash
# Ollama
UAGENT_PROVIDER=ollama
UAGENT_OLLAMA_BASE_URL=http://localhost:11434/v1
UAGENT_OLLAMA_DEPNAME=llama3.1

# llama.cpp / llama-server
UAGENT_PROVIDER=llama_cpp
UAGENT_LLAMA_CPP_BASE_URL=http://localhost:8080/v1
UAGENT_LLAMA_CPP_DEPNAME=local-model
UAGENT_LLAMA_CPP_API_KEY=dummy
```

The llama.cpp provider používá cestu kompatibilní s dokončováním chatu. Zachovejte `UAGENT_RESPONSES=0`, pokud není nakonfigurován kompatibilní proxy.

### ⚡ Paralelní spouštění nástrojů

Když LLM požaduje více nástrojů současně, uag je **automaticky paralelizuje**.
130 nástrojů je staticky označeno jako concurrent_xafe` `ThreadPoolExecutor`(ve výchozím nastavení 8 vláken; pro změnu nastavte`UAGENT_PARALLEL_WORKERS\`).

**Příklad**: Zeptejte se „Zkontrolujte počasí v severských metropolích“ → LLM spustí `search_web` × 5 zemí → všech 5 vyhledávání běží paralelně na základě → výsledky shromážděné v jednom modulu `TOOL_SPEC` (aktuálně 222, včetně 2 nástrojů podporovaných Rustem v `src/uagent/tools_rust/`). `http_request` používá bezpečnost citlivou na metody: volání `GET`/`HEAD`/`OPTIONS` mohou běžet paralelně, zatímco metody zápisu zůstávají sériové.

Nástroje pouze pro čtení (vyhledávání souborů, výpočet hash, výpis adresářů, překlad, dotazy DB atd.) jsou agresivně paralelizovány. Kompatibilní)

uagent implementuje systém zásuvných modulů **Claude kompatibilní s kódem**. Pluginy sdružují dovednosti, agenty, MCP servery, háky a další do samostatných adresářů s manifestem `.claude-plugin/plugin.json`.

**Podporované komponenty**: dovednosti, dílčí agenti, servery MCP, háky (12 událostí životního cyklu, styly výstupních příkazů, přelomení kanálu), kanál Slash Příkazy Marketplaces

**CLI**:

```
:seznam pluginů # Seznam nainstalovaných pluginů
:plugin install <zdroj> [--scope] # Install (dir/zip/git/http)
:plugin install <name>@<marketplace> # Install from marketplace
 # disable: <plugin remove # enable/name Toggle
:plugin marketplace add/remove/list # Manage marketplaces
:plugin init <name> # Scaffold new plugin
```

Úplnou dokumentaci naleznete na [DEVELOP_PLUGIN.md](src/uagent/docs/DEVELOP_PLUGIN.md)⟏##⏄⟏. Kontinuita

- **Změňte poskytovatele uprostřed relace** pomocí `UAGENT_PROVIDER` — historie konverzace je zachována.
- **Znovu načtěte minulé relace** pomocí `:load <index>` — pokračujte tam, kde jste skončili.
- **Ukládání výsledků do mezipaměti nástroje** zabraňuje nadbytečnému opětovnému spuštění ###9 při stejném nástroji. ⏛2 Nástroje

| Kategorie | Nástroje |
|---|---|
| **Operace souborů** | číst/zapisovat/vytvářet/mazat/hledat/grep/hash/zip, typ_souboru, parse_eml (soubory .eml), `alias_cesty` |
| **Web** | fetch_url, search_web, screenshot, browser_playwright, `url_alias`, `public_transit_route` ([guide](docs/PUBLIC_TRANSIT_ROUTE.md)) |
| **Média** | generovat_image, analyzovat_obrazek, img2img, audio_speech, audio_transcribe |
| **Dokumenty** | Extrakce PDF/PPTX/DOCX/RTF/ODT, strukturovaná extrakce Excel |
| **Předpověď** | Prognóza časových řad s 9 modely (AutoARIMA, Prophet, LightGBM, CatBoost, TimesFM atd.), automatický výběr modelu, generování grafu, i18n |
| **Komunikace** | gmail_send, gmail_read, bluesky, discord_channel, teamy_webhook, **pybitchat** (BLE Mesh) – viz [COMMUNICATION.md](https://github.com/awaku7/agentcli/blob/main/docs/COMMUNICATION.md) a [BITCHAT.md](https://github.com/awaku7/agentcli/blob/main/docs/BITCHAT.md) |
| **IoT** | SwitchBot (Cloud + BLE), ECHONET Lite, Matter, UPnP, reverse_geocode |
| **Cloud API** | `aws_api`, `gcp_api`, `azure_api` – generické operace AWS, Google Cloud a Azure API; operace zápisu vyžadují výslovné potvrzení |
| **Nástroje pro vývojáře** | workspace_status, git_ops, git_review, security_scan, coverage_report, python_compile, lint_format, run_tests, db_query, **29 navigátorů zdrojového kódu (rodina idx)** |
| **MCP** | Připojte se k externím serverům MCP, vypište nástroje, spusťte — [Průvodce protokolem OAuth / proxy](docs/MCP_OAUTH_PROXY_GUIDE.md) |
| **A2A** | Komunikace mezi agenty (s jinými instancemi uag nebo servery kompatibilními s A2A) |
| **Systém** | env vars, systémové specifikace, čas, výpočet data, [množství](docs/QUANTITIES.md), [geodesic_distance](docs/GEODESIC_DISTANCE.md), uuid_gen, slugify |
| **Zdroj Nav** | **29 nástrojů idx** pro Python, PHP, TypeScript, Java, C#, Dart, C/C++, Rust, Go, Swift, Kotlin, COBOL, VBA, LotusScript, Makefile — získejte index funkce/třídy nebo konkrétní definici, aniž byste museli číst celý soubor |

###⎢usstat \`-work report the aktivní repozitář a pokrytí větev Git pracovního prostoru, změny, stav synchronizace upstream, runtime Python a běžné značky projektu bez úpravy souborů.

- `git_review`: shrnutí změn Gitu, rizikových souborů, kandidátů na testování a tajných nálezů bez odhalení tajných hodnot.
- `security_scan`: skenování souborů úložiště na pravděpodobná tajemství portů a riskantní `prohledání souborů úložišť na pravděpodobná`⎎recovery a riskantní_konfigurační soubory. Python, TypeScript/JavaScript, Rust, Go, Java/Kotlin, .NET, C/C++, Ruby, PHP, Swift a Dart/Flutter.
- Chybějící závislosti pokrytí lze nainstalovat automaticky, když je požadováno spuštění; `dry_run` nikdy neinstaluje balíčky.

Viz [Nástroje pro analýzu úložiště](docs/REPOSITORY_TOOLS.md) pro parametry, výstup a bezpečnostní podrobnosti.

Viz [Cesta a aliasy URL](docs/PATH_URL_ALIASES.md) pro zkrácení opakovaných cest k souborům a URL#4. Rozhraní + rozšíření kódu VS

| Režim | Příkaz | Účel |
|---|---|---|
| **CLI** | `uag` | Rychlý terminálový provoz |
| **GUI** | "uagg" | Desktop UI přes tkinter |
| **Web** | "uagw" | Přístup na základě prohlížeče |
| **A2A Server** | "uaga" | Protokol Agent2Agent pro multiagentní komunikaci |
| **VS kód** | — | [Rozšíření](https://github.com/awaku7/agentcli/blob/main/docs/VSCODE.md) s panelem chatu, vysvětlením, refaktorem, opravou chyb a zobrazením stromu nástrojů |

Viz \[VSCODE.md\](podrobnosti https://github.com/awaku7/agentcli on/VMD Code pro rozšíření Vmd/docs. instalace, příkazy, klávesové zkratky a konfigurace.

### 🏠 Řízení zařízení IoT

- **BACnet**: Čtení/zápis zařízení BACnet/IP (HVAC, osvětlení, měřiče výkonu). Předplatné COV pro oznámení push
- **Modbus TCP**: Čtení/zápis přidržovacích/vstupních registrů a cívek. Monitorování změn na základě dotazování
- **OPC UA**: Procházení adresního prostoru, čtení/zápis proměnných, přihlášení k odběru změn dat
- **SwitchBot**: Cloudové dávkové řízení a BLE skenování/ovládání. Předplatné na základě dotazování
  – **ECHONET Lite**: Objevte, ovládejte a přihlaste se k odběru oznámení INF z domácích spotřebičů (AC, světla, ohřívače vody atd.)
  – **Záležitost**: Řízení čtení/zápisu + předplatné atributů pro sledování změny stavu
  – **UPnP**: Zjišťování zařízení a předávání portů IGD

Viz [IOT_USECASE.md](https://github.com/awaku7/agentcli/blob/main/docs/IOT_USECASE.md)

### 🎯 Agent Skills Marketplace

`:skills mp_search` k procházení [SkillsMP].https://) [ClawHub](https://clawhub.ai) pro komunitní dovednosti.
Instalujte a rozšiřujte možnosti uag za chodu.

### 🤖 Auto-Pilot (`:auto`)

uag může **autonomně sledovat cíl v několika LLM kolech**. Perfektní pro složité, vícekrokové úkoly, které vyžadují iterativní upřesnění.

- **Jak to funguje**: Každé kolo má hlavní dotaz (krok A) následovaný posudkem recenzenta (krok B), který rozhodne „DOKONČIT nebo POKRAČOVAT?“
- **Stejný poskytovatel, stejný dotaz API**: Posudek recenzenta používá identickou podporu kódu, včetně cesty k odpovědi-PH_3 jako hlavní kód odpovědi-PH **Samostatný porotce LLM** (volitelné): Nastavte `UAGENT_AP_PROVIDER` pro použití jiného poskytovatele/modelu pro recenzenta (např. použijte levnější model pro posuzování).
- **Ukončit kdykoli**: Stisknutím klávesy F11 okamžitě zastavíte, dokonce i uprostřed odezvy. Nebo nechte recenzenta, aby rozhodl, kdy je cíl splněn.
- **Konfigurovatelné**: `--max-rounds N` pro kontrolu rozpočtu.

Úplnou dokumentaci naleznete v [README_AUTO.md](https://github.com/awaku7/agentcli/blob/main/docs/README_AUTO.md). Správce

uag může sledovat postup v rámci dlouho běžících úloh s více soubory. Když LLM zpracovává desítky souborů, `batch_state` uchovává na disku seznam čekajících, dokončených a neúspěšných souborů. Pokud relace skončí nebo vyprší časový limit kola, další běh bude pokračovat od místa, kde byl zastaven – nic se neztratí.

### 🛡 Human-in-the-Loop

`human_ask` umožňuje LLM pozastavit se a požádat o potvrzení před provedením destruktivních operací (smazání souboru, přepsání, příkazy shellu). Zůstanete pod kontrolou.

### 🛑 Přerušení (klávesa c/tlačítko Stop)

Zastavte generování odpovědi LLM kdykoli a zadejte příkaz zastavení zpět do LLM.

| Rozhraní | Jak přerušit |
|---|---|
| **CLI** | Stiskněte klávesu F12 během streamování LLM – aktuální odpověď se zastaví a `"Stop"` se odešle jako uživatelská zpráva, takže LLM odpovídajícím způsobem zareaguje |
| **WEBOVÉ ROZHRANÍ** | Klikněte na červené tlačítko **■ Zastavit** (zobrazí se automaticky během zpracování LLM) |
| **Počítač GUI** | Klikněte na červené tlačítko **■** (objeví se automaticky během zpracování LLM) |

Přerušení funguje jako „prompt injection“: namísto pouhého přerušení odešle „Stop“\` zpět do LLM jako uživatelskou zprávu, což mu umožní ladně ukončit nebo potvrdit přerušení. [README_AUTO.md](https://github.com/awaku7/agentcli/blob/main/docs/README_AUTO.md)).

### 🕵️ Automatizace prohlížeče a Web Inspector

Dva doplňkové nástroje založené na Playwrightwright Playwright\*\* brows: mate: mate

### relace prohlížeče – navigace, kliknutí, vyplňování formulářů, extrahování dat, zpracování vícestránkových toků. Funguje bez hlavy nebo bez hlavy.

- **playwright_inspector**: Zaznamenávejte přechody prohlížeče, pořizujte snímky DOM a snímky obrazovky v každém kroku. Užitečné pro ladění webových interakcí nebo auditování změn stránky v průběhu času.

### 🔄 Dynamické načítání nástrojů

`tool_catalog` a `tool_load` vám umožňují objevovat a povolit nástroje za běhu.
Není třeba načítat vše při spuštění – aktivujte pouze to, co potřebujete, když to potřebujete.

## Rusative. Nástroje

`uuid_gen` a `slugify` jsou implementovány v Rust (prostřednictvím PyO3) kvůli výkonu.
Načítají se přímo z předem vytvořeného `.pyd` — **není potřeba `pip install`**.

Externí vývojáři mohou dodávat také nástroje založené na Rust, umístěte `⏏wra` py`vedle`.pyd.` `load_rust_pyd()`z`uagent.tools.rust_helper\` a
uživatelé získají tento nástroj bez jakýchkoli dalších závislostí. Viz
[TOOL_CREATOR_GUIDE.md](https://github.com/awaku7/agentcli/blob/main/TOOL_CREATOR_GUIDE.md).

### 🌐 i18n / L10n

日本語 / 䖓万語 / anglicky / 简繁體中文 / 한국어 / Español / Français / Русский / a další.
Pro přepnutí nastavte `UAGENT_LANG`. Chcete-li přidat nové národní prostředí, přejděte na [ADD_LOCALE.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/ADD_LOCALE.md).

Překlady tohoto README jsou k dispozici v [docs/README.translations.md](https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md).

### 🔒 Proměnné šifrovaného prostředí

Ukládejte API``` klíče a tajemství v zašifrovaném ``ec. soubor. Spravujte pomocí ```uag_envsec\`.

## Konfigurace a podrobnosti

- **Proměnné prostředí**: [docs/ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/docs/ENVIRONMENT.md)
- **Průvodce nastavením**: `python -m __PH**:Encrypted `uag_envsec`— zašifrovat`.env`jako`.env.sec\`
- **Odpovědi API**: Nastavte `UAGENT_RESPONSES=1` pro režim odpovědí API (OpenAI/Azure/Bedrock/OpenRouter/AILM/babakana/Ollama). Automaticky povoleno pro Sakana AI (Fugu).
- **Dokumenty pro vývojáře**: [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)
- **Tok nástrojů**: [TOOL_FLOW.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/TOOL_FLOW.md) – jak jsou nástroje odesílány do LLM (maska žánru, katalog nástrojů, GPT-5.4+ nativní tipy pro vyhledávání nástrojů)
- PH_5\*\*Small : [SLM_TIPS.md](https://github.com/awaku7/agentcli/blob/main/docs/SLM_TIPS.md)

## Project Philosophy

uag se snaží být **vaší AI, na vašem počítači, podle vašich podmínek.**

- Žádná závislost na SaaS – běží lokálně
- Žádné uzamčení poskytovatele – přepínání kdykoli
  – Žádné uzamčení uživatelského rozhraní – CLI / Web / _0 funkce uzamčení-_ rozšířit pomocí nástrojů a dovedností

Bezplatná zkušenost s agentem AI, bez uzamčení dodavatele.

### ✨ Vytvořte si vlastní nástroje

Psaní nového nástroje pro uag je přímočaré – vytvořte jeden soubor `.py` pomocí
`TOOL_SPEC` a `run_tool()` `UAGENT_EXTERNAL_TOOLS_DIR` a
je okamžitě k dispozici. Vývojářům Rust zašlete předpřipravený soubor `.pyd` s
nulovými závislostmi navíc pro uživatele.

Viz [TOOL_CREATOR_GUIDE.md](https://github.com/awaku7/agentcli/blob/main/TOOL_CREATOR_GUIDE.md)

podrobný návod⎏⎏## Přispívání

Příspěvky jsou vítány! Hlášení chyb, návrhy funkcí, vylepšení dokumentace, překlady a žádosti o stažení – to vše se cení.

- **Problémy**: Otevřete problém GitHub pro chyby nebo požadavky na funkce.
- **Požadavky na stažení**: Rozdělte repo, proveďte změny a odešlete PR. Nastavení vývoje a pokyny naleznete na [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md).
- **Překlady**: Překlady README a přidání národního prostředí jsou vítány. Viz [ADD_LOCALE.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/ADD_LOCALE.md).
- **Nástroje a dovednosti**: Nové zásuvné moduly nástrojů a dovednosti agenta lze přispívat prostřednictvím tržiště.
  ⎕ Vývojová kontrola (Install)⎎#l# nejprve pouze testovací závislosti. Jsou drženy mimo seznam runtime
  závislosti:

```bash
python -m pip install -e ".[test]"
python -m pip install black ruff
```

Spusťte stejné kontroly, jaké používá GitHub Akce před odesláním:
th ruffy -rc:
thbash⏏ testy
python -m black --check src tests
python scripts/tool_json_i18n_batch.py status
python -m pytest -q .

````

Pro rychlejší místní iteraci spouštějte pouze příslušné testy:

```bash
py test testy/<affected_area>
````

Další kontroly, pokud jsou relevantní:

````bash
python -m py_compile src/uagent/
mypy src/uagent
```) pyth po locale (s:`. scripts/compile_locales.py` a `python scripts/po_qc_summary.py`.

Runtime zásada (podrobnosti v [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docmd.6): nápověda §1ersOP místo ofmds/DEVELOP.6 `sys.exit`; hostitel nástroje změní nástroj `SystemExit`/`Exception` na chybové řetězce, takže jediný nástroj nemůže proces ukončit. Rychlé ukončení spouštění při selhání zůstává záměrné.

## Architektura a provozní invarianty

Prohlédněte si [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) pro trvalé smlouvy zahrnující A2A životní cyklus, kontexty I18N, volitelnou instalaci závislostí, bezpečnost nástroje, možnosti poskytovatele, hranice důvěryhodnosti OAuth, strukturované události⎎ a ověření přijetí.## Enterprise Policy Engine

 Jsou podporovány zásady na úrovni organizace pro nástroje, poskytovatele, přihlašovací údaje, MCP servery, sítě, dovednosti a pluginy. Nastavit `UAGENT_POLICY_FILE` na soubor zásad JSON/YAML; viz [docs/ENTERPRISE_POLICY.md](docs/ENTERPRISE_POLICY.md) pro příklady konfigurace, role, potvrzení a seznamy povolených.


### Runtime obnovení a orchestrace

Viz [RESTART_RECOVERY.md](docs/RESTART_RECOVERY.md)RECOVERY [DAG_SCHEDULER.md](docs/DAG_SCHEDULER.md) / [MULTI_AGENT_RUNTIME.md](docs/MULTI_AGENT_RUNTIME.md) pro trvalé obnovení, spouštění s vědomím závislostí, orchestraci s více agenty a vzdálené použití A2A.

Viz. [DISTRIBUTED_COORDINATION.md](docs/DISTRIBUTED_COORDINATION.md) pro koordinaci pronájmu vedoucího ve sdíleném běhu.
````
