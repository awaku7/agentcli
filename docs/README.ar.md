<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="720">
</p>

<h1 align="center">uag - بوابة الذكاء الاصطناعي العالمية</h1>

<p align="center">
  <b>U</b>niversal <b>A</b>I <b>G</b>ateway — Your environment, your freedom.
</p>

<p align="center">
  File ops / Web search / Image generation &amp; analysis / PDF &amp; Excel extraction / IoT control / MCP integration<br>
  15+ providers / 3 UIs / Parallel tool execution / Agent Skills marketplace
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
- **حرية المزود**: OpenAI، وClaude، وGemini، وDeepSeek، وOllama، وAzure، وBedrock، وHuggingFace... أكثر من 15 مقدمًا، يمكن الوصول إليهم جميعًا من واجهة واحدة. قم بالتبديل بينهما عن طريق إعادة تكوين متغيرات البيئة - دون الحاجة إلى إعادة التثبيت أو الترحيل.
- **131 أداة**: إدخال/إخراج الملفات، وبحث الويب، وإنشاء الصور، وGmail، ومسح جهاز BLE، وتكامل خادم MCP - **76 أداة آمنة بالتوازي** (يتم تنفيذ ما يصل إلى 8 أدوات بشكل متزامن عبر مجموعة مؤشرات الترابط، ويمكن تكوينها عبر `UAGENT_PARALLEL_WORKERS`). عندما يطلق LLM استدعاءات متعددة للأدوات مرة واحدة، يقوم uag بموازاة هذه الاستدعاءات تلقائيًا.
- **3 واجهات مستخدم + A2A**: واجهة سطر الأوامر (CLI) وواجهة المستخدم الرسومية (GUI) والويب وبروتوكول وكيل إلى وكيل. نفس المحرك، أي واجهة.
- **جاهز لإنترنت الأشياء**: SwitchBot، وECHONET Lite، وMatter، وUPnP - يمكنك التحكم في أجهزتك المنزلية من خلال الذكاء الاصطناعي.
- **مهارات الوكيل**: قم بتثبيت المهارات المجتمعية من السوق. تمديد UAG إلى ما لا نهاية.

uag هو **مساعد الذكاء الاصطناعي الخاص بك وفقًا لشروطك**. غير مرتبط بمزود، وغير مرتبط بواجهة، وغير مرتبط بمنصة.

## بداية سريعة

```bash
pip install uag
uag
```

عند التشغيل لأول مرة، يرشدك معالج الإعداد عبر تكوين الموفر.
راجع [ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md) للتعرف على جميع متغيرات البيئة.

## سمات

### 🧠 بنية متعددة الموفرين

OpenAI / Azure / Bedrock / OpenRouter / Ollama / Gemini / Vertex AI / Claude / Grok / NVIDIA / DeepSeek / Z.AI (Zhipu AI) / HuggingFace / Alibaba Cloud (Qwen) / KIMI (Moonshot AI) / Xiaomi MiMo / LM Studio / MiniMax / **Sakana AI (Fugu)**

يتشارك جميع مقدمي الخدمة في نفس مجموعة الأدوات والواجهة. قم بالتبديل عن طريق إعداد `UAGENT_PROVIDER` - لا توجد تغييرات في التعليمات البرمجية، ولا توجد عمليات تثبيت منفصلة.

### ⚡ تنفيذ الأداة الموازية

عندما يطلب LLM أدوات متعددة في وقت واحد، يقوم uag بموازاة هذه الأدوات تلقائيًا.
تم وضع علامة على 76 أداة `x_parallel_safe` ويتم تنفيذها بشكل متزامن عبر `ThreadPoolExecutor` (8 سلاسل بشكل افتراضي؛ قم بتعيين `UAGENT_PARALLEL_WORKERS` للتغيير).

**مثال**: اسأل "التحقق من الطقس في عواصم بلدان الشمال الأوروبي" ← تطلق LLM `search_web` × 5 دول ← يتم تشغيل جميع عمليات البحث الخمسة بالتوازي ← يتم جمع النتائج في دفعة واحدة.

أدوات القراءة فقط (البحث عن الملفات، وحساب التجزئة، وقائمة الدليل، والترجمة، واستعلامات قاعدة البيانات، وما إلى ذلك) متوازية بقوة.

### 🔄استمرارية الجلسة

- **Switch providers mid-session** with `UAGENT_PROVIDER` — conversation history is preserved.
- **Reload past sessions** with `:load <index>` — pick up where you left off.
- **Tool result caching** avoids redundant re-execution when the same tool call repeats.

### 🛠 131 أداة

| الفئة | أدوات |
|---|---|
| **عمليات الملف** | قراءة/كتابة/إنشاء/حذف/بحث/grep/hash/zip, parse_eml (ملفات .eml) |
| **الويب** | fetch_url، search_web، لقطة شاشة، browser_playwright |
| **الإعلام** | إنشاء صورة، تحليل الصورة، img2img، audio_speech، audio_transcribe |
| **الوثائق** | استخراج PDF/PPTX/DOCX/RTF/ODT، استخراج منظم لـ Excel |
| **الاتصالات** | gmail_send، gmail_read، bluesky، discord_channel، Teams_webhook — راجع [COMMUNICATION.md](https://github.com/awaku7/agentcli/blob/main/docs/COMMUNICATION.md) |
| **إنترنت الأشياء** | SwitchBot (Cloud + BLE)، ECHONET Lite، Matter، UPnP |
| ** أدوات التطوير ** | git_ops، python_compile، lint_format، run_tests، db_query، ** 13 متصفحًا لكود المصدر (عائلة idx) ** |
| **الخطة التشاورية المتعددة الأطراف** | الاتصال بخوادم MCP الخارجية، وقائمة الأدوات، وتنفيذ |
| **A2A** | الاتصال من وكيل إلى وكيل (مع مثيلات UAG الأخرى أو الخوادم المتوافقة مع A2A) |
| **النظام** | env vars، مواصفات النظام، الوقت، حساب التاريخ |
| **التنقل المصدر** | **13 أداة idx** لـ Python وPHP وTypeScript وJava وC# وDart وC/C++ وRust وGo وSwift وKotlin وCOBOL - احصل على فهرس وظيفة/فئة أو تعريف محدد دون قراءة الملف بأكمله |

### 🖥 4 واجهات + ملحق VS Code

| الوضع | الأمر | الغرض |
|---|---|---|
| ** سطر ** | `واج` | عملية سريعة تعتمد على المحطة |
| ** واجهة المستخدم الرسومية ** | `واغ` | واجهة مستخدم سطح المكتب عبر tkinter |
| **الويب** | `واجو` | الوصول عبر المتصفح |
| **خادم A2A** | `واجا` | بروتوكول Agent2Agent للاتصال متعدد الوكلاء |
| **رمز VS** | — | [ملحق](https://github.com/awaku7/agentcli/blob/main/VSCODE.md) مع لوحة الدردشة والشرح وإعادة البناء وإصلاح الخطأ وعرض شجرة الأدوات |

راجع [VSCODE.md](https://github.com/awaku7/agentcli/blob/main/VSCODE.md) للحصول على تفاصيل حول ملحق VS Code - التثبيت والأوامر وارتباطات المفاتيح والتكوين.

### 🏠 التحكم في أجهزة إنترنت الأشياء

- **SwitchBot**: التحكم في الدفعة السحابية ومسح/تحكم BLE
- **ECHONET Lite**: اكتشاف الأجهزة المنزلية والتحكم فيها (تكييف الهواء والأضواء وسخانات المياه وما إلى ذلك) على الشبكة المحلية
- **المسألة**: فحص للقراءة فقط لهيكل وحدة التحكم/الجسر/الجهاز
- **UPnP**: اكتشاف الجهاز وإعادة توجيه منفذ IGD

راجع [IOT_USECASE.md](https://github.com/awaku7/agentcli/blob/main/IOT_USECASE.md)

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

راجع [README_AUTO.md](https://github.com/awaku7/agentcli/blob/main/README_AUTO.md) للحصول على الوثائق الكاملة.

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

اضغط على المفتاح "x" للخروج من وضع الطيار التلقائي (راجع [README_AUTO.md](https://github.com/awaku7/agentcli/blob/main/README_AUTO.md)).

### 🕵️ أتمتة المتصفح ومفتش الويب

أداتان متكاملتان تعتمدان على الكاتب المسرحي:

- **browser_playwright**: أتمتة جلسات المتصفح الحقيقية — التنقل، والنقر، وملء النماذج، واستخراج البيانات، والتعامل مع التدفقات المتعددة الصفحات. يعمل بدون رأس أو رأس.
- **playwright_inspector**: تسجيل انتقالات المتصفح، والتقاط لقطات DOM ولقطات الشاشة في كل خطوة. مفيد لتصحيح أخطاء تفاعلات الويب أو تدقيق تغييرات الصفحة بمرور الوقت.

### 🔄 التحميل الديناميكي للأداة

يتيح لك `tool_catalog` و`tool_load` اكتشاف الأدوات وتمكينها في وقت التشغيل.
لا داعي لتحميل كل شيء عند بدء التشغيل - قم بتنشيط ما تحتاجه فقط، عندما تحتاج إليه.

### 🌐i18n / L10n

日本語 / الإنجليزية / 简体中文 / 繁體中文 / 한국어 / Español / Français / Русский / والمزيد.
اضبط "UAGENT_LANG" للتبديل. راجع [ADD_LOCALE.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/ADD_LOCALE.md) لإضافة لغة جديدة.

تتوفر ترجمات هذا الملف التمهيدي في [docs/README.translations.md](https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md).

### 🔒 متغيرات البيئة المشفرة

قم بتخزين مفاتيح وأسرار واجهة برمجة التطبيقات في ملف `.env.sec` - وهو ملف مشفر `.env`.
الإدارة باستخدام "uag_envsec".

## التكوين والتفاصيل

- **متغيرات البيئة**: [ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md)
- **معالج الإعداد**: `python -m uagent.setup_cli`
- **env المشفر**: `uag_envsec` — تشفير `.env` كـ `.env.sec`
- **Responses API**: قم بتعيين `UAGENT_RESPONSES=1` لوضع واجهة برمجة التطبيقات للاستجابات (OpenAI/Azure/Bedrock/OpenRouter/Ollama/Alibaba/LM Studio/Sakana AI). تم تمكينه تلقائيًا لـ Sakana AI (Fugu).
- **مستندات المطورين**: [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)
- **نصائح LLM الصغيرة**: [SLM_TIPS.md](https://github.com/awaku7/agentcli/blob/main/SLM_TIPS.md)

## فلسفة المشروع

تطمح uag إلى أن تكون **الذكاء الاصطناعي الخاص بك، على جهازك، وفقًا لشروطك.**

- لا توجد تبعية SaaS - تعمل محليًا
- لا يوجد قفل للمزود - قم بالتبديل في أي وقت
- لا يوجد قفل لواجهة المستخدم — CLI / GUI / Web / A2A
- لا يوجد قفل للميزات - قم بالتوسيع باستخدام الأدوات والمهارات

تجربة وكيل AI مجانية، خالية من تقييد البائع.
