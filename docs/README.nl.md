<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="680">
</p>

<h1 align="center">uag</h1>

<p align="center">
  <strong>Universal AI Gateway</strong><br>
  Eén lokale agent. Elk model. Elke tool. Jouw omgeving, jouw regels.
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
  <a href="https://github.com/awaku7/agentcli/discussions">Discussions</a> ·
  <a href="https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md">Translations</a>
</p>

______________________________________________________________________

**Waarom uag?**

uag is een local-first AI-agent die het model van jouw voorkeur verbindt met de tools die je daadwerkelijk gebruikt.
Het biedt één uitbreidbare runtime voor bestanden, browsers, codebases, communicatie, cloud-API's,
IoT-apparaten, MCP-servers en workflows met meerdere agents.

- **Vrijheid van provider** — OpenAI, Anthropic, Gemini, Azure, Bedrock, Ollama, llama.cpp, Grok, DeepSeek en meer.
- **Local-first uitvoering** — de runtime van je agent en de uitvoering van tools blijven op jouw machine; alleen de API-aanroepen die je kiest verlaten deze.
- **Eén toollaag** — dezelfde tools werken vanuit de CLI, desktop-GUI, webinterface, VS Code en A2A.
- **Van nature parallel** — onafhankelijke alleen-lezenbewerkingen kunnen gelijktijdig worden uitgevoerd.
- **Uitbreidbaar** — voeg tools, plugins, Agent Skills, MCP-servers en door Rust ondersteunde tools toe zonder de core te wijzigen.
- **Veiligheidsbewust** — destructieve acties, inloggegevens, apparaatbediening en netwerkschrijfacties ondersteunen expliciete bevestiging en beleidscontroles.

> **Kort gezegd:** uag is het besturingsvlak tussen je AI-modellen en je echte omgeving.

> **🧠 Contextbewuste toolresultaten** — Grote toolresultaten worden waar mogelijk buiten de actieve modelcontext gehouden. uag slaat ze op als artefacten en geeft het model in plaats daarvan een begrensd voorbeeld met een stabiele Artifact-referentie. Dit kan het aantal invoertokens dat nodig is voor vervolgbeurten aanzienlijk verminderen wanneer een tool een groot resultaat oplevert.
> [Uitgebreide gids voor contextcompressie](CONTEXT_COMPRESSION.nl.md)

## Snel starten

**Python 3.11+**

```bash
python -m pip install --upgrade uag
uag
```

Bij de eerste start wordt de installatiewizard geopend. Deze helpt bij het configureren van een provider en slaat de geselecteerde instellingen
op in je lokale omgeving.

Voor de meest gebruikte functiegroepen:

```bash
python -m pip install "uag[core,providers,tools]"
```

> Platformintegraties zijn optioneel. Installeer alleen wat je besturingssysteem nodig heeft; zie

```text
> What files changed in this repository?
> Search the web for today's AI news and summarize the top five stories.
> :help
```

[Quickstart](QUICKSTART.md) · [Environment](ENVIRONMENT.md)

## Interfaces

| Interface | Command | Best for |
|---|---|---|
| **CLI** | `uag` | Snel werk waarbij het toetsenbord centraal staat |
| **Desktop GUI** | `uagg` | Een native desktopervaring |
| **Web UI** | `uagw` | Toegang via de browser |
| **A2A server** | `uaga` | Agent-tot-agentcommunicatie |
| **VS Code** | Extension | Tools in de editor uitleggen, herstructureren, repareren en doorzoeken |

Alle interfaces delen dezelfde providerconfiguratie, toolregistry, veiligheidsregels en sessiegegevens.

~~~bash
# Desktop GUI
python -m pip install "uag[platform]"

# Web UI
python -m pip install "uag[web]" fastapi uvicorn
~~~

[Interface options](USAGE.md) · [Environment](ENVIRONMENT.md)

## Wat je kunt bouwen

Provideradapters dekken gehoste en lokale runtimes, waaronder:

**OpenAI · Meta Model API · Anthropic · Google Gemini · Vertex AI · Azure OpenAI · Amazon Bedrock · OpenRouter · Ollama · llama.cpp · Grok · DeepSeek · NVIDIA · Hugging Face · Alibaba Cloud · Moonshot · Xiaomi MiMo · LM Studio · MiniMax · Sakana AI · SAKURA AI Engine · Together AI · Vercel AI Gateway · PFN/PLaMo · Z.AI · Novita**

Wissel van provider met `UAGENT_PROVIDER`; je tools en interface veranderen niet.

**Werken met je omgeving**

- Bestanden lezen, maken, bewerken, doorzoeken, hashen, archiveren en inspecteren
- Git-wijzigingen beoordelen, zoeken naar geheimen, tests uitvoeren, linten, compileren en coverage meten
- Grote codebases in Python, TypeScript, JavaScript, Go, Rust, C/C++, Java, C#, COBOL, VBA en andere talen navigeren
- Browsers automatiseren met Playwright, inclusief workflows met meerdere pagina's en downloads

**Services en apparaten verbinden**

- **MCP** — externe toolservers verbinden, waaronder services met OAuth
- **A2A** — coördineren met andere agents en compatibele servers
- **Cloud** — AWS-, Google Cloud- en Azure-API-toegang met bevestiging voor schrijfbewerkingen
- **Communicatie** — Gmail, Bluesky, Discord, Microsoft Teams en pybitchat
- **IoT** — SwitchBot, ECHONET Lite, Matter, BACnet, Modbus TCP, OPC UA en UPnP
- **Media** — afbeeldingen genereren/bewerken, audio transcriberen/spraak, camerabeelden vastleggen en QR-codes
- **Documenten** — PDF, PowerPoint, Word, Excel, CSV, JSON, YAML, SQL en loganalyse

**IoT en fysieke wereld bedienen**

- **SwitchBot** — ontdekking via Cloud en BLE, status, bediening, batching en subscriptions
- **ECHONET Lite** — Japanse huishoudelijke apparaten ontdekken en bedienen, inclusief INF-meldingen
- **Matter** — endpoints, clusters, attributen, statusgeschiedenis, subscriptions en bediening
- **BACnet / Modbus TCP / OPC UA** — lezen, schrijven, browsen en monitoren voor industriële en gebouwautomatisering
- **UPnP** — apparaten ontdekken, WAN-status en beheer van routerpoortdoorschakeling

### Waar past uag?

uag bevindt zich aan de ene kant tussen mensen en interfaces, en aan de andere kant tussen modellen, tools en systemen uit de echte wereld.
Het coördineert het gesprek, selecteert mogelijkheden, past veiligheidsregels toe en houdt de workflow hervatbaar.

~~~mermaid
flowchart LR
    UI["CLI · Desktop · Web · VS Code · A2A"] --> UAG["UAG agent runtime"]
    UAG --> MODELS["Hosted & local models"]
    UAG --> TOOLS["Tools & extensions"]
    UAG --> STATE["Sessions & context"]
    TOOLS --> SYSTEMS["Files · Code · Web · MCP · Cloud · IoT"]
    POLICY["Confirmation · Credentials · Policy"] -.-> UAG
~~~

### Plugins, Agent Skills en marketplaces

Maak van uag een gespecialiseerde agent zonder de core te forken:

- Installeer **Claude Code-compatibele plugins** vanuit een map, ZIP, Git-repository, HTTP-bron of marketplace
- Bundel skills, subagents, MCP-servers, hooks, slash-commando's, uitvoerstijlen, afhankelijkheden en kanalen
- Bekijk communitymogelijkheden van [SkillsMP](https://skillsmp.com) en [ClawHub](https://clawhub.ai)
- Voeg lokaal privé-organization skills en tools toe via `UAGENT_EXTERNAL_TOOLS_DIR`

```text
:skills mp_search browser automation
:plugin list
:plugin install <source>
:plugin marketplace list
```

Zie de [Plugin Development Guide](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP_PLUGIN.md).

- **200+ tools** voor bestanden, web, media, documenten, code, cloud, communicatie en IoT
- **Dynamische ontdekking en laden** — gebruik `tool_catalog` om mogelijkheden te vinden en `tool_load` om ze alleen in te schakelen wanneer dat nodig is
- **Code-intelligentie** — `code_map`, taalspecifieke `idx`-navigators, Git-review, testuitvoering, linting, compilatie en coverage
- **Claude Code-compatibele plugins** met skills, agents, MCP-servers, hooks, commando's en marketplaces
- **Agent Skills** van SkillsMP en ClawHub
- **Aangepaste Python-tools** met `TOOL_SPEC` en `run_tool()`
- **Door Rust ondersteunde tools** voor lichtgewicht native uitbreidingen

[Tool Creator Guide](../TOOL_CREATOR_GUIDE.md) · [MCP OAuth / Proxy Guide](MCP_OAUTH_PROXY_GUIDE.md)

## Gebouwd voor echte workflows

### 🧠 Contextbewuste toolresultaten

Grote toolresultaten worden waar mogelijk buiten de actieve modelcontext gehouden. uag slaat ze op als artefacten en geeft het model in plaats daarvan een begrensd voorbeeld met een stabiele Artifact-referentie. Dit kan het aantal invoertokens dat nodig is voor vervolgbeurten aanzienlijk verminderen wanneer een tool een groot resultaat oplevert.

Hervat eerdere gesprekken met `:load <index>`. Toolresultaten kunnen worden gecachet en providers kunnen worden gewijzigd
zonder de applicatie opnieuw op te bouwen.

[Context compression](CONTEXT_COMPRESSION.nl.md) · [Memory](MEMORY.md) · [Session portability](SESSION_PORTABILITY.md)

### Autopiloot

Gebruik `:auto` voor werk in meerdere rondes met een optioneel reviewermodel. Stel een rondelimiet in met `--max-rounds N`.
Druk op **F12** om de autopiloot te stoppen of op **F12** om de huidige respons te stoppen.

Onafhankelijke alleen-lezenbewerkingen worden, wanneer dat veilig is, gelijktijdig uitgevoerd. Webzoekopdrachten, bestandsinspectie,
repositoryanalyse en vergelijkbare workloads kunnen parallel worden voltooid met een configureerbare workerpool
(`UAGENT_PARALLEL_WORKERS`). Schrijfbewerkingen blijven geserialiseerd of vereisen bevestiging.

Sessiebehoud, caching van toolresultaten, batchstatus, herstel na herstart, DAG-planning en
orkestratie van meerdere agents maken complex werk hervatbaar in plaats van eenmalig.

[Auto-pilot](README_AUTO.md) · [Timers](SET_TIMER.md) · [Multi-agent runtime](MULTI_AGENT_RUNTIME.md)

### 🌍 Privé, meertalig en beleidsbewust

`human_ask` pauzeert vóór gevoelige acties. Bestandsverwijderingen, overschrijvingen, shellcommando's, apparaatbediening,
credentialbewerkingen en netwerkschrijfbewerkingen kunnen worden beheerd met bevestigings- en beleidsregels.

Gebruik de credential store in plaats van langdurig geldige geheimen in prompts te plaatsen:

De web-UI bevat OIDC-aanmelding met Authorization Code + PKCE, geverifieerde ID-tokens, server-side sessies en toegangscontroles voor projecten/ruimtes. Geverifieerde Microsoft Entra ID-groepclaims kunnen, wanneer geconfigureerd, toegangsbeleid op basis van directory ondersteunen. Windows Active Directory-, OAuth- en trusted-proxy-implementaties kunnen worden geïntegreerd via expliciete geverifieerde identiteitsadapters; Windows AD vereist een implementatiespecifieke Kerberos/Negotiate-verifier en is standaard niet ingeschakeld.

uag omvat opt-in, provider-neutrale OpenTelemetry tracering en statistieken voor Agent, LLM, tool, Context, Memory en ophaalbewerkingen. Waarneembaarheid is standaard uitgeschakeld.

Local-first betekent niet dat UAG standaard volledig offline werkt of dat alle tools geïsoleerd worden uitgevoerd. Aanroepen naar externe modellen en verbonden diensten zijn afhankelijk van de configuratie.

- [Enterprise policies](ENTERPRISE_POLICY.md)
- [MXC sandbox](SANDBOX_MXC.md)
- [Remote Web / A2A](REMOTE_MXC_DEFAULT.md)
- [Web identity](WEB_IDENTITY_MEMORY.md)
- [OpenTelemetry](UAG_OPENTELEMETRY_DESIGN.md)

### 🌍 Meertalige vertaling

- `translate_text` ondersteunt Google Translate en de officiële DeepL Python-client via `provider=auto`, `provider=deepl` of `provider=google`.
- Tooldefinities zijn beschikbaar in 37 locales plus het Engels (38 in totaal), waarbij plaatshouders en technische identificatiecodes behouden blijven.

Full-duplex-spraak is beschikbaar via OpenAI Realtime, Azure OpenAI, xAI Grok Voice, Gemini Live
en Bedrock Nova Sonic, met optionele AEC3-echocancellatie en veiligheidsbeperkte realtime functieaanroepen.

[Translations](README.translations.md) · [IoT](IOT_USECASE.md) · [Communication](COMMUNICATION.md)

## Documentatie

| Topic | Documentation |
|---|---|
| Environment variables | [docs/ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/docs/ENVIRONMENT.md) |
| Architecture and invariants | [docs/ARCHITECTURE.md](https://github.com/awaku7/agentcli/blob/main/docs/ARCHITECTURE.md) |
| Computer Use | [docs/COMPUTER_USE_IMPLEMENTATION.md](https://github.com/awaku7/agentcli/blob/main/docs/COMPUTER_USE_IMPLEMENTATION.md) |
| Repository tools | [docs/REPOSITORY_TOOLS.md](https://github.com/awaku7/agentcli/blob/main/docs/REPOSITORY_TOOLS.md) |
| IoT use cases | [docs/IOT_USECASE.md](https://github.com/awaku7/agentcli/blob/main/docs/IOT_USECASE.md) |
| Communication tools | [docs/COMMUNICATION.md](https://github.com/awaku7/agentcli/blob/main/docs/COMMUNICATION.md) |
| Auto-pilot | [docs/README_AUTO.md](https://github.com/awaku7/agentcli/blob/main/docs/README_AUTO.md) |
| MCP OAuth / Proxy | [docs/MCP_OAUTH_PROXY_GUIDE.md](https://github.com/awaku7/agentcli/blob/main/docs/MCP_OAUTH_PROXY_GUIDE.md) |
| VS Code extension | [docs/VSCODE.md](https://github.com/awaku7/agentcli/blob/main/docs/VSCODE.md) |
| Developer guide | [src/uagent/docs/DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md) |
| Tool flow | [src/uagent/docs/TOOL_FLOW.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/TOOL_FLOW.md) |

[Quickstart](QUICKSTART.md) · [Architecture](ARCHITECTURE.md) · [Context management](UAG_CONTEXT_MANAGEMENT_DESIGN.md)

## Ontwikkeling en bijdragen

```bash
git clone https://github.com/awaku7/agentcli.git
cd agentcli
python -m pip install -e ".[core,providers,test]"
```

Voer de controles vóór een pull request uit:

```bash
python -m ruff check src tests
python -m black --check src tests
python -m pytest -q .
```

Zie voor de volledige ontwikkelworkflow [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md).

Bugmeldingen, ideeën voor functies, verbeteringen van documentatie, vertalingen, tools, skills en pull requests zijn welkom.
Open vóór grote wijzigingen een issue of discussion. Lees de [Developer Guide](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)
en voer de bovenstaande controles uit voordat je een pull request indient.

## Licentie

Gelicentieerd onder de [Apache License 2.0](https://github.com/awaku7/agentcli/blob/main/LICENSE).
