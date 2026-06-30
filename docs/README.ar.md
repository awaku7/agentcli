<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="720">
</p>

<h1 align="center">uag — بوابة الذكاء الاصطناعي العالمية</h1>

<p align="center">
  <b>U</b>niversal <b>A</b>I <b>G</b>ateway — بيئتك، حريتك.
</p>

<p align="center">
  عمليات الملفات / بحث الويب / إنشاء الصور وتحليلها / استخراج PDF وExcel / التحكم في إنترنت الأشياء / تكامل MCP<br>
  أكثر من 15 مزودًا / 3 واجهات مستخدم / تنفيذ الأدوات المتوازية / سوق مهارات الوكيل
</p>

<p align="center">
  <a href="https://github.com/awaku7/agentcli">GitHub</a>
  ·
  <a href="https://pypi.org/project/uag/">PyPI</a>
  ·
  <a href="README.translations.md">اقرأ هذا بلغتك</a>
</p>

---

## لماذا UAG؟

**تحرر من تقييد البائع.** يربطك معظم مساعدي الذكاء الاصطناعي بمزود معين أو خدمة سحابية. uag مختلف.

- **يعمل محليًا** على جهازك. تظل بياناتك معك (باستثناء استدعاءات واجهة برمجة التطبيقات التي تجريها).
- **حرية الموفر**: OpenAI، وClaude، وGemini، وDeepSeek، وOllama، وAzure، وBedrock... أكثر من 15 موفرًا، يمكن الوصول إليهم جميعًا من واجهة واحدة. قم بالتبديل بينهما عن طريق إعادة تكوين متغيرات البيئة - دون الحاجة إلى إعادة التثبيت أو الترحيل.
- **131 أداة**: إدخال/إخراج الملفات، وبحث الويب، وإنشاء الصور، ومسح جهاز BLE، وتكامل خادم MCP - و**76 منها تعمل بالتوازي**. عندما يطلق LLM استدعاءات أدوات متعددة مرة واحدة، يقوم uag بتنفيذها تلقائيًا عبر تجمع مؤشرات الترابط.
- **4 واجهات مستخدم + A2A**: واجهة سطر الأوامر (CLI) وواجهة المستخدم الرسومية (GUI) والويب وبروتوكول وكيل إلى وكيل. نفس المحرك، أي واجهة.
- **جاهز لإنترنت الأشياء**: SwitchBot، وECHONET Lite، وMatter، وUPnP - يمكنك التحكم في أجهزتك المنزلية من خلال الذكاء الاصطناعي.
- **مهارات الوكيل**: قم بتثبيت المهارات المجتمعية من السوق. تمديد UAG إلى ما لا نهاية.

uag هو **مساعد الذكاء الاصطناعي الخاص بك وفقًا لشروطك**. غير مرتبط بمزود، وغير مرتبط بواجهة، وغير مرتبط بمنصة.

## بداية سريعة

```bash
pip install uag
uag
```

عند التشغيل لأول مرة، يرشدك معالج الإعداد عبر تكوين الموفر.
راجع [ENVIRONMENT.md](../ENVIRONMENT.md)) للتعرف على جميع متغيرات البيئة.

## الميزات

### 🧠 بنية متعددة الموفرين

OpenAI / Azure / Bedrock / OpenRouter / Ollama / Gemini / Vertex AI / Claude / Grok / NVIDIA / DeepSeek / HuggingFace / Alibaba Cloud (Qwen) / KIMI (Moonshot AI) / Xiaomi MiMo / LM Studio / MiniMax / **Sakana AI (Fugu)**

يتشارك جميع مقدمي الخدمة في نفس مجموعة الأدوات والواجهة. قم بالتبديل عن طريق إعداد `UAGENT_PROVIDER` - لا توجد تغييرات في التعليمات البرمجية، ولا توجد عمليات تثبيت منفصلة.

### ⚡ تنفيذ الأداة الموازية

عندما يطلب LLM أدوات متعددة في وقت واحد، يقوم uag بموازاة هذه الأدوات تلقائيًا.
تم وضع علامة على 76 أداة `x_parallel_safe` ويتم تنفيذها بشكل متزامن عبر `ThreadPoolExecutor` المكون من 4 خيوط.

**مثال**: اسأل "التحقق من الطقس في عواصم بلدان الشمال الأوروبي" ← تطلق LLM `search_web` × 5 دول ← يتم تشغيل جميع عمليات البحث الخمسة بالتوازي ← يتم جمع النتائج في دفعة واحدة.

أدوات القراءة فقط (البحث عن الملفات، وحساب التجزئة، وقائمة الدليل، والترجمة، واستعلامات قاعدة البيانات، وما إلى ذلك) متوازية بقوة.

### 🔄استمرارية الجلسة

- **تبديل موفري الخدمة في منتصف الجلسة** باستخدام `UAGENT_PROVIDER` — يتم الاحتفاظ بسجل المحادثات.
- **إعادة تحميل الجلسات السابقة** باستخدام `:load <index>` — تابع من حيث توقفت.
- **التخزين المؤقت لنتائج الأداة** يتجنب إعادة التنفيذ المتكررة عند تكرار نفس استدعاء الأداة.

### 🛠 131 أداة

| الفئة | أدوات |
|---|---|
| **عمليات الملف** | قراءة/كتابة/إنشاء/حذف/بحث/grep/hash/zip |
| **الويب** | fetch_url، search_web، لقطة شاشة، browser_playwright |
| **الإعلام** | إنشاء صورة، تحليل الصورة، img2img، audio_speech، audio_transcribe |
| **الوثائق** | استخراج PDF/PPTX/DOCX/RTF/ODT، استخراج منظم لـ Excel |
| **إنترنت الأشياء** | SwitchBot (Cloud + BLE)، ECHONET Lite، Matter، UPnP |
| ** أدوات التطوير ** | git_ops، python_compile، lint_format، run_tests، db_query, **13 idx tools** |
| **الخطة التشاورية المتعددة الأطراف** | الاتصال بخوادم MCP الخارجية، وقائمة الأدوات، وتنفيذ |
| **A2A** | الاتصال من وكيل إلى وكيل (مع مثيلات UAG الأخرى أو الخوادم المتوافقة مع A2A) |
| **النظام** | env vars، مواصفات النظام، الوقت، حساب التاريخ |

### 🖥 3 واجهات + A2A + VS Code

| الوضع | الأمر | الغرض |
|---|---|---|
| ** سطر ** | `واج` | عملية سريعة تعتمد على المحطة |
| ** واجهة المستخدم الرسومية ** | `واغ` | واجهة مستخدم سطح المكتب عبر tkinter |
| **الويب** | `واجو` | الوصول عبر المتصفح |
| **خادم A2A** | `واجا` | بروتوكول Agent2Agent للاتصال متعدد الوكلاء |
| **VS Code** | — | Extension (Chat Panel, Explain, Refactor, Fix Error, Tools Tree View) — see [VSCODE.md](../VSCODE.md)) |

### 🏠 التحكم في أجهزة إنترنت الأشياء

- **SwitchBot**: التحكم في الدفعة السحابية ومسح/تحكم BLE
- **ECHONET Lite**: اكتشاف الأجهزة المنزلية والتحكم فيها (تكييف الهواء والأضواء وسخانات المياه وما إلى ذلك) على الشبكة المحلية
- **المسألة**: فحص للقراءة فقط لهيكل وحدة التحكم/الجسر/الجهاز
- **UPnP**: اكتشاف الجهاز وإعادة توجيه منفذ IGD

راجع [IOT_USECASE.md](../IOT_USECASE.md))

### 🎯 سوق مهارات الوكيل

`:skills mp_search` لتصفح [SkillsMP](https://skillsmp.com) و[ClawHub](https://clawhub.ai) للتعرف على مهارات المجتمع.
قم بتثبيت وتوسيع قدرات UAG بسرعة.

### 🤖 Auto-Pilot (`:auto`)

uag can **autonomously pursue a goal across multiple LLM rounds**. Perfect for complex, multi-step tasks that need iterative refinement.

- **How it works**: Each round has a main query (Step A) followed by a reviewer judgment (Step B) that decides "COMPLETE or CONTINUE?"
- **Same provider, same API**: The reviewer judgment uses the identical code path as the main query — including Responses API support.
- **Exit anytime**: Press `x` key to stop immediately, even mid-response. Or let the reviewer decide when the goal is met.
- **Configurable**: `--max-rounds N` to control the budget.

See [README_AUTO.md](../README_AUTO.md)) for full documentation.

### 🧩 مدير حالة الدفعة

يمكن لـ uag تتبع التقدم عبر مهام متعددة الملفات طويلة الأمد. عندما تقوم LLM بمعالجة العشرات من الملفات، فإن "batch_state" يحتفظ بقائمة الملفات المعلقة والمكتملة والفاشلة على القرص. إذا انتهت الجلسة أو انتهت مدة الجولة، فسيتم استئناف التشغيل التالي من حيث توقف - ولن يتم فقدان أي شيء.

### 🛡 الإنسان في الحلقة

يتيح `human_ask` لـ LLM التوقف مؤقتًا وطلب تأكيدك قبل تنفيذ العمليات المدمرة (حذف الملف، الكتابة الفوقية، أوامر الصدفة). يمكنك البقاء في السيطرة.

### 🛑 Interrupt (c-key / Stop button)

Stop LLM response generation at any time and inject a stop command back to the LLM.

| Interface | How to interrupt |
|---|---|
| **CLI** | Press `c` key during LLM streaming -- the current response stops, and `"Stop"` is sent as a user message so the LLM responds accordingly |
| **WEB UI** | Click the red **■ Stop** button (appears automatically during LLM processing) |
| **Desktop GUI** | Click the red **■** button (appears automatically during LLM processing) |

The interrupt works as "prompt injection": instead of just aborting, it feeds `"Stop"` back to the LLM as a user message, allowing it to gracefully conclude or acknowledge the interruption.

Press `x` key to exit auto-pilot mode (see `:auto` command).

### 🕵️ أتمتة المتصفح ومفتش الويب

أداتان متكاملتان تعتمدان على الكاتب المسرحي:

- **browser_playwright**: أتمتة جلسات المتصفح الحقيقية — التنقل، والنقر، وملء النماذج، واستخراج البيانات، والتعامل مع التدفقات المتعددة الصفحات. يعمل بدون رأس أو رأس.
- **playwright_inspector**: تسجيل انتقالات المتصفح، والتقاط لقطات DOM ولقطات الشاشة في كل خطوة. مفيد لتصحيح أخطاء تفاعلات الويب أو تدقيق تغييرات الصفحة بمرور الوقت.

### 🔄 التحميل الديناميكي للأداة

يتيح لك `tool_catalog` و`tool_load` اكتشاف الأدوات وتمكينها في وقت التشغيل.
لا داعي لتحميل كل شيء عند بدء التشغيل - قم بتنشيط ما تحتاجه فقط، عندما تحتاج إليه.

### 🌐i18n / L10n

日本語 / الإنجليزية / 简体中文 / 繁體中文 / 한국어 / Español / Français / Русский / والمزيد.
اضبط "UAGENT_LANG" للتبديل. راجع [ADD_LOCALE.md](../src/uagent/docs/ADD_LOCALE.md)) لإضافة لغة جديدة.

تتوفر ترجمات هذا الملف التمهيدي في [docs/README.translations.md](README.translations.md)).

### 🔒 متغيرات البيئة المشفرة

قم بتخزين مفاتيح وأسرار واجهة برمجة التطبيقات في ملف `.env.sec` - وهو ملف مشفر `.env`.
الإدارة باستخدام "uag_envsec".

## التكوين والتفاصيل

- **متغيرات البيئة**: [ENVIRONMENT.md](../ENVIRONMENT.md))
- **معالج الإعداد**: `python -m uagent.setup_cli`
- **env المشفر**: `uag_envsec` — تشفير `.env` كـ `.env.sec`
- **Responses API**: قم بتعيين `UAGENT_RESPONSES=1` لوضع واجهة API للاستجابات (OpenAI/Azure/Bedrock/OpenRouter/Ollama/Alibaba/LM Studio/Sakana AI)
- **مستندات المطورين**: [DEVELOP.md](../src/uagent/docs/DEVELOP.md))
- **نصائح LLM الصغيرة**: [SLM_TIPS.md](../SLM_TIPS.md))

## فلسفة المشروع

تطمح uag إلى أن تكون **الذكاء الاصطناعي الخاص بك، على جهازك، وفقًا لشروطك.**

- لا توجد تبعية SaaS - تعمل محليًا
- لا يوجد قفل للمزود - قم بالتبديل في أي وقت
- لا يوجد قفل لواجهة المستخدم — CLI / GUI / Web / A2A
- لا يوجد قفل للميزات - قم بالتوسيع باستخدام الأدوات والمهارات

تجربة وكيل AI مجانية، خالية من تقييد البائع.