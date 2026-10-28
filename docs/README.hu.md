<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="UAG — Universal AI Gateway" width="620">
</p>
<h1 align="center">UAG</h1>
<p align="center"><strong>Universal AI Gateway</strong><br>Az Ön MI-modelljei. Az Ön eszközei. Az Ön környezete.</p>

<p align="center">
  <a href="https://github.com/awaku7/agentcli/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/awaku7/agentcli/ci.yml?style=flat-square&label=CI" alt="CI"></a>
  <a href="https://pypi.org/project/uag/"><img src="https://img.shields.io/pypi/v/uag?style=flat-square" alt="PyPI"></a>
  <a href="https://pypi.org/project/uag/"><img src="https://img.shields.io/pypi/pyversions/uag?style=flat-square" alt="Python versions"></a>
  <a href="../LICENSE"><img src="https://img.shields.io/github/license/awaku7/agentcli?style=flat-square" alt="License"></a>
  <a href="https://pepy.tech/projects/uag"><img src="https://static.pepy.tech/personalized-badge/uag?period=total&units=INTERNATIONAL_SYSTEM&left_color=grey&right_color=green&left_text=downloads" alt="Downloads"></a>
</p>
<p align="center"><a href="../README.md">English</a> · <a href="README.translations.md">További nyelvek</a></p>

---

**Az UAG nyílt forráskódú, helyi működést előnyben részesítő MI-ügynök futtatókörnyezet.** Összekapcsolja a választott nyelvi modellt a használt eszközökkel és rendszerekkel. Egyetlen felületen kezelhető a kód, a fájlok, a böngészők, a szolgáltatások és az eszközök, egyetlen modellszolgáltatóhoz való kötöttség nélkül.

| **Válasszon modellt** | **Csatlakoztasson eszközöket** | **Maradjon kézben az irányítás** |
| :--- | :--- | :--- |
| Felhős és helyi modellek: OpenAI, Claude, Gemini, Grok, Bedrock, Ollama | Fájlok, kód, web, MCP, Agent Skills, bővítmények, felhőszolgáltatások és IoT | Helyi futtatás, emberi jóváhagyás, hitelesítőadat-tárolás és szabályozható házirendek |

> Az UAG **ügynökfuttatási réteg, nem modellszolgáltató**. A külső modellek és kapcsolt szolgáltatások hívása a beállításoktól függ. A helyi működés előnyben részesítése nem jelent alapértelmezett teljes offline használatot vagy általános elkülönítést.

## Gyors kezdés
<!-- README-SYNC:quick-start -->

**Python 3.11 vagy újabb** szükséges. Telepítse az UAG-t a [PyPI](https://pypi.org/project/uag/) oldalról, majd indítsa el a parancssort:

~~~bash
python -m pip install --upgrade uag
uag
~~~

Az első indításkor a varázsló segít kiválasztani a modellszolgáltatót és beállítani a hitelesítő adatokat. Környezeti változók és biztonságos adattár is használható. További szolgáltatói és eszközfüggőségek előzetes telepítéséhez:

~~~bash
python -m pip install "uag[core,providers,tools]"
~~~

Ezután próbálja ki például ezeket:

~~~text
> Mi változott ebben a Git-tárolóban? Foglald össze a kockázatokat.
> Keresd meg a könyvtár legfrissebb dokumentációját, és magyarázd el az áttérés lépéseit.
> Vizsgáld meg ezeket a fájlokat, és készíts rövid jelentést.
> :help
~~~

Kezdőknek a Windows telepítési útmutatót ajánljuk, amely a Gitet és a virtuális környezeteket is ismerteti, valamint a konfigurációs leírást: [Quickstart (Windows)](QUICKSTART.md) · [Environment](ENVIRONMENT.md).

## Felületek
<!-- README-SYNC:interfaces -->

Minden belépési pont ugyanazt az ügynökfuttatót és eszközregisztert használja.

| Felület | Indítás | Felhasználás |
| :--- | :--- | :--- |
| **CLI** | `uag` | Terminál és automatizálás |
| **Desktop** | `uagg` | Natív asztali beszélgetések |
| **Web** | `uagw` | Böngészős beszélgetések és szobák |
| **A2A** | `uaga` | Ügynökök közti együttműködés |
| **VS Code** | [Bővítmény útmutató](VSCODE.md) | Munka a forráskód mellett |

Az asztali és webes felülethez további függőségek szükségesek, amelyeket a `uag[core,providers,tools]` nem tartalmaz:

~~~bash
# Desktop GUI (PySide6 and platform integrations)
python -m pip install "uag[platform]"

# Web UI (authentication dependencies, FastAPI, and Uvicorn)
python -m pip install "uag[web]" fastapi uvicorn
~~~

A webszerver induláskor megpróbálhatja telepíteni a FastAPI-t és az Uvicornt. Előzetes telepítéssel ez elkerülhető. Részletek: [CLI usage](USAGE.md) · [Environment](ENVIRONMENT.md).

## Mire használható az UAG?
<!-- README-SYNC:capabilities -->

| Képesség | Amit az UAG nyújt |
| :--- | :--- |
| **Modellfüggetlen folyamatok** | Felhős és helyi szolgáltatók váltása a `UAGENT_PROVIDER` használatával, az eszközök átírása nélkül |
| **Kód és fájlok** | Tárolóbejárás, Git-ellenőrzés, lint, tesztek, fájlkezelés és böngészőautomatizálás |
| **Bővíthető eszközök** | Több mint 200 eszköz, dinamikus felfedezés `tool_catalog` / `tool_load` útján, saját Python- és Rust-eszközök |
| **Összekapcsolt ügynökök** | MCP, A2A, Claude Code-kompatibilis bővítmények, Agent Skills és alügynökök |
| **Hosszú feladatok** | Autopilot, párhuzamos független olvasások, ütemezés, helyreállítás és megőrzött munkamenetek |
| **Terminálon túl** | Felhő, kommunikáció, dokumentumok, média, valós idejű hang és támogatott IoT-protokollok |

### Egy futtatókörnyezet, sok integráció
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

**Támogatott modellszolgáltatók példái** lent találhatók; az egyedi beállításokat a környezeti dokumentáció ismerteti.

**OpenAI · Anthropic · Gemini · Vertex AI · Azure OpenAI · Amazon Bedrock · Grok · DeepSeek · OpenRouter · Ollama · llama.cpp · LM Studio**

[ENVIRONMENT.md](ENVIRONMENT.md)

### Bővítés skillekkel és bővítményekkel
<!-- README-SYNC:extensions -->

Az UAG a mag módosítása nélkül bővíthető. Telepítsen Agent Skills elemeket a SkillsMP vagy a ClawHub kínálatából, csatlakoztasson MCP-kiszolgálókat, vagy használjon eszközöket, skilleket, ügynököket és hookokat tartalmazó Claude Code-kompatibilis bővítményeket.

~~~text
:skills mp_search browser automation
:plugin list
:plugin install <source>
:plugin marketplace list
~~~

Saját eszközök a `TOOL_SPEC` és `run_tool()` felületet tehetik elérhetővé; a Rust-alapú eszközök is támogatottak. Útmutatók: [Tool Creator Guide](../TOOL_CREATOR_GUIDE.md) · [Plugin Development Guide](../src/uagent/docs/DEVELOP_PLUGIN.md) · [MCP OAuth / Proxy](MCP_OAUTH_PROXY_GUIDE.md).

## Valós munkafolyamatokhoz
<!-- README-SYNC:workflows -->

### Kontextus és memória
<!-- README-SYNC:context-memory -->

A nagy eszközeredmények **artefaktumként** tárolhatók, így nem terhelik a modell aktív kontextusát. Az ügynök később az `artifact_read` segítségével csak a szükséges részt tölti be. A munkamenetek alapértelmezés szerint SQLite-ban tárolódnak, előzménykereséssel és kifejezett memóriavizsgálattal.

- [Context compression](CONTEXT_COMPRESSION.hu.md)
- [Memory](MEMORY.md)
- [Session portability](SESSION_PORTABILITY.md)

### Automatizálás és együttműködés
<!-- README-SYNC:automation -->

Az UAG támogatja a független olvasási műveletek párhuzamos futtatását, a többügynökös koordinációt, a munkamenetek helyreállítását és a többfordulós autopilotot. Indítás: `:auto`. A **F12** megszakítja az aktuális választ, és az autopilot leállítását kéri.

- [Auto-pilot](README_AUTO.md)
- [Timers and scheduled tasks](SET_TIMER.md)
- [Multi-agent runtime](MULTI_AGENT_RUNTIME.md)

### Biztonság és megfigyelhetőség
<!-- README-SYNC:security -->

Érzékeny műveletekhez `human_ask` jóváhagyás kérhető. A hitelesítő adatok az operációs rendszer titoktárában vagy titkosított fájlban tárolhatók. A Web felület konfigurált OIDC-bejelentkezést és hozzáférés-szabályozást támogat. Az OpenTelemetry nyomkövetés és metrikák **nem kötelezők**.

- [Enterprise policies](ENTERPRISE_POLICY.md)
- [MXC sandbox](SANDBOX_MXC.md)
- [Remote Web / A2A MXC defaults](REMOTE_MXC_DEFAULT.md)
- [Web identity and rooms](WEB_IDENTITY_MEMORY.md)
- [OpenTelemetry design](UAG_OPENTELEMETRY_DESIGN.md)
- [Developer observability](../src/uagent/docs/DEVELOP_OBSERVABILITY.md)

A védelmek beállíthatók, de **nem garantálják** minden eszköz sandboxban való elkülönített futását. Nem megbízható felhasználók vagy hálózatok előtt olvassa el az üzembe helyezési és házirendi útmutatókat.

### Nyelvek, eszközök és hang
<!-- README-SYNC:languages -->

Az UAG **38 nyelvi környezethez** biztosít erőforrásokat (angol és 37 fordítás), választható teljes duplex hangfunkciókat és SwitchBot, Matter, ECHONET Lite, BACnet, Modbus TCP, OPC UA eszközöket.

- [Translations](README.translations.md)
- [IoT use cases](IOT_USECASE.md)
- [Communication tools](COMMUNICATION.md)

## Dokumentáció
<!-- README-SYNC:documentation -->

Kezdje ezekkel a leírásokkal, majd tekintse át a részleteket:

| Kezdés | Részletek |
| :--- | :--- |
| [Quickstart (Windows)](QUICKSTART.md) | [Architecture](ARCHITECTURE.md) |
| [CLI usage](USAGE.md) | [Context management](UAG_CONTEXT_MANAGEMENT_DESIGN.md) |
| [Environment and providers](ENVIRONMENT.md) | [Enterprise policy](ENTERPRISE_POLICY.md) |
| [Agent Skills and plugins](../src/uagent/docs/DEVELOP_PLUGIN.md) | [Tool flow](../src/uagent/docs/TOOL_FLOW.md) |
| [MCP and OAuth](MCP_OAUTH_PROXY_GUIDE.md) | [Computer Use](COMPUTER_USE_IMPLEMENTATION.md) |
| [VS Code extension](VSCODE.md) | [Developer guide](../src/uagent/docs/DEVELOP.md) |

További dokumentumok és nyelvek is elérhetők: [Documentation](./) · [Other languages](README.translations.md).

## Fejlesztés és közreműködés
<!-- README-SYNC:contributing -->

~~~bash
git clone https://github.com/awaku7/agentcli.git
cd agentcli
python -m pip install -e ".[core,providers,test]"
~~~

**Python-kód** módosítását tartalmazó pull request előtt futtassa a megfelelő teszteket és ellenőrzéseket:

~~~bash
python -m ruff check src tests
python -m black --check src tests
python -m pytest -q .
~~~

A közreműködési szabályok és a fejlesztői útmutató alább találhatók. Várjuk a hibajelentéseket, dokumentációjavításokat, eszközöket, fordításokat és célzott pull requesteket: [AGENTS.md](../AGENTS.md) · [Developer guide](../src/uagent/docs/DEVELOP.md).

## Licenc
<!-- README-SYNC:license -->

Az UAG az alábbi licenc alatt érhető el: [Apache License 2.0](../LICENSE).
