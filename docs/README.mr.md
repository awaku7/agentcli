<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="720">
</p>

# uag (स्थानिक AI एजंट)

uag हा **कमांड चालवणे**, **फाइल हाताळणे**, आणि PDF, PPTX, Excel यांसारख्या **डेटा फाइल्स वाचणे** यासाठी तयार केलेला स्थानिक संवादात्मक एजंट आहे. यात CLI, GUI आणि Web अशी तीन इंटरफेसेस आहेत.
uag **एका प्रदात्यावर अडकणे** टाळण्यास मदत करतो: तुम्हाला योग्य इंटरफेस निवडा, प्रदाता बदला, आणि तुमचे वातावरण तुमच्या नियंत्रणात ठेवा.
GitHub: https://github.com/awaku7/agentcli

## स्थापना

PyPI वरून pip वापरून स्थापित करा:

```bash
pip install uag
```

तुम्ही virtual environment वापरत असाल, तर आधी ते सक्रिय करा आणि मग वरचा आदेश चालवा.

पहिल्या सुरूवातीला आवश्यक provider variables नसतील तर `uag` setup wizard आपोआप सुरू होईल. सेटिंग्जची अधिक माहिती [ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md) मध्ये आहे.

## मुख्य वैशिष्ट्ये

- **उपयुक्त साधनांचा संच**: फाइल बदल, वेब शोध, PDF/PPTX/Excel पार्सिंग, प्रतिमा निर्मिती, प्रतिमा विश्लेषण.
- **अनेक प्रदात्यांना समर्थन**: OpenAI / Azure / Bedrock / OpenRouter / Ollama / Gemini / Vertex AI / Claude / Grok / NVIDIA / DeepSeek / Alibaba Cloud (Qwen) / KIMI (Moonshot AI).
- **तीन इंटरफेसेस**:
  - **CLI**: `uag` / `python -m uagent`
  - **GUI**: `uagg` / `python -m uagent.gui`
  - **Web**: `uagw` / `python -m uagent.web`
  - **A2A सर्व्हर**: `uaga` / `python -m uagent.a2a.server`
- **MCP समर्थन**: बाह्य MCP टूल सर्व्हरशी जोडू शकतो.
- **Session continuity**: मॉडेल किंवा provider बदलला तरी संदर्भ टिकून राहतो.
- **Web Inspector**: `playwright_inspector` वापरून browser navigation, DOM snapshot, screenshot जतन करतो.
- **समाविष्ट docs**: `uag docs` मधून bundled docs वाचता येतात.
- **IoT device support**: Control SwitchBot, ECHONET Lite, Matter, and UPnP devices. See [IOT_USECASE.md](IOT_USECASE.md).


## IoT Device Support

Control smart home and IoT devices through multiple interfaces:

- **SwitchBot Cloud**: List, control, and batch-operate SwitchBot devices (TV, air conditioner, lights, etc.).
  - Infrared remote devices (on/off, brightness, temperature)
  - Air conditioner mode and fan speed control
  - Batch execution of multiple commands
- **SwitchBot BLE**: Scan and control nearby SwitchBot BLE devices.
- **ECHONET Lite**: Discover and control ECHONET Lite home appliances over the local network.
- **Matter**: Inspect Matter controller/bridge/device structure (read-only).
- **UPnP**: Discover UPnP devices and manage IGD port forwarding.

For detailed usage, see [IOT_USECASE.md](IOT_USECASE.md).

## वापर

### सुरू करणे आणि बाहेर पडणे

टर्मिनलमध्ये `uag` चालवा. बाहेर पडण्यासाठी `:exit` लिहा.

### A2A सर्व्हर

Agent2Agent-सुसंगत HTTP सर्व्हर सुरू करा:

```bash
uaga
```

`UAGENT_A2A_*` सेटिंग्ज — auth, host, port, reload, public base URL, concurrency, engine इ. — बद्दल [ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md) पहा.

### उपयुक्त टिपा

- `:tools`: लोड केलेली साधने दाखवतो
- `:logs [n]`: मागील session logs दाखवतो
- `:load <index>`: पूर्वीची session लोड करतो
- `:skills`: Agent Skills निवडून लोड करतो
- `:shrink [n]`: history कमी करून शेवटची `n` संदेश ठेवतो

## सेटिंग्ज आणि तपशील

### पर्यावरण चल आणि सेटिंग्ज

API keys, language settings (`UAGENT_LANG`), history shrink settings, आणि इतर गोष्टींसाठी [ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md) पहा.

- **Setup wizard**: `python -m uagent.setup_cli`
- **Encrypted environment**: `.env` ला `.env.sec` मध्ये encrypt करण्यासाठी `uag_envsec` वापरा
- **Encrypted values update**: `uag_envsec add --file .env.sec --key NAME --value VALUE`

### Responses API टीप

जर `UAGENT_RESPONSES=1` सेट केले, तर OpenAI / Azure / Bedrock / OpenRouter / Ollama साठी Responses API वापरले जाईल.
Gemini / Claude / Vertex AI स्वतःचे native API paths वापरतात आणि Responses API लागू होत नाही.
Image analysis साठीचे Responses API सध्या फक्त OpenAI / Azure / Bedrock / OpenRouter वर मर्यादित आहे.
इतर provider साठी uag provider-specific किंवा chat-completions path कडे परत जाईल.

### Developer docs आणि अनुवाद

- **Developer docs**: [`src/uagent/docs/DEVELOP.md`](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)
- **Add locales**: [`src/uagent/docs/ADD_LOCALE.md`](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/ADD_LOCALE.md)
- **इतर README अनुवाद**: [`docs/README.translations.md`](https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md)
