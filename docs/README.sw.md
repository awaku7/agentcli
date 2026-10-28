<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="UAG — Universal AI Gateway" width="620">
</p>
<h1 align="center">UAG</h1>
<p align="center"><strong>Universal AI Gateway</strong><br>Miundo yako ya AI. Zana zako. Mazingira yako.</p>

<p align="center">
  <a href="https://github.com/awaku7/agentcli/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/awaku7/agentcli/ci.yml?style=flat-square&label=CI" alt="CI"></a>
  <a href="https://pypi.org/project/uag/"><img src="https://img.shields.io/pypi/v/uag?style=flat-square" alt="PyPI"></a>
  <a href="https://pypi.org/project/uag/"><img src="https://img.shields.io/pypi/pyversions/uag?style=flat-square" alt="Python versions"></a>
  <a href="../LICENSE"><img src="https://img.shields.io/github/license/awaku7/agentcli?style=flat-square" alt="License"></a>
  <a href="https://pepy.tech/projects/uag"><img src="https://static.pepy.tech/personalized-badge/uag?period=total&units=INTERNATIONAL_SYSTEM&left_color=grey&right_color=green&left_text=downloads" alt="Downloads"></a>
</p>
<p align="center"><a href="../README.md">English</a> · <a href="README.translations.md">Lugha nyingine</a></p>

---

**UAG ni mazingira huria ya kuendesha mawakala wa AI yanayotanguliza utekelezaji wa ndani.** Huunganisha modeli ya lugha unayoichagua na zana na mifumo unayotumia. Shughulikia msimbo, faili, vivinjari, huduma na vifaa kupitia kiolesura kimoja, bila kutegemea mtoa huduma mmoja wa modeli.

| **Chagua modeli yako** | **Unganisha zana halisi** | **Dumisha udhibiti** |
| :--- | :--- | :--- |
| Modeli za wingu na za ndani kama OpenAI, Claude, Gemini, Grok, Bedrock na Ollama | Faili, msimbo, wavuti, MCP, Agent Skills, programu-jalizi, wingu na IoT | Utekelezaji wa ndani, uthibitisho wa binadamu, kuhifadhi taarifa za kuingia na sera zinazoweza kusanidiwa |

> UAG ni **safu ya kutekeleza mawakala, si mtoa huduma wa modeli**. Miito kwa modeli na huduma za nje hutegemea mipangilio. Kutanguliza kazi za ndani hakumaanishi kufanya kazi nje ya mtandao kabisa au kutenga zana zote moja kwa moja.

## Anza kwa haraka
<!-- README-SYNC:quick-start -->

Unahitaji **Python 3.11 au mpya zaidi**. Sakinisha UAG kutoka [PyPI](https://pypi.org/project/uag/) na uanzishe CLI shirikishi:

~~~bash
python -m pip install --upgrade uag
uag
~~~

Unapoanza kwa mara ya kwanza, mwongozo wa usanidi hukusaidia kuchagua mtoa huduma wa modeli na kuweka taarifa za uthibitisho. Unaweza pia kutumia vigeu vya mazingira au hifadhi salama. Kusakinisha mapema vitegemezi zaidi vya modeli na zana:

~~~bash
python -m pip install "uag[core,providers,tools]"
~~~

Kisha jaribu maombi haya:

~~~text
> Ni nini kimebadilika katika hazina hii ya Git? Fupisha hatari.
> Tafuta nyaraka mpya zaidi za maktaba hii na ueleze hatua za uhamishaji.
> Kagua faili hizi na uandike ripoti fupi.
> :help
~~~

Watumiaji wapya wanaweza kusoma mwongozo wa Windows wenye maelezo ya Git na mazingira pepe, pamoja na rejea ya usanidi: [Quickstart (Windows)](QUICKSTART.md) · [Environment](ENVIRONMENT.md).

## Miingiliano
<!-- README-SYNC:interfaces -->

Miingiliano yote hutumia mazingira yale yale ya wakala na orodha moja ya zana.

| Kiolesura | Anza kwa | Kinafaa kwa |
| :--- | :--- | :--- |
| **CLI** | `uag` | Kazi za terminali na uendeshaji otomatiki |
| **Desktop** | `uagg` | Mazungumzo katika programu ya kompyuta |
| **Web** | `uagw` | Mazungumzo na vyumba kwenye kivinjari |
| **A2A** | `uaga` | Ushirikiano kati ya mawakala |
| **VS Code** | [Mwongozo wa kiendelezi](VSCODE.md) | Kufanya kazi pamoja na msimbo |

Desktop na Web zinahitaji vitegemezi vya ziada ambavyo havipo kwenye usakinishaji wa `uag[core,providers,tools]`:

~~~bash
# Desktop GUI (PySide6 and platform integrations)
python -m pip install "uag[platform]"

# Web UI (authentication dependencies, FastAPI, and Uvicorn)
python -m pip install "uag[web]" fastapi uvicorn
~~~

Seva ya Web inaweza kujaribu kusakinisha FastAPI na Uvicorn inapoanza. Kuzisakinisha mapema huondoa utegemezi wa usakinishaji wa kiotomatiki. Maelezo: [CLI usage](USAGE.md) · [Environment](ENVIRONMENT.md).

## Unachoweza kufanya kwa UAG
<!-- README-SYNC:capabilities -->

| Uwezo | UAG inachotoa |
| :--- | :--- |
| **Kazi zisizofungwa kwa modeli** | Badili watoa huduma wa wingu na wa ndani kupitia `UAGENT_PROVIDER` bila kuandika upya zana |
| **Msimbo na faili** | Kuchunguza hazina, kukagua Git, lint, majaribio, shughuli za faili na uendeshaji otomatiki wa kivinjari |
| **Zana zinazopanuka** | Zaidi ya zana 200, ugunduzi wa moja kwa moja kwa `tool_catalog` / `tool_load`, zana maalumu za Python na Rust |
| **Mawakala waliounganishwa** | MCP, A2A, programu-jalizi zinazoendana na Claude Code, Agent Skills na mawakala wadogo |
| **Kazi za muda mrefu** | Autopilot, usomaji huru sambamba, ratiba, urejeshaji na vikao vinavyohifadhiwa |
| **Zaidi ya terminali** | Wingu, mawasiliano, nyaraka, media, sauti ya wakati halisi na itifaki za IoT zinazotumika |

### Mazingira moja ya utekelezaji, miunganisho mingi
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

**Mifano ya watoa huduma wa modeli wanaokubaliwa** ipo hapa chini. Mipangilio maalumu iko kwenye nyaraka za mazingira.

**OpenAI · Anthropic · Gemini · Vertex AI · Azure OpenAI · Amazon Bedrock · Grok · DeepSeek · OpenRouter · Ollama · llama.cpp · LM Studio**

[ENVIRONMENT.md](ENVIRONMENT.md)

### Binafsisha kwa ujuzi na programu-jalizi
<!-- README-SYNC:extensions -->

Panua UAG bila kubadilisha kiini chake. Sakinisha Agent Skills kutoka SkillsMP au ClawHub, unganisha seva za MCP, au pakia programu-jalizi zinazoendana na Claude Code zenye zana, ujuzi, mawakala na hooks.

~~~text
:skills mp_search browser automation
:plugin list
:plugin install <source>
:plugin marketplace list
~~~

Zana maalumu zinaweza kutoa `TOOL_SPEC` na `run_tool()`; zana za Rust pia zinatumika. Soma miongozo: [Tool Creator Guide](../TOOL_CREATOR_GUIDE.md) · [Plugin Development Guide](../src/uagent/docs/DEVELOP_PLUGIN.md) · [MCP OAuth / Proxy](MCP_OAUTH_PROXY_GUIDE.md).

## Kwa kazi za kweli
<!-- README-SYNC:workflows -->

### Muktadha na kumbukumbu
<!-- README-SYNC:context-memory -->

Matokeo makubwa ya zana yanaweza kuhifadhiwa kama **artifakti** badala ya kujaza muktadha hai wa modeli. Baadaye wakala huchukua sehemu inayohitajika kupitia `artifact_read`. Vikao huhifadhiwa kwenye SQLite kwa chaguomsingi, pamoja na utafutaji wa historia na mapitio ya kumbukumbu yaliyo wazi.

- [Context compression](CONTEXT_COMPRESSION.sw.md)
- [Memory](MEMORY.md)
- [Session portability](SESSION_PORTABILITY.md)

### Uendeshaji otomatiki na ushirikiano
<!-- README-SYNC:automation -->

UAG inaunga mkono usomaji huru unaoenda sambamba, uratibu wa mawakala wengi, kurejesha vikao na Autopilot kwa kazi za hatua nyingi. Anza kwa `:auto`; bonyeza **F12** kukatiza jibu la sasa na kuomba Autopilot isimame.

- [Auto-pilot](README_AUTO.md)
- [Timers and scheduled tasks](SET_TIMER.md)
- [Multi-agent runtime](MULTI_AGENT_RUNTIME.md)

### Usalama na uangalizi
<!-- README-SYNC:security -->

Vitendo nyeti vinaweza kuhitaji idhini kupitia `human_ask`. Taarifa za uthibitisho zinaweza kuwekwa kwenye hifadhi ya mfumo wa uendeshaji au faili iliyosimbwa. Web inaunga mkono kuingia kwa OIDC na udhibiti wa ufikiaji baada ya usanidi. Ufuatiliaji na vipimo vya OpenTelemetry ni **hiari**.

- [Enterprise policies](ENTERPRISE_POLICY.md)
- [MXC sandbox](SANDBOX_MXC.md)
- [Remote Web / A2A MXC defaults](REMOTE_MXC_DEFAULT.md)
- [Web identity and rooms](WEB_IDENTITY_MEMORY.md)
- [OpenTelemetry design](UAG_OPENTELEMETRY_DESIGN.md)
- [Developer observability](../src/uagent/docs/DEVELOP_OBSERVABILITY.md)

Vidhibiti hivi vinaweza kusanidiwa lakini **havihakikishi** kila zana inaendeshwa katika sandbox iliyotengwa. Soma miongozo ya uwekaji na sera kabla ya kufungua UAG kwa watumiaji au mitandao isiyoaminika.

### Lugha, vifaa na sauti
<!-- README-SYNC:languages -->

UAG ina rasilimali za **mipangilio 38 ya lugha** (Kiingereza na tafsiri 37), muunganisho wa sauti wa pande mbili wa hiari na zana za SwitchBot, Matter, ECHONET Lite, BACnet, Modbus TCP na OPC UA.

- [Translations](README.translations.md)
- [IoT use cases](IOT_USECASE.md)
- [Communication tools](COMMUNICATION.md)

## Nyaraka
<!-- README-SYNC:documentation -->

Anza na miongozo hii na uende kwa maelezo zaidi:

| Anza hapa | Maelezo zaidi |
| :--- | :--- |
| [Quickstart (Windows)](QUICKSTART.md) | [Architecture](ARCHITECTURE.md) |
| [CLI usage](USAGE.md) | [Context management](UAG_CONTEXT_MANAGEMENT_DESIGN.md) |
| [Environment and providers](ENVIRONMENT.md) | [Enterprise policy](ENTERPRISE_POLICY.md) |
| [Agent Skills and plugins](../src/uagent/docs/DEVELOP_PLUGIN.md) | [Tool flow](../src/uagent/docs/TOOL_FLOW.md) |
| [MCP and OAuth](MCP_OAUTH_PROXY_GUIDE.md) | [Computer Use](COMPUTER_USE_IMPLEMENTATION.md) |
| [VS Code extension](VSCODE.md) | [Developer guide](../src/uagent/docs/DEVELOP.md) |

Unaweza pia kuona nyaraka zote na lugha nyingine: [Documentation](./) · [Other languages](README.translations.md).

## Uendelezaji na michango
<!-- README-SYNC:contributing -->

~~~bash
git clone https://github.com/awaku7/agentcli.git
cd agentcli
python -m pip install -e ".[core,providers,test]"
~~~

Kabla ya pull request inayobadili **msimbo wa Python**, endesha majaribio husika na ukaguzi wa mradi:

~~~bash
python -m ruff check src tests
python -m black --check src tests
python -m pytest -q .
~~~

Sheria za michango na mwongozo wa msanidi zipo hapa chini. Ripoti za hitilafu, uboreshaji wa nyaraka, zana, tafsiri na pull requests zenye lengo maalumu zinakaribishwa: [AGENTS.md](../AGENTS.md) · [Developer guide](../src/uagent/docs/DEVELOP.md).

## Leseni
<!-- README-SYNC:license -->

UAG inasambazwa chini ya leseni: [Apache License 2.0](../LICENSE).
