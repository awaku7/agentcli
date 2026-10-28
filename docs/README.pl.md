<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="UAG — Universal AI Gateway" width="620">
</p>
<h1 align="center">UAG</h1>
<p align="center"><strong>Universal AI Gateway</strong><br>Twoje modele AI. Twoje narzędzia. Twoje środowisko.</p>

<p align="center">
  <a href="https://github.com/awaku7/agentcli/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/awaku7/agentcli/ci.yml?style=flat-square&label=CI" alt="CI"></a>
  <a href="https://pypi.org/project/uag/"><img src="https://img.shields.io/pypi/v/uag?style=flat-square" alt="PyPI"></a>
  <a href="https://pypi.org/project/uag/"><img src="https://img.shields.io/pypi/pyversions/uag?style=flat-square" alt="Python versions"></a>
  <a href="../LICENSE"><img src="https://img.shields.io/github/license/awaku7/agentcli?style=flat-square" alt="License"></a>
  <a href="https://pepy.tech/projects/uag"><img src="https://static.pepy.tech/personalized-badge/uag?period=total&units=INTERNATIONAL_SYSTEM&left_color=grey&right_color=green&left_text=downloads" alt="Downloads"></a>
</p>
<p align="center"><a href="../README.md">English</a> · <a href="README.translations.md">Inne języki</a></p>

---

**UAG to otwarte środowisko uruchomieniowe agentów AI, w którym priorytetem jest działanie lokalne.** Łączy wybrany model językowy z narzędziami i systemami, których używasz. Pozwala obsługiwać kod, pliki, przeglądarki, usługi i urządzenia w jednym interfejsie, bez uzależniania procesów od jednego dostawcy modeli.

| **Wybierz model** | **Połącz rzeczywiste narzędzia** | **Zachowaj kontrolę** |
| :--- | :--- | :--- |
| Modele chmurowe i lokalne, takie jak OpenAI, Claude, Gemini, Grok, Bedrock i Ollama | Pliki, kod, WWW, MCP, Agent Skills, wtyczki, chmura i IoT | Lokalne wykonywanie, potwierdzanie przez człowieka, przechowywanie danych uwierzytelniających i konfigurowalne zasady |

> UAG to **warstwa wykonywania agentów, a nie dostawca modeli**. Żądania do zewnętrznych modeli i usług zależą od konfiguracji. Priorytet lokalnego działania nie oznacza, że UAG domyślnie pracuje całkowicie offline ani że wszystkie narzędzia są izolowane.

## Szybki start
<!-- README-SYNC:quick-start -->

Wymagany jest **Python 3.11 lub nowszy**. Zainstaluj UAG z [PyPI](https://pypi.org/project/uag/) i uruchom interfejs wiersza poleceń:

~~~bash
python -m pip install --upgrade uag
uag
~~~

Przy pierwszym uruchomieniu kreator pomaga wybrać dostawcę modelu i skonfigurować dane uwierzytelniające. Możesz również użyć zmiennych środowiskowych albo magazynu poświadczeń. Aby od razu zainstalować więcej zależności dostawców i narzędzi:

~~~bash
python -m pip install "uag[core,providers,tools]"
~~~

Następnie spróbuj takich poleceń:

~~~text
> Co zmieniło się w tym repozytorium Git? Podsumuj zagrożenia.
> Znajdź najnowszą dokumentację tej biblioteki i wyjaśnij migrację.
> Sprawdź te pliki i sporządź zwięzły raport.
> :help
~~~

Osobom początkującym polecamy instrukcję instalacji dla Windows, obejmującą Git i środowiska wirtualne, oraz dokumentację konfiguracji: [Quickstart (Windows)](QUICKSTART.md) · [Environment](ENVIRONMENT.md).

## Interfejsy
<!-- README-SYNC:interfaces -->

Wszystkie interfejsy wykorzystują to samo środowisko agentów i ten sam rejestr narzędzi.

| Interfejs | Uruchomienie | Zastosowanie |
| :--- | :--- | :--- |
| **CLI** | `uag` | Praca terminalowa i automatyzacja |
| **Desktop** | `uagg` | Rozmowy w aplikacji natywnej |
| **Web** | `uagw` | Rozmowy i pokoje w przeglądarce |
| **A2A** | `uaga` | Integracja agentów |
| **VS Code** | [Instrukcja rozszerzenia](VSCODE.md) | Praca z kodem źródłowym |

Interfejsy Desktop i Web wymagają dodatkowych zależności, których nie ma w podstawowej instalacji `uag[core,providers,tools]`:

~~~bash
# Desktop GUI (PySide6 and platform integrations)
python -m pip install "uag[platform]"

# Web UI (authentication dependencies, FastAPI, and Uvicorn)
python -m pip install "uag[web]" fastapi uvicorn
~~~

Serwer Web może też próbować doinstalować FastAPI i Uvicorn podczas uruchamiania. Wcześniejsza instalacja usuwa zależność od automatycznego instalatora. Szczegóły: [CLI usage](USAGE.md) · [Environment](ENVIRONMENT.md).

## Co można zbudować dzięki UAG
<!-- README-SYNC:capabilities -->

| Możliwość | Co zapewnia UAG |
| :--- | :--- |
| **Procesy niezależne od modelu** | Przełączanie dostawców chmurowych i lokalnych przez `UAGENT_PROVIDER` bez przepisywania narzędzi |
| **Kod i pliki** | Nawigacja po repozytoriach, analiza Git, lintowanie, testy, operacje na plikach i automatyzacja przeglądarki |
| **Rozszerzalne narzędzia** | Ponad 200 narzędzi, dynamiczne wyszukiwanie przez `tool_catalog` / `tool_load`, własne narzędzia Python i Rust |
| **Połączeni agenci** | MCP, A2A, wtyczki zgodne z Claude Code, Agent Skills i podagenci |
| **Długotrwałe zadania** | Autopilot, równoległe niezależne odczyty, zadania planowane, przywracanie i trwałe sesje |
| **Nie tylko terminal** | Usługi chmurowe i komunikacyjne, dokumenty, multimedia, głos w czasie rzeczywistym i obsługiwane protokoły IoT |

### Jedno środowisko, wiele integracji
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

**Przykłady obsługiwanych dostawców modeli** znajdują się poniżej. Ustawienia poszczególnych dostawców opisuje dokumentacja środowiska.

**OpenAI · Anthropic · Gemini · Vertex AI · Azure OpenAI · Amazon Bedrock · Grok · DeepSeek · OpenRouter · Ollama · llama.cpp · LM Studio**

[ENVIRONMENT.md](ENVIRONMENT.md)

### Dostosowanie przez skills i wtyczki
<!-- README-SYNC:extensions -->

Rozszerzaj UAG bez modyfikowania rdzenia. Instaluj Agent Skills ze SkillsMP lub ClawHub, podłączaj serwery MCP lub używaj wtyczek zgodnych z Claude Code, zawierających narzędzia, skills, agentów i hooks.

~~~text
:skills mp_search browser automation
:plugin list
:plugin install <source>
:plugin marketplace list
~~~

Własne narzędzia mogą udostępniać `TOOL_SPEC` i `run_tool()`; obsługiwane są też narzędzia oparte na Rust. Pomocne przewodniki: [Tool Creator Guide](../TOOL_CREATOR_GUIDE.md) · [Plugin Development Guide](../src/uagent/docs/DEVELOP_PLUGIN.md) · [MCP OAuth / Proxy](MCP_OAUTH_PROXY_GUIDE.md).

## Stworzone do rzeczywistych zadań
<!-- README-SYNC:workflows -->

### Kontekst i pamięć
<!-- README-SYNC:context-memory -->

Duże wyniki narzędzi można zapisywać jako **artefakty** zamiast przepełniać aktywny kontekst modelu. Później agent odczytuje potrzebny fragment za pomocą `artifact_read`. Sesje są domyślnie przechowywane w SQLite, z wyszukiwaniem historii i jawnym przeglądem pamięci.

- [Context compression](CONTEXT_COMPRESSION.pl.md)
- [Memory](MEMORY.md)
- [Session portability](SESSION_PORTABILITY.md)

### Automatyzacja i współpraca
<!-- README-SYNC:automation -->

UAG obsługuje równoległe niezależne odczyty, koordynację wielu agentów, przywracanie sesji i autopilota do wieloetapowej pracy. Uruchom go przez `:auto`. Naciśnij **F12**, aby przerwać bieżącą odpowiedź i zażądać zatrzymania autopilota.

- [Auto-pilot](README_AUTO.md)
- [Timers and scheduled tasks](SET_TIMER.md)
- [Multi-agent runtime](MULTI_AGENT_RUNTIME.md)

### Bezpieczeństwo i obserwowalność
<!-- README-SYNC:security -->

Wrażliwe działania mogą wymagać zatwierdzenia przez `human_ask`. Dane uwierzytelniające można przechowywać w systemowym menedżerze lub zaszyfrowanym pliku. Interfejs Web obsługuje skonfigurowane logowanie OIDC i kontrolę dostępu. Śledzenie i metryki OpenTelemetry są **opcjonalne**.

- [Enterprise policies](ENTERPRISE_POLICY.md)
- [MXC sandbox](SANDBOX_MXC.md)
- [Remote Web / A2A MXC defaults](REMOTE_MXC_DEFAULT.md)
- [Web identity and rooms](WEB_IDENTITY_MEMORY.md)
- [OpenTelemetry design](UAG_OPENTELEMETRY_DESIGN.md)
- [Developer observability](../src/uagent/docs/DEVELOP_OBSERVABILITY.md)

Są to mechanizmy konfigurowalne i **nie gwarantują**, że wykonanie dowolnego narzędzia odbywa się w odizolowanej piaskownicy. Przed udostępnieniem UAG niezaufanym użytkownikom lub sieciom zapoznaj się z instrukcjami wdrażania i zasad.

### Języki, urządzenia i głos
<!-- README-SYNC:languages -->

UAG udostępnia zasoby dla **38 wersji językowych** (angielski i 37 tłumaczeń), opcjonalne integracje głosowe w trybie pełnego dupleksu oraz narzędzia SwitchBot, Matter, ECHONET Lite, BACnet, Modbus TCP i OPC UA.

- [Translations](README.translations.md)
- [IoT use cases](IOT_USECASE.md)
- [Communication tools](COMMUNICATION.md)

## Dokumentacja
<!-- README-SYNC:documentation -->

Zacznij od tych materiałów, a następnie pogłębiaj wybrane tematy:

| Na początek | Szczegóły |
| :--- | :--- |
| [Quickstart (Windows)](QUICKSTART.md) | [Architecture](ARCHITECTURE.md) |
| [CLI usage](USAGE.md) | [Context management](UAG_CONTEXT_MANAGEMENT_DESIGN.md) |
| [Environment and providers](ENVIRONMENT.md) | [Enterprise policy](ENTERPRISE_POLICY.md) |
| [Agent Skills and plugins](../src/uagent/docs/DEVELOP_PLUGIN.md) | [Tool flow](../src/uagent/docs/TOOL_FLOW.md) |
| [MCP and OAuth](MCP_OAUTH_PROXY_GUIDE.md) | [Computer Use](COMPUTER_USE_IMPLEMENTATION.md) |
| [VS Code extension](VSCODE.md) | [Developer guide](../src/uagent/docs/DEVELOP.md) |

Przejrzyj także pełną dokumentację i inne wersje językowe: [Documentation](./) · [Other languages](README.translations.md).

## Rozwój i współtworzenie
<!-- README-SYNC:contributing -->

~~~bash
git clone https://github.com/awaku7/agentcli.git
cd agentcli
python -m pip install -e ".[core,providers,test]"
~~~

Przed wysłaniem pull requestu zmieniającego **kod Python** uruchom odpowiednie testy i sprawdzenia projektu:

~~~bash
python -m ruff check src tests
python -m black --check src tests
python -m pytest -q .
~~~

Zasady współpracy i przewodnik programisty znajdziesz tutaj. Mile widziane są zgłoszenia, poprawki dokumentacji, narzędzia, tłumaczenia i przemyślane pull requesty: [AGENTS.md](../AGENTS.md) · [Developer guide](../src/uagent/docs/DEVELOP.md).

## Licencja
<!-- README-SYNC:license -->

UAG jest udostępniany na licencji: [Apache License 2.0](../LICENSE).
