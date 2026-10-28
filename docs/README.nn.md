<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="UAG — Universal AI Gateway" width="620">
</p>
<h1 align="center">UAG</h1>
<p align="center"><strong>Universal AI Gateway</strong><br>Dine KI-modellar. Dine verktøy. Ditt miljø.</p>

<p align="center">
  <a href="https://github.com/awaku7/agentcli/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/awaku7/agentcli/ci.yml?style=flat-square&label=CI" alt="CI"></a>
  <a href="https://pypi.org/project/uag/"><img src="https://img.shields.io/pypi/v/uag?style=flat-square" alt="PyPI"></a>
  <a href="https://pypi.org/project/uag/"><img src="https://img.shields.io/pypi/pyversions/uag?style=flat-square" alt="Python versions"></a>
  <a href="../LICENSE"><img src="https://img.shields.io/github/license/awaku7/agentcli?style=flat-square" alt="License"></a>
  <a href="https://pepy.tech/projects/uag"><img src="https://static.pepy.tech/personalized-badge/uag?period=total&units=INTERNATIONAL_SYSTEM&left_color=grey&right_color=green&left_text=downloads" alt="Downloads"></a>
</p>
<p align="center"><a href="../README.md">English</a> · <a href="README.translations.md">Andre språk</a></p>

---

**UAG er ei open og lokalorientert køyretid for KI-agentar.** Ho koplar språkmodellen du vel, til verktøya og systema du nyttar. Arbeid med kode, filer, nettlesarar, tenester og einingar frå eitt samla grensesnitt utan å binde arbeidsflyten til éin modellleverandør.

| **Vel din eigen modell** | **Kopla til verktøy** | **Ha kontrollen sjølv** |
| :--- | :--- | :--- |
| Skybaserte og lokale modellar som OpenAI, Claude, Gemini, Grok, Bedrock og Ollama | Filer, kode, nett, MCP, Agent Skills, programtillegg, skytenester og IoT | Lokal køyring, stadfesting frå menneske, trygg lagring av påloggingsopplysningar og tilpassbare retningsliner |

> UAG er **eit køyrelag for agentar, ikkje ein modellleverandør**. Kall til eksterne modellar og tilkopla tenester kjem an på oppsettet. Lokal-først tyder ikkje at alt verkar utan nett eller at alle verktøy er isolerte som standard.

## Kom raskt i gang
<!-- README-SYNC:quick-start -->

Du treng **Python 3.11 eller nyare**. Installer frå [PyPI](https://pypi.org/project/uag/) og start den interaktive kommandolinja:

~~~bash
python -m pip install --upgrade uag
uag
~~~

Ved første oppstart hjelper rettleiaren deg med å velje leverandør og oppgje legitimasjon. Du kan òg bruke miljøvariablar eller eit trygt lager. For å installere fleire avhengnader til leverandørar og verktøy på førehand:

~~~bash
python -m pip install "uag[core,providers,tools]"
~~~

Prøv deretter desse førespurnadene:

~~~text
> Kva har endra seg i dette Git-repositoriet? Oppsummer risikoen.
> Finn den nyaste dokumentasjonen for biblioteket og forklar migreringa.
> Undersøk desse filene og lag ein kort rapport.
> :help
~~~

Nye brukarar kan lese Windows-rettleiinga med Git og virtuelle miljø, og referansen for oppsett: [Quickstart (Windows)](QUICKSTART.md) · [Environment](ENVIRONMENT.md).

## Grensesnitt
<!-- README-SYNC:interfaces -->

Alle grensesnitta nyttar den same agentkøyretida og det same verktøyregisteret.

| Grensesnitt | Start | Høver for |
| :--- | :--- | :--- |
| **CLI** | `uag` | Terminal og automatisering |
| **Desktop** | `uagg` | Samtalar i skrivebordsprogram |
| **Web** | `uagw` | Samtalar og rom i nettlesaren |
| **A2A** | `uaga` | Samspel mellom agentar |
| **VS Code** | [Rettleiing for utvidinga](VSCODE.md) | Arbeid med kjeldekode |

Desktop og Web treng ekstra avhengnader som ikkje er med i `uag[core,providers,tools]`:

~~~bash
# Desktop GUI (PySide6 and platform integrations)
python -m pip install "uag[platform]"

# Web UI (authentication dependencies, FastAPI, and Uvicorn)
python -m pip install "uag[web]" fastapi uvicorn
~~~

Webtenaren kan prøve å installere FastAPI og Uvicorn ved oppstart. Installerer du dei på førehand, slepp du å stole på automatisk installasjon. Sjå: [CLI usage](USAGE.md) · [Environment](ENVIRONMENT.md).

## Dette kan du byggje med UAG
<!-- README-SYNC:capabilities -->

| Eigenskap | Kva UAG tilbyr |
| :--- | :--- |
| **Modelluavhengige arbeidsflytar** | Byt mellom lokale og skybaserte leverandørar med `UAGENT_PROVIDER` utan å skrive om verktøya |
| **Kode og filer** | Navigering i repositorium, Git-kontroll, linting, testar, filoperasjonar og nettlesarautomatisering |
| **Utvidbare verktøy** | Over 200 verktøy, dynamisk søk med `tool_catalog` / `tool_load`, eigne Python- og Rust-verktøy |
| **Samanbundne agentar** | MCP, A2A, Claude Code-kompatible tillegg, Agent Skills og underagentar |
| **Langvarige oppgåver** | Autopilot, parallelle uavhengige lesingar, tidsplanar, attoppretting og lagra økter |
| **Meir enn terminal** | Sky, kommunikasjon, dokument, medium, tale i sanntid og støtta IoT-protokollar |

### Éi køyretid, mange integrasjonar
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

**Døme på modellleverandørar som er støtta** finn du nedanfor; innstillingar står i miljørettleiinga.

**OpenAI · Anthropic · Gemini · Vertex AI · Azure OpenAI · Amazon Bedrock · Grok · DeepSeek · OpenRouter · Ollama · llama.cpp · LM Studio**

[ENVIRONMENT.md](ENVIRONMENT.md)

### Tilpass med ferdigheiter og programtillegg
<!-- README-SYNC:extensions -->

Utvid UAG utan å endre kjernen. Installer Agent Skills frå SkillsMP eller ClawHub, kopla til MCP-tenarar eller last inn Claude Code-kompatible tillegg med verktøy, ferdigheiter, agentar og hooks.

~~~text
:skills mp_search browser automation
:plugin list
:plugin install <source>
:plugin marketplace list
~~~

Eigne verktøy kan tilby `TOOL_SPEC` og `run_tool()`; Rust-baserte verktøy er òg støtta. Sjå rettleiingane: [Tool Creator Guide](../TOOL_CREATOR_GUIDE.md) · [Plugin Development Guide](../src/uagent/docs/DEVELOP_PLUGIN.md) · [MCP OAuth / Proxy](MCP_OAUTH_PROXY_GUIDE.md).

## For verkelege arbeidsoppgåver
<!-- README-SYNC:workflows -->

### Kontekst og minne
<!-- README-SYNC:context-memory -->

Store verktøyresultat kan lagrast som **artefaktar** i staden for å fylle den aktive konteksten til modellen. Agenten kan seinare hente berre det aktuelle utdraget med `artifact_read`. Økter blir som standard lagra i SQLite, med historikksøk og tydeleg minnegjennomgang.

- [Context compression](CONTEXT_COMPRESSION.nn.md)
- [Memory](MEMORY.md)
- [Session portability](SESSION_PORTABILITY.md)

### Automatisering og samarbeid
<!-- README-SYNC:automation -->

UAG støttar parallelle uavhengige leseoperasjonar, samordning av fleire agentar, attoppretting av økter og autopilot for oppgåver over fleire rundar. Start med `:auto`; trykk **F12** for å avbryte svaret og be autopiloten stoppe.

- [Auto-pilot](README_AUTO.md)
- [Timers and scheduled tasks](SET_TIMER.md)
- [Multi-agent runtime](MULTI_AGENT_RUNTIME.md)

### Tryggleik og observerbarheit
<!-- README-SYNC:security -->

Sensitive handlingar kan krevje stadfesting med `human_ask`. Legitimasjon kan lagrast i operativsystemet sitt sikre lager eller ei kryptert fil. Webgrensesnittet støttar konfigurert OIDC-innlogging og tilgangskontroll. OpenTelemetry-sporing og målingar er **valfrie**.

- [Enterprise policies](ENTERPRISE_POLICY.md)
- [MXC sandbox](SANDBOX_MXC.md)
- [Remote Web / A2A MXC defaults](REMOTE_MXC_DEFAULT.md)
- [Web identity and rooms](WEB_IDENTITY_MEMORY.md)
- [OpenTelemetry design](UAG_OPENTELEMETRY_DESIGN.md)
- [Developer observability](../src/uagent/docs/DEVELOP_OBSERVABILITY.md)

Tiltaka kan stillast inn, men **garanterer ikkje** at alle verktøy blir køyrde isolert i ei sandkasse. Les rettleiingane om utrulling og retningsliner før UAG blir opna for ikkje-trudde brukarar eller nettverk.

### Språk, einingar og tale
<!-- README-SYNC:languages -->

UAG har ressursar for **38 språkvariantar** (engelsk og 37 omsetjingar), valfri tovegs tale og verktøy for SwitchBot, Matter, ECHONET Lite, BACnet, Modbus TCP og OPC UA.

- [Translations](README.translations.md)
- [IoT use cases](IOT_USECASE.md)
- [Communication tools](COMMUNICATION.md)

## Dokumentasjon
<!-- README-SYNC:documentation -->

Begynn med desse rettleiingane, og les vidare ved behov:

| Begynn her | Meir informasjon |
| :--- | :--- |
| [Quickstart (Windows)](QUICKSTART.md) | [Architecture](ARCHITECTURE.md) |
| [CLI usage](USAGE.md) | [Context management](UAG_CONTEXT_MANAGEMENT_DESIGN.md) |
| [Environment and providers](ENVIRONMENT.md) | [Enterprise policy](ENTERPRISE_POLICY.md) |
| [Agent Skills and plugins](../src/uagent/docs/DEVELOP_PLUGIN.md) | [Tool flow](../src/uagent/docs/TOOL_FLOW.md) |
| [MCP and OAuth](MCP_OAUTH_PROXY_GUIDE.md) | [Computer Use](COMPUTER_USE_IMPLEMENTATION.md) |
| [VS Code extension](VSCODE.md) | [Developer guide](../src/uagent/docs/DEVELOP.md) |

Sjå òg resten av dokumentasjonen og omsetjingane: [Documentation](./) · [Other languages](README.translations.md).

## Utvikling og bidrag
<!-- README-SYNC:contributing -->

~~~bash
git clone https://github.com/awaku7/agentcli.git
cd agentcli
python -m pip install -e ".[core,providers,test]"
~~~

Før ein pull request som endrar **Python-kode**, køyr relevante testar og prosjektkontrollar:

~~~bash
python -m ruff check src tests
python -m black --check src tests
python -m pytest -q .
~~~

Bidragsreglar og utviklarrettleiing står nedanfor. Feilrapportar, dokumentasjonsbetringar, verktøy, omsetjingar og avgrensa pull requests er velkomne: [AGENTS.md](../AGENTS.md) · [Developer guide](../src/uagent/docs/DEVELOP.md).

## Lisens
<!-- README-SYNC:license -->

UAG blir distribuert under lisensen: [Apache License 2.0](../LICENSE).
