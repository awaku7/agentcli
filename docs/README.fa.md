<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="720">
</p>

<h1 align="center">uag - دروازه هوش مصنوعی جهانی</h1>

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

## چرا uag؟

**از قفل شدن فروشنده رها شوید.** بیشتر دستیاران هوش مصنوعی شما را به یک ارائه دهنده یا سرویس ابری خاص می بندند. uag متفاوت است.

- **به صورت محلی** روی دستگاه شما اجرا می شود. داده های شما با شما باقی می ماند (به جز تماس های API که انجام می دهید).
- **آزادی ارائه دهنده**: OpenAI، Claude، Gemini، DeepSeek، Ollama، Azure، Bedrock، HuggingFace... بیش از 15 ارائه دهنده، همه از یک رابط در دسترس هستند. با پیکربندی مجدد متغیرهای محیط - بدون نصب مجدد، بدون مهاجرت، بین آنها تعویض کنید.
- **131 ابزار**: فایل ورودی/خروجی، جستجوی وب، تولید تصویر، Gmail، اسکن دستگاه BLE، ادغام سرور MCP — **76 ابزار به صورت موازی امن هستند** (حداکثر 8 مورد به صورت همزمان از طریق Thread Pool اجرا می شوند، قابل تنظیم از طریق `UAGENT_PARALLEL_WORKERS`). هنگامی که LLM چندین تماس ابزار را همزمان انجام می دهد، uag به طور خودکار آنها را موازی می کند.
- **3 UI + A2A**: CLI، GUI، وب و پروتکل Agent-to-Agent. همان موتور، هر رابط.
- **آماده اینترنت اشیا **: SwitchBot، ECHONET Lite، Matter، UPnP - دستگاه های خانگی خود را از طریق هوش مصنوعی کنترل کنید.
- **مهارت های عامل**: مهارت های ایجاد شده در جامعه را از بازار نصب کنید. uag را بی پایان گسترش دهید.

uag **دستیار هوش مصنوعی شما طبق شرایط شماست**. نه به یک ارائه دهنده، نه به یک رابط، نه به یک پلت فرم.

## شروع سریع

```bash
pip install uag
uag
```

در اولین راه‌اندازی، جادوگر راه‌اندازی شما را از طریق پیکربندی ارائه‌دهنده راهنمایی می‌کند.
برای همه متغیرهای محیطی به [ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md) مراجعه کنید.

## ویژگی ها

### 🧠 معماری چند ارائه دهنده

OpenAI / Azure / Bedrock / OpenRouter / Ollama / Gemini / Vertex AI / Claude / Grok / NVIDIA / DeepSeek / Z.AI (Zhipu AI) / HuggingFace / Alibaba Cloud (Qwen) / KIMI (Moonshot AI) / Xiaomi / MiMo/*AIS Studio /*L.

همه ارائه دهندگان یک مجموعه ابزار و رابط مشترک دارند. با تنظیم «UAGENT_PROVIDER» تغییر دهید — بدون تغییر کد، بدون نصب جداگانه.

### ⚡ اجرای ابزار موازی

هنگامی که LLM چندین ابزار را به طور همزمان درخواست می کند، uag **به طور خودکار آنها را موازی می کند**.
۷۶ ابزار «x_parallel_safe» علامت‌گذاری شده‌اند و به طور همزمان از طریق «ThreadPoolExecutor» اجرا می‌شوند (۸ رشته به‌طور پیش‌فرض؛ «UAGENT_PARALLEL_WORKERS» را برای تغییر تنظیم کنید).

**مثال**: "آب و هوا را در پایتخت های شمال اروپا بررسی کنید" بپرسید → LLM جستجوی_وب را فعال می کند × 5 کشور → همه 5 جستجو به صورت موازی انجام می شوند → نتایج جمع آوری شده در یک دسته.

ابزارهای فقط خواندنی (جستجوی فایل، محاسبه هش، فهرست فهرست، ترجمه، جستارهای DB و غیره) به شدت موازی می شوند.

### 🔄 تداوم جلسه

- **Switch providers mid-session** with `UAGENT_PROVIDER` — conversation history is preserved.
- **Reload past sessions** with `:load <index>` — pick up where you left off.
- **Tool result caching** avoids redundant re-execution when the same tool call repeats.

### 🛠 131 ابزار

| دسته بندی | ابزار |
|---|---|
| **عملیات فایل** | خواندن/نوشتن/ایجاد/حذف/جستجو/grep/hash/zip، parse_eml (فایل‌های eml) |
| **وب** | fetch_url، search_web، اسکرین شات، مرورگر_نمایشنامه نویس |
| **رسانه** | تولید_تصویر، تحلیل_تصویر، img2img، گفتار_صوتی، رونویسی_صوتی |
| **اسناد** | استخراج PDF/PPTX/DOCX/RTF/ODT، استخراج ساختار یافته اکسل |
| **ارتباطات** | gmail_send، gmail_read، bluesky، discord_channel، teams_webhook — به [COMMUNICATION.md](https://github.com/awaku7/agentcli/blob/main/docs/COMMUNICATION.md) مراجعه کنید |
| **اینترنت اشیا** | SwitchBot (Cloud + BLE)، ECHONET Lite، Matter، UPnP |
| **ابزارهای توسعه** | git_ops، python_compile، lint_format، run_tests، db_query، **13 پیمایش کد منبع (خانواده idx)** |
| **MCP** | اتصال به سرورهای MCP خارجی، فهرست ابزارها، اجرا |
| **A2A** | ارتباط عامل به عامل (با سایر نمونه های uag یا سرورهای سازگار با A2A) |
| **سیستم** | env vars، مشخصات سیستم، زمان، محاسبه تاریخ |
| **منبع Nav** | **13 ابزار idx** برای Python، PHP، TypeScript، Java، C#، Dart، C/C++، Rust، Go، Swift، Kotlin، COBOL — دریافت یک شاخص تابع/کلاس یا تعریف خاص بدون خواندن کل فایل |

### 🖥 4 رابط + پسوند کد VS

| حالت | فرمان | هدف |
|---|---|---|
| **CLI** | "uag" | عملکرد سریع مبتنی بر ترمینال |
| ** رابط کاربری گرافیکی ** | "uagg" | رابط کاربری دسکتاپ از طریق tkinter |
| **وب** | `uagw` | دسترسی مبتنی بر مرورگر |
| **سرور A2A** | `uaga` | پروتکل Agent2Agent برای ارتباط چند عاملی |
| ** کد VS ** | — | [افزونه](https://github.com/awaku7/agentcli/blob/main/VSCODE.md) با پنل چت، توضیح، Refactor، رفع خطا، و نمای درختی ابزارها |

[VSCODE.md](https://github.com/awaku7/agentcli/blob/main/VSCODE.md) را برای جزئیات بیشتر در مورد برنامه افزودنی VS Code - نصب، دستورات، کلیدبندی و پیکربندی ببینید.

### 🏠 کنترل دستگاه اینترنت اشیا

- **SwitchBot**: کنترل دسته ای ابری و اسکن/کنترل BLE
- **ECHONET Lite**: کشف و کنترل لوازم خانگی (AC، چراغ ها، آبگرمکن، و غیره) در شبکه محلی
- **موضوع**: بازرسی فقط خواندنی توپولوژی کنترلر/پل/دستگاه
- **UPnP**: کشف دستگاه و ارسال پورت IGD

[IOT_USECASE.md](https://github.com/awaku7/agentcli/blob/main/IOT_USECASE.md) را ببینید

### 🎯 بازار مهارت های نماینده

«:skills mp_search» برای مرور [SkillsMP](https://skillsmp.com) و [ClawHub](https://clawhub.ai) برای مهارت‌های اجتماعی.
قابلیت‌های uag را در لحظه نصب و گسترش دهید.

### 🤖 خلبان خودکار (`:auto`)

uag می تواند **به طور مستقل هدفی را در چندین دور LLM دنبال کند**. ایده آل برای کارهای پیچیده و چند مرحله ای که نیاز به اصلاح تکراری دارند.

- **چگونه کار می کند**: هر دور دارای یک پرس و جو اصلی (مرحله A) و به دنبال آن یک قضاوت بازبین (مرحله B) است که تصمیم می گیرد "کامل یا ادامه دهید؟"
- ** ارائه دهنده یکسان، همان API **: قضاوت بازبین از مسیر کد یکسان به عنوان پرس و جو اصلی استفاده می کند - از جمله پشتیبانی از API پاسخ ها.
- **قاضی جداگانه LLM** (اختیاری): «UAGENT_AP_PROVIDER» را تنظیم کنید تا از ارائه دهنده/مدل متفاوتی برای داور استفاده کند (مثلاً از مدل ارزان‌تری برای قضاوت استفاده کنید).
- **خروج در هر زمان**: کلید "x" را فشار دهید تا فورا متوقف شود، حتی در اواسط پاسخ. یا اجازه دهید داور تصمیم بگیرد که چه زمانی به هدف رسیده است.
- **قابل تنظیم**: "--max-round N" برای کنترل بودجه.

برای مستندات کامل به [README_AUTO.md](https://github.com/awaku7/agentcli/blob/main/README_AUTO.md) مراجعه کنید.

### 🧩 Batch State Manager

uag می تواند پیشرفت را در وظایف طولانی مدت چند فایلی ردیابی کند. هنگامی که LLM ده‌ها فایل را پردازش می‌کند، "batch_state" لیست فایل‌های در حال انتظار، تکمیل‌شده و ناموفق را روی دیسک باقی می‌ماند. اگر جلسه به پایان برسد یا یک دوره دور تمام شود، اجرای بعدی از جایی که متوقف شده از سر گرفته می شود - هیچ چیز از دست نمی رود.

### 🛡 انسان در حلقه

«human_ask» به LLM اجازه می دهد قبل از انجام عملیات مخرب (حذف فایل، رونویسی، دستورات پوسته) تائید شما را متوقف کند. شما در کنترل بمانید.

### 🛑 وقفه (کلید c / دکمه توقف)

تولید پاسخ LLM را در هر زمان متوقف کنید و یک دستور توقف را به LLM بازگردانید.

| رابط | نحوه قطع کردن |
|---|---|
| **CLI** | کلید «c» را در حین پخش جریانی LLM فشار دهید — پاسخ فعلی متوقف می‌شود، و «توقف»» به‌عنوان یک پیام کاربر ارسال می‌شود تا LLM مطابق با آن پاسخ دهد |
| **واسطه وب** | روی دکمه قرمز **■ Stop** کلیک کنید (به طور خودکار در طول پردازش LLM ظاهر می شود) |
| ** رابط کاربری گرافیکی دسکتاپ ** | روی دکمه قرمز **■** کلیک کنید (به طور خودکار در طول پردازش LLM ظاهر می شود) |

وقفه به‌عنوان «تزریق سریع» عمل می‌کند: به جای صرفاً سقط، «توقف» را به عنوان یک پیام کاربر به LLM برمی‌گرداند و به آن اجازه می‌دهد تا به‌خوبی وقفه را به پایان برساند یا تأیید کند.

برای خروج از حالت خلبان خودکار، کلید «x» را فشار دهید (به [README_AUTO.md](https://github.com/awaku7/agentcli/blob/main/README_AUTO.md) مراجعه کنید).

### 🕵️ اتوماسیون مرورگر و بازرس وب

دو ابزار مکمل مبتنی بر نمایشنامه نویس:

- **browser_playwright**: جلسات واقعی مرورگر را خودکار کنید - پیمایش کنید، کلیک کنید، فرم ها را پر کنید، داده ها را استخراج کنید، جریان های چند صفحه ای را مدیریت کنید. بدون سر یا سر کار می کند.
- **playwright_inspector**: انتقال مرورگر را ضبط کنید، عکس های فوری DOM و اسکرین شات ها را در هر مرحله بگیرید. برای رفع اشکال تعاملات وب یا ممیزی تغییرات صفحه در طول زمان مفید است.

### 🔄 در حال بارگذاری ابزار پویا

«کاتالوگ_ابزار» و «بار_ابزار» به شما امکان می دهند ابزارها را در زمان اجرا کشف و فعال کنید.
بدون نیاز به بارگیری همه چیز در هنگام راه‌اندازی - فقط آنچه را که نیاز دارید فعال کنید، زمانی که به آن نیاز دارید.

### 🌐 i18n / L10n

日本語 / انگلیسی / 简体中文 / 繁體中文 / 한국어 / Español / Français / Русский / و بیشتر.
«UAGENT_LANG» را برای جابجایی تنظیم کنید. برای افزودن محلی جدید به [ADD_LOCALE.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/ADD_LOCALE.md) مراجعه کنید.

ترجمه‌های این README در [docs/README.translations.md] (https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md) موجود است.

### 🔒 متغیرهای محیطی رمزگذاری شده

کلیدها و اسرار API را در «.env.sec» ذخیره کنید - یک فایل «.env» رمزگذاری شده.
مدیریت با «uag_envsec».

## پیکربندی و جزئیات

- **متغیرهای محیطی**: [ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md)
- **جادوگر راه اندازی**: `python -m uagent.setup_cli`
- ** env رمزگذاری شده **: `uag_envsec` — رمزگذاری `.env` به عنوان `.env.sec`
- **Responses API**: "UAGENT_RESPONSES=1" را برای حالت Responses API (OpenAI/Azure/Bedrock/OpenRouter/Ollama/Alibaba/LM Studio/Sakana AI) تنظیم کنید. به طور خودکار برای Sakana AI (Fugu) فعال شده است.
- **اسناد برنامه‌نویس**: [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)
- **نکات کوچک LLM**: [SLM_TIPS.md](https://github.com/awaku7/agentcli/blob/main/SLM_TIPS.md)

## فلسفه پروژه

uag آرزو دارد **هوش مصنوعی شما باشد، بر روی دستگاه شما، طبق شرایط شما.**

- بدون وابستگی SaaS - به صورت محلی اجرا می شود
- بدون قفل ارائه دهنده - در هر زمان تغییر دهید
- بدون قفل UI - CLI / GUI / Web / A2A
- بدون قفل ویژگی - با ابزارها و مهارت ها گسترش دهید

تجربه عامل هوش مصنوعی رایگان، بدون قفل شدن فروشنده.
