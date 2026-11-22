# Zadání: opravy nálezů z review Mylaru 2026-11-22, čtvrtá část (data sérií, jména souborů, pull list)

## Kontext

**Mylar** (fork mylar3, `tarzan77cz/mylar3`) je automatický stahovač komiksů. Běží pro jednoho uživatele ostře
nad knihovnou asi 11 300 sérií. Refresh sérií z ComicVine (CV) běží denně, PP pojmenovává soubory podle
`FILE_FORMAT` (včetně data obálky), pull list řídí, co je `Wanted`. První tři části oprav jsou v `python3-dev`
a nasazené (FOLLOWUPS části 1–3).

Tahle část opravuje pět nízkých nálezů v kódu forku, které **tiše mění nebo ztrácejí data**:

| ID | Oblast | Soubory (hledej podle jmen funkcí, čísla řádků v review platí pro starší commit) |
|---|---|---|
| R31 | `firstdate` z `cv.GetIssuesInfo` je u série vždy `2099-00-00` → nový rok série = aktuální rok | `cv.py` (`GetIssuesInfo`, `getComic`), `importer.py` (`addComictoDB`, rok série), `series_metadata.py` |
| R32 | `GetIssuesInfo` tiše vynechá issue, které spadne; refresh pak issue smaže z DB i se stavem a `Location` | `cv.py` (`GetIssuesInfo`, `getComic`), `updater.py` (`dbUpdate`, `DELETE` + `issue_collection`), `importer.py` |
| R30 | přejmenování složky série z roku 2099: vnoření do existující složky, `re.sub` mění i název série | `importer.py` (`addComictoDB`, blok „check for year change“) |
| R29 | registr provizorně datovaných jmen (`provisional_renames.json`) ztrácí záznamy | `helpers.py` (`load/save_provisional_renames`, `rename_placeholder_dated_files`, `register_provisional_rename`, `rename_param`), `filers.py` (`rename_file`), `webserve.py` (`previewRename`, `manualRename`), `PostProcessor.py` (registrace po PP) |
| R33 | `weekly_local_fallback` při výpadku providera smaže celý týden pull listu | `weeklypull.py` (`weekly_local_fallback`, větev `ALT_PULL == 2` v `pullit`) |

**Hlavní riziko opravy:** rozbít refresh sérií (série se přestane aktualizovat, nebo naopak smaže víc), PP
a pojmenování souborů jednotlivých čísel, nebo pull list. **Stahování a PP jednotlivých čísel přes GC-Main se
nesmí změnit.** Opravy mají být úzké: chování mimo popsaný scénář zůstává.

- **Pravidla repa:** `CLAUDE.md` ve worktree (Python 3.8, `sqlite3.Row` nemá `.get()`, živé služby, secrets,
  styl commitů, sekce Review, klienti API Comics a comics-nzb-hunter). Přečti ho jako první.
- **Nálezy:** řádky R29–R33 v tabulce kap. 4 `review/REVIEW-2026-11-22.md` a rozhodnutí v kap. 11 (doplnění
  z večera 22. 11.: čtvrtá část).
- **Minulé opravy, jejichž chování neměň, pokud to nález nežádá:** hlavně R17 z druhé části (`dbUpdate` nepřepíše
  při obnově stavů issue, které je mezitím `Downloaded` s `Location`; `foundsearch` počká na řádek, který refresh
  smazal), viz `review/FOLLOWUPS-2026-11-22-part2.md`. Oprava R32 je ve stejné funkci, testy R17 musí dál
  procházet.
- **Reprodukce z review** (v `.gitignore`, do repa je nekopíruj, použij jako výchozí bod testů):
  `.scratch/review-2026-11-22/cv/` v hlavním stromu `/data/Tarzan/Cursor/Mylar/`:
  - `repro_cv.py`: `GetIssuesInfo` nad podvrženým XML z CV (R31 `firstdate`, R32 scénář 2: první issue bez
    `issue_number`),
  - `repro_rename.py`: scénáře C, C2 (R29: záznam zmizí, když přejmenování jednou selže nebo soubor chvíli
    chybí), D (R29: `manualRename` pojmenuje odhadem bez registrace), E (R29: `previewRename` přepíše záznam),
    G (kontrolní: druhá změna data bez smyčky), I (R30: `shutil.move` na existující složku).
- **Navazující repa:** `/data/Tarzan/Cursor/Comics` (mimo jiné `comics_mylar_rename.py` volá webový
  `manualRename` a převádí `.cbr` → `.cbz`, čímž mění `Location`) a
  `/data/Tarzan/Cursor/scripts/apps/comics-nzb-hunter` (`refreshComic`, `getComic`, `getIssueInfo`, `markissues`).
  Neměň schéma tabulek, odpovědi API ani webových akcí, názvy stavů ani tvar jmen souborů a složek (mění se jen
  to, že se správné jméno opravdu použije).

## Režim práce: bez dozoru, všechno v jedné session

Uživatel u toho není. **Na nic se neptej a nezastavuj se mezi nálezy**, nikdo neodpoví. Projdi všechny nálezy
a na konci napiš a commitni souhrn. Když něco nejde nebo si nejsi jistý, zvol konzervativnější variantu (ta, po
které se žádná data neztratí a nic se nepřesune), zapiš ji do souhrnu jako otevřenou otázku a pokračuj dalším
nálezem.

## Pravidla

1. **Izolace.** `git -C /data/Tarzan/Cursor/Mylar worktree add -b claude/review-2026-11-22-part4
   /data/Tarzan/Cursor/Mylar-review-2026-11-22-part4 python3-dev`. Pracuj jen tam. Hlavní strom ani worktree
   třetí části nepřepínej a neměň (ani netrackované soubory). Nepushuj, nemerguj, nepřepisuj historii.
2. **Review soubory** (`REVIEW_PROMPT-*`, `REVIEW-*`, `FIX_PROMPT-*`, `FOLLOWUPS-2026-11-2*.md`) neměň, výsledky
   patří do nového `review/FOLLOWUPS-2026-11-22-part4.md`.
3. **Na živou aplikaci nesahej:** žádný `docker cp`, `docker restart`, `docker exec` do kontejneru `mylar`,
   žádné volání Mylar API ani webových akcí, žádné dotazy do `mylar.db`, nic v `/comics`, `/downloads` a
   `/config` (ani `provisional_renames.json`). Nečti `/config/mylar/config.ini`, `env` kontejneru ani
   `docker inspect`. Žádná síť (ComicVine, GetComics, pull list). Image `mylar3:local` nepřestavuj
   a nepřetaguj. **Číst smíš** `docker logs mylar` (od 22. 11. 21:17 SEČ) a `docker logs mylar-2026-09-11`
   (zastavený starý kontejner, historie od 11. 9. do 22. 11.); časy v nich jsou UTC, do souhrnu je převeď na
   pražský čas.
4. **Opravuj jen R29, R30, R31, R32, R33.** Ostatní (R10, R11, R14, R26, R28, R34–R37, R40, R43–R45) nech být,
   i když na ně narazíš; jen je případně zmiň v souhrnu. Žádné refaktoringy ani vylepšení navíc. `lib/` neměň.
   Upstream kód měň jen tam, kudy vede scénář nálezu (např. `updater.dbUpdate` u R32), a napiš to.
5. **Test dřív než oprava.** Každý test musí před opravou selhat a po ní projít. Když neselže, nález se
   nereprodukuje: neopravuj ho a napiš proč. Ověř to aspoň u R32 a R29 i odložením změn (`git stash` jen ve tvém
   worktree). Kontrolní testy, které procházejí i před opravou (hlídají nezměněné chování), tak v souhrnu označ.
6. **Commit na nález**, anglicky, jedna věta v rozkazovacím způsobu, co a proč, ID na konci, např. „Take the
   series start year from the earliest cover date again, so a series without a start year in Comic Vine is no
   longer filed under the current year (R31)“. Commit jen v repu Mylar.
7. **Python 3.8.** Nic z 3.9+ (`match`, `X | Y`, `list[str]` mimo řetězce, `removeprefix`, `dict | dict`,
   `zoneinfo`). Na `sqlite3.Row` nikdy `.get()` ani `'col' in row`; sloupce přes `row['col']`, `row.keys()` nebo
   `try/except (KeyError, IndexError)`.
8. **Nic nemaž natrvalo.** Žádný soubor z repa se neodstraňuje. Kód nesmí nově mazat soubory ani složky
   v knihovně.

## Testy a prostředí

Worktree leží na Z2 pod `/share/Tarzan/Cursor/Mylar-review-2026-11-22-part4`, Docker socket patří Z2:

```sh
docker run --rm -e PYTHONDONTWRITEBYTECODE=1 -v /share/Tarzan/Cursor/Mylar-review-2026-11-22-part4:/src:ro mylar3:local \
  sh -c "pip install -q pytest >/dev/null 2>&1; cd /src && python3 -m pytest -q -p no:cacheprovider tests"
docker run --rm -e PYTHONDONTWRITEBYTECODE=1 -v /share/Tarzan/Cursor/Mylar-review-2026-11-22-part4:/src:ro mylar3:local \
  sh -c "pip install -q pytest >/dev/null 2>&1; cd /src && python3 -m pytest -q -p no:cacheprovider tests_db"
```

- **Výchozí stav nejdřív:** na čistém worktree `tests` **131 passed**, `tests_db` **142 passed**. Zapiš do
  souhrnu.
- Nové testy patří do `tests_db/` (skutečný balík `mylar`, dočasná SQLite a `mylar.DATA_DIR` v tempu). Schéma
  v `tests_db/conftest.py` můžeš rozšířit o sloupce a tabulky, které test potřebuje (`comics`, `issues`,
  `annuals`, `weekly`…). ComicVine podvrhni (`cv.pulldetails` vracející XML z `parseString`, vzor
  `repro_cv.py`, nebo přímo `cv.getComic`), soubory a složky zakládej v `tmp_path`.
- Před každým commitem: obě sady testů a `ast.parse` změněných souborů v image (příkaz v `CLAUDE.md`).
- Na konci navíc import všech modulů `mylar.*` v 3.8.2 (`sys.path[:0] = ['/src', '/src/lib']`), vzor
  `.scratch/review-2026-11-22/try_imports.py` v hlavním stromu: musí zůstat 71 ze 71.

## Nálezy a co přesně udělat

Pořadí: R31 → R32 → R30 → R29 → R33.

### R31: `firstdate` série je vždy `2099-00-00`

- V `cv.GetIssuesInfo` je porovnání `tempissue['CoverDate'] < firstdate` odsazením jen ve větvi pro story arc
  (`else` za `if arcid is None`). Upstream (`b609c28c`) ho měl pro obě větve. Vrať ho pro obě, beze změny jinde.
- Dopad dnes: `importer.addComictoDB` při chybějícím CV `start_year` bere `issued['firstdate'][:4]` = `2099`
  a fallback forku pak rok z pull listu nebo **aktuální rok**; `series_metadata` bere `int(firstdate[:4])`.
- Testy (vzor `repro_cv.py`): série s cover dates `2018-06-01` a `2018-07-01` → `firstdate == '2018-06-01'`;
  issue s `0000-00-00` se do minima nepočítá (kontrolní); bez jakéhokoli data zůstane `2099-00-00` a
  `addComictoDB` použije dnešní fallback (kontrolní). Test `addComictoDB` nebo jeho výpočtu roku s CV
  `ComicYear='0000'` a issues z roku 2018 → `ComicYear` 2018, ne aktuální rok (podvrhni `cv.getComic`).
- **Zjisti z logů** (`docker logs mylar` a `mylar-2026-09-11`, hledej „No usable Series Year from CV“ a
  „[PULL-SHIPDATE] No usable Series Year“), které série od 11. 1. 2026 (`89ac088d`) dostaly rok takhle, a vypiš je
  v souhrnu (název, ComicID, přidělený rok, čas). Nic na nich neopravuj. Zjisti z kódu, jestli je příští refresh
  opraví sám (zda `dbUpdate` rok přepočítá a co se stane se jménem složky), a napiš to.

### R32: refresh tiše smaže issue, které se nepovedlo načíst

- `GetIssuesInfo` má od `89ac088d` kolem těla smyčky `try/except Exception: continue`. Issue, u kterého zpracování
  spadne (typicky první issue bez `issue_number`: `KeyError` při sestavení slovníku), z výsledku zmizí.
  `dbUpdate` pak udělá `DELETE FROM issues/annuals WHERE ComicID=?` a `issue_collection` bez něj: issue zmizí
  z DB i se `Status` a `Location`. Upstream v té situaci shodil celý refresh ještě před `DELETE`.
- Navíc `tempissue` je jeden slovník pro všechny issue, takže issue bez `issue_number` převezme číslo
  předchozího (upstream chyba, dvě issue se stejným číslem).
- Cíl: **refresh nesmí z DB odstranit issue, které má soubor nebo stav, protože se nepodařilo načíst nebo
  ho CV vrátil neúplně.** Navržené řešení (odchylku zdůvodni):
  1. `GetIssuesInfo` pro sérii (`arcid is None`): `tempissue` nový pro každé issue. Issue bez `issue_number` se
     nepřidá (upstream ho hlásí jako nepodporovaný TPB/GN), ale zaloguje se **WARN** s `Issue_ID`, ne tiše.
     Jiná výjimka při zpracování issue = selhání načtení: zaloguj ERROR s `Issue_ID` a tracebackem a dej
     volajícímu vědět, že data nejsou úplná (např. `cv.getComic(…, 'issue')` vrátí `None` jako při chybě CV,
     takže `addComictoDB` skončí `incomplete` a `dbUpdate` nic nesmaže). Story arc (`arcid` zadané) nech jako
     dnes a napiš to.
  2. Pojistka v `updater.dbUpdate` před `DELETE`: když v DB existuje issue této série se `Status`
     `Downloaded`, `Archived` nebo `Snatched` nebo s vyplněnou `Location` a jeho `IssueID` v nových datech
     (`chkstatus['issuedata']`) chybí, refresh se před `DELETE` zastaví (WARN se seznamem IssueID, zpráva
     „Failure refreshing …“ jako u jiné chyby refreshe, nic se nesmaže). Pokrývá to i neúplné stránkování CV
     (`getComic` při chybě stránky vrátí, „co má“). U annualů postupuj stejně, jen když jdou spolehlivě porovnat;
     jinak to zapiš.
  Série, ze které CV issue opravdu odstranil a uživatel ho má staženo, se pak refreshovat přestane (WARN při
  každém refreshi). To je záměr; zapiš to jako otevřenou otázku.
- Testy: (a) `repro_cv.py` scénář 2 (první issue bez `issue_number`) → výsledek bez něj, v logu WARN s Issue_ID,
  druhé issue bez čísla nepřevezme číslo předchozího; (b) issue, jehož zpracování vyhodí jinou výjimku →
  `getComic` vrátí `None` (nebo jak zvolíš); (c) `dbUpdate` s DB, kde je issue `Downloaded` s `Location`, a novými
  daty bez něj → řádek v DB zůstane beze změny, `DELETE` neproběhl; (d) kontrolní: běžný refresh se všemi issue
  proběhne jako dnes (smaže a vloží, stavy obnoví); (e) kontrolní: issue `Wanted` bez souboru, které v nových datech
  chybí, refresh nezastaví. Testy R17 z druhé části musí dál procházet.

### R30: přejmenování složky série z roku 2099

- `importer.addComictoDB`, blok „check for year change and rename the folder to the corrected year“: když
  uložený rok je `2099` a nový rok jiný, `re.sub('2099', SeriesYear, comlocation)` nahradí **všechny** výskyty
  v celé cestě (u jediného výskytu), a `shutil.move` na existující cílovou složku složku vnoří
  (`Y (2026)/Y (2099)/…`), přičemž DB dostane `new_location`.
- Oprava: nahrazuj jen v posledním prvku cesty (název složky série), a jen výskyt, který je rokem, ne součástí
  názvu série (např. „Spider-Man 2099“). Když to nejde rozhodnout spolehlivě (složka bez roku v názvu, `2099`
  jen v názvu série), nepřejmenovávej, nech `comlocation` a zaloguj to. Když cílová složka už existuje,
  **nepřesouvej** a nech `comlocation` beze změny (WARN s oběma cestami). Větev, kdy stará složka neexistuje
  a nová ano (`comlocation = new_location`), nech.
- Testy (vzor `repro_rename.py` I, složky v `tmp_path`, `shutil.move` skutečný): `Spider-Man 2099 (2099)` →
  `Spider-Man 2099 (2014)`; složka bez roku `Spider-Man 2099` → žádné přejmenování; základní cesta obsahující
  `2099` (`…/2099/Y (2099)`) → změní se jen poslední prvek; cíl existuje → nic se nepřesune, `comlocation`
  zůstane stará, WARN; kontrolní: `Y (2099)` → `Y (2026)` bez kolize proběhne jako dnes.

### R29: registr provizorně datovaných jmen ztrácí záznamy

Registr (`DATA_DIR/provisional_renames.json`, `{IssueID: jméno souboru}`) drží soubory pojmenované odhadnutým
datem obálky, aby je `rename_placeholder_dated_files` přejmenoval, až CV datum dodá. Od 28. 10. je v logu 89×
„Recorded provisional“ a ani jedna oprava. Čtyři příčiny a zámek:

- **`pop` před pokusem** (`rename_placeholder_dated_files`): záznam se odebere dřív, než se ví, jestli
  přejmenování projde. Když soubor chybí, cíl existuje, jméno nejde sestavit nebo `move` spadne, záznam zmizí
  a soubor si odhad nechá navždy. Oprava: odebrat jen po úspěšném přejmenování, nebo když je jisté, že soubor
  už odhadem pojmenovaný není (`Location` se změnila na jméno bez odhadu). Při selhání záznam zůstane a příští
  refresh to zkusí znovu (kontrolní scénář G: po skutečném přejmenování žádná smyčka).
- **Převod `.cbr` → `.cbz` z Comics** změní `Location`, takže `row['Location'] != provisional_name` a záznam se
  zahodí bez přejmenování. Oprava: porovnávat bez přípony (stejné jméno, jiná přípona = pořád odhad).
- **`previewRename` přepíše záznam** náhledovým jménem: `filers.FileHandlers.rename_file` registruje při každém
  sestavení jména, i když se nic nepřejmenuje. Oprava: `rename_file` jen vrátí, že datum je odhad (nový klíč ve
  vráceném slovníku, stávající klíče beze změny), a registruje až kód, který soubor opravdu přesunul.
  Projdi všechny volající `rename_file` a `rename_param` (PP už po přesunu registruje sám, kolem
  `PostProcessor.py:3628`) a napiš, kdo teď registruje.
- **`manualRename`** (`webserve.manualRename` → `helpers.rename_param`; volá ho i Comics `comics_mylar_rename.py`)
  pojmenuje soubor odhadem a nezaregistruje ho. Soubor s `0000-00` tak po ručním přejmenování přestane být
  opravitelný. Oprava: `rename_param` vrátí příznak odhadu stejně jako `rename_file` (dnes ho zahazuje,
  `filename_issue_date(...)[0]`) a `manualRename` po úspěšném přesunu zaregistruje. Odpověď `manualRename`
  se nemění.
- **Zámek:** load–modify–save bez zámku a s pevným `.tmp` (PP a refresh běží v různých vláknech). Oprava:
  modulový `threading.Lock` kolem celé operace čti–změň–ulož a dočasný soubor s unikátním jménem ve stejné
  složce (`tempfile.mkstemp(dir=…)`), `os.replace` jako dnes.
- Testy (vzor `repro_rename.py` C, C2, D, E, G; `mylar.DATA_DIR` v `tmp_path`): C (cíl jednou existuje) → záznam
  zůstane, po odstranění překážky druhý běh přejmenuje a záznam odebere; C2 (soubor chvíli chybí) → záznam
  zůstane; `.cbr` v registru, `Location` `.cbz` se stejným jménem → přejmenuje se; E (`previewRename`) → registr
  beze změny; D (`manualRename` s odhadem) → záznam vznikne; G kontrolní; souběh: dvě vlákna registrují různé
  IssueID současně (např. 2 × 50 zápisů) → v registru jsou všechny.

### R33: lokální fallback pull listu smaže celý týden

- `weeklypull.weekly_local_fallback` (volá ho `pullit` při `ALT_PULL == 2`, když provider vrátí jiný stav než
  `up2date`/`success`/`update_required`, při 4h backoffu tedy každý běh) udělá `DELETE FROM weekly WHERE
  weeknumber=? AND year=?` a týden naplní jen issues sledovaných sérií s CV `ReleaseDate` v týdnu, se `STATUS`
  `Skipped`. Upsert klíčuje jen `DYNAMICNAME` + `ISSUE`, bez týdne, takže může přepsat řádek jiného týdne.
- Dopad: zmizí ship dates z providera, na kterých stojí fallbacky forku (`helpers.weekly_shipdate`,
  `weekly_series_year`, `filename_issue_date`): issues bez CV data přijdou o `Wanted` z pull listu a PP jim dá
  `0000-00` místo odhadu.
- Oprava: fallback **nemaže** existující řádky týdne. Doplní jen issues, které v tom týdnu ještě nejsou (klíč
  včetně `weeknumber` a `year`, nejlépe `IssueID`), a u existujících řádků nemění nic (ani `STATUS`). Když týden
  v `weekly` žádné řádky nemá, chová se jako dnes. Návratová hodnota a `new_pullcheck` beze změny.
- Testy: týden s řádky z providera (včetně issue bez CV `ReleaseDate` se `STATUS` `Wanted` a `SHIPDATE`) +
  fallback → původní řádky beze změny, nová issue z CV doplněná; řádek stejné série a čísla v **jiném** týdnu
  zůstane beze změny; kontrolní: prázdný týden → naplní se jako dnes.

## Na konci

1. Obě sady testů, `ast.parse` změněných souborů, import všech modulů v 3.8.2.
2. Souhrn **`review/FOLLOWUPS-2026-11-22-part4.md`** ve worktree (česky, kód v originále, časy pražsky):
   - prostředí: worktree, větev, základ (`python3-dev` a jeho commit), image `mylar3:local` a jeho ID, že se nic
     nenasadilo ani nerestartovalo,
   - výchozí a konečný stav testů,
   - tabulka ID | Stav (opraveno / neopraveno / nereprodukováno) | Commit | Nové testy (kolik padalo před
     opravou) | Poznámka (jak reprodukováno, co oprava dělá, dopad na refresh, PP a pull list),
   - u R31 seznam sérií z logu s rokem z fallbacku a co s nimi udělá příští refresh,
   - otevřené otázky a konzervativní volby (minimálně: R32 série, kterou pojistka zablokuje; R30 případy bez
     přejmenování),
   - kontrola Comics a comics-nzb-hunteru: nic nemění API, odpovědi webových akcí (`manualRename`), schéma,
     stavy ani tvar jmen souborů a složek,
   - postup nasazení pro uživatele: změněné soubory jmenovitě pro `docker cp` podle `CLAUDE.md`; u Python modulů
     je potřeba **`docker restart mylar`** (jen se souhlasem a když neběží DDL ani PP, viz `CLAUDE.md`); co
     ověřit v logu po restartu (hlášky nových větví) a že po nasazení je potřeba rebuild image (R14, kap. 9
     `FOLLOWUPS-2026-11-22-part2.md`), který zatím čeká i na šablony třetí části,
   - prázdná sekce „Stav po merge“.
3. Commitni souhrn ve worktree. Nepushuj, nemerguj, worktree nech být.
4. Poslední zprávou napiš, ve kterých repech a na které větvi jsi commitnul, a stav testů.
