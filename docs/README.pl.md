<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="logo uag" width="720">
</p>

<h1 align="center">uag — uniwersalna bramka AI</h1>

<p align="center">
  <b>U</b>niversal <b>A</b>I <b>G</b>ateway — Twoje środowisko, Twoja wolność.
</p>

<p align="center">
  Operacje plików / Wyszukiwanie w Internecie / Generowanie i analiza obrazów / Ekstrakcja plików PDF i Excel / Kontrola IoT / Integracja MCP<br>
  Ponad 15 dostawców / 3 interfejsy użytkownika / Równoległe wykonywanie narzędzi / Rynek umiejętności agenta
</p>

<p align="center">
  <a href="https://github.com/awaku7/agentcli">GitHub</a>
  ·
  <a href="https://pypi.org/project/uag/">PyPI</a>
  ·
  <a href="README.translations.md">Przeczytaj to w swoim języku</a>
</p>

---

## Dlaczego uag?

**Uwolnij się od uzależnienia od dostawcy.** Większość asystentów AI wiąże Cię z konkretnym dostawcą lub usługą w chmurze. uag jest inny.

- **Działa lokalnie** na Twoim komputerze. Twoje dane pozostają przy Tobie (z wyjątkiem wywołań API, które wykonujesz).
- **Wolność dostawcy**: OpenAI, Claude, Gemini, DeepSeek, Ollama, Azure, Bedrock... Ponad 15 dostawców, wszyscy dostępni z jednego interfejsu. Przełączaj się między nimi, rekonfigurując zmienne środowiskowe — bez ponownej instalacji i bez migracji.
- **131 narzędzi**: operacje we/wy plików, wyszukiwanie w Internecie, generowanie obrazów, skanowanie urządzeń BLE, integracja z serwerem MCP — przy czym **76 z nich działa równolegle**. Kiedy LLM uruchamia wiele wywołań narzędzi jednocześnie, uag automatycznie wykonuje je za pośrednictwem puli wątków.
- **4 interfejsy użytkownika + A2A**: CLI, GUI, Internet i protokół Agent-Agent. Ten sam silnik, dowolny interfejs.
- **Gotowy na IoT**: SwitchBot, ECHONET Lite, Matter, UPnP — kontroluj swoje urządzenia domowe poprzez sztuczną inteligencję.
- **Umiejętności agenta**: Zainstaluj umiejętności opracowane przez społeczność z rynku. Rozszerzaj uag w nieskończoność.

uag to **Twój asystent AI na Twoich warunkach**. Nie jest powiązany z dostawcą, nie jest powiązany z interfejsem, nie jest powiązany z platformą.

## Szybki start

```bash
pip install uag
uag
```

Przy pierwszym uruchomieniu kreator instalacji przeprowadzi Cię przez konfigurację dostawcy.
Zobacz [ENVIRONMENT.md](../ENVIRONMENT.md)), aby zapoznać się ze wszystkimi zmiennymi środowiskowymi.

## Funkcje

### 🧠 Architektura obejmująca wielu dostawców

OpenAI / Azure / Bedrock / OpenRouter / Ollama / Gemini / Vertex AI / Claude / Grok / NVIDIA / DeepSeek / HuggingFace / Alibaba Cloud (Qwen) / KIMI (Moonshot AI) / Xiaomi MiMo / LM Studio / MiniMax / **Sakana AI (Fugu)**

Wszyscy dostawcy korzystają z tego samego zestawu narzędzi i interfejsu. Przełącz, ustawiając `UAGENT_PROVIDER` — bez zmian kodu, bez oddzielnych instalacji.

### ⚡ Równoległe wykonanie narzędzia

Kiedy LLM żąda jednocześnie wielu narzędzi, uag **automatycznie łączy je** zrównolegle.
76 narzędzi jest oznaczonych jako `x_parallel_safe` i uruchamianych jednocześnie poprzez 4-wątkowy `ThreadPoolExecutor`.

**Przykład**: Zapytaj „Sprawdź pogodę w stolicach nordyckich” → LLM uruchamia `search_web` × 5 krajów → wszystkie 5 wyszukiwań przebiega równolegle → wyniki zebrane w jednej partii.

Narzędzia tylko do odczytu (wyszukiwanie plików, obliczanie skrótu, wyświetlanie listy katalogów, tłumaczenie, zapytania do bazy danych itp.) są agresywnie zrównoleglone.

### 🔄 Ciągłość sesji

- **Zmień dostawcę w połowie sesji** z `UAGENT_PROVIDER` — historia rozmów zostaje zachowana.
- **Wczytaj ponownie poprzednie sesje** za pomocą `:load <index>` — rozpocznij od miejsca, w którym przerwałeś.
- **Buforowanie wyników narzędzi** pozwala uniknąć zbędnego ponownego wykonywania, gdy powtarza się to samo wywołanie narzędzia.

### 🛠 131 narzędzi

| Kategoria | Narzędzia |
|---|---|
| **Operacje na plikach** | odczyt/zapis/tworzenie/usuwanie/wyszukiwanie/grep/hash/zip |
| **Sieć** | fetch_url, search_web, zrzut ekranu, przeglądarka_playwright |
| **Media** | generuj obraz_obraz_analizuj, img2img, mowa_audio, transkrypcja_audio |
| **Dokumenty** | Ekstrakcja PDF/PPTX/DOCX/RTF/ODT, ekstrakcja strukturalna Excel |
| **IoT** | SwitchBot (Cloud + BLE), ECHONET Lite, Materia, UPnP |
| **Narzędzia deweloperskie**, ****13 narzędzi idx** (Python, PHP, TypeScript, Java, C#, Dart, C/C++, Rust, Go, Swift, Kotlin, COBOL) — uzyskaj indeks funkcji/klas lub konkretną definicję bez czytania całego pliku** | git_ops, python_compile, lint_format, run_tests, db_query, ****13 narzędzi idx** (Python, PHP, TypeScript, Java, C#, Dart, C/C++, Rust, Go, Swift, Kotlin, COBOL) — uzyskaj indeks funkcji/klas lub konkretną definicję bez czytania całego pliku** |
| **MCP** | Połącz się z zewnętrznymi serwerami MCP, wyświetl listę narzędzi, wykonaj |
| **A2A** | Komunikacja agent-agent (z innymi instancjami uag lub serwerami kompatybilnymi z A2A) |
| **System** | env vars, specyfikacje systemu, czas, obliczanie daty |
| **Nawigacja kodu źródłowego** | **13 narzędzi idx** (Python, PHP, TypeScript, Java, C#, Dart, C/C++, Rust, Go, Swift, Kotlin, COBOL) — uzyskaj indeks funkcji/klas lub konkretną definicję bez czytania całego pliku |

### 🖥 3 interfejsy + A2A + VS Code

| Tryb | Polecenie | Cel |
|---|---|---|
| **CLI** | `uag` | Szybka obsługa terminalowa |
| **GUI** | `uagg` | Interfejs użytkownika komputera stacjonarnego za pośrednictwem tkinter |
| **Sieć** | `uagw` | Dostęp przez przeglądarkę |
| **Serwer A2A** | `uaga` | Protokół Agent2Agent do komunikacji wieloagentowej |
| **VS Code** | — | Extension (Chat Panel, Explain, Refactor, Fix Error, Tools Tree View) — see [VSCODE.md](../VSCODE.md)) |

### 🏠 Kontrola urządzeń IoT

- **SwitchBot**: Kontrola wsadowa w chmurze i skanowanie/kontrola BLE
- **ECHONET Lite**: odkrywaj i kontroluj urządzenia gospodarstwa domowego (klimatyzację, oświetlenie, podgrzewacze wody itp.) w sieci lokalnej
- **Materia**: Kontrola topologii kontrolera/mostka/urządzenia w trybie tylko do odczytu
- **UPnP**: wykrywanie urządzeń i przekierowywanie portów IGD

Zobacz [IOT_USECASE.md](../IOT_USECASE.md))

### 🎯 Rynek umiejętności agentów

`:skills mp_search`, aby przeglądać [SkillsMP](https://skillsmp.com) i [ClawHub](https://clawhub.ai) w poszukiwaniu umiejętności społeczności.
Instaluj i rozszerzaj możliwości uag w locie.

### 🤖 Auto-Pilot (`:auto`)

uag can **autonomously pursue a goal across multiple LLM rounds**. Perfect for complex, multi-step tasks that need iterative refinement.

- **How it works**: Each round has a main query (Step A) followed by a reviewer judgment (Step B) that decides "COMPLETE or CONTINUE?"
- **Same provider, same API**: The reviewer judgment uses the identical code path as the main query — including Responses API support.
- **Exit anytime**: Press `x` key to stop immediately, even mid-response. Or let the reviewer decide when the goal is met.
- **Configurable**: `--max-rounds N` to control the budget.

See [README_AUTO.md](../README_AUTO.md)) for full documentation.

### 🧩 Menedżer stanu partii

uag może śledzić postęp długotrwałych zadań obejmujących wiele plików. Gdy LLM przetwarza dziesiątki plików, „stan_wsadowy” utrwala na dysku listę plików oczekujących, ukończonych i zakończonych niepowodzeniem. Jeśli sesja dobiegnie końca lub upłynie limit czasu rundy, następna runda zostanie wznowiona od miejsca, w którym została przerwana – nic nie jest stracone.

### 🛡 Człowiek w pętli

`human_ask` pozwala LLM zatrzymać się i poprosić o potwierdzenie przed wykonaniem destrukcyjnych operacji (usunięcie pliku, nadpisanie, polecenia powłoki). Pozostajesz pod kontrolą.

### 🛑 Interrupt (c-key / Stop button)

Stop LLM response generation at any time and inject a stop command back to the LLM.

| Interface | How to interrupt |
|---|---|
| **CLI** | Press `c` key during LLM streaming -- the current response stops, and `"Stop"` is sent as a user message so the LLM responds accordingly |
| **WEB UI** | Click the red **■ Stop** button (appears automatically during LLM processing) |
| **Desktop GUI** | Click the red **■** button (appears automatically during LLM processing) |

The interrupt works as "prompt injection": instead of just aborting, it feeds `"Stop"` back to the LLM as a user message, allowing it to gracefully conclude or acknowledge the interruption.

Press `x` key to exit auto-pilot mode (see `:auto` command).

### 🕵️ Automatyzacja przeglądarki i inspektor sieciowy

Dwa uzupełniające się narzędzia oparte na Playwright:

- **browser_playwright**: Automatyzuj prawdziwe sesje przeglądarki — nawiguj, klikaj, wypełniaj formularze, wyodrębniaj dane, obsługuj przepływy wielostronicowe. Działa bez głowy lub z głową.
- **playwright_inspector**: Nagrywaj przejścia przeglądarki, przechwytuj migawki DOM i zrzuty ekranu na każdym kroku. Przydatne do debugowania interakcji internetowych lub kontrolowania zmian stron w czasie.

### 🔄 Dynamiczne ładowanie narzędzi

`tool_catalog` i `tool_load` pozwalają odkrywać i włączać narzędzia w czasie wykonywania.
Nie musisz ładować wszystkiego przy uruchomieniu — aktywuj tylko to, czego potrzebujesz, kiedy tego potrzebujesz.

### 🌐 i18n / L10n

日本語 / angielski / 简体中文 / 繁體中文 / 한국어 / Español / Français / Русский / i więcej.
Ustaw „UAGENT_LANG”, aby przełączyć. Zobacz [ADD_LOCALE.md](../src/uagent/docs/ADD_LOCALE.md)), aby dodać nowe ustawienia regionalne.

Tłumaczenia tego pliku README są dostępne w [docs/README.translations.md](README.translations.md)).

### 🔒 Zaszyfrowane zmienne środowiskowe

Przechowuj klucze i sekrety API w `.env.sec` — zaszyfrowanym pliku `.env`.
Zarządzaj za pomocą `uag_envsec`.

## Konfiguracja i szczegóły

- **Zmienne środowiskowe**: [ENVIRONMENT.md](../ENVIRONMENT.md))
- **Kreator instalacji**: `python -m uagent.setup_cli`
- **Zaszyfrowane env**: `uag_envsec` — szyfruj `.env` jako `.env.sec`
- **Responses API**: Ustaw `UAGENT_RESPONSES=1` dla trybu Responses API (OpenAI/Azure/Bedrock/OpenRouter/Ollama/Alibaba/LM Studio/Sakana AI)
- **Dokumentacja programisty**: [DEVELOP.md](../src/uagent/docs/DEVELOP.md))
- **Małe wskazówki LLM**: [SLM_TIPS.md](../SLM_TIPS.md))

## Filozofia projektu

uag pragnie być **twoją sztuczną inteligencją na Twojej maszynie i na Twoich warunkach.**

- Brak zależności SaaS — działa lokalnie
- Brak blokady dostawcy - zmień w dowolnym momencie
- Brak blokady interfejsu użytkownika — CLI / GUI / Web / A2A
- Brak blokowania funkcji — rozszerzanie o narzędzia i umiejętności

Bezpłatne doświadczenie agenta AI, wolne od uzależnienia od dostawcy.