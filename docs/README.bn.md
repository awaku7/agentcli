<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="UAG — Universal AI Gateway" width="620">
</p>
<h1 align="center">UAG</h1>
<p align="center"><strong>Universal AI Gateway</strong><br>আপনার AI মডেল। আপনার টুল। আপনার পরিবেশ।</p>

<p align="center">
  <a href="https://github.com/awaku7/agentcli/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/awaku7/agentcli/ci.yml?style=flat-square&label=CI" alt="CI"></a>
  <a href="https://pypi.org/project/uag/"><img src="https://img.shields.io/pypi/v/uag?style=flat-square" alt="PyPI"></a>
  <a href="https://pypi.org/project/uag/"><img src="https://img.shields.io/pypi/pyversions/uag?style=flat-square" alt="Python versions"></a>
  <a href="../LICENSE"><img src="https://img.shields.io/github/license/awaku7/agentcli?style=flat-square" alt="License"></a>
  <a href="https://pepy.tech/projects/uag"><img src="https://static.pepy.tech/personalized-badge/uag?period=total&units=INTERNATIONAL_SYSTEM&left_color=grey&right_color=green&left_text=downloads" alt="Downloads"></a>
</p>
<p align="center"><a href="../README.md">English</a> · <a href="README.translations.md">অন্যান্য ভাষা</a></p>

---

**UAG একটি উন্মুক্ত উৎসের AI এজেন্ট রানটাইম, যেখানে স্থানীয়ভাবে কাজ করাকে অগ্রাধিকার দেওয়া হয়।** এটি আপনার নির্বাচিত ভাষা মডেলকে আপনার ব্যবহৃত টুল ও সিস্টেমের সঙ্গে যুক্ত করে। একটি অভিন্ন ইন্টারফেসে কোড, ফাইল, ব্রাউজার, সেবা ও ডিভাইস নিয়ে কাজ করুন—একজন মডেল প্রদানকারীর ওপর নির্ভর না করেই।

| **নিজের মডেল বেছে নিন** | **বাস্তব টুল যুক্ত করুন** | **নিয়ন্ত্রণ নিজের হাতে রাখুন** |
| :--- | :--- | :--- |
| OpenAI, Claude, Gemini, Grok, Bedrock ও Ollama-সহ ক্লাউড এবং স্থানীয় মডেল | ফাইল, কোড, ওয়েব, MCP, Agent Skills, প্লাগইন, ক্লাউড ও IoT | স্থানীয় নির্বাহ, মানুষের অনুমোদন, পরিচয়পত্র সংরক্ষণ ও কনফিগারযোগ্য নীতি |

> UAG হলো **এজেন্ট চালানোর স্তর, মডেল প্রদানকারী নয়**। বাইরের মডেল ও সংযুক্ত সেবায় অনুরোধ কনফিগারেশনের ওপর নির্ভর করে। স্থানীয় কাজকে অগ্রাধিকার দেওয়ার অর্থ সম্পূর্ণ অফলাইন চালনা বা সব টুলের স্বয়ংক্রিয় বিচ্ছিন্নতা নয়।

## দ্রুত শুরু
<!-- README-SYNC:quick-start -->

**Python 3.11 বা নতুন সংস্করণ** প্রয়োজন। [PyPI](https://pypi.org/project/uag/) থেকে UAG ইনস্টল করে ইন্টারঅ্যাক্টিভ CLI চালু করুন:

~~~bash
python -m pip install --upgrade uag
uag
~~~

প্রথমবার চালু করার সময় সেটআপ উইজার্ড মডেল প্রদানকারী বাছাই ও পরিচয়পত্র কনফিগার করতে সাহায্য করে। পরিবেশ ভেরিয়েবল বা সুরক্ষিত ক্রেডেনশিয়াল স্টোরও ব্যবহার করা যায়। আরও প্রদানকারী ও টুলের নির্ভরতা আগেই ইনস্টল করতে:

~~~bash
python -m pip install "uag[core,providers,tools]"
~~~

এরপর নিচের অনুরোধগুলো চেষ্টা করুন:

~~~text
> এই Git রিপোজিটরিতে কী পরিবর্তন হয়েছে? ঝুঁকিগুলো সংক্ষেপ করো।
> এই লাইব্রেরির নতুনতম নথি খুঁজে মাইগ্রেশনের ধাপ ব্যাখ্যা করো।
> এই ফাইলগুলো পরীক্ষা করে সংক্ষিপ্ত প্রতিবেদন তৈরি করো।
> :help
~~~

নতুন ব্যবহারকারীরা Git ও ভার্চুয়াল এনভায়রনমেন্টসহ Windows ইনস্টলেশন গাইড এবং কনফিগারেশন রেফারেন্স পড়তে পারেন: [Quickstart (Windows)](QUICKSTART.md) · [Environment](ENVIRONMENT.md).

## ইন্টারফেস
<!-- README-SYNC:interfaces -->

সব ইন্টারফেস একই এজেন্ট রানটাইম ও টুল রেজিস্ট্রি ব্যবহার করে।

| ইন্টারফেস | চালুর উপায় | উপযোগী কাজ |
| :--- | :--- | :--- |
| **CLI** | `uag` | টার্মিনাল ও স্বয়ংক্রিয়করণ |
| **Desktop** | `uagg` | ডেস্কটপ অ্যাপে কথোপকথন |
| **Web** | `uagw` | ব্রাউজারে কথোপকথন ও রুম |
| **A2A** | `uaga` | এজেন্টগুলোর মধ্যে সংযোগ |
| **VS Code** | [এক্সটেনশন গাইড](VSCODE.md) | কোডের পাশাপাশি কাজ |

Desktop ও Web-এ অতিরিক্ত নির্ভরতা লাগে, যা প্রাথমিক `uag[core,providers,tools]` ইনস্টলে নেই:

~~~bash
# Desktop GUI (PySide6 and platform integrations)
python -m pip install "uag[platform]"

# Web UI (authentication dependencies, FastAPI, and Uvicorn)
python -m pip install "uag[web]" fastapi uvicorn
~~~

Web সার্ভার চালু হওয়ার সময় FastAPI ও Uvicorn ইনস্টল করার চেষ্টা করতে পারে। আগে ইনস্টল করলে সেই স্বয়ংক্রিয় প্রক্রিয়ার ওপর নির্ভর করতে হয় না। বিস্তারিত: [CLI usage](USAGE.md) · [Environment](ENVIRONMENT.md).

## UAG দিয়ে কী তৈরি করা যায়
<!-- README-SYNC:capabilities -->

| সক্ষমতা | UAG যা দেয় |
| :--- | :--- |
| **মডেলনিরপেক্ষ কাজ** | `UAGENT_PROVIDER` দিয়ে ক্লাউড ও স্থানীয় প্রদানকারী বদলানো, টুল আবার লিখতে হয় না |
| **কোড ও ফাইল** | রিপোজিটরি দেখা, Git পরীক্ষা, লিন্ট, টেস্ট, ফাইল পরিচালনা ও ব্রাউজার অটোমেশন |
| **সম্প্রসারণযোগ্য টুল** | ২০০-এর বেশি টুল, `tool_catalog` / `tool_load` দিয়ে গতিশীল অনুসন্ধান, নিজস্ব Python ও Rust টুল |
| **সংযুক্ত এজেন্ট** | MCP, A2A, Claude Code-সামঞ্জস্যপূর্ণ প্লাগইন, Agent Skills ও উপ-এজেন্ট |
| **দীর্ঘ কাজ** | অটোপাইলট, সমান্তরাল স্বাধীন পাঠ, সময়সূচি, পুনরুদ্ধার ও স্থায়ী সেশন |
| **টার্মিনালের বাইরে** | ক্লাউড, যোগাযোগ, নথি, মিডিয়া, রিয়েল-টাইম কণ্ঠস্বর ও সমর্থিত IoT প্রোটোকল |

### একটি রানটাইম, অনেক সংযোগ
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

**সমর্থিত মডেল প্রদানকারীর উদাহরণ** নিচে রয়েছে। প্রদানকারীভিত্তিক সেটিংস পরিবেশ নথিতে বর্ণিত।

**OpenAI · Anthropic · Gemini · Vertex AI · Azure OpenAI · Amazon Bedrock · Grok · DeepSeek · OpenRouter · Ollama · llama.cpp · LM Studio**

[ENVIRONMENT.md](ENVIRONMENT.md)

### স্কিল ও প্লাগইন দিয়ে কাস্টমাইজ
<!-- README-SYNC:extensions -->

মূল অংশ না বদলিয়েও UAG সম্প্রসারণ করা যায়। SkillsMP বা ClawHub থেকে Agent Skills ইনস্টল করুন, MCP সার্ভার যুক্ত করুন অথবা টুল, স্কিল, এজেন্ট ও হুকসহ Claude Code-সামঞ্জস্যপূর্ণ প্লাগইন লোড করুন।

~~~text
:skills mp_search browser automation
:plugin list
:plugin install <source>
:plugin marketplace list
~~~

নিজস্ব টুল `TOOL_SPEC` ও `run_tool()` দিতে পারে; Rust-ভিত্তিক টুলও সমর্থিত। গাইড: [Tool Creator Guide](../TOOL_CREATOR_GUIDE.md) · [Plugin Development Guide](../src/uagent/docs/DEVELOP_PLUGIN.md) · [MCP OAuth / Proxy](MCP_OAUTH_PROXY_GUIDE.md).

## বাস্তব কাজের জন্য তৈরি
<!-- README-SYNC:workflows -->

### প্রসঙ্গ ও স্মৃতি
<!-- README-SYNC:context-memory -->

বড় টুল ফলাফল মডেলের সক্রিয় প্রসঙ্গ পূর্ণ না করে **আর্টিফ্যাক্ট** হিসেবে রাখা যায়। পরে এজেন্ট `artifact_read` দিয়ে প্রয়োজনীয় অংশ উদ্ধার করে। সেশন ডিফল্টভাবে SQLite-এ সংরক্ষিত হয়; ইতিহাস অনুসন্ধান ও স্পষ্ট স্মৃতি পর্যালোচনাও রয়েছে।

- [Context compression](CONTEXT_COMPRESSION.bn.md)
- [Memory](MEMORY.md)
- [Session portability](SESSION_PORTABILITY.md)

### স্বয়ংক্রিয়করণ ও সহযোগিতা
<!-- README-SYNC:automation -->

UAG স্বাধীন পাঠের সমান্তরাল নির্বাহ, বহু এজেন্টের সমন্বয়, সেশন পুনরুদ্ধার ও একাধিক ধাপের কাজের অটোপাইলট সমর্থন করে। `:auto` দিয়ে শুরু করুন; **F12** বর্তমান উত্তর থামিয়ে অটোপাইলট বন্ধের অনুরোধ জানায়।

- [Auto-pilot](README_AUTO.md)
- [Timers and scheduled tasks](SET_TIMER.md)
- [Multi-agent runtime](MULTI_AGENT_RUNTIME.md)

### নিরাপত্তা ও পর্যবেক্ষণযোগ্যতা
<!-- README-SYNC:security -->

সংবেদনশীল কাজের জন্য `human_ask` অনুমোদন চাওয়া যায়। পরিচয়পত্র অপারেটিং সিস্টেমের নিরাপদ স্টোর বা এনক্রিপ্ট করা ফাইলে রাখা যায়। কনফিগার করলে Web ইন্টারফেস OIDC লগইন ও প্রবেশাধিকার নিয়ন্ত্রণ সমর্থন করে। OpenTelemetry ট্রেস ও মেট্রিক **ঐচ্ছিক**।

- [Enterprise policies](ENTERPRISE_POLICY.md)
- [MXC sandbox](SANDBOX_MXC.md)
- [Remote Web / A2A MXC defaults](REMOTE_MXC_DEFAULT.md)
- [Web identity and rooms](WEB_IDENTITY_MEMORY.md)
- [OpenTelemetry design](UAG_OPENTELEMETRY_DESIGN.md)
- [Developer observability](../src/uagent/docs/DEVELOP_OBSERVABILITY.md)

এই নিয়ন্ত্রণগুলো কনফিগারযোগ্য; **সব টুল স্যান্ডবক্সে বিচ্ছিন্নভাবে চলবে—এমন নিশ্চয়তা নয়**। অবিশ্বস্ত ব্যবহারকারী বা নেটওয়ার্কে UAG খোলার আগে স্থাপন ও নীতির গাইড পড়ুন।

### ভাষা, ডিভাইস ও কণ্ঠস্বর
<!-- README-SYNC:languages -->

UAG-এ **৩৮টি ভাষা-লোকেলের** (ইংরেজি ও ৩৭টি অনুবাদ) রিসোর্স, ঐচ্ছিক দ্বিমুখী রিয়েল-টাইম অডিও এবং SwitchBot, Matter, ECHONET Lite, BACnet, Modbus TCP ও OPC UA-এর টুল রয়েছে।

- [Translations](README.translations.md)
- [IoT use cases](IOT_USECASE.md)
- [Communication tools](COMMUNICATION.md)

## নথিপত্র
<!-- README-SYNC:documentation -->

এই গাইডগুলো দিয়ে শুরু করে পরে বিস্তারিত পড়ুন:

| এখান থেকে শুরু | আরও বিস্তারিত |
| :--- | :--- |
| [Quickstart (Windows)](QUICKSTART.md) | [Architecture](ARCHITECTURE.md) |
| [CLI usage](USAGE.md) | [Context management](UAG_CONTEXT_MANAGEMENT_DESIGN.md) |
| [Environment and providers](ENVIRONMENT.md) | [Enterprise policy](ENTERPRISE_POLICY.md) |
| [Agent Skills and plugins](../src/uagent/docs/DEVELOP_PLUGIN.md) | [Tool flow](../src/uagent/docs/TOOL_FLOW.md) |
| [MCP and OAuth](MCP_OAUTH_PROXY_GUIDE.md) | [Computer Use](COMPUTER_USE_IMPLEMENTATION.md) |
| [VS Code extension](VSCODE.md) | [Developer guide](../src/uagent/docs/DEVELOP.md) |

সম্পূর্ণ নথিপত্র ও অন্য ভাষাগুলোও দেখতে পারেন: [Documentation](./) · [Other languages](README.translations.md).

## উন্নয়ন ও অবদান
<!-- README-SYNC:contributing -->

~~~bash
git clone https://github.com/awaku7/agentcli.git
cd agentcli
python -m pip install -e ".[core,providers,test]"
~~~

**Python কোড** বদলানো পুল রিকোয়েস্ট দেওয়ার আগে সংশ্লিষ্ট পরীক্ষা ও প্রকল্প যাচাই চালান:

~~~bash
python -m ruff check src tests
python -m black --check src tests
python -m pytest -q .
~~~

অবদান নীতি ও ডেভেলপার গাইড নিচে রয়েছে। বাগ রিপোর্ট, নথির উন্নয়ন, টুল, অনুবাদ এবং সীমিত পরিসরের পুল রিকোয়েস্ট স্বাগত: [AGENTS.md](../AGENTS.md) · [Developer guide](../src/uagent/docs/DEVELOP.md).

## লাইসেন্স
<!-- README-SYNC:license -->

UAG নিচের লাইসেন্সে প্রকাশিত: [Apache License 2.0](../LICENSE).
