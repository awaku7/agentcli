<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="680">
</p>

<h1 align="center">uag</h1>

<p align="center">
  <strong>Universal AI Gateway</strong><br>
  Én lokal agent. Enhver model. Ethvert værktøj. Dit miljø, dine regler.
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

**Hvorfor uag?**

uag er en lokal-først AI-agent, der forbinder den model, du foretrækker, med de værktøjer, du faktisk bruger.
Den giver dig et enkelt, udvideligt runtime-miljø til filer, browsere, kodebaser, kommunikation, cloud-API'er,
IoT-enheder, MCP-servere og arbejdsgange med flere agenter.

- **Frihed til at vælge udbyder** — OpenAI, Anthropic, Gemini, Azure, Bedrock, Ollama, llama.cpp, Grok, DeepSeek og flere.
- **Lokal-først-udførelse** — din agent-runtime og værktøjsudførelse forbliver på din maskine; kun de API-kald, du vælger, forlader den.
- **Ét værktøjslag** — de samme værktøjer fungerer fra CLI'en, desktop-GUI'en, webbrugerfladen, VS Code og A2A.
- **Parallelitet som udgangspunkt** — uafhængige skrivebeskyttede operationer kan køre samtidigt.
- **Udvidelig** — tilføj værktøjer, plugins, Agent Skills, MCP-servere og Rust-baserede værktøjer uden at ændre kernen.
- **Sikkerhedsbevidst** — destruktive handlinger, legitimationsoplysninger, enhedskontroller og netværksskrivninger understøtter eksplicit bekræftelse og politikstyring.

> **Kort sagt:** uag er kontrolplanet mellem dine AI-modeller og dit virkelige miljø.

> **🧠 Kontekstbevidste værktøjsresultater** — Store værktøjsresultater holdes så vidt muligt uden for den aktive modelkontekst. uag gemmer dem som artefakter og sender i stedet en afgrænset forhåndsvisning med en stabil Artifact-reference til modellen. Dette kan reducere antallet af input-tokens, der kræves til opfølgende runder, betydeligt, når et værktøj genererer et stort resultat.
> [Detaljeret guide til kontekstkomprimering](CONTEXT_COMPRESSION.da.md)

## Hurtig start

**Python 3.11+**

```bash
python -m pip install --upgrade uag
uag
```

Ved første start åbnes installationsguiden. Den hjælper med at konfigurere en udbyder og gemmer de valgte indstillinger
i dit lokale miljø.

For de almindelige funktionsgrupper:

```bash
python -m pip install "uag[core,providers,tools]"
```

> Plattformsspecifikke integrationer er valgfri. Installér kun det, dit operativsystem har brug for; se

```text
> What files changed in this repository?
> Search the web for today's AI news and summarize the top five stories.
> :help
```

[Quickstart](QUICKSTART.md) · [Environment](ENVIRONMENT.md)

## Grænseflader

| Grænseflade | Kommando | Bedst til |
|---|---|---|
| **CLI** | `uag` | Hurtigt arbejde med tastaturet først |
| **Desktop-GUI** | `uagg` | En native desktopoplevelse |
| **Webbrugerflade** | `uagw` | Browserbaseret adgang |
| **A2A-server** | `uaga` | Kommunikation agent-til-agent |
| **VS Code** | Extension | Forklar, refaktorér, ret og gennemse værktøjer i editoren |

Alle grænseflader deler den samme udbyderkonfiguration, værktøjsregistrering, sikkerhedsregler og sessionsdata.

~~~bash
# Desktop GUI
python -m pip install "uag[platform]"

# Web UI
python -m pip install "uag[web]" fastapi uvicorn
~~~

[Interface options](USAGE.md) · [Environment](ENVIRONMENT.md)

## Hvad du kan bygge

Udbyderadaptere dækker hostede og lokale runtimes, herunder:

**OpenAI · Anthropic · Gemini · Vertex AI · Azure OpenAI · Amazon Bedrock · Grok · DeepSeek · OpenRouter · Ollama · llama.cpp · LM Studio**

- Læs, opret, redigér, søg i, hash, arkivér og inspicér filer
- Gennemgå Git-ændringer, scan efter hemmeligheder, kør tests, udfør linting, kompilér og mål dækning
- Navigér i store Python-, TypeScript-, JavaScript-, Go-, Rust-, C/C++-, Java-, C#-, COBOL-, VBA- og andre kodebaser
- Automatisér browsere med Playwright, inklusive arbejdsgange på flere sider og downloads

- **MCP** — forbind eksterne værktøjsservere, herunder OAuth-aktiverede tjenester
- **A2A** — koordinér med andre agenter og kompatible servere
- **Cloud** — AWS-, Google Cloud- og Azure-API-adgang med bekræftelse ved skrivninger
- **Kommunikation** — Gmail, Bluesky, Discord, Microsoft Teams og pybitchat
- **IoT** — SwitchBot, ECHONET Lite, Matter, BACnet, Modbus TCP, OPC UA og UPnP
- **Medier** — billedgenerering/-redigering, lydtransskription/tale, kameraoptagelse og QR-koder
- **Dokumenter** — PDF, PowerPoint, Word, Excel, CSV, JSON, YAML, SQL og loganalyse

- **SwitchBot** — Cloud- og BLE-opdagelse, status, styring, batching og abonnementer
- **ECHONET Lite** — opdag og styr japanske husholdningsapparater, herunder INF-notifikationer
- **Matter** — endpoints, clusters, attributter, tilstandshistorik, abonnementer og styring
- **BACnet / Modbus TCP / OPC UA** — læsning, skrivning, browsing og overvågning til industriel automation og bygningsautomation
- **UPnP** — enhedsopdagelse, WAN-status og styring af routerens portmapping

### Hvor passer uag ind?

uag befinder sig mellem mennesker og grænseflader på den ene side og modeller, værktøjer og systemer i den virkelige verden på den anden.
Den koordinerer samtalen, vælger funktioner, anvender sikkerhedsregler og holder arbejdsgangen genoptagelig.

~~~mermaid
flowchart LR
    UI["CLI · Desktop · Web · VS Code · A2A"] --> UAG["UAG agent runtime"]
    UAG --> MODELS["Hosted & local models"]
    UAG --> TOOLS["Tools & extensions"]
    UAG --> STATE["Sessions & context"]
    TOOLS --> SYSTEMS["Files · Code · Web · MCP · Cloud · IoT"]
    POLICY["Confirmation · Credentials · Policy"] -.-> UAG
~~~

### Plugins, Agent Skills og markedspladser

Gør uag til en specialiseret agent uden at forke kernen:

- Installér **Claude Code-kompatible plugins** fra en mappe, ZIP, et Git-repository, en HTTP-kilde eller en markedsplads
- Saml skills, underagenter, MCP-servere, hooks, slash-kommandoer, outputstile, afhængigheder og kanaler
- Gennemse fællesskabets funktioner fra [SkillsMP](https://skillsmp.com) og [ClawHub](https://clawhub.ai)
- Tilføj private organisationsskills og -værktøjer lokalt via `UAGENT_EXTERNAL_TOOLS_DIR`

```text
:skills mp_search browser automation
:plugin list
:plugin install <source>
:plugin marketplace list
```

Se [Plugin Development Guide](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP_PLUGIN.md).

- **200+ værktøjer** til filer, web, medier, dokumenter, kode, cloud, kommunikation og IoT
- **Dynamisk opdagelse og indlæsning** — brug `tool_catalog` til at finde funktioner og `tool_load` til kun at aktivere dem, når der er brug for dem
- **Kodeintelligens** — `code_map`, sprogspecifikke `idx`-navigatorer, Git-gennemgang, testkørsel, linting, kompilering og dækningsmåling
- **Claude Code-kompatible plugins** med skills, agenter, MCP-servere, hooks, kommandoer og markedspladser
- **Agent Skills** fra SkillsMP og ClawHub
- **Brugerdefinerede Python-værktøjer** med `TOOL_SPEC` og `run_tool()`
- **Rust-baserede værktøjer** til lette native udvidelser

[Tool Creator Guide](../TOOL_CREATOR_GUIDE.md) · [MCP OAuth / Proxy Guide](MCP_OAUTH_PROXY_GUIDE.md)

## Bygget til virkelige arbejdsgange

### 🧠 Kontekstbevidste værktøjsresultater

Store værktøjsresultater holdes så vidt muligt uden for den aktive modelkontekst. uag gemmer dem som artefakter og sender i stedet en afgrænset forhåndsvisning med en stabil Artifact-reference til modellen. Dette kan reducere antallet af input-tokens, der kræves til opfølgende runder, betydeligt, når et værktøj genererer et stort resultat.

Genoptag tidligere samtaler med `:load <index>`. Værktøjsresultater kan caches, og udbydere kan ændres
uden at genopbygge applikationen.

[Context compression](CONTEXT_COMPRESSION.da.md) · [Memory](MEMORY.md) · [Session portability](SESSION_PORTABILITY.md)

### Autopilot

Brug `:auto` til arbejde i flere runder med en valgfri reviewermodel. Angiv en rundegrænse med `--max-rounds N`.
Tryk på **F12** for at stoppe autopiloten eller **F12** for at stoppe det aktuelle svar.

Uafhængige skrivebeskyttede operationer kører samtidigt, når det er sikkert. Websøgninger, filinspektion,
repository-analyse og lignende arbejdsbelastninger kan fuldføres parallelt med en konfigurerbar worker-
pool (`UAGENT_PARALLEL_WORKERS`). Skriveoperationer forbliver serialiserede eller kræver bekræftelse.

Sessionskontinuitet, caching af værktøjsresultater, batchtilstand, genstartsgendannelse, DAG-planlægning og
orkestrering af flere agenter gør komplekst arbejde genoptageligt i stedet for engangsbaseret.

[Auto-pilot](README_AUTO.md) · [Timers](SET_TIMER.md) · [Multi-agent runtime](MULTI_AGENT_RUNTIME.md)

### 🌍 Privat, flersproget og politikbevidst

`human_ask` holder pause før følsomme handlinger. Sletning af filer, overskrivninger, shell-kommandoer, enhedskontroller,
legitimationshandlinger og netværksskrivninger kan styres af bekræftelses- og politikregler.

Brug legitimationsoplysningslageret i stedet for at placere langtidsholdbare hemmeligheder i prompts:

Web UI inkluderer OIDC-login ved brug af Authorization Code + PKCE, verificerede ID-tokens, server-side sessioner og adgangskontrol til projekter/rum. Verificerede Microsoft Entra ID-gruppekrav kan bruges til mappebaseret adgangspolitik, når det er konfigureret. Windows Active Directory, OAuth og trusted-proxy-implementeringer kan integreres via eksplicit verificerede identitetsadaptere; Windows AD kræver en implementeringsspecifik Kerberos/Negotiate-verifikator og er ikke aktiveret som standard.

uag inkluderer opt-in, udbyderneutral OpenTelemetry-sporing og metrics for Agent, LLM, værktøj, Context, Memory og hentning. Observerbarhed er deaktiveret som standard.

Local-first betyder ikke, at UAG som standard fungerer helt offline, eller at alle værktøjer er isolerede. Kald til eksterne modeller og tilsluttede tjenester afhænger af konfigurationen.

- [Enterprise policies](ENTERPRISE_POLICY.md)
- [MXC sandbox](SANDBOX_MXC.md)
- [Remote Web / A2A](REMOTE_MXC_DEFAULT.md)
- [Web identity](WEB_IDENTITY_MEMORY.md)
- [OpenTelemetry](UAG_OPENTELEMETRY_DESIGN.md)

### 🌍 Flersproget oversættelse

- `translate_text` understøtter Google Translate og den officielle DeepL Python-klient via `provider=auto`, `provider=deepl` eller `provider=google`.
- Værktøjsdefinitioner er tilgængelige på 37 sprog samt engelsk (i alt 38), hvor pladsholdere og tekniske identifikatorer bevares.

Fuldt tovejs-stemmelyd er tilgængelig via OpenAI Realtime, Azure OpenAI, xAI Grok Voice, Gemini Live,
og Bedrock Nova Sonic, med valgfri AEC3-ekkoannullering og sikkerhedsbegrænset realtime-funktionskald.

[Translations](README.translations.md) · [IoT](IOT_USECASE.md) · [Communication](COMMUNICATION.md)

## Dokumentation

| Emne | Dokumentation |
|---|---|
| Miljøvariabler | [docs/ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/docs/ENVIRONMENT.md) |
| Arkitektur og invariants | [docs/ARCHITECTURE.md](https://github.com/awaku7/agentcli/blob/main/docs/ARCHITECTURE.md) |
| Computer Use | [docs/COMPUTER_USE_IMPLEMENTATION.md](https://github.com/awaku7/agentcli/blob/main/docs/COMPUTER_USE_IMPLEMENTATION.md) |
| Repository-værktøjer | [docs/REPOSITORY_TOOLS.md](https://github.com/awaku7/agentcli/blob/main/docs/REPOSITORY_TOOLS.md) |
| IoT-anvendelsestilfælde | [docs/IOT_USECASE.md](https://github.com/awaku7/agentcli/blob/main/docs/IOT_USECASE.md) |
| Kommunikationsværktøjer | [docs/COMMUNICATION.md](https://github.com/awaku7/agentcli/blob/main/docs/COMMUNICATION.md) |
| Autopilot | [docs/README_AUTO.md](https://github.com/awaku7/agentcli/blob/main/docs/README_AUTO.md) |
| MCP OAuth / Proxy | [docs/MCP_OAUTH_PROXY_GUIDE.md](https://github.com/awaku7/agentcli/blob/main/docs/MCP_OAUTH_PROXY_GUIDE.md) |
| VS Code-udvidelse | [docs/VSCODE.md](https://github.com/awaku7/agentcli/blob/main/docs/VSCODE.md) |
| Udviklervejledning | [src/uagent/docs/DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md) |
| Værktøjsflow | [src/uagent/docs/TOOL_FLOW.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/TOOL_FLOW.md) |

[Quickstart](QUICKSTART.md) · [Architecture](ARCHITECTURE.md) · [Context management](UAG_CONTEXT_MANAGEMENT_DESIGN.md)

## Udvikling og bidrag

```bash
git clone https://github.com/awaku7/agentcli.git
cd agentcli
python -m pip install -e ".[core,providers,test]"
```

Kør kontrollerne før en PR:

```bash
python -m ruff check src tests
python -m black --check src tests
python -m pytest -q .
```

Se [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md) for den komplette udviklingsarbejdsgang.

Fejlrapporter, idéer til funktioner, forbedringer af dokumentationen, oversættelser, værktøjer, skills og pull requests er velkomne.
Opret venligst en issue eller diskussion før større ændringer. Læs [Developer Guide](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)
og kør kontrollerne ovenfor, før du indsender en pull request.

## Licens

Licenseret under [Apache License 2.0](https://github.com/awaku7/agentcli/blob/main/LICENSE).
