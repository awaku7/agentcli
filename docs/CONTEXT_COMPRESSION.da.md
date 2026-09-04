# Kontekstkomprimering og afgrænset modelkontekst

uag anvender flere lag for at holde den aktive modelkontekst afgrænset. Målet er at reducere unødvendige input-tokens uden at fjerne de filer, værktøjsresultater eller sessionsdata, som brugeren muligvis stadig har brug for.

Dette dokument beskriver den nuværende implementering. Det skelner også mellem deterministisk adfærd og udbyderspecifik eller LLM-assisteret adfærd.

## 1. Dynamisk værktøjsoverflade

Ikke alle værktøjsdefinitioner behøver at blive sendt til modellen ved hvert træk.

- `tool_catalog` søger blandt de tilgængelige funktioner.
- `tool_load` aktiverer kun de værktøjer, der er nødvendige for den aktuelle opgave.
- `tool_catalog`, `tool_load` og `unload_tool` forbliver tilgængelige som administrationsværktøjer.
- GPT-5.4-kompatible Responses API-forløb kan anvende indbygget server-side Tool Search.
- Den ældre Tool Search-tilstand indsnævrer værktøjsspecifikationerne med `tool_catalog` på klientsiden.

Dette reducerer antallet af input-tokens, der bruges af værktøjsskemaer, især i installationer med mange værktøjer.

## 2. Store tekstbaserede værktøjsresultater bliver til artefakter

Når et tekstbaseret værktøjsresultat overskrider Artifact-tærsklen, gemmer uag det komplette resultat som en Artifact og sender modellen en afgrænset reference og et eksempel i stedet for den fulde tekst.

Standardgrænserne er:

```text
UAGENT_TOOL_RESULT_ARTIFACT_THRESHOLD_CHARS=100000
UAGENT_TOOL_RESULT_MAX_CHARS=12000
```

Den model-synlige repræsentation indeholder værktøjsnavnet, den oprindelige længde, en `artifact://`-reference, lagringsstien og et afgrænset eksempel. Det fulde resultat forbliver tilgængeligt via Artifact-lageret.

Tærsklen kan ændres med `UAGENT_TOOL_RESULT_ARTIFACT_THRESHOLD_CHARS`. En værdi på `0` deaktiverer Artifact-fremhævning. `UAGENT_TOOL_RESULT_MAX_CHARS` styrer den almindelige politik for begrænsede resultater; `0` deaktiverer denne almindelige grænse.

## 3. Begrænset hentning af `Artifact`

`artifact_read`-infrastrukturværktøjet henter kun den anmodede del af en `Artifact`:

- `start_line` vælger den første linje.
- `max_lines` er begrænset til 500.
- `max_chars` er begrænset til 50.000 tegn.
- Både et Artifact-ID og en `artifact://`-URI kan anvendes.

Dette gør det muligt at undersøge et lille, relevant interval i stedet for at indsætte en hel fil eller et kommandoresultat i den næste modelomgang.

Nye artefakter gemmes nedenfor:

```text
~/.uag/artifacts/
```

Eksisterende ældre Artifact-stier forbliver læsbare af hensyn til kompatibilitet.

## 4. Isolering af binær nyttelast

Inline binære data sendes ikke som et tekstbaseret værktøjsresultat til den næste modelrunde. Base64-formede felter erstattes med en kort markør, f.eks.:

```text
[binær nyttelast udeladt fra LLM-kontekst]
```

Brugergrænsefladen og fjernklienter kan stadig modtage vedhæftede filer i hukommelsen, og gemte filer forbliver tilgængelige via deres stier eller Artifact-referencer. Dette forhindrer, at billeder, lyd, skærmbilleder og andre binære data udvider den tekstbaserede modelkontekst.

Den samme type binære data renses før lagring i SQLite og JSONL, hvilket forhindrer, at de returneres som store datamængder efter en genindlæsning af sessionen.

## 5. Automatisk komprimering af historik

uag kan komprimere ældre samtalehistorik, når antallet af beskeder eller det estimerede antal tokens når den konfigurerede grænse.

Komprimeringspolitikken anvender:

- antallet af ikke-systembeskeder;
- modellens opløste kontekstvindue, når det er tilgængeligt;
- `UAGENT_SHRINK_KEEP_LAST` (20 som standard);
- `UAGENT_SHRINK_MAX_TOKENS` eller en model-specifik tilsidesættelse;
- `UAGENT_SHRINK_CNT`; og
- `UAGENT_SHRINK_RATIO` (0,5 som standard, når et kontekstvindue er kendt).

En modelspecifik grænse kan angives som:

```text
UAGENT_SHRINK_MAX_TOKENS_<MODEL_NAME>
```

Et tidligere resumé genoprettes ikke ved hver tur. Hysterese kræver, at der akkumuleres tilstrækkelig ny historik, eller at der sker endnu et token-budgetoverskridelse, før komprimeringen kører igen.

## 6. LLM-assisterede historikoversigter

Når automatisk komprimering bruger LLM, sammenfattes ældre bruger-, assistent- og værktøjsmeddelelser til en rullende systemmeddelelse, mens den seneste del bevares.

Lange historikker kan sammenfattes i bidder. De relevante kontrolparametre er:

```text
UAGENT_SHRINK_CHUNK_SIZE=100
UAGENT_SHRINK_SINGLE_SHOT=1
```

Oversigten foldes fremad i stedet for at skabe en ubegrænset sekvens af oversigtsmeddelelser. Dette er en LLM-assisteret operation og kan kræve yderligere anmodninger til udbyderen.

## 7. Deterministisk fallback-komprimering

Hvis en LLM-opsummering ikke er tilgængelig, kan uag beholde de førende systemmeddelelser og kun de seneste meddelelser. Grænserne mellem værktøjsopkald repareres, så den resulterende historik hverken begynder eller slutter med et forældreløst værktøjsopkald.

Loader og sanitizer fjerner også modelirrelevante eller ugyldige poster, herunder meddelelser, der kun vedrører brugergrænsefladen, interne kontrolmeddelelser, ødelagte loglinjer, roller, der ikke understøttes, forældreløse værktøjsresultater og ufuldstændige værktøjsopkaldsblokke.

Når en session genindlæses, gendannes den aktuelle systemprompt, og kun relevante indsatte systemmeddelelser, såsom færdigheds- eller hook-kontekst, bevares.

## 8. Gendannelse efter kontekstoverskridelse

Hvis en udbyder rapporterer, at kontekstvinduet er overskredet, identificerer uag en stor, nylig historikmeddelelse og fortryder denne meddelelse samt den efterfølgende historik, før der forsøges igen. Dette er en reaktiv sikkerhedsløsning, ikke en erstatning for normal ressourceplanlægning.

## 9. Fortsættelse og komprimering på udbydersiden

Hvor det understøttes, bruger Responses API `previous_response_id` til at fortsætte en svarkæde uden at sende hele den udbyderstyrede svarhistorik fra klienten igen.

Responses API-forløb sender også udbyderside-komprimeringskonfiguration ved hjælp af den samme lokale komprimeringstærskel. Den nøjagtige adfærd afhænger af udbyderen; lokale Artifact og historikpolitikker forbliver de udbyderneutrale sikkerhedsforanstaltninger.

## 10. Effektivitet ved tælling af tokens

Token-tællinger, der anvendes til komprimeringsbeslutninger, caches og opdateres inkrementelt, når der kun er tilføjet nye meddelelser. Dette reducerer ikke direkte modelkonteksten, men det reducerer CPU-omkostningerne og ventetiden ved beslutningen om, hvornår komprimering er nødvendig.

## Hvad der endnu ikke udgør et fuldstændigt samlet lag

Den nuværende implementering leverer endnu ikke alle følgende elementer som én udbyderneutral manager:

- et samlet `ContextManager` og `ContextBudget`;
- et `ToolResultRecord` med metadata om vigtighed og fjernelse;
- semantiske resuméer, der ikke kræver en `LLM`;
- automatisk hentning og genindsættelse af relevante artefakter;
- en central resultatmanager, der garanterer `Artifact`-konvertering for hvert værktøj, der producerer binære filer; eller
- prioriteringsbevidst fjernelse på tværs af alle system-, historik-, værktøjsskema- og resultatkategorier.

Kort sagt kombinerer uag i øjeblikket deterministisk afkortning, Artifact-referencer, binær isolering, dynamisk værktøjsvalg, historikoversigter, fortsættelse af udbyder og gendannelse efter overløb. Designkøreplanen for et samlet kontekstlag er dokumenteret i [UAG_CONTEXT_MANAGEMENT_DESIGN.md](UAG_CONTEXT_MANAGEMENT_DESIGN.md).
