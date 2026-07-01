<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="720">
</p>

<h1 align="center">uag — युनिव्हर्सल एआय गेटवे</h1>

<p align="center">
  <b>U</b>niversal <b>A</b>I <b>G</b>ateway — Your environment, your freedom.
</p>

<p align="center">
  File ops / Web search / Image generation &amp; analysis / PDF &amp; Excel extraction / IoT control / MCP integration<br>
  15+ providers / 3 UIs / Parallel tool execution / Agent Skills marketplace
</p>

<p align="center">
  <a href="https://github.com/awaku7/agentcli">GitHub</a>
  ·
  <a href="https://pypi.org/project/uag/">PyPI</a>
  ·
  <a href="https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md">Read this in your language</a>
</p>

---

## का उग?

**विक्रेता लॉक-इनपासून मुक्त व्हा.** बहुतेक AI सहाय्यक तुम्हाला विशिष्ट प्रदाता किंवा क्लाउड सेवेशी जोडतात. uag वेगळे आहे.

- **Runs locally** on your machine. Your data stays with you (except API calls you make).
- **Provider freedom**: OpenAI, Claude, Gemini, DeepSeek, Ollama, Azure, Bedrock, HuggingFace... 15+ providers, all accessible from a single interface. Swap between them by reconfiguring environment variables — no reinstall, no migration.
- **131 tools**: File I/O, web search, image generation, Gmail, BLE device scanning, MCP server integration — **76 are parallel-safe** (up to 8 execute concurrently via thread pool, configurable via `UAGENT_PARALLEL_WORKERS`). When the LLM fires multiple tool calls at once, uag automatically parallelizes them.
- **3 UIs + A2A**: CLI, GUI, Web, and Agent-to-Agent protocol. Same engine, any interface.
- **IoT ready**: SwitchBot, ECHONET Lite, Matter, UPnP — control your home devices through AI.
- **Agent Skills**: Install community-built skills from the marketplace. Extend uag endlessly.

uag हा **तुमच्या अटींवर तुमचा AI सहाय्यक आहे**. प्रदात्याशी बांधलेले नाही, इंटरफेसशी बांधलेले नाही, प्लॅटफॉर्मशी बांधलेले नाही.

## द्रुत सुरुवात

```bash
pip install uag
uag
```

पहिल्या लॉन्चवर, सेटअप विझार्ड तुम्हाला प्रदाता कॉन्फिगरेशनमध्ये घेऊन जातो.
सर्व पर्यावरणीय चलांसाठी [ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md) पहा.

## वैशिष्ट्ये

### 🧠 मल्टी-प्रोव्हायडर आर्किटेक्चर

OpenAI / Azure / Bedrock / OpenRouter / Ollama / Gemini / Vertex AI / Claude / Grok / NVIDIA / DeepSeek / Z.AI (Zhipu AI) / HuggingFace / Alibaba Cloud (Qwen) / KIMI (Moonshot AI) / Xiaomi MiMo / LMAkguana / MinFa_Studio**

सर्व प्रदाते समान टूलसेट आणि इंटरफेस सामायिक करतात. `UAGENT_PROVIDER` सेट करून स्विच करा — कोणतेही कोड बदल नाहीत, वेगळे इंस्टॉलेशन नाहीत.

### ⚡ समांतर टूल एक्झिक्यूशन

जेव्हा LLM एकाच वेळी अनेक साधनांची विनंती करते, तेव्हा uag **आपोआप त्यांना समांतर करते**.
76 साधने `x_parallel_safe` म्हणून चिन्हांकित केली आहेत आणि `ThreadPoolExecutor` द्वारे एकाच वेळी कार्यान्वित करा (8 थ्रेड बाय डीफॉल्ट; बदलण्यासाठी `UAGENT_PARALLEL_WORKERS` सेट करा).

**उदाहरण**: "नॉर्डिक कॅपिटलमधील हवामान तपासा" विचारा → LLM फायर्स `search_web` × 5 देश → सर्व 5 शोध समांतर चालतात → एका बॅचमध्ये एकत्रित केलेले परिणाम.

केवळ-वाचनीय साधने (फाइल शोध, हॅश गणना, निर्देशिका सूची, भाषांतर, डीबी क्वेरी इ.) आक्रमकपणे समांतर आहेत.

### 🔄 सत्र सातत्य

- **Switch providers mid-session** with `UAGENT_PROVIDER` — conversation history is preserved.
- **Reload past sessions** with `:load <index>` — pick up where you left off.
- **Tool result caching** avoids redundant re-execution when the same tool call repeats.

### 🛠 १३१ साधने

| श्रेणी | साधने |
|---|---|
| **फाइल ऑपरेशन्स** | read/write/create/delete/search/grep/hash/zip, parse_eml (.eml फाइल्स) |
| **वेब** | fetch_url, search_web, स्क्रीनशॉट, browser_playwright |
| **मीडिया** | generate_image, analyze_image, img2img, audio_speech, audio_transscribe |
| **कागदपत्रे** | PDF/PPTX/DOCX/RTF/ODT एक्स्ट्रॅक्शन, एक्सेल स्ट्रक्चर्ड एक्सट्रॅक्शन |
| **संवाद** | gmail_send, gmail_read, bluesky, discord_channel, teams_webhook — पहा [COMMUNICATION.md](https://github.com/awaku7/agentcli/blob/main/docs/COMMUNICATION.md) |
| **IoT** | SwitchBot (Cloud + BLE), ECHONET Lite, Matter, UPnP |
| **देव साधने** | git_ops, python_compile, lint_format, run_tests, db_query, **१३ सोर्स कोड नेव्हिगेटर (idx फॅमिली)** |
| **MCP** | बाह्य MCP सर्व्हरशी कनेक्ट करा, साधने सूची करा, कार्यान्वित करा |
| **A2A** | एजंट-टू-एजंट संप्रेषण (इतर uag उदाहरणे किंवा A2A-सुसंगत सर्व्हरसह) |
| **सिस्टम** | env vars, सिस्टम स्पेक्स, वेळ, तारीख गणना |
| **स्रोत Nav** | Python, PHP, TypeScript, Java, C#, Dart, C/C++, Rust, Go, Swift, Kotlin, COBOL साठी **13 idx टूल्स** — संपूर्ण फाइल न वाचता फंक्शन/क्लास इंडेक्स किंवा विशिष्ट व्याख्या मिळवा |

### 🖥 4 इंटरफेस + VS कोड विस्तार

| मोड | आज्ञा | उद्देश |
|---|---|---|
| **CLI** | `uag` | फास्ट टर्मिनल-आधारित ऑपरेशन |
| **GUI** | `uagg` | tkinter द्वारे डेस्कटॉप UI |
| **वेब** | `uagw` | ब्राउझर-आधारित प्रवेश |
| **A2A सर्व्हर** | `उगा` | मल्टी-एजंट संप्रेषणासाठी Agent2Agent प्रोटोकॉल |
| **VS कोड** | — | [विस्तार](https://github.com/awaku7/agentcli/blob/main/VSCODE.md) चॅट पॅनेलसह, स्पष्टीकरण, रिफॅक्टर, त्रुटी दूर करा आणि टूल्स ट्री व्ह्यू |

व्हीएस कोड एक्स्टेंशन — इंस्टॉलेशन, कमांड, कीबाइंडिंग आणि कॉन्फिगरेशनच्या तपशीलांसाठी [VSCODE.md](https://github.com/awaku7/agentcli/blob/main/VSCODE.md) पहा.

### 🏠 IoT डिव्हाइस नियंत्रण

- **स्विचबॉट**: क्लाउड बॅच कंट्रोल आणि BLE स्कॅन/नियंत्रण
- **ECHONET Lite**: स्थानिक नेटवर्कवर घरगुती उपकरणे (AC, लाइट, वॉटर हीटर्स इ.) शोधा आणि नियंत्रित करा
- **मॅटर**: कंट्रोलर/ब्रिज/डिव्हाइस टोपोलॉजीची केवळ वाचनीय तपासणी
- **UPnP**: डिव्हाइस शोध आणि IGD पोर्ट फॉरवर्डिंग

पहा [IOT_USECASE.md](https://github.com/awaku7/agentcli/blob/main/IOT_USECASE.md)

### 🎯 एजंट स्किल्स मार्केटप्लेस

समुदाय कौशल्यांसाठी [SkillsMP](https://skillsmp.com) आणि [ClawHub](https://clawhub.ai) ब्राउझ करण्यासाठी `:skills mp_search`.
फ्लायवर uag च्या क्षमता स्थापित करा आणि वाढवा.

### 🤖 ऑटो-पायलट (`:ऑटो`)

uag **एकाहून अधिक LLM फेऱ्यांमध्ये स्वायत्तपणे ध्येयाचा पाठपुरावा करू शकतो**. जटिल, बहु-चरण कार्यांसाठी योग्य ज्यांना पुनरावृत्ती परिष्करण आवश्यक आहे.

- **ते कसे कार्य करते**: प्रत्येक फेरीत एक मुख्य क्वेरी (चरण A) असते आणि त्यानंतर समीक्षकाचा निर्णय (चरण B) असतो जो "पूर्ण किंवा सुरू ठेवा?"
- **समान प्रदाता, समान API**: पुनरावलोकनकर्ता निर्णय मुख्य क्वेरी म्हणून समान कोड पथ वापरतो — प्रतिसाद API समर्थनासह.
- **वेगळा न्यायाधीश LLM** (पर्यायी): पुनरावलोकनकर्त्यासाठी वेगळा प्रदाता/मॉडेल वापरण्यासाठी `UAGENT_AP_PROVIDER` सेट करा (उदा. न्यायासाठी स्वस्त मॉडेल वापरा).
- **केव्हाही बाहेर पडा**: लगेच थांबण्यासाठी `x` की दाबा, अगदी मध्य-प्रतिसादही. किंवा ध्येय कधी पूर्ण होईल हे समीक्षकाला ठरवू द्या.
- **कॉन्फिगर करण्यायोग्य**: बजेट नियंत्रित करण्यासाठी `--अधिकतम फेरी N`.

संपूर्ण कागदपत्रांसाठी [README_AUTO.md](https://github.com/awaku7/agentcli/blob/main/README_AUTO.md) पहा.

### 🧩 बॅच स्टेट मॅनेजर

uag दीर्घकाळ चालणाऱ्या मल्टी-फाइल टास्कमध्ये प्रगतीचा मागोवा घेऊ शकते. जेव्हा LLM डझनभर फाइल्सवर प्रक्रिया करते, तेव्हा `batch_state` डिस्कवर प्रलंबित, पूर्ण झालेल्या आणि अयशस्वी फाइल्सची सूची कायम ठेवते. जर सत्र संपले किंवा राऊंड टाइम आउट झाला, तर पुढची रन जिथे थांबली होती तिथून पुन्हा सुरू होते - काहीही गमावले जात नाही.

### 🛡 मानवी-इन-द-लूप

`human_ask` LLM ला विराम देऊ देते आणि विध्वंसक ऑपरेशन्स (फाइल हटवणे, ओव्हरराईट, शेल कमांड) करण्यापूर्वी तुमची पुष्टी मागू देते. तुम्ही नियंत्रणात रहा.

### 🛑 व्यत्यय (c-की / थांबवा बटण)

LLM प्रतिसाद निर्मिती कधीही थांबवा आणि LLM ला परत एक stop कमांड इंजेक्ट करा.

| इंटरफेस | व्यत्यय कसा आणावा |
|---|---|
| **CLI** | LLM प्रवाहादरम्यान `c` की दाबा — वर्तमान प्रतिसाद थांबतो, आणि `"थांबा"` वापरकर्ता संदेश म्हणून पाठविला जातो जेणेकरून LLM त्यानुसार प्रतिसाद देईल |
| **वेब UI** | लाल **■ थांबवा** बटणावर क्लिक करा (LLM प्रक्रियेदरम्यान स्वयंचलितपणे दिसून येते) |
| **डेस्कटॉप GUI** | लाल **■** बटणावर क्लिक करा (एलएलएम प्रक्रियेदरम्यान स्वयंचलितपणे दिसून येते) |

व्यत्यय "प्रॉम्प्ट इंजेक्शन" म्हणून कार्य करते: फक्त रद्द करण्याऐवजी, ते `"थांबा"` ला वापरकर्ता संदेश म्हणून परत LLM ला फीड करते, ज्यामुळे ते व्यत्यय मान्य करण्यास किंवा निष्कर्ष काढण्याची परवानगी देते.

ऑटो-पायलट मोडमधून बाहेर पडण्यासाठी `x` की दाबा (पहा [README_AUTO.md](https://github.com/awaku7/agentcli/blob/main/README_AUTO.md)).

### 🕵️ ब्राउझर ऑटोमेशन आणि वेब इन्स्पेक्टर

दोन पूरक नाटककार-आधारित साधने:

- **browser_playwright**: वास्तविक ब्राउझर सत्रे स्वयंचलित करा — नेव्हिगेट करा, क्लिक करा, फॉर्म भरा, डेटा काढा, एकाधिक-पृष्ठ प्रवाह हाताळा. हेडलेस किंवा डोके रहित कार्य करते.
- **playwright_inspector**: ब्राउझर संक्रमण रेकॉर्ड करा, प्रत्येक पायरीवर DOM स्नॅपशॉट आणि स्क्रीनशॉट कॅप्चर करा. वेब परस्परसंवाद डीबग करण्यासाठी किंवा कालांतराने पृष्ठ बदलांचे ऑडिट करण्यासाठी उपयुक्त.

### 🔄 डायनॅमिक टूल लोडिंग

`tool_catalog` आणि `tool_load` तुम्हाला रनटाइममध्ये टूल्स शोधू आणि सक्षम करू देतात.
स्टार्टअपवर सर्व काही लोड करण्याची गरज नाही — जेव्हा तुम्हाला आवश्यक असेल तेव्हाच सक्रिय करा.

### 🌐 i18n / L10n

日本語 / इंग्रजी / 简体中文 / 繁體中文 / 한국어 / Español / Français / Русский / आणि बरेच काही.
स्विच करण्यासाठी `UAGENT_LANG` सेट करा. नवीन लोकॅल जोडण्यासाठी [ADD_LOCALE.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/ADD_LOCALE.md) पहा.

या README चे भाषांतर [docs/README.translations.md](https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md) मध्ये उपलब्ध आहेत.

### 🔒 एनक्रिप्टेड एन्व्हायर्नमेंट व्हेरिएबल्स

API की आणि गुपिते `.env.sec` मध्ये संग्रहित करा — एक एनक्रिप्टेड `.env` फाइल.
`uag_envsec` सह व्यवस्थापित करा.

## कॉन्फिगरेशन आणि तपशील

- **पर्यावरण व्हेरिएबल्स**: [ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md)
- **सेटअप विझार्ड**: `python -m uagent.setup_cli`
- **एनक्रिप्ट केलेले env**: `uag_envsec` — एंक्रिप्ट `.env` म्हणून `.env.sec`
- **प्रतिसाद API**: प्रतिसाद API मोडसाठी `UAGENT_RESPONSES=1` सेट करा (OpenAI/Azure/Bedrock/OpenRouter/Ollama/Alibaba/LM Studio/Sakana AI). Sakana AI (Fugu) साठी स्वयं-सक्षम.
- **डेव्हलपर डॉक्स**: [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)
- **लहान LLM टिपा**: [SLM_TIPS.md](https://github.com/awaku7/agentcli/blob/main/SLM_TIPS.md)

## प्रकल्प तत्वज्ञान

uag **तुमची AI, तुमच्या मशीनवर, तुमच्या अटींवर.** बनण्याची आकांक्षा बाळगतो.

- SaaS अवलंबित्व नाही — स्थानिक पातळीवर चालते
- प्रदाता लॉक-इन नाही — कधीही स्विच करा
- कोणतेही UI लॉक-इन नाही — CLI/GUI/Web/A2A
- कोणतेही वैशिष्ट्य लॉक-इन नाही — साधने आणि कौशल्यांसह विस्तार करा

विक्रेता लॉक-इनपासून मुक्त एआय एजंट अनुभव.
