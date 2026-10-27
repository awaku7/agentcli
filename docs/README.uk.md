<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="UAG — Universal AI Gateway" width="620">
</p>
<h1 align="center">UAG</h1>
<p align="center"><strong>Universal AI Gateway</strong><br>Ваші моделі ШІ. Ваші інструменти. Ваше середовище.</p>

<p align="center">
  <a href="https://github.com/awaku7/agentcli/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/awaku7/agentcli/ci.yml?style=flat-square&label=CI" alt="CI"></a>
  <a href="https://pypi.org/project/uag/"><img src="https://img.shields.io/pypi/v/uag?style=flat-square" alt="PyPI"></a>
  <a href="https://pypi.org/project/uag/"><img src="https://img.shields.io/pypi/pyversions/uag?style=flat-square" alt="Python versions"></a>
  <a href="../LICENSE"><img src="https://img.shields.io/github/license/awaku7/agentcli?style=flat-square" alt="License"></a>
  <a href="https://pepy.tech/projects/uag"><img src="https://static.pepy.tech/personalized-badge/uag?period=total&units=INTERNATIONAL_SYSTEM&left_color=grey&right_color=green&left_text=downloads" alt="Downloads"></a>
</p>
<p align="center"><a href="../README.md">English</a> · <a href="README.translations.md">Інші мови</a></p>

---

**UAG — відкрите середовище виконання ШІ-агентів із пріоритетом локальної роботи.** Воно поєднує обрану мовну модель із потрібними інструментами й системами. Працюйте з кодом, файлами, браузерами, службами та пристроями через єдиний інтерфейс, не прив'язуючи процеси до одного постачальника моделей.

| **Обирайте модель** | **Підключайте інструменти** | **Зберігайте контроль** |
| :--- | :--- | :--- |
| Хмарні та локальні моделі, зокрема OpenAI, Claude, Gemini, Grok, Bedrock і Ollama | Файли, код, веб, MCP, Agent Skills, плагіни, хмарні сервіси та IoT | Локальне виконання, підтвердження людини, сховище облікових даних і налаштовувані політики |

> UAG — **рівень виконання агентів, а не постачальник моделей**. Виклики зовнішніх моделей і сервісів залежать від налаштувань. Пріоритет локальної роботи не гарантує цілковитої автономності від мережі чи ізоляції всіх інструментів.

## Швидкий початок
<!-- README-SYNC:quick-start -->

Потрібен **Python 3.11 або новіший**. Установіть UAG з [PyPI](https://pypi.org/project/uag/) і відкрийте інтерактивний командний рядок:

~~~bash
python -m pip install --upgrade uag
uag
~~~

Під час першого запуску майстер допоможе вибрати постачальника та налаштувати облікові дані. Можна також використати змінні середовища чи захищене сховище. Щоб заздалегідь встановити більше залежностей для моделей та інструментів:

~~~bash
python -m pip install "uag[core,providers,tools]"
~~~

Після цього спробуйте такі запити:

~~~text
> Що змінилося в цьому Git-репозиторії? Підсумуй ризики.
> Знайди найновішу документацію бібліотеки та поясни кроки міграції.
> Перевір ці файли та підготуй стислий звіт.
> :help
~~~

Початківцям радимо посібник зі встановлення Windows, зокрема Git і віртуальних середовищ, та довідник налаштувань: [Quickstart (Windows)](QUICKSTART.md) · [Environment](ENVIRONMENT.md).

## Інтерфейси
<!-- README-SYNC:interfaces -->

Усі інтерфейси використовують єдине середовище агента й реєстр інструментів.

| Інтерфейс | Запуск | Для чого |
| :--- | :--- | :--- |
| **CLI** | `uag` | Термінал та автоматизація |
| **Desktop** | `uagg` | Розмови в настільному застосунку |
| **Web** | `uagw` | Діалоги й кімнати в браузері |
| **A2A** | `uaga` | Взаємодія агентів |
| **VS Code** | [Посібник із розширення](VSCODE.md) | Робота з кодом |

Для Desktop і Web потрібні додаткові залежності, яких немає в початковій установці `uag[core,providers,tools]`:

~~~bash
# Desktop GUI (PySide6 and platform integrations)
python -m pip install "uag[platform]"

# Web UI (authentication dependencies, FastAPI, and Uvicorn)
python -m pip install "uag[web]" fastapi uvicorn
~~~

Вебсервер може спробувати встановити FastAPI та Uvicorn під час запуску. Попереднє встановлення усуває цю залежність. Докладніше: [CLI usage](USAGE.md) · [Environment](ENVIRONMENT.md).

## Що можна зробити з UAG
<!-- README-SYNC:capabilities -->

| Можливість | Що надає UAG |
| :--- | :--- |
| **Незалежні від моделі процеси** | Зміна локальних і хмарних постачальників через `UAGENT_PROVIDER` без переписування інструментів |
| **Код і файли** | Навігація репозиторіями, перевірка Git, lint, тести, файлові операції й автоматизація браузера |
| **Розширювані інструменти** | Понад 200 інструментів, динамічний пошук через `tool_catalog` / `tool_load`, власні інструменти Python і Rust |
| **Пов'язані агенти** | MCP, A2A, сумісні з Claude Code плагіни, Agent Skills і підлеглі агенти |
| **Тривалі задачі** | Автопілот, паралельні незалежні читання, розклад, відновлення й збережені сеанси |
| **Не лише термінал** | Хмара, комунікації, документи, медіа, голос у реальному часі й підтримувані IoT-протоколи |

### Одне середовище виконання, багато інтеграцій
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

**Приклади підтримуваних постачальників моделей** наведено нижче. Особливі налаштування містяться в документації середовища.

### Налаштування за допомогою навичок і плагінів
<!-- README-SYNC:extensions -->

Розширюйте UAG без змін ядра. Установлюйте Agent Skills зі SkillsMP чи ClawHub, підключайте сервери MCP або завантажуйте плагіни, сумісні з Claude Code, з інструментами, навичками, агентами й hooks.

~~~text
:skills mp_search browser automation
:plugin list
:plugin install <source>
:plugin marketplace list
~~~

Власні інструменти можуть надавати `TOOL_SPEC` і `run_tool()`; підтримуються також інструменти на Rust. Посібники: [Tool Creator Guide](../TOOL_CREATOR_GUIDE.md) · [Plugin Development Guide](../src/uagent/docs/DEVELOP_PLUGIN.md) · [MCP OAuth / Proxy](MCP_OAUTH_PROXY_GUIDE.md).

## Для справжніх робочих завдань
<!-- README-SYNC:workflows -->

### Контекст і пам'ять
<!-- README-SYNC:context-memory -->

Великі результати інструментів можна зберігати як **артефакти**, не заповнюючи активний контекст моделі. Пізніше агент читає лише потрібну частину через `artifact_read`. Сеанси типово зберігаються в SQLite з пошуком історії та явним переглядом пам'яті.

- [Context compression](CONTEXT_COMPRESSION.uk.md)
- [Memory](MEMORY.md)
- [Session portability](SESSION_PORTABILITY.md)

### Автоматизація та співпраця
<!-- README-SYNC:automation -->

UAG підтримує паралельні незалежні операції читання, координацію кількох агентів, відновлення сеансів та автопілот для багатоетапної роботи. Запускайте його через `:auto`; **F12** перериває відповідь і запитує зупинку автопілота.

- [Auto-pilot](README_AUTO.md)
- [Timers and scheduled tasks](SET_TIMER.md)
- [Multi-agent runtime](MULTI_AGENT_RUNTIME.md)

### Безпека і спостережуваність
<!-- README-SYNC:security -->

Чутливі дії можуть вимагати підтвердження `human_ask`. Облікові дані можна зберігати в системному менеджері або зашифрованому файлі. Вебінтерфейс підтримує налаштований OIDC-вхід і контроль доступу. Трасування та метрики OpenTelemetry є **необов'язковими**.

- [Enterprise policies](ENTERPRISE_POLICY.md)
- [MXC sandbox](SANDBOX_MXC.md)
- [Remote Web / A2A MXC defaults](REMOTE_MXC_DEFAULT.md)
- [Web identity and rooms](WEB_IDENTITY_MEMORY.md)
- [OpenTelemetry design](UAG_OPENTELEMETRY_DESIGN.md)
- [Developer observability](../src/uagent/docs/DEVELOP_OBSERVABILITY.md)

Ці механізми налаштовуються, але **не гарантують**, що будь-який інструмент виконуватиметься в ізольованій пісочниці. Перед відкриттям UAG недовіреним користувачам чи мережам прочитайте посібники з розгортання та політик.

### Мови, пристрої та голос
<!-- README-SYNC:languages -->

UAG містить ресурси для **38 мовних локалей** (англійська та 37 перекладів), додаткову повнодуплексну голосову інтеграцію й інструменти для SwitchBot, Matter, ECHONET Lite, BACnet, Modbus TCP та OPC UA.

- [Translations](README.translations.md)
- [IoT use cases](IOT_USECASE.md)
- [Communication tools](COMMUNICATION.md)

## Документація
<!-- README-SYNC:documentation -->

Почніть із цих матеріалів і поглиблюйте знання за потреби:

| Почніть тут | Докладніше |
| :--- | :--- |
| [Quickstart (Windows)](QUICKSTART.md) | [Architecture](ARCHITECTURE.md) |
| [CLI usage](USAGE.md) | [Context management](UAG_CONTEXT_MANAGEMENT_DESIGN.md) |
| [Environment and providers](ENVIRONMENT.md) | [Enterprise policy](ENTERPRISE_POLICY.md) |
| [Agent Skills and plugins](../src/uagent/docs/DEVELOP_PLUGIN.md) | [Tool flow](../src/uagent/docs/TOOL_FLOW.md) |
| [MCP and OAuth](MCP_OAUTH_PROXY_GUIDE.md) | [Computer Use](COMPUTER_USE_IMPLEMENTATION.md) |
| [VS Code extension](VSCODE.md) | [Developer guide](../src/uagent/docs/DEVELOP.md) |

Перегляньте також усю документацію та інші переклади: [Documentation](./) · [Other languages](README.translations.md).

## Розробка та внесок
<!-- README-SYNC:contributing -->

~~~bash
git clone https://github.com/awaku7/agentcli.git
cd agentcli
python -m pip install -e ".[core,providers,test]"
~~~

Перед pull request зі змінами **коду Python** виконайте відповідні тести й перевірки проєкту:

~~~bash
python -m ruff check src tests
python -m black --check src tests
python -m pytest -q .
~~~

Правила внесків і посібник розробника наведені нижче. Вітаються повідомлення про помилки, поліпшення документації, інструменти, переклади й цільові pull requests: [AGENTS.md](../AGENTS.md) · [Developer guide](../src/uagent/docs/DEVELOP.md).

## Ліцензія
<!-- README-SYNC:license -->

UAG поширюється за ліцензією: [Apache License 2.0](../LICENSE).
