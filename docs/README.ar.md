<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="720">
</p>

# uag (الوكيل المحلي للذكاء الاصطناعي)

uag هو وكيل تفاعلي محلي ينفّذ **الأوامر**، ويتعامل مع **الملفات**، ويقرأ ملفات البيانات مثل PDF وPPTX وExcel. ويوفّر ثلاث واجهات للمستخدم: CLI وGUI وWeb.

uag تم تصميمه لكي **يبقيك بعيدًا عن التطبيقات المقيدة بمورد واحد**: استخدم الواجهة التي تناسب سير عملك، وبدّل المزودين، وابقَ متحكمًا في بيئتك.

GitHub: https://github.com/awaku7/agentcli

## التثبيت

ثبّت الحزمة من PyPI باستخدام pip:

```bash
pip install uag
```

إذا كنت تستخدم بيئة افتراضية، فقم بتفعيلها أولًا ثم شغّل الأمر أعلاه.

عند التشغيل الأول، يفحص `uag` بيئتك ويبدأ معالج الإعداد تلقائيًا عندما تكون متغيرات المزوّد المطلوبة مفقودة. للحصول على تفاصيل الإعداد، راجع [ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md).

## أهم الميزات

- **مجموعة أدوات عملية**: التعامل مع الملفات، البحث على الويب، استخراج PDF/PPTX/Excel، توليد الصور، وتحليل الصور.
- **دعم عدة مزوّدين**: OpenAI / Azure / Bedrock / OpenRouter / Ollama / Gemini / Vertex AI / Claude / Grok / NVIDIA.
- **ثلاث واجهات**:
  - **CLI**: `uag` / `python -m uagent`
  - **GUI**: `uagg` / `python -m uagent.gui`
  - **Web**: `uagw` / `python -m uagent.web`
  - **خادم A2A**: `uaga` / `python -m uagent.a2a.server`
- **دعم MCP**: الاتصال بخوادم أدوات MCP الخارجية.
- **استمرارية الجلسة**: الحفاظ على السياق عند تبديل النماذج أو المزوّدين.
- **Web Inspector**: حفظ انتقالات المتصفح ولقطات DOM ولقطات الشاشة باستخدام `playwright_inspector`.
- **وثائق مدمجة**: قراءة الوثائق المرفقة باستخدام `uag docs`.

## الاستخدام

### البدء والخروج
شغّل `uag` في الطرفية لبدء التشغيل. اكتب `:exit` للخروج.

### خادم A2A
شغّل خادم HTTP متوافقًا مع Agent2Agent:

```bash
uaga
```

راجع [ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md) لإعدادات `UAGENT_A2A_*` مثل المصادقة والمضيف والمنفذ وإعادة التحميل وعنوان URL العام والتوازي والمحرك.

### نصائح مفيدة
- `:tools`: عرض الأدوات المحمّلة
- `:logs [n]`: عرض آخر سجلات الجلسة
- `:load <index>`: تحميل جلسة سابقة
- `:skills`: اختيار وتحميل Agent Skills
- `:shrink [n]`: تلخيص السجل والإبقاء على آخر `n` من الرسائل

## الإعداد والتفاصيل

### متغيرات البيئة والإعداد
لمفاتيح API وإعدادات اللغة (`UAGENT_LANG`) وإعدادات تقليص السجل والمزيد، راجع [ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md).

- **معالج الإعداد**: `python -m uagent.setup_cli`
- **بيئة مشفّرة**: استخدم `uag_envsec` لتشفير `.env` إلى `.env.sec`
- **تحديث القيم المشفّرة**: `uag_envsec add --file .env.sec --key NAME --value VALUE`

### ملاحظة حول Responses API
إذا ضبطت `UAGENT_RESPONSES=1` فسيُستخدم Responses API للمزوّدين المدعومين: OpenAI / Azure / Bedrock / OpenRouter / Ollama.
أما المزوّدون الآخرون فيعود uag إلى المسار الخاص بالمزوّد أو مسار chat-completions.

### وثائق المطورين والترجمات
- **وثائق المطورين**: [`src/uagent/docs/DEVELOP.md`](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)
- **إضافة اللغات**: [`src/uagent/docs/ADD_LOCALE.md`](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/ADD_LOCALE.md)
- **ترجمات README الأخرى**: [English](https://github.com/awaku7/agentcli/blob/main/README.md) / [日本語](https://github.com/awaku7/agentcli/blob/main/docs/README.ja.md) / [Deutsch](https://github.com/awaku7/agentcli/blob/main/docs/README.de.md) / [Español](https://github.com/awaku7/agentcli/blob/main/docs/README.es.md) / [Français](https://github.com/awaku7/agentcli/blob/main/docs/README.fr.md) / [Italiano](https://github.com/awaku7/agentcli/blob/main/docs/README.it.md) / [한국어](https://github.com/awaku7/agentcli/blob/main/docs/README.ko.md) / [Português](https://github.com/awaku7/agentcli/blob/main/docs/README.pt_BR.md) / [Русский](https://github.com/awaku7/agentcli/blob/main/docs/README.ru.md) / [ไทย](https://github.com/awaku7/agentcli/blob/main/docs/README.th.md) / [简体中文](https://github.com/awaku7/agentcli/blob/main/docs/README.zh_CN.md) / [繁體中文](https://github.com/awaku7/agentcli/blob/main/docs/README.zh_TW.md) / [Polski](https://github.com/awaku7/agentcli/blob/main/docs/README.pl.md) / [Tiếng Việt](https://github.com/awaku7/agentcli/blob/main/docs/README.vi.md) / [Bahasa Indonesia](https://github.com/awaku7/agentcli/blob/main/docs/README.id.md) / [العربية](https://github.com/awaku7/agentcli/blob/main/docs/README.ar.md) / [हिन्दी](https://github.com/awaku7/agentcli/blob/main/docs/README.hi.md) / [Português](https://github.com/awaku7/agentcli/blob/main/docs/README.pt.md) / [Svenska](https://github.com/awaku7/agentcli/blob/main/docs/README.sv.md) / [Norsk bokmål](https://github.com/awaku7/agentcli/blob/main/docs/README.nb.md) / [Swahili](https://github.com/awaku7/agentcli/blob/main/docs/README.sw.md)
