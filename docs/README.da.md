<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="UAG — Universal AI Gateway" width="620">
</p>
<h1 align="center">UAG</h1>
<p align="center"><strong>Universal AI Gateway</strong><br>Dine AI-modeller. Dine værktøjer. Dit miljø.</p>

<p align="center">
  <a href="https://github.com/awaku7/agentcli/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/awaku7/agentcli/ci.yml?style=flat-square&label=CI" alt="CI"></a>
  <a href="https://pypi.org/project/uag/"><img src="https://img.shields.io/pypi/v/uag?style=flat-square" alt="PyPI"></a>
  <a href="https://pypi.org/project/uag/"><img src="https://img.shields.io/pypi/pyversions/uag?style=flat-square" alt="Python versions"></a>
  <a href="../LICENSE"><img src="https://img.shields.io/github/license/awaku7/agentcli?style=flat-square" alt="License"></a>
  <a href="https://pepy.tech/projects/uag"><img src="https://static.pepy.tech/personalized-badge/uag?period=total&units=INTERNATIONAL_SYSTEM&left_color=grey&right_color=green&left_text=downloads" alt="Downloads"></a>
</p>
<p align="center"><a href="../README.md">English</a> · <a href="README.translations.md">Andre sprog</a></p>

---

**UAG er en open source-runtime til AI-agenter med lokal kørsel som udgangspunkt.** Den forbinder din foretrukne sprogmodel med de værktøjer og systemer, du bruger. Arbejd med kode, filer, browsere, tjenester og enheder gennem én ensartet grænseflade uden at binde dine arbejdsgange til én modelleverandør.

| **Vælg din model** | **Forbind værktøjer** | **Bevar kontrollen** |
| :--- | :--- | :--- |
| Hostede og lokale modeller som OpenAI, Claude, Gemini, Grok, Bedrock og Ollama | Filer, kode, web, MCP, Agent Skills, plugins, cloudtjenester og IoT | Lokal kørsel, menneskelig godkendelse, opbevaring af legitimationsoplysninger og konfigurerbare politikker |

> UAG er **et eksekveringslag for agenter, ikke en modelleverandør**. Kald til eksterne modeller og tilknyttede tjenester afhænger af din opsætning. Local-first betyder hverken fuld offlinefunktion eller isolering af alle værktøjer som standard.

## Hurtig start
<!-- README-SYNC:quick-start -->

**Python 3.11 eller nyere** er påkrævet. Installer fra [PyPI](https://pypi.org/project/uag/) og start den interaktive kommandolinje:

~~~bash
python -m pip install --upgrade uag
uag
~~~

Ved første start hjælper opsætningsguiden med at vælge leverandør og indstille legitimationsoplysninger. Miljøvariabler og sikker opbevaring kan også bruges. Installer på forhånd flere afhængigheder til leverandører og værktøjer med:

~~~bash
python -m pip install "uag[core,providers,tools]"
~~~

Prøv derefter at spørge:

~~~text
> Hvad er ændret i dette Git-repository? Opsummér risiciene.
> Find den nyeste dokumentation for biblioteket, og forklar migreringen.
> Gennemgå filerne, og skriv en kort rapport.
> :help
~~~

Er du ny bruger, så se Windows-installationsguiden med Git og virtuelle miljøer samt konfigurationsvejledningen: [Quickstart (Windows)](QUICKSTART.md) · [Environment](ENVIRONMENT.md).

## Grænseflader
<!-- README-SYNC:interfaces -->

De forskellige grænseflader deler samme agent-runtime og værktøjsregister.

| Grænseflade | Start | Velegnet til |
| :--- | :--- | :--- |
| **CLI** | `uag` | Terminalarbejde og automatisering |
| **Desktop** | `uagg` | Samtaler i en lokal applikation |
| **Web** | `uagw` | Samtaler og rum i browseren |
| **A2A** | `uaga` | Integration mellem agenter |
| **VS Code** | [Udvidelsesvejledning](VSCODE.md) | Arbejde ved siden af koden |

Desktop og Web kræver ekstra afhængigheder, som ikke indgår i den indledende installation `uag[core,providers,tools]`:

~~~bash
# Desktop GUI (PySide6 and platform integrations)
python -m pip install "uag[platform]"

# Web UI (authentication dependencies, FastAPI, and Uvicorn)
python -m pip install "uag[web]" fastapi uvicorn
~~~

Webserveren kan prøve at installere FastAPI og Uvicorn ved opstart. Forudinstallation gør dig uafhængig af automatisk installation. Læs mere: [CLI usage](USAGE.md) · [Environment](ENVIRONMENT.md).

## Det kan du bygge med UAG
<!-- README-SYNC:capabilities -->

| Funktion | UAG tilbyder |
| :--- | :--- |
| **Modeluafhængige arbejdsgange** | Skift mellem hostede og lokale leverandører med `UAGENT_PROVIDER` uden at omskrive værktøjer |
| **Kode og filer** | Repository-navigation, Git-gennemgang, lint, test, filoperationer og browserautomatisering |
| **Udvidelige værktøjer** | Over 200 værktøjer, dynamisk opdagelse med `tool_catalog` / `tool_load`, egne Python- og Rust-værktøjer |
| **Forbundne agenter** | MCP, A2A, Claude Code-kompatible plugins, Agent Skills og underagenter |
| **Langvarige opgaver** | Autopilot, parallelle uafhængige læsninger, tidsplaner, genopretning og gemte sessioner |
| **Uden for terminalen** | Cloud, kommunikation, dokumenter, medier, tale i realtid og understøttede IoT-protokoller |

### Én runtime, mange integrationer
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

**Eksempler på understøttede leverandører** er vist nedenfor. Leverandørindstillinger findes i miljøvejledningen.

**OpenAI · Anthropic · Gemini · Vertex AI · Azure OpenAI · Amazon Bedrock · Grok · DeepSeek · OpenRouter · Ollama · llama.cpp · LM Studio**

[ENVIRONMENT.md](ENVIRONMENT.md)

### Tilpas med skills og plugins
<!-- README-SYNC:extensions -->

Udvid UAG uden at ændre kernen. Installer Agent Skills fra SkillsMP eller ClawHub, forbind MCP-servere, eller indlæs Claude Code-kompatible plugins med værktøjer, skills, agenter og hooks.

~~~text
:skills mp_search browser automation
:plugin list
:plugin install <source>
:plugin marketplace list
~~~

Egne værktøjer kan stille `TOOL_SPEC` og `run_tool()` til rådighed; Rust-baserede værktøjer understøttes også. Se guiderne: [Tool Creator Guide](../TOOL_CREATOR_GUIDE.md) · [Plugin Development Guide](../src/uagent/docs/DEVELOP_PLUGIN.md) · [MCP OAuth / Proxy](MCP_OAUTH_PROXY_GUIDE.md).

## Bygget til reelle arbejdsgange
<!-- README-SYNC:workflows -->

### Kontekst og hukommelse
<!-- README-SYNC:context-memory -->

Store værktøjsresultater kan gemmes som **artefakter** i stedet for at fylde modellens aktive kontekst. Senere kan agenten hente den relevante del med `artifact_read`. Sessioner gemmes som standard i SQLite med historiksøgning og eksplicit gennemgang af hukommelsen.

- [Context compression](CONTEXT_COMPRESSION.da.md)
- [Memory](MEMORY.md)
- [Session portability](SESSION_PORTABILITY.md)

### Automatisering og samarbejde
<!-- README-SYNC:automation -->

UAG understøtter parallelle uafhængige læsninger, koordinering af flere agenter, gendannelse af sessioner og autopilot til opgaver over flere runder. Start med `:auto`; tryk på **F12** for at afbryde svaret og anmode autopiloten om at stoppe.

- [Auto-pilot](README_AUTO.md)
- [Timers and scheduled tasks](SET_TIMER.md)
- [Multi-agent runtime](MULTI_AGENT_RUNTIME.md)

### Sikkerhed og observerbarhed
<!-- README-SYNC:security -->

Følsomme handlinger kan kræve godkendelse via `human_ask`. Legitimationsoplysninger kan gemmes i operativsystemets nøglelager eller i krypterede filer. Webgrænsefladen understøtter konfigureret OIDC-login og adgangskontrol. OpenTelemetry-sporing og målinger er **valgfri**.

- [Enterprise policies](ENTERPRISE_POLICY.md)
- [MXC sandbox](SANDBOX_MXC.md)
- [Remote Web / A2A MXC defaults](REMOTE_MXC_DEFAULT.md)
- [Web identity and rooms](WEB_IDENTITY_MEMORY.md)
- [OpenTelemetry design](UAG_OPENTELEMETRY_DESIGN.md)
- [Developer observability](../src/uagent/docs/DEVELOP_OBSERVABILITY.md)

Disse kontroller kan konfigureres, men **garanterer ikke** isolering af enhver værktøjskørsel i en sandbox. Læs vejledningerne til udrulning og politikker, før UAG åbnes for ikke-betroede brugere eller netværk.

### Sprog, enheder og tale
<!-- README-SYNC:languages -->

UAG har ressourcer til **38 lokaliteter** (engelsk og 37 oversættelser), valgfri fulddupleks tale og værktøjer til SwitchBot, Matter, ECHONET Lite, BACnet, Modbus TCP og OPC UA.

- [Translations](README.translations.md)
- [IoT use cases](IOT_USECASE.md)
- [Communication tools](COMMUNICATION.md)

## Dokumentation
<!-- README-SYNC:documentation -->

Begynd med disse guider, og gå i dybden efter behov:

| Start her | Læs videre |
| :--- | :--- |
| [Quickstart (Windows)](QUICKSTART.md) | [Architecture](ARCHITECTURE.md) |
| [CLI usage](USAGE.md) | [Context management](UAG_CONTEXT_MANAGEMENT_DESIGN.md) |
| [Environment and providers](ENVIRONMENT.md) | [Enterprise policy](ENTERPRISE_POLICY.md) |
| [Agent Skills and plugins](../src/uagent/docs/DEVELOP_PLUGIN.md) | [Tool flow](../src/uagent/docs/TOOL_FLOW.md) |
| [MCP and OAuth](MCP_OAUTH_PROXY_GUIDE.md) | [Computer Use](COMPUTER_USE_IMPLEMENTATION.md) |
| [VS Code extension](VSCODE.md) | [Developer guide](../src/uagent/docs/DEVELOP.md) |

Se også hele dokumentationsmappen og andre sprog: [Documentation](./) · [Other languages](README.translations.md).

## Udvikling og bidrag
<!-- README-SYNC:contributing -->

~~~bash
git clone https://github.com/awaku7/agentcli.git
cd agentcli
python -m pip install -e ".[core,providers,test]"
~~~

Før pull requests, der ændrer **Python-kode**, skal relevante tests og projektkontroller køres:

~~~bash
python -m ruff check src tests
python -m black --check src tests
python -m pytest -q .
~~~

Læs bidragsreglerne og udviklerguiden. Fejlrapporter, dokumentationsforbedringer, værktøjer, oversættelser og fokuserede pull requests er velkomne: [AGENTS.md](../AGENTS.md) · [Developer guide](../src/uagent/docs/DEVELOP.md).

## Licens
<!-- README-SYNC:license -->

UAG udgives under licensen: [Apache License 2.0](../LICENSE).
