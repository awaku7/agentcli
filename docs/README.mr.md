<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="720">
</p>

<h1 align="center">uag — युनिव्हर्सल AI गेटवे</h1>

<p align="center">
  <b>U</b>वैश्विक <b>A</b>I <b>G</b>ateway — तुमचे वातावरण, तुमचे स्वातंत्र्य.
</p>

<p align="center">
  फाइल ऑप्स / वेब शोध / प्रतिमा निर्मिती आणि विश्लेषण / पीडीएफ आणि एक्सेल एक्स्ट्रक्शन / IoT नियंत्रण / MCP एकत्रीकरण<br>
  15+ प्रदाते / 3 UI / समांतर साधन अंमलबजावणी / एजंट कौशल्ये मार्केटप्लेस
</p>

<p align="center">
  <a href="https://github.com/awaku7/agentcli">GitHub</a>
  ·
  <a href="https://pypi.org/project/uag/">PyPI</a>
  ·
  <a href="https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md">हे तुमच्या भाषेत वाचा</a>
</p>

---

## का उग?

**विक्रेता लॉक-इनपासून मुक्त व्हा.** बहुतेक AI सहाय्यक तुम्हाला विशिष्ट प्रदाता किंवा क्लाउड सेवेशी जोडतात. uag वेगळे आहे.

- तुमच्या मशीनवर **स्थानिकरित्या चालते**. तुमचा डेटा तुमच्यासोबत राहतो (तुम्ही केलेले API कॉल वगळता).
- **प्रदाता स्वातंत्र्य**: OpenAI, Claude, Gemini, DeepSeek, Ollama, Azure, Bedrock... 15+ प्रदाते, सर्व एकाच इंटरफेसवरून प्रवेशयोग्य. पर्यावरण व्हेरिएबल्स पुन्हा कॉन्फिगर करून त्यांच्यामध्ये अदलाबदल करा — पुन्हा स्थापित नाही, स्थलांतर नाही.
- **131 साधने**: फाइल I/O, वेब शोध, प्रतिमा निर्मिती, BLE डिव्हाइस स्कॅनिंग, MCP सर्व्हर एकत्रीकरण — आणि **76 समांतर चालतात**. जेव्हा LLM एकाच वेळी अनेक टूल कॉल्स फायर करते, तेव्हा uag त्यांना थ्रेड पूलद्वारे स्वयंचलितपणे कार्यान्वित करते.
- **4 UI + A2A**: CLI, GUI, वेब आणि एजंट-टू-एजंट प्रोटोकॉल. समान इंजिन, कोणताही इंटरफेस.
- **IoT तयार**: SwitchBot, ECHONET Lite, Matter, UPnP — AI द्वारे तुमची घरगुती उपकरणे नियंत्रित करा.
- **एजंट कौशल्य**: बाजारपेठेतून समुदाय-निर्मित कौशल्ये स्थापित करा. uag अविरतपणे वाढवा.

uag हा **तुमच्या अटींवर तुमचा AI सहाय्यक आहे**. प्रदात्याशी बांधलेले नाही, इंटरफेसशी बांधलेले नाही, प्लॅटफॉर्मशी बांधलेले नाही.

## द्रुत सुरुवात

``बाश
pip install uag
uag
```bash

पहिल्या लॉन्चवर, सेटअप विझार्ड तुम्हाला प्रदाता कॉन्फिगरेशनमध्ये घेऊन जातो.
सर्व पर्यावरणीय चलांसाठी [ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md) पहा.

## वैशिष्ट्ये

### 🧠 मल्टी-प्रोव्हायडर आर्किटेक्चर

OpenAI / Azure / Bedrock / OpenRouter / Ollama / Gemini / Vertex AI / Claude / Grok / NVIDIA / DeepSeek / Alibaba Cloud (Qwen) / KIMI (Moonshot AI) / Xiaomi MiMo / LM स्टुडिओ

सर्व प्रदाते समान टूलसेट आणि इंटरफेस सामायिक करतात. `UAGENT_PROVIDER` सेट करून स्विच करा — कोणतेही कोड बदल नाहीत, वेगळे इंस्टॉलेशन नाहीत.

### ⚡ समांतर टूल एक्झिक्यूशन

जेव्हा LLM एकाच वेळी अनेक साधनांची विनंती करते, तेव्हा uag **आपोआप त्यांना समांतर करते**.
76 साधने `x_parallel_safe` म्हणून चिन्हांकित केली आहेत आणि 4-थ्रेड `ThreadPoolExecutor` द्वारे एकाच वेळी कार्यान्वित करतात.

**उदाहरण**: "नॉर्डिक कॅपिटलमधील हवामान तपासा" विचारा → LLM फायर्स `search_web` × 5 देश → सर्व 5 शोध समांतर चालतात → एका बॅचमध्ये एकत्रित केलेले परिणाम.

केवळ-वाचनीय साधने (फाइल शोध, हॅश गणना, निर्देशिका सूची, भाषांतर, डीबी क्वेरी इ.) आक्रमकपणे समांतर आहेत.

### 🔄 सत्र सातत्य

- `UAGENT_PROVIDER` सह **प्रदाते मिड-सेशन** स्विच करा — संभाषण इतिहास जतन केला आहे.
- **मागील सत्रे रीलोड करा** `:लोड <index>` सह — तुम्ही जिथे सोडले होते तेथून सुरू करा.
- **टूल रिझल्ट कॅशिंग** जेव्हा तेच टूल कॉल रिपीट होते तेव्हा रिडंडंट री-एक्झिक्यूशन टाळते.

### 🛠 131 साधने

| श्रेणी | साधने |
|---|---|
| **फाइल ऑपरेशन्स** | read/write/create/delete/search/grep/hash/zip |
| **वेब** | fetch_url, search_web, स्क्रीनशॉट, browser_playwright |
| **मीडिया** | generate_image, analyze_image, img2img, audio_speech, audio_transscribe |
| **कागदपत्रे** | PDF/PPTX/DOCX/RTF/ODT एक्स्ट्रॅक्शन, एक्सेल स्ट्रक्चर्ड एक्सट्रॅक्शन |
| **IoT** | SwitchBot (Cloud + BLE), ECHONET Lite, Matter, UPnP |
| **देव साधने** | git_ops, python_compile, lint_format, run_tests, db_query, **13 idx tools** |
| **MCP** | बाह्य MCP सर्व्हरशी कनेक्ट करा, साधने सूची करा, कार्यान्वित करा |
| **A2A** | एजंट-टू-एजंट संप्रेषण (इतर uag उदाहरणे किंवा A2A-सुसंगत सर्व्हरसह) |
| **सिस्टम** | env vars, सिस्टम स्पेक्स, वेळ, तारीख गणना |

### 🖥 3 इंटरफेस + A2A + VS Code

| मोड | आज्ञा | उद्देश |
|---|---|---|
| **CLI** | `uag` | फास्ट टर्मिनल-आधारित ऑपरेशन |
| **GUI** | `uagg` | tkinter द्वारे डेस्कटॉप UI |
| **वेब** | `uagw` | ब्राउझर-आधारित प्रवेश |
| **A2A सर्व्हर** | `उगा` | मल्टी-एजंट संप्रेषणासाठी Agent2Agent प्रोटोकॉल |
| **VS Code** | — | Extension (Chat Panel, Explain, Refactor, Fix Error, Tools Tree View) — see [VSCODE.md](VSCODE.md) |

### 🏠 IoT डिव्हाइस नियंत्रण

- **स्विचबॉट**: क्लाउड बॅच कंट्रोल आणि BLE स्कॅन/नियंत्रण
- **ECHONET Lite**: स्थानिक नेटवर्कवर घरगुती उपकरणे (AC, लाइट, वॉटर हीटर्स इ.) शोधा आणि नियंत्रित करा
- **मॅटर**: कंट्रोलर/ब्रिज/डिव्हाइस टोपोलॉजीची केवळ वाचनीय तपासणी
- **UPnP**: डिव्हाइस शोध आणि IGD पोर्ट फॉरवर्डिंग

पहा [IOT_USECASE.md](https://github.com/awaku7/agentcli/blob/main/IOT_USECASE.md)

### 🎯 एजंट स्किल्स मार्केटप्लेस

समुदाय कौशल्यांसाठी [SkillsMP](https://skillsmp.com) आणि [ClawHub](https://clawhub.ai) ब्राउझ करण्यासाठी `:skills mp_search`.
फ्लायवर uag च्या क्षमता स्थापित करा आणि वाढवा.

### 🧩 बॅच स्टेट मॅनेजर

uag दीर्घकाळ चालणाऱ्या मल्टी-फाइल टास्कमध्ये प्रगतीचा मागोवा घेऊ शकते. जेव्हा LLM डझनभर फाइल्सवर प्रक्रिया करते, तेव्हा `batch_state` डिस्कवर प्रलंबित, पूर्ण झालेल्या आणि अयशस्वी फाइल्सची सूची कायम ठेवते. जर सत्र संपले किंवा राऊंड टाइम आउट झाला, तर पुढची रन जिथे थांबली होती तिथून पुन्हा सुरू होते - काहीही गमावले जात नाही.

### 🛡 मानवी-इन-द-लूप

`human_ask` LLM ला विराम देऊ देते आणि विध्वंसक ऑपरेशन्स (फाइल हटवणे, ओव्हरराईट, शेल कमांड) करण्यापूर्वी तुमची पुष्टी मागू देते. तुम्ही नियंत्रणात रहा.

### 🛑 Interrupt (c-key / Stop button)

Stop LLM response generation at any time and inject a stop command back to the LLM.

| Interface | How to interrupt |
|---|---|
| **CLI** | Press `c` key during LLM streaming -- the current response stops, and `"Stop"` is sent as a user message so the LLM responds accordingly |
| **WEB UI** | Click the red **■ Stop** button (appears automatically during LLM processing) |
| **Desktop GUI** | Click the red **■** button (appears automatically during LLM processing) |

The interrupt works as "prompt injection": instead of just aborting, it feeds `"Stop"` back to the LLM as a user message, allowing it to gracefully conclude or acknowledge the interruption.

Press `x` key to exit auto-pilot mode (see `:auto` command).

### 🕵️ ब्राउझर ऑटोमेशन आणि वेब इन्स्पेक्टर

दोन पूरक नाटककार-आधारित साधने:

- **browser_playwright**: वास्तविक ब्राउझर सत्रे स्वयंचलित करा — नेव्हिगेट करा, क्लिक करा, फॉर्म भरा, डेटा काढा, एकाधिक-पृष्ठ प्रवाह हाताळा. हेडलेस किंवा डोके रहित कार्य करते.
- **playwright_inspector**: ब्राउझरची संक्रमणे रेकॉर्ड करा, प्रत्येक पायरीवर DOM स्नॅपशॉट आणि स्क्रीनशॉट कॅप्चर करा. वेब परस्परसंवाद डीबग करण्यासाठी किंवा कालांतराने पृष्ठ बदलांचे ऑडिट करण्यासाठी उपयुक्त.

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
- **प्रतिसाद API**: प्रतिसाद API मोडसाठी `UAGENT_RESPONSES=1` सेट करा (OpenAI/Azure/Bedrock/OpenRouter/Ollama/LM स्टुडिओ)
- **डेव्हलपर डॉक्स**: [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)
- **लहान LLM टिपा**: [SLM_TIPS.md](https://github.com/awaku7/agentcli/blob/main/SLM_TIPS.md)

## प्रकल्प तत्वज्ञान

uag **तुमची AI, तुमच्या मशीनवर, तुमच्या अटींवर.** बनण्याची आकांक्षा बाळगतो.

- SaaS अवलंबित्व नाही — स्थानिक पातळीवर चालते
- प्रदाता लॉक-इन नाही — कधीही स्विच करा
- कोणतेही UI लॉक-इन नाही — CLI/GUI/Web/A2A
- कोणतेही वैशिष्ट्य लॉक-इन नाही — साधने आणि कौशल्यांसह विस्तार करा

विक्रेता लॉक-इनपासून मुक्त एआय एजंट अनुभव.