<p align="center">
 <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="720">
</p>

<h1 AI PH_4">Universaali Yhdyskäytävä</h1>

<p align="center">
 <b>U</b>yleinen <b>A</b>I <b>G</b>-portti – ympäristösi, sinun vapautesi.
</p>

<p align="center">
 Tiedoston toiminnot / Web-haku / I_o-tiedostojen hallinta / / PDF-tiedostojen hallinta ja analysointi integraatio<br>
 24 palveluntarjoajaa / 3 käyttöliittymää / Rinnakkaistyökalujen suoritus / Agent Skills Marketplace
</p>

<p align="center">
 <a href="https://github.com/awaku7/agentcli">GitHub</a>
 ·
 <a href="https://pypi.org/project/uag/">PyPI</a>
 ·
 <a href="https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md">Read this in your language</a>
</p>
_________________________________________## Miksi uag?

**Vapauta toimittajan lukituksesta.** Useimmat tekoälyavustajat sitovat sinut tiettyyn palveluntarjoajaan tai pilvipalveluun. uag on erilainen.

- **Toimii paikallisesti** koneellasi. Tietosi pysyvät mukanasi (paitsi API soittamaasi puhelua).
- **Toimittajan vapaus**: OpenAI, Claude, Gemini, DeepSeek, Ollama, Azure, Bedrock, Novita, HuggingFace... 24 palveluntarjoajaa, kaikki käytettävissä yhdestä käyttöliittymästä. Vaihda niiden välillä määrittämällä ympäristömuuttujat uudelleen – ei uudelleenasennusta, ei siirtoa.
- **222-työkalut**: tiedostojen I/O, verkkohaku, kuvan luominen, Gmail, BLE-laitteiden skannaus, MCP-palvelinintegrointi — **130 on staattisesti merkitty rinnakkain turvalliseksi** (jopa 8 suoritettavaa samanaikaisesti PARS:n kautta, konfiguroitavissa ALL`WALL`UENT:n kautta). Kun LLM käynnistää useita työkalukutsuja kerralla, uag rinnastaa ne automaattisesti.
- **3 käyttöliittymää + A2A**: CLI, GUI, Web ja Agent-to-Agent-protokolla. Sama moottori, mikä tahansa käyttöliittymä.
- **IoT-valmius**: SwitchBot, ECHONET Lite, Matter, UPnP – ohjaa kodin laitteita tekoälyn avulla.
- **Agenttitaidot**: Asenna yhteisön rakentamia taitoja markkinoilta. Laajenna uag loputtomasti.

uag on **AI-avustajasi ehdoillasi**. Ei sidottu palveluntarjoajaan, ei sidottu käyttöliittymään, ei sidottu alustaan.

## Pika-aloitus

```bash
pip install uag
uag
```

The base installation keeps provider and tool integrations optional. Missing packages are installed automatically when a selected provider or tool needs one.

```bash
pip install "uag[core,providers,tools,development,platform,web]"
```

For a repository checkout with the full development and test environment:

```bash
pip install -r requirements.txt
```

## Computer Use

Computer Use on valinnainen ja tukee sekä näkyvää Playwright-selaimen suoritusaikaa
että työpöydän suoritusaikaa. Kun tämä on käytössä, molemmat suoritusajat luodaan ja rekisteröidään;

````bat
set UAGENT_COMPUTER_USE=1
suljetaan yhdessä normaalin poistumisen, `Ctrl-C` ja prosessin sulkemisen yhteydessä. Aseta
`UAGENT_COMPUTER_HEADLESS=1` selainpohjaisille CI- tai savutesteille.
Katso [docs/COMPUTER_USE_IMPLEMENTATION.md](docs/COMPUTER_USE_IMPLEMENTATION.md)
integraatio- ja turvallisuustiedot.

## Reaaliaikainen ääni ja AEC3

Reaaliaikainen äänitila tukee OpenAI Realtime, Azure OpenAI GPT Reaaliaikainen, xAI Grok Voice API, Google Gemini Multimodal Live ja S-mikrofoninen Full-puhelimella ja S-mikrofonisella __PH-duu-puhelimella. I/O. Vaadittu pywebrtc-audio AEC3-taustaosa asennetaan automaattisesti, ja Bedrockin valinnainen kaksisuuntainen suoratoisto-SDK asennetaan automaattisesti vain, kun Bedrock-palveluntarjoaja on valittuna:

```bash
python scheck.py realtime
````

AEC3-mikropuhelinsignaali vastaanottaa todellisen käsin tarkoitetun ääniputken. (`kaukaan`), jotta avustaja voi kuunnella puhuessaan. Ota diagnostiikka käyttöön vain, kun tutkit ääniongelmia:

```bat
set UAGENT_REALTIME_AUDIO_DEBUG=1
python scheck.py realtime
```

### OpenAI Reaaliaikainen toimintokutsu

OpenAI Turvallisuus-Reaaliaikainen tuki. Nykyinen reaaliaikainen sovitin paljastaa vain luku -muodon "get_current_time" automaattisesti. Tuhoavat työkalut ja laitteiden säätimet eivät tule näkyviin ilman nimenomaista sallittujen luetteloa ja vahvistuskulkua. Grok reaaliaikainen käyttää erillistä sovitinta, eikä käytä tätä OpenAI-kohtaista toimintokutsupolkua.

## Ominaisuudet

### 🧠 Monen palveluntarjoajan arkkitehtuuri

OpenAI / PFN (PLaMo) / Azure / Bedrock / OpenRouter / Ollama / llama.cpp / Gemini / Vertex AI / Claude / ZAI /NAI / ZGrok / Z\_\_DeepSeek (Zhipu AI) / HuggingFace / Alibaba Cloud (Qwen) / KIMI (Moonshot AI) / Xiaomi MiMo / LM Studio / MiniMax / Sakana AI (Fugu) / SAKURA AI Engine / Together AI / Vercel AI Gateway

Kaikilla palveluntarjoajilla on samat työkalut ja käyttöliittymä. Vaihda asettamalla UAGENT_PROVIDER — ei koodimuutoksia, ei erillisiä asennuksia.

#### Ollama ja llama.cpp

Ollama ja llama.cpp ovat erillisiä palveluntarjoajia. Ollama käyttää omaa palvelu- ja mallihallintaansa, kun taas `llama.cpp` muodostaa yhteyden `llama-server` OpenAI-yhteensopivaan päätepisteeseen:

```bash
# llama.cpp / llama-server
UAGENT_PROVIDER=llama_cpp
UAGENT_LLAMA_CPP_BASE_URL=http://localhost:8080/v1
UAGENT_LLAMA_CPP_DEPNAME=local-model
UAGENT_LLAMA_CPP_API_KEY=dummy
```

:plugin list # Listaa asennetut laajennukset
:plugin install \<lähde> [--scope] # Asenna (dir/zip/git/http)

> Asennus paikasta poista <nimi> # Poista
> :plugin käytössä/pois käytöstä <nimi> # Toggle
> :plugin marketplace add/remove/list # Hallitse kauppapaikkoja
> :plugin init <nimi> # Scaffold new plugin

````

Katso [DEVELOP_PLUGIN.md](src./PLUGIN.md) täydelliset dokumentaatiot.

### 🔄 Istunnon jatkuvuus

- **Vaihda palveluntarjoajaa istunnon puolivälissä** `UAGENT_PROVIDER`:n kanssa – keskusteluhistoria säilyy.
- **Lataa aiemmat istunnot** komennolla `:load <index>` — jatka välimuistiin** ja suorituksen välttämisestä. sama työkalukutsu toistuu.

### 🛠 229 Työkalut

| Luokka | Työkalut |
|---|---|
| **Tiedostotoiminnot** | read/write/create/delete/search/grep/hash/zip, file_type, parse_eml (.eml-tiedostot), `path_alias` |
| **Web** | hae_url, search_web, screenshot, browser_playwright, "url_alias", "public_transit_route" ([opas](docs/PUBLIC_TRANSIT_ROUTE.md)) |
| **Media** | genero_image, analysoi_kuva, img2img, audio_speech, audio_transcribe |
| **Asiakirjat** | PDF/PPTX/DOCX/RTF/ODT-poiminta, Excel-strukturoitu poiminta |
| **Ennuste** | Aikasarjaennuste 9 mallilla (AutoARIMA, Prophet, LightGBM, CatBoost, TimesFM jne.), automaattinen mallin valinta, juonen luominen, i18n |
| **Viestintä** | gmail_send, gmail_read, bluesky, discord_channel, teams_webhook, **pybitchat** (BLE Mesh) – katso [COMMUNICATION.md](https://github.com/awaku7/agentcli/blob/main/docs/COMMUNICATION.md) ja [BITCHAT.md](https://github.com/awaku7/agentcli/blob/main/docs/BITCHAT.md) |
| **IoT** | SwitchBot (Cloud + BLE), ECHONET Lite, Matter, UPnP, reverse_geocode |
| **Pilvisovellusliittymät** | "aws_api", "gcp_api", "azure_api" – yleiset AWS-, Google-pilvi- ja Azure API -toiminnot; kirjoitustoiminnot vaativat nimenomaisen vahvistuksen |
| **Kehittäjätyökalut** | workspace_status, git_ops, git_review, security_scan, coverage_report, python_compile, lint_format, run_tests, db_query, **29 lähdekoodinavigaattoria (idx-perhe)** |
| **MCP** | Yhdistä ulkoisiin MCP-palvelimiin, luetteloi työkaluja, suorita — [OAuth / Proxy-opas](docs/MCP_OAUTH_PROXY_GUIDE.md) |
| **A2A** | Agenttien välinen viestintä (muiden uag esiintymien tai A2A-yhteensopivien palvelimien kanssa) |
| **Järjestelmä** | env vars, järjestelmän tiedot, aika, päivämäärälaskenta, [määrät](docs/QUANTITIES.md), [geodesic_distance](docs/GEODESIC_DISTANCE.md), uuid_gen, slugify |
| **Lähde Nav** | **29 idx-työkalua** Python-, PHP-, TypeScript-, Java-, C#-, Dart-, C/C++-, Rust-, Go-, Swift-, Kotlin-, COBOL-, VBA-, LotusScript-, Makefile-työkaluille – hanki funktio-/luokkaindeksi tai tietty määritelmä lukematta koko tiedostoa |

##⎎⎎
##⎎⎞ coverage`statusory: raportoi aktiivisen työtilan Git-haara, muutokset, ylävirran synkronointitila, Python-ajoaika ja yleiset projektimerkit muokkaamatta tiedostoja.
- `git_review`: tee yhteenveto Git-muutoksista, riskialttiista tiedostoista, testiehdokkaista ja salaisista löydöistä paljastamatta salaisia arvoja.
- `security_scan`: todennäköisten määritystiedostojen ja riskien salausvaraston tiedostot. `coverage_report`: suorita ja normalisoi kattavuus kohteille Python, TypeScript/JavaScript, Rust, Go, Java/Kotlin, .NET, C/C++, Ruby, PHP, Swift ja Dart/Flutter.
- Puuttuvat kattavuusriippuvuudet voidaan pyytää automaattisesti, kun suoritus suoritetaan; `dry_run` ei koskaan asenna paketteja.

Katso [Arkistoanalyysityökalut](docs/REPOSITORY_TOOLS.md) parametrien, tulosteiden ja turvallisuustietojen saamiseksi.

Katso [Polku- ja URL-aliakset] (docs/PATH_URL_ALIASES.md) saadaksesi lisätietoja tiedoston #-polun lyhentämisestä. 🖥 4 käyttöliittymää + VS-koodin laajennus

| Tila | Komento | Tarkoitus |
|---|---|---|
| **CLI** | `uag` | Nopea terminaalipohjainen toiminta |
| **GUI** | "uagg" | Työpöytäkäyttöliittymä tkinterin kautta |
| **Web** | "uagw" | Selainpohjainen pääsy |
| **A2A Palvelin** | "uaga" | Agent2Agent-protokolla usean agentin tietoliikenteeseen |
| **VS-koodi** | — | [Laajennus](https://github.com/awaku7/agentcli/blob/main/docs/VSCODE.md) chat-paneelilla, selityksellä, uudelleentekijällä, korjausvirheellä ja työkalujen puunäkymällä |

Katso [VSCODE.md](https://github.com/awaku7/bCOmain/agentc.doc.md. VS-koodin laajennus — asennus, komennot, näppäinyhdistelmät ja konfigurointi.

### 🏠 IoT-laitteiden ohjaus

- **BACnet**: Lue/kirjoita BACnet/IP-laitteita (LVI, valaistus, tehomittarit). COV-tilaus push-ilmoituksia varten
- **Modbus TCP**: Lukea/kirjoita pito-/syöttörekisterit ja kelat. Pollauspohjainen muutosten seuranta
- **OPC UA**: Selaa osoiteavaruutta, lue/kirjoita muuttujia, tilaa tietojen muutokset
- **SwitchBot**: Cloud eräohjaus ja BLE-skannaus/hallinta. Äänestyspohjainen tilaus
- **ECHONET Lite**: Löydä, hallitse ja tilaa kodinkoneista (AC, valot, vedenlämmittimet jne.) tulevat INF-ilmoitukset
- **Matter**: Luku-/kirjoitusohjaus + attribuuttien tilaus tilanmuutosten seurantaa varten
- **UPnP**: Laitteen etsintä ja IGD-portin edelleenlähetys
 [IOT_USECASE.md](https://github.com/awaku7/agentcli/blob/main/docs/IOT_USECASE.md)

### 🎯 Agent Skills Marketplace

`:skills mp_search` selataksesi [SkillsMP](https://skills.mp) [ClawHub](https://clawhub.ai) yhteisön taitoja varten.
Asenna ja laajenna uag:n ominaisuuksia lennossa.

### 🤖 Auto-Pilot (`:auto`)

uag voi **tavoitella itsenäisesti tavoitetta usealla kierroksella__PH_ 6 kierroksella.** Täydellinen monimutkaisiin, monivaiheisiin tehtäviin, jotka vaativat iteratiivista tarkennusta.

- **Kuinka se toimii**: Jokaisella kierroksella on pääkysely (vaihe A), jota seuraa arvioijan arvio (vaihe B), joka päättää "VALMISTEE vai JATKA?"
- **Sama toimittaja, sama API-koodin käyttöpolku: pääkyselyn polku mukaan lukien Vastaukset API-tuki.
- **Erillinen tuomari LLM** (valinnainen): Aseta `UAGENT_AP_PROVIDER` käyttämään eri toimittajaa/mallia arvioijalle (käytä esim. halvempaa mallia arvioinnissa).
- **Poistu milloin tahansa**: Paina `x.-näppäintä. Vastaa välittömästi, ponse. Tai anna arvioijan päättää, milloin tavoite saavutetaan.
- **Määritettävissä**: `--max-rounds N' budjetin hallintaan.

Katso täydellinen dokumentaatio osoitteesta [README_AUTO.md](https://github.com/awaku7/agentcli/blob/main/docs/README_AUTO.md)👍⧎#ch. Manager

uag voi seurata edistymistä pitkäkestoisissa monitiedostotehtävissä. Kun LLM käsittelee kymmeniä tiedostoja, "batch_state" säilyttää odottavien, valmiiden ja epäonnistuneiden tiedostojen luettelon levylle. Jos istunto päättyy tai kierros aikakatkaistaan, seuraava ajo jatkuu kohdasta, jossa se pysähtyi – mitään ei häviä.

### 🛡 Human-in-the-Loop

`human_ask` antaa LLM:n pysähtyä ja pyytää vahvistusta ennen tuhoavien toimintojen suorittamista (tiedoston poisto, ylikirjoituskomento). Pysyt hallinnassasi.

### 🛑 Keskeytä (c-näppäin / Stop-painike)

Lopeta LLM-vastauksen luominen milloin tahansa ja anna pysäytyskomento takaisin LLM:een.

| Käyttöliittymä | Kuinka keskeyttää |
|---|---|
| **CLI** | Paina c-näppäintä LLM-suoratoiston aikana – nykyinen vastaus pysähtyy ja "Stop"' lähetetään käyttäjäviestinä, joten LLM vastaa vastaavasti |
| **VERKKO-UI** | Napsauta punaista **■ Stop** -painiketta (näkyy automaattisesti LLM käsittelyn aikana) |
| **Työpöytä GUI** | Napsauta punaista **■**-painiketta (näkyy automaattisesti LLM-käsittelyn aikana) |

Keskeytys toimii "kehotuksena": sen sijaan, että se vain keskeyttäisi, se syöttää "Stop"' takaisin LLM:een käyttäjäviestinä, jolloin se voi päättää tai kuitata keskeytyksen automaattisesti. [README_AUTO.md](https://github.com/awaku7/agentcli/blob/main/docs/README_AUTO.md)).

### 🕵️ Selainautomaatio ja Web Inspector

** Pelaa kahta toisiaan täydentävää Playwright-rivipohjaista työkalua: todelliset selainistunnot – navigoi, napsauta, täytä lomakkeita, poimi tietoja, käsittele monisivuisia virtoja. Toimii päättömästi tai päättömästi.
- **playwright_inspector**: Tallenna selaimen siirtymät, ota DOM-tilanteet ja kuvakaappaukset jokaisessa vaiheessa. Hyödyllinen verkkovuorovaikutusten virheenkorjauksessa tai sivumuutosten tarkastamisessa ajan mittaan.

### 🔄 Dynaamisen työkalun latauksen

`tool_catalog` ja `tool_load' avulla voit löytää ja ottaa työkalut käyttöön suorituksen aikana.
Kaikkea ei tarvitse ladata käynnistyksen yhteydessä – aktivoi vain tarvitsemasi, kun tarvitset sitä.
## Rusative. Työkalut

`uuid_gen` ja `slugify` on toteutettu Rustissa (PyO3:n kautta) suorituskyvyn takaamiseksi.
Ne latautuvat suoraan valmiiksi rakennetusta .pyd-tiedostosta — **pip-asennusta ei vaadita**.

Ulkoiset kehittäjät voivat toimittaa myös Rust-pohjaisia työkaluja: käytä seuraavaksi.pydpy. `load_rust_pyd()` tiedostosta `uagent.tools.rust_helper`, ja
käyttäjät saavat työkalun ilman ylimääräisiä riippuvuuksia. Katso
[TOOL_CREATOR_GUIDE.md](https://github.com/awaku7/agentcli/blob/main/TOOL_CREATOR_GUIDE.md).

### 🌐 i18n / L10n

日本語 / / / /縁本語 / English /繁體中文 / 한국어 / Español / Français / Русский / ja paljon muuta.
Aseta "UAGENT_LANG" vaihtaaksesi. Katso [ADD_LOCALE.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/ADD_LOCALE.md) lisätäksesi uuden kielen.

Tämän README käännökset ovat saatavilla kielellä [docs/README.translations.md](https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md).

### 🔒 Encrypted Environment Variables

Tallenna API-salatut avaimet ja salatut avaimet. `.env`-tiedosto.
Hallinnoi komennolla `uag_envsec.

## Kokoonpano ja tiedot

- **Ympäristömuuttujat**: [docs/ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/docs/ENVIRONMENT.md)
- **Ohjattu asennustoiminto**: `python -m 
 __PHcli`ed** env**: `uag_envsec` — salaa `.env` muodossa `.env.sec`
- **Vastaukset API**: Aseta `UAGENT_RESPONSES=1` Responses API -tilalle (OpenAI/__/PH_LMRobaAlbauter Studio/Sakana AI). Automaattisesti käytössä Sakana AI:lle (Fugu).
- **Kehittäjädokumentit**: [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)
- **Työkalukulku**: [TOOL_FLOW.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/TOOL_FLOW.md) – kuinka työkalut lähetetään LLM:ille (genremaski, työkaluluettelo, GPT-5.4+ natiivi tool_search)
-**:Smalls__**:Sma [SLM_TIPS.md](https://github.com/awaku7/agentcli/blob/main/docs/SLM_TIPS.md)

## Project Philosophy

uag pyrkii olemaan **tekoälysi, koneellasi, sinun ehdoillasi.**

- Ei SaaS-riippuvuutta – toimii paikallisesti
- Ei palveluntarjoajan lukitusta – vaihda milloin tahansa
- Ei käyttöliittymän lukitusta – CLI / _GUI / _GUI / _GUI lock-in – laajenna työkaluilla ja taidoilla

Ilmainen tekoälyagenttikokemus ilman toimittajan lukitusta.

### ✨ Luo omat työkalusi

Uuden työkalun kirjoittaminen kohteelle uag on yksinkertaista – luo yksi `.py`-tiedosto komennoilla
`TOOL_tool ja(`run_SPEC) "UAGENT_EXTERNAL_TOOLS_DIR", ja
se on heti saatavilla. Rust-kehittäjille toimitetaan valmiiksi rakennettu `.pyd`, jossa
 ei ole ylimääräisiä riippuvuuksia käyttäjille.

Katso [TOOL_CREATOR_GUIDE.md](https://github.com/awaku7/agentcli/blob/main/TOOL_CREATOR_GUIDE.md)



-vaiheopas.## Osallistuminen

Avustukset ovat tervetulleita! Virheraportit, ominaisuusehdotukset, dokumentaation parannukset, käännökset ja vetopyynnöt – kaikki arvostetaan.

- **Ongelmia**: Avaa GitHub-ongelma virheiden tai ominaisuuspyyntöjen varalta.
- **Pullauspyynnöt**: Fork repo, tee muutokset ja lähetä PR. Katso [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md) kehitysasetuksista ja ohjeista.
- **Käännökset**: README-käännökset ja kieli- ja aluelisäykset ovat tervetulleita. Katso [ADD_LOCALE.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/ADD_LOCALE.md).
- **Tools & Skills**: Uusia työkalulaajennuksia ja agenttitaitoja voidaan tarjota Marketplacen kautta (##for#e checks.
⏏ PR)

Asenna ensin vain testiriippuvuudet. Ne pidetään poissa ajonaikaisten
riippuvuusluettelosta:

```bash
python -m pip install -e ".[test]"
python -m pip install black ruff
````

Suorita samat tarkistukset, joita GitHub käyttävät. Toiminnot ennen kuin painat:⎎rc\`\`\`
check testit
python -m black --check src tests
python scripts/tool_json_i18n_batch.py status
python -m pytest -q .

````

Jos haluat nopeamman paikallisen iteroinnin, suorita vain asiaankuuluvat testit:


```ba -q testit/<affected_area>
````

Lisätarkistukset tarvittaessa:

```bash
python -m py_compile src/uagent/
mypy src/uagent
```

muokkaus:Poter`thon. scripts/compile_locales.py` ja `python scripts/po_qc_summary.py`.

Runtime-käytäntö (yksityiskohdat: [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP) §6:n sijaan. `sys.exit`; työkaluisäntä muuttaa työkalun "SystemExit"/"Exception" virhemerkkijonoiksi, jotta yksittäinen työkalu ei voi lopettaa prosessia. Käynnistyksen nopeat poistumiset ovat tahallisia.

## Arkkitehtuuri ja toiminnalliset invariantit

Katso [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) kestävistä sopimuksista, jotka kattavat A2A elinkaaren, I18N-kontekstit, valinnaisen riippuvuusasennuksen, työkalun turvallisuuden, palveluntarjoajan ominaisuudet, OAuth-rakenteen⎏-varmennusrajoitukset ja⎏-tapahtumat.## Enterprise Policy Engine

Organisaatiotason käytäntöjä työkaluille, palveluntarjoajille, tunnistetiedoille, MCP palvelimille, verkoille, taidoille ja laajennuksille tuetaan. Aseta "UAGENT_POLICY_FILE" käytäntötiedostoksi JSON/YAML; Katso [docs/ENTERPRISE_POLICY.md](docs/ENTERPRISE_POLICY.md) määritysesimerkkejä, rooleja, vahvistuksia ja sallittuja luetteloita varten.

### Runtime palautus ja organisointi

Katso [RESTART_RECOVERY.md](docs/REY.mRE_d)COVERY.mRE_d) [DAG_SCHEDULER.md](docs/DAG_SCHEDULER.md) / [MULTI_AGENT_RUNTIME.md](docs/MULTI_AGENT_RUNTIME.md) kestävään palautukseen, riippuvuustietoiseen suoritukseen, usean agentin orkestrointiin ja A2A-etäkäyttöön. [DISTRIBUTED_COORDINATION.md](docs/DISTRIBUTED_COORDINATION.md) jaetun ajonaikaisen johtajan vuokrasopimuksen koordinointiin.

## Installation and optional dependencies

The base installation keeps provider and tool integrations optional. Missing
packages are installed automatically when a selected provider or tool needs
one. To install the main feature groups in advance:

```bash
pip install "uag[core,providers,tools,development,platform,web]"
```

For a repository checkout with the full development and test environment:

```bash
pip install -r requirements.txt
```
