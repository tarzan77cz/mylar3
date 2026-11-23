# Opravy nálezů z review 2026-11-22, čtvrtá část (data sérií, jména souborů, pull list)

Session bez dozoru podle [FIX_PROMPT-2026-11-22-part4.md](FIX_PROMPT-2026-11-22-part4.md), nálezy R29–R33 z
[REVIEW-2026-11-22.md](REVIEW-2026-11-22.md) (kap. 4 a rozhodnutí v kap. 11). Pořadí oprav R31 → R32 → R30 → R29 →
R33, u každého nejdřív test, který před opravou selhal, a teprve potom oprava. Hotovo 22. 11. 2026 kolem 23:35 SEČ.

## 1. Prostředí

- Worktree `/data/Tarzan/Cursor/Mylar-review-2026-11-22-part4` (na Z2 `/share/Tarzan/Cursor/Mylar-review-2026-11-22-part4`),
  větev `claude/review-2026-11-22-part4` z `python3-dev` na `187c958e`.
- Testy v image `mylar3:local` `sha256:616267dfa1c56951ef72e540a4bdce2eb2f7a2b2d0c6ef2cd3f693657850d072`
  (vytvořen 22. 11. 2026 20:59 SEČ), Python 3.8.2. pytest jen v dočasném kontejneru.
- **Nic se nenasadilo ani nerestartovalo.** Žádný `docker cp`, `docker exec` do `mylar`, žádné volání API ani
  webových akcí, žádný dotaz do `mylar.db`, nic v `/comics`, `/downloads`, `/config`. Bez sítě (ComicVine i pull
  list podvržené). Image se nepřestavoval. Hlavní strom a worktree třetí části nedotčené.
- Číst se smělo jen `docker logs mylar-2026-09-11` a `docker logs mylar`: použité pro seznam sérií u R31 (kap. 4).
  Časy v logu jsou UTC, níž přepočtené na pražský čas.

## 2. Testy

| | `tests/` | `tests_db/` |
|---|---|---|
| Výchozí stav (čistý worktree) | **131 passed** | **142 passed** |
| Konečný stav | **131 passed** | **176 passed** (34 nových) |

- `ast.parse` všech změněných modulů v 3.8.2 před každým commitem: OK.
- Import všech modulů `mylar.*` v 3.8.2 (`.scratch/review-2026-11-22/try_imports.py`, `--network none`):
  **71 ze 71 OK**. Selhání jen v `lib/` (`lib.certgen`, `lib.utorrent.client`, `lib.deluge_client.tests`), mimo rozsah.
- U R32 a R29 navíc ověřeno odložením opravy (`git stash` jen kódu ve worktree): bez opravy padají přesně nové
  testy (R32: 4, R29: 6), kontrolní testy a testy R17 procházejí, po vrácení opravy prochází vše.
- Nové pomocné soubory testů: [tests_db/cvxml.py](../tests_db/cvxml.py) (podvržené XML z ComicVine podle
  `repro_cv.py`).
- Upravený existující test: fixture `refresh` v [tests_db/test_pp_refresh.py](../tests_db/test_pp_refresh.py)
  (R17) vracela jako `issuedata` čísla `[5, 6]`. Skutečný `addComictoDB` vrací seznam slovníků s `IssueID` a s tím
  pojistka R32 pracuje, proto fixture vrací `[{'IssueID': 'I5', …}, {'IssueID': 'I6', …}]`. Testy R17 kontrolují
  totéž co dřív a procházejí.

## 3. Nálezy

| ID | Stav | Commit | Nové testy (padalo před opravou) | Poznámka |
|---|---|---|---|---|
| R31 | **opraveno** | `2c243f83` | 6 (4) | Reprodukováno testy podle `repro_cv.py`: `GetIssuesInfo` i `getComic(…, 'issue')` vracely pro sérii `firstdate == '2099-00-00'` i s daty `2018-06-01` a `2018-07-01`. `addComictoDB` u nové série s CV `ComicYear='0000'` (podvržené `cv.getComic` pro `comic`/`firstissue`, `issue` přes skutečný `GetIssuesInfo`) vybral **2026** místo 2018. Oprava: porovnání `CoverDate < firstdate` je zase pro obě větve jako v upstreamu `b609c28c`, jinak beze změny. Kontrolní (prošly i před opravou): bez jakéhokoli data zůstane `2099-00-00` a `addComictoDB` použije dnešní fallback (aktuální rok). Test s `0000-00-00` u jednoho issue padal také (2099), ověřuje, že se `0000-00-00` nebere jako minimum. Dopad: refresh a přidání série bez CV `start_year` berou rok z nejstarší obálky. PP a pull list beze změny. |
| R32 | **opraveno** | `0c35985c` | 7 (4) | Reprodukováno: (a) `repro_cv.py` scénář 2: první issue bez `issue_number` tiše zmizelo (bez WARN), třetí převzalo číslo `2` druhého. (b) Issue, jehož zpracování vyhodí jinou výjimku (podvržený `FileChecker.checkthedate` při popisu „print and digital“), zmizelo a `getComic` vrátil zbytek. (c) `dbUpdate` nad DB s issue `Downloaded` + `Location` a novými daty bez něj issue smazal. **Oprava v `cv.GetIssuesInfo` (jen série, `arcid is None`):** `tempissue` je pro každé issue nový (`{'Issue_Name': None}`). Issue bez čísla se nepřidá a zaloguje se WARN s `Issue_ID`. Jiná výjimka = ERROR s `Issue_ID` a tracebackem a `GetIssuesInfo` vrátí `(None, firstdate)`. `getComic(…, 'issue')` pak vrátí `None` jako při chybě CV, takže `addComictoDB` skončí `incomplete` a `dbUpdate` nic nesmaže. **Story arc** (`arcid` zadané) beze změny: sdílený `tempissue`, chybné issue se přeskočí (kontrolní test). **Pojistka v `updater.dbUpdate`** (upstream kód, větev `CV_ONETIMER`, kudy vede scénář) před `DELETE`: když v `issues` této série existuje issue se `Status` `Downloaded`/`Archived`/`Snatched` nebo s vyplněnou `Location`, jehož `IssueID` v `chkstatus['issuedata']` chybí, zaloguje se WARN `[REFRESH-GUARD]` se seznamem IssueID, `GLOBAL_MESSAGES` dostane „Failure refreshing …“, `comics.Status` se vrátí na stav před refreshem a nic se nesmaže. Pokrývá i neúplné stránkování CV. Kontrolní: běžný refresh se všemi issue smaže, vloží a obnoví stavy jako dřív. Chybějící issue `Wanted` bez souboru refresh nezastaví a zmizí jako dřív. Testy R17 procházejí. Odchylky od zadání v kap. 5. |
| R30 | **opraveno** | `c8e833dc` | 8 (3) | Blok „check for year change“ přesunut beze změny do funkce `importer.rename_2099_folder(comlocation, stored_year, SeriesYear)`, aby šel testovat se skutečnými složkami v `tmp_path` a skutečným `shutil.move`. `addComictoDB` ji volá na stejném místě. Pak testy, pak oprava. Reprodukováno: `Spider-Man 2099` (bez roku) → `Spider-Man 2014`, `…/2099/Y` → přejmenovaná nadřazená složka `…/2026/Y`, existující `Y (2026)` → `Y (2026)/Y (2099)/…` (scénář I z `repro_rename.py`). **Oprava:** nahrazuje se jen `(2099)` v posledním prvku cesty a jen když tam je právě jednou. Jinak INFO `[YEAR-RENAME] Cannot tell the year apart…` a složka zůstane. Když cílová složka existuje, nic se nepřesune, `comlocation` zůstane stará a zaloguje se WARN s oběma cestami. Větev „stará složka neexistuje, nová ano“ beze změny. Prošly i před opravou: `Spider-Man 2099 (2099)` → `(2014)` a `…/2099/Y (2099)` (stará logika u víc výskytů brala ten nejpravější) a kontrolní `Y (2099)` → `Y (2026)` bez kolize, chybějící stará složka, rok ≠ 2099. |
| R29 | **opraveno** | `46d7b846` | 9 (6) | Reprodukováno testy podle `repro_rename.py`: C (cíl jednou existuje) a C2 (soubor chvíli chybí) → záznam zmizel. Registr s `.cbr` a `Location` `.cbz` → nic se nepřejmenovalo. E (`previewRename`) → záznam přepsán náhledovým jménem. D (`manualRename` s odhadem) → záznam nevznikl. Souběh 2 × 50 registrací → v registru 40 ze 100. **Oprava v `helpers`:** záznam se odebere jen po úspěšném přejmenování, když nové jméno už je správné (odhad vyšel), nebo když `Location` odhad nenese (jiné jméno bez ohledu na příponu a bez `0000-00`). Při každém selhání záznam zůstane a příští refresh to zkusí znovu. Porovnání bez přípony (`_same_name_ignoring_extension`). Odebrání na konci pod zámkem s novým načtením registru, a jen když záznam pořád odpovídá (novější registraci z PP nesmaže). Modulový `PROVISIONAL_RENAMES_LOCK` (`threading.RLock`) kolem load–modify–save v `register_provisional_rename` i v `rename_placeholder_dated_files`. `save_provisional_renames` píše přes `tempfile.mkstemp(dir=DATA_DIR)` a `os.replace`. **`filers.rename_file` už neregistruje**, vrací nový klíč `provisional_date` (stávající klíče beze změny). Stejný klíč vrací `helpers.rename_param` (dřív příznak zahazoval). `webserve.manualRename` po úspěšném `shutil.move` registruje, když je `provisional_date`. Odpověď `manualRename` beze změny. Kontrolní: G (po skutečném přejmenování a další změně data žádná smyčka), přejmenováno mezitím → záznam pryč bez přejmenování, `manualRename` s datem z CV nic neregistruje. Kdo teď registruje, viz kap. 5. |
| R33 | **opraveno** | `91b57e03` | 4 (3) | Reprodukováno: týden s řádky providera (issue bez CV data `Wanted` se `SHIPDATE`, issue `Snatched`, nesledovaná série) a fallback → týden smazaný a naplněný jen issues s CV `ReleaseDate` jako `Skipped`. Řádek stejné série a čísla v **jiném** týdnu byl přepsán (upsert klíčoval jen `DYNAMICNAME` + `ISSUE`). Řádek providera bez `IssueID` byl nahrazen. **Oprava:** žádný `DELETE`. Fallback načte řádky týdne (`weeknumber`/`year` jako dřív `DELETE`) a přeskočí issue, které tam už je podle `IssueID` nebo podle `DynamicName` + `ISSUE` (řádek providera, který ještě nemá `IssueID`). Nová issue vloží s klíčem `IssueID` + `weeknumber` + `year`, existující řádky nemění (ani `STATUS`). Prázdný týden se naplní jako dřív (kontrolní test, stejná návratová hodnota). Návratová hodnota (`count` = počet nalezených sledovaných issues) a volání `new_pullcheck` beze změny. Log nově říká, kolik issues přidal. |

## 4. R31: série s rokem z fallbacku (log od 11. 9. 2026)

Hledáno „No usable Series Year from CV“ a „[PULL-SHIPDATE] No usable Series Year“ v `docker logs mylar-2026-09-11`
(11. 9. až 22. 11.) a `docker logs mylar` (od 22. 11. 21:17). V novém kontejneru nic. Ve starém 9 řádků, všechny
„[PULL-SHIPDATE] … using pull-list ship date year 2026“. Hláška „assuming current year“ v logu není ani jednou.
ComicID z kontextu (`Refreshing/Updating …` / `[MASS-ADD] Now adding ComicID`).

| Čas (SEČ) | Série | ComicID | Přidělený rok | Odkud |
|---|---|---|---|---|
| 25. 10. 2026 17:32:35 | Valiant Beyond: X-O Manowar - The Pilgrimage | 177684 | 2026 | mass-refresh, dřív `2099` |
| 25. 10. 2026 17:32:47 | X-O Manowar: Black, White & Gold | 177686 | 2026 | mass-refresh, dřív `2099` |
| 25. 10. 2026 17:32:59 | Amazing Spider-Man: Halloween Special | 177664 | 2026 | mass-refresh, dřív `2099` |
| 25. 10. 2026 17:33:11 | Iron Man: Racing Towards Doom | 177672 | 2026 | mass-refresh, dřív `2099` |
| 25. 10. 2026 17:33:23 | Punisher Showdowns: Black Widow | 177676 | 2026 | mass-refresh, dřív `2099` |
| 27. 10. 2026 20:59:56 | X-O Manowar: Black, White & Gold (znovu) | 177686 | 2026 | mass-refresh |
| 19. 11. 2026 17:51:30 | Vampirella: Paradise | 178066 | 2026 | mass-add |
| 19. 11. 2026 17:52:25 | Chainkata | 178060 | 2026 | mass-add |
| 19. 11. 2026 17:54:10 | Uncle Scrooge: A Christmas Carol | 178065 | 2026 | mass-add |

(UTC v logu: 16:32–16:33, 19:59 a 16:51–16:54.)

**Žádnou z nich nezpůsobil R31.** Ve všech případech měla série v CV jediné issue a to v tu chvíli nemělo datum
obálky (`issue_collection` v logu: `IssueDate '0000-00-00'`). `firstdate` by zůstal `2099-00-00` i s opravou
a rok by se vzal z pull listu stejně. Rok 2026 odpovídá ship date (21. 10. a 18. 11. 2026). Série, u kterých CV
`start_year` chybí, ale issues data obálky mají (ty R31 opravdu poškodil), se v logu od 11. 9. neobjevily.
V logu tedy chybí doklad, že by R31 od 11. 1. 2026 (`89ac088d`) dal sérii špatný rok, a nic opravovat netřeba.

Co udělá příští refresh (z kódu):
- `addComictoDB` počítá `SeriesYear` při každém refreshi znovu a zapíše ho do `comics.ComicYear`. Při chybějícím
  CV `start_year` vezme nejdřív rok obálky prvního issue (`getComic(…, 'firstissue')`, cesta mimo R31), teprve pak
  `firstdate` (R31) a pull list nebo aktuální rok. U 177684, 177664, 177672 a 177676 má issue od 26.–27. 10.
  obálku 2026-10 nebo 2026-12, takže rok zůstane 2026.
- Složka se přejmenuje jen při uloženém roku `2099` (R30). Při uloženém 2026 se složka nepřejmenuje, ani kdyby nový
  rok vyšel jinak. Pak by `ComicYear` a rok ve jméně složky nesouhlasily (upstream chování, mimo rozsah).
- 177686, 178066, 178060 a 178065 neměly v posledním logovaném refreshi datum obálky. Dokud ho nemají, rok zase
  přijde z pull listu (`helpers.weekly_series_year`). Když v `weekly` jejich týden nebude, dostanou **aktuální rok**,
  takže po Novém roce 2027. R33 to zmírní (fallback už týden nemaže), úplně to nevyřeší.
- Mimochodem: review uvádí, že v logu od 11. 9. „Renaming directory“ není. Ve skutečnosti je tam 5× (25. 10.
  17:32–17:33 SEČ, `… (2099)` → `… (2026)`, vždy jediné `(2099)` ve jméně složky a bez kolize). Nová logika R30 by
  je přejmenovala stejně.

## 5. Otevřené otázky a konzervativní volby

**R32**
1. **Série, kterou pojistka zablokuje.** Když CV issue opravdu odstraní (sloučení, přečíslování) a uživatel ho má
   stažené nebo `Snatched`, refresh té série se při každém běhu zastaví s WARN `[REFRESH-GUARD] … missing … (IssueID …)`
   a v UI se ukáže „Failure refreshing …“. Data se neztratí. Série se ale přestane aktualizovat: `updateissuedata`
   ještě před pojistkou zapíše nová issue s CV daty (`issue_collection(nostatus='True')`), takže nová issue v DB
   jsou, ale zůstanou se `Status` NULL, dokud uživatel issue nevyřeší ručně (změnit stav nebo smazat záznam).
   Alternativa k rozhodnutí: při chybějícím issue jen vynechat `DELETE` a refresh dokončit nedestruktivně (staré
   řádky zůstanou, nové dostanou stav).
2. **`continue` místo `return`.** Ostatní chyby refreshe v `dbUpdate` končí `return`, tedy celý běh. Pojistka se
   opakuje při každém refreshi, proto dělá `continue` (další série se refreshují dál). Hláška a `GLOBAL_MESSAGES`
   jsou stejné jako u jiné chyby. `comics.Status` vrací na hodnotu před refreshem (`addComictoDB` ho přepnul na
   `Loading`, takže by pozastavená série zůstala `Loading`).
3. **Annualy pojistka nehlídá.** `chkstatus['anndata']` se nedá spolehlivě porovnat: při `ANNUALS_ON` vypnutém
   `dbUpdate` annualy v snapshotu nemá, ale `DELETE FROM annuals` přesto udělá (upstream). Ručně přidané annualy
   přicházejí přes `annual_check`/`annload` jinou cestou. `DELETE FROM annuals` zůstává jako dřív.
4. **Issue bez čísla** se vynechá úplně, i z výpočtu `firstdate`. Výchozí `Issue_Name` je `None`, aby issue bez
   prvku `<name>` neshodilo refresh (dřív převzalo jméno předchozího issue).
5. Když se issue nedá přečíst v cestě „série bez roku“ (`CV_NoYearGiven`), `addComictoDB` udělá holé `return`
   (`importer.py`, `if not issued: return`) a `dbUpdate` spadne na `chkstatus['status']` (`TypeError`). Platí to
   i dnes při chybě CV, neopravováno (mimo rozsah, nic se nesmaže).
6. Režim `CV_ONLY=False` (není výchozí, produkce podle logu běží s `CV_ONLY` a `CV_ONETIMER`: „Refreshing the series
   and pulling in new data using only CV“) dřív kvůli `KeyError` tiše zahodil všechna issue. Teď vrátí `None` a
   refresh skončí chybou dřív, než se cokoli smaže.

**R30**
7. **Bez přejmenování** (INFO `[YEAR-RENAME]`, `ComicLocation` zůstane stará, `ComicYear` se opraví): složka bez
   `(2099)` ve jméně (formát bez závorek, `[2099]`, `2099` jen v názvu série), dvě `(2099)` ve jméně, nebo
   `2099` jen v nadřazené cestě. Formát složek produkce je podle logu `$Publisher/$Series ($Year)`, takže běžný
   případ (`… (2099)`) se přejmenuje jako dřív. **Cíl existuje** → WARN, nic se nepřesune ani neslučuje.
   Uživatel to musí vyřešit ručně (sloučit nebo přejmenovat). V obou případech pak rok ve jméně složky nesedí
   s `ComicYear`.
8. Blok se kvůli testům přesunul do funkce `rename_2099_folder` (stejné chování mimo opravu, stejné hlášky).

**R29**
9. **Kdo teď registruje provizorní jméno:** PP po přesunu souboru (`PostProcessor.py`, `register_provisional_rename`
   po zápisu `Location`, beze změny) a nově `webserve.manualRename` po `shutil.move` (také volání z Comics
   `comics_mylar_rename.py`). Nikdy neregistruje `filers.rename_file`: `previewRename` a
   `rename_placeholder_dated_files` (ten volá `rename_file` jen s datem z CV, odhad tam nevzniká).
   **Neregistrují, stejně jako dřív:** import s `IMP_RENAME` (`moveit.movefiles`, `librarysync`) a cesty PP pro
   story arc a grab bag (`rename_param(…, arc=…)`, tam se odhad nepoužívá). Import s odhadnutým datem tedy dál
   pojmenuje soubor bez registrace. Otázka, jestli registraci doplnit i tam.
10. **Ztracené záznamy se samy neobnoví.** Soubory, které od 28. 10. dostaly odhad a o záznam přišly (log: 89×
    „Recorded provisional“, žádná oprava), si odhad nechají. `manualRename` registruje jen při skutečném
    přejmenování, ne když jméno už sedí. Možnost: jednorázový skript, který registr doplní ze souborů
    pojmenovaných odhadem (`IssueDate` `0000-00-00`, ve jménu datum ze `ReleaseDate` nebo ship date).
11. Zámek je `threading.RLock`, ne `Lock`. Zabrání to zablokování, kdyby registraci někdo zavolal zevnitř operace
    pod zámkem. Dočasný soubor registru (`provisional_renames.json.<náhodné>.tmp` v `DATA_DIR`) se při chybě
    zápisu smaže. Je to vlastní soubor v `DATA_DIR`, ne v knihovně.

**R33**
12. Řádek providera bez `IssueID` se pozná podle `DynamicName` + `ISSUE` a fallback k němu nepřidá duplikát.
    `count` v návratové hodnotě je dál počet nalezených sledovaných issues, ne počet přidaných (počet přidaných je
    v logu).

**Mimo rozsah, jen zmínka:** R14 (image pozadu za kódem) platí dál, viz kap. 7. Ostatní odložené nálezy (R10, R11,
R26, R28, R34–R37, R40, R43–R45) nedotčené.

## 6. Kontrola Comics a comics-nzb-hunteru

- **API a webové akce:** odpovědi beze změny. `manualRename` vrací dál `{"status": "success"}` (test), jen navíc
  zaregistruje odhadnuté jméno. `refreshComic`, `getComic`, `getIssueInfo`, `markissues` nezměněné. Zablokovaný
  refresh (R32) se projeví jen v logu a v `GLOBAL_MESSAGES`. `refreshComic` stejně běží na pozadí a vrací hned.
- **Schéma, stavy, jména:** žádná nová tabulka ani sloupec, žádný nový stav issue. Tvar jmen souborů a složek je
  stejný (`FILE_FORMAT`, `$Series ($Year)`). Mění se jen to, že se správné jméno opravdu použije: soubor po
  `manualRename` z Comics se později sám přejmenuje na datum z CV (funkce forku od `657fb712`, dřív kvůli R29
  nefungovala). Comics (`comics_mylar_rename.py`, remediace) pak uvidí jinou `Location` u souborů, které měly
  odhadnuté datum, stejně jako po refreshi s datem z CV.
- **Tabulka `weekly` a `provisional_renames.json`:** Comics ani comics-nzb-hunter je nečtou (grep v obou repech).
- comics-nzb-hunter: po `refreshComic` u série zablokované pojistkou R32 neuvidí nová issue se stavem (zůstanou
  NULL), viz otázka 1.

## 7. Nasazení (jen se souhlasem uživatele)

Změněné soubory (všechno Python, žádná šablona):

```sh
docker cp mylar/cv.py mylar:/app/mylar/mylar/cv.py
docker cp mylar/updater.py mylar:/app/mylar/mylar/updater.py
docker cp mylar/importer.py mylar:/app/mylar/mylar/importer.py
docker cp mylar/helpers.py mylar:/app/mylar/mylar/helpers.py
docker cp mylar/filers.py mylar:/app/mylar/mylar/filers.py
docker cp mylar/webserve.py mylar:/app/mylar/mylar/webserve.py
docker cp mylar/weeklypull.py mylar:/app/mylar/mylar/weeklypull.py
```

1. Po merge do `python3-dev` zkopírovat soubory jmenovitě (výš). Python moduly potřebují **`docker restart mylar`**,
   jen se souhlasem uživatele a když neběží DDL stahování ani PP (`docker logs mylar --tail 50`). Restart smaže
   stav v paměti (`REJECTED_MATCHES`).
2. Ověření v kontejneru:
   `docker exec mylar grep -c "REFRESH-GUARD" /app/mylar/mylar/updater.py` (1),
   `docker exec mylar grep -c "def rename_2099_folder" /app/mylar/mylar/importer.py` (1),
   `docker exec mylar grep -c "PROVISIONAL_RENAMES_LOCK" /app/mylar/mylar/helpers.py` (≥ 3),
   `docker exec mylar grep -c "existing pull-list rows kept" /app/mylar/mylar/weeklypull.py` (1),
   `docker exec mylar grep -c "provisional_date" /app/mylar/mylar/filers.py` (≥ 1).
3. Co hledat v logu po restartu a dalším refreshi:
   - `[GetIssuesInfo] Completed - returning N issues, firstdate: <datum>`: u sérií s daty obálek už ne `2099-00-00`.
   - `[GetIssuesInfo] ComicID … Issue_ID … has no issue number on ComicVine - not adding it` (WARN, nově viditelné).
   - `[GetIssuesInfo] ComicID …: unable to read issue …` (ERROR): refresh té série se vynechá, nic se nesmaže.
   - `[REFRESH-GUARD] ComicVine data for … is missing …`: série zablokovaná pojistkou (otázka 1).
   - `[YEAR-RENAME]`: složka z roku 2099 nepřejmenovaná.
   - `[PLACEHOLDER-RENAME] … --> …`: první opravy provizorních jmen. Registr `provisional_renames.json` by měl
     přestat ztrácet záznamy, které ještě nejsou opravené.
   - `[PULL-LIST] Local fallback found N watched issues … and added M not yet listed (existing pull-list rows kept)`
     při výpadku providera.
4. **Rebuild image** (R14, kap. 9 [FOLLOWUPS-2026-11-22-part2.md](FOLLOWUPS-2026-11-22-part2.md)): po nasazení
   přes `docker cp` je image `mylar3:local` pozadu o tuto část i o šablony třetí části. Před jakýmkoli recreate
   kontejneru nejdřív `docker build -t mylar3:local .` z aktuální `python3-dev`, recreate přes Dockhand jen služby
   `mylar` a se souhlasem.

## 8. Stav po merge

Doplněno 23. 11. 2026 kolem 10:10 SEČ zpětně z reflogu, Dockeru a `docker logs mylar` (časy pražské, v závorce
UTC). Co se z nich vyčíst nedá, je označené.

- **Merge** 22. 11. ve 23:53 (22:53 UTC): `python3-dev` posunuta fast-forwardem z `187c958e` na `61cc4c49`, bez
  merge commitu.
- **Push:** `fork/python3-dev` = `61cc4c49`. Čas pushe z reflogu nevyčtu. Na `origin` nic.
- **Nasazení:** `docker cp` sedmi modulů podle kap. 7 a **`docker restart mylar`** 22. 11. ve 23:54 (22:54 UTC).
  Kontrola `docker logs mylar --tail 50` před restartem v záznamu není.
- **Ověření v kontejneru** (23. 11.): md5 všech 99 souborů `mylar/*.py`, `mylar/downloaders/*.py` a
  `data/interfaces/default/*.html` v `/app/mylar/` = `HEAD` `61cc4c49`. Značky z kap. 7, bod 2: `REFRESH-GUARD` 1,
  `def rename_2099_folder` 1, `PROVISIONAL_RENAMES_LOCK` 3, `existing pull-list rows kept` 1, `provisional_date` 2.
- **Testy na `61cc4c49`** v image `mylar3:local`, Python 3.8.2: `tests/` 131 passed, `tests_db/` 176 passed.
- **Log od restartu do 23. 11. 10:08 SEČ:** žádný ERROR, traceback, chyba Mako ani HTTP 500. DDL smyčka i
  `[DDL-WATCHDOG]` běží, fronta prázdná. Pull list týdnů 46 a 47 načtený z providera ve 3:54 a 7:54 (fallback R33
  nebyl potřeba). Refresh přes API série DC Connect (127365) v 5:11 (4:11 UTC) prošel bez `[REFRESH-GUARD]`,
  `forceRescan` našel 72 ze 73 souborů, nic se nesmazalo. Po něm doběhl PP čtyř issues (DC Connect #72,
  Bloodhound #1, Batman: No Man's Land #1, Batman: No Man's Land Gallery #1). `[YEAR-RENAME]`,
  `[PLACEHOLDER-RENAME]` a WARN o issue bez čísla se zatím neobjevily (žádná taková situace).
- **Image (R14):** `mylar3:local` (a `mylar3:candidate`) přestavěný 23. 11. v 0:12 (22. 11. 23:12 UTC),
  `sha256:64223322…`. Klíčové moduly a šablony v něm mají md5 shodné s `HEAD`, takže recreate už kód nevrátí.
  Kontejner zatím běží na předchozím image `616267df` (tag `mylar3:2026-11-22-part2`) s kódem přes `docker cp`.
  Recreate se neprováděl. Starší rollback zůstává jako `mylar3:2026-09-11`.
- **Neověřeno:** UI v prohlížeči. Akce měnící stav (`manualRename`, refresh se zablokovanou sérií, výpadek
  pull-list providera) se nespouštěly.
- Worktree `/data/Tarzan/Cursor/Mylar-review-2026-11-22-part4` a větev `claude/review-2026-11-22-part4` už
  neexistují. V `_archive` worktree této části není.

