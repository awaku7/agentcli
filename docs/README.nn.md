<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="680">
</p>

<h1 align="center">uag</h1>

<p align="center">
  <strong>Universal AI Gateway</strong><br>
  Éin lokal agent. Kva modell som helst. Kva verktøy som helst. Ditt miljø, dine reglar.
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
  <a href="https://github.com/awaku7/agentcli/discussions">Diskusjonar</a> ·
  <a href="https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md">Omsetjingar</a>
</p>

______________________________________________________________________

**Kvifor uag?**

uag er ein lokal-først AI-agent som koplar modellen du føretrekkjer, til verktøya du faktisk bruker.
Han gir deg éin utvidbar køyretidsmiljø for filer, nettlesarar, kodebasar, kommunikasjon, sky-API-ar,
IoT-einingar, MCP-tenarar og arbeidsflytar med fleire agentar.

- **Fridom til å velje leverandør** — OpenAI, Anthropic, Gemini, Azure, Bedrock, Ollama, llama.cpp, Grok, DeepSeek og fleire.
- **Lokal-først-køyring** — agentkøyretida og verktøykøyringa blir verande på maskina di; berre API-kalla du vel, forlèt henne.
- **Eitt verktøylag** — dei same verktøya fungerer frå CLI, skrivebords-GUI, nettgrensesnittet, VS Code og A2A.
- **Parallellitet frå grunnen av** — uavhengige skrivefrie operasjonar kan køyre samtidig.
- **Utvidbar** — legg til verktøy, programtillegg, Agent Skills, MCP-tenarar og Rust-baserte verktøy utan å endre kjernen.
- **Tryggleiksmedviten** — øydeleggande handlingar, legitimasjonar, einingskontrollar og nettverksskriving støttar uttrykkeleg stadfesting og styring med reglar.

> **Kort sagt:** uag er kontrollplanet mellom AI-modellane dine og det verkelege miljøet ditt.

> **🧠 Kontekstmedvitne verktøyresultat** — Store verktøyresultat blir haldne utanfor den aktive modellkonteksten når det er mogleg. uag lagrar dei som Artifact og sender i staden ein avgrensa førehandsvising med ein stabil Artifact-referanse til modellen. Dette kan redusere talet på inndatatoken som trengst i dei neste rundane monaleg når eit verktøy lagar eit stort resultat.
> [Detaljert rettleiing for kontekstkomprimering](CONTEXT_COMPRESSION.nn.md)

## Rask start

**Python 3.11+**

```bash
python -m pip install --upgrade uag
uag
```

Den første oppstarten opnar oppsetjingsvegvisaren. Han hjelper deg å konfigurere ein leverandør og lagrar dei valde innstillingane
i det lokale miljøet ditt.

For dei vanlegaste funksjonsgruppene:

```bash
python -m pip install "uag[core,providers,tools]"
```

> Plattformintegrasjonar er valfrie. Installer berre det operativsystemet ditt treng; sjå

```text
> What files changed in this repository?
> Search the web for today's AI news and summarize the top five stories.
> :help
```

[Quickstart](QUICKSTART.md) · [Environment](ENVIRONMENT.md)

## Grensesnitt

| Grensesnitt | Kommando | Best for |
|---|---|---|
| **CLI** | `uag` | Raskt arbeid med tastaturet først |
| **Skrivebords-GUI** | `uagg` | Ei innebygd skrivebordsoppleving |
| **Nettgrensesnitt** | `uagw` | Tilgang frå nettlesaren |
| **A2A-tenar** | `uaga` | Kommunikasjon agent-til-agent |
| **VS Code** | Extension | Forklar, refaktorer, rett og bla i verktøy i redigeringsprogrammet |

Alle grensesnitta deler den same leverandørkonfigurasjonen, verktøyregisteret, tryggleiksreglane og øktdata.

~~~bash
# Desktop GUI
python -m pip install "uag[platform]"

# Web UI
python -m pip install "uag[web]" fastapi uvicorn
~~~

[Interface options](USAGE.md) · [Environment](ENVIRONMENT.md)

## Kva du kan byggje

Leverandøradapterar dekkjer vertsbaserte og lokale køyretider, mellom anna:

- Les, opprett, rediger, søk i, hash, arkiver og inspiser filer
- Gå gjennom Git-endringar, skann etter løyndommar, køyr testar, lint, kompiler og mål dekning
- Naviger i store kodebasar i Python, TypeScript, JavaScript, Go, Rust, C/C++, Java, C#, COBOL, VBA og andre språk
- Automatiser nettlesarar med Playwright, inkludert arbeidsflytar over fleire sider og nedlastingar

- **MCP** — kopla til eksterne verktøytenarar, inkludert tenester med OAuth
- **A2A** — samordna med andre agentar og kompatible tenarar
- **Cloud** — AWS-, Google Cloud- og Azure-API-tilgang med stadfesting for skriving
- **Communication** — Gmail, Bluesky, Discord, Microsoft Teams og pybitchat
- **IoT** — SwitchBot, ECHONET Lite, Matter, BACnet, Modbus TCP, OPC UA og UPnP
- **Media** — biletgenerering/-redigering, lydtranskripsjon/tale, kamerainnhenting og QR-kodar
- **Documents** — PDF, PowerPoint, Word, Excel, CSV, JSON, YAML, SQL og logganalyse

- **SwitchBot** — oppdaging i sky og via BLE, status, kontroll, batching og abonnement
- **ECHONET Lite** — oppdag og kontroller japanske hushaldningsapparat, inkludert INF-varslingar
- **Matter** — endepunkt, klynger, attributt, tilstandshistorikk, abonnement og kontroll
- **BACnet / Modbus TCP / OPC UA** — lesing, skriving, blaing og overvaking for industri- og bygningsautomasjon
- **UPnP** — einingsoppdaging, WAN-status og handtering av porttilordning på rutaren

### Kvar passar uag inn?

uag ligg mellom menneske og grensesnitt på den eine sida, og modellar, verktøy og system i den verkelege verda på den andre.
Det samordnar samtalen, vel funksjonar, handhevar tryggleiksreglar og held arbeidsflyten mogleg å ta opp att.

~~~mermaid
flowchart LR
    UI["CLI · Desktop · Web · VS Code · A2A"] --> UAG["UAG agent runtime"]
    UAG --> MODELS["Hosted & local models"]
    UAG --> TOOLS["Tools & extensions"]
    UAG --> STATE["Sessions & context"]
    TOOLS --> SYSTEMS["Files · Code · Web · MCP · Cloud · IoT"]
    POLICY["Confirmation · Credentials · Policy"] -.-> UAG
~~~

### Programtillegg, Agent Skills og marknadsplassar

Gjer uag til ein spesialisert agent utan å forke kjernen:

- Installer **Claude Code-kompatible programtillegg** frå ei mappe, ZIP, eit Git-repositorium, ei HTTP-kjelde eller ein marknadsplass
- Samle ferdigheiter, underagentar, MCP-tenarar, hooks, skråstrekkommandoar, utdataformat, avhengnader og kanalar
- Bla gjennom funksjonar frå fellesskapet på [SkillsMP](https://skillsmp.com) og [ClawHub](https://clawhub.ai)
- Legg til private organisasjonsferdigheiter og verktøy lokalt gjennom `UAGENT_EXTERNAL_TOOLS_DIR`

```text
:skills mp_search browser automation
:plugin list
:plugin install <source>
:plugin marketplace list
```

Sjå [Plugin Development Guide](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP_PLUGIN.md).

- **200+ verktøy** for filer, nett, medium, dokument, kode, sky, kommunikasjon og IoT
- **Dynamisk oppdaging og lasting** — bruk `tool_catalog` for å finne funksjonar og `tool_load` for å aktivere dei berre når det trengst
- **Kodeintelligens** — `code_map`, språkspesifikke `idx`-navigatorar, Git-gjennomgang, testkøyring, linting, kompilering og dekning
- **Claude Code-kompatible programtillegg** med ferdigheiter, agentar, MCP-tenarar, hooks, kommandoar og marknadsplassar
- **Agent Skills** frå SkillsMP og ClawHub
- **Eigendefinerte Python-verktøy** med `TOOL_SPEC` og `run_tool()`
- **Rust-baserte verktøy** for lette native-utvidingar

[Tool Creator Guide](../TOOL_CREATOR_GUIDE.md) · [MCP OAuth / Proxy Guide](MCP_OAUTH_PROXY_GUIDE.md)

## Bygd for verkelege arbeidsflytar

### 🧠 Kontekstmedvitne verktøyresultat

Store verktøyresultat blir haldne utanfor den aktive modellkonteksten når det er mogleg. uag lagrar dei som Artifact og sender i staden ein avgrensa førehandsvising med ein stabil Artifact-referanse til modellen. Dette kan redusere talet på inndatatoken som trengst i dei neste rundane monaleg når eit verktøy lagar eit stort resultat.

Ta opp att tidlegare samtalar med `:load <index>`. Verktøyresultat kan mellomlagrast, og leverandørar kan bytast
utan å byggje programmet på nytt.

[Context compression](CONTEXT_COMPRESSION.nn.md) · [Memory](MEMORY.md) · [Session portability](SESSION_PORTABILITY.md)

### Autopilot

Bruk `:auto` for arbeid over fleire rundar med ein valfri vurderingsmodell. Set ei grense for rundane med `--max-rounds N`.
Trykk **F12** for å stoppe autopiloten eller **F12** for å stoppe det gjeldande svaret.

Uavhengige skrivefrie operasjonar køyrer samtidig når det er trygt. Nettsøk, filinspeksjon,
analyse av repositorium og liknande arbeidsmengder kan fullførast parallelt med ein konfigurerbar arbeidarpool
(`UAGENT_PARALLEL_WORKERS`). Skriveoperasjonar blir serialiserte eller krev stadfesting.

Kontinuitet i økter, mellomlagring av verktøyresultat, batchtilstand, gjenoppretting etter omstart, DAG-planlegging og
orkestrering av fleire agentar gjer komplekst arbeid mogleg å ta opp att, i staden for at det berre kan gjerast éin gong.

[Auto-pilot](README_AUTO.md) · [Timers](SET_TIMER.md) · [Multi-agent runtime](MULTI_AGENT_RUNTIME.md)

### 🌍 Privat, fleirspråkleg og medvitent om reglar

`human_ask` set på pause før sensitive handlingar. Sletting av filer, overskrivingar, shell-kommandoar, einingskontrollar,
legitimasjonsoperasjonar og nettverksskriving kan styrast av stadfestings- og reglar.

Bruk legitimasjonslageret i staden for å leggje langvarige løyndommar i førespurnader:

Webgrensesnittet inkluderer OIDC-pålogging med Authorization Code + PKCE, verifiserte ID-token, server-side økter og tilgangskontrollar for prosjekt/rom. Verifiserte Microsoft Entra ID-gruppekrav kan gi katalogbasert tilgangspolicy når det er konfigurert. Windows Active Directory, OAuth og trusted-proxy-distribusjonar kan integrerast gjennom eksplisitte verifiserte identitetsadapterar; Windows AD krev ein distribusjonsspesifikk Kerberos/Negotiate-verifiserar og er ikkje aktivert som standard.

uag inkluderer opt-in, leverandør-nøytral OpenTelemetry-sporing og beregninger for Agent, LLM, Tool, Context, Memory og gjenfinningsoperasjoner. Observabilitet er deaktivert som standard.

Lokal-først tyder ikkje at UAG som standard fungerer heilt utan nett, eller at alle verktøy er isolerte. Kall til eksterne modellar og tilkopla tenester er avhengige av oppsettet.

- [Enterprise policies](ENTERPRISE_POLICY.md)
- [MXC sandbox](SANDBOX_MXC.md)
- [Remote Web / A2A](REMOTE_MXC_DEFAULT.md)
- [Web identity](WEB_IDENTITY_MEMORY.md)
- [OpenTelemetry](UAG_OPENTELEMETRY_DESIGN.md)

### 🌍 Fleirspråkleg omsetjing

- `translate_text` støttar Google Translate og det offisielle DeepL Python-klientbiblioteket gjennom `provider=auto`, `provider=deepl` eller `provider=google`.
- Verktøydefinisjonar finst på 37 språkvariantar i tillegg til engelsk (38 totalt), og plasshaldarar og tekniske identifikatorar blir bevarte.

Full-dupleks tale er tilgjengeleg gjennom OpenAI Realtime, Azure OpenAI, xAI Grok Voice, Gemini Live,
og Bedrock Nova Sonic, med valfri ekkofjerning med AEC3 og tryggleiksavgrensa funksjonskalling i sanntid.

[Translations](README.translations.md) · [IoT](IOT_USECASE.md) · [Communication](COMMUNICATION.md)

## Dokumentasjon

| Emne | Dokumentasjon |
|---|---|
| Miljøvariablar | [docs/ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/docs/ENVIRONMENT.md) |
| Arkitektur og invariantar | [docs/ARCHITECTURE.md](https://github.com/awaku7/agentcli/blob/main/docs/ARCHITECTURE.md) |
| Computer Use | [docs/COMPUTER_USE_IMPLEMENTATION.md](https://github.com/awaku7/agentcli/blob/main/docs/COMPUTER_USE_IMPLEMENTATION.md) |
| Repositorieverktøy | [docs/REPOSITORY_TOOLS.md](https://github.com/awaku7/agentcli/blob/main/docs/REPOSITORY_TOOLS.md) |
| IoT-brukstilfelle | [docs/IOT_USECASE.md](https://github.com/awaku7/agentcli/blob/main/docs/IOT_USECASE.md) |
| Kommunikasjonsverktøy | [docs/COMMUNICATION.md](https://github.com/awaku7/agentcli/blob/main/docs/COMMUNICATION.md) |
| Autopilot | [docs/README_AUTO.md](https://github.com/awaku7/agentcli/blob/main/docs/README_AUTO.md) |
| MCP OAuth / Proxy | [docs/MCP_OAUTH_PROXY_GUIDE.md](https://github.com/awaku7/agentcli/blob/main/docs/MCP_OAUTH_PROXY_GUIDE.md) |
| VS Code-utviding | [docs/VSCODE.md](https://github.com/awaku7/agentcli/blob/main/docs/VSCODE.md) |
| Utviklarrettleiing | [src/uagent/docs/DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md) |
| Verktøyflyt | [src/uagent/docs/TOOL_FLOW.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/TOOL_FLOW.md) |

[Quickstart](QUICKSTART.md) · [Architecture](ARCHITECTURE.md) · [Context management](UAG_CONTEXT_MANAGEMENT_DESIGN.md)

## Utvikling og bidrag

```bash
git clone https://github.com/awaku7/agentcli.git
cd agentcli
python -m pip install -e ".[core,providers,test]"
```

Køyr kontrollane før ein PR:

```bash
python -m ruff check src tests
python -m black --check src tests
python -m pytest -q .
```

Sjå [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md) for den fullstendige arbeidsflyten for utvikling.

Feilrapportar, funksjonsidéar, dokumentasjonsforbetringar, omsetjingar, verktøy, ferdigheiter og pull requests er velkomne.
Opne ei sak eller diskusjon før større endringar. Les [Developer Guide](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)
og køyr kontrollane ovanfor før du sender inn ein pull request.

## Lisens

Lisensiert under [Apache License 2.0](https://github.com/awaku7/agentcli/blob/main/LICENSE).
