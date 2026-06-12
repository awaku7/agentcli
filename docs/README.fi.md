<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="720">
</p>

# uag (Paikallinen AI-agentti)

uag on paikallinen interaktiivinen agentti, joka suorittaa **komentoja**, käsittelee **tiedostoja** ja lukee **datatiedostoja** kuten PDF-, PPTX- ja Excel-tiedostoja. Se tarjoaa kolme käyttöliittymää: CLI, GUI ja Web.

uag on suunniteltu **vapauttamaan sinut toimittajalukituista sovelluksista**: käytä työnkulkuusi sopivaa käyttöliittymää, vaihda palveluntarjoajaa ja pidä ympäristösi hallinnassasi.

GitHub: https://github.com/awaku7/agentcli

## Asennus

Asenna PyPI:stä pipillä:

```bash
pip install uag
```

Jos käytät virtuaaliympäristöä, aktivoi se ensin ja suorita sitten yllä oleva komento.

Ensimmäisellä käynnistyksellä `uag` tarkistaa ympäristösi ja käynnistää asetustoiminnon automaattisesti, jos vaadittuja provider-muuttujia puuttuu. Katso asetustiedot tiedostosta [ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md).

## Tärkeimmät ominaisuudet

- **Käytännölliset työkalut**: tiedostojen käsittely, web-haku, PDF/PPTX/Excel-purku, kuvien luonti ja kuvien analysointi.
- **Usean providerin tuki**: OpenAI / Azure / Bedrock / OpenRouter / Ollama / Gemini / Vertex AI / Claude / Grok / NVIDIA.
- **Kolme käyttöliittymää**:
  - **CLI**: `uag` / `python -m uagent`
  - **GUI**: `uagg` / `python -m uagent.gui`
  - **Web**: `uagw` / `python -m uagent.web`
  - **A2A-palvelin**: `uaga` / `python -m uagent.a2a.server`
- **MCP-tuki**: Yhdistä ulkoisiin MCP-työkalupalvelimiin.
- **Istunnon jatkuvuus**: säilytä konteksti, kun vaihdat mallia tai provideria.
- **Web Inspector**: tallenna selaimen siirtymät, DOM-tilannevedokset ja kuvakaappaukset `playwright_inspector`-työkalulla.
- **Sisäänrakennetut dokumentit**: lue mukana tulevat dokumentit komennolla `uag docs`.

## Käyttö

### Käynnistys ja lopetus

Aloita suorittamalla `uag` terminaalissa. Poistu kirjoittamalla `:exit`.

### A2A-palvelin

Käynnistä Agent2Agent-yhteensopiva HTTP-palvelin:

```bash
uaga
```

Katso `UAGENT_A2A_*`-asetukset, kuten tunnistus, host, portti, uudelleenlataus, julkinen perus-URL, rinnakkaisuus ja engine, tiedostosta [ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md).

### Kätevät komennot

- `:tools`: näytä ladatut työkalut
- `:logs [n]`: näytä viimeisimmät istuntolokit
- `:load <index>`: lataa aiempi istunto
- `:skills`: valitse ja lataa Agent Skills -osaamisia
- `:shrink [n]`: tiivistä historia ja säilytä viimeiset `n` viestiä

## Asetukset ja lisätiedot

### Ympäristömuuttujat ja asetukset

API-avaimia, kieliasetuksia (`UAGENT_LANG`), historian tiivistysasetuksia ja muita tietoja varten katso [ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md).

- **Asetustoiminto**: `python -m uagent.setup_cli`
- **Salattu ympäristö**: käytä `uag_envsec`-työkalua salataksesi `.env`-tiedoston muotoon `.env.sec`
- **Salattujen arvojen päivitys**: `uag_envsec add --file .env.sec --key NAME --value VALUE`

### Huomio Responses API:sta

Jos asetat arvon `UAGENT_RESPONSES=1`, Responses API:ta käytetään tuetuille providerille: OpenAI / Azure / Bedrock / OpenRouter / Ollama.
Gemini / Claude / Vertex AI käyttävät omia API-polkujaan, eikä Responses API kata niitä.
Muiden providerien kohdalla uag käyttää provider-kohtaista tai chat-completions-polkuja.

### Kehittäjädokumentaatio ja käännökset

- **Kehittäjädokumentit**: [`src/uagent/docs/DEVELOP.md`](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)
- **Lisää localeja**: [`src/uagent/docs/ADD_LOCALE.md`](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/ADD_LOCALE.md)
- **Muut README-käännökset**: [`docs/README.translations.md`](https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md)

Jos asetat arvon `UAGENT_RESPONSES=1`, Responses API:ta käytetään tuetuille providerille: OpenAI / Azure / Bedrock / OpenRouter / Ollama.
Gemini / Claude / Vertex AI use their native API paths and are not covered by Responses API.
For other providers, uag falls back to the provider-specific or chat-completions path.
