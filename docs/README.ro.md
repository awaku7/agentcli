<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="UAG — Universal AI Gateway" width="620">
</p>
<h1 align="center">UAG</h1>
<p align="center"><strong>Universal AI Gateway</strong><br>Modelele dvs. AI. Instrumentele dvs. Mediul dvs.</p>

<p align="center">
  <a href="https://github.com/awaku7/agentcli/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/awaku7/agentcli/ci.yml?style=flat-square&label=CI" alt="CI"></a>
  <a href="https://pypi.org/project/uag/"><img src="https://img.shields.io/pypi/v/uag?style=flat-square" alt="PyPI"></a>
  <a href="https://pypi.org/project/uag/"><img src="https://img.shields.io/pypi/pyversions/uag?style=flat-square" alt="Python versions"></a>
  <a href="../LICENSE"><img src="https://img.shields.io/github/license/awaku7/agentcli?style=flat-square" alt="License"></a>
  <a href="https://pepy.tech/projects/uag"><img src="https://static.pepy.tech/personalized-badge/uag?period=total&units=INTERNATIONAL_SYSTEM&left_color=grey&right_color=green&left_text=downloads" alt="Downloads"></a>
</p>
<p align="center"><a href="../README.md">English</a> · <a href="README.translations.md">Alte limbi</a></p>

---

**UAG este un mediu open-source de execuție pentru agenți AI, orientat spre rularea locală.** Conectează modelul lingvistic ales la instrumentele și sistemele pe care le folosiți. Puteți lucra cu cod, fișiere, browsere, servicii și dispozitive printr-o interfață unitară, fără să depindeți de un singur furnizor de modele.

| **Alegeți modelul** | **Conectați instrumente reale** | **Păstrați controlul** |
| :--- | :--- | :--- |
| Modele găzduite sau locale: OpenAI, Claude, Gemini, Grok, Bedrock și Ollama | Fișiere, cod, web, MCP, Agent Skills, pluginuri, servicii cloud și IoT | Rulare locală, confirmare umană, stocarea acreditărilor și politici configurabile |

> UAG este **stratul de execuție a agenților, nu un furnizor de modele**. Solicitările către modele și servicii externe depind de configurație. Prioritatea locală nu înseamnă funcționare complet offline sau izolarea implicită a tuturor instrumentelor.

## Pornire rapidă
<!-- README-SYNC:quick-start -->

Este necesar **Python 3.11 sau mai nou**. Instalați UAG din [PyPI](https://pypi.org/project/uag/) și porniți interfața interactivă în linie de comandă:

~~~bash
python -m pip install --upgrade uag
uag
~~~

La prima pornire, asistentul vă ajută să alegeți furnizorul și să configurați acreditările. Sunt disponibile și variabile de mediu sau depozitul de acreditări. Pentru a instala din timp mai multe dependențe de furnizori și instrumente:

~~~bash
python -m pip install "uag[core,providers,tools]"
~~~

Apoi încercați următoarele cereri:

~~~text
> Ce s-a schimbat în acest depozit Git? Rezumă riscurile.
> Găsește cea mai recentă documentație a bibliotecii și explică migrarea.
> Examinează aceste fișiere și pregătește un raport scurt.
> :help
~~~

Dacă sunteți la început, consultați ghidul pentru Windows, care include Git și mediile virtuale, și referința de configurare: [Quickstart (Windows)](QUICKSTART.md) · [Environment](ENVIRONMENT.md).

## Interfețe
<!-- README-SYNC:interfaces -->

Toate intrările folosesc același motor de agenți și același registru de instrumente.

| Interfață | Pornire | Potrivită pentru |
| :--- | :--- | :--- |
| **CLI** | `uag` | Terminal și automatizare |
| **Desktop** | `uagg` | Conversații în aplicația nativă |
| **Web** | `uagw` | Conversații și camere în browser |
| **A2A** | `uaga` | Colaborare între agenți |
| **VS Code** | [Ghidul extensiei](VSCODE.md) | Lucru alături de cod |

Interfețele Desktop și Web necesită dependențe suplimentare, care nu sunt incluse în `uag[core,providers,tools]`:

~~~bash
# Desktop GUI (PySide6 and platform integrations)
python -m pip install "uag[platform]"

# Web UI (authentication dependencies, FastAPI, and Uvicorn)
python -m pip install "uag[web]" fastapi uvicorn
~~~

Serverul Web poate încerca să instaleze FastAPI și Uvicorn la pornire. Instalarea lor în avans elimină această dependență. Detalii: [CLI usage](USAGE.md) · [Environment](ENVIRONMENT.md).

## Ce puteți realiza cu UAG
<!-- README-SYNC:capabilities -->

| Funcționalitate | Ce oferă UAG |
| :--- | :--- |
| **Fluxuri independente de model** | Schimbați furnizorii locali sau cloud prin `UAGENT_PROVIDER`, fără rescrierea instrumentelor |
| **Cod și fișiere** | Navigarea depozitelor, analiza Git, lint, teste, operațiuni cu fișiere și automatizarea browserului |
| **Instrumente extensibile** | Peste 200 de instrumente, descoperire dinamică prin `tool_catalog` / `tool_load`, instrumente Python și Rust personalizate |
| **Agenți conectați** | MCP, A2A, pluginuri compatibile Claude Code, Agent Skills și subagenți |
| **Sarcini de durată** | Pilot automat, citiri independente paralele, programări, recuperare și sesiuni persistente |
| **Dincolo de terminal** | Cloud, comunicații, documente, media, voce în timp real și protocoale IoT acceptate |

### Un singur mediu de rulare, multe integrări
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

**Exemple de furnizori de modele compatibili** sunt enumerate mai jos. Configurațiile specifice se găsesc în ghidul mediului.

**OpenAI · Anthropic · Gemini · Vertex AI · Azure OpenAI · Amazon Bedrock · Grok · DeepSeek · OpenRouter · Ollama · llama.cpp · LM Studio**

[ENVIRONMENT.md](ENVIRONMENT.md)

### Personalizare prin skills și pluginuri
<!-- README-SYNC:extensions -->

Extindeți UAG fără modificarea nucleului. Instalați Agent Skills din SkillsMP sau ClawHub, conectați servere MCP ori încărcați pluginuri compatibile Claude Code cu instrumente, skills, agenți și hooks.

~~~text
:skills mp_search browser automation
:plugin list
:plugin install <source>
:plugin marketplace list
~~~

Instrumentele proprii pot expune `TOOL_SPEC` și `run_tool()`; sunt acceptate și cele bazate pe Rust. Consultați ghidurile: [Tool Creator Guide](../TOOL_CREATOR_GUIDE.md) · [Plugin Development Guide](../src/uagent/docs/DEVELOP_PLUGIN.md) · [MCP OAuth / Proxy](MCP_OAUTH_PROXY_GUIDE.md).

## Conceput pentru activități reale
<!-- README-SYNC:workflows -->

### Context și memorie
<!-- README-SYNC:context-memory -->

Rezultatele voluminoase pot fi păstrate ca **artefacte** în loc să ocupe contextul activ al modelului. Agentul recuperează ulterior doar partea necesară prin `artifact_read`. Sesiunile sunt salvate implicit în SQLite, cu căutare în istoric și revizuirea explicită a memoriei.

- [Context compression](CONTEXT_COMPRESSION.ro.md)
- [Memory](MEMORY.md)
- [Session portability](SESSION_PORTABILITY.md)

### Automatizare și colaborare
<!-- README-SYNC:automation -->

UAG suportă citiri independente în paralel, coordonare multi-agent, recuperarea sesiunilor și pilot automat pentru activități în mai multe runde. Porniți-l cu `:auto`; tasta **F12** întrerupe răspunsul curent și solicită oprirea pilotului automat.

- [Auto-pilot](README_AUTO.md)
- [Timers and scheduled tasks](SET_TIMER.md)
- [Multi-agent runtime](MULTI_AGENT_RUNTIME.md)

### Securitate și observabilitate
<!-- README-SYNC:security -->

Acțiunile sensibile pot necesita confirmare `human_ask`. Acreditările se pot stoca în managerul sistemului de operare sau într-un fișier criptat. Interfața Web permite autentificare OIDC și controlul accesului, dacă sunt configurate. Urmărirea și metricile OpenTelemetry sunt **opționale**.

- [Enterprise policies](ENTERPRISE_POLICY.md)
- [MXC sandbox](SANDBOX_MXC.md)
- [Remote Web / A2A MXC defaults](REMOTE_MXC_DEFAULT.md)
- [Web identity and rooms](WEB_IDENTITY_MEMORY.md)
- [OpenTelemetry design](UAG_OPENTELEMETRY_DESIGN.md)
- [Developer observability](../src/uagent/docs/DEVELOP_OBSERVABILITY.md)

Aceste măsuri sunt configurabile și **nu garantează** izolarea în sandbox a oricărei execuții de instrument. Citiți ghidurile de implementare și politici înainte de a expune UAG unor utilizatori sau rețele de neîncredere.

### Limbi, dispozitive și voce
<!-- README-SYNC:languages -->

UAG include resurse pentru **38 de variante lingvistice** (engleza și 37 de traduceri), integrare vocală full-duplex opțională și instrumente pentru SwitchBot, Matter, ECHONET Lite, BACnet, Modbus TCP și OPC UA.

- [Translations](README.translations.md)
- [IoT use cases](IOT_USECASE.md)
- [Communication tools](COMMUNICATION.md)

## Documentație
<!-- README-SYNC:documentation -->

Începeți cu aceste ghiduri și continuați cu subiectele detaliate:

| Pentru început | Aprofundare |
| :--- | :--- |
| [Quickstart (Windows)](QUICKSTART.md) | [Architecture](ARCHITECTURE.md) |
| [CLI usage](USAGE.md) | [Context management](UAG_CONTEXT_MANAGEMENT_DESIGN.md) |
| [Environment and providers](ENVIRONMENT.md) | [Enterprise policy](ENTERPRISE_POLICY.md) |
| [Agent Skills and plugins](../src/uagent/docs/DEVELOP_PLUGIN.md) | [Tool flow](../src/uagent/docs/TOOL_FLOW.md) |
| [MCP and OAuth](MCP_OAUTH_PROXY_GUIDE.md) | [Computer Use](COMPUTER_USE_IMPLEMENTATION.md) |
| [VS Code extension](VSCODE.md) | [Developer guide](../src/uagent/docs/DEVELOP.md) |

Puteți parcurge și directorul complet de documentație și traducerile: [Documentation](./) · [Other languages](README.translations.md).

## Dezvoltare și contribuții
<!-- README-SYNC:contributing -->

~~~bash
git clone https://github.com/awaku7/agentcli.git
cd agentcli
python -m pip install -e ".[core,providers,test]"
~~~

Înainte de un pull request care modifică **cod Python**, rulați testele relevante și verificările proiectului:

~~~bash
python -m ruff check src tests
python -m black --check src tests
python -m pytest -q .
~~~

Regulile de contribuție și ghidul dezvoltatorului sunt mai jos. Sunt binevenite raportări de erori, îmbunătățiri ale documentației, instrumente, traduceri și pull requesturi focalizate: [AGENTS.md](../AGENTS.md) · [Developer guide](../src/uagent/docs/DEVELOP.md).

## Licență
<!-- README-SYNC:license -->

UAG este distribuit sub licența: [Apache License 2.0](../LICENSE).
