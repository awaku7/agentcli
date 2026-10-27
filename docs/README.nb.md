<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="UAG — Universal AI Gateway" width="620">
</p>
<h1 align="center">UAG</h1>
<p align="center"><strong>Universal AI Gateway</strong><br>Dine KI-modeller. Dine verktøy. Ditt miljø.</p>

<p align="center">
  <a href="https://github.com/awaku7/agentcli/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/awaku7/agentcli/ci.yml?style=flat-square&label=CI" alt="CI"></a>
  <a href="https://pypi.org/project/uag/"><img src="https://img.shields.io/pypi/v/uag?style=flat-square" alt="PyPI"></a>
  <a href="https://pypi.org/project/uag/"><img src="https://img.shields.io/pypi/pyversions/uag?style=flat-square" alt="Python versions"></a>
  <a href="../LICENSE"><img src="https://img.shields.io/github/license/awaku7/agentcli?style=flat-square" alt="License"></a>
  <a href="https://pepy.tech/projects/uag"><img src="https://static.pepy.tech/personalized-badge/uag?period=total&units=INTERNATIONAL_SYSTEM&left_color=grey&right_color=green&left_text=downloads" alt="Downloads"></a>
</p>
<p align="center"><a href="../README.md">English</a> · <a href="README.translations.md">Andre språk</a></p>

---

**UAG er en åpen, lokalorientert kjøretid for KI-agenter.** Den kobler språkmodellen du velger, til verktøyene og systemene du bruker. Arbeid med kode, filer, nettlesere, tjenester og enheter fra ett felles grensesnitt uten å låse arbeidsflyten til én modellleverandør.

| **Velg modellen selv** | **Koble til verktøy** | **Behold kontrollen** |
| :--- | :--- | :--- |
| Skybaserte og lokale modeller, som OpenAI, Claude, Gemini, Grok, Bedrock og Ollama | Filer, kode, nett, MCP, Agent Skills, programtillegg, skytjenester og IoT | Lokal kjøring, menneskelig bekreftelse, sikker lagring av legitimasjon og justerbare retningslinjer |

> UAG er **et kjørelag for agenter, ikke en modellleverandør**. Kall til eksterne modeller og tilkoblede tjenester avhenger av oppsettet. Lokal-først betyr ikke at alt fungerer uten nett eller at alle verktøy er isolert som standard.

## Kom raskt i gang
<!-- README-SYNC:quick-start -->

Du trenger **Python 3.11 eller nyere**. Installer fra [PyPI](https://pypi.org/project/uag/) og start den interaktive kommandolinjen:

~~~bash
python -m pip install --upgrade uag
uag
~~~

Ved første oppstart hjelper veiviseren med valg av leverandør og legitimasjon. Du kan også bruke miljøvariabler eller legitimasjonslager. Installer flere avhengigheter for leverandører og verktøy på forhånd med:

~~~bash
python -m pip install "uag[core,providers,tools]"
~~~

Prøv deretter disse forespørslene:

~~~text
> Hva har endret seg i dette Git-repositoriet? Oppsummer risikoene.
> Finn den nyeste dokumentasjonen for biblioteket og forklar migreringsstegene.
> Undersøk disse filene og lag en kort rapport.
> :help
~~~

For nybegynnere finnes en installasjonsveiledning for Windows, inkludert Git og virtuelle miljøer, samt en konfigurasjonsreferanse: [Quickstart (Windows)](QUICKSTART.md) · [Environment](ENVIRONMENT.md).

## Grensesnitt
<!-- README-SYNC:interfaces -->

Alle grensesnitt deler samme agentkjøretid og verktøyregister.

| Grensesnitt | Start | Egnet for |
| :--- | :--- | :--- |
| **CLI** | `uag` | Terminal og automatisering |
| **Desktop** | `uagg` | Samtaler i skrivebordsprogram |
| **Web** | `uagw` | Samtaler og rom i nettleseren |
| **A2A** | `uaga` | Samhandling mellom agenter |
| **VS Code** | [Utvidelsesveiledning](VSCODE.md) | Arbeid med kildekode |

Desktop og Web krever ekstra avhengigheter som ikke er inkludert i `uag[core,providers,tools]`:

~~~bash
# Desktop GUI (PySide6 and platform integrations)
python -m pip install "uag[platform]"

# Web UI (authentication dependencies, FastAPI, and Uvicorn)
python -m pip install "uag[web]" fastapi uvicorn
~~~

Webserveren kan prøve å installere FastAPI og Uvicorn ved oppstart. Forhåndsinstallasjon gjør deg uavhengig av dette. Se: [CLI usage](USAGE.md) · [Environment](ENVIRONMENT.md).

## Dette kan du bygge med UAG
<!-- README-SYNC:capabilities -->

| Egenskap | Hva UAG tilbyr |
| :--- | :--- |
| **Modelluavhengige arbeidsflyter** | Bytt mellom lokale og skybaserte leverandører med `UAGENT_PROVIDER` uten å skrive om verktøy |
| **Kode og filer** | Repositorienavigasjon, Git-kontroll, linting, tester, filoperasjoner og nettleserautomatisering |
| **Utvidbare verktøy** | Over 200 verktøy, dynamisk oppdagelse med `tool_catalog` / `tool_load`, egne Python- og Rust-verktøy |
| **Sammenkoblede agenter** | MCP, A2A, Claude Code-kompatible tillegg, Agent Skills og underagenter |
| **Langvarige oppgaver** | Autopilot, parallelle uavhengige leseoperasjoner, planlegging, gjenoppretting og lagrede økter |
| **Utover terminalen** | Sky, kommunikasjon, dokumenter, medier, tale i sanntid og støttede IoT-protokoller |

### Én kjøretid, mange integrasjoner
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

**Eksempler på støttede modellleverandører** står nedenfor; innstillinger er beskrevet i miljøveiledningen.

### Tilpass med ferdigheter og programtillegg
<!-- README-SYNC:extensions -->

Utvid UAG uten å endre kjernen. Installer Agent Skills fra SkillsMP eller ClawHub, koble til MCP-servere, eller last inn Claude Code-kompatible tillegg med verktøy, ferdigheter, agenter og hooks.

~~~text
:skills mp_search browser automation
:plugin list
:plugin install <source>
:plugin marketplace list
~~~

Egne verktøy kan tilby `TOOL_SPEC` og `run_tool()`; Rust-baserte verktøy støttes også. Se veiledningene: [Tool Creator Guide](../TOOL_CREATOR_GUIDE.md) · [Plugin Development Guide](../src/uagent/docs/DEVELOP_PLUGIN.md) · [MCP OAuth / Proxy](MCP_OAUTH_PROXY_GUIDE.md).

## For virkelige arbeidsoppgaver
<!-- README-SYNC:workflows -->

### Kontekst og hukommelse
<!-- README-SYNC:context-memory -->

Store verktøyresultater kan lagres som **artefakter** fremfor å fylle modellens aktive kontekst. Agenten henter senere bare den relevante delen med `artifact_read`. Økter lagres som standard i SQLite, med historikksøk og eksplisitt minnegjennomgang.

- [Context compression](CONTEXT_COMPRESSION.nb.md)
- [Memory](MEMORY.md)
- [Session portability](SESSION_PORTABILITY.md)

### Automatisering og samarbeid
<!-- README-SYNC:automation -->

UAG støtter parallelle uavhengige leseoperasjoner, samarbeid mellom flere agenter, øktgjenoppretting og autopilot for oppgaver over flere runder. Start med `:auto`; trykk **F12** for å avbryte svaret og be autopiloten stoppe.

- [Auto-pilot](README_AUTO.md)
- [Timers and scheduled tasks](SET_TIMER.md)
- [Multi-agent runtime](MULTI_AGENT_RUNTIME.md)

### Sikkerhet og observerbarhet
<!-- README-SYNC:security -->

Følsomme handlinger kan kreve `human_ask`-bekreftelse. Legitimasjon kan lagres i operativsystemets sikre lager eller kryptert fil. Webgrensesnittet støtter konfigurert OIDC-pålogging og tilgangsstyring. OpenTelemetry-sporing og målinger er **valgfrie**.

- [Enterprise policies](ENTERPRISE_POLICY.md)
- [MXC sandbox](SANDBOX_MXC.md)
- [Remote Web / A2A MXC defaults](REMOTE_MXC_DEFAULT.md)
- [Web identity and rooms](WEB_IDENTITY_MEMORY.md)
- [OpenTelemetry design](UAG_OPENTELEMETRY_DESIGN.md)
- [Developer observability](../src/uagent/docs/DEVELOP_OBSERVABILITY.md)

Disse tiltakene er konfigurerbare, og **garanterer ikke** at alle verktøy kjøres isolert i en sandkasse. Les distribusjons- og policyveiledningene før UAG åpnes for upålitelige brukere eller nettverk.

### Språk, enheter og tale
<!-- README-SYNC:languages -->

UAG har ressurser for **38 språkvarianter** (engelsk og 37 oversettelser), valgfri toveis tale og verktøy for SwitchBot, Matter, ECHONET Lite, BACnet, Modbus TCP og OPC UA.

- [Translations](README.translations.md)
- [IoT use cases](IOT_USECASE.md)
- [Communication tools](COMMUNICATION.md)

## Dokumentasjon
<!-- README-SYNC:documentation -->

Start med disse veiledningene, og les videre ved behov:

| Begynn her | Les mer |
| :--- | :--- |
| [Quickstart (Windows)](QUICKSTART.md) | [Architecture](ARCHITECTURE.md) |
| [CLI usage](USAGE.md) | [Context management](UAG_CONTEXT_MANAGEMENT_DESIGN.md) |
| [Environment and providers](ENVIRONMENT.md) | [Enterprise policy](ENTERPRISE_POLICY.md) |
| [Agent Skills and plugins](../src/uagent/docs/DEVELOP_PLUGIN.md) | [Tool flow](../src/uagent/docs/TOOL_FLOW.md) |
| [MCP and OAuth](MCP_OAUTH_PROXY_GUIDE.md) | [Computer Use](COMPUTER_USE_IMPLEMENTATION.md) |
| [VS Code extension](VSCODE.md) | [Developer guide](../src/uagent/docs/DEVELOP.md) |

Se også hele dokumentasjonsmappen og oversettelsene: [Documentation](./) · [Other languages](README.translations.md).

## Utvikling og bidrag
<!-- README-SYNC:contributing -->

~~~bash
git clone https://github.com/awaku7/agentcli.git
cd agentcli
python -m pip install -e ".[core,providers,test]"
~~~

Før en pull request som endrer **Python-kode**, kjør relevante tester og prosjektkontroller:

~~~bash
python -m ruff check src tests
python -m black --check src tests
python -m pytest -q .
~~~

Bidragsregler og utviklerveiledning finnes nedenfor. Feilrapporter, dokumentasjonsforbedringer, verktøy, oversettelser og avgrensede pull requests er velkomne: [AGENTS.md](../AGENTS.md) · [Developer guide](../src/uagent/docs/DEVELOP.md).

## Lisens
<!-- README-SYNC:license -->

UAG distribueres under lisensen: [Apache License 2.0](../LICENSE).
