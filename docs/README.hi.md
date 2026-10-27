<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="680">
</p>

<h1 align="center">uag</h1>

<p align="center">
  <strong>Universal AI Gateway</strong><br>
  एक स्थानीय एजेंट। कोई भी मॉडल। कोई भी टूल। आपका वातावरण, आपके नियम।
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

**uag क्यों?**

uag एक local-first AI एजेंट है, जो आपके पसंदीदा मॉडल को उन टूल्स से जोड़ता है जिनका आप वास्तव में उपयोग करते हैं।
यह फ़ाइलों, ब्राउज़र, कोडबेस, संचार, cloud APIs, IoT devices, MCP servers और multi-agent workflows के लिए एकल, विस्तार योग्य runtime प्रदान करता है।

- **Provider की स्वतंत्रता** — OpenAI, Anthropic, Gemini, Azure, Bedrock, Ollama, llama.cpp, Grok, DeepSeek और अन्य।
- **Local-first execution** — आपका एजेंट runtime और tool execution आपकी मशीन पर ही रहता है; केवल आपके चुने हुए API calls ही बाहर जाते हैं।
- **एक tool layer** — वही टूल CLI, desktop GUI, web UI, VS Code और A2A से काम करते हैं।
- **डिज़ाइन से parallel** — स्वतंत्र read-only operations एक साथ चल सकते हैं।
- **विस्तार योग्य** — core बदले बिना tools, plugins, Agent Skills, MCP servers और Rust-backed tools जोड़ें।
- **सुरक्षा-सचेत** — विनाशकारी कार्रवाइयों, credentials, device controls और network writes के लिए स्पष्ट confirmation और policy controls उपलब्ध हैं।

> **संक्षेप में:** uag आपके AI models और वास्तविक environment के बीच control plane है।

> **🧠 संदर्भ-जागरूक टूल परिणाम** — जब संभव हो, बड़े टूल परिणाम सक्रिय मॉडल संदर्भ से बाहर रखे जाते हैं। uag इन्हें आर्टिफैक्ट्स के रूप में संग्रहीत करता है और मॉडल को एक स्थिर Artifact संदर्भ के साथ एक सीमित पूर्वावलोकन भेजता है। जब कोई टूल बड़ा परिणाम उत्पन्न करता है, तो इससे फॉलो-अप टर्न के लिए आवश्यक इनपुट टोकन की संख्या काफी कम हो सकती है।
> [संदर्भ संपीड़न की विस्तृत मार्गदर्शिका](CONTEXT_COMPRESSION.hi.md)

## त्वरित शुरुआत

**Python 3.11+**

```bash
python -m pip install --upgrade uag
uag
```

पहली बार launch करने पर setup wizard खुलता है। यह provider configure करने में सहायता करता है और चयनित settings
आपके local environment में संग्रहीत करता है।

सामान्य feature groups के लिए:

```bash
python -m pip install "uag[core,providers,tools]"
```

```text
> What files changed in this repository?
> Search the web for today's AI news and summarize the top five stories.
> :help
```

[Quickstart](QUICKSTART.md) · [Environment](ENVIRONMENT.md)

## Interfaces

| Interface | Command | Best for |
|---|---|---|
| **CLI** | `uag` | तेज़, keyboard-first कार्य |
| **Desktop GUI** | `uagg` | Native desktop अनुभव |
| **Web UI** | `uagw` | Browser-based access |
| **A2A server** | `uaga` | Agent-to-agent communication |
| **VS Code** | Extension | Editor में tools को explain, refactor, fix और browse करना |

सभी interfaces समान provider configuration, tool registry, safety rules और session data साझा करते हैं।

~~~bash
# Desktop GUI
python -m pip install "uag[platform]"

# Web UI
python -m pip install "uag[web]" fastapi uvicorn
~~~

[Interface options](USAGE.md) · [Environment](ENVIRONMENT.md)

## आप क्या बना सकते हैं

Provider adapters hosted और local runtimes को support करते हैं, जिनमें शामिल हैं:

**OpenAI · Meta Model API · Anthropic · Google Gemini · Vertex AI · Azure OpenAI · Amazon Bedrock · OpenRouter · Ollama · llama.cpp · Grok · DeepSeek · NVIDIA · Hugging Face · Alibaba Cloud · Moonshot · Xiaomi MiMo · LM Studio · MiniMax · Sakana AI · SAKURA AI Engine · Together AI · Vercel AI Gateway · PFN/PLaMo · Z.AI · Novita**

`UAGENT_PROVIDER` से providers बदलें; आपके tools और interface नहीं बदलते।

**अपने environment के साथ काम करें**

- Files को read, create, edit, search, hash, archive और inspect करें
- Git changes की समीक्षा करें, secrets scan करें, tests चलाएँ, lint और compile करें तथा coverage मापें
- बड़े Python, TypeScript, JavaScript, Go, Rust, C/C++, Java, C#, COBOL, VBA और अन्य codebases में navigate करें
- Playwright से browsers automate करें, जिसमें multi-page workflows और downloads शामिल हैं

**Services और devices कनेक्ट करें**

- **MCP** — external tool servers कनेक्ट करें, जिनमें OAuth-enabled services भी शामिल हैं
- **A2A** — अन्य agents और compatible servers के साथ समन्वय करें
- **Cloud** — AWS, Google Cloud और Azure API access, writes के लिए confirmation के साथ
- **Communication** — Gmail, Bluesky, Discord, Microsoft Teams और pybitchat
- **IoT** — SwitchBot, ECHONET Lite, Matter, BACnet, Modbus TCP, OPC UA और UPnP
- **Media** — image generation/editing, audio transcription/speech, camera capture और QR codes
- **Documents** — PDF, PowerPoint, Word, Excel, CSV, JSON, YAML, SQL और log analysis

**IoT और physical-world control**

- **SwitchBot** — Cloud और BLE discovery, status, control, batching और subscriptions
- **ECHONET Lite** — Japanese home appliances को discover और control करें, जिसमें INF notifications शामिल हैं
- **Matter** — endpoints, clusters, attributes, state history, subscriptions और control
- **BACnet / Modbus TCP / OPC UA** — industrial और building automation reads, writes, browsing और monitoring
- **UPnP** — device discovery, WAN status और router port-mapping management

### uag कहाँ काम आता है

uag एक ओर लोगों और interfaces के बीच तथा दूसरी ओर models, tools और real-world systems के बीच स्थित है।
यह बातचीत का समन्वय करता है, क्षमताएँ चुनता है, safety rules लागू करता है और workflow को फिर से शुरू करने योग्य बनाए रखता है।

~~~mermaid
flowchart LR
    UI["CLI · Desktop · Web · VS Code · A2A"] --> UAG["UAG agent runtime"]
    UAG --> MODELS["Hosted & local models"]
    UAG --> TOOLS["Tools & extensions"]
    UAG --> STATE["Sessions & context"]
    TOOLS --> SYSTEMS["Files · Code · Web · MCP · Cloud · IoT"]
    POLICY["Confirmation · Credentials · Policy"] -.-> UAG
~~~

### Plugins, Agent Skills और marketplaces

Core को fork किए बिना uag को specialized agent बनाएँ:

- Directory, ZIP, Git repository, HTTP source या marketplace से **Claude Code-compatible plugins** install करें
- Skills, sub-agents, MCP servers, hooks, slash commands, output styles, dependencies और channels को bundle करें
- [SkillsMP](https://skillsmp.com) और [ClawHub](https://clawhub.ai) से community capabilities browse करें
- `UAGENT_EXTERNAL_TOOLS_DIR` के माध्यम से private organization skills और tools locally जोड़ें

```text
:skills mp_search browser automation
:plugin list
:plugin install <source>
:plugin marketplace list
```

[Plugin Development Guide](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP_PLUGIN.md) देखें।

- **200+ tools** files, web, media, documents, code, cloud, communication और IoT के लिए
- **Dynamic discovery and loading** — क्षमताएँ खोजने के लिए `tool_catalog` और आवश्यकता होने पर ही enable करने के लिए `tool_load` का उपयोग करें
- **Code intelligence** — `code_map`, language-specific `idx` navigators, Git review, test execution, linting, compilation और coverage
- skills, agents, MCP servers, hooks, commands और marketplaces वाले **Claude Code-compatible plugins**
- SkillsMP और ClawHub से **Agent Skills**
- `TOOL_SPEC` और `run_tool()` वाले **Custom Python tools**
- lightweight native extensions के लिए **Rust-backed tools**

[Tool Creator Guide](../TOOL_CREATOR_GUIDE.md) · [MCP OAuth / Proxy Guide](MCP_OAUTH_PROXY_GUIDE.md)

## वास्तविक कार्यप्रवाहों के लिए निर्मित

### 🧠 संदर्भ-जागरूक टूल परिणाम

जब संभव हो, बड़े टूल परिणाम सक्रिय मॉडल संदर्भ से बाहर रखे जाते हैं। uag इन्हें आर्टिफैक्ट्स के रूप में संग्रहीत करता है और मॉडल को एक स्थिर Artifact संदर्भ के साथ एक सीमित पूर्वावलोकन भेजता है। जब कोई टूल बड़ा परिणाम उत्पन्न करता है, तो इससे फॉलो-अप टर्न के लिए आवश्यक इनपुट टोकन की संख्या काफी कम हो सकती है।

`:load <index>` से पिछली conversations resume करें। Tool results cache किए जा सकते हैं और application को rebuild किए बिना
providers बदले जा सकते हैं।

[Context compression](CONTEXT_COMPRESSION.hi.md) · [Memory](MEMORY.md) · [Session portability](SESSION_PORTABILITY.md)

### Auto-pilot

Optional reviewer model के साथ multi-round work के लिए `:auto` का उपयोग करें। `--max-rounds N` से round limit सेट करें।
Auto-pilot रोकने के लिए **F12** या current response रोकने के लिए **F12** दबाएँ।

सुरक्षित होने पर स्वतंत्र read-only operations concurrent रूप से चलती हैं। Web searches, file inspection,
repository analysis और समान workloads configurable worker pool (`UAGENT_PARALLEL_WORKERS`) के साथ parallel में पूरे हो सकते हैं।
Write operations serialized रहती हैं या confirmation आवश्यक होता है।

Session continuity, tool-result caching, batch state, restart recovery, DAG scheduling और
multi-agent orchestration जटिल कार्यों को one-shot के बजाय फिर से शुरू करने योग्य बनाते हैं।

[Auto-pilot](README_AUTO.md) · [Timers](SET_TIMER.md) · [Multi-agent runtime](MULTI_AGENT_RUNTIME.md)

### 🌍 निजी, बहुभाषी और policy-aware

`human_ask` sensitive actions से पहले pause करता है। File deletion, overwrites, shell commands, device controls,
credential operations और network writes को confirmation और policy rules द्वारा नियंत्रित किया जा सकता है।

Prompts में long-lived secrets रखने के बजाय credential store का उपयोग करें:

वेब UI में Authorization Code + PKCE का उपयोग करके OIDC साइन-इन, सत्यापित ID टोकन, सर्वर-साइड सत्र, और प्रोजेक्ट/रूम एक्सेस नियंत्रण शामिल हैं। सत्यापित Microsoft Entra ID समूह दावे कॉन्फ़िगर किए जाने पर डायरेक्टरी-आधारित एक्सेस नीति को फीड कर सकते हैं। Windows Active Directory, OAuth, और trusted-proxy डिप्लॉयमेंट्स स्पष्ट सत्यापित पहचान एडाप्टर के माध्यम से एकीकृत हो सकते हैं; Windows AD को डिप्लॉयमेंट-विशिष्ट Kerberos/Negotiate वेरीफायर की आवश्यकता होती है और यह डिफ़ॉल्ट रूप से सक्षम नहीं है।

uag में Agent, LLM, टूल, Context, Memory और पुनर्प्राप्ति संचालन के लिए ऑप्ट-इन, प्रदाता-तटस्थ OpenTelemetry ट्रेसिंग और मेट्रिक्स शामिल हैं। अवलोकनशीलता डिफ़ॉल्ट रूप से अक्षम है.

लोकल-फ़र्स्ट का अर्थ यह नहीं है कि UAG डिफ़ॉल्ट रूप से पूरी तरह ऑफ़लाइन है या सभी टूल अलग-थलग चलते हैं। बाहरी मॉडल और जुड़ी सेवाओं को अनुरोध भेजना कॉन्फ़िगरेशन पर निर्भर करता है।

- [Enterprise policies](ENTERPRISE_POLICY.md)
- [MXC sandbox](SANDBOX_MXC.md)
- [Remote Web / A2A](REMOTE_MXC_DEFAULT.md)
- [Web identity](WEB_IDENTITY_MEMORY.md)
- [OpenTelemetry](UAG_OPENTELEMETRY_DESIGN.md)

### 🌍 बहुभाषी अनुवाद

- `translate_text` `provider=auto`, `provider=deepl`, या `provider=google` के माध्यम से Google Translate और आधिकारिक DeepL Python क्लाइंट का समर्थन करता है।
- टूल परिभाषाएँ 37 लोकल और अंग्रेज़ी (कुल 38) में उपलब्ध हैं, जिसमें प्लेसहोल्डर और तकनीकी पहचानकर्ता संरक्षित हैं।

Full-duplex voice OpenAI Realtime, Azure OpenAI, xAI Grok Voice, Gemini Live और Bedrock Nova Sonic के माध्यम से उपलब्ध है,
जिसमें optional AEC3 echo cancellation और safety-limited realtime function calling शामिल हैं।

[Translations](README.translations.md) · [IoT](IOT_USECASE.md) · [Communication](COMMUNICATION.md)

## दस्तावेज़

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

## विकास और योगदान

```bash
git clone https://github.com/awaku7/agentcli.git
cd agentcli
python -m pip install -e ".[core,providers,test]"
```

Pre-PR checks चलाएँ:

```bash
python -m ruff check src tests
python -m black --check src tests
python -m pytest -q .
```

पूर्ण development workflow के लिए [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md) देखें।

Bug reports, feature ideas, documentation improvements, translations, tools, skills और pull requests का स्वागत है।
बड़े changes से पहले issue या discussion खोलें। [Developer Guide](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md) पढ़ें
और pull request submit करने से पहले ऊपर दिए checks चलाएँ।

## License

Licensed under the [Apache License 2.0](https://github.com/awaku7/agentcli/blob/main/LICENSE).
