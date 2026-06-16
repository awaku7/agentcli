<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="720">
</p>

# uag (عامل هوش مصنوعی محلی)

uag یک عامل تعاملی محلی است که **دستورها را اجرا می‌کند**، **فایل‌ها را مدیریت می‌کند** و **فایل‌های داده** مانند PDF، PPTX و Excel را می‌خواند. این ابزار سه رابط کاربری ارائه می‌دهد: CLI، GUI و Web.
uag طوری ساخته شده است که شما را از **وابستگی به برنامه‌های قفل‌شده به یک فروشنده** آزاد نگه دارد: رابطی را انتخاب کنید که با کار شما سازگار است، ارائه‌دهنده را عوض کنید و کنترل محیط خود را در دست داشته باشید.
GitHub: https://github.com/awaku7/agentcli

## نصب

با pip از PyPI نصب کنید:

```bash
pip install uag
```

اگر از virtual environment استفاده می‌کنید، ابتدا آن را فعال کنید و سپس دستور بالا را اجرا کنید.

در اولین اجرا، اگر متغیرهای لازمِ ارائه‌دهنده موجود نباشند، `uag` به‌طور خودکار setup wizard را اجرا می‌کند. برای جزئیات پیکربندی، [ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md) را ببینید.

## ویژگی‌های اصلی

- **مجموعه ابزار کاربردی**: ویرایش فایل، جست‌وجوی وب، استخراج PDF/PPTX/Excel، تولید تصویر و تحلیل تصویر.
- **پشتیبانی از چند ارائه‌دهنده**: OpenAI / Azure / Bedrock / OpenRouter / Ollama / Gemini / Vertex AI / Claude / Grok / NVIDIA / DeepSeek / Alibaba Cloud (Qwen) / Moonshot AI.
- **سه رابط کاربری**:
  - **CLI**: `uag` / `python -m uagent`
  - **GUI**: `uagg` / `python -m uagent.gui`
  - **Web**: `uagw` / `python -m uagent.web`
  - **A2A server**: `uaga` / `python -m uagent.a2a.server`
- **پشتیبانی از MCP**: اتصال به سرورهای ابزار MCP خارجی.
- **تداوم نشست**: با تغییر مدل یا ارائه‌دهنده، زمینه گفتگو حفظ می‌شود.
- **بازار مهارت‌های عامل**: مهارت‌های انجمن را از [SkillsMP](https://skillsmp.com) یا [ClawHub](https://clawhub.ai) با `:skills mp_search` مرور و نصب کنید.
- **Web Inspector**: با `playwright_inspector` جابه‌جایی‌های مرورگر، DOM snapshot و screenshot را ذخیره کنید.
- **مستندات داخلی**: با `uag docs` مستندات همراه را بخوانید.
- **IoT device support**: Control SwitchBot, ECHONET Lite, Matter, and UPnP devices. See [IOT_USECASE.md](IOT_USECASE.md).


## IoT Device Support

Control smart home and IoT devices through multiple interfaces:

- **SwitchBot Cloud**: List, control, and batch-operate SwitchBot devices (TV, air conditioner, lights, etc.).
  - Infrared remote devices (on/off, brightness, temperature)
  - Air conditioner mode and fan speed control
  - Batch execution of multiple commands
- **SwitchBot BLE**: Scan and control nearby SwitchBot BLE devices.
- **ECHONET Lite**: Discover and control ECHONET Lite home appliances over the local network.
- **Matter**: Inspect Matter controller/bridge/device structure (read-only).
- **UPnP**: Discover UPnP devices and manage IGD port forwarding.

For detailed usage, see [IOT_USECASE.md](IOT_USECASE.md).

## استفاده

### شروع و خروج

برای شروع، در ترمینال `uag` را اجرا کنید. برای خروج `:exit` را وارد کنید.

### سرور A2A

یک سرور HTTP سازگار با Agent2Agent راه‌اندازی کنید:

```bash
uaga
```

برای تنظیمات `UAGENT_A2A_*` مانند احراز هویت، میزبان، پورت، reload، public base URL، concurrency و engine، به [ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md) مراجعه کنید.

### نکته‌های کاربردی

- `:tools`: ابزارهای بارگذاری‌شده را نشان می‌دهد
- `:logs [n]`: لاگ‌های اخیر نشست را نشان می‌دهد
- `:load <index>`: یک نشست قبلی را بارگذاری می‌کند
- `:skills`: انتخاب و بارگذاری Agent Skills (از `:skills mp_search` برای مرور بازارهای [SkillsMP](https://skillsmp.com) یا [ClawHub](https://clawhub.ai) استفاده کنید)
- `:shrink [n]`: history را خلاصه می‌کند و آخرین `n` پیام را نگه می‌دارد

## پیکربندی و جزئیات

### متغیرهای محیطی و راه‌اندازی

برای API keyها، تنظیمات زبان (`UAGENT_LANG`)، تنظیمات shrink history و موارد دیگر، [ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md) را ببینید.

- **Setup wizard**: `python -m uagent.setup_cli`
- **محیط رمزنگاری‌شده**: برای رمزنگاری `.env` به `.env.sec` از `uag_envsec` استفاده کنید
- **به‌روزرسانی مقادیر رمزنگاری‌شده**: `uag_envsec add --file .env.sec --key NAME --value VALUE`

### یادداشت Responses API

اگر `UAGENT_RESPONSES=1` را تنظیم کنید، برای ارائه‌دهنده‌های OpenAI / Azure / Bedrock / OpenRouter / Ollama از Responses API استفاده می‌شود.
Gemini / Claude / Vertex AI از مسیر بومی API خود استفاده می‌کنند و شامل Responses API نیستند.
Image analysis از طریق Responses API فعلاً فقط برای OpenAI / Azure / Bedrock / OpenRouter محدود است.
برای سایر ارائه‌دهنده‌ها، uag به مسیر provider-specific یا chat-completions برمی‌گردد.

### مستندات توسعه‌دهنده و ترجمه‌ها

- **Developer docs**: [`src/uagent/docs/DEVELOP.md`](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)
- **Add locales**: [`src/uagent/docs/ADD_LOCALE.md`](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/ADD_LOCALE.md)
- **ترجمه‌های دیگر README**: [`docs/README.translations.md`](https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md)
