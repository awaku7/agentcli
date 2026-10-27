<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="680">
</p>

<h1 align="center">uag</h1>

<p align="center">
  <strong>Universal AI Gateway</strong><br>
  Jeden lokalny agent. Dowolny model. Dowolne narzędzie. Twoje środowisko, Twoje zasady.
</p>

<p align="center">
  <a href="https://github.com/awaku7/agentcli/actions"><img src="https://img.shields.io/github/actions/workflow/status/awaku7/agentcli/ci.yml?style=flat-square&label=CI" alt="CI status"></a>
  <a href="https://pypi.org/project/uag/"><img src="https://img.shields.io/pypi/v/uag?style=flat-square" alt="PyPI version"></a>
  <a href="https://pypi.org/project/uag/"><img src="https://img.shields.io/pypi/pyversions/uag?style=flat-square" alt="Python versions"></a>
  <a href="https://github.com/awaku7/agentcli/blob/main/LICENSE"><img src="https://img.shields.io/github/license/awaku7/agentcli?style=flat-square" alt="License"></a>
  <a href="https://pepy.tech/projects/uag"><img src="https://static.pepy.tech/personalized-badge/uag?period=total&units=INTERNATIONAL_SYSTEM&left_color=grey&right_color=green&left_text=downloads" alt="PyPI Downloads"></a>
</p>

<p align="center">
  <a href="https://github.com/awaku7/agentcli">GitHub</a> ·
  <a href="https://pypi.org/project/uag/">PyPI</a> ·
  <a href="https://github.com/awaku7/agentcli/discussions">Dyskusje</a> ·
  <a href="https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md">Tłumaczenia</a>
</p>

______________________________________________________________________

**Dlaczego uag?**

uag to lokalny agent AI, który łączy preferowany przez Ciebie model z narzędziami, których faktycznie używasz.
Zapewnia jeden, rozszerzalny runtime do obsługi plików, przeglądarek, baz kodu, komunikacji, API chmurowych,
urządzeń IoT, serwerów MCP i przepływów pracy wielu agentów.

- **Swoboda wyboru dostawcy** — OpenAI, Anthropic, Gemini, Azure, Bedrock, Ollama, llama.cpp, Grok, DeepSeek i inni.
- **Wykonywanie lokalne** — runtime agenta i wykonywanie narzędzi pozostają na Twoim komputerze; opuszczają go tylko wybrane przez Ciebie wywołania API.
- **Jedna warstwa narzędzi** — te same narzędzia działają w CLI, desktopowym GUI, interfejsie webowym, VS Code i A2A.
- **Równoległość z założenia** — niezależne operacje tylko do odczytu mogą działać współbieżnie.
- **Rozszerzalność** — dodawaj narzędzia, pluginy, Agent Skills, serwery MCP i narzędzia oparte na Rust bez zmieniania rdzenia.
- **Świadomość bezpieczeństwa** — działania destrukcyjne, dane uwierzytelniające, sterowanie urządzeniami i zapisy sieciowe obsługują jawną zgodę oraz reguły polityk.

> **W skrócie:** uag to płaszczyzna sterowania między Twoimi modelami AI a rzeczywistym środowiskiem.

> **🧠 Wyniki narzędzi uwzględniające kontekst** — W miarę możliwości obszerne wyniki narzędzi są wykluczane z kontekstu aktywnego modelu. uag przechowuje je jako artefakty i zamiast tego przekazuje modelowi ograniczony podgląd ze stabilnym odwołaniem do Artifact. Może to znacznie zmniejszyć liczbę tokenów wejściowych wymaganych w kolejnych turach, gdy narzędzie generuje obszerny wynik.
> [Szczegółowy przewodnik po kompresji kontekstu](CONTEXT_COMPRESSION.pl.md)

## Szybki start

**Python 3.11+**

```bash
python -m pip install --upgrade uag
uag
```

Przy pierwszym uruchomieniu otworzy się kreator konfiguracji. Pomoże skonfigurować dostawcę i zapisze wybrane ustawienia
w lokalnym środowisku.

Dla typowych grup funkcji:

```bash
python -m pip install "uag[core,providers,tools]"
```

> Integracje platformowe są opcjonalne. Zainstaluj tylko to, czego potrzebuje Twój system operacyjny; zobacz

```text
> What files changed in this repository?
> Search the web for today's AI news and summarize the top five stories.
> :help
```

[Quickstart](QUICKSTART.md) · [Environment](ENVIRONMENT.md)

## Interfejsy

| Interfejs | Polecenie | Najlepsze zastosowanie |
|---|---|---|
| **CLI** | `uag` | Szybka praca z klawiaturą |
| **Desktop GUI** | `uagg` | Natywne środowisko desktopowe |
| **Web UI** | `uagw` | Dostęp przez przeglądarkę |
| **Serwer A2A** | `uaga` | Komunikacja agent-agent |
| **VS Code** | Extension | Wyjaśnianie, refaktoryzacja, naprawianie i przeglądanie narzędzi w edytorze |

Wszystkie interfejsy współdzielą tę samą konfigurację dostawcy, rejestr narzędzi, reguły bezpieczeństwa i dane sesji.

~~~bash
# Desktop GUI
python -m pip install "uag[platform]"

# Web UI
python -m pip install "uag[web]" fastapi uvicorn
~~~

[Interface options](USAGE.md) · [Environment](ENVIRONMENT.md)

## Co możesz zbudować

Adaptery dostawców obejmują runtime'y hostowane i lokalne, w tym:

**OpenAI · Meta Model API · Anthropic · Google Gemini · Vertex AI · Azure OpenAI · Amazon Bedrock · OpenRouter · Ollama · llama.cpp · Grok · DeepSeek · NVIDIA · Hugging Face · Alibaba Cloud · Moonshot · Xiaomi MiMo · LM Studio · MiniMax · Sakana AI · SAKURA AI Engine · Together AI · Vercel AI Gateway · PFN/PLaMo · Z.AI · Novita**

Przełączaj dostawców za pomocą `UAGENT_PROVIDER`; Twoje narzędzia i interfejs pozostają bez zmian.

**Praca ze środowiskiem**

- Odczytywać, tworzyć, edytować, wyszukiwać, haszować, archiwizować i sprawdzać pliki
- Przeglądać zmiany Git, wyszukiwać sekrety, uruchamiać testy, lintować, kompilować i mierzyć pokrycie
- Nawigować po dużych bazach kodu Python, TypeScript, JavaScript, Go, Rust, C/C++, Java, C#, COBOL, VBA i innych
- Automatyzować przeglądarki za pomocą Playwright, w tym przepływy wielostronicowe i pobieranie plików

**Łączenie usług i urządzeń**

- **MCP** — łączenie z zewnętrznymi serwerami narzędzi, w tym usługami obsługującymi OAuth
- **A2A** — współpraca z innymi agentami i kompatybilnymi serwerami
- **Cloud** — dostęp do API AWS, Google Cloud i Azure z potwierdzeniem zapisów
- **Communication** — Gmail, Bluesky, Discord, Microsoft Teams i pybitchat
- **IoT** — SwitchBot, ECHONET Lite, Matter, BACnet, Modbus TCP, OPC UA i UPnP
- **Media** — generowanie/edycja obrazów, transkrypcja i mowa audio, przechwytywanie obrazu z kamery oraz kody QR
- **Documents** — analiza PDF, PowerPoint, Word, Excel, CSV, JSON, YAML, SQL i logów

**IoT i sterowanie światem fizycznym**

- **SwitchBot** — wyszukiwanie w chmurze i przez BLE, status, sterowanie, grupowanie i subskrypcje
- **ECHONET Lite** — wykrywanie i sterowanie japońskimi urządzeniami domowymi, w tym powiadomieniami INF
- **Matter** — endpointy, klastry, atrybuty, historia stanu, subskrypcje i sterowanie
- **BACnet / Modbus TCP / OPC UA** — odczyty, zapisy, przeglądanie i monitorowanie automatyki przemysłowej oraz budynkowej
- **UPnP** — wykrywanie urządzeń, status WAN i zarządzanie mapowaniem portów routera

### Miejsce uag w systemie

uag znajduje się między ludźmi i interfejsami z jednej strony a modelami, narzędziami i systemami świata rzeczywistego z drugiej.
Koordynuje rozmowę, wybiera możliwości, stosuje reguły bezpieczeństwa i pozwala wznawiać przepływ pracy.

~~~mermaid
flowchart LR
    UI["CLI · Desktop · Web · VS Code · A2A"] --> UAG["UAG agent runtime"]
    UAG --> MODELS["Hosted & local models"]
    UAG --> TOOLS["Tools & extensions"]
    UAG --> STATE["Sessions & context"]
    TOOLS --> SYSTEMS["Files · Code · Web · MCP · Cloud · IoT"]
    POLICY["Confirmation · Credentials · Policy"] -.-> UAG
~~~

### Pluginy, Agent Skills i marketplace'y

Przekształć uag w wyspecjalizowanego agenta bez forkowania rdzenia:

- Instaluj **pluginy zgodne z Claude Code** z katalogu, ZIP-a, repozytorium Git, źródła HTTP lub marketplace'u
- Pakuj umiejętności, podagentów, serwery MCP, hooki, polecenia slash, style wyjścia, zależności i kanały
- Przeglądaj możliwości społeczności w [SkillsMP](https://skillsmp.com) i [ClawHub](https://clawhub.ai)
- Dodawaj prywatne umiejętności i narzędzia organizacji lokalnie przez `UAGENT_EXTERNAL_TOOLS_DIR`

```text
:skills mp_search browser automation
:plugin list
:plugin install <source>
:plugin marketplace list
```

Zobacz [przewodnik tworzenia pluginów](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP_PLUGIN.md).

- **Ponad 200 narzędzi** do plików, sieci, mediów, dokumentów, kodu, chmury, komunikacji i IoT
- **Dynamiczne wyszukiwanie i ładowanie** — użyj `tool_catalog`, aby znaleźć możliwości, oraz `tool_load`, aby włączyć je tylko wtedy, gdy są potrzebne
- **Inteligencja kodu** — `code_map`, nawigatory `idx` dla konkretnych języków, przegląd Git, wykonywanie testów, linting, kompilacja i pokrycie kodu
- **Pluginy zgodne z Claude Code** z umiejętnościami, agentami, serwerami MCP, hookami, poleceniami i marketplace'ami
- **Agent Skills** z SkillsMP i ClawHub
- **Niestandardowe narzędzia Python** z `TOOL_SPEC` i `run_tool()`
- **Narzędzia oparte na Rust** dla lekkich natywnych rozszerzeń

[Tool Creator Guide](../TOOL_CREATOR_GUIDE.md) · [MCP OAuth / Proxy Guide](MCP_OAUTH_PROXY_GUIDE.md)

## Stworzone z myślą o rzeczywistych procesach pracy

### 🧠 Wyniki narzędzi uwzględniające kontekst

W miarę możliwości obszerne wyniki narzędzi są wykluczane z kontekstu aktywnego modelu. uag przechowuje je jako artefakty i zamiast tego przekazuje modelowi ograniczony podgląd ze stabilnym odwołaniem do Artifact. Może to znacznie zmniejszyć liczbę tokenów wejściowych wymaganych w kolejnych turach, gdy narzędzie generuje obszerny wynik.

Wznawiaj poprzednie rozmowy za pomocą `:load <index>`. Wyniki narzędzi mogą być buforowane, a dostawców można zmieniać
bez ponownego budowania aplikacji.

[Context compression](CONTEXT_COMPRESSION.pl.md) · [Memory](MEMORY.md) · [Session portability](SESSION_PORTABILITY.md)

### Auto-pilot

Użyj `:auto` do pracy wieloetapowej z opcjonalnym modelem recenzenta. Ustaw limit rund za pomocą `--max-rounds N`.
Naciśnij **F12**, aby zatrzymać auto-pilot, lub **F12**, aby zatrzymać bieżącą odpowiedź.

Niezależne operacje tylko do odczytu działają współbieżnie, gdy jest to bezpieczne. Wyszukiwanie w sieci, inspekcja plików,
analiza repozytorium i podobne zadania mogą kończyć się równolegle dzięki konfigurowalnej puli roboczej
(`UAGENT_PARALLEL_WORKERS`). Operacje zapisu pozostają szeregowane lub wymagają potwierdzenia.

Ciągłość sesji, buforowanie wyników narzędzi, stan zadań wsadowych, odzyskiwanie po restarcie, planowanie DAG
i orkiestracja wielu agentów sprawiają, że złożoną pracę można wznawiać zamiast wykonywać ją tylko jednorazowo.

[Auto-pilot](README_AUTO.md) · [Timers](SET_TIMER.md) · [Multi-agent runtime](MULTI_AGENT_RUNTIME.md)

### 🌍 Prywatność, wielojęzyczność i polityki

`human_ask` wstrzymuje działanie przed wrażliwymi operacjami. Usuwanie i nadpisywanie plików, polecenia powłoki, sterowanie urządzeniami,
operacje na danych uwierzytelniających i zapisy sieciowe mogą podlegać regułom potwierdzania i politykom.

Korzystaj z magazynu danych uwierzytelniających zamiast umieszczać długotrwałe sekrety w promptach:

Interfejs webowy zawiera logowanie OIDC przy użyciu Authorization Code + PKCE, zweryfikowane tokeny ID, sesje po stronie serwera oraz kontrolę dostępu do projektów/pokoi. Zweryfikowane roszczenia grup Microsoft Entra ID mogą zasilać politykę dostępu opartą na katalogu, jeśli są skonfigurowane. Wdrożenia Windows Active Directory, OAuth i trusted-proxy mogą integrować się za pomocą jawnych, zweryfikowanych adapterów tożsamości; Windows AD wymaga wdrożeniowego weryfikatora Kerberos/Negotiate i nie jest domyślnie włączony.

uag obejmuje opcjonalne, neutralne dla dostawcy śledzenie OpenTelemetry i metryki dla Agent, LLM, narzędzi, Context, Memory i operacji pobierania. Obserwowalność jest domyślnie wyłączona.

Podejście local-first nie oznacza, że UAG domyślnie działa całkowicie offline ani że wszystkie narzędzia są izolowane. Wywołania zewnętrznych modeli i połączonych usług zależą od konfiguracji.

- [Enterprise policies](ENTERPRISE_POLICY.md)
- [MXC sandbox](SANDBOX_MXC.md)
- [Remote Web / A2A](REMOTE_MXC_DEFAULT.md)
- [Web identity](WEB_IDENTITY_MEMORY.md)
- [OpenTelemetry](UAG_OPENTELEMETRY_DESIGN.md)

### 🌍 Tłumaczenie wielojęzyczne

- `translate_text` obsługuje Google Translate oraz oficjalny klient DeepL dla języka Python poprzez ustawienia `provider=auto`, `provider=deepl` lub `provider=google`.
- Definicje narzędzi są dostępne w 37 lokalizacjach oraz w języku angielskim (łącznie 38), z zachowaniem symboli zastępczych i identyfikatorów technicznych.

Głos pełnodupleksowy jest dostępny przez OpenAI Realtime, Azure OpenAI, xAI Grok Voice, Gemini Live
i Bedrock Nova Sonic, z opcjonalnym tłumieniem echa AEC3 oraz ograniczonym bezpieczeństwem wywoływaniem funkcji w czasie rzeczywistym.

[Translations](README.translations.md) · [IoT](IOT_USECASE.md) · [Communication](COMMUNICATION.md)

## Dokumentacja

| Temat | Dokumentacja |
|---|---|
| Zmienne środowiskowe | [docs/ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/docs/ENVIRONMENT.md) |
| Architektura i niezmienniki | [docs/ARCHITECTURE.md](https://github.com/awaku7/agentcli/blob/main/docs/ARCHITECTURE.md) |
| Computer Use | [docs/COMPUTER_USE_IMPLEMENTATION.md](https://github.com/awaku7/agentcli/blob/main/docs/COMPUTER_USE_IMPLEMENTATION.md) |
| Narzędzia repozytorium | [docs/REPOSITORY_TOOLS.md](https://github.com/awaku7/agentcli/blob/main/docs/REPOSITORY_TOOLS.md) |
| Przypadki użycia IoT | [docs/IOT_USECASE.md](https://github.com/awaku7/agentcli/blob/main/docs/IOT_USECASE.md) |
| Narzędzia komunikacyjne | [docs/COMMUNICATION.md](https://github.com/awaku7/agentcli/blob/main/docs/COMMUNICATION.md) |
| Auto-pilot | [docs/README_AUTO.md](https://github.com/awaku7/agentcli/blob/main/docs/README_AUTO.md) |
| MCP OAuth / Proxy | [docs/MCP_OAUTH_PROXY_GUIDE.md](https://github.com/awaku7/agentcli/blob/main/docs/MCP_OAUTH_PROXY_GUIDE.md) |
| Rozszerzenie VS Code | [docs/VSCODE.md](https://github.com/awaku7/agentcli/blob/main/docs/VSCODE.md) |
| Przewodnik deweloperski | [src/uagent/docs/DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md) |
| Przepływ narzędzi | [src/uagent/docs/TOOL_FLOW.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/TOOL_FLOW.md) |

[Quickstart](QUICKSTART.md) · [Architecture](ARCHITECTURE.md) · [Context management](UAG_CONTEXT_MANAGEMENT_DESIGN.md)

## Rozwój i współtworzenie

```bash
git clone https://github.com/awaku7/agentcli.git
cd agentcli
python -m pip install -e ".[core,providers,test]"
```

Uruchom kontrole przed zgłoszeniem PR:

```bash
python -m ruff check src tests
python -m black --check src tests
python -m pytest -q .
```

Pełny przepływ pracy deweloperskiej opisano w [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md).

Zgłoszenia błędów, pomysły na funkcje, ulepszenia dokumentacji, tłumaczenia, narzędzia, umiejętności i pull requesty są mile widziane.
Przed dużymi zmianami otwórz issue lub dyskusję. Przeczytaj [przewodnik deweloperski](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)
i uruchom powyższe kontrole przed wysłaniem pull requesta.

## Licencja

Na licencji [Apache License 2.0](https://github.com/awaku7/agentcli/blob/main/LICENSE).
