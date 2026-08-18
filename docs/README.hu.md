<p align="center">
 <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="720">
</p>

<h1 AI PH_4">Univerzális Átjáró</h1>

<p align="center">
 <b>U</b>univerzális <b>A</b>I <b>G</b>átjáró – Az Ön környezete, az Ön szabadsága.
</p>

<p align="center">
 Fájlműveletek / Web I_o-keresés / Képek vezérlése / / PDF-ek vezérlése és elemzése integráció<br>
 24 szolgáltató / 3 felhasználói felület / Párhuzamos eszközvégrehajtás / Ügynöki készségek piactér
</p>

<p align="center">
 <a href="https://github.com/awaku7/agentcli">GitHub</a>
 ·
 <a href="https://pypi.org/project/uag/">PyPI</a>
 ·
 <a href="https://github.com/awaku7/agentcli/blob/main/docs/____README.translations.md">Olvassa el az Ön nyelvén</a>
</p>
________________________________________## Miért uag?

**Szabadjon ki a szállítói bezárás alól.** A legtöbb AI-asszisztens egy adott szolgáltatóhoz vagy felhőszolgáltatáshoz köti Önt. A uag más.

- **Lokálisan fut** a gépén. Adatai Önnél maradnak (kivéve API hívást).
- **Szolgáltatói szabadság**: OpenAI, Claude, Gemini, DeepSeek, Ollama, Azure, Bedrock, Novita, HuggingFace... 24 szolgáltató, mindegyik elérhető egyetlen felületről. Váltson közöttük a környezeti változók újrakonfigurálásával – nincs újratelepítés, nincs migráció.
- **222-es eszközök**: Fájl I/O, webes keresés, képgenerálás, Gmail, BLE-eszközök szkennelése, MCP szerverintegráció – **130 statikusan párhuzamosan biztonságosnak van jelölve** (akár 8 futtatható párhuzamosan a szálkészleten keresztül, PARKER_WOR\`UAG konfigurálható). Amikor a LLM egyszerre több eszközhívást indít el, a uag automatikusan párhuzamosítja azokat.
- **3 felhasználói felület + A2A**: CLI, GUI, Web és Agent-to-Agent protokoll. Ugyanaz a motor, bármilyen interfész.
- **IoT-kész**: SwitchBot, ECHONET Lite, Matter, UPnP – vezérelje otthoni eszközeit mesterséges intelligencia segítségével.
- **Agent Skills**: Telepítse a közösség által épített készségeket a piacról. A uag végtelenségig kiterjeszthető.

uag **az Ön AI-asszisztense az Ön feltételei szerint**. Nincs szolgáltatóhoz, nem interfészhez, nem platformhoz kötve.

## Gyorsindítás

```bash
pip telepítés uag
uag
```

Az első indításkor a telepítővarázsló végigvezeti a szolgáltatói konfiguráción.
Lásd: [docs/ENVIRONMENT.md](https://github.com/awakublo7/agent)ENVIVIMENT/docli/docli változók.

## Computer Use

Computer Use opcionális, és támogatja a látható Playwright böngésző futtatási környezetet
és az asztali futási környezetet is. Ha engedélyezve van, mindkét futási idő létrejön és regisztrálásra kerül;

````bat
set UAGENT_COMPUTER_USE=1
egymásba zárva van normál kilépéskor, `Ctrl-C`, és a folyamat leállításakor. Állítsa be az 
`UAGENT_COMPUTER_HEADLESS=1` beállítást a böngésző alapú CI- vagy füsttesztekhez.
Az integrációs és biztonsági részletekért lásd: [docs/COMPUTER_USE_IMPLEMENTATION.md](docs/COMPUTER_USE_IMPLEMENTATION.md)
.

## Valós idejű hang és AEC3

A valós idejű hangmód támogatja a következőt: OpenAI Realtime, Azure OpenAI GPT Realtime, xAI Grok Voice API, Google Gemini Multimodal Live API és S microphone fullphone és S Micro-duplex beszél I/O. A szükséges "pywebrtc-audio" AEC3 háttérrendszer automatikusan telepítésre kerül, és a Bedrock opcionális, kétirányú streaming SDK-ja csak akkor kerül telepítésre automatikusan, ha a Bedrock szolgáltatót kiválasztja:

```bash
python scheck.py realtime
````

Az AEC3 csővezeték fogadja a ténylegesen hangolt mikrofont, és beszéli a ténylegesen hangzó mikrofont. (`messze`), hogy az asszisztens beszéd közben hallgathasson. Csak a hangproblémák kivizsgálásakor engedélyezze a diagnosztikát:

```bat
set UAGENT_REALTIME_AUDIO_DEBUG=1
python scheck.py realtime
```

### OpenAI Valós idejű funkcióhívás

OpenAI Funkcióhívás Valós idejű integráció támogatása. Az aktuális valós idejű adapter automatikusan felteszi a csak olvasható \`get_current_time' értéket. A roncsoló szerszámok és eszközvezérlők nem láthatók explicit engedélyezési lista és megerősítési folyamat nélkül. A Grok realtime külön adaptert használ, és nem használja ezt a OpenAI-specifikus függvényhívási útvonalat.

## Jellemzők

### 🧠 Többszolgáltatós architektúra

OpenAI / PFN (PLaMo) / Azure / Bedrock / OpenRouter / Ollama / llama.cpp / Gemini / Vertex AI / \_\_PHVID_4 / /ZAI /NAI /NAI /NAI / ZGrok / ZClaude (Zhipu AI) / HuggingFace / Alibaba Cloud (Qwen) / KIMI (Moonshot AI) / Xiaomi MiMo / LM Studio / MiniMax / Sakana AI (Fugu) / SAKURA AI Engine / Together AI / Vercel AI Gateway

Minden szolgáltató ugyanazokat az eszközöket és felületeket használja. Váltás az „UAGENT_PROVIDER” beállításával – nincs kódmódosítás, nincs külön telepítés.

#### Az Ollama és a llama.cpp

Az Ollama és a llama.cpp külön szolgáltatók. Az Ollama saját szolgáltatás- és modellkezelést használ, míg a `llama.cpp` egy `llama-server` OpenAI-kompatibilis végponthoz csatlakozik:

```bash
# Ollama
UAGENT_PROVIDER=ollama
UAGENT_OLLAMA_BASE_URL=http://localhost:11434/v1
UAGENT_OLLAMA_DEPNAME=llama3.1

# llama.cpp / llama-server
UAGENT_PROVIDER=llama_cpp
UAGENT_LLAMA_CPP_BASE_URL=http://localhost:8080/v1
UAGENT_LLAMA_CPP_DEPNAME=local-model
UAGENT_LLAMA_CPP_API_KEY=clla`pp szolgáltató. a Chat Completions-kompatibilis elérési utat használja. Tartsa meg az `UAGENT_RESPONSES=0' értéket, hacsak nincs beállítva kompatibilis proxy.

### ⚡ Párhuzamos eszköz-végrehajtás

Ha a LLM egyszerre több eszközt kér, a uag **automatikusan párhuzamosítja őket**, és az eszközök statikusan párhuzamosak lesznek. párhuzamos végrehajtás a "ThreadPoolExecutor"-on keresztül (alapértelmezés szerint 8 szál; állítsa be az "UAGENT_PARALLEL_WORKERS" beállítást a módosításhoz).

**Példa**: Kérdezze meg: "Ellenőrizze az időjárást északi nagyvárosokban" → LLM párhuzamosan aktiválja a `search_web-et → 5 keresési eredményt gyűjtött egy országban. batch.

Az aktuális számlálás a `TOOL_SPEC'-t definiáló szerszámmodulokon alapul (jelenleg 222, beleértve a 2 Rust-backed eszközt a `src/uagent/tools_rust/` fájlban). A `http_request` metódusérzékeny biztonságot használ: a `GET`/`HEAD`/`OPTIONS` hívások párhuzamosan futhatnak, míg az írási metódusok soros maradnak.

A csak olvasható eszközök (fájlkeresés, hash-számítás, könyvtárlista, fordítás, DB-lekérdezések stb.) agresszíven párhuzamba állítják a rendszert. (Claude Kódkompatibilis)

uagent egy **Claude kódkompatibilis beépülő modult** valósít meg. A beépülő modulok készségeket, ügynököket, MCP szervereket, hookokat és egyebeket önálló könyvtárakba csomagolnak `.claude-plugin/plugin.json` jegyzékkel.

**Támogatott összetevők**: készségek, segédügynökök, MCP szerverek, Slash-ek, 2 stílusok, életciklusok (1) userConfig, Dependencies, Channels, Marketplaces

**CLI parancsok**:

```

:plugin list # Telepített beépülő modulok listázása
:plugin install \<forrás> [--scope] # Telepítés (dir/zip/git/http)

> pluatelepítési piactérről
> plugin@plugin eltávolítás \<név> # Eltávolítás
> :plugin engedélyezése/letiltása \<név> # Toggle
> :plugin piactér hozzáadása/eltávolítása/lista # Piacterek kezelése
> :plugin init \<név> # Állvány új beépülő modul

````

Lásd: [DEVELOP_PLUGIN.md](src. a teljes dokumentációért.

### 🔄 Munkamenet folytonossága

- **Szolgáltatóváltás a munkamenet közben** a `UAGENT_PROVIDER` szolgáltatással – a beszélgetések előzményei megmaradnak.
- **Múlt munkamenetek újratöltése** a `:load <index>` paraméterrel – folytassa a gyorsítótárat, és elkerülje az újraindítást**, és elkerülje a gyorsítótárat, és elkerülje a végrehajtást. ugyanaz az eszközhívás ismétlődik.

### 🛠 229 Eszközök

| Kategória | Eszközök |
|---|---|
| **Fájlműveletek** | read/write/create/delete/search/grep/hash/zip, file_type, parse_eml (.eml fájlok), `path_alias` |
| **Web** | fetch_url, search_web, screenshot, browser_playwright, "url_alias", "public_transit_route" ([guide](docs/PUBLIC_TRANSIT_ROUTE.md)) |
| **Média** | gener_image, analysis_image, img2img, audio_speech, audio_transcribe |
| **Dokumentumok** | PDF/PPTX/DOCX/RTF/ODT kinyerés, Excel strukturált kivonat |
| **Előrejelzés** | Idősoros előrejelzés 9 modellel (AutoARIMA, Prophet, LightGBM, CatBoost, TimesFM stb.), automatikus modellválasztás, telekgenerálás, i18n |
| **Kommunikáció** | gmail_send, gmail_read, bluesky, discord_channel, teams_webhook, **pybitchat** (BLE Mesh) – lásd: [COMMUNICATION.md](https://github.com/awaku7/agentcli/blob/main/docs/COMMUNICATION.md) és [BITCHAT.md](https://github.com/awaku7/agentcli/blob/main/docs/BITCHAT.md) |
| **IoT** | SwitchBot (Cloud + BLE), ECHONET Lite, Matter, UPnP, fordított_geokód |
| **Felhő API-k** | "aws_api", "gcp_api", "azure_api" – általános AWS, Google Cloud és Azure API műveletek; írási műveletekhez kifejezett megerősítés szükséges |
| **Fejlesztői eszközök** | workspace_status, git_ops, git_review, security_scan, coverage_report, python_compile, lint_format, run_tests, db_query, **29 forráskód-navigátor (idx család)** |
| **MCP** | Csatlakozás külső MCP szerverekhez, eszközök listázása, végrehajtás — [OAuth / Proxy útmutató](docs/MCP_OAUTH_PROXY_GUIDE.md) |
| **A2A** | Ügynök-ügynök kommunikáció (más uag példányokkal vagy A2A-kompatibilis szerverekkel) |
| **Rendszer** | env vars, rendszerspecifikációk, idő, dátum számítás, [mennyiségek](docs/QUANTITIES.md), [geodéziai_távolság](docs/GEODESIC_DISTANCE.md), uuid_gen, slugify |
| **Navigációs forrás** | **29 idx-eszköz** Python, PHP, TypeScript, Java, C#, Dart, C/C++, Rust, Go, Swift, Kotlin, COBOL, VBA, LotusScript, Makefile-hez – függvény-/osztályindexet vagy meghatározott definíciót kaphat a teljes fájl elolvasása nélkül |

##⎎⎪ coverage`stastory: jelentse az aktív munkaterület Git-ágát, változásait, upstream szinkronizálási állapotát, Python futási idejét és általános projektjelölőit fájlok módosítása nélkül.
- `git_review`: összefoglalja a Git módosításait, kockázatos fájljait, tesztjelöltjeit és titkos megállapításait titkos értékek felfedése nélkül. 
- `security_scan`: valószínű konfigurációs fájlok és kockázati fájlok vizsgálata titkos tárolóhoz. `coverage_report`: futtassa és normalizálja a lefedettséget a következőhöz: Python, TypeScript/JavaScript, Rust, Go, Java/Kotlin, .NET, C/C++, Ruby, PHP, Swift és Dart/Flutter.
- A hiányzó lefedettségi függőségek automatikusan telepíthetők a végrehajtáskor; A `dry_run` soha nem telepít csomagokat.

Lásd a [Repository Analysis Tools](docs/REPOSITORY_TOOLS.md) részt a paraméterekkel, a kimenettel és a biztonsági részletekkel kapcsolatban.

Lásd az [Elérési út és URL-aliasok](docs/PATH_URL_ALIASES.md) részt az 
# fájl elérési útja# eszközben az ismétlődő URL argumentum és az URL## rövidítéséért. 🖥 4 interfész + VS kód kiterjesztés

| mód | Parancs | Cél |
|---|---|---|
| **CLI** | `uag` | Gyors terminál alapú működés |
| **GUI** | "uagg" | Asztali felhasználói felület a tkinterrel |
| **Web** | "uagw" | Böngésző alapú hozzáférés |
| **A2A Szerver** | "uaga" | Agent2Agent protokoll többügynökös kommunikációhoz |
| **VS kód** | — | [Bővítmény](https://github.com/awaku7/agentcli/blob/main/docs/VSCODE.md) Csevegőpanellel, Magyarázattal, Refaktorral, Hibajavítással és Eszközök fanézettel |

Lásd: [VSCODE.md](https://github.com/awaku7/agentc.main/agentc. VS Code kiterjesztés – telepítés, parancsok, billentyűkombinációk és konfiguráció.

### 🏠 IoT-eszközvezérlés

- **BACnet**: BACnet/IP-eszközök olvasása/írása (HVAC, világítás, teljesítménymérők). COV-előfizetés push értesítésekhez
- **Modbus TCP**: tartási/bemeneti regiszterek és tekercsek olvasása/írása. Lekérdezésalapú változásfigyelés
- **OPC UA**: Böngésszen a címtartományban, olvasási/írási változókat, feliratkozás az adatváltozásokra
- **SwitchBot**: Kötegelt felhővezérlés és BLE-ellenőrzés/vezérlés. Lekérdezésalapú előfizetés
- **ECHONET Lite**: Fedezze fel, vezérelje és iratkozzon fel a háztartási készülékek INF-értesítéseire (AC, lámpák, vízmelegítők stb.)
- **Lényeg**: Olvasási/írási vezérlés + attribútum-előfizetés az állapotváltozás figyeléséhez
- **UPnP**: Eszközfelderítés és IGD port továbbítása
 [IOT_USECASE.md](https://github.com/awaku7/agentcli/blob/main/docs/IOT_USECASE.md)

### 🎯 Agent Skills Marketplace

`:skills mp_search` a [SkillsMP](https://skills.com) és [ClawHub](https://clawhub.ai) a közösségi készségekhez.
A uag képességeit menet közben telepítheti és bővítheti.

### 🤖 Auto-Pilot (`:auto`)

uag **autonóm módon képes elérni egy célt több körön keresztül__PH_**. Tökéletes összetett, többlépcsős feladatokhoz, amelyek ismétlődő finomítást igényelnek.

- **Hogyan működik**: Minden körben van egy fő lekérdezés (A lépés), amelyet egy felülvizsgálói ítélet követ (B. lépés), amely eldönti, hogy „BEFEJEZET vagy FOLYTATJA?”
- **Ugyanaz a szolgáltató, ugyanaz a API kódhasználati út – a fő értékelési útvonalat is beleértve** A válaszok API támogatása.
- **Külön bíró LLM** (opcionális): Állítsa be az `UAGENT_AP_PROVIDER' beállítást, hogy más szolgáltatót/modellt használjon a véleményező számára (pl. használjon olcsóbb modellt a bírálathoz).
- **Bármikor kilép**: Nyomja meg az `x.-gombot az azonnali válasz leállításához. Vagy hagyja, hogy az értékelő döntse el, mikor teljesül a cél. 
- **Konfigurálható**: `--max-rounds N` a költségvetés szabályozásához.

A teljes dokumentációért lásd: [README_AUTO.md](https://github.com/awaku7/agentcli/blob/main/docs/README_AUTO.md)🧎#ch. A Manager

uag nyomon követheti a folyamatot a hosszan tartó, több fájlt tartalmazó feladatok során. Amikor a LLM több tucat fájlt dolgoz fel, a "batch_state" a függőben lévő, befejezett és sikertelen fájlok listáját a lemezen tárolja. Ha a munkamenet véget ér vagy egy kör időtúllépése következik be, a következő futás onnan folytatódik, ahol abbamaradt – semmi sem vész el.

### 🛡 Human-in-the-Loop

`human_ask` lehetővé teszi, hogy a LLM szüneteljen, és megerősítést kérjen, mielőtt romboló műveleteket hajt végre (fájltörlés, felülírási parancs). Marad az irányítás.

### 🛑 Megszakítás (c-billentyű / Stop gomb)

Bármikor leállíthatja a LLM válaszgenerálást, és visszaadhatja a stop parancsot a LLM-ba.

| Interfész | Hogyan kell megszakítani |
|---|---|
| **CLI** | Nyomja meg a F12 billentyűt a LLM adatfolyam közben – az aktuális válasz leáll, és a "Stop"-t felhasználói üzenetként küldi el, így a LLM ennek megfelelően válaszol |
| **WEBES UI** | Kattintson a piros **■ Stop** gombra (automatikusan megjelenik a LLM feldolgozás során) |
| **Asztali GUI** | Kattintson a piros **■** gombra (automatikusan megjelenik a LLM feldolgozása közben) |

A megszakítás "prompt injekcióként" működik: a megszakítás helyett a "Stop"-t visszaadja a LLM-nak felhasználói üzenetként, lehetővé téve a megszakítás automatikus befejezését vagy nyugtázását. [README_AUTO.md](https://github.com/awaku7/agentcli/blob/main/docs/README_AUTO.md)).

### 🕵️ Böngészőautomatizálás és Web Inspector

**Játssz két egymást kiegészítő Playwright-alapú eszköz valódi böngészőmunkamenetek – navigálhat, kattinthat, kitöltheti az űrlapokat, kivonhatja az adatokat, kezelheti a többoldalas folyamatokat. Fej nélkül vagy fejjel működik.
- **playwright_inspector**: Rögzítse a böngésző átmeneteit, és minden lépésnél DOM-pillanatfelvételeket és képernyőképeket készít. Hasznos a webes interakciók hibakereséséhez vagy az oldalváltozások időbeli megfigyeléséhez.

### 🔄 A dinamikus eszközbetöltés

`tool_catalog` és a `tool_load` lehetővé teszi az eszközök felfedezését és engedélyezését futás közben.
Nem kell mindent betölteni indításkor – csak azt aktiválja, amire szüksége van, amikor szüksége van rá. Az eszközök

`uuid_gen` és `slugify` a Rustban vannak implementálva (PyO3-on keresztül) a teljesítmény érdekében.
Közvetlenül egy előre beépített `.pyd`-ből töltődnek be – **nincs szükség pip installálásra**.

Külső fejlesztők is szállíthatnak Rust-alapú eszközöket: ⎎ per next wrap, `.py`` wrap. `load_rust_pyd()` a `uagent.tools.rust_helper` fájlból, és
a felhasználók minden további függőség nélkül hozzáférnek az eszközhöz. Lásd:
[TOOL_CREATOR_GUIDE.md](https://github.com/awaku7/agentcli/blob/main/TOOL_CREATOR_GUIDE.md).

###繁體中文 / 한국어 / Español / Français / Русский / és még sok más.
A váltáshoz állítsa be az `UAGENT_LANG` lehetőséget. Új nyelvi beállítás hozzáadásához lásd: [ADD_LOCALE.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/ADD_LOCALE.md).

A README fordítása a következő nyelven érhető el [docs/README.translations.md](https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md).

### 🔒 Titkosított környezeti változók

Tároljon API titkosított kulcsokat és titkosított kulcsokat. `.env` fájl.
Kezelés az `uag_envsec` segítségével.

## Konfiguráció és részletek

- **Környezeti változók**: [docs/ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/docs/ENVIRONMENT.md)
- **Telepítő varázsló**: `python -m 
cryptup** __PH-cli env**: `uag_envsec` — `.env` titkosítása `.env.sec`
- **Válaszok API**: Állítsa be az `UAGENT_RESPONSES=1` értéket a válaszok API módhoz (OpenAI/__PH/OLMAAlbauter Stúdió/Sakana AI). Automatikusan engedélyezve a Sakana AI-hez (Fugu).
- **Fejlesztői dokumentumok**: [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)
- **Eszközfolyamat**: [TOOL_FLOW.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/TOOL_FLOW.md) – az eszközök elküldése az LLM-eknek (műfaji maszk, tool_catalog, GPT-5.4+ natív tool_search)
s__**:PH_5 tipp [SLM_TIPS.md](https://github.com/awaku7/agentcli/blob/main/docs/SLM_TIPS.md)

## A Project Philosophy

uag arra törekszik, hogy **az Ön mesterséges intelligenciája legyen a gépén, az Ön feltételei szerint.**

- Nincs SaaS-függőség – helyileg fut
- Nincs szolgáltatói bekötés – bármikor válthat
- Nincs felhasználói felület zárolása – CLI / _A2A / _A2A lock-in – bővítse ki eszközökkel és készségekkel

Ingyenes mesterségesintelligencia-ügynöki élmény, gyártói bekötéstől mentes.

### ✨ Saját eszközök létrehozása

A uag új eszközének írása egyszerű – hozzon létre egyetlen `.py` fájlt a 
`TOOL, place it in és(``run_SPEC`) funkcióval. `UAGENT_EXTERNAL_TOOLS_DIR`, és
azonnal elérhető. A Rust fejlesztői számára szállítson egy előre beépített `.pyd`-et, amely
nulla extra függőséget biztosít a felhasználók számára.

A lépésről lépésre lásd: [TOOL_CREATOR_GUIDE.md](https://github.com/awaku7/agentcli/blob/main/TOOL_CREATOR_GUIDE.md)

.## Hozzájárulás

A hozzájárulásokat szívesen fogadjuk! Hibajelentések, funkciójavaslatok, dokumentációjavítások, fordítások és lekérési kérések – mindezt nagyra értékeljük.

- **Problémák**: Nyisson meg egy GitHub-problémát a hibákért vagy a funkciókra vonatkozó kérésekért.
- **Lekérések**: Forgassa le a repót, hajtsa végre a módosításokat, és küldjön be PR-t. Tekintse meg a [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md) webhelyet a fejlesztési beállításokért és útmutatókért.
- **Fordítások**: A README fordításokat és nyelvi kiegészítéseket szívesen fogadjuk. Lásd: [ADD_LOCALE.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/ADD_LOCALE.md).
- **Eszközök és készségek**: Új eszközbővítmények és ügynöki készségek adhatók hozzá a piactéren keresztül (##for#e
e. PR)

Először telepítse a csak tesztfüggőségeket. A futásidejű
függőségi listán kívül maradnak:

```bash
python -m pip install -e ".[teszt]"
python -m pip install black ruff
````

Futtassa le ugyanazokat az ellenőrzéseket, amelyeket a GitHub. Műveletek a check lenyomása előtt:⎎ffm\`
bash - tests
python -m black --check src tests
python scripts/tool_json_i18n_batch.py status
python -m pytest -q .

````

A gyorsabb helyi iteráció érdekében csak az érintett teszteket futtassa:


```ba -q tesztek/<affected_area>
````

További ellenőrzések, ha szükséges:

```bash
python -m py_compile src/uagent/
mypy src/uagent
```

szerkesztés:Poter`thon)e scripts/compile_locales.py` és `python scripts/po_qc_summary.py`.

Runtime házirend (részletek itt: \[DEVELOP.md\](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP. 1 helyett): helpers 6. §. `sys.exit`; az eszközgazda a "SystemExit"/"Exception" eszközt hibakarakterláncokká alakítja, így egyetlen eszköz nem tudja megállítani a folyamatot. A hibamentes indítási kilépések szándékosak maradnak.

## Architektúra és működési invariánsok

Lásd a [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) webhelyet a A2A életciklusra, I18N kontextusokra, opcionális függőségi telepítésre, eszközbiztonságra, szolgáltatói képességekre, OAuth-elfogadási alapú hitelesítési korlátokra és⎏-eseményekre vonatkozó tartós szerződésekre vonatkozóan.## Enterprise Policy Engine

Támogatja az eszközökre, szolgáltatókra, hitelesítő adatokra, MCP szerverekre, hálózatokra, készségekre és bővítményekre vonatkozó szervezeti szintű házirendeket. Állítsa be az `UAGENT_POLICY_FILE`-t JSON/YAML házirendfájlra; lásd: [docs/ENTERPRISE_POLICY.md](docs/ENTERPRISE_POLICY.md) konfigurációs példákért, szerepkörökért, megerősítésért és engedélyezési listákért.

### Runtime helyreállítás és hangszerelés

Lásd: [RESTART_RECOVERY.md](docs/REY.mRE_d)COVERY.mRE [DAG_SCHEDULER.md](docs/DAG_SCHEDULER.md) / [MULTI_AGENT_RUNTIME.md](docs/MULTI_AGENT_RUNTIME.md) a tartós helyreállításhoz, a függőség-tudatos végrehajtáshoz, a többügynökös hangszereléshez és a távoli A2A használathoz. [DISTRIBUTED_COORDINATION.md](docs/DISTRIBUTED_COORDINATION.md) a megosztott futásidejű vezetői bérlet koordinációjához.
