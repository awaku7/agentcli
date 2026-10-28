<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="UAG — Universal AI Gateway" width="620">
</p>
<h1 align="center">UAG</h1>
<p align="center"><strong>Universal AI Gateway</strong><br>نماذج الذكاء الاصطناعي الخاصة بك. أدواتك. بيئتك.</p>

<p align="center">
  <a href="https://github.com/awaku7/agentcli/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/awaku7/agentcli/ci.yml?style=flat-square&label=CI" alt="CI"></a>
  <a href="https://pypi.org/project/uag/"><img src="https://img.shields.io/pypi/v/uag?style=flat-square" alt="PyPI"></a>
  <a href="https://pypi.org/project/uag/"><img src="https://img.shields.io/pypi/pyversions/uag?style=flat-square" alt="Python versions"></a>
  <a href="../LICENSE"><img src="https://img.shields.io/github/license/awaku7/agentcli?style=flat-square" alt="License"></a>
  <a href="https://pepy.tech/projects/uag"><img src="https://static.pepy.tech/personalized-badge/uag?period=total&units=INTERNATIONAL_SYSTEM&left_color=grey&right_color=green&left_text=downloads" alt="Downloads"></a>
</p>
<p align="center"><a href="../README.md">English</a> · <a href="README.translations.md">لغات أخرى</a></p>

---

**UAG بيئة تشغيل مفتوحة المصدر لوكلاء الذكاء الاصطناعي تعطي الأولوية للعمل المحلي.** تصل نموذج اللغة الذي تختاره بالأدوات والأنظمة التي تستخدمها. يمكنك التعامل مع التعليمات البرمجية والملفات والمتصفحات والخدمات والأجهزة من واجهة موحدة دون ربط سير عملك بمزوّد نماذج واحد.

| **اختر النموذج** | **اربط الأدوات الفعلية** | **احتفظ بالتحكم** |
| :--- | :--- | :--- |
| نماذج مستضافة ومحلية مثل OpenAI وClaude وGemini وGrok وBedrock وOllama | الملفات والبرمجة والويب وMCP وAgent Skills والإضافات والسحابة وIoT | تشغيل محلي وتأكيد بشري وتخزين بيانات الاعتماد وسياسات قابلة للضبط |

> UAG هو **طبقة لتنفيذ الوكلاء، وليس مزوّد نماذج**. تعتمد طلبات النماذج والخدمات الخارجية على الإعدادات. لا تعني أولوية التشغيل المحلي عملًا كاملًا دون اتصال أو عزل جميع الأدوات بصورة افتراضية.

## البدء السريع
<!-- README-SYNC:quick-start -->

يتطلب **Python 3.11 أو إصدارًا أحدث**. ثبّت UAG من [PyPI](https://pypi.org/project/uag/) ثم شغّل واجهة الأوامر التفاعلية:

~~~bash
python -m pip install --upgrade uag
uag
~~~

في التشغيل الأول، يساعدك معالج الإعداد في اختيار مزوّد النماذج وضبط بيانات الاعتماد. ويمكنك استخدام متغيرات البيئة أو مخزن بيانات الاعتماد أيضًا. لتثبيت مجموعة أوسع من اعتماديات المزوّدين والأدوات مسبقًا:

~~~bash
python -m pip install "uag[core,providers,tools]"
~~~

جرّب بعد ذلك الطلبات التالية:

~~~text
> ما الذي تغيّر في مستودع Git هذا؟ لخّص المخاطر.
> ابحث عن أحدث توثيق لهذه المكتبة واشرح خطوات الترحيل.
> افحص هذه الملفات وقدّم تقريرًا مختصرًا.
> :help
~~~

للمستخدم الجديد، راجع دليل تثبيت Windows بما فيه Git والبيئات الافتراضية، ومرجع الإعدادات: [Quickstart (Windows)](QUICKSTART.md) · [Environment](ENVIRONMENT.md).

## الواجهات
<!-- README-SYNC:interfaces -->

تستخدم جميع المداخل بيئة تشغيل الوكيل نفسها وسجل الأدوات نفسه.

| الواجهة | التشغيل | الاستخدام المناسب |
| :--- | :--- | :--- |
| **CLI** | `uag` | العمل في الطرفية والأتمتة |
| **Desktop** | `uagg` | المحادثات في تطبيق سطح المكتب |
| **Web** | `uagw` | المحادثات والغرف في المتصفح |
| **A2A** | `uaga` | تكامل الوكلاء فيما بينهم |
| **VS Code** | [دليل الإضافة](VSCODE.md) | العمل إلى جانب الشيفرة |

تحتاج واجهتا Desktop وWeb إلى اعتماديات إضافية غير مشمولة في التثبيت الأولي `uag[core,providers,tools]`:

~~~bash
# Desktop GUI (PySide6 and platform integrations)
python -m pip install "uag[platform]"

# Web UI (authentication dependencies, FastAPI, and Uvicorn)
python -m pip install "uag[web]" fastapi uvicorn
~~~

يمكن لخادم Web محاولة تثبيت FastAPI وUvicorn عند بدء التشغيل. يجنّب تثبيتهما مسبقًا الاعتماد على التثبيت التلقائي. التفاصيل: [CLI usage](USAGE.md) · [Environment](ENVIRONMENT.md).

## ما الذي يمكنك إنجازه باستخدام UAG
<!-- README-SYNC:capabilities -->

| الإمكانية | ما يوفّره UAG |
| :--- | :--- |
| **سير عمل مستقل عن النموذج** | تبديل المزوّدين المحليين والمستضافين باستخدام `UAGENT_PROVIDER` دون إعادة كتابة الأدوات |
| **البرمجة والملفات** | استعراض المستودعات وفحص Git والتحليل والاختبارات وعمليات الملفات وأتمتة المتصفح |
| **أدوات قابلة للتوسعة** | أكثر من 200 أداة واكتشاف ديناميكي عبر `tool_catalog` و`tool_load` وأدوات Python وRust مخصصة |
| **وكلاء مترابطون** | MCP وA2A وإضافات متوافقة مع Claude Code وAgent Skills والوكلاء الفرعيون |
| **المهام الطويلة** | الطيار الآلي وقراءات مستقلة متوازية ومهام مجدولة واستعادة الجلسات وحفظها |
| **ما وراء الطرفية** | السحابة والاتصالات والمستندات والوسائط والصوت الفوري وبروتوكولات IoT المدعومة |

### بيئة تشغيل واحدة وتكاملات متعددة
<!-- README-SYNC:integrations -->

~~~mermaid
flowchart LR
    UI["CLI · Desktop · Web · VS Code · A2A"] --> UAG["UAG agent runtime"]
    UAG --> MODELS["Hosted & local models"]
    UAG --> TOOLS["Tools & extensions"]
    UAG --> STATE["Sessions & context"]
    TOOLS --> SYSTEMS["Files · Code · Web · MCP · Cloud · IoT"]
    POLICY["Confirmation · Credentials · Policy"] -.-> UAG
~~~

**أمثلة لمزوّدي النماذج المدعومين** مدرجة أدناه. راجع دليل البيئة لإعدادات كل مزوّد.

**OpenAI · Anthropic · Gemini · Vertex AI · Azure OpenAI · Amazon Bedrock · Grok · DeepSeek · OpenRouter · Ollama · llama.cpp · LM Studio**

[ENVIRONMENT.md](ENVIRONMENT.md)

### التخصيص بالمهارات والإضافات
<!-- README-SYNC:extensions -->

وسّع UAG دون تغيير النواة. ثبّت Agent Skills من SkillsMP أو ClawHub، أو اربط خوادم MCP، أو حمّل إضافات متوافقة مع Claude Code تشمل أدوات ومهارات ووكلاء وhooks.

~~~text
:skills mp_search browser automation
:plugin list
:plugin install <source>
:plugin marketplace list
~~~

يمكن للأدوات المخصصة توفير `TOOL_SPEC` و`run_tool()`؛ كما تُدعم الأدوات المبنية باستخدام Rust. راجع الأدلة: [Tool Creator Guide](../TOOL_CREATOR_GUIDE.md) · [Plugin Development Guide](../src/uagent/docs/DEVELOP_PLUGIN.md) · [MCP OAuth / Proxy](MCP_OAUTH_PROXY_GUIDE.md).

## مصمم لسير العمل الحقيقي
<!-- README-SYNC:workflows -->

### السياق والذاكرة
<!-- README-SYNC:context-memory -->

يمكن حفظ نتائج الأدوات الكبيرة بوصفها **مصنوعات (Artifacts)** بدلًا من ملء سياق النموذج النشط. يسترجع الوكيل لاحقًا الجزء المطلوب عبر `artifact_read`. تُحفظ الجلسات في SQLite افتراضيًا مع البحث في السجل ومراجعة صريحة للذاكرة.

- [Context compression](CONTEXT_COMPRESSION.ar.md)
- [Memory](MEMORY.md)
- [Session portability](SESSION_PORTABILITY.md)

### الأتمتة والتعاون
<!-- README-SYNC:automation -->

يدعم UAG عمليات القراءة المستقلة المتوازية وتنسيق عدة وكلاء واستعادة الجلسات والطيار الآلي للعمل متعدد الجولات. شغّله باستخدام `:auto`، واضغط **F12** لمقاطعة الرد الحالي وطلب إيقاف الطيار الآلي.

- [Auto-pilot](README_AUTO.md)
- [Timers and scheduled tasks](SET_TIMER.md)
- [Multi-agent runtime](MULTI_AGENT_RUNTIME.md)

### الأمان وقابلية الرصد
<!-- README-SYNC:security -->

يمكن أن تتطلب الإجراءات الحساسة تأكيد `human_ask`. يمكن حفظ بيانات الاعتماد في مدير النظام أو ملف مشفّر. تدعم واجهة Web تسجيل الدخول عبر OIDC والتحكم في الوصول بعد ضبطهما. تتبّع OpenTelemetry ومقاييسه **اختيارية**.

- [Enterprise policies](ENTERPRISE_POLICY.md)
- [MXC sandbox](SANDBOX_MXC.md)
- [Remote Web / A2A MXC defaults](REMOTE_MXC_DEFAULT.md)
- [Web identity and rooms](WEB_IDENTITY_MEMORY.md)
- [OpenTelemetry design](UAG_OPENTELEMETRY_DESIGN.md)
- [Developer observability](../src/uagent/docs/DEVELOP_OBSERVABILITY.md)

هذه ضوابط قابلة للتكوين **ولا تضمن** عزل تنفيذ أي أداة داخل بيئة حماية. اقرأ أدلة النشر والسياسات قبل إتاحة UAG لمستخدمين أو شبكات غير موثوقة.

### اللغات والأجهزة والصوت
<!-- README-SYNC:languages -->

يوفّر UAG موارد لـ **38 إعدادًا لغويًا** (الإنجليزية و37 ترجمة)، وتكاملًا صوتيًا ثنائي الاتجاه اختياريًا وأدوات لـ SwitchBot وMatter وECHONET Lite وBACnet وModbus TCP وOPC UA.

- [Translations](README.translations.md)
- [IoT use cases](IOT_USECASE.md)
- [Communication tools](COMMUNICATION.md)

## التوثيق
<!-- README-SYNC:documentation -->

ابدأ بهذه المراجع ثم تعمّق في الموضوعات:

| ابدأ هنا | للتفاصيل |
| :--- | :--- |
| [Quickstart (Windows)](QUICKSTART.md) | [Architecture](ARCHITECTURE.md) |
| [CLI usage](USAGE.md) | [Context management](UAG_CONTEXT_MANAGEMENT_DESIGN.md) |
| [Environment and providers](ENVIRONMENT.md) | [Enterprise policy](ENTERPRISE_POLICY.md) |
| [Agent Skills and plugins](../src/uagent/docs/DEVELOP_PLUGIN.md) | [Tool flow](../src/uagent/docs/TOOL_FLOW.md) |
| [MCP and OAuth](MCP_OAUTH_PROXY_GUIDE.md) | [Computer Use](COMPUTER_USE_IMPLEMENTATION.md) |
| [VS Code extension](VSCODE.md) | [Developer guide](../src/uagent/docs/DEVELOP.md) |

يمكنك أيضًا تصفح التوثيق الكامل واللغات الأخرى: [Documentation](./) · [Other languages](README.translations.md).

## التطوير والمساهمة
<!-- README-SYNC:contributing -->

~~~bash
git clone https://github.com/awaku7/agentcli.git
cd agentcli
python -m pip install -e ".[core,providers,test]"
~~~

قبل طلب دمج يغيّر **شيفرة Python**، شغّل الاختبارات والفحوص المناسبة للمشروع:

~~~bash
python -m ruff check src tests
python -m black --check src tests
python -m pytest -q .
~~~

قواعد المساهمة ودليل المطور موجودان أدناه. نرحب بتقارير الأخطاء وتحسين التوثيق والأدوات والترجمات وطلبات الدمج المحددة: [AGENTS.md](../AGENTS.md) · [Developer guide](../src/uagent/docs/DEVELOP.md).

## الترخيص
<!-- README-SYNC:license -->

يُوزّع UAG بموجب ترخيص: [Apache License 2.0](../LICENSE).
