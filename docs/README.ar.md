<p align="center">
 <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="720">
</p>

<h1 align="center">uag — الذكاء الاصطناعي العالمي البوابة</h1>

<p align="center">
 <b>U</b>niversal <b>A</b>I <b>G</b>ateway — بيئتك، حريتك.
</p>

<p align="center">
 عمليات الملفات / Web البحث / إنشاء الصور وتحليلها / استخراج PDF وExcel / التحكم في إنترنت الأشياء / MCP التكامل<br>
 24 مزودًا / 3 واجهات مستخدم / تنفيذ الأدوات المتوازية / سوق مهارات الوكيل
</p>

<p align="center">
 <a href="https://github.com/awaku7/agentcli">GitHub</a>
 ·
 <a href="https://pypi.org/project/uag/">PyPI</a>
 ·
 <a href="https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md">Read this in your language</a>
</p>

______________________________________________________________________

## لماذا uag؟

**تحرر من تقييد البائع.** يربطك معظم مساعدي الذكاء الاصطناعي بموفر معين أو خدمة سحابية. uag مختلف.

- **يتم تشغيله محليًا** على جهازك. تبقى بياناتك معك (باستثناء API المكالمات التي تجريها).
- **حرية المزود**: OpenAI، Claude، Gemini، DeepSeek، Ollama، Azure، Bedrock، Novita، HuggingFace... 24 مقدمًا، يمكن الوصول إليهم جميعًا من واجهة واحدة. يمكنك التبديل بينها عن طريق إعادة تكوين متغيرات البيئة - بدون إعادة تثبيت أو ترحيل.
- **222 أداة**: إدخال/إخراج الملفات، بحث الويب، إنشاء الصور، Gmail، فحص جهاز BLE، MCP تكامل الخادم - **130 تم وضع علامة ثابتة عليها كآمنة متوازية** (ما يصل إلى 8 يتم تنفيذها بشكل متزامن عبر مجموعة مؤشرات الترابط، قابلة للتكوين عبر `UAGENT_PARALLEL_WORKERS`). عندما يطلق LLM استدعاءات متعددة للأداة مرة واحدة، يقوم uag بموازاتها تلقائيًا.
- **3 واجهات مستخدم + A2A**: CLI، GUI، Web، وبروتوكول وكيل إلى وكيل. نفس المحرك، بأي واجهة.
- **جاهز لإنترنت الأشياء**: SwitchBot، ECHONET Lite، Matter، UPnP — تحكم في أجهزتك المنزلية من خلال الذكاء الاصطناعي.
- **مهارات الوكيل**: قم بتثبيت المهارات المجتمعية من السوق. قم بتوسيع uag إلى ما لا نهاية.

uag هو **مساعد الذكاء الاصطناعي الخاص بك وفقًا لشروطك**. غير مرتبط بمزود خدمة، وغير مرتبط بواجهة، وغير مرتبط بمنصة.

## البدء السريع

```bash
pip install uag
uag
```

يحافظ التثبيت الأساسي على تكاملات المزوّدين والأدوات كاعتماديات اختيارية. تُثبّت الحزم الناقصة تلقائيًا عند حاجة المزوّد أو الأداة المحددة إليها. لتثبيت الميزات الرئيسية مسبقًا:

```bash
pip install "uag[core,providers,tools,development,platform,web]"
```

لتثبيت بيئة التطوير والاختبار الكاملة للمستودع:

```bash
pip install -r requirements.txt
```

عند التشغيل الأول، يرشدك معالج الإعداد خلال تكوين المزوّد.
لجميع متغيرات البيئة، راجع [https://github.com/awaku7/agentcli/blob/main/docs/ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/docs/ENVIRONMENT.md).

## Computer Use

Computer Use هو خيار الاشتراك ويدعم كلاً من وقت تشغيل المتصفح Playwright المرئي
ووقت تشغيل سطح المكتب. عند التمكين، يتم إنشاء وقتي التشغيل وتسجيلهما؛

```bat
set UAGENT_COMPUTER_USE=1
```

استخدم `سطح المكتب` لتحديد وقت تشغيل سطح مكتب نظام التشغيل بدلاً من ذلك. يتم إغلاق موارد Runtime معًا عند الخروج العادي، `Ctrl-C`، وإيقاف العملية. قم بتعيين
`UAGENT_COMPUTER_HEADLESS=1` لاختبارات CI أو الدخان المستندة إلى المتصفح.
راجع [docs/COMPUTER_USE_IMPLEMENTATION.md](docs/COMPUTER_USE_IMPLEMENTATION.md)
للحصول على تفاصيل التكامل والسلامة.

## Realtime Voice وAEC3

يدعم وضع الصوت الحقيقي OpenAI Realtime وAzure OpenAI GPT Realtime وxAI Grok Voice API وGoogle Gemini Multimodal Live API وAmazon Bedrock Nova Sonic مع ميكروفون مزدوج الاتجاه ومكبر صوت I/O. يتم تثبيت الواجهة الخلفية `pywebrtc-audio` AEC3 المطلوبة تلقائيًا، ويتم تثبيت SDK الاختياري للبث ثنائي الاتجاه من Bedrock تلقائيًا فقط عند تحديد موفر Bedrock:

```bash
python scheck.py realtime
```

يتلقى خط أنابيب AEC3 إشارة الميكروفون الفعلية (`قريب`) ويتم تسليم الصوت فعليًا إلى مكبر الصوت (`بعيد`) لذا فإن المساعد يمكن الاستماع أثناء التحدث. قم بتمكين التشخيص فقط عند التحقيق في مشكلات الصوت:

```bat
set UAGENT_REALTIME_AUDIO_DEBUG=1
python scheck.py realtime
```

### OpenAI استدعاء الوظائف في الوقت الفعلي

OpenAI يدعم الوقت الحقيقي تكامل استدعاء الوظائف المحدود الأمان. يعرض محول الوقت الفعلي الحالي `get_current_time` للقراءة فقط تلقائيًا. لا يتم الكشف عن الأدوات الضارة وعناصر التحكم في الأجهزة بدون قائمة مسموح بها وتدفق تأكيد واضح. Grok يستخدم الوقت الفعلي محولًا منفصلاً ولا يستخدم مسار استدعاء الوظيفة الخاص بـ OpenAI.

## الميزات

### 🧠 بنية متعددة الموفرين

OpenAI / PFN (PLaMo) / Azure / Bedrock / OpenRouter / Ollama / llama.cpp / Gemini / Vertex AI / Claude / Grok / NVIDIA / Novita / DeepSeek / Z.AI (Zhipu AI) / HuggingFace / Alibaba Cloud (Qwen) / KIMI (Moonshot AI) / Xiaomi MiMo / LM Studio / MiniMax / Sakana AI (Fugu) / SAKURA AI Engine / Together AI / Vercel AI Gateway

يشترك جميع مقدمي الخدمة في نفس مجموعة الأدوات والواجهة. قم بالتبديل عن طريق إعداد `UAGENT_PROVIDER` - لا توجد تغييرات في التعليمات البرمجية، ولا توجد عمليات تثبيت منفصلة.

#### Ollama وllama.cpp

Ollama وllama.cpp موفران منفصلان. تستخدم شركة Ollama خدمتها الخاصة وإدارة النماذج، بينما يتصل `llama.cpp` بنقطة نهاية متوافقة مع `llama-server` OpenAI:

```bash
# llama.cpp / llama-server
UAGENT_PROVIDER=llama_cpp
UAGENT_LLAMA_CPP_BASE_URL=http://localhost:8080/v1
UAGENT_LLAMA_CPP_DEPNAME=local-model
UAGENT_LLAMA_CPP_API_KEY=dummy
```

يستخدم موفر llama.cpp المسار المتوافق مع إكمالات الدردشة. احتفظ بـ `UAGENT_RESPONSES=0` ما لم يتم تكوين وكيل متوافق.

### ⚡التنفيذ المتوازي للأداة

عندما يطلب LLM أدوات متعددة في وقت واحد، uag **يوازنها تلقائيًا**.
يتم وضع علامة على 130 أداة بشكل ثابت `x_parallel_safe` ويتم تنفيذها بشكل متزامن عبر `ThreadPoolExecutor` (8 سلاسل المحادثات بشكل افتراضي؛ قم بتعيين `UAGENT_PARALLEL_WORKERS` للتغيير).

**مثال**: اسأل "التحقق من الطقس في عواصم بلدان الشمال الأوروبي" → LLM يطلق `search_web` × 5 دول → يتم تشغيل جميع عمليات البحث الخمسة بالتوازي ← يتم جمع النتائج في دفعة واحدة.

يعتمد العدد الحالي على وحدات الأدوات التي تحدد `TOOL_SPEC` (حاليًا 222، بما في ذلك 2 أدوات مدعومة بالصدأ في `src/uagent/tools_rust/`). يستخدم `http_request` أمانًا حساسًا للطريقة: قد يتم تشغيل مكالمات `GET`/`HEAD`/`OPTIONS` بالتوازي، بينما تظل طرق الكتابة تسلسلية.

أدوات القراءة فقط (البحث عن الملفات، وحساب التجزئة، وقائمة الدليل، والترجمة، واستعلامات قاعدة البيانات، وما إلى ذلك) متوازية بقوة.

### 🧩 نظام المكونات الإضافية (Claude كود متوافق)

uagent ينفذ **Claude نظام مكون إضافي متوافق مع الكود**. مهارات حزمة المكونات الإضافية، والوكلاء، وخوادم MCP، والخطافات، والمزيد في أدلة قائمة بذاتها مع بيان `.claude-plugin/plugin.json`.

**المكونات المدعومة**: المهارات، والوكلاء الفرعيون، وخوادم MCP، والخطافات (12 حدثًا لدورة الحياة)، وأوامر الشرطة المائلة، وأنماط الإخراج، وتكوين المستخدم، والتبعيات، والقنوات، الأسواق

**CLI الأوامر**:

```
:قائمة المكونات الإضافية المثبتة # قائمة المكونات الإضافية المثبتة
:plugin install <source> [--scope] # تثبيت (dir/zip/git/http)
:plugin install <name>@<marketplace> # التثبيت من Marketplace
:plugin Remove <name> # Uninstall
:plugin تمكين/تعطيل <name> # Toggle
:plugin marketplace add/remove/list # Managemarketplaces
:plugin init <name> # Scaffold new plugin
```

راجع [DEVELOP_PLUGIN.md](src/uagent/docs/DEVELOP_PLUGIN.md) للحصول على التوثيق الكامل.

### 🔄 الجلسة الاستمرارية

- **تبديل موفري الخدمة في منتصف الجلسة** باستخدام `UAGENT_PROVIDER` - يتم الاحتفاظ بسجل المحادثات.
- **إعادة تحميل الجلسات السابقة** باستخدام `:load <index>` - المتابعة من حيث توقفت.
- **التخزين المؤقت لنتائج الأداة** يتجنب إعادة التنفيذ المتكررة عند تكرار استدعاء الأداة نفسها.

### 🛠 229 الأدوات

| الفئة | الأدوات |
|---|---|
| **عمليات الملف** | قراءة/كتابة/إنشاء/حذف/بحث/grep/hash/zip, file_type, parse_eml (ملفات .eml), `path_alias` |
| **Web** | fetch_url, search_web, لقطة شاشة, browser_playwright, `url_alias`, `public_transit_route` ([guide](docs/PUBLIC_TRANSIT_ROUTE.md)) |
| **الإعلام** | توليد_صورة، تحليل_صورة، img2img، audio_speech، audio_transcribe |
| **الوثائق** | استخراج PDF/PPTX/DOCX/RTF/ODT، استخراج منظم لـ Excel |
| **التوقعات** | التنبؤ بالسلاسل الزمنية مع 9 نماذج (AutoARIMA، Prophet، LightGBM، CatBoost، TimesFM، إلخ)، اختيار النموذج التلقائي، إنشاء قطعة الأرض، i18n |
| **الاتصالات** | gmail_send وgmail_read وbluesky وdiscord_channel وteams_webhook و**pybitchat** (BLE Mesh) - راجع [COMMUNICATION.md](https://github.com/awaku7/agentcli/blob/main/docs/COMMUNICATION.md) و [BITCHAT.md](https://github.com/awaku7/agentcli/blob/main/docs/BITCHAT.md) |
| **إنترنت الأشياء** | SwitchBot (Cloud + BLE)، ECHONET Lite، Matter، UPnP، الرمز الجغرافي العكسي |
| **واجهات برمجة التطبيقات السحابية** | `aws_api` و`gcp_api` و`azure_api` - عمليات AWS العامة وGoogle Cloud وAzure API؛ تتطلب عمليات الكتابة تأكيدًا صريحًا |
| \*\* أدوات التطوير \*\* | Workspace_status, git_ops, git_review, Security_scan, Cover_report, python_compile, lint_format, run_tests, db_query, **29 متصفحًا لكود المصدر (عائلة idx)** |
| **MCP** | الاتصال بخوادم MCP الخارجية، وقائمة الأدوات، والتنفيذ — [دليل OAuth / الوكيل](docs/MCP_OAUTH_PROXY_GUIDE.md) |
| **A2A** | الاتصال من وكيل إلى وكيل (مع مثيلات uag الأخرى أو الخوادم المتوافقة مع A2A) |
| **النظام** | env vars، مواصفات النظام، الوقت، حساب التاريخ، [الكميات](docs/QUANTITIES.md)، [geodesic_distance](docs/GEODESIC_DISTANCE.md)، uuid_gen، slugify |
| **التنقل المصدر** | **29 أداة idx** لـ Python، PHP، TypeScript، Java، C#، Dart، C/C++، Rust، Go، Swift، Kotlin، COBOL، VBA، LotusScript، Makefile - احصل على فهرس وظيفة/فئة أو تعريف محدد دون قراءة الملف بالكامل |

#### مراجعة المستودع وتغطيته

- `workspace_status`: الإبلاغ عن مساحة العمل النشطة فرع Git والتغييرات وحالة المزامنة الأولية وPython وقت التشغيل وعلامات المشروع الشائعة دون تعديل الملفات.
- `git_review`: تلخيص تغييرات Git والملفات الخطرة ومرشحي الاختبار والنتائج السرية دون الكشف عن القيم السرية.
- `security_scan`: فحص ملفات المستودع بحثًا عن الأسرار المحتملة وملفات التكوين المحفوفة بالمخاطر.
- `coverage_report`: تشغيل التغطية وتطبيعها لـ Python، TypeScript/JavaScript وRust وGo وJava/Kotlin و.NET وC/C++ وRuby وPHP وSwift وDart/Flutter.
- يمكن تثبيت تبعيات التغطية المفقودة تلقائيًا عند طلب التنفيذ؛ لا يقوم `dry_run` بتثبيت الحزم مطلقًا.

راجع [أدوات تحليل المستودع](docs/REPOSITORY_TOOLS.md) للحصول على المعلمات والمخرجات وتفاصيل الأمان.

راجع [الأسماء المستعارة للمسار وعنوان URL](docs/PATH_URL_ALIASES.md) لتقصير مسارات الملفات وعناوين URL المتكررة في وسيطات الأداة.

### 🖥 4 واجهات + ملحق VS Code

| الوضع | الأمر | الغرض |
|---|---|---|
| **CLI** | `uag` | عملية سريعة تعتمد على المحطة |
| **GUI** | `uagg` | واجهة سطح المكتب عبر tkinter |
| **Web** | `uagw` | الوصول عبر المتصفح |
| **A2A الخادم** | `uaga` | بروتوكول Agent2Agent للاتصال متعدد الوكلاء |
| **رمز VS** | — | [ملحق](https://github.com/awaku7/agentcli/blob/main/docs/VSCODE.md) مع لوحة الدردشة والشرح وإعادة البناء وإصلاح الخطأ وعرض شجرة الأدوات |

راجع [VSCODE.md](https://github.com/awaku7/agentcli/blob/main/docs/VSCODE.md) للحصول على تفاصيل حول ملحق VS Code - التثبيت، الأوامر وربطات المفاتيح والتكوين.

### 🏠 التحكم في جهاز إنترنت الأشياء

- **BACnet**: قراءة/كتابة أجهزة BACnet/IP (HVAC، الإضاءة، عدادات الطاقة). اشتراك COV لإشعارات الدفع
- **Modbus TCP**: قراءة/كتابة سجلات وملفات الإدخال/الإدخال. مراقبة التغيير القائم على الاقتراع
- **OPC UA**: تصفح مساحة العنوان، ومتغيرات القراءة/الكتابة، والاشتراك في تغييرات البيانات
- **SwitchBot**: التحكم في الدفعة السحابية ومسح/تحكم BLE. الاشتراك القائم على الاقتراع
- **ECHONET Lite**: اكتشاف إشعارات INF من الأجهزة المنزلية والتحكم فيها والاشتراك فيها (أجهزة تكييف الهواء والأضواء وسخانات المياه وما إلى ذلك)
- **المادة**: التحكم في القراءة/الكتابة + الاشتراك في السمات لمراقبة تغيير الحالة
- **UPnP**: اكتشاف الجهاز وإعادة توجيه منفذ IGD

انظر [IOT_USECASE.md](https://github.com/awaku7/agentcli/blob/main/docs/IOT_USECASE.md)

### 🎯 Agent Skills Marketplace

`:skills mp_search` لتصفح [SkillsMP](https://skillsmp.com) و [ClawHub](https://clawhub.ai) لمهارات المجتمع.
تثبيت وتوسيع قدرات uag بسرعة.

### 🤖 الطيار الآلي (`:auto`)

uag يمكنه **متابعة الهدف بشكل مستقل عبر جولات LLM المتعددة**. مثالية للمهام المعقدة والمتعددة الخطوات التي تحتاج إلى تحسين متكرر.

- **كيفية العمل**: تحتوي كل جولة على استعلام رئيسي (الخطوة أ) متبوعًا بحكم المراجع (الخطوة ب) الذي يقرر "إكمال أو متابعة؟"
- **نفس الموفر، نفس API**: يستخدم حكم المراجع مسار التعليمات البرمجية المتطابق مثل الاستعلام الرئيسي - بما في ذلك دعم الردود API.
- **حكم منفصل LLM** (اختياري): قم بتعيين `UAGENT_AP_PROVIDER` لاستخدام موفر/نموذج مختلف للمراجع (على سبيل المثال، استخدام نموذج أرخص للتحكيم).
- **الخروج في أي وقت**: اضغط على مفتاح F11 للتوقف فورًا، حتى في منتصف الاستجابة. أو دع المراجع يقرر متى يتم تحقيق الهدف.
- **قابل للتكوين**: `--max-rounds N` للتحكم في الميزانية.

راجع [README_AUTO.md](https://github.com/awaku7/agentcli/blob/main/docs/README_AUTO.md) للحصول على التوثيق الكامل.

### 🧩 حالة الدفعة يستطيع Manager

uag تتبع التقدم عبر المهام المتعددة الملفات طويلة الأمد. عندما يقوم LLM بمعالجة العشرات من الملفات، فإن `batch_state` يحتفظ بقائمة الملفات المعلقة والمكتملة والفاشلة على القرص. إذا انتهت الجلسة أو انتهت مهلة الجولة، فسيتم استئناف التشغيل التالي من حيث توقف - لن يتم فقدان أي شيء.

### 🛡 Human-in-the-Loop

`human_ask` يتيح لـ LLM التوقف مؤقتًا وطلب تأكيدك قبل إجراء عمليات تدميرية (حذف الملف، الكتابة الفوقية، أوامر الصدفة). تبقى مسيطرًا.

### 🛑 مقاطعة (مفتاح c / زر إيقاف)

أوقف إنشاء استجابة LLM في أي وقت وأدخل أمر إيقاف مرة أخرى إلى LLM.

| الواجهة | كيفية مقاطعة |
|---|---|
| **CLI** | اضغط على مفتاح F12 أثناء بث LLM - تتوقف الاستجابة الحالية، ويتم إرسال `"Stop"` كرسالة مستخدم بحيث يستجيب LLM وفقًا لذلك |
| \*\* واجهة مستخدم الويب \*\* | انقر فوق الزر الأحمر **■ إيقاف** (يظهر تلقائيًا أثناء معالجة LLM) |
| **سطح المكتب GUI** | انقر فوق الزر الأحمر **■** (يظهر تلقائيًا أثناء معالجة LLM) |

تعمل المقاطعة كـ "إدخال سريع": بدلاً من مجرد الإجهاض، فإنها تغذي `"Stop"` مرة أخرى إلى LLM كرسالة مستخدم، مما يسمح لها بإنهاء المقاطعة أو الإقرار بها بأمان.

اضغط على مفتاح F11 للخروج من وضع الطيار الآلي (انظر [README_AUTO.md](https://github.com/awaku7/agentcli/blob/main/docs/README_AUTO.md)).

### 🕵️ أتمتة المتصفح وWeb Inspector

أداتان متكاملتان تعتمدان على Playwright:

- **browser_playwright**: أتمتة المتصفح الحقيقي الجلسات - التنقل، والنقر، وملء النماذج، واستخراج البيانات، والتعامل مع التدفقات متعددة الصفحات. يعمل بدون رأس أو برأس.
- **playwright_inspector**: تسجيل انتقالات المتصفح، والتقاط لقطات DOM ولقطات الشاشة في كل خطوة. مفيد لتصحيح أخطاء تفاعلات الويب أو تدقيق تغييرات الصفحة بمرور الوقت.

### 🔄 يتيح لك التحميل الديناميكي للأداة

`tool_catalog` و`tool_load` اكتشاف الأدوات وتمكينها في وقت التشغيل.
لا داعي لتحميل كل شيء عند بدء التشغيل - قم بتنشيط ما تحتاجه فقط، عندما تحتاج إليه.

### 🦀 Rust Native يتم تنفيذ الأدوات

`uuid_gen` و`slugify` في Rust (عبر PyO3) للأداء.
يتم تحميلها مباشرة من `.pyd` مُنشأ مسبقًا - **لا يلزم تثبيت نقطة**.

يمكن للمطورين الخارجيين أيضًا شحن الأدوات المستندة إلى Rust: ضع `.pyd` بجوار
المجمع `.py`، استخدم `load_rust_pyd()` من `uagent.tools.rust_helper`، و
يحصل المستخدمون على الأداة دون أي تبعيات إضافية. راجع
[TOOL_CREATOR_GUIDE.md](https://github.com/awaku7/agentcli/blob/main/TOOL_CREATOR_GUIDE.md).

### 🌐 i18n / L10n

日本語 / الإنجليزية / 简体中文 /繁體中文 / 한국어 / Español / Français / Русский / والمزيد.
اضبط "UAGENT_LANG" للتبديل. راجع [ADD_LOCALE.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/ADD_LOCALE.md) لإضافة لغة جديدة.

تتوفر ترجمات README هذه في [docs/README.translations.md](https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md).

### 🔒 متغيرات البيئة المشفرة

قم بتخزين API مفاتيح وأسرار في `.env.sec` - ملف `.env` مشفر file.
قم بإدارته باستخدام `uag_envsec`.

## التكوين والتفاصيل

- **متغيرات البيئة**: [docs/ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/docs/ENVIRONMENT.md)
- **معالج الإعداد**: `python -m uagent.setup_cli`
- **enved env**: `uag_envsec` — تشفير `.env` كـ `.env.sec`
- **الردود API**: اضبط `UAGENT_RESPONSES=1` لوضع الردود API (OpenAI/Azure/Bedrock/OpenRouter/Ollama/Alibaba/LM Studio/Sakana AI). تم تمكينه تلقائيًا لـ Sakana AI (Fugu).
- **مستندات المطور**: [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)
- **تدفق الأداة**: [TOOL_FLOW.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/TOOL_FLOW.md) - كيفية إرسال الأدوات إلى LLMs (قناع النوع، كتالوج_الأدوات، GPT-5.4+ أداة_بحث أصلية)
- **نصائح LLM صغيرة**: [SLM_TIPS.md](https://github.com/awaku7/agentcli/blob/main/docs/SLM_TIPS.md)

## فلسفة المشروع

uag تطمح إلى أن تكون **الذكاء الاصطناعي الخاص بك، على جهازك، وفقًا لشروطك.**

- لا توجد تبعية SaaS - تعمل محليًا
- لا يوجد قفل للموفر - قم بالتبديل في أي وقت
- لا يوجد قفل لواجهة المستخدم - CLI / GUI / Web / A2A
- لا يوجد قفل للميزات - يمتد باستخدام الأدوات و المهارات

تجربة وكيل AI مجانية، خالية من تقييد البائع.

### ✨ إنشاء أدواتك الخاصة

إن كتابة أداة جديدة لـ uag أمر بسيط - أنشئ ملف `.py` واحد باستخدام
`TOOL_SPEC` و`run_tool()`، وضعه في `UAGENT_EXTERNAL_TOOLS_DIR`، و
يتم تنفيذه على الفور متاح. بالنسبة لمطوري Rust، قم بشحن `.pyd` مُصمم مسبقًا بدون أي تبعيات إضافية للمستخدمين.

راجع [TOOL_CREATOR_GUIDE.md](https://github.com/awaku7/agentcli/blob/main/TOOL_CREATOR_GUIDE.md)
للحصول على دليل خطوة بخطوة.

## المساهمة

المساهمات مرحب بها! تقارير الأخطاء، واقتراحات الميزات، وتحسينات الوثائق، والترجمات، وطلبات السحب - كلها موضع تقدير.

- **المشكلات**: افتح مشكلة GitHub للأخطاء أو طلبات الميزات.
- **طلبات السحب**: قم بتقسيم الريبو، وإجراء التغييرات، وإرسال العلاقات العامة. راجع [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md) لإعداد التطوير وإرشاداته.
- **الترجمات**: README نرحب بالترجمات والإضافات المحلية. راجع [ADD_LOCALE.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/ADD_LOCALE.md).
- **الأدوات والمهارات**: يمكن المساهمة بالمكونات الإضافية الجديدة للأداة ومهارات الوكيل عبر السوق.

### فحوصات التطوير (قبل العلاقات العامة)

تثبيت تبعيات الاختبار فقط أولاً. يتم الاحتفاظ بها خارج قائمة التبعيات لوقت التشغيل:

```bash
python -m pip install -e ".[test]"
python -m pip install black ruff
```

قم بتشغيل نفس عمليات التحقق المستخدمة بواسطة GitHub Actions قبل الدفع:

```bash
python -m ruff check src tests
python -m black --check src tests
python scripts/tool_json_i18n_batch.pystatus
python -m pytest -q .
```

للحصول على تكرار محلي أسرع، قم بتشغيل الاختبارات المتأثرة فقط:

```bash
pytest -q الاختبارات/<affected_area>
```

فحوصات إضافية عند الاقتضاء:

```bash
python -m py_compile src/uagent/
mypy src/uagent
```

بعد التعديلات المحلية (`.po`): `python scripts/compile_locales.py` و`python scripts/po_qc_summary.py`.

Runtime السياسة (التفاصيل في [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md) §6.1): يرفع المساعدون بدلاً من `sys.exit`; يقوم مضيف الأداة بتحويل الأداة `SystemExit`/`الاستثناء` إلى سلاسل أخطاء بحيث لا يمكن لأداة واحدة إنهاء العملية. تظل عمليات الخروج السريعة عند بدء التشغيل مقصودة.

## البنية والمتغيرات التشغيلية

راجع [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) للاطلاع على العقود الدائمة التي تغطي دورة حياة A2A وسياقات I18N وتثبيت التبعية الاختيارية وسلامة الأداة وإمكانيات الموفر وحدود ثقة OAuth والأحداث المنظمة والتحقق من القبول.

## محرك سياسة المؤسسة

يتم دعم السياسات على مستوى المؤسسة للأدوات والموفرين وبيانات الاعتماد وخوادم MCP والشبكات والمهارات والمكونات الإضافية. قم بتعيين `UAGENT_POLICY_FILE` على ملف سياسة JSON/YAML؛ راجع [docs/ENTERPRISE_POLICY.md](docs/ENTERPRISE_POLICY.md) للحصول على أمثلة التكوين والأدوار والتأكيد والقوائم المسموح بها.

### Runtime الاسترداد والتنسيق

راجع [RESTART_RECOVERY.md](docs/RESTART_RECOVERY.md) / [DAG_SCHEDULER.md](docs/DAG_SCHEDULER.md) / [MULTI_AGENT_RUNTIME.md](docs/MULTI_AGENT_RUNTIME.md) للاسترداد الدائم، والتنفيذ المدرك للتبعية، والتنسيق متعدد الوكلاء، واستخدام A2A عن بعد.

راجع [DISTRIBUTED_COORDINATION.md](docs/DISTRIBUTED_COORDINATION.md) لتنسيق عقد إيجار قائد وقت التشغيل المشترك.
