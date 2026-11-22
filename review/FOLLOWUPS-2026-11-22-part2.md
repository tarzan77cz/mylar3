# Opravy nálezů z review 2026-11-22, druhá část

Opravy nálezů R46, R23, R25, R41, R38, R24, R39, R42, R27, R19, R18 a R17 z
[REVIEW-2026-11-22.md](REVIEW-2026-11-22.md) podle [FIX_PROMPT-2026-11-22-part2.md](FIX_PROMPT-2026-11-22-part2.md)
a rozhodnutí uživatele v kap. 11 zprávy (Q14 a, Q15 a, R41 přidán). Session běžela bez dozoru 22. 11. 2026
asi 15:15–16:10 SEČ (commity 15:20–15:59 SEČ, 14:20–14:59 UTC).

## 1. Prostředí

- **Worktree:** `/data/Tarzan/Cursor/Mylar-review-2026-11-22-part2` (na Z2 `/share/Tarzan/Cursor/Mylar-review-2026-11-22-part2`),
  větev `claude/review-2026-11-22-part2`, založená z **`python3-dev` (`b912ddc4`)**: první část
  (`claude/review-2026-11-22`) už v `python3-dev` je (`git merge-base --is-ancestor` vrátil 0). Hlavní strom
  ani worktree první části se nepřepínaly ani neměnily (ani netrackované soubory).
- **Image:** `mylar3:local`, `sha256:b7cfffeb59ee1b6d6c3bb459ba492bd146075392a2d6e7df8535c8a3b7c93167`
  (vytvořen 11. 9. 2026 17:21 SELČ), Python 3.8.2. Testy, import a kompilace šablony běžely v jednorázových
  kontejnerech nad worktree jen pro čtení. Image se nepřestavoval ani nepřetagoval.
- **Živá aplikace:** kontejner `mylar` se nerestartoval, nic se nenasadilo (žádný `docker cp`, `docker exec`,
  `docker inspect mylar`), žádné volání Mylar API, žádný dotaz do `mylar.db`, nic v `/comics` a `/downloads`,
  `config.ini` ani `env` se nečetly, žádná síť. `docker logs mylar` se nečetl (nebylo potřeba). Nic se
  nepushovalo ani nemergovalo.
- **Reprodukce:** `.scratch/review-2026-11-22/` z hlavního stromu zkopírovaný do `.scratch/` worktree (v
  `.gitignore`, mimo git). Vlastní pomocné skripty v `.scratch/fix-part2/`: `run_tests.sh` (obě sady +
  `ast.parse`), `compile_templates.py` (Mako `TemplateLookup` nad `data/interfaces/default`).

## 2. Testy

| | `tests/` (stuby, parser) | `tests_db/` (skutečný balík `mylar`, dočasná SQLite) |
|---|---|---|
| Výchozí stav (čistý worktree) | **88 passed** | **85 passed** |
| Konečný stav | **96 passed** (8 nových) | **142 passed** (57 nových) |

```sh
docker run --rm -e PYTHONDONTWRITEBYTECODE=1 -v /share/Tarzan/Cursor/Mylar-review-2026-11-22-part2:/src:ro mylar3:local \
  sh -c "pip install -q pytest >/dev/null 2>&1; cd /src && python3 -m pytest -q -p no:cacheprovider tests"
docker run --rm -e PYTHONDONTWRITEBYTECODE=1 -v /share/Tarzan/Cursor/Mylar-review-2026-11-22-part2:/src:ro mylar3:local \
  sh -c "pip install -q pytest >/dev/null 2>&1; cd /src && python3 -m pytest -q -p no:cacheprovider tests_db"
```

- Před každým commitem obě sady a `ast.parse` změněných souborů v image. Na konci `ast.parse` všech 21 změněných
  `.py` souborů: v pořádku. Grep přidaných řádků na 3.9+ (`removeprefix`, `X | Y`, `list[...]`, `match`, `:=`)
  a na `.get()` nad `sqlite3.Row`: nic.
- **Import všech modulů `mylar.*` v 3.8.2** (`.scratch/review-2026-11-22/try_imports.py`): **71 ze 71**.
- **Šablona:** `comicdetails_update.html` se zkompiluje (`TemplateLookup`). V prohlížeči neověřeno.
- **Test dřív než oprava:** každý nový test jsem pustil před opravou, v tabulce je počet tehdy padajících. U R41
  a R42 jsem to ověřil i odložením změn v `mylar/getcomics.py` (`git stash`), u R25 a R18 po krocích (nejdřív
  jedna polovina opravy, test druhé poloviny dál padal). Testy, které procházely i předtím, jsou **kontrolní**
  (hlídají nezměněné chování).
- **Upravené stávající testy:** `tests_db/test_queue_threads.py` (poznámka R41 → kontrola `DDL_QUEUED == []`,
  před opravou padá). Čtyři testy posílaly do smyčky položku bez řádku v `ddl_info`, což žádný producent fronty
  nedělá (viz R41): `test_single_exhausted.py` (`test_exhausted_single_annual_is_wanted`,
  `test_downloaded_single_issue_is_left_alone`, `test_manual_item_keeps_the_pack_path`) a
  `test_pack_sections.py::test_finished_subpack_clears_only_its_issues` dostaly řádek; dva z nich navíc kontrolu
  stavu řádku, jinak by po R41 procházely naprázdno. `tests/test_getcomics_post.py::test_pack_queues_every_matching_subpack`
  (`issues: []`) se neměnil: s prázdným `issues` se hledaná čísla vrací k celému rozsahu, test dál prochází.
- **Schéma testů:** `tests_db/conftest.py` rozšířen o sloupce `comics` (`Type`, `Corrected_Type`, `ComicName_Filesafe`,
  `ComicPublisher`, `AlternateSearch`, `UseFuzzy`, `ComicVersion`, `TorrentID_32P`, `IgnoreType`, `AllowPacks`,
  `ComicLocation`, `LatestDate`, `LastUpdated`, `Corrected_SeriesYear`, `Status`), `issues` (`ReleaseDate`,
  `DigitalDate`, `DateAdded`, `Location`, `ComicSize`, `IssueDate_Edit`) a `annuals` (`IssueDate`, `ReleaseDate`,
  `Location`). Tabulky `storyarcs`, `manualresults`, `snatched`, `weekly` si zakládají jednotlivé testy.
  `tests/conftest.py`: stub DB umí `selectone` nad slovníkem `_DB.rows` (stav řádku `ddl_info`).
- **Reprodukce z review** (`.scratch/review-2026-11-22/h/test_h_repro.py`): všech 5 se otočilo. U
  `test_tpb_extra_item_exhausted_marks_issue_wanted` to ale způsobuje R41 (položka nemá řádek v `ddl_info`, smyčka
  ji přeskočí), ne R42. R42 pokrývají nové testy s řádkem. `cv/repro_rename.py` F: `foundsearch returned
  normally` (dřív `TypeError`).

## 3. Nálezy

| ID | Stav | Commit | Nové testy (před opravou padalo) | Poznámka |
|---|---|---|---|---|
| R46 | opraveno | `740550ee` | `tests_db/test_rejected_matches.py::test_select_passes_the_issue_date` (2, padaly 2) | **Reprodukce:** výběr odmítnuté shody s i bez `verified_data` poslal do `searcher` `IssueDate=''` místo `2020-05-01`. **Oprava:** v obou větvích `select_rejected_match` `'IssueDate' in issue.keys()`. Grep celého `mylar/` na `'x' in <řádek>`: jiný výskyt nad `sqlite3.Row` není (`opds.py:385,391` pracuje s dicty z `_dic_from_query`, zbytek jsou podřetězce v řetězcích). |
| R23 | opraveno | `740550ee` | `tests_db/test_rejected_matches.py` (6, padalo 5; `test_select_the_last_match_clears_the_issue` kontrolní) | **Reprodukce** (vzor `ui/repro_select.py`): `[neoferovaná, m1, m2]`, výběr m2 → `searcher` zavolán a pak chyba (`pop` mimo rozsah), uložený seznam beze změny; když se nabízí vše, success, ale shoda zůstala a druhé kliknutí ji zařadilo znovu; výběr podle indexu vzal špatnou položku. **Oprava:** v obou větvích (nesjednocené) se po úspěchu odebere vybraná shoda z uloženého `REJECTED_MATCHES[IssueID]` přes stávající `search_filer._remove_rejected_match` (hledá `_find_rejected_match_index` podle `link`/`nzbid` shody, kterou normalizace mění na tomtéž objektu). Druhé kliknutí vrátí chybu bez volání `searcher`. Prázdný seznam smaže klíč. **Dopad na GC-Main:** žádný. |
| R25 | opraveno | `055a552e` | `tests_db/test_search_lock.py` (2, padaly 2) | **Reprodukce:** RSS dávka, první položka (`issues.ComicName` je NULL) vyhodí `TypeError`, obsluha spadla na `UnboundLocalError` (`comicname`, `smode`), funkce skončila se `SEARCHLOCK=True` a druhá položka se nezpracovala. **Oprava:** obsluha používá `result.get('mode')` a `comicname`/`SeriesYear`/`booktype` se nastavují na začátku každé položky (žádná hodnota z předchozí). `searchforissue` je teď obal kolem původní funkce (`_searchforissue`): při výjimce v RSS běhu uvolní `SEARCHLOCK` a výjimku pošle dál jako dřív. Jednotlivé hledání má svůj `finally` jako dřív. **Dopad na GC-Main:** žádný. |
| R41 | opraveno | `6f07fd57` | `tests_db/test_ddl_queue_state.py` R41 část (7, padalo 6; `test_item_with_its_row_is_still_downloaded` kontrolní) + kontrola v `test_queue_threads.py` (padala) | **Reprodukce:** po úspěchu i selhání skutečného `GC.downloadit` (GC-Main na podvržené `requests.Session.get`) zůstalo ID v `DDL_QUEUED`; po „Vyčistit frontu“ a „Remove“ se položka stáhla a upsert založil řádek jen s `id`/`status`; ruční PP s výjimkou nechal `MANUAL_PP_STATUS['running']=True`. **Producenti fronty** (`getcomics._queue_section`, `queue_direct_ddl` obě větve, `ddl_requeue`, auto-load, startovní načítání, vrácení po `incomplete`) zapisují řádek **před** `put` (ověřeno čtením), proto: **Oprava:** (1) `downloadit` přidá ID jen když v `DDL_QUEUED` není. (2) Smyčka `ddl_downloader` po vyzvednutí položky ověří řádek v `ddl_info`; když chybí, zaloguje, ID odebere z `DDL_QUEUED` a nic nestahuje ani nezakládá. (3) Ruční PP se spouští ve vlákně s `finally`, které po chybě nastaví `running=False`, `phase='done'` a souhrn „Post-processing ended with an error. See the log.“ (`MANUAL_PP_LOCK` uvolňuje `PostProcessor.Process` jako dřív). **Dopad na GC-Main:** úspěch a selhání beze změny, jen jedna kopie ID. |
| R38 | opraveno | `6f07fd57` | `tests_db/test_ddl_queue_state.py` R38 část (4, padaly 3; `test_abort_of_the_running_download_stops_it` kontrolní) | **Reprodukce:** zbylé `DDL_ABORT_REQUESTED=True` zrušilo další GC-Main stahování (`Failed`); abort jiné položky během stahování zrušil běžící; abort položky ve stavu `Queued` příznak nastavil. **Oprava:** smyčka příznak shodí na `False` na začátku každé položky; abort z UI nastaví příznak na **ID** položky a jen když je její řádek `Downloading`; GC-Main/Mirror přeruší jen stahování té položky (`helpers.ddl_abort_requested(id)`, `True` dál platí pro všechny). **Známé omezení:** Pixeldrain a MediaFire abort nečtou. |
| R24 | opraveno | `6c7d9230` | `tests_db/test_picker_retry.py` (7, padalo 7) | **Reprodukce** (vzor `ui/repro_dsr.py`, podvržený `getcomics.GC`): picker vrátil holé `False` (CherryPy z boolu neudělá odpověď), retry z historie `KeyError 'nzbid'`. **Oprava:** picker i retry doplní do `comicinfo` všechno, co `searcher` čte bez `.get` (`nzbid`, `pack_numbers`, `pack_issuelist`, `IssueID`, `ComicID`, `size`, `nzbtitle`) a předají `provider_stat` (nová `helpers.search_provider_stat`, typy jako `provider_order`). `nzbid` = ID příspěvku (z `link` u pickeru, z `nzblog.ID` u retry; `<post>-N` z `ddl_info` se nepoužije). Picker u DDL posílá `manualresults.link` (`?p=` URL), ne holé ID (`loadsite` by spadl). Pack: rozsah z `manualresults.pack_numbers` / `ddl_info.issues`, jinak `check_for_pack` z titulku, pak `issue_find_ids` (nová `helpers.ddl_pack_info`); retry packu podle `ddl_info.pack`. Picker vrací JSON (`status` + `error`/`message`), výjimku loguje s tracebackem, při neúspěchu `searcher` nevolá `foundsearch`, při části packu vrací nezařazené sekce jako `select_rejected_match`. Retry chytá výjimku a chybový výsledek `searcher` hlásí jako `failure` (dřív `success` i po `ddl-fail`). JS pickeru: zobrazí `error` z odpovědi (i když přijde jako text) a má `.fail()`; nic jiného v šabloně se neměnilo. **Dopad na GC-Main:** žádný na automatické stahování. |
| R39 | opraveno | `5fcf20c3` | `tests_db/test_direct_ddl.py` (6, padaly 3; Skipped/Ignored a requeue `1-5 + Annual 1-3`, `#1 - 5` kontrolní) | **Reprodukce** (vzor `ui/repro_ranges.py`): `Archived` číslo rozsahu šlo na `Snatched`; dva požadavky v jedné sekundě dostaly stejné `manual-1770040500`; requeue `Annual 1-3` dal položku s `comicinfo=None`. **Oprava:** `queue_direct_ddl` nemění (ani nezapíše do `nzblog`) čísla `Archived`; `Skipped`/`Ignored` jako dřív. ID `manual-<milisekundy>` z `webserve.new_direct_ddl_id` (zámek, monotónní, kontrola existence v `ddl_info`), jen číslice za prefixem. Requeue bere kontrolní číslo přes `getcomics_parse.direct_ddl_check_issue` jako `queue_direct_ddl`. |
| R42 | opraveno | `03177466` | `tests/test_getcomics_post.py` (2, padaly 2), `tests_db/test_tpb_extras.py` (6, padaly 4; hlavní odkaz TPB stránky a obnovené `77` jdou dál přes Q5, kontrolní) | **Reprodukce:** extra položka TPB seznamu po selhání vrátila TPB issue na `Wanted` a zapsala `failed` (`77-1`); opakování hlavního odkazu zařadilo extras znovu jako `1-2-1`, `1-2-2`; obnovená `<post>-N` s `pack=0` šla přes Q5. **Oprava:** `_queue_section` dá extra položce `pack_id` (ID příspěvku) a `tpb_extra=True`; extras se zařazují jen při prvním zařazení (`link_type_failure is None`, opakování ze smyčky ho vždy předává). Nová `helpers.ddl_item_is_tpb_extra`: `tpb_extra`, nebo položka bez kontextu s ID `<post>-N` a bez packu. `release_exhausted_ddl_item` pro ni nic nemění (řádek `ddl_info` je už `Failed`, žádný `failed`), `ddl_item_section_issueids` vrací `[]` (PP self-heal ani úklid `PACK_ISSUEIDS_DONT_QUEUE` čísla packu nesahají). Totéž platí pro heal (R20) a vyčerpané `incomplete`. Stávající Q5 testy (`test_single_exhausted.py`, `test_restored_items.py`) procházejí. **Dopad na GC-Main jednotlivých čísel:** žádný (ID bez `-N`). |
| R27 | opraveno | `0a6c2877` | `tests/test_getcomics_post.py` (6, padaly 4; „nic staženo“ a opakování sekce v `Downloading` kontrolní) | **Reprodukce:** Tomahawk, #1–70 `Downloaded`, hledané #71 → zařadily se oba sub-packy; druhé hledání téhož příspěvku zařadilo znovu `1-1`, který byl `Queued`/`Downloading`/`Completed`. **Oprava:** hledaná čísla packu jsou čísla nestažených issue z `pack_issuelist['issues']` (annualy jen když žádné běžné číslo nezbylo; když nezbylo nic, celý rozsah jako dřív), `choose_sections` beze změny. `_queue_section` při novém hledání (ne při opakování ze smyčky) nezařadí `<post>-N` (sub-pack nebo položku TPB seznamu), jehož řádek je `Queued`, `Downloading` nebo `Completed`; zaloguje a počítá ji jako zařazenou (její čísla R4 nevrací). Samostatný příspěvek `77` se dál zařadit dá (ruční nové stažení). |
| R19 | opraveno | `dd84f7ef` | `tests_db/test_pp_tidyup.py` (5, padaly 3; rozbalený pack a SAB kontrolní) | **Reprodukce** (vzor `cv/repro_rename.py` H): single DDL PP smazal prázdné `SABnzbd/incomplete` a `hunter-ddl/x`, v prázdném `DDL_LOCATION` smazal i `DDL_LOCATION`; u DDL položky mimo `DDL_LOCATION` smazal prázdné podsložky (knihovna). **Oprava** (Q15 a): v `tidyup` pro DDL (`self.ddl`) se adresáře mažou jen když jde o vlastní podsložku položky uvnitř `DDL_LOCATION` (`_ddl_own_folder`, `realpath`); jinak se smaže jen vlastní soubor položky, pokud tam ještě je. `DDL_LOCATION` nikdy. Manual Run a SAB beze změny. **Dopad na GC-Main:** po PP jednotlivého čísla zůstanou prázdné složky jiných nástrojů. |
| R18 | opraveno | `b35ba408` | `tests_db/test_pp_issue_number.py` (7, padalo 5; Spider-Man 2099 a „číslo jen mezi kandidáty“ kontrolní) | **Reprodukce** se skutečným filecheckerem (`listFiles` + `matchIT`) proti dočasné DB: `Top 10 005` → #10, `Kick-Ass 3 005` → #3, `Infinity 8 003` → #8, pack „Top 10 #1-12“ → všechny soubory na #10, `Top 10 005` i když #10 je `Downloaded`. **Oprava** (Q14 a): výběr čísla v PP bez issueid je v metodě `PostProcessor._issue_for_file` (nejdřív beze změny chování přesunutý, test na něm padal, pak otočené pořadí): nejdřív číslo z filecheckeru (`justthedigits`, TPB/One-Shot jako dřív, annual/special přes `_issue_for_number`), kandidáti z `possible_issuenumbers` (issues, pak annuals) až když to v sérii není. Když filechecker číslo nepřečte, zkusí se kandidáti dřív, než se položka vzdá. **Story-arc a one-off** (`possible_arc`, `possible_oneoff`) mají jiný vzor (číslo z oblouku stačí najít kdekoli mezi kandidáty), neopraveno, viz kap. 4. **Dopad na GC-Main jednotlivých čísel:** žádný (force-match podle issueid). |
| R17 | opraveno | `9f6b23b8` | `tests_db/test_pp_refresh.py` (5, padaly 3; „řádek je, nečeká“ a obnova stavů jako dřív kontrolní) | **Reprodukce** (vzor `cv/repro_rename.py` F, podvržený `importer`, žádný ComicVine): `foundsearch(down=…)` nad smazaným řádkem `TypeError: 'NoneType' object is not subscriptable` (jako v produkci); `dbUpdate` po PP, který zapsal #5 `Downloaded` s `Location` hned po reinsertu, obnovil `Location` na `None`. **Oprava:** `foundsearch` při chybějícím řádku issue/annual v režimu PP (`down`) čeká na refresh (`_wait_for_issue_row`, 24× `time.sleep(5)`, asi 2 min), pak pokračuje jako dřív; když se řádek nevrátí (i bez `down`), zaloguje ERROR s IssueID a vrátí `False`. PP pak zaloguje ERROR s IssueID a cestou souboru a nezapíše `Status`/`Location` upsertem (ten by založil řádek jen s IssueID). Obnova stavů v `dbUpdate` těsně před zápisem přečte aktuální řádek: je-li `Downloaded` s `Location`, `Status`, `Location` a `ComicSize` se nepřepíší. Globální zámek mezi PP a refreshem nezaveden. **Dopad na GC-Main jednotlivých čísel:** bez souběžného refreshe beze změny (kontrolní test nečeká). |

**Mimo zadání, jen zmíněno:**
- **R16/R41:** větev `links_exhausted` ve smyčce (`ddzstat` ji z downloaderů nikdy nemá, vrací ji jen
  `parse_downloadresults`) a úspěch při vypnutém `POST_PROCESSING` ID z `DDL_QUEUED` neodebírají. Produkce má PP
  zapnuté, neměnil jsem.
- **Abort položky `Queued`** (R38/R41): řádek jde na `Failed`, položka v paměťové frontě se ale stáhne (řádek
  existuje). Neměnil jsem.
- **R20 heal u extra položky TPB:** pokryto pravidlem R42 (obnovená `<post>-N`, `pack=0` jen `Failed`).
- **R37:** `upsert` bez UNIQUE na `issues`. Kvůli tomu PP při chybějícím řádku nezapisuje (R17).
- Ostatní nálezy (R10, R11, R14, R26, R28–R37, R40, R43–R45) se neměnily.

## 4. Otevřené otázky a konzervativní volby

1. **R25, obal místo `try/finally` přes 700 řádků.** `searchforissue` volá původní tělo (`_searchforissue`) a při
   výjimce v RSS běhu uvolní `SEARCHLOCK`, je-li `True`. Teoreticky to může být zámek jiného vlákna, které ho vzalo
   mezi čekáním a výjimkou (stejné okno jako stávající „zkontroluj a nastav“). Výjimka se dál posílá volajícímu.
   Když selže i `helpers.log_that_exception` (zápis do `exceptions_log`), původní chyba se dál zaloguje až jím
   (beze změny).
2. **R41, položky bez řádku.** Smyčka je přeskočí. Protože to platí pro všechny, čtyři starší testy dostaly
   řádek (kap. 2). Kdyby někdy vznikl producent, který zapíše řádek až po `put`, jeho položky by se přeskočily.
3. **R38, příznak nese ID.** UI větev „does not exist“ (řádek `Downloading`, soubor chybí) příznak nastaví na ID
   té položky; nic nestahuje, smyčka ho u další položky shodí a GC-Main přeruší jen stahování se stejným ID.
4. **R24, packy v pickeru.** `choose_specific_download` neuloží do `manualresults` výsledek packu
   (`pack_issuelist` je dict, SQLite ho neváže, výjimku spolkne `try`). Picker pak u packu vrátí „Unable to locate
   this result“. Ukládání jsem neměnil; když ho chceš, stačí ukládat `pack_issuelist=None` (picker ho dopočítá).
5. **R24, retry packu z historie** se dřív nepodporoval („packs not supported on retry atm“). Teď se podle
   `ddl_info.pack` dopočítá rozsah a zařadí jako pack. `ddl_info` se hledá podle `IssueID` (u packu první číslo).
6. **R24, retry vrací `failure`**, když `searcher` vrátí chybový řetězec (`ddl-fail`, `downloadchk-fail`). Dřív
   hlásil `success` i tehdy.
7. **R39, `Skipped`/`Ignored`** v ručně zadaném rozsahu dál jdou na `Snatched` (zadání). `Archived` číslo zůstává
   v `pack_issuelist` položky (stahuje se celý archiv); PP ho podle stávající kontroly duplicit může zpracovat.
8. **R39, formát ID** `manual-<13 číslic>` (milisekundy) místo `manual-<10 číslic>`. Hunter testuje jen
   `startswith("manual-")`, Comics `manual-` nepoužívá. Druhá pomlčka by z ID udělala „sub-pack“ pro
   `pack_queued_for_download`, proto jen číslice.
9. **R42, obnovená `<post>-N` s `pack=0`** se bere jen jako `Failed` (zadání). Týká se i hlavního odkazu TPB
   stránky se seznamem „TPBs“ po restartu: jeho číslo pak zůstane `Snatched` (jako před R16). Obnovené extras
   TPB **packu** (`pack=1`) jdou cestou obnoveného packu jako dřív.
10. **R27, annualy v hledaných číslech** jen když nezbylo žádné běžné číslo („Annual 1“ by jinak vybralo „#1 – 70“).
    **Zbytek cyklu s R4** (sekce bez povoleného hosta jde na `Wanted`, příští hledání najde tentýž příspěvek a sekce
    se zase nezařadí) jsem podle Q4 nechal. Samostatným testem jsem ho nereprodukoval; z kódu: nezařaditelná sekce
    nemá řádek `ddl_info`, ochrana R27 se jí netýká, takže se pokus opakuje každý cyklus hledání (bez stahování).
    Otevřená otázka, zda zavést blacklist sekce.
11. **R18, story-arc a one-off větve** (`PostProcessor.py`, `possible_arc` a `possible_oneoff`) přijmou soubor,
    když je hledané číslo kdekoli mezi kandidáty: `Top 10 005` projde i pro položku oblouku `Top 10 #10`. Jiný
    vzor než pořadí, test ho nepokrývá, neopraveno.
12. **R18, refaktoring kvůli testu.** Výběr čísla je přesunutý do `_issue_for_file`/`_issue_for_number`, aby šel
    testovat bez celého PP. Nedosažitelná větev „bez čísla → všechna issue série“ odpadla (temploc `None` nastává
    jen u ne-TPB, kde původní kód skončil dřív).
13. **R17, čekání jen pro PP** (`down`), nejvýš asi 2 minuty, blokuje vlákno PP. Při snatchi (UI, hledání) se
    nečeká a vrátí se `False` s ERROR (dřív `TypeError`). Větev PP, která při `False` nezapíše `Location`, nepokrývá
    test (vyžadovala by běh celého PP), jen čtení kódu.
14. **R19, DDL položka mimo `DDL_LOCATION`** (např. ručně zadaná cesta) nemaže žádný adresář, jen svůj soubor,
    pokud tam ještě je. Speciální složka `mega` beze změny.

## 5. Kontrola Comics a comics-nzb-hunteru

- **API:** `api.py` se neměnil. Žádný z obou klientů nevolá změněné webové akce (`download_specific_release`,
  `retryissue`, `select_rejected_match`, `queue_direct_ddl`, `ddl_requeue`, `post_process`, `manual_pp_status`;
  grep bez nálezu). `refreshComic` a `forceProcess` beze změny; po R17 PP souběžný s refreshem téže série počká
  na řádek místo pádu (spouštěč hunteru `refreshComic` → `forceProcess`).
- **Schéma:** žádná nová tabulka ani sloupec. **Stavy issue:** žádný nový stav. **Formát ID v `ddl_info`:**
  `<id>`, `<id>-N` beze změny; `manual-` + číslice (jen delší, viz kap. 4 bod 8).
- **Pojmenování souborů (R17, R18):** beze změny. R18 mění jen to, ke kterému issue se soubor bez issueid přiřadí
  (jméno se pak tvoří stejně). R17 zapisuje `Downloaded`/`Location` stejně jako dřív, jen počká na řádek a
  refresh je nepřepíše.
- **Řádky ve `failed`:** nový tvar žádný. Ubude řádků `<post>-N` z extra položek TPB (R42). Q5 jednotlivých čísel
  (`ID` = ID příspěvku, `Provider='DDL(GetComics)'`, skutečné `IssueID`/`Issue_Number`) beze změny.
- **`ddl_info`:** smyčka už nezakládá řádky jen s `id`/`status` (R41). Hunter čte `status='Completed'` beze změny.

## 6. Nasazení (pro uživatele)

Nasazuje se až po první části nebo spolu s ní. První část je v `python3-dev`, ale nenasazená, a tato větev na ní
stojí. Merge do `python3-dev`, nasazení a restart jen se souhlasem. Změněné soubory obou částí jmenovitě:

```sh
# druhá část
docker cp mylar/getcomics.py mylar:/app/mylar/mylar/getcomics.py
docker cp mylar/helpers.py mylar:/app/mylar/mylar/helpers.py
docker cp mylar/PostProcessor.py mylar:/app/mylar/mylar/PostProcessor.py
docker cp mylar/search.py mylar:/app/mylar/mylar/search.py
docker cp mylar/updater.py mylar:/app/mylar/mylar/updater.py
docker cp mylar/webserve.py mylar:/app/mylar/mylar/webserve.py
docker cp data/interfaces/default/comicdetails_update.html mylar:/app/mylar/data/interfaces/default/comicdetails_update.html
# z první části (tato část je neměnila)
docker cp mylar/search_filer.py mylar:/app/mylar/mylar/search_filer.py
docker cp mylar/filers.py mylar:/app/mylar/mylar/filers.py
docker cp mylar/downloaders/pixeldrain.py mylar:/app/mylar/mylar/downloaders/pixeldrain.py
docker cp mylar/downloaders/mediafire.py mylar:/app/mylar/mylar/downloaders/mediafire.py
docker cp data/interfaces/default/queue_management.html mylar:/app/mylar/data/interfaces/default/queue_management.html
```

- Před restartem `docker logs mylar --tail 50`: restart přeruší běžící DDL a PP a smaže `REJECTED_MATCHES`,
  `PACK_ISSUEIDS_DONT_QUEUE`, `DDL_HEAL_PP_COUNT` a položky fronty s kontextem.
- **Rebuild image (R14) a připnutí závislostí (Q8)** jsou samostatný krok uživatele po merge.

**Ověření po restartu:**

- markery: `docker exec mylar grep -c "def ddl_item_is_tpb_extra" /app/mylar/mylar/helpers.py`,
  `… grep -c "def ddl_abort_requested" …/helpers.py`, `… grep -c "def search_provider_stat" …/helpers.py`,
  `… grep -c "tpb_extra" /app/mylar/mylar/getcomics.py`, `… grep -c "def _issue_for_file" /app/mylar/mylar/PostProcessor.py`,
  `… grep -c "def _ddl_own_folder" …/PostProcessor.py`, `… grep -c "def _searchforissue" /app/mylar/mylar/search.py`,
  `… grep -c "def _wait_for_issue_row" /app/mylar/mylar/updater.py`, `… grep -c "def new_direct_ddl_id" /app/mylar/mylar/webserve.py`,
  `… grep -c "Error downloading " /app/mylar/data/interfaces/default/comicdetails_update.html`;
- `docker logs mylar --tail 50`: start bez tracebacku, `[DDL-DOWNLOADER] DDL downloader thread started and running`;
- **UI** (v prohlížeči neověřeno): picker ručního hledání u DDL výsledku (stáhne, nebo ukáže chybu, žádný
  nekonečný spinner); výběr odmítnuté shody (po úspěchu shoda z dialogu zmizí, druhé kliknutí hlásí chybu);
  přímé DDL rozsahu na stránce série (`Archived` čísla zůstanou); Queue Management: Remove/Vyčistit frontu,
  Abort; ruční PP (po chybě se tlačítko uvolní);
- **nové hlášky v logu:** `[DDL-DOWNLOADER] … was removed from the queue. Skipping it.`,
  `[DDL-DOWNLOADER] … is an extra item of a TPB list. Only the download failed; …`,
  `[DDL-QUEUE] … is already Queued/Downloading/Completed. Not queueing it again.`,
  `[SEARCH] The RSS search scan ended with an error. Releasing the search lock.`,
  `[SELECT-REJECTED-MATCH] Chosen match for IssueID … not found in the stored rejected matches, nothing removed`,
  `[DOWNLOAD-SPECIFIC-RELEASE] Download of … failed: …` / `… was not started: …`, `[RETRY] Retry of … failed/was not sent`,
  `[QUEUE-DIRECT-DDL] IssueID … is Archived. Leaving its status as it is.`,
  `[UPDATER] IssueID … is not in the issues table - a series refresh is likely in progress. Waiting for it.` a
  `… is back in the issues table. Continuing.` (nebo ERROR `… Its status was not updated.` a v PP
  `… The file is in the library at …, but its status and location were not written.`),
  fdebug `[#…] IssueID … was post-processed during the refresh. Keeping its status and location.`,
  fdebug `Not removing directories in …: it is not the download's own folder.`;
- za provozu u jednotlivých čísel přes GC-Main stejné `Now downloading`/`Completed` jako dřív a po PP zůstanou
  prázdné složky v `/downloads` (`SABnzbd`, `hunter-ddl`).

## 7. Stav po merge

2026-11-22 (časy pražské):

- **Merge** v 16:09 na pokyn uživatele: `python3-dev` posunuta fast-forwardem z `b912ddc4` na `aeddc549`,
  bez merge commitu. Na `python3-dev` v hlavním stromu znovu `tests/` 96 passed, `tests_db/` 142 passed,
  `ast.parse` šesti změněných modulů v 3.8 bez chyby.
- **Push** na pokyn uživatele: `fork/python3-dev` `b912ddc4..328edce1` (včetně záznamu o merge). Na `origin` nic.
- Worktree `/data/Tarzan/Cursor/Mylar-review-2026-11-22-part2` a větev `claude/review-2026-11-22-part2` zatím
  zůstávají (celá větev je v `python3-dev`).

## 8. Nasazení

2026-11-22 (časy pražské, v závorce UTC z `docker logs`), na pokyn uživatele, **první i druhá část najednou**
(stav `python3-dev` `328edce1`):

- **Před nasazením** `docker logs mylar`: fronta DDL prázdná (`DDL_LOCK: False`, `Queue size: 0`,
  `DDL_QUEUED count: 0`), za posledních 15 min žádné stahování ani post-processing, běžela jen fronta hledání.
  Těsně před restartem znovu ověřeno.
- **`docker cp`** 12 souborů podle kap. 6: `mylar/getcomics.py`, `helpers.py`, `PostProcessor.py`, `search.py`,
  `updater.py`, `webserve.py`, `search_filer.py`, `filers.py`, `downloaders/pixeldrain.py`,
  `downloaders/mediafire.py`, `data/interfaces/default/comicdetails_update.html`, `queue_management.html`.
  md5 všech 12 v kontejneru = repo.
- **`docker restart mylar`** v 16:26 SEČ (15:26 UTC). Start čistý: `Starting Mylar on http://0.0.0.0:8090/`,
  `[DDL-STARTUP] No queued items found in ddl_info table`, `[DDL-DOWNLOADER] DDL downloader thread started and
  running`, `[DDL-WATCHDOG] DDL Watchdog thread started`. Jediné varování `No branch specified within config`
  (běžné). V dalších minutách žádný ERROR ani traceback.
- **Šablony:** `curl` z devel-workstation na `http://mylar:8090` (UI nemá proxy host, `mylar.tarzan77.cz` vede
  na přihlášení brány UniFi UCG Max): `queueManage` 200 s `ajaxcallit('restart_queue')`, `comicDetails` (série
  `160511`) 200 s novým JS pickeru (`Error downloading`), bez chyby Mako. Log po načtení bez chyb.
- **Neověřeno:** v prohlížeči nic (Playwright MCP se na Mylar nedostane, skončil na přihlášení UniFi OS). Akce
  měnící stav (picker, výběr odmítnuté shody, přímé DDL, Remove, Abort, Restart Queue, ruční PP) se
  nespouštěly. Hlášky k ověření za provozu v kap. 6.
- **Image `mylar3:local` se nepřestavoval.** Běžící kód je teď o obě části review před image; recreate kontejneru
  by produkci vrátil na stav z 11. 9. Další krok: po pár dnech klidného provozu rebuild image z `python3-dev`
  a recreate přes Dockhand (R14, Q8), pak třetí (bezpečnostní) část.
