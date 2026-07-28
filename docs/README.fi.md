<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="720">
</p>

<h1 align="center">uag - Universal AI Gateway</h1>

<p align="center">
  <b>U</b>niversal <b>A</b>I <b>G</b>ateway — Your environment, your freedom.
</p>

<p align="center">
  File ops / Web search / Image generation &amp; analysis / PDF &amp; Excel extraction / IoT control / MCP integration<br>
  20+ providers / 3 UIs / Parallel tool execution / Agent Skills marketplace
</p>

<p align="center">
  <a href="https://github.com/awaku7/agentcli">GitHub</a>
  ·
  <a href="https://pypi.org/project/uag/">PyPI</a>
  ·
  <a href="https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md">Read this in your language</a>
</p>

---

## Miksi uag?

**Vapauta toimittajan lukituksesta.** Useimmat tekoälyavustajat sitovat sinut tiettyyn palveluntarjoajaan tai pilvipalveluun. uag on erilainen.

- **Runs locally** on your machine. Tietosi pysyvät mukanasi (paitsi tekemäsi API-kutsut).
- **Tarjoajan vapaus**: OpenAI, Claude, Gemini, DeepSeek, Ollama, Azure, Bedrock, HuggingFace... 21 palveluntarjoajaa, kaikki käytettävissä yhdestä käyttöliittymästä. Vaihda niiden välillä määrittämällä ympäristömuuttujat uudelleen – ei uudelleenasennusta, ei siirtoa.
- **185 työkalua**: tiedostojen I/O, verkkohaku, kuvien luominen, Gmail, BLE-laitteiden skannaus, MCP-palvelinintegrointi — **111 ovat rinnakkain turvallisia** (jopa 8 suoritetaan samanaikaisesti säikeen varaan kautta, konfiguroitavissa `UAGENT_PARALLEL_WORKERS'-toiminnolla). Kun LLM käynnistää useita työkalukutsuja kerralla, uag rinnastaa ne automaattisesti.
- **3 käyttöliittymää + A2A**: CLI, GUI, Web ja Agent-to-Agent-protokolla. Same engine, any interface.
- **Agenttitaidot**: Asenna yhteisön rakentamia taitoja markkinoilta. Laajenna uag loputtomasti.

uag on **AI-avustajasi sinun ehdoillasi**. Ei sidottu palveluntarjoajaan, ei sidottu käyttöliittymään, ei sidottu alustaan.

## Pikaopas

```bash
pip install uag
uag
```

Ensimmäisen käynnistyksen yhteydessä ohjattu asennustoiminto opastaa sinua palveluntarjoajan määrittämisessä.
Katso kaikki ympäristömuuttujat osoitteesta [docs/ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/docs/ENVIRONMENT.md).

## Ominaisuudet

### 🧠 Usean palveluntarjoajan arkkitehtuuri

OpenAI / Azure / Bedrock / OpenRouter / Ollama / Gemini / Vertex AI / Claude / Grok / NVIDIA / DeepSeek / Z.AI (Zhipu AI) / HuggingFace / Alibaba Cloud (Qwen) / KIMI (Moonshot AI) / Xiaomi MiMo / / LM Studio / MiniMax** / **Together AI** / **Vercel AI Gateway**

Kaikilla palveluntarjoajilla on sama työkalusarja ja käyttöliittymä. Vaihda asettamalla UAGENT_PROVIDER — ei koodimuutoksia, ei erillisiä asennuksia.

### ⚡ Työkalun rinnakkaissuoritus

Kun LLM pyytää useita työkaluja samanaikaisesti, uag **rinnakkaisee** ne automaattisesti.
87 työkalut on merkitty "x_parallel_safe" ja suoritetaan samanaikaisesti "ThreadPoolExecutorin" kautta (oletusarvoisesti 8 säiettä; muuta "UAGENT_PARALLEL_WORKERS").

**Esimerkki**: Kysy "Tarkista sää Pohjoismaiden pääkaupungeissa" → LLM laukaisee `search_web` × 5 maata → kaikki 5 hakua suoritetaan rinnakkain → tulokset kerätään yhdessä erässä.

Vain luku -työkalut (tiedostohaku, hash-laskenta, hakemistolistaus, käännös, tietokantakyselyt jne.) rinnastetaan aggressiivisesti.


### 🧩 Plugin System (Claude Code Compatible)

uagent implements a **Claude Code-compatible plugin system**. Plugins bundle skills, agents, MCP servers, hooks, and more into self-contained directories with a `.claude-plugin/plugin.json` manifest.

**Supported components**: Skills, Sub-agents, MCP servers, Hooks (12 lifecycle events), Slash commands, Output styles, userConfig, Dependencies, Channels, Marketplaces

**CLI commands**:
```
:plugin list                         # List installed plugins
:plugin install <source> [--scope]   # Install (dir/zip/git/http)
:plugin install <name>@<marketplace>  # Install from marketplace
:plugin remove <name>                # Uninstall
:plugin enable/disable <name>        # Toggle
:plugin marketplace add/remove/list  # Manage marketplaces
:plugin init <name>                  # Scaffold new plugin
```

See [DEVELOP_PLUGIN.md](src/uagent/docs/DEVELOP_PLUGIN.md) for full documentation.


### 🔄 Istunnon jatkuvuus

- **Switch providers mid-session** with `UAGENT_PROVIDER` — conversation history is preserved.
- **Reload past sessions** with `:load <index>` — pick up where you left off.
- **Tool result caching** avoids redundant re-execution when the same tool call repeats.

### 🛠 185 Työkalut

| Luokka | Työkalut |
|---|---|
| **Tiedostotoiminnot** | lue/kirjoita/luo/delete/search/grep/hash/zip, file_type, parse_eml (.eml-tiedostot) |
| **Web** | fetch_url, search_web, screenshot, browser_playwright |
| **Media** | genero_image, analysoi_kuva, img2img, audio_speech, audio_transcribe |
| **Asiakirjat** | PDF/PPTX/DOCX/RTF/ODT-uutto, Excel-strukturoitu poiminta |
| **Ennuste** | Aikasarjaennuste 9 mallilla (AutoARIMA, Prophet, LightGBM, CatBoost, TimesFM jne.), automaattinen mallin valinta, kuvaajan luonti, i18n |
| **Viestintä** | gmail_send, gmail_read, bluesky, discord_channel, teams_webhook, **pybitchat** (BLE Mesh) – katso [COMMUNICATION.md](https://github.com/awaku7/agentcli/blob/main/docs/COMMUNICATION.md) ja [BITCHAT.md](https://github.com/awaku7/agentcli/blob/main/docs/BITCHAT.md)|
| **IoT** | BACnet、Modbus TCP、OPC UA、SwitchBot（Cloud + BLE）、ECHONET Lite、Matter、UPnP、reverse_geocode |
| **Kehittäjätyökalut** | git_ops, python_compile, lint_format, run_tests, db_query, **13 lähdekoodinavigaattoria (idx-perhe)** |
| **MCP** | Yhdistä ulkoisiin MCP-palvelimiin, luetteloi työkalut, suorita |
| **A2A** | Agenttien välinen viestintä (muiden uag-esiintymien tai A2A-yhteensopivien palvelimien kanssa) |
| **Järjestelmä** | env vars, järjestelmän tiedot, aika, päivämäärälaskenta, uuid_gen, slugify ||
| **Lähde Nav** | **13 idx-työkalua** Pythonille, PHP:lle, TypeScriptille, Javalle, C#:lle, Dartille, C/C++:lle, Rustille, Golle, Swiftille, Kotlinille, COBOLille – hanki funktio/luokkaindeksi tai tietty määritelmä lukematta koko tiedostoa |

### 🖥 4 käyttöliittymää + VS-koodilaajennus

| Tila | Komento | Tarkoitus |
|---|---|---|
| **CLI** | "uag" | Nopea terminaalipohjainen toiminta |
| **GUI** | "uagg" | Työpöytäkäyttöliittymä tkinterin kautta |
| **Web** | "uagw" | Selainpohjainen pääsy |
| **A2A-palvelin** | "uaga" | Agent2Agent-protokolla usean agentin tietoliikenteeseen |
| **VS-koodi** | — | [Laajennus](https://github.com/awaku7/agentcli/blob/main/docs/VSCODE.md) chat-paneelilla, selityksellä, uudelleentekijällä, korjausvirheellä ja työkaluilla puunäkymä |

Katso [VSCODE.md](https://github.com/awaku7/agentcli/blob/main/docs/VSCODE.md) saadaksesi lisätietoja VS-koodilaajennuksesta – asennuksesta, komennoista, näppäimistä ja määrityksistä.

### 🏠 IoT-laitteiden ohjaus
Katso [IOT_USECASE.md](https://github.com/awaku7/agentcli/blob/main/docs/IOT_USECASE.md)


### 🏠 IoT-laitteiden ohjaus

- **BACnet**: Lue/kirjoita BACnet/IP-laitteita (LVI, valaistus, tehomittarit). COV-tilaus push-ilmoituksia varten
- **Modbus TCP**: Lukea/kirjoita pito-/syöttörekisterit ja kelat. Kyselyyn perustuva muutosten seuranta
- **OPC UA**: Selaa osoiteavaruutta, lue/kirjoita muuttujia, tilaa datamuutoksia
- **SwitchBot**: Cloud eräohjaus ja BLE-skannaus/hallinta. Kyselyyn perustuva tilaus
- **ECHONET Lite**: Löydä, hallitse ja tilaa INF-ilmoitukset kodinkoneista (AC, valot, vedenlämmittimet jne.)
- **Tärkeää**: Luku-/kirjoitusohjaus + attribuuttien tilaus tilanmuutosten seurantaa varten
[=]- **UPnP**: Laitteen etsintä ja IGD-portti BR=]Katso [IOT_USECASE.md](IOT_USECASE.md)

### 🎯 Agent Skills Marketplace

`:skills mp_search` selataksesi [SkillsMP](https://skillsmp.com) ja [ClawHub](https://clawhub.ai) yhteisötaitoja.
Asenna ja laajenna uag:n ominaisuuksia lennossa.

### 🤖 Auto-Pilot (`:auto`)

uag voi **pyrkiä itsenäisesti tavoitteeseen useilla LLM-kierroksilla**. Täydellinen monimutkaisiin, monivaiheisiin tehtäviin, jotka vaativat iteratiivista hienosäätöä.

- **Miten se toimii**: Jokaisella kierroksella on pääkysely (vaihe A), jota seuraa arvioijan arvio (vaihe B), joka päättää "VALMISTEE vai JATKA?"
- **Sama toimittaja, sama API**: Arvioijan arvio käyttää identtistä koodipolkua pääkyselynä – mukaan lukien Responses API -tuki.
- **Erillinen tuomari LLM** (valinnainen): Aseta UAGENT_AP_PROVIDER käyttämään eri palveluntarjoajaa/mallia arvioijalle (käytä esimerkiksi halvempaa mallia arvioinnissa).
- **Poistu milloin tahansa**: Paina `x`-näppäintä lopettaaksesi välittömästi, jopa kesken vastauksen. Tai anna arvioijan päättää, milloin tavoite saavutetaan.
- **Määritettävä**: `--max-kierrokset N' budjetin hallitsemiseksi.

Katso täydelliset asiakirjat kohdasta [README_AUTO.md](https://github.com/awaku7/agentcli/blob/main/docs/README_AUTO.md).

### 🧩 Erätilan johtaja

uag voi seurata edistymistä pitkäkestoisissa monitiedostotehtävissä. Kun LLM käsittelee kymmeniä tiedostoja, "batch_state" säilyttää odottavien, valmiiden ja epäonnistuneiden tiedostojen luettelon levylle. Jos istunto päättyy tai kierros aikakatkaistaan, seuraavaa ajoa jatketaan siitä, mihin se pysähtyi – mitään ei häviä.

### 🛡 Human-in-the-Loop

"human_ask" antaa LLM:n pysähtyä ja pyytää vahvistusta ennen tuhoavien toimintojen suorittamista (tiedoston poistaminen, päällekirjoitukset, komentotulkkikomennot). Pysyt hallinnassasi.

### 🛑 Keskeytys (c-näppäin / Stop-painike)

Pysäytä LLM-vastauksen luominen milloin tahansa ja anna pysäytyskomento takaisin LLM:ään.

| Käyttöliittymä | Kuinka keskeyttää |
|---|---|
| **CLI** | Paina `c`-näppäintä LLM-suoratoiston aikana — nykyinen vastaus pysähtyy ja `"Stop"` lähetetään käyttäjäviestinä, joten LLM vastaa vastaavasti |
| **VERKKO-UI** | Napsauta punaista **■ Stop** -painiketta (näkyy automaattisesti LLM-käsittelyn aikana) |
| **Työpöytäkäyttöliittymä** | Napsauta punaista **■**-painiketta (näkyy automaattisesti LLM-käsittelyn aikana) |

Keskeytys toimii "prompt-injektiona": pelkän keskeyttämisen sijaan se syöttää "Stop"' takaisin LLM:lle käyttäjäviestinä, jolloin se voi päättää tai kuitata keskeytyksen sulavasti.

Poistu automaattiohjaustilasta painamalla x-näppäintä (katso [README_AUTO.md](https://github.com/awaku7/agentcli/blob/main/docs/README_AUTO.md)).

### 🕵️ Selainautomaatio ja Web Inspector

Kaksi toisiaan täydentävää näytelmäkirjailijapohjaista työkalua:

- **browser_playwright**: Automatisoi todelliset selainistunnot – navigoi, napsauta, täytä lomakkeita, poimi tietoja, käsittele monisivuisia kulkuja. Toimii päättömänä tai päättömänä.
- **playwright_inspector**: Tallenna selaimen siirtymät, kaappaa DOM-otoksia ja kuvakaappauksia jokaisessa vaiheessa. Hyödyllinen verkkovuorovaikutusten virheenkorjauksessa tai sivumuutosten tarkastamisessa ajan mittaan.

### 🔄 Dynaaminen työkalun lataus

"tool_catalog" ja "tool_load" antavat sinun löytää ja ottaa työkalut käyttöön suorituksen aikana.
Kaikkea ei tarvitse ladata käynnistyksen yhteydessä – aktivoi vain tarvitsemasi, kun tarvitset sitä.


### 🦀 Rust Native Tools

`uuid_gen` and `slugify` are implemented in Rust (via PyO3) for performance.
They load directly from a pre-built `.pyd` — **no `pip install` required**.

External developers can also ship Rust-based tools: place a `.pyd` next to the
wrapper `.py`, use ``load_rust_pyd()`` from ``uagent.tools.rust_helper``, and
users get the tool without any extra dependencies. See
[TOOL_CREATOR_GUIDE.fi.md](TOOL_CREATOR_GUIDE.fi.md).

### 🌐 i18n / L10n

日本語 / Englanti / 简体中文 / 繁體中文 / 한국어 / Español / Français / Русский / ja paljon muuta.
Aseta UAGENT_LANG vaihtaaksesi. Katso [ADD_LOCALE.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/ADD_LOCALE.md) lisätäksesi uuden kielen.

Tämän README:n käännökset ovat saatavilla osoitteessa [docs/README.translations.md](https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md).

### 🔒 Salatut ympäristömuuttujat

Tallenna API-avaimet ja salaisuudet .env.sec-salatussa .env-tiedostossa.
Hallinnoi komennolla "uag_envsec".

## Kokoonpano ja tiedot

- **Ympäristömuuttujat**: [docs/ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/docs/ENVIRONMENT.md)
- **Ohjattu asennustoiminto**: `python -m uagent.setup_cli`
- **Salattu env**: `uag_envsec` — salaa `.env` muodossa `.env.sec`
- **Responses API**: Aseta `UAGENT_RESPONSES=1` Responses API -tilalle (OpenAI/Azure/Bedrock/OpenRouter/Ollama/Alibaba/LM Studio/Sakana AI). Automaattinen käytössä Sakana AI:lle (Fugu).
- **Kehittäjien asiakirjat**: [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)
- **Tool flow**: [TOOL_FLOW.md](../src/uagent/docs/TOOL_FLOW.md)
- **Pienet LLM-vinkit**: [SLM_TIPS.md](https://github.com/awaku7/agentcli/blob/main/docs/SLM_TIPS.md)

## Projektifilosofia

uag pyrkii olemaan **tekoäly, koneellasi, sinun ehdoillasi.**

- Ei SaaS-riippuvuutta - toimii paikallisesti
- Ei palveluntarjoajan lukitusta - vaihda milloin tahansa
- Ei käyttöliittymän lukitusta - CLI / GUI / Web / A2A
- Ei toimintojen lukitusta - laajenna työkaluilla ja taidoilla

Ilmainen tekoälyagenttikokemus ilman toimittajan lukitusta.

### ✨ Create Your Own Tools

Writing a new tool for uag is straightforward — create a single `.py` file with
`TOOL_SPEC` and `run_tool()`, place it in ``UAGENT_EXTERNAL_TOOLS_DIR``, and
it's immediately available. For Rust developers, ship a pre-built `.pyd` with
zero extra dependencies for users.

See [TOOL_CREATOR_GUIDE.fi.md](TOOL_CREATOR_GUIDE.fi.md)
for the step-by-step guide.

## Contributing

Contributions are welcome! Bug reports, feature suggestions, documentation improvements, translations, and pull requests — all appreciated.

- **Issues**: Open a GitHub issue for bugs or feature requests.
- **Pull requests**: Fork the repo, make your changes, and submit a PR. See [DEVELOP.md](../src/uagent/docs/DEVELOP.md) for development setup and guidelines.
- **Translations**: README translations and locale additions are welcome. See [ADD_LOCALE.md](../src/uagent/docs/ADD_LOCALE.md).
- **Tools & Skills**: New tool plugins and Agent Skills can be contributed via the marketplace.

Realtime Ääni ja AEC3

## Realtime-äänitila tukee kaksisuuntaista mikrofonia ja kaiuttimen tuloa/lähtöä. Jos AEC3-taustaosa puuttuu, uag asentaa pywebrtc-audio:n automaattisesti.

```bat
python scheck.py realtime
```

AEC3 käyttää todellista mikrofonisignaalia (lähellä) ja kaiuttimeen lähetettyä ääntä (kaukana). Ota diagnostiikka käyttöön vain, kun tutkit ääniongelmia.

```bat
set UAGENT_REALTIME_AUDIO_DEBUG=1
python scheck.py realtime
```

### OpenAI Realtime Function Calling

OpenAI Realtime tukee turvarajoitettua Function Calling-integraatiota. Nykyinen sovitin paljastaa vain luku -toiminnon get_current_time automaattisesti. Tuhoavat työkalut ja laiteohjaimet vaativat nimenomaisen sallittujen luettelon ja vahvistuksen. Grok reaaliaikainen käyttää erillistä sovitinta, eikä käytä tätä OpenAI-kohtaista Function Calling-polkua.
