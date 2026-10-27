<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="UAG — Universal AI Gateway" width="620">
</p>
<h1 align="center">UAG</h1>
<p align="center"><strong>Universal AI Gateway</strong><br>Vaše modely AI. Vaše nástroje. Vaše prostředí.</p>

<p align="center">
  <a href="https://github.com/awaku7/agentcli/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/awaku7/agentcli/ci.yml?style=flat-square&label=CI" alt="CI"></a>
  <a href="https://pypi.org/project/uag/"><img src="https://img.shields.io/pypi/v/uag?style=flat-square" alt="PyPI"></a>
  <a href="https://pypi.org/project/uag/"><img src="https://img.shields.io/pypi/pyversions/uag?style=flat-square" alt="Python versions"></a>
  <a href="../LICENSE"><img src="https://img.shields.io/github/license/awaku7/agentcli?style=flat-square" alt="License"></a>
  <a href="https://pepy.tech/projects/uag"><img src="https://static.pepy.tech/personalized-badge/uag?period=total&units=INTERNATIONAL_SYSTEM&left_color=grey&right_color=green&left_text=downloads" alt="Downloads"></a>
</p>
<p align="center"><a href="../README.md">English</a> · <a href="README.translations.md">Další jazyky</a></p>

---

**UAG je otevřené prostředí pro běh agentů AI s důrazem na místní zpracování.** Propojuje zvolený jazykový model s nástroji a systémy, které skutečně používáte. S kódem, soubory, prohlížeči, službami a zařízeními pracujete z jednotného rozhraní, bez závislosti na jediném poskytovateli modelů.

| **Vlastní volba modelu** | **Připojení skutečných nástrojů** | **Kontrola ve vašich rukou** |
| :--- | :--- | :--- |
| Hostované i místní modely: OpenAI, Claude, Gemini, Grok, Bedrock, Ollama | Soubory, kód, web, MCP, Agent Skills, pluginy, cloud a IoT | Místní běh, lidské potvrzení, úložiště přihlašovacích údajů a nastavitelné zásady |

> UAG je **vrstva pro běh agentů, nikoli poskytovatel modelů**. Volání externích modelů a služeb závisí na nastavení. Přednost místního běhu neznamená úplný provoz offline ani automatickou izolaci všech nástrojů.

## Rychlý začátek
<!-- README-SYNC:quick-start -->

Vyžaduje se **Python 3.11 nebo novější**. Nainstalujte UAG z [PyPI](https://pypi.org/project/uag/) a spusťte interaktivní CLI:

~~~bash
python -m pip install --upgrade uag
uag
~~~

Při prvním spuštění průvodce pomůže vybrat poskytovatele a nastavit přihlašovací údaje. Lze použít i proměnné prostředí nebo bezpečné úložiště. Pro předběžnou instalaci dalších závislostí poskytovatelů a nástrojů:

~~~bash
python -m pip install "uag[core,providers,tools]"
~~~

Poté vyzkoušejte například tyto požadavky:

~~~text
> Co se změnilo v tomto repozitáři Git? Shrň rizika.
> Najdi aktuální dokumentaci této knihovny a vysvětli postup migrace.
> Prozkoumej tyto soubory a připrav stručnou zprávu.
> :help
~~~

Začátečníkům doporučujeme instalační návod pro Windows včetně Gitu a virtuálních prostředí a příručku konfigurace: [Quickstart (Windows)](QUICKSTART.md) · [Environment](ENVIRONMENT.md).

## Rozhraní
<!-- README-SYNC:interfaces -->

Všechna rozhraní používají stejné jádro agenta i registr nástrojů.

| Rozhraní | Spuštění | Využití |
| :--- | :--- | :--- |
| **CLI** | `uag` | Terminál a automatizace |
| **Desktop** | `uagg` | Nativní desktopové konverzace |
| **Web** | `uagw` | Konverzace a místnosti v prohlížeči |
| **A2A** | `uaga` | Propojení agentů |
| **VS Code** | [Průvodce rozšířením](VSCODE.md) | Práce vedle zdrojového kódu |

Desktop a Web vyžadují další závislosti, které základní instalace `uag[core,providers,tools]` neobsahuje:

~~~bash
# Desktop GUI (PySide6 and platform integrations)
python -m pip install "uag[platform]"

# Web UI (authentication dependencies, FastAPI, and Uvicorn)
python -m pip install "uag[web]" fastapi uvicorn
~~~

Webový server může při startu zkusit nainstalovat FastAPI a Uvicorn. Instalace předem tuto závislost na automatickém postupu odstraní. Podrobnosti: [CLI usage](USAGE.md) · [Environment](ENVIRONMENT.md).

## Co lze s UAG vytvořit
<!-- README-SYNC:capabilities -->

| Možnost | Co UAG nabízí |
| :--- | :--- |
| **Nezávislost na modelu** | Přepínání hostovaných i místních poskytovatelů přes `UAGENT_PROVIDER` bez přepisování nástrojů |
| **Kód a soubory** | Procházení repozitářů, kontrola Gitu, lint, testy, práce se soubory a automatizace prohlížeče |
| **Rozšiřitelné nástroje** | Více než 200 nástrojů, vyhledávání přes `tool_catalog` / `tool_load`, vlastní Python a Rust nástroje |
| **Propojení agenti** | MCP, A2A, pluginy kompatibilní s Claude Code, Agent Skills a podagenti |
| **Dlouhé úlohy** | Autopilot, paralelní nezávislé čtení, plánované úlohy, obnovení a trvalé relace |
| **Více než terminál** | Cloud, komunikace, dokumenty, média, hlas v reálném čase a podporované IoT protokoly |

### Jedno prostředí, mnoho integrací
<!-- README-SYNC:integrations -->

~~~mermaid
flowchart LR
    UI["CLI · Desktop · Web · VS Code · A2A"] --> UAG["UAG agent runtime"]
    UAG --> MODELS["Hosted & local models"]
    UAG --> TOOLS["Tools & extensions"]
    UAG --> STATE["Sessions & context"]
    TOOLS --> SYSTEMS["Files · Code · Web · MCP · Cloud · IoT"]
    POLICY["Confirmation · Credentials · Policy"] -.-> UAG
~~~

**Příklady podporovaných poskytovatelů** jsou níže. Konkrétní nastavení najdete v příručce prostředí.

### Přizpůsobení pomocí dovedností a pluginů
<!-- README-SYNC:extensions -->

UAG lze rozšířit bez úprav jádra: Agent Skills ze SkillsMP nebo ClawHub, servery MCP a pluginy kompatibilní s Claude Code obsahující nástroje, dovednosti, agenty a hooky.

~~~text
:skills mp_search browser automation
:plugin list
:plugin install <source>
:plugin marketplace list
~~~

Vlastní nástroje mohou vystavit `TOOL_SPEC` a `run_tool()`; podporovány jsou i nástroje založené na Rustu. Viz příručky: [Tool Creator Guide](../TOOL_CREATOR_GUIDE.md) · [Plugin Development Guide](../src/uagent/docs/DEVELOP_PLUGIN.md) · [MCP OAuth / Proxy](MCP_OAUTH_PROXY_GUIDE.md).

## Pro skutečné pracovní postupy
<!-- README-SYNC:workflows -->

### Kontext a paměť
<!-- README-SYNC:context-memory -->

Velké výsledky nástrojů lze uložit jako **artefakty**, aby nezahltily aktivní kontext modelu. Později agent vyhledá příslušnou část pomocí `artifact_read`. Relace se standardně ukládají do SQLite, včetně vyhledávání historie a výslovné kontroly paměti.

- [Context compression](CONTEXT_COMPRESSION.cs.md)
- [Memory](MEMORY.md)
- [Session portability](SESSION_PORTABILITY.md)

### Automatizace a spolupráce
<!-- README-SYNC:automation -->

UAG umožňuje paralelní nezávislé operace čtení, koordinaci více agentů, obnovení relací a autopilota pro vícekrokovou práci. Spusťte ho pomocí `:auto`; klávesa **F12** přeruší aktuální odpověď a vyžádá zastavení autopilota.

- [Auto-pilot](README_AUTO.md)
- [Timers and scheduled tasks](SET_TIMER.md)
- [Multi-agent runtime](MULTI_AGENT_RUNTIME.md)

### Zabezpečení a sledovatelnost
<!-- README-SYNC:security -->

Citlivé akce mohou vyžadovat potvrzení `human_ask`. Přihlašovací údaje lze uložit do správce systému nebo šifrovaného souboru. Web při konfiguraci podporuje přihlášení OIDC a řízení přístupu. Trasy a metriky OpenTelemetry jsou **volitelné**.

- [Enterprise policies](ENTERPRISE_POLICY.md)
- [MXC sandbox](SANDBOX_MXC.md)
- [Remote Web / A2A MXC defaults](REMOTE_MXC_DEFAULT.md)
- [Web identity and rooms](WEB_IDENTITY_MEMORY.md)
- [OpenTelemetry design](UAG_OPENTELEMETRY_DESIGN.md)
- [Developer observability](../src/uagent/docs/DEVELOP_OBSERVABILITY.md)

Jde o nastavitelné ochrany, **nikoli záruku**, že libovolný nástroj běží izolovaně v sandboxu. Před zpřístupněním nedůvěryhodným uživatelům či sítím prostudujte návody k nasazení a zásadám.

### Jazyky, zařízení a hlas
<!-- README-SYNC:languages -->

UAG obsahuje prostředky pro **38 jazykových lokalizací** (angličtina a 37 překladů), volitelný obousměrný hlas a nástroje pro SwitchBot, Matter, ECHONET Lite, BACnet, Modbus TCP a OPC UA.

- [Translations](README.translations.md)
- [IoT use cases](IOT_USECASE.md)
- [Communication tools](COMMUNICATION.md)

## Dokumentace
<!-- README-SYNC:documentation -->

Začněte s těmito materiály a podle potřeby pokračujte podrobněji:

| Začněte zde | Podrobnosti |
| :--- | :--- |
| [Quickstart (Windows)](QUICKSTART.md) | [Architecture](ARCHITECTURE.md) |
| [CLI usage](USAGE.md) | [Context management](UAG_CONTEXT_MANAGEMENT_DESIGN.md) |
| [Environment and providers](ENVIRONMENT.md) | [Enterprise policy](ENTERPRISE_POLICY.md) |
| [Agent Skills and plugins](../src/uagent/docs/DEVELOP_PLUGIN.md) | [Tool flow](../src/uagent/docs/TOOL_FLOW.md) |
| [MCP and OAuth](MCP_OAUTH_PROXY_GUIDE.md) | [Computer Use](COMPUTER_USE_IMPLEMENTATION.md) |
| [VS Code extension](VSCODE.md) | [Developer guide](../src/uagent/docs/DEVELOP.md) |

Prohlédněte si také další dokumenty a překlady: [Documentation](./) · [Other languages](README.translations.md).

## Vývoj a příspěvky
<!-- README-SYNC:contributing -->

~~~bash
git clone https://github.com/awaku7/agentcli.git
cd agentcli
python -m pip install -e ".[core,providers,test]"
~~~

Před pull requestem měnícím **kód Pythonu** spusťte odpovídající testy a projektové kontroly:

~~~bash
python -m ruff check src tests
python -m black --check src tests
python -m pytest -q .
~~~

Pravidla přispívání i vývojářská příručka jsou níže. Vítáme hlášení chyb, vylepšení dokumentace, nástroje, překlady a cílené pull requesty: [AGENTS.md](../AGENTS.md) · [Developer guide](../src/uagent/docs/DEVELOP.md).

## Licence
<!-- README-SYNC:license -->

UAG se vydává pod licencí: [Apache License 2.0](../LICENSE).
