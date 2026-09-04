# Kontextkomprimering och avgränsad modellkontext

uag använder flera lager för att hålla den aktiva modellkontexten avgränsad. Målet är att minska antalet onödiga inmatningstoken utan att ta bort filer, verktygsresultat eller sessionsdata som användaren fortfarande kan behöva.

Detta dokument beskriver den nuvarande implementeringen. Det skiljer också mellan deterministiskt beteende och leverantörsspecifikt eller LLM-assisterat beteende.

## 1. Dynamisk verktygsyta

Inte varje verktygsdefinition behöver skickas till modellen vid varje tur.

- `tool_catalog` söker bland de tillgängliga funktionerna.
- `tool_load` aktiverar endast de verktyg som krävs för den aktuella uppgiften.
- `tool_catalog`, `tool_load` och `unload_tool` förblir tillgängliga som hanteringsverktyg.
- GPT-5.4-kompatibla Responses API-flöden kan använda inbyggt Tool Search på serversidan.
- Det äldre Tool Search-läget begränsar verktygsspecifikationerna med `tool_catalog` på klientsidan.

Detta minskar antalet ingångstoken som används av verktygsscheman, särskilt i installationer med många verktyg.

## 2. Stora textbaserade verktygsresultat blir artefakter

När ett textbaserat verktygsresultat överskrider Artifact-tröskeln lagrar uag det fullständiga resultatet som en Artifact och skickar en avgränsad referens och förhandsgranskning till modellen istället för hela texten.

Standardgränserna är:

```text
UAGENT_TOOL_RESULT_ARTIFACT_THRESHOLD_CHARS=100000
UAGENT_TOOL_RESULT_MAX_CHARS=12000
```

Den representation som är synlig för modellen innehåller verktygets namn, den ursprungliga längden, en `artifact://`-referens, lagringsvägen och en begränsad förhandsvisning. Det fullständiga resultatet förblir tillgängligt via Artifact-lagret.

Tröskelvärdet kan ändras med `UAGENT_TOOL_RESULT_ARTIFACT_THRESHOLD_CHARS`. Värdet `0` inaktiverar Artifact-framhävning. `UAGENT_TOOL_RESULT_MAX_CHARS` styr den vanliga policyn för begränsade resultat; `0` inaktiverar den vanliga gränsen.

## 3. Begränsad hämtning av `Artifact`

Infrastrukturverktyget `artifact_read` hämtar endast den begärda delen av ett `Artifact`:

- `start_line` väljer den första raden.
- `max_lines` är begränsat till 500.
- `max_chars` är begränsat till 50 000 tecken.
- Både ett Artifact-ID och en `artifact://`-URI kan användas.

Detta gör det möjligt att granska ett litet relevant intervall istället för att återinföra en hel fil eller ett kommandoresultat i nästa modellomgång.

Nya artefakter lagras nedan:

```text
~/.uag/artifacts/
```

Befintliga äldre Artifact-sökvägar förblir läsbara av kompatibilitetsskäl.

## 4. Isolering av binär nyttolast

Inline-binärdata skickas inte som ett textbaserat verktygsresultat till nästa modellomgång. Base64-formade fält ersätts med en kort markör, till exempel:

```text
[binär nyttolast utelämnad från LLM-sammanhanget]
```

Användargränssnittet och fjärrklienter kan fortfarande ta emot bilagor i minnet, och sparade filer förblir tillgängliga via sina sökvägar eller Artifact-referenser. Detta förhindrar att bilder, ljud, skärmdumpar och annan binär data sväller upp modellkontexten med text.

Samma typ av binär data rensas innan den lagras i SQLite och JSONL, vilket förhindrar att den återkommer som en stor datamängd efter att sessionen har laddats om.

## 5. Automatisk komprimering av historik

uag kan komprimera äldre konversationshistorik när antalet meddelanden eller det uppskattade antalet token når den konfigurerade gränsen.

Komprimeringspolicyn använder:

- antalet icke-systemmeddelanden;
- modellens upplösta kontextfönster när det är tillgängligt;
- `UAGENT_SHRINK_KEEP_LAST` (20 som standard);
- `UAGENT_SHRINK_MAX_TOKENS` eller en modellspecifik överskrivning;
- `UAGENT_SHRINK_CNT`; och
- `UAGENT_SHRINK_RATIO` (0,5 som standard när ett kontextfönster är känt).

En modellspecifik gräns kan anges som:

```text
UAGENT_SHRINK_MAX_TOKENS_<MODEL_NAME>
```

En tidigare sammanfattning genereras inte på nytt vid varje tur. Hysteres kräver att tillräckligt med ny historik har ackumulerats, eller att tokenbudgeten överskrids igen, innan komprimeringen körs på nytt.

## 6. LLM-assisterade historiksammanfattningar

När automatisk komprimering använder LLM sammanfattas äldre användar-, assistent- och verktygsmeddelanden till ett rullande systemmeddelande, medan den senaste delen behålls.

Långa historiker kan sammanfattas i delar. De relevanta kontrollerna är:

```text
UAGENT_SHRINK_CHUNK_SIZE=100
UAGENT_SHRINK_SINGLE_SHOT=1
```

Sammanfattningen viks framåt istället för att skapa en obegränsad sekvens av sammanfattningsmeddelanden. Detta är en LLM-assisterad operation och kan kräva ytterligare förfrågningar till leverantören.

## 7. Deterministisk reservkomprimering

Om en LLM-sammanfattning inte är tillgänglig kan uag behålla de inledande systemmeddelandena och endast de allra senaste meddelandena. Gränserna för verktygsanrop repareras så att den resulterande historiken inte börjar eller slutar med ett övergivet verktygsanrop.

Laddaren och saneraren tar också bort modellirrelevanta eller ogiltiga poster, inklusive meddelanden som endast gäller användargränssnittet, interna kontrollmeddelanden, trasiga loggrader, roller som inte stöds, övergivna verktygsresultat och ofullständiga verktygsanropsblock.

När en session laddas om återställs den aktuella systemprompten och endast relevanta injicerade systemmeddelanden, såsom färdighets- eller hook-kontext, behålls.

## 8. Återställning vid kontextöverskridning

Om en leverantör rapporterar att kontextfönstret har överskridits identifierar uag ett stort meddelande från den senaste historiken och återställer det meddelandet samt den efterföljande historiken innan ett nytt försök görs. Detta är en reaktiv reservlösning, inte en ersättning för normal budgetering.

## 9. Fortsättning och komprimering på leverantörssidan

Där detta stöds använder Responses API `previous_response_id` för att fortsätta en svarskedja utan att skicka om hela den leverantörshanterade svarhistoriken från klienten.

Responses API-flöden skickar även konfiguration för komprimering på leverantörssidan med samma lokala komprimeringströskel. Det exakta beteendet är leverantörsberoende; lokala Artifact och historikpolicyer förblir de leverantörsneutrala säkerhetsåtgärderna.

## 10. Effektivitet vid tokenräkning

Tokenantal som används för komprimeringsbeslut cachelagras och uppdateras stegvis endast när nya meddelanden har lagts till. Detta minskar inte direkt modellkontexten, men det minskar CPU-kostnaden och latensen vid beslut om när komprimering är nödvändig.

## Vad som ännu inte är ett fullständigt enhetligt lager

Den nuvarande implementeringen tillhandahåller ännu inte alla följande funktioner som en enda leverantörsneutral hanterare:

- ett enhetligt `ContextManager` och `ContextBudget`;
- ett `ToolResultRecord` med metadata om betydelse och borttagning;
- semantiska sammanfattningar som inte kräver en `LLM`;
- automatisk hämtning och återinsättning av relevanta artefakter;
- en central resultatförvaltare som garanterar `Artifact`-konvertering för varje verktyg som producerar binärdata; eller
- prioriteringsmedveten borttagning över alla system-, historik-, verktygsschema- och resultatkategorier.

Kort sagt kombinerar uag för närvarande deterministisk avkortning, Artifact-referenser, binär isolering, dynamiskt verktygsval, historiksammanfattningar, leverantörskontinuitet och återställning efter överflöd. Utvecklingsplanen för ett enhetligt kontextlager finns dokumenterad i [UAG_CONTEXT_MANAGEMENT_DESIGN.md](UAG_CONTEXT_MANAGEMENT_DESIGN.md).
