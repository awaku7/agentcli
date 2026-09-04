# Komprimering av kontekst og avgrensa modellkontekst

uag brukar flere lag for å holde den aktive modellkonteksten avgrensa. Målet er å redusere unødvendige inndatatokener uten å fjerne filer, verktøysresultater eller sesjonsdata som brukaren fortsatt kan ha behov for.

Dette dokumentet beskriver den noverande implementeringen. Det skiller også mellom deterministisk atferd og leverandørspesifikk eller LLM-assistert atferd.

## 1. Dynamisk verktøyflate

Ikke alle verktøydefinisjoner trenger å sendes til modellen ved hver runde.

- `tool_catalog` søker blant de tilgjengelege funksjonene.
- `tool_load` aktiverer kun de verktøyene som kreves for den aktuelle oppgaven.
- `tool_catalog`, `tool_load` og `unload_tool` forblir tilgjengelege som administrasjonsverktøy.
- GPT-5.4-kompatible Responses API-flyter kan bruke innfødt Tool Search på serversiden.
- Den eldre Tool Search-modusen begrenser verktøyspesifikasjonene med `tool_catalog` på klientsiden.

Dette reduserer antallet inndatatokener som blir brukt av verktøyskjemaer, spesielt i installasjoner med mange verktøy.

## 2. Store tekstbaserte verktøysresultater blir artefakter

Når et tekstbasert verktøysresultat overskrider Artifact-terskelen, lagrer uag det komplette resultatet som en Artifact og sender modellen en avgrensa referanse og forhåndsvisning i stedet for fullteksten.

Standardgrensene er:

```text
UAGENT_TOOL_RESULT_ARTIFACT_THRESHOLD_CHARS=100000
UAGENT_TOOL_RESULT_MAX_CHARS=12000
```

Representasjonen som er synlig for modellen inneholder verktøyets navn, opprinnelig lengde, en `artifact://`-referanse, lagringsstien og en begrenset forhåndsvisning. Det fullstendige resultatet forblir tilgjengeleg via Artifact-lagringen.

Terskelen kan endres med `UAGENT_TOOL_RESULT_ARTIFACT_THRESHOLD_CHARS`. En verdi på `0` deaktiverer Artifact-fremheving. `UAGENT_TOOL_RESULT_MAX_CHARS` styrer den vanlige retningslinjen for begrensede resultater; `0` deaktiverer den vanlige grensen.

## 3. Begrenset henting av `Artifact`

`artifact_read`-infrastrukturverktøyet hentar kun den forespurte delen av et `Artifact`:

- `start_line` velger den fyrste linjen.
- `max_lines` er begrenset til 500.
- `max_chars` er begrenset til 50 000 tegn.
- Både en Artifact-ID og en `artifact://`-URI kan blir brukt.

Dette gjør det mulig å undersøke et lite, relevant utdrag i stedet for å mate inn en hel fil eller et kommandoresultat på nytt i neste modellrunde.

Nye artefakter blir lagra nedenfor:

```text
~/.uag/artifacts/
```

Eksisterende eldre Artifact-baner forblir lesberre av kompatibilitetshensyn.

## 4. Isolering av binær nyttelast

Inline binære data sendes ikkje som et tekstbasert verktøyresultat til neste modellrunde. Base64-formede felt erstattes med en kort markør, for eksempel:

```text
[binær nyttelast utelatt fra LLM-konteksten]
```

Brukergrensesnittet og eksterne klienter kan fortsatt motta vedlegg i minnet, og lagrede filer forblir tilgjengelege via sine baner eller Artifact-referanser. Dette forhindrer at bilder, lyd, skjermbilder og annen binær nyttelast gjør tekstmodellkonteksten unødvendig stor.

Den samme typen binær nyttelast renses før lagring i SQLite og JSONL, noe som forhindrer at den returneres som en stor nyttelast etter at en sesjon er lastet inn på nytt.

## 5. Automatisk komprimering av historikk

uag kan komprimere eldre samtalehistorikk når antall meldingar eller estimert antall token når den konfigurerte grensen.

Komprimeringspolitikkjen brukar:

- antall ikkje-systemmeldingar;
- modellens oppløste kontekstvindu når det er tilgjengeleg;
- `UAGENT_SHRINK_KEEP_LAST` (20 som standard);
- `UAGENT_SHRINK_MAX_TOKENS` eller en modellspesifikk overstyring;
- `UAGENT_SHRINK_CNT`; og
- `UAGENT_SHRINK_RATIO` (0,5 som standard når et kontekstvindu er kjent).

En modellspesifikk grense kan angis som:

```text
UAGENT_SHRINK_MAX_TOKENS_<MODEL_NAME>
```

En tidligere samandrag genereres ikkje på nytt ved hver runde. Hysterese krever at det akkumuleres nok ny historikk, eller at det oppstår et nytt overskridelse av tokenbudsjettet, før komprimeringen kjører igjen.

## 6. LLM-assisterte historikksammendrag

Når automatisk komprimering brukar LLM, blir eldre brukar-, assistent- og verktøymeldingar oppsummert i en rullende systemmelding, mens den nyaste delen beholdes.

Lange historikkjer kan blir samanfatta i deler. De relevante kontrollene er:

```text
UAGENT_SHRINK_CHUNK_SIZE=100
UAGENT_SHRINK_SINGLE_SHOT=1
```

Oppsummeringen foldes fremover i stedet for å skape en ubegrenset sekvens av samandragsmeldingar. Dette er en LLM-assistert operasjon og kan kreve ytterligere forespørsler til leverandøren.

## 7. Deterministisk reservekomprimering

Hvis et LLM-sammendrag ikkje er tilgjengeleg, kan uag beholde de fyrste systemmeldingae og berre de aller nyaste meldingae. Grensene for verktøyoppkall repareres slik at den resulterende historikkjen ikkje begynner eller slutter med et foreldreløst verktøyoppkall.

Lasteren og renserprogrammet fjerner også modellirrelevante eller ugyldige oppføringer, inkludert meldingar som kun gjelder brukargrensesnittet, interne kontrollmeldingar, ødelagte logglinjer, roller som ikkje støttes, foreldreløse verktøyresultat og ufullstendige blokker med verktøyoppkall.

Når en økt lastes inn på nytt, blir gjenoppretta den gjeldande systemprompten, og kun relevante injiserte systemmeldingar, for eksempel ferdighets- eller hook-kontekst, beholdes.

## 8. Gjenoppretting ved kontekstoverskridelse

Hvis en leverandør rapporterer at kontekstvinduet ble overskredet, identifiserer uag en stor melding fra den nylige historikkjen og tilbakestiller den meldinga og den påfølgende historikkjen før det gjøres et nytt forsøk. Dette er en reaktiv reserve, ikkje en erstatning for normal budsjettering.

## 9. Fortsettelse og komprimering på leverandørsiden

Der det støttes, brukar Responses API `previous_response_id` til å fortsette en svarkjede uten å sende hele den leverandørstyrte svarthistorikkjen fra klienten på nytt.

Responses API-flyter sender også konfigurasjon for komprimering på leverandørsiden ved å bruke den samme lokale komprimeringsterskelen. Den nøyaktige oppførselen avhenger av leverandøren; lokale Artifact- og historikkretningslinjer forblir de leverandørnøytrale sikkjerhetsmekanismene.

## 10. Effektivitet ved telling av tokener

Token-tallene som blir brukt til komprimeringsbeslutninger, blir lagra i cachen og blir oppdatert trinnvis når det kun er lagt til nye meldingar. Dette reduserer ikkje modellkonteksten direkte, men det reduserer CPU-kostnaden og ventetiden ved å avgjøre når komprimering er nødvendig.

## Hva som ennå ikkje er et fullstendig enhetlig lag

Den noverande implementeringen tilbyr ennå ikkje alle følgende elementer som én leverandørnøytral manager:

- et enhetlig `ContextManager` og `ContextBudget`;
- et `ToolResultRecord` med metadata om betydning og utkastelse;
- semantiske sammendrag som ikkje krever en `LLM`;
- automatisk henting og reinjeksjon av relevante artefakter;
- en sentral resultatmanager som garanterer `Artifact`-konvertering for hvert verktøy som produserer binærfiler; eller
- prioriteringsbevisst utkastelse på tvers av alle system-, historikk-, verktøyskjema- og resultatkategorier.

Kort sagt kombinerer uag for tiden deterministisk avkorting, Artifact-referanser, binær isolasjon, dynamisk verktøyvalg, historikksammendrag, leverandørkontinuitet og gjenoppretting etter overløp. Utviklingsplanen for et enhetlig kontekstlag er dokumentert i [UAG_CONTEXT_MANAGEMENT_DESIGN.md](UAG_CONTEXT_MANAGEMENT_DESIGN.md).
