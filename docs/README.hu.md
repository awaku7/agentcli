<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="720">
</p>

<h1 align="center">uag – Universal AI Gateway</h1>

<p align="center">
  <b>U</b>niversal <b>A</b>I <b>G</b>ateway — Your environment, your freedom.
</p>

<p align="center">
  File ops / Web search / Image generation &amp; analysis / PDF &amp; Excel extraction / IoT control / MCP integration<br>
  15+ providers / 3 UIs / Parallel tool execution / Agent Skills marketplace
</p>

<p align="center">
  <a href="https://github.com/awaku7/agentcli">GitHub</a>
  ·
  <a href="https://pypi.org/project/uag/">PyPI</a>
  ·
  <a href="https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md">Read this in your language</a>
</p>

---

## Miért uag?

**Szabadjon ki a szállítói bezárás alól.** A legtöbb AI-asszisztens egy adott szolgáltatóhoz vagy felhőszolgáltatáshoz köti Önt. uag más.

- **Lokálisan fut** a gépén. Adatai Önnél maradnak (kivéve az Ön által kezdeményezett API-hívásokat).
- **Szolgáltatói szabadság**: OpenAI, Claude, Gemini, DeepSeek, Ollama, Azure, Bedrock, HuggingFace... 15+ szolgáltató, mindegyik egyetlen felületről elérhető. Váltson közöttük a környezeti változók újrakonfigurálásával – nincs újratelepítés, nincs migráció.
- **131 eszköz**: Fájl I/O, webes keresés, képgenerálás, Gmail, BLE-eszközök szkennelése, MCP-szerver integráció – **76 párhuzamosan biztonságos** (akár 8 végrehajtása párhuzamosan a szálkészleten keresztül, az `UAGENT_PARALLEL_WORKERS`-en keresztül konfigurálható). Amikor az LLM egyszerre több eszközhívást indít el, az uag automatikusan párhuzamosítja azokat.
- **3 felhasználói felület + A2A**: CLI, GUI, web és Agent-to-Agent protokoll. Ugyanaz a motor, bármilyen interfész.
- **IoT-kész**: SwitchBot, ECHONET Lite, Matter, UPnP – vezérelje otthoni eszközeit mesterséges intelligencia segítségével.
- **Agent Skills**: Telepítse a közösség által épített készségeket a piactérről. Hosszabbítsa meg az uag-ot végtelenül.

uag **az Ön AI-asszisztense az Ön feltételei szerint**. Nincs szolgáltatóhoz, nem interfészhez, nem platformhoz kötve.

## Gyorsindítás

```bash
pip install uag
uag
```

Az első indításkor a telepítővarázsló végigvezeti a szolgáltató konfigurációján.
Az összes környezeti változóhoz lásd az [ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md) webhelyet.

## Jellemzők

### 🧠 Többszolgáltatós architektúra

OpenAI / Azure / Bedrock / OpenRouter / Ollama / Gemini / Vertex AI / Claude / Grok / NVIDIA / DeepSeek / Z.AI (Zhipu AI) / HuggingFace / Alibaba Cloud (Qwen) / KIMI (Moonshot AI) / Xiaomi MiMo / / LM Studio / SauguMax**

Minden szolgáltató ugyanazt az eszközkészletet és felületet használja. Váltás az "UAGENT_PROVIDER" beállításával – nincs kódmódosítás, nincs külön telepítés.

### ⚡ Párhuzamos szerszámvégrehajtás

Amikor az LLM egyszerre több eszközt kér, az uag **automatikusan párhuzamosítja** azokat.
76 eszköz `x_parallel_safe` megjelöléssel rendelkezik, és egyidejűleg fut a `ThreadPoolExecutor'-on keresztül (alapértelmezés szerint 8 szál; állítsa be az `UAGENT_PARALLEL_WORKERS` paramétert a módosításhoz).

**Példa**: Kérdezze meg: "Ellenőrizze az időjárást északi fővárosokban" → Az LLM a `search_web` × 5 országot indítja el → mind az 5 keresés párhuzamosan fut → az eredmények egy kötegben gyűjtve.

A csak olvasható eszközök (fájlkeresés, hash számítás, könyvtárlista, fordítás, DB lekérdezések stb.) agresszíven párhuzamosak.

### 🔄 Munkamenet folytonossága

- **Switch providers mid-session** with `UAGENT_PROVIDER` — conversation history is preserved.
- **Reload past sessions** with `:load <index>` — pick up where you left off.
- **Tool result caching** avoids redundant re-execution when the same tool call repeats.

### 🛠 131 Eszközök

| Kategória | Eszközök |
|---|---|
| **Fájlműveletek** | read/write/create/delete/search/grep/hash/zip, parse_eml (.eml fájlok) |
| **Web** | fetch_url, search_web, screenshot, browser_playwright |
| **Média** | gener_image, analysis_image, img2img, audio_speech, audio_transcribe |
| **Dokumentumok** | PDF/PPTX/DOCX/RTF/ODT kinyerés, Excel strukturált kivonat |
| **Kommunikáció** | gmail_send, gmail_read, bluesky, discord_channel, teams_webhook – lásd: [COMMUNICATION.md](https://github.com/awaku7/agentcli/blob/main/docs/COMMUNICATION.md) |
| **IoT** | SwitchBot (Cloud + BLE), ECHONET Lite, Matter, UPnP |
| **Fejlesztői eszközök** | git_ops, python_compile, lint_format, run_tests, db_query, **13 forráskód-navigátor (idx család)** |
| **MCP** | Csatlakozás külső MCP-kiszolgálókhoz, eszközök listázása, |
| **A2A** | Ügynök-ügynök kommunikáció (más uag-példányokkal vagy A2A-kompatibilis szerverekkel) |
| **Rendszer** | env vars, rendszerspecifikációk, idő, dátum számítás |
| **Navigációs forrás** | **13 idx-eszköz** Python, PHP, TypeScript, Java, C#, Dart, C/C++, Rust, Go, Swift, Kotlin, COBOL számára – függvény/osztályindex vagy konkrét definíció beszerzése a teljes fájl beolvasása nélkül |

### 🖥 4 interfész + VS kód kiterjesztés

| mód | Parancs | Cél |
|---|---|---|
| **CLI** | "uag" | Gyors terminál alapú működés |
| **GUI** | "uagg" | Asztali felhasználói felület a tkinterrel |
| **Web** | "uagw" | Böngésző alapú hozzáférés |
| **A2A szerver** | "uaga" | Agent2Agent protokoll többügynökös kommunikációhoz |
| **VS kód** | — | [Bővítmény](https://github.com/awaku7/agentcli/blob/main/VSCODE.md) Csevegőpanellel, Magyarázattal, Refaktorral, Hibajavítással és Eszközök fanézettel |

Tekintse meg a [VSCODE.md](https://github.com/awaku7/agentcli/blob/main/VSCODE.md) webhelyet a VS Code bővítmény részleteiért – telepítés, parancsok, billentyűkombinációk és konfiguráció.

### 🏠 IoT-eszközvezérlés

- **SwitchBot**: Cloud kötegelt vezérlés és BLE szkennelés/vezérlés
- **ECHONET Lite**: Fedezze fel és irányítsa a háztartási készülékeket (AC, lámpák, vízmelegítők stb.) a helyi hálózaton
- **Matter**: A vezérlő/híd/eszköz topológia csak olvasható ellenőrzése
- **UPnP**: Eszközfelderítés és IGD port továbbítás

Lásd: [IOT_USECASE.md](https://github.com/awaku7/agentcli/blob/main/IOT_USECASE.md)

### 🎯 Agent Skills Marketplace

A `:skills mp_search' segítségével böngészhet a [SkillsMP](https://skillsmp.com) és a [ClawHub](https://clawhub.ai) webhelyen közösségi készségekért.
Telepítse és bővítse az uag képességeit menet közben.

### 🤖 Auto-Pilot (`:auto`)

Az uag **autonóm módon követheti a célt több LLM-körön keresztül**. Tökéletes összetett, többlépéses feladatokhoz, amelyek ismétlődő finomítást igényelnek.

- **Hogyan működik**: Minden körben van egy fő lekérdezés (A lépés), amelyet egy felülvizsgálói ítélet követ (B. lépés), amely eldönti, hogy "BEFEJEZTE vagy FOLYTATJA?"
- **Ugyanaz a szolgáltató, ugyanaz az API**: A felülvizsgálói döntés ugyanazt a kódútvonalat használja fő lekérdezésként – beleértve a Responses API támogatást is.
- **Különbíró LLM** (opcionális): Állítsa be az `UAGENT_AP_PROVIDER' paramétert, ha más szolgáltatót/modellt szeretne használni a véleményező számára (például használjon olcsóbb modellt az elbíráláshoz).
- **Bármikor kilépés**: Nyomja meg az `x` billentyűt az azonnali leállításhoz, akár válasz közben is. Vagy hagyja, hogy az értékelő döntse el, mikor teljesül a cél.
- **Konfigurálható**: `--max-kör N` a költségvetés szabályozásához.

A teljes dokumentációért lásd: [README_AUTO.md](https://github.com/awaku7/agentcli/blob/main/README_AUTO.md).

### 🧩 Batch State Manager

Az uag nyomon követheti az előrehaladást a hosszan futó többfájlos feladatok között. Amikor az LLM több tucat fájlt dolgoz fel, a "batch_state" a függőben lévő, befejezett és sikertelen fájlok listáját a lemezen tárolja. Ha a munkamenet véget ér, vagy egy kör időtúllépéssel jár, a következő futás onnan folytatódik, ahol abbamaradt – semmi sem vész el.

### 🛡 Human-in-the-Loop

A `human_ask` lehetővé teszi, hogy az LLM megálljon, és megerősítést kérjen, mielőtt romboló műveleteket hajt végre (fájltörlés, felülírás, shell-parancsok). Marad az irányítás.

### 🛑 Megszakítás (c-billentyű / Stop gomb)

Bármikor leállíthatja az LLM-válasz generálását, és visszaadhatja a stop parancsot az LLM-nek.

| Interfész | Hogyan szakítsuk meg |
|---|---|
| **CLI** | Nyomja meg a `c` billentyűt LLM adatfolyam közben – az aktuális válasz leáll, és a "Stop"-t felhasználói üzenetként küldi el, így az LLM ennek megfelelően válaszol |
| **WEBES UI** | Kattintson a piros **■ Stop** gombra (automatikusan megjelenik az LLM feldolgozás során) |
| **Asztali GUI** | Kattintson a piros **■** gombra (automatikusan megjelenik az LLM feldolgozás során) |

A megszakítás "prompt injekcióként" működik: ahelyett, hogy egyszerűen megszakítaná, a "Stop"-t visszaadja az LLM-nek felhasználói üzenetként, lehetővé téve a megszakítás kecses befejezését vagy nyugtázását.

Nyomja meg az „x” billentyűt az automatikus pilóta módból való kilépéshez (lásd: [README_AUTO.md](https://github.com/awaku7/agentcli/blob/main/README_AUTO.md)).

### 🕵️ Böngészőautomatizálás és webellenőr

Két kiegészítő, drámaíró-alapú eszköz:

- **browser_playwright**: Automatizálja a valódi böngészőmunkameneteket – navigálhat, kattinthat, kitöltheti az űrlapokat, kivonhatja az adatokat, kezelheti a többoldalas folyamatokat. Fej nélkül vagy fejjel működik.
- **playwright_inspector**: Böngésző átmenetek rögzítése, DOM-pillanatképek és képernyőképek rögzítése minden lépésnél. Hasznos a webes interakciók hibakereséséhez vagy az oldalváltozások idővel történő ellenőrzéséhez.

### 🔄 Dinamikus eszköz betöltése

A "tool_catalog" és a "tool_load" segítségével futás közben fedezheti fel és engedélyezheti az eszközöket.
Nem kell mindent betölteni indításkor – csak azt aktiválja, amire szüksége van, amikor szüksége van rá.

### 🌐 i18n / L10n

日本語 / angol / 简体中文 / 繁體中文 / 한국어 / Español / Français / Русский / és még sok más.
Állítsa be az „UAGENT_LANG” nyelvet a váltáshoz. Az [ADD_LOCALE.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/ADD_LOCALE.md) oldalon új területi beállítást adhat hozzá.

A README fordításai a [docs/README.translations.md] webhelyen érhetők el (https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md).

### 🔒 Titkosított környezeti változók

Tárolja az API-kulcsokat és titkokat az .env.sec-ben – egy titkosított .env-fájlban.
Kezelje az "uag_envsec" segítségével.

## Konfiguráció és részletek

- **Környezeti változók**: [ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md)
- **Telepítő varázsló**: `python -m uagent.setup_cli`
- **Titkosított env**: `uag_envsec` — `.env` titkosítása `.env.sec`-ként
- **Responses API**: Állítsa be az "UAGENT_RESPONSES=1" értéket a Responses API módhoz (OpenAI/Azure/Bedrock/OpenRouter/Ollama/Alibaba/LM Studio/Sakana AI). Automatikusan engedélyezve a Sakana AI (Fugu) számára.
- **Fejlesztői dokumentumok**: [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)
- **Kis LLM-tippek**: [SLM_TIPS.md](https://github.com/awaku7/agentcli/blob/main/SLM_TIPS.md)

## Projektfilozófia

uag arra törekszik, hogy az Ön MI-je legyen a gépén, az Ön feltételei szerint.**

- Nincs SaaS-függőség – helyileg fut
- Nincs szolgáltatói bezárás - bármikor válthat
- Nincs felhasználói felület zárolása – CLI / GUI / Web / A2A
- Nincs funkciórögzítés – bővítse ki eszközökkel és készségekkel

Ingyenes mesterséges intelligencia ügynöki élmény, mentes a szállítói bekötéstől.
