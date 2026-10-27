<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="UAG — Universal AI Gateway" width="620">
</p>
<h1 align="center">UAG</h1>
<p align="center"><strong>Universal AI Gateway</strong><br>आपके AI मॉडल। आपके टूल। आपका परिवेश।</p>

<p align="center">
  <a href="https://github.com/awaku7/agentcli/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/awaku7/agentcli/ci.yml?style=flat-square&label=CI" alt="CI"></a>
  <a href="https://pypi.org/project/uag/"><img src="https://img.shields.io/pypi/v/uag?style=flat-square" alt="PyPI"></a>
  <a href="https://pypi.org/project/uag/"><img src="https://img.shields.io/pypi/pyversions/uag?style=flat-square" alt="Python versions"></a>
  <a href="../LICENSE"><img src="https://img.shields.io/github/license/awaku7/agentcli?style=flat-square" alt="License"></a>
  <a href="https://pepy.tech/projects/uag"><img src="https://static.pepy.tech/personalized-badge/uag?period=total&units=INTERNATIONAL_SYSTEM&left_color=grey&right_color=green&left_text=downloads" alt="Downloads"></a>
</p>
<p align="center"><a href="../README.md">English</a> · <a href="README.translations.md">अन्य भाषाएँ</a></p>

---

**UAG एक मुक्त-स्रोत AI एजेंट रनटाइम है जो स्थानीय संचालन को प्राथमिकता देता है।** यह आपकी पसंद के भाषा मॉडल को आपके उपयोग के टूल और सिस्टम से जोड़ता है। एक समान इंटरफ़ेस से कोड, फ़ाइलों, ब्राउज़र, सेवाओं और उपकरणों पर काम करें, बिना किसी एक मॉडल प्रदाता पर निर्भर हुए।

| **अपना मॉडल चुनें** | **वास्तविक टूल जोड़ें** | **नियंत्रण अपने हाथ रखें** |
| :--- | :--- | :--- |
| OpenAI, Claude, Gemini, Grok, Bedrock, Ollama जैसे क्लाउड और स्थानीय मॉडल | फ़ाइलें, कोड, वेब, MCP, Agent Skills, प्लगइन, क्लाउड सेवाएँ और IoT | स्थानीय निष्पादन, मानव पुष्टि, क्रेडेंशियल संग्रहण और विन्यास योग्य नीतियाँ |

> UAG **एजेंट निष्पादन की परत है, मॉडल प्रदाता नहीं**। बाहरी मॉडल और सेवाओं को कॉल करना आपके विन्यास पर निर्भर करता है। स्थानीय प्राथमिकता का अर्थ यह नहीं कि सब कुछ डिफ़ॉल्ट रूप से पूरी तरह ऑफ़लाइन या अलग-थलग चलता है।

## त्वरित शुरुआत
<!-- README-SYNC:quick-start -->

**Python 3.11 या नया** संस्करण आवश्यक है। [PyPI](https://pypi.org/project/uag/) से UAG स्थापित करें और इंटरैक्टिव CLI चलाएँ:

~~~bash
python -m pip install --upgrade uag
uag
~~~

पहले चलाने पर सेटअप विज़ार्ड मॉडल प्रदाता चुनने और क्रेडेंशियल सेट करने में मदद करता है। पर्यावरण चर या सुरक्षित क्रेडेंशियल स्टोर भी इस्तेमाल कर सकते हैं। अधिक प्रदाता और टूल निर्भरताएँ पहले से स्थापित करने के लिए:

~~~bash
python -m pip install "uag[core,providers,tools]"
~~~

फिर ये अनुरोध आज़माएँ:

~~~text
> इस Git रिपॉज़िटरी में क्या बदला? जोखिमों का सार बताओ।
> इस लाइब्रेरी का नवीनतम दस्तावेज़ ढूँढ़ो और माइग्रेशन के चरण समझाओ।
> इन फ़ाइलों की जाँच करके संक्षिप्त रिपोर्ट बनाओ।
> :help
~~~

नए उपयोगकर्ता Git और वर्चुअल परिवेश सहित Windows स्थापना मार्गदर्शिका तथा कॉन्फ़िगरेशन संदर्भ पढ़ सकते हैं: [Quickstart (Windows)](QUICKSTART.md) · [Environment](ENVIRONMENT.md).

## इंटरफ़ेस
<!-- README-SYNC:interfaces -->

सभी इंटरफ़ेस एक ही एजेंट रनटाइम और टूल रजिस्ट्री का उपयोग करते हैं।

| इंटरफ़ेस | शुरू करने का तरीका | उपयोग |
| :--- | :--- | :--- |
| **CLI** | `uag` | टर्मिनल और स्वचालन |
| **Desktop** | `uagg` | डेस्कटॉप ऐप में बातचीत |
| **Web** | `uagw` | ब्राउज़र में बातचीत और कमरे |
| **A2A** | `uaga` | एजेंटों के बीच एकीकरण |
| **VS Code** | [एक्सटेंशन मार्गदर्शिका](VSCODE.md) | कोड के साथ काम |

Desktop और Web को अतिरिक्त निर्भरताएँ चाहिए, जो प्रारंभिक `uag[core,providers,tools]` स्थापना में नहीं हैं:

~~~bash
# Desktop GUI (PySide6 and platform integrations)
python -m pip install "uag[platform]"

# Web UI (authentication dependencies, FastAPI, and Uvicorn)
python -m pip install "uag[web]" fastapi uvicorn
~~~

Web सर्वर शुरू होते समय FastAPI और Uvicorn स्थापित करने की कोशिश भी कर सकता है। इन्हें पहले से स्थापित करने से स्वचालित स्थापना पर निर्भरता नहीं रहती। विवरण: [CLI usage](USAGE.md) · [Environment](ENVIRONMENT.md).

## UAG से क्या बनाया जा सकता है
<!-- README-SYNC:capabilities -->

| क्षमता | UAG क्या देता है |
| :--- | :--- |
| **मॉडल-स्वतंत्र कार्यप्रवाह** | `UAGENT_PROVIDER` से क्लाउड और स्थानीय प्रदाता बदलें, टूल फिर से लिखने की आवश्यकता नहीं |
| **कोड और फ़ाइलें** | रिपॉज़िटरी नेविगेशन, Git निरीक्षण, लिंट, परीक्षण, फ़ाइल संचालन और ब्राउज़र स्वचालन |
| **विस्तार योग्य टूल** | 200 से अधिक टूल, `tool_catalog` / `tool_load` से गतिशील खोज, Python और Rust के कस्टम टूल |
| **जुड़े हुए एजेंट** | MCP, A2A, Claude Code संगत प्लगइन, Agent Skills और उप-एजेंट |
| **लंबे कार्य** | ऑटोपायलट, स्वतंत्र पढ़ने के कार्य समानांतर, शेड्यूल, पुनर्प्राप्ति और स्थायी सत्र |
| **टर्मिनल से आगे** | क्लाउड, संचार, दस्तावेज़, मीडिया, रीयल-टाइम आवाज़ और समर्थित IoT प्रोटोकॉल |

### एक रनटाइम, अनेक एकीकरण
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

**समर्थित मॉडल प्रदाताओं के उदाहरण** नीचे हैं। प्रदाता-विशिष्ट सेटिंग्स पर्यावरण दस्तावेज़ में मिलेंगी।

### स्किल और प्लगइन से अनुकूलन
<!-- README-SYNC:extensions -->

मूल कोड बदले बिना UAG का विस्तार करें। SkillsMP या ClawHub से Agent Skills स्थापित करें, MCP सर्वर जोड़ें या टूल, स्किल, एजेंट और hooks वाले Claude Code संगत प्लगइन लोड करें।

~~~text
:skills mp_search browser automation
:plugin list
:plugin install <source>
:plugin marketplace list
~~~

कस्टम टूल `TOOL_SPEC` और `run_tool()` दे सकते हैं; Rust आधारित टूल भी समर्थित हैं। मार्गदर्शिकाएँ: [Tool Creator Guide](../TOOL_CREATOR_GUIDE.md) · [Plugin Development Guide](../src/uagent/docs/DEVELOP_PLUGIN.md) · [MCP OAuth / Proxy](MCP_OAUTH_PROXY_GUIDE.md).

## वास्तविक कार्यप्रवाहों के लिए
<!-- README-SYNC:workflows -->

### संदर्भ और स्मृति
<!-- README-SYNC:context-memory -->

बड़े टूल परिणामों को सक्रिय मॉडल संदर्भ में भरने के बजाय **आर्टिफ़ैक्ट** के रूप में रखा जा सकता है। बाद में एजेंट `artifact_read` से केवल आवश्यक हिस्सा ले सकता है। सत्र डिफ़ॉल्ट रूप से SQLite में संग्रहीत होते हैं, साथ में इतिहास खोज और स्पष्ट स्मृति समीक्षा भी उपलब्ध है।

- [Context compression](CONTEXT_COMPRESSION.hi.md)
- [Memory](MEMORY.md)
- [Session portability](SESSION_PORTABILITY.md)

### स्वचालन और सहयोग
<!-- README-SYNC:automation -->

UAG स्वतंत्र पढ़ने के कार्यों का समानांतर निष्पादन, अनेक एजेंटों का समन्वय, सत्र पुनर्प्राप्ति और कई चरणों वाले कार्यों के लिए ऑटोपायलट समर्थित करता है। `:auto` से शुरू करें; **F12** वर्तमान उत्तर रोककर ऑटोपायलट बंद करने का अनुरोध करता है।

- [Auto-pilot](README_AUTO.md)
- [Timers and scheduled tasks](SET_TIMER.md)
- [Multi-agent runtime](MULTI_AGENT_RUNTIME.md)

### सुरक्षा और अवलोकनीयता
<!-- README-SYNC:security -->

संवेदनशील कार्रवाइयों के लिए `human_ask` पुष्टि आवश्यक की जा सकती है। क्रेडेंशियल ऑपरेटिंग सिस्टम के प्रबंधक या एन्क्रिप्टेड फ़ाइल में रखे जा सकते हैं। Web इंटरफ़ेस कॉन्फ़िगर किए गए OIDC लॉगिन और पहुँच नियंत्रण को समर्थित करता है। OpenTelemetry ट्रेस और मेट्रिक्स **वैकल्पिक** हैं।

- [Enterprise policies](ENTERPRISE_POLICY.md)
- [MXC sandbox](SANDBOX_MXC.md)
- [Remote Web / A2A MXC defaults](REMOTE_MXC_DEFAULT.md)
- [Web identity and rooms](WEB_IDENTITY_MEMORY.md)
- [OpenTelemetry design](UAG_OPENTELEMETRY_DESIGN.md)
- [Developer observability](../src/uagent/docs/DEVELOP_OBSERVABILITY.md)

ये नियंत्रण कॉन्फ़िगर किए जा सकते हैं, लेकिन **इस बात की गारंटी नहीं** देते कि हर टूल पृथक sandbox में चलेगा। UAG को अविश्वसनीय उपयोगकर्ताओं या नेटवर्क के लिए खोलने से पहले तैनाती और नीति मार्गदर्शिकाएँ पढ़ें।

### भाषाएँ, उपकरण और आवाज़
<!-- README-SYNC:languages -->

UAG में **38 भाषा-क्षेत्रों** (अंग्रेज़ी और 37 अनुवाद), वैकल्पिक दोनों ओर एक साथ आवाज़ संचार और SwitchBot, Matter, ECHONET Lite, BACnet, Modbus TCP तथा OPC UA के टूल के लिए संसाधन हैं।

- [Translations](README.translations.md)
- [IoT use cases](IOT_USECASE.md)
- [Communication tools](COMMUNICATION.md)

## दस्तावेज़
<!-- README-SYNC:documentation -->

इन मार्गदर्शिकाओं से शुरुआत करें और फिर विषयों को विस्तार से पढ़ें:

| यहाँ से शुरू करें | विस्तार से जानें |
| :--- | :--- |
| [Quickstart (Windows)](QUICKSTART.md) | [Architecture](ARCHITECTURE.md) |
| [CLI usage](USAGE.md) | [Context management](UAG_CONTEXT_MANAGEMENT_DESIGN.md) |
| [Environment and providers](ENVIRONMENT.md) | [Enterprise policy](ENTERPRISE_POLICY.md) |
| [Agent Skills and plugins](../src/uagent/docs/DEVELOP_PLUGIN.md) | [Tool flow](../src/uagent/docs/TOOL_FLOW.md) |
| [MCP and OAuth](MCP_OAUTH_PROXY_GUIDE.md) | [Computer Use](COMPUTER_USE_IMPLEMENTATION.md) |
| [VS Code extension](VSCODE.md) | [Developer guide](../src/uagent/docs/DEVELOP.md) |

पूरा दस्तावेज़ संग्रह और अन्य भाषाएँ भी देखें: [Documentation](./) · [Other languages](README.translations.md).

## विकास और योगदान
<!-- README-SYNC:contributing -->

~~~bash
git clone https://github.com/awaku7/agentcli.git
cd agentcli
python -m pip install -e ".[core,providers,test]"
~~~

**Python कोड** बदलने वाले पुल अनुरोध से पहले संबंधित परीक्षण और प्रोजेक्ट जाँच चलाएँ:

~~~bash
python -m ruff check src tests
python -m black --check src tests
python -m pytest -q .
~~~

योगदान नियम और डेवलपर मार्गदर्शिका नीचे हैं। बग रिपोर्ट, दस्तावेज़ सुधार, टूल, अनुवाद और सीमित दायरे वाले पुल अनुरोधों का स्वागत है: [AGENTS.md](../AGENTS.md) · [Developer guide](../src/uagent/docs/DEVELOP.md).

## लाइसेंस
<!-- README-SYNC:license -->

UAG निम्न लाइसेंस के अंतर्गत उपलब्ध है: [Apache License 2.0](../LICENSE).
