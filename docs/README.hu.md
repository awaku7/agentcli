<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="720">
</p>

<h1 align="center">uag – Universal AI Gateway</h1>

<p align="center">
  <b>U</b>niversal <b>A</b>I <b>G</b>ateway — A környezeted, a te szabadságod.
</p>

<p align="center">
  Fájlműveletek / Webes keresés / Képgenerálás és -elemzés / PDF és Excel kivonás / IoT vezérlés / MCP integráció<br>
  24 providers / 3 felhasználói felület / párhuzamos szerszámvégrehajtás / Agent Skills piactér
</p>

<p align="center">
  <a href="https://github.com/awaku7/agentcli">GitHub</a>
  ·
  <a href="https://pypi.org/project/uag/">PyPI</a>
  ·
  <a href="README.translations.md">Read this in your language</a>
</p>

______________________________________________________________________

## Miért uag?

**Szabadjon ki a szállítói bezárás alól.** A legtöbb AI-asszisztens egy adott szolgáltatóhoz vagy felhőszolgáltatáshoz köti Önt. uag más.

- **Lokálisan fut** a gépén. Adatai Önnél maradnak (kivéve az Ön által kezdeményezett API-hívásokat).
- **Szolgáltatói szabadság**: OpenAI, Claude, Gemini, DeepSeek, Ollama, Azure, Bedrock, HuggingFace... 21+ szolgáltató, mindegyik egyetlen felületről elérhető. Váltson közöttük a környezeti változók újrakonfigurálásával – nincs újratelepítés, nincs migráció.
- **203 eszköz**: Fájl I/O, webes keresés, képgenerálás, Gmail, BLE-eszközök szkennelése, MCP-szerver integráció – **111 párhuzamosan biztonságos** (akár 8 végrehajtása párhuzamosan a szálkészleten keresztül, az `UAGENT_PARALLEL_WORKERS`-en keresztül konfigurálható). Amikor az LLM egyszerre több eszközhívást indít el, az uag automatikusan párhuzamosítja azokat.
- **3 felhasználói felület + A2A**: CLI, GUI, web és Agent-to-Agent protokoll. Ugyanaz a motor, bármilyen interfész.
- **Agent Skills**: Telepítse a közösség által épített készségeket a piactérről. Hosszabbítsa meg az uag-ot végtelenül.

uag **az Ön AI-asszisztense az Ön feltételei szerint**. Nincs szolgáltatóhoz, nem interfészhez, nem platformhoz kötve.

## Gyorsindítás

```bash
pip install uag
uag
```

Az első indításkor a telepítővarázsló végigvezeti a szolgáltató konfigurációján.
Az összes környezeti változóhoz lásd az [docs/ENVIRONMENT.md](ENVIRONMENT.md) webhelyet.

## Jellemzők

### 🧠 Többszolgáltatós architektúra

OpenAI / PFN (PLaMo) / Azure / Bedrock / OpenRouter / Ollama / Gemini / Vertex AI / Claude / Grok / NVIDIA / Novita / DeepSeek / Z.AI (Zhipu AI) / HuggingFace / Alibaba Cloud (Qwen) / KIMI (Moonshot AI) / Xiaomi MiMo / LM Studio / MiniMax / Sakana AI (Fugu) / SAKURA AI Engine / Together AI / Vercel AI Gateway

Minden szolgáltató ugyanazt az eszközkészletet és felületet használja. Váltás az "UAGENT_PROVIDER" beállításával – nincs kódmódosítás, nincs külön telepítés.

### ⚡ Párhuzamos szerszámvégrehajtás

Amikor az LLM egyszerre több eszközt kér, az uag **automatikusan párhuzamosítja** azokat.
111 eszköz `x_parallel_safe` megjelöléssel rendelkezik, és egyidejűleg fut a `ThreadPoolExecutor'-on keresztül (alapértelmezés szerint 8 szál; állítsa be az `UAGENT_PARALLEL_WORKERS\` paramétert a módosításhoz).

**Példa**: Kérdezze meg: "Ellenőrizze az időjárást északi fővárosokban" → Az LLM a `search_web` × 5 országot indítja el → mind az 5 keresés párhuzamosan fut → az eredmények egy kötegben gyűjtve.

A csak olvasható eszközök (fájlkeresés, hash számítás, könyvtárlista, fordítás, DB lekérdezések stb.) agresszíven párhuzamosak.

### 🧩 Beépülő modulrendszer (Claude Code kompatibilis)

A uagent egy Claude Code-kompatibilis bővítményrendszert valósít meg. A beépülő modulok a készségeket, az ügynököket, az MCP-szervereket, a hookokat és egyebeket önálló könyvtárakba csomagolják `.claude-plugin/plugin.json` jegyzékkel.

**Támogatott összetevők: készségek, segédügynökök, MCP-szerverek, hookok (12 életciklus-esemény), perjelparancsok, kimeneti stílusok, userConfig, függőségek, csatornák, piacterek**

**CLI commands**:

```
:plugin list                         # A telepített bővítmények listája
:plugin install <source> [--scope]
:plugin install <name>@<marketplace>  # Telepítés a piactérről
:plugin remove <name>                # Eltávolítás
:plugin enable/disable <name>        # Be- vagy kikapcsolás
:plugin marketplace add/remove/list  # Piacterek kezelése
:plugin init <name>                  # Új bővítmény vázának létrehozása
```

A részletekért lásd a teljes dokumentációt. [DEVELOP_PLUGIN.md](../src/uagent/docs/DEVELOP_PLUGIN.md)

### 🔄 Munkamenet folytonossága

- **Szolgáltatóváltás a munkamenet közben** a `UAGENT_PROVIDER` használatával — a beszélgetési előzmények megmaradnak.
- **Korábbi munkamenetek újratöltése** a `:load <index>` paranccsal — folytassa onnan, ahol abbahagyta.

### 🛠 203 Eszközök

| Kategória | Eszközök |
|---|---|
| **Fájlműveletek** | read/write/create/delete/search/grep/hash/zip, file_type, parse_eml (.eml fájlok) |
| **Web** | fetch_url, search_web, screenshot, browser_playwright |
| **Média** | gener_image, analysis_image, img2img, audio_speech, audio_transcribe |
| **Dokumentumok** | PDF/PPTX/DOCX/RTF/ODT kinyerés, Excel strukturált kivonat |
| **Előrejelzés** | Idősor-előrejelzés 9 modellel (AutoARIMA, Prophet, LightGBM, CatBoost, TimesFM stb.), automatikus modellválasztás, diagramgenerálás, i18n |
| **Kommunikáció** | gmail_send, gmail_read, bluesky, discord_channel, teams_webhook, **pybitchat** (BLE Mesh) – lásd [COMMUNICATION.md](COMMUNICATION.md) és [BITCHAT.md](BITCHAT.md)|
| **IoT** | BACnet、Modbus TCP、OPC UA、SwitchBot（Cloud + BLE）、ECHONET Lite、Matter、UPnP、reverse_geocode |
| **Felhő API-k** | `aws_api`, `gcp_api`, `azure_api` — AWS, Google Cloud, and Azure API operations; write operations require explicit confirmation |
| **Fejlesztői eszközök** | git_ops, python_compile, lint_format, run_tests, db_query, **29 forráskód-navigátor (idx család)** |
| **MCP** | Csatlakozás külső MCP-kiszolgálókhoz, eszközök listázása, |
| **A2A** | Ügynök-ügynök kommunikáció (más uag-példányokkal vagy A2A-kompatibilis szerverekkel) |
| **Rendszer** | env vars, rendszerspecifikációk, idő, dátum számítás, uuid_gen, slugify ||
| **Navigációs forrás** | **29 idx-eszköz** Python, PHP, TypeScript, Java, C#, Dart, C/C++, Rust, Go, Swift, Kotlin, COBOL, VBA, LotusScript, Makefile számára – függvény/osztályindex vagy konkrét definíció beszerzése a teljes fájl beolvasása nélkül |

### 🖥 4 interfész + VS kód kiterjesztés

| mód | Parancs | Cél |
|---|---|---|
| **CLI** | "uag" | Gyors terminál alapú működés |
| **GUI** | "uagg" | Asztali felhasználói felület a tkinterrel |
| **Web** | "uagw" | Böngésző alapú hozzáférés |
| **A2A szerver** | "uaga" | Agent2Agent protokoll többügynökös kommunikációhoz |
| **VS kód** | — | [Bővítmény](VSCODE.md) Csevegőpanellel, Magyarázattal, Refaktorral, Hibajavítással és Eszközök fanézettel |

Tekintse meg a [VSCODE.md](VSCODE.md) webhelyet a VS Code bővítmény részleteiért – telepítés, parancsok, billentyűkombinációk és konfiguráció.

### 🏠 IoT-eszközvezérlés

Lásd: [IOT_USECASE.md](IOT_USECASE.md)

### 🎯 Agent Skills Marketplace

A \`:skills mp_search' segítségével böngészhet a [SkillsMP](https://skillsmp.com) és a [ClawHub](https://clawhub.ai) webhelyen közösségi készségekért.
Telepítse és bővítse az uag képességeit menet közben.

### 🤖 Auto-Pilot (`:auto`)

Az uag **autonóm módon követheti a célt több LLM-körön keresztül**. Tökéletes összetett, többlépéses feladatokhoz, amelyek ismétlődő finomítást igényelnek.

- **Hogyan működik**: Minden körben van egy fő lekérdezés (A lépés), amelyet egy felülvizsgálói ítélet követ (B. lépés), amely eldönti, hogy "BEFEJEZTE vagy FOLYTATJA?"
- **Ugyanaz a szolgáltató, ugyanaz az API**: A felülvizsgálói döntés ugyanazt a kódútvonalat használja fő lekérdezésként – beleértve a Responses API támogatást is.
- **Különbíró LLM** (opcionális): Állítsa be az \`UAGENT_AP_PROVIDER' paramétert, ha más szolgáltatót/modellt szeretne használni a véleményező számára (például használjon olcsóbb modellt az elbíráláshoz).
- **Bármikor kilépés**: Nyomja meg az `x` billentyűt az azonnali leállításhoz, akár válasz közben is. Vagy hagyja, hogy az értékelő döntse el, mikor teljesül a cél.
- **Konfigurálható**: `--max-kör N` a költségvetés szabályozásához.

A teljes dokumentációért lásd: [README_AUTO.md](README_AUTO.md).

### 🧩 Batch State Manager

Az uag nyomon követheti az előrehaladást a hosszan futó többfájlos feladatok között. Amikor az LLM több tucat fájlt dolgoz fel, a "batch_state" a függőben lévő, befejezett és sikertelen fájlok listáját a lemezen tárolja. Ha a munkamenet véget ér, vagy egy kör időtúllépéssel jár, a következő futás onnan folytatódik, ahol abbamaradt – semmi sem vész el.

### 🛡 Ember a folyamatban

A `human_ask` lehetővé teszi, hogy az LLM megálljon, és megerősítést kérjen, mielőtt romboló műveleteket hajt végre (fájltörlés, felülírás, shell-parancsok). Marad az irányítás.

### 🛑 Megszakítás (c-billentyű / Stop gomb)

Bármikor leállíthatja az LLM-válasz generálását, és visszaadhatja a stop parancsot az LLM-nek.

| Interfész | Hogyan szakítsuk meg |
|---|---|
| **CLI** | Nyomja meg a `c` billentyűt LLM adatfolyam közben – az aktuális válasz leáll, és a "Stop"-t felhasználói üzenetként küldi el, így az LLM ennek megfelelően válaszol |
| **WEBES UI** | Kattintson a piros **■ Stop** gombra (automatikusan megjelenik az LLM feldolgozás során) |
| **Asztali GUI** | Kattintson a piros **■** gombra (automatikusan megjelenik az LLM feldolgozás során) |

A megszakítás "prompt injekcióként" működik: ahelyett, hogy egyszerűen megszakítaná, a "Stop"-t visszaadja az LLM-nek felhasználói üzenetként, lehetővé téve a megszakítás kecses befejezését vagy nyugtázását.

Nyomja meg az „x” billentyűt az automatikus pilóta módból való kilépéshez (lásd: [README_AUTO.md](README_AUTO.md)).

### 🕵️ Böngészőautomatizálás és webellenőr

Két kiegészítő, drámaíró-alapú eszköz:

- **browser_playwright**: Automatizálja a valódi böngészőmunkameneteket – navigálhat, kattinthat, kitöltheti az űrlapokat, kivonhatja az adatokat, kezelheti a többoldalas folyamatokat. Fej nélkül vagy fejjel működik.
- **playwright_inspector**: Böngésző átmenetek rögzítése, DOM-pillanatképek és képernyőképek rögzítése minden lépésnél. Hasznos a webes interakciók hibakereséséhez vagy az oldalváltozások idővel történő ellenőrzéséhez.

### 🔄 Dinamikus eszköz betöltése

A "tool_catalog" és a "tool_load" segítségével futás közben fedezheti fel és engedélyezheti az eszközöket.
Nem kell mindent betölteni indításkor – csak azt aktiválja, amire szüksége van, amikor szüksége van rá.

### 🦀 Rust Native Tools

A `uuid_gen` és a `slugify` a teljesítmény érdekében Rustban (PyO3-on keresztül) van megvalósítva.

### 🌐 i18n / L10n

日本語 / angol / 简体中文 / 繁體中文 / 한국어 / Español / Français / Русский / és még sok más.
Állítsa be az „UAGENT_LANG” nyelvet a váltáshoz. Az [ADD_LOCALE.md](../src/uagent/docs/DEVELOP_I18N.md) oldalon új területi beállítást adhat hozzá.

A README fordításai a [docs/README.translations.md] webhelyen érhetők el (README.translations.md).

### 🔒 Titkosított környezeti változók

Tárolja az API-kulcsokat és titkokat az .env.sec-ben – egy titkosított .env-fájlban.
Kezelje az "uag_envsec" segítségével.

## Konfiguráció és részletek

- **Környezeti változók**: [docs/ENVIRONMENT.md](ENVIRONMENT.md)
- **Telepítő varázsló**: `python -m uagent.setup_cli`
- **Titkosított env**: `uag_envsec` — `.env` titkosítása `.env.sec`-ként
- **Responses API**: Állítsa be az "UAGENT_RESPONSES=1" értéket a Responses API módhoz (OpenAI/Azure/Bedrock/OpenRouter/Ollama/Alibaba/LM Studio/Sakana AI). Automatikusan engedélyezve a Sakana AI (Fugu) számára.
- **Fejlesztői dokumentumok**: [DEVELOP.md](../src/uagent/docs/DEVELOP.md)
- **Tool flow**: [TOOL_FLOW.md](../src/uagent/docs/TOOL_FLOW.md)
- **Kis LLM-tippek**: [SLM_TIPS.md](SLM_TIPS.md)

## Projektfilozófia

uag arra törekszik, hogy az Ön MI-je legyen a gépén, az Ön feltételei szerint.\*\*

- Nincs SaaS-függőség – helyileg fut
- Nincs szolgáltatói bezárás - bármikor válthat
- Nincs felhasználói felület zárolása – CLI / GUI / Web / A2A
- Nincs funkciórögzítés – bővítse ki eszközökkel és készségekkel

Ingyenes mesterséges intelligencia ügynöki élmény, mentes a szállítói bekötéstől.

### ✨ Készítse el saját eszközeit

[hu.md](TOOL_CREATOR_GUIDE.hu.md)
A lépésről lépésre bemutatott útmutatóért kattintson ide.

## Közreműködés

Hozzájárulásokat szívesen fogadunk! Hibajelentések, funkciójavaslatok, dokumentációjavítások, fordítások és lekérések – mindezt nagyra értékeljük.

- **Issues**: Nyisson meg egy GitHub-problémát a hibákért vagy a funkciókra vonatkozó kérésekért.
- **Pull kérések**: Forkolja a tárolót, végezze el a módosításokat, majd küldjön PR-t. A fejlesztési beállításokról és irányelvekről a [DEVELOP.md](../src/uagent/docs/DEVELOP.md) fájlban olvashat.

Realtime Hang és AEC3

## A Realtime hangmód támogatja a full-duplex mikrofont és a hangszóró be-/kimenetet. Ha a AEC3 háttérprogram hiányzik, a uag automatikusan telepíti a pywebrtc-audio-at.

**Valós idejű szolgáltatók**: OpenAI Realtime, Azure OpenAI GPT Realtime, Google Gemini Live, xAI Grok Voice és Amazon Bedrock Nova Sonic. A Bedrock kétirányú adatfolyam SDK automatikusan csak a Bedrock kiválasztásakor kerül telepítésre.

```bat
python scheck.py realtime
```

A AEC3 a tényleges mikrofonjelet (közel) és a hangszórónak ténylegesen küldött hangot (távoli) használja. Csak a hangproblémák kivizsgálásakor engedélyezze a diagnosztikát.

```bat
set UAGENT_REALTIME_AUDIO_DEBUG=1
python scheck.py realtime
```

### OpenAI Realtime Function Calling

OpenAI A Realtime támogatja a biztonságilag korlátozott Function Calling integrációt. Az aktuális adapter automatikusan megjeleníti a csak olvasható get_current_time funkciót. A roncsoló eszközök és eszközvezérlők kifejezett engedélyezési listát és megerősítési folyamatot igényelnek. A Grok realtime külön adaptert használ, és nem ezt a OpenAI-specifikus Function Calling elérési utat.
