<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="680">
</p>

<h1 align="center">uag</h1>

<p align="center">
  <strong>Univerzální AI brána</strong><br>
  Jeden lokální agent. Jakýkoli model. Jakýkoli nástroj. Vaše prostředí, vaše pravidla.
</p>

<p align="center">
  <a href="https://github.com/awaku7/agentcli/actions"><img src="https://img.shields.io/github/actions/workflow/status/awaku7/agentcli/ci.yml?style=flat-square&label=CI" alt="CI status"></a>
  <a href="https://pypi.org/project/uag/"><img src="https://img.shields.io/pypi/v/uag?style=flat-square" alt="PyPI version"></a>
  <a href="https://pypi.org/project/uag/"><img src="https://img.shields.io/pypi/pyversions/uag?style=flat-square" alt="Python versions"></a>
  <a href="https://github.com/awaku7/agentcli/blob/main/LICENSE"><img src="https://img.shields.io/github/license/awaku7/agentcli?style=flat-square" alt="License"></a>
  <a href="https://pepy.tech/projects/uag"><img src="https://static.pepy.tech/personalized-badge/uag?period=total&units=INTERNATIONAL_SYSTEM&left_color=grey&right_color=green&left_text=downloads" alt="PyPI Downloads"></a>
</p>

<p align="center">
  <a href="https://github.com/awaku7/agentcli">GitHub</a> ·
  <a href="https://pypi.org/project/uag/">PyPI</a> ·
  <a href="https://github.com/awaku7/agentcli/discussions">Diskuse</a> ·
  <a href="https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md">Překlady</a>
</p>

______________________________________________________________________

**Proč uag?**

uag je AI agent s prioritou lokálního zpracování, který propojuje vámi preferovaný model s nástroji, které skutečně používáte.
Poskytuje jediné rozšiřitelné běhové prostředí pro soubory, prohlížeče, kódové základny, komunikaci, cloudová API,
IoT zařízení, MCP servery a pracovní postupy s více agenty.

- **Svoboda volby poskytovatele** — OpenAI, Anthropic, Gemini, Azure, Bedrock, Ollama, llama.cpp, Grok, DeepSeek a další.
- **Lokální provádění v první řadě** — běhové prostředí agenta i provádění nástrojů zůstávají na vašem počítači; opouštějí jej pouze API volání, která zvolíte.
- **Jedna vrstva nástrojů** — stejné nástroje fungují z CLI, desktopového GUI, webového UI, VS Code i A2A.
- **Navrženo pro paralelní běh** — nezávislé operace pouze pro čtení mohou běžet souběžně.
- **Rozšiřitelnost** — přidávejte nástroje, pluginy, Agent Skills, MCP servery a nástroje využívající Rust bez změn jádra.
- **S ohledem na bezpečnost** — destruktivní akce, přihlašovací údaje, ovládání zařízení a síťové zápisy podporují explicitní potvrzení a zásady.

> **Stručně:** uag je řídicí rovina mezi vašimi AI modely a skutečným prostředím.

> **🧠 Výsledky nástrojů s ohledem na kontext** — Rozsáhlé výsledky nástrojů se pokud možno neukládají do kontextu aktivního modelu. uag je ukládá jako artefakty a modelu místo toho předává ohraničený náhled se stabilním odkazem na Artifact. To může podstatně snížit počet vstupních tokenů potřebných pro následující tahy, když nástroj vygeneruje rozsáhlý výsledek.
> [Podrobný průvodce kompresí kontextu](CONTEXT_COMPRESSION.cs.md)

## Rychlý start

**Python 3.11+**

```bash
python -m pip install --upgrade uag
uag
```

Při prvním spuštění se otevře průvodce nastavením. Pomůže nakonfigurovat poskytovatele a uloží vybraná nastavení
do vašeho lokálního prostředí.

Pro běžné skupiny funkcí:

```bash
python -m pip install "uag[core,providers,tools]"
```

> Integrace platformy jsou volitelné. Nainstalujte pouze to, co váš operační systém potřebuje; viz

```text
> What files changed in this repository?
> Search the web for today's AI news and summarize the top five stories.
> :help
```

[Quickstart](QUICKSTART.md) · [Environment](ENVIRONMENT.md)

## Rozhraní

| Rozhraní | Příkaz | Nejvhodnější pro |
|---|---|---|
| **CLI** | `uag` | Rychlou práci primárně s klávesnicí |
| **Desktopové GUI** | `uagg` | Nativní desktopové prostředí |
| **Webové UI** | `uagw` | Přístup z prohlížeče |
| **Server A2A** | `uaga` | Komunikaci agent–agent |
| **VS Code** | Extension | Vysvětlování, refaktorování, opravy a procházení nástrojů v editoru |

Všechna rozhraní sdílejí stejnou konfiguraci poskytovatele, registr nástrojů, bezpečnostní pravidla a data relací.

~~~bash
# Desktop GUI
python -m pip install "uag[platform]"

# Web UI
python -m pip install "uag[web]" fastapi uvicorn
~~~

[Interface options](USAGE.md) · [Environment](ENVIRONMENT.md)

## Co můžete vytvořit

Adaptéry poskytovatelů pokrývají hostovaná i lokální běhová prostředí včetně:

**OpenAI · Meta Model API · Anthropic · Google Gemini · Vertex AI · Azure OpenAI · Amazon Bedrock · OpenRouter · Ollama · llama.cpp · Grok · DeepSeek · NVIDIA · Hugging Face · Alibaba Cloud · Moonshot · Xiaomi MiMo · LM Studio · MiniMax · Sakana AI · SAKURA AI Engine · Together AI · Vercel AI Gateway · PFN/PLaMo · Z.AI · Novita**

Poskytovatele přepnete pomocí `UAGENT_PROVIDER`; vaše nástroje ani rozhraní se nezmění.

**Práce s vaším prostředím**

- Číst, vytvářet, upravovat, vyhledávat, vytvářet hashe, archivovat a kontrolovat soubory
- Kontrolovat změny v Gitu, hledat tajné údaje, spouštět testy, provádět linting a kompilaci a měřit pokrytí
- Procházet rozsáhlé kódové základny v Pythonu, TypeScriptu, JavaScriptu, Go, Rustu, C/C++, Javě, C#, COBOLu, VBA a dalších jazycích
- Automatizovat prohlížeče pomocí Playwright včetně vícestránkových pracovních postupů a stahování

**Připojení služeb a zařízení**

- **MCP** — připojení externích serverů nástrojů včetně služeb s podporou OAuth
- **A2A** — koordinace s dalšími agenty a kompatibilními servery
- **Cloud** — přístup k API AWS, Google Cloud a Azure s potvrzením zápisů
- **Komunikace** — Gmail, Bluesky, Discord, Microsoft Teams a pybitchat
- **IoT** — SwitchBot, ECHONET Lite, Matter, BACnet, Modbus TCP, OPC UA a UPnP
- **Média** — generování a úprava obrázků, přepis a syntéza zvuku, snímání kamerou a QR kódy
- **Dokumenty** — analýza PDF, PowerPointu, Wordu, Excelu, CSV, JSON, YAML, SQL a logů

**IoT a ovládání fyzického světa**

- **SwitchBot** — cloudové a BLE vyhledávání, stav, ovládání, dávkování a odběry
- **ECHONET Lite** — vyhledávání a ovládání japonských domácích spotřebičů včetně oznámení INF
- **Matter** — koncové body, clustery, atributy, historie stavu, odběry a ovládání
- **BACnet / Modbus TCP / OPC UA** — čtení, zápisy, procházení a monitorování průmyslové automatizace a automatizace budov
- **UPnP** — vyhledávání zařízení, stav WAN a správa mapování portů routeru

### Kam uag zapadá

uag stojí mezi lidmi a rozhraními na jedné straně a modely, nástroji a systémy reálného světa na straně druhé.
Koordinuje konverzaci, vybírá schopnosti, uplatňuje bezpečnostní pravidla a udržuje pracovní postup obnovitelný.

~~~mermaid
flowchart LR
    UI["CLI · Desktop · Web · VS Code · A2A"] --> UAG["UAG agent runtime"]
    UAG --> MODELS["Hosted & local models"]
    UAG --> TOOLS["Tools & extensions"]
    UAG --> STATE["Sessions & context"]
    TOOLS --> SYSTEMS["Files · Code · Web · MCP · Cloud · IoT"]
    POLICY["Confirmation · Credentials · Policy"] -.-> UAG
~~~

### Pluginy, Agent Skills a tržiště

Proměňte uag ve specializovaného agenta bez forkování jádra:

- Instalujte **pluginy kompatibilní s Claude Code** z adresáře, ZIP archivu, repozitáře Git, zdroje HTTP nebo tržiště
- Sdružujte skills, podagenty, MCP servery, hooky, příkazy se zpětným lomítkem, styly výstupu, závislosti a kanály
- Procházejte komunitní schopnosti ze služeb [SkillsMP](https://skillsmp.com) a [ClawHub](https://clawhub.ai)
- Přidávejte soukromé organizační skills a nástroje lokálně prostřednictvím `UAGENT_EXTERNAL_TOOLS_DIR`

```text
:skills mp_search browser automation
:plugin list
:plugin install <source>
:plugin marketplace list
```

Viz [Průvodce vývojem pluginů](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP_PLUGIN.md).

- **200+ nástrojů** pro soubory, web, média, dokumenty, kód, cloud, komunikaci a IoT
- **Dynamické zjišťování a načítání** — pomocí `tool_catalog` vyhledáte schopnosti a pomocí `tool_load` je povolíte pouze v případě potřeby
- **Inteligence pro práci s kódem** — `code_map`, jazykově specifické navigátory `idx`, kontrola Gitu, spouštění testů, linting, kompilace a pokrytí
- **Pluginy kompatibilní s Claude Code** se skills, agenty, MCP servery, hooky, příkazy a tržišti
- **Agent Skills** ze SkillsMP a ClawHub
- **Vlastní nástroje v Pythonu** s `TOOL_SPEC` a `run_tool()`
- **Nástroje využívající Rust** pro lehká nativní rozšíření

[Tool Creator Guide](../TOOL_CREATOR_GUIDE.md) · [MCP OAuth / Proxy Guide](MCP_OAUTH_PROXY_GUIDE.md)

## Vytvořeno pro reálné pracovní postupy

### 🧠 Výsledky nástrojů s ohledem na kontext

Rozsáhlé výsledky nástrojů se pokud možno neukládají do kontextu aktivního modelu. uag je ukládá jako artefakty a modelu místo toho předává ohraničený náhled se stabilním odkazem na Artifact. To může podstatně snížit počet vstupních tokenů potřebných pro následující tahy, když nástroj vygeneruje rozsáhlý výsledek.

Předchozí konverzace obnovíte pomocí `:load <index>`. Výsledky nástrojů lze ukládat do mezipaměti a poskytovatele lze měnit
bez opětovného sestavení aplikace.

[Context compression](CONTEXT_COMPRESSION.cs.md) · [Memory](MEMORY.md) · [Session portability](SESSION_PORTABILITY.md)

### Autopilot

Pro vícekolovou práci s volitelným kontrolním modelem použijte `:auto`. Limit kol nastavte pomocí `--max-rounds N`.
Stisknutím **F12** autopilota zastavíte, stisknutím **F12** zastavíte aktuální odpověď.

Nezávislé operace pouze pro čtení běží při bezpečném provádění souběžně. Webová vyhledávání, kontrola souborů,
analýza repozitáře a podobná zatížení mohou být dokončena paralelně pomocí konfigurovatelného fondu pracovníků
(`UAGENT_PARALLEL_WORKERS`). Operace zápisu zůstávají serializované nebo vyžadují potvrzení.

Kontinuita relací, ukládání výsledků nástrojů do mezipaměti, stav dávek, obnova po restartu, plánování DAG a
koordinace více agentů umožňují obnovit složitou práci namísto jednorázového provedení.

[Auto-pilot](README_AUTO.md) · [Timers](SET_TIMER.md) · [Multi-agent runtime](MULTI_AGENT_RUNTIME.md)

### 🌍 Soukromé, vícejazyčné a respektující zásady

`human_ask` pozastaví běh před citlivými akcemi. Mazání souborů, přepisování, příkazy shellu, ovládání zařízení,
operace s přihlašovacími údaji a síťové zápisy mohou podléhat pravidlům potvrzení a zásadám.

Používejte úložiště přihlašovacích údajů namísto vkládání dlouhodobých tajemství do promptů:

Webové uživatelské rozhraní zahrnuje přihlášení pomocí OIDC s Authorization Code + PKCE, ověřené ID tokeny, serverové relace a přístupová oprávnění k projektům/místnostem. Ověřené skupinové nároky Microsoft Entra ID mohou při konfiguraci sloužit jako základ pro přístupovou politiku založenou na adresáři. Nasazení Windows Active Directory, OAuth a trusted-proxy lze integrovat pomocí explicitně ověřených adaptérů identity; Windows AD vyžaduje nasazení specifický ověřovač Kerberos/Negotiate a není ve výchozím nastavení povolen.

uag zahrnuje volitelné, na poskytovateli nezávislé trasování OpenTelemetry a metriky pro operace Agent, LLM, nástrojů, Context, Memory a vyhledávání. Pozorovatelnost je ve výchozím nastavení zakázána.

Přístup local-first neznamená, že UAG ve výchozím nastavení funguje zcela offline nebo že jsou všechny nástroje izolované. Volání externích modelů a připojených služeb závisí na konfiguraci.

- [Enterprise policies](ENTERPRISE_POLICY.md)
- [MXC sandbox](SANDBOX_MXC.md)
- [Remote Web / A2A](REMOTE_MXC_DEFAULT.md)
- [Web identity](WEB_IDENTITY_MEMORY.md)
- [OpenTelemetry](UAG_OPENTELEMETRY_DESIGN.md)

### 🌍 Vícejazyčný překlad

- `translate_text` podporuje Google Translate a oficiálního klienta DeepL pro Python prostřednictvím `provider=auto`, `provider=deepl` nebo `provider=google`.
- Definice nástrojů jsou k dispozici v 37 jazykových verzích plus angličtině (celkem 38), přičemž jsou zachovány zástupné symboly a technické identifikátory.

Obousměrný hlas je dostupný prostřednictvím OpenAI Realtime, Azure OpenAI, xAI Grok Voice, Gemini Live
a Bedrock Nova Sonic, s volitelným potlačením ozvěny AEC3 a voláním funkcí v reálném čase omezeným bezpečnostními pravidly.

[Translations](README.translations.md) · [IoT](IOT_USECASE.md) · [Communication](COMMUNICATION.md)

## Dokumentace

| Téma | Dokumentace |
|---|---|
| Proměnné prostředí | [docs/ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/docs/ENVIRONMENT.md) |
| Architektura a invarianty | [docs/ARCHITECTURE.md](https://github.com/awaku7/agentcli/blob/main/docs/ARCHITECTURE.md) |
| Computer Use | [docs/COMPUTER_USE_IMPLEMENTATION.md](https://github.com/awaku7/agentcli/blob/main/docs/COMPUTER_USE_IMPLEMENTATION.md) |
| Nástroje repozitáře | [docs/REPOSITORY_TOOLS.md](https://github.com/awaku7/agentcli/blob/main/docs/REPOSITORY_TOOLS.md) |
| Případy použití IoT | [docs/IOT_USECASE.md](https://github.com/awaku7/agentcli/blob/main/docs/IOT_USECASE.md) |
| Komunikační nástroje | [docs/COMMUNICATION.md](https://github.com/awaku7/agentcli/blob/main/docs/COMMUNICATION.md) |
| Autopilot | [docs/README_AUTO.md](https://github.com/awaku7/agentcli/blob/main/docs/README_AUTO.md) |
| MCP OAuth / Proxy | [docs/MCP_OAUTH_PROXY_GUIDE.md](https://github.com/awaku7/agentcli/blob/main/docs/MCP_OAUTH_PROXY_GUIDE.md) |
| Rozšíření VS Code | [docs/VSCODE.md](https://github.com/awaku7/agentcli/blob/main/docs/VSCODE.md) |
| Příručka pro vývojáře | [src/uagent/docs/DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md) |
| Tok nástroje | [src/uagent/docs/TOOL_FLOW.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/TOOL_FLOW.md) |

[Quickstart](QUICKSTART.md) · [Architecture](ARCHITECTURE.md) · [Context management](UAG_CONTEXT_MANAGEMENT_DESIGN.md)

## Vývoj a přispívání

```bash
git clone https://github.com/awaku7/agentcli.git
cd agentcli
python -m pip install -e ".[core,providers,test]"
```

Spusťte kontroly před PR:

```bash
python -m ruff check src tests
python -m black --check src tests
python -m pytest -q .
```

Úplný vývojový postup najdete v [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md).

Vítány jsou hlášení chyb, nápady na funkce, vylepšení dokumentace, překlady, nástroje, skills a pull requesty.
Před rozsáhlými změnami prosím otevřete issue nebo diskusi. Přečtěte si [Příručku pro vývojáře](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)
a před odesláním pull requestu spusťte výše uvedené kontroly.

## Licence

Licencováno pod [Apache License 2.0](https://github.com/awaku7/agentcli/blob/main/LICENSE).
