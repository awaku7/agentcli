# Kontextustömörítés és korlátozott modellkontextus

A uag több réteget használ az aktív modellkontextus korlátozására. A cél az, hogy csökkentsük a felesleges bemeneti tokenek számát anélkül, hogy eltávolítanánk azokat a fájlokat, szerszámeredményeket vagy munkamenetadatokat, amelyekre a felhasználónak még szüksége lehet.

Ez a dokumentum a jelenlegi megvalósítást írja le. Ezenkívül megkülönbözteti a determinisztikus viselkedést a szolgáltató-specifikus vagy a LLM által támogatott viselkedéstől.

## 1. Dinamikus eszközfelület

Nem minden eszközdefiníciót kell minden körben elküldeni a modellnek.

- A `tool_catalog` átkutatja a rendelkezésre álló képességeket.
- A `tool_load` csak az aktuális feladathoz szükséges eszközöket aktiválja.
- A `tool_catalog`, `tool_load` és `unload_tool` továbbra is elérhetőek kezelőeszközként.
- A GPT-5.4-kompatibilis Responses API-folyamatok használhatják a natív, szerveroldali Tool Search-öt.
- A régi Tool Search mód a kliens oldalon a `tool_catalog` segítségével szűkíti az eszközspecifikációkat.

Ez csökkenti az eszközsémák által használt bemeneti tokenek számát, különösen olyan telepítések esetén, ahol sok eszköz van.

## 2. A nagy méretű szöveges eszközeredmények artefaktumokká válnak

Amikor egy szöveges eszközeredmény meghaladja a Artifact küszöbértéket, a uag a teljes eredményt Artifact-ként tárolja, és a teljes szöveg helyett egy korlátozott hivatkozást és előnézetet küld a modellnek.

Az alapértelmezett határértékek a következők:

```text
UAGENT_TOOL_RESULT_ARTIFACT_THRESHOLD_CHARS=100000
UAGENT_TOOL_RESULT_MAX_CHARS=12000
```

A modell számára látható ábrázolás tartalmazza az eszköz nevét, az eredeti hosszúságot, egy `artifact://` hivatkozást, a tárolási útvonalat és egy korlátozott előnézetet. A teljes eredmény továbbra is elérhető marad a Artifact-tárolón keresztül.

A küszöbérték a `UAGENT_TOOL_RESULT_ARTIFACT_THRESHOLD_CHARS` segítségével módosítható. A `0` érték letiltja a Artifact-promóciót. A `UAGENT_TOOL_RESULT_MAX_CHARS` szabályozza a szokásos korlátozott eredményre vonatkozó szabályt; a `0` érték letiltja ezt a szokásos korlátot.

## 3. Korlátozott Artifact-letöltés

A `artifact_read` infrastruktúra-eszköz csak az Artifact kért részét tölti le:

- A `start_line` az első sort választja ki.
- A `max_lines` értéke legfeljebb 500 lehet.
- A `max_chars` értéke legfeljebb 50 000 karakter lehet.
- Használható mind az Artifact azonosító, mind az `artifact://` URI.

Ez lehetővé teszi egy kis, releváns tartomány vizsgálatát ahelyett, hogy a teljes fájlt vagy a parancs eredményét újra beolvasná a modell következő körébe.

Az új artefaktumok az alábbiakban kerülnek tárolásra:

```text
~/.uag/artifacts/
```

A kompatibilitás érdekében a meglévő, régebbi Artifact útvonalak továbbra is olvashatók maradnak.

## 4. Bináris hasznosadat-elkülönítés

A beágyazott bináris adatok nem kerülnek elküldésre szöveges eszköz-eredményként a következő modellfutásba. A Base64 formátumú mezőket egy rövid jelölővel helyettesítik, például:

```text
[bináris hasznos adat kihagyva a LLM kontextusból]
```

A felhasználói felület és a távoli kliensek továbbra is fogadhatnak memóriában tárolt mellékleteket, a mentett fájlok pedig továbbra is elérhetők az elérési útjaikon vagy a Artifact hivatkozásokon keresztül. Ez megakadályozza, hogy a képek, hangfájlok, képernyőképek és egyéb bináris hasznos adatok felfújják a szöveges modell kontextusát.

Ugyanazon osztályba tartozó bináris hasznos adatokat az SQLite-ba és JSONL-be történő mentés előtt megtisztítják, így megakadályozva, hogy a munkamenet újratöltése után nagy méretű hasznos adatként jelenjenek meg.

## 5. Automatikus előzménytömörítés

A uag képes a régebbi beszélgetési előzményeket tömöríteni, amikor az üzenetek száma vagy a becsült tokenek száma eléri a beállított határt.

A tömörítési szabály a következőket veszi figyelembe:

- a nem rendszerüzenetek számát;
- a modell feloldott kontextusablakát, ha rendelkezésre áll;
- `UAGENT_SHRINK_KEEP_LAST` (alapértelmezés szerint 20);
- `UAGENT_SHRINK_MAX_TOKENS` vagy egy modellspecifikus felülírás;
- `UAGENT_SHRINK_CNT`; és
- `UAGENT_SHRINK_RATIO` (alapértelmezés szerint 0,5, ha a kontextusablak ismert).

A modellspecifikus korlát a következőképpen adható meg:

```text
UAGENT_SHRINK_MAX_TOKENS_<MODEL_NAME>
```

A korábbi összefoglalót nem minden körben generálják újra. A hiszterézis miatt elegendő új előzménynek kell felhalmozódnia, vagy újabb token-keret túllépésnek kell bekövetkeznie, mielőtt a tömörítés újra elindulna.

## 6. LLM-alapú előzményösszefoglalók

Amikor az automatikus tömörítés a LLM-at használja, a régebbi felhasználói, asszisztensi és eszközüzeneteket egy gördülő rendszerüzenetbe foglalja össze, miközben a legfrissebb rész megmarad.

A hosszú előzmények szakaszosan is összefoglalhatók. A vonatkozó vezérlők:

```text
UAGENT_SHRINK_CHUNK_SIZE=100
UAGENT_SHRINK_SINGLE_SHOT=1
```

Az összefoglalás előre hajtódik, ahelyett, hogy korlátlan sorozatot hozna létre az összefoglaló üzenetekből. Ez egy LLM által támogatott művelet, amely további szolgáltatói kéréseket igényelhet.

## 7. Determinisztikus tartalék tömörítés

Ha egy LLM összefoglaló nem áll rendelkezésre, a uag megtarthatja a legelső rendszerüzeneteket és csak a legfrissebb üzeneteket. Az eszközhívások határait kijavítják, hogy a kapott előzmények ne árva eszközhívással kezdődjenek vagy végződjenek.

A betöltő és a tisztítóprogram eltávolítja a modell szempontjából irreleváns vagy érvénytelen bejegyzéseket is, beleértve a kizárólag a felhasználói felületre vonatkozó üzeneteket, a belső vezérlőüzeneteket, a hibás naplóbejegyzéseket, a nem támogatott szerepköröket, az árva eszközhívási eredményeket és a hiányos eszközhívási blokkokat.

Amikor egy munkamenetet újratöltenek, az aktuális rendszerparancssor visszaáll, és csak a releváns, beillesztett rendszerüzenetek – például a készség- vagy hook-kontextus – maradnak meg.

## 8. Kontextus-túlcsordulás helyreállítása

Ha egy szolgáltató jelenti, hogy a kontextusablak mérete túllépte a határt, a uag azonosít egy nagy méretű, közelmúltbeli előzményüzenetet, majd visszavonja azt az üzenetet és az azt követő előzményeket, mielőtt újra megpróbálná a műveletet. Ez egy reaktív tartalékmegoldás, nem pedig a normál kapacitástervezés helyettesítője.

## 9. Szolgáltatói oldali folytatás és tömörítés

Ahol támogatott, a Responses API a `previous_response_id`-t használja a válaszlánc folytatásához anélkül, hogy a kliensről újra elküldené a szolgáltató által kezelt teljes válaszelőzményeket.

A Responses API-folyamatok ugyanazt a helyi zsugorítási küszöbértéket használva szolgáltatói oldali tömörítési konfigurációt is elküldenek. A pontos viselkedés szolgáltatótól függ; a helyi Artifact és az előzmény-szabályok továbbra is szolgáltató-semleges biztosítékok maradnak.

## 10. A tokenek számlálásának hatékonysága

A tömörítési döntésekhez használt tokenszámokat gyorsítótárba tárolják, és csak akkor frissítik inkrementálisan, ha új üzenetek kerültek hozzáadásra. Ez nem csökkenti közvetlenül a modellkontextust, de csökkenti a tömörítés szükségességének eldöntéséhez szükséges CPU-terhelést és késleltetést.

## Mi még nem alkot teljes, egységes réteget

A jelenlegi megvalósítás még nem biztosítja az alábbiak mindegyikét egyetlen szolgáltatótól független kezelőként:

- egységes `ContextManager` és `ContextBudget`;
- `ToolResultRecord` fontossági és eltávolítási metaadatokkal;
- olyan szemantikai összefoglalók, amelyek nem igényelnek `LLM`-at;
- a releváns Artifacts automatikus visszakeresése és újrabeillesztése;
- egy központi Result Manager, amely minden bináris fájlt előállító eszköz esetében garantálja a `Artifact` konverziót; vagy
- prioritásérzékeny eltávolítás az összes rendszer-, előzmény-, eszköz-séma- és eredménykategóriában.

Röviden: a uag jelenleg ötvözi a determinisztikus csonkítást, a Artifact hivatkozásokat, a bináris elszigetelést, a dinamikus eszközválasztást, a történeti összefoglalókat, a szolgáltató folytonosságát és a túlcsordulás utáni helyreállítást. Az egységes kontextusréteg tervezési ütemtervét a [UAG_CONTEXT_MANAGEMENT_DESIGN.md](UAG_CONTEXT_MANAGEMENT_DESIGN.md) dokumentum tartalmazza.
