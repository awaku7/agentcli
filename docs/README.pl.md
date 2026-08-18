\<play="center">
\<img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" szerokość="720">

</p>

<h1 wyrównać="center">uag — uniwersalna sztuczna inteligencja Gateway</h1>

\<play="center">
<b>U</b>niversal <b>A</b>I <b>G</b>ateway — Twoje środowisko, Twoja wolność.

</p>

\<play="center">
Obsługa plików / Wyszukiwanie w Internecie / Generowanie i analiza obrazów / Ekstrakcja plików PDF i Excel / Kontrola IoT / Integracja MCP<br>
24 dostawców / 3 interfejsy użytkownika / Równoległe wykonywanie narzędzi / Rynek umiejętności agenta

</p>

\<play="center">
<a href="https://github.com/awaku7/agentcli">GitHub</a>
·
<a href="https://pypi.org/project/uag/">PyPI</a>
·
<a href="https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md">Read this in your language</a>

</p>

______________________________________________________________________

## Dlaczego uag?

**Uwolnij się od uzależnienia od dostawcy.** Większość asystentów AI wiąże Cię z konkretnym dostawcą lub usługą w chmurze. uag jest inny.

- **Działa lokalnie** na Twoim komputerze. Twoje dane pozostają przy Tobie (z wyjątkiem API połączeń, które wykonujesz).
- **Wolność dostawcy**: OpenAI, Claude, Gemini, DeepSeek, Ollama, Azure, Bedrock, Novita, HuggingFace... 24 dostawców, wszyscy dostępni z jednego interfejsu. Przełączaj się między nimi, konfigurując zmienne środowiskowe — bez ponownej instalacji, bez migracji.
- **222 narzędzia**: operacje we/wy plików, wyszukiwanie w Internecie, generowanie obrazów, Gmail, skanowanie urządzeń BLE, integracja z serwerem MCP — **130 jest oznaczonych statycznie jako bezpieczne** (do 8 wykonywanych jednocześnie za pośrednictwem puli wątków, konfigurowalnych za pomocą `UAGENT_PARALLEL_WORKERS`). Kiedy LLM uruchamia jednocześnie wiele wywołań narzędzi, uag automatycznie łączy je równolegle.
- **3 interfejsy użytkownika + A2A**: interfejs CLI, GUI, Internet i protokół Agent-Agent. Ten sam silnik, dowolny interfejs.
- **Gotowy na IoT**: SwitchBot, ECHONET Lite, Matter, UPnP — kontroluj swoje urządzenia domowe za pomocą sztucznej inteligencji.
- **Umiejętności agenta**: Zainstaluj umiejętności opracowane przez społeczność z rynku. Rozszerzaj uag w nieskończoność.

uag to **Twój asystent AI na Twoich warunkach**. Nie jest powiązany z dostawcą, nie jest powiązany z interfejsem, nie jest powiązany z platformą.

## Szybki start

```bash
pip install uag
uag
```

Przy pierwszym uruchomieniu kreator instalacji przeprowadzi Cię przez konfigurację dostawcy.
Zobacz [docs/ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/docs/ENVIRONMENT.md) dla wszystkich środowisk zmienne.

## Korzystanie z komputera

Korzystanie z komputera jest opcjonalne i obsługuje zarówno widoczne środowisko wykonawcze przeglądarki Playwright
, jak i środowisko wykonawcze komputera stacjonarnego. Po włączeniu oba środowiska wykonawcze są tworzone i rejestrowane;

```bat
set UAGENT_COMPUTER_USE=1
```

Użyj `desktop`, aby zamiast tego wybrać środowisko wykonawcze systemu operacyjnego. Zasoby wykonawcze są
zamykane przy normalnym wyjściu, naciśnięciu Ctrl-C i zamknięciu procesu. Ustaw
`UAGENT_COMPUTER_HEADLESS=1`, aby uzyskać testy CI lub dymu w przeglądarce.
Zobacz [docs/COMPUTER_USE_IMPLEMENTATION.md](docs/COMPUTER_USE_IMPLEMENTATION.md)
więcej informacji na temat integracji i bezpieczeństwa.

## Głos w czasie rzeczywistym i AEC3

Tryb głosu w czasie rzeczywistym obsługuje OpenAI Realtime, Azure OpenAI GPT Realtime, xAI Grok Voice API, Google Gemini Multimodal Live API i Amazon Bedrock Nova Sonic z mikrofonem i głośnikiem w trybie pełnego dupleksu. Wymagany backend `pywebrtc-audio` AEC3 jest instalowany automatycznie, a opcjonalny pakiet SDK do dwukierunkowego przesyłania strumieniowego firmy Bedrock jest instalowany automatycznie tylko po wybraniu dostawcy Bedrock:

```bash
python scheck.py realtime
```

Potok AEC3 odbiera rzeczywisty sygnał z mikrofonu („near”) i dźwięk faktycznie przekazywany do głośnika („daleko”), dzięki czemu asystent potrafi słuchać podczas mówienia. Włącz diagnostykę tylko podczas sprawdzania problemów z dźwiękiem:

```bat
set UAGENT_REALTIME_AUDIO_DEBUG=1
python scheck.py realtime
```

### OpenAI Wywoływanie funkcji w czasie rzeczywistym

OpenAI Realtime obsługuje integrację wywołań funkcji z ograniczeniami bezpieczeństwa. Bieżący adapter czasu rzeczywistego automatycznie udostępnia opcję „get_current_time” tylko do odczytu. Destrukcyjne narzędzia i elementy sterujące urządzeniami nie są ujawniane bez wyraźnej listy dozwolonych i przepływu potwierdzeń. Grok realtime korzysta z oddzielnego adaptera i nie korzysta ze ścieżki wywołań funkcji specyficznej dla OpenAI.

## Funkcje

### 🧠 Architektura wielu dostawców

OpenAI / PFN (PLaMo) / Azure / Bedrock / OpenRouter / Ollama / llama.cpp / Gemini / Vertex AI / Claude / Grok / NVIDIA / Novita / DeepSeek / Z.AI (Zhipu AI) / HuggingFace / Alibaba Cloud (Qwen) / KIMI (Moonshot AI) / Xiaomi MiMo / LM Studio / MiniMax / Sakana AI (Fugu) / SAKURA AI Engine / Together AI / Vercel AI Gateway
Wszyscy dostawcy korzystają z tego samego zestawu narzędzi i interfejsu. Przełącz, ustawiając `UAGENT_PROVIDER` — bez zmian kodu, bez oddzielnych instalacji.

#### Ollama i llama.cpp

Ollama i llama.cpp to oddzielni dostawcy. Ollama korzysta z własnego zarządzania usługami i modelami, podczas gdy `llama.cpp` łączy się z punktem końcowym zgodnym z `llama-server` OpenAI:

```bash
# Ollama
UAGENT_PROVIDER=ollama
UAGENT_OLLAMA_BASE_URL=http://localhost:11434/v1
UAGENT_OLLAMA_DEPNAME=llama3.1
# llama.cpp / llama-server
UAGENT_PROVIDER=llama_cpp
UAGENT_LLAMA_CPP_BASE_URL=http://localhost:8080/v1
UAGENT_LLAMA_CPP_DEPNAME=local-model
UAGENT_LLAMA_CPP_API_KEY=dummy
```

Dostawca llama.cpp korzysta z czatu Ścieżka zgodna z uzupełnieniami. Zachowaj `UAGENT_RESPONSES=0`, chyba że skonfigurowany jest kompatybilny serwer proxy.

### ⚡ Równoległe wykonanie narzędzia

Kiedy LLM żąda jednocześnie wielu narzędzi, uag **automatycznie je łączy**.
130 narzędzi jest statycznie oznaczonych jako `x_parallel_safe` i są wykonywane współbieżnie przez `ThreadPoolExecutor` (8 wątków przez domyślnie; ustaw `UAGENT_PARALLEL_WORKERS` na zmianę).
**Przykład**: Zapytaj „Sprawdź pogodę w stolicach nordyckich” → LLM uruchamia `search_web` × 5 krajów → wszystkie 5 wyszukiwań przebiega równolegle → wyniki zebrane w jednej partii.
Bieżąca liczba opiera się na modułach narzędzi definiujących `TOOL_SPEC` (obecnie 222, w tym 2 narzędzia oparte na rdzy w `src/uagent/tools_rust/`). `http_request` wykorzystuje bezpieczeństwo zależne od metody: wywołania `GET`/`HEAD`/`OPTIONS` mogą działać równolegle, podczas gdy metody zapisu pozostają szeregowe.
Narzędzia tylko do odczytu (wyszukiwanie plików, obliczanie skrótu, wyświetlanie katalogów, tłumaczenie, zapytania do bazy danych itp.) są agresywnie równoległe.

### 🧩 System wtyczek (kompatybilny z kodem Claude)

uagent implementuje wtyczkę kompatybilną z kodem **Claude systemu**. Wtyczki łączą umiejętności, agentów, serwery MCP, hooki i inne elementy w samodzielnych katalogach z manifestem `.claude-plugin/plugin.json`.
**Obsługiwane komponenty**: umiejętności, sub-agenci, serwery MCP, hooki (12 zdarzeń cyklu życia), polecenia ukośnika, style wyjściowe, konfiguracja użytkownika, zależności, kanały, rynki
**CLI polecenia**:

```
:lista wtyczek # Lista zainstalowanych wtyczek
:plugin install <źródło> [--scope] # Zainstaluj (katalog/zip/git/http)
:plugin install <nazwa>@<rynek> # Zainstaluj z rynku
:plugin usuń <nazwa> # Odinstaluj
:włącz/wyłącz wtyczkę <nazwa> # Przełącz
:rynek wtyczek add/remove/list # Zarządzaj rynkiem
:plugin init <nazwa> # Utwórz nową wtyczkę
```

Zobacz [DEVELOP_PLUGIN.md](src/uagent/docs/DEVELOP_PLUGIN.md), aby uzyskać pełną dokumentację.

### 🔄 Ciągłość sesji

- **Zmień dostawców w połowie sesji** z `UAGENT_PROVIDER` — historia rozmów zostaje zachowana.
- **Odśwież poprzednie sesje** za pomocą `:load <index>` — kontynuuj od miejsca, w którym przerwałeś.
- **Buforowanie wyników narzędzi** pozwala uniknąć zbędnego ponownego wykonywania, gdy powtarzane jest wywołanie tego samego narzędzia.

### 🛠 229 narzędzi

| Kategoria | Narzędzia |
|---|---|
| **Operacje na plikach** | odczyt/zapis/utwórz/usunięcie/wyszukiwanie/grep/hash/zip, typ_pliku, parse_eml (pliki .eml), `alias_ścieżki` |
| **Sieć** | fetch_url, search_web, zrzut ekranu, przeglądarka_playwright, `url_alias`, `public_transit_route` ([przewodnik](docs/PUBLIC_TRANSIT_ROUTE.md)) |
| **Media** | generuj_obraz, analizuj_obraz, img2img, audio_speech, audio_transcribe |
| **Dokumenty** | Ekstrakcja PDF/PPTX/DOCX/RTF/ODT, ekstrakcja strukturalna Excel |
| **Prognoza** | Prognozowanie szeregów czasowych z 9 modelami (AutoARIMA, Prophet, LightGBM, CatBoost, TimesFM itp.), automatyczny wybór modelu, generowanie wykresów, i18n |
| **Komunikacja** | gmail_send, gmail_read, bluesky, discord_channel, Teams_webhook, **pybitchat** (BLE Mesh) — zobacz [COMMUNICATION.md](https://github.com/awaku7/agentcli/blob/main/docs/COMMUNICATION.md) i [BITCHAT.md](https://github.com/awaku7/agentcli/blob/main/docs/BITCHAT.md) |
| **IoT** | SwitchBot (Cloud + BLE), ECHONET Lite, Matter, UPnP, Reverse_geocode |
| **Interfejsy API chmury** | `aws_api`, `gcp_api`, `azure_api` — ogólne operacje AWS, Google Cloud i Azure API; operacje zapisu wymagają wyraźnego potwierdzenia |
| **Narzędzia deweloperskie** | workspace_status, git_ops, git_review, security_scan, zasięg_report, python_compile, lint_format, run_tests, db_query, **29 nawigatorów kodu źródłowego (rodzina idx)** |
| **MCP** | Połącz się z zewnętrznymi serwerami MCP, wyświetl listę narzędzi, wykonaj — [Przewodnik OAuth / Proxy](docs/MCP_OAUTH_PROXY_GUIDE.md) |
| **A2A** | Komunikacja agent-agent (z innymi instancjami uag lub serwerami kompatybilnymi z A2A) |
| **System** | env vars, specyfikacje systemu, czas, obliczenie daty, [ilości](docs/QUANTITIES.md), [geodesic_distance](docs/GEODESIC_DISTANCE.md), uuid_gen, slugify |
| **Nawigacja źródłowa** | **29 narzędzi idx** dla Pythona, PHP, TypeScript, Java, C#, Dart, C/C++, Rust, Go, Swift, Kotlin, COBOL, VBA, LotusScript, Makefile — uzyskaj indeks funkcji/klasy lub konkretną definicję bez czytania całego pliku |

#### Przegląd i pokrycie repozytorium

- `workspace_status`: raportowanie gałęzi Git aktywnego obszaru roboczego, zmian, stanu synchronizacji upstream, Python środowisko uruchomieniowe i typowe znaczniki projektów bez modyfikowania plików.
- `git_review`: podsumowanie zmian w Git, ryzykownych plikach, kandydatów do testów i tajnych ustaleń bez ujawniania tajnych wartości.
- `security_scan`: skanowanie plików repozytorium w poszukiwaniu prawdopodobnych sekretów i ryzykownych plików konfiguracyjnych.
- `coverage_report`: uruchamianie i normalizowanie pokrycia dla Pythona, TypeScript/JavaScript, Rust, Go, Java/Kotlin, .NET, C/C++, Ruby, PHP, Swift i Dart/Flutter.
- Brakujące zależności zasięgu można zainstalować automatycznie, gdy zażądane zostanie wykonanie; `dry_run` nigdy nie instaluje pakietów.
  Zobacz [Narzędzia analizy repozytorium] (docs/REPOSITORY_TOOLS.md), aby uzyskać parametry, dane wyjściowe i szczegóły dotyczące bezpieczeństwa.
  Zobacz [Aliasy ścieżek i adresów URL] (docs/PATH_URL_ALIASES.md), aby dowiedzieć się, jak skracać powtarzające się ścieżki plików i adresy URL w argumentach narzędzi.

### 🖥 4 interfejsy + kod VS Rozszerzenie

| Tryb | Polecenie | Cel |
|---|---|---|
| **CLI** | `uag` | Szybka obsługa terminalowa |
| **GUI** | `uagg` | Interfejs użytkownika komputera stacjonarnego za pośrednictwem tkinter |
| **Sieć** | `uagw` | Dostęp przez przeglądarkę |
| **A2A Serwer** | `uaga` | Protokół Agent2Agent do komunikacji wieloagentowej |
| **Kod VS** | — | [Rozszerzenie] (https://github.com/awaku7/agentcli/blob/main/docs/VSCODE.md) z panelem czatu, objaśnieniem, refaktoryzacją, naprawą błędów i widokiem drzewa narzędzi |
Zobacz [VSCODE.md](https://github.com/awaku7/agentcli/blob/main/docs/VSCODE.md), aby uzyskać szczegółowe informacje na temat rozszerzenia VS Code — instalacja, polecenia, przypisania klawiszy i konfiguracja.

### 🏠 Kontrola urządzeń IoT

- **BACnet**: Odczyt/zapis urządzeń BACnet/IP (HVAC, oświetlenie, mierniki mocy). Subskrypcja COV dla powiadomień push
- **Modbus TCP**: Odczyt/zapis rejestrów trzymających/wejściowych i cewek. Monitorowanie zmian w oparciu o odpytywanie
- **OPC UA**: przeglądanie przestrzeni adresowej, odczyt/zapis zmiennych, subskrybowanie zmian danych
- **SwitchBot**: kontrola wsadowa w chmurze i skanowanie/kontrola BLE. Subskrypcja oparta na odpytywaniu
- **ECHONET Lite**: odkrywaj, kontroluj i subskrybuj powiadomienia INF z urządzeń domowych (AC, oświetlenie, podgrzewacze wody itp.)
- **Materia**: kontrola odczytu/zapisu + subskrypcja atrybutów do monitorowania zmiany stanu
- **UPnP**: wykrywanie urządzeń i przekierowywanie portów IGD
  Zobacz [IOT_USECASE.md](https://github.com/awaku7/agentcli/blob/main/docs/IOT_USECASE.md)

### 🎯 Agent Skills Marketplace

`:skills mp_search` do przeglądania [SkillsMP](https://skillsmp.com) i [ClawHub](https://clawhub.ai) umiejętności społeczności.
Instaluj i rozszerzaj możliwości uag na bieżąco.

### 🤖 Auto-Pilot (`:auto`)

uag może **autonomicznie realizować cel w wielu LLM rundach**. Idealny do złożonych, wieloetapowych zadań wymagających iteracyjnego udoskonalania.

- **Jak to działa**: Każda runda składa się z głównego zapytania (krok A), po którym następuje ocena recenzenta (krok B), która decyduje: „UKOŃCZYĆ czy KONTYNUOWAĆ?”
- **Ten sam dostawca, ten sam API**: Ocena recenzenta wykorzystuje tę samą ścieżkę kodu co główne zapytanie — łącznie z obsługą odpowiedzi API.
- **Oddzielny sędzia LLM** (opcjonalnie): Ustaw `UAGENT_AP_PROVIDER`, aby użyć innego dostawcy/modelu dla recenzenta (np. użyj tańszego modelu do oceny).
- **Wyjdź w dowolnym momencie**: Naciśnij klawisz F11, aby zatrzymać natychmiast, nawet w połowie odpowiedzi. Możesz też pozwolić recenzentowi zdecydować, kiedy cel zostanie osiągnięty.
- **Konfigurowalne**: `--max-rounds N` w celu kontrolowania budżetu.
  Zobacz [README_AUTO.md](https://github.com/awaku7/agentcli/blob/main/docs/README_AUTO.md), aby uzyskać pełną dokumentację.

### 🧩 Stan wsadowy Menedżer

uag może śledzić postęp długotrwałych zadań obejmujących wiele plików. Kiedy LLM przetwarza dziesiątki plików, `batch_state` utrwala na dysku listę plików oczekujących, ukończonych i zakończonych niepowodzeniem. Jeśli sesja się zakończy lub upłynie limit czasu rundy, następne uruchomienie zostanie wznowione od miejsca, w którym zostało zatrzymane — nic nie zostanie utracone.

### 🛡 Human-in-the-Loop

`human_ask` pozwala LLM wstrzymać się i poprosić o potwierdzenie przed wykonaniem destrukcyjnych operacji (usunięcie pliku, nadpisanie, polecenia powłoki). Zachowaj kontrolę.

### 🛑 Przerwij (klawisz c / przycisk Stop)

Zatrzymaj generowanie odpowiedzi LLM w dowolnym momencie i wprowadź polecenie zatrzymania z powrotem do LLM.
| Interfejs | Jak przerwać |
|---|---|
| **CLI** | Naciśnij klawisz F12 podczas przesyłania strumieniowego LLM — bieżąca odpowiedź zostanie zatrzymana, a jako wiadomość do użytkownika zostanie wysłany komunikat „Stop”, dzięki czemu LLM odpowiednio zareaguje |
| **Interfejs WWW** | Kliknij czerwony przycisk **■ Zatrzymaj** (pojawia się automatycznie podczas przetwarzania LLM) |
| **GUI pulpitu** | Kliknij czerwony przycisk **■** (pojawia się automatycznie podczas przetwarzania LLM) |
Przerwanie działa jako „wstrzyknięcie monitu”: zamiast po prostu przerywać, przekazuje komunikat „Stop” z powrotem do LLM jako komunikat użytkownika, umożliwiając mu eleganckie zakończenie lub potwierdzenie przerwania.
Naciśnij klawisz F11, aby wyjść z trybu autopilota (patrz [README_AUTO.md](https://github.com/awaku7/agentcli/blob/main/docs/README_AUTO.md)).

### 🕵️ Automatyzacja przeglądarki i inspektor sieciowy

Dwa uzupełniające się narzędzia oparte na Playwright:

- **browser_playwright**: Automatyzuj prawdziwe sesje przeglądarki — nawiguj, klikaj, wypełniaj formularze, wyodrębniaj dane, obsługiwać przepływy wielostronicowe. Działa bez głowy lub z głową.
- **playwright_inspector**: Nagrywaj przejścia przeglądarki, przechwytuj migawki DOM i zrzuty ekranu na każdym kroku. Przydatne do debugowania interakcji internetowych lub kontrolowania zmian stron w czasie.

### 🔄 Dynamiczne ładowanie narzędzi

`tool_catalog` i `tool_load` pozwalają odkrywać i włączać narzędzia w czasie wykonywania.
Nie musisz ładować wszystkiego przy uruchomieniu — aktywuj tylko to, czego potrzebujesz, kiedy tego potrzebujesz.

### 🦀 Zaimplementowano narzędzia natywne dla Rust

`uuid_gen` i `slugify` w Rust (przez PyO3) w celu zwiększenia wydajności.
Ładują bezpośrednio z gotowego pliku `.pyd` — **nie jest wymagana instalacja pip**.
Zewnętrzni programiści mogą również dostarczać narzędzia oparte na Rust: umieść `.pyd` obok
wrappera `.py`, użyj `load_rust_pyd()` z `uagent.tools.rust_helper`, and
użytkownicy otrzymują narzędzie bez żadnych dodatkowych zależności. Zobacz
[TOOL_CREATOR_GUIDE.md](https://github.com/awaku7/agentcli/blob/main/TOOL_CREATOR_GUIDE.md).

### 🌐 i18n / L10n

日本語 / angielski / 简体中文 /繁體中文 / 한국어 / Español / Français / Русский / i więcej.
Ustaw `UAGENT_LANG`, aby przełączyć. Zobacz [ADD_LOCALE.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/ADD_LOCALE.md), aby dodać nowe ustawienia regionalne.
Tłumaczenia tego pliku README są dostępne w [docs/README.translations.md](https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md).

### 🔒 Szyfrowane zmienne środowiskowe

Przechowuj klucze i wpisy tajne API w `.env.sec` — zaszyfrowanym pliku `.env`.
Zarządzaj za pomocą `uag_envsec`.

## Konfiguracja i szczegóły

- **Zmienne środowiskowe**: [docs/ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/docs/ENVIRONMENT.md)
- **Kreator instalacji**: `python -m uagent.setup_cli`
- **Zaszyfrowane środowisko**: `uag_envsec` — szyfruj `.env` jako `.env.sec`
- **Odpowiedzi API**: Ustaw `UAGENT_RESPONSES=1` dla trybu Odpowiedzi API (OpenAI/Azure/Bedrock/OpenRouter/Ollama/Alibaba/LM Studio/Sakana AI). Automatycznie włączona dla Sakana AI (Fugu).
- **Dokumentacja programisty**: [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)
- **Przepływ narzędzi**: [TOOL_FLOW.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/TOOL_FLOW.md) — w jaki sposób narzędzia są wysyłane do LLM (maska gatunku, katalog_narzędzi, GPT-5.4+ natywne wyszukiwanie_narzędzi)
- **Małe LLM wskazówek**: [SLM_TIPS.md](https://github.com/awaku7/agentcli/blob/main/docs/SLM_TIPS.md)

## Filozofia projektu

uag aspiruje do bycia **twoją sztuczną inteligencją na Twojej maszynie i na Twoich warunkach.**

- Brak zależności od SaaS — działa lokalnie
- Brak blokady dostawcy — zmiana w dowolnym momencie
- Brak blokady interfejsu użytkownika — CLI / GUI / Internet / A2A
- Brak blokady funkcji — rozszerzanie za pomocą narzędzi i umiejętności

Bezpłatne doświadczenie agenta AI, wolne od blokada dostawcy.

### ✨ Stwórz własne narzędzia

Napisanie nowego narzędzia dla uag jest proste — utwórz pojedynczy plik `.py` z
`TOOL_SPEC` i `run_tool()`, umieść go w `UAGENT_EXTERNAL_TOOLS_DIR` i
będzie natychmiast dostępny. Programiści Rust powinni dostarczyć użytkownikom wstępnie skompilowany plik .pyd z
zero dodatkowych zależności.

Zobacz [TOOL_CREATOR_GUIDE.md](https://github.com/awaku7/agentcli/blob/main/TOOL_CREATOR_GUIDE.md)
przewodnik krok po kroku.

## Wkład

Wkład jest mile widziany! Raporty o błędach, sugestie dotyczące funkcji, ulepszenia dokumentacji, tłumaczenia i prośby o ściągnięcie — wszystko to mile widziane.

- **Problemy**: Otwórz problem GitHub w przypadku błędów lub próśb o funkcje.
- **Żądania ściągnięcia**: rozwidl repozytorium, wprowadź zmiany i prześlij PR. Zobacz [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md), aby zapoznać się z konfiguracją programowania i wytycznymi.
- **Tłumaczenia**: Tłumaczenia README i dodatki dotyczące ustawień regionalnych są mile widziane. Zobacz [ADD_LOCALE.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/ADD_LOCALE.md).
- **Narzędzia i umiejętności**: Nowe wtyczki narzędzi i umiejętności agenta można udostępniać za pośrednictwem rynku.

### Kontrole programistyczne (przed PR)

Zainstaluj najpierw zależności tylko do testowania. Są one trzymane poza listą zależności środowiska wykonawczego:

```bash
python -m pip install -e ".[test]"
python -m pip install black ruff
```

Uruchom te same kontrole, których używa GitHub Akcje przed wypchnięciem:

```bash
python -m ruff check src testy
python -m black --check src testy
python scripts/tool_json_i18n_batch.py status
python -m pytest -q .
```

Aby uzyskać szybszą iterację lokalną, uruchom tylko te testy, których to dotyczy:

```bash
pytest -q testy/<affected_area>
```

Dodatkowe kontrole, jeśli dotyczy:

\`\`bash
python -m py_compile src/uagent/
mypy src/uagent

```

Po wprowadzeniu zmian w ustawieniach regionalnych (`.po`): `python scripts/compile_locales.py` i `python scripts/po_qc_summary.py`.

Zasady wykonawcze (szczegóły w [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md) §6.1): pomocnicy podbijają zamiast `sys.exit`; host narzędzia zamienia narzędzie `SystemExit`/`Exception` na ciągi błędów, więc pojedyncze narzędzie nie może zakończyć procesu. Szybkie zamykanie systemu podczas uruchamiania pozostaje zamierzone.

## Architektura i niezmienniki operacyjne

Zobacz [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), aby zapoznać się z trwałymi kontraktami obejmującymi cykl życia A2A, konteksty I18N, opcjonalną instalację zależności, bezpieczeństwo narzędzi, możliwości dostawcy, granice zaufania OAuth, zdarzenia strukturalne i weryfikację akceptacji.

## Mechanizm zasad przedsiębiorstwa

Obsługiwane są zasady na poziomie organizacji dotyczące narzędzi, dostawców, danych uwierzytelniających, serwerów MCP, sieci, umiejętności i wtyczek. Ustaw `UAGENT_POLICY_FILE` na plik zasad JSON/YAML; zobacz [docs/ENTERPRISE_POLICY.md](docs/ENTERPRISE_POLICY.md), aby zapoznać się z przykładami konfiguracji, rolami, potwierdzeniami i listami dozwolonych.

### Odzyskiwanie i orkiestracja środowiska wykonawczego

Zobacz [RESTART_RECOVERY.md](docs/RESTART_RECOVERY.md) / [DAG_SCHEDULER.md](docs/DAG_SCHEDULER.md) / [MULTI_AGENT_RUNTIME.md](docs/MULTI_AGENT_RUNTIME.md) do trwałego odzyskiwania, wykonywania z uwzględnieniem zależności, orkiestracji wielu agentów i zdalnego użycia A2A.

Zobacz [DISTRIBUTED_COORDINATION.md](docs/DISTRIBUTED_COORDINATION.md) do koordynacji dzierżawy lidera w środowisku współdzielonym.
```
