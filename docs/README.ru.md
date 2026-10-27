<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="UAG — Universal AI Gateway" width="620">
</p>
<h1 align="center">UAG</h1>
<p align="center"><strong>Universal AI Gateway</strong><br>Ваши модели ИИ. Ваши инструменты. Ваша среда.</p>

<p align="center">
  <a href="https://github.com/awaku7/agentcli/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/awaku7/agentcli/ci.yml?style=flat-square&label=CI" alt="CI"></a>
  <a href="https://pypi.org/project/uag/"><img src="https://img.shields.io/pypi/v/uag?style=flat-square" alt="PyPI"></a>
  <a href="https://pypi.org/project/uag/"><img src="https://img.shields.io/pypi/pyversions/uag?style=flat-square" alt="Python versions"></a>
  <a href="../LICENSE"><img src="https://img.shields.io/github/license/awaku7/agentcli?style=flat-square" alt="License"></a>
  <a href="https://pepy.tech/projects/uag"><img src="https://static.pepy.tech/personalized-badge/uag?period=total&units=INTERNATIONAL_SYSTEM&left_color=grey&right_color=green&left_text=downloads" alt="Downloads"></a>
</p>
<p align="center"><a href="../README.md">English</a> · <a href="README.translations.md">Другие языки</a></p>

---

**UAG — открытая среда выполнения ИИ-агентов, ориентированная на локальную работу.** Она соединяет выбранную языковую модель с инструментами и системами, которыми вы пользуетесь. Работайте с кодом, файлами, браузерами, сервисами и устройствами через единый интерфейс, не привязывая процессы к одному поставщику моделей.

| **Выберите модель** | **Подключите инструменты** | **Сохраняйте контроль** |
| :--- | :--- | :--- |
| Облачные и локальные модели, включая OpenAI, Claude, Gemini, Grok, Bedrock и Ollama | Файлы, код, веб, MCP, Agent Skills, плагины, облачные сервисы и IoT | Локальное выполнение, подтверждение человеком, хранение учётных данных и настраиваемые политики |

> UAG — **среда выполнения агентов, а не поставщик моделей**. Обращения к внешним моделям и подключённым службам зависят от конфигурации. Принцип local-first не означает, что всё по умолчанию работает полностью без сети или в изоляции.

## Быстрый старт
<!-- README-SYNC:quick-start -->

Требуется **Python 3.11 или новее**. Установите UAG из [PyPI](https://pypi.org/project/uag/) и запустите интерактивную командную строку:

~~~bash
python -m pip install --upgrade uag
uag
~~~

При первом запуске мастер настройки поможет выбрать поставщика модели и задать учётные данные. Также доступны переменные окружения и хранилище секретов. Чтобы заранее установить расширенный набор зависимостей поставщиков и инструментов:

~~~bash
python -m pip install "uag[core,providers,tools]"
~~~

Затем попробуйте такие запросы:

~~~text
> Что изменилось в этом репозитории Git? Кратко опиши риски.
> Найди актуальную документацию этой библиотеки и объясни шаги миграции.
> Проверь эти файлы и подготовь краткий отчёт.
> :help
~~~

Если вы впервые знакомитесь с UAG, воспользуйтесь инструкцией установки для Windows (включая Git и виртуальное окружение) и справочником настроек: [Quickstart (Windows)](QUICKSTART.md) · [Environment](ENVIRONMENT.md).

## Интерфейсы
<!-- README-SYNC:interfaces -->

Разные способы запуска используют одну среду выполнения агента и общий реестр инструментов.

| Интерфейс | Запуск | Для чего подходит |
| :--- | :--- | :--- |
| **CLI** | `uag` | Работа в терминале и автоматизация |
| **Desktop** | `uagg` | Беседы в настольном приложении |
| **Web** | `uagw` | Диалоги и комнаты в браузере |
| **A2A** | `uaga` | Связь между агентами |
| **VS Code** | [Руководство по расширению](VSCODE.md) | Работа рядом с исходным кодом |

Для настольного и веб-интерфейсов нужны дополнительные зависимости, не входящие в первоначальную установку `uag[core,providers,tools]`:

~~~bash
# Desktop GUI (PySide6 and platform integrations)
python -m pip install "uag[platform]"

# Web UI (authentication dependencies, FastAPI, and Uvicorn)
python -m pip install "uag[web]" fastapi uvicorn
~~~

Веб-сервер может попытаться установить FastAPI и Uvicorn при запуске. Установка заранее позволяет не зависеть от автоматической установки во время работы. Подробнее: [CLI usage](USAGE.md) · [Environment](ENVIRONMENT.md).

## Что можно сделать с UAG
<!-- README-SYNC:capabilities -->

| Возможность | Что предоставляет UAG |
| :--- | :--- |
| **Независимые от модели процессы** | Переключение облачных и локальных поставщиков через `UAGENT_PROVIDER` без переписывания инструментов |
| **Код и файлы** | Навигация по репозиторию, анализ Git, линтеры, тесты, операции с файлами и автоматизация браузера |
| **Расширяемые инструменты** | Более 200 инструментов, динамический поиск через `tool_catalog` / `tool_load`, собственные инструменты на Python и Rust |
| **Связанные агенты** | MCP, A2A, плагины, совместимые с Claude Code, Agent Skills и подагенты |
| **Долгие задачи** | Автопилот, параллельное независимое чтение, задачи по расписанию, восстановление и сохраняемые сеансы |
| **За пределами терминала** | Облачные и коммуникационные сервисы, документы, медиа, голос в реальном времени и поддерживаемые протоколы IoT |

### Одна среда выполнения — множество интеграций
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

**Примеры поддерживаемых поставщиков моделей** приведены ниже. Индивидуальные параметры описаны в справочнике конфигурации.

### Расширение с помощью навыков и плагинов
<!-- README-SYNC:extensions -->

Расширяйте UAG без изменения ядра. Устанавливайте Agent Skills из SkillsMP или ClawHub, подключайте серверы MCP или загружайте плагины, совместимые с Claude Code, включая инструменты, навыки, агентов и хуки.

~~~text
:skills mp_search browser automation
:plugin list
:plugin install <source>
:plugin marketplace list
~~~

Собственные инструменты могут предоставлять `TOOL_SPEC` и `run_tool()`; также поддерживаются инструменты на базе Rust. Начните с руководств: [Tool Creator Guide](../TOOL_CREATOR_GUIDE.md) · [Plugin Development Guide](../src/uagent/docs/DEVELOP_PLUGIN.md) · [MCP OAuth / Proxy](MCP_OAUTH_PROXY_GUIDE.md).

## Для реальных рабочих задач
<!-- README-SYNC:workflows -->

### Контекст и память
<!-- README-SYNC:context-memory -->

Большие результаты работы инструментов можно сохранять как **артефакты**, не перегружая активный контекст модели. Позже агент извлечёт нужный фрагмент через `artifact_read`. По умолчанию сеансы хранятся в SQLite; доступны поиск по истории и явная проверка памяти.

- [Context compression](CONTEXT_COMPRESSION.ru.md)
- [Memory](MEMORY.md)
- [Session portability](SESSION_PORTABILITY.md)

### Автоматизация и совместная работа
<!-- README-SYNC:automation -->

UAG поддерживает параллельные независимые операции чтения, координацию нескольких агентов, восстановление сеансов и автопилот для многоэтапных задач. Запустите его командой `:auto`; клавиша **F12** прерывает текущий ответ и запрашивает остановку автопилота.

- [Auto-pilot](README_AUTO.md)
- [Timers and scheduled tasks](SET_TIMER.md)
- [Multi-agent runtime](MULTI_AGENT_RUNTIME.md)

### Безопасность и наблюдаемость
<!-- README-SYNC:security -->

Для чувствительных операций можно требовать подтверждение `human_ask`. Учётные данные хранятся в системном менеджере секретов или в зашифрованном файле. Веб-интерфейс поддерживает настроенный вход через OIDC и управление доступом. Трассировка и метрики OpenTelemetry **включаются отдельно**.

- [Enterprise policies](ENTERPRISE_POLICY.md)
- [MXC sandbox](SANDBOX_MXC.md)
- [Remote Web / A2A MXC defaults](REMOTE_MXC_DEFAULT.md)
- [Web identity and rooms](WEB_IDENTITY_MEMORY.md)
- [OpenTelemetry design](UAG_OPENTELEMETRY_DESIGN.md)
- [Developer observability](../src/uagent/docs/DEVELOP_OBSERVABILITY.md)

Эти меры можно настраивать; **они не гарантируют**, что любое выполнение инструмента изолировано в песочнице. Перед предоставлением доступа недоверенным пользователям или сетям изучите инструкции по развёртыванию и политикам.

### Языки, устройства и голос
<!-- README-SYNC:languages -->

UAG содержит ресурсы для **38 локалей** (английский и 37 переводов), дополнительные интеграции полнодуплексного голоса и инструменты для SwitchBot, Matter, ECHONET Lite, BACnet, Modbus TCP и OPC UA.

- [Translations](README.translations.md)
- [IoT use cases](IOT_USECASE.md)
- [Communication tools](COMMUNICATION.md)

## Документация
<!-- README-SYNC:documentation -->

Начните с этих материалов и при необходимости переходите к более подробным руководствам:

| С чего начать | Подробнее |
| :--- | :--- |
| [Quickstart (Windows)](QUICKSTART.md) | [Architecture](ARCHITECTURE.md) |
| [CLI usage](USAGE.md) | [Context management](UAG_CONTEXT_MANAGEMENT_DESIGN.md) |
| [Environment and providers](ENVIRONMENT.md) | [Enterprise policy](ENTERPRISE_POLICY.md) |
| [Agent Skills and plugins](../src/uagent/docs/DEVELOP_PLUGIN.md) | [Tool flow](../src/uagent/docs/TOOL_FLOW.md) |
| [MCP and OAuth](MCP_OAUTH_PROXY_GUIDE.md) | [Computer Use](COMPUTER_USE_IMPLEMENTATION.md) |
| [VS Code extension](VSCODE.md) | [Developer guide](../src/uagent/docs/DEVELOP.md) |

Также можно просмотреть весь каталог документации и переводы: [Documentation](./) · [Other languages](README.translations.md).

## Разработка и участие
<!-- README-SYNC:contributing -->

~~~bash
git clone https://github.com/awaku7/agentcli.git
cd agentcli
python -m pip install -e ".[core,providers,test]"
~~~

Перед запросом на изменение **кода Python** запускайте соответствующие тесты и проверки проекта:

~~~bash
python -m ruff check src tests
python -m black --check src tests
python -m pytest -q .
~~~

Правила участия и руководство разработчика приведены ниже. Мы приветствуем сообщения об ошибках, улучшения документации, инструменты, переводы и небольшие целевые запросы на включение изменений: [AGENTS.md](../AGENTS.md) · [Developer guide](../src/uagent/docs/DEVELOP.md).

## Лицензия
<!-- README-SYNC:license -->

UAG распространяется на условиях лицензии: [Apache License 2.0](../LICENSE).
