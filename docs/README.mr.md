<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="680">
</p>

<h1 align="center">uag</h1>

<p align="center">
  <strong>Universal AI Gateway</strong><br>
  एक स्थानिक एजंट. कोणतेही मॉडेल. कोणतेही साधन. तुमचे वातावरण, तुमचे नियम.
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

**uag का?**

uag हा स्थानिकतेला प्राधान्य देणारा AI एजंट आहे, जो तुम्हाला पसंत असलेले मॉडेल तुम्ही प्रत्यक्षात वापरत असलेल्या साधनांशी जोडतो.
तो फाइल्स, ब्राउझर, कोडबेस, संवाद, क्लाउड API, IoT उपकरणे, MCP सर्व्हर आणि बहु-एजंट कार्यप्रवाहांसाठी
एकच, विस्तारता येणारे रनटाइम उपलब्ध करून देतो.

- **Provider स्वातंत्र्य** — OpenAI, Anthropic, Gemini, Azure, Bedrock, Ollama, llama.cpp, Grok, DeepSeek आणि इतर अनेक.
- **Local-first अंमलबजावणी** — तुमचा एजंट रनटाइम आणि साधनांची अंमलबजावणी तुमच्या मशीनवरच राहते; तुम्ही निवडलेले API कॉल्सच बाहेर जातात.
- **एकच साधन-स्तर** — CLI, डेस्कटॉप GUI, वेब UI, VS Code आणि A2A मधून तीच साधने कार्य करतात.
- **मूळ रचनेत समांतरता** — स्वतंत्र, केवळ-वाचन प्रक्रिया सुरक्षितपणे एकाच वेळी चालू शकतात.
- **विस्तारक्षम** — core मध्ये बदल न करता साधने, plugins, Agent Skills, MCP servers आणि Rust-backed tools जोडा.
- **सुरक्षिततेची जाणीव** — विध्वंसक कृती, credentials, device controls आणि network writes साठी स्पष्ट पुष्टीकरण व policy controls उपलब्ध आहेत.

> **थोडक्यात:** uag हा तुमच्या AI models आणि प्रत्यक्ष वातावरणामधील control plane आहे.

> **🧠 संदर्भ-जागरूक साधन निकाल** — मोठ्या साधन निकालांना शक्यतो सक्रिय मॉडेलच्या संदर्भाबाहेर ठेवले जाते. uag त्यांना आर्टिफॅक्ट्स म्हणून संग्रहित करते आणि मॉडेलला स्थिर Artifact संदर्भासह मर्यादित पूर्वावलोकन पाठवते. जेव्हा एखादे साधन मोठा परिणाम तयार करते, तेव्हा पुढील फेरींसाठी आवश्यक इनपुट टोकनची संख्या यामुळे लक्षणीयरीत्या कमी होऊ शकते.
> [संदर्भ संकुचनासाठी सविस्तर मार्गदर्शक](CONTEXT_COMPRESSION.mr.md)

## झटपट सुरुवात

**Python 3.11+**

```bash
python -m pip install --upgrade uag
uag
```

पहिल्यांदा सुरू केल्यावर setup wizard उघडतो. तो provider configure करण्यात मदत करतो आणि निवडलेल्या settings तुमच्या local environment मध्ये साठवतो.

सामान्य feature groups साठी:

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
| **CLI** | `uag` | जलद, keyboard-first काम |
| **Desktop GUI** | `uagg` | Native desktop अनुभव |
| **Web UI** | `uagw` | Browser-based access |
| **A2A server** | `uaga` | Agent-to-agent communication |
| **VS Code** | Extension | Editor मध्ये tools समजावणे, refactor, fix आणि browse करणे |

सर्व interfaces समान provider configuration, tool registry, safety rules आणि session data सामायिक करतात.

~~~bash
# Desktop GUI
python -m pip install "uag[platform]"

# Web UI
python -m pip install "uag[web]" fastapi uvicorn
~~~

[Interface options](USAGE.md) · [Environment](ENVIRONMENT.md)

## तुम्ही काय तयार करू शकता

Provider adapters hosted आणि local runtimes साठी उपलब्ध आहेत, यामध्ये:

**OpenAI · Meta Model API · Anthropic · Google Gemini · Vertex AI · Azure OpenAI · Amazon Bedrock · OpenRouter · Ollama · llama.cpp · Grok · DeepSeek · NVIDIA · Hugging Face · Alibaba Cloud · Moonshot · Xiaomi MiMo · LM Studio · MiniMax · Sakana AI · SAKURA AI Engine · Together AI · Vercel AI Gateway · PFN/PLaMo · Z.AI · Novita**

`UAGENT_PROVIDER` वापरून providers बदला; तुमची tools आणि interface बदलत नाहीत.

**तुमच्या environment सोबत काम**

- Files वाचा, तयार करा, संपादित करा, शोधा, hash करा, archive करा आणि inspect करा
- Git changes चे review करा, secrets शोधा, tests चालवा, lint व compile करा आणि coverage मोजा
- मोठे Python, TypeScript, JavaScript, Go, Rust, C/C++, Java, C#, COBOL, VBA आणि इतर codebases मध्ये नेव्हिगेट करा
- Playwright वापरून browsers automate करा, multi-page workflows आणि downloads सहित

**Services आणि devices जोडा**

- **MCP** — OAuth-enabled services सहित external tool servers शी जोडा
- **A2A** — इतर agents आणि compatible servers सोबत समन्वय करा
- **Cloud** — writes साठी confirmation सह AWS, Google Cloud आणि Azure API access
- **Communication** — Gmail, Bluesky, Discord, Microsoft Teams आणि pybitchat
- **IoT** — SwitchBot, ECHONET Lite, Matter, BACnet, Modbus TCP, OPC UA आणि UPnP
- **Media** — image generation/editing, audio transcription/speech, camera capture आणि QR codes
- **Documents** — PDF, PowerPoint, Word, Excel, CSV, JSON, YAML, SQL आणि log analysis

**IoT आणि physical-world control**

- **SwitchBot** — Cloud आणि BLE discovery, status, control, batching आणि subscriptions
- **ECHONET Lite** — INF notifications सहित Japanese home appliances शोधा व नियंत्रित करा
- **Matter** — endpoints, clusters, attributes, state history, subscriptions आणि control
- **BACnet / Modbus TCP / OPC UA** — industrial आणि building automation reads, writes, browsing आणि monitoring
- **UPnP** — device discovery, WAN status आणि router port-mapping management

### uag कुठे बसतो

एका बाजूला लोक आणि interfaces, तर दुसऱ्या बाजूला models, tools आणि वास्तविक-जगातील systems यांच्या मध्ये uag काम करतो.
तो संवाद समन्वयित करतो, क्षमता निवडतो, safety rules लागू करतो आणि workflow पुन्हा सुरू करता येईल याची खात्री करतो.

~~~mermaid
flowchart LR
    UI["CLI · Desktop · Web · VS Code · A2A"] --> UAG["UAG agent runtime"]
    UAG --> MODELS["Hosted & local models"]
    UAG --> TOOLS["Tools & extensions"]
    UAG --> STATE["Sessions & context"]
    TOOLS --> SYSTEMS["Files · Code · Web · MCP · Cloud · IoT"]
    POLICY["Confirmation · Credentials · Policy"] -.-> UAG
~~~

### Plugins, Agent Skills आणि marketplaces

Core fork न करता uag ला specialized agent मध्ये रूपांतरित करा:

- Directory, ZIP, Git repository, HTTP source किंवा marketplace मधून **Claude Code-compatible plugins** install करा
- Skills, sub-agents, MCP servers, hooks, slash commands, output styles, dependencies आणि channels bundle करा
- [SkillsMP](https://skillsmp.com) आणि [ClawHub](https://clawhub.ai) वरील community capabilities ब्राउझ करा
- `UAGENT_EXTERNAL_TOOLS_DIR` द्वारे private organization skills आणि tools locally जोडा

```text
:skills mp_search browser automation
:plugin list
:plugin install <source>
:plugin marketplace list
```

[Plugin Development Guide](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP_PLUGIN.md) पहा.

- **200+ tools** — files, web, media, documents, code, cloud, communication आणि IoT साठी
- **Dynamic discovery and loading** — क्षमता शोधण्यासाठी `tool_catalog` आणि गरज असेल तेव्हाच सक्षम करण्यासाठी `tool_load` वापरा
- **Code intelligence** — `code_map`, भाषानिहाय `idx` navigators, Git review, test execution, linting, compilation आणि coverage
- **Claude Code-compatible plugins** — skills, agents, MCP servers, hooks, commands आणि marketplaces सह
- **Agent Skills** — SkillsMP आणि ClawHub मधून
- **Custom Python tools** — `TOOL_SPEC` आणि `run_tool()` सह
- **Rust-backed tools** — हलक्या native extensions साठी

[Tool Creator Guide](../TOOL_CREATOR_GUIDE.md) · [MCP OAuth / Proxy Guide](MCP_OAUTH_PROXY_GUIDE.md)

## वास्तविक कार्यप्रवाहांसाठी तयार

### 🧠 संदर्भ-जागरूक साधन निकाल

मोठ्या साधन निकालांना शक्यतो सक्रिय मॉडेलच्या संदर्भाबाहेर ठेवले जाते. uag त्यांना आर्टिफॅक्ट्स म्हणून संग्रहित करते आणि मॉडेलला स्थिर Artifact संदर्भासह मर्यादित पूर्वावलोकन पाठवते. जेव्हा एखादे साधन मोठा परिणाम तयार करते, तेव्हा पुढील फेरींसाठी आवश्यक इनपुट टोकनची संख्या यामुळे लक्षणीयरीत्या कमी होऊ शकते.

`:load <index>` ने आधीचे conversations पुन्हा सुरू करा. Tool results cache करता येतात आणि application rebuild न करता providers बदलता येतात.

[Context compression](CONTEXT_COMPRESSION.mr.md) · [Memory](MEMORY.md) · [Session portability](SESSION_PORTABILITY.md)

### Auto-pilot

Optional reviewer model सह multi-round कामासाठी `:auto` वापरा. `--max-rounds N` ने round limit सेट करा.
Auto-pilot थांबवण्यासाठी **F12** किंवा current response थांबवण्यासाठी **F12** दाबा.

सुरक्षित असल्यास स्वतंत्र, केवळ-वाचन प्रक्रिया एकाच वेळी चालतात. Web searches, file inspection, repository analysis आणि तत्सम कामे
configurable worker pool (`UAGENT_PARALLEL_WORKERS`) वापरून समांतर पूर्ण होऊ शकतात. Write operations क्रमाने होतात किंवा पुष्टीकरण आवश्यक असते.

Session continuity, tool-result caching, batch state, restart recovery, DAG scheduling आणि multi-agent orchestration यांमुळे
कठीण कामे one-shot न राहता पुन्हा सुरू करता येतात.

[Auto-pilot](README_AUTO.md) · [Timers](SET_TIMER.md) · [Multi-agent runtime](MULTI_AGENT_RUNTIME.md)

### 🌍 Private, multilingual आणि policy-aware

Sensitive actions आधी `human_ask` थांबवतो. File deletion, overwrites, shell commands, device controls, credential operations आणि network writes confirmation व policy rules द्वारे नियंत्रित करता येतात.

Prompts मध्ये दीर्घकाळ टिकणारी secrets ठेवण्याऐवजी credential store वापरा:

वेब UI मध्ये Authorization Code + PKCE वापरून OIDC साइन-इन, पडताळणी केलेले ID टोकन्स, सर्व्हर-साइड सत्रे, आणि प्रोजेक्ट/रूम प्रवेश नियंत्रणांचा समावेश आहे. कॉन्फिगर केल्यावर पडताळणी केलेले Microsoft Entra ID ग्रुप क्लेम्स डायरेक्टरी-आधारित प्रवेश धोरणाला पुरवू शकतात. Windows Active Directory, OAuth, आणि trusted-proxy डिप्लॉयमेंट्स स्पष्टपणे पडताळणी केलेल्या ओळख अडॅप्टरद्वारे एकत्रित होऊ शकतात; Windows AD साठी डिप्लॉयमेंट-विशिष्ट Kerberos/Negotiate पडताळणी करणारा आवश्यक आहे आणि तो डीफॉल्टने सक्षम नाही.

uag मध्ये Agent, LLM, टूल, Context, Memory, आणि पुनर्प्राप्ती ऑपरेशन्ससाठी ऑप्ट-इन, प्रदाता-तटस्थ OpenTelemetry ट्रेसिंग आणि मेट्रिक्स समाविष्ट आहेत. निरीक्षणक्षमता डीफॉल्टनुसार अक्षम केली जाते.

स्थानिक वापराला प्राधान्य देणे म्हणजे UAG डीफॉल्टने पूर्णपणे ऑफलाइन चालते किंवा सर्व टूल्स वेगळी ठेवली जातात असे नाही. बाह्य मॉडेल्स आणि जोडलेल्या सेवांना होणाऱ्या विनंत्या कॉन्फिगरेशनवर अवलंबून असतात.

- [Enterprise policies](ENTERPRISE_POLICY.md)
- [MXC sandbox](SANDBOX_MXC.md)
- [Remote Web / A2A](REMOTE_MXC_DEFAULT.md)
- [Web identity](WEB_IDENTITY_MEMORY.md)
- [OpenTelemetry](UAG_OPENTELEMETRY_DESIGN.md)

### 🌍 बहुभाषिक भाषांतर

- `translate_text` Google Translate आणि अधिकृत DeepL Python क्लायंटला `provider=auto`, `provider=deepl`, किंवा `provider=google` द्वारे समर्थन करते.
- साधन परिभाषा 37 स्थानिकीकरणात आणि इंग्रजीमध्ये (एकूण 38) उपलब्ध आहेत, प्लेसहोल्डर्स आणि तांत्रिक ओळखपत्रे जतन केली आहेत.

OpenAI Realtime, Azure OpenAI, xAI Grok Voice, Gemini Live आणि Bedrock Nova Sonic द्वारे full-duplex voice उपलब्ध आहे;
यात पर्यायी AEC3 echo cancellation आणि safety-limited realtime function calling आहे.

[Translations](README.translations.md) · [IoT](IOT_USECASE.md) · [Communication](COMMUNICATION.md)

## दस्तऐवजीकरण

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

## विकास आणि योगदान

```bash
git clone https://github.com/awaku7/agentcli.git
cd agentcli
python -m pip install -e ".[core,providers,test]"
```

Pre-PR checks चालवा:

```bash
python -m ruff check src tests
python -m black --check src tests
python -m pytest -q .
```

पूर्ण development workflow साठी [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md) पहा.

Bug reports, feature ideas, documentation improvements, translations, tools, skills आणि pull requests चे स्वागत आहे.
मोठे बदल करण्यापूर्वी issue किंवा discussion उघडा. [Developer Guide](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md) वाचा
आणि pull request सादर करण्यापूर्वी वरील checks चालवा.

## License

Licensed under the [Apache License 2.0](https://github.com/awaku7/agentcli/blob/main/LICENSE).
