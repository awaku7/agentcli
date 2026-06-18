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
- **دعم عدة مزوّدين**: OpenAI / Azure / Bedrock / OpenRouter / Ollama / Gemini / Vertex AI / Claude / Grok / NVIDIA / DeepSeek / Alibaba Cloud (Qwen) / Moonshot AI.
- **ثلاث واجهات**:
  - **CLI**: `uag` / `python -m uagent`
  - **GUI**: `uagg` / `python -m uagent.gui`
  - **Web**: `uagw` / `python -m uagent.web`
  - **خادم A2A**: `uaga` / `python -m uagent.a2a.server`
- **دعم MCP**: الاتصال بخوادم أدوات MCP الخارجية.
- **استمرارية الجلسة**: الحفاظ على السياق عند تبديل النماذج أو المزوّدين.
- **سوق مهارات الوكلاء**: تصفح وقم بتثبيت مهارات المجتمع من [SkillsMP](https://skillsmp.com) أو [ClawHub](https://clawhub.ai) باستخدام `:skills mp_search`.
- **Web Inspector**: حفظ انتقالات المتصفح ولقطات DOM ولقطات الشاشة باستخدام `playwright_inspector`.
- **وثائق مدمجة**: قراءة الوثائق المرفقة باستخدام `uag docs`.
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

## الاستخدام

### البدء والخروج

شغّل `uag` في الطرفية لبدء التشغيل. اكتب `:exit` للخروج.

For all command-line options, see [USAGE.md](USAGE.md).

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
- `:skills`: تحديد وتحميل Agent Skills (استخدم `:skills mp_search` لتصفح أسواق [SkillsMP](https://skillsmp.com) أو [ClawHub](https://clawhub.ai))
- `:shrink [n]`: تلخيص السجل والإبقاء على آخر `n` من الرسائل
- Small LLM tips: see [SLM_TIPS.md](SLM_TIPS.md).

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
- **ترجمات README الأخرى**: [`docs/README.translations.md`](https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md)
