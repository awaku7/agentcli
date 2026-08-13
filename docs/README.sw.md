<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="720">
</p>

<h1 align="center">uag - Universal AI Gateway</h1>

<p align="center">
  <b>U</b>niversal <b>A</b>I <b>G</b>ateway — Mazingira yako, uhuru wako.
</p>

<p align="center">
  Uendeshaji wa faili / Utafutaji wa wavuti / Uundaji wa picha & uchanganuzi / PDF & Excel uchimbaji / IoT udhibiti / MCP muunganisho<br>
  24 providers / 3 UIs / Utekelezaji wa zana Sambamba / Agent Skills sokoni
</p>

<p align="center">
  <a href="https://github.com/awaku7/agentcli">GitHub</a>
  ·
  <a href="https://pypi.org/project/uag/">PyPI</a>
  ·
  <a href="README.translations.md">Read this in your language</a>
</p>

______________________________________________________________________

##Kwanini uag?

**Jiepushe na kufuli kwa muuzaji.** Wasaidizi wengi wa AI hukufungamanisha na mtoa huduma mahususi au huduma ya wingu. uag ni tofauti.

- \*\* Huendesha ndani \*\* kwenye mashine yako. Data yako itasalia nawe (isipokuwa simu za API unazopiga).
- **Uhuru wa mtoa huduma**: OpenAI, Claude, Gemini, DeepSeek, Ollama, Azure, Bedrock, HuggingFace... 21+ watoa huduma, wote wanaweza kufikiwa kutoka kwa kiolesura kimoja. Badilisha kati yao kwa kusanidi upya anuwai za mazingira - hakuna kusakinisha tena, hakuna uhamiaji.
- **Zana 229**: Faili ya I/O, utafutaji wa wavuti, kutengeneza picha, Gmail, kuchanganua kifaa cha BLE, muunganisho wa seva ya MCP — **130 ni salama sambamba** (hadi 8 hutekelezwa kwa wakati mmoja kupitia mkusanyiko wa mazungumzo, inaweza kusanidiwa kupitia `UAGENT_PARALLEL_WORKERS`). Wakati LLM inapiga simu za zana nyingi mara moja, uag huzilinganisha kiotomatiki.
- **UI 3 + A2A**: CLI, GUI, Wavuti, na itifaki ya Wakala kwa Wakala. Injini sawa, interface yoyote.
- **Ujuzi wa Wakala**: Sakinisha ujuzi uliojengwa na jamii kutoka sokoni. Panua uag bila mwisho.

uag ni **msaidizi wako wa AI kwa masharti yako**. Haijafungwa kwa mtoa huduma, haijafungwa kwenye kiolesura, haijafungwa kwenye jukwaa.

## Anza Haraka

```bash
pip install uag
uag
```

Katika uzinduzi wa kwanza, mchawi wa kusanidi hukutembeza kupitia usanidi wa mtoa huduma.
Angalia [docs/ENVIRONMENT.md](ENVIRONMENT.md) kwa anuwai zote za mazingira.

## Vipengele

### 🧠 Usanifu wa Watoa Huduma nyingi

OpenAI / PFN (PLaMo) / Azure / Bedrock / OpenRouter / Ollama / Gemini / Vertex AI / Claude / Grok / NVIDIA / Novita / DeepSeek / Z.AI (Zhipu AI) / HuggingFace / Alibaba Cloud (Qwen) / KIMI (Moonshot AI) / Xiaomi MiMo / LM Studio / MiniMax / Sakana AI (Fugu) / SAKURA AI Engine / Together AI / Vercel AI Gateway

Watoa huduma wote wanashiriki zana sawa na kiolesura. Badili kwa kuweka `UAGENT_PROVIDER` — hakuna mabadiliko ya msimbo, hakuna usakinishaji tofauti.

### ⚡ Utekelezaji wa Zana Sambamba

Wakati LLM inaomba zana nyingi kwa wakati mmoja, uag **inazilinganisha kiotomatiki**.
Zana 130 zimewekwa alama `x_parallel_safe` na hutekelezwa kwa wakati mmoja kupitia `ThreadPoolExecutor` (nyuzi 8 kwa chaguomsingi; weka `UAGENT_PARALLEL_WORKERS` ili kubadilisha).

**Mfano**: Uliza "Angalia hali ya hewa katika herufi kubwa za Nordic" → Mioto ya LLM `search_web` × nchi 5 → utafutaji wote 5 unakwenda sambamba → matokeo yaliyokusanywa katika kundi moja.

Zana za kusoma pekee (utaftaji wa faili, hesabu ya heshi, orodha ya saraka, tafsiri, hoja za DB, n.k.) zimesawazishwa kwa ukali.

### 🧩 Mfumo wa programu-jalizi (unaooana na Claude Code)

uagent hutekeleza mfumo wa programu-jalizi unaooana na Claude Code. Programu-jalizi huunganisha ujuzi, mawakala, seva za MCP, hooks na mengine katika saraka zinazojitegemea zenye manifest `.claude-plugin/plugin.json`.

**Vipengele vinavyotumika: ujuzi, mawakala wasaidizi, seva za MCP, hooks (matukio 12 ya mzunguko wa maisha), amri za slash, mitindo ya matokeo, userConfig, vitegemezi, vituo, masoko**

**CLI commands**:

```
:plugin list                         # Orodhesha programu-jalizi zilizosakinishwa
:plugin install <source> [--scope]
:plugin install <name>@<marketplace>  # Sakinisha kutoka kwenye soko
:plugin remove <name>                # Ondoa usakinishaji
:plugin enable/disable <name>        # Washa au zima
:plugin marketplace add/remove/list  # Dhibiti masoko
:plugin init <name>                  # Unda muundo wa programu-jalizi mpya
```

Tazama nyaraka kamili kwa maelezo zaidi. [DEVELOP_PLUGIN.md](../src/uagent/docs/DEVELOP_PLUGIN.md)

### 🔄 Mwendelezo wa Kikao

- **Badilisha mtoa huduma katikati ya kipindi** kwa kutumia `UAGENT_PROVIDER` — historia ya mazungumzo huhifadhiwa.
- **Pakia tena vipindi vya awali** kwa kutumia `:load <index>` — endelea ulipoishia.

### 🛠 Zana 229

| Kitengo | Zana |
|---|---|
| **Uendeshaji wa Faili** | soma/andika/unda/futa/tafuta/grep/hash/zip, file_type, changanua_eml (faili.eml) |
| **Mtandao** | fetch_url, search_web, screenshot, browser_playwright |
| **Vyombo vya habari** | zalisha_picha, changanua_picha, img2img, hotuba_ya_sauti,nukuu_sauti |
| **Nyaraka** | Uchimbaji wa PDF/PPTX/DOCX/RTF/ODT, uchimbaji muundo wa Excel |
| **Utabiri** | Utabiri wa mfululizo wa muda na modeli 9 (AutoARIMA, Prophet, LightGBM, CatBoost, TimesFM, nk.), uteuzi wa modeli kiotomatiki, kizazi cha mpango, i18n |
| **Mawasiliano** | gmail_send, gmail_read, bluesky, discord_channel, team_webhook , **pybitchat** (BLE Mesh) — tazama [COMMUNICATION.md](COMMUNICATION.md) and [BITCHAT.md](BITCHAT.md)|
| **IoT** | BACnet、Modbus TCP、OPC UA、SwitchBot（Cloud + BLE）、ECHONET Lite、Matter、UPnP、reverse_geocode |
| **API za Wingu** | `aws_api`, `gcp_api`, `azure_api` — AWS, Google Cloud, and Azure API operations; write operations require explicit confirmation |
| **Zana za Usanidi** | git_ops, python_compile, lint_format, run_tets, db_query, **vielekezi 29 vya msimbo wa chanzo (idx family)** |
| **MCP** | Unganisha kwa seva za MCP za nje, orodhesha zana, tekeleza — [OAuth / Proxy guide](MCP_OAUTH_PROXY_GUIDE.md) |
| **A2A** | Mawasiliano ya wakala kwa wakala (pamoja na matukio mengine ya uag au seva zinazooana na A2A) |
| **Mfumo** | env vars, vipimo vya mfumo, saa, hesabu ya tarehe, uuid_gen, slugify, quantities ||
| **Chanzo Nav** | **zana 29 za idx** za Python, PHP, TypeScript, Java, C#, Dart, C/C++, Rust, Go, Swift, Kotlin, COBOL, VBA, LotusScript, Makefile — pata faharasa ya kitendakazi/darasa au ufafanuzi mahususi bila kusoma faili nzima |

#### Mapitio ya hazina na chanjo

- `git_review`: fanya muhtasari wa mabadiliko ya Git, faili hatari, watahiniwa wa majaribio, na matokeo ya siri bila kufichua thamani za siri.
- `security_scan`: changanua faili za hazina kwa ajili ya uwezekano wa siri na faili za usanidi hatari.
- `coverage_report` Rust, Go, Java/Kotlin, .NET, C/C++, Ruby, PHP, Swift, na Dart/Flutter.
- Vitegemezi vya chanjo vinavyokosekana vinaweza kusakinishwa kiotomatiki wakati utekelezaji unapoombwa; `dry_run` haisakinishi vifurushi kamwe.

Angalia [Zana za Uchanganuzi wa Hifadhi](REPOSITORY_TOOLS.md) kwa vigezo, pato na maelezo ya usalama.

### 🖥 Violesura 4 + Kiendelezi cha Msimbo wa VS

| Hali | Amri | Kusudi |
|---|---|---|
| **CLI** | `ua` | Uendeshaji wa haraka wa msingi wa terminal |
| **GUI** | `uagg` | UI ya Eneo-kazi kupitia tkinter |
| **Mtandao** | `ua` | Ufikiaji unaotegemea kivinjari |
| **Seva ya A2A** | `uaga` | Itifaki ya Agent2Agent kwa mawasiliano ya mawakala wengi |
| **Msimbo wa VS** | - | [Kiendelezi](VSCODE.md) yenye Paneli ya Gumzo, Eleza, Kirekebishaji, Rekebisha Hitilafu, na Mwonekano wa Mti wa Zana |

Tazama [VSCODE.md](VSCODE.md) kwa maelezo kuhusu kiendelezi cha Msimbo wa VS - usakinishaji, amri, vifungo muhimu na usanidi.

### 🏠 Kidhibiti cha Kifaa cha IoT

- **Jambo**: Ukaguzi wa kusoma pekee wa kidhibiti/daraja/topolojia ya kifaa

Tazama [IOT_USECASE.md](IOT_USECASE.md)

### 🎯 Soko la Ujuzi wa Wakala

`:ujuzi mp_search` ili kuvinjari [SkillsMP](https://skillsmp.com) na [ClawHub](https://clawhub.ai) kwa ujuzi wa jumuiya.
Sakinisha na upanue uwezo wa uag kwenye nzi.

### 🤖 Pilot-Otomatiki (`:otomati`)

uag inaweza **kufuata lengo kwa uhuru katika raundi nyingi za LLM**. Ni kamili kwa kazi ngumu, za hatua nyingi zinazohitaji uboreshaji wa kurudia.

- **Jinsi inavyofanya kazi**: Kila duru ina hoja kuu (Hatua A) ikifuatiwa na hukumu ya mhakiki (Hatua B) inayoamua "KIKAMILISHA au ENDELEA?"
- **Mtoa huduma sawa, API sawa**: Hukumu ya mkaguzi hutumia njia inayofanana ya msimbo kama hoja kuu - ikiwa ni pamoja na usaidizi wa API ya Majibu.
- **Mwamuzi tofauti LLM** (si lazima): Weka `UAGENT_AP_PROVIDER` ili utumie mtoaji/muundo tofauti kwa mkaguzi (k.m. tumia muundo wa bei nafuu zaidi kutathmini).
- **Ondoka wakati wowote**: Bonyeza kitufe cha `x` ili kuacha mara moja, hata jibu la katikati. Au acha mkaguzi aamue wakati lengo linatimizwa.
- **Inayoweza kusanidiwa**: `--max-raundi N` ili kudhibiti bajeti.

Tazama [README_AUTO.md](README_AUTO.md) kwa uhifadhi kamili.

### 🧩 Kidhibiti cha Jimbo la Kundi

uag inaweza kufuatilia maendeleo katika kazi za muda mrefu za faili nyingi. Wakati LLM inachakata faili nyingi, `batch_state` huendelea kuwa na orodha ya faili zinazosubiri, zilizokamilishwa na ambazo hazijafaulu kwenye diski. Kipindi kikimalizika au mzunguko ungeisha, kipindi kifuatacho kitaanza tena pale kiliposimama - hakuna kinachopotea.

### 🛡 Binadamu-katika-Kitanzi

`human_ask` huruhusu LLM kusitisha na kuomba uthibitisho wako kabla ya kutekeleza utendakazi wa uharibifu (kufuta faili, kubatilisha, amri za shell). Wewe kukaa katika udhibiti.

### 🛑 Katiza (kitufe cha c / kitufe cha Kusimamisha)

Komesha uzalishaji wa majibu ya LLM wakati wowote na urudishe amri ya kusitisha kwa LLM.

| Kiolesura | Jinsi ya kukatiza |
|---|---|
| **CLI** | Bonyeza kitufe cha `c` wakati wa utiririshaji wa LLM — jibu la sasa litasimama, na `"Sitisha"` hutumwa kama ujumbe wa mtumiaji ili LLM ijibu ipasavyo |
| **WEB UI** | Bofya kitufe chekundu **■ Acha** (kinaonekana kiotomatiki wakati wa uchakataji wa LLM) |
| **GUI ya Eneo-kazi** | Bofya kitufe chekundu **■** (huonekana kiotomatiki wakati wa uchakataji wa LLM) |

Ukatizaji hufanya kazi kama "sindano ya papo hapo": badala ya kutoa mimba tu, inalisha `"Acha"` kurudi kwenye LLM kama ujumbe wa mtumiaji, ikiiruhusu kuhitimisha au kukiri kukatizwa kwa uzuri.

Bonyeza kitufe cha `x` ili kuondoka kwenye hali ya majaribio ya kiotomatiki (angalia [README_AUTO.md](README_AUTO.md)).

### 🕵️ Uendeshaji wa Kivinjari na Kikaguzi cha Wavuti

Zana mbili za msingi za mwandishi wa kucheza:

- **browser_playwright**: Rekebisha vipindi halisi vya kivinjari — vinjari, bofya, jaza fomu, toa data, shughulikia mtiririko wa kurasa nyingi. Inafanya kazi bila kichwa au kichwa.
- **mkaguzi_wa_mwigizaji**: Rekodi mabadiliko ya kivinjari, nasa vijipicha na picha za skrini za DOM kwa kila hatua. Inafaa kwa kutatua mwingiliano wa wavuti au kukagua mabadiliko ya ukurasa kwa wakati.

### 🔄 Dynamic Tool Loading

`kitalogi_ya_zana` na `kupakia_zana` hukuwezesha kugundua na kuwasha zana wakati wa utekelezaji.
Hakuna haja ya kupakia kila kitu wakati wa kuanza - wezesha tu kile unachohitaji, wakati unakihitaji.

### 🦀 Rust Native Tools

`uuid_gen` na `slugify` zimetekelezwa katika Rust (kupitia PyO3) kwa utendaji bora.

### 🌐 i18n / L10n

Kiswahili / 简体中文 / 繁體中文 / 한국어 / Español / Français / Русский / na zaidi.
Weka `UAGENT_LANG` ili kubadili. Tazama [ADD_LOCALE.md](../src/uagent/docs/DEVELOP_I18N.md) ili kuongeza lugha mpya.

Tafsiri za README hii zinapatikana katika [docs/README.translations.md](README.translations.md).

### 🔒 Vigezo vya Mazingira Vilivyosimbwa kwa Njia Fiche

Hifadhi funguo na siri za API katika `.env.sec` — faili ya `.env` iliyosimbwa kwa njia fiche.
Dhibiti ukitumia `uag_envsec`.

## Usanidi & Maelezo

- **Vigeu vya mazingira**: [docs/ENVIRONMENT.md](ENVIRONMENT.md)
- **Mchawi wa kusanidi**: `python -m uagent.setup_cli`
- **env iliyosimbwa kwa njia fiche**: `uag_envsec` — simba kwa njia fiche `.env` kama `.env.sec`
- **API ya Majibu**: Weka `UAGENT_RESPONSES=1` kwa modi ya API ya Majibu (OpenAI/Azure/Bedrock/OpenRouter/Ollama/Alibaba/LM Studio/Sakana AI). Imewashwa kiotomatiki kwa Sakana AI (Fugu).
- **Hati za Msanidi**: [DEVELOP.md](../src/uagent/docs/DEVELOP.md)
- **Tool flow**: [TOOL_FLOW.md](../src/uagent/docs/TOOL_FLOW.md)
- **Vidokezo vidogo vya LLM**: [SLM_TIPS.md](SLM_TIPS.md)

## Falsafa ya Mradi

uag anatamani kuwa **AI yako, kwenye mashine yako, kwa masharti yako.**

- Hakuna utegemezi wa SaaS - inaendeshwa ndani ya nchi
- Hakuna kufuli kwa mtoa huduma - badilisha wakati wowote
- Hakuna kufuli kwa UI - CLI / GUI / Wavuti / A2A
- Hakuna kipengele cha kufuli - panua kwa zana na ujuzi

Uzoefu wa bure wa wakala wa AI, usio na kufuli kwa muuzaji.

### ✨ Unda Zana Zako Mwenyewe

[sw.md](TOOL_CREATOR_GUIDE.sw.md)
Tazama mwongozo wa hatua kwa hatua hapa.

## Kuchangia

Michango inakaribishwa! Ripoti za hitilafu, mapendekezo ya vipengele, uboreshaji wa hati, tafsiri na maombi ya kuvuta — yote yanathaminiwa.

- **Issues**: Fungua GitHub suala la hitilafu au maombi ya vipengele.
- **Maombi ya kuvuta**: Tengeneza fork ya hazina, fanya mabadiliko yako na uwasilishe PR. Tazama [DEVELOP.md](../src/uagent/docs/DEVELOP.md) kwa usanidi wa maendeleo na miongozo.

Realtime Sauti na AEC3

## Realtime hali ya sauti inaweza kutumia maikrofoni ya duplex kamili na ingizo/pato la spika. Ikiwa mandhari ya nyuma ya AEC3 haipo, uag husakinisha pywebrtc-audio kiotomatiki.

**Watoa huduma kwa wakati halisi**: OpenAI Realtime, Azure OpenAI GPT Realtime, Google Gemini Live, xAI Grok Voice na Amazon Bedrock Nova Sonic. SDK ya utiririshaji wa pande mbili wa Bedrock husakinishwa kiotomatiki tu Bedrock inapochaguliwa.

```bat
python scheck.py realtime
```

AEC3 hutumia mawimbi halisi ya maikrofoni (karibu) na sauti inayotumwa kwa spika (mbali). Washa uchunguzi unapochunguza matatizo ya sauti pekee.

```bat
set UAGENT_REALTIME_AUDIO_DEBUG=1
python scheck.py realtime
```

### OpenAI Realtime Function Calling

OpenAI Realtime inaweza kutumia muunganisho usio na kikomo wa Function Calling. Adapta ya sasa hufichua kitendakazi cha kusoma tu get_current_time kiotomatiki. Zana haribifu na vidhibiti vya kifaa vinahitaji orodha ya wazi ya ruhusa na mtiririko wa uthibitishaji. Grok katika muda halisi hutumia adapta tofauti na haitumii njia hii OpenAI mahususi Function Calling.
