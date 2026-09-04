# KÄYTTÖ (Komentorivivaihtoehdot)

Tässä asiakirjassa kuvataan uag-sisäänkäyntipisteille käytettävissä olevat komentorivivaihtoehdot.

______________________________________________________________________

## Käynnistyskohdat

| Komento | Python-moduuli | Rajapinta |
|---|---|---|
| `uag` | `python -m uagent` | CLI (stdin-silmukka) |
| `uagg` | `python -m uagent.gui` | GUI (tkinter) |
| `uagw` | `python -m uagent.web` | Verkkopalvelin (FastAPI) |
| `uaga` | `python -m uagent.a2a.server` | A2A HTTP-palvelin |

______________________________________________________________________

## CLI-käynnistysvaihtoehdot (`uag`)

### `--workdir` / `-C <polku>`

Työkansio. Jos sitä ei ole määritetty, käytetään oletuksena ympäristömuuttujaa `UAGENT_WORKDIR` ja sen jälkeen nykyistä hakemistoa.
Hakemisto luodaan, jos sitä ei ole olemassa.

### `--tool-genre-mask <int>`

Työkalutyyppien bittimaski. Kun tämä annetaan, interaktiivinen tyyppivalintakysely ohitetaan.

| Bitti | Tyyppi | Kuvaus |
|-----|-------|-------------|
| 1 | basic | Tärkeimmät tiedosto- ja chat-työkalut |
| 2 | comm | Viestintätyökalut (Bluesky, Teams) |
| 4 | office | Toimistopaketin työkalut (Excel, PDF, PPTX) |
| 8 | devel | Kehitystyökalut (git, lint, compile) |
| 16 | iot | IoT-laitetuotteet (SwitchBot, ECHONET, Matter, UPnP) |
| 32 | exec | Komentojen suoritustyökalut |
| 64 | external | Ulkoiset laajennustyökalut |
| 128 | media | Kuva- ja äänituotanto sekä -analyysi |
| 256 | file | Tiedostojenhallintatyökalut |
| 512 | index | Lähde- ja hakemistojen selaustyökalut |
| 1024 | dev | Kehittäjä- ja arkistotyökalut |
| 2048 | web | Verkkotyökalut ja selaintyökalut |
| 4096 | utility | Apu- ja tukityökalut |
| 8191 | all | Kaikki työkalut |

Esimerkkejä:

```
uag --tool-genre-mask 1 # vain perus
uag --tool-genre-mask 9 # perus + kehitys (1 + 8)
uag --tool-genre-mask 8191    # kaikki työkalut
```

### `--use-tool` / `--no-use-tool`

Ota käyttöön tai poista käytöstä työkalumääritelmien lähettäminen LLM:ään. Ohittaa `UAGENT_USE_TOOL`-ympäristömuuttujan.

- `--use-tool` pakottaa työkalujen lähettämisen päälle.
- `--no-use-tool` pakottaa työkalujen lähettämisen pois päältä.

Kun tämä on pois käytöstä, LLM ei vastaanota työkalumääritelmiä eikä voi kutsua mitään työkalua.

### `--computer-use` / `--no-computer-use`

Ota tietokoneen käyttö käyttöön tai poista se käytöstä. Ohittaa `UAGENT_COMPUTER_USE`-ympäristömuuttujan.

### `--inject-message` / `-M <message>`

Lisää viestin LLM:ään käynnistyksen yhteydessä ja lopettaa ohjelman suorituksen päätyttyä. Tämä edellyttää `--non-interactive`-parametria.

### `--embedded`

Upotettu tila rajoitetuille tai toistettavuudelle herkille käyttöönotoille.

- Poistaa istuntotallennustilan käytöstä.
- Piilottaa työkalujen hallintatyökalut (`tool_catalog`, `tool_load`, `unload_tool`), ellei niitä ole nimenomaisesti otettu käyttöön.
- Ohittaa `--tool-genre-mask`-vaihtoehdon; käytä `--enable-tool`-vaihtoehtoa työkalun nimenomaiseen lataamiseen.

### `--enable-tool <nimi>`

Lataa työkalu nimenomaisesti käynnistyksen yhteydessä. Vaihtoehtoa voidaan toistaa, ja myös pilkuilla erotetut nimet hyväksytään.

```
uag --embedded --enable-tool handle_mcp_v2 --enable-tool human_ask
uag --embedded --enable-tool handle_mcp_v2,human_ask
```

Määritetty järjestys säilyy ja näkyy LLM:lle esitettävässä työkalujen järjestyksessä. Nimenomaisesti käytöön otetut työkalut on suojattu automaattiselta poistamiselta.

### `--plugin-dir <polku>`

Lataa laajennukset määritetystä hakemistosta. Vaihtoehtoa voidaan toistaa.

______________________________________________________________________

## Vain komentorivillä käytettävät vaihtoehdot

### `--inject-message-auto <goal-options>`

Käynnistä automaattiohjaus ei-vuorovaikutteisesta, syötetystä tavoitteesta. Arvo käyttää samoja vaihtoehtoja kuin `:auto`; laita koko arvo lainausmerkkien sisään, jos se sisältää vaihtoehtoja.

```
uag --embedded --enable-tool handle_mcp_v2 --inject-message-auto "Lajittele kohteet --max-rounds 10"
uag --embedded --enable-tool handle_mcp_v2 --inject-message-auto "Lajittele kohteet --infinite"
```

Normaalitilassa käytetään arvioijan harkintapolkua. Aseta `UAGENT_AUTO_SENTINEL=1`, jos haluat käyttää yksittäisen LLM-vartijamoodia. Tässä tilassa kohteen LLM on lopetettava jokainen vastaus täsmälleen yhdellä seuraavista:

- `<AUTO_CONTINUE>` — suorita uusi kierros
- `<AUTO_COMPLETE>` — lopeta onnistuneesti

Puuttuvat tai virheelliset merkit pysäyttävät automaattiohjauksen turvallisesti. Tämä suorittaa edelleen kohde-LLM:n; se vain välttää ylimääräisen tarkistaja-LLM-kutsun.

### `--non-interactive`

Ei-interaktiivinen tila. Ei käynnistä stdin-silmukkaa. Jos tiedostopolku annetaan positiivisena argumenttina, se käsitellään ja ohjelma lopetetaan välittömästi.

```
uag --non-interactive README.md
uag --non-interactive --workdir /tmp/project
```

______________________________________________________________________

## Verkkopalvelimen asetukset (`uagw`)

### `--host <address>`

Verkkopalvelimen sidontaosoite (oletus: `127.0.0.1`, voidaan ohittaa `UAGENT_WEB_HOST`-muuttujalla).

Oletusarvoisesti verkkopalvelin kuuntelee vain localhostia (`127.0.0.1`). Jotta se olisi käytettävissä myös verkon muilta koneilta, käytä `--host 0.0.0.0`.

```
uagw --host 0.0.0.0
uagw --host 192.168.1.10
```

### `--tool-genre-mask <int>`

Valitse työkalutyypit käyttämällä samaa edellä kuvattua bittimaskia. Kun tämä määritetään, interaktiivinen tyyppikysely ohitetaan.

### `--use-tool` / `--no-use-tool`

Ota käyttöön tai poista käytöstä työkalumääritelmien lähettäminen LLM:ään. Ohittaa `UAGENT_USE_TOOL`-asetuksen.

### `--computer-use` / `--no-computer-use`

Ota käyttöön tai poista käytöstä tietokoneen käyttö. Ohittaa `UAGENT_COMPUTER_USE`-asetuksen.

### `--no-frontend`

Suorittaa pelkän API:n ilman HTML-malleja tai staattisia käyttöliittymätiedostoja.

### `--embedded`

Poistaa istuntotallennustilan käytöstä ja piilottaa työkalujen hallintatyökalut (`tool_catalog`, `tool_load`, `unload_tool`).

______________________________________________________________________

## A2A-palvelimen asetukset (`uaga`)

### `--host <address>`

A2A- ja HTTP-palvelimen sidontaosoite (oletus: `0.0.0.0`, ohitettavissa `UAGENT_A2A_HOST`-muuttujalla).

### `--port <numero>`

A2A- ja HTTP-palvelimen porttinumero (oletus: `8765`, voidaan ohittaa `UAGENT_A2A_PORT`-muuttujalla).

### `--reload`

Ota käyttöön koodin muutosten yhteydessä tapahtuva automaattinen uudelleenlataaminen (oletus: pois päältä, voidaan ohittaa `UAGENT_A2A_RELOAD`-muuttujalla).

```
uaga --host 127.0.0.1 --port 8080 --reload
```

### `--tool-genre-mask <int>`

Valitse työkalutyypit yllä kuvatun bittimaskin avulla. Kun tämä on määritetty, interaktiivinen tyyppikysely ohitetaan.

### `--use-tool` / `--no-use-tool`

Ota käyttöön tai poista käytöstä työkalumääritelmien lähettäminen LLM:ään. Ohittaa `UAGENT_USE_TOOL`-asetuksen.

### `--computer-use` / `--no-computer-use`

Ota tietokoneen käyttö käyttöön tai poista se käytöstä. Ohittaa `UAGENT_COMPUTER_USE`-asetuksen.

### `--embedded`

Poistaa istuntotallennuksen käytöstä ja piilottaa työkalujen hallintatyökalut (`tool_catalog`, `tool_load`, `unload_tool`).

______________________________________________________________________

## Liittyvät ympäristömuuttujat

| Muuttuja | Kuvaus |
|---|---|
| `UAGENT_PROVIDER` | LLM-palveluntarjoajan nimi (vaaditaan käynnistyksessä) |
| `UAGENT_*_API_KEY` | Valitun palveluntarjoajan API-avain |
| `UAGENT_WORKDIR` | Oletustyökansio |
| `UAGENT_WEB_HOST` | Verkkopalvelimen sitoutumisosoite (oletus: `127.0.0.1`) |
| `UAGENT_A2A_HOST` | A2A-palvelimen sitoutumisosoite (oletus: `0.0.0.0`) |
| `UAGENT_A2A_PORT` | A2A-palvelimen portti (oletus: `8765`) |
| `UAGENT_A2A_RELOAD` | Ota A2A-kuumakäynnistys käyttöön oletuksena |
| `UAGENT_USE_TOOL` | Poista työkalut käytöstä, kun asetukseksi valitaan `0`, `false`, `no` tai `off` |
| `UAGENT_COMPUTER_USE` | Ota tietokoneen käyttö oletusarvoisesti käyttöön tai poista se käytöstä |
| `UAGENT_SESSION_STORE` | Ota istuntotallennus käyttöön tai poista se käytöstä; Sulautettu tila pakottaa arvon `0` |
| `UAGENT_PLUGIN_DIRS` | Lisähakemistot laajennusten etsimistä varten |
| `UAGENT_AUTO_SENTINEL` | Ota käyttöön yksittäinen LLM-autopilotti-sentinel-tila, kun asetuksena on `1` |
| `UAGENT_CONSECUTIVE_TOOL_CALL_LIMIT` | Peräkkäisten uusien työkalukutsujen enimmäismäärä (oletus: `100`) |
| `UAGENT_MAX_TOOL_ROUNDS` | Enimmäismäärä LLM/työkierrosta käyttäjätoimintoa kohti (oletus: `200`) |
| `UAGENT_SHRINK_CNT` | Valinnainen viestien automaattisen pienentämisen kynnysarvo (`0`/asetusta ei määritetty = pois käytöstä) |
| `UAGENT_SHRINK_KEEP_LAST` | Tiivistämisen jälkeen säilytettävät viestit (oletus: `20`) |
| `UAGENT_LANG` | Käyttöliittymän kieli (`ja`, `en` jne.) |

Katso täydellinen luettelo ympäristömuuttujista kohdasta [ENVIRONMENT.md](ENVIRONMENT.md).

______________________________________________________________________

## Esimerkkejä

### Minimiasetukset käynnistettäessä OpenAI

```
set UAGENT_PROVIDER=openai
set UAGENT_OPENAI_API_KEY=sk-...
uag
```

### Paikallinen Ollama vain perustyökaluilla

```
set UAGENT_PROVIDER=ollama
set UAGENT_OLLAMA_MODEL=qwen2.5:7b
uag --tool-genre-mask 1
```

### Verkkopalvelin kaikilla rajapinnoilla

```
set UAGENT_WEB_HOST=0.0.0.0
uagw
```

tai

```
uagw --host 0.0.0.0
```

### A2A-palvelin localhostissa mukautetulla portilla

```
uaga --host 127.0.0.1 --port 8080
```

### Työkalujen poistaminen käytöstä pienessä mallissa

```
uag --no-use-tool --tool-genre-mask 1
```

### Ei-interaktiivinen tiedostojen käsittely

```
uag --non-interactive README.md
```
