<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="680">
</p>

<h1 align="center">uag</h1>

<p align="center">
  <strong>Universal AI Gateway</strong><br>
  Yksi paikallinen agentti. Mikä tahansa malli. Mikä tahansa työkalu. Sinun ympäristösi, sinun sääntösi.
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

**Miksi uag?**

uag on paikallisuutta painottava tekoälyagentti, joka yhdistää haluamasi mallin tosiasiassa käyttämiisi työkaluihin.
Se tarjoaa yhden laajennettavan ajonaikaisen ympäristön tiedostoille, selaimille, koodikannoille, viestinnälle,
pilvi-API:en, IoT-laitteiden, MCP-palvelimien ja moniagenttisten työnkulkujen käsittelyyn.

- **Vapaus valita palveluntarjoaja** — OpenAI, Anthropic, Gemini, Azure, Bedrock, Ollama, llama.cpp, Grok, DeepSeek ja muut.
- **Paikallisuutta painottava suoritus** — agentin ajonaikainen ympäristö ja työkalujen suoritus pysyvät koneellasi; vain valitsemasi API-kutsut poistuvat sieltä.
- **Yksi työkalukerros** — samat työkalut toimivat CLI:stä, työpöydän graafisesta käyttöliittymästä, verkkokäyttöliittymästä, VS Codesta ja A2A:sta.
- **Suunniteltu rinnakkaisuuteen** — toisistaan riippumattomat vain luku -operaatiot voivat suorittua samanaikaisesti.
- **Laajennettava** — lisää työkaluja, liitännäisiä, Agent Skills -taitoja, MCP-palvelimia ja Rust-pohjaisia työkaluja ydintä muuttamatta.
- **Turvallisuustietoinen** — tuhoavat toiminnot, tunnistetiedot, laiteohjaus ja verkkokirjoitukset tukevat nimenomaista vahvistusta ja käytäntöjen hallintaa.

> **Lyhyesti:** uag on ohjaustaso tekoälymalliesi ja todellisen ympäristösi välillä.

> **🧠 Kontekstia huomioivat työkalun tulokset** — Suuria työkalun tuloksia pidetään mahdollisuuksien mukaan pois aktiivisesta mallikontekstista. uag tallentaa ne artefakteiksi ja välittää mallille sen sijaan rajatun esikatselun, jossa on vakaa Artifact-viite. Tämä voi vähentää huomattavasti seuraavissa vuoroissa tarvittavien syöttötunnusten määrää, kun työkalu tuottaa laajan tuloksen.
> [Yksityiskohtainen kontekstin pakkausopas](CONTEXT_COMPRESSION.fi.md)

## Pika-aloitus

**Python 3.11+**

```bash
python -m pip install --upgrade uag
uag
```

Ensimmäinen käynnistys avaa ohjattuun asetusten määritykseen. Se auttaa määrittämään palveluntarjoajan ja tallentaa valitut asetukset
paikalliseen ympäristöösi.

Yleisiä ominaisuusryhmiä varten:

```bash
python -m pip install "uag[core,providers,tools]"
```

> Alustaintegraatiot ovat valinnaisia. Asenna vain käyttöjärjestelmäsi tarvitsemat osat; katso

```text
> What files changed in this repository?
> Search the web for today's AI news and summarize the top five stories.
> :help
```

[Quickstart](QUICKSTART.md) · [Environment](ENVIRONMENT.md)

## Käyttöliittymät

| Käyttöliittymä | Komento | Soveltuu parhaiten |
|---|---|---|
| **CLI** | `uag` | Nopeaan, näppäimistöpainotteiseen työskentelyyn |
| **Työpöydän graafinen käyttöliittymä** | `uagg` | Natiivin työpöytäkokemuksen saamiseen |
| **Verkkokäyttöliittymä** | `uagw` | Selainpohjaiseen käyttöön |
| **A2A-palvelin** | `uaga` | Agenttien väliseen viestintään |
| **VS Code** | Laajennus | Työkalujen selittämiseen, uudelleenmuokkaukseen, korjaamiseen ja selaamiseen editorissa |

Kaikki käyttöliittymät jakavat saman palveluntarjoajan määrityksen, työkalurekisterin, turvallisuussäännöt ja istuntotiedot.

~~~bash
# Desktop GUI
python -m pip install "uag[platform]"

# Web UI
python -m pip install "uag[web]" fastapi uvicorn
~~~

[Interface options](USAGE.md) · [Environment](ENVIRONMENT.md)

## Mitä voit rakentaa

Palveluntarjoajasovittimet kattavat isännöidyt ja paikalliset ajonaikaiset ympäristöt, mukaan lukien:

- Lue, luo, muokkaa, etsi, tiivistä, arkistoi ja tarkastele tiedostoja
- Tarkastele Git-muutoksia, etsi salaisuuksia, suorita testejä, linttaa, käännä ja mittaa kattavuutta
- Navigoi suurissa Python-, TypeScript-, JavaScript-, Go-, Rust-, C/C++-, Java-, C#-, COBOL-, VBA- ja muissa koodikannoissa
- Automatisoi selaimia Playwrightilla, mukaan lukien monisivuiset työnkulut ja lataukset

- **MCP** — yhdistä ulkoisia työkalupalvelimia, mukaan lukien OAuthia tukevat palvelut
- **A2A** — koordinoi muiden agenttien ja yhteensopivien palvelimien kanssa
- **Pilvi** — AWS-, Google Cloud- ja Azure-API-käyttö, kirjoitusten vahvistuksella
- **Viestintä** — Gmail, Bluesky, Discord, Microsoft Teams ja pybitchat
- **IoT** — SwitchBot, ECHONET Lite, Matter, BACnet, Modbus TCP, OPC UA ja UPnP
- **Media** — kuvien luonti ja muokkaus, äänen litterointi ja puhesynteesi, kameran kaappaus ja QR-koodit
- **Dokumentit** — PDF-, PowerPoint-, Word-, Excel-, CSV-, JSON-, YAML-, SQL- ja lokianalyysi

- **SwitchBot** — pilvi- ja BLE-haku, tila, ohjaus, eräkäsittely ja tilaukset
- **ECHONET Lite** — japanilaisten kodinkoneiden etsintä ja ohjaus, mukaan lukien INF-ilmoitukset
- **Matter** — päätepisteet, klusterit, attribuutit, tilahistoria, tilaukset ja ohjaus
- **BACnet / Modbus TCP / OPC UA** — teollisuuden ja rakennusautomaation luku, kirjoitus, selaus ja valvonta
- **UPnP** — laitteiden etsintä, WAN-tila ja reitittimen porttikartoituksen hallinta

### Mihin uag sijoittuu?

uag toimii ihmisten ja käyttöliittymien toisella puolella sekä mallien, työkalujen ja reaalimaailman järjestelmien toisella puolella.
Se koordinoi keskustelua, valitsee kyvykkyydet, soveltaa turvallisuussääntöjä ja pitää työnkulun jatkettavana.

~~~mermaid
flowchart LR
    UI["CLI · Desktop · Web · VS Code · A2A"] --> UAG["UAG agent runtime"]
    UAG --> MODELS["Hosted & local models"]
    UAG --> TOOLS["Tools & extensions"]
    UAG --> STATE["Sessions & context"]
    TOOLS --> SYSTEMS["Files · Code · Web · MCP · Cloud · IoT"]
    POLICY["Confirmation · Credentials · Policy"] -.-> UAG
~~~

### Liitännäiset, Agent Skills -taidot ja markkinapaikat

Muunna uag erikoistuneeksi agentiksi ilman ytimen haarauttamista:

- Asenna **Claude Code -yhteensopivia liitännäisiä** hakemistosta, ZIP-tiedostosta, Git-repositorysta, HTTP-lähteestä tai markkinapaikasta
- Niputa taitoja, aliagentteja, MCP-palvelimia, koukkuja, kauttaviivakomentoja, tulostustyylejä, riippuvuuksia ja kanavia
- Selaa yhteisön kyvykkyyksiä palveluista [SkillsMP](https://skillsmp.com) ja [ClawHub](https://clawhub.ai)
- Lisää yksityisiä organisaation taitoja ja työkaluja paikallisesti muuttujan `UAGENT_EXTERNAL_TOOLS_DIR` kautta

```text
:skills mp_search browser automation
:plugin list
:plugin install <source>
:plugin marketplace list
```

Katso [liitännäisten kehitysopas](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP_PLUGIN.md).

- **200+ työkalua** tiedostoille, verkolle, medialle, dokumenteille, koodille, pilvipalveluille, viestinnälle ja IoT:lle
- **Dynaaminen etsintä ja lataus** — etsi kyvykkyyksiä `tool_catalog`-komennolla ja ota ne käyttöön `tool_load`-komennolla vain tarvittaessa
- **Koodiäly** — `code_map`, kielikohtaiset `idx`-navigaattorit, Git-tarkastelu, testien suoritus, linttaus, käännös ja kattavuus
- **Claude Code -yhteensopivat liitännäiset**, joissa on taitoja, agentteja, MCP-palvelimia, koukkuja, komentoja ja markkinapaikkoja
- **Agent Skills** SkillsMP:stä ja ClawHubista
- **Mukautetut Python-työkalut**, joissa käytetään `TOOL_SPEC`-määritystä ja `run_tool()`-funktiota
- **Rust-pohjaiset työkalut** kevyisiin natiivilaajennuksiin

[Tool Creator Guide](../TOOL_CREATOR_GUIDE.md) · [MCP OAuth / Proxy Guide](MCP_OAUTH_PROXY_GUIDE.md)

## Suunniteltu todellisiin työnkulkuihin

### 🧠 Kontekstia huomioivat työkalun tulokset

Suuria työkalun tuloksia pidetään mahdollisuuksien mukaan pois aktiivisesta mallikontekstista. uag tallentaa ne artefakteiksi ja välittää mallille sen sijaan rajatun esikatselun, jossa on vakaa Artifact-viite. Tämä voi vähentää huomattavasti seuraavissa vuoroissa tarvittavien syöttötunnusten määrää, kun työkalu tuottaa laajan tuloksen.

Jatka aiempia keskusteluja komennolla `:load <index>`. Työkalutuloksia voidaan tallentaa välimuistiin ja palveluntarjoajia voidaan vaihtaa
sovellusta uudelleen rakentamatta.

[Context compression](CONTEXT_COMPRESSION.fi.md) · [Memory](MEMORY.md) · [Session portability](SESSION_PORTABILITY.md)

### Autopilotti

Käytä monikierroksiseen työskentelyyn komentoa `:auto`, ja halutessasi arvioijamallia. Aseta kierrosraja valitsimella `--max-rounds N`.
Paina **F12** pysäyttääksesi autopilotin tai **F12** pysäyttääksesi nykyisen vastauksen.

Toisistaan riippumattomat vain luku -operaatiot suoritetaan turvallisissa tilanteissa samanaikaisesti. Verkkohaut, tiedostojen tarkastelu,
repositoryn analyysi ja vastaavat työkuormat voidaan suorittaa rinnakkain määritettävän työpoolin
(`UAGENT_PARALLEL_WORKERS`) avulla. Kirjoitusoperaatiot pysyvät sarjallistettuina tai vaativat vahvistuksen.

Istunnon jatkuvuus, työkalutulosten välimuisti, erätila, uudelleenkäynnistyksen palautuminen, DAG-ajastus ja
moniagenttinen orkestrointi tekevät monimutkaisesta työstä jatkettavaa kertaluonteisen sijaan.

[Auto-pilot](README_AUTO.md) · [Timers](SET_TIMER.md) · [Multi-agent runtime](MULTI_AGENT_RUNTIME.md)

### 🌍 Yksityinen, monikielinen ja käytäntötietoinen

`human_ask` keskeyttää toiminnan ennen arkaluonteisia toimintoja. Tiedostojen poistamista, ylikirjoituksia, komentotulkin komentoja, laiteohjausta,
tunnistetieto-operaatioita ja verkkokirjoituksia voidaan hallita vahvistus- ja käytäntösäännöillä.

Käytä tunnistetietovarastoa sen sijaan, että sijoittaisit pitkäkestoisia salaisuuksia kehotteisiin:

Verkkokäyttöliittymä sisältää OIDC-kirjautumisen Authorization Code + PKCE -menetelmällä, varmennetut ID-tokenit, palvelinpuolen istunnot sekä projektien/huoneiden käyttöoikeuksien hallinnan. Varmennetut Microsoft Entra ID -ryhmäväitteet voivat syöttää hakemistopohjaista käyttöoikeuspolitiikkaa, kun ne on määritetty. Windows Active Directory-, OAuth- ja trusted-proxy-järjestelmät voidaan integroida eksplisiittisten varmennettujen tunnistusadapterien kautta; Windows AD vaatii käyttöönottoon räätälöidyn Kerberos/Negotiate-varmentimen eikä ole oletuksena käytössä.

uag sisältää valinnaisen, toimittajaneutraalin OpenTelemetry-seurannan ja mittarit kohteille Agent, LLM, työkalu, Context, Memory ja hakutoiminnot. Havainnointi on oletuksena pois käytöstä.

Paikallisuus edellä ei tarkoita, että UAG toimisi oletusarvoisesti täysin ilman verkkoyhteyttä tai että kaikki työkalut olisi eristetty. Ulkoisten mallien ja palveluiden kutsut riippuvat määrityksistä.

- [Enterprise policies](ENTERPRISE_POLICY.md)
- [MXC sandbox](SANDBOX_MXC.md)
- [Remote Web / A2A](REMOTE_MXC_DEFAULT.md)
- [Web identity](WEB_IDENTITY_MEMORY.md)
- [OpenTelemetry](UAG_OPENTELEMETRY_DESIGN.md)

### 🌍 Monikielinen käännös

- `translate_text` tukee Google Translate:aa ja virallista DeepL-Python-asiakasohjelmaa asetuksilla `provider=auto`, `provider=deepl` tai `provider=google`.
- Työkalumääritelmät ovat saatavilla 37 kieliversiossa sekä englanniksi (yhteensä 38), ja paikkamerkit sekä tekniset tunnisteet säilytetään.

Täysdupleksiääni on saatavilla OpenAI Realtime-, Azure OpenAI-, xAI Grok Voice-, Gemini Live-
ja Bedrock Nova Sonic -palvelujen kautta. Saatavilla on myös valinnainen AEC3-kaikupoisto ja turvallisuusrajoitettu reaaliaikainen funktiokutsu.

[Translations](README.translations.md) · [IoT](IOT_USECASE.md) · [Communication](COMMUNICATION.md)

## Dokumentaatio

| Aihe | Dokumentaatio |
|---|---|
| Ympäristömuuttujat | [docs/ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/docs/ENVIRONMENT.md) |
| Arkkitehtuuri ja invarianssit | [docs/ARCHITECTURE.md](https://github.com/awaku7/agentcli/blob/main/docs/ARCHITECTURE.md) |
| Computer Use | [docs/COMPUTER_USE_IMPLEMENTATION.md](https://github.com/awaku7/agentcli/blob/main/docs/COMPUTER_USE_IMPLEMENTATION.md) |
| Repository-työkalut | [docs/REPOSITORY_TOOLS.md](https://github.com/awaku7/agentcli/blob/main/docs/REPOSITORY_TOOLS.md) |
| IoT-käyttötapaukset | [docs/IOT_USECASE.md](https://github.com/awaku7/agentcli/blob/main/docs/IOT_USECASE.md) |
| Viestintätyökalut | [docs/COMMUNICATION.md](https://github.com/awaku7/agentcli/blob/main/docs/COMMUNICATION.md) |
| Autopilotti | [docs/README_AUTO.md](https://github.com/awaku7/agentcli/blob/main/docs/README_AUTO.md) |
| MCP OAuth / Proxy | [docs/MCP_OAUTH_PROXY_GUIDE.md](https://github.com/awaku7/agentcli/blob/main/docs/MCP_OAUTH_PROXY_GUIDE.md) |
| VS Code -laajennus | [docs/VSCODE.md](https://github.com/awaku7/agentcli/blob/main/docs/VSCODE.md) |
| Kehittäjän opas | [src/uagent/docs/DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md) |
| Työkalujen kulku | [src/uagent/docs/TOOL_FLOW.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/TOOL_FLOW.md) |

[Quickstart](QUICKSTART.md) · [Architecture](ARCHITECTURE.md) · [Context management](UAG_CONTEXT_MANAGEMENT_DESIGN.md)

## Kehitys ja osallistuminen

```bash
git clone https://github.com/awaku7/agentcli.git
cd agentcli
python -m pip install -e ".[core,providers,test]"
```

Suorita PR:ää edeltävät tarkistukset:

```bash
python -m ruff check src tests
python -m black --check src tests
python -m pytest -q .
```

Katso koko kehitystyönkulku [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)-tiedostosta.

Vikaraportit, ominaisuusideat, dokumentaation parannukset, käännökset, työkalut, taidot ja pull requestit ovat tervetulleita.
Avaa issue tai keskustelu ennen suuria muutoksia. Lue [kehittäjän opas](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)
ja suorita yllä olevat tarkistukset ennen pull requestin lähettämistä.

## Lisenssi

Lisensoitu [Apache License 2.0](https://github.com/awaku7/agentcli/blob/main/LICENSE) -lisenssillä.
