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
- **अनेक प्रदात्यांना समर्थन**: OpenAI / Azure / Bedrock / OpenRouter / Ollama / Gemini / Vertex AI / Claude / Grok / NVIDIA.
- **तीन इंटरफेसेस**:
  - **CLI**: `uag` / `python -m uagent`
  - **GUI**: `uagg` / `python -m uagent.gui`
  - **Web**: `uagw` / `python -m uagent.web`
  - **A2A सर्व्हर**: `uaga` / `python -m uagent.a2a.server`
- **MCP समर्थन**: बाह्य MCP टूल सर्व्हरशी जोडू शकतो.
- **Session continuity**: मॉडेल किंवा provider बदलला तरी संदर्भ टिकून राहतो.
- **Web Inspector**: `playwright_inspector` वापरून browser navigation, DOM snapshot, screenshot जतन करतो.
- **समाविष्ट docs**: `uag docs` मधून bundled docs वाचता येतात.

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
- **इतर README अनुवाद**: [इंग्रजी](https://github.com/awaku7/agentcli/blob/main/README.md) / [जपानी](https://github.com/awaku7/agentcli/blob/main/docs/README.ja.md) / [जर्मन](https://github.com/awaku7/agentcli/blob/main/docs/README.de.md) / [स्पॅनिश](https://github.com/awaku7/agentcli/blob/main/docs/README.es.md) / [फ्रेंच](https://github.com/awaku7/agentcli/blob/main/docs/README.fr.md) / [इटालियन](https://github.com/awaku7/agentcli/blob/main/docs/README.it.md) / [कोरियन](https://github.com/awaku7/agentcli/blob/main/docs/README.ko.md) / [पोर्तुगीज (ब्राझिल)](https://github.com/awaku7/agentcli/blob/main/docs/README.pt_BR.md) / [रशियन](https://github.com/awaku7/agentcli/blob/main/docs/README.ru.md) / [थाई](https://github.com/awaku7/agentcli/blob/main/docs/README.th.md) / [सरलीकृत चीनी](https://github.com/awaku7/agentcli/blob/main/docs/README.zh_CN.md) / [पारंपारिक चीनी](https://github.com/awaku7/agentcli/blob/main/docs/README.zh_TW.md) / [पोलिश](https://github.com/awaku7/agentcli/blob/main/docs/README.pl.md) / [व्हिएतनामी](https://github.com/awaku7/agentcli/blob/main/docs/README.vi.md) / [इंडोनेशियन](https://github.com/awaku7/agentcli/blob/main/docs/README.id.md) / [अरबी](https://github.com/awaku7/agentcli/blob/main/docs/README.ar.md) / [हिंदी](https://github.com/awaku7/agentcli/blob/main/docs/README.hi.md) / [पोर्तुगीज](https://github.com/awaku7/agentcli/blob/main/docs/README.pt.md) / [स्वीडिश](https://github.com/awaku7/agentcli/blob/main/docs/README.sv.md) / [नॉर्वेजियन बोकमाल](https://github.com/awaku7/agentcli/blob/main/docs/README.nb.md) / [फिन्निश](https://github.com/awaku7/agentcli/blob/main/docs/README.fi.md) / [डच](https://github.com/awaku7/agentcli/blob/main/docs/README.nl.md) / [झेक](https://github.com/awaku7/agentcli/blob/main/docs/README.cs.md) / [युक्रेनियन](https://github.com/awaku7/agentcli/blob/main/docs/README.uk.md) / [स्वाहिली](https://github.com/awaku7/agentcli/blob/main/docs/README.sw.md) / [बंगाली](https://github.com/awaku7/agentcli/blob/main/docs/README.bn.md) / [फारसी](https://github.com/awaku7/agentcli/blob/main/docs/README.fa.md) / [मंगोलियन](https://github.com/awaku7/agentcli/blob/main/docs/README.mn.md) / [मराठी](https://github.com/awaku7/agentcli/blob/main/docs/README.mr.md)
