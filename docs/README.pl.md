<p wyrównanie="centrum">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="logo uag" szerokość="720">
</p>

<h1lay="center">uag — uniwersalna bramka AI</h1>

<p wyrównanie="centrum">
  <b>U</b>niversal <b>A</b>I <b>G</b>ateway — Twoje środowisko, Twoja wolność.
</p>

<p wyrównanie="centrum">
  Operacje plików / Wyszukiwanie w Internecie / Generowanie i analiza obrazów / Ekstrakcja plików PDF i Excel / Kontrola IoT / Integracja MCP<br>
  Ponad 15 dostawców / 3 interfejsy użytkownika / Równoległe wykonywanie narzędzi / Rynek umiejętności agenta
</p>

<p wyrównanie="centrum">
  <a href="https://github.com/awaku7/agentcli">GitHub</a>
  ·
  <a href="https://pypi.org/project/uag/">PyPI</a>
  ·
  <a href="https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md">Przeczytaj to w swoim języku</a>
</p>

---

## Dlaczego uag?

**Uwolnij się od uzależnienia od dostawcy.** Większość asystentów AI wiąże Cię z konkretnym dostawcą lub usługą w chmurze. uag jest inny.

- **Działa lokalnie** na Twoim komputerze. Twoje dane pozostają przy Tobie (z wyjątkiem wywołań API, które wykonujesz).
- **Wolność dostawcy**: OpenAI, Claude, Gemini, DeepSeek, Ollama, Azure, Bedrock... Ponad 15 dostawców, wszyscy dostępni z jednego interfejsu. Przełączaj się między nimi, rekonfigurując zmienne środowiskowe — bez ponownej instalacji i bez migracji.
- **111 narzędzi**: operacje we/wy plików, wyszukiwanie w Internecie, generowanie obrazów, skanowanie urządzeń BLE, integracja z serwerem MCP — przy czym **55 z nich działa równolegle**. Kiedy LLM uruchamia wiele wywołań narzędzi jednocześnie, uag automatycznie wykonuje je za pośrednictwem puli wątków.
- **3 interfejsy użytkownika + A2A**: CLI, GUI, Internet i protokół Agent-Agent. Ten sam silnik, dowolny interfejs.
- **Gotowy na IoT**: SwitchBot, ECHONET Lite, Matter, UPnP — kontroluj swoje urządzenia domowe poprzez sztuczną inteligencję.
- **Umiejętności agenta**: Zainstaluj umiejętności opracowane przez społeczność z rynku. Rozszerzaj uag w nieskończoność.

uag to **Twój asystent AI na Twoich warunkach**. Nie jest powiązany z dostawcą, nie jest powiązany z interfejsem, nie jest powiązany z platformą.

## Szybki start

,,bicie
pip zainstaluj uag
uag
```

Przy pierwszym uruchomieniu kreator instalacji przeprowadzi Cię przez konfigurację dostawcy.
Zobacz [ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md), aby zapoznać się ze wszystkimi zmiennymi środowiskowymi.

## Funkcje

### 🧠 Architektura obejmująca wielu dostawców

OpenAI / Azure / Bedrock / OpenRouter / Ollama / Gemini / Vertex AI / Claude / Grok / NVIDIA / DeepSeek / Alibaba Cloud (Qwen) / KIMI (Moonshot AI) / Xiaomi MiMo / LM Studio

Wszyscy dostawcy korzystają z tego samego zestawu narzędzi i interfejsu. Przełącz, ustawiając `UAGENT_PROVIDER` — bez zmian kodu, bez oddzielnych instalacji.

### ⚡ Równoległe wykonanie narzędzia

Kiedy LLM żąda jednocześnie wielu narzędzi, uag **automatycznie łączy je** zrównolegle.
55 narzędzi jest oznaczonych jako `x_parallel_safe` i uruchamianych jednocześnie poprzez 4-wątkowy `ThreadPoolExecutor`.

**Przykład**: Zapytaj „Sprawdź pogodę w stolicach nordyckich” → LLM uruchamia `search_web` × 5 krajów → wszystkie 5 wyszukiwań przebiega równolegle → wyniki zebrane w jednej partii.

Narzędzia tylko do odczytu (wyszukiwanie plików, obliczanie skrótu, wyświetlanie listy katalogów, tłumaczenie, zapytania do bazy danych itp.) są agresywnie zrównoleglone.

### 🔄 Ciągłość sesji

- **Zmień dostawcę w połowie sesji** z `UAGENT_PROVIDER` — historia rozmów zostaje zachowana.
- **Wczytaj ponownie poprzednie sesje** za pomocą `:load <index>` — rozpocznij od miejsca, w którym przerwałeś.
- **Buforowanie wyników narzędzi** pozwala uniknąć zbędnego ponownego wykonywania, gdy powtarza się to samo wywołanie narzędzia.

### 🛠 111 narzędzi

| Kategoria | Narzędzia |
|---|---|
| **Operacje na plikach** | odczyt/zapis/tworzenie/usuwanie/wyszukiwanie/grep/hash/zip |
| **Sieć** | fetch_url, search_web, zrzut ekranu, przeglądarka_playwright |
| **Media** | generuj obraz_obraz_analizuj, img2img, mowa_audio, transkrypcja_audio |
| **Dokumenty** | Ekstrakcja PDF/PPTX/DOCX/RTF/ODT, ekstrakcja strukturalna Excel |
| **IoT** | SwitchBot (Cloud + BLE), ECHONET Lite, Materia, UPnP |
| **Narzędzia deweloperskie** | git_ops, python_compile, lint_format, run_tests, db_query |
| **MCP** | Połącz się z zewnętrznymi serwerami MCP, wyświetl listę narzędzi, wykonaj |
| **A2A** | Komunikacja agent-agent (z innymi instancjami uag lub serwerami kompatybilnymi z A2A) |
| **System** | env vars, specyfikacje systemu, czas, obliczanie daty |

### 🖥 3 interfejsy + A2A

| Tryb | Polecenie | Cel |
|---|---|---|
| **CLI** | `uag` | Szybka obsługa terminalowa |
| **GUI** | `uagg` | Interfejs użytkownika komputera stacjonarnego za pośrednictwem tkinter |
| **Sieć** | `uagw` | Dostęp przez przeglądarkę |
| **Serwer A2A** | `uaga` | Protokół Agent2Agent do komunikacji wieloagentowej |

### 🏠 Kontrola urządzeń IoT

- **SwitchBot**: Kontrola wsadowa w chmurze i skanowanie/kontrola BLE
- **ECHONET Lite**: odkrywaj i kontroluj urządzenia gospodarstwa domowego (klimatyzację, oświetlenie, podgrzewacze wody itp.) w sieci lokalnej
- **Materia**: Kontrola topologii kontrolera/mostka/urządzenia w trybie tylko do odczytu
- **UPnP**: wykrywanie urządzeń i przekierowywanie portów IGD

Zobacz [IOT_USECASE.md](https://github.com/awaku7/agentcli/blob/main/IOT_USECASE.md)

### 🎯 Rynek umiejętności agentów

`:skills mp_search`, aby przeglądać [SkillsMP](https://skillsmp.com) i [ClawHub](https://clawhub.ai) w poszukiwaniu umiejętności społeczności.
Instaluj i rozszerzaj możliwości uag w locie.

### 🧩 Menedżer stanu partii

uag może śledzić postęp długotrwałych zadań obejmujących wiele plików. Gdy LLM przetwarza dziesiątki plików, „stan_wsadowy” utrwala na dysku listę plików oczekujących, ukończonych i zakończonych niepowodzeniem. Jeśli sesja dobiegnie końca lub upłynie limit czasu rundy, następna runda zostanie wznowiona od miejsca, w którym została przerwana – nic nie jest stracone.

### 🛡 Człowiek w pętli

`human_ask` pozwala LLM zatrzymać się i poprosić o potwierdzenie przed wykonaniem destrukcyjnych operacji (usunięcie pliku, nadpisanie, polecenia powłoki). Pozostajesz pod kontrolą.

### 🕵️ Automatyzacja przeglądarki i inspektor sieciowy

Dwa uzupełniające się narzędzia oparte na Playwright:

- **browser_playwright**: Automatyzuj prawdziwe sesje przeglądarki — nawiguj, klikaj, wypełniaj formularze, wyodrębniaj dane, obsługuj przepływy wielostronicowe. Działa bez głowy lub z głową.
- **playwright_inspector**: Nagrywaj przejścia przeglądarki, przechwytuj migawki DOM i zrzuty ekranu na każdym kroku. Przydatne do debugowania interakcji internetowych lub kontrolowania zmian stron w czasie.

### 🔄 Dynamiczne ładowanie narzędzi

`tool_catalog` i `tool_load` pozwalają odkrywać i włączać narzędzia w czasie wykonywania.
Nie musisz ładować wszystkiego przy uruchomieniu — aktywuj tylko to, czego potrzebujesz, kiedy tego potrzebujesz.

### 🌐 i18n / L10n

日本語 / angielski / 简体中文 / 繁體中文 / 한국어 / Español / Français / Русский / i więcej.
Ustaw „UAGENT_LANG”, aby przełączyć. Zobacz [ADD_LOCALE.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/ADD_LOCALE.md), aby dodać nowe ustawienia regionalne.

Tłumaczenia tego pliku README są dostępne w [docs/README.translations.md](https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md).

### 🔒 Zaszyfrowane zmienne środowiskowe

Przechowuj klucze i sekrety API w `.env.sec` — zaszyfrowanym pliku `.env`.
Zarządzaj za pomocą `uag_envsec`.

## Konfiguracja i szczegóły

- **Zmienne środowiskowe**: [ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md)
- **Kreator instalacji**: `python -m uagent.setup_cli`
- **Zaszyfrowane env**: `uag_envsec` — szyfruj `.env` jako `.env.sec`
- **Responses API**: Ustaw `UAGENT_RESPONSES=1` dla trybu Responses API (OpenAI/Azure/Bedrock/OpenRouter/Ollama/LM Studio)
- **Dokumentacja programisty**: [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)
- **Małe wskazówki LLM**: [SLM_TIPS.md](https://github.com/awaku7/agentcli/blob/main/SLM_TIPS.md)

## Filozofia projektu

uag pragnie być **twoją sztuczną inteligencją na Twojej maszynie i na Twoich warunkach.**

- Brak zależności SaaS — działa lokalnie
- Brak blokady dostawcy - zmień w dowolnym momencie
- Brak blokady interfejsu użytkownika — CLI / GUI / Web / A2A
- Brak blokowania funkcji — rozszerzanie o narzędzia i umiejętności

Bezpłatne doświadczenie agenta AI, wolne od uzależnienia od dostawcy.