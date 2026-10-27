<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="680">
</p>

<h1 align="center">uag</h1>

<p align="center">
  <strong>Universal AI Gateway</strong><br>
  Un agent local. Orice model. Orice instrument. Mediul tău, regulile tale.
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
  <a href="https://github.com/awaku7/agentcli/discussions">Discussions</a> ·
  <a href="https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md">Traduceri</a>
</p>

______________________________________________________________________

**De ce uag?**

uag este un agent AI local-first care conectează modelul preferat de instrumentele pe care le folosești efectiv.
Îți oferă un singur runtime extensibil pentru fișiere, browsere, baze de cod, comunicare, API-uri cloud,
dispozitive IoT, servere MCP și fluxuri de lucru cu mai mulți agenți.

- **Libertatea furnizorului** — OpenAI, Anthropic, Gemini, Azure, Bedrock, Ollama, llama.cpp, Grok, DeepSeek și altele.
- **Execuție local-first** — runtime-ul agentului și execuția instrumentelor rămân pe mașina ta; doar apelurile API pe care le alegi părăsesc mașina.
- **Un singur nivel de instrumente** — aceleași instrumente funcționează din CLI, interfața grafică desktop, interfața web, VS Code și A2A.
- **Paralelă prin proiectare** — operațiunile independente, doar pentru citire, pot rula simultan.
- **Extensibil** — adaugă instrumente, pluginuri, Agent Skills, servere MCP și instrumente bazate pe Rust fără a modifica nucleul.
- **Conștient de siguranță** — acțiunile distructive, acreditările, comenzile dispozitivelor și scrierile în rețea acceptă confirmare explicită și controale de politică.

> **Pe scurt:** uag este planul de control dintre modelele tale AI și mediul tău real.

> **🧠 Rezultate ale instrumentelor adaptate la context** — Rezultatele voluminoase ale instrumentelor sunt excluse din contextul modelului activ, atunci când este posibil. uag le stochează ca artefacte și transmite modelului o previzualizare limitată cu o referință stabilă Artifact. Acest lucru poate reduce substanțial numărul de tokenuri de intrare necesare pentru rundele următoare atunci când un instrument produce un rezultat voluminos.
> [Ghid detaliat pentru comprimarea contextului](CONTEXT_COMPRESSION.ro.md)

## Pornire rapidă

**Python 3.11+**

```bash
python -m pip install --upgrade uag
uag
```

La prima pornire se deschide expertul de configurare. Acesta te ajută să configurezi un furnizor și stochează setările selectate
în mediul tău local.

Pentru grupurile uzuale de funcții:

```bash
python -m pip install "uag[core,providers,tools]"
```

> Integrările de platformă sunt opționale. Instalează doar ceea ce necesită sistemul tău de operare; vezi

```text
> What files changed in this repository?
> Search the web for today's AI news and summarize the top five stories.
> :help
```

[Quickstart](QUICKSTART.md) · [Environment](ENVIRONMENT.md)

## Interfețe

| Interfață | Comandă | Potrivită pentru |
|---|---|---|
| **CLI** | `uag` | Lucru rapid, bazat pe tastatură |
| **Interfață grafică desktop** | `uagg` | O experiență desktop nativă |
| **Interfață web** | `uagw` | Acces din browser |
| **Server A2A** | `uaga` | Comunicare agent-la-agent |
| **VS Code** | Extension | Explicarea, refactorizarea, repararea și explorarea instrumentelor în editor |

Toate interfețele folosesc aceeași configurare a furnizorului, același registru de instrumente, aceleași reguli de siguranță și aceleași date de sesiune.

~~~bash
# Desktop GUI
python -m pip install "uag[platform]"

# Web UI
python -m pip install "uag[web]" fastapi uvicorn
~~~

[Interface options](USAGE.md) · [Environment](ENVIRONMENT.md)

## Ce poți crea

Adaptoarele de furnizori acoperă runtime-uri găzduite și locale, inclusiv:

- Citește, creează, editează, caută, calculează hash-uri, arhivează și inspectează fișiere
- Revizuiește modificările Git, caută secrete, rulează teste, face linting, compilează și măsoară acoperirea
- Navighează baze mari de cod Python, TypeScript, JavaScript, Go, Rust, C/C++, Java, C#, COBOL, VBA și alte limbaje
- Automatizează browsere cu Playwright, inclusiv fluxuri cu mai multe pagini și descărcări

- **MCP** — conectează servere externe de instrumente, inclusiv servicii cu OAuth
- **A2A** — coordonează-te cu alți agenți și servere compatibile
- **Cloud** — acces la API-urile AWS, Google Cloud și Azure, cu confirmare pentru scrieri
- **Communication** — Gmail, Bluesky, Discord, Microsoft Teams și pybitchat
- **IoT** — SwitchBot, ECHONET Lite, Matter, BACnet, Modbus TCP, OPC UA și UPnP
- **Media** — generare/editare de imagini, transcriere/sinteză audio, captură de la cameră și coduri QR
- **Documents** — PDF, PowerPoint, Word, Excel, CSV, JSON, YAML, SQL și analiză de jurnale

- **SwitchBot** — descoperire în cloud și BLE, stare, control, grupare și abonamente
- **ECHONET Lite** — descoperă și controlează aparate electrocasnice japoneze, inclusiv notificări INF
- **Matter** — endpoint-uri, clustere, atribute, istoric de stare, abonamente și control
- **BACnet / Modbus TCP / OPC UA** — citiri, scrieri, navigare și monitorizare pentru automatizări industriale și de clădiri
- **UPnP** — descoperirea dispozitivelor, starea WAN și gestionarea mapării porturilor routerului

### Locul lui uag

uag se află între oameni și interfețe, pe de o parte, și modele, instrumente și sisteme din lumea reală, pe de altă parte.
Coordonează conversația, selectează capabilitățile, aplică regulile de siguranță și menține fluxul de lucru reluabil.

~~~mermaid
flowchart LR
    UI["CLI · Desktop · Web · VS Code · A2A"] --> UAG["UAG agent runtime"]
    UAG --> MODELS["Hosted & local models"]
    UAG --> TOOLS["Tools & extensions"]
    UAG --> STATE["Sessions & context"]
    TOOLS --> SYSTEMS["Files · Code · Web · MCP · Cloud · IoT"]
    POLICY["Confirmation · Credentials · Policy"] -.-> UAG
~~~

### Pluginuri, Agent Skills și marketplace-uri

Transformă uag într-un agent specializat fără să separi nucleul:

- Instalează **pluginuri compatibile cu Claude Code** dintr-un director, ZIP, depozit Git, sursă HTTP sau marketplace
- Grupează skill-uri, sub-agenți, servere MCP, hook-uri, comenzi slash, stiluri de ieșire, dependențe și canale
- Explorează capabilități ale comunității din [SkillsMP](https://skillsmp.com) și [ClawHub](https://clawhub.ai)
- Adaugă local skill-uri și instrumente private ale organizației prin `UAGENT_EXTERNAL_TOOLS_DIR`

```text
:skills mp_search browser automation
:plugin list
:plugin install <source>
:plugin marketplace list
```

Vezi [Ghidul de dezvoltare a pluginurilor](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP_PLUGIN.md).

- **Peste 200 de instrumente** pentru fișiere, web, media, documente, cod, cloud, comunicare și IoT
- **Descoperire și încărcare dinamică** — folosește `tool_catalog` pentru a găsi capabilități și `tool_load` pentru a le activa doar când este necesar
- **Inteligență pentru cod** — `code_map`, navigatoare `idx` specifice limbajului, revizuire Git, execuția testelor, linting, compilare și acoperire
- **Pluginuri compatibile cu Claude Code** cu skill-uri, agenți, servere MCP, hook-uri, comenzi și marketplace-uri
- **Agent Skills** de la SkillsMP și ClawHub
- **Instrumente Python personalizate** cu `TOOL_SPEC` și `run_tool()`
- **Instrumente bazate pe Rust** pentru extensii native ușoare

[Tool Creator Guide](../TOOL_CREATOR_GUIDE.md) · [MCP OAuth / Proxy Guide](MCP_OAUTH_PROXY_GUIDE.md)

## Creat pentru fluxuri de lucru reale

### 🧠 Rezultate ale instrumentelor adaptate la context

Rezultatele voluminoase ale instrumentelor sunt excluse din contextul modelului activ, atunci când este posibil. uag le stochează ca artefacte și transmite modelului o previzualizare limitată cu o referință stabilă Artifact. Acest lucru poate reduce substanțial numărul de tokenuri de intrare necesare pentru rundele următoare atunci când un instrument produce un rezultat voluminos.

Reia conversațiile anterioare cu `:load <index>`. Rezultatele instrumentelor pot fi păstrate în cache, iar furnizorii pot fi schimbați
fără a reconstrui aplicația.

[Context compression](CONTEXT_COMPRESSION.ro.md) · [Memory](MEMORY.md) · [Session portability](SESSION_PORTABILITY.md)

### Pilot automat

Folosește `:auto` pentru lucrări în mai multe runde, cu un model revizor opțional. Setează limita rundelor cu `--max-rounds N`.
Apasă **F12** pentru a opri pilotul automat sau **F12** pentru a opri răspunsul curent.

Operațiunile independente, doar pentru citire, rulează simultan atunci când este sigur. Căutările web, inspectarea fișierelor,
analiza depozitului și sarcinile similare se pot finaliza în paralel cu un pool configurabil de lucrători
(`UAGENT_PARALLEL_WORKERS`). Operațiunile de scriere rămân serializate sau necesită confirmare.

Continuitatea sesiunii, stocarea în cache a rezultatelor instrumentelor, starea loturilor, recuperarea după repornire,
planificarea DAG și orchestrarea mai multor agenți fac ca lucrările complexe să poată fi reluate, nu să fie executate o singură dată.

[Auto-pilot](README_AUTO.md) · [Timers](SET_TIMER.md) · [Multi-agent runtime](MULTI_AGENT_RUNTIME.md)

### 🌍 Privat, multilingv și conștient de politici

`human_ask` pune pe pauză execuția înaintea acțiunilor sensibile. Ștergerea fișierelor, suprascrierile, comenzile shell, comenzile dispozitivelor,
operațiunile cu acreditări și scrierile în rețea pot fi guvernate de reguli de confirmare și politici.

Folosește magazinul de acreditări în loc să plasezi secrete cu durată lungă de viață în prompturi:

Interfața web include autentificare OIDC folosind Authorization Code + PKCE, tokenuri ID verificate, sesiuni server-side și controale de acces pentru proiecte/camere. Afirmările de grup Microsoft Entra ID verificate pot alimenta politica de acces bazată pe director atunci când sunt configurate. Implementările Windows Active Directory, OAuth și trusted-proxy pot fi integrate prin adaptoare de identitate verificate explicit; Windows AD necesită un verificator Kerberos/Negotiate specific implementării și nu este activat implicit.

uag include urmărire OpenTelemetry opțională și independentă de furnizor, precum și metrici pentru operațiile Agent, LLM, instrument, Context, Memory și recuperare. Observabilitatea este dezactivată în mod implicit.

Prioritizarea rulării locale nu înseamnă că UAG funcționează implicit complet offline sau că toate instrumentele sunt izolate. Apelurile către modele și servicii externe depind de configurare.

- [Enterprise policies](ENTERPRISE_POLICY.md)
- [MXC sandbox](SANDBOX_MXC.md)
- [Remote Web / A2A](REMOTE_MXC_DEFAULT.md)
- [Web identity](WEB_IDENTITY_MEMORY.md)
- [OpenTelemetry](UAG_OPENTELEMETRY_DESIGN.md)

### 🌍 Traducere multilingvă

- `translate_text` acceptă Google Translate și clientul oficial DeepL pentru Python prin intermediul `provider=auto`, `provider=deepl` sau `provider=google`.
- Definițiile instrumentelor sunt disponibile în 37 de seturi de localizare plus engleză (38 în total), cu păstrarea substituenților și a identificatorilor tehnici.

Vocea full-duplex este disponibilă prin OpenAI Realtime, Azure OpenAI, xAI Grok Voice, Gemini Live
și Bedrock Nova Sonic, cu anulare opțională a ecoului AEC3 și apelare de funcții în timp real limitată de siguranță.

[Translations](README.translations.md) · [IoT](IOT_USECASE.md) · [Communication](COMMUNICATION.md)

## Documentație

| Subiect | Documentație |
|---|---|
| Variabile de mediu | [docs/ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/docs/ENVIRONMENT.md) |
| Arhitectură și invariabile | [docs/ARCHITECTURE.md](https://github.com/awaku7/agentcli/blob/main/docs/ARCHITECTURE.md) |
| Computer Use | [docs/COMPUTER_USE_IMPLEMENTATION.md](https://github.com/awaku7/agentcli/blob/main/docs/COMPUTER_USE_IMPLEMENTATION.md) |
| Instrumente ale depozitului | [docs/REPOSITORY_TOOLS.md](https://github.com/awaku7/agentcli/blob/main/docs/REPOSITORY_TOOLS.md) |
| Cazuri de utilizare IoT | [docs/IOT_USECASE.md](https://github.com/awaku7/agentcli/blob/main/docs/IOT_USECASE.md) |
| Instrumente de comunicare | [docs/COMMUNICATION.md](https://github.com/awaku7/agentcli/blob/main/docs/COMMUNICATION.md) |
| Pilot automat | [docs/README_AUTO.md](https://github.com/awaku7/agentcli/blob/main/docs/README_AUTO.md) |
| OAuth / Proxy MCP | [docs/MCP_OAUTH_PROXY_GUIDE.md](https://github.com/awaku7/agentcli/blob/main/docs/MCP_OAUTH_PROXY_GUIDE.md) |
| Extensia VS Code | [docs/VSCODE.md](https://github.com/awaku7/agentcli/blob/main/docs/VSCODE.md) |
| Ghidul dezvoltatorului | [src/uagent/docs/DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md) |
| Fluxul instrumentelor | [src/uagent/docs/TOOL_FLOW.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/TOOL_FLOW.md) |

[Quickstart](QUICKSTART.md) · [Architecture](ARCHITECTURE.md) · [Context management](UAG_CONTEXT_MANAGEMENT_DESIGN.md)

## Dezvoltare și contribuție

```bash
git clone https://github.com/awaku7/agentcli.git
cd agentcli
python -m pip install -e ".[core,providers,test]"
```

Rulează verificările pre-PR:

```bash
python -m ruff check src tests
python -m black --check src tests
python -m pytest -q .
```

Pentru fluxul complet de dezvoltare, vezi [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md).

Rapoartele de erori, ideile de funcții, îmbunătățirile documentației, traducerile, instrumentele, skill-urile și pull request-urile sunt binevenite.
Te rugăm să deschizi un issue sau o discuție înainte de modificări ample. Citește [Ghidul dezvoltatorului](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)
și rulează verificările de mai sus înainte de a trimite un pull request.

## Licență

Licențiat sub [Apache License 2.0](https://github.com/awaku7/agentcli/blob/main/LICENSE).
