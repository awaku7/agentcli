<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="680">
</p>

<h1 align="center">uag</h1>

<p align="center">
  <strong>Universal AI Gateway</strong><br>
  Один локальний агент. Будь-яка модель. Будь-який інструмент. Ваше середовище, ваші правила.
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
  <a href="https://github.com/awaku7/agentcli/discussions">Обговорення</a> ·
  <a href="https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md">Переклади</a>
</p>

______________________________________________________________________

**Чому uag?**

uag — це AI-агент із пріоритетом локального виконання, який підключає потрібну вам модель до інструментів, якими ви фактично користуєтеся.
Він надає єдине розширюване середовище виконання для файлів, браузерів, кодових баз, комунікацій, хмарних API,
пристроїв IoT, MCP-серверів і робочих процесів із кількома агентами.

- **Свобода вибору провайдера** — OpenAI, Anthropic, Gemini, Azure, Bedrock, Ollama, llama.cpp, Grok, DeepSeek та інші.
- **Локальне виконання** — середовище виконання агента й інструментів залишається на вашій машині; її залишають лише вибрані вами виклики API.
- **Єдиний шар інструментів** — ті самі інструменти працюють у CLI, настільному GUI, веб-інтерфейсі, VS Code та A2A.
- **Паралельність за задумом** — незалежні операції лише для читання можуть виконуватися одночасно.
- **Розширюваність** — додавайте інструменти, плагіни, Agent Skills, MCP-сервери та інструменти на основі Rust без зміни ядра.
- **Урахування безпеки** — руйнівні дії, облікові дані, керування пристроями та мережеві записи підтримують явне підтвердження й політики.

> **Коротко:** uag — це площина керування між вашими AI-моделями та реальним середовищем.

> **🧠 Результати інструментів з урахуванням контексту** — Результати великих інструментів, якщо це можливо, не включаються до контексту активної моделі. uag зберігає їх як артефакти та натомість передає моделі обмежений попередній перегляд зі стабільною посиланням на Artifact. Це може суттєво зменшити кількість вхідних токенів, необхідних для наступних ходів, коли інструмент генерує великий результат.
> [Докладний посібник зі стиснення контексту](CONTEXT_COMPRESSION.uk.md)

## Швидкий старт

**Python 3.11+**

```bash
python -m pip install --upgrade uag
uag
```

Під час першого запуску відкривається майстер налаштування. Він допомагає налаштувати провайдера та зберігає вибрані параметри
у вашому локальному середовищі.

Для поширених груп функцій:

```bash
python -m pip install "uag[core,providers,tools]"
```

> Інтеграції з платформами є необов’язковими. Встановлюйте лише те, що потрібно вашій операційній системі; див.

```text
> What files changed in this repository?
> Search the web for today's AI news and summarize the top five stories.
> :help
```

[Quickstart](QUICKSTART.md) · [Environment](ENVIRONMENT.md)

## Інтерфейси

| Інтерфейс | Команда | Найкраще підходить для |
|---|---|---|
| **CLI** | `uag` | Швидкої роботи з клавіатури |
| **Настільний GUI** | `uagg` | Нативного настільного інтерфейсу |
| **Веб-інтерфейс** | `uagw` | Доступу через браузер |
| **Сервер A2A** | `uaga` | Взаємодії між агентами |
| **VS Code** | Extension | Пояснення, рефакторингу, виправлення та перегляду інструментів у редакторі |

Усі інтерфейси спільно використовують конфігурацію провайдера, реєстр інструментів, правила безпеки та дані сесій.

~~~bash
# Desktop GUI
python -m pip install "uag[platform]"

# Web UI
python -m pip install "uag[web]" fastapi uvicorn
~~~

[Interface options](USAGE.md) · [Environment](ENVIRONMENT.md)

## Що можна створити

Адаптери провайдерів охоплюють хмарні та локальні середовища виконання, зокрема:

**OpenAI · Anthropic · Gemini · Vertex AI · Azure OpenAI · Amazon Bedrock · Grok · DeepSeek · OpenRouter · Ollama · llama.cpp · LM Studio**

- Читати, створювати, редагувати, шукати, хешувати, архівувати та перевіряти файли
- Переглядати зміни Git, шукати секрети, запускати тести, виконувати linting і компіляцію та вимірювати покриття
- Навігувати великими кодовими базами Python, TypeScript, JavaScript, Go, Rust, C/C++, Java, C#, COBOL, VBA та іншими
- Автоматизувати браузери за допомогою Playwright, зокрема багатосторінкові процеси та завантаження

- **MCP** — підключення зовнішніх серверів інструментів, зокрема сервісів із підтримкою OAuth
- **A2A** — координація з іншими агентами та сумісними серверами
- **Хмара** — доступ до API AWS, Google Cloud і Azure із підтвердженням записів
- **Комунікації** — Gmail, Bluesky, Discord, Microsoft Teams і pybitchat
- **IoT** — SwitchBot, ECHONET Lite, Matter, BACnet, Modbus TCP, OPC UA та UPnP
- **Медіа** — генерування й редагування зображень, транскрипція/синтез аудіо, захоплення з камери та QR-коди
- **Документи** — аналіз PDF, PowerPoint, Word, Excel, CSV, JSON, YAML, SQL і журналів

- **SwitchBot** — хмарне та BLE-виявлення, стан, керування, пакетна обробка та підписки
- **ECHONET Lite** — виявлення та керування японськими побутовими приладами, зокрема сповіщеннями INF
- **Matter** — кінцеві точки, кластери, атрибути, історія станів, підписки та керування
- **BACnet / Modbus TCP / OPC UA** — читання, записи, перегляд і моніторинг у промисловій автоматизації та автоматизації будівель
- **UPnP** — виявлення пристроїв, стан WAN і керування перенаправленням портів маршрутизатора

### Місце uag у системі

uag розташовується між людьми й інтерфейсами з одного боку та моделями, інструментами й реальними системами — з іншого.
Він координує розмову, вибирає можливості, застосовує правила безпеки та зберігає можливість відновити робочий процес.

~~~mermaid
flowchart LR
    UI["CLI · Desktop · Web · VS Code · A2A"] --> UAG["UAG agent runtime"]
    UAG --> MODELS["Hosted & local models"]
    UAG --> TOOLS["Tools & extensions"]
    UAG --> STATE["Sessions & context"]
    TOOLS --> SYSTEMS["Files · Code · Web · MCP · Cloud · IoT"]
    POLICY["Confirmation · Credentials · Policy"] -.-> UAG
~~~

### Плагіни, Agent Skills і маркетплейси

Перетворіть uag на спеціалізованого агента без розгалуження ядра:

- Встановлюйте **плагіни, сумісні з Claude Code**, з каталогу, ZIP, Git-репозиторію, HTTP-джерела або маркетплейсу
- Об’єднуйте skills, субагентів, MCP-сервери, хуки, slash-команди, стилі виведення, залежності та канали
- Переглядайте можливості спільноти на [SkillsMP](https://skillsmp.com) і [ClawHub](https://clawhub.ai)
- Додавайте приватні skills та інструменти організації локально через `UAGENT_EXTERNAL_TOOLS_DIR`

```text
:skills mp_search browser automation
:plugin list
:plugin install <source>
:plugin marketplace list
```

Див. [Посібник із розробки плагінів](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP_PLUGIN.md).

- **200+ інструментів** для файлів, вебу, медіа, документів, коду, хмарних сервісів, комунікацій та IoT
- **Динамічне виявлення та завантаження** — використовуйте `tool_catalog`, щоб знаходити можливості, і `tool_load`, щоб вмикати їх лише за потреби
- **Інтелект роботи з кодом** — `code_map`, спеціалізовані навігатори `idx`, перевірка Git, виконання тестів, linting, компіляція та покриття
- **Плагіни, сумісні з Claude Code**, зі skills, агентами, MCP-серверами, хуками, командами та маркетплейсами
- **Agent Skills** зі SkillsMP та ClawHub
- **Користувацькі інструменти Python** із `TOOL_SPEC` і `run_tool()`
- **Інструменти на основі Rust** для легковагих нативних розширень

[Tool Creator Guide](../TOOL_CREATOR_GUIDE.md) · [MCP OAuth / Proxy Guide](MCP_OAUTH_PROXY_GUIDE.md)

## Створено для реальних робочих процесів

### 🧠 Результати інструментів з урахуванням контексту

Результати великих інструментів, якщо це можливо, не включаються до контексту активної моделі. uag зберігає їх як артефакти та натомість передає моделі обмежений попередній перегляд зі стабільною посиланням на Artifact. Це може суттєво зменшити кількість вхідних токенів, необхідних для наступних ходів, коли інструмент генерує великий результат.

Відновлюйте попередні розмови за допомогою `:load <index>`. Результати інструментів можна кешувати, а провайдерів можна змінювати
без повторної збірки застосунку.

[Context compression](CONTEXT_COMPRESSION.uk.md) · [Memory](MEMORY.md) · [Session portability](SESSION_PORTABILITY.md)

### Автопілот

Використовуйте `:auto` для багатоетапної роботи з необов’язковою моделлю-рецензентом. Установіть обмеження кількості раундів за допомогою `--max-rounds N`.
Натисніть **F12**, щоб зупинити автопілот, або **F12**, щоб зупинити поточну відповідь.

Незалежні операції лише для читання виконуються одночасно, якщо це безпечно. Вебпошук, перевірка файлів,
аналіз репозиторію та подібні завдання можуть виконуватися паралельно за допомогою налаштованого пулу
воркерів (`UAGENT_PARALLEL_WORKERS`). Операції запису залишаються послідовними або потребують підтвердження.

Безперервність сесій, кешування результатів інструментів, стан пакетних операцій, відновлення після перезапуску, планування DAG і
оркестрація кількох агентів роблять складну роботу відновлюваною, а не одноразовою.

[Auto-pilot](README_AUTO.md) · [Timers](SET_TIMER.md) · [Multi-agent runtime](MULTI_AGENT_RUNTIME.md)

### 🌍 Приватність, багатомовність і політики

`human_ask` призупиняє роботу перед чутливими діями. Видалення файлів, перезапис, команди оболонки, керування пристроями,
операції з обліковими даними та мережеві записи можуть регулюватися правилами підтвердження та політики.

Використовуйте сховище облікових даних замість розміщення довготривалих секретів у запитах:

Веб-інтерфейс включає вхід через OIDC з використанням Authorization Code + PKCE, перевірені ID-токени, серверні сесії та контроль доступу до проєктів/кімнат. Перевірені групові твердження Microsoft Entra ID можуть використовуватися для політики доступу на основі каталогу при налаштуванні. Розгортання Windows Active Directory, OAuth і trusted-proxy можуть інтегруватися через явні перевірені адаптери ідентичності; Windows AD потребує специфічного для розгортання перевіряча Kerberos/Negotiate і за замовчуванням не увімкнений.

uag включає додаткове відстеження OpenTelemetry і показники для Agent, LLM, інструментів, Context, Memory і операцій пошуку. Спостережливість вимкнена за замовчуванням.

Принцип local-first не означає, що UAG типово працює повністю офлайн або що всі інструменти ізольовані. Виклики зовнішніх моделей і підключених служб залежать від налаштувань.

- [Enterprise policies](ENTERPRISE_POLICY.md)
- [MXC sandbox](SANDBOX_MXC.md)
- [Remote Web / A2A](REMOTE_MXC_DEFAULT.md)
- [Web identity](WEB_IDENTITY_MEMORY.md)
- [OpenTelemetry](UAG_OPENTELEMETRY_DESIGN.md)

### 🌍 Багатомовний переклад

- `translate_text` підтримує Google Translate та офіційний Python-клієнт DeepL за допомогою параметрів `provider=auto`, `provider=deepl` або `provider=google`.
- Визначення інструментів доступні в 37 локалях плюс англійська (всього 38), із збереженням заповнювачів та технічних ідентифікаторів.

Повнодуплексний голос доступний через OpenAI Realtime, Azure OpenAI, xAI Grok Voice, Gemini Live
і Bedrock Nova Sonic, з опційним шумозаглушенням відлуння AEC3 та обмеженим правилами безпеки викликом функцій у реальному часі.

[Translations](README.translations.md) · [IoT](IOT_USECASE.md) · [Communication](COMMUNICATION.md)

## Документація

| Тема | Документація |
|---|---|
| Змінні середовища | [docs/ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/docs/ENVIRONMENT.md) |
| Архітектура та інваріанти | [docs/ARCHITECTURE.md](https://github.com/awaku7/agentcli/blob/main/docs/ARCHITECTURE.md) |
| Computer Use | [docs/COMPUTER_USE_IMPLEMENTATION.md](https://github.com/awaku7/agentcli/blob/main/docs/COMPUTER_USE_IMPLEMENTATION.md) |
| Інструменти репозиторію | [docs/REPOSITORY_TOOLS.md](https://github.com/awaku7/agentcli/blob/main/docs/REPOSITORY_TOOLS.md) |
| Варіанти використання IoT | [docs/IOT_USECASE.md](https://github.com/awaku7/agentcli/blob/main/docs/IOT_USECASE.md) |
| Інструменти комунікацій | [docs/COMMUNICATION.md](https://github.com/awaku7/agentcli/blob/main/docs/COMMUNICATION.md) |
| Автопілот | [docs/README_AUTO.md](https://github.com/awaku7/agentcli/blob/main/docs/README_AUTO.md) |
| MCP OAuth / Proxy | [docs/MCP_OAUTH_PROXY_GUIDE.md](https://github.com/awaku7/agentcli/blob/main/docs/MCP_OAUTH_PROXY_GUIDE.md) |
| Розширення VS Code | [docs/VSCODE.md](https://github.com/awaku7/agentcli/blob/main/docs/VSCODE.md) |
| Посібник розробника | [src/uagent/docs/DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md) |
| Потік інструментів | [src/uagent/docs/TOOL_FLOW.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/TOOL_FLOW.md) |

[Quickstart](QUICKSTART.md) · [Architecture](ARCHITECTURE.md) · [Context management](UAG_CONTEXT_MANAGEMENT_DESIGN.md)

## Розробка та внесок

```bash
git clone https://github.com/awaku7/agentcli.git
cd agentcli
python -m pip install -e ".[core,providers,test]"
```

Запустіть перевірки перед PR:

```bash
python -m ruff check src tests
python -m black --check src tests
python -m pytest -q .
```

Повний робочий процес розробки описано в [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md).

Повідомлення про помилки, ідеї функцій, покращення документації, переклади, інструменти, skills і pull request вітаються.
Перед великими змінами спочатку створіть issue або обговорення. Прочитайте [Посібник розробника](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)
та запустіть наведені вище перевірки перед надсиланням pull request.

## License

Licensed under the [Apache License 2.0](https://github.com/awaku7/agentcli/blob/main/LICENSE).
