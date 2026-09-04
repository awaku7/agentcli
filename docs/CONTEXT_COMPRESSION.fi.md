# Kontekstin pakkaus ja rajattu mallikonteksti

uag käyttää useita tasoja pitääkseen aktiivisen mallikontekstin rajattuna. Tavoitteena on vähentää tarpeettomia syöttötunnuksia poistamatta tiedostoja, työkalun tuloksia tai istuntotietoja, joita käyttäjä saattaa vielä tarvita.

Tässä asiakirjassa kuvataan nykyinen toteutus. Siinä erotetaan myös deterministinen käyttäytyminen palveluntarjoajakohtaisesta tai LLM:n avustamasta käyttäytymisestä.

## 1. Dynaaminen työkalupinta

Kaikkia työkalumääritelmiä ei tarvitse lähettää malliin jokaisella vuorolla.

- `tool_catalog` etsii käytettävissä olevia ominaisuuksia.
- `tool_load` ottaa käyttöön vain nykyiseen tehtävään tarvittavat työkalut.
- `tool_catalog`, `tool_load` ja `unload_tool` pysyvät käytettävissä hallintatyökaluina.
- GPT-5.4-yhteensopivat Responses API-virrat voivat käyttää natiivia palvelinpuolen Tool Search:tä.
- Vanha Tool Search-tila rajoittaa työkalujen määrityksiä `tool_catalog`-komennolla asiakaspuolella.

Tämä vähentää työkaluskeemojen käyttämiä syöttötunnuksia, etenkin asennuksissa, joissa on paljon työkaluja.

## 2. Suuret tekstimuotoiset työkalun tulokset muuttuvat artefakteiksi

Kun tekstimuotoinen työkalun tulos ylittää Artifact-kynnyksen, uag tallentaa täydellisen tuloksen Artifact-muodossa ja lähettää mallille rajoitetun viitteen ja esikatselun koko tekstin sijaan.

Oletusrajat ovat:

```text
UAGENT_TOOL_RESULT_ARTIFACT_THRESHOLD_CHARS=100000
UAGENT_TOOL_RESULT_MAX_CHARS=12000
```

Mallille näkyvä esitys sisältää työkalun nimen, alkuperäisen pituuden, `artifact://`-viittauksen, tallennuspolun ja rajatun esikatselun. Koko tulos on edelleen saatavilla Artifact-tallennustilan kautta.

Kynnysarvoa voidaan muuttaa `UAGENT_TOOL_RESULT_ARTIFACT_THRESHOLD_CHARS`:lla. Arvo `0` poistaa Artifact-edistämisen käytöstä. `UAGENT_TOOL_RESULT_MAX_CHARS` ohjaa tavanomaista rajoitetun tuloksen käytäntöä; `0` poistaa kyseisen tavanomaisen rajan käytöstä.

## 3. Rajattu Artifact-hakutoiminto

`artifact_read`-infrastruktuurityökalu hakee vain pyydetyn osan Artifact:stä:

- `start_line` valitsee ensimmäisen rivin.
- `max_lines` on rajoitettu arvoon 500.
- `max_chars` on rajoitettu 50 000 merkkiin.
- Voidaan käyttää sekä Artifact-tunnusta että `artifact://`-URI:tä.

Tämä mahdollistaa pienen, merkityksellisen alueen tarkastelun sen sijaan, että koko tiedosto tai komennon tulos syötettäisiin uudelleen seuraavaan mallin kierrokseen.

Uudet artefaktit tallennetaan seuraavasti:

```text
~/.uag/artifacts/
```

Olemassa olevat vanhat Artifact-polut pysyvät luettavissa yhteensopivuuden vuoksi.

## 4. Binaarisen hyötykuorman eristäminen

Sisäiset binaaritiedot eivät lähetetä tekstimuotoisena työkalun tuloksena seuraavalle mallikierrokselle. Base64-muotoiset kentät korvataan lyhyellä merkillä, kuten:

```text
[binaarinen hyötykuorma jätetty pois LLM-kontekstista]
```

Käyttöliittymä ja etäasiakkaat voivat edelleen vastaanottaa muistissa olevia liitteitä, ja tallennetut tiedostot ovat edelleen käytettävissä niiden polkujen tai Artifact-viittausten kautta. Tämä estää kuvia, ääntä, kuvakaappauksia ja muita binäärisiä hyötykuormia paisuttamasta tekstimuotoista mallikontekstia.

Saman luokan binäärinen hyötykuorma puhdistetaan ennen tallennusta SQLiteen ja JSONL:ään, mikä estää sen palaamisen suurena hyötykuormana istunnon uudelleenlataamisen jälkeen.

## 5. Automaattinen historiatiedostojen pakkaus

uag voi pakata vanhemman keskusteluhistorian, kun viestien lukumäärä tai arvioitu merkkimäärä saavuttaa määritetyn rajan.

Pakkauskäytäntö käyttää seuraavia tekijöitä:

- järjestelmän ulkopuolisten viestien lukumäärää;
- mallin ratkaistua konteksti-ikkunaa, jos se on käytettävissä;
- `UAGENT_SHRINK_KEEP_LAST` (oletusarvo 20);
- `UAGENT_SHRINK_MAX_TOKENS` tai mallikohtainen ohitus;
- `UAGENT_SHRINK_CNT`; ja
- `UAGENT_SHRINK_RATIO` (oletusarvo 0,5, kun konteksti-ikkuna on tiedossa).

Mallikohtainen raja voidaan antaa seuraavasti:

```text
UAGENT_SHRINK_MAX_TOKENS_<MODEL_NAME>
```

Aikaisempaa yhteenvetoa ei luoda uudelleen jokaisella kierroksella. Hystereesin vuoksi tarvitaan riittävästi uutta historiaa tai toinen token-budjetin ylitys, ennen kuin pakkaus suoritetaan uudelleen.

## 6. LLM:n avulla laaditut historiayhteenvedot

Kun automaattinen tiivistys käyttää LLM:tä, vanhemmat käyttäjä-, avustaja- ja työkaluviestit tiivistetään jatkuvasti päivittyvään järjestelmäviestiin, samalla kun viimeisimmät viestit säilytetään.

Pitkät historiat voidaan tiivistää osissa. Asiaankuuluvat asetukset ovat:

```text
UAGENT_SHRINK_CHUNK_SIZE=100
UAGENT_SHRINK_SINGLE_SHOT=1
```

Yhteenveto taitetaan eteenpäin sen sijaan, että luotaisiin rajaton sarja yhteenvetoviestejä. Tämä on LLM:n avustama toiminto, joka voi vaatia lisäpyyntöjä palveluntarjoajalta.

## 7. Deterministinen varapakkaus

Jos LLM-yhteenvetoa ei ole saatavilla, uag voi säilyttää järjestelmän ensimmäiset viestit ja vain uusimmat viestit. Työkalukutsujen rajat korjataan siten, että tuloksena oleva historia ei ala tai pääty orpoon työkalukutsuun.

Lataaja ja puhdistaja poistavat myös mallin kannalta merkityksettömät tai virheelliset merkinnät, mukaan lukien pelkästään käyttöliittymään liittyvät viestit, sisäiset ohjausviestit, rikkoutuneet lokirivit, tuottamattomat roolit, orpoja työkaluja koskevat tulokset sekä epätäydelliset työkalukutsulohkot.

Kun istunto ladataan uudelleen, nykyinen järjestelmäkehote palautetaan ja vain merkitykselliset lisätyt järjestelmäviestit, kuten taito- tai koukkukonteksti, säilytetään.

## 8. Kontekstin ylivuodon korjaus

Jos palveluntarjoaja ilmoittaa, että konteksti-ikkuna ylittyi, uag tunnistaa suuren, äskettäisen historiaviestin ja peruu kyseisen viestin sekä sitä seuraavan historian ennen uuden yrityksen tekemistä. Tämä on reaktiivinen varajärjestelmä, ei korvike tavalliselle budjetoinnille.

## 9. Palveluntarjoajapuolen jatkaminen ja tiivistäminen

Siellä missä se tuetaan, Responses API käyttää `previous_response_id`:tä jatkaakseen vastausketjua ilman, että koko palveluntarjoajan hallinnoimaa vastaushistoriaa lähetetään uudelleen asiakkaalta.

Responses API-virrat lähettävät myös palveluntarjoajan puolella tapahtuvan tiivistämisen määritykset käyttäen samaa paikallista tiivistämiskynnystä. Tarkka käyttäytyminen riippuu palveluntarjoajasta; paikalliset Artifact- ja historiakäytännöt pysyvät palveluntarjoajasta riippumattomina suojatoimina.

## 10. Tunnisteiden laskennan tehokkuus

Pakkauspäätöksiin käytetyt tunnistemäärät tallennetaan välimuistiin ja päivitetään inkrementaalisesti, kun vain uusia viestejä on lisätty. Tämä ei suoraan pienennä mallikontekstia, mutta se vähentää CPU-kuormitusta ja viivettä päätettäessä, milloin tiivistys on tarpeen.

## Mikä ei vielä ole täysin yhtenäistetty kerros

Nykyinen toteutus ei vielä tarjoa kaikkia seuraavia ominaisuuksia yhtenä palveluntarjoajasta riippumattomana hallintatyökaluna:

- yhtenäistetyt `ContextManager` ja `ContextBudget`;
- `ToolResultRecord`, jossa on tärkeys- ja poistometatiedot;
- semanttisia yhteenvetoja, jotka eivät vaadi `LLM`:tä;
- merkityksellisten artefaktien automaattinen haku ja uudelleenlisäys;
- keskitetty tuloshallintaohjelma, joka takaa `Artifact`-muunnoksen jokaiselle binääritiedostoja tuottavalle työkalulle; tai
- prioriteettia huomioiva poisto kaikissa järjestelmä-, historia-, työkaluskeema- ja tulosluokissa.

Lyhyesti sanottuna uag yhdistää tällä hetkellä deterministisen katkaisun, Artifact-viittaukset, binäärien eristämisen, dynaamisen työkalunvalinnan, historiayhteenvedot, palveluntarjoajan jatkumisen ja ylivuodon palautuksen. Yhtenäistetyn kontekstikerroksen suunnittelusuunnitelma on dokumentoitu viitteessä [UAG_CONTEXT_MANAGEMENT_DESIGN.md](UAG_CONTEXT_MANAGEMENT_DESIGN.md).
