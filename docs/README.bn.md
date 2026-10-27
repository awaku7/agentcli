<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="680">
</p>

<h1 align="center">uag</h1>

<p align="center">
  <strong>Universal AI Gateway</strong><br>
  একটি স্থানীয় এজেন্ট। যেকোনো মডেল। যেকোনো টুল। আপনার পরিবেশ, আপনার নিয়ম।
</p>

<p align="center">
  <a href="https://github.com/awaku7/agentcli/actions"><img src="https://img.shields.io/github/actions/workflow/status/awaku7/agentcli/ci.yml?style=flat-square&label=CI" alt="CI status"></a>
  <a href="https://pypi.org/project/uag/"><img src="https://img.shields.io/pypi/v/uag?style=flat-square" alt="PyPI version"></a>
  <a href="https://pypi.org/project/uag/"><img src="https://img.shields.io/pypi/pyversions/uag?style=flat-square" alt="Python versions"></a>
  <a href="https://github.com/awaku7/agentcli/blob/main/LICENSE"><img src="https://img.shields.io/github/license/awaku7/agentcli?style=flat-square" alt="লাইসেন্স"></a>
  <a href="https://pepy.tech/projects/uag"><img src="https://static.pepy.tech/personalized-badge/uag?period=total&units=INTERNATIONAL_SYSTEM&left_color=grey&right_color=green&left_text=downloads" alt="PyPI Downloads"></a>
</p>

<p align="center">
  <a href="https://github.com/awaku7/agentcli">GitHub</a> ·
  <a href="https://pypi.org/project/uag/">PyPI</a> ·
  <a href="https://github.com/awaku7/agentcli/discussions">আলোচনা</a> ·
  <a href="https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md">অনুবাদ</a>
</p>

______________________________________________________________________

**uag কেন?**

uag একটি স্থানীয়-অগ্রাধিকার AI এজেন্ট, যা আপনার পছন্দের মডেলকে আপনার ব্যবহৃত প্রকৃত টুলগুলোর সঙ্গে যুক্ত করে।
ফাইল, ব্রাউজার, কোডবেস, যোগাযোগ, ক্লাউড API, IoT ডিভাইস, MCP সার্ভার এবং বহু-এজেন্ট কর্মপ্রবাহের জন্য
এটি আপনাকে একটি একক, সম্প্রসারণযোগ্য রানটাইম দেয়।

- **প্রোভাইডার বেছে নেওয়ার স্বাধীনতা** — OpenAI, Anthropic, Gemini, Azure, Bedrock, Ollama, llama.cpp, Grok, DeepSeek এবং আরও অনেক কিছু।
- **স্থানীয়-অগ্রাধিকার সম্পাদন** — আপনার এজেন্ট রানটাইম ও টুল সম্পাদন আপনার মেশিনেই থাকে; কেবল আপনার নির্বাচিত API কলগুলোই বাইরে যায়।
- **একটি টুল স্তর** — একই টুল CLI, ডেস্কটপ GUI, ওয়েব UI, VS Code এবং A2A থেকে কাজ করে।
- **নকশাতেই সমান্তরাল** — স্বাধীন, শুধু-পাঠযোগ্য কাজগুলো একসঙ্গে চলতে পারে।
- **সম্প্রসারণযোগ্য** — মূল অংশ পরিবর্তন না করেই টুল, প্লাগইন, Agent Skills, MCP সার্ভার এবং Rust-ভিত্তিক টুল যোগ করুন।
- **নিরাপত্তা-সচেতন** — ধ্বংসাত্মক কাজ, শংসাপত্র, ডিভাইস নিয়ন্ত্রণ এবং নেটওয়ার্কে লেখার কাজে স্পষ্ট অনুমোদন ও নীতিনিয়ন্ত্রণ ব্যবহার করা যায়।

> **সংক্ষেপে:** uag হলো আপনার AI মডেল এবং বাস্তব পরিবেশের মধ্যকার নিয়ন্ত্রণ স্তর।

> **🧠 প্রসঙ্গ-সচেতন টুল ফলাফল** — বড় টুল ফলাফলগুলো সম্ভব হলে সক্রিয় মডেলের প্রসঙ্গ থেকে বাদ রাখা হয়। uag এগুলো আর্টিফ্যাক্ট হিসেবে সংরক্ষণ করে এবং মডেলের কাছে স্থিতিশীল Artifact রেফারেন্সসহ একটি সীমাবদ্ধ প্রিভিউ পাঠায়। যখন কোনো টুল বড় ফলাফল তৈরি করে, তখন এটি পরবর্তী পালাগুলির জন্য প্রয়োজনীয় ইনপুট টোকেনের সংখ্যা উল্লেখযোগ্যভাবে কমিয়ে দিতে পারে।
> [প্রসঙ্গ সংকোচনের বিস্তারিত নির্দেশিকা](CONTEXT_COMPRESSION.bn.md)

## দ্রুত শুরু

**Python 3.11+**

```bash
python -m pip install --upgrade uag
uag
```

প্রথমবার চালু হলে setup wizard খোলে। এটি একটি প্রোভাইডার কনফিগার করতে সাহায্য করে এবং নির্বাচিত সেটিংস
আপনার স্থানীয় পরিবেশে সংরক্ষণ করে।

সাধারণ feature group-গুলোর জন্য:

```bash
python -m pip install "uag[core,providers,tools]"
```

> Platform integration ঐচ্ছিক। আপনার অপারেটিং সিস্টেমের প্রয়োজন অনুযায়ী কেবল সেগুলো ইনস্টল করুন; দেখুন

```text
> What files changed in this repository?
> Search the web for today's AI news and summarize the top five stories.
> :help
```

[Quickstart](QUICKSTART.md) · [Environment](ENVIRONMENT.md)

## ইন্টারফেস

| ইন্টারফেস | কমান্ড | কোন কাজের জন্য উপযোগী |
|---|---|---|
| **CLI** | `uag` | দ্রুত, কীবোর্ড-নির্ভর কাজ |
| **Desktop GUI** | `uagg` | native desktop অভিজ্ঞতা |
| **Web UI** | `uagw` | ব্রাউজার-ভিত্তিক প্রবেশাধিকার |
| **A2A server** | `uaga` | agent-to-agent যোগাযোগ |
| **VS Code** | Extension | এডিটরে টুল ব্যাখ্যা, refactor, ঠিক করা এবং ব্রাউজ করা |

সব ইন্টারফেস একই provider configuration, tool registry, safety rules এবং session data ভাগ করে।

~~~bash
# Desktop GUI
python -m pip install "uag[platform]"

# Web UI
python -m pip install "uag[web]" fastapi uvicorn
~~~

[Interface options](USAGE.md) · [Environment](ENVIRONMENT.md)

## আপনি কী তৈরি করতে পারেন

Provider adapter-গুলো hosted ও local runtime সমর্থন করে, যার মধ্যে রয়েছে:

**OpenAI · Meta Model API · Anthropic · Google Gemini · Vertex AI · Azure OpenAI · Amazon Bedrock · OpenRouter · Ollama · llama.cpp · Grok · DeepSeek · NVIDIA · Hugging Face · Alibaba Cloud · Moonshot · Xiaomi MiMo · LM Studio · MiniMax · Sakana AI · SAKURA AI Engine · Together AI · Vercel AI Gateway · PFN/PLaMo · Z.AI · Novita**

`UAGENT_PROVIDER` দিয়ে প্রোভাইডার বদলান; আপনার টুল ও ইন্টারফেস বদলাবে না।

**আপনার পরিবেশের সঙ্গে কাজ**

- ফাইল পড়া, তৈরি, সম্পাদনা, অনুসন্ধান, hash করা, archive করা এবং পরিদর্শন করা
- Git পরিবর্তন পর্যালোচনা, secret খোঁজা, test চালানো, lint, compile এবং coverage পরিমাপ করা
- Python, TypeScript, JavaScript, Go, Rust, C/C++, Java, C#, COBOL, VBA এবং অন্যান্য বড় codebase-এ নেভিগেট করা
- Playwright দিয়ে ব্রাউজার স্বয়ংক্রিয় করা, যার মধ্যে বহু-পৃষ্ঠার কর্মপ্রবাহ ও download রয়েছে

**সার্ভিস ও ডিভাইস সংযুক্ত করা**

- **MCP** — OAuth-সক্ষম service-সহ বাহ্যিক tool server সংযুক্ত করুন
- **A2A** — অন্য agent ও compatible server-এর সঙ্গে সমন্বয় করুন
- **Cloud** — লেখার ক্ষেত্রে confirmation-সহ AWS, Google Cloud এবং Azure API access
- **Communication** — Gmail, Bluesky, Discord, Microsoft Teams এবং pybitchat
- **IoT** — SwitchBot, ECHONET Lite, Matter, BACnet, Modbus TCP, OPC UA এবং UPnP
- **Media** — image generation/editing, audio transcription/speech, camera capture এবং QR code
- **Documents** — PDF, PowerPoint, Word, Excel, CSV, JSON, YAML, SQL এবং log analysis

**IoT ও বাস্তব জগতের নিয়ন্ত্রণ**

- **SwitchBot** — Cloud ও BLE discovery, status, control, batching এবং subscription
- **ECHONET Lite** — INF notification-সহ জাপানি গৃহস্থালি যন্ত্র আবিষ্কার ও নিয়ন্ত্রণ
- **Matter** — endpoint, cluster, attribute, state history, subscription এবং control
- **BACnet / Modbus TCP / OPC UA** — শিল্প ও building automation-এর read, write, browsing এবং monitoring
- **UPnP** — device discovery, WAN status এবং router port-mapping management

### uag কোথায় কাজ করে

একদিকে মানুষ ও ইন্টারফেস, অন্যদিকে মডেল, টুল এবং বাস্তব জগতের সিস্টেম—uag এই দুইয়ের মাঝখানে অবস্থান করে।
এটি কথোপকথন সমন্বয় করে, সক্ষমতা নির্বাচন করে, নিরাপত্তা নিয়ম প্রয়োগ করে এবং কর্মপ্রবাহকে পুনরায় চালানোযোগ্য রাখে।

~~~mermaid
flowchart LR
    UI["CLI · Desktop · Web · VS Code · A2A"] --> UAG["UAG agent runtime"]
    UAG --> MODELS["Hosted & local models"]
    UAG --> TOOLS["Tools & extensions"]
    UAG --> STATE["Sessions & context"]
    TOOLS --> SYSTEMS["Files · Code · Web · MCP · Cloud · IoT"]
    POLICY["Confirmation · Credentials · Policy"] -.-> UAG
~~~

### প্লাগইন, Agent Skills এবং marketplace

মূল অংশ fork না করেই uag-কে একটি বিশেষায়িত agent-এ রূপান্তর করুন:

- directory, ZIP, Git repository, HTTP source বা marketplace থেকে **Claude Code-compatible plugin** ইনস্টল করুন
- skill, sub-agent, MCP server, hook, slash command, output style, dependency এবং channel একত্র করুন
- [SkillsMP](https://skillsmp.com) ও [ClawHub](https://clawhub.ai) থেকে community capability ব্রাউজ করুন
- `UAGENT_EXTERNAL_TOOLS_DIR`-এর মাধ্যমে ব্যক্তিগত organization skill ও tool স্থানীয়ভাবে যোগ করুন

```text
:skills mp_search browser automation
:plugin list
:plugin install <source>
:plugin marketplace list
```

দেখুন [Plugin Development Guide](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP_PLUGIN.md)।

- **200+ টুল** — ফাইল, ওয়েব, মিডিয়া, ডকুমেন্ট, কোড, ক্লাউড, যোগাযোগ এবং IoT-এর জন্য
- **গতিশীল আবিষ্কার ও লোডিং** — সক্ষমতা খুঁজতে `tool_catalog` এবং প্রয়োজনের সময় কেবল সক্রিয় করতে `tool_load` ব্যবহার করুন
- **কোড ইন্টেলিজেন্স** — `code_map`, ভাষাভিত্তিক `idx` নেভিগেটর, Git পর্যালোচনা, টেস্ট সম্পাদন, linting, compilation এবং coverage
- **Claude Code-সামঞ্জস্যপূর্ণ প্লাগইন** — skill, agent, MCP server, hook, command এবং marketplace-সহ
- **SkillsMP ও ClawHub-এর Agent Skills**
- **`TOOL_SPEC` ও `run_tool()`-সহ কাস্টম Python টুল**
- **হালকা native extension-এর জন্য Rust-ভিত্তিক টুল**

[Tool Creator Guide](../TOOL_CREATOR_GUIDE.md) · [MCP OAuth / Proxy Guide](MCP_OAUTH_PROXY_GUIDE.md)

## বাস্তব কাজের প্রবাহের জন্য তৈরি

### 🧠 প্রসঙ্গ-সচেতন টুল ফলাফল

বড় টুল ফলাফলগুলো সম্ভব হলে সক্রিয় মডেলের প্রসঙ্গ থেকে বাদ রাখা হয়। uag এগুলো আর্টিফ্যাক্ট হিসেবে সংরক্ষণ করে এবং মডেলের কাছে স্থিতিশীল Artifact রেফারেন্সসহ একটি সীমাবদ্ধ প্রিভিউ পাঠায়। যখন কোনো টুল বড় ফলাফল তৈরি করে, তখন এটি পরবর্তী পালাগুলির জন্য প্রয়োজনীয় ইনপুট টোকেনের সংখ্যা উল্লেখযোগ্যভাবে কমিয়ে দিতে পারে।

`:load <index>` দিয়ে আগের conversation পুনরায় চালু করুন। Tool result cache করা যায় এবং application পুনর্নির্মাণ
না করেই provider বদলানো যায়।

[Context compression](CONTEXT_COMPRESSION.bn.md) · [Memory](MEMORY.md) · [Session portability](SESSION_PORTABILITY.md)

### অটো-পাইলট

ঐচ্ছিক reviewer model-সহ বহু-round কাজের জন্য `:auto` ব্যবহার করুন। `--max-rounds N` দিয়ে round limit সেট করুন।
অটো-পাইলট থামাতে **F12**, অথবা বর্তমান response থামাতে **F12** চাপুন।

নিরাপদ হলে স্বাধীন, শুধু-পাঠযোগ্য কাজগুলো একসঙ্গে চলে। ওয়েব অনুসন্ধান, ফাইল পরিদর্শন, রিপোজিটরি বিশ্লেষণ
এবং অনুরূপ কাজ কনফিগারযোগ্য worker pool (`UAGENT_PARALLEL_WORKERS`)-এর মাধ্যমে সমান্তরালে সম্পন্ন হতে পারে।
লেখার কাজগুলো ধারাবাহিক থাকে অথবা অনুমোদন প্রয়োজন হয়।

সেশন ধারাবাহিকতা, টুল-ফলাফল ক্যাশিং, batch state, পুনরায় চালু হওয়ার পুনরুদ্ধার, DAG scheduling এবং
বহু-এজেন্ট orchestration জটিল কাজকে একবারে শেষ করার বদলে পুনরায় চালানোযোগ্য করে।

[Auto-pilot](README_AUTO.md) · [Timers](SET_TIMER.md) · [Multi-agent runtime](MULTI_AGENT_RUNTIME.md)

### 🌍 ব্যক্তিগত, বহুভাষিক এবং নীতিসচেতন

সংবেদনশীল কাজের আগে `human_ask` বিরতি দেয়। File deletion, overwrite, shell command, device control,
credential operation এবং network write confirmation ও policy rule দ্বারা নিয়ন্ত্রিত হতে পারে।

Prompt-এ দীর্ঘমেয়াদি secret রাখার পরিবর্তে শংসাপত্র সংরক্ষণাগার ব্যবহার করুন:

ওয়েব UI-তে Authorization Code + PKCE ব্যবহার করে OIDC সাইন-ইন, যাচাইকৃত ID টোকেন, সার্ভার-সাইড সেশন এবং প্রকল্প/রুম অ্যাক্সেস নিয়ন্ত্রণ অন্তর্ভুক্ত রয়েছে। কনফিগার করা হলে যাচাইকৃত Microsoft Entra ID গ্রুপ দাবি ডিরেক্টরি-ব্যাকড অ্যাক্সেস নীতিতে ব্যবহার করা যেতে পারে। Windows Active Directory, OAuth, এবং trusted-proxy ডিপ্লয়মেন্টগুলি স্পষ্টভাবে যাচাইকৃত পরিচয় অ্যাডাপ্টারের মাধ্যমে ইন্টিগ্রেট করা যায়; Windows AD একটি ডিপ্লয়মেন্ট-নির্দিষ্ট Kerberos/Negotiate ভেরিফায়ার প্রয়োজন এবং ডিফল্টভাবে সক্রিয় নয়।

uag এর মধ্যে রয়েছে অপ্ট-ইন, প্রদানকারী-নিরপেক্ষ OpenTelemetry ট্রেসিং এবং Agent, LLM, টুল, Context, Memory, এবং পুনরুদ্ধার ক্রিয়াকলাপের জন্য মেট্রিক্স। পর্যবেক্ষণযোগ্যতা ডিফল্টরূপে অক্ষম করা হয়।

লোকাল-ফার্স্ট মানেই ডিফল্টভাবে সম্পূর্ণ অফলাইন কাজ করা বা সব টুলের নির্বাহ বিচ্ছিন্ন থাকা নয়। বাহ্যিক মডেল ও সংযুক্ত পরিষেবায় অনুরোধ কনফিগারেশনের ওপর নির্ভর করে।

- [Enterprise policies](ENTERPRISE_POLICY.md)
- [MXC sandbox](SANDBOX_MXC.md)
- [Remote Web / A2A](REMOTE_MXC_DEFAULT.md)
- [Web identity](WEB_IDENTITY_MEMORY.md)
- [OpenTelemetry](UAG_OPENTELEMETRY_DESIGN.md)

### 🌍 বহুভাষিক অনুবাদ

- `translate_text` `Google Translate` এবং অফিসিয়াল DeepL Python ক্লায়েন্টকে `provider=auto`, `provider=deepl`, অথবা `provider=google` এর মাধ্যমে সমর্থন করে।
- টুল সংজ্ঞা ৩৭টি লোকেলের পাশাপাশি ইংরেজি (মোট ৩৮টি) ভাষায় উপলব্ধ, প্লেসহোল্ডার এবং প্রযুক্তিগত আইডেন্টিফায়ার সংরক্ষিত রয়েছে।

OpenAI Realtime, Azure OpenAI, xAI Grok Voice, Gemini Live এবং Bedrock Nova Sonic-এর মাধ্যমে full-duplex
ভয়েস পাওয়া যায়; এর সঙ্গে ঐচ্ছিক AEC3 echo cancellation এবং নিরাপত্তা-সীমাবদ্ধ realtime function calling রয়েছে।

[Translations](README.translations.md) · [IoT](IOT_USECASE.md) · [Communication](COMMUNICATION.md)

## ডকুমেন্টেশন

| বিষয় | ডকুমেন্টেশন |
|---|---|
| পরিবেশ চলক | [docs/ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/docs/ENVIRONMENT.md) |
| Architecture এবং invariants | [docs/ARCHITECTURE.md](https://github.com/awaku7/agentcli/blob/main/docs/ARCHITECTURE.md) |
| Computer Use | [docs/COMPUTER_USE_IMPLEMENTATION.md](https://github.com/awaku7/agentcli/blob/main/docs/COMPUTER_USE_IMPLEMENTATION.md) |
| রিপোজিটরি টুল | [docs/REPOSITORY_TOOLS.md](https://github.com/awaku7/agentcli/blob/main/docs/REPOSITORY_TOOLS.md) |
| IoT ব্যবহারের উদাহরণ | [docs/IOT_USECASE.md](https://github.com/awaku7/agentcli/blob/main/docs/IOT_USECASE.md) |
| যোগাযোগ টুল | [docs/COMMUNICATION.md](https://github.com/awaku7/agentcli/blob/main/docs/COMMUNICATION.md) |
| অটো-পাইলট | [docs/README_AUTO.md](https://github.com/awaku7/agentcli/blob/main/docs/README_AUTO.md) |
| MCP OAuth / Proxy | [docs/MCP_OAUTH_PROXY_GUIDE.md](https://github.com/awaku7/agentcli/blob/main/docs/MCP_OAUTH_PROXY_GUIDE.md) |
| VS Code এক্সটেনশন | [docs/VSCODE.md](https://github.com/awaku7/agentcli/blob/main/docs/VSCODE.md) |
| ডেভেলপার গাইড | [src/uagent/docs/DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md) |
| টুল প্রবাহ | [src/uagent/docs/TOOL_FLOW.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/TOOL_FLOW.md) |

[Quickstart](QUICKSTART.md) · [Architecture](ARCHITECTURE.md) · [Context management](UAG_CONTEXT_MANAGEMENT_DESIGN.md)

## উন্নয়ন ও অবদান

```bash
git clone https://github.com/awaku7/agentcli.git
cd agentcli
python -m pip install -e ".[core,providers,test]"
```

Pre-PR check চালান:

```bash
python -m ruff check src tests
python -m black --check src tests
python -m pytest -q .
```

সম্পূর্ণ development workflow-এর জন্য দেখুন [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)।

Bug report, feature idea, documentation improvement, translation, tool, skill এবং pull request স্বাগত।
বড় পরিবর্তনের আগে একটি issue বা discussion খুলুন। [Developer Guide](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md) পড়ুন
এবং pull request জমা দেওয়ার আগে উপরের check-গুলো চালান।

## লাইসেন্স

[Apache লাইসেন্স 2.0](https://github.com/awaku7/agentcli/blob/main/LICENSE)-এর অধীনে লাইসেন্সপ্রাপ্ত।
