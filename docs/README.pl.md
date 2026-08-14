<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="720">
</p>

<h1 align="center">uag — uniwersalna bramka AI</h1>

<p align="center">
  <b>U</b>niversal <b>A</b>I <b>G</b>ateway — Twoje środowisko, Twoja wolność.
</p>

<p align="center">
  Operacje na plikach / Wyszukiwanie w sieci / Generowanie i analiza obrazu / Ekstrakcja PDF i Excel / Kontrola IoT / Integracja MCP<br>
  24 providers / 3 interfejsy użytkownika / Równoległe wykonanie narzędzia / Agent Skills rynek
</p>

<p align="center">
  <a href="https://github.com/awaku7/agentcli">GitHub</a>
  ·
  <a href="https://pypi.org/project/uag/">PyPI</a>
  ·
  <a href="README.translations.md">Read this in your language</a>
</p>

______________________________________________________________________

## Dlaczego uag?

**Uwolnij się od uzależnienia od dostawcy.** Większość asystentów AI wiąże Cię z konkretnym dostawcą lub usługą w chmurze. uag jest inny.

- **Działa lokalnie** na Twoim komputerze. Twoje dane pozostają przy Tobie (z wyjątkiem wykonywanych wywołań API).
- **Wolność dostawcy**: OpenAI, Claude, Gemini, DeepSeek, Ollama, Azure, Bedrock, HuggingFace... 21 dostawców, wszyscy dostępni z jednego interfejsu. Przełączaj się między nimi, rekonfigurując zmienne środowiskowe — bez ponownej instalacji i bez migracji.
- **229 narzędzi**: operacje we/wy plików, wyszukiwanie w Internecie, generowanie obrazów, Gmail, skanowanie urządzeń BLE, integracja z serwerem MCP — **130 jest bezpiecznych w trybie równoległym** (do 8 jest wykonywanych jednocześnie za pośrednictwem puli wątków, konfigurowalne za pomocą `UAGENT_PARALLEL_WORKERS`). Kiedy LLM uruchamia wiele wywołań narzędzi jednocześnie, uag automatycznie łączy je równolegle.
- **3 interfejsy użytkownika + A2A**: CLI, GUI, Internet i protokół Agent-Agent. Ten sam silnik, dowolny interfejs.
- **Umiejętności agenta**: Zainstaluj umiejętności opracowane przez społeczność z rynku. Rozszerzaj uag w nieskończoność.

uag to **Twój asystent AI na Twoich warunkach**. Nie jest powiązany z dostawcą, nie jest powiązany z interfejsem, nie jest powiązany z platformą.

## Szybki start

```bash
pip install uag
uag
```

Przy pierwszym uruchomieniu kreator instalacji przeprowadzi Cię przez konfigurację dostawcy.
Zobacz [docs/ENVIRONMENT.md](ENVIRONMENT.md), aby zapoznać się ze wszystkimi zmiennymi środowiskowymi.

## Cechy

### 🧠 Architektura wielu dostawców

OpenAI / PFN (PLaMo) / Azure / Bedrock / OpenRouter / Ollama / Gemini / Vertex AI / Claude / Grok / NVIDIA / Novita / DeepSeek / Z.AI (Zhipu AI) / HuggingFace / Alibaba Cloud (Qwen) / KIMI (Moonshot AI) / Xiaomi MiMo / LM Studio / MiniMax / Sakana AI (Fugu) / SAKURA AI Engine / Together AI / Vercel AI Gateway

Wszyscy dostawcy korzystają z tego samego zestawu narzędzi i interfejsu. Przełącz, ustawiając `UAGENT_PROVIDER` — bez zmian kodu, bez oddzielnych instalacji.

### ⚡ Równoległe wykonanie narzędzia

Kiedy LLM żąda jednocześnie wielu narzędzi, uag **automatycznie porównuje je**.
130 narzędzi jest oznaczonych jako `x_parallel_safe` i są wykonywane współbieżnie poprzez `ThreadPoolExecutor` (domyślnie 8 wątków; ustaw `UAGENT_PARALLEL_WORKERS`, aby zmienić).

**Przykład**: Zapytaj „Sprawdź pogodę w stolicach nordyckich” → LLM uruchamia `search_web` × 5 krajów → wszystkie 5 wyszukiwań przebiega równolegle → wyniki zebrane w jednej partii.

Narzędzia tylko do odczytu (wyszukiwanie plików, obliczanie skrótu, wyświetlanie listy katalogów, tłumaczenie, zapytania do bazy danych itp.) są agresywnie zrównoleglone.

### 🧩 System wtyczek (zgodny z Claude Code)

uagent implementuje system wtyczek zgodny z Claude Code. Wtyczki łączą umiejętności, agentów, serwery MCP, hooki i inne elementy w samodzielnych katalogach z manifestem `.claude-plugin/plugin.json`.

**Obsługiwane komponenty: umiejętności, podagenci, serwery MCP, hooki (12 zdarzeń cyklu życia), polecenia ukośnikowe, style wyjścia, userConfig, zależności, kanały, marketplace**

**CLI commands**:

```
:plugin list                         # Lista zainstalowanych wtyczek
:plugin install <source> [--scope]
:plugin install <name>@<marketplace>  # Instalacja z marketplace
:plugin remove <name>                # Odinstaluj
:plugin enable/disable <name>        # Przełącz
:plugin marketplace add/remove/list  # Zarządzaj marketplace
:plugin init <name>                  # Utwórz szkielet nowej wtyczki
```

Pełna dokumentacja zawiera więcej szczegółów. [DEVELOP_PLUGIN.md](../src/uagent/docs/DEVELOP_PLUGIN.md)

### 🔄 Ciągłość sesji

- **Zmiana dostawcy w trakcie sesji** za pomocą `UAGENT_PROVIDER` — historia rozmowy zostaje zachowana.
- **Ponowne wczytanie poprzednich sesji** za pomocą `:load <index>` — kontynuuj od miejsca, w którym przerwano.

### 🛠 229 narzędzi

| Kategoria | Narzędzia |
|---|---|
| **Operacje na plikach** | odczyt/zapis/utwórz/usunięcie/wyszukiwanie/grep/hash/zip, file_type, parse_eml (pliki .eml) |
| **Sieć** | fetch_url, search_web, zrzut ekranu, przeglądarka_playwright |
| **Media** | generuj obraz_obraz_analizuj, img2img, mowa_audio, transkrypcja_audio |
| **Dokumenty** | Ekstrakcja PDF/PPTX/DOCX/RTF/ODT, ekstrakcja strukturalna Excel |
| **Prognoza** | Prognozowanie szeregów czasowych z 9 modelami (AutoARIMA, Prophet, LightGBM, CatBoost, TimesFM itp.), automatyczny wybór modelu, generowanie wykresów, i18n |
| **Komunikacja** | gmail_send, gmail_read, bluesky, discord_channel, team_webhook , **pybitchat** (BLE Mesh) — zobacz [COMMUNICATION.md](COMMUNICATION.md) and [BITCHAT.md](BITCHAT.md)|
| **IoT** | BACnet、Modbus TCP、OPC UA、SwitchBot（Cloud + BLE）、ECHONET Lite、Matter、UPnP、reverse_geocode |
| **Interfejsy API chmury** | `aws_api`, `gcp_api`, `azure_api` — AWS, Google Cloud, and Azure API operations; write operations require explicit confirmation |
| **Narzędzia deweloperskie** | git_ops, python_compile, lint_format, run_tests, db_query, **29 nawigatorów kodu źródłowego (rodzina idx)** |
| **MCP** | Połącz się z zewnętrznymi serwerami MCP, wyświetl listę narzędzi, wykonaj — [OAuth / Proxy guide](MCP_OAUTH_PROXY_GUIDE.md) |
| **A2A** | Komunikacja agent-agent (z innymi instancjami uag lub serwerami kompatybilnymi z A2A) |
| **System** | env vars, specyfikacje systemu, czas, obliczanie daty, uuid_gen, slugify, quantities ||
| **Nawigacja źródłowa** | **29 narzędzi idx** dla Pythona, PHP, TypeScript, Java, C#, Dart, C/C++, Rust, Go, Swift, Kotlin, COBOL, VBA, LotusScript, Makefile — uzyskaj indeks funkcji/klasy lub konkretną definicję bez czytania całego pliku |

#### Przegląd i pokrycie repozytorium

- `git_review`: podsumowanie zmian w Git, ryzykownych plikach, kandydatów do testów i tajnych ustaleń bez ujawniania tajnych wartości.
- `security_scan`: skanowanie plików repozytorium pod kątem prawdopodobnych sekretów i ryzykownych plików konfiguracyjnych.
- `coverage_report`: uruchamianie i normalizowanie pokrycia dla Pythona, TypeScript/JavaScript, Rust, Go, Java/Kotlin, .NET, C/C++, Ruby, PHP, Swift i Dart/Flutter.
- Brakujące zależności zasięgu można zainstalować automatycznie, gdy zażądane zostanie wykonanie; `dry_run` nigdy nie instaluje pakietów.

Zobacz [Narzędzia analizy repozytorium] (REPOSITORY_TOOLS.md), aby uzyskać parametry, dane wyjściowe i szczegóły dotyczące bezpieczeństwa.

### 🖥 4 interfejsy + rozszerzenie kodu VS

| Tryb | Polecenie | Cel |
|---|---|---|
| **CLI** | `uag` | Szybka obsługa terminalowa |
| **GUI** | `uagg` | Interfejs użytkownika komputera stacjonarnego za pośrednictwem tkinter |
| **Sieć** | `uagw` | Dostęp przez przeglądarkę |
| **Serwer A2A** | `uaga` | Protokół Agent2Agent do komunikacji wieloagentowej |
| **Kod VS** | — | [Rozszerzenie](VSCODE.md) z panelem czatu, wyjaśnianiem, refaktoryzacją, naprawianiem błędów i widokiem drzewa narzędzi |

Zobacz [VSCODE.md](VSCODE.md), aby uzyskać szczegółowe informacje na temat rozszerzenia VS Code — instalacji, poleceń, przypisań klawiszy i konfiguracji.

### 🏠 Kontrola urządzeń IoT

- **Materia**: Kontrola topologii kontrolera/mostka/urządzenia w trybie tylko do odczytu

Zobacz [IOT_USECASE.md](IOT_USECASE.md)

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

Pełną dokumentację znajdziesz w [README_AUTO.md](README_AUTO.md).

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

Naciśnij klawisz `x`, aby wyjść z trybu autopilota (patrz [README_AUTO.md](README_AUTO.md)).

### 🕵️ Automatyzacja przeglądarki i inspektor sieciowy

Dwa uzupełniające się narzędzia oparte na Playwright:

- **browser_playwright**: Automatyzuj prawdziwe sesje przeglądarki — nawiguj, klikaj, wypełniaj formularze, wyodrębniaj dane, obsługuj przepływy wielostronicowe. Działa bez głowy lub z głową.
- **playwright_inspector**: Nagrywaj przejścia przeglądarki, przechwytuj migawki DOM i zrzuty ekranu na każdym kroku. Przydatne do debugowania interakcji internetowych lub kontrolowania zmian stron w czasie.

### 🔄 Dynamiczne ładowanie narzędzi

`tool_catalog` i `tool_load` pozwalają odkrywać i włączać narzędzia w czasie wykonywania.
Nie musisz ładować wszystkiego przy uruchomieniu — aktywuj tylko to, czego potrzebujesz, kiedy tego potrzebujesz.

### 🦀 Rust Native Tools

`uuid_gen` i `slugify` zaimplementowano w Rust (przez PyO3) dla lepszej wydajności.

### 🌐 i18n / L10n

日本語 / angielski / 简体中文 / 繁體中文 / 한국어 / Español / Français / Русский / i więcej.
Ustaw „UAGENT_LANG”, aby przełączyć. Zobacz [ADD_LOCALE.md](../src/uagent/docs/DEVELOP_I18N.md), aby dodać nowe ustawienia regionalne.

Tłumaczenia tego pliku README są dostępne w [docs/README.translations.md](README.translations.md).

### 🔒 Zaszyfrowane zmienne środowiskowe

Przechowuj klucze i sekrety API w `.env.sec` — zaszyfrowanym pliku `.env`.
Zarządzaj za pomocą `uag_envsec`.

## Konfiguracja i szczegóły

- **Zmienne środowiskowe**: [docs/ENVIRONMENT.md](ENVIRONMENT.md)
- **Kreator instalacji**: `python -m uagent.setup_cli`
- **Zaszyfrowane env**: `uag_envsec` — szyfruj `.env` jako `.env.sec`
- **API odpowiedzi**: Ustaw `UAGENT_RESPONSES=1` dla trybu API odpowiedzi (OpenAI/Azure/Bedrock/OpenRouter/Ollama/Alibaba/LM Studio/Sakana AI). Automatycznie włączone dla Sakana AI (Fugu).
- **Dokumentacja programisty**: [DEVELOP.md](../src/uagent/docs/DEVELOP.md)
- **Tool flow**: [TOOL_FLOW.md](../src/uagent/docs/TOOL_FLOW.md)
- **Małe wskazówki LLM**: [SLM_TIPS.md](SLM_TIPS.md)

## Filozofia projektu

uag pragnie być **twoją sztuczną inteligencją na Twojej maszynie i na Twoich warunkach.**

- Brak zależności SaaS — działa lokalnie
- Brak blokady dostawcy - zmień w dowolnym momencie
- Brak blokady interfejsu użytkownika — CLI / GUI / Web / A2A
- Brak blokowania funkcji — rozszerzanie o narzędzia i umiejętności

Bezpłatne doświadczenie agenta AI, wolne od uzależnienia od dostawcy.

### ✨ Twórz własne narzędzia

[pl.md](TOOL_CREATOR_GUIDE.pl.md)
Zapoznaj się tutaj z instrukcją krok po kroku.

## Współtworzenie

Zapraszamy do współpracy! Cenimy zgłoszenia błędów, propozycje funkcji, ulepszenia dokumentacji, tłumaczenia i pull requesty.

- **Issues**: Otwórz problem GitHub w przypadku błędów lub próśb o funkcje.
- **Pull requesty**: Utwórz fork repozytorium, wprowadź zmiany i wyślij PR. Informacje o konfiguracji środowiska i wytycznych znajdziesz w [DEVELOP.md](../src/uagent/docs/DEVELOP.md).

Realtime Głos i AEC3

## Tryb głosowy Realtime obsługuje wejście/wyjście mikrofonu i głośnika w trybie pełnego dupleksu. Jeśli brakuje backendu AEC3, uag automatycznie instaluje pywebrtc-audio.

**Dostawcy czasu rzeczywistego**: OpenAI Realtime, Azure OpenAI GPT Realtime, Google Gemini Live, xAI Grok Voice i Amazon Bedrock Nova Sonic. SDK dwukierunkowego przesyłania strumieniowego Bedrock jest instalowany automatycznie tylko po wybraniu Bedrock.

```bat
python scheck.py realtime
```

AEC3 wykorzystuje rzeczywisty sygnał mikrofonu (w pobliżu) i dźwięk faktycznie wysyłany do głośnika (daleko). Włącz diagnostykę tylko podczas sprawdzania problemów z dźwiękiem.

```bat
set UAGENT_REALTIME_AUDIO_DEBUG=1
python scheck.py realtime
```

### OpenAI Realtime Function Calling

OpenAI Realtime obsługuje integrację Function Calling z ograniczeniami bezpieczeństwa. Bieżący adapter automatycznie udostępnia funkcję tylko do odczytu get_current_time. Destrukcyjne narzędzia i kontrola urządzeń wymagają jawnej listy dozwolonych i przepływu potwierdzeń. Grok Realtime korzysta z oddzielnego adaptera i nie używa tej ścieżki Function Calling specyficznej dla OpenAI.

## Architecture and operational invariants

See [ARCHITECTURE.md](ARCHITECTURE.md) for the durable implementation contracts covering A2A lifecycle, I18N contexts, optional dependency installation, tool safety, provider capabilities, OAuth trust boundaries, structured events, and acceptance verification.
