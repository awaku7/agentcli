<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="720">
</p>

# uag (Локальний ШІ-агент)

uag — це локальний інтерактивний агент, який виконує **команди**, працює з **файлами** та читає **файли даних** на кшталт PDF, PPTX і Excel. Він надає три інтерфейси: CLI, GUI та Web.

uag створено, щоб **звільнити вас від застосунків, прив’язаних до постачальника**: використовуйте інтерфейс, що підходить вашому робочому процесу, перемикайте постачальників і зберігайте контроль над своїм середовищем.

GitHub: https://github.com/awaku7/agentcli

## Встановлення

Встановіть із PyPI за допомогою pip:

```bash
pip install uag
```

Якщо ви використовуєте віртуальне середовище, спочатку активуйте його, а потім виконайте наведену вище команду.

Під час першого запуску `uag` перевіряє ваше середовище та автоматично запускає майстер налаштування, якщо бракує потрібних змінних постачальника. Докладнішу інформацію про налаштування дивіться в [ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md).

## Основні можливості

- **Практичний набір інструментів**: робота з файлами, вебпошук, витягування з PDF/PPTX/Excel, генерація зображень і аналіз зображень.
- **Підтримка кількох постачальників**: OpenAI / Azure / Bedrock / OpenRouter / Ollama / Gemini / Vertex AI / Claude / Grok / NVIDIA / DeepSeek / Alibaba Cloud (Qwen) / Moonshot AI.
- **Три інтерфейси**:
  - **CLI**: `uag` / `python -m uagent`
  - **GUI**: `uagg` / `python -m uagent.gui`
  - **Web**: `uagw` / `python -m uagent.web`
  - **A2A server**: `uaga` / `python -m uagent.a2a.server`
- **Підтримка MCP**: підключення до зовнішніх MCP tool server.
- **Безперервність сесії**: збереження контексту під час зміни моделі або постачальника.
- **Торговельний майданчик навичок агента**: Переглядайте та встановлюйте навички спільноти з [SkillsMP](https://skillsmp.com) або [ClawHub](https://clawhub.ai) за допомогою `:skills mp_search`.
- **Web Inspector**: збереження переходів у браузері, DOM-знімків і скриншотів за допомогою `playwright_inspector`.
- **Вбудована документація**: читання вбудованих документів за допомогою `uag docs`.
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

## Використання

### Запуск і вихід

Запустіть `uag` у терміналі. Щоб вийти, введіть `:exit`.

### A2A server

Запустіть HTTP-сервер, сумісний з Agent2Agent:

```bash
uaga
```

Налаштування `UAGENT_A2A_*`, зокрема автентифікацію, хост, порт, перезавантаження, публічний базовий URL, паралельність і engine, дивіться в [ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md).

### Корисні команди

- `:tools`: показати завантажені інструменти
- `:logs [n]`: показати останні журнали сесії
- `:load <index>`: завантажити попередню сесію
- `:skills`: вибрати та завантажити Agent Skills (використовуйте `:skills mp_search` для перегляду торговельних майданчиків [SkillsMP](https://skillsmp.com) або [ClawHub](https://clawhub.ai))
- `:shrink [n]`: стиснути історію й залишити останні `n` повідомлень

## Налаштування та деталі

### Змінні середовища та налаштування

Докладніше про ключі API, мовні налаштування (`UAGENT_LANG`), згортання історії та інше дивіться в [ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md).

- **Майстер налаштування**: `python -m uagent.setup_cli`
- **Шифроване середовище**: використайте `uag_envsec`, щоб зашифрувати `.env` як `.env.sec`
- **Оновлення зашифрованих значень**: `uag_envsec add --file .env.sec --key NAME --value VALUE`

### Примітка щодо Responses API

Якщо встановити `UAGENT_RESPONSES=1`, Responses API використовується для підтримуваних постачальників: OpenAI / Azure / Bedrock / OpenRouter / Ollama.
Gemini / Claude / Vertex AI використовують власні нативні API-шляхи, і Responses API на них не поширюється.
Для інших постачальників uag переходить на шлях, специфічний для постачальника, або на chat-completions.

### Документація для розробників і переклади

- **Документація для розробників**: [`src/uagent/docs/DEVELOP.md`](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)
- **Додати локалі**: [`src/uagent/docs/ADD_LOCALE.md`](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/ADD_LOCALE.md)
- **Інші переклади README**: [`docs/README.translations.md`](https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md)
