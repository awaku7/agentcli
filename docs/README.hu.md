<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logó" width="720">
</p>

<h1 align="center">uag – Universal AI Gateway</h1>

<p align="center">
  <b>U</b>verzális <b>A</b>I <b>G</b>ateway — A környezeted, a te szabadságod.
</p>

<p align="center">
  Fájlműveletek / Webes keresés / Képgenerálás és -elemzés / PDF és Excel kivonás / IoT-vezérlés / MCP-integráció<br>
  15+ szolgáltató / 3 felhasználói felület / Párhuzamos eszközvégrehajtás / Ügynöki készségek piactér
</p>

<p align="center">
  <a href="https://github.com/awaku7/agentcli">GitHub</a>
  ·
  <a href="https://pypi.org/project/uag/">PyPI</a>
  ·
  <a href="https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md">Olvassa el az Ön nyelvén</a>
</p>

---

## Miért uag?

**Szabadjon ki a szállítói bezárás alól.** A legtöbb AI-asszisztens egy adott szolgáltatóhoz vagy felhőszolgáltatáshoz köti Önt. uag más.

- **Lokálisan fut** a gépén. Adatai Önnél maradnak (kivéve az Ön által kezdeményezett API-hívásokat).
- **Szolgáltatói szabadság**: OpenAI, Claude, Gemini, DeepSeek, Ollama, Azure, Bedrock... 15+ szolgáltató, mindegyik egyetlen felületről elérhető. Váltson közöttük a környezeti változók újrakonfigurálásával – nincs újratelepítés, nincs migráció.
- **111 eszköz**: Fájl I/O, webes keresés, képgenerálás, BLE-eszköz szkennelés, MCP szerver integráció – és **55 párhuzamosan fut**. Amikor az LLM egyszerre több eszközhívást indít el, az uag automatikusan végrehajtja azokat egy szálkészleten keresztül.
- **3 felhasználói felület + A2A**: CLI, GUI, web és Agent-to-Agent protokoll. Ugyanaz a motor, bármilyen interfész.
- **IoT-kész**: SwitchBot, ECHONET Lite, Matter, UPnP – vezérelje otthoni eszközeit mesterséges intelligencia segítségével.
- **Agent Skills**: Telepítse a közösség által épített készségeket a piacról. Hosszabbítsa meg az uag-ot végtelenül.

uag **az Ön AI-asszisztense az Ön feltételei szerint**. Nincs szolgáltatóhoz, nem interfészhez, nem platformhoz kötve.

## Gyors kezdés

``` bash
pip install uag
uag
```

Az első indításkor a telepítővarázsló végigvezeti a szolgáltató konfigurációján.
Az összes környezeti változóhoz lásd az [ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md) webhelyet.

## Jellemzők

### 🧠 Többszolgáltatós architektúra

OpenAI / Azure / Bedrock / OpenRouter / Ollama / Gemini / Vertex AI / Claude / Grok / NVIDIA / DeepSeek / Alibaba Cloud (Qwen) / KIMI (Moonshot AI) / Xiaomi MiMo / LM Studio

Minden szolgáltató ugyanazt az eszközkészletet és felületet használja. Váltás az "UAGENT_PROVIDER" beállításával – nincs kódmódosítás, nincs külön telepítés.

### ⚡ Párhuzamos szerszámvégrehajtás

Amikor az LLM egyszerre több eszközt kér, az uag **automatikusan párhuzamosítja** azokat.
55 eszközt `x_parallel_safe` jelölnek, és egyidejűleg futnak egy 4 szálas `ThreadPoolExecutor` segítségével.

**Példa**: Kérdezze meg: "Ellenőrizze az időjárást északi fővárosokban" → Az LLM a `search_web` × 5 országot indítja el → mind az 5 keresés párhuzamosan fut → az eredmények egy kötegben gyűjtve.

A csak olvasható eszközök (fájlkeresés, hash számítás, könyvtárlista, fordítás, DB lekérdezések stb.) agresszíven párhuzamosak.

### 🔄 Munkamenet folytonossága

- **Szolgáltatóváltás a munkamenet közben** a `UAGENT_PROVIDER' szolgáltatással – a beszélgetési előzmények megmaradnak.
- **Korábbi munkamenetek újratöltése** a `:load <index>` paraméterrel – folytassa onnan, ahol abbahagyta.
- Az **Eszközeredmények gyorsítótárazása** elkerüli a redundáns újrafuttatást, amikor ugyanaz az eszközhívás ismétlődik.

### 🛠 111 Eszközök

| Kategória | Eszközök |
|---|---|
| **Fájlműveletek** | read/write/create/delete/search/grep/hash/zip |
| **Web** | fetch_url, search_web, screenshot, browser_playwright |
| **Média** | gener_image, analysis_image, img2img, audio_speech, audio_transcribe |
| **Dokumentumok** | PDF/PPTX/DOCX/RTF/ODT kinyerés, Excel strukturált kivonat |
| **IoT** | SwitchBot (Cloud + BLE), ECHONET Lite, Matter, UPnP |
| **Fejlesztői eszközök** | git_ops, python_compile, lint_format, run_tests, db_query |
| **MCP** | Csatlakozás külső MCP-kiszolgálókhoz, eszközök listázása, |
| **A2A** | Ügynök-ügynök kommunikáció (más uag-példányokkal vagy A2A-kompatibilis szerverekkel) |
| **Rendszer** | env vars, rendszerspecifikációk, idő, dátum számítás |

### 🖥 3 interfész + A2A

| mód | Parancs | Cél |
|---|---|---|
| **CLI** | "uag" | Gyors terminál alapú működés |
| **GUI** | "uagg" | Asztali felhasználói felület a tkinterrel |
| **Web** | "uagw" | Böngésző alapú hozzáférés |
| **A2A szerver** | "uaga" | Agent2Agent protokoll többügynökös kommunikációhoz |

### 🏠 IoT-eszközvezérlés

- **SwitchBot**: Cloud kötegelt vezérlés és BLE szkennelés/vezérlés
- **ECHONET Lite**: Fedezze fel és irányítsa a háztartási készülékeket (AC, lámpák, vízmelegítők stb.) a helyi hálózaton
- **Matter**: A vezérlő/híd/eszköz topológia csak olvasható ellenőrzése
- **UPnP**: Eszközfelderítés és IGD port továbbítás

Lásd: [IOT_USECASE.md](https://github.com/awaku7/agentcli/blob/main/IOT_USECASE.md)

### 🎯 Agent Skills Marketplace

A `:skills mp_search' segítségével böngészhet a [SkillsMP](https://skillsmp.com) és a [ClawHub](https://clawhub.ai) webhelyen közösségi készségekért.
Telepítse és bővítse az uag képességeit menet közben.

### 🧩 Batch State Manager

Az uag nyomon követheti az előrehaladást a hosszan futó többfájlos feladatok között. Amikor az LLM több tucat fájlt dolgoz fel, a "batch_state" a függőben lévő, befejezett és sikertelen fájlok listáját a lemezen tárolja. Ha a munkamenet véget ér, vagy egy kör időtúllépéssel jár, a következő futás onnan folytatódik, ahol abbamaradt – semmi sem vész el.

### 🛡 Human-in-the-Loop

A `human_ask` lehetővé teszi, hogy az LLM megálljon, és megerősítést kérjen, mielőtt romboló műveleteket hajt végre (fájltörlés, felülírás, shell-parancsok). Marad az irányítás.

### 🕵️ Böngészőautomatizálás és webellenőr

Két kiegészítő, drámaíró-alapú eszköz:

- **browser_playwright**: Automatizálja a valódi böngészőmunkameneteket – navigálhat, kattinthat, kitöltheti az űrlapokat, kivonhatja az adatokat, kezelheti a többoldalas folyamatokat. Fej nélkül vagy fejjel működik.
- **playwright_inspector**: Böngésző átmenetek rögzítése, DOM-pillanatképek és képernyőképek rögzítése minden lépésnél. Hasznos a webes interakciók hibakereséséhez vagy az oldalváltozások idővel történő ellenőrzéséhez.

### 🔄 Dinamikus eszköz betöltése

A "tool_catalog" és a "tool_load" segítségével futás közben fedezheti fel és engedélyezheti az eszközöket.
Nem kell mindent betölteni indításkor – csak azt aktiválja, amire szüksége van, amikor szüksége van rá.

### 🌐 i18n / L10n

日本語 / angol / 简体中文 / 繁體中文 / 한국어 / Español / Français / Русский / és így tovább.
A váltáshoz állítsa be az „UAGENT_LANG” nyelvet. Az [ADD_LOCALE.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/ADD_LOCALE.md) oldalon új területi beállítást adhat hozzá.

A README fordításai a [docs/README.translations.md] webhelyen érhetők el (https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md).

### 🔒 Titkosított környezeti változók

Tárolja az API-kulcsokat és titkokat a `.env.sec`-ben – egy titkosított `.env`-fájlban.
Kezelje az "uag_envsec" segítségével.

## Konfiguráció és részletek

- **Környezeti változók**: [ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md)
- **Telepítő varázsló**: `python -m uagent.setup_cli`
- **Titkosított env**: `uag_envsec` — `.env` titkosítása `.env.sec`-ként
- **Responses API**: Állítsa be az "UAGENT_RESPONSES=1" értéket a Responses API módhoz (OpenAI/Azure/Bedrock/OpenRouter/Ollama/LM Studio)
- **Fejlesztői dokumentumok**: [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)
- **Kis LLM-tippek**: [SLM_TIPS.md](https://github.com/awaku7/agentcli/blob/main/SLM_TIPS.md)

## Projektfilozófia

uag arra törekszik, hogy az Ön MI-je legyen a gépén, az Ön feltételei szerint.**

- Nincs SaaS-függőség – helyileg fut
- Nincs szolgáltatói bezárás - bármikor válthat
- Nincs felhasználói felület zárolása – CLI / GUI / Web / A2A
- Nincs funkciórögzítés – bővítse ki eszközökkel és készségekkel

Ingyenes mesterséges intelligencia ügynöki élmény, mentes a szállítói bekötéstől.