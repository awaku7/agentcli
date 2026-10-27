<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="UAG — Universal AI Gateway" width="620">
</p>
<h1 align="center">UAG</h1>
<p align="center"><strong>Universal AI Gateway</strong><br>Uw AI-modellen. Uw hulpmiddelen. Uw omgeving.</p>

<p align="center">
  <a href="https://github.com/awaku7/agentcli/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/awaku7/agentcli/ci.yml?style=flat-square&label=CI" alt="CI"></a>
  <a href="https://pypi.org/project/uag/"><img src="https://img.shields.io/pypi/v/uag?style=flat-square" alt="PyPI"></a>
  <a href="https://pypi.org/project/uag/"><img src="https://img.shields.io/pypi/pyversions/uag?style=flat-square" alt="Python versions"></a>
  <a href="../LICENSE"><img src="https://img.shields.io/github/license/awaku7/agentcli?style=flat-square" alt="License"></a>
  <a href="https://pepy.tech/projects/uag"><img src="https://static.pepy.tech/personalized-badge/uag?period=total&units=INTERNATIONAL_SYSTEM&left_color=grey&right_color=green&left_text=downloads" alt="Downloads"></a>
</p>
<p align="center"><a href="../README.md">English</a> · <a href="README.translations.md">Andere talen</a></p>

---

**UAG is een open-source runtime voor AI-agenten die lokale uitvoering vooropstelt.** Het verbindt het taalmodel van uw keuze met de hulpmiddelen en systemen die u gebruikt. Werk met code, bestanden, browsers, diensten en apparaten via één consistente interface, zonder afhankelijk te worden van één modelaanbieder.

| **Kies uw model** | **Verbind echte hulpmiddelen** | **Behoud de regie** |
| :--- | :--- | :--- |
| Gehoste en lokale modellen zoals OpenAI, Claude, Gemini, Grok, Bedrock en Ollama | Bestanden, code, web, MCP, Agent Skills, plug-ins, clouddiensten en IoT | Lokale uitvoering, menselijke bevestiging, opslag van aanmeldgegevens en instelbaar beleid |

> UAG is **een uitvoeringslaag voor agenten, geen aanbieder van modellen**. Aanroepen naar externe modellen en gekoppelde diensten zijn afhankelijk van uw configuratie. 'Local-first' betekent niet dat UAG standaard volledig offline of geïsoleerd werkt.

## Snel beginnen
<!-- README-SYNC:quick-start -->

**Python 3.11 of nieuwer** is vereist. Installeer UAG via [PyPI](https://pypi.org/project/uag/) en start de interactieve opdrachtregel:

~~~bash
python -m pip install --upgrade uag
uag
~~~

Bij de eerste start helpt de installatiewizard u een modelaanbieder te kiezen en aanmeldgegevens in te stellen. U kunt ook omgevingsvariabelen of de beveiligde opslag gebruiken. Voor een uitgebreidere set afhankelijkheden van aanbieders en hulpmiddelen:

~~~bash
python -m pip install "uag[core,providers,tools]"
~~~

Probeer daarna bijvoorbeeld het volgende:

~~~text
> Wat is er veranderd in deze Git-repository? Vat de risico's samen.
> Zoek de nieuwste documentatie van deze bibliotheek en leg de migratiestappen uit.
> Onderzoek deze bestanden en maak een beknopt rapport.
> :help
~~~

Bent u nieuw bij UAG? Lees de Windows-installatiehandleiding met uitleg over Git en virtuele omgevingen, en de configuratiehandleiding: [Quickstart (Windows)](QUICKSTART.md) · [Environment](ENVIRONMENT.md).

## Interfaces
<!-- README-SYNC:interfaces -->

Alle ingangen gebruiken dezelfde agentruntime en hetzelfde register met hulpmiddelen.

| Interface | Starten | Geschikt voor |
| :--- | :--- | :--- |
| **CLI** | `uag` | Terminalwerk en automatisering |
| **Desktop** | `uagg` | Gesprekken in een native toepassing |
| **Web** | `uagw` | Gesprekken en ruimtes in de browser |
| **A2A** | `uaga` | Samenwerking tussen agenten |
| **VS Code** | [Extensiehandleiding](VSCODE.md) | Werken naast broncode |

Voor Desktop en Web zijn extra afhankelijkheden vereist die niet in de eerste installatie `uag[core,providers,tools]` zitten:

~~~bash
# Desktop GUI (PySide6 and platform integrations)
python -m pip install "uag[platform]"

# Web UI (authentication dependencies, FastAPI, and Uvicorn)
python -m pip install "uag[web]" fastapi uvicorn
~~~

De webserver kan FastAPI en Uvicorn tijdens het starten proberen te installeren. Door ze vooraf te installeren hoeft u niet op automatische installatie te vertrouwen. Meer informatie: [CLI usage](USAGE.md) · [Environment](ENVIRONMENT.md).

## Wat u met UAG kunt bouwen
<!-- README-SYNC:capabilities -->

| Mogelijkheid | Wat UAG biedt |
| :--- | :--- |
| **Modelonafhankelijke workflows** | Wissel met `UAGENT_PROVIDER` tussen lokale en gehoste modellen zonder hulpmiddelen te herschrijven |
| **Code en bestanden** | Repository-navigatie, Git-controle, linting, tests, bestandsbewerkingen en browserautomatisering |
| **Uitbreidbare hulpmiddelen** | Meer dan 200 tools, dynamisch zoeken met `tool_catalog` / `tool_load`, eigen Python- en Rust-tools |
| **Verbonden agenten** | MCP, A2A, Claude Code-compatibele plug-ins, Agent Skills en subagenten |
| **Langlopende taken** | Autopilot, parallelle onafhankelijke leesbewerkingen, planning, herstel en opgeslagen sessies |
| **Buiten de terminal** | Cloud- en communicatiediensten, documenten, media, realtime spraak en ondersteunde IoT-protocollen |

### Eén runtime, veel integraties
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

**Voorbeelden van ondersteunde modelaanbieders** staan hieronder. Hun specifieke instellingen vindt u in de configuratiehandleiding.

### Aanpassen met skills en plug-ins
<!-- README-SYNC:extensions -->

Breid UAG uit zonder de kern te wijzigen. Installeer Agent Skills via SkillsMP of ClawHub, verbind MCP-servers of laad Claude Code-compatibele plug-ins met tools, skills, agenten en hooks.

~~~text
:skills mp_search browser automation
:plugin list
:plugin install <source>
:plugin marketplace list
~~~

Eigen tools kunnen `TOOL_SPEC` en `run_tool()` aanbieden; ook Rust-gebaseerde tools worden ondersteund. Zie de handleidingen: [Tool Creator Guide](../TOOL_CREATOR_GUIDE.md) · [Plugin Development Guide](../src/uagent/docs/DEVELOP_PLUGIN.md) · [MCP OAuth / Proxy](MCP_OAUTH_PROXY_GUIDE.md).

## Ontworpen voor echte workflows
<!-- README-SYNC:workflows -->

### Context en geheugen
<!-- README-SYNC:context-memory -->

Om de actieve modelcontext niet te overladen kunnen grote toolresultaten als **artefacten** worden opgeslagen. Met `artifact_read` haalt de agent later alleen het relevante deel op. Sessies worden standaard in SQLite bewaard, inclusief het zoeken in de geschiedenis en expliciete geheugencontrole.

- [Context compression](CONTEXT_COMPRESSION.nl.md)
- [Memory](MEMORY.md)
- [Session portability](SESSION_PORTABILITY.md)

### Automatisering en samenwerking
<!-- README-SYNC:automation -->

UAG ondersteunt parallelle onafhankelijke leesbewerkingen, samenwerking tussen meerdere agenten, herstel van sessies en autopilot voor taken in meerdere rondes. Start deze met `:auto`; druk op **F12** om het huidige antwoord te onderbreken en te vragen de autopilot te stoppen.

- [Auto-pilot](README_AUTO.md)
- [Timers and scheduled tasks](SET_TIMER.md)
- [Multi-agent runtime](MULTI_AGENT_RUNTIME.md)

### Beveiliging en waarneembaarheid
<!-- README-SYNC:security -->

Gevoelige acties kunnen met `human_ask` om toestemming vragen. Aanmeldgegevens kunnen in de beveiligde opslag van het besturingssysteem of in versleutelde bestanden worden bewaard. De webinterface ondersteunt na configuratie OIDC-aanmelding en toegangsbeheer. OpenTelemetry-traces en -statistieken zijn **optioneel**.

- [Enterprise policies](ENTERPRISE_POLICY.md)
- [MXC sandbox](SANDBOX_MXC.md)
- [Remote Web / A2A MXC defaults](REMOTE_MXC_DEFAULT.md)
- [Web identity and rooms](WEB_IDENTITY_MEMORY.md)
- [OpenTelemetry design](UAG_OPENTELEMETRY_DESIGN.md)
- [Developer observability](../src/uagent/docs/DEVELOP_OBSERVABILITY.md)

Deze beveiligingsmaatregelen zijn instelbaar en **garanderen niet** dat willekeurige tooluitvoering in een sandbox wordt geïsoleerd. Lees de inzet- en beleidsrichtlijnen voordat u UAG toegankelijk maakt voor niet-vertrouwde gebruikers of netwerken.

### Talen, apparaten en spraak
<!-- README-SYNC:languages -->

UAG bevat middelen voor **38 taalvarianten** (Engels en 37 vertalingen), optionele full-duplex spraakintegraties en tools voor SwitchBot, Matter, ECHONET Lite, BACnet, Modbus TCP en OPC UA.

- [Translations](README.translations.md)
- [IoT use cases](IOT_USECASE.md)
- [Communication tools](COMMUNICATION.md)

## Documentatie
<!-- README-SYNC:documentation -->

Gebruik deze handleidingen als startpunt of voor meer verdieping:

| Begin hier | Meer informatie |
| :--- | :--- |
| [Quickstart (Windows)](QUICKSTART.md) | [Architecture](ARCHITECTURE.md) |
| [CLI usage](USAGE.md) | [Context management](UAG_CONTEXT_MANAGEMENT_DESIGN.md) |
| [Environment and providers](ENVIRONMENT.md) | [Enterprise policy](ENTERPRISE_POLICY.md) |
| [Agent Skills and plugins](../src/uagent/docs/DEVELOP_PLUGIN.md) | [Tool flow](../src/uagent/docs/TOOL_FLOW.md) |
| [MCP and OAuth](MCP_OAUTH_PROXY_GUIDE.md) | [Computer Use](COMPUTER_USE_IMPLEMENTATION.md) |
| [VS Code extension](VSCODE.md) | [Developer guide](../src/uagent/docs/DEVELOP.md) |

Blader ook door de volledige documentatiemap en de andere talen: [Documentation](./) · [Other languages](README.translations.md).

## Ontwikkeling en bijdragen
<!-- README-SYNC:contributing -->

~~~bash
git clone https://github.com/awaku7/agentcli.git
cd agentcli
python -m pip install -e ".[core,providers,test]"
~~~

Voer voor een pull request met wijzigingen aan **Python-code** de toepasselijke tests en projectcontroles uit:

~~~bash
python -m ruff check src tests
python -m black --check src tests
python -m pytest -q .
~~~

In de bijdrageregels en ontwikkelaarshandleiding staat meer informatie. Foutmeldingen, documentatieverbeteringen, tools, vertalingen en gerichte pull requests zijn welkom: [AGENTS.md](../AGENTS.md) · [Developer guide](../src/uagent/docs/DEVELOP.md).

## Licentie
<!-- README-SYNC:license -->

UAG wordt verspreid onder de licentie: [Apache License 2.0](../LICENSE).
