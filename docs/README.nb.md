<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="680">
</p>

<h1 align="center">uag</h1>

<p align="center">
  <strong>Universal AI Gateway</strong><br>
  Én lokal agent. Enhver modell. Ethvert verktøy. Ditt miljø, dine regler.
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

uag er en lokal-først AI-agent som kobler modellen du foretrekker, til verktøyene du faktisk bruker.
Den gir deg én utvidbar kjøretid for filer, nettlesere, kodebaser, kommunikasjon, sky-API-er,
IoT-enheter, MCP-servere og arbeidsflyter med flere agenter.

- **Frihet til å velge leverandør** — OpenAI, Anthropic, Gemini, Azure, Bedrock, Ollama, llama.cpp, Grok, DeepSeek og flere.
- **Lokal-først-kjøring** — agentens kjøretid og verktøykjøring forblir på maskinen din; bare API-kallene du velger, forlater den.
- **Ett verktøylag** — de samme verktøyene fungerer fra CLI, skrivebords-GUI, webgrensesnittet, VS Code og A2A.
- **Parallellitet som utgangspunkt** — uavhengige skrivebeskyttede operasjoner kan kjøre samtidig.
- **Utvidbar** — legg til verktøy, programtillegg, Agent Skills, MCP-servere og Rust-baserte verktøy uten å endre kjernen.
- **Sikkerhetsbevisst** — destruktive handlinger, legitimasjon, enhetsstyring og nettverksskriving støtter eksplisitt bekreftelse og policykontroller.

> **Kort sagt:** uag er kontrollplanet mellom AI-modellene dine og det virkelige miljøet ditt.

> **🧠 Kontekstbevisste verktøyresultater** — Store verktøyresultater holdes utenfor den aktive modellkonteksten når det er mulig. uag lagrer dem som artefakter og gir modellen en avgrenset forhåndsvisning med en stabil Artifact-referanse i stedet. Dette kan redusere antallet inndatatokener som kreves for oppfølgende runder betydelig når et verktøy produserer et stort resultat.
> [Detaljert veiledning for kontekstkomprimering](CONTEXT_COMPRESSION.nb.md)

## Hurtigstart

**Python 3.11+**

```bash
python -m pip install --upgrade uag
uag
```

Ved første oppstart åpnes en konfigurasjonsveiviser. Den hjelper deg med å konfigurere en leverandør og lagrer de valgte innstillingene
i det lokale miljøet ditt.

For de vanligste funksjonsgruppene:

```bash
python -m pip install "uag[core,providers,tools]"
```

> Plattformintegrasjoner er valgfrie. Installer bare det operativsystemet ditt trenger; se

```text
> What files changed in this repository?
> Search the web for today's AI news and summarize the top five stories.
> :help
```

[Quickstart](QUICKSTART.md) · [Environment](ENVIRONMENT.md)

## Grensesnitt

| Grensesnitt | Kommando | Best for |
|---|---|---|
| **CLI** | `uag` | Raskt, tastaturbasert arbeid |
| **Skrivebords-GUI** | `uagg` | En innebygd skrivebordsopplevelse |
| **Webgrensesnitt** | `uagw` | Nettleserbasert tilgang |
| **A2A-server** | `uaga` | Agent-til-agent-kommunikasjon |
| **VS Code** | Extension | Forklar, refaktorer, rett og bla gjennom verktøy i editoren |

Alle grensesnittene deler samme leverandørkonfigurasjon, verktøyregister, sikkerhetsregler og øktdata.

~~~bash
# Desktop GUI
python -m pip install "uag[platform]"

# Web UI
python -m pip install "uag[web]" fastapi uvicorn
~~~

[Interface options](USAGE.md) · [Environment](ENVIRONMENT.md)

## Hva du kan bygge

Leverandøradaptere dekker vertsbaserte og lokale kjøretider, inkludert:

**OpenAI · Anthropic · Gemini · Vertex AI · Azure OpenAI · Amazon Bedrock · Grok · DeepSeek · OpenRouter · Ollama · llama.cpp · LM Studio**

- Les, opprett, rediger, søk i, hash, arkiver og inspiser filer
- Gjennomgå Git-endringer, søk etter hemmeligheter, kjør tester, bruk linting, kompiler og mål dekning
- Naviger i store Python-, TypeScript-, JavaScript-, Go-, Rust-, C/C++-, Java-, C#-, COBOL-, VBA- og andre kodebaser
- Automatiser nettlesere med Playwright, inkludert flersidige arbeidsflyter og nedlastinger

- **MCP** — koble til eksterne verktøyservere, inkludert tjenester med OAuth
- **A2A** — koordiner med andre agenter og kompatible servere
- **Cloud** — AWS-, Google Cloud- og Azure-API-tilgang med bekreftelse for skriving
- **Communication** — Gmail, Bluesky, Discord, Microsoft Teams og pybitchat
- **IoT** — SwitchBot, ECHONET Lite, Matter, BACnet, Modbus TCP, OPC UA og UPnP
- **Media** — bildegenerering/-redigering, lydtranskripsjon/tale, kameraopptak og QR-koder
- **Documents** — analyse av PDF, PowerPoint, Word, Excel, CSV, JSON, YAML, SQL og logger

- **SwitchBot** — sky- og BLE-oppdagelse, status, styring, batching og abonnementer
- **ECHONET Lite** — oppdag og styr japanske husholdningsapparater, inkludert INF-varsler
- **Matter** — endepunkter, klynger, attributter, historikk for tilstand, abonnementer og styring
- **BACnet / Modbus TCP / OPC UA** — lesing, skriving, blaing og overvåking for industri- og bygningsautomasjon
- **UPnP** — enhetsoppdagelse, WAN-status og håndtering av porttilordning på rutere

### Hvor passer uag inn?

uag befinner seg mellom mennesker og grensesnitt på den ene siden, og modeller, verktøy og systemer i den virkelige verden på den andre.
Den koordinerer samtalen, velger funksjoner, håndhever sikkerhetsregler og sørger for at arbeidsflyten kan gjenopptas.

~~~mermaid
flowchart LR
    UI["CLI · Desktop · Web · VS Code · A2A"] --> UAG["UAG agent runtime"]
    UAG --> MODELS["Hosted & local models"]
    UAG --> TOOLS["Tools & extensions"]
    UAG --> STATE["Sessions & context"]
    TOOLS --> SYSTEMS["Files · Code · Web · MCP · Cloud · IoT"]
    POLICY["Confirmation · Credentials · Policy"] -.-> UAG
~~~

### Programtillegg, Agent Skills og markedsplasser

Gjør uag til en spesialisert agent uten å lage en fork av kjernen:

- Installer **Claude Code-kompatible programtillegg** fra en katalog, ZIP-fil, Git-repositorium, HTTP-kilde eller markedsplass
- Samle ferdigheter, underagenter, MCP-servere, hooks, skråstrekkommandoer, utdatastiler, avhengigheter og kanaler
- Bla gjennom fellesskapsfunksjoner fra [SkillsMP](https://skillsmp.com) og [ClawHub](https://clawhub.ai)
- Legg til private organisasjonsferdigheter og verktøy lokalt gjennom `UAGENT_EXTERNAL_TOOLS_DIR`

```text
:skills mp_search browser automation
:plugin list
:plugin install <source>
:plugin marketplace list
```

Se [Plugin Development Guide](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP_PLUGIN.md).

- **200+ verktøy** for filer, web, medier, dokumenter, kode, sky, kommunikasjon og IoT
- **Dynamisk oppdagelse og lasting** — bruk `tool_catalog` til å finne funksjoner og `tool_load` til å aktivere dem bare når det trengs
- **Kodeintelligens** — `code_map`, språkspesifikke `idx`-navigatører, Git-gjennomgang, testkjøring, linting, kompilering og dekning
- **Claude Code-kompatible programtillegg** med ferdigheter, agenter, MCP-servere, hooks, kommandoer og markedsplasser
- **Agent Skills** fra SkillsMP og ClawHub
- **Egendefinerte Python-verktøy** med `TOOL_SPEC` og `run_tool()`
- **Rust-baserte verktøy** for lette native-utvidelser

[Tool Creator Guide](../TOOL_CREATOR_GUIDE.md) · [MCP OAuth / Proxy Guide](MCP_OAUTH_PROXY_GUIDE.md)

## Bygget for virkelige arbeidsflyter

### 🧠 Kontekstbevisste verktøyresultater

Store verktøyresultater holdes utenfor den aktive modellkonteksten når det er mulig. uag lagrer dem som artefakter og gir modellen en avgrenset forhåndsvisning med en stabil Artifact-referanse i stedet. Dette kan redusere antallet inndatatokener som kreves for oppfølgende runder betydelig når et verktøy produserer et stort resultat.

Gjenoppta tidligere samtaler med `:load <index>`. Verktøyresultater kan hurtigbufres, og leverandører kan byttes
uten å bygge applikasjonen på nytt.

[Context compression](CONTEXT_COMPRESSION.nb.md) · [Memory](MEMORY.md) · [Session portability](SESSION_PORTABILITY.md)

### Autopilot

Bruk `:auto` for arbeid over flere runder med en valgfri kontrollmodell. Angi en rundegrense med `--max-rounds N`.
Trykk **F12** for å stoppe autopiloten eller **F12** for å stoppe det gjeldende svaret.

Uavhengige skrivebeskyttede operasjoner kjører samtidig når det er trygt. Nettsøk, filinspeksjon,
analyse av repositorier og lignende arbeidsbelastninger kan fullføres parallelt med en konfigurerbar arbeiderpool
(`UAGENT_PARALLEL_WORKERS`). Skriveoperasjoner forblir serialiserte eller krever bekreftelse.

Kontinuitet i økter, hurtigbufring av verktøyresultater, batchtilstand, gjenoppretting etter omstart, DAG-planlegging og
orkestrering av flere agenter gjør komplekst arbeid gjenopptakbart i stedet for engangsbasert.

[Auto-pilot](README_AUTO.md) · [Timers](SET_TIMER.md) · [Multi-agent runtime](MULTI_AGENT_RUNTIME.md)

### 🌍 Privat, flerspråklig og policybevisst

`human_ask` setter på pause før følsomme handlinger. Sletting av filer, overskrivinger, shell-kommandoer, enhetsstyring,
legitimasjonsoperasjoner og nettverksskriving kan styres av regler for bekreftelse og policy.

Bruk legitimasjonslageret i stedet for å legge langvarige hemmeligheter i ledetekster:

Webgrensesnittet inkluderer OIDC-pålogging med Authorization Code + PKCE, verifiserte ID-tokener, server-side økter og tilgangskontroller for prosjekt/rom. Verifiserte Microsoft Entra ID-gruppekrav kan gi tilgangspolicy basert på katalog når det er konfigurert. Windows Active Directory, OAuth og trusted-proxy-distribusjoner kan integreres gjennom eksplisitte verifiserte identitetsadaptere; Windows AD krever en distribusjonsspesifikk Kerberos/Negotiate-verifiserer og er ikke aktivert som standard.

uag inkluderer opt-in, leverandørnøytral OpenTelemetry-sporing og beregninger for Agent, LLM, verktøy, Context, Memory og gjenfinningsoperasjoner. Observerbarhet er deaktivert som standard.

Local-first betyr ikke at UAG som standard fungerer helt uten nett, eller at alle verktøy er isolert. Kall til eksterne modeller og tilkoblede tjenester avhenger av konfigurasjonen.

- [Enterprise policies](ENTERPRISE_POLICY.md)
- [MXC sandbox](SANDBOX_MXC.md)
- [Remote Web / A2A](REMOTE_MXC_DEFAULT.md)
- [Web identity](WEB_IDENTITY_MEMORY.md)
- [OpenTelemetry](UAG_OPENTELEMETRY_DESIGN.md)

### 🌍 Flerspråklig oversettelse

- `translate_text` støtter Google Translate og den offisielle DeepL-Python-klienten via `provider=auto`, `provider=deepl` eller `provider=google`.
- Verktøydefinisjoner er tilgjengelige på 37 språk i tillegg til engelsk (38 totalt), med plassholdere og tekniske identifikatorer bevart.

Full dupleks-tale er tilgjengelig gjennom OpenAI Realtime, Azure OpenAI, xAI Grok Voice, Gemini Live,
og Bedrock Nova Sonic, med valgfri ekkokansellering med AEC3 og sikkerhetsbegrenset funksjonskalling i sanntid.

[Translations](README.translations.md) · [IoT](IOT_USECASE.md) · [Communication](COMMUNICATION.md)

## Dokumentasjon

| Emne | Dokumentasjon |
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

## Utvikling og bidrag

```bash
git clone https://github.com/awaku7/agentcli.git
cd agentcli
python -m pip install -e ".[core,providers,test]"
```

Kjør kontrollene før en PR:

```bash
python -m ruff check src tests
python -m black --check src tests
python -m pytest -q .
```

Se [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md) for den fullstendige arbeidsflyten for utvikling.

Feilrapporter, funksjonsideer, forbedringer av dokumentasjonen, oversettelser, verktøy, ferdigheter og pull requests ønskes velkommen.
Opprett en issue eller diskusjon før større endringer. Les [Developer Guide](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)
og kjør kontrollene ovenfor før du sender inn en pull request.

## Lisens

Lisensiert under [Apache License 2.0](https://github.com/awaku7/agentcli/blob/main/LICENSE).
