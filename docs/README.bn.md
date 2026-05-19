<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="720">
</p>

# uag (স্থানীয় AI এজেন্ট)

uag একটি স্থানীয় ইন্টারঅ্যাকটিভ এজেন্ট, যা **কমান্ড চালায়**, **ফাইল পরিচালনা করে**, এবং PDF, PPTX, Excel-এর মতো **ডেটা ফাইল পড়ে**। এটি CLI, GUI, এবং Web—এই তিনটি ইন্টারফেস দেয়।
uag এমনভাবে তৈরি করা হয়েছে যাতে আপনি **ভেন্ডর-লকড অ্যাপের ওপর নির্ভরশীল না থাকেন**: আপনার কাজের ধরন অনুযায়ী ইন্টারফেস বেছে নিন, প্রোভাইডার বদলান, আর নিজের পরিবেশের নিয়ন্ত্রণ নিজের হাতেই রাখুন।
GitHub: https://github.com/awaku7/agentcli

## ইনস্টলেশন

pip ব্যবহার করে PyPI থেকে ইনস্টল করুন:

```bash
pip install uag
```

আপনি যদি virtual environment ব্যবহার করেন, আগে সেটি সক্রিয় করে তারপর উপরের কমান্ডটি চালান।

প্রথমবার চালু হলে, প্রয়োজনীয় provider variables অনুপস্থিত থাকলে `uag` স্বয়ংক্রিয়ভাবে setup wizard শুরু করে। কনফিগারেশনের বিস্তারিত জানতে [ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md) দেখুন।

## মূল বৈশিষ্ট্য

- **ব্যবহারিক টুলসেট**: ফাইল ম্যানিপুলেশন, ওয়েব সার্চ, PDF/PPTX/Excel extraction, image generation, এবং image analysis।
- **মাল্টি-প্রোভাইডার সাপোর্ট**: OpenAI / Azure / Bedrock / OpenRouter / Ollama / Gemini / Vertex AI / Claude / Grok / NVIDIA।
- **তিনটি ইন্টারফেস**:
  - **CLI**: `uag` / `python -m uagent`
  - **GUI**: `uagg` / `python -m uagent.gui`
  - **Web**: `uagw` / `python -m uagent.web`
  - **A2A সার্ভার**: `uaga` / `python -m uagent.a2a.server`
- **MCP সাপোর্ট**: বাহ্যিক MCP টুল সার্ভারের সাথে সংযোগ করতে পারে।
- **সেশন ধারাবাহিকতা**: মডেল বা প্রোভাইডার বদলালেও প্রসঙ্গ বজায় থাকে।
- **Web Inspector**: `playwright_inspector` দিয়ে ব্রাউজার নেভিগেশন, DOM snapshot, এবং screenshot সংরক্ষণ করুন।
- **অন্তর্নির্মিত ডকস**: `uag docs` দিয়ে bundled docs পড়া যায়।

## ব্যবহার

### শুরু ও বন্ধ
টার্মিনালে `uag` চালিয়ে শুরু করুন। বন্ধ করতে `:exit` লিখুন।

### A2A সার্ভার
Agent2Agent-সামঞ্জস্যপূর্ণ একটি HTTP সার্ভার চালু করুন:

```bash
uaga
```

`UAGENT_A2A_*` সেটিংস—যেমন auth, host, port, reload, public base URL, concurrency, এবং engine—সম্পর্কে জানতে [ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md) দেখুন।

### দরকারি টিপস
- `:tools`: লোড করা টুলগুলোর তালিকা দেখায়
- `:logs [n]`: সাম্প্রতিক সেশন লগ দেখায়
- `:load <index>`: আগের একটি সেশন লোড করে
- `:skills`: Agent Skills নির্বাচন করে লোড করে
- `:shrink [n]`: history সংক্ষিপ্ত করে শেষ `n` বার্তা রেখে দেয়

## কনফিগারেশন ও বিস্তারিত

### পরিবেশ ভেরিয়েবল ও সেটআপ
API keys, language settings (`UAGENT_LANG`), history shrink settings, এবং আরও অনেক কিছুর জন্য [ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md) দেখুন।

- **Setup wizard**: `python -m uagent.setup_cli`
- **Encrypted environment**: `.env`-কে `.env.sec` হিসেবে encrypt করতে `uag_envsec` ব্যবহার করুন
- **Encrypted values update**: `uag_envsec add --file .env.sec --key NAME --value VALUE`

### Responses API নোট
আপনি যদি `UAGENT_RESPONSES=1` সেট করেন, তাহলে OpenAI / Azure / Bedrock / OpenRouter / Ollama-র জন্য Responses API ব্যবহার করা হবে।
Gemini / Claude / Vertex AI তাদের native API path ব্যবহার করে এবং Responses API-র অন্তর্ভুক্ত নয়।
Image analysis-এর জন্য Responses API বর্তমানে শুধু OpenAI / Azure / Bedrock / OpenRouter-এ সীমিত।
অন্য provider-গুলোর জন্য uag provider-specific বা chat-completions path-এ ফিরে যায়।

### ডেভেলপার ডকস এবং অনুবাদ
- **Developer docs**: [`src/uagent/docs/DEVELOP.md`](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)
- **Add locales**: [`src/uagent/docs/ADD_LOCALE.md`](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/ADD_LOCALE.md)
- **Other README translations**: [English](https://github.com/awaku7/agentcli/blob/main/README.md) / [日本語](https://github.com/awaku7/agentcli/blob/main/docs/README.ja.md) / [Deutsch](https://github.com/awaku7/agentcli/blob/main/docs/README.de.md) / [Español](https://github.com/awaku7/agentcli/blob/main/docs/README.es.md) / [Français](https://github.com/awaku7/agentcli/blob/main/docs/README.fr.md) / [Italiano](https://github.com/awaku7/agentcli/blob/main/docs/README.it.md) / [한국어](https://github.com/awaku7/agentcli/blob/main/docs/README.ko.md) / [Português](https://github.com/awaku7/agentcli/blob/main/docs/README.pt_BR.md) / [Русский](https://github.com/awaku7/agentcli/blob/main/docs/README.ru.md) / [ไทย](https://github.com/awaku7/agentcli/blob/main/docs/README.th.md) / [简体中文](https://github.com/awaku7/agentcli/blob/main/docs/README.zh_CN.md) / [繁體中文](https://github.com/awaku7/agentcli/blob/main/docs/README.zh_TW.md) / [Polski](https://github.com/awaku7/agentcli/blob/main/docs/README.pl.md) / [Tiếng Việt](https://github.com/awaku7/agentcli/blob/main/docs/README.vi.md) / [Bahasa Indonesia](https://github.com/awaku7/agentcli/blob/main/docs/README.id.md) / [العربية](https://github.com/awaku7/agentcli/blob/main/docs/README.ar.md) / [हिन्दी](https://github.com/awaku7/agentcli/blob/main/docs/README.hi.md) / [Português](https://github.com/awaku7/agentcli/blob/main/docs/README.pt.md) / [Svenska](https://github.com/awaku7/agentcli/blob/main/docs/README.sv.md) / [Norsk bokmål](https://github.com/awaku7/agentcli/blob/main/docs/README.nb.md) / [Suomi](https://github.com/awaku7/agentcli/blob/main/docs/README.fi.md) / [Nederlands](https://github.com/awaku7/agentcli/blob/main/docs/README.nl.md) / [Čeština](https://github.com/awaku7/agentcli/blob/main/docs/README.cs.md) / [Українська](https://github.com/awaku7/agentcli/blob/main/docs/README.uk.md) / [Swahili](https://github.com/awaku7/agentcli/blob/main/docs/README.sw.md) / [Bengali](https://github.com/awaku7/agentcli/blob/main/docs/README.bn.md) / [Persian](https://github.com/awaku7/agentcli/blob/main/docs/README.fa.md) / [Mongolian](https://github.com/awaku7/agentcli/blob/main/docs/README.mn.md) / [Marathi](https://github.com/awaku7/agentcli/blob/main/docs/README.mr.md)
