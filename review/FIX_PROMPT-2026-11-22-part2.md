# Zadání: opravy nálezů z review Mylaru 2026-11-22, druhá část

## Kontext

**Mylar** (fork mylar3, `tarzan77cz/mylar3`) je automatický stahovač komiksů. Běží ostře nad knihovnou asi
11 300 sérií a denně stahuje jednotlivá nová čísla z GetComics (DDL), packů je pár za měsíc. Hlavní riziko je
ztráta nebo poškození souborů v knihovně (soubor uložený jako jiné číslo, přepsaný, smazaný) a tiché selhání
stahování. **Stahování jednotlivých čísel přes GC-Main (Download Now) a jejich post-processing fungují a nesmí
se změnit.** Opravy se jich dotknou jen tam, kde to nález výslovně žádá.

Druhá část navazuje na první (větev `claude/review-2026-11-22`, R12, R13, R15, R16, R20, R21, R22 a úklid
R47–R51). Ta ještě nemusí být v `python3-dev`.

- **Pravidla repa:** `CLAUDE.md` ve worktree (aktualizovaný v R51: Python 3.8, `sqlite3.Row` nemá `.get()`,
  živé služby, secrets, styl commitů, sekce Review, druhý klient API comics-nzb-hunter). Přečti ho jako první.
- **Nálezy s doklady a scénáři:** `review/REVIEW-2026-11-22.md`. U každého nálezu čti jeho řádek v tabulce
  (kap. 4), navržené testy (kap. 8) a otázky (kap. 10). Čísla řádků v review platí pro `a4d24a40`; v
  `helpers.py`, `getcomics.py`, `webserve.py`, `search_filer.py` a downloaderech je první část posunula, hledej
  podle jmen funkcí.
- **Rozhodnutí uživatele:** kap. 11 téže zprávy včetně doplnění z odpoledne 22. 11. (Q14 a, Q15 a, R41 přidán,
  bezpečnost zvlášť). Jsou závazná.
- **Minulé opravy, jejichž chování neměň, pokud to nález nežádá:**
  - `review/FOLLOWUPS-2026-11-21.md` (R1–R9, Q5: `pack_id`, `section_issues`, `release_exhausted_ddl_item`,
    `reverse_ddl_item_snatch`),
  - `review/FOLLOWUPS-2026-11-22.md` (první část: `ddl_host_download_check`, `ddl_row_file`,
    `ddl_item_is_pack`, `release_restored_ddl_item`, supervisor `ddl_downloader`/`search_queue`,
    `ddl_thread_check`, `ddl_download_in_progress`, `DDL_HEAL_PP_COUNT`). Přečti hlavně jeho kap. 6.
- **Reprodukce z review** (v `.gitignore`, do repa je nekopíruj, použij jako výchozí bod testů): `.scratch/review-2026-11-22/`
  v hlavním stromu `/data/Tarzan/Cursor/Mylar/` (a kopie ve worktree první části
  `/data/Tarzan/Cursor/Mylar-review-2026-11-22/.scratch/`):
  - `cv/repro_rename.py` (F: `foundsearch` nad smazaným issue, R17; H: `_remove_empty_dirs`, R19),
    `cv/repro_possible.py` (R18), `cv/pp_overlap.py`,
  - `ui/repro_select.py` (R23), `ui/repro_dsr.py` (R24), `ui/repro_ranges.py` (R39), `ui/repro_verification.py`,
  - `h/test_h_repro.py::test_tpb_extra_item_exhausted_marks_issue_wanted` (R42), `ddl/r1`, `ddl/r3` (R41).
- **Testové pomůcky z první části:** `tests_db/conftest.py` (`lib`, `run_ddl_downloader`), `tests_db/fakes.py`
  (podvržené `requests.Session.get`), `tests_db/test_restored_items.py` (`ScriptedGC`), `tests_db/test_restart_queue.py`
  (skutečné `WebInterface.ddl_requeue`).
- **Navazující repa:** `/data/Tarzan/Cursor/Comics` a `/data/Tarzan/Cursor/scripts/apps/comics-nzb-hunter`
  volají Mylar API (`getWanted`, `getComic`, `getIssueInfo`, `refreshComic`, `addComic`, `findComic`,
  `unqueueIssue`, `forceProcess`, `recheckFiles`, `queueIssue`) a čtou `mylar.db` (`ddl_info`, `issues`,
  `failed`). Neměň schéma žádné tabulky, formát ID v `ddl_info` (`<id>`, `<id>-N`, `manual-…`), názvy stavů,
  pojmenování souborů ani odpovědi API. Spouštěč R17 je pravděpodobně hunter (`refreshComic` a hned
  `forceProcess`): jeho volání `refreshComic` nesmíš rozbít (obchází chybu R45 v `mylar_client.py:66-75`,
  R45 se neopravuje).

## Režim práce: bez dozoru, všechno v jedné session

Uživatel u toho není. **Na nic se neptej a nezastavuj se mezi nálezy**, nikdo neodpoví. Projdi všechny nálezy
a na konci napiš a commitni souhrn. Když něco nejde nebo si nejsi jistý, zvol konzervativnější variantu,
zapiš ji do souhrnu jako otevřenou otázku a pokračuj dalším nálezem.

## Pravidla

1. **Izolace.** Založ worktree navazující na první část. Když je `claude/review-2026-11-22` už v `python3-dev`
   (`git -C /data/Tarzan/Cursor/Mylar merge-base --is-ancestor claude/review-2026-11-22 python3-dev` vrátí 0),
   zakládej z `python3-dev`, jinak z `claude/review-2026-11-22`:
   `git -C /data/Tarzan/Cursor/Mylar worktree add -b claude/review-2026-11-22-part2 /data/Tarzan/Cursor/Mylar-review-2026-11-22-part2 <základ>`.
   Zapiš do souhrnu, z čeho jsi zakládal. Pracuj jen tam. Hlavní strom ani worktree první části nepřepínej
   a neměň (ani netrackované soubory). Nepushuj, nemerguj, nepřepisuj historii.
2. **Review soubory** (`REVIEW_PROMPT-2026-11-22.md`, `REVIEW-2026-11-22.md`, `FIX_PROMPT-2026-11-22*.md`,
   `FOLLOWUPS-2026-11-22.md`) neměň, výsledky patří do nového `FOLLOWUPS-2026-11-22-part2.md`.
3. **Na živou aplikaci nesahej:** žádný `docker cp`, `docker restart`, `docker exec` do kontejneru `mylar`,
   žádné volání Mylar API, žádné dotazy do `mylar.db`, nic v `/comics` a `/downloads`. Nečti
   `/config/mylar/config.ini`, `env` kontejneru ani `docker inspect mylar`. Žádná síť (GetComics, Pixeldrain,
   MediaFire, ComicVine). Číst `docker logs mylar` smíš (časy v něm jsou UTC, do souhrnu je převeď na
   pražský čas). Image `mylar3:local` nepřestavuj a nepřetaguj.
4. **Opravuj jen nálezy z tohoto zadání:** R17, R18, R19, R23, R24, R25, R27, R38, R39, R41, R42, R46.
   Ostatní (R10, R11, R14, R26, R28–R37, R40, R43–R45) nech být, i když na ně narazíš; jen je případně zmiň
   v souhrnu. Žádné refaktoringy ani vylepšení navíc. `lib/` neměň.
5. **Test dřív než oprava.** Každý test musí před opravou selhat a po ní projít. Když neselže, nález se
   nereprodukuje: neopravuj ho a napiš proč. Ověř to aspoň u větších oprav i odložením změn (`git stash`
   jen ve tvém worktree). Kontrolní testy, které procházejí i před opravou (hlídají nezměněné chování),
   tak v souhrnu označ.
6. **Commit na nález** (nebo úzce související skupinu), anglicky, jedna věta v rozkazovacím způsobu, co a proč,
   ID na konci, např. „Prefer the issue number the file checker picked over other numbers in the name when
   post-processing a pack, so Top 10 005 is no longer filed as #10 (R18)“. Commit jen v repu Mylar.
7. **Python 3.8.** Nic z 3.9+ (`match`, `X | Y`, `list[str]` mimo řetězce, `removeprefix`, `dict | dict`,
   `zoneinfo`). Na `sqlite3.Row` nikdy `.get()` a ani `'col' in row` (to testuje hodnoty, viz R46); sloupce přes
   `row['col']`, `row.keys()` nebo `try/except (KeyError, IndexError)`.
8. **Nic nemaž natrvalo.** Žádný soubor z repa se v této části neodstraňuje. Kdyby přesto bylo potřeba,
   nejdřív kopie do `/data/Tarzan/Cursor/_archive/2026-11-22-mylar-cleanup-part2/` se zachovanou cestou.
9. **Šablony a JS:** měň jen to, co nález žádá. Mako šablonu po změně zkompiluj (`TemplateLookup` nad
   `data/interfaces/default`, vzor ve FOLLOWUPS první části); v prohlížeči se neověřuje, napiš to.

## Testy a prostředí

Worktree leží na Z2 pod `/share/Tarzan/Cursor/Mylar-review-2026-11-22-part2`, Docker socket patří Z2:

```sh
docker run --rm -e PYTHONDONTWRITEBYTECODE=1 -v /share/Tarzan/Cursor/Mylar-review-2026-11-22-part2:/src:ro mylar3:local \
  sh -c "pip install -q pytest >/dev/null 2>&1; cd /src && python3 -m pytest -q -p no:cacheprovider tests"
docker run --rm -e PYTHONDONTWRITEBYTECODE=1 -v /share/Tarzan/Cursor/Mylar-review-2026-11-22-part2:/src:ro mylar3:local \
  sh -c "pip install -q pytest >/dev/null 2>&1; cd /src && python3 -m pytest -q -p no:cacheprovider tests_db"
```

- **Výchozí stav nejdřív:** na čistém worktree `tests` 88 passed, `tests_db` 85 passed (stav po první části).
  Zapiš do souhrnu.
- Nové testy s DB, PP, webovými akcemi a smyčkou `ddl_downloader` patří do `tests_db/` (skutečný balík `mylar`,
  dočasná SQLite). Schéma v `tests_db/conftest.py` můžeš rozšířit o sloupce a tabulky, které test potřebuje
  (`comics`, `issues`, `annuals`, `storyarcs`, `snatched`, `manualresults`…); auto-load bez tabulky `storyarcs`
  se zacyklí, viz FOLLOWUPS první části. Smyčky zastavuj přes `'exit'` ve frontě nebo podvržený `time.sleep`,
  který vyhodí vlastní `BaseException`.
- Před každým commitem: obě sady testů a `ast.parse` změněných souborů v image (příkaz v `CLAUDE.md`).
- Na konci navíc import všech modulů `mylar.*` v 3.8.2 (`sys.path[:0] = ['/src', '/src/lib']`), vzor
  `.scratch/review-2026-11-22/try_imports.py`: musí zůstat 71 ze 71.

## Nálezy a co přesně udělat

Pořadí: R46 → R25 → R41 → R38 → R23 → R24 → R39 → R42 → R27 → R19 → R18 → R17.

### R46 (nízká): `'IssueDate' in issue` na `sqlite3.Row`

- `webserve.select_rejected_match` (obě větve, dnes kolem `webserve.py:4052` a `:4234`): test názvu sloupce přes
  `issue.keys()`. Grep celého `mylar/` na `in issue`, `in row` apod. nad `sqlite3.Row` v kódu forku a oprav jen
  stejný vzor ve stejné funkci; jiné výskyty zapiš.
- Test: řádek `issues` s `IssueDate='2020-05-01'`, výběr odmítnuté shody bez `verified_data` → `searcher`
  dostane `IssueDate='2020-05-01'` (dnes `''`).

### R25 (střední): `smode` v hromadné větvi `searchforissue`

- `search.py:2077` (`'smode': smode` v obsluze výjimky, kde `smode` není přiřazené): výjimka položky se musí
  zalogovat s původní chybou a tracebackem a nesmí opustit funkci s `SEARCHLOCK=True` (nastaven kolem `:1665`,
  uvolněn kolem `:2355`). Konzervativně: v obsluze nepoužívej nepřiřazenou proměnnou, zbytek dávky zpracuj jako
  dnes a `SEARCHLOCK` uvolni i při chybě (`try/finally` kolem úseku, který ho drží). `search_queue` má od první
  části supervisor, ten ale `SEARCHLOCK` neuvolňuje.
- Test: RSS/hromadná položka, u které zpracování vyhodí výjimku (např. `comic` je `None`), → funkce neskončí
  `UnboundLocalError`, v logu je původní chyba, `SEARCHLOCK` je `False`, další položka dávky se zpracuje.

### R41 (nízká, přidaný): stav DDL fronty a ručního PP

Tři části jednoho nálezu:
- `getcomics.GC.downloadit` přidá ID do `DDL_QUEUED` podruhé (smyčka ho už přidala), úklid odebere jednu kopii.
  Nepřidávej, když tam ID je. Test: po úspěšném i neúspěšném stažení přes GC-Main ID v `DDL_QUEUED` není
  (v `tests_db/test_queue_threads.py` je k tomu poznámka, uprav ji na kontrolu).
- „Vyčistit frontu“ (`webserve`, `clear_queue`) a „Remove“ (`ddl_requeue('remove')`) mažou jen řádky v DB,
  položky v paměťové frontě se stáhnou dál a upsert založí řádek jen s `id`/`status`. Smyčka `ddl_downloader`
  má položku, jejíž řádek v `ddl_info` už neexistuje, přeskočit (log, žádné stahování, nic nezakládat, ID
  odebrat z `DDL_QUEUED`). Před tím ověř, že všichni producenti fronty (`getcomics._queue_section`,
  `queue_direct_ddl`, `ddl_requeue`, auto-load, startovní načítání, vrácení po `incomplete`) zapisují řádek
  **před** `put`; když ne, napiš to a zvol variantu, která čerstvou položku nezahodí. Test: položka ve frontě,
  její řádek smazaný → `downloadit` se nezavolá, řádek nevznikne.
- `MANUAL_PP_STATUS['running']` se po výjimce v ručním PP nevrátí na `False` (nastavuje ho `webserve.py` kolem
  `:2042`, průběh a konec `PostProcessor.py` kolem `:465-469`, `:535-550`, `:2505`, `:2670`; polling v
  `manage.html`). Vrať ho ve `finally` toho místa, které ruční PP spouští. Test: ruční PP vyhodí výjimku →
  `running` je `False`.

### R38 (nízká): `DDL_ABORT_REQUESTED` zůstane `True`

- Příznak čte jen GC-Main/Mirror. Abort u GC-Pixel/GC-Media nebo v UI větvi „does not exist“ ho nechá `True`
  a příští GC-Main stahování se tiše zruší. Oprava: smyčka `ddl_downloader` příznak shodí na `False`, když
  začíná nová položka (abort platí jen pro právě stahovanou), a UI větev, která nic nestahuje, ho nenastaví.
  Pixeldrain a MediaFire abort číst nemusí (zapiš jako známé omezení).
- Test: `DDL_ABORT_REQUESTED=True` zbylý z předchozí položky → další GC-Main položka se stáhne (podvržené
  `requests`, vzor `tests_db/test_queue_threads.py`).

### R23 (střední): `select_rejected_match` maže z jiného seznamu

- Index `match_index_to_remove` se počítá v uloženém `mylar.REJECTED_MATCHES[IssueID]`, `pop` se volá na
  filtrovaném seznamu z `_filter_offerable_rejected_matches`. Obě větve funkce mají stejný kód, oprav obě
  stejně (nesjednocuj je, to je refaktoring navíc).
- Oprava: vybranou shodu najdi v uloženém seznamu (`search_filer._find_rejected_match_index` podle `link`
  a `nzbid`) a odeber ji z uloženého seznamu; `IndexError` po úspěšném `searcher`/`foundsearch` už nesmí nastat.
  Druhé kliknutí na tutéž shodu vrátí chybu bez volání `searcher`.
- Testy (kap. 8, vzor `ui/repro_select.py`): `REJECTED_MATCHES[I] = [neoferovaná, m1, m2]`, výběr m2 → success,
  m2 zmizí z uloženého seznamu, m1 a neoferovaná zůstanou; druhý výběr m2 → chyba, `searcher` se nezavolá.
  Varianta B (vše oferované) → po výběru shoda v uloženém seznamu není.

### R24 (střední): picker a retry z historie bez `nzbid`

- `download_specific_release` (picker) a `retryissue` (retry z historie) staví `comicinfo` bez `nzbid`,
  `pack_numbers`, `pack_issuelist` a bez `provider_stat`; `searcher` spadne na `KeyError 'nzbid'`
  (`search.py:2902`), u pickeru to spolkne holé `except`. Doplň klíče tak, jak je `searcher` čte (projdi celý
  `searcher` pro DDL i NZB větev, ne jen první `KeyError`), hodnoty ber z řádku `manualresults` / historie
  (`nzbid` = ID příspěvku z linku, pack podle titulku přes stávající `check_for_pack`/`issue_find_ids`, když je to
  pack). U pickeru zaloguj výjimku místo tichého `False`. `retryissue` u DDL nesmí vrátit HTTP 500.
- JS pickeru (`comicdetails_update.html:1419-1435`) nemá fail handler a nechá spinner; přidej jen zobrazení chyby
  z odpovědi, nic jiného v šabloně neměň.
- Testy (vzor `ui/repro_dsr.py`): řádek `manualresults` pro `DDL(GetComics)` → `searcher` se zavolá s úplným
  `comicinfo` a vrátí success; retry z historie DDL → `searcher` zavolán, žádná výjimka. Podvrhni `searcher`
  nebo `getcomics.GC`, síť nesmí běžet.

### R39 (nízká): přímé DDL rozsahu

- `queue_direct_ddl` dá na `Snatched` každé číslo rozsahu kromě `Downloaded`. Nesmí měnit `Archived` (soubor
  existuje). `Skipped` a `Ignored` nech jako dnes (uživatel rozsah vybral ručně) a zapiš to jako otevřenou otázku.
- `pack_id='manual-<int(time)>'` sdílí dva požadavky v jedné sekundě: udělej ID unikátní, ale ponech prefix
  `manual-` a jen znaky, se kterými počítá zbytek kódu a Comics (grep `manual-` v obou repech).
- Requeue rekonstruuje kontrolní číslo naivním `split('-')` (`webserve.ddl_requeue`, kolem
  `item['issues'].strip().split('-')[0]`): použij `getcomics_parse.direct_ddl_check_issue` jako
  `queue_direct_ddl` (R8), aby „Annual 1-3“ nevracelo `valid=False` a `comicinfo=None`.
- Testy (vzor `ui/repro_ranges.py`, `tests_db/test_issue_find_ids.py`): rozsah s `Archived` číslem → zůstane
  `Archived`; dva požadavky ve stejné sekundě → dvě různá ID; requeue `Annual 1-3` → položka má `comicinfo`
  a `packinfo`.

### R42 (nízká): TPB extras a Q5

- Extra položky TPB seznamu (`x is not link` v `_queue_section`) nemají `pack_id`, mají `issueid` a `pack=False`,
  takže selhání jedné z nich spustí Q5 pro TPB issue (`Wanted` + `failed` s `<post>-1`), zatímco hlavní odkaz
  se stahuje. Opakování sekce (`section is not None`) má `include_extras=True` a extras zařadí znovu.
- Oprava: extra položka nese `pack_id` = ID příspěvku a příznak, podle kterého ji `release_exhausted_ddl_item`
  / `release_restored_ddl_item` pozná; její selhání nastaví jen `ddl_info` `Failed` bez změny issue a bez
  zápisu do `failed` (čísla řídí hlavní odkaz). Opakování sekce extras znovu nezařazuje. Jak extra pozná
  položka obnovená z `ddl_info` (bez kontextu, ID `<post>-N`, `pack=0`), zvol konzervativně a zapiš (nejspíš:
  obnovená `<post>-N` s `pack=0` se jako jednotlivé číslo nebere, jen `Failed`).
- Testy: `h/test_h_repro.py::test_tpb_extra_item_exhausted_marks_issue_wanted` se otočí (TPB issue zůstane
  `Snatched`, `failed` prázdné); opakování sekce s TPB seznamem nezařadí `<id>-1-1`. Stávající testy Q5 pro
  jednotlivé číslo (`test_single_exhausted.py`, `test_restored_items.py`) musí dál procházet.

### R27 (střední): pack vybírá stažené sub-packy a cyklus s R4

- Hledaná čísla packu se berou z `pack_issuelist['issue_range']` (celý rozsah), ne z nestažených čísel
  (`pack_issuelist['issues']`, které vybírá `issue_find_ids`). `choose_sections` proto vybere i sub-pack, jehož
  čísla jsou všechna `Downloaded`. Oprava: hledaná čísla = čísla nestažených issue z `pack_issuelist['issues']`
  (annualy podle `section_annual`), `choose_sections` beze změny.
- Cyklus s R4: nezařaditelná sekce jde na `Wanted`, příští hledání najde tentýž příspěvek a zařadí znovu i sekce,
  které se stahují nebo stáhly (upsert stejného `<id>-N` zpět na `Queued`). `_queue_section` nesmí znovu zařadit
  sekci, jejíž řádek `<id>-N` je `Queued`, `Downloading` nebo `Completed` (log, sekce se počítá jako zařazená).
  Zbytek cyklu (sekce bez povoleného hosta se vrací na `Wanted` a hledání ji najde znovu) podle Q4 nech; když ho
  reprodukuješ, popiš ho v souhrnu jako otevřenou otázku, nezaváděj blacklist.
- Testy: `tests/test_getcomics_post.py::test_pack_queues_every_matching_subpack` (zařadí obě sekce i s `issues: []`) uprav jen pokud
  odporuje nové logice a napiš proč; nový `test_pack_skips_subpack_with_all_issues_downloaded` (Tomahawk,
  #1–70 `Downloaded`, hledané #71 → zařadí se jen `#71 – 140`); druhé hledání stejného příspěvku, když `1-1` je
  `Downloading` → `1-1` se znovu nezařadí a jeho řádek zůstane `Downloading`.

### R19 (střední): mazání prázdných adresářů v `/downloads` (rozhodnutí Q15 a)

- U single DDL je `nzb_folder` cesta k souboru, `tidyup` z ní udělá `DDL_LOCATION` a `_remove_empty_dirs`
  maže prázdné adresáře v celém `/downloads` a zkusí `rmtree` samotného `DDL_LOCATION`. Oprava: u DDL souboru
  přímo v `DDL_LOCATION` se nemaže žádný adresář; u DDL položky ve vlastní podsložce (rozbalený pack) jen ta
  podsložka, když je prázdná; `DDL_LOCATION` samotný nikdy. Manual Run a SAB beze změny.
- Testy (vzor `cv/repro_rename.py` H): `DDL_LOCATION` s prázdnými `SABnzbd/incomplete` a `hunter-ddl/x`, single DDL
  PP → oba zůstanou, `DDL_LOCATION` existuje; rozbalený pack ve `DDL_LOCATION/Pack/` po PP prázdný → `Pack/`
  zmizí, sourozenci zůstanou. Knihovny `/comics` se úklid netýká, ověř to testem s cestou mimo `DDL_LOCATION`.

### R18 (střední): pořadí čísel v PP bez issueid (rozhodnutí Q14 a)

- `PostProcessor.py` kolem `:1175-1192`: bez `issueid` (DDL packy, Manual Run) se bere první kandidát
  z `possible_issuenumbers`, který v sérii existuje, dřív než číslo, které vybral filechecker. Oprava: nejdřív
  číslo z filecheckeru (`justthedigits` / jak ho PP dnes čte), kandidáti z `possible_issuenumbers` až když
  filecheckerovo číslo v sérii není; stejně pro fallback do `annuals`. Story-arc a one-off větve (`:1746`,
  `:2119`) mají stejný vzor: oprav je stejně jen když jde o totéž pořadí a test to pokryje, jinak je zapiš.
- Testy (kap. 8, vzor `cv/repro_possible.py`): série „Top 10“ s #5 a #10, `Top 10 005 (2000).cbz` → #5;
  `Kick-Ass 3 005 (2014)` → #5; `Infinity 8 003 (2017)` → #3; soubor, kde filechecker číslo nepozná a správné je
  jen v `possible_issuenumbers` → dál se najde (kontrolní). Pack „Top 10 #1-12“ → každý soubor na své číslo.
- Pozor na přepis duplicit: test, že `Top 10 005` se nezapíše přes existující #10.

### R17 (střední): PP souběžně s refreshem série

- Když souběžný `dbUpdate` (snapshot → CV → `DELETE` → reinsert → obnova stavů) zrovna smazal řádky `issues`,
  `totals()` od `97059342` nespadne, ale hned potom `updater.foundsearch()` spadne na `issue['IssueDate']`
  nad `None` (`updater.py` kolem `:925`). Soubor je už v knihovně, zdroj uklizený, `nzblog` smazaný, stav
  `Downloaded` a `Location` se nezapíšou; obnova ze snapshotu navíc přepíše stav a `Location` na hodnotu před PP.
  V produkci 4× (viz review). Cíl: po PP souběžném s refreshem téže série je issue `Downloaded` s `Location`
  a PP nespadne.
- Konzervativní oprava (zvol a zdůvodni; když nejde, zapiš): `foundsearch` při chybějícím řádku issue nespadne,
  počká s omezeným počtem pokusů (podvržitelný `time.sleep`), než refresh řádek vrátí, a pak zapíše stav jako
  dnes; když se řádek nevrátí, zaloguje ERROR s IssueID a cestou souboru. A refresh nesmí výsledek PP přepsat:
  obnova stavů v `dbUpdate` nemá přepsat issue, které je mezitím `Downloaded` s `Location` (porovnej se stavem
  v DB těsně před obnovou, ne jen se snapshotem). Nezaváděj globální zámek mezi PP a refreshem bez testu, který
  ukáže, že neblokuje ostatní série.
- Testy (kap. 8, vzor `cv/repro_rename.py` F): řádek `issues` smazaný mezi přesunem a `foundsearch`, refresh ho
  vrátí → issue `Downloaded` s `Location`; řádek se nevrátí → žádná výjimka, ERROR v logu; obnova ze snapshotu po
  PP nepřepíše `Downloaded`. Žádné volání ComicVine (podvrhni `cv`).

## Na konci

1. Obě sady testů, `ast.parse` změněných souborů, import všech modulů v 3.8.2, kompilace změněných šablon.
2. Souhrn **`review/FOLLOWUPS-2026-11-22-part2.md`** ve worktree (česky, kód v originále, časy pražsky):
   - prostředí: worktree, větev a z čeho byla založená, image `mylar3:local` a jeho ID, že se kontejner
     nerestartoval a nic se nenasadilo,
   - výchozí a konečný stav testů (počty, příkazy),
   - tabulka ID | Stav (opraveno / neopraveno / nereprodukováno) | Commit | Nové testy (kolik padalo před opravou)
     | Poznámka (jak reprodukováno, co oprava dělá, dopad na stahování a PP jednotlivých čísel přes GC-Main),
   - otevřené otázky a konzervativní volby, které jsi udělal místo uživatele,
   - kontrola Comics a comics-nzb-hunteru: nic z oprav nemění API, schéma, formát ID, stavy ani pojmenování
     souborů (u R17 a R18 výslovně, u nových řádků v `failed` jejich tvar),
   - postup nasazení pro uživatele: seznam změněných souborů pro `docker cp` jmenovitě (podle `CLAUDE.md`), že se
     nasazuje až po první části (nebo spolu s ní), co ověřit v logu a v UI po restartu (hlášky nových větví,
     picker, výběr odmítnuté shody, přímé DDL); rebuild image (R14) a Q8 jsou samostatný krok uživatele,
   - prázdná sekce „Stav po merge“.
3. Commitni souhrn ve worktree. Nepushuj, nemerguj, worktree nech být.
4. Poslední zprávou napiš, ve kterých repech a na které větvi jsi commitnul, a stav testů.
