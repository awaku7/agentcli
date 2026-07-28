<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="720">
</p>

<h1 align="center">uag — універсальний шлюз ШІ</h1>

<p align="center">
  <b>U</b>niversal <b>A</b>I <b>G</b>ateway — Your environment, your freedom.
</p>

<p align="center">
  File ops / Web search / Image generation &amp; analysis / PDF &amp; Excel extraction / IoT control / MCP integration<br>
  20+ providers / 3 UIs / Parallel tool execution / Agent Skills marketplace
</p>

<p align="center">
  <a href="https://github.com/awaku7/agentcli">GitHub</a>
  ·
  <a href="https://pypi.org/project/uag/">PyPI</a>
  ·
  <a href="https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md">Read this in your language</a>
</p>

---

## Чому uag?

**Звільніться від прив’язки до постачальника.** Більшість помічників штучного інтелекту прив’язують вас до певного постачальника або хмарної служби. uag відрізняється.

- **Запускається локально** на вашій машині. Ваші дані залишаються з вами (крім викликів API, які ви робите).
- **Свобода постачальників**: OpenAI, Claude, Gemini, DeepSeek, Ollama, Azure, Bedrock, HuggingFace... 21 постачальників, усі доступні з єдиного інтерфейсу. Перемикайтеся між ними шляхом переналаштування змінних середовища — без перевстановлення, без міграції.
- **185 інструмент**: введення/виведення файлів, веб-пошук, створення зображень, Gmail, сканування пристроїв BLE, інтеграція сервера MCP — **111 є паралельно безпечними** (до 8 виконуються одночасно через пул потоків, налаштовується за допомогою `UAGENT_PARALLEL_WORKERS`). Коли LLM запускає кілька викликів інструментів одночасно, uag автоматично розпаралелює їх.
- **3 інтерфейси користувача + A2A**: CLI, графічний інтерфейс користувача, веб і протокол «Агент-агент». Той самий двигун, будь-який інтерфейс.
- **Агентські навички**: встановлюйте навички, створені спільнотою, з ринку. Подовжувати uag нескінченно.

uag — **ваш AI-помічник на ваших умовах**. Не прив’язаний до постачальника, не прив’язаний до інтерфейсу, не прив’язаний до платформи.

## Швидкий старт

```bash
pip install uag
uag
```

Під час першого запуску майстер налаштування проведе вас через налаштування постачальника.
Перегляньте [docs/ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/docs/ENVIRONMENT.md) для всіх змінних середовища.

## Особливості

### 🧠 Багатопровайдерна архітектура

OpenAI / Azure / Bedrock / OpenRouter / Ollama / Gemini / Vertex AI / Claude / Grok / NVIDIA / DeepSeek / Z.AI (Zhipu AI) / HuggingFace / Alibaba Cloud (Qwen) / KIMI (Moonshot AI) / Xiaomi MiMo / LM Studio / MiniMax / **Sakana AI (Fugu)** / **Together AI** / **Vercel AI Gateway**

Усі постачальники мають однаковий набір інструментів та інтерфейс. Перемикайтеся, встановлюючи `UAGENT_PROVIDER` — без змін коду, без окремих установок.

### ⚡ Паралельне виконання інструментів

Коли LLM запитує декілька інструментів одночасно, uag **автоматично розпаралелює** їх.
111 інструментів позначено як `x_parallel_safe` і виконуються одночасно через `ThreadPoolExecutor` (8 потоків за замовчуванням; змініть `UAGENT_PARALLEL_WORKERS`).

**Приклад**: запитайте «Перевірте погоду в скандинавських столицях» → LLM запускає `search_web` × 5 країн → усі 5 пошуків виконуються паралельно → результати збираються в одній групі.

Інструменти лише для читання (пошук файлів, обчислення хешу, перелік каталогів, переклад, запити до БД тощо) агресивно розпаралелюються.


### 🧩 Plugin System (Claude Code Compatible)

uagent implements a **Claude Code-compatible plugin system**. Plugins bundle skills, agents, MCP servers, hooks, and more into self-contained directories with a `.claude-plugin/plugin.json` manifest.

**Supported components**: Skills, Sub-agents, MCP servers, Hooks (12 lifecycle events), Slash commands, Output styles, userConfig, Dependencies, Channels, Marketplaces

**CLI commands**:
```
:plugin list                         # List installed plugins
:plugin install <source> [--scope]   # Install (dir/zip/git/http)
:plugin install <name>@<marketplace>  # Install from marketplace
:plugin remove <name>                # Uninstall
:plugin enable/disable <name>        # Toggle
:plugin marketplace add/remove/list  # Manage marketplaces
:plugin init <name>                  # Scaffold new plugin
```

See [DEVELOP_PLUGIN.md](src/uagent/docs/DEVELOP_PLUGIN.md) for full documentation.


### 🔄 Безперервність сесії

- **Switch providers mid-session** with `UAGENT_PROVIDER` — conversation history is preserved.
- **Reload past sessions** with `:load <index>` — pick up where you left off.
- **Tool result caching** avoids redundant re-execution when the same tool call repeats.

### 🛠 185 інструмент

| Категорія | Інструменти |
|---|---|
| **Файлові операції** | read/write/create/delete/search/grep/hash/zip, file_type, parse_eml (.eml файли) |
| **Веб** | fetch_url, search_web, знімок екрана, browser_playwright |
| **Медіа** | генерувати_зображення, аналізувати_зображення, img2img, аудіо_мовлення, аудіо_транскрибувати |
| **Документи** | Вилучення PDF/PPTX/DOCX/RTF/ODT, структуроване вилучення Excel |
| **Прогноз** | Прогнозування часових рядів з 9 моделями (AutoARIMA, Prophet, LightGBM, CatBoost, TimesFM тощо), автоматичний вибір моделі, створення графіків, i18n |
| **Спілкування** | gmail_send, gmail_read, bluesky, discord_channel, teams_webhook , **pybitchat** (BLE Mesh) — див. [COMMUNICATION.md](https://github.com/awaku7/agentcli/blob/main/docs/COMMUNICATION.md) and [BITCHAT.md](https://github.com/awaku7/agentcli/blob/main/docs/BITCHAT.md)|
| **Інтернет речей** | SwitchBot (Cloud + BLE), ECHONET Lite, Matter, UPnP, reverse_geocode |
| **Інструменти розробника** | git_ops, python_compile, lint_format, run_tests, db_query, **13 навігаторів вихідного коду (сімейство idx)** |
| **MCP** | Підключення до зовнішніх серверів MCP, список інструментів, виконання |
| **A2A** | Зв'язок між агентами (з іншими примірниками uag або A2A-сумісними серверами) |
| **Система** | env vars, характеристики системи, час, обчислення дати, uuid_gen, slugify ||
| **Source Nav** | **13 інструментів idx** для Python, PHP, TypeScript, Java, C#, Dart, C/C++, Rust, Go, Swift, Kotlin, COBOL — отримуйте індекс функції/класу або конкретне визначення, не читаючи весь файл |

### 🖥 4 інтерфейси + розширення коду VS

| Режим | Команда | Призначення |
|---|---|---|
| **CLI** | `uag` | Швидка термінальна робота |
| **GUI** | `uagg` | Інтерфейс робочого столу через tkinter |
| **Веб** | `uagw` | Браузерний доступ |
| **Сервер A2A** | `uaga` | Протокол Agent2Agent для мультиагентного зв'язку |
| **Код VS** | — | [Розширення](https://github.com/awaku7/agentcli/blob/main/docs/VSCODE.md) із панеллю чату, поясненням, рефакторингом, виправленням помилок і переглядом дерева інструментів |

Див. [VSCODE.md](https://github.com/awaku7/agentcli/blob/main/docs/VSCODE.md), щоб дізнатися більше про розширення VS Code — встановлення, команди, прив’язки клавіш і налаштування.

### 🏠 Контроль пристроїв IoT
Перегляньте [IOT_USECASE.md](https://github.com/awaku7/agentcli/blob/main/docs/IOT_USECASE.md)


### 🏠 IoT Device Control

- **BACnet**: читання/запис пристроїв BACnet/IP (HVAC, освітлення, лічильники електроенергії). Підписка COV на push-сповіщення
- **Modbus TCP**: читання/записування/введення регістрів і котушок. Моніторинг змін на основі опитувань
- **OPC UA**: перегляд адресного простору, читання/запис змінних, підписка на зміни даних
- **SwitchBot**: контроль пакетів у хмарі та сканування/контроль BLE. Підписка на основі опитування
- **ECHONET Lite**: знаходьте, контролюйте та підписуйтеся на сповіщення INF від побутової техніки (кондиціонера, світильників, водонагрівачів тощо)
- **Matter**: керування читанням/записом + підписка на атрибути для моніторингу змін стану
- **UPnP**: виявлення пристроїв і переадресація портів IGD

Див. [IOT_USECASE.md](IOT_USECASE.md)

### 🎯 Ринок навичок агента

`:skills mp_search`, щоб переглянути [SkillsMP](https://skillsmp.com) і [ClawHub](https://clawhub.ai) навички спільноти.
Встановлюйте та розширюйте можливості uag на льоту.

### 🤖 Автопілот (`:auto`)

uag може **автономно досягати мети протягом кількох раундів LLM**. Ідеально підходить для складних багатоетапних завдань, які потребують повторного вдосконалення.

- **Як це працює**: кожен раунд містить головний запит (Крок A), за яким слідує судження рецензента (Крок B), яке вирішує «ЗАВЕРШИТИ чи ПРОДОВЖИТИ?»
- **Той самий постачальник, той самий API**: на думку рецензента, як основний запит використовується ідентичний шлях коду, включаючи підтримку Responses API.
- **Окремий суддя LLM** (необов’язково): установіть `UAGENT_AP_PROVIDER`, щоб використовувати іншого постачальника/модель для рецензента (наприклад, використовувати дешевшу модель для оцінювання).
- **Вийти в будь-який час**: натисніть клавішу `x`, щоб зупинити негайно, навіть у середині відповіді. Або дозвольте рецензенту вирішити, коли мета буде досягнута.
- **Настроюється**: `--max-rounds N` для контролю бюджету.

Перегляньте [README_AUTO.md](https://github.com/awaku7/agentcli/blob/main/docs/README_AUTO.md), щоб отримати повну документацію.

### 🧩 Менеджер стану партії

uag може відстежувати перебіг тривалих багатофайлових завдань. Коли LLM обробляє десятки файлів, `batch_state` зберігає на диску список файлів, що очікують на розгляд, завершених і невдалих. Якщо сеанс закінчується або раунд минув, наступний запуск поновлюється з того місця, де він був зупинений — нічого не втрачається.

### 🛡 Human-in-the-Loop

`human_ask` дозволяє програмі LLM зупинятися та запитувати ваше підтвердження перед виконанням руйнівних операцій (видалення файлів, перезапис, команди оболонки). Ви залишаєтесь під контролем.

### 🛑 Переривання (c-клавіша / кнопка зупинки)

Зупиніть генерацію відповіді LLM у будь-який час і введіть команду зупинки назад до LLM.

| Інтерфейс | Як перервати |
|---|---|
| **CLI** | Натисніть клавішу `c` під час трансляції LLM — поточна відповідь припиняється, і `"Stop"` надсилається як повідомлення користувача, тому LLM відповідає відповідно |
| **ВЕБ-Інтерфейс користувача** | Натисніть червону кнопку **■ Зупинити** (з’являється автоматично під час обробки LLM) |
| **Графічний інтерфейс робочого столу** | Натисніть червону кнопку **■** (з’являється автоматично під час обробки LLM) |

Переривання працює як «оперативна ін’єкція»: замість того, щоб просто переривати, воно повертає «Stop» назад до LLM як повідомлення користувача, дозволяючи йому вишукано завершити або підтвердити переривання.

Натисніть клавішу `x`, щоб вийти з режиму автопілота (див. [README_AUTO.md](https://github.com/awaku7/agentcli/blob/main/docs/README_AUTO.md)).

### 🕵️ Автоматизація веб-переглядача та веб-інспектор

Два взаємодоповнюючих інструменти на основі Playwright:

- **browser_playwright**: автоматизуйте реальні сеанси браузера — переходьте, клацайте, заповнюйте форми, витягуйте дані, обробляйте багатосторінкові потоки. Працює без голови або з головою.
- **playwright_inspector**: запис переходів у веб-переглядачі, знімків DOM і скріншотів на кожному кроці. Корисно для налагодження веб-взаємодій або перевірки змін сторінки з часом.

### 🔄 Динамічне завантаження інструментів

`tool_catalog` і `tool_load` дозволяють знаходити та вмикати інструменти під час виконання.
Не потрібно завантажувати все під час запуску — активуйте лише те, що вам потрібно, коли вам це потрібно.


### 🦀 Rust Native Tools

`uuid_gen` and `slugify` are implemented in Rust (via PyO3) for performance.
They load directly from a pre-built `.pyd` — **no `pip install` required**.

External developers can also ship Rust-based tools: place a `.pyd` next to the
wrapper `.py`, use ``load_rust_pyd()`` from ``uagent.tools.rust_helper``, and
users get the tool without any extra dependencies. See
[TOOL_CREATOR_GUIDE.uk.md](TOOL_CREATOR_GUIDE.uk.md).

### 🌐 i18n / L10n

日本語 / англійська / 简体中文 / 繁體中文 / 한국어 / Español / Français / Русский / тощо.
Встановіть `UAGENT_LANG` для перемикання. Перегляньте [ADD_LOCALE.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/ADD_LOCALE.md), щоб додати нову мову.

Переклади цього README доступні в [docs/README.translations.md](https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md).

### 🔒 Зашифровані змінні середовища

Зберігайте ключі та секрети API у `.env.sec` — зашифрованому файлі `.env`.
Керуйте за допомогою `uag_envsec`.

## Конфігурація та деталі

- **Змінні середовища**: [docs/ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/docs/ENVIRONMENT.md)
- **Майстер налаштування**: `python -m uagent.setup_cli`
- **Зашифроване env**: `uag_envsec` — зашифрувати `.env` як `.env.sec`
- **Responses API**: установіть `UAGENT_RESPONSES=1` для режиму Responses API (OpenAI/Azure/Bedrock/OpenRouter/Ollama/Alibaba/LM Studio/Sakana AI). Автоматично ввімкнено для Sakana AI (Fugu).
- **Документація розробника**: [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)
- **Tool flow**: [TOOL_FLOW.md](../src/uagent/docs/TOOL_FLOW.md)
- **Невеликі поради LLM**: [SLM_TIPS.md](https://github.com/awaku7/agentcli/blob/main/docs/SLM_TIPS.md)

## Філософія проекту

uag прагне бути **вашим штучним інтелектом на вашій машині, на ваших умовах.**

- Немає залежності SaaS — працює локально
- Немає прив’язки до постачальника — будь-коли змінюйте
- Немає блокування інтерфейсу користувача — CLI / GUI / Web / A2A
- Немає блокування функцій — розширюйте інструменти та навички

Безкоштовний досвід роботи зі штучним інтелектом, вільний від блокування від постачальника.

### ✨ Create Your Own Tools

Writing a new tool for uag is straightforward — create a single `.py` file with
`TOOL_SPEC` and `run_tool()`, place it in ``UAGENT_EXTERNAL_TOOLS_DIR``, and
it's immediately available. For Rust developers, ship a pre-built `.pyd` with
zero extra dependencies for users.

See [TOOL_CREATOR_GUIDE.uk.md](TOOL_CREATOR_GUIDE.uk.md)
for the step-by-step guide.

## Contributing

Contributions are welcome! Bug reports, feature suggestions, documentation improvements, translations, and pull requests — all appreciated.

- **Issues**: Open a GitHub issue for bugs or feature requests.
- **Pull requests**: Fork the repo, make your changes, and submit a PR. See [DEVELOP.md](../src/uagent/docs/DEVELOP.md) for development setup and guidelines.
- **Translations**: README translations and locale additions are welcome. See [ADD_LOCALE.md](../src/uagent/docs/ADD_LOCALE.md).
- **Tools & Skills**: New tool plugins and Agent Skills can be contributed via the marketplace.

Realtime Голос і AEC3

## Голосовий режим Realtime підтримує повнодуплексний вхід/вихід для мікрофона та динаміка. Якщо серверна частина AEC3 відсутня, uag автоматично встановлює pywebrtc-audio.

```bat
python scheck.py realtime
```

AEC3 використовує фактичний сигнал мікрофона (поблизу) та аудіо, фактично надісланий до динаміка (далекий). Увімкніть діагностику лише під час дослідження проблем зі звуком.

```bat
set UAGENT_REALTIME_AUDIO_DEBUG=1
python scheck.py realtime
```

### OpenAI Realtime Function Calling

OpenAI Realtime підтримує обмежену безпеку інтеграцію Function Calling. Поточний адаптер автоматично надає функцію get_current_time лише для читання. Деструктивні інструменти та елементи керування пристроєм вимагають явного білого списку та процесу підтвердження. Grok realtime використовує окремий адаптер і не використовує цей OpenAI-специфічний шлях Function Calling.
