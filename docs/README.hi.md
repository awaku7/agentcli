<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="720">
</p>

# uag (स्थानीय AI एजेंट)

uag एक स्थानीय, इंटरैक्टिव एजेंट है जो **कमांड** चलाता है, **फ़ाइलों** को संभालता है, और PDF, PPTX, तथा Excel जैसी डेटा फ़ाइलों को पढ़ता है। यह उपयोगकर्ता के लिए CLI, GUI, और Web — तीन इंटरफ़ेस प्रदान करता है।

uag को **वेंडर-लॉक्ड ऐप्स से आपको मुक्त रखने** के लिए बनाया गया है: अपने workflow के लिए उपयुक्त interface इस्तेमाल करें, provider बदलें, और अपने environment पर नियंत्रण बनाए रखें.

GitHub: https://github.com/awaku7/agentcli

## स्थापना

pip का उपयोग करके PyPI से इंस्टॉल करें:

```bash
pip install uag
```

यदि आप वर्चुअल वातावरण का उपयोग करते हैं, तो पहले उसे सक्रिय करें और फिर ऊपर दिया गया कमांड चलाएँ।

पहली बार लॉन्च करने पर, `uag` आपके वातावरण की जाँच करता है और जब आवश्यक provider variables गायब होते हैं, तब सेटअप विज़ार्ड अपने आप शुरू करता है। कॉन्फ़िगरेशन विवरण के लिए [ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md) देखें।

## मुख्य विशेषताएँ

- **व्यावहारिक टूलसेट**: फ़ाइल संचालन, वेब खोज, PDF/PPTX/Excel निष्कर्षण, छवि निर्माण, और छवि विश्लेषण।
- **बहु-provider समर्थन**: OpenAI / Azure / Bedrock / OpenRouter / Ollama / Gemini / Vertex AI / Claude / Grok / NVIDIA / DeepSeek / Alibaba Cloud (Qwen) / KIMI (Moonshot AI).
- **तीन इंटरफ़ेस**:
  - **CLI**: `uag` / `python -m uagent`
  - **GUI**: `uagg` / `python -m uagent.gui`
  - **Web**: `uagw` / `python -m uagent.web`
  - **A2A server**: `uaga` / `python -m uagent.a2a.server`
- **MCP समर्थन**: बाहरी MCP tool servers से कनेक्ट करें।
- **सेशन निरंतरता**: मॉडल या provider बदलने पर भी context बनाए रखें।
- **Web Inspector**: `playwright_inspector` के साथ ब्राउज़र transitions, DOM snapshots, और screenshots सहेजें।
- **अंतर्निहित docs**: `uag docs` से bundled docs पढ़ें।

## उपयोग

### शुरू करना और बाहर निकलना

टर्मिनल में `uag` चलाएँ। बाहर निकलने के लिए `:exit` टाइप करें।

### A2A server

Agent2Agent-संगत HTTP server चालू करें:

```bash
uaga
```

`UAGENT_A2A_*` सेटिंग्स जैसे प्रमाणीकरण, होस्ट, पोर्ट, रीलोड, सार्वजनिक base URL, concurrency, और engine के लिए [ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md) देखें।

### काम की टिप्स

- `:tools`: loaded tools दिखाएँ
- `:logs [n]`: हाल के session logs दिखाएँ
- `:load <index>`: पिछला session लोड करें
- `:skills`: Agent Skills चुनें और लोड करें
- `:shrink [n]`: history का सारांश बनाकर आख़िरी `n` messages रखें

## कॉन्फ़िगरेशन और विवरण

### Environment variables और setup

API keys, language settings (`UAGENT_LANG`), history shrink settings, और अधिक के लिए [ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md) देखें।

- **Setup wizard**: `python -m uagent.setup_cli`
- **Encrypted environment**: `.env` को `.env.sec` के रूप में encrypt करने के लिए `uag_envsec` का उपयोग करें
- **Encrypted values अपडेट करें**: `uag_envsec add --file .env.sec --key NAME --value VALUE`

### Responses API नोट

यदि आप `UAGENT_RESPONSES=1` सेट करते हैं, तो समर्थित providers के लिए Responses API उपयोग होगा: OpenAI / Azure / Bedrock / OpenRouter / Ollama.
अन्य providers के लिए uag provider-specific या chat-completions path पर वापस जाता है।

### डेवलपर docs और अनुवाद

- **डेवलपर docs**: [`src/uagent/docs/DEVELOP.md`](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)
- **लोकल जोड़ें**: [`src/uagent/docs/ADD_LOCALE.md`](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/ADD_LOCALE.md)
- **अन्य README अनुवाद**: [`docs/README.translations.md`](https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md)

यदि आप `UAGENT_RESPONSES=1` सेट करते हैं, तो समर्थित providers के लिए Responses API उपयोग होगा: OpenAI / Azure / Bedrock / OpenRouter / Ollama.
Gemini / Claude / Vertex AI use their native API paths and are not covered by Responses API.
For other providers, uag falls back to the provider-specific or chat-completions path.
