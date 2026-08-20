<p align="center">
 <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="720">
</p>

<h1 align="er_center">

<h1 संरेखित गेटवे</h1>

<p align="center">
 <b>U</b>niversal <b>A</b>I <b>G</b>ateway — तुमचे वातावरण, तुमचे स्वातंत्र्य.
</p>

<p align="center">
 File ops / Web / PH_3 अतिरिक्त शोध / प्रतिमा / पीडीएफ नियंत्रण & PH_2 / प्रतिमा नियंत्रण आणि PH_2 अतिरिक्त नियंत्रण इंटिग्रेशन<br>
 २४ प्रदाता / ३ UIs / समांतर टूल एक्झिक्यूशन / एजंट स्किल्स मार्केटप्लेस
</p>

<p align="center">
 <a href="https://github.com/awaku7/agentcli">GitHub</a>
·
 href="https://pypi.org/project/uag/">PyPI</a>
 ·
 <a href="https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md">Read this in your language</a>
</p>
__________________________________________

______________________________________________________________________

## uag का?

```bash
pip install uag
uag
```

The base installation keeps provider and tool integrations optional. Missing packages are installed automatically when a selected provider or tool needs one.

```bash
pip install "uag[core,providers,tools,development,platform,web]"
```

For a repository checkout with the full development and test environment:

```bash
pip install -r requirements.txt
```

## क्विक स्टार्ट

\`\`bash
pip install uag
uag

```

पहिल्या लॉन्चवर, सेटअप विझार्ड तुम्हाला प्रदाता कॉन्फिगरेशनमध्ये घेऊन जातो.
पहा [docs/ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/docs/ENVIRONMENT.md) सर्व पर्यावरणीय चलांसाठी.

## Computer Use

Computer Use निवडले आहे आणि दृश्यमान Playwright ब्राउझर रनटाइम
 आणि डेस्कटॉप रनटाइम या दोन्हींना समर्थन देते. सक्षम केल्यावर, दोन्ही रनटाइम तयार केले जातात आणि नोंदणीकृत केले जातात;

``bat
सेट UAGENT_COMPUTER_USE=1
`ओएस` वर सेट करा. त्याऐवजी रनटाइम. Runtime संसाधने 
सामान्य निर्गमन, `Ctrl-C` आणि प्रक्रिया शटडाउनवर एकत्र बंद आहेत. ब्राउझर-आधारित CI किंवा स्मोक चाचण्यांसाठी
`UAGENT_COMPUTER_HEADLESS=1` सेट करा. 
एकीकरण आणि सुरक्षितता तपशीलांसाठी [docs/COMPUTER_USE_IMPLEMENTATION.md](docs/COMPUTER_USE_IMPLEMENTATION.md)
 पहा.

## रिअलटाइम व्हॉइस आणि AEC3

रिअलटाइम व्हॉइस मोड OpenAI रिअलटाइम, Azure OpenAI GPT रिअलटाइम, xAI Grok व्हॉइस API, Google Gemini मल्टीमॉडल लाइव्ह API, आणि Amazon Bedrock आणि Microphone-Nova-Nova Spok-up सह समर्थन करतो. आवश्यक `pywebrtc-audio` AEC3 बॅकएंड आपोआप इंस्टॉल केला जातो आणि बेडरॉकचा पर्यायी द्विदिशात्मक-स्ट्रीमिंग SDK फक्त जेव्हा बेडरॉक प्रदाता निवडला जातो तेव्हाच आपोआप इंस्टॉल होतो:

``bash
python scheck.py realtime
```

AEC3 ने वास्तविकपणे ऑडिओची पाइपलाइन प्राप्त केली आहे आणि ऑडिओ प्राप्त करण्यासाठी मायक्रोफोनला प्रत्यक्ष साइन इन केले आहे. स्पीकर (\`दूर') जेणेकरून सहाय्यक बोलत असताना ऐकू शकेल. ऑडिओ समस्या तपासत असतानाच निदान सक्षम करा:

\`\`bat
set UAGENT_REALTIME_AUDIO_DEBUG=1
python scheck.py realtime

```bash
# llama.cpp / llama-server
UAGENT_PROVIDER=llama_cpp
UAGENT_LLAMA_CPP_BASE_URL=http://localhost:8080/v1
UAGENT_LLAMA_CPP_DEPNAME=local-model
UAGENT_LLAMA_CPP_API_KEY=dummy
```

:प्लगइन सूची # स्थापित प्लगइनची सूची
:प्लगइन इंस्टॉल \<स्रोत> [--स्कोप] # इन्स्टॉल करा (dir/zip/git/http कडून)
stall> मध्ये <mark>
stall>
stall> मध्ये. marketplace
:plugin remove <name> # Uninstall
:plugin enable/disable <name> # Toggle
:plugin marketplace add/remove/list # marketplaces व्यवस्थापित करा
:plugin init <name> # Scaffold new plugin
\`\`

पहा [DEVELOP_PLUGIN.md](src/uagent/docs/DEVELOP_PLUGIN.md) पूर्ण दस्तऐवजासाठी.

### 🔄 सत्र सातत्य

- \*\*'UAGENT_PROVIDER' च्या इतिहासासोबत **प्रीलोड-सर्व्ह** संभाषण पूर्व-लोड सत्रासोबत **प्रदात्यांचे मध्य सत्र** स्विच करा. `:लोड <index>` — तुम्ही जिथे सोडले होते तेथून उचला.
- **टूल रिझल्ट कॅशिंग** जेव्हा तेच टूल कॉल रिपीट होते तेव्हा अनावश्यक री-एक्झिक्यूशन टाळते.

### 🛠 229 टूल्स

| श्रेणी | साधने |
|---|---|
| **फाइल ऑपरेशन्स** | read/write/create/delete/search/grep/hash/zip, file_type, parse_eml (.eml फाइल्स), `path_alias` |
| **Web** | fetch_url, search_web, स्क्रीनशॉट, browser_playwright, `url_alias`, `public_transit_route` ([मार्गदर्शक](docs/PUBLIC_TRANSIT_ROUTE.md)) |
| **मीडिया** | जनरेट_इमेज, विश्लेषण_इमेज, img2img, audio_speech, audio_transcribe |
| **कागदपत्रे** | PDF/PPTX/DOCX/RTF/ODT एक्स्ट्रॅक्शन, एक्सेल स्ट्रक्चर्ड एक्सट्रॅक्शन |
| **अंदाज** | 9 मॉडेल्स (AutoARIMA, Prophet, LightGBM, CatBoost, TimesFM, इ.), ऑटो मॉडेल निवड, प्लॉट जनरेशन, i18n |
| **संवाद** | gmail_send, gmail_read, bluesky, discord_channel, teams_webhook, **pybitchat** (BLE Mesh) — पहा [COMMUNICATION.md](https://github.com/awaku7/agentcli/blob/main/docs/COMMUNICATION.md) आणि [BITCHAT.md](https://github.com/awaku7/agentcli/blob/main/docs/BITCHAT.md) |
| **IoT** | SwitchBot (Cloud + BLE), ECHONET Lite, Matter, UPnP, reverse_geocode |
| **क्लाउड API** | `aws_api`, `gcp_api`, `azure_api` — जेनेरिक AWS, Google क्लाउड, आणि Azure API ऑपरेशन्स; लेखन ऑपरेशन्ससाठी स्पष्ट पुष्टीकरण आवश्यक आहे |
| **देव साधने** | workspace_status, git_ops, git_review, security_scan, coverage_report, python_compile, lint_format, run_tests, db_query, **29 स्त्रोत कोड नेव्हिगेटर (idx फॅमिली)** |
| **MCP** | बाह्य MCP सर्व्हरशी कनेक्ट करा, सूची साधने, कार्यान्वित करा — [OAuth / प्रॉक्सी मार्गदर्शक](docs/MCP_OAUTH_PROXY_GUIDE.md) |
| **A2A** | एजंट-टू-एजंट संप्रेषण (इतर uag उदाहरणांसह किंवा A2A-सुसंगत सर्व्हरसह) |
| **सिस्टम** | env vars, सिस्टमचे तपशील, वेळ, तारीख गणना, [मात्रा](docs/QUANTITIES.md), [geodesic_distance](docs/GEODESIC_DISTANCE.md), uuid_gen, slugify |
| **स्रोत Nav** | Python, PHP, TypeScript, Java, C#, Dart, C/C++, Rust, Go, Swift, Kotlin, COBOL, VBA, LotusScript, Makefile साठी **२९ idx साधने** — संपूर्ण फाइल न वाचता फंक्शन/वर्ग निर्देशांक किंवा विशिष्ट व्याख्या मिळवा | `वर्कस्पेस_स्टेटस`: फाइल्समध्ये बदल न करता सक्रिय वर्कस्पेसची Git शाखा, बदल, अपस्ट्रीम सिंक स्थिती, Python रनटाइम आणि सामान्य प्रोजेक्ट मार्करचा अहवाल द्या.

- `git_review`: Git बदल, जोखमीच्या फाइल्स, चाचणी उमेदवार आणि गुप्त निष्कर्षांचा सारांश द्या, गुप्त मूल्ये उघड न करता गुप्त निष्कर्ष काढा. गुपिते आणि धोकादायक कॉन्फिगरेशन फाइल्स.
- `कव्हरेज_रिपोर्ट`: Python, TypeScript/JavaScript, Rust, Go, Java/Kotlin, .NET, C/C++, Ruby, PHP, Swift आणि Dart/Flutter साठी कव्हरेज चालवा आणि सामान्य करा. `dry_run` कधीही पॅकेजेस इंस्टॉल करत नाही.

पॅरामीटर्स, आउटपुट आणि सुरक्षितता तपशीलांसाठी [रिपॉझिटरी विश्लेषण साधने](docs/REPOSITORY_TOOLS.md) पहा.

[पथ आणि URL उपनाम](%E0%A4%A6%E0%A4%B8%E0%A5%8D%E0%A4%A4%E0%A4%90%E0%A4%B5%E0%A4%9C/PATH_URL_ALIASES.md) लहान पाथसाठी पुनरावृत्ती केलेल्या URL मध्ये फाईल पहा. arguments.

### 🖥 4 इंटरफेस + VS कोड विस्तार

| मोड | आज्ञा | उद्देश |
|---|---|---|
| **CLI** | `uag` | फास्ट टर्मिनल-आधारित ऑपरेशन |
| **GUI** | `uagg` | tkinter द्वारे डेस्कटॉप UI |
| **Web** | `uagw` | ब्राउझर-आधारित प्रवेश |
| **A2A सर्व्हर** | `uaga` | मल्टी-एजंट संप्रेषणासाठी Agent2Agent प्रोटोकॉल |
| **VS कोड** | — | [विस्तार](https://github.com/awaku7/agentcli/blob/main/docs/VSCODE.md) चॅट पॅनेलसह, स्पष्टीकरण, रिफॅक्टर, त्रुटी दूर करा आणि टूल्स ट्री व्ह्यू |

पहा [VSCODE.md](https://github.com/awaku7/agentcli/blob/main/docs/VSCODE.md) व्हीएस कोड विस्ताराच्या तपशीलांसाठी — इंस्टॉलेशन, कमांड, कीबाइंडिंग आणि कॉन्फिगरेशन. उपकरणे (HVAC, प्रकाश, वीज मीटर). पुश नोटिफिकेशन्ससाठी COV सबस्क्रिप्शन

- **मॉडबस TCP**: होल्डिंग/इनपुट रजिस्टर आणि कॉइल वाचा/लिहा. मतदान-आधारित बदल मॉनिटरिंग
- **OPC UA**: ॲड्रेस स्पेस ब्राउझ करा, व्हेरिएबल्स वाचा/लिहा, डेटा बदलांची सदस्यता घ्या
- **स्विचबॉट**: क्लाउड बॅच कंट्रोल आणि BLE स्कॅन/नियंत्रण. मतदान-आधारित सदस्यता
- **ECHONET Lite**: घरगुती उपकरणे (AC, लाइट, वॉटर हीटर्स इ.) वरील INF सूचना शोधा, नियंत्रित करा आणि सदस्यता घ्या. [IOT_USECASE.md](https://github.com/awaku7/agentcli/blob/main/docs/IOT_USECASE.md)

### 🎯 Agent Skills Marketplace

`:skills mp_search` ब्राउझ करण्यासाठी [कौशल्य]https://MP.comll) सामुदायिक कौशल्यांसाठी [ClawHub](https://clawhub.ai) जटिल, बहु-चरण कार्यांसाठी योग्य ज्यांना पुनरावृत्ती परिष्करण आवश्यक आहे.

- **ते कसे कार्य करते**: प्रत्येक फेरीत एक मुख्य क्वेरी (स्टेप A) त्यानंतर पुनरावलोकनकर्त्याचा निर्णय (स्टेप ब) असतो जो "पूर्ण किंवा सुरू ठेवा?" ठरवतो. क्वेरी — प्रतिसादांसह API समर्थन.
- **वेगळा न्यायाधीश LLM** (पर्यायी): पुनरावलोकनकर्त्यासाठी वेगळा प्रदाता/मॉडेल वापरण्यासाठी `UAGENT_AP_PROVIDER` सेट करा (उदा. न्यायासाठी स्वस्त मॉडेल वापरा).
- **केव्हाही बाहेर पडा**: थांबण्यासाठी \`x' दाबा, ताबडतोब दाबा. किंवा लक्ष्य केव्हा पूर्ण होईल हे समीक्षकाला ठरवू द्या.
- **कॉन्फिगर करण्यायोग्य**: बजेट नियंत्रित करण्यासाठी `--max-rounds N`.

पहा \[README_AUTO.md\](https://github.com/awaku7/agentcli/blob/main/docs/README_AUTO.md#

# full document. बॅच स्टेट मॅनेजर

uag दीर्घकाळ चालणाऱ्या मल्टी-फाइल टास्कमध्ये प्रगतीचा मागोवा घेऊ शकतो. जेव्हा LLM डझनभर फायलींवर प्रक्रिया करते, तेव्हा `batch_state` डिस्कवर प्रलंबित, पूर्ण झालेल्या आणि अयशस्वी फायलींची सूची कायम ठेवते. जर सेशन संपले किंवा राऊंड टाइम आऊट झाला, तर पुढची रन जिथे थांबली होती तिथून पुन्हा सुरू होते — काहीही गमावले जात नाही.

### 🛡 Human-in-the-Loop

`human_ask` ला LLM विराम देऊ देते आणि विध्वंसक ऑपरेशन्स करण्यापूर्वी तुमची पुष्टी विचारू देते (फाइल हटवणे, कमांड ओव्हरवाईट). तुम्ही नियंत्रणात रहा.

### 🛑 व्यत्यय (c-की / स्टॉप बटण)

कधीही LLM प्रतिसाद निर्मिती थांबवा आणि LLM वर परत थांबा आदेश इंजेक्ट करा.

| इंटरफेस | व्यत्यय कसा आणायचा |
|---|---|
| **CLI** | LLM प्रवाहादरम्यान F12 की दाबा — वर्तमान प्रतिसाद थांबतो, आणि `"थांबा"` वापरकर्ता संदेश म्हणून पाठविला जातो जेणेकरून LLM त्यानुसार प्रतिसाद देईल |
| **वेब UI** | लाल **■ थांबवा** बटण क्लिक करा (LLM प्रक्रियेदरम्यान स्वयंचलितपणे दिसून येते) |
| **डेस्कटॉप GUI** | लाल **■** बटणावर क्लिक करा (LLM प्रक्रियेदरम्यान स्वयंचलितपणे दिसून येते) |

व्यत्यय "प्रॉम्प्ट इंजेक्शन" म्हणून कार्य करते: फक्त निरस्त करण्याऐवजी, ते `"थांबा"` ला वापरकर्ता संदेश म्हणून LLM वर परत फीड करते, त्यास कृपापूर्वक निष्कर्ष काढण्यास किंवा व्यत्यय स्वीकारण्याची अनुमती देऊन `ऑटो `s
`s-P `s की मोड सोडण्याची परवानगी देते. (पहा [README_AUTO.md](https://github.com/awaku7/agentcli/blob/main/docs/README_AUTO.md)).

### 🕵️ ब्राउझर ऑटोमेशन आणि Web Inspector

दोन पूरक \__⎎ PH_ बेस्ड टूल: **browser_playwright**: वास्तविक ब्राउझर सत्रे स्वयंचलित करा — नेव्हिगेट करा, क्लिक करा, फॉर्म भरा, डेटा काढा, एकाधिक-पृष्ठ प्रवाह हाताळा. हेडलेस किंवा हेडलेस काम करते.

- **playwright_inspector**: ब्राउझर संक्रमण रेकॉर्ड करा, प्रत्येक पायरीवर DOM स्नॅपशॉट आणि स्क्रीनशॉट कॅप्चर करा. वेब परस्परसंवाद डीबग करण्यासाठी किंवा वेळोवेळी पृष्ठांचे ऑडिट करण्यासाठी उपयुक्त.

### 🔄 डायनॅमिक टूल लोडिंग

`tool_catalog` आणि `tool_load` तुम्हाला रनटाइममध्ये टूल्स शोधू आणि सक्षम करू देतात.
स्टार्टअपवर सर्वकाही लोड करण्याची आवश्यकता नाही — तुम्हाला आवश्यक असेल तेव्हाच सक्रिय करा.

# रस्ट नेटिव्ह टूल्स

`uuid_gen` आणि `slugify` कार्यप्रदर्शनासाठी Rust मध्ये (PyO3 द्वारे) लागू केले आहेत.
ते थेट पूर्व-निर्मित `.pyd` वरून लोड करतात — **कोणतेही `pip install` आवश्यक नाही**. `.py`, `uagent.tools.rust_helper` वरून `load_rust_pyd()` वापरा आणि
वापरकर्त्यांना कोणत्याही अतिरिक्त अवलंबनाशिवाय साधन मिळते. पाहा
[TOOL_CREATOR_GUIDE.md](https://github.com/awaku7/agentcli/blob/main/TOOL_CREATOR_GUIDE.md).

### 🌐 i18n / L10n

日 / इंग्रजी / 简万有繁體中文 / 한국어 / Español / Français / Русский / आणि बरेच काही.
स्विच करण्यासाठी `UAGENT_LANG` सेट करा. नवीन लोकॅल जोडण्यासाठी [ADD_LOCALE.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/ADD_LOCALE.md) पहा.

या README चे भाषांतर यामध्ये उपलब्ध आहेत \[docs/README.translations.md\](https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md. `.env` फाइल.
`uag_envsec` सह व्यवस्थापित करा.

## कॉन्फिगरेशन आणि तपशील

- **पर्यावरण व्हेरिएबल्स**: [docs/ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/docs/ENVIRONMENT.md)
- **सेटअप विझार्ड**: `_ _ _ पीथॉन सेट अप करा **: _ _ _ पी 2 _ _ _ 2 _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 2 सेट **एनक्रिप्ट केलेले env**: `uag_envsec`—`.env`ला`.env.sec`म्हणून कूटबद्ध करा- **प्रतिसाद API**: प्रतिसादांसाठी`UAGENT_RESPONSES=1\` सेट करा API मोड (OpenAI/Azure/Bedrouber/Bedrock/Bedrock स्टुडिओ/सकाना एआय). Sakana AI (Fugu) साठी ऑटो-सक्षम.
- **डेव्हलपर डॉक्स**: [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)
- **टूल फ्लो**: [TOOL_FLOW.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/TOOL_FLOW.md) — LLM मध्ये टूल्स कशी पाठवली जातात (शैली मास्क, टूल_कॅटलॉग, GPT-5.4+ नेटिव्ह टूल_सर्च)
- \*\* PH\_\*\* ti [SLM_TIPS.md](https://github.com/awaku7/agentcli/blob/main/docs/SLM_TIPS.md)

## प्रोजेक्ट फिलॉसॉफी

uag **तुमचे AI, तुमच्या मशीनवर, तुमच्या अटींवर.**

- SaaS अवलंबित्व नाही — स्थानिक पातळीवर चालते
- प्रदाता लॉक-इन नाही — कधीही स्विच करा
- कोणतेही UI लॉक-इन नाही — CLI / Web वैशिष्ट्य नाही लॉक-इन — टूल्स आणि स्किल्ससह विस्तारित करा

विक्रेता लॉक-इनपासून मुक्त AI एजंट अनुभव.

### ✨ तुमची स्वतःची साधने तयार करा

uag साठी नवीन साधन लिहिणे सोपे आहे — एक एकल `.py` फाईल तयार करा
`TOOL_ मध्ये,  ` TOOL\_ रन करा. `UAGENT_EXTERNAL_TOOLS_DIR`, आणि
ते त्वरित उपलब्ध आहे. रस्ट डेव्हलपरसाठी, वापरकर्त्यांसाठी शून्य अतिरिक्त अवलंबनांसह पूर्व-निर्मित `.pyd` पाठवा.## योगदान देणे

योगदानांचे स्वागत आहे! बग अहवाल, वैशिष्ट्य सूचना, दस्तऐवजीकरण सुधारणा, भाषांतरे आणि पुल विनंत्या — सर्वांचे कौतुक.

- **समस्या**: बग किंवा वैशिष्ट्य विनंत्यांसाठी GitHub समस्या उघडा.
- **पुल विनंत्या**: रेपो फोर्क करा, तुमचे बदल करा आणि PR सबमिट करा. डेव्हलपमेंट सेटअप आणि मार्गदर्शक तत्त्वांसाठी [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md) पहा.
- **अनुवाद**: README भाषांतरे आणि लोकेल जोडण्यांचे स्वागत आहे. पहा [ADD_LOCALE.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/ADD_LOCALE.md).
- **टूल्स आणि स्किल्स**: नवीन टूल प्लगइन्स आणि एजंट स्किल्सचे योगदान मार्केटप्लेससाठी (#

# 

# 

डेव्हलपमेंट द्वारे केले जाऊ शकते. PR)

प्रथम फक्त चाचणी अवलंबित्व स्थापित करा. त्यांना रनटाइम
अवलंबन सूचीच्या बाहेर ठेवले जाते:

\`\`bash
python -m pip install -e "[test]"
python -m pip install black ruff

```

Pushing
`m
`m
`pushing करण्यापूर्वी GitHub क्रियांनी वापरलेल्या समान तपासा चालवा: ruff check src tests
python -m black --check src tests
python scripts/tool_json_i18n_batch.py status
python -m pytest -q .
```

जलद स्थानिक पुनरावृत्तीसाठी, फक्त प्रभावित चाचण्या चालवा: चाचण्या/\<affected_area>

```

संबंधित असताना अतिरिक्त तपासण्या:

``bash
python -m py_compile src/uagent/
mypy src/uagent
```

स्थानिक: `ppo.`s संपादित करा. scripts/compile_locales.py`आणि`python scripts/po_qc_summary.py\`.

Runtime धोरण (तपशील \[DEVELOP.md\](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/dEl ऐवजी) `sys.exit`; टूल होस्ट टूल `SystemExit`/`Exception` ला एरर स्ट्रिंगमध्ये रूपांतरित करतो जेणेकरून एक टूल प्रक्रिया नष्ट करू शकत नाही. स्टार्टअप अयशस्वी-जलद निर्गमन हेतुपुरस्सर राहते.

## आर्किटेक्चर आणि ऑपरेशनल इन्व्हेरियंट

पहा [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) टिकाऊ करारासाठी A2A जीवनचक्र, I18N संदर्भ, पर्यायी अवलंबित्व स्थापना, साधन सुरक्षा, प्रदाता क्षमता, OAuth ट्रस्ट
स्वीकारलेले इव्हेंट, स्वीकारलेले इव्हेंट आणि बंधने.## एंटरप्राइझ पॉलिसी इंजिन

टूल्स, प्रदाता, क्रेडेन्शियल्स, MCP सर्व्हर, नेटवर्क, कौशल्ये आणि प्लगइनसाठी संस्था-स्तरीय धोरणे समर्थित आहेत. `UAGENT_POLICY_FILE` ला JSON/YAML धोरण फाइलवर सेट करा; कॉन्फिगरेशन उदाहरणे, भूमिका, पुष्टीकरण आणि अनुमत सूचीसाठी [docs/ENTERPRISE_POLICY.md](docs/ENTERPRISE_POLICY.md) पहा. [DAG_SCHEDULER.md](docs/DAG_SCHEDULER.md) / [MULTI_AGENT_RUNTIME.md](docs/MULTI_AGENT_RUNTIME.md) टिकाऊ पुनर्प्राप्ती, अवलंबित्व-जागरूक अंमलबजावणी, मल्टी-एजंट ऑर्केस्ट्रेशन आणि रिमोट वापरासाठी \_\_⏏S_PH3 [DISTRIBUTED_COORDINATION.md](docs/DISTRIBUTED_COORDINATION.md) शेअर-रनटाइम लीडर लीज समन्वयासाठी.

## Installation and optional dependencies

The base installation keeps provider and tool integrations optional. Missing
packages are installed automatically when a selected provider or tool needs
one. To install the main feature groups in advance:

```bash
pip install "uag[core,providers,tools,development,platform,web]"
```

For a repository checkout with the full development and test environment:

```bash
pip install -r requirements.txt
```
