# Ukomazaji wa muktadha na muktadha wa mfano wenye mipaka

uag inatumia tabaka kadhaa ili kuweka muktadha wa mfano unaoendelea kuwa na mipaka. Lengo ni kupunguza tokeni zisizo za lazima za ingizo bila kuondoa faili, matokeo ya zana, au data ya kikao ambayo mtumiaji bado anaweza kuhitaji.

Hati hii inaelezea utekelezaji wa sasa. Pia inatofautisha tabia ya uhakika dhidi ya tabia maalum ya mtoa huduma au tabia inayosaidiwa na LLM.

## 1. Uso wa zana unaobadilika

Sio kila ufafanuzi wa zana unahitaji kutumwa kwa mfano kila mzunguko.

- `tool_catalog` hutafuta uwezo uliopo.
- `tool_load` huwezesha tu zana zinazohitajika kwa kazi ya sasa.
- `tool_catalog`, `tool_load`, na `unload_tool` zinaendelea kupatikana kama zana za usimamizi.
- Mtiririko unaoendana na GPT-5.4 Responses API unaweza kutumia Tool Search asilia upande wa seva.
- Modhi ya zamani ya Tool Search hupunguza vipimo vya zana kwa kutumia `tool_catalog` upande wa mteja.

Hii hupunguza tokeni za ingizo zinazotumika na schemas za zana, hasa katika usakinishaji wenye zana nyingi.

## 2. Matokeo makubwa ya zana za maandishi yanakuwa Artifacts

Wakati matokeo ya maandishi ya zana yanapovuka kikomo cha Artifact, uag huhifadhi matokeo kamili kama Artifact na kutuma kwa mfano rejeleo lenye mipaka na muonekano badala ya maandishi yote.

Vipimo chaguo-msingi ni:

```text
UAGENT_TOOL_RESULT_ARTIFACT_THRESHOLD_CHARS=100000
UAGENT_TOOL_RESULT_MAX_CHARS=12000
```

Uwasilishaji unaoonekana kwa mfano unajumuisha jina la zana, urefu halisi, rejea ya `artifact://`, njia ya uhifadhi, na muhtasari wenye ukomo. Matokeo kamili yanabaki kupatikana kupitia hifadhi ya Artifact.

Kipimo kinaweza kubadilishwa kwa kutumia `UAGENT_TOOL_RESULT_ARTIFACT_THRESHOLD_CHARS`. Thamani ya `0` inazima uendelezaji wa Artifact. `UAGENT_TOOL_RESULT_MAX_CHARS` inadhibiti sera ya kawaida ya matokeo yenye ukomo; `0` inazima kikomo hicho cha kawaida.

## 3. Upakuaji ulio na kikomo wa Artifact

Zana ya miundombinu ya `artifact_read` hupakua tu sehemu iliyoombwa ya Artifact:

- `start_line` huchagua mstari wa kwanza.
- `max_lines` imewekwa hadi mistari 500.
- `max_chars` imewekwa hadi alama 50,000.
- ID ya Artifact na URI ya `artifact://` zote zinaweza kutumika.

Hii inafanya iwezekane kuchunguza wigo mdogo unaohusiana badala ya kuingiza tena faili nzima au matokeo ya amri katika mzunguko unaofuata wa mfano.

Vipengee vipya vimehifadhiwa hapa chini:

```text
~/.uag/artifacts/
```

Njia za urithi za Artifact zilizopo zinaendelea kusomeka kwa ajili ya uendelevu.

## 4. Kutenganisha mzigo wa binary

Data ya binary iliyojengewa ndani haitumiwi kama matokeo ya zana ya maandishi kwa mzunguko ujao wa modeli. Sehemu zenye umbo la Base64 hubadilishwa na kiashiria kifupi kama vile:

```text
[mzigo wa binary umetolewa kutoka kwenye muktadha wa LLM]
```

UI na wateja wa mbali bado wanaweza kupokea viambatisho vilivyomo kwenye kumbukumbu, na faili zilizohifadhiwa zinaendelea kupatikana kupitia njia zao au marejeleo ya Artifact. Hii huzuia picha, sauti, picha za skrini, na mizigo mingine ya binary kuongeza ukubwa wa muktadha wa modeli ya maandishi.

Aina ile ile ya mzigo wa binary husafishwa kabla ya uhifadhi wa SQLite na JSONL, ikizuia kurudi kama mzigo mkubwa baada ya upakiaji upya wa kikao.

## 5. Ufinyaji wa kiotomatiki wa historia

uag inaweza kufinya historia ya mazungumzo ya zamani wakati idadi ya ujumbe au makadirio ya idadi ya tokeni inapofikia kikomo chake kilichowekwa.

Sera ya ufinyaji inatumia:

- idadi ya ujumbe zisizo za mfumo;
- dirisha la muktadha lililosuluhishwa la mfano linapopatikana;
- `UAGENT_SHRINK_KEEP_LAST` (20 kwa chaguo-msingi);
- `UAGENT_SHRINK_MAX_TOKENS` au ubatilishaji maalum wa mfano;
- `UAGENT_SHRINK_CNT`; na
- `UAGENT_SHRINK_RATIO` (0.5 kwa chaguo-msingi wakati dirisha la muktadha linajulikana).

Kikomo maalum cha mfano kinaweza kutolewa kama:

```text
UAGENT_SHRINK_MAX_TOKENS_<JINA_LA_MFANO>
```

Muhtasari wa awali hautolewi upya kila zamu. Hysteresis inahitaji historia mpya ya kutosha ikusanyike, au bajeti nyingine ya tokeni izidiwe, kabla ya ukandishaji kufanyika tena.

## 6. Muhtasari wa historia unaosaidiwa na LLM

Wakati ukandaji wa kiotomatiki unatumia LLM, ujumbe wa zamani wa mtumiaji, msaidizi, na zana hufupishwa kuwa ujumbe wa mfumo unaosogezwa mbele huku mwisho wa hivi karibuni ukihifadhiwa.

Historia ndefu zinaweza kufupishwa kwa sehemu. Vidhibiti husika ni:

```text
UAGENT_SHRINK_CHUNK_SIZE=100
UAGENT_SHRINK_SINGLE_SHOT=1
```

Muhtasari unakunjwa mbele badala ya kuunda mfululizo usio na kikomo wa ujumbe wa muhtasari. Hii ni operesheni inayosaidiwa na LLM na inaweza kuhitaji maombi ya ziada kutoka kwa mtoa huduma.

## 7. Ufinyaji wa mbadala unaotabirika

Ikiwa muhtasari wa LLM haupatikani, uag inaweza kuhifadhi ujumbe wa mfumo wa mwanzo na ujumbe wa hivi karibuni tu. Mipaka ya wito wa zana inarekebishwa ili historia inayotokana nayo isianze wala kuishia na wito wa zana ulioachwa peke yake.

Loader na sanitizer pia huondoa maingizo yasiyo na uhusiano na mfano au yasiyo halali, ikiwa ni pamoja na ujumbe wa UI pekee, ujumbe wa udhibiti wa ndani, mistari ya logi iliyovunjika, majukumu yasiyotumika, matokeo ya zana yaliyoachwa peke yake, na bloku zisizokamilika za wito wa zana.

Wakati kikao kinapopakiwa upya, ombi la mfumo la sasa linarejeshwa na ujumbe tu wa mfumo ulioingizwa unaohusiana, kama muktadha wa ujuzi au hook, ndio huhifadhiwa.

## 8. Urejeshaji baada ya kupita mipaka ya muktadha

Ikiwa mtoa huduma ataripoti kuwa dirisha la muktadha limezidiwa, uag hutambua ujumbe mkubwa wa hivi karibuni wa historia na kurudisha ujumbe huo na historia inayofuata nyuma kabla ya kujaribu tena. Hii ni njia ya kurejea inayotumika baada ya hitilafu, si mbadala wa upangaji wa kawaida.

## 9. Uendelezaji na Ufinyaji upande wa mtoa huduma

Pale inapoungwa mkono, Responses API hutumia `previous_response_id` kuendeleza mnyororo wa majibu bila kutuma tena historia nzima ya majibu inayosimamiwa na mtoa huduma kutoka kwa mteja.Mtiririko wa Responses API pia hutuma usanidi wa ukandamizaji upande wa mtoa huduma kwa kutumia kizingiti sawa cha kupunguza cha ndani. Utendaji halisi hutegemea mtoa huduma; sera za ndani za Artifact na historia hubaki kuwa kinga zisizoegemea upande wowote wa mtoa huduma.

## 10. Ufanisi wa kuhesabu tokeni

Idadi za tokeni zinazotumika kwa maamuzi ya kubana huhifadhiwa kwenye kache na kusasishwa kidogo kidogo pale tu ujumbe mpya umeongezwa. Hii haipunguzi moja kwa moja muktadha wa mfano, lakini inapunguza gharama ya CPU na ucheleweshaji wa kuamua ni lini ukandaji unahitajika.

## Kile ambacho bado si safu moja iliyounganishwa kikamilifu

Utekelezaji wa sasa bado haujatoa yote yafuatayo kama meneja mmoja asiyeegemea mtoa huduma:

- `ContextManager` na `ContextBudget` zilizounganishwa;
- `ToolResultRecord` yenye metadata ya umuhimu na uondoaji;
- muhtasari wa kisemantiki ambao hauhitaji LLM;
- upatikanaji na uingizaji upya wa kiotomatiki wa Artifacts husika;
- Msimamizi wa Matokeo wa Kati anayehakikisha uongofu wa Artifact kwa kila zana inayotengeneza binary; au
- uondoaji unaozingatia vipaumbele katika kategoria zote za mfumo, historia, mpangilio wa zana, na matokeo.Kwa ufupi, uag kwa sasa inachanganya ukataaji unaobainika, marejeleo ya Artifact, utengaji wa binary, uteuzi wa zana unaobadilika, muhtasari wa historia, uendelezaji wa mtoa huduma, na urejeshaji baada ya kuzidi uwezo. Ramani ya usanifu kwa ajili ya safu ya muktadha iliyounganishwa imeandikwa katika [UAG_CONTEXT_MANAGEMENT_DESIGN.md](UAG_CONTEXT_MANAGEMENT_DESIGN.md).
