# SPOSÓB UŻYCIA (Opcje wiersza poleceń)

Niniejszy dokument opisuje opcje wiersza poleceń dostępne dla punktów wejścia uag.

______________________________________________________________________

## Punkty wejścia

| Polecenie | Moduł Pythona | Interfejs |
|---|---|---|
| `uag` | `python -m uagent` | CLI (pętla stdin) |
| `uagg` | `python -m uagent.gui` | GUI (tkinter) |
| `uagw` | `python -m uagent.web` | Serwer WWW (FastAPI) |
| `uaga` | `python -m uagent.a2a.server` | serwer A2A HTTP |

______________________________________________________________________

## Opcje uruchamiania z wiersza poleceń (`uag`)

### `--workdir` / `-C <ścieżka>`

Katalog roboczy. Jeśli nie zostanie ustawiony, domyślnie przyjmowana jest zmienna środowiskowa `UAGENT_WORKDIR`, a następnie bieżący katalog.
Katalog zostanie utworzony, jeśli nie istnieje.

### `--use-tool` / `--no-use-tool`

Włącza lub wyłącza wysyłanie definicji narzędzi do `LLM`. Zastępuje zmienną środowiskową `UAGENT_USE_TOOL`.

- `--use-tool` wymusza włączenie wysyłania narzędzi.
- `--no-use-tool` wymusza wyłączenie wysyłania narzędzi.

Gdy opcja jest wyłączona, plik LLM nie otrzymuje żadnych definicji narzędzi i nie może wywołać żadnego narzędzia.

### `--computer-use` / `--no-computer-use`

Włączanie lub wyłączanie funkcji „Computer Use”. Zastępuje zmienną środowiskową `UAGENT_COMPUTER_USE`.

### `--inject-message` / `-M <komunikat>`

Wstawia komunikat do `LLM` podczas uruchamiania i kończy działanie po zakończeniu. Oznacza to `--non-interactive`.

### `--embedded`

Tryb wbudowany dla wdrożeń o ograniczonych zasobach lub wymagających powtarzalności.

- Wyłącza magazyn sesji.
- Ukrywa narzędzia do zarządzania narzędziami (`tool_catalog`, `tool_load`, `unload_tool`), chyba że zostaną one wyraźnie włączone.

### `--enable-tool <nazwa>`

Wyraźne załadowanie narzędzia podczas uruchamiania. Opcję tę można powtórzyć; akceptowane są również nazwy oddzielone przecinkami.

```
uag --embedded --enable-tool handle_mcp_v2 --enable-tool human_ask
uag --embedded --enable-tool handle_mcp_v2,human_ask
```

Określona kolejność zostaje zachowana i znajduje odzwierciedlenie w kolejności narzędzi przedstawionej w `LLM`. Narzędzia wyraźnie włączone są zabezpieczone przed automatycznym wyładowaniem.

### `--plugin-dir <ścieżka>`

Załaduj wtyczki z określonego katalogu. Opcję tę można powtórzyć.

______________________________________________________________________

## Opcje dostępne tylko w CLI

### `--inject-message-auto <opcje-celu>`

Uruchom tryb autopilota z nieinteraktywnego, wstrzykniętego celu. Wartość wykorzystuje te same opcje co `:auto`; należy ująć w cudzysłowy całą wartość, jeśli zawiera opcje.

```
uag --embedded --enable-tool handle_mcp_v2 --inject-message-auto „Posortuj elementy --max-rounds 10”
uag --embedded --enable-tool handle_mcp_v2 --inject-message-auto „Posortuj elementy --infinite”
```

Tryb normalny wykorzystuje ścieżkę opartą na ocenie recenzenta. Ustaw `UAGENT_AUTO_SENTINEL=1`, aby włączyć tryb pojedynczego strażnika LLM. W tym trybie docelowy LLM musi kończyć każdą odpowiedź dokładnie jednym z następujących elementów:

- `<AUTO_CONTINUE>` — uruchom kolejną rundę
- `<AUTO_COMPLETE>` — zakończ pomyślnie

Brakujące lub nieprawidłowe znaczniki powodują bezpieczne zatrzymanie trybu automatycznego. Program docelowy LLM nadal jest uruchamiany; unika się jedynie dodatkowego wywołania recenzenta LLM.

### `--non-interactive`

Tryb nieinteraktywny. Nie uruchamia pętli stdin. Jeśli ścieżka do pliku zostanie podana jako argument pozycyjny, zostanie ona przetworzona, a program natychmiast się zakończy.

```
uag --non-interactive README.md
uag --non-interactive --workdir /tmp/project
```

______________________________________________________________________

## Opcje serwera WWW (`uagw`)

### `--host <address>`

Adres, do którego serwer WWW się przypisuje (domyślnie: `127.0.0.1`, można go zmienić za pomocą `UAGENT_WEB_HOST`).

Domyślnie serwer WWW nasłuchuje wyłącznie na localhost (`127.0.0.1`). Aby zapewnić dostęp do niego z innych komputerów w sieci, należy użyć `--host 0.0.0.0`.

```env
UAGENT_WEB_ALLOWED_ORIGINS=http://192.168.1.10:8000
```

```
uagw --host 0.0.0.0
uagw --host 192.168.1.10
```

### `--use-tool` / `--no-use-tool`

Włącz lub wyłącz wysyłanie definicji narzędzi do `LLM`. Zastępuje ustawienie `UAGENT_USE_TOOL`.

### `--computer-use` / `--no-computer-use`

Włącza lub wyłącza korzystanie z komputera. Zastępuje ustawienie `UAGENT_COMPUTER_USE`.

### `--no-frontend`

Uruchamia wyłącznie moduł API bez szablonów HTML ani statycznych plików interfejsu użytkownika.

### `--embedded`

Wyłącza magazyn sesji i ukrywa narzędzia do zarządzania narzędziami (`tool_catalog`, `tool_load`, `unload_tool`).

______________________________________________________________________

## Opcje serwera A2A (`uaga`)

### `--host <address>`

Adres powiązania dla serwera A2A HTTP (domyślnie: `0.0.0.0`, można nadpisać za pomocą `UAGENT_A2A_HOST`).

### `--port <liczba>`

Numer portu serwera A2A HTTP (domyślnie: `8765`, można zmienić za pomocą `UAGENT_A2A_PORT`).

### `--reload`

Włącz automatyczne przeładowywanie po zmianach w kodzie (domyślnie: wyłączone, można to zmienić za pomocą `UAGENT_A2A_RELOAD`).

```
uaga --host 127.0.0.1 --port 8080 --reload
```

### `--use-tool` / `--no-use-tool`

Włącza lub wyłącza wysyłanie definicji narzędzi do LLM. Zastępuje `UAGENT_USE_TOOL`.

### `--computer-use` / `--no-computer-use`

Włącza lub wyłącza korzystanie z komputera. Zastępuje `UAGENT_COMPUTER_USE`.

### `--embedded`

Wyłącza magazyn sesji i ukrywa narzędzia do zarządzania narzędziami (`tool_catalog`, `tool_load`, `unload_tool`).

______________________________________________________________________

## Powiązane zmienne środowiskowe

| Zmienna | Opis |
|---|---|
| `UAGENT_PROVIDER` | Nazwa dostawcy LLM (wymagana podczas uruchamiania) |
| `UAGENT_*_API_KEY` | Klucz API dla wybranego dostawcy |
| `UAGENT_WORKDIR` | Domyślny katalog roboczy |
| `UAGENT_WEB_HOST` | Adres wiązania serwera WWW (domyślnie: `127.0.0.1`) |
| `UAGENT_A2A_HOST` | Adres wiązania serwera A2A (domyślnie: `0.0.0.0`) |
| `UAGENT_A2A_PORT` | Port serwera A2A (domyślnie: `8765`) |
| `UAGENT_A2A_RELOAD` | Domyślnie włącz ponowne ładowanie na gorąco w A2A |
| `UAGENT_USE_TOOL` | Wyłącz narzędzia, gdy ustawiono wartość `0`, `false`, `no` lub `off` |
| `UAGENT_COMPUTER_USE` | Włącz lub wyłącz domyślne korzystanie z komputera |
| `UAGENT_SESSION_STORE` | Włącz lub wyłącz magazyn sesji; tryb wbudowany wymusza wartość `0` |
| `UAGENT_PLUGIN_DIRS` | Dodatkowe katalogi wyszukiwania wtyczek |
| `UAGENT_AUTO_SENTINEL` | Włącz tryb strażnika autopilota pojedynczego LLM, gdy ustawiono na `1` |
| `UAGENT_CONSECUTIVE_TOOL_CALL_LIMIT` | Maksymalna liczba kolejnych wywołań nowych narzędzi (domyślnie: `50`) |
| `UAGENT_MAX_TOOL_ROUNDS` | Maksymalna liczba rund LLM/narzędzie na operację użytkownika (domyślnie: `512`) |
| `UAGENT_SHRINK_CNT` | Opcjonalny próg automatycznego zmniejszania rozmiaru wiadomości (`0`/brak ustawienia = wyłączone) |
| `UAGENT_SHRINK_KEEP_LAST` | Liczba komunikatów do zachowania po skróceniu (domyślnie: `20`) |
| `UAGENT_LANG` | Język interfejsu (`ja`, `en` itp.) |

Pełna lista zmiennych środowiskowych znajduje się w pliku [ENVIRONMENT.md](ENVIRONMENT.md).

______________________________________________________________________

## Przykłady

### Minimalna konfiguracja początkowa z OpenAI

```
set UAGENT_PROVIDER=openai
set UAGENT_OPENAI_API_KEY=sk-...
uag
```

### Lokalny serwer Ollama z samymi podstawowymi narzędziami

```
set UAGENT_PROVIDER=ollama
set UAGENT_OLLAMA_MODEL=qwen2.5:7b
uag
```

### Serwer WWW na wszystkich interfejsach

```
set UAGENT_WEB_HOST=0.0.0.0
set UAGENT_WEB_ALLOWED_ORIGINS=http://192.168.1.10:8000
uagw
```

lub

```
set UAGENT_WEB_ALLOWED_ORIGINS=http://192.168.1.10:8000
uagw --host 0.0.0.0
```

### Serwer A2A na localhost z niestandardowym portem

```
uaga --host 127.0.0.1 --port 8080
```

### Wyłącz narzędzia dla małego modelu

```
uag --no-use-tool
```

### Nieinteraktywne przetwarzanie plików

```
uag --non-interactive README.md
```
