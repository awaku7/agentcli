# Contextcompressie en begrensde modelcontext

uag maakt gebruik van verschillende lagen om de actieve modelcontext begrensd te houden. Het doel is om onnodige invoertokens te verminderen zonder de bestanden, gereedschapsresultaten of sessiegegevens te verwijderen die de gebruiker mogelijk nog nodig heeft.

Dit document beschrijft de huidige implementatie. Het maakt ook onderscheid tussen deterministisch gedrag en provider-specifiek of door LLM ondersteund gedrag.

## 1. Dynamisch tooloppervlak

Niet elke tooldefinitie hoeft bij elke beurt naar het model te worden verzonden.

- `tool_catalog` doorzoekt de beschikbare mogelijkheden.
- `tool_load` schakelt alleen de tools in die nodig zijn voor de huidige taak.
- `tool_catalog`, `tool_load` en `unload_tool` blijven beschikbaar als beheertools.
- GPT-5.4-compatibele Responses API-stromen kunnen gebruikmaken van native server-side Tool Search.
- De verouderde Tool Search-modus beperkt de toolspecificaties met `tool_catalog` aan de clientzijde.

Dit vermindert het aantal invoertokens dat door toolschema’s wordt gebruikt, met name in installaties met veel tools.

## 2. Grote tekstuele toolresultaten worden artefacten

Wanneer een tekstueel toolresultaat de Artifact-drempel overschrijdt, slaat uag het volledige resultaat op als een Artifact en stuurt het model een begrensde verwijzing en een voorbeeld in plaats van de volledige tekst.

De standaardlimieten zijn:

```text
UAGENT_TOOL_RESULT_ARTIFACT_THRESHOLD_CHARS=100000
UAGENT_TOOL_RESULT_MAX_CHARS=12000
```

De voor het model zichtbare weergave bevat de naam van de tool, de oorspronkelijke lengte, een `artifact://`-verwijzing, het opslagpad en een beperkt voorbeeld. Het volledige resultaat blijft beschikbaar via de Artifact-opslag.

De drempelwaarde kan worden gewijzigd met `UAGENT_TOOL_RESULT_ARTIFACT_THRESHOLD_CHARS`. Een waarde van `0` schakelt Artifact-promotie uit. `UAGENT_TOOL_RESULT_MAX_CHARS` regelt het standaardbeleid voor beperkte resultaten; `0` schakelt die standaardlimiet uit.

## 3. Beperkt ophalen van Artifact

De `artifact_read`-infrastructuurtool haalt alleen het gevraagde deel van een Artifact op:

- `start_line` selecteert de eerste regel.
- `max_lines` is beperkt tot 500.
- `max_chars` is beperkt tot 50.000 tekens.
- Zowel een Artifact-ID als een `artifact://`-URI kan worden gebruikt.

Dit maakt het mogelijk om een klein, relevant bereik te inspecteren in plaats van een volledig bestand of commando-resultaat opnieuw in de volgende modelronde te injecteren.

Nieuwe artefacten worden hieronder opgeslagen:

```text
~/.uag/artifacts/
```

Bestaande verouderde Artifact-paden blijven leesbaar omwille van de compatibiliteit.

## 4. Isolatie van binaire payloads

Inline binaire gegevens worden niet als een tekstueel toolresultaat naar de volgende modelronde verzonden. Velden met de vorm Base64 worden vervangen door een korte markering, zoals:

```text
[binaire payload weggelaten uit LLM-context]
```

De gebruikersinterface en externe clients kunnen nog steeds bijlagen in het geheugen ontvangen, en opgeslagen bestanden blijven beschikbaar via hun paden of Artifact-verwijzingen. Dit voorkomt dat afbeeldingen, audio, schermafbeeldingen en andere binaire payloads de tekstuele modelcontext onnodig vergroten.

Dezelfde klasse van binaire payload wordt opgeschoond vóór opslag in SQLite en JSONL, waardoor wordt voorkomen dat deze na het herladen van de sessie als een grote payload terugkeert.

## 5. Automatische compressie van de gespreksgeschiedenis

uag kan oudere gespreksgeschiedenis comprimeren wanneer het aantal berichten of het geschatte aantal tokens de geconfigureerde limiet bereikt.

Het compressiebeleid maakt gebruik van:

- het aantal niet-systeemberichten;
- het opgeloste contextvenster van het model, indien beschikbaar;
- `UAGENT_SHRINK_KEEP_LAST` (standaard 20);
- `UAGENT_SHRINK_MAX_TOKENS` of een modelspecifieke overschrijving;
- `UAGENT_SHRINK_CNT`; en
- `UAGENT_SHRINK_RATIO` (standaard 0,5 wanneer een contextvenster bekend is).

Een modelspecifieke limiet kan worden opgegeven als:

```text
UAGENT_SHRINK_MAX_TOKENS_<MODEL_NAME>
```

Een eerdere samenvatting wordt niet bij elke beurt opnieuw gegenereerd. Er moet voldoende nieuwe geschiedenis zijn opgebouwd, of er moet opnieuw een overschrijding van het tokenbudget plaatsvinden, voordat de compressie opnieuw wordt uitgevoerd.

## 6. LLM-ondersteunde geschiedenisoverzichten

Wanneer automatische compressie gebruikmaakt van de LLM, worden oudere berichten van gebruikers, assistenten en tools samengevat tot een doorlopend systeembericht, terwijl de recente staart behouden blijft.

Lange geschiedenissen kunnen in delen worden samengevat. De relevante instellingen zijn:

```text
UAGENT_SHRINK_CHUNK_SIZE=100
UAGENT_SHRINK_SINGLE_SHOT=1
```

De samenvatting wordt naar voren geschoven in plaats van een onbeperkte reeks samenvattingsberichten te creëren. Dit is een door LLM ondersteunde bewerking en kan extra verzoeken aan de provider vereisen.

## 7. Deterministische fallback-compressie

Als een LLM-samenvatting niet beschikbaar is, kan uag de eerste systeemberichten en alleen de meest recente berichten behouden. De grenzen van tool-aanroepen worden hersteld, zodat de resulterende geschiedenis niet begint of eindigt met een verweesde tool-aanroep.

De loader en de sanitizer verwijderen ook model-irrelevante of ongeldige vermeldingen, waaronder berichten die alleen voor de gebruikersinterface bestemd zijn, interne controleberichten, ongeldige logregels, niet-ondersteunde rollen, verweesde tool-resultaten en onvolledige tool-aanroepblokken.

Wanneer een sessie opnieuw wordt geladen, wordt de huidige systeemprompt hersteld en worden alleen relevante geïnjecteerde systeemberichten, zoals vaardigheids- of hook-context, behouden.

## 8. Herstel bij contextoverschrijding

Als een provider meldt dat het contextvenster is overschreden, identificeert uag een recent bericht uit de geschiedenis met een grote omvang en draait het dat bericht en de daaropvolgende geschiedenis terug voordat het opnieuw wordt geprobeerd. Dit is een reactieve terugvalmaatregel, geen vervanging voor normale budgettering.

## 9. Voortzetting en verdichting aan de kant van de provider

Waar ondersteund, gebruikt de Responses API `previous_response_id` om een responsketen voort te zetten zonder de volledige, door de provider beheerde responsgeschiedenis vanaf de client opnieuw te verzenden.

Responses API-stromen verzenden ook configuratie voor verdichting aan de kant van de provider met dezelfde lokale verdichtingsdrempel. Het exacte gedrag is afhankelijk van de provider; lokale Artifact- en geschiedenisbeleidsregels blijven de providerneutrale waarborgen.

## 10. Efficiëntie bij het tellen van tokens

Token-aantallen die worden gebruikt voor compressiebeslissingen worden in de cache opgeslagen en incrementeel bijgewerkt wanneer er alleen nieuwe berichten zijn toegevoegd. Dit verkleint de modelcontext niet direct, maar het vermindert de CPU-belasting en de latentie bij het bepalen wanneer compressie nodig is.

## Wat nog geen volledige, uniforme laag is

De huidige implementatie biedt nog niet al het volgende als één provider-neutrale manager:

- een uniforme `ContextManager` en `ContextBudget`;
- een `ToolResultRecord` met metadata over belangrijkheid en verwijdering;
- semantische samenvattingen waarvoor geen `LLM` nodig is;
- het automatisch ophalen en opnieuw invoegen van relevante artefacten;
- een centrale resultaatmanager die de Artifact-conversie garandeert voor elke tool die binaire bestanden produceert; of
- prioriteitsbewuste verwijdering over alle systeem-, geschiedenis-, tool-schema- en resultaatcategorieën heen.

Kortom, uag combineert momenteel deterministische afkapping, Artifact-referenties, binaire isolatie, dynamische toolselectie, geschiedenisoverzichten, voortzetting door de provider en herstel na overloop. De ontwerplijst voor een uniforme contextlaag is gedocumenteerd in [UAG_CONTEXT_MANAGEMENT_DESIGN.md](UAG_CONTEXT_MANAGEMENT_DESIGN.md).
