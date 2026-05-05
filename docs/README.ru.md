<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="720">
</p>

# uag (Локальный ИИ-агент)

uag — это интерактивный агент, который выполняет **команды**, манипулирует **файлами** и читает **различные форматы данных** (PDF/PPTX/Excel и т. д.) на вашем локальном ПК. Он предоставляет три интерфейса: CLI, GUI и Web.

GitHub: https://github.com/awaku7/agentcli

## Установка

Вы можете установить `uag` через pip:

```bash
pip install uag
```

После установки первый запуск `uag` автоматически запустит **интерактивный мастер настройки** для настройки переменных окружения. Подробную информацию о конфигурации и шифровании см. в **[ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md)**.

## Основные возможности

- **Практичный набор инструментов**: Оснащен инструментами для манипуляций с файлами, веб-поиска, извлечения данных (PDF/PPTX/Excel), генерации и анализа изображений — все это выполняется в вашей локальной среде.
- **Поддержка нескольких провайдеров**: Поддерживает OpenAI / Azure / Bedrock / OpenRouter / Ollama / Gemini / Vertex AI / Claude / Grok / NVIDIA.
- **Гибкие интерфейсы**: 
  - **CLI**: `uag` / `python -m uagent`
  - **GUI**: `uagg` / `python -m uagent.gui`
  - **Web**: `uagw` / `python -m uagent.web`
- **MCP (Model Context Protocol)**: Поддержка подключения к внешним серверам инструментов MCP.
- **Непрерывность сессии**: Сохранение контекста беседы даже при смене провайдера или модели.
- **Web Inspector**: Автоматическое сохранение переходов в браузере, DOM и скриншотов с помощью `playwright_inspector`.
- **Встроенная документация**: Мгновенный доступ к подробной внутренней документации с помощью команды `uag docs`.

## Использование

### Запуск и выход
Запустите `uag` из терминала, чтобы начать. Введите `:exit`, чтобы выйти.

### Сервер A2A (Agent2Agent)
Вы можете запустить HTTP-сервер, совместимый с A2A, отдельно от существующих интерфейсов.
```bash
uaga
# или python -m uagent.a2a.server
```

### Примечание по Responses API

Если задать `UAGENT_RESPONSES=1`, Responses API будет использоваться для поддерживаемых провайдеров: OpenAI / Azure / Bedrock / OpenRouter / Ollama.
Gemini / Claude / Vertex AI используют свои нативные пути API и не покрываются Responses API.
Для остальных провайдеров uag возвращается к пути, специфичному для провайдера, или к потоку chat-completions.

См. [ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md) для настроек `UAGENT_A2A_*`, таких как аутентификация, хост, порт, перезагрузка, публичный базовый URL, параллелизм и движок.

### Полезные советы (непрерывность и управление)
- `:tools`: Показать список загруженных инструментов.
- `:logs [n]`: Показать логи сессии (`n` для указания количества записей).
- `:load <index>`: Загрузить прошлую сессию, чтобы возобновить беседу.
- `:skills`: Выбрать и загрузить навыки агента (дополнительные роли или инструкции).
- `:shrink [n]`: Организовать историю, чтобы оставить только последние `n` сообщений для экономии токенов.

## Конфигурация и детали

### Переменные окружения и настройка
Для получения подробных настроек (API-ключи, язык интерфейса `UAGENT_LANG`, настройки сокращения истории и т. д.) см. **[ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md)**.
- **Настройка**: Настройте интерактивно с помощью `python -m uagent.setup_cli`.
- **Шифрование**: Надежно зашифруйте свои файлы `.env` с помощью инструмента `uag_envsec`.
- **Обновление**: Используйте `uag_envsec add --file .env.sec --key NAME --value VALUE`, чтобы добавить или обновить переменную в уже зашифрованном файле.

### Разработчикам и интернационализация
- **Документация для разработчиков**: [`src/uagent/docs/DEVELOP.md`](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)
- **Добавление локалей**: [`src/uagent/docs/ADD_LOCALE.md`](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/ADD_LOCALE.md)
- **README на других языках**: [English](https://github.com/awaku7/agentcli/blob/main/README.md) / [日本語](https://github.com/awaku7/agentcli/blob/main/docs/README.ja.md) / [Deutsch](https://github.com/awaku7/agentcli/blob/main/docs/README.de.md) / [Español](https://github.com/awaku7/agentcli/blob/main/docs/README.es.md) / [Français](https://github.com/awaku7/agentcli/blob/main/docs/README.fr.md) / [Italiano](https://github.com/awaku7/agentcli/blob/main/docs/README.it.md) / [한국어](https://github.com/awaku7/agentcli/blob/main/docs/README.ko.md) / [Português](https://github.com/awaku7/agentcli/blob/main/docs/README.pt_BR.md) / [Русский](https://github.com/awaku7/agentcli/blob/main/docs/README.ru.md) / [ไทย](https://github.com/awaku7/agentcli/blob/main/docs/README.th.md) / [简体中文](https://github.com/awaku7/agentcli/blob/main/docs/README.zh_CN.md) / [繁體中文](https://github.com/awaku7/agentcli/blob/main/docs/README.zh_TW.md) / [Polski](https://github.com/awaku7/agentcli/blob/main/docs/README.pl.md) / [Tiếng Việt](https://github.com/awaku7/agentcli/blob/main/docs/README.vi.md) / [Bahasa Indonesia](https://github.com/awaku7/agentcli/blob/main/docs/README.id.md) / [العربية](https://github.com/awaku7/agentcli/blob/main/docs/README.ar.md) / [हिन्दी](https://github.com/awaku7/agentcli/blob/main/docs/README.hi.md) / [Português](https://github.com/awaku7/agentcli/blob/main/docs/README.pt.md) / [Svenska](https://github.com/awaku7/agentcli/blob/main/docs/README.sv.md) / [Norsk bokmål](https://github.com/awaku7/agentcli/blob/main/docs/README.nb.md) / [Swahili](https://github.com/awaku7/agentcli/blob/main/docs/README.sw.md)
