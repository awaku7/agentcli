<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="720">
</p>

<h1 align="center">uag - بوابة الذكاء الاصطناعي العالمية</h1>

<p align="center">
  <b>U</b>niversal <b>A</b>I <b>G</b>ateway — Your environment, your freedom.
</p>

<p align="center">
  File ops / Web search / Image generation &amp; analysis / PDF &amp; Excel extraction / IoT control / MCP integration<br>
  20+ providers / 3 UIs / Parallel tool execution / Agent Skills marketplace
</p>

<p align="center">
  <a href="https://github.com/awaku7/agentcli">GitHub</a>
  ·
  <a href="https://pypi.org/project/uag/">PyPI</a>
  ·
  <a href="https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md">Read this in your language</a>
</p>

---

## لماذا UAG؟

**تحرر من تقييد البائع.** يربطك معظم مساعدي الذكاء الاصطناعي بمزود معين أو خدمة سحابية. uag مختلف.

- **يعمل محليًا** على جهازك. تظل بياناتك معك (باستثناء استدعاءات واجهة برمجة التطبيقات التي تجريها).
- **حرية المزود**: OpenAI، وClaude، وGemini، وDeepSeek، وOllama، وAzure، وBedrock، وHuggingFace... 21 مقدمًا، يمكن الوصول إليهم جميعًا من واجهة واحدة. قم بالتبديل بينهما عن طريق إعادة تكوين متغيرات البيئة - دون الحاجة إلى إعادة التثبيت أو الترحيل.
- **185 أداة**: إدخال/إخراج الملفات، وبحث الويب، وإنشاء الصور، وGmail، ومسح جهاز BLE، وتكامل خادم MCP - **111 أداة آمنة بالتوازي** (يتم تنفيذ ما يصل إلى 8 أدوات بشكل متزامن عبر مجموعة مؤشرات الترابط، ويمكن تكوينها عبر `UAGENT_PARALLEL_WORKERS`). عندما يطلق LLM استدعاءات متعددة للأدوات مرة واحدة، يقوم uag بموازاة هذه الاستدعاءات تلقائيًا.
- **3 واجهات مستخدم + A2A**: واجهة سطر الأوامر (CLI) وواجهة المستخدم الرسومية (GUI) والويب وبروتوكول وكيل إلى وكيل. نفس المحرك، أي واجهة.
- **مهارات الوكيل**: قم بتثبيت المهارات المجتمعية من السوق. تمديد UAG إلى ما لا نهاية.

uag هو **مساعد الذكاء الاصطناعي الخاص بك وفقًا لشروطك**. غير مرتبط بمزود، وغير مرتبط بواجهة، وغير مرتبط بمنصة.

## بداية سريعة

```bash
pip install uag
uag
```

عند التشغيل لأول مرة، يرشدك معالج الإعداد عبر تكوين الموفر.
راجع [docs/ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/docs/ENVIRONMENT.md) للتعرف على جميع متغيرات البيئة.

## سمات

### 🧠 بنية متعددة الموفرين

OpenAI / Azure / Bedrock / OpenRouter / Ollama / Gemini / Vertex AI / Claude / Grok / NVIDIA / DeepSeek / Z.AI (Zhipu AI) / HuggingFace / Alibaba Cloud (Qwen) / KIMI (Moonshot AI) / Xiaomi MiMo / LM Studio / MiniMax / **Sakana AI (Fugu)** / **Together AI** / **Vercel AI Gateway**

يتشارك جميع مقدمي الخدمة في نفس مجموعة الأدوات والواجهة. قم بالتبديل عن طريق إعداد `UAGENT_PROVIDER` - لا توجد تغييرات في التعليمات البرمجية، ولا توجد عمليات تثبيت منفصلة.

### ⚡ تنفيذ الأداة الموازية

عندما يطلب LLM أدوات متعددة في وقت واحد، يقوم uag بموازاة هذه الأدوات تلقائيًا.
تم وضع علامة على 87 أداة `x_parallel_safe` ويتم تنفيذها بشكل متزامن عبر `ThreadPoolExecutor` (8 سلاسل بشكل افتراضي؛ قم بتعيين `UAGENT_PARALLEL_WORKERS` للتغيير).

**مثال**: اسأل "التحقق من الطقس في عواصم بلدان الشمال الأوروبي" ← تطلق LLM `search_web` × 5 دول ← يتم تشغيل جميع عمليات البحث الخمسة بالتوازي ← يتم جمع النتائج في دفعة واحدة.

أدوات القراءة فقط (البحث عن الملفات، وحساب التجزئة، وقائمة الدليل، والترجمة، واستعلامات قاعدة البيانات، وما إلى ذلك) متوازية بقوة.


### 🧩 Plugin System (Claude Code Compatible)

uagent implements a **Claude Code-compatible plugin system**. Plugins bundle skills, agents, MCP servers, hooks, and more into self-contained directories with a `.claude-plugin/plugin.json` manifest.

**Supported components**: Skills, Sub-agents, MCP servers, Hooks (12 lifecycle events), Slash commands, Output styles, userConfig, Dependencies, Channels, Marketplaces

**CLI commands**:
```
:plugin list                         # List installed plugins
:plugin install <source> [--scope]   # Install (dir/zip/git/http)
:plugin install <name>@<marketplace>  # Install from marketplace
:plugin remove <name>                # Uninstall
:plugin enable/disable <name>        # Toggle
:plugin marketplace add/remove/list  # Manage marketplaces
:plugin init <name>                  # Scaffold new plugin
```

See [DEVELOP_PLUGIN.md](src/uagent/docs/DEVELOP_PLUGIN.md) for full documentation.


### 🔄استمرارية الجلسة

- **Switch providers mid-session** with `UAGENT_PROVIDER` — conversation history is preserved.
- **Reload past sessions** with `:load <index>` — pick up where you left off.
- **Tool result caching** avoids redundant re-execution when the same tool call repeats.

### 🛠 185 أداة

| الفئة | أدوات |
|---|---|
| **عمليات الملف** | قراءة/كتابة/إنشاء/حذف/بحث/grep/hash/zip, file_type, parse_eml (ملفات .eml) |
| **الويب** | fetch_url، search_web، لقطة شاشة، browser_playwright |
| **الإعلام** | إنشاء صورة، تحليل الصورة، img2img، audio_speech، audio_transcribe |
| **الوثائق** | استخراج PDF/PPTX/DOCX/RTF/ODT، استخراج منظم لـ Excel |
| **تنبؤ** | التنبؤ بالسلاسل الزمنية باستخدام 9 نماذج (AutoARIMA وProphet وLightGBM وCatBoost وTimesFM وغيرها)، اختيار النموذج تلقائيًا، إنشاء الرسوم البيانية، تدويل i18n |
| **الاتصالات** | gmail_send، gmail_read، bluesky، discord_channel، Teams_webhook، **pybitchat** (BLE Mesh) — راجع [COMMUNICATION.md](https://github.com/awaku7/agentcli/blob/main/docs/COMMUNICATION.md) و [BITCHAT.md](https://github.com/awaku7/agentcli/blob/main/docs/BITCHAT.md) |
| **إنترنت الأشياء** | SwitchBot (Cloud + BLE)، ECHONET Lite، Matter، UPnP، reverse_geocode |
| ** أدوات التطوير ** | git_ops، python_compile، lint_format، run_tests، db_query، ** 13 متصفحًا لكود المصدر (عائلة idx) ** |
| **الخطة التشاورية المتعددة الأطراف** | الاتصال بخوادم MCP الخارجية، وقائمة الأدوات، وتنفيذ |
| **A2A** | الاتصال من وكيل إلى وكيل (مع مثيلات UAG الأخرى أو الخوادم المتوافقة مع A2A) |
| **النظام** | env vars، مواصفات النظام، الوقت، حساب التاريخ, uuid_gen, slugify ||
| **التنقل المصدر** | **13 أداة idx** لـ Python وPHP وTypeScript وJava وC# وDart وC/C++ وRust وGo وSwift وKotlin وCOBOL - احصل على فهرس وظيفة/فئة أو تعريف محدد دون قراءة الملف بأكمله |

### 🖥 4 واجهات + ملحق VS Code

| الوضع | الأمر | الغرض |
|---|---|---|
| ** سطر ** | `واج` | عملية سريعة تعتمد على المحطة |
| ** واجهة المستخدم الرسومية ** | `واغ` | واجهة مستخدم سطح المكتب عبر tkinter |
| **الويب** | `واجو` | الوصول عبر المتصفح |
| **خادم A2A** | `واجا` | بروتوكول Agent2Agent للاتصال متعدد الوكلاء |
| **رمز VS** | — | [ملحق](https://github.com/awaku7/agentcli/blob/main/docs/VSCODE.md) مع لوحة الدردشة والشرح وإعادة البناء وإصلاح الخطأ وعرض شجرة الأدوات |

راجع [VSCODE.md](https://github.com/awaku7/agentcli/blob/main/docs/VSCODE.md) للحصول على تفاصيل حول ملحق VS Code - التثبيت والأوامر وارتباطات المفاتيح والتكوين.

### 🏠 التحكم في أجهزة إنترنت الأشياء
- **المسألة**: فحص للقراءة فقط لهيكل وحدة التحكم/الجسر/الجهاز

راجع [IOT_USECASE.md](https://github.com/awaku7/agentcli/blob/main/docs/IOT_USECASE.md)


### 🏠 التحكم في جهاز إنترنت الأشياء

- **BACnet**: قراءة/كتابة أجهزة BACnet/IP (HVAC، الإضاءة، عدادات الطاقة). اشتراك COV لإشعارات الدفع
- **Modbus TCP**: قراءة/كتابة سجلات وملفات الإدخال/الإمساك. مراقبة التغيير القائم على الاقتراع
- **OPC UA**: تصفح مساحة العنوان، ومتغيرات القراءة/الكتابة، والاشتراك في تغييرات البيانات
- **SwitchBot**: التحكم في مجموعة السحابة ومسح/تحكم BLE. الاشتراك المستند إلى الاقتراع
- **ECHONET Lite**: اكتشف إشعارات INF الواردة من الأجهزة المنزلية (أجهزة تكييف الهواء والأضواء وسخانات المياه وما إلى ذلك) والتحكم فيها والاشتراك فيها.)
- **Matter**: التحكم في القراءة/الكتابة + الاشتراك في السمات لمراقبة تغيير الحالة
- **UPnP**: اكتشاف الأجهزة وإعادة توجيه منفذ IGD

راجع [IOT_USECASE.md](IOT_USECASE.md)

### 🎯 سوق مهارات الوكيل

`:skills mp_search` لتصفح [SkillsMP](https://skillsmp.com) و[ClawHub](https://clawhub.ai) للتعرف على مهارات المجتمع.
قم بتثبيت وتوسيع قدرات UAG بسرعة.

### 🤖 الطيار الآلي (`:تلقائي`)

يمكن لـ uag ** متابعة الهدف بشكل مستقل عبر جولات LLM متعددة **. مثالية للمهام المعقدة ومتعددة الخطوات التي تحتاج إلى تحسين متكرر.

- **كيفية العمل**: تحتوي كل جولة على استعلام رئيسي (الخطوة أ) متبوعًا بحكم المراجع (الخطوة ب) الذي يقرر "إكمال أم متابعة؟"
- **نفس الموفر، نفس واجهة برمجة التطبيقات**: يستخدم حكم المراجع مسار التعليمات البرمجية المطابق للاستعلام الرئيسي - بما في ذلك دعم واجهة برمجة التطبيقات للاستجابات.
- **محكم منفصل LLM** (اختياري): قم بتعيين `UAGENT_AP_PROVIDER` لاستخدام مزود/نموذج مختلف للمراجع (على سبيل المثال، استخدم نموذجًا أرخص للتحكيم).
- **الخروج في أي وقت**: اضغط على مفتاح x للتوقف فورًا، حتى في منتصف الاستجابة. أو دع المراجع يقرر متى يتم تحقيق الهدف.
- **قابل للتكوين**: `--max-rounds N` للتحكم في الميزانية.

راجع [README_AUTO.md](https://github.com/awaku7/agentcli/blob/main/docs/README_AUTO.md) للحصول على الوثائق الكاملة.

### 🧩 مدير حالة الدفعة

يمكن لـ uag تتبع التقدم عبر مهام متعددة الملفات طويلة الأمد. عندما تقوم LLM بمعالجة العشرات من الملفات، فإن "batch_state" يحتفظ بقائمة الملفات المعلقة والمكتملة والفاشلة على القرص. إذا انتهت الجلسة أو انتهت مدة الجولة، فسيتم استئناف التشغيل التالي من حيث توقف - ولن يتم فقدان أي شيء.

### 🛡 الإنسان في الحلقة

يتيح `human_ask` لـ LLM التوقف مؤقتًا وطلب تأكيدك قبل تنفيذ العمليات المدمرة (حذف الملف، الكتابة الفوقية، أوامر الصدفة). يمكنك البقاء في السيطرة.

### 🛑 المقاطعة (مفتاح c / زر الإيقاف)

قم بإيقاف إنشاء استجابة LLM في أي وقت وأدخل أمر الإيقاف مرة أخرى إلى LLM.

| الواجهة | كيفية المقاطعة |
|---|---|
| ** سطر ** | اضغط على مفتاح `c` أثناء بث LLM - تتوقف الاستجابة الحالية، ويتم إرسال `"Stop"` كرسالة مستخدم حتى يستجيب LLM وفقًا لذلك |
| ** واجهة مستخدم الويب ** | انقر فوق الزر الأحمر **■ إيقاف** (يظهر تلقائيًا أثناء معالجة LLM) |
| **واجهة المستخدم الرسومية لسطح المكتب** | انقر فوق الزر الأحمر **■** (يظهر تلقائيًا أثناء معالجة LLM) |

تعمل المقاطعة كـ "إدخال سريع": بدلاً من مجرد الإجهاض، فإنها تغذي ""Stop"" مرة أخرى إلى LLM كرسالة مستخدم، مما يسمح لها بإنهاء المقاطعة أو الإقرار بها بأمان.

اضغط على المفتاح "x" للخروج من وضع الطيار التلقائي (راجع [README_AUTO.md](https://github.com/awaku7/agentcli/blob/main/docs/README_AUTO.md)).

### 🕵️ أتمتة المتصفح ومفتش الويب

أداتان متكاملتان تعتمدان على الكاتب المسرحي:

- **browser_playwright**: أتمتة جلسات المتصفح الحقيقية — التنقل، والنقر، وملء النماذج، واستخراج البيانات، والتعامل مع التدفقات المتعددة الصفحات. يعمل بدون رأس أو رأس.
- **playwright_inspector**: تسجيل انتقالات المتصفح، والتقاط لقطات DOM ولقطات الشاشة في كل خطوة. مفيد لتصحيح أخطاء تفاعلات الويب أو تدقيق تغييرات الصفحة بمرور الوقت.

### 🔄 التحميل الديناميكي للأداة

يتيح لك `tool_catalog` و`tool_load` اكتشاف الأدوات وتمكينها في وقت التشغيل.
لا داعي لتحميل كل شيء عند بدء التشغيل - قم بتنشيط ما تحتاجه فقط، عندما تحتاج إليه.

### 🦀 Rust Native Tools

`uuid_gen` and `slugify` are implemented in Rust (via PyO3) for performance.
They load directly from a pre-built `.pyd` — **no `pip install` required**.

External developers can also ship Rust-based tools: place a `.pyd` next to the
wrapper `.py`, use ``load_rust_pyd()`` from ``uagent.tools.rust_helper``, and
users get the tool without any extra dependencies. See
[TOOL_CREATOR_GUIDE.ar.md](TOOL_CREATOR_GUIDE.ar.md).

### 🌐i18n / L10n

日本語 / الإنجليزية / 简体中文 / 繁體中文 / 한국어 / Español / Français / Русский / والمزيد.
اضبط "UAGENT_LANG" للتبديل. راجع [ADD_LOCALE.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/ADD_LOCALE.md) لإضافة لغة جديدة.

تتوفر ترجمات هذا الملف التمهيدي في [docs/README.translations.md](https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md).

### 🔒 متغيرات البيئة المشفرة

قم بتخزين مفاتيح وأسرار واجهة برمجة التطبيقات في ملف `.env.sec` - وهو ملف مشفر `.env`.
الإدارة باستخدام "uag_envsec".

## التكوين والتفاصيل

- **متغيرات البيئة**: [docs/ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/docs/ENVIRONMENT.md)
- **معالج الإعداد**: `python -m uagent.setup_cli`
- **env المشفر**: `uag_envsec` — تشفير `.env` كـ `.env.sec`
- **Responses API**: قم بتعيين `UAGENT_RESPONSES=1` لوضع واجهة برمجة التطبيقات للاستجابات (OpenAI/Azure/Bedrock/OpenRouter/Ollama/Alibaba/LM Studio/Sakana AI). تم تمكينه تلقائيًا لـ Sakana AI (Fugu).
- **مستندات المطورين**: [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)
- **Tool flow**: [TOOL_FLOW.md](../src/uagent/docs/TOOL_FLOW.md)
- **نصائح LLM الصغيرة**: [SLM_TIPS.md](https://github.com/awaku7/agentcli/blob/main/docs/SLM_TIPS.md)

## فلسفة المشروع

تطمح uag إلى أن تكون **الذكاء الاصطناعي الخاص بك، على جهازك، وفقًا لشروطك.**

- لا توجد تبعية SaaS - تعمل محليًا
- لا يوجد قفل للمزود - قم بالتبديل في أي وقت
- لا يوجد قفل لواجهة المستخدم — CLI / GUI / Web / A2A
- لا يوجد قفل للميزات - قم بالتوسيع باستخدام الأدوات والمهارات

تجربة وكيل AI مجانية، خالية من تقييد البائع.

### ✨ Create Your Own Tools

Writing a new tool for uag is straightforward — create a single `.py` file with
`TOOL_SPEC` and `run_tool()`, place it in ``UAGENT_EXTERNAL_TOOLS_DIR``, and
it's immediately available. For Rust developers, ship a pre-built `.pyd` with
zero extra dependencies for users.

See [TOOL_CREATOR_GUIDE.ar.md](TOOL_CREATOR_GUIDE.ar.md)
for the step-by-step guide.

## Contributing

Contributions are welcome! Bug reports, feature suggestions, documentation improvements, translations, and pull requests — all appreciated.

- **Issues**: Open a GitHub issue for bugs or feature requests.
- **Pull requests**: Fork the repo, make your changes, and submit a PR. See [DEVELOP.md](../src/uagent/docs/DEVELOP.md) for development setup and guidelines.
- **Translations**: README translations and locale additions are welcome. See [ADD_LOCALE.md](../src/uagent/docs/ADD_LOCALE.md).
- **Tools & Skills**: New tool plugins and Agent Skills can be contributed via the marketplace.

Realtime صوت و AEC3

## Realtime يدعم وضع الصوت ميكروفون مزدوج الاتجاه وإدخال/إخراج مكبر الصوت. إذا كانت الواجهة الخلفية AEC3 مفقودة، فسيقوم uag بتثبيت pywebrtc-audio تلقائيًا.

```bat
python scheck.py realtime
```

يستخدم AEC3 إشارة الميكروفون الفعلية (قريب) والصوت الذي يتم إرساله فعليًا إلى مكبر الصوت (بعيد). قم بتمكين التشخيص فقط عند التحقيق في مشكلات الصوت.

```bat
set UAGENT_REALTIME_AUDIO_DEBUG=1
python scheck.py realtime
```

### OpenAI Realtime Function Calling

OpenAI Realtime يدعم التكامل المحدود الأمان Function Calling. يعرض المحول الحالي وظيفة القراءة فقط get_current_time تلقائيًا. تتطلب الأدوات التدميرية وعناصر التحكم في الأجهزة وجود قائمة مسموح بها وتدفق تأكيد واضح. يستخدم الوقت الفعلي Grok محولًا منفصلاً ولا يستخدم مسار Function Calling الخاص بـ OpenAI.
