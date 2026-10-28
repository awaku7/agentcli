<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="UAG — Universal AI Gateway" width="620">
</p>
<h1 align="center">UAG</h1>
<p align="center"><strong>Universal AI Gateway</strong><br>तुमची AI मॉडेल्स. तुमची साधने. तुमचे वातावरण.</p>

<p align="center">
  <a href="https://github.com/awaku7/agentcli/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/awaku7/agentcli/ci.yml?style=flat-square&label=CI" alt="CI"></a>
  <a href="https://pypi.org/project/uag/"><img src="https://img.shields.io/pypi/v/uag?style=flat-square" alt="PyPI"></a>
  <a href="https://pypi.org/project/uag/"><img src="https://img.shields.io/pypi/pyversions/uag?style=flat-square" alt="Python versions"></a>
  <a href="../LICENSE"><img src="https://img.shields.io/github/license/awaku7/agentcli?style=flat-square" alt="License"></a>
  <a href="https://pepy.tech/projects/uag"><img src="https://static.pepy.tech/personalized-badge/uag?period=total&units=INTERNATIONAL_SYSTEM&left_color=grey&right_color=green&left_text=downloads" alt="Downloads"></a>
</p>
<p align="center"><a href="../README.md">English</a> · <a href="README.translations.md">इतर भाषा</a></p>

---

**UAG हे मुक्त-स्रोत AI एजंट रनटाइम आहे, जे स्थानिक अंमलबजावणीला प्राधान्य देते.** ते तुमच्या पसंतीचे भाषा मॉडेल तुमच्या वापरातील साधने आणि प्रणालींशी जोडते. एका सुसंगत इंटरफेसमधून कोड, फाइल्स, ब्राउझर, सेवा आणि उपकरणांवर काम करा; एका मॉडेल पुरवठादारावर अवलंबून राहावे लागत नाही.

| **मॉडेल निवडा** | **प्रत्यक्ष साधने जोडा** | **नियंत्रण तुमच्याकडे ठेवा** |
| :--- | :--- | :--- |
| OpenAI, Claude, Gemini, Grok, Bedrock, Ollama यांसारखी क्लाउड आणि स्थानिक मॉडेल्स | फाइल्स, कोड, वेब, MCP, Agent Skills, प्लगइन्स, क्लाउड आणि IoT | स्थानिक अंमलबजावणी, मानवी पुष्टी, क्रेडेन्शियल संचयन आणि बदलता येणारी धोरणे |

> UAG हा **एजंट अंमलबजावणीचा स्तर आहे; मॉडेल पुरवठादार नाही**. बाह्य मॉडेल्स आणि सेवांना होणारे कॉल सेटिंग्जवर अवलंबून असतात. स्थानिक प्राधान्य म्हणजे पूर्णपणे ऑफलाइन कार्य किंवा सर्व साधनांचे आपोआप विलगीकरण नव्हे.

## झटपट सुरुवात
<!-- README-SYNC:quick-start -->

**Python 3.11 किंवा नवीन** आवृत्ती आवश्यक आहे. [PyPI](https://pypi.org/project/uag/) वरून UAG इन्स्टॉल करून परस्परसंवादी CLI सुरू करा:

~~~bash
python -m pip install --upgrade uag
uag
~~~

पहिल्यांदा सुरू करताना सेटअप विझार्ड मॉडेल पुरवठादार निवडण्यासाठी आणि क्रेडेन्शियल सेट करण्यासाठी मदत करतो. पर्यावरण चल किंवा सुरक्षित क्रेडेन्शियल स्टोअरही वापरता येते. पुरवठादार आणि साधनांच्या अधिक अवलंबनांसाठी आधी हे इन्स्टॉल करा:

~~~bash
python -m pip install "uag[core,providers,tools]"
~~~

त्यानंतर हे प्रश्न विचारून पाहा:

~~~text
> या Git रिपॉझिटरीमध्ये काय बदल झाले? धोके थोडक्यात सांगा.
> या लायब्ररीचे नवीनतम दस्तऐवज शोधा आणि स्थलांतराची पावले समजवा.
> या फाइल्स तपासून थोडक्यात अहवाल तयार करा.
> :help
~~~

नवीन वापरकर्त्यांनी Git आणि व्हर्च्युअल वातावरणांसह Windows स्थापना मार्गदर्शक आणि कॉन्फिगरेशन संदर्भ पाहावा: [Quickstart (Windows)](QUICKSTART.md) · [Environment](ENVIRONMENT.md).

## इंटरफेस
<!-- README-SYNC:interfaces -->

सर्व इंटरफेस एकच एजंट रनटाइम आणि साधनांची नोंदणी वापरतात.

| इंटरफेस | सुरू करण्याची पद्धत | उपयोग |
| :--- | :--- | :--- |
| **CLI** | `uag` | टर्मिनल आणि स्वयंचलन |
| **Desktop** | `uagg` | डेस्कटॉप अॅपमधील संवाद |
| **Web** | `uagw` | ब्राउझरमधील संवाद आणि रूम |
| **A2A** | `uaga` | एजंटमधील एकत्रीकरण |
| **VS Code** | [एक्स्टेन्शन मार्गदर्शक](VSCODE.md) | कोडसोबत काम |

Desktop आणि Web साठी अतिरिक्त अवलंबने आवश्यक आहेत; ती `uag[core,providers,tools]` मध्ये समाविष्ट नाहीत:

~~~bash
# Desktop GUI (PySide6 and platform integrations)
python -m pip install "uag[platform]"

# Web UI (authentication dependencies, FastAPI, and Uvicorn)
python -m pip install "uag[web]" fastapi uvicorn
~~~

Web सर्व्हर सुरू होताना FastAPI व Uvicorn इन्स्टॉल करण्याचा प्रयत्न करू शकतो. आधीच इन्स्टॉल केल्यास स्वयंचलित स्थापनेवर अवलंबून राहावे लागत नाही. तपशील: [CLI usage](USAGE.md) · [Environment](ENVIRONMENT.md).

## UAG वापरून काय तयार करता येते
<!-- README-SYNC:capabilities -->

| क्षमता | UAG काय देते |
| :--- | :--- |
| **मॉडेलनिरपेक्ष कार्यप्रवाह** | `UAGENT_PROVIDER` ने क्लाउड आणि स्थानिक पुरवठादार बदला; साधने पुन्हा लिहावी लागत नाहीत |
| **कोड आणि फाइल्स** | रिपॉझिटरी पाहणे, Git तपासणी, लिंट, चाचण्या, फाइल ऑपरेशन्स आणि ब्राउझर स्वयंचलन |
| **विस्तारक्षम साधने** | २०० पेक्षा अधिक साधने, `tool_catalog` / `tool_load` ने गतिशील शोध, स्वतःची Python आणि Rust साधने |
| **जोडलेले एजंट** | MCP, A2A, Claude Code सुसंगत प्लगइन, Agent Skills आणि उपएजंट |
| **दीर्घकालीन कामे** | ऑटोपायलट, समांतर स्वतंत्र वाचन, वेळापत्रक, पुनर्प्राप्ती आणि जतन केलेली सत्रे |
| **टर्मिनलच्या पलीकडे** | क्लाउड, संवाद, दस्तऐवज, मीडिया, रिअल-टाइम आवाज आणि समर्थित IoT प्रोटोकॉल |

### एक रनटाइम, अनेक एकत्रीकरणे
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

**समर्थित मॉडेल पुरवठादारांची उदाहरणे** खाली आहेत. प्रत्येक पुरवठादाराची सेटिंग्ज पर्यावरण दस्तऐवजात आहेत.

**OpenAI · Anthropic · Gemini · Vertex AI · Azure OpenAI · Amazon Bedrock · Grok · DeepSeek · OpenRouter · Ollama · llama.cpp · LM Studio**

[ENVIRONMENT.md](ENVIRONMENT.md)

### स्किल्स आणि प्लगइनद्वारे सानुकूलन
<!-- README-SYNC:extensions -->

मूळ कोड न बदलता UAG विस्तारित करा. SkillsMP किंवा ClawHub वरून Agent Skills इन्स्टॉल करा, MCP सर्व्हर जोडा किंवा साधने, स्किल्स, एजंट व hooks असलेले Claude Code सुसंगत प्लगइन लोड करा.

~~~text
:skills mp_search browser automation
:plugin list
:plugin install <source>
:plugin marketplace list
~~~

स्वतःची साधने `TOOL_SPEC` आणि `run_tool()` उपलब्ध करून देऊ शकतात; Rust आधारित साधनांनाही समर्थन आहे. मार्गदर्शक: [Tool Creator Guide](../TOOL_CREATOR_GUIDE.md) · [Plugin Development Guide](../src/uagent/docs/DEVELOP_PLUGIN.md) · [MCP OAuth / Proxy](MCP_OAUTH_PROXY_GUIDE.md).

## प्रत्यक्ष कार्यप्रवाहांसाठी
<!-- README-SYNC:workflows -->

### संदर्भ आणि स्मृती
<!-- README-SYNC:context-memory -->

मोठे साधन परिणाम मॉडेलचा सक्रिय संदर्भ भरून टाकण्याऐवजी **आर्टिफॅक्ट्स** म्हणून ठेवता येतात. एजंट नंतर `artifact_read` द्वारे आवश्यक भागच मिळवतो. सत्रे डिफॉल्टने SQLite मध्ये साठवली जातात; इतिहास शोध आणि स्पष्ट स्मृती पुनरावलोकनही उपलब्ध आहे.

- [Context compression](CONTEXT_COMPRESSION.mr.md)
- [Memory](MEMORY.md)
- [Session portability](SESSION_PORTABILITY.md)

### स्वयंचलन आणि सहकार्य
<!-- README-SYNC:automation -->

UAG स्वतंत्र वाचनाचे समांतर काम, अनेक एजंटांचे समन्वय, सत्र पुनर्प्राप्ती आणि अनेक फेऱ्यांच्या कामासाठी ऑटोपायलट समर्थित करते. `:auto` ने सुरू करा; **F12** सध्याचे उत्तर थांबवून ऑटोपायलट बंद करण्याची विनंती करते.

- [Auto-pilot](README_AUTO.md)
- [Timers and scheduled tasks](SET_TIMER.md)
- [Multi-agent runtime](MULTI_AGENT_RUNTIME.md)

### सुरक्षा आणि निरीक्षणक्षमता
<!-- README-SYNC:security -->

संवेदनशील कामांपूर्वी `human_ask` पुष्टी मागता येते. क्रेडेन्शियल ऑपरेटिंग सिस्टिमच्या सुरक्षित स्टोअरमध्ये किंवा एन्क्रिप्टेड फाइलमध्ये ठेवता येतात. Web इंटरफेस सेट केलेले OIDC लॉगिन आणि प्रवेश नियंत्रण समर्थित करते. OpenTelemetry ट्रेसिंग आणि मेट्रिक्स **पर्यायी** आहेत.

- [Enterprise policies](ENTERPRISE_POLICY.md)
- [MXC sandbox](SANDBOX_MXC.md)
- [Remote Web / A2A MXC defaults](REMOTE_MXC_DEFAULT.md)
- [Web identity and rooms](WEB_IDENTITY_MEMORY.md)
- [OpenTelemetry design](UAG_OPENTELEMETRY_DESIGN.md)
- [Developer observability](../src/uagent/docs/DEVELOP_OBSERVABILITY.md)

ही नियंत्रणे कॉन्फिगर करता येतात, पण **प्रत्येक साधन sandbox मध्ये वेगळेच चालेल याची हमी नाही**. UAG अविश्वसनीय वापरकर्त्यांना किंवा नेटवर्कला उपलब्ध करण्याआधी तैनाती आणि धोरण मार्गदर्शक वाचा.

### भाषा, उपकरणे आणि आवाज
<!-- README-SYNC:languages -->

UAG मध्ये **३८ भाषा-लोकेल्स** (इंग्रजी आणि ३७ भाषांतरे), पर्यायी द्विदिश ध्वनी एकत्रीकरण आणि SwitchBot, Matter, ECHONET Lite, BACnet, Modbus TCP व OPC UA साठी साधने आहेत.

- [Translations](README.translations.md)
- [IoT use cases](IOT_USECASE.md)
- [Communication tools](COMMUNICATION.md)

## दस्तऐवज
<!-- README-SYNC:documentation -->

या मार्गदर्शकांपासून सुरुवात करा आणि मग सविस्तर माहिती वाचा:

| येथून सुरुवात | अधिक माहिती |
| :--- | :--- |
| [Quickstart (Windows)](QUICKSTART.md) | [Architecture](ARCHITECTURE.md) |
| [CLI usage](USAGE.md) | [Context management](UAG_CONTEXT_MANAGEMENT_DESIGN.md) |
| [Environment and providers](ENVIRONMENT.md) | [Enterprise policy](ENTERPRISE_POLICY.md) |
| [Agent Skills and plugins](../src/uagent/docs/DEVELOP_PLUGIN.md) | [Tool flow](../src/uagent/docs/TOOL_FLOW.md) |
| [MCP and OAuth](MCP_OAUTH_PROXY_GUIDE.md) | [Computer Use](COMPUTER_USE_IMPLEMENTATION.md) |
| [VS Code extension](VSCODE.md) | [Developer guide](../src/uagent/docs/DEVELOP.md) |

सर्व दस्तऐवज आणि इतर भाषाही पाहता येतात: [Documentation](./) · [Other languages](README.translations.md).

## विकास आणि योगदान
<!-- README-SYNC:contributing -->

~~~bash
git clone https://github.com/awaku7/agentcli.git
cd agentcli
python -m pip install -e ".[core,providers,test]"
~~~

**Python कोड** बदलणारी पुल रिक्वेस्ट करण्यापूर्वी संबंधित चाचण्या आणि प्रकल्प तपासण्या चालवा:

~~~bash
python -m ruff check src tests
python -m black --check src tests
python -m pytest -q .
~~~

योगदान नियम व विकासक मार्गदर्शक खाली आहेत. बग अहवाल, दस्तऐवज सुधारणा, साधने, भाषांतरे आणि नेमक्या व्याप्तीच्या पुल रिक्वेस्टचे स्वागत आहे: [AGENTS.md](../AGENTS.md) · [Developer guide](../src/uagent/docs/DEVELOP.md).

## परवाना
<!-- README-SYNC:license -->

UAG खालील परवान्यांतर्गत वितरित केले जाते: [Apache License 2.0](../LICENSE).
