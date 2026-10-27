<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="680">
</p>

<h1 align="center">uag</h1>

<p align="center">
  <strong>Universal AI Gateway</strong><br>
  Isang lokal na agent. Anumang modelo. Anumang tool. Iyong environment, iyong mga panuntunan.
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

**Bakit uag?**

Ang uag ay isang AI agent na inuuna ang lokal na pagpapatakbo at nag-uugnay sa modelong gusto mo sa mga tool na aktuwal mong ginagamit.
Nagbibigay ito sa iyo ng iisang runtime na napapalawak para sa mga file, browser, codebase, komunikasyon, cloud API,
IoT device, MCP server, at mga workflow na may maraming agent.

- **Kalayaan sa provider** — OpenAI, Anthropic, Gemini, Azure, Bedrock, Ollama, llama.cpp, Grok, DeepSeek, at iba pa.
- **Lokal muna ang pagpapatakbo** — nananatili sa iyong makina ang runtime ng agent at pagpapatakbo ng tool; ang mga API call lamang na pinili mo ang lumalabas dito.
- **Iisang layer ng tool** — gumagana ang parehong mga tool mula sa CLI, desktop GUI, web UI, VS Code, at A2A.
- **Dinisenyo para sa parallel na pagpapatakbo** — maaaring sabay-sabay na tumakbo ang mga magkakahiwalay na read-only operation.
- **Napapalawak** — magdagdag ng mga tool, plugin, Agent Skills, MCP server, at tool na nakabase sa Rust nang hindi binabago ang core.
- **May kamalayan sa kaligtasan** — sinusuportahan ng mga mapanirang aksyon, credential, kontrol ng device, at network write ang tahasang kumpirmasyon at mga kontrol ng patakaran.

> **Sa madaling sabi:** ang uag ang control plane sa pagitan ng iyong mga AI model at ng iyong aktuwal na environment.

> **🧠 Mga resulta ng tool na may kamalayan sa konteksto** — Ang malalaking resulta ng tool ay hindi isinasama sa konteksto ng aktibong modelo kapag posible. Ina-store ng uag ang mga ito bilang Artifacts at ipinapasa sa modelo ang isang may hangganang preview na may matatag na Artifact reference. Maaari nitong lubos na mabawasan ang bilang ng mga input token na kailangan para sa mga kasunod na turn kapag gumawa ang tool ng malaking resulta.
> [Detalyadong gabay sa pag-compress ng konteksto](CONTEXT_COMPRESSION.fil.md)

## Mabilis na pagsisimula

**Python 3.11+**

```bash
python -m pip install --upgrade uag
uag
```

Sa unang paglunsad, bubukas ang setup wizard. Tinutulungan ka nitong mag-configure ng provider at sine-save ang napiling setting
sa iyong lokal na environment.

Para sa mga karaniwang feature group:

```bash
python -m pip install "uag[core,providers,tools]"
```

> Opsyonal ang mga platform integration. I-install lamang ang kailangan ng iyong operating system; tingnan ang

```text
> What files changed in this repository?
> Search the web for today's AI news and summarize the top five stories.
> :help
```

[Quickstart](QUICKSTART.md) · [Environment](ENVIRONMENT.md)

## Mga interface

| Interface | Command | Pinakamainam para sa |
|---|---|---|
| **CLI** | `uag` | Mabilis na gawaing keyboard-first |
| **Desktop GUI** | `uagg` | Native desktop experience |
| **Web UI** | `uagw` | Access na nakabatay sa browser |
| **A2A server** | `uaga` | Komunikasyon ng agent sa agent |
| **VS Code** | Extension | Pagpapaliwanag, refactor, pag-aayos, at pag-browse ng tool sa editor |

Pare-pareho ang provider configuration, tool registry, safety rule, at session data na ginagamit ng lahat ng interface.

~~~bash
# Desktop GUI
python -m pip install "uag[platform]"

# Web UI
python -m pip install "uag[web]" fastapi uvicorn
~~~

[Interface options](USAGE.md) · [Environment](ENVIRONMENT.md)

## Ano ang maaari mong buuin

Sinasaklaw ng mga provider adapter ang hosted at lokal na runtime, kabilang ang:

**OpenAI · Anthropic · Gemini · Vertex AI · Azure OpenAI · Amazon Bedrock · Grok · DeepSeek · OpenRouter · Ollama · llama.cpp · LM Studio**

- Magbasa, lumikha, mag-edit, maghanap, mag-hash, mag-archive, at magsuri ng mga file
- Suriin ang mga pagbabago sa Git, mag-scan para sa secret, magpatakbo ng test, mag-lint, mag-compile, at magsukat ng coverage
- Mag-navigate sa malalaking Python, TypeScript, JavaScript, Go, Rust, C/C++, Java, C#, COBOL, VBA, at iba pang codebase
- I-automate ang browser gamit ang Playwright, kabilang ang multi-page workflow at download

- **MCP** — kumonekta sa mga external tool server, kabilang ang mga serbisyong may OAuth
- **A2A** — makipag-ugnayan sa ibang agent at compatible na server
- **Cloud** — access sa AWS, Google Cloud, at Azure API na may kumpirmasyon para sa write
- **Communication** — Gmail, Bluesky, Discord, Microsoft Teams, at pybitchat
- **IoT** — SwitchBot, ECHONET Lite, Matter, BACnet, Modbus TCP, OPC UA, at UPnP
- **Media** — pagbuo/pag-edit ng larawan, transcription/pagsasalita ng audio, pagkuha ng camera, at QR code
- **Documents** — pagsusuri ng PDF, PowerPoint, Word, Excel, CSV, JSON, YAML, SQL, at log

- **SwitchBot** — Cloud at BLE discovery, status, control, batching, at subscription
- **ECHONET Lite** — tumuklas at kumontrol ng mga appliance sa tahanan sa Japan, kabilang ang INF notification
- **Matter** — endpoint, cluster, attribute, history ng state, subscription, at control
- **BACnet / Modbus TCP / OPC UA** — pagbasa, pagsulat, pag-browse, at monitoring para sa industrial at building automation
- **UPnP** — pagtuklas ng device, WAN status, at pamamahala ng port mapping ng router

### Saan nababagay ang uag

Nasa pagitan ang uag ng mga tao at interface sa isang panig, at ng mga model, tool, at sistema sa totoong mundo sa kabilang panig.
Itinatalaga nito ang pag-uusap, pinipili ang mga kakayahan, ipinapatupad ang mga panuntunang pangkaligtasan, at pinananatiling maipagpapatuloy ang workflow.

~~~mermaid
flowchart LR
    UI["CLI · Desktop · Web · VS Code · A2A"] --> UAG["UAG agent runtime"]
    UAG --> MODELS["Hosted & local models"]
    UAG --> TOOLS["Tools & extensions"]
    UAG --> STATE["Sessions & context"]
    TOOLS --> SYSTEMS["Files · Code · Web · MCP · Cloud · IoT"]
    POLICY["Confirmation · Credentials · Policy"] -.-> UAG
~~~

### Mga plugin, Agent Skills, at marketplace

Gawing espesyalistang agent ang uag nang hindi bina-bifurcate ang core:

- Mag-install ng **mga plugin na compatible sa Claude Code** mula sa directory, ZIP, Git repository, HTTP source, o marketplace
- Mag-bundle ng skill, sub-agent, MCP server, hook, slash command, output style, dependency, at channel
- Mag-browse ng mga kakayahan ng komunidad mula sa [SkillsMP](https://skillsmp.com) at [ClawHub](https://clawhub.ai)
- Magdagdag ng pribadong skill at tool ng organisasyon nang lokal sa pamamagitan ng `UAGENT_EXTERNAL_TOOLS_DIR`

```text
:skills mp_search browser automation
:plugin list
:plugin install <source>
:plugin marketplace list
```

Tingnan ang [Plugin Development Guide](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP_PLUGIN.md).

- **200+ tool** para sa file, web, media, dokumento, code, cloud, komunikasyon, at IoT
- **Dynamic na pagtuklas at pag-load** — gamitin ang `tool_catalog` upang maghanap ng mga kakayahan at ang `tool_load` upang paganahin lamang ang mga ito kung kinakailangan
- **Code intelligence** — `code_map`, mga navigator na `idx` na partikular sa wika, pagsusuri ng Git, pagpapatakbo ng test, linting, compilation, at coverage
- **Mga plugin na compatible sa Claude Code** na may skill, agent, MCP server, hook, command, at marketplace
- **Agent Skills** mula sa SkillsMP at ClawHub
- **Mga custom na Python tool** gamit ang `TOOL_SPEC` at `run_tool()`
- **Mga tool na nakabase sa Rust** para sa magagaan na native extension

[Tool Creator Guide](../TOOL_CREATOR_GUIDE.md) · [MCP OAuth / Proxy Guide](MCP_OAUTH_PROXY_GUIDE.md)

## Ginawa para sa totoong mga daloy ng trabaho

### 🧠 Mga resulta ng tool na may kamalayan sa konteksto

Ang malalaking resulta ng tool ay hindi isinasama sa konteksto ng aktibong modelo kapag posible. Ina-store ng uag ang mga ito bilang Artifacts at ipinapasa sa modelo ang isang may hangganang preview na may matatag na Artifact reference. Maaari nitong lubos na mabawasan ang bilang ng mga input token na kailangan para sa mga kasunod na turn kapag gumawa ang tool ng malaking resulta.

Ipagpatuloy ang mga nakaraang pag-uusap gamit ang `:load <index>`. Maaaring i-cache ang mga resulta ng tool, at maaaring magpalit ng provider
nang hindi muling binubuo ang application.

[Context compression](CONTEXT_COMPRESSION.fil.md) · [Memory](MEMORY.md) · [Session portability](SESSION_PORTABILITY.md)

### Auto-pilot

Gamitin ang `:auto` para sa multi-round na gawain na may opsyonal na reviewer model. Magtakda ng limitasyon ng round gamit ang `--max-rounds N`.
Pindutin ang **F12** upang ihinto ang auto-pilot o ang **F12** upang ihinto ang kasalukuyang response.

Sabay-sabay na tumatakbo ang magkakahiwalay na read-only operation kapag ligtas ito. Maaaring makumpleto nang parallel ang mga web search, inspeksyon ng file,
pagsusuri ng repository, at katulad na workload gamit ang worker pool na nako-configure
(`UAGENT_PARALLEL_WORKERS`). Nananatiling serialized ang mga write operation o nangangailangan ng kumpirmasyon.

Ginagawang maipagpapatuloy ang kumplikadong gawain sa halip na one-shot ng continuity ng session, pag-cache ng resulta ng tool,
batch state, recovery pagkatapos ng restart, DAG scheduling, at orchestration ng maraming agent.

[Auto-pilot](README_AUTO.md) · [Timers](SET_TIMER.md) · [Multi-agent runtime](MULTI_AGENT_RUNTIME.md)

### 🌍 Pribado, maraming wika, at may kamalayan sa patakaran

Humihinto ang `human_ask` bago ang sensitibong aksyon. Maaaring pamahalaan ng mga panuntunan sa kumpirmasyon at patakaran ang pagbura ng file, pag-overwrite,
shell command, kontrol ng device, operasyon sa credential, at network write.

Gamitin ang credential store sa halip na maglagay ng pangmatagalang secret sa prompt:

Kasama sa Web UI ang OIDC sign-in gamit ang Authorization Code + PKCE, mga na-verify na ID token, mga session sa server-side, at mga kontrol sa access ng proyekto/room. Ang mga na-verify na Microsoft Entra ID group claims ay maaaring magbigay ng directory-backed access policy kapag naka-configure. Maaaring mag-integrate ang Windows Active Directory, OAuth, at trusted-proxy deployments sa pamamagitan ng mga explicit na verified identity adapters; nangangailangan ang Windows AD ng deployment-specific na Kerberos/Negotiate verifier at hindi ito naka-enable bilang default.

Kasama sa uag ang pag-opt-in, provider-neutral na OpenTelemetry na pagsubaybay at mga sukatan para sa Agent, LLM, tool, Context, Memory, at mga operasyon sa pagkuha. Ang Observability ay hindi pinagana bilang default.

Ang local-first ay hindi nangangahulugang ganap na offline o nakahiwalay ang lahat ng tool bilang default. Nakadepende sa configuration ang mga tawag sa mga panlabas na modelo at nakakonektang serbisyo.

- [Enterprise policies](ENTERPRISE_POLICY.md)
- [MXC sandbox](SANDBOX_MXC.md)
- [Remote Web / A2A](REMOTE_MXC_DEFAULT.md)
- [Web identity](WEB_IDENTITY_MEMORY.md)
- [OpenTelemetry](UAG_OPENTELEMETRY_DESIGN.md)

### 🌍 Multilingual na pagsasalin

- Sinusuportahan ng `translate_text` ang Google Translate at ang opisyal na DeepL Python client sa pamamagitan ng `provider=auto`, `provider=deepl`, o `provider=google`.
- Magagamit ang mga kahulugan ng tool sa 37 na lokalidad at Ingles (38 kabuuan), na pinananatili ang mga placeholder at teknikal na identifier.

Available ang full-duplex voice sa pamamagitan ng OpenAI Realtime, Azure OpenAI, xAI Grok Voice, Gemini Live,
at Bedrock Nova Sonic, na may opsyonal na AEC3 echo cancellation at realtime function calling na may limitasyong pangkaligtasan.

[Translations](README.translations.md) · [IoT](IOT_USECASE.md) · [Communication](COMMUNICATION.md)

## Dokumentasyon

| Paksa | Dokumentasyon |
|---|---|
| Environment variables | [docs/ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/docs/ENVIRONMENT.md) |
| Architecture at invariant | [docs/ARCHITECTURE.md](https://github.com/awaku7/agentcli/blob/main/docs/ARCHITECTURE.md) |
| Computer Use | [docs/COMPUTER_USE_IMPLEMENTATION.md](https://github.com/awaku7/agentcli/blob/main/docs/COMPUTER_USE_IMPLEMENTATION.md) |
| Repository tools | [docs/REPOSITORY_TOOLS.md](https://github.com/awaku7/agentcli/blob/main/docs/REPOSITORY_TOOLS.md) |
| Mga gamit sa IoT | [docs/IOT_USECASE.md](https://github.com/awaku7/agentcli/blob/main/docs/IOT_USECASE.md) |
| Mga tool sa komunikasyon | [docs/COMMUNICATION.md](https://github.com/awaku7/agentcli/blob/main/docs/COMMUNICATION.md) |
| Auto-pilot | [docs/README_AUTO.md](https://github.com/awaku7/agentcli/blob/main/docs/README_AUTO.md) |
| MCP OAuth / Proxy | [docs/MCP_OAUTH_PROXY_GUIDE.md](https://github.com/awaku7/agentcli/blob/main/docs/MCP_OAUTH_PROXY_GUIDE.md) |
| VS Code extension | [docs/VSCODE.md](https://github.com/awaku7/agentcli/blob/main/docs/VSCODE.md) |
| Gabay para sa developer | [src/uagent/docs/DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md) |
| Daloy ng tool | [src/uagent/docs/TOOL_FLOW.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/TOOL_FLOW.md) |

[Quickstart](QUICKSTART.md) · [Architecture](ARCHITECTURE.md) · [Context management](UAG_CONTEXT_MANAGEMENT_DESIGN.md)

## Pagbuo at pag-aambag

```bash
git clone https://github.com/awaku7/agentcli.git
cd agentcli
python -m pip install -e ".[core,providers,test]"
```

Patakbuhin ang mga pagsusuri bago ang PR:

```bash
python -m ruff check src tests
python -m black --check src tests
python -m pytest -q .
```

Para sa buong workflow ng development, tingnan ang [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md).

Malugod na tinatanggap ang mga ulat ng bug, ideya sa feature, pagpapahusay ng dokumentasyon, translation, tool, skill, at pull request.
Mangyaring magbukas ng issue o discussion bago ang malalaking pagbabago. Basahin ang [Developer Guide](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)
at patakbuhin ang mga pagsusuri sa itaas bago magsumite ng pull request.

## Lisensya

Lisensyado sa ilalim ng [Apache License 2.0](https://github.com/awaku7/agentcli/blob/main/LICENSE).
