<p align="center">
 <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="720">
</p>
_ign = PH_4-al"> دروازه</h1>

<p align="center">
 <b>U</b> جهانی <b>A</b>I <b>G</b>ateway — محیط شما، آزادی شما. ادغام<br>
 24 ارائه دهنده / 3 رابط کاربری / اجرای موازی ابزار / بازار مهارت های عامل
</p>

<p align="center">
 <a href="https://github.com/awaku7/agentcli">GitHub</a> <a ·
 href="https://pypi.org/project/uag/">PyPI</a>
 ·
 <a href="https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md">Read this in your language</a>
___________________________________________## چرا uag؟

**از قفل شدن فروشنده رها شوید.** اکثر دستیاران هوش مصنوعی شما را به یک ارائه دهنده یا سرویس ابری خاص گره می زنند. uag متفاوت است.

- **به صورت محلی** روی دستگاه شما اجرا می شود. داده‌های شما با شما باقی می‌ماند (به جز API تماسی که برقرار می‌کنید).
- **آزادی ارائه‌دهنده**: OpenAI، Claude، Gemini، DeepSeek، Ollama، Azure، Bedrock، Novita، HuggingFace... ۲۴ ارائه‌دهنده، همه از طریق یک رابط قابل دسترسی هستند. با پیکربندی مجدد متغیرهای محیط، آنها را تعویض کنید - بدون نصب مجدد، بدون انتقال.
- **222 ابزار**: فایل ورودی/خروجی، جستجوی وب، تولید تصویر، Gmail، اسکن دستگاه BLE، ادغام سرور MCP — **130 به صورت ایستا به صورت موازی-ایمن علامت گذاری شده اند** (حداکثر تا 8 قابلیت تنظیم و پیکربندی قابل تنظیم، با قابلیت تنظیم سریع «UAGENT_PARALLEL_WORKERS»). هنگامی که LLM چندین تماس ابزار را همزمان انجام می دهد، uag به طور خودکار آنها را موازی می کند.
- \*\* 3 رابط کاربری + A2A\*\*: CLI، GUI، Web، و پروتکل Agent-to-Agent. موتور مشابه، هر رابطی.
- **آماده اینترنت اشیا**: SwitchBot، ECHONET Lite، Matter، UPnP — دستگاه های خانگی خود را از طریق هوش مصنوعی کنترل کنید.
- **مهارت های عامل**: مهارت های ساخته شده توسط جامعه را از بازار نصب کنید. uag را بی نهایت گسترش دهید.

uag **دستیار هوش مصنوعی شما طبق شرایط شماست**. نه به یک ارائه دهنده، نه به یک رابط، نه به یک پلت فرم.

## شروع سریع

```bash
نصب پیپ uag
uag
```

در اولین راه‌اندازی، جادوگر راه‌اندازی شما را از طریق پیکربندی ارائه‌دهنده راهنمایی می‌کند.
به آن مراجعه کنید. [docs/ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/docs/ENVIRONMENT.md) برای همه متغیرهای محیطی.

## Computer Use

Computer Use انتخاب شده است و هم از زمان اجرا Playwright مرورگر قابل مشاهده و هم از زمان اجرا دسکتاپ پشتیبانی می کند. وقتی فعال باشد، هر دو زمان اجرا ایجاد و ثبت می‌شوند؛

````bat در عوض Runtime منبع
در خروجی معمولی، «Ctrl-C» و خاموش شدن فرآیند با هم بسته می‌شوند. برای تست‌های CI یا دود مبتنی بر مرورگر تنظیم کنید
`UAGENT_COMPUTER_HEADLESS=1`.## Realtime Voice و AEC3

حالت صدای بیدرنگ از OpenAI Realtime، Azure OpenAI GPT Realtime، xAI Grok Voice API، Google Gemini Multimodal Live API، و Amazon Bedrock Full-Up Nova S/Lexs و آمازون Bedrock Nova S/Alex پشتیبانی می کند. پشتیبان AEC3 «pywebrtc-audio» مورد نیاز به‌طور خودکار نصب می‌شود، و SDK پخش جریانی دوطرفه اختیاری Bedrock به‌طور خودکار تنها زمانی نصب می‌شود که ارائه‌دهنده Bedrock انتخاب شده باشد:

```bash
python scheck.py بلادرنگ
````

به گوینده («دور») تا دستیار بتواند در حین صحبت گوش کند. فقط هنگام بررسی مشکلات صوتی، عیب‌یابی را فعال کنید: آداپتور بیدرنگ فعلی «get_current_time» فقط خواندنی را به‌طور خودکار نمایش می‌دهد. ابزارهای مخرب و کنترل‌های دستگاه بدون فهرست مجاز صریح و جریان تأیید آشکار نمی‌شوند. Grok بلادرنگ از یک آداپتور جداگانه استفاده می کند و از این مسیر فراخوانی تابع خاص OpenAI استفاده نمی کند.

## امکانات Z.AI (Zhipu AI) / HuggingFace / Alibaba Cloud (Qwen) / KIMI (Moonshot AI) / Xiaomi MiMo / LM Studio / MiniMax / Sakana AI (Fugu) / SAKURA AI Engine / Together AI / Vercel AI Gateway

همه ابزارهای رابط را به اشتراک می گذارند. با تنظیم «UAGENT_PROVIDER» تغییر دهید — بدون تغییر کد، بدون نصب جداگانه.

#### Ollama و llama.cpp

Ollama و llama.cpp ارائه دهندگان جداگانه هستند. Ollama از سرویس و مدیریت مدل خود استفاده می کند، در حالی که `llama.cpp` به یک "llama-server" OpenAI-compatible endpoint متصل می شود:

```bash
# llama.cpp / llama-server
UAGENT_PROVIDER=llama_cpp
UAGENT_LLAMA_CPP_BASE_URL=http://localhost:8080/v1
UAGENT_LLAMA_CPP_DEPNAME=local-model
UAGENT_LLAMA_CPP_API_KEY=dummy
```

: لیست پلاگین # فهرست پلاگین های نصب شده marketplace
:plugin remove <name> # Uninstall
:plugin enable/disable <name> # Toggle
:plugin marketplace add/remove/list # Manage marketplaces
:plugin init <name> # Scaffold new plugin

```

نگاه کنید برای مستندات کامل [DEVELOP_PLUGIN.md](src/uagent/docs/DEVELOP_PLUGIN.md) `:load <index>` — از جایی که کار را متوقف کردید ادامه دهید.
- ** ذخیره سازی نتایج ابزار** از اجرای مجدد اضافی در صورت تکرار همان فراخوانی ابزار جلوگیری می کند.

### 🛠 229 ابزار

| دسته بندی | ابزار |
|---|---|
| **عملیات فایل** | خواندن/نوشتن/ایجاد/حذف/جستجو/grep/hash/zip، file_type، parse_eml (فایل‌های eml)، `path_alias` |
| **Web** | fetch_url، search_web، اسکرین شات، مرورگر_نمایشنامه‌نویس، «url_alias»، «راهنمای_حمل‌ونقل عمومی» ([راهنما](docs/PUBLIC_TRANSIT_ROUTE.md)) |
| **رسانه** | ایجاد_تصویر، تحلیل_تصویر، img2img، audio_speech، audio_transcribe |
| **اسناد** | استخراج PDF/PPTX/DOCX/RTF/ODT، استخراج ساختار یافته اکسل |
| **پیش بینی** | پیش بینی سری زمانی با 9 مدل (AutoARIMA، Prophet، LightGBM، CatBoost، TimesFM، و غیره)، انتخاب مدل خودکار، تولید طرح، i18n |
| **ارتباطات** | gmail_send، gmail_read، bluesky، discord_channel، teams_webhook، **pybitchat** (BLE Mesh) — به [COMMUNICATION.md](https://github.com/awaku7/agentcli/blob/main/docs/COMMUNICATION.md) و [BITCHAT.md](https://github.com/awaku7/agentcli/blob/main/docs/BITCHAT.md) |
| **اینترنت اشیا** | SwitchBot (Cloud + BLE)، ECHONET Lite، Matter، UPnP، reverse_geocode |
| **APIهای ابری** | «aws_api»، «gcp_api»، «azure_api» — عملیات عمومی AWS، Google Cloud، و Azure API؛ عملیات نوشتن نیاز به تأیید صریح دارد |
| **ابزارهای توسعه** | workspace_status، git_ops، git_review، security_scan، coverage_report، python_compile، lint_format، run_tests، db_query، **29 ناوبر کد منبع (خانواده idx)** |
| **MCP** | اتصال به سرورهای خارجی MCP، فهرست ابزارها، اجرا — [OAuth / راهنمای پروکسی](docs/MCP_OAUTH_PROXY_GUIDE.md) |
| **A2A** | ارتباط عامل به نماینده (با سایر نمونه های uag یا سرورهای سازگار با A2A) |
| **سیستم** | env vars، مشخصات سیستم، زمان، محاسبه تاریخ، [تعداد](docs/QUANTITIES.md)، [geodesic_distance](docs/GEODESIC_DISTANCE.md)، uuid_gen، slugify |
| **منبع Nav** | **29 ابزار idx** برای Python، PHP، TypeScript، جاوا، C#، Dart، C/C++، Rust، Go، Swift، Kotlin، COBOL، VBA، LotusScript، Makefile — یک نمایه تابع/کلاس یا تعریف خاص بدون خواندن کل فایل دریافت کنید | "وضعیت_فضای_کار": گزارش شاخه Git فضای کاری فعال، تغییرات، وضعیت همگام سازی بالادست، زمان اجرا Python و نشانگرهای معمول پروژه بدون تغییر فایل ها. فایل. «dry_run» هرگز بسته‌ها را نصب نمی‌کند. آرگومان ها.

### 🖥 4 رابط + افزونه کد VS

| حالت | فرمان | هدف |
|---|---|---|
| **CLI** | `uag` | عملکرد سریع مبتنی بر ترمینال |
| **GUI** | "uagg" | رابط کاربری دسکتاپ از طریق tkinter |
| **Web** | `uagw` | دسترسی مبتنی بر مرورگر |
| **A2A سرور ** | `uaga` | پروتکل Agent2Agent برای ارتباط چند عامله |
| ** کد VS ** | — | [افزونه](https://github.com/awaku7/agentcli/blob/main/docs/VSCODE.md) با پنل چت، توضیح، Refactor، رفع خطا، و نمای درخت ابزارها |

مشاهده کنید [VSCODE.md](https://github.com/awaku7/agentcli/blob/main/docs/VSCODE.md) برای جزئیات بیشتر در مورد برنامه افزودنی VS Code — نصب، دستورات، ترکیب کلید، و پیکربندی. (تهویه مطبوع، روشنایی، کنتور برق). اشتراک COV برای اعلان‌های فشاری
- **Modbus TCP**: رجیسترها و سیم‌پیچ‌های نگهداری/ورودی خواندن/نوشتن. نظارت بر تغییرات مبتنی بر نظرسنجی
- **OPC UA**: فضای آدرس را مرور کنید، متغیرهای خواندن/نوشتن، اشتراک در تغییرات داده‌ها
- **SwitchBot**: کنترل دسته‌ای Cloud و اسکن/کنترل BLE. اشتراک مبتنی بر نظرسنجی
- **ECHONET Lite**: کشف، کنترل و اشتراک در اعلان‌های INF از لوازم خانگی (AC، چراغ‌ها، آبگرمکن‌ها و غیره)
- **موضوع**: کنترل خواندن/نوشتن + اشتراک ویژگی برای نظارت بر تغییر وضعیت
- **UPnP***: کشف درگاه و IGD [IOT_USECASE.md](https://github.com/awaku7/agentcli/blob/main/docs/IOT_USECASE.md)

### 🎯 Agent Skills Marketplace

`:skills mp_search` برای مرور MPsll(http.com://skills) [ClawHub](https://clawhub.ai) برای مهارت‌های اجتماعی. 
 قابلیت‌های uag را در حین پرواز نصب و گسترش دهید. ایده آل برای کارهای پیچیده و چند مرحله ای که نیاز به پالایش تکراری دارند.

- **نحوه کار**: هر دور دارای یک جستار اصلی (مرحله A) و به دنبال آن یک قضاوت بازبین (مرحله B) است که تصمیم می گیرد "کامل شود یا ادامه دهید؟"
- **همان ارائه دهنده، همان مسیر کد اصلی بازبینی کننده، همان مسیر کد اصلی *gAPI استفاده می کند. — از جمله پاسخ‌های API پشتیبانی. یا به بازبین اجازه دهید تصمیم بگیرد چه زمانی به هدف رسید.
- **قابل تنظیم**: «--max-rounds N» برای کنترل بودجه. 🧩 Batch State Manager

uag می‌تواند پیشرفت را در کارهای طولانی مدت چند فایلی ردیابی کند. هنگامی که LLM ده‌ها فایل را پردازش می‌کند، «batch_state» فهرست فایل‌های در حال انتظار، تکمیل‌شده و ناموفق را روی دیسک باقی می‌ماند. اگر جلسه به پایان برسد یا یک دور تمام شود، اجرای بعدی از جایی که متوقف شده از سر گرفته می‌شود - هیچ چیز گم نمی‌شود. شما در کنترل خود باقی می‌مانید.

### 🛑 وقفه (کلید c / دکمه توقف)

تولید پاسخ LLM را در هر زمان متوقف کنید و یک فرمان توقف را به LLM تزریق کنید.

| رابط | نحوه قطع کردن |
|---|---|
| **CLI** | کلید «c» را در حین پخش جریانی LLM فشار دهید — پاسخ فعلی متوقف می‌شود و «توقف»» به‌عنوان یک پیام کاربر ارسال می‌شود، بنابراین LLM پاسخ می‌دهد |
| **واسطه وب** | روی دکمه قرمز **■ Stop** کلیک کنید (به طور خودکار در حین پردازش LLM ظاهر می شود) |
| **رومیزی GUI** | روی دکمه قرمز **■** کلیک کنید (به طور خودکار در طول پردازش LLM ظاهر می‌شود) |

وقفه به‌عنوان "تزریق سریع" عمل می‌کند: به جای صرفاً سقط، "توقف" را به عنوان پیام کاربر به LLM برمی‌گرداند و به آن اجازه می‌دهد تا به‌خوبی وقفه را به‌خوبی نتیجه‌گیری کند یا وقفه را تأیید کند. (به [README_AUTO.md](https://github.com/awaku7/agentcli/blob/main/docs/README_AUTO.md) مراجعه کنید).

### 🕵️ اتوماسیون مرورگر و Web بازرس

دو ابزار مکمل:PH_ **browser_playwright**: جلسات واقعی مرورگر را خودکار کنید - پیمایش، کلیک کنید، فرم ها را پر کنید، داده ها را استخراج کنید، جریان های چند صفحه ای را مدیریت کنید. بدون سر یا بدون سر کار می کند.
- **playwright_inspector**: انتقال مرورگر را ضبط کنید، عکس های فوری DOM و اسکرین شات ها را در هر مرحله بگیرید. برای اشکال‌زدایی تعاملات وب یا بررسی تغییرات صفحه در طول زمان مفید است. ابزارهای Native

`uuid_gen` و `slugify` برای عملکرد در Rust (از طریق PyO3) پیاده‌سازی می‌شوند. آنها مستقیماً از یک ".pyd" از پیش ساخته شده بارگیری می‌شوند — **نیازی به نصب پیپ نیست**. «load_rust_pyd()» از «uagent.tools.rust_helper»، و 
کاربران این ابزار را بدون هیچ گونه وابستگی اضافی دریافت می‌کنند. رجوع کنید به 
[TOOL_CREATOR_GUIDE.md](https://github.com/awaku7/agentcli/blob/main/TOOL_CREATOR_GUIDE.md).

### 🌐 i18n / L10n

日本 /語繁體中文 / 한국어 / Español / Français / Русский / و بیشتر. 
 «UAGENT_LANG» را برای جابجایی تنظیم کنید. برای افزودن محلی جدید به [ADD_LOCALE.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/ADD_LOCALE.md) مراجعه کنید.

ترجمه‌های این README در [docs/README.translations.md](https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md).

### 🔒 Encrypted Environment Variables. —Store ancrypted. فایل `.env`. 
مدیریت با `uag_envsec`.

پیکربندی و جزئیات ** env encrypted **: `uag_envsec` — رمزگذاری `.env` به عنوان `.env.sec`
- **پاسخ‌ها API**: «UAGENT_RESPONSES=1» را برای حالت پاسخ‌ها API تنظیم کنید (OpenAI/Azure/BedrockAaLmapen/Bedrock/MaLmapen هوش مصنوعی). به‌طور خودکار برای Sakana AI (Fugu) فعال می‌شود.
- **اسناد برنامه‌نویس**: [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)
- **جریان ابزار**: [TOOL_FLOW.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/TOOL_FLOW.md) — نحوه ارسال ابزارها به LLM (ماسک ژانر، کاتالوگ_ابزار، GPT-5.4+ ابزار_جستجوی بومی)
_*:_S [SLM_TIPS.md](https://github.com/awaku7/agentcli/blob/main/docs/SLM_TIPS.md)

## Project Philosophy

uag می‌خواهد **هوش مصنوعی شما، بر روی دستگاه شما، طبق شرایط شما باشد.**

- بدون وابستگی به SaaS — به صورت محلی اجرا می‌شود
- بدون قفل ارائه‌دهنده – سوئیچ در هر زمان
- بدون قفل رابط کاربری – CLI /Web /Web / بدون ویژگی Web قفل کردن — گسترش با ابزارها و مهارت‌ها

تجربه رایگان عامل هوش مصنوعی، بدون قفل شدن فروشنده «UAGENT_EXTERNAL_TOOLS_DIR»، و 
 بلافاصله در دسترس است. برای توسعه‌دهندگان Rust، یک «.pyd» از پیش ساخته شده با 
صفر وابستگی اضافی برای کاربران ارسال کنید.## مشارکت

مشارکت پذیرفته می شود! گزارش‌های اشکال، پیشنهادات ویژگی‌ها، بهبود اسناد، ترجمه‌ها و درخواست‌های کششی — همه قابل قدردانی هستند.

- **مشکلات**: یک مشکل GitHub را برای اشکالات یا درخواست‌های ویژگی باز کنید.
- ** درخواست‌ها را بکشید**: مخزن را جدا کنید، تغییرات خود را انجام دهید و یک PR ارسال کنید. برای راه‌اندازی و دستورالعمل‌های توسعه به [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md) مراجعه کنید.
- **ترجمه‌ها**: README ترجمه و افزوده‌های محلی خوش آمدید. به [ADD_LOCALE.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/ADD_LOCALE.md) مراجعه کنید.
- **ابزارها و مهارت ها**: افزونه های ابزار جدید و مهارت های عامل را می توان از طریق بررسی های توسعه ارائه داد. PR)

ابتدا وابستگی های فقط تست را نصب کنید. آنها از لیست وابستگی زمان اجرا حذف می شوند: tests
python -m سیاه --بررسی تست‌های src
python scripts/tool_json_i18n_batch.py status
python -m pytest -q .
```

tests/\<afected_aa>

```

بررسی‌های اضافی در صورت لزوم: خط‌مشی scripts/compile_locales.py و «python scripts/po_qc_summary.py». از `sys.exit`; میزبان ابزار ابزار 'SystemExit'/'Exception' را به رشته های خطا تبدیل می کند بنابراین یک ابزار واحد نمی تواند فرآیند را از بین ببرد. خروج‌های سریع راه‌اندازی عمدی باقی می‌مانند.

## معماری و متغیرهای عملیاتی

به [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) برای قراردادهای بادوام که چرخه عمر A2A، زمینه‌های I18N، نصب وابستگی اختیاری، ایمنی ابزار، قابلیت‌های ارائه‌دهنده، وقایع مربوط به OAuth را پوشش می‌دهند، مراجعه کنید. تایید.

## Enterprise Policy Engine

 خط‌مشی‌های سطح سازمان برای ابزارها، ارائه‌دهندگان، اعتبارنامه‌ها، سرورهای MCP، شبکه‌ها، مهارت‌ها و افزونه‌ها پشتیبانی می‌شوند. «UAGENT_POLICY_FILE» را روی یک فایل خط مشی JSON/YAML تنظیم کنید. برای نمونه‌های پیکربندی، نقش‌ها، تأیید و فهرست‌های مجاز به [docs/ENTERPRISE_POLICY.md](docs/ENTERPRISE_POLICY.md) مراجعه کنید. [DAG_SCHEDULER.md](docs/DAG_SCHEDULER.md) / [MULTI_AGENT_RUNTIME.md](docs/MULTI_AGENT_RUNTIME.md) برای بازیابی بادوام، اجرای آگاه به وابستگی، ارکستراسیون چند عامله، و استفاده از راه دور.⎥PH_3. [DISTRIBUTED_COORDINATION.md](docs/DISTRIBUTED_COORDINATION.md) برای هماهنگی اجاره رهبر در زمان اجرا مشترک.
```
