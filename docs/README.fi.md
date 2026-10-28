<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="UAG — Universal AI Gateway" width="620">
</p>
<h1 align="center">UAG</h1>
<p align="center"><strong>Universal AI Gateway</strong><br>Omat tekoälymallisi. Omat työkalusi. Oma ympäristösi.</p>

<p align="center">
  <a href="https://github.com/awaku7/agentcli/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/awaku7/agentcli/ci.yml?style=flat-square&label=CI" alt="CI"></a>
  <a href="https://pypi.org/project/uag/"><img src="https://img.shields.io/pypi/v/uag?style=flat-square" alt="PyPI"></a>
  <a href="https://pypi.org/project/uag/"><img src="https://img.shields.io/pypi/pyversions/uag?style=flat-square" alt="Python versions"></a>
  <a href="../LICENSE"><img src="https://img.shields.io/github/license/awaku7/agentcli?style=flat-square" alt="License"></a>
  <a href="https://pepy.tech/projects/uag"><img src="https://static.pepy.tech/personalized-badge/uag?period=total&units=INTERNATIONAL_SYSTEM&left_color=grey&right_color=green&left_text=downloads" alt="Downloads"></a>
</p>
<p align="center"><a href="../README.md">English</a> · <a href="README.translations.md">Muut kielet</a></p>

---

**UAG on avoimen lähdekoodin tekoälyagenttien suoritusympäristö, jossa paikallinen käyttö on etusijalla.** Se yhdistää valitsemasi kielimallin käyttämiisi työkaluihin ja järjestelmiin. Koodia, tiedostoja, selaimia, palveluja ja laitteita voi käsitellä samalla käyttöliittymällä ilman riippuvuutta yhdestä mallitoimittajasta.

| **Valitse malli** | **Yhdistä työkalut** | **Pidä hallinta itselläsi** |
| :--- | :--- | :--- |
| Pilvi- ja paikallismallit, kuten OpenAI, Claude, Gemini, Grok, Bedrock ja Ollama | Tiedostot, koodi, verkko, MCP, Agent Skills, lisäosat, pilvipalvelut ja IoT | Paikallinen suoritus, käyttäjän vahvistus, tunnusten tallennus ja määritettävät käytännöt |

> UAG on **agenttien suorituskerros, ei mallipalveluntarjoaja**. Ulkoisten mallien ja palvelujen kutsut riippuvat asetuksista. Paikallisuus ei tarkoita täysin verkotonta toimintaa eikä kaikkien työkalujen automaattista eristämistä.

## Pika-aloitus
<!-- README-SYNC:quick-start -->

Vaaditaan **Python 3.11 tai uudempi**. Asenna UAG [PyPI:stä](https://pypi.org/project/uag/) ja käynnistä vuorovaikutteinen komentorivi:

~~~bash
python -m pip install --upgrade uag
uag
~~~

Ensimmäisellä käynnistyskerralla ohjattu asennus auttaa valitsemaan mallitoimittajan ja määrittämään tunnukset. Myös ympäristömuuttujat ja tunnusvarasto käyvät. Laajemmat toimittaja- ja työkaluriippuvuudet voi asentaa etukäteen komennolla:

~~~bash
python -m pip install "uag[core,providers,tools]"
~~~

Kokeile seuraavia pyyntöjä:

~~~text
> Mitä tässä Git-repositoriossa on muuttunut? Tiivistä riskit.
> Etsi kirjaston uusin dokumentaatio ja selitä siirtymävaiheet.
> Tutki nämä tiedostot ja tee tiivis raportti.
> :help
~~~

Uusille käyttäjille suosittelemme Windows-asennusohjetta, jossa käsitellään Git ja virtuaaliympäristöt, sekä asetusopasta: [Quickstart (Windows)](QUICKSTART.md) · [Environment](ENVIRONMENT.md).

## Käyttöliittymät
<!-- README-SYNC:interfaces -->

Kaikki käyttöliittymät käyttävät samaa agenttisuoritusympäristöä ja työkalurekisteriä.

| Käyttöliittymä | Käynnistys | Soveltuu |
| :--- | :--- | :--- |
| **CLI** | `uag` | Pääte ja automaatio |
| **Desktop** | `uagg` | Natiivit työpöytäkeskustelut |
| **Web** | `uagw` | Selainkeskustelut ja huoneet |
| **A2A** | `uaga` | Agenttien välinen integraatio |
| **VS Code** | [Laajennusopas](VSCODE.md) | Työskentely koodin rinnalla |

Työpöytä- ja verkkokäyttöliittymät tarvitsevat lisäriippuvuuksia, joita `uag[core,providers,tools]`-perusasennus ei sisällä:

~~~bash
# Desktop GUI (PySide6 and platform integrations)
python -m pip install "uag[platform]"

# Web UI (authentication dependencies, FastAPI, and Uvicorn)
python -m pip install "uag[web]" fastapi uvicorn
~~~

Verkkopalvelin voi yrittää asentaa FastAPI:n ja Uvicornin käynnistyessään. Asentaminen etukäteen poistaa riippuvuuden automaattisesta asennuksesta. Lisätiedot: [CLI usage](USAGE.md) · [Environment](ENVIRONMENT.md).

## Mitä UAG:lla voi tehdä
<!-- README-SYNC:capabilities -->

| Ominaisuus | UAG tarjoaa |
| :--- | :--- |
| **Malliriippumattomat työnkulut** | Vaihda paikallista tai pilvitoimittajaa `UAGENT_PROVIDER`-asetuksella kirjoittamatta työkaluja uudelleen |
| **Koodi ja tiedostot** | Repositorion selaus, Git-tarkastus, linttaus, testit, tiedostotoiminnot ja selainautomaatio |
| **Laajennettavat työkalut** | Yli 200 työkalua, dynaaminen haku `tool_catalog` / `tool_load`, omat Python- ja Rust-työkalut |
| **Yhdistetyt agentit** | MCP, A2A, Claude Code -yhteensopivat lisäosat, Agent Skills ja aliagentit |
| **Pitkäkestoiset tehtävät** | Autopilotti, rinnakkaiset erilliset lukuoperaatiot, ajastukset, palautuminen ja pysyvät istunnot |
| **Päätettä laajempi käyttö** | Pilvi, viestintä, dokumentit, media, reaaliaikainen puhe ja tuetut IoT-protokollat |

### Yksi suoritusympäristö, monta integraatiota
<!-- README-SYNC:integrations -->

~~~mermaid
flowchart LR
    UI["CLI · Desktop · Web · VS Code · A2A"] --> UAG["UAG agent runtime"]
    UAG --> MODELS["Hosted & local models"]
    UAG --> TOOLS["Tools & extensions"]
    UAG --> STATE["Sessions & context"]
    TOOLS --> SYSTEMS["Files · Code · Web · MCP · Cloud · IoT"]
    POLICY["Confirmation · Credentials · Policy"] -.-> UAG
~~~

**Esimerkkejä tuetuista mallitoimittajista** on alla. Toimittajakohtaiset asetukset löytyvät ympäristöoppaasta.

**OpenAI · Anthropic · Gemini · Vertex AI · Azure OpenAI · Amazon Bedrock · Grok · DeepSeek · OpenRouter · Ollama · llama.cpp · LM Studio**

[ENVIRONMENT.md](ENVIRONMENT.md)

### Mukauttaminen taidoilla ja lisäosilla
<!-- README-SYNC:extensions -->

Laajenna UAG:ta muuttamatta sen ydintä. Asenna Agent Skills -taitoja SkillsMP:stä tai ClawHubista, liitä MCP-palvelimia tai lataa Claude Code -yhteensopivia lisäosia, joissa on työkaluja, taitoja, agentteja ja koukkuja.

~~~text
:skills mp_search browser automation
:plugin list
:plugin install <source>
:plugin marketplace list
~~~

Omat työkalut voivat tarjota `TOOL_SPEC`- ja `run_tool()`-rajapinnat; myös Rust-pohjaisia työkaluja tuetaan. Oppaat: [Tool Creator Guide](../TOOL_CREATOR_GUIDE.md) · [Plugin Development Guide](../src/uagent/docs/DEVELOP_PLUGIN.md) · [MCP OAuth / Proxy](MCP_OAUTH_PROXY_GUIDE.md).

## Todellisiin työnkulkuihin
<!-- README-SYNC:workflows -->

### Konteksti ja muisti
<!-- README-SYNC:context-memory -->

Laajat työkalutulokset voidaan tallentaa **artefakteina**, jotta ne eivät täytä mallin aktiivista kontekstia. Agentti voi hakea tarvittavan osan myöhemmin `artifact_read`-toiminnolla. Istunnot tallennetaan oletuksena SQLiteen; mukana ovat historiakyselyt ja muistimerkintöjen nimenomainen tarkastelu.

- [Context compression](CONTEXT_COMPRESSION.fi.md)
- [Memory](MEMORY.md)
- [Session portability](SESSION_PORTABILITY.md)

### Automaatio ja yhteistyö
<!-- README-SYNC:automation -->

UAG tukee rinnakkaisia erillisiä lukuoperaatioita, usean agentin koordinointia, istuntojen palauttamista ja monivaiheista autopilottia. Käynnistä se `:auto`-komennolla; **F12** keskeyttää vastauksen ja pyytää autopilotin pysäyttämistä.

- [Auto-pilot](README_AUTO.md)
- [Timers and scheduled tasks](SET_TIMER.md)
- [Multi-agent runtime](MULTI_AGENT_RUNTIME.md)

### Tietoturva ja havaittavuus
<!-- README-SYNC:security -->

Arkaluonteiset toimet voidaan asettaa vaatimaan `human_ask`-vahvistus. Tunnukset voi säilyttää käyttöjärjestelmän tunnusvarastossa tai salatussa tiedostossa. Web-käyttöliittymä tukee määritettyä OIDC-kirjautumista ja käyttöoikeuksien hallintaa. OpenTelemetry-jäljitys ja mittarit ovat **valinnaisia**.

- [Enterprise policies](ENTERPRISE_POLICY.md)
- [MXC sandbox](SANDBOX_MXC.md)
- [Remote Web / A2A MXC defaults](REMOTE_MXC_DEFAULT.md)
- [Web identity and rooms](WEB_IDENTITY_MEMORY.md)
- [OpenTelemetry design](UAG_OPENTELEMETRY_DESIGN.md)
- [Developer observability](../src/uagent/docs/DEVELOP_OBSERVABILITY.md)

Suojaukset ovat määritettäviä eivätkä **takaa**, että mikä tahansa työkalu suoritetaan eristetyssä hiekkalaatikossa. Tutustu käyttöönotto- ja käytäntöoppaisiin ennen UAG:n avaamista epäluotetuille käyttäjille tai verkoille.

### Kielet, laitteet ja puhe
<!-- README-SYNC:languages -->

UAG sisältää resurssit **38 kielialueelle** (englanti ja 37 käännöstä), valinnaisia kaksisuuntaisia puheintegraatioita sekä työkalut SwitchBotille, Matterille, ECHONET Litelle, BACnetille, Modbus TCP:lle ja OPC UA:lle.

- [Translations](README.translations.md)
- [IoT use cases](IOT_USECASE.md)
- [Communication tools](COMMUNICATION.md)

## Dokumentaatio
<!-- README-SYNC:documentation -->

Aloita näistä oppaista ja syvenny yksityiskohtiin tarvittaessa:

| Aloita tästä | Lisätiedot |
| :--- | :--- |
| [Quickstart (Windows)](QUICKSTART.md) | [Architecture](ARCHITECTURE.md) |
| [CLI usage](USAGE.md) | [Context management](UAG_CONTEXT_MANAGEMENT_DESIGN.md) |
| [Environment and providers](ENVIRONMENT.md) | [Enterprise policy](ENTERPRISE_POLICY.md) |
| [Agent Skills and plugins](../src/uagent/docs/DEVELOP_PLUGIN.md) | [Tool flow](../src/uagent/docs/TOOL_FLOW.md) |
| [MCP and OAuth](MCP_OAUTH_PROXY_GUIDE.md) | [Computer Use](COMPUTER_USE_IMPLEMENTATION.md) |
| [VS Code extension](VSCODE.md) | [Developer guide](../src/uagent/docs/DEVELOP.md) |

Löydät myös koko dokumentaation ja muut kieliversiot: [Documentation](./) · [Other languages](README.translations.md).

## Kehitys ja osallistuminen
<!-- README-SYNC:contributing -->

~~~bash
git clone https://github.com/awaku7/agentcli.git
cd agentcli
python -m pip install -e ".[core,providers,test]"
~~~

Ennen **Python-koodia** muuttavaa pull requestia suorita asiaankuuluvat testit ja projektitarkistukset:

~~~bash
python -m ruff check src tests
python -m black --check src tests
python -m pytest -q .
~~~

Osallistumisohjeet ja kehittäjäopas löytyvät alta. Virheraportit, dokumentaation parannukset, työkalut, käännökset ja rajatut pull requestit ovat tervetulleita: [AGENTS.md](../AGENTS.md) · [Developer guide](../src/uagent/docs/DEVELOP.md).

## Lisenssi
<!-- README-SYNC:license -->

UAG julkaistaan lisenssillä: [Apache License 2.0](../LICENSE).
