# Pagkukompres ng konteksto at limitadong konteksto ng modelo

uag ay gumagamit ng ilang mga layer upang panatilihing limitado ang aktibong konteksto ng modelo. Ang layunin ay bawasan ang hindi kinakailangang input token nang hindi tinatanggal ang mga file, resulta ng tool, o datos ng sesyon na maaaring kailanganin pa ng gumagamit.

Inilalarawan ng dokumentong ito ang kasalukuyang implementasyon. Ipinapakita rin nito ang pagkakaiba ng deterministikong pag-uugali sa pag-uugali na partikular sa provider o sa LLM-assisted na pag-uugali.

## 1. Dynamic tool surface

Hindi kailangang ipadala sa modelo ang bawat depinisyon ng tool sa bawat pag-ikot.

- Naghahanap ang `tool_catalog` ng mga magagamit na kakayahan.
- Pinapagana lamang ng `tool_load` ang mga tool na kinakailangan para sa kasalukuyang gawain.
- Nananatiling magagamit ang `tool_catalog`, `tool_load`, at `unload_tool` bilang mga kasangkapang pangangasiwa.
- Maaaring gumamit ang mga daloy na GPT-5.4-compatible Responses API ng katutubong Tool Search sa panig ng server.
- Pinapaliit ng legacy na Tool Search mode ang mga espesipikasyon ng tool gamit ang `tool_catalog` sa panig ng kliyente.

Binabawasan nito ang mga input token na ginagamit ng mga schema ng tool, lalo na sa mga instalasyon na may maraming tool.

## 2. Ang malalaking tekstuwal na resulta ng tool ay nagiging mga Artifacts

Kapag ang tekstuwal na resulta ng tool ay lumampas sa Artifact threshold, uag ay iniimbak ang buong resulta bilang isang Artifact at nagpapadala sa modelo ng isang may hangganang sanggunian at paunang sulyap sa halip na ang buong teksto.

Ang mga default na limitasyon ay:

```text
UAGENT_TOOL_RESULT_ARTIFACT_THRESHOLD_CHARS=100000
UAGENT_TOOL_RESULT_MAX_CHARS=12000
```

Ang representasyong nakikita ng modelo ay naglalaman ng pangalan ng tool, orihinal na haba, isang `artifact://` na sanggunian, landas ng imbakan, at isang limitadong paunang sulyap. Ang buong resulta ay nananatiling magagamit sa pamamagitan ng Artifact store.

Maaaring baguhin ang threshold gamit ang `UAGENT_TOOL_RESULT_ARTIFACT_THRESHOLD_CHARS`. Ang halagang `0` ay nagpapagana sa pag-disable ng Artifact promotion. Kinokontrol ng `UAGENT_TOOL_RESULT_MAX_CHARS` ang karaniwang patakaran sa limitadong resulta; ang `0` ay nagpapagana sa pag-disable ng karaniwang limitasyong iyon.

## 3. Nilimitahang pagkuha ng Artifact

Ang `artifact_read` na infrastructure tool ay kumukuha lamang ng hinihinging bahagi ng isang Artifact:

- Ang `start_line` ay pumipili ng unang linya.
- Ang `max_lines` ay limitado sa 500.
- Ang `max_chars` ay limitado sa 50,000 na karakter.
- Maaaring gamitin ang parehong Artifact ID at `artifact://` URI.

Pinapayagan nito na suriin ang maliit na kaugnay na saklaw sa halip na muling i-inject ang buong file o resulta ng utos sa susunod na pag-ikot ng modelo.

Ang mga bagong Artifacts ay nakaimbak sa ibaba:

```text
~/.uag/artifacts/
```

Ang umiiral na legacy Artifact na mga landas ay nananatiling mababasa para sa pagiging tugma.

## 4. Paghiwalay ng binary payload

Ang inline na binary data ay hindi ipinapadala bilang tekstuwal na resulta ng tool sa susunod na pag-ikot ng modelo. Ang mga larangang hugis Base64 ay pinalitan ng maikling tagapagmarka tulad ng:

```text
[binary payload omitted from LLM context]
```

Maaari pa ring makatanggap ang UI at mga remote client ng mga in-memory attachment, at nananatiling magagamit ang mga naka-save na file sa pamamagitan ng kanilang mga path o Artifact na sanggunian. Ito ay pumipigil sa mga larawan, audio, screenshot, at iba pang binary payload na magpabigat sa konteksto ng tekstuwal na modelo.

Ang parehong uri ng binary payload ay nililinis bago i-persist sa SQLite at JSONL, na pumipigil dito na bumalik bilang malaking payload pagkatapos ng pag-reload ng sesyon.

## 5. Awtomatikong pagkompres ng kasaysayan

uag ay maaaring magkompres ng mas lumang kasaysayan ng pag-uusap kapag ang bilang ng mensahe o tinatayang bilang ng token ay umabot sa itinakdang limitasyon.

Ang patakaran sa pagkompres ay gumagamit ng:

- ang bilang ng mga mensaheng hindi mula sa sistema;
- ang resolved context window ng modelo kapag magagamit;
- `UAGENT_SHRINK_KEEP_LAST` (20 bilang default);
- `UAGENT_SHRINK_MAX_TOKENS` o isang override na partikular sa modelo;
- `UAGENT_SHRINK_CNT`; at
- `UAGENT_SHRINK_RATIO` (0.5 bilang default kapag kilala ang kontekstong bintana).

Maaaring magbigay ng limitasyong partikular sa modelo bilang:

```text
UAGENT_SHRINK_MAX_TOKENS_<MODEL_NAME>
```

Hindi muling ginagawa ang naunang buod sa bawat pag-ikot. Kinakailangan ng hysteresis na mag-ipon ng sapat na bagong kasaysayan, o magkaroon ng isa pang pag-uumapaw ng token-budget, bago muling magpatakbo ang compression.

## 6. Mga buod ng kasaysayan na tinutulungan ng LLM

Kapag ginagamit ng awtomatikong compression ang LLM, ang mas lumang mga mensahe ng gumagamit, katulong, at kasangkapan ay binubuod sa isang paikot na mensahe ng sistema habang pinananatili ang kamakailang dulo.

Maaaring buuin nang paisa-isa ang mahahabang kasaysayan. Ang mga kaugnay na kontrol ay:

```text
UAGENT_SHRINK_CHUNK_SIZE=100
UAGENT_SHRINK_SINGLE_SHOT=1
```

Ang buod ay itinutupi pasulong sa halip na lumikha ng walang hanggan na sunud-sunod na mga mensahe ng buod. Ito ay isang operasyong tinutulungan ng LLM at maaaring mangailangan ng karagdagang kahilingan sa provider.

## 7. Deterministikong fallback na kompresyon

Kung hindi magagamit ang buod ng LLM, maaaring panatilihin ng uag ang mga nangungunang mensahe ng sistema at tanging ang pinakabagong mga mensahe lamang. Inaayos ang mga hangganan ng tawag sa tool upang ang nagresultang kasaysayan ay hindi magsimula o magtapos sa isang ulilang tawag sa tool.

Tinatanggal din ng loader at sanitizer ang mga entry na hindi nauugnay sa modelo o hindi wasto, kabilang ang mga mensaheng para lamang sa UI, mga panloob na mensaheng pangkontrol, mga sirang linya ng log, mga hindi sinusuportahang papel, mga ulilang resulta ng tool, at mga hindi kumpletong bloke ng tawag sa tool.

Kapag muling na-load ang isang sesyon, ibinabalik ang kasalukuyang prompt ng sistema at pinananatili lamang ang mga kaugnay na iniksiyong mensahe ng sistema, tulad ng konteksto ng kasanayan o hook.

## 8. Pagbawi mula sa pag-uumapaw ng konteksto

Kung iuulat ng provider na nalampasan ang kontekstong bintana, tinutukoy ng uag ang isang malaking kamakailang mensahe sa kasaysayan at ibinabalik iyon at ang kasunod na kasaysayan bago muling subukan. Ito ay isang reaktibong fallback, hindi kapalit ng normal na pagba-budget.

## 9. Pagpapatuloy at pag-compact sa panig ng provider

Kung sinusuportahan, ginagamit ng Responses API ang `previous_response_id` upang ipagpatuloy ang isang kadena ng tugon nang hindi muling ipinapadala ang buong kasaysayan ng tugon na pinamamahalaan ng provider mula sa kliyente.Ang mga daloy ng Responses API ay nagpapadala rin ng konfigurasyon ng pag-compact sa panig ng provider gamit ang parehong lokal na threshold ng pag-shrink. Ang eksaktong pag-uugali ay nakadepende sa provider; ang lokal na Artifact at mga polisiya ng kasaysayan ay nananatiling mga panseguro na hindi nakadepende sa provider. Epekto sa pagbibilang ng token

Ang mga bilang ng token na ginagamit para sa mga desisyon sa compression ay naka-cache at unti-unting ina-update kapag mga bagong mensahe lamang ang nadagdag. Hindi nito direktang binabawasan ang konteksto ng modelo, ngunit binabawasan nito ang gastos sa CPU at ang pagkaantala sa pagpapasya kung kailan kinakailangan ang compression.

## Ano ang hindi pa ganap na pinag-isang layer

Ang kasalukuyang implementasyon ay hindi pa nagbibigay ng lahat ng mga sumusunod bilang isang provider-neutral na tagapamahala:

- isang pinag-isang `ContextManager` at `ContextBudget`;
- isang `ToolResultRecord` na may metadata ng kahalagahan at pag-evict;
- mga semantikong buod na hindi nangangailangan ng LLM;
- awtomatikong pagkuha at muling pag-iniksyon ng mga kaugnay na Artifacts;
- isang sentral na Tagapamahala ng Resulta na ginagarantiyahan ang Artifact na konbersyon para sa bawat kasangkapang gumagawa ng binaryo; o
- pag-alis na may kamalayan sa prayoridad sa lahat ng kategorya ng sistema, kasaysayan, tool-schema, at resulta.Sa madaling sabi, pinagsasama-sama ng uag sa kasalukuyan ang deterministikong pagputol, mga sangguniang Artifact, paghihiwalay ng binaryo, dinamikong pagpili ng kasangkapan, mga buod ng kasaysayan, pagpapatuloy ng tagapagbigay, at pagbawi mula sa pag-aapaw. Ang roadmap ng disenyo para sa isang pinag-isang kontekstong layer ay nakadokumento sa [UAG_CONTEXT_MANAGEMENT_DESIGN.md](UAG_CONTEXT_MANAGEMENT_DESIGN.md).
