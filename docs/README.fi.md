<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag-logo" width="720">
</p>

<h1 align="center">uag – Universal AI Gateway</h1>

<p align="center">
  <b>U</b>yleinen <b>A</b>I <b>G</b>teway – ympäristösi, vapautesi.
</p>

<p align="center">
  Tiedostojen käyttö / Verkkohaku / Kuvien luominen ja analysointi / PDF- ja Excel-poiminta / IoT-hallinta / MCP-integrointi<br>
  Yli 15 palveluntarjoajaa / 3 käyttöliittymää / Rinnakkaistyökalujen suoritus / Agent Skills Marketplace
</p>

<p align="center">
  <a href="https://github.com/awaku7/agentcli">GitHub</a>
  ·
  <a href="https://pypi.org/project/uag/">PyPI</a>
  ·
  <a href="https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md">Lue tämä omalla kielelläsi</a>
</p>

---

## Miksi uag?

**Vapauta toimittajan lukituksesta.** Useimmat tekoälyavustajat sitovat sinut tiettyyn palveluntarjoajaan tai pilvipalveluun. uag on erilainen.

- **Toimii paikallisesti** koneellasi. Tietosi pysyvät mukanasi (paitsi tekemäsi API-kutsut).
- **Toimittajan vapaus**: OpenAI, Claude, Gemini, DeepSeek, Ollama, Azure, Bedrock... Yli 15 palveluntarjoajaa, kaikki käytettävissä yhdestä käyttöliittymästä. Vaihda niiden välillä määrittämällä ympäristömuuttujat uudelleen – ei uudelleenasennusta, ei siirtoa.
- **131 työkalua**: tiedostojen I/O, verkkohaku, kuvan luominen, BLE-laitteiden skannaus, MCP-palvelinintegrointi – ja **76 niistä toimii rinnakkain**. Kun LLM käynnistää useita työkalukutsuja kerralla, uag suorittaa ne automaattisesti säiejoukon kautta.
- **3 käyttöliittymää + A2A**: CLI, GUI, Web ja Agent-to-Agent -protokolla. Sama moottori, mikä tahansa käyttöliittymä.
- **IoT-valmius**: SwitchBot, ECHONET Lite, Matter, UPnP – ohjaa kodin laitteita tekoälyn avulla.
- **Agenttitaidot**: Asenna yhteisön rakentamia taitoja markkinoilta. Laajenna uag loputtomasti.

uag on **AI-avustajasi sinun ehdoillasi**. Ei sidottu palveluntarjoajaan, ei sidottu käyttöliittymään, ei sidottu alustaan.

## Pika-aloitus

```bash
pip install uag
uag
```

Ensimmäisen käynnistyksen yhteydessä ohjattu asennustoiminto opastaa sinua palveluntarjoajan määrittämisessä.
Katso kaikki ympäristömuuttujat osoitteesta [ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md).

## Ominaisuudet

### 🧠 Usean palveluntarjoajan arkkitehtuuri

OpenAI / Azure / Bedrock / OpenRouter / Ollama / Gemini / Vertex AI / Claude / Grok / NVIDIA / DeepSeek / Alibaba Cloud (Qwen) / KIMI (Moonshot AI) / Xiaomi MiMo / LM Studio / MiniMax

Kaikilla palveluntarjoajilla on sama työkalusarja ja käyttöliittymä. Vaihda asettamalla UAGENT_PROVIDER — ei koodimuutoksia, ei erillisiä asennuksia.

### ⚡ Työkalun rinnakkaissuoritus

Kun LLM pyytää useita työkaluja samanaikaisesti, uag **rinnakkaisee** ne automaattisesti.
76 työkalua on merkitty `x_parallel_safe`, ja ne suoritetaan samanaikaisesti 4-säikeisen ThreadPoolExecutorin kautta.

**Esimerkki**: Kysy "Tarkista sää Pohjoismaiden pääkaupungeissa" → LLM laukaisee `search_web` × 5 maata → kaikki 5 hakua suoritetaan rinnakkain → tulokset kerätään yhdessä erässä.

Vain luku -työkalut (tiedostohaku, hash-laskenta, hakemistolistaus, käännös, tietokantakyselyt jne.) rinnastetaan aggressiivisesti.

### 🔄 Istunnon jatkuvuus

- **Vaihda palveluntarjoajaa kesken istunnon** UAGENT_PROVIDER:n kanssa – keskusteluhistoria säilyy.
- **Lataa aiemmat istunnot** komennolla `:load <index>` – jatka siitä, mihin jäit.
- **Työkalun tulosten välimuisti** välttää redundantin uudelleensuorituksen, kun sama työkalukutsu toistuu.

### 🛠 131 Työkalut

| Luokka | Työkalut |
|---|---|
| **Tiedostotoiminnot** | lue/kirjoita/luo/delete/search/grep/hash/zip |
| **Web** | fetch_url, search_web, screenshot, browser_playwright |
| **Media** | genero_image, analysoi_kuva, img2img, audio_speech, audio_transcribe |
| **Asiakirjat** | PDF/PPTX/DOCX/RTF/ODT-uutto, Excel-strukturoitu poiminta |
| **IoT** | SwitchBot (Cloud + BLE), ECHONET Lite, Matter, UPnP |
| **Kehittäjätyökalut** | git_ops, python_compile, lint_format, run_tests, db_query, **13 idx tools** |
| **MCP** | Yhdistä ulkoisiin MCP-palvelimiin, luetteloi työkalut, suorita |
| **A2A** | Agenttien välinen viestintä (muiden uag-esiintymien tai A2A-yhteensopivien palvelimien kanssa) |
| **Järjestelmä** | env vars, järjestelmän tiedot, aika, päivämäärälaskenta |

### 🖥 3 liitäntää + A2A

| Tila | Komento | Tarkoitus |
|---|---|---|
| **CLI** | `uag` | Nopea terminaalipohjainen toiminta |
| **GUI** | `uagg` | Työpöytäkäyttöliittymä tkinterin kautta |
| **Web** | `uagw` | Selainpohjainen pääsy |
| **A2A-palvelin** | `uaga` | Agent2Agent-protokolla usean agentin tietoliikenteeseen |

### 🏠 IoT-laitteiden ohjaus

- **SwitchBot**: Cloud eräohjaus ja BLE-skannaus/ohjaus
- **ECHONET Lite**: Löydä ja hallitse kodinkoneet (AC, valot, vedenlämmittimet jne.) paikallisverkossa
- **Matter**: Ohjaimen/sillan/laitteen topologian vain luku -tarkastus
- **UPnP**: Laitteen etsintä ja IGD-portin edelleenlähetys

Katso [IOT_USECASE.md](https://github.com/awaku7/agentcli/blob/main/IOT_USECASE.md)

### 🎯 Agent Skills Marketplace

`:skills mp_search` selataksesi [SkillsMP](https://skillsmp.com) ja [ClawHub](https://clawhub.ai) yhteisötaitoja.
Asenna ja laajenna uag:n ominaisuuksia lennossa.

### 🧩 Erätilan johtaja

uag voi seurata edistymistä pitkäkestoisissa monitiedostotehtävissä. Kun LLM käsittelee kymmeniä tiedostoja, "batch_state" säilyttää odottavien, valmiiden ja epäonnistuneiden tiedostojen luettelon levylle. Jos istunto päättyy tai kierros aikakatkaistaan, seuraavaa ajoa jatketaan siitä, mihin se pysähtyi – mitään ei häviä.

### 🛡 Ihminen silmukassa

"human_ask" antaa LLM:n pysähtyä ja pyytää vahvistusta ennen tuhoavien toimintojen suorittamista (tiedoston poistaminen, ylikirjoitukset, komentotulkkikomennot). Pysyt hallinnassasi.

### 🕵️ Selaimen automaatio ja verkkotarkastaja

Kaksi toisiaan täydentävää näytelmäkirjailijapohjaista työkalua:

- **browser_playwright**: Automatisoi todelliset selainistunnot – navigoi, napsauta, täytä lomakkeita, poimi tietoja, käsittele monisivuisia kulkuja. Toimii päättömänä tai päättömänä.
- **playwright_inspector**: Tallenna selaimen siirtymät, kaappaa DOM-otoksia ja kuvakaappauksia jokaisessa vaiheessa. Hyödyllinen verkkovuorovaikutusten virheenkorjauksessa tai sivumuutosten tarkastamisessa ajan mittaan.

### 🔄 Dynaaminen työkalun lataus

"tool_catalog" ja "tool_load" antavat sinun löytää ja ottaa työkalut käyttöön suorituksen aikana.
Kaikkea ei tarvitse ladata käynnistyksen yhteydessä – aktivoi vain tarvitsemasi, kun tarvitset sitä.

### 🌐 i18n / L10n

日本語 / Englanti / 简体中文 / 繁體中文 / 한국어 / Español / Français / Русский / ja paljon muuta.
Aseta UAGENT_LANG vaihtaaksesi. Katso [ADD_LOCALE.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/ADD_LOCALE.md) lisätäksesi uuden kielen.

Tämän README:n käännökset ovat saatavilla osoitteessa [docs/README.translations.md](https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md).

### 🔒 Salatut ympäristömuuttujat

Tallenna API-avaimet ja salaisuudet .env.sec-salatussa .env-tiedostossa.
Hallitse komennolla "uag_envsec".

## Kokoonpano ja tiedot

- **Ympäristömuuttujat**: [ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md)
- **Ohjattu asennustoiminto**: `python -m uagent.setup_cli`
- **Salattu env**: `uag_envsec` — salaa `.env` muodossa `.env.sec`
- **Responses API**: aseta `UAGENT_RESPONSES=1` Responses API -tilalle (OpenAI/Azure/Bedrock/OpenRouter/Ollama/LM Studio)
- **Kehittäjien asiakirjat**: [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)
- **Pienet LLM-vinkit**: [SLM_TIPS.md](https://github.com/awaku7/agentcli/blob/main/SLM_TIPS.md)

## Projektifilosofia

uag pyrkii olemaan **tekoälysi, koneellasi, sinun ehdoillasi.**

- Ei SaaS-riippuvuutta - toimii paikallisesti
- Ei palveluntarjoajan lukitusta - vaihda milloin tahansa
- Ei käyttöliittymän lukitusta - CLI / GUI / Web / A2A
- Ei toimintojen lukitusta – laajenna työkaluilla ja taidoilla

Ilmainen tekoälyagenttikokemus ilman toimittajan lukitusta.