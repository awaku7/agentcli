<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="720">
</p>

<h1 align="center">uag - Universal AI Gateway</h1>

<p align="center">
  <b>U</b>niversal <b>A</b>I <b>G</b>ateway — Your environment, your freedom.
</p>

<p align="center">
  File ops / Web search / Image generation &amp; analysis / PDF &amp; Excel extraction / IoT control / MCP integration<br>
  15+ providers / 3 UIs / Parallel tool execution / Agent Skills marketplace
</p>

<p align="center">
  <a href="https://github.com/awaku7/agentcli">GitHub</a>
  ·
  <a href="https://pypi.org/project/uag/">PyPI</a>
  ·
  <a href="https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md">Read this in your language</a>
</p>

---

##Kwanini uag?

**Jiepushe na kufuli kwa muuzaji.** Wasaidizi wengi wa AI hukufungamanisha na mtoa huduma mahususi au huduma ya wingu. uag ni tofauti.

- ** Huendesha ndani ** kwenye mashine yako. Data yako itasalia nawe (isipokuwa simu za API unazopiga).
- **Uhuru wa mtoa huduma**: OpenAI, Claude, Gemini, DeepSeek, Ollama, Azure, Bedrock, HuggingFace... 15+ watoa huduma, wote wanaweza kufikiwa kutoka kwa kiolesura kimoja. Badilisha kati yao kwa kusanidi upya anuwai za mazingira - hakuna kusakinisha tena, hakuna uhamiaji.
- **Zana 131**: Faili ya I/O, utafutaji wa wavuti, kutengeneza picha, Gmail, kuchanganua kifaa cha BLE, muunganisho wa seva ya MCP — **76 ni salama sambamba** (hadi 8 hutekelezwa kwa wakati mmoja kupitia mkusanyiko wa mazungumzo, inaweza kusanidiwa kupitia `UAGENT_PARALLEL_WORKERS`). Wakati LLM inapiga simu za zana nyingi mara moja, uag huzilinganisha kiotomatiki.
- **UI 3 + A2A**: CLI, GUI, Wavuti, na itifaki ya Wakala kwa Wakala. Injini sawa, interface yoyote.
- **IoT tayari**: SwitchBot, ECHONET Lite, Matter, UPnP - dhibiti vifaa vyako vya nyumbani kupitia AI.
- **Ujuzi wa Wakala**: Sakinisha ujuzi uliojengwa na jamii kutoka sokoni. Panua uag bila mwisho.

uag ni **msaidizi wako wa AI kwa masharti yako**. Haijafungwa kwa mtoa huduma, haijafungwa kwenye kiolesura, haijafungwa kwenye jukwaa.

## Anza Haraka

```bash
pip install uag
uag
```

Katika uzinduzi wa kwanza, mchawi wa kusanidi hukutembeza kupitia usanidi wa mtoa huduma.
Angalia [ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md) kwa anuwai zote za mazingira.

## Vipengele

### 🧠 Usanifu wa Watoa Huduma nyingi

OpenAI / Azure / Bedrock / OpenRouter / Ollama / Gemini / Vertex AI / Claude / Grok / NVIDIA / DeepSeek / Z.AI (Zhipu AI) / HuggingFace / Alibaba Cloud (Qwen) / KIMI (Moonshot AI) / Xiaomi MiMo / LM Studio / MiniMax / **Sakana AI*

Watoa huduma wote wanashiriki zana sawa na kiolesura. Badili kwa kuweka `UAGENT_PROVIDER` — hakuna mabadiliko ya msimbo, hakuna usakinishaji tofauti.

### ⚡ Utekelezaji wa Zana Sambamba

Wakati LLM inaomba zana nyingi kwa wakati mmoja, uag **inazilinganisha kiotomatiki**.
Zana 76 zimewekwa alama `x_parallel_safe` na hutekelezwa kwa wakati mmoja kupitia `ThreadPoolExecutor` (nyuzi 8 kwa chaguomsingi; weka `UAGENT_PARALLEL_WORKERS` ili kubadilisha).

**Mfano**: Uliza "Angalia hali ya hewa katika herufi kubwa za Nordic" → Mioto ya LLM `search_web` × nchi 5 → utafutaji wote 5 unakwenda sambamba → matokeo yaliyokusanywa katika kundi moja.

Zana za kusoma pekee (utaftaji wa faili, hesabu ya heshi, orodha ya saraka, tafsiri, hoja za DB, n.k.) zimesawazishwa kwa ukali.

### 🔄 Mwendelezo wa Kikao

- **Switch providers mid-session** with `UAGENT_PROVIDER` — conversation history is preserved.
- **Reload past sessions** with `:load <index>` — pick up where you left off.
- **Tool result caching** avoids redundant re-execution when the same tool call repeats.

### 🛠 Zana 131

| Kitengo | Zana |
|---|---|
| **Uendeshaji wa Faili** | soma/andika/unda/futa/tafuta/grep/hash/zip, changanua_eml (faili.eml) |
| **Mtandao** | fetch_url, search_web, screenshot, browser_playwright |
| **Vyombo vya habari** | zalisha_picha, changanua_picha, img2img, hotuba_ya_sauti,nukuu_sauti |
| **Nyaraka** | Uchimbaji wa PDF/PPTX/DOCX/RTF/ODT, uchimbaji muundo wa Excel |
| **Mawasiliano** | gmail_send, gmail_read, bluesky, discord_channel, team_webhook — tazama [COMMUNICATION.md](https://github.com/awaku7/agentcli/blob/main/docs/COMMUNICATION.md) |
| **IoT** | SwitchBot (Wingu + BLE), ECHONET Lite, Matter, UPnP |
| **Zana za Usanidi** | git_ops, python_compile, lint_format, run_tets, db_query, **vielekezi 13 vya msimbo wa chanzo (idx family)** |
| **MCP** | Unganisha kwa seva za MCP za nje, orodhesha zana, tekeleza |
| **A2A** | Mawasiliano ya wakala kwa wakala (pamoja na matukio mengine ya uag au seva zinazooana na A2A) |
| **Mfumo** | env vars, vipimo vya mfumo, saa, hesabu ya tarehe |
| **Chanzo Nav** | **zana 13 za idx** za Python, PHP, TypeScript, Java, C#, Dart, C/C++, Rust, Go, Swift, Kotlin, COBOL — pata faharasa ya kitendakazi/darasa au ufafanuzi mahususi bila kusoma faili nzima |

### 🖥 Violesura 4 + Kiendelezi cha Msimbo wa VS

| Hali | Amri | Kusudi |
|---|---|---|
| **CLI** | `ua` | Uendeshaji wa haraka wa msingi wa terminal |
| **GUI** | `uagg` | UI ya Eneo-kazi kupitia tkinter |
| **Mtandao** | `ua` | Ufikiaji unaotegemea kivinjari |
| **Seva ya A2A** | `uaga` | Itifaki ya Agent2Agent kwa mawasiliano ya mawakala wengi |
| **Msimbo wa VS** | - | [Kiendelezi](https://github.com/awaku7/agentcli/blob/main/VSCODE.md) yenye Paneli ya Gumzo, Eleza, Kirekebishaji, Rekebisha Hitilafu, na Mwonekano wa Mti wa Zana |

Tazama [VSCODE.md](https://github.com/awaku7/agentcli/blob/main/VSCODE.md) kwa maelezo kuhusu kiendelezi cha Msimbo wa VS - usakinishaji, amri, vifungo muhimu na usanidi.

### 🏠 Kidhibiti cha Kifaa cha IoT

- **SwitchBot**: Udhibiti wa bechi ya wingu & skanisho/udhibiti wa BLE
- **ECHONET Lite**: Gundua na udhibiti vifaa vya nyumbani (AC, taa, hita za maji, n.k.) kwenye mtandao wa ndani
- **Jambo**: Ukaguzi wa kusoma pekee wa kidhibiti/daraja/topolojia ya kifaa
- **UPnP**: Ugunduzi wa kifaa na usambazaji wa mlango wa IGD

Tazama [IOT_USECASE.md](https://github.com/awaku7/agentcli/blob/main/IOT_USECASE.md)

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

Tazama [README_AUTO.md](https://github.com/awaku7/agentcli/blob/main/README_AUTO.md) kwa uhifadhi kamili.

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

Bonyeza kitufe cha `x` ili kuondoka kwenye hali ya majaribio ya kiotomatiki (angalia [README_AUTO.md](https://github.com/awaku7/agentcli/blob/main/README_AUTO.md)).

### 🕵️ Uendeshaji wa Kivinjari na Kikaguzi cha Wavuti

Zana mbili za msingi za mwandishi wa kucheza:

- **browser_playwright**: Rekebisha vipindi halisi vya kivinjari — vinjari, bofya, jaza fomu, toa data, shughulikia mtiririko wa kurasa nyingi. Inafanya kazi bila kichwa au kichwa.
- **mkaguzi_wa_mwigizaji**: Rekodi mabadiliko ya kivinjari, nasa vijipicha na picha za skrini za DOM kwa kila hatua. Inafaa kwa kutatua mwingiliano wa wavuti au kukagua mabadiliko ya ukurasa kwa wakati.

### 🔄 Dynamic Tool Loading

`kitalogi_ya_zana` na `kupakia_zana` hukuwezesha kugundua na kuwasha zana wakati wa utekelezaji.
Hakuna haja ya kupakia kila kitu wakati wa kuanza - wezesha tu kile unachohitaji, wakati unakihitaji.

### 🌐 i18n / L10n

Kiswahili / 简体中文 / 繁體中文 / 한국어 / Español / Français / Русский / na zaidi.
Weka `UAGENT_LANG` ili kubadili. Tazama [ADD_LOCALE.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/ADD_LOCALE.md) ili kuongeza lugha mpya.

Tafsiri za README hii zinapatikana katika [docs/README.translations.md](https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md).

### 🔒 Vigezo vya Mazingira Vilivyosimbwa kwa Njia Fiche

Hifadhi funguo na siri za API katika `.env.sec` — faili ya `.env` iliyosimbwa kwa njia fiche.
Dhibiti ukitumia `uag_envsec`.

## Usanidi & Maelezo

- **Vigeu vya mazingira**: [ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md)
- **Mchawi wa kusanidi**: `python -m uagent.setup_cli`
- **env iliyosimbwa kwa njia fiche**: `uag_envsec` — simba kwa njia fiche `.env` kama `.env.sec`
- **API ya Majibu**: Weka `UAGENT_RESPONSES=1` kwa modi ya API ya Majibu (OpenAI/Azure/Bedrock/OpenRouter/Ollama/Alibaba/LM Studio/Sakana AI). Imewashwa kiotomatiki kwa Sakana AI (Fugu).
- **Hati za Msanidi**: [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)
- **Vidokezo vidogo vya LLM**: [SLM_TIPS.md](https://github.com/awaku7/agentcli/blob/main/SLM_TIPS.md)

## Falsafa ya Mradi

uag anatamani kuwa **AI yako, kwenye mashine yako, kwa masharti yako.**

- Hakuna utegemezi wa SaaS - inaendeshwa ndani ya nchi
- Hakuna kufuli kwa mtoa huduma - badilisha wakati wowote
- Hakuna kufuli kwa UI - CLI / GUI / Wavuti / A2A
- Hakuna kipengele cha kufuli - panua kwa zana na ujuzi

Uzoefu wa bure wa wakala wa AI, usio na kufuli kwa muuzaji.
