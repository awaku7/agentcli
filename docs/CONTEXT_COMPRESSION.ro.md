# Compresia contextului și contextul de model delimitat

uag utilizează mai multe straturi pentru a menține contextul de model activ delimitat. Scopul este de a reduce token-urile de intrare inutile fără a elimina fișierele, rezultatele instrumentelor sau datele de sesiune de care utilizatorul ar putea încă avea nevoie.

Acest document descrie implementarea actuală. De asemenea, face distincția între comportamentul determinist și comportamentul specific furnizorului sau asistat de LLM.

## 1. Suprafață dinamică a instrumentelor

Nu este necesar ca fiecare definiție de instrument să fie trimisă către model la fiecare rundă.

- `tool_catalog` caută capacitățile disponibile.
- `tool_load` activează doar instrumentele necesare pentru sarcina curentă.
- `tool_catalog`, `tool_load` și `unload_tool` rămân disponibile ca instrumente de gestionare.
- Fluxurile Responses API compatibile cu GPT-5.4 pot utiliza Tool Search nativ pe partea de server.
- Modul Tool Search vechi restrânge specificațiile instrumentelor cu `tool_catalog` pe partea clientului.

Acest lucru reduce numărul de tokenuri de intrare utilizate de schemele instrumentelor, în special în instalațiile cu multe instrumente.

## 2. Rezultatele textuale voluminoase ale instrumentelor devin Artefacte

Când un rezultat textual al unui instrument depășește pragul Artifact, uag stochează rezultatul complet ca un Artifact și trimite modelului o referință limitată și o previzualizare în loc de textul complet.

Limitele implicite sunt:

```text
UAGENT_TOOL_RESULT_ARTIFACT_THRESHOLD_CHARS=100000
UAGENT_TOOL_RESULT_MAX_CHARS=12000
```

Reprezentarea vizibilă pentru model conține numele instrumentului, lungimea originală, o referință `artifact://`, calea de stocare și o previzualizare limitată. Rezultatul complet rămâne disponibil prin intermediul magazinului Artifact.

Pragul poate fi modificat cu `UAGENT_TOOL_RESULT_ARTIFACT_THRESHOLD_CHARS`. O valoare de `0` dezactivează promovarea Artifact. `UAGENT_TOOL_RESULT_MAX_CHARS` controlează politica obișnuită privind rezultatele limitate; `0` dezactivează acea limită obișnuită.

## 3. Recuperarea limitată a Artifact

Instrumentul de infrastructură `artifact_read` recuperează doar porțiunea solicitată dintr-un Artifact:

- `start_line` selectează prima linie.
- `max_lines` este limitat la 500.
- `max_chars` este limitat la 50.000 de caractere.
- Se pot utiliza atât un ID Artifact, cât și un URI `artifact://`.

Acest lucru permite inspectarea unui interval mic și relevant, în loc de reinjectarea întregului fișier sau a rezultatului unei comenzi în următoarea rundă a modelului.

Noile artefacte sunt stocate mai jos:

```text
~/.uag/artifacts/
```

Căile Artifact existente rămân lizibile din motive de compatibilitate.

## 4. Izolarea încărcăturii binare

Datele binare încorporate nu sunt trimise ca rezultat textual al instrumentului către următorul ciclu al modelului. Câmpurile de tip Base64 sunt înlocuite cu un marcator scurt, de exemplu:

```text
[sarcină utilă binară omisă din contextul LLM]
```

Interfața utilizatorului și clienții la distanță pot primi în continuare atașamente în memorie, iar fișierele salvate rămân disponibile prin intermediul căilor lor sau al referințelor Artifact. Acest lucru împiedică imaginile, fișierele audio, capturile de ecran și alte încărcături binare să umfle contextul textual al modelului.

Aceeași clasă de încărcături binare este curățată înainte de stocarea în SQLite și JSONL, împiedicând-o să revină ca o încărcătură de dimensiuni mari după reîncărcarea sesiunii.

## 5. Compresia automată a istoricului

uag poate comprima istoricul conversațiilor mai vechi atunci când numărul de mesaje sau numărul estimat de tokenuri atinge limita configurată.

Politica de compresie utilizează:

- numărul de mesaje care nu sunt de sistem;
- fereastra de context rezolvată a modelului, atunci când este disponibilă;
- `UAGENT_SHRINK_KEEP_LAST` (20 în mod implicit);
- `UAGENT_SHRINK_MAX_TOKENS` sau o suprascriere specifică modelului;
- `UAGENT_SHRINK_CNT`; și
- `UAGENT_SHRINK_RATIO` (0,5 în mod implicit atunci când se cunoaște o fereastră de context).

O limită specifică modelului poate fi furnizată astfel:

```text
UAGENT_SHRINK_MAX_TOKENS_<MODEL_NAME>
```

Un rezumat anterior nu este regenerat la fiecare tur. Histerezisul necesită acumularea unui istoric suficient de nou sau o altă depășire a bugetului de tokenuri înainte ca compresia să se execute din nou.

## 6. Rezumatele istoricului asistate de LLM

Când compresia automată utilizează LLM, mesajele mai vechi ale utilizatorului, ale asistentului și ale instrumentului sunt rezumate într-un mesaj de sistem continuu, în timp ce partea recentă este păstrată.

Istoricele lungi pot fi rezumate în porțiuni. Comenzile relevante sunt:

```text
UAGENT_SHRINK_CHUNK_SIZE=100
UAGENT_SHRINK_SINGLE_SHOT=1
```

Rezumatul este pliat înainte, în loc să se creeze o secvență nelimitată de mesaje de rezumat. Aceasta este o operațiune asistată de LLM și poate necesita solicitări suplimentare către furnizor.

## 7. Compresie deterministă de rezervă

Dacă un rezumat LLM nu este disponibil, uag poate păstra mesajele de sistem inițiale și doar cele mai recente mesaje. Limitele apelurilor de instrumente sunt reparate astfel încât istoricul rezultat să nu înceapă sau să se termine cu un apel de instrument orfan.

Încărcătorul și programul de curățare elimină, de asemenea, intrările irelevante pentru model sau nevalide, inclusiv mesajele exclusiv pentru interfața de utilizator, mesajele de control interne, liniile de jurnal defecte, rolurile neacceptate, rezultatele orfane ale instrumentelor și blocurile incomplete de apeluri de instrumente.

Când o sesiune este reîncărcată, promptul curent al sistemului este restaurat și sunt păstrate doar mesajele de sistem relevante injectate, cum ar fi contextul abilității sau al cârligului.

## 8. Recuperarea în caz de depășire a contextului

Dacă un furnizor raportează că fereastra de context a fost depășită, uag identifică un mesaj recent de dimensiuni mari din istoric și anulează acel mesaj și istoricul următor înainte de a încerca din nou. Aceasta este o soluție de rezervă reactivă, nu un înlocuitor pentru gestionarea normală a resurselor.

## 9. Continuarea și compactarea la nivelul furnizorului

Acolo unde este acceptat, Responses API utilizează `previous_response_id` pentru a continua un lanț de răspunsuri fără a retrimite de la client întregul istoric al răspunsurilor gestionat de furnizor.

Fluxurile Responses API trimit, de asemenea, configurația de compactare din partea furnizorului, utilizând același prag local de reducere. Comportamentul exact depinde de furnizor; Artifact local și politicile privind istoricul rămân măsurile de protecție neutre față de furnizor.

## 10. Eficiența numărării token-urilor

Numărul de token-uri utilizat pentru deciziile de compresie este stocat în cache și actualizat incremental atunci când au fost adăugate doar mesaje noi. Acest lucru nu reduce direct contextul modelului, dar reduce costul de procesare și latența deciziei privind momentul în care este necesară compresia.

## Ce nu constituie încă un strat unificat complet

Implementarea actuală nu oferă încă toate elementele următoare sub forma unui singur manager neutru față de furnizor:

- un `ContextManager` și un `ContextBudget` unificate;
- un `ToolResultRecord` cu metadate privind importanța și eliminarea;
- rezumate semantice care nu necesită un `LLM`;
- recuperarea și reinjectarea automată a artefactelor relevante;
- un manager central de rezultate care să garanteze conversia `Artifact` pentru fiecare instrument care generează fișiere binare; sau
- eliminarea ținând cont de prioritate în toate categoriile de sistem, istoric, schemă de instrumente și rezultate.

Pe scurt, uag combină în prezent trunchierea deterministă, referințele Artifact, izolarea binară, selecția dinamică a instrumentelor, rezumatele istorice, continuarea furnizorului și recuperarea în caz de depășire a capacității. Foaia de parcurs de proiectare pentru un strat de context unificat este documentată în [UAG_CONTEXT_MANAGEMENT_DESIGN.md](UAG_CONTEXT_MANAGEMENT_DESIGN.md).
