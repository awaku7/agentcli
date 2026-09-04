# Komprese kontextu a ohraničený kontext modelu

uag využívá několik vrstev k tomu, aby aktivní kontext modelu zůstal ohraničený. Cílem je omezit počet zbytečných vstupních tokenů, aniž by byly odstraněny soubory, výsledky nástrojů nebo data relace, které by uživatel mohl ještě potřebovat.

Tento dokument popisuje aktuální implementaci. Rovněž rozlišuje deterministické chování od chování specifického pro poskytovatele nebo chování podporovaného funkcí LLM.

## 1. Dynamické rozhraní nástrojů

Ne každá definice nástroje musí být odeslána do modelu v každém kroku.

- `tool_catalog` prohledává dostupné funkce.
- `tool_load` aktivuje pouze nástroje potřebné pro aktuální úkol.
- `tool_catalog`, `tool_load` a `unload_tool` zůstávají k dispozici jako nástroje pro správu.
- Průběhy Responses API kompatibilní s GPT-5.4 mohou využívat nativní serverovou verzi Tool Search.
- Starší režim Tool Search omezuje specifikace nástrojů pomocí `tool_catalog` na straně klienta.

Tím se snižuje počet vstupních tokenů používaných schématy nástrojů, zejména v instalacích s velkým počtem nástrojů.

## 2. Rozsáhlé textové výsledky nástrojů se stávají artefakty

Pokud textový výsledek nástroje překročí prahovou hodnotu Artifact, uag uloží kompletní výsledek jako Artifact a místo plného textu odešle modelu ohraničený odkaz a náhled.

Výchozí limity jsou:

```text
UAGENT_TOOL_RESULT_ARTIFACT_THRESHOLD_CHARS=100000
UAGENT_TOOL_RESULT_MAX_CHARS=12000
```

Reprezentace viditelná pro model obsahuje název nástroje, původní délku, odkaz `artifact://`, cestu k uložení a ohraničený náhled. Úplný výsledek zůstává k dispozici prostřednictvím úložiště Artifact.

Prahovou hodnotu lze změnit pomocí `UAGENT_TOOL_RESULT_ARTIFACT_THRESHOLD_CHARS`. Hodnota `0` deaktivuje propagaci Artifact. `UAGENT_TOOL_RESULT_MAX_CHARS` řídí běžnou politiku ohraničených výsledků; `0` tento běžný limit deaktivuje.

## 3. Omezené načítání `Artifact`

Infra-nástroj `artifact_read` načte pouze požadovanou část `Artifact`:

- `start_line` vybere první řádek.
- `max_lines` je omezeno na 500.
- `max_chars` je omezeno na 50 000 znaků.
- Lze použít jak ID Artifact, tak URI `artifact://`.

To umožňuje prozkoumat malý relevantní rozsah namísto opětovného vložení celého souboru nebo výsledku příkazu do dalšího kola modelu.

Nové artefakty jsou uloženy níže:

```text
~/.uag/artifacts/
```

Stávající starší cesty Artifact zůstávají čitelné z důvodu kompatibility.

## 4. Izolace binárního užitečného obsahu

Vložená binární data se do dalšího kola modelu neodesílají jako textový výsledek nástroje. Pole ve formátu Base64 jsou nahrazena krátkým značkovačem, například:

```text
[binární datová náplň vynechána z kontextu LLM]
```

Uživatelské rozhraní i vzdálení klienti mohou i nadále přijímat přílohy v paměti a uložené soubory zůstávají dostupné prostřednictvím jejich cest nebo odkazů Artifact. Tím se zabrání tomu, aby obrázky, zvukové soubory, snímky obrazovky a další binární data nadměrně zvětšovaly textový kontext modelu.

Stejná třída binárních dat je před uložením do SQLite a JSONL očištěna, což zabraňuje tomu, aby se po znovu načtení relace vrátila jako velká datová zátěž.

## 5. Automatická komprese historie

uag dokáže komprimovat starší historii konverzací, když počet zpráv nebo odhadovaný počet tokenů dosáhne nastaveného limitu.

Zásady komprese využívají:

- počet nesystémových zpráv;
- vyřešené kontextové okno modelu, je-li k dispozici;
- `UAGENT_SHRINK_KEEP_LAST` (výchozí hodnota 20);
- `UAGENT_SHRINK_MAX_TOKENS` nebo přepsání specifické pro daný model;
- `UAGENT_SHRINK_CNT`; a
- `UAGENT_SHRINK_RATIO` (výchozí hodnota 0,5, pokud je kontextové okno známo).

Limit specifický pro daný model lze zadat takto:

```text
UAGENT_SHRINK_MAX_TOKENS_<MODEL_NAME>
```

Předchozí souhrn se negeneruje při každém tahu. Hysteréze vyžaduje, aby se nashromáždilo dostatečné množství nové historie nebo došlo k dalšímu přetečení tokenového rozpočtu, než se komprese spustí znovu.

## 6. Shrnutí historie s podporou LLM

Pokud automatická komprese využívá LLM, jsou starší zprávy uživatelů, asistentů a nástrojů shrnuty do průběžné systémové zprávy, zatímco nejnovější část je zachována.

Dlouhé historie lze shrnout po částech. Příslušné ovládací prvky jsou:

```text
UAGENT_SHRINK_CHUNK_SIZE=100
UAGENT_SHRINK_SINGLE_SHOT=1
```

Souhrn se posouvá dopředu, místo aby vytvářel neomezenou sekvenci souhrnných zpráv. Jedná se o operaci podporovanou funkcí LLM a může vyžadovat další požadavky na poskytovatele.

## 7. Deterministická záložní komprese

Pokud není souhrn LLM k dispozici, může uag zachovat úvodní systémové zprávy a pouze nejnovější zprávy. Hranice volání nástrojů jsou opraveny tak, aby výsledná historie nezačínala ani nekončila osamoceným voláním nástroje.

Načítací modul a sanitizátor také odstraňují položky irelevantní pro model nebo neplatné, včetně zpráv určených pouze pro uživatelské rozhraní, interních řídicích zpráv, poškozených řádků protokolu, nepodporovaných rolí, osamocených výsledků nástrojů a neúplných bloků volání nástrojů.

Při opětovném načtení relace se obnoví aktuální systémová výzva a zachovají se pouze relevantní vložené systémové zprávy, jako je kontext dovednosti nebo háčku.

## 8. Obnova po přetečení kontextu

Pokud poskytovatel nahlásí, že bylo překročeno okno kontextu, uag identifikuje velkou zprávu z nedávné historie a před opakovaným pokusem tuto zprávu a následující historii vrátí zpět. Jedná se o reaktivní záložní řešení, nikoli o náhradu za běžné rozvrhování.

## 9. Pokračování a zhušťování na straně poskytovatele

Tam, kde je to podporováno, používá Responses API `previous_response_id` k pokračování řetězce odpovědí, aniž by bylo nutné znovu odesílat celou historii odpovědí spravovanou poskytovatelem z klienta.

Toky Responses API také odesílají konfiguraci zhušťování na straně poskytovatele s použitím stejné lokální prahové hodnoty pro zmenšení. Přesné chování závisí na poskytovateli; lokální Artifact a zásady týkající se historie zůstávají ochrannými opatřeními nezávislými na poskytovateli.

## 10. Účinnost počítání tokenů

Počty tokenů používané pro rozhodnutí o kompresi se ukládají do mezipaměti a aktualizují se přírůstkově, pouze pokud byly přidány nové zprávy. To sice přímo nezmenšuje kontext modelu, ale snižuje zatížení procesoru a latenci při rozhodování o tom, kdy je komprese nutná.

## Co zatím není zcela sjednocenou vrstvou

Současná implementace zatím neposkytuje všechny následující prvky jako jeden správce nezávislý na poskytovateli:

- sjednocené `ContextManager` a `ContextBudget`;
- `ToolResultRecord` s metadaty o důležitosti a vyřazování;
- sémantické souhrny, které nevyžadují `LLM`;
- automatické načítání a opětovné vkládání relevantních artefaktů;
- centrální správce výsledků zaručující konverzi `Artifact` pro každý nástroj produkující binární výstup; nebo
- vyřazování s ohledem na prioritu napříč všemi kategoriemi systému, historie, schématu nástrojů a výsledků.

Stručně řečeno, uag v současné době kombinuje deterministické zkrácení, odkazy na Artifact, izolaci binárních souborů, dynamický výběr nástrojů, souhrny historie, pokračování poskytovatele a obnovu po přetečení. Plán vývoje sjednocené kontextové vrstvy je zdokumentován v [UAG_CONTEXT_MANAGEMENT_DESIGN.md](UAG_CONTEXT_MANAGEMENT_DESIGN.md).
