<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="680">
</p>

<h1 align="center">uag</h1>

<p align="center">
  <strong>Universal AI Gateway</strong><br>
  En lokal agent. Vilken modell som helst. Vilket verktyg som helst. Din miljö, dina regler.
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
  <a href="https://github.com/awaku7/agentcli/discussions">Diskussioner</a> ·
  <a href="https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md">Översättningar</a>
</p>

______________________________________________________________________

**Varför uag?**

uag är en lokal-först AI-agent som ansluter den modell du föredrar till de verktyg du faktiskt använder.
Den ger dig en enda, utbyggbar körmiljö för filer, webbläsare, kodbaser, kommunikation, moln-API:er,
IoT-enheter, MCP-servrar och arbetsflöden med flera agenter.

- **Frihet att välja leverantör** — OpenAI, Anthropic, Gemini, Azure, Bedrock, Ollama, llama.cpp, Grok, DeepSeek med flera.
- **Lokal-först-körning** — din agentkörmiljö och verktygskörning stannar på din dator; endast de API-anrop du väljer lämnar den.
- **Ett verktygslager** — samma verktyg fungerar från CLI, skrivbordsgränssnittet, webbgränssnittet, VS Code och A2A.
- **Parallell från grunden** — oberoende skrivskyddade åtgärder kan köras samtidigt.
- **Utbyggbar** — lägg till verktyg, plugin-program, Agent Skills, MCP-servrar och Rust-baserade verktyg utan att ändra kärnan.
- **Säkerhetsmedveten** — destruktiva åtgärder, autentiseringsuppgifter, enhetsstyrning och nätverksskrivningar stöder uttrycklig bekräftelse och policykontroller.

> **Kort sagt:** uag är kontrollplanet mellan dina AI-modeller och din verkliga miljö.

> **🧠 Kontextmedvetna verktygsresultat** — Stora verktygsresultat hålls utanför den aktiva modellkontexten när det är möjligt. uag lagrar dem som artefakter och skickar istället en avgränsad förhandsvisning med en stabil Artifact-referens till modellen. Detta kan avsevärt minska antalet inmatningstoken som krävs för efterföljande turer när ett verktyg genererar ett stort resultat.
> [Detaljerad guide till kontextkomprimering](CONTEXT_COMPRESSION.sv.md)

## Snabbstart

**Python 3.11+**

```bash
python -m pip install --upgrade uag
uag
```

Vid den första starten öppnas installationsguiden. Den hjälper dig att konfigurera en leverantör och sparar de valda inställningarna
i din lokala miljö.

För de vanligaste funktionsgrupperna:

```bash
python -m pip install "uag[core,providers,tools]"
```

> Plattformsspecifika integrationer är valfria. Installera endast det som ditt operativsystem behöver; se

```text
> What files changed in this repository?
> Search the web for today's AI news and summarize the top five stories.
> :help
```

[Quickstart](QUICKSTART.md) · [Environment](ENVIRONMENT.md)

## Gränssnitt

| Gränssnitt | Kommando | Bäst för |
|---|---|---|
| **CLI** | `uag` | Snabbt, tangentbordsfokuserat arbete |
| **Skrivbordsgränssnitt** | `uagg` | En inbyggd skrivbordsupplevelse |
| **Webbgränssnitt** | `uagw` | Webbläsarbaserad åtkomst |
| **A2A-server** | `uaga` | Kommunikation agent-till-agent |
| **VS Code** | Extension | Förklara, omstrukturera, åtgärda och bläddra bland verktyg i editorn |

Alla gränssnitt delar samma leverantörskonfiguration, verktygsregister, säkerhetsregler och sessionsdata.

~~~bash
# Desktop GUI
python -m pip install "uag[platform]"

# Web UI
python -m pip install "uag[web]" fastapi uvicorn
~~~

[Interface options](USAGE.md) · [Environment](ENVIRONMENT.md)

## Vad du kan bygga

Leverantörsadaptrar täcker värdbaserade och lokala körmiljöer, bland annat:

**OpenAI · Anthropic · Gemini · Vertex AI · Azure OpenAI · Amazon Bedrock · Grok · DeepSeek · OpenRouter · Ollama · llama.cpp · LM Studio**

- Läsa, skapa, redigera, söka i, hasha, arkivera och inspektera filer
- Granska Git-ändringar, söka efter hemligheter, köra tester, lintning, kompilera och mäta täckning
- Navigera i stora kodbaser i Python, TypeScript, JavaScript, Go, Rust, C/C++, Java, C#, COBOL, VBA och andra språk
- Automatisera webbläsare med Playwright, inklusive flersidiga arbetsflöden och nedladdningar

- **MCP** — anslut externa verktygsservrar, inklusive OAuth-aktiverade tjänster
- **A2A** — samordna med andra agenter och kompatibla servrar
- **Moln** — AWS-, Google Cloud- och Azure-API-åtkomst med bekräftelse för skrivningar
- **Kommunikation** — Gmail, Bluesky, Discord, Microsoft Teams och pybitchat
- **IoT** — SwitchBot, ECHONET Lite, Matter, BACnet, Modbus TCP, OPC UA och UPnP
- **Media** — bildgenerering/redigering, ljudtranskribering/tal, kamerafångst och QR-koder
- **Dokument** — PDF, PowerPoint, Word, Excel, CSV, JSON, YAML, SQL och logganalys

- **SwitchBot** — moln- och BLE-upptäckt, status, styrning, batchbearbetning och prenumerationer
- **ECHONET Lite** — upptäck och styr japanska hushållsapparater, inklusive INF-aviseringar
- **Matter** — slutpunkter, kluster, attribut, historik för tillstånd, prenumerationer och styrning
- **BACnet / Modbus TCP / OPC UA** — läsning, skrivning, bläddring och övervakning för industri- och byggnadsautomation
- **UPnP** — enhetsupptäckt, WAN-status och hantering av routerns portmappning

### Var passar uag in?

uag ligger mellan människor och gränssnitt på ena sidan och modeller, verktyg och verkliga system på den andra.
Den samordnar konversationen, väljer funktioner, tillämpar säkerhetsregler och håller arbetsflödet återupptagbart.

~~~mermaid
flowchart LR
    UI["CLI · Desktop · Web · VS Code · A2A"] --> UAG["UAG agent runtime"]
    UAG --> MODELS["Hosted & local models"]
    UAG --> TOOLS["Tools & extensions"]
    UAG --> STATE["Sessions & context"]
    TOOLS --> SYSTEMS["Files · Code · Web · MCP · Cloud · IoT"]
    POLICY["Confirmation · Credentials · Policy"] -.-> UAG
~~~

### Plugin-program, Agent Skills och marknadsplatser

Gör uag till en specialiserad agent utan att skapa en fork av kärnan:

- Installera **Claude Code-kompatibla plugin-program** från en katalog, ZIP-fil, Git-repositorium, HTTP-källa eller marknadsplats
- Paketera färdigheter, underagenter, MCP-servrar, hooks, snedstreckskommandon, utmatningsstilar, beroenden och kanaler
- Bläddra bland community-funktioner från [SkillsMP](https://skillsmp.com) och [ClawHub](https://clawhub.ai)
- Lägg till privata organisationsfärdigheter och verktyg lokalt via `UAGENT_EXTERNAL_TOOLS_DIR`

```text
:skills mp_search browser automation
:plugin list
:plugin install <source>
:plugin marketplace list
```

Se [Plugin Development Guide](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP_PLUGIN.md).

- **200+ verktyg** för filer, webben, media, dokument, kod, moln, kommunikation och IoT
- **Dynamisk upptäckt och inläsning** — använd `tool_catalog` för att hitta funktioner och `tool_load` för att aktivera dem endast vid behov
- **Kodintelligens** — `code_map`, språkspecifika `idx`-navigatorer, Git-granskning, testkörning, lintning, kompilering och täckning
- **Claude Code-kompatibla plugin-program** med färdigheter, agenter, MCP-servrar, hooks, kommandon och marknadsplatser
- **Agent Skills** från SkillsMP och ClawHub
- **Anpassade Python-verktyg** med `TOOL_SPEC` och `run_tool()`
- **Rust-baserade verktyg** för lätta inbyggda tillägg

[Tool Creator Guide](../TOOL_CREATOR_GUIDE.md) · [MCP OAuth / Proxy Guide](MCP_OAUTH_PROXY_GUIDE.md)

## Byggt för verkliga arbetsflöden

### 🧠 Kontextmedvetna verktygsresultat

Stora verktygsresultat hålls utanför den aktiva modellkontexten när det är möjligt. uag lagrar dem som artefakter och skickar istället en avgränsad förhandsvisning med en stabil Artifact-referens till modellen. Detta kan avsevärt minska antalet inmatningstoken som krävs för efterföljande turer när ett verktyg genererar ett stort resultat.

Återuppta tidigare konversationer med `:load <index>`. Verktygsresultat kan cachelagras och leverantörer kan bytas
utan att programmet behöver byggas om.

[Context compression](CONTEXT_COMPRESSION.sv.md) · [Memory](MEMORY.md) · [Session portability](SESSION_PORTABILITY.md)

### Autopilot

Använd `:auto` för arbete i flera omgångar med en valfri granskningsmodell. Ange en gräns för antalet omgångar med `--max-rounds N`.
Tryck på **F12** för att stoppa autopiloten eller **F12** för att stoppa det aktuella svaret.

Oberoende skrivskyddade åtgärder körs samtidigt när det är säkert. Webbsökningar, filinspektion,
analys av kodarkiv och liknande arbetsbelastningar kan slutföras parallellt med en konfigurerbar arbetarpool
(`UAGENT_PARALLEL_WORKERS`). Skrivåtgärder förblir sekventiella eller kräver bekräftelse.

Sessionskontinuitet, cachelagring av verktygsresultat, batchtillstånd, återställning efter omstart, DAG-schemaläggning och
orkestrering av flera agenter gör komplext arbete återupptagbart i stället för engångsbaserat.

[Auto-pilot](README_AUTO.md) · [Timers](SET_TIMER.md) · [Multi-agent runtime](MULTI_AGENT_RUNTIME.md)

### 🌍 Privat, flerspråkig och policy-medveten

`human_ask` pausar före känsliga åtgärder. Filradering, överskrivningar, skal-kommandon, enhetsstyrning,
hantering av autentiseringsuppgifter och nätverksskrivningar kan styras av bekräftelse- och policyregler.

Använd lagret för autentiseringsuppgifter i stället för att placera långlivade hemligheter i promptar:

Webbgränssnittet inkluderar OIDC-inloggning med Authorization Code + PKCE, verifierade ID-token, serversessioner och åtkomstkontroller för projekt/rum. Verifierade Microsoft Entra ID-gruppanspråk kan användas för katalogbaserad åtkomstpolicy när det är konfigurerat. Distributioner av Windows Active Directory, OAuth och trusted-proxy kan integreras via explicita verifierade identitetsadaptrar; Windows AD kräver en distributionsspecifik Kerberos/Negotiate-verifierare och är inte aktiverat som standard.

uag inkluderar opt-in, leverantörsneutral OpenTelemetry-spårning och mätvärden för Agent, LLM, verktyg, Context, Memory och hämtning. Observerbarhet är inaktiverat som standard.

Local-first innebär inte att UAG som standard fungerar helt offline eller att alla verktyg körs isolerat. Anrop till externa modeller och anslutna tjänster beror på konfigurationen.

- [Enterprise policies](ENTERPRISE_POLICY.md)
- [MXC sandbox](SANDBOX_MXC.md)
- [Remote Web / A2A](REMOTE_MXC_DEFAULT.md)
- [Web identity](WEB_IDENTITY_MEMORY.md)
- [OpenTelemetry](UAG_OPENTELEMETRY_DESIGN.md)

### 🌍 Flerspråkig översättning

- `translate_text` stöder Google Translate och den officiella DeepL-klienten för Python via `provider=auto`, `provider=deepl` eller `provider=google`.
- Verktygsdefinitioner finns tillgängliga på 37 språk samt engelska (totalt 38), där platshållare och tekniska identifierare bevaras.

Full duplex-röst är tillgänglig via OpenAI Realtime, Azure OpenAI, xAI Grok Voice, Gemini Live
och Bedrock Nova Sonic, med valfri AEC3-ekokancellering och säkerhetsbegränsade funktionsanrop i realtid.

[Translations](README.translations.md) · [IoT](IOT_USECASE.md) · [Communication](COMMUNICATION.md)

## Dokumentation

| Ämne | Dokumentation |
|---|---|
| Miljövariabler | [docs/ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/docs/ENVIRONMENT.md) |
| Arkitektur och invariansvillkor | [docs/ARCHITECTURE.md](https://github.com/awaku7/agentcli/blob/main/docs/ARCHITECTURE.md) |
| Computer Use | [docs/COMPUTER_USE_IMPLEMENTATION.md](https://github.com/awaku7/agentcli/blob/main/docs/COMPUTER_USE_IMPLEMENTATION.md) |
| Repositoriets verktyg | [docs/REPOSITORY_TOOLS.md](https://github.com/awaku7/agentcli/blob/main/docs/REPOSITORY_TOOLS.md) |
| IoT-användningsfall | [docs/IOT_USECASE.md](https://github.com/awaku7/agentcli/blob/main/docs/IOT_USECASE.md) |
| Kommunikationsverktyg | [docs/COMMUNICATION.md](https://github.com/awaku7/agentcli/blob/main/docs/COMMUNICATION.md) |
| Autopilot | [docs/README_AUTO.md](https://github.com/awaku7/agentcli/blob/main/docs/README_AUTO.md) |
| MCP OAuth / Proxy | [docs/MCP_OAUTH_PROXY_GUIDE.md](https://github.com/awaku7/agentcli/blob/main/docs/MCP_OAUTH_PROXY_GUIDE.md) |
| VS Code-tillägg | [docs/VSCODE.md](https://github.com/awaku7/agentcli/blob/main/docs/VSCODE.md) |
| Utvecklarguide | [src/uagent/docs/DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md) |
| Verktygsflöde | [src/uagent/docs/TOOL_FLOW.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/TOOL_FLOW.md) |

[Quickstart](QUICKSTART.md) · [Architecture](ARCHITECTURE.md) · [Context management](UAG_CONTEXT_MANAGEMENT_DESIGN.md)

## Utveckling och bidrag

```bash
git clone https://github.com/awaku7/agentcli.git
cd agentcli
python -m pip install -e ".[core,providers,test]"
```

Kör kontrollerna före en PR:

```bash
python -m ruff check src tests
python -m black --check src tests
python -m pytest -q .
```

För det fullständiga utvecklingsarbetsflödet, se [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md).

Felrapporter, funktionsidéer, dokumentationsförbättringar, översättningar, verktyg, färdigheter och pull requests är välkomna.
Öppna gärna ett issue eller en diskussion före större ändringar. Läs [Developer Guide](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)
och kör kontrollerna ovan innan du skickar in en pull request.

## Licens

Licensierad under [Apache License 2.0](https://github.com/awaku7/agentcli/blob/main/LICENSE).
