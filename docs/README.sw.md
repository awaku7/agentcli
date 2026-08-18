<p align="center">
 <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="720">
</p>

<h1 Universal_Icenter —PH_2 Gateway</h1>

<p align="center">
 <b>U</b>zima <b>A</b>I <b>G</b>ateway — Mazingira yako, uhuru wako.
</p>

<p align="center">
 Utendaji wa faili / Utafutaji wa Wavuti / Utoaji wa picha na uchanganuzi / PDF_T_1br / Udhibiti wa faili / PDF_T_1 Watoa huduma 24 / UI 3 / Utekelezaji wa zana Sambamba / Soko la Ujuzi wa Mawakala
</p>

<p align="center">
 <a href="https://github.com/awaku7/agentcli">GitHub</a>
 ·
 <a href="https://py/Pypi.org"<a href="https://py/Pypi.org" ·
 <a href="https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md">Soma hili katika lugha yako</a>
</p>

______________________________________________________________________

## Kwa nini uag?

**Jiepushe na kufuli kwa muuzaji.** Wasaidizi wengi wa AI hukuunganisha na mtoa huduma mahususi au huduma ya wingu. uag ni tofauti.

- **Inaendeshwa karibu nawe** kwenye mashine yako. Data yako itasalia nawe (isipokuwa simu API unazopiga).
- **Uhuru wa mtoa huduma**: OpenAI, Claude, Gemini, DeepSeek, Ollama, Azure, Bedrock, Novita, HuggingFace... Watoa huduma 24, zote zinapatikana kwa kutumia kiolesura kimoja. Badilisha kati yao kwa kusanidi upya vigezo vya mazingira — hakuna kusakinisha tena, hakuna uhamishaji.
- **zana 222**: Faili I/O, utafutaji wa wavuti, utengenezaji wa picha, Gmail, BLE kuchanganua kifaa, MCP muunganisho wa seva — **130 zimewekwa alama sawia-salama** (hadi AG 8 kutekelezwa kwa wakati mmoja kupitia mtandao wa URKENT_PARO, URKENT_WORKERS). LLM inapopiga simu za zana nyingi kwa wakati mmoja, uag huzilinganisha kiotomatiki.
- **UI 3 + A2A**: CLI, GUI, Wavuti, na itifaki ya Wakala kwa Wakala. Injini sawa, kiolesura chochote.
- **IoT tayari**: SwitchBot, ECHONET Lite, Matter, UPnP — dhibiti vifaa vyako vya nyumbani kupitia AI.
- **Ujuzi wa Wakala**: Sakinisha ujuzi uliojengwa na jumuiya kutoka sokoni. Ongeza uag bila kikomo.

uag ni **msaidizi wako wa AI kwa masharti yako**. Haijafungamana na mtoa huduma, haijafungwa kwenye kiolesura, haijafungwa kwenye jukwaa.

## Anza kwa Haraka

```bash
pip install uag
uag
```

Katika uzinduzi wa kwanza, mchawi wa usanidi hukupitisha kwenye usanidi wa mtoa huduma.
Angalia. [docs/ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/docs/ENVIRONMENT.md) kwa anuwai zote za mazingira.

## Matumizi ya Kompyuta

Matumizi ya Kompyuta ni ya kuchagua kuingia na yanatumia Playwright wakati wa utekelezaji wa kivinjari
na muda wa matumizi wa eneo-kazi. Inapowashwa, saa zote mbili za utekelezaji huundwa na kusajiliwa;

```bat
weka UAGENT_COMPUTER_USE=1
```

endesha desktop

````
 juu ya eneo-kazi. Rasilimali za muda 
hufungwa pamoja wakati wa kutoka kwa kawaida, `Ctrl-C`, na kuzima kwa mchakato. Weka
`UAGENT_COMPUTER_HEADLESS=1` kwa majaribio ya CI au moshi kulingana na kivinjari.
Angalia [hati/COMPUTER_USE_IMPLEMENTATION.md](docs/COMPUTER_USE_IMPLEMENTATION.md)
kwa ujumuishaji na maelezo ya usalama.

## Sauti ya Wakati Halisi na AEC3

Modi ya sauti ya wakati halisi inaweza kutumia OpenAI Wakati Halisi, Azure OpenAI GPT Wakati Halisi, xAI Grok Sauti API, Google Gemini Multimodal Live API, na Sonic Inayotumia maikrofoni na Noduva ya Amazon na Noduck kamili ya Amazon. Mandhari ya nyuma ya `pywebrtc-audio` AEC3 inayohitajika husakinishwa kiotomatiki, na SDK ya hiari ya Bedrock ya kutiririsha njia mbili itasakinishwa kiotomatiki tu wakati mtoa huduma wa Bedrock amechaguliwa:

``` bash
python scheck.py wakati halisi
````

kupokea kipaza sauti kwa mkono (`kipaza sauti cha AEC3) na kupokea sauti ya sauti. mzungumzaji (`mbali\`) ili msaidizi aweze kusikiliza anapozungumza. Washa uchunguzi unapochunguza maswala ya sauti pekee:

```bat
weka UAGENT_REALTIME_AUDIO_DEBUG=1
python scheck.py realtime
```

### OpenAI Upigaji simu wa Utendaji Wakati Halisi

\_\_Uunganisho wa Usalama wa Muda halisi. Adapta ya sasa ya wakati halisi hufichua kiotomatiki `get_current_time` ya kusoma tu. Zana haribifu na vidhibiti vya kifaa havifichuliwi bila orodha ya wazi ya ruhusa na mtiririko wa uthibitishaji. Grok wakati halisi hutumia adapta tofauti na haitumii njia hii mahususi ya kupiga simu ya OpenAI.

## Sifa

### 🧠 Usanifu wa Watoa Huduma nyingi

OpenAI / PFN (PLaMo) / Azure / Bedrock / OpenRouter / Ollama / llama.cpp / Gemini / Vertex AI / Claude / Grok / NVIDIA / Novita ZINGA / AIbaba / AIbaba Deep Cloud (Qwen) / KIMI (Moonshot AI) / Xiaomi MiMo / LM Studio / MiniMax / Sakana AI (Fugu) / SAKURA AI Engine / Pamoja AI / Vercel AI Gateway
Watoa huduma wote wanashiriki seti sawa ya zana na kiolesura. Badili kwa kuweka `UAGENT_PROVIDER` — hakuna mabadiliko ya msimbo, hakuna usakinishaji tofauti.

#### Ollama na llama.cpp

Ollama na llama.cpp ni watoa huduma tofauti. Ollama hutumia huduma yake mwenyewe na usimamizi wa kielelezo, huku `llama.cpp` inaunganishwa na `llama-server` OpenAI- sehemu ya mwisho inayooana:

```bash
# Ollama
UAGENT_PROVIDER=ollama
UAGENT_OLLAMA_BASE_URL=http://localhost:11434/v1
UAGENT_OLLAMA_DEPNAME=llama3.1
# llama.cpp / llama-server
UAGENT_PROVIDER=llama_cpp
UAGENT_LLAMA_CPP_BASE_URL=http://localhost:8080/v1
UAGENT_LLAMA_CPP_DEPNAME=local-model
UAGENT_LLAMA_CPP_API_KEY``matumizi
 anatumia `map
. Njia inayolingana na ukamilishaji. Weka `UAGENT_RESPONSES=0` isipokuwa seva mbadala inayooana haijasanidiwa.
### ⚡ Utekelezaji wa Zana Sambamba
Wakati LLM inapoomba zana nyingi kwa wakati mmoja, uag **husawazisha kiotomatiki**. `ThreadPoolExecutor` (nyuzi 8 kwa chaguo-msingi; weka `UAGENT_PARALLEL_WORKERS` ili kubadilisha).
**Mfano**: Uliza "Angalia hali ya hewa katika herufi kubwa za Nordic" → LLM huwasha `search_web` × nchi 5 → matokeo yote ya utafutaji 5 yanaendeshwa kwa usawa → kusanya matokeo ya fungu moja la utafutaji → kusanya matokeo ya fungu moja la utafutaji. inayofafanua `TOOL_SPEC` (ambayo kwa sasa ni 222, ikijumuisha zana 2 zinazoungwa mkono na kutu katika `src/uagent/tools_rust/`). `http_request` hutumia usalama nyeti wa mbinu: simu za `GET`/`HEAD`/`OPTIONS` zinaweza kuendeshwa kwa sambamba, huku mbinu za kuandika zikisalia mfululizo.
Zana za kusoma pekee (utaftaji wa faili, kukokotoa heshi, kuorodhesha saraka, tafsiri, hoja za DB, n.k.) zimesawazishwa kwa ukali. Inaoana)
uagent inatekeleza **Claude mfumo jalizi unaooana na Msimbo**. Huingiza ujuzi wa kifurushi, mawakala, MCP seva, ndoano, na zaidi katika saraka zinazojitosheleza kwa kutumia faili ya maelezo ya `.claude-plugin/plugin.json`.
**Vipengele vinavyotumika**: Ujuzi, Mawakala Ndogo, MCP seva, Hooks (12 za mzunguko wa maisha, Mitindo ya Mtumiaji, Mitindo ya Kutegemea, Mitindo ya Utegemezi), Slash Vituo, Marketplaces
**CLI amri**:
```

:orodha ya programu-jalizi # Orodhesha programu-jalizi zilizosakinishwa
:isakinisha programu-jalizi <source> [--scope] # Sakinisha (dir/zip/git/http)
:plugin install <name>@<marketplace> # Sakinisha kutoka sokoni
me> #Sakinisha kutoka sokoni
me> #plugin Geuza
:sokoni jalizi ongeza/ondoa/orodhesha # Dhibiti soko
:ingilizi ya programu-jalizi <jina> # Programu-jalizi mpya ya kiunzi

````
Angalia [DEVELOP_PLUGIN.md](src/uagent/docs/DEVELOP_PLUGIN.🏎#Sehemu kamili ya####) Muendelezo
- **Badilisha watoa huduma katika kipindi cha katikati** ukitumia `UAGENT_PROVIDER` — historia ya mazungumzo imehifadhiwa.
- **Pakia upya vipindi vilivyopita** kwa `:load <index>` — endelea ulipoishia.
- **Uakibishaji wa matokeo ya zana** huepuka kutekeleza tena kusikohitajika wakati simu sawa ya kifaa inaporudiwa #2|9| Kitengo | Zana |
|---|---|
| **Uendeshaji wa Faili** | soma/andika/unda/futa/tafuta/grep/hash/zip, aina_ya faili, changanua_eml (faili.eml), `path_alias` |
| **Mtandao** | fetch_url, search_web, screenshot, browser_playwright, `url_lakas`, `public_transit_rout` ([mwongozo](docs/PUBLIC_TRANSIT_ROUTE.md)) |
| **Vyombo vya habari** | tengeneza_picha, changanua_picha, img2img, audio_speech, audio_transcribe |
| **Nyaraka** | Uchimbaji wa PDF/PPTX/DOCX/RTF/ODT, Uchimbaji muundo wa Excel |
| **Utabiri** | Utabiri wa mfululizo wa saa wenye miundo 9 (AutoARIMA, Prophet, LightGBM, CatBoost, TimesFM, n.k.), uteuzi wa kielelezo kiotomatiki, kutengeneza njama, i18n |
| **Mawasiliano** | gmail_send, gmail_read, bluesky, discord_channel, team_webhook, **pybitchat** (BLE Mesh) — tazama [COMMUNICATION.md](https://github.com/awaku7/agentcli/blob/main/docs/COMMUNICATION.md) na [BITCHAT.md](https://github.com/awaku7/agentcli/blob/main/docs/BITCHAT.md) |
| **IoT** | SwitchBot (Wingu + BLE), ECHONET Lite, Matter, UPnP, reverse_geocode |
| **API za Wingu** | `aws_api`, `gcp_api`, `azure_api` — shughuli za kawaida za AWS, Google Cloud, na Azure API; shughuli za kuandika zinahitaji uthibitisho dhahiri |
| **Zana za Usanidi** | workspace_status, git_ops, git_review, security_scan, coverage_report, python_compile, lint_format, run_tets, db_query, **vielekezi 29 vya msimbo wa chanzo (idx family)** |
| **MCP** | Unganisha kwenye seva za MCP za nje, zana za kuorodhesha, tekeleza — [OAuth / Mwongozo wa Proksi](hati/MCP_OAUTH_PROXY_GUIDE.md) |
| **A2A** | Mawasiliano kati ya wakala kwa wakala (pamoja na matukio mengine uag au seva zinazooana A2A) |
| **Mfumo** | env vars, vipimo vya mfumo, muda, hesabu ya tarehe, [quantities](docs/QUANTITIES.md), [geodesic_distance](docs/GEODESIC_DISTANCE.md), uuid_gen, slugify |
| **Chanzo Nav** | **zana 29 za idx** za Python, PHP, TypeScript, Java, C#, Dart, C/C++, Rust, Go, Swift, Kotlin, COBOL, VBA, LotusScript, Makefile - pata faharasa ya kitendakazi/darasa au ufafanuzi mahususi bila kusoma faili nzima |
#### Mapitio ya hazina na chanjo
-`, `nafasi ya kazi ya ripoti inabadilisha nafasi ya kazi hali ya kusawazisha, muda wa utekelezaji wa Python, na vialamisho vya kawaida vya mradi bila kurekebisha faili.
- `git_review`: fanya muhtasari wa mabadiliko ya Git, faili hatari, watahiniwa wa majaribio, na matokeo ya siri bila kufichua thamani za siri.
- `security_scan`: changanua faili za hazina kwa ajili ya uwezekano wa siri na faili za usanidi hatari kwa ajili ya uendeshaji wa faili za usanidi. TypeScript/JavaScript, Rust, Go, Java/Kotlin, .NET, C/C++, Ruby, PHP, Swift, na Dart/Flutter.
- Vitegemezi vya chanjo vinavyokosekana vinaweza kusakinishwa kiotomatiki wakati utekelezaji unapoombwa; `dry_run` haisakinishi vifurushi kamwe.
Angalia [Zana za Uchambuzi wa Hifadhi](docs/REPOSITORY_TOOLS.md) kwa vigezo, matokeo na maelezo ya usalama.
Angalia [Lakabu za Njia na URL](hati/PATH_URL_ALIASES.md) kwa kufupisha vielelezo vya faili vinavyorudiwa#4 Violesura + VS Kiendelezi cha Msimbo
| Hali | Amri | Kusudi |
|---|---|---|
| **CLI** | `uag` | Uendeshaji wa haraka wa msingi wa terminal |
| **GUI** | `uagg` | UI ya Eneo-kazi kupitia tkinter |
| **Mtandao** | `ua` | Ufikiaji unaotegemea kivinjari |
| **A2A Seva** | `uaga` | Itifaki ya Agent2Agent kwa mawasiliano ya mawakala wengi |
| **Msimbo wa VS** | - | [Kiendelezi](https://github.com/awaku7/agentcli/blob/main/docs/VSCODE.md) iliyo na Paneli ya Gumzo, Eleza, Kirekebishaji, Rekebisha Hitilafu, na Mwonekano wa Mti wa Zana |
Angalia [VSCODE.md](https://github.com/awaku7/Vmadetails/VD Upanuzi wa Msimbo wa VS — usakinishaji, amri, viunganishi muhimu, na usanidi.
### 🏠 Udhibiti wa Kifaa cha IoT
- **BACnet**: Kusoma/kuandika vifaa vya BACnet/IP (HVAC, taa, mita za umeme). Usajili wa COV kwa arifa zinazotumwa na programu hata wakati huitumii
- **Modbus TCP**: Soma/andika rejista za kushikilia/kuingiza na koili. Ufuatiliaji wa mabadiliko kulingana na kura
- **OPC UA**: Vinjari nafasi ya anwani, vibadilishi vya kusoma/kuandika, jisajili ili upate mabadiliko ya data
- **SwitchBot**: Kidhibiti cha bechi ya Wingu & BLE scan/control. Usajili unaotegemea upigaji kura
- **ECHONET Lite**: Gundua, dhibiti na ujiandikishe kupokea arifa za INF kutoka kwa vifaa vya nyumbani (AC, taa, hita za maji, n.k.)
- **Matter**: Udhibiti wa kusoma/andika + sifa kwa ufuatiliaji wa mabadiliko ya hali
- **UPnP**: Ugunduzi wa mlango wa kifaa & IGD [IOT_USECASE.md](https://github.com/awaku7/agentcli/blob/main/docs/IOT_USECASE.md)
### 🎯 Soko la Ujuzi wa Wakala
`:ujuzi mp_search` ili kuvinjari [SkillsMP](https://wclai/Skills. kwa ujuzi wa jumuiya.
Sakinisha na upanue uwezo wa uag kwa njia ya ndege.
### 🤖 Majaribio ya Kiotomatiki (`:oto`)
uag yanaweza **kufuata lengo kiotomatiki katika raundi nyingi LLM**. Ni kamili kwa kazi ngumu, za hatua nyingi zinazohitaji uboreshaji unaorudiwa.
- **Jinsi inavyofanya kazi**: Kila awamu ina swali kuu (Hatua A) ikifuatwa na hukumu ya mkaguzi (Hatua B) ambayo itaamua "KIKAMILISHA au ENDELEA?"
- **Mtoa huduma sawa, API**: Hukumu ya mkaguzi hutumia njia ya msimbo sawa kama hoja kuu - ikiwa ni pamoja na Majibu __tejaji*PH_2 usaidizi wa Majibu __tejaji*PH_2. (si lazima): Weka `UAGENT_AP_PROVIDER` ili kutumia mtoaji/muundo tofauti kwa mkaguzi (k.m. tumia muundo wa bei nafuu kutathmini).
- **Ondoka wakati wowote**: Bonyeza kitufe cha F11 ili kuacha mara moja, hata jibu la katikati. Au mruhusu mhakiki aamue wakati lengo litakapotimizwa.
- **Inaweza kusanidiwa**: `--raundi-ya juu zaidi N` ili kudhibiti bajeti.
Angalia [README_AUTO.md](https://github.com/awaku7/agentcli/blob/main/docs/README_AUTO.####Batch ⏧#Bajeti kamili ya hati Msimamizi
uag anaweza kufuatilia maendeleo katika majukumu ya muda mrefu ya faili nyingi. LLM inapochakata faili nyingi, `batch_state` hudumisha orodha ya faili ambazo hazijakamilika, zilizokamilika na ambazo hazijakamilika kwenye diski. Kipindi kikiisha au muda wa mzunguko kuisha, mwendo unaofuata utaanza tena kutoka pale kiliposimama - hakuna kitakachopotea.
### 🛡 Human-in-the-Loop
`human_ask` huruhusu LLM kusitisha na kuomba uthibitisho wako kabla ya kutekeleza utendakazi wa uharibifu (kufuta faili, kubatilisha, amri za shell). Wewe endelea kudhibiti.
### 🛑 Katiza (kitufe cha c-c / kitufe cha Komesha)
Simamisha LLM uundaji wa majibu wakati wowote na urudishe amri ya kusitisha kwenye LLM.
| Kiolesura | Jinsi ya kukatiza |
|---|---|
| **CLI** | Bonyeza kitufe cha F12 wakati wa LLM utiririshaji — jibu la sasa litakoma, na `"Simamisha"` hutumwa kama ujumbe wa mtumiaji kwa hivyo LLM ijibu ipasavyo |
| **WEB UI** | Bofya kitufe chekundu **■ Sitisha** (kinaonekana kiotomatiki wakati LLM uchakataji) |
| **GUI ya Eneo-kazi** | Bofya kitufe chekundu **■** (huonekana kiotomatiki wakati wa LLM kuchakata) |
Kikatizi hufanya kazi kama "sindano ya papo hapo": badala ya kuacha tu, hurudisha `"Acha"` hadi LLM kama ujumbe wa mtumiaji, na kuuruhusu kuhitimisha au kukiri kukatizwa kwa ustadi.
Bonyeza kitufe cha 'ona otomatiki' ili kuondoka kwenye kitufe cha F11. [README_AUTO.md](https://github.com/awaku7/agentcli/blob/main/docs/README_AUTO.md)).
### 🕵️ Kivinjari Kiotomatiki na Kikaguzi cha Wavuti
Vipindi viwili vya Playwright vinavyosaidiana, kivinjari**:_-chezea kivinjari kiotomatiki*:_-chezea kiotomatiki kivinjari bofya, jaza fomu, toa data, shughulikia mtiririko wa kurasa nyingi. Hufanya kazi bila kichwa au kichwa.
- **mkaguzi_wa_mwigizaji**: Rekodi mabadiliko ya kivinjari, nasa vijipicha vya DOM na picha za skrini kwa kila hatua. Inafaa kwa utatuzi wa mwingiliano wa wavuti au mabadiliko ya ukurasa wa ukaguzi kwa wakati.
### 🔄 Dynamic Tool Loading
`tool_catalog` na `tool_load` hukuwezesha kugundua na kuwezesha zana wakati wa utekelezaji.
Hakuna haja ya kupakia kila kitu wakati wa kuanza - wezesha unachohitaji pekee, unapokihitaji.
#### Ruid_Updative` `slugify` inatekelezwa katika Rust (kupitia PyO3) kwa ajili ya utendakazi.
Zinapakia moja kwa moja kutoka kwa `.pyd` iliyojengwa awali — **hakuna `pip install` inayohitajika**.
Wasanidi wa nje wanaweza pia kusafirisha zana zinazotokana na kutu: weka `.pyd` kando ya kanga `.py`, tumia `pyd(_`st) `uagent.tools.rust_helper`, na
watumiaji hupata zana bila utegemezi wowote wa ziada. Tazama
[TOOL_CREATOR_GUIDE.md](https://github.com/awaku7/agentcli/blob/main/TOOL_CREATOR_GUIDE.md).
### 🌐 i18n / L10n
日本語 / Kiingereza / 简体中文 / 繁体中文 / 繁体中文 / Français / Русский / na zaidi.
Weka `UAGENT_LANG` ili kubadili. Tazama [ADD_LOCALE.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/ADD_LOCALE.md) ili kuongeza lugha mpya.
Tafsiri za README hii zinapatikana katika [docs/README.translations.md](https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md).
### 🔒 Vigezo vya Mazingira Vilivyosimbwa
Hifadhi API funguo na siri katika `.env.`sec file` — env. `uag_envsec`.
## Usanidi na Maelezo

- **Vigezo vya mazingira**: [docs/ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/docs/ENVIRONMENT.md)
- **Mchawi wa kusanidi**: `python_`ncrypted_ph. env**: `uag_envsec` — simba kwa njia fiche `.env` kama `.env.sec`
- **Majibu API**: Weka `UAGENT_RESPONSES=1` kwa Majibu API modi (OpenAI/Azure/Bedrock/OpennaIOLM Studio/Alibaba/Alibaba Studio/Alibaba). Imewashwa kiotomatiki kwa Sakana AI (Fugu).
- **Hati za Msanidi**: [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)
- **Mtiririko wa zana**: [TOOL_FLOW.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/TOOL_FLOW.md) — jinsi zana zinavyotumwa kwa LLMs (kinyago cha aina, katalogi_ya_zana, GPT-5.4+ utaftaji_wa_zana asilia)
_* **Vidokezo_vidogo 5 [SLM_TIPS.md](https://github.com/awaku7/agentcli/blob/main/docs/SLM_TIPS.md)

## Falsafa ya Mradi

uag inatamani kuwa **AI yako, kwenye mashine yako, kulingana na masharti yako.**

- Hakuna utegemezi wa SaaS — inaendeshwa ndani ya nchi
- Hakuna kufuli kwa mtoa huduma — badilisha wakati wowote
- Hakuna kifungia cha UI kwa kutumia kipengele cha CLI / GUI / Wavuti / ___PH ujuzi

Utumiaji wa wakala wa AI bila malipo, usio na kufuli kwa muuzaji.

### ✨ Unda Zana Zako Mwenyewe

Kuandika zana mpya ya uag ni rahisi - unda faili `.py` moja na
`TOOL_SPEC` na ``endesha, weka chombo() `UAGENT_EXTERNAL_TOOLS_DIR`, na
inapatikana mara moja. Kwa wasanidi wa kutu, safirisha `.pyd` iliyojengwa awali ikiwa na
 utegemezi sifuri zaidi kwa watumiaji.

Angalia [TOOL_CREATOR_GUIDE.md](https://github.com/awaku7/agentcli/blob/main/TOOL_CREATOR_GUIDE.md)

 kwa hatua kwa hatua.## Kuchangia

Michango inakaribishwa! Ripoti za hitilafu, mapendekezo ya vipengele, uboreshaji wa hati, tafsiri na maombi ya kuvuta — yote yanathaminiwa.

- **Masuala**: Fungua GitHub suala la hitilafu au maombi ya kipengele.
- **Vuta maombi**: Fanya repo, fanya mabadiliko yako na uwasilishe PR. Angalia [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md) kwa usanidi na miongozo ya usanidi.
- **Tafsiri**: Tafsiri za README na nyongeza za lugha zinakaribishwa. Angalia [ADD_LOCALE.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/ADD_LOCALE.md).
- **Zana na Ujuzi**: Programu-jalizi mpya za zana na Ujuzi wa Wakala zinaweza kuchangiwa kupitia soko.#be#
 Ukaguzi wa Maendeleo PR)

Sakinisha vitegemezi vya majaribio pekee kwanza. Huwekwa nje ya muda wa utekelezaji
orodha ya utegemezi:

```bash
python -m pip install -e ".[test]"
python -m pip install black ruff
````

Endesha ukaguzi sawa na GitHub Vitendo kabla ya kusukuma ruff -`py`bansh
︎ﻠ tests
python -m black --angalia src tests
python scripts/tool_json_i18n_batch.py status
python -m pytest -q .

````

Kwa marudio ya haraka ya ndani, fanya majaribio yaliyoathiriwa pekee:
test
`` vipimo/<affected_eneo>
``

Ukaguzi wa ziada inapofaa:

```bash
python -m py_compile src/uagent/
mypy src/uagent
````

Baada ya kuhariri \`\`s. scripts/compile_locales.py`na`scripts za chatu/po_qc_summary.py\`.

Sera ya muda wa utekelezaji (maelezo katika [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOPed) §1 wasaidia. `sys.toka`; seva pangishi ya zana hugeuza zana `SystemExit`/`Exception` kuwa mifuatano ya hitilafu ili zana moja haiwezi kuua mchakato. Njia za kutoka kwa kutofaulu kwa uanzishaji hubaki kuwa za kukusudia.

## Vigezo vya usanifu na uendeshaji

Angalia [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) kwa mikataba ya kudumu inayojumuisha A2A lifecycle, miktadha ya I18N, usakinishaji wa hiari wa utegemezi, usalama wa zana, uwezo wa mtoa huduma, mipaka ya uaminifu ya OAuth, ⎏ uthibitishaji wa matukio yaliyopangwa.## Enterprise Policy Engine

Sera za kiwango cha shirika za zana, watoa huduma, vitambulisho, seva MCP, mitandao, ujuzi na programu jalizi zinatumika. Weka `UAGENT_POLICY_FILE` kuwa faili ya sera ya JSON/YAML; tazama [hati/ENTERPRISE_POLICY.md](hati/ENTERPRISE_POLICY.md) kwa mifano ya usanidi, majukumu, uthibitishaji, na orodha za vibali.

### Urejeshaji na upangaji wa muda wa kukimbia

Angalia [RESTART_RECOVERY.md](COVERY.START_RE) [DAG_SCHEDULER.md](hati/DAG_SCHEDULER.md) / [MULTI_AGENT_RUNTIME.md](docs/MULTI_AGENT_RUNTIME.md) kwa urejeshaji wa kudumu, utekelezaji wa kufahamu utegemezi, upangaji wa wakala wengi, na matumizi ya mbali A2A .\_PH_1 [DISTRIBUTED_COORDINATION.md](hati/DISTRIBUTED_COORDINATION.md) kwa ajili ya uratibu wa ukodishaji wa kiongozi wa wakati unaoshirikiwa.
