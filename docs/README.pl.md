<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="720">
</p>

<h1 align="center">uag — uniwersalna bramka AI</h1>

<p align="center">
  <b>U</b>niversal <b>A</b>I <b>G</b>ateway — Your environment, your freedom.
</p>

<p align="center">
  File ops / Web search / Image generation &amp; analysis / PDF &amp; Excel extraction / IoT control / MCP integration<br>
  15+ providers / 3 UIs / Parallel tool execution / Agent Skills marketplace
</p>

<p align="center">
  <a href="https://github.com/awaku7/agentcli">GitHub</a>
  ·
  <a href="https://pypi.org/project/uag/">PyPI</a>
  ·
  <a href="https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md">Read this in your language</a>
</p>

---

## Dlaczego uag?

**Uwolnij się od uzależnienia od dostawcy.** Większość asystentów AI wiąże Cię z konkretnym dostawcą lub usługą w chmurze. uag jest inny.

- **Runs locally** on your machine. Twoje dane pozostają przy Tobie (z wyjątkiem wywołań API, które wykonujesz).
- **Wolność dostawcy**: OpenAI, Claude, Gemini, DeepSeek, Ollama, Azure, Bedrock, HuggingFace... Ponad 15 dostawców, wszyscy dostępni z jednego interfejsu. Przełączaj się między nimi, rekonfigurując zmienne środowiskowe — bez ponownej instalacji i bez migracji.
- **131 narzędzi**: operacje we/wy plików, wyszukiwanie w Internecie, generowanie obrazów, Gmail, skanowanie urządzeń BLE, integracja z serwerem MCP — **76 jest bezpiecznych w trybie równoległym** (do 8 jest wykonywanych jednocześnie za pośrednictwem puli wątków, konfigurowalne za pomocą `UAGENT_PARALLEL_WORKERS`). Kiedy LLM uruchamia wiele wywołań narzędzi jednocześnie, uag automatycznie łączy je równolegle.
- **3 interfejsy użytkownika + A2A**: CLI, GUI, Internet i protokół Agent-Agent. Same engine, any interface.
- **Gotowy na IoT**: SwitchBot, ECHONET Lite, Matter, UPnP — kontroluj swoje urządzenia domowe poprzez sztuczną inteligencję.
- **Umiejętności agenta**: Zainstaluj umiejętności opracowane przez społeczność z rynku. Rozszerzaj uag w nieskończoność.

uag to **Twój asystent AI na Twoich warunkach**. Nie jest powiązany z dostawcą, nie jest powiązany z interfejsem, nie jest powiązany z platformą.

## Szybki start

```bash
pip install uag
uag
```

Przy pierwszym uruchomieniu kreator instalacji przeprowadzi Cię przez konfigurację dostawcy.
Zobacz [ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md), aby zapoznać się ze wszystkimi zmiennymi środowiskowymi.

## Cechy

### 🧠 Architektura wielu dostawców

OpenAI / Azure / Bedrock / OpenRouter / Ollama / Gemini / Vertex AI / Claude / Grok / NVIDIA / DeepSeek / Z.AI (Zhipu AI) / HuggingFace / Alibaba Cloud (Qwen) / KIMI (Moonshot AI) / Xiaomi MiMo / LM Studio / MiniMax / **Sakana AI (Fugu)**

Wszyscy dostawcy korzystają z tego samego zestawu narzędzi i interfejsu. Przełącz, ustawiając `UAGENT_PROVIDER` — bez zmian kodu, bez oddzielnych instalacji.

### ⚡ Równoległe wykonanie narzędzia

Kiedy LLM żąda jednocześnie wielu narzędzi, uag **automatycznie porównuje je**.
76 narzędzi jest oznaczonych jako `x_parallel_safe` i są wykonywane współbieżnie poprzez `ThreadPoolExecutor` (domyślnie 8 wątków; ustaw `UAGENT_PARALLEL_WORKERS`, aby zmienić).

**Przykład**: Zapytaj „Sprawdź pogodę w stolicach nordyckich” → LLM uruchamia `search_web` × 5 krajów → wszystkie 5 wyszukiwań przebiega równolegle → wyniki zebrane w jednej partii.

Narzędzia tylko do odczytu (wyszukiwanie plików, obliczanie skrótu, wyświetlanie listy katalogów, tłumaczenie, zapytania do bazy danych itp.) są agresywnie zrównoleglone.

### 🔄 Ciągłość sesji

- **Switch providers mid-session** with `UAGENT_PROVIDER` — conversation history is preserved.
- **Reload past sessions** with `:load <index>` — pick up where you left off.
- **Tool result caching** avoids redundant re-execution when the same tool call repeats.

### 🛠 131 narzędzi

| Kategoria | Narzędzia |
|---|---|
| **Operacje na plikach** | odczyt/zapis/utwórz/usunięcie/wyszukiwanie/grep/hash/zip, parse_eml (pliki .eml) |
| **Sieć** | fetch_url, search_web, zrzut ekranu, przeglądarka_playwright |
| **Media** | generuj obraz_obraz_analizuj, img2img, mowa_audio, transkrypcja_audio |
| **Dokumenty** | Ekstrakcja PDF/PPTX/DOCX/RTF/ODT, ekstrakcja strukturalna Excel |
| **Komunikacja** | gmail_send, gmail_read, bluesky, discord_channel, team_webhook — zobacz [COMMUNICATION.md](https://github.com/awaku7/agentcli/blob/main/docs/COMMUNICATION.md) |
| **IoT** | SwitchBot (Cloud + BLE), ECHONET Lite, Materia, UPnP |
| **Narzędzia deweloperskie** | git_ops, python_compile, lint_format, run_tests, db_query, **13 nawigatorów kodu źródłowego (rodzina idx)** |
| **MCP** | Połącz się z zewnętrznymi serwerami MCP, wyświetl listę narzędzi, wykonaj |
| **A2A** | Komunikacja agent-agent (z innymi instancjami uag lub serwerami kompatybilnymi z A2A) |
| **System** | env vars, specyfikacje systemu, czas, obliczanie daty |
| **Nawigacja źródłowa** | **13 narzędzi idx** dla Pythona, PHP, TypeScript, Java, C#, Dart, C/C++, Rust, Go, Swift, Kotlin, COBOL — uzyskaj indeks funkcji/klasy lub konkretną definicję bez czytania całego pliku |

### 🖥 4 interfejsy + rozszerzenie kodu VS

| Tryb | Polecenie | Cel |
|---|---|---|
| **CLI** | `uag` | Szybka obsługa terminalowa |
| **GUI** | `uagg` | Interfejs użytkownika komputera stacjonarnego za pośrednictwem tkinter |
| **Sieć** | `uagw` | Dostęp przez przeglądarkę |
| **Serwer A2A** | `uaga` | Protokół Agent2Agent do komunikacji wieloagentowej |
| **Kod VS** | — | [Rozszerzenie](https://github.com/awaku7/agentcli/blob/main/VSCODE.md) z panelem czatu, wyjaśnianiem, refaktoryzacją, naprawianiem błędów i widokiem drzewa narzędzi |

Zobacz [VSCODE.md](https://github.com/awaku7/agentcli/blob/main/VSCODE.md), aby uzyskać szczegółowe informacje na temat rozszerzenia VS Code — instalacji, poleceń, przypisań klawiszy i konfiguracji.

### 🏠 Kontrola urządzeń IoT

- **SwitchBot**: Kontrola wsadowa w chmurze i skanowanie/kontrola BLE
- **ECHONET Lite**: odkrywaj i kontroluj urządzenia gospodarstwa domowego (klimatyzację, oświetlenie, podgrzewacze wody itp.) w sieci lokalnej
- **Materia**: Kontrola topologii kontrolera/mostka/urządzenia w trybie tylko do odczytu
- **UPnP**: wykrywanie urządzeń i przekierowywanie portów IGD

Zobacz [IOT_USECASE.md](https://github.com/awaku7/agentcli/blob/main/IOT_USECASE.md)

### 🎯 Rynek umiejętności agentów

`:skills mp_search`, aby przeglądać [SkillsMP](https://skillsmp.com) i [ClawHub](https://clawhub.ai) w poszukiwaniu umiejętności społeczności.
Instaluj i rozszerzaj możliwości uag w locie.

### 🤖 Auto-Pilot (`:auto`)

uag może **autonomicznie realizować cel w wielu rundach LLM**. Idealny do złożonych, wieloetapowych zadań wymagających iteracyjnego udoskonalania.

- **Jak to działa**: Każda runda składa się z głównego zapytania (Krok A), po którym następuje ocena recenzenta (Krok B), która decyduje: „UKOŃCZYĆ czy KONTYNUOWAĆ?”
- **Ten sam dostawca, ten sam interfejs API**: w ocenie recenzenta używana jest identyczna ścieżka kodu, jak w głównym zapytaniu — łącznie z obsługą interfejsu API odpowiedzi.
- **Oddzielny sędzia LLM** (opcjonalnie): Ustaw `UAGENT_AP_PROVIDER`, aby używać innego dostawcy/modelu dla recenzenta (np. użyj tańszego modelu do oceniania).
- **Wyjdź w dowolnym momencie**: Naciśnij klawisz „x”, aby zatrzymać natychmiast, nawet w połowie odpowiedzi. Lub pozwól recenzentowi zdecydować, kiedy cel zostanie osiągnięty.
- **Konfigurowalne**: `--max-zaokrągla N` w celu kontroli budżetu.

Pełną dokumentację znajdziesz w [README_AUTO.md](https://github.com/awaku7/agentcli/blob/main/README_AUTO.md).

### 🧩 Menedżer stanu partii

uag może śledzić postęp długotrwałych zadań obejmujących wiele plików. Gdy LLM przetwarza dziesiątki plików, „stan_wsadowy” utrwala na dysku listę plików oczekujących, ukończonych i zakończonych niepowodzeniem. Jeśli sesja dobiegnie końca lub upłynie limit czasu rundy, następna runda zostanie wznowiona od miejsca, w którym została przerwana – nic nie jest stracone.

### 🛡 Człowiek w pętli

`human_ask` pozwala LLM zatrzymać się i poprosić o potwierdzenie przed wykonaniem destrukcyjnych operacji (usunięcie pliku, nadpisanie, polecenia powłoki). Pozostajesz pod kontrolą.

### 🛑 Przerwanie (klawisz C / przycisk Stop)

Zatrzymaj generowanie odpowiedzi LLM w dowolnym momencie i wprowadź polecenie zatrzymania z powrotem do LLM.

| Interfejs | Jak przerwać |
|---|---|
| **CLI** | Naciśnij klawisz „c” podczas przesyłania strumieniowego LLM — bieżąca odpowiedź zostanie zatrzymana, a komunikat „Stop” zostanie wysłany jako wiadomość użytkownika, dzięki czemu LLM odpowiednio zareaguje |
| **Interfejs WWW** | Kliknij czerwony przycisk **■ Zatrzymaj** (pojawia się automatycznie podczas przetwarzania LLM) |
| **GUI pulpitu** | Kliknij czerwony przycisk **■** (pojawia się automatycznie podczas przetwarzania LLM) |

Przerwanie działa jako „szybkie wstrzyknięcie”: zamiast po prostu przerywać, przesyła „Stop” z powrotem do LLM jako komunikat użytkownika, umożliwiając mu eleganckie zakończenie lub potwierdzenie przerwania.

Naciśnij klawisz `x`, aby wyjść z trybu autopilota (patrz [README_AUTO.md](https://github.com/awaku7/agentcli/blob/main/README_AUTO.md)).

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
- **API odpowiedzi**: Ustaw `UAGENT_RESPONSES=1` dla trybu API odpowiedzi (OpenAI/Azure/Bedrock/OpenRouter/Ollama/Alibaba/LM Studio/Sakana AI). Automatycznie włączone dla Sakana AI (Fugu).
- **Dokumentacja programisty**: [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)
- **Małe wskazówki LLM**: [SLM_TIPS.md](https://github.com/awaku7/agentcli/blob/main/SLM_TIPS.md)

## Filozofia projektu

uag pragnie być **twoją sztuczną inteligencją na Twojej maszynie i na Twoich warunkach.**

- Brak zależności SaaS — działa lokalnie
- Brak blokady dostawcy - zmień w dowolnym momencie
- Brak blokady interfejsu użytkownika — CLI / GUI / Web / A2A
- Brak blokowania funkcji — rozszerzanie o narzędzia i umiejętności

Bezpłatne doświadczenie agenta AI, wolne od uzależnienia od dostawcy.
