<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="720">
</p>

# uag (Lokalny agent AI)

`uag` to interaktywny agent, który wykonuje **polecenia**, obsługuje **pliki** i odczytuje **różne formaty danych** (PDF/PPTX/Excel itp.) na Twoim lokalnym komputerze. Oferuje trzy interfejsy: CLI, GUI i Web.


GitHub: https://github.com/awaku7/agentcli

## Instalacja

`uag` możesz zainstalować za pomocą pip:

```bash
pip install uag
```

Po instalacji, przy pierwszym uruchomieniu `uag` automatycznie zostanie uruchomiony **interaktywny kreator konfiguracji**, aby skonfigurować zmienne środowiskowe. Szczegółowe informacje o konfiguracji i szyfrowaniu znajdziesz w **[ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md)**.

## Główne funkcje

- **Praktyczny zestaw narzędzi**: narzędzia do pracy z plikami, wyszukiwania w sieci, ekstrakcji danych (PDF/PPTX/Excel), generowania obrazów i analizy — wszystko uruchamiane lokalnie.
- **Obsługa wielu dostawców**: OpenAI / Azure / Bedrock / OpenRouter / Ollama / Gemini / Vertex AI / Claude / Grok / NVIDIA.
- **Elastyczne interfejsy**:
  - **CLI**: `uag` / `python -m uagent`
  - **GUI**: `uagg` / `python -m uagent.gui`
  - **Web**: `uagw` / `python -m uagent.web`
  - **A2A (Server)**: `uaga` / `python -m uagent.a2a.server`
- **MCP (Model Context Protocol)**: obsługa łączenia z zewnętrznymi serwerami narzędzi MCP.
- **Ciągłość sesji**: utrzymuje kontekst rozmowy nawet po zmianie dostawcy lub modelu.
- **Web Inspector**: automatycznie zapisuje przejścia przeglądarki, DOM i zrzuty ekranu za pomocą `playwright_inspector`.
- **Wbudowana dokumentacja**: natychmiastowy dostęp do szczegółowej dokumentacji wewnętrznej za pomocą polecenia `uag docs`.

## Użycie

### Uruchamianie i zakończenie
Uruchom `uag` z terminala, aby rozpocząć. Wpisz `:exit`, aby zakończyć.

### Serwer A2A (Agent2Agent)
Uruchom serwer HTTP zgodny z A2A:
```bash
uaga
```

### Responses API note

If you set `UAGENT_RESPONSES=1`, Responses API is used for supported providers: OpenAI / Azure / Bedrock / OpenRouter / Ollama.
Gemini / Claude / Vertex AI use their native API paths and are not covered by Responses API.
For other providers, uag falls back to the provider-specific or chat-completions path.


Zobacz [ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md), aby poznać ustawienia `UAGENT_A2A_*`, takie jak uwierzytelnianie, host, port, przeładowanie, publiczny adres bazowy URL, współbieżność i silnik.


### Przydatne skróty (ciągłość i kontrola)
- `:tools`: wyświetla listę załadowanych narzędzi.
- `:logs [n]`: pokazuje logi sesji (`n` określa liczbę wpisów).
- `:load <index>`: wczytuje poprzednią sesję, aby wznowić rozmowę.
- `:skills`: wybiera i ładuje Agent Skills (dodatkowe role lub instrukcje).
- `:shrink [n]`: porządkuje historię, pozostawiając tylko ostatnie `n` wiadomości, aby oszczędzać tokeny.

## Konfiguracja i szczegóły

### Zmienne środowiskowe i konfiguracja
Szczegółowe ustawienia (klucze API, język interfejsu `UAGENT_LANG`, ustawienia zwijania historii itp.) znajdziesz w **[ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md)**.
- **Konfiguracja**: ustawienia można skonfigurować interaktywnie za pomocą `python -m uagent.setup_cli`.
- **Szyfrowanie**: bezpiecznie zaszyfruj plik `.env` za pomocą narzędzia `uag_envsec`.
- **Aktualizacja**: Użyj `uag_envsec add --file .env.sec --key NAME --value VALUE`, aby dodać lub zaktualizować zmienną w istniejącym zaszyfrowanym pliku.

### Dokumentacja dla deweloperów i internacjonalizacja
- **Dokumentacja dla deweloperów**: [`src/uagent/docs/DEVELOP.md`](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)
- **Dodawanie lokalizacji**: [`src/uagent/docs/ADD_LOCALE.md`](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/ADD_LOCALE.md)
- **README w innych językach**: [English](https://github.com/awaku7/agentcli/blob/main/README.md) / [日本語](https://github.com/awaku7/agentcli/blob/main/README.ja.md) / [Deutsch](https://github.com/awaku7/agentcli/blob/main/README.de.md) / [Español](https://github.com/awaku7/agentcli/blob/main/README.es.md) / [Français](https://github.com/awaku7/agentcli/blob/main/README.fr.md) / [Italiano](https://github.com/awaku7/agentcli/blob/main/README.it.md) / [한국어](https://github.com/awaku7/agentcli/blob/main/README.ko.md) / [Português](https://github.com/awaku7/agentcli/blob/main/README.pt_BR.md) / [Русский](https://github.com/awaku7/agentcli/blob/main/README.ru.md) / [ไทย](https://github.com/awaku7/agentcli/blob/main/README.th.md) / [简体中文](https://github.com/awaku7/agentcli/blob/main/README.zh_CN.md) / [繁體中文](https://github.com/awaku7/agentcli/blob/main/README.zh_TW.md) / [Polski](https://github.com/awaku7/agentcli/blob/main/README.pl.md) / [Tiếng Việt](https://github.com/awaku7/agentcli/blob/main/README.vi.md) / [Bahasa Indonesia](https://github.com/awaku7/agentcli/blob/main/README.id.md) / [العربية](https://github.com/awaku7/agentcli/blob/main/README.ar.md) / [हिन्दी](https://github.com/awaku7/agentcli/blob/main/README.hi.md) / [Português](https://github.com/awaku7/agentcli/blob/main/README.pt.md) / [Svenska](https://github.com/awaku7/agentcli/blob/main/README.sv.md) / [Norsk bokmål](https://github.com/awaku7/agentcli/blob/main/README.nb.md)
