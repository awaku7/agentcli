<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="680">
</p>

<h1 align="center">uag</h1>

<p align="center">
  <strong>Universal AI Gateway</strong><br>
  Egy helyi ügynök. Bármely modell. Bármely eszköz. A te környezeted, a te szabályaid.
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
  <a href="https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md">Translations</a>
</p>

______________________________________________________________________

**Miért az uag?**

Az uag local-first szemléletű AI-ügynök, amely összekapcsolja az általad előnyben részesített modellt a ténylegesen használt eszközeiddel.
Egyetlen, bővíthető futtatókörnyezetet biztosít fájlokhoz, böngészőkhöz, kódbázisokhoz, kommunikációhoz, felhőalapú API-khoz,
IoT-eszközökhöz, MCP-szerverekhez és többügynökös munkafolyamatokhoz.

- **Szolgáltatói szabadság** — OpenAI, Anthropic, Gemini, Azure, Bedrock, Ollama, llama.cpp, Grok, DeepSeek és mások.
- **Local-first végrehajtás** — az ügynök futtatókörnyezete és az eszközök végrehajtása a gépeden marad; csak az általad választott API-hívások hagyják el azt.
- **Egyetlen eszközréteg** — ugyanazok az eszközök működnek a CLI-ból, az asztali GUI-ból, a webes felületről, a VS Code-ból és az A2A-ból.
- **Párhuzamosságra tervezve** — a független, csak olvasási műveletek párhuzamosan futhatnak.
- **Bővíthető** — eszközöket, bővítményeket, Agent Skills-képességeket, MCP-szervereket és Rust-alapú eszközöket adhatsz hozzá a mag módosítása nélkül.
- **Biztonságtudatos** — a romboló műveletek, hitelesítő adatok, eszközvezérlések és hálózati írások támogatják a kifejezett megerősítést és a szabályozási vezérlőket.

> **Röviden:** az uag a vezérlési sík az AI-modelljeid és a valós környezeted között.

> **🧠 Kontextustudatos eszköz-eredmények** — A nagy méretű eszköz-eredményeket – amennyiben lehetséges – kizárják az aktív modell kontextusából. A uag ezeket Artifactként tárolja, és helyette egy korlátozott előnézetet ad át a modellnek, stabil Artifact hivatkozással. Ez jelentősen csökkentheti a következő körökhöz szükséges bemeneti tokenek számát, amikor egy eszköz nagy eredményt produkál.
> [Részletes útmutató a kontextustömörítéshez](CONTEXT_COMPRESSION.hu.md)

## Gyors kezdés

**Python 3.11+**

```bash
python -m pip install --upgrade uag
uag
```

Az első indítás megnyitja a beállítási varázslót. Segít beállítani egy szolgáltatót, és a kiválasztott beállításokat
elmenti a helyi környezetedbe.

A leggyakoribb funkciócsoportokhoz:

```bash
python -m pip install "uag[core,providers,tools]"
```

> A platformintegrációk opcionálisak. Csak azt telepítsd, amire az operációs rendszerednek szüksége van; lásd a

```text
> What files changed in this repository?
> Search the web for today's AI news and summarize the top five stories.
> :help
```

[Quickstart](QUICKSTART.md) · [Environment](ENVIRONMENT.md)

## Felületek

| Felület | Parancs | Leginkább erre alkalmas |
|---|---|---|
| **CLI** | `uag` | Gyors, billentyűzetközpontú munka |
| **Asztali GUI** | `uagg` | Natív asztali élmény |
| **Webes felület** | `uagw` | Böngészőalapú hozzáférés |
| **A2A-szerver** | `uaga` | Ügynökök közötti kommunikáció |
| **VS Code** | Extension | Eszközök magyarázata, refaktorálása, javítása és böngészése a szerkesztőben |

Minden felület ugyanazt a szolgáltatói konfigurációt, eszközregisztrációt, biztonsági szabályokat és munkamenetadatokat használja.

~~~bash
# Desktop GUI
python -m pip install "uag[platform]"

# Web UI
python -m pip install "uag[web]" fastapi uvicorn
~~~

[Interface options](USAGE.md) · [Environment](ENVIRONMENT.md)

## Mit építhetsz

A szolgáltatóadapterek hosztolt és helyi futtatókörnyezeteket fednek le, többek között:

**OpenAI · Meta Model API · Anthropic · Google Gemini · Vertex AI · Azure OpenAI · Amazon Bedrock · OpenRouter · Ollama · llama.cpp · Grok · DeepSeek · NVIDIA · Hugging Face · Alibaba Cloud · Moonshot · Xiaomi MiMo · LM Studio · MiniMax · Sakana AI · SAKURA AI Engine · Together AI · Vercel AI Gateway · PFN/PLaMo · Z.AI · Novita**

Válts szolgáltatót a `UAGENT_PROVIDER` használatával; az eszközeid és a felületed nem változik.

**Együttműködés a környezeteddel**

- Fájlok olvasása, létrehozása, szerkesztése, keresése, hash-elése, archiválása és vizsgálata
- Git-módosítások áttekintése, titkok keresése, tesztek futtatása, lintelés, fordítás és a lefedettség mérése
- Nagy Python-, TypeScript-, JavaScript-, Go-, Rust-, C/C++-, Java-, C#-, COBOL-, VBA- és egyéb kódbázisok navigálása
- Böngészők automatizálása Playwrighttal, többoldalas munkafolyamatokkal és letöltésekkel együtt

**Szolgáltatások és eszközök csatlakoztatása**

- **MCP** — külső eszközszerverek csatlakoztatása, beleértve az OAuth-kompatibilis szolgáltatásokat
- **A2A** — együttműködés más ügynökökkel és kompatibilis szerverekkel
- **Cloud** — AWS-, Google Cloud- és Azure-API-hozzáférés írások esetén megerősítéssel
- **Communication** — Gmail, Bluesky, Discord, Microsoft Teams és pybitchat
- **IoT** — SwitchBot, ECHONET Lite, Matter, BACnet, Modbus TCP, OPC UA és UPnP
- **Media** — képgenerálás/-szerkesztés, hangátírás/-beszéd, kamerafelvétel és QR-kódok
- **Documents** — PDF, PowerPoint, Word, Excel, CSV, JSON, YAML, SQL és naplóelemzés

**IoT- és fizikai világ vezérlése**

- **SwitchBot** — felhő- és BLE-felfedezés, állapot, vezérlés, kötegelt műveletek és feliratkozások
- **ECHONET Lite** — japán háztartási készülékek felfedezése és vezérlése, beleértve az INF-értesítéseket
- **Matter** — végpontok, clusterek, attribútumok, állapottörténet, feliratkozások és vezérlés
- **BACnet / Modbus TCP / OPC UA** — ipari és épületautomatizálási olvasás, írás, böngészés és felügyelet
- **UPnP** — eszközfelfedezés, WAN-állapot és routeres porttovábbítás kezelése

### Hol helyezkedik el az uag?

Az uag az egyik oldalon az emberek és a felületek, a másikon pedig a modellek, az eszközök és a valós rendszerek között helyezkedik el.
Összehangolja a beszélgetést, kiválasztja a képességeket, alkalmazza a biztonsági szabályokat, és folytathatóvá teszi a munkafolyamatot.

~~~mermaid
flowchart LR
    UI["CLI · Desktop · Web · VS Code · A2A"] --> UAG["UAG agent runtime"]
    UAG --> MODELS["Hosted & local models"]
    UAG --> TOOLS["Tools & extensions"]
    UAG --> STATE["Sessions & context"]
    TOOLS --> SYSTEMS["Files · Code · Web · MCP · Cloud · IoT"]
    POLICY["Confirmation · Credentials · Policy"] -.-> UAG
~~~

### Bővítmények, Agent Skills és piacterek

Alakítsd az uag-t specializált ügynökké a mag elágaztatása nélkül:

- **Claude Code-kompatibilis bővítmények** telepítése könyvtárból, ZIP-fájlból, Git-tárházból, HTTP-forrásból vagy piactérről
- Skillek, alügynökök, MCP-szerverek, hookok, perjeles parancsok, kimeneti stílusok, függőségek és csatornák csomagolása
- Közösségi képességek böngészése a [SkillsMP](https://skillsmp.com) és a [ClawHub](https://clawhub.ai) kínálatából
- Privát szervezeti skillek és eszközök helyi hozzáadása a `UAGENT_EXTERNAL_TOOLS_DIR` használatával

```text
:skills mp_search browser automation
:plugin list
:plugin install <source>
:plugin marketplace list
```

Lásd a [Plugin Development Guide](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP_PLUGIN.md) útmutatót.

- **200+ eszköz** fájlokhoz, webhez, médiához, dokumentumokhoz, kódhoz, felhőhöz, kommunikációhoz és IoT-hoz
- **Dinamikus felfedezés és betöltés** — használd a `tool_catalog` eszközt a képességek megtalálásához, a `tool_load` eszközt pedig csak szükség esetén való engedélyezésükhöz
- **Kódintelligencia** — `code_map`, nyelvspecifikus `idx` navigátorok, Git-áttekintés, tesztfuttatás, lintelés, fordítás és lefedettségmérés
- **Claude Code-kompatibilis bővítmények** skillekkel, ügynökökkel, MCP-szerverekkel, hookokkal, parancsokkal és piacterekkel
- **Agent Skills** a SkillsMP-ről és a ClawHubról
- **Egyéni Python-eszközök** `TOOL_SPEC` és `run_tool()` használatával
- **Rust-alapú eszközök** könnyű natív bővítményekhez

[Tool Creator Guide](../TOOL_CREATOR_GUIDE.md) · [MCP OAuth / Proxy Guide](MCP_OAUTH_PROXY_GUIDE.md)

## Valós munkafolyamatokra tervezve

### 🧠 Kontextustudatos eszköz-eredmények

A nagy méretű eszköz-eredményeket – amennyiben lehetséges – kizárják az aktív modell kontextusából. A uag ezeket Artifactként tárolja, és helyette egy korlátozott előnézetet ad át a modellnek, stabil Artifact hivatkozással. Ez jelentősen csökkentheti a következő körökhöz szükséges bemeneti tokenek számát, amikor egy eszköz nagy eredményt produkál.

Folytasd a korábbi beszélgetéseket a `:load <index>` paranccsal. Az eszközeredmények gyorsítótárazhatók, a szolgáltatók pedig módosíthatók
az alkalmazás újraépítése nélkül.

[Context compression](CONTEXT_COMPRESSION.hu.md) · [Memory](MEMORY.md) · [Session portability](SESSION_PORTABILITY.md)

### Automata pilóta

Használd a `:auto` parancsot többfordulós munkához, opcionális ellenőrző modellel. A fordulók számának korlátját a `--max-rounds N` kapcsolóval állítsd be.
A **F12** billentyűvel leállíthatod az automata pilótát, a **F12** billentyűvel pedig az aktuális választ.

A független, csak olvasási műveletek biztonságos esetben párhuzamosan futnak. A webes keresések, a fájlvizsgálat,
a repository elemzése és a hasonló terhelések párhuzamosan fejeződhetnek be egy konfigurálható worker pool
(`UAGENT_PARALLEL_WORKERS`) segítségével. Az írási műveletek sorosítva maradnak, vagy megerősítést igényelnek.

A munkamenet-folytonosság, az eszközeredmények gyorsítótárazása, a kötegállapot, az újraindítás utáni helyreállítás,
a DAG-ütemezés és a többügynökös koordináció folytathatóvá teszi az összetett munkát az egyszeri futtatás helyett.

[Auto-pilot](README_AUTO.md) · [Timers](SET_TIMER.md) · [Multi-agent runtime](MULTI_AGENT_RUNTIME.md)

### 🌍 Privát, többnyelvű és szabályzat-tudatos

A `human_ask` szünetet tart az érzékeny műveletek előtt. A fájltörlés, a felülírások, a shell-parancsok, az eszközvezérlések,
a hitelesítőadat-műveletek és a hálózati írások megerősítési és szabályzati előírásokkal vezérelhetők.

Hosszú élettartamú titkok promptokba helyezése helyett használd a hitelesítőadat-tárolót:

A Web UI tartalmazza az OIDC bejelentkezést Authorization Code + PKCE használatával, ellenőrzött ID tokeneket, szerveroldali munkameneteket és projekt/szoba hozzáférés-vezérlést. Az ellenőrzött Microsoft Entra ID csoportigények konfigurálás esetén táplálhatják a könyvtár-alapú hozzáférési szabályzatot. A Windows Active Directory, OAuth és trusted-proxy telepítések explicit, telepítés-specifikus ellenőrzött adaptereken keresztül integrálhatók; a Windows AD telepítés-specifikus Kerberos/Negotiate ellenőrzőt igényel, és alapértelmezés szerint nincs engedélyezve.

A uag opcionális, szolgáltatófüggetlen OpenTelemetry-nyomkövetést és metrikákat biztosít az Agent, LLM, eszköz, Context, Memory és visszakeresési műveletekhez. A megfigyelhetőség alapértelmezés szerint le van tiltva.

A local-first működés nem jelenti azt, hogy az UAG alapértelmezés szerint teljesen offline, vagy hogy minden eszköz futása el van szigetelve. A külső modellek és kapcsolt szolgáltatások hívása a beállításoktól függ.

- [Enterprise policies](ENTERPRISE_POLICY.md)
- [MXC sandbox](SANDBOX_MXC.md)
- [Remote Web / A2A](REMOTE_MXC_DEFAULT.md)
- [Web identity](WEB_IDENTITY_MEMORY.md)
- [OpenTelemetry](UAG_OPENTELEMETRY_DESIGN.md)

### 🌍 Többnyelvű fordítás

- A `translate_text` támogatja a Google Translate-t és a hivatalos DeepL Python-klienst a `provider=auto`, `provider=deepl` vagy `provider=google` beállításokkal.
- Az eszközdefiníciók 37 nyelvi változatban és angolul (összesen 38) érhetők el, a helyőrzők és a technikai azonosítók megőrzésével.

A teljes duplex hang az OpenAI Realtime, az Azure OpenAI, az xAI Grok Voice, a Gemini Live és a Bedrock Nova Sonic segítségével érhető el,
opcionális AEC3 visszhangkioltással és biztonsági korlátozású, valós idejű függvényhívással.

[Translations](README.translations.md) · [IoT](IOT_USECASE.md) · [Communication](COMMUNICATION.md)

## Dokumentáció

| Téma | Dokumentáció |
|---|---|
| Környezeti változók | [docs/ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/docs/ENVIRONMENT.md) |
| Architektúra és invariánsok | [docs/ARCHITECTURE.md](https://github.com/awaku7/agentcli/blob/main/docs/ARCHITECTURE.md) |
| Computer Use | [docs/COMPUTER_USE_IMPLEMENTATION.md](https://github.com/awaku7/agentcli/blob/main/docs/COMPUTER_USE_IMPLEMENTATION.md) |
| Repository-eszközök | [docs/REPOSITORY_TOOLS.md](https://github.com/awaku7/agentcli/blob/main/docs/REPOSITORY_TOOLS.md) |
| IoT-esetek | [docs/IOT_USECASE.md](https://github.com/awaku7/agentcli/blob/main/docs/IOT_USECASE.md) |
| Kommunikációs eszközök | [docs/COMMUNICATION.md](https://github.com/awaku7/agentcli/blob/main/docs/COMMUNICATION.md) |
| Automata pilóta | [docs/README_AUTO.md](https://github.com/awaku7/agentcli/blob/main/docs/README_AUTO.md) |
| MCP OAuth / Proxy | [docs/MCP_OAUTH_PROXY_GUIDE.md](https://github.com/awaku7/agentcli/blob/main/docs/MCP_OAUTH_PROXY_GUIDE.md) |
| VS Code-bővítmény | [docs/VSCODE.md](https://github.com/awaku7/agentcli/blob/main/docs/VSCODE.md) |
| Fejlesztői útmutató | [src/uagent/docs/DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md) |
| Eszközfolyamat | [src/uagent/docs/TOOL_FLOW.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/TOOL_FLOW.md) |

[Quickstart](QUICKSTART.md) · [Architecture](ARCHITECTURE.md) · [Context management](UAG_CONTEXT_MANAGEMENT_DESIGN.md)

## Fejlesztés és közreműködés

```bash
git clone https://github.com/awaku7/agentcli.git
cd agentcli
python -m pip install -e ".[core,providers,test]"
```

A PR előtti ellenőrzések futtatása:

```bash
python -m ruff check src tests
python -m black --check src tests
python -m pytest -q .
```

A teljes fejlesztési munkafolyamatért lásd a [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md) dokumentumot.

Örömmel fogadjuk a hibajelentéseket, funkcióötleteket, dokumentációs fejlesztéseket, fordításokat, eszközöket, skilleket és pull requesteket.
Nagyobb módosítások előtt kérjük, nyiss egy issue-t vagy indíts egy vitát. Olvasd el a [Developer Guide](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md) útmutatót,
és a pull request beküldése előtt futtasd a fenti ellenőrzéseket.

## Licenc

Az [Apache License 2.0](https://github.com/awaku7/agentcli/blob/main/LICENSE) licenc feltételei szerint érhető el.
