<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="680">
</p>

<h1 align="center">uag</h1>

<p align="center">
  <strong>Universal AI Gateway</strong><br>
  وكيل محلي واحد. أي نموذج. أي أداة. بيئتك، وقواعدك.
</p>

<p align="center">
  <a href="https://github.com/awaku7/agentcli/actions"><img src="https://img.shields.io/github/actions/workflow/status/awaku7/agentcli/ci.yml?style=flat-square&label=CI" alt="CI status"></a>
  <a href="https://pypi.org/project/uag/"><img src="https://img.shields.io/pypi/v/uag?style=flat-square" alt="PyPI version"></a>
  <a href="https://pypi.org/project/uag/"><img src="https://img.shields.io/pypi/pyversions/uag?style=flat-square" alt="Python versions"></a>
  <a href="https://github.com/awaku7/agentcli/blob/main/LICENSE"><img src="https://img.shields.io/github/license/awaku7/agentcli?style=flat-square" alt="License"></a>
  <a href="https://pepy.tech/projects/uag"><img src="https://static.pepy.tech/personalized-badge/uag?period=total&units=INTERNATIONAL_SYSTEM&left_color=grey&right_color=green&left_text=downloads" alt="PyPI Downloads"></a>
</p>

<p align="center">
  <a href="https://github.com/awaku7/agentcli">GitHub</a> ·
  <a href="https://pypi.org/project/uag/">PyPI</a> ·
  <a href="https://github.com/awaku7/agentcli/discussions">Discussions</a> ·
  <a href="https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md">Translations</a>
</p>

______________________________________________________________________

**لماذا uag؟**

uag هو وكيل ذكاء اصطناعي محلي أولًا، يربط النموذج الذي تفضله بالأدوات التي تستخدمها فعليًا.
يوفر لك بيئة تشغيل واحدة قابلة للتوسعة للملفات، والمتصفحات، وقواعد الشيفرة، والاتصالات، وواجهات
برمجة التطبيقات السحابية، وأجهزة إنترنت الأشياء، وخوادم MCP، وسير عمل الوكلاء المتعددين.

- **حرية اختيار المزوّد** — OpenAI وAnthropic وGemini وAzure وBedrock وOllama وllama.cpp وGrok وDeepSeek وغير ذلك.
- **تنفيذ محلي أولًا** — تبقى بيئة تشغيل وكيلك وتنفيذ أدواتك على جهازك؛ ولا تغادره إلا استدعاءات API التي تختارها.
- **طبقة أدوات واحدة** — تعمل الأدوات نفسها من CLI وواجهة سطح المكتب وواجهة الويب وVS Code وA2A.
- **مصمم للتوازي** — يمكن تشغيل العمليات المستقلة للقراءة فقط بالتزامن.
- **قابل للتوسعة** — أضف الأدوات والإضافات وAgent Skills وخوادم MCP والأدوات المدعومة بـRust دون تغيير النواة.
- **واعٍ بالسلامة** — تدعم الإجراءات المدمرة وبيانات الاعتماد وعناصر التحكم بالأجهزة وعمليات الكتابة عبر الشبكة التأكيد الصريح وضوابط السياسات.

> **باختصار:** ‏uag هو مستوى التحكم بين نماذج الذكاء الاصطناعي وبيئتك الحقيقية.

> **🧠 نتائج الأدوات المراعية للسياق** — يتم استبعاد نتائج الأدوات الكبيرة من سياق النموذج النشط كلما أمكن ذلك. يخزن uag هذه النتائج كـ Artifacts ويمرر للنموذج معاينة محدودة مع مرجع Artifact ثابت بدلاً من ذلك. يمكن أن يقلل هذا بشكل كبير من عدد الرموز المطلوبة للدورات التالية عندما تنتج الأداة نتيجة كبيرة الحجم.
> [دليل مفصل لضغط السياق](CONTEXT_COMPRESSION.ar.md)

## البدء السريع

**Python 3.11+**

```bash
python -m pip install --upgrade uag
uag
```

يفتح التشغيل الأول معالج الإعداد. يساعدك المعالج على تهيئة مزوّد ويخزّن الإعدادات المحددة
في بيئتك المحلية.

لمجموعات الميزات الشائعة:

```bash
python -m pip install "uag[core,providers,tools]"
```

> تكاملات المنصة اختيارية. ثبّت فقط ما يحتاجه نظام التشغيل لديك؛ راجع

```text
> What files changed in this repository?
> Search the web for today's AI news and summarize the top five stories.
> :help
```

[Quickstart](QUICKSTART.md) · [Environment](ENVIRONMENT.md)

## الواجهات

| الواجهة | الأمر | الأنسب لـ |
|---|---|---|
| **CLI** | `uag` | العمل السريع المعتمد على لوحة المفاتيح |
| **واجهة سطح المكتب** | `uagg` | تجربة سطح مكتب أصلية |
| **واجهة الويب** | `uagw` | الوصول عبر المتصفح |
| **خادم A2A** | `uaga` | التواصل بين الوكلاء |
| **VS Code** | Extension | الشرح وإعادة الهيكلة والإصلاح وتصفح الأدوات في المحرر |

تشترك جميع الواجهات في إعداد المزوّد نفسه وسجل الأدوات وقواعد السلامة وبيانات الجلسات.

~~~bash
# Desktop GUI
python -m pip install "uag[platform]"

# Web UI
python -m pip install "uag[web]" fastapi uvicorn
~~~

[Interface options](USAGE.md) · [Environment](ENVIRONMENT.md)

## ما الذي يمكنك بناؤه

تغطي محولات المزوّدين بيئات التشغيل المستضافة والمحلية، بما في ذلك:

- قراءة الملفات وإنشاؤها وتحريرها والبحث فيها وحساب تجزئتها وأرشفتها وفحصها
- مراجعة تغييرات Git والبحث عن الأسرار وتشغيل الاختبارات والفحص والترجمة البرمجية وقياس التغطية
- التنقل في قواعد شيفرة كبيرة مكتوبة بـPython وTypeScript وJavaScript وGo وRust وC/C++ وJava وC# وCOBOL وVBA وغيرها
- أتمتة المتصفحات باستخدام Playwright، بما في ذلك تدفقات الصفحات المتعددة والتنزيلات

- **MCP** — ربط خوادم الأدوات الخارجية، بما في ذلك الخدمات المفعّل لها OAuth
- **A2A** — التنسيق مع الوكلاء الآخرين والخوادم المتوافقة
- **السحابة** — الوصول إلى واجهات AWS وGoogle Cloud وAzure API مع التأكيد لعمليات الكتابة
- **الاتصالات** — Gmail وBluesky وDiscord وMicrosoft Teams وpybitchat
- **إنترنت الأشياء** — SwitchBot وECHONET Lite وMatter وBACnet وModbus TCP وOPC UA وUPnP
- **الوسائط** — إنشاء/تحرير الصور ونسخ الصوت/تحويله إلى كلام والتقاط الكاميرا ورموز QR
- **المستندات** — تحليل PDF وPowerPoint وWord وExcel وCSV وJSON وYAML وSQL والسجلات

- **SwitchBot** — اكتشاف Cloud وBLE والحالة والتحكم والتجميع والاشتراكات
- **ECHONET Lite** — اكتشاف الأجهزة المنزلية اليابانية والتحكم بها، بما في ذلك إشعارات INF
- **Matter** — نقاط النهاية والعناقيد والسمات وسجل الحالة والاشتراكات والتحكم
- **BACnet / Modbus TCP / OPC UA** — القراءة والكتابة والتصفح والمراقبة في أتمتة المباني والصناعة
- **UPnP** — اكتشاف الأجهزة وحالة WAN وإدارة تعيين منافذ الموجّه

### موضع uag

يقع uag بين الأشخاص والواجهات من جهة، والنماذج والأدوات والأنظمة الواقعية من جهة أخرى.
وهو ينسّق المحادثة، ويختار القدرات، ويطبّق قواعد السلامة، ويحافظ على إمكانية استئناف سير العمل.

~~~mermaid
flowchart LR
    UI["CLI · Desktop · Web · VS Code · A2A"] --> UAG["UAG agent runtime"]
    UAG --> MODELS["Hosted & local models"]
    UAG --> TOOLS["Tools & extensions"]
    UAG --> STATE["Sessions & context"]
    TOOLS --> SYSTEMS["Files · Code · Web · MCP · Cloud · IoT"]
    POLICY["Confirmation · Credentials · Policy"] -.-> UAG
~~~

### الإضافات وAgent Skills والأسواق

حوّل uag إلى وكيل متخصص من دون تفريع النواة:

- ثبّت **إضافات متوافقة مع Claude Code** من دليل أو ZIP أو مستودع Git أو مصدر HTTP أو سوق
- اجمع المهارات والوكلاء الفرعيين وخوادم MCP والخطافات وأوامر الشرطة المائلة وأنماط الإخراج والتبعيات والقنوات
- تصفّح القدرات المجتمعية من [SkillsMP](https://skillsmp.com) و[ClawHub](https://clawhub.ai)
- أضف مهارات وأدوات مؤسستك الخاصة محليًا عبر `UAGENT_EXTERNAL_TOOLS_DIR`

```text
:skills mp_search browser automation
:plugin list
:plugin install <source>
:plugin marketplace list
```

راجع [دليل تطوير الإضافات](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP_PLUGIN.md).

- **أكثر من 200 أداة** للملفات والويب والوسائط والمستندات والشيفرة والسحابة والاتصالات وإنترنت الأشياء
- **الاكتشاف والتحميل الديناميكيان** — استخدم `tool_catalog` للعثور على القدرات و`tool_load` لتمكينها عند الحاجة فقط
- **ذكاء الشيفرة** — ‏`code_map` ومتصفحات `idx` الخاصة باللغات ومراجعة Git وتنفيذ الاختبارات والفحص والترجمة البرمجية والتغطية
- **إضافات متوافقة مع Claude Code** تتضمن المهارات والوكلاء وخوادم MCP والخطافات والأوامر والأسواق
- **Agent Skills** من SkillsMP وClawHub
- **أدوات Python مخصصة** باستخدام `TOOL_SPEC` و`run_tool()`
- **أدوات مدعومة بـRust** للإضافات الأصلية خفيفة الوزن

[Tool Creator Guide](../TOOL_CREATOR_GUIDE.md) · [MCP OAuth / Proxy Guide](MCP_OAUTH_PROXY_GUIDE.md)

## مصمم لسير العمل الفعلي

### 🧠 نتائج الأدوات المراعية للسياق

يتم استبعاد نتائج الأدوات الكبيرة من سياق النموذج النشط كلما أمكن ذلك. يخزن uag هذه النتائج كـ Artifacts ويمرر للنموذج معاينة محدودة مع مرجع Artifact ثابت بدلاً من ذلك. يمكن أن يقلل هذا بشكل كبير من عدد الرموز المطلوبة للدورات التالية عندما تنتج الأداة نتيجة كبيرة الحجم.

استأنف المحادثات السابقة باستخدام `:load <index>`. ويمكن تخزين نتائج الأدوات مؤقتًا، كما يمكن تغيير المزوّدين
من دون إعادة بناء التطبيق.

[Context compression](CONTEXT_COMPRESSION.ar.md) · [Memory](MEMORY.md) · [Session portability](SESSION_PORTABILITY.md)

### القيادة الآلية

استخدم `:auto` للعمل متعدد الجولات مع نموذج مراجِع اختياري. عيّن حدًا للجولات باستخدام `--max-rounds N`.
اضغط **F12** لإيقاف القيادة الآلية أو **F12** لإيقاف الاستجابة الحالية.

تعمل العمليات المستقلة للقراءة فقط بالتزامن عندما يكون ذلك آمنًا. ويمكن لعمليات البحث على الويب وفحص
الملفات وتحليل المستودعات وأحمال العمل المماثلة أن تكتمل بالتوازي باستخدام مجموعة عمال قابلة للتهيئة
(`UAGENT_PARALLEL_WORKERS`). أما عمليات الكتابة فتبقى متسلسلة أو تتطلب تأكيدًا.

تجعل استمرارية الجلسة وتخزين نتائج الأدوات مؤقتًا وحالة الدُفعات واستعادة التشغيل وجدولة DAG
وتنسيق الوكلاء المتعددين العمل المعقد قابلًا للاستئناف بدلًا من كونه تنفيذًا لمرة واحدة.

[Auto-pilot](README_AUTO.md) · [Timers](SET_TIMER.md) · [Multi-agent runtime](MULTI_AGENT_RUNTIME.md)

### 🌍 خاص ومتعدد اللغات وواعٍ بالسياسات

تتوقف `human_ask` قبل الإجراءات الحساسة. ويمكن إخضاع حذف الملفات والكتابة فوقها وأوامر الصدفة وعناصر التحكم
بالأجهزة وعمليات بيانات الاعتماد وعمليات الكتابة عبر الشبكة لقواعد التأكيد والسياسات.

استخدم مخزن بيانات الاعتماد بدلًا من وضع الأسرار طويلة الأمد في المطالبات:

تتضمن واجهة الويب تسجيل الدخول باستخدام OIDC عبر Authorization Code + PKCE، رموز تعريف الهوية المُحققة، جلسات على جانب الخادم، وضوابط وصول للمشاريع/الغرف. يمكن لمطالبات مجموعات Microsoft Entra ID المُحققة أن تغذي سياسة الوصول المدعومة بالدليل عند التكوين. يمكن لتوزيعات Windows Active Directory وOAuth وtrusted-proxy التكامل من خلال محولات هوية مُحققة ومحددة النشر؛ يتطلب Windows AD محقق Kerberos/Negotiate محدد النشر ولا يتم تمكينه بشكل افتراضي.

يتضمن uag تتبع OpenTelemetry المحايد للموفر ومقاييس لعمليات Agent وLLM والأداة وContext وMemory وعمليات الاسترداد. يتم تعطيل إمكانية الملاحظة بشكل افتراضي.

إعطاء الأولوية للتنفيذ المحلي لا يعني أن UAG يعمل بالكامل دون اتصال أو أن جميع الأدوات معزولة افتراضيًا. تعتمد طلبات النماذج والخدمات الخارجية على الإعدادات.

- [Enterprise policies](ENTERPRISE_POLICY.md)
- [MXC sandbox](SANDBOX_MXC.md)
- [Remote Web / A2A](REMOTE_MXC_DEFAULT.md)
- [Web identity](WEB_IDENTITY_MEMORY.md)
- [OpenTelemetry](UAG_OPENTELEMETRY_DESIGN.md)

### 🌍 الترجمة متعددة اللغات

- يدعم `translate_text` Google Translate وعميل DeepL الرسمي للغة Python من خلال `provider=auto` أو `provider=deepl` أو `provider=google`.
- تتوفر تعريفات الأدوات في 37 لغة بالإضافة إلى الإنجليزية (38 لغة إجمالًا)، مع الحفاظ على العناصر النائبة والمعرفات الفنية.

يتوفر الصوت ثنائي الاتجاه عبر OpenAI Realtime وAzure OpenAI وxAI Grok Voice وGemini Live
وBedrock Nova Sonic، مع إلغاء صدى AEC3 اختياري واستدعاء دوال لحظي مقيّد بالسلامة.

[Translations](README.translations.md) · [IoT](IOT_USECASE.md) · [Communication](COMMUNICATION.md)

## الوثائق

| الموضوع | الوثائق |
|---|---|
| متغيرات البيئة | [docs/ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/docs/ENVIRONMENT.md) |
| البنية والثوابت | [docs/ARCHITECTURE.md](https://github.com/awaku7/agentcli/blob/main/docs/ARCHITECTURE.md) |
| Computer Use | [docs/COMPUTER_USE_IMPLEMENTATION.md](https://github.com/awaku7/agentcli/blob/main/docs/COMPUTER_USE_IMPLEMENTATION.md) |
| أدوات المستودع | [docs/REPOSITORY_TOOLS.md](https://github.com/awaku7/agentcli/blob/main/docs/REPOSITORY_TOOLS.md) |
| حالات استخدام IoT | [docs/IOT_USECASE.md](https://github.com/awaku7/agentcli/blob/main/docs/IOT_USECASE.md) |
| أدوات الاتصال | [docs/COMMUNICATION.md](https://github.com/awaku7/agentcli/blob/main/docs/COMMUNICATION.md) |
| القيادة الآلية | [docs/README_AUTO.md](https://github.com/awaku7/agentcli/blob/main/docs/README_AUTO.md) |
| MCP OAuth / Proxy | [docs/MCP_OAUTH_PROXY_GUIDE.md](https://github.com/awaku7/agentcli/blob/main/docs/MCP_OAUTH_PROXY_GUIDE.md) |
| إضافة VS Code | [docs/VSCODE.md](https://github.com/awaku7/agentcli/blob/main/docs/VSCODE.md) |
| دليل المطوّر | [src/uagent/docs/DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md) |
| تدفق الأدوات | [src/uagent/docs/TOOL_FLOW.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/TOOL_FLOW.md) |

[Quickstart](QUICKSTART.md) · [Architecture](ARCHITECTURE.md) · [Context management](UAG_CONTEXT_MANAGEMENT_DESIGN.md)

## التطوير والمساهمة

```bash
git clone https://github.com/awaku7/agentcli.git
cd agentcli
python -m pip install -e ".[core,providers,test]"
```

شغّل فحوصات ما قبل PR:

```bash
python -m ruff check src tests
python -m black --check src tests
python -m pytest -q .
```

للاطلاع على سير عمل التطوير الكامل، راجع [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md).

نرحب بتقارير الأخطاء وأفكار الميزات وتحسينات الوثائق والترجمات والأدوات والمهارات وطلبات السحب.
يرجى فتح issue أو مناقشة قبل إجراء تغييرات كبيرة. اقرأ [دليل المطوّر](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)
وشغّل الفحوصات أعلاه قبل إرسال طلب سحب.

## الترخيص

مرخّص بموجب [Apache License 2.0](https://github.com/awaku7/agentcli/blob/main/LICENSE).
