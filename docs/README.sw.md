<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="720">
</p>

<h1 align="center">uag — Universal AI Gateway</h1>

<p align="center">
  <b>U</b>_ya kila siku <b>A</b>I <b>G</b>teway - Mazingira yako, uhuru wako.
</p>

<p align="center">
  Utendaji wa faili / Utafutaji wa Wavuti / Uzalishaji wa picha & uchanganuzi / uchimbaji wa PDF na Excel / Udhibiti wa IoT / muunganisho wa MCP<br>
  15+ watoa huduma / 3 UIs / Utekelezaji wa zana Sambamba / Soko la Ujuzi wa Wakala
</p>

<p align="center">
  <a href="https://github.com/awaku7/agentcli">GitHub</a>
  ·
  <a href="https://pypi.org/project/uag/">PyPI</a>
  ·
  <a href="https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md">Soma hii katika lugha yako</a>
</p>

---

##Kwanini uag?

**Jiepushe na kufuli kwa muuzaji.** Wasaidizi wengi wa AI hukufungamanisha na mtoa huduma mahususi au huduma ya wingu. uag ni tofauti.

- ** Huendesha ndani ** kwenye mashine yako. Data yako itasalia nawe (isipokuwa simu za API unazopiga).
- **Uhuru wa mtoa huduma**: OpenAI, Claude, Gemini, DeepSeek, Ollama, Azure, Bedrock... 15+ watoa huduma, wote wanaweza kufikiwa kutoka kwa kiolesura kimoja. Badilisha kati yao kwa kusanidi upya anuwai za mazingira - hakuna kusakinisha tena, hakuna uhamiaji.
- **Zana 131**: Faili I/O, utafutaji wa wavuti, kutengeneza picha, kuchanganua kifaa cha BLE, muunganisho wa seva ya MCP — na **76 zinalindwa kwa usawa** (hadi 4 kwa wakati mmoja). Wakati LLM inapiga simu za zana nyingi mara moja, uag huzitekeleza kiotomatiki kupitia dimbwi la nyuzi.
- **UI 3 + A2A**: CLI, GUI, Wavuti, na itifaki ya Wakala kwa Wakala. Injini sawa, interface yoyote.
- **IoT tayari**: SwitchBot, ECHONET Lite, Matter, UPnP - dhibiti vifaa vyako vya nyumbani kupitia AI.
- **Ujuzi wa Wakala**: Sakinisha ujuzi uliojengwa na jumuiya kutoka sokoni. Panua uag bila mwisho.

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

OpenAI / Azure / Bedrock / OpenRouter / Ollama / Gemini / Vertex AI / Claude / Grok / NVIDIA / DeepSeek / Alibaba Cloud (Qwen) / KIMI (Moonshot AI) / Xiaomi MiMo / LM Studio / MiniMax

Watoa huduma wote hushiriki zana na kiolesura sawa. Badili kwa kuweka `UAGENT_PROVIDER` — hakuna mabadiliko ya msimbo, hakuna usakinishaji tofauti.

### ⚡ Utekelezaji wa Zana Sambamba

LLM inapoomba zana nyingi kwa wakati mmoja, uag **inazilinganisha kiotomatiki**.
Zana 76 zimewekwa alama `x_parallel_safe` na hutekelezwa kwa wakati mmoja kupitia `ThreadPoolExecutor` yenye nyuzi 4.

**Mfano**: Uliza "Angalia hali ya hewa katika herufi kubwa za Nordic" → Mioto ya LLM `search_web` × nchi 5 → utafutaji wote 5 unakwenda sambamba → matokeo yaliyokusanywa katika kundi moja.

Zana za kusoma pekee (kutafuta faili, kukokotoa heshi, kuorodhesha saraka, tafsiri, hoja za DB, n.k.) zimesawazishwa kwa ukali.

### 🔄 Mwendelezo wa Kikao

- **Badilisha watoa huduma katikati ya kipindi** ukitumia `UAGENT_PROVIDER` — historia ya mazungumzo imehifadhiwa.
- **Pakia upya vipindi vilivyopita** kwa `:pakia <index>` — endelea ulipoishia.
- **Uakibishaji wa matokeo ya zana** huepuka kutekeleza tena tena simu ile ile inaporudiwa.

### 🛠 Zana 131

| Kitengo | Zana |
|---|---|
| **Uendeshaji wa Faili** | soma/andika/unda/futa/tafuta/grep/hash/zip |
| **Mtandao** | fetch_url, search_web, screenshot, browser_playwright |
| **Vyombo vya habari** | zalisha_picha, changanua_picha, img2img, hotuba_ya_sauti,nukuu_sauti |
| **Nyaraka** | Uchimbaji wa PDF/PPTX/DOCX/RTF/ODT, uchimbaji muundo wa Excel |
| **IoT** | SwitchBot (Wingu + BLE), ECHONET Lite, Matter, UPnP |
| **Zana za Usanidi** | git_ops, python_compile, lint_format, run_tests, db_query, **13 idx tools** |
| **MCP** | Unganisha kwa seva za MCP za nje, orodhesha zana, tekeleza |
| **A2A** | Mawasiliano ya wakala kwa wakala (pamoja na matukio mengine ya uag au seva zinazooana na A2A) |
| **Mfumo** | env vars, vipimo vya mfumo, saa, hesabu ya tarehe |

### 🖥 Violesura 3 + A2A

| Hali | Amri | Kusudi |
|---|---|---|
| **CLI** | `uag` | Operesheni ya haraka ya msingi wa terminal |
| **GUI** | `uagg` | UI ya Eneo-kazi kupitia tkinter |
| **Mtandao** | `uagw` | Ufikiaji unaotegemea kivinjari |
| **Seva ya A2A** | `uaga` | Itifaki ya Agent2Agent kwa mawasiliano ya mawakala wengi |

### 🏠 Kidhibiti cha Kifaa cha IoT

- **SwitchBot**: Udhibiti wa bechi ya wingu & skanisho/udhibiti wa BLE
- **ECHONET Lite**: Gundua na udhibiti vifaa vya nyumbani (AC, taa, hita za maji, n.k.) kwenye mtandao wa ndani
- **Jambo**: Ukaguzi wa kusoma tu wa kidhibiti/daraja/topolojia ya kifaa
- **UPnP**: Ugunduzi wa kifaa na usambazaji wa mlango wa IGD

Tazama [IOT_USECASE.md](https://github.com/awaku7/agentcli/blob/main/IOT_USECASE.md)

### 🎯 Soko la Ujuzi wa Wakala

`:ujuzi mp_search` ili kuvinjari [SkillsMP](https://skillsmp.com) na [ClawHub](https://clawhub.ai) kwa ujuzi wa jumuiya.
Sakinisha na upanue uwezo wa uag kwenye nzi.

### 🧩 Kidhibiti cha Jimbo la Kundi

uag inaweza kufuatilia maendeleo katika kazi za muda mrefu za faili nyingi. LLM inapochakata faili nyingi, `batch_state` huendelea kuwa na orodha ya faili zinazosubiri, zilizokamilishwa na ambazo hazijafaulu kwenye diski. Kipindi kikimalizika au mzunguko ungeisha, kipindi kifuatacho kitaanza tena pale kiliposimama - hakuna kinachopotea.

### 🛡 Binadamu-katika-Kitanzi

`human_ask` huruhusu LLM kusitisha na kuomba uthibitisho wako kabla ya kutekeleza utendakazi wa uharibifu (kufuta faili, kubatilisha, amri za shell). Wewe kukaa katika udhibiti.

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

### 🔒 Vigezo vya Mazingira Vilivyosimbwa

Hifadhi funguo na siri za API katika `.env.sec` — faili ya `.env` iliyosimbwa kwa njia fiche.
Dhibiti ukitumia `uag_envsec`.

## Usanidi & Maelezo

- **Vigeu vya mazingira**: [ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md)
- **Mchawi wa kusanidi**: `python -m uagent.setup_cli`
- **env iliyosimbwa kwa njia fiche**: `uag_envsec` — simba kwa njia fiche `.env` kama `.env.sec`
- **API ya Majibu**: Weka `UAGENT_RESPONSES=1` kwa modi ya API ya Majibu (OpenAI/Azure/Bedrock/OpenRouter/Ollama/LM Studio)
- **Hati za Msanidi**: [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)
- **Vidokezo vidogo vya LLM**: [SLM_TIPS.md](https://github.com/awaku7/agentcli/blob/main/SLM_TIPS.md)

## Falsafa ya Mradi

uag anatamani kuwa **AI yako, kwenye mashine yako, kwa masharti yako.**

- Hakuna utegemezi wa SaaS - inaendeshwa ndani ya nchi
- Hakuna kufuli kwa mtoa huduma - badilisha wakati wowote
- Hakuna kufuli kwa UI - CLI / GUI / Wavuti / A2A
- Hakuna kipengele cha kufuli - panua kwa zana na ujuzi

Uzoefu wa bure wa wakala wa AI, usio na kufuli kwa muuzaji.