<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="720">
</p>

# uag (Wakala wa AI wa Ndani)

uag ni wakala shirikishi wa ndani unaotekeleza **amri**, kusimamia **faili**, na kusoma **faili za data** kama PDF, PPTX, na Excel. Inatoa miingiliano mitatu ya mtumiaji: CLI, GUI, na Web.

uag imeundwa ili **ikuepushe na programu zilizo fungwa na mtoa huduma**: tumia kiolesura kinachofaa mtiririko wako wa kazi, badili watoa huduma, na udumishe udhibiti wa mazingira yako.

GitHub: https://github.com/awaku7/agentcli

## Usakinishaji

Sakinisha kutoka PyPI kwa kutumia pip:

```bash
pip install uag
```

Ukitumia mazingira ya virtual, yasha kwanza kisha endesha amri hapo juu.

Wakati wa kuzindua kwa mara ya kwanza, `uag` hukagua mazingira yako na huanza kiotomatiki mchawi wa usanidi ikiwa vigezo vinavyohitajika vya mtoa huduma havipo. Kwa maelezo ya usanidi, tazama [ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md).

## Vipengele Vikuu

- **Zana za vitendo**: Usimamizi wa faili, utafutaji wa wavuti, uchimbaji wa PDF/PPTX/Excel, uundaji wa picha, na uchambuzi wa picha.
- **Unga mkono wa watoa huduma wengi**: OpenAI / Azure / Bedrock / OpenRouter / Ollama / Gemini / Vertex AI / Claude / Grok / NVIDIA.
- **Miingiliano mitatu**:
  - **CLI**: `uag` / `python -m uagent`
  - **GUI**: `uagg` / `python -m uagent.gui`
  - **Web**: `uagw` / `python -m uagent.web`
  - **A2A server**: `uaga` / `python -m uagent.a2a.server`
- **Unga mkono wa MCP**: Unganisha kwenye seva za zana za MCP za nje.
- **Mwendelezo wa kipindi**: Hifadhi muktadha hata ukibadilisha modeli au mtoa huduma.
- **Web Inspector**: Hifadhi mabadiliko ya kivinjari, picha za DOM, na skrini kwa `playwright_inspector`.
- **Nyaraka zilizojengwa**: Soma nyaraka zilizomo kwa `uag docs`.

## Matumizi

### Kuanzisha na kuondoka

Endesha `uag` kwenye terminal yako ili kuanza. Andika `:exit` ili kutoka.

### Seva ya A2A

Zindua seva ya HTTP inayooana na Agent2Agent:

```bash
uaga
```

Tazama [ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md) kwa mipangilio ya `UAGENT_A2A_*` kama uthibitisho, hosti, bandari, reload, public base URL, concurrency, na engine.

### Vidokezo vya haraka

- `:tools`: onyesha orodha ya zana zilizopakiwa
- `:logs [n]`: onyesha logi za hivi karibuni za kipindi
- `:load <index>`: pakia kipindi cha awali
- `:skills`: chagua na pakia Agent Skills
- `:shrink [n]`: fupisha historia na uhifadhi ujumbe wa mwisho `n`

## Usanidi na maelezo

### Vigezo vya mazingira na usanidi

Kwa funguo za API, mipangilio ya lugha (`UAGENT_LANG`), mipangilio ya kupunguza historia, na zaidi, tazama [ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md).

- **Mchawi wa usanidi**: `python -m uagent.setup_cli`
- **Mazingira yaliyosimbwa**: tumia `uag_envsec` kusimba `.env` kuwa `.env.sec`
- **Sasisha thamani zilizosimbwa**: `uag_envsec add --file .env.sec --key NAME --value VALUE`

### Dokezo kuhusu Responses API

Ukiweka `UAGENT_RESPONSES=1`, Responses API itatumika kwa watoa huduma wanaoungwa mkono: OpenAI / Azure / Bedrock / OpenRouter / Ollama.
Gemini / Claude / Vertex AI hutumia njia zao asili za API na hazimo kwenye Responses API.
Kwa watoa huduma wengine, uag hurudi kwenye njia mahususi ya mtoa huduma au chat-completions.

### Nyaraka za msanidi na tafsiri

- **Nyaraka za msanidi**: [`src/uagent/docs/DEVELOP.md`](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)
- **Ongeza locale**: [`src/uagent/docs/ADD_LOCALE.md`](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/ADD_LOCALE.md)
- **README za lugha nyingine**: [`docs/README.translations.md`](https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md)
