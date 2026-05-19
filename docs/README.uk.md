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
- **Підтримка кількох постачальників**: OpenAI / Azure / Bedrock / OpenRouter / Ollama / Gemini / Vertex AI / Claude / Grok / NVIDIA.
- **Три інтерфейси**:
  - **CLI**: `uag` / `python -m uagent`
  - **GUI**: `uagg` / `python -m uagent.gui`
  - **Web**: `uagw` / `python -m uagent.web`
  - **A2A server**: `uaga` / `python -m uagent.a2a.server`
- **Підтримка MCP**: підключення до зовнішніх MCP tool server.
- **Безперервність сесії**: збереження контексту під час зміни моделі або постачальника.
- **Web Inspector**: збереження переходів у браузері, DOM-знімків і скриншотів за допомогою `playwright_inspector`.
- **Вбудована документація**: читання вбудованих документів за допомогою `uag docs`.

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
- `:skills`: вибрати та завантажити Agent Skills
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
- **Інші переклади README**: [English](https://github.com/awaku7/agentcli/blob/main/README.md) / [日本語](https://github.com/awaku7/agentcli/blob/main/docs/README.ja.md) / [Deutsch](https://github.com/awaku7/agentcli/blob/main/docs/README.de.md) / [Español](https://github.com/awaku7/agentcli/blob/main/docs/README.es.md) / [Français](https://github.com/awaku7/agentcli/blob/main/docs/README.fr.md) / [Italiano](https://github.com/awaku7/agentcli/blob/main/docs/README.it.md) / [한국어](https://github.com/awaku7/agentcli/blob/main/docs/README.ko.md) / [Português](https://github.com/awaku7/agentcli/blob/main/docs/README.pt_BR.md) / [Русский](https://github.com/awaku7/agentcli/blob/main/docs/README.ru.md) / [ไทย](https://github.com/awaku7/agentcli/blob/main/docs/README.th.md) / [简体中文](https://github.com/awaku7/agentcli/blob/main/docs/README.zh_CN.md) / [繁體中文](https://github.com/awaku7/agentcli/blob/main/docs/README.zh_TW.md) / [Polski](https://github.com/awaku7/agentcli/blob/main/docs/README.pl.md) / [Tiếng Việt](https://github.com/awaku7/agentcli/blob/main/docs/README.vi.md) / [Bahasa Indonesia](https://github.com/awaku7/agentcli/blob/main/docs/README.id.md) / [العربية](https://github.com/awaku7/agentcli/blob/main/docs/README.ar.md) / [हिन्दी](https://github.com/awaku7/agentcli/blob/main/docs/README.hi.md) / [Português](https://github.com/awaku7/agentcli/blob/main/docs/README.pt.md) / [Svenska](https://github.com/awaku7/agentcli/blob/main/docs/README.sv.md) / [Norsk bokmål](https://github.com/awaku7/agentcli/blob/main/docs/README.nb.md) / [Suomi](https://github.com/awaku7/agentcli/blob/main/docs/README.fi.md) / [Nederlands](https://github.com/awaku7/agentcli/blob/main/docs/README.nl.md) / [Čeština](https://github.com/awaku7/agentcli/blob/main/docs/README.cs.md) / [Українська](https://github.com/awaku7/agentcli/blob/main/docs/README.uk.md) / [Swahili](https://github.com/awaku7/agentcli/blob/main/docs/README.sw.md) / [Bengali](https://github.com/awaku7/agentcli/blob/main/docs/README.bn.md) / [Persian](https://github.com/awaku7/agentcli/blob/main/docs/README.fa.md) / [Mongolian](https://github.com/awaku7/agentcli/blob/main/docs/README.mn.md) / [Marathi](https://github.com/awaku7/agentcli/blob/main/docs/README.mr.md)
