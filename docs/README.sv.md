<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="UAG — Universal AI Gateway" width="620">
</p>
<h1 align="center">UAG</h1>
<p align="center"><strong>Universal AI Gateway</strong><br>Dina AI-modeller. Dina verktyg. Din miljö.</p>

<p align="center">
  <a href="https://github.com/awaku7/agentcli/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/awaku7/agentcli/ci.yml?style=flat-square&label=CI" alt="CI"></a>
  <a href="https://pypi.org/project/uag/"><img src="https://img.shields.io/pypi/v/uag?style=flat-square" alt="PyPI"></a>
  <a href="https://pypi.org/project/uag/"><img src="https://img.shields.io/pypi/pyversions/uag?style=flat-square" alt="Python versions"></a>
  <a href="../LICENSE"><img src="https://img.shields.io/github/license/awaku7/agentcli?style=flat-square" alt="License"></a>
  <a href="https://pepy.tech/projects/uag"><img src="https://static.pepy.tech/personalized-badge/uag?period=total&units=INTERNATIONAL_SYSTEM&left_color=grey&right_color=green&left_text=downloads" alt="Downloads"></a>
</p>
<p align="center"><a href="../README.md">English</a> · <a href="README.translations.md">Andra språk</a></p>

---

**UAG är en öppen körmiljö för AI-agenter med lokal körning i första hand.** Den kopplar den språkmodell du väljer till dina verktyg och system. Hantera kod, filer, webbläsare, tjänster och enheter via ett enhetligt gränssnitt utan att binda arbetsflödena till en enda modellleverantör.

| **Välj modell** | **Anslut verkliga verktyg** | **Behåll kontrollen** |
| :--- | :--- | :--- |
| Molnbaserade och lokala modeller som OpenAI, Claude, Gemini, Grok, Bedrock och Ollama | Filer, kod, webb, MCP, Agent Skills, tillägg, molntjänster och IoT | Lokal körning, mänskligt godkännande, lagring av inloggningsuppgifter och konfigurerbara policyer |

> UAG är **ett körlager för agenter, inte en modellleverantör**. Anrop till externa modeller och tjänster styrs av konfigurationen. Local-first innebär varken fullständig offlinedrift eller att alla verktyg är isolerade som standard.

## Kom igång
<!-- README-SYNC:quick-start -->

**Python 3.11 eller senare** krävs. Installera UAG från [PyPI](https://pypi.org/project/uag/) och starta den interaktiva kommandoraden:

~~~bash
python -m pip install --upgrade uag
uag
~~~

Vid första starten hjälper installationsguiden dig att välja leverantör och ange inloggningsuppgifter. Du kan också använda miljövariabler eller säker lagring. För att installera fler beroenden för leverantörer och verktyg i förväg:

~~~bash
python -m pip install "uag[core,providers,tools]"
~~~

Prova sedan dessa frågor:

~~~text
> Vad har ändrats i det här Git-repot? Sammanfatta riskerna.
> Hitta den senaste dokumentationen för biblioteket och förklara hur man migrerar.
> Granska de här filerna och skriv en kort rapport.
> :help
~~~

För nya användare finns en Windows-guide som även beskriver Git och virtuella miljöer, samt en konfigurationsreferens: [Quickstart (Windows)](QUICKSTART.md) · [Environment](ENVIRONMENT.md).

## Gränssnitt
<!-- README-SYNC:interfaces -->

Samma agentkörmiljö och verktygsregister används från flera ingångar.

| Gränssnitt | Start | Passar för |
| :--- | :--- | :--- |
| **CLI** | `uag` | Terminalarbete och automatisering |
| **Desktop** | `uagg` | Samtal i ett inbyggt skrivbordsprogram |
| **Web** | `uagw` | Samtal och rum i webbläsaren |
| **A2A** | `uaga` | Integration mellan agenter |
| **VS Code** | [Guide för tillägg](VSCODE.md) | Arbete intill koden |

Desktop och Web behöver extra beroenden som inte ingår i snabbstartens `uag[core,providers,tools]`:

~~~bash
# Desktop GUI (PySide6 and platform integrations)
python -m pip install "uag[platform]"

# Web UI (authentication dependencies, FastAPI, and Uvicorn)
python -m pip install "uag[web]" fastapi uvicorn
~~~

Webbservern kan försöka installera FastAPI och Uvicorn vid start. Genom att installera dem i förväg slipper du förlita dig på automatisk installation. Läs mer: [CLI usage](USAGE.md) · [Environment](ENVIRONMENT.md).

## Vad du kan göra med UAG
<!-- README-SYNC:capabilities -->

| Funktion | Vad UAG erbjuder |
| :--- | :--- |
| **Modelloberoende arbetsflöden** | Byt mellan moln- och lokala leverantörer med `UAGENT_PROVIDER` utan att skriva om verktyg |
| **Kod och filer** | Navigera i kodarkiv, granska Git, lintning, tester, filoperationer och webbläsarautomatisering |
| **Utbyggbara verktyg** | Över 200 verktyg, dynamisk upptäckt med `tool_catalog` / `tool_load`, egna Python- och Rust-verktyg |
| **Sammankopplade agenter** | MCP, A2A, Claude Code-kompatibla tillägg, Agent Skills och underagenter |
| **Långvariga uppgifter** | Autopilot, parallella oberoende läsningar, schemalagda uppgifter, återhämtning och sparade sessioner |
| **Mer än terminalen** | Moln- och kommunikationstjänster, dokument, media, röst i realtid och stödda IoT-protokoll |

### En körmiljö, många integrationer
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

**Exempel på leverantörer som stöds** finns nedan; inställningar för respektive leverantör beskrivs i miljöguiden.

**OpenAI · Anthropic · Gemini · Vertex AI · Azure OpenAI · Amazon Bedrock · Grok · DeepSeek · OpenRouter · Ollama · llama.cpp · LM Studio**

[ENVIRONMENT.md](ENVIRONMENT.md)

### Anpassa med skills och tillägg
<!-- README-SYNC:extensions -->

Utöka UAG utan att ändra kärnan. Installera Agent Skills från SkillsMP eller ClawHub, anslut MCP-servrar eller läs in Claude Code-kompatibla tillägg med verktyg, skills, agenter och hooks.

~~~text
:skills mp_search browser automation
:plugin list
:plugin install <source>
:plugin marketplace list
~~~

Egna verktyg kan tillhandahålla `TOOL_SPEC` och `run_tool()`; även Rust-baserade verktyg stöds. Se guiderna: [Tool Creator Guide](../TOOL_CREATOR_GUIDE.md) · [Plugin Development Guide](../src/uagent/docs/DEVELOP_PLUGIN.md) · [MCP OAuth / Proxy](MCP_OAUTH_PROXY_GUIDE.md).

## Byggt för verkliga arbetsflöden
<!-- README-SYNC:workflows -->

### Kontext och minne
<!-- README-SYNC:context-memory -->

Stora verktygsresultat kan sparas som **artefakter** i stället för att ta upp utrymme i modellens aktiva kontext. Agenten kan senare hämta relevanta delar via `artifact_read`. Sessioner lagras som standard i SQLite, med historiksökning och uttrycklig granskning av minnesuppgifter.

- [Context compression](CONTEXT_COMPRESSION.sv.md)
- [Memory](MEMORY.md)
- [Session portability](SESSION_PORTABILITY.md)

### Automatisering och samarbete
<!-- README-SYNC:automation -->

UAG stöder parallella oberoende läsoperationer, samordning av flera agenter, återställning av sessioner och autopilot för uppgifter i flera omgångar. Starta med `:auto`; tryck på **F12** för att avbryta svaret och begära att autopiloten stoppas.

- [Auto-pilot](README_AUTO.md)
- [Timers and scheduled tasks](SET_TIMER.md)
- [Multi-agent runtime](MULTI_AGENT_RUNTIME.md)

### Säkerhet och observerbarhet
<!-- README-SYNC:security -->

Känsliga åtgärder kan kräva bekräftelse via `human_ask`. Inloggningsuppgifter kan lagras i operativsystemets lösenordshanterare eller krypterade filer. Webbgränssnittet stöder konfigurerad OIDC-inloggning och åtkomstkontroll. OpenTelemetry-spårning och mätvärden är **valfria**.

- [Enterprise policies](ENTERPRISE_POLICY.md)
- [MXC sandbox](SANDBOX_MXC.md)
- [Remote Web / A2A MXC defaults](REMOTE_MXC_DEFAULT.md)
- [Web identity and rooms](WEB_IDENTITY_MEMORY.md)
- [OpenTelemetry design](UAG_OPENTELEMETRY_DESIGN.md)
- [Developer observability](../src/uagent/docs/DEVELOP_OBSERVABILITY.md)

Kontrollerna går att konfigurera men **garanterar inte** att godtycklig verktygskörning isoleras i en sandbox. Läs guiderna om driftsättning och policyer innan UAG exponeras för opålitliga användare eller nätverk.

### Språk, enheter och röst
<!-- README-SYNC:languages -->

UAG innehåller resurser för **38 språkvarianter** (engelska och 37 översättningar), valfria full-duplex-röstintegrationer och verktyg för SwitchBot, Matter, ECHONET Lite, BACnet, Modbus TCP och OPC UA.

- [Translations](README.translations.md)
- [IoT use cases](IOT_USECASE.md)
- [Communication tools](COMMUNICATION.md)

## Dokumentation
<!-- README-SYNC:documentation -->

Börja med följande guider och läs vidare inom valda områden:

| Börja här | Fördjupning |
| :--- | :--- |
| [Quickstart (Windows)](QUICKSTART.md) | [Architecture](ARCHITECTURE.md) |
| [CLI usage](USAGE.md) | [Context management](UAG_CONTEXT_MANAGEMENT_DESIGN.md) |
| [Environment and providers](ENVIRONMENT.md) | [Enterprise policy](ENTERPRISE_POLICY.md) |
| [Agent Skills and plugins](../src/uagent/docs/DEVELOP_PLUGIN.md) | [Tool flow](../src/uagent/docs/TOOL_FLOW.md) |
| [MCP and OAuth](MCP_OAUTH_PROXY_GUIDE.md) | [Computer Use](COMPUTER_USE_IMPLEMENTATION.md) |
| [VS Code extension](VSCODE.md) | [Developer guide](../src/uagent/docs/DEVELOP.md) |

Du kan också bläddra i hela dokumentationen och övriga översättningar: [Documentation](./) · [Other languages](README.translations.md).

## Utveckling och bidrag
<!-- README-SYNC:contributing -->

~~~bash
git clone https://github.com/awaku7/agentcli.git
cd agentcli
python -m pip install -e ".[core,providers,test]"
~~~

Innan en pull request som ändrar **Python-kod**, kör relevanta tester och projektkontroller:

~~~bash
python -m ruff check src tests
python -m black --check src tests
python -m pytest -q .
~~~

Läs bidragsreglerna och utvecklarguiden. Felrapporter, dokumentationsförbättringar, verktyg, översättningar och fokuserade pull requests är välkomna: [AGENTS.md](../AGENTS.md) · [Developer guide](../src/uagent/docs/DEVELOP.md).

## Licens
<!-- README-SYNC:license -->

UAG distribueras under licensen: [Apache License 2.0](../LICENSE).
