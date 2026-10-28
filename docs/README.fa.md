<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="UAG — Universal AI Gateway" width="620">
</p>
<h1 align="center">UAG</h1>
<p align="center"><strong>Universal AI Gateway</strong><br>مدل‌های هوش مصنوعی شما. ابزارهای شما. محیط شما.</p>

<p align="center">
  <a href="https://github.com/awaku7/agentcli/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/awaku7/agentcli/ci.yml?style=flat-square&label=CI" alt="CI"></a>
  <a href="https://pypi.org/project/uag/"><img src="https://img.shields.io/pypi/v/uag?style=flat-square" alt="PyPI"></a>
  <a href="https://pypi.org/project/uag/"><img src="https://img.shields.io/pypi/pyversions/uag?style=flat-square" alt="Python versions"></a>
  <a href="../LICENSE"><img src="https://img.shields.io/github/license/awaku7/agentcli?style=flat-square" alt="License"></a>
  <a href="https://pepy.tech/projects/uag"><img src="https://static.pepy.tech/personalized-badge/uag?period=total&units=INTERNATIONAL_SYSTEM&left_color=grey&right_color=green&left_text=downloads" alt="Downloads"></a>
</p>
<p align="center"><a href="../README.md">English</a> · <a href="README.translations.md">زبان‌های دیگر</a></p>

---

**UAG یک محیط اجرای متن‌باز برای عامل‌های هوش مصنوعی با اولویت اجرای محلی است.** مدل زبانی انتخابی شما را به ابزارها و سامانه‌هایی که استفاده می‌کنید متصل می‌کند. با کد، فایل، مرورگر، سرویس و دستگاه از یک رابط یکپارچه کار کنید، بدون وابستگی گردش‌کار به یک ارائه‌دهندهٔ مدل.

| **مدل خود را انتخاب کنید** | **ابزارهای واقعی را متصل کنید** | **کنترل را حفظ کنید** |
| :--- | :--- | :--- |
| مدل‌های ابری و محلی مانند OpenAI، Claude، Gemini، Grok، Bedrock و Ollama | فایل، کد، وب، MCP، Agent Skills، افزونه، ابر و اینترنت اشیا | اجرای محلی، تأیید انسانی، ذخیرهٔ اطلاعات ورود و سیاست‌های قابل تنظیم |

> UAG **لایهٔ اجرای عامل‌هاست، نه ارائه‌دهندهٔ مدل**. فراخوانی مدل‌ها و سرویس‌های بیرونی به پیکربندی بستگی دارد. اولویت اجرای محلی به معنی کار کاملاً آفلاین یا ایزوله بودن پیش‌فرض همهٔ ابزارها نیست.

## شروع سریع
<!-- README-SYNC:quick-start -->

به **Python 3.11 یا جدیدتر** نیاز دارید. UAG را از [PyPI](https://pypi.org/project/uag/) نصب و خط فرمان تعاملی را اجرا کنید:

~~~bash
python -m pip install --upgrade uag
uag
~~~

در نخستین اجرا، راهنمای تنظیمات به انتخاب ارائه‌دهنده و ثبت اطلاعات احراز هویت کمک می‌کند. متغیرهای محیطی و مخزن امن اطلاعات نیز قابل استفاده‌اند. برای نصب پیشاپیش وابستگی‌های بیشتر مدل‌ها و ابزارها:

~~~bash
python -m pip install "uag[core,providers,tools]"
~~~

سپس درخواست‌های زیر را امتحان کنید:

~~~text
> چه چیزهایی در این مخزن Git تغییر کرده است؟ خطرها را خلاصه کن.
> جدیدترین مستندات این کتابخانه را پیدا کن و مراحل مهاجرت را توضیح بده.
> این فایل‌ها را بررسی کن و گزارشی کوتاه بنویس.
> :help
~~~

کاربران تازه‌کار می‌توانند راهنمای نصب Windows، شامل Git و محیط مجازی، و مرجع پیکربندی را بخوانند: [Quickstart (Windows)](QUICKSTART.md) · [Environment](ENVIRONMENT.md).

## رابط‌های کاربری
<!-- README-SYNC:interfaces -->

همهٔ روش‌های دسترسی از یک محیط اجرای عامل و یک فهرست ابزار مشترک استفاده می‌کنند.

| رابط | اجرا | کاربرد |
| :--- | :--- | :--- |
| **CLI** | `uag` | ترمینال و خودکارسازی |
| **Desktop** | `uagg` | گفت‌وگو در برنامهٔ دسکتاپ |
| **Web** | `uagw` | گفت‌وگو و اتاق در مرورگر |
| **A2A** | `uaga` | یکپارچه‌سازی میان عامل‌ها |
| **VS Code** | [راهنمای افزونه](VSCODE.md) | کار در کنار کد |

رابط‌های Desktop و Web به وابستگی‌های بیشتری نیاز دارند که در نصب اولیهٔ `uag[core,providers,tools]` نیست:

~~~bash
# Desktop GUI (PySide6 and platform integrations)
python -m pip install "uag[platform]"

# Web UI (authentication dependencies, FastAPI, and Uvicorn)
python -m pip install "uag[web]" fastapi uvicorn
~~~

سرور Web می‌تواند هنگام راه‌اندازی برای نصب FastAPI و Uvicorn تلاش کند. نصب آن‌ها از پیش، نیاز به نصب خودکار را برطرف می‌کند. جزئیات: [CLI usage](USAGE.md) · [Environment](ENVIRONMENT.md).

## با UAG چه می‌توان ساخت؟
<!-- README-SYNC:capabilities -->

| قابلیت | آنچه UAG فراهم می‌کند |
| :--- | :--- |
| **گردش‌کار مستقل از مدل** | جابه‌جایی بین ارائه‌دهندگان ابری و محلی با `UAGENT_PROVIDER` بدون بازنویسی ابزارها |
| **کد و فایل** | پیمایش مخازن، بررسی Git، تحلیل کد، آزمون، عملیات فایل و خودکارسازی مرورگر |
| **ابزارهای توسعه‌پذیر** | بیش از ۲۰۰ ابزار، کشف پویا با `tool_catalog` / `tool_load` و ابزارهای اختصاصی Python و Rust |
| **عامل‌های متصل** | MCP، A2A، افزونه‌های سازگار با Claude Code، Agent Skills و عامل‌های فرعی |
| **کارهای طولانی** | اجرای خودکار، خواندن مستقل موازی، زمان‌بندی، بازیابی و نشست‌های ماندگار |
| **فراتر از ترمینال** | سرویس‌های ابری و ارتباطی، اسناد، رسانه، صدای بلادرنگ و پروتکل‌های IoT پشتیبانی‌شده |

### یک محیط اجرا، یکپارچه‌سازی‌های گوناگون
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

**نمونه‌هایی از ارائه‌دهندگان مدل پشتیبانی‌شده** در ادامه آمده‌اند. تنظیمات اختصاصی در راهنمای محیط توضیح داده شده است.

**OpenAI · Anthropic · Gemini · Vertex AI · Azure OpenAI · Amazon Bedrock · Grok · DeepSeek · OpenRouter · Ollama · llama.cpp · LM Studio**

[ENVIRONMENT.md](ENVIRONMENT.md)

### سفارشی‌سازی با مهارت‌ها و افزونه‌ها
<!-- README-SYNC:extensions -->

UAG را بدون تغییر هسته گسترش دهید. Agent Skills را از SkillsMP یا ClawHub نصب کنید، سرورهای MCP را متصل کنید یا افزونه‌های سازگار با Claude Code شامل ابزار، مهارت، عامل و hook بارگذاری کنید.

~~~text
:skills mp_search browser automation
:plugin list
:plugin install <source>
:plugin marketplace list
~~~

ابزارهای اختصاصی می‌توانند `TOOL_SPEC` و `run_tool()` ارائه دهند؛ ابزارهای مبتنی بر Rust نیز پشتیبانی می‌شوند. راهنماها: [Tool Creator Guide](../TOOL_CREATOR_GUIDE.md) · [Plugin Development Guide](../src/uagent/docs/DEVELOP_PLUGIN.md) · [MCP OAuth / Proxy](MCP_OAUTH_PROXY_GUIDE.md).

## برای گردش‌کارهای واقعی
<!-- README-SYNC:workflows -->

### بافت و حافظه
<!-- README-SYNC:context-memory -->

نتایج حجیم ابزارها را می‌توان به‌صورت **آرتیفکت** ذخیره کرد تا بافت فعال مدل پر نشود. عامل بعداً تنها بخش موردنیاز را با `artifact_read` برمی‌گرداند. نشست‌ها به‌طور پیش‌فرض در SQLite نگهداری می‌شوند، همراه با جست‌وجوی تاریخچه و بازبینی صریح حافظه.

- [Context compression](CONTEXT_COMPRESSION.fa.md)
- [Memory](MEMORY.md)
- [Session portability](SESSION_PORTABILITY.md)

### خودکارسازی و همکاری
<!-- README-SYNC:automation -->

UAG از عملیات خواندن مستقل موازی، هماهنگی چند عامل، بازیابی نشست‌ها و اجرای خودکار برای کارهای چندمرحله‌ای پشتیبانی می‌کند. با `:auto` شروع کنید؛ **F12** پاسخ فعلی را قطع کرده و توقف حالت خودکار را درخواست می‌کند.

- [Auto-pilot](README_AUTO.md)
- [Timers and scheduled tasks](SET_TIMER.md)
- [Multi-agent runtime](MULTI_AGENT_RUNTIME.md)

### امنیت و مشاهده‌پذیری
<!-- README-SYNC:security -->

عملیات حساس ممکن است به تأیید `human_ask` نیاز داشته باشند. اطلاعات ورود را می‌توان در مدیر سیستم‌عامل یا فایل رمزگذاری‌شده نگه داشت. رابط Web از ورود OIDC و کنترل دسترسی در صورت پیکربندی پشتیبانی می‌کند. ردیابی و سنجه‌های OpenTelemetry **اختیاری** هستند.

- [Enterprise policies](ENTERPRISE_POLICY.md)
- [MXC sandbox](SANDBOX_MXC.md)
- [Remote Web / A2A MXC defaults](REMOTE_MXC_DEFAULT.md)
- [Web identity and rooms](WEB_IDENTITY_MEMORY.md)
- [OpenTelemetry design](UAG_OPENTELEMETRY_DESIGN.md)
- [Developer observability](../src/uagent/docs/DEVELOP_OBSERVABILITY.md)

این کنترل‌ها قابل تنظیم‌اند اما **تضمین نمی‌کنند** که اجرای هر ابزار در یک محیط ایزوله انجام شود. پیش از ارائهٔ UAG به کاربران یا شبکه‌های نامطمئن، راهنمای استقرار و سیاست‌ها را بخوانید.

### زبان‌ها، دستگاه‌ها و صدا
<!-- README-SYNC:languages -->

UAG برای **۳۸ تنظیم زبانی** (انگلیسی و ۳۷ ترجمه)، یکپارچه‌سازی صوتی دوطرفهٔ اختیاری و ابزارهایی برای SwitchBot، Matter، ECHONET Lite، BACnet، Modbus TCP و OPC UA منابع دارد.

- [Translations](README.translations.md)
- [IoT use cases](IOT_USECASE.md)
- [Communication tools](COMMUNICATION.md)

## مستندات
<!-- README-SYNC:documentation -->

از این راهنماها آغاز کنید و سپس جزئیات را بخوانید:

| شروع از اینجا | مطالعهٔ بیشتر |
| :--- | :--- |
| [Quickstart (Windows)](QUICKSTART.md) | [Architecture](ARCHITECTURE.md) |
| [CLI usage](USAGE.md) | [Context management](UAG_CONTEXT_MANAGEMENT_DESIGN.md) |
| [Environment and providers](ENVIRONMENT.md) | [Enterprise policy](ENTERPRISE_POLICY.md) |
| [Agent Skills and plugins](../src/uagent/docs/DEVELOP_PLUGIN.md) | [Tool flow](../src/uagent/docs/TOOL_FLOW.md) |
| [MCP and OAuth](MCP_OAUTH_PROXY_GUIDE.md) | [Computer Use](COMPUTER_USE_IMPLEMENTATION.md) |
| [VS Code extension](VSCODE.md) | [Developer guide](../src/uagent/docs/DEVELOP.md) |

مستندات کامل و زبان‌های دیگر نیز در دسترس‌اند: [Documentation](./) · [Other languages](README.translations.md).

## توسعه و مشارکت
<!-- README-SYNC:contributing -->

~~~bash
git clone https://github.com/awaku7/agentcli.git
cd agentcli
python -m pip install -e ".[core,providers,test]"
~~~

پیش از درخواست ادغام شامل تغییر **کد Python**، آزمون‌ها و بررسی‌های مرتبط را اجرا کنید:

~~~bash
python -m ruff check src tests
python -m black --check src tests
python -m pytest -q .
~~~

قوانین مشارکت و راهنمای توسعه‌دهنده در ادامه آمده‌اند. گزارش خطا، بهبود مستندات، ابزار، ترجمه و درخواست‌های ادغام هدفمند پذیرفته می‌شوند: [AGENTS.md](../AGENTS.md) · [Developer guide](../src/uagent/docs/DEVELOP.md).

## مجوز
<!-- README-SYNC:license -->

UAG تحت مجوز زیر منتشر می‌شود: [Apache License 2.0](../LICENSE).
