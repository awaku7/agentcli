<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="680">
</p>

<h1 align="center">uag</h1>

<p align="center">
  <strong>درگاه جهانی هوش مصنوعی</strong><br>
  یک عامل محلی. هر مدل. هر ابزار. محیط شما، قوانین شما.
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

**چرا uag؟**

uag یک عامل هوش مصنوعی محلی‌محور است که مدل دلخواه شما را به ابزارهایی که واقعاً استفاده می‌کنید متصل می‌کند.
این ابزار یک محیط اجرایی واحد و قابل‌گسترش برای فایل‌ها، مرورگرها، پایگاه‌های کد، ارتباطات، APIهای ابری،
دستگاه‌های IoT، سرورهای MCP و گردش‌کارهای چندعاملی در اختیار شما می‌گذارد.

- **آزادی انتخاب ارائه‌دهنده** — OpenAI، Anthropic، Gemini، Azure، Bedrock، Ollama، llama.cpp، Grok، DeepSeek و موارد دیگر.
- **اجرای محلی‌محور** — محیط اجرای عامل و اجرای ابزارها روی دستگاه شما باقی می‌ماند؛ فقط فراخوانی‌های API که خودتان انتخاب می‌کنید از آن خارج می‌شوند.
- **یک لایه ابزار** — همان ابزارها از CLI، رابط کاربری دسکتاپ، رابط وب، VS Code و A2A کار می‌کنند.
- **طراحی‌شده برای اجرای موازی** — عملیات مستقلِ فقط‌خواندنی می‌توانند هم‌زمان اجرا شوند.
- **قابل‌گسترش** — ابزارها، افزونه‌ها، Agent Skills، سرورهای MCP و ابزارهای مبتنی بر Rust را بدون تغییر هسته اضافه کنید.
- **آگاه از ایمنی** — اقدامات مخرب، اعتبارنامه‌ها، کنترل دستگاه‌ها و نوشتن در شبکه از تأیید صریح و کنترل‌های سیاستی پشتیبانی می‌کنند.

> **خلاصه:** uag صفحهٔ کنترل میان مدل‌های هوش مصنوعی شما و محیط واقعی شماست.

> **🧠 نتایج ابزار آگاه از زمینه** — نتایج بزرگ ابزار، در صورت امکان، از زمینه مدل فعال خارج نگه داشته می‌شوند. uag آن‌ها را به‌عنوان مصنوعات ذخیره می‌کند و به‌جای آن پیش‌نمایشی محدودشده با مرجع ثابت Artifact را به مدل ارسال می‌کند. این کار می‌تواند به‌طور قابل‌توجهی تعداد توکن‌های ورودی مورد نیاز برای نوبت‌های بعدی را کاهش دهد، زمانی که یک ابزار نتیجهٔ بزرگی تولید می‌کند.
> [راهنمای مفصل فشرده‌سازی زمینه](CONTEXT_COMPRESSION.fa.md)

## شروع سریع

**Python 3.11+**

```bash
python -m pip install --upgrade uag
uag
```

در اولین اجرا، جادوگر راه‌اندازی باز می‌شود. این جادوگر به پیکربندی یک ارائه‌دهنده کمک می‌کند و تنظیمات انتخاب‌شده
را در محیط محلی شما ذخیره می‌کند.

برای گروه‌های قابلیت رایج:

```bash
python -m pip install "uag[core,providers,tools]"
```

> یکپارچه‌سازی‌های پلتفرم اختیاری هستند. فقط موارد موردنیاز سیستم‌عامل خود را نصب کنید؛ به

```text
> What files changed in this repository?
> Search the web for today's AI news and summarize the top five stories.
> :help
```

[Quickstart](QUICKSTART.md) · [Environment](ENVIRONMENT.md)

## رابط‌ها

| رابط | فرمان | مناسب برای |
|---|---|---|
| **CLI** | `uag` | کار سریع با محوریت صفحه‌کلید |
| **رابط کاربری دسکتاپ** | `uagg` | تجربهٔ بومی دسکتاپ |
| **رابط وب** | `uagw` | دسترسی مبتنی بر مرورگر |
| **سرور A2A** | `uaga` | ارتباط عامل‌به‌عامل |
| **VS Code** | Extension | توضیح، بازآرایی، اصلاح و مرور ابزارها در ویرایشگر |

همهٔ رابط‌ها پیکربندی یکسان ارائه‌دهنده، رجیستری ابزار، قوانین ایمنی و داده‌های نشست را به اشتراک می‌گذارند.

~~~bash
# Desktop GUI
python -m pip install "uag[platform]"

# Web UI
python -m pip install "uag[web]" fastapi uvicorn
~~~

[Interface options](USAGE.md) · [Environment](ENVIRONMENT.md)

## چه چیزی می‌توانید بسازید

آداپتورهای ارائه‌دهنده از محیط‌های اجرایی میزبانی‌شده و محلی، ازجمله موارد زیر، پشتیبانی می‌کنند:

- خواندن، ایجاد، ویرایش، جست‌وجو، هش‌کردن، بایگانی و بررسی فایل‌ها
- بررسی تغییرات Git، جست‌وجوی اسرار، اجرای آزمون، lint، کامپایل و اندازه‌گیری پوشش کد
- پیمایش پایگاه‌های کد بزرگ Python، TypeScript، JavaScript، Go، Rust، C/C++، Java، C#، COBOL، VBA و زبان‌های دیگر
- خودکارسازی مرورگرها با Playwright، ازجمله گردش‌کارهای چندصفحه‌ای و بارگیری‌ها

- **MCP** — اتصال به سرورهای ابزار خارجی، ازجمله سرویس‌های دارای OAuth
- **A2A** — هماهنگی با عامل‌ها و سرورهای سازگار دیگر
- **Cloud** — دسترسی API به AWS، Google Cloud و Azure با تأیید برای نوشتن‌ها
- **Communication** — Gmail، Bluesky، Discord، Microsoft Teams و pybitchat
- **IoT** — SwitchBot، ECHONET Lite، Matter، BACnet، Modbus TCP، OPC UA و UPnP
- **Media** — تولید/ویرایش تصویر، رونویسی/گفتار صوتی، ثبت تصویر دوربین و QR code
- **Documents** — تحلیل PDF، PowerPoint، Word، Excel، CSV، JSON، YAML، SQL و گزارش‌ها

- **SwitchBot** — کشف ابری و BLE، وضعیت، کنترل، دسته‌بندی و اشتراک‌ها
- **ECHONET Lite** — کشف و کنترل لوازم خانگی ژاپنی، ازجمله اعلان‌های INF
- **Matter** — endpointها، clusterها، attributeها، تاریخچهٔ وضعیت، اشتراک‌ها و کنترل
- **BACnet / Modbus TCP / OPC UA** — خواندن، نوشتن، مرور و پایش سامانه‌های صنعتی و خودکارسازی ساختمان
- **UPnP** — کشف دستگاه، وضعیت WAN و مدیریت نگاشت پورت روتر

### جایگاه uag

uag در یک سو میان افراد و رابط‌ها، و در سوی دیگر میان مدل‌ها، ابزارها و سامانه‌های دنیای واقعی قرار می‌گیرد.
این ابزار گفت‌وگو را هماهنگ می‌کند، قابلیت‌ها را انتخاب می‌کند، قوانین ایمنی را اعمال می‌کند و امکان ادامه‌پذیری گردش‌کار را حفظ می‌کند.

~~~mermaid
flowchart LR
    UI["CLI · Desktop · Web · VS Code · A2A"] --> UAG["UAG agent runtime"]
    UAG --> MODELS["Hosted & local models"]
    UAG --> TOOLS["Tools & extensions"]
    UAG --> STATE["Sessions & context"]
    TOOLS --> SYSTEMS["Files · Code · Web · MCP · Cloud · IoT"]
    POLICY["Confirmation · Credentials · Policy"] -.-> UAG
~~~

### افزونه‌ها، Agent Skills و marketplaceها

uag را بدون forkکردن هسته به عاملی تخصصی تبدیل کنید:

- **افزونه‌های سازگار با Claude Code** را از یک فهرست، ZIP، مخزن Git، منبع HTTP یا marketplace نصب کنید
- مهارت‌ها، عامل‌های فرعی، سرورهای MCP، hookها، فرمان‌های slash، سبک‌های خروجی، وابستگی‌ها و channelها را بسته‌بندی کنید
- قابلیت‌های جامعه را از [SkillsMP](https://skillsmp.com) و [ClawHub](https://clawhub.ai) مرور کنید
- مهارت‌ها و ابزارهای خصوصی سازمان خود را به‌صورت محلی از طریق `UAGENT_EXTERNAL_TOOLS_DIR` اضافه کنید

```text
:skills mp_search browser automation
:plugin list
:plugin install <source>
:plugin marketplace list
```

[راهنمای توسعهٔ افزونه](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP_PLUGIN.md) را ببینید.

- **بیش از ۲۰۰ ابزار** برای فایل‌ها، وب، رسانه، اسناد، کد، ابر، ارتباطات و IoT
- **کشف و بارگذاری پویا** — برای یافتن قابلیت‌ها از `tool_catalog` و برای فعال‌کردن آن‌ها فقط هنگام نیاز از `tool_load` استفاده کنید
- **هوشمندی کد** — `code_map`، ناوبرهای `idx` مخصوص زبان، بررسی Git، اجرای آزمون، lint، کامپایل و پوشش کد
- **افزونه‌های سازگار با Claude Code** با مهارت‌ها، عامل‌ها، سرورهای MCP، hookها، فرمان‌ها و marketplaceها
- **Agent Skills** از SkillsMP و ClawHub
- **ابزارهای سفارشی Python** با `TOOL_SPEC` و `run_tool()`
- **ابزارهای مبتنی بر Rust** برای افزونه‌های بومی سبک

[Tool Creator Guide](../TOOL_CREATOR_GUIDE.md) · [MCP OAuth / Proxy Guide](MCP_OAUTH_PROXY_GUIDE.md)

## ساخته‌شده برای گردش‌کارهای واقعی

### 🧠 نتایج ابزار آگاه از زمینه

نتایج بزرگ ابزار، در صورت امکان، از زمینه مدل فعال خارج نگه داشته می‌شوند. uag آن‌ها را به‌عنوان مصنوعات ذخیره می‌کند و به‌جای آن پیش‌نمایشی محدودشده با مرجع ثابت Artifact را به مدل ارسال می‌کند. این کار می‌تواند به‌طور قابل‌توجهی تعداد توکن‌های ورودی مورد نیاز برای نوبت‌های بعدی را کاهش دهد، زمانی که یک ابزار نتیجهٔ بزرگی تولید می‌کند.

گفت‌وگوهای قبلی را با `:load <index>` ادامه دهید. نتایج ابزار را می‌توان ذخیره کرد و ارائه‌دهندگان را می‌توان
بدون بازسازی برنامه تغییر داد.

[Context compression](CONTEXT_COMPRESSION.fa.md) · [Memory](MEMORY.md) · [Session portability](SESSION_PORTABILITY.md)

### خلبان خودکار

برای کارهای چندمرحله‌ای با یک مدل بازبین اختیاری از `:auto` استفاده کنید. محدودیت دورها را با `--max-rounds N` تنظیم کنید.
برای توقف خلبان خودکار **F12** یا برای توقف پاسخ فعلی **F12** را فشار دهید.

عملیات مستقلِ فقط‌خواندنی، هر زمان که ایمن باشد، هم‌زمان اجرا می‌شوند. جست‌وجوهای وب، بررسی فایل‌ها،
تحلیل مخزن و بارهای کاری مشابه می‌توانند با یک pool کارگر قابل‌پیکربندی
(`UAGENT_PARALLEL_WORKERS`) به‌صورت موازی تکمیل شوند. عملیات نوشتن سریالی باقی می‌مانند یا به تأیید نیاز دارند.

تداوم نشست، ذخیرهٔ نتایج ابزار، وضعیت دسته‌ای، بازیابی پس از راه‌اندازی مجدد، زمان‌بندی DAG و
هماهنگ‌سازی چندعامل، کارهای پیچیده را به‌جای یک‌باره‌بودن، قابل ادامه می‌کنند.

[Auto-pilot](README_AUTO.md) · [Timers](SET_TIMER.md) · [Multi-agent runtime](MULTI_AGENT_RUNTIME.md)

### 🌍 خصوصی، چندزبانه و آگاه از سیاست

`human_ask` پیش از اقدامات حساس مکث می‌کند. حذف فایل، بازنویسی، فرمان‌های shell، کنترل دستگاه، عملیات اعتبارنامه
و نوشتن‌های شبکه می‌توانند مشمول قوانین تأیید و سیاست باشند.

به‌جای قراردادن اسرار بلندمدت در promptها، از مخزن اعتبارنامه استفاده کنید:

رابط کاربری وب شامل ورود OIDC با استفاده از Authorization Code + PKCE، توکن‌های شناسه تأیید شده، نشست‌های سمت سرور و کنترل‌های دسترسی به پروژه/اتاق است. ادعاهای گروهی تأیید شده Microsoft Entra ID می‌توانند هنگام پیکربندی، سیاست دسترسی مبتنی بر دایرکتوری را تأمین کنند. استقرارهای Windows Active Directory، OAuth و trusted-proxy می‌توانند از طریق آداپتورهای هویت تأیید شده و مشخص برای استقرار ادغام شوند؛ Windows AD به یک تأییدکننده Kerberos/Negotiate مشخص برای استقرار نیاز دارد و به طور پیش‌فرض فعال نیست.

uag شامل ردیابی و سنجه‌های OpenTelemetry است که به‌صورت اختیاری فعال می‌شوند و به ارائه‌دهنده وابسته نیستند؛ این قابلیت‌ها عملیات Agent، LLM، ابزار، Context، Memory و بازیابی را پوشش می‌دهند. قابلیت مشاهده به‌طور پیش‌فرض غیرفعال است.

محلی‌بودن در اولویت، به این معنی نیست که UAG به‌طور پیش‌فرض کاملاً آفلاین است یا اجرای همهٔ ابزارها ایزوله می‌شود. فراخوانی مدل‌ها و سرویس‌های خارجی به پیکربندی بستگی دارد.

- [Enterprise policies](ENTERPRISE_POLICY.md)
- [MXC sandbox](SANDBOX_MXC.md)
- [Remote Web / A2A](REMOTE_MXC_DEFAULT.md)
- [Web identity](WEB_IDENTITY_MEMORY.md)
- [OpenTelemetry](UAG_OPENTELEMETRY_DESIGN.md)

### 🌍 ترجمه چندزبانه

- `translate_text` از Google Translate و کلاینت رسمی Python دیپ‌ال از طریق `provider=auto`، `provider=deepl`، یا `provider=google` پشتیبانی می‌کند.
- تعاریف ابزارها در ۳۷ لوکال به‌علاوهٔ انگلیسی (در مجموع ۳۸) در دسترس هستند، با نگه‌داشتن جای‌گرها و شناسه‌های فنی.

صدای تمام‌دوطرفه از طریق OpenAI Realtime، Azure OpenAI، xAI Grok Voice، Gemini Live و Bedrock Nova Sonic
در دسترس است و حذف پژواک AEC3 اختیاری و فراخوانی تابع بی‌درنگ با محدودیت‌های ایمنی را ارائه می‌کند.

[Translations](README.translations.md) · [IoT](IOT_USECASE.md) · [Communication](COMMUNICATION.md)

## مستندات

| موضوع | مستندات |
|---|---|
| متغیرهای محیطی | [docs/ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/docs/ENVIRONMENT.md) |
| معماری و ناوردایی‌ها | [docs/ARCHITECTURE.md](https://github.com/awaku7/agentcli/blob/main/docs/ARCHITECTURE.md) |
| Computer Use | [docs/COMPUTER_USE_IMPLEMENTATION.md](https://github.com/awaku7/agentcli/blob/main/docs/COMPUTER_USE_IMPLEMENTATION.md) |
| ابزارهای مخزن | [docs/REPOSITORY_TOOLS.md](https://github.com/awaku7/agentcli/blob/main/docs/REPOSITORY_TOOLS.md) |
| موارد کاربرد IoT | [docs/IOT_USECASE.md](https://github.com/awaku7/agentcli/blob/main/docs/IOT_USECASE.md) |
| ابزارهای ارتباطی | [docs/COMMUNICATION.md](https://github.com/awaku7/agentcli/blob/main/docs/COMMUNICATION.md) |
| خلبان خودکار | [docs/README_AUTO.md](https://github.com/awaku7/agentcli/blob/main/docs/README_AUTO.md) |
| OAuth / Proxy مربوط به MCP | [docs/MCP_OAUTH_PROXY_GUIDE.md](https://github.com/awaku7/agentcli/blob/main/docs/MCP_OAUTH_PROXY_GUIDE.md) |
| افزونهٔ VS Code | [docs/VSCODE.md](https://github.com/awaku7/agentcli/blob/main/docs/VSCODE.md) |
| راهنمای توسعه‌دهنده | [src/uagent/docs/DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md) |
| جریان ابزار | [src/uagent/docs/TOOL_FLOW.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/TOOL_FLOW.md) |

[Quickstart](QUICKSTART.md) · [Architecture](ARCHITECTURE.md) · [Context management](UAG_CONTEXT_MANAGEMENT_DESIGN.md)

## توسعه و مشارکت

```bash
git clone https://github.com/awaku7/agentcli.git
cd agentcli
python -m pip install -e ".[core,providers,test]"
```

بررسی‌های پیش از PR را اجرا کنید:

```bash
python -m ruff check src tests
python -m black --check src tests
python -m pytest -q .
```

برای گردش‌کار کامل توسعه، [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md) را ببینید.

گزارش اشکال، ایده‌های قابلیت، بهبود مستندات، ترجمه‌ها، ابزارها، مهارت‌ها و pull requestها پذیرفته می‌شوند.
پیش از تغییرات بزرگ، یک issue یا discussion باز کنید. [راهنمای توسعه‌دهنده](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md) را بخوانید
و پیش از ارسال pull request، بررسی‌های بالا را اجرا کنید.

## مجوز

این پروژه تحت [Apache License 2.0](https://github.com/awaku7/agentcli/blob/main/LICENSE) منتشر می‌شود.
