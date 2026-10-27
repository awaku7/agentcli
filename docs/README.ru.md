<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="680">
</p>

<h1 align="center">uag</h1>

<p align="center">
  <strong>Universal AI Gateway</strong><br>
  Один локальный агент. Любая модель. Любой инструмент. Ваша среда, ваши правила.
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
  <a href="https://github.com/awaku7/agentcli/discussions">Обсуждения</a> ·
  <a href="https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md">Переводы</a>
</p>

______________________________________________________________________

**Зачем нужен uag?**

uag — ИИ-агент с приоритетом локального выполнения, который подключает предпочитаемую вами модель к инструментам, которыми вы действительно пользуетесь.
Он предоставляет единую расширяемую среду выполнения для файлов, браузеров, кодовых баз, коммуникаций, облачных API,
устройств IoT, MCP-серверов и рабочих процессов с несколькими агентами.

- **Свобода выбора провайдера** — OpenAI, Anthropic, Gemini, Azure, Bedrock, Ollama, llama.cpp, Grok, DeepSeek и другие.
- **Локальное выполнение по умолчанию** — среда выполнения агента и выполнение инструментов остаются на вашем компьютере; его покидают только выбранные вами API-вызовы.
- **Единый слой инструментов** — одни и те же инструменты работают из CLI, настольного GUI, веб-интерфейса, VS Code и A2A.
- **Параллельность заложена в основу** — независимые операции только для чтения могут выполняться одновременно.
- **Расширяемость** — добавляйте инструменты, плагины, Agent Skills, MCP-серверы и инструменты на базе Rust без изменения ядра.
- **Безопасность прежде всего** — деструктивные действия, учетные данные, управление устройствами и сетевые записи поддерживают явное подтверждение и политики.

> **Коротко:** uag — это плоскость управления между вашими моделями ИИ и реальной средой.

> **🧠 Результаты работы инструментов с учетом контекста** — Результаты работы инструментов большого объема, по возможности, не включаются в контекст активной модели. uag сохраняет их в виде артефактов и вместо этого передаёт модели ограниченный фрагмент предварительного просмотра со стабильной ссылкой на Artifact. Это может существенно сократить количество входных токенов, необходимых для последующих ходов, когда инструмент генерирует объёмный результат.
> [Подробное руководство по сжатию контекста](CONTEXT_COMPRESSION.ru.md)

## Быстрый старт

**Python 3.11+**

```bash
python -m pip install --upgrade uag
uag
```

При первом запуске открывается мастер настройки. Он помогает настроить провайдера и сохраняет выбранные параметры
в локальной среде.

Для наиболее распространенных групп функций:

```bash
python -m pip install "uag[core,providers,tools]"
```

> Интеграции с платформами являются необязательными. Устанавливайте только то, что нужно вашей операционной системе; см.

```text
> What files changed in this repository?
> Search the web for today's AI news and summarize the top five stories.
> :help
```

[Quickstart](QUICKSTART.md) · [Environment](ENVIRONMENT.md)

## Интерфейсы

| Интерфейс | Команда | Лучше всего подходит для |
|---|---|---|
| **CLI** | `uag` | Быстрой работы с клавиатуры |
| **Настольный GUI** | `uagg` | Нативного настольного интерфейса |
| **Веб-интерфейс** | `uagw` | Доступа через браузер |
| **Сервер A2A** | `uaga` | Взаимодействия между агентами |
| **VS Code** | Extension | Объяснения, рефакторинга, исправления и просмотра инструментов в редакторе |

Все интерфейсы используют общие настройки провайдера, реестр инструментов, правила безопасности и данные сессий.

~~~bash
# Desktop GUI
python -m pip install "uag[platform]"

# Web UI
python -m pip install "uag[web]" fastapi uvicorn
~~~

[Interface options](USAGE.md) · [Environment](ENVIRONMENT.md)

## Что можно создать

Адаптеры провайдеров охватывают облачные и локальные среды выполнения, включая:

**OpenAI · Meta Model API · Anthropic · Google Gemini · Vertex AI · Azure OpenAI · Amazon Bedrock · OpenRouter · Ollama · llama.cpp · Grok · DeepSeek · NVIDIA · Hugging Face · Alibaba Cloud · Moonshot · Xiaomi MiMo · LM Studio · MiniMax · Sakana AI · SAKURA AI Engine · Together AI · Vercel AI Gateway · PFN/PLaMo · Z.AI · Novita**

Переключайте провайдеров с помощью `UAGENT_PROVIDER`; инструменты и интерфейс не изменятся.

**Работа с вашей средой**

- Читать, создавать, редактировать, искать, хешировать, архивировать и проверять файлы
- Просматривать изменения Git, искать секреты, запускать тесты, выполнять линтинг, компиляцию и измерять покрытие
- Работать с большими кодовыми базами на Python, TypeScript, JavaScript, Go, Rust, C/C++, Java, C#, COBOL, VBA и других языках
- Автоматизировать браузеры с Playwright, включая многостраничные процессы и загрузки

**Подключение сервисов и устройств**

- **MCP** — подключение внешних серверов инструментов, включая сервисы с поддержкой OAuth
- **A2A** — координация с другими агентами и совместимыми серверами
- **Cloud** — доступ к API AWS, Google Cloud и Azure с подтверждением операций записи
- **Communication** — Gmail, Bluesky, Discord, Microsoft Teams и pybitchat
- **IoT** — SwitchBot, ECHONET Lite, Matter, BACnet, Modbus TCP, OPC UA и UPnP
- **Media** — генерация и редактирование изображений, транскрибация и синтез речи, захват с камеры и QR-коды
- **Documents** — анализ PDF, PowerPoint, Word, Excel, CSV, JSON, YAML, SQL и журналов

**IoT и управление физическим миром**

- **SwitchBot** — облачное и BLE-обнаружение, состояние, управление, пакетная обработка и подписки
- **ECHONET Lite** — обнаружение и управление японской бытовой техникой, включая уведомления INF
- **Matter** — конечные точки, кластеры, атрибуты, история состояния, подписки и управление
- **BACnet / Modbus TCP / OPC UA** — чтение, запись, просмотр и мониторинг в промышленной автоматизации и автоматизации зданий
- **UPnP** — обнаружение устройств, состояние WAN и управление перенаправлением портов маршрутизатора

### Где находится uag

uag располагается между людьми и интерфейсами, с одной стороны, и моделями, инструментами и реальными системами — с другой.
Он координирует диалог, выбирает возможности, применяет правила безопасности и сохраняет возможность возобновить рабочий процесс.

~~~mermaid
flowchart LR
    UI["CLI · Desktop · Web · VS Code · A2A"] --> UAG["UAG agent runtime"]
    UAG --> MODELS["Hosted & local models"]
    UAG --> TOOLS["Tools & extensions"]
    UAG --> STATE["Sessions & context"]
    TOOLS --> SYSTEMS["Files · Code · Web · MCP · Cloud · IoT"]
    POLICY["Confirmation · Credentials · Policy"] -.-> UAG
~~~

### Плагины, Agent Skills и маркетплейсы

Превратите uag в специализированного агента без ответвления ядра:

- Устанавливайте **плагины, совместимые с Claude Code**, из каталога, ZIP-архива, Git-репозитория, HTTP-источника или маркетплейса
- Объединяйте навыки, субагентов, MCP-серверы, хуки, slash-команды, стили вывода, зависимости и каналы
- Просматривайте возможности сообщества на [SkillsMP](https://skillsmp.com) и [ClawHub](https://clawhub.ai)
- Добавляйте частные навыки и инструменты организации локально через `UAGENT_EXTERNAL_TOOLS_DIR`

```text
:skills mp_search browser automation
:plugin list
:plugin install <source>
:plugin marketplace list
```

См. [Руководство по разработке плагинов](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP_PLUGIN.md).

- **200+ инструментов** для файлов, веба, медиа, документов, кода, облака, коммуникаций и IoT
- **Динамическое обнаружение и загрузка** — используйте `tool_catalog` для поиска возможностей и `tool_load`, чтобы включать их только при необходимости
- **Интеллектуальная работа с кодом** — `code_map`, языковые навигаторы `idx`, проверка Git, запуск тестов, линтинг, компиляция и измерение покрытия
- **Плагины, совместимые с Claude Code**, с навыками, агентами, MCP-серверами, хуками, командами и маркетплейсами
- **Agent Skills** из SkillsMP и ClawHub
- **Пользовательские инструменты Python** с `TOOL_SPEC` и `run_tool()`
- **Инструменты на базе Rust** для легковесных нативных расширений

[Tool Creator Guide](../TOOL_CREATOR_GUIDE.md) · [MCP OAuth / Proxy Guide](MCP_OAUTH_PROXY_GUIDE.md)

## Создано для реальных рабочих процессов

### 🧠 Результаты работы инструментов с учетом контекста

Результаты работы инструментов большого объема, по возможности, не включаются в контекст активной модели. uag сохраняет их в виде артефактов и вместо этого передаёт модели ограниченный фрагмент предварительного просмотра со стабильной ссылкой на Artifact. Это может существенно сократить количество входных токенов, необходимых для последующих ходов, когда инструмент генерирует объёмный результат.

Возобновляйте предыдущие разговоры с помощью `:load <index>`. Результаты инструментов можно кэшировать, а провайдеров можно менять
без пересборки приложения.

[Context compression](CONTEXT_COMPRESSION.ru.md) · [Memory](MEMORY.md) · [Session portability](SESSION_PORTABILITY.md)

### Автопилот

Используйте `:auto` для многоэтапной работы с дополнительной моделью-рецензентом. Ограничьте число раундов с помощью `--max-rounds N`.
Нажмите **F12**, чтобы остановить автопилот, или **F12**, чтобы остановить текущий ответ.

Независимые операции только для чтения выполняются одновременно, если это безопасно. Поиск в интернете, проверка файлов,
анализ репозитория и аналогичные задачи могут выполняться параллельно с настраиваемым пулом
воркеров (`UAGENT_PARALLEL_WORKERS`). Операции записи остаются последовательными или требуют подтверждения.

Непрерывность сессий, кэширование результатов инструментов, состояние пакетных операций, восстановление после перезапуска,
планирование DAG и оркестрация нескольких агентов делают сложную работу возобновляемой, а не одноразовой.

[Auto-pilot](README_AUTO.md) · [Timers](SET_TIMER.md) · [Multi-agent runtime](MULTI_AGENT_RUNTIME.md)

### 🌍 Приватность, мультиязычность и политики

`human_ask` приостанавливает работу перед чувствительными действиями. Удаление и перезапись файлов, команды оболочки, управление устройствами,
операции с учетными данными и сетевые записи могут регулироваться правилами подтверждения и политиками.

Используйте хранилище учетных данных вместо размещения долгосрочных секретов в запросах:

Веб-интерфейс включает вход через OIDC с использованием Authorization Code + PKCE, проверенные ID-токены, серверные сессии и управление доступом к проектам/комнатам. Проверенные групповые утверждения Microsoft Entra ID могут использоваться для политики доступа, основанной на каталоге, при соответствующей настройке. Развертывания Windows Active Directory, OAuth и trusted-proxy могут интегрироваться через явные проверенные адаптеры идентификации; Windows AD требует специфичного для развертывания проверяющего Kerberos/Negotiate и по умолчанию не включён.

uag включает добровольную, независимую от поставщика трассировку OpenTelemetry и метрики для Agent, LLM, инструментов, Context, Memory и операций извлечения. По умолчанию наблюдаемость отключена.

Принцип local-first не означает, что UAG по умолчанию работает полностью офлайн или что все инструменты изолированы. Вызовы внешних моделей и подключённых сервисов зависят от настроек.

- [Enterprise policies](ENTERPRISE_POLICY.md)
- [MXC sandbox](SANDBOX_MXC.md)
- [Remote Web / A2A](REMOTE_MXC_DEFAULT.md)
- [Web identity](WEB_IDENTITY_MEMORY.md)
- [OpenTelemetry](UAG_OPENTELEMETRY_DESIGN.md)

### 🌍 Многоязычный перевод

- `translate_text` поддерживает Google Translate и официальный Python-клиент DeepL при настройках `provider=auto`, `provider=deepl` или `provider=google`.
- Описания инструментов доступны на 37 языках плюс английский (всего 38), с сохранением заполнителей и технических идентификаторов.

Полнодуплексный голос доступен через OpenAI Realtime, Azure OpenAI, xAI Grok Voice, Gemini Live
и Bedrock Nova Sonic, с опциональным эхоподавлением AEC3 и ограниченным правилами безопасности вызовом функций в реальном времени.

[Translations](README.translations.md) · [IoT](IOT_USECASE.md) · [Communication](COMMUNICATION.md)

## Документация

| Тема | Документация |
|---|---|
| Переменные окружения | [docs/ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/docs/ENVIRONMENT.md) |
| Архитектура и инварианты | [docs/ARCHITECTURE.md](https://github.com/awaku7/agentcli/blob/main/docs/ARCHITECTURE.md) |
| Computer Use | [docs/COMPUTER_USE_IMPLEMENTATION.md](https://github.com/awaku7/agentcli/blob/main/docs/COMPUTER_USE_IMPLEMENTATION.md) |
| Инструменты репозитория | [docs/REPOSITORY_TOOLS.md](https://github.com/awaku7/agentcli/blob/main/docs/REPOSITORY_TOOLS.md) |
| Варианты использования IoT | [docs/IOT_USECASE.md](https://github.com/awaku7/agentcli/blob/main/docs/IOT_USECASE.md) |
| Инструменты коммуникации | [docs/COMMUNICATION.md](https://github.com/awaku7/agentcli/blob/main/docs/COMMUNICATION.md) |
| Автопилот | [docs/README_AUTO.md](https://github.com/awaku7/agentcli/blob/main/docs/README_AUTO.md) |
| MCP OAuth / Proxy | [docs/MCP_OAUTH_PROXY_GUIDE.md](https://github.com/awaku7/agentcli/blob/main/docs/MCP_OAUTH_PROXY_GUIDE.md) |
| Расширение VS Code | [docs/VSCODE.md](https://github.com/awaku7/agentcli/blob/main/docs/VSCODE.md) |
| Руководство разработчика | [src/uagent/docs/DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md) |
| Поток инструментов | [src/uagent/docs/TOOL_FLOW.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/TOOL_FLOW.md) |

[Quickstart](QUICKSTART.md) · [Architecture](ARCHITECTURE.md) · [Context management](UAG_CONTEXT_MANAGEMENT_DESIGN.md)

## Разработка и участие

```bash
git clone https://github.com/awaku7/agentcli.git
cd agentcli
python -m pip install -e ".[core,providers,test]"
```

Запустите проверки перед PR:

```bash
python -m ruff check src tests
python -m black --check src tests
python -m pytest -q .
```

Полный рабочий процесс разработки описан в [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md).

Мы приветствуем сообщения об ошибках, идеи функций, улучшения документации, переводы, инструменты, навыки и pull request.
Перед крупными изменениями создайте issue или обсуждение. Ознакомьтесь с [Руководством разработчика](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)
и выполните указанные выше проверки перед отправкой pull request.

## License

Licensed under the [Apache License 2.0](https://github.com/awaku7/agentcli/blob/main/LICENSE).
