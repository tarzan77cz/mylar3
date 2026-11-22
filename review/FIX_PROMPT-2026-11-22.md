# Zadání: opravy nálezů z review Mylaru 2026-11-22, první část

## Kontext

**Mylar** (fork mylar3, `tarzan77cz/mylar3`) je automatický stahovač komiksů. Běží ostře nad knihovnou asi
11 300 sérií a denně stahuje jednotlivá nová čísla z GetComics (DDL), packů je pár za měsíc. Hlavní riziko je
ztráta nebo poškození souborů v knihovně a tiché selhání stahování. **Stahování jednotlivých čísel přes GC-Main
(Download Now) funguje a nesmí se změnit.** Opravy se ho dotknou jen tam, kde to nález výslovně žádá.

- **Pravidla repa:** `CLAUDE.md` (Python 3.8, `sqlite3.Row` nemá `.get()`, živé služby, secrets, styl
  commitů, sekce Review). Přečti ho jako první.
- **Nálezy s doklady a scénáři:** `review/REVIEW-2026-11-22.md`. U každého nálezu čti jeho řádek v tabulce
  (kap. 4), kontrolu oprav minulého review (kap. 6), navržené testy (kap. 8) a otázky (kap. 10). Tady je
  jen zkrácené zadání.
- **Rozhodnutí uživatele:** kap. 11 téže zprávy. Jsou závazná.
- **Minulé opravy:** `review/FOLLOWUPS-2026-11-21.md` (R1–R9, Q5: `pack_id`, `section_issues`,
  `release_exhausted_ddl_item`, `reverse_ddl_item_snatch`). Jejich chování neměň, pokud to nález nežádá.
- **Reprodukce z review** (hlavní strom, v `.gitignore`, do repa je nekopíruj, použij jako výchozí bod testů):
  - `/data/Tarzan/Cursor/Mylar/.scratch/review-2026-11-22/h/test_h_repro.py`: smyčka `ddl_downloader`
    s podvrženým `getcomics.GC` (R16, R42). Testy dnes popisují **chybné** chování, po opravě R16 se jejich
    očekávání otočí.
  - `.scratch/review-2026-11-22/ddl/`: `h.py` (harness s podvrženým `requests`), `r1` (výjimka zabije vlákno,
    R13), `r2`/`r2b` (useknutý Pixeldrain/MediaFire, R12), `r3` (Restart Queue, R15), `r4` (heal, R20, R21),
    `r5` (incomplete, R16), `r6` (mislabel, R22).
  - `.scratch/review-2026-11-22/import_graph.py`, `who_imports.py`, `try_imports.py`, `asset_refs.py`,
    `dockerignore_sim.py`: inventura (R47, R48).
- **Navazující repa:** `/data/Tarzan/Cursor/Comics` a `/data/Tarzan/Cursor/scripts/apps/comics-nzb-hunter`
  volají Mylar API a čtou `mylar.db` (`ddl_info`, `issues`, `failed`). Neměň schéma `ddl_info` (žádné nové
  sloupce), formát ID v `ddl_info` (`<id>`, `<id>-N`, `manual-…`), názvy stavů ani odpovědi API.

## Režim práce: bez dozoru, všechno v jedné session

Uživatel u toho není. **Na nic se neptej a nezastavuj se mezi nálezy**, nikdo neodpoví. Projdi všechny nálezy
a na konci napiš a commitni souhrn. Když něco nejde nebo si nejsi jistý, zvol konzervativnější variantu,
zapiš ji do souhrnu jako otevřenou otázku a pokračuj dalším nálezem.

## Pravidla

1. **Izolace.** Založ worktree z aktuálního `python3-dev`:
   `git -C /data/Tarzan/Cursor/Mylar worktree add -b claude/review-2026-11-22 /data/Tarzan/Cursor/Mylar-review-2026-11-22 python3-dev`.
   Pracuj jen tam. Hlavní strom nepřepínej ani neměň (ani netrackované soubory). Nepushuj, nemerguj,
   nepřepisuj historii.
2. **Review soubory** (`review/REVIEW_PROMPT-2026-11-22.md`, `review/REVIEW-2026-11-22.md`, tohle zadání)
   neměň, výsledky patří do `FOLLOWUPS`. Když ve worktree chybí (nebyly commitnuté), čti je z hlavního stromu
   `/data/Tarzan/Cursor/Mylar/review/` a zapiš to do souhrnu.
3. **Na živou aplikaci nesahej:** žádný `docker cp`, `docker restart`, `docker exec` do kontejneru `mylar`,
   žádné volání Mylar API, žádné dotazy do `mylar.db`, nic v `/comics` a `/downloads`. Nečti
   `/config/mylar/config.ini`, `env` kontejneru ani `docker inspect mylar`. Žádná síť (GetComics, Pixeldrain,
   MediaFire, ComicVine). Číst `docker logs mylar` smíš (časy v něm jsou UTC, do souhrnu je převeď na
   pražský čas). Image `mylar3:local` nepřestavuj a nepřetaguj.
4. **Opravuj jen nálezy z tohoto zadání:** R47, R48, R49, R50, R51, R12, R22, R21, R16, R13, R15, R20.
   Ostatní nálezy z review (R10, R11, R17–R19, R23–R46) nech být, i když na ně narazíš; jen je případně
   zmiň v souhrnu. Žádné refaktoringy ani vylepšení navíc. `lib/` neměň, kromě odstranění souborů v R48.
5. **Test dřív než oprava.** Každý test musí před opravou selhat a po ní projít. Když neselže, nález se
   nereprodukuje: neopravuj ho a napiš proč. Úklid bez změny chování (R47–R51) dostane charakterizační
   ověření, které projde před i po změně (import všech modulů v 3.8, `ast.parse`, kontrola obsahu build
   kontextu), a v souhrnu ho tak označ.
6. **Commit na nález** (nebo úzce související skupinu), anglicky, jedna věta v rozkazovacím způsobu, co a proč,
   ID na konci, např. „Check the HTTP status and size of Pixeldrain and MediaFire downloads, so a cut-off
   file no longer goes to post-processing as complete (R12)“. Commit jen v repu Mylar.
7. **Python 3.8.** Nic z 3.9+ (`match`, `X | Y`, `list[str]` mimo řetězce, `removeprefix`, `dict | dict`,
   `zoneinfo`). Na `sqlite3.Row` nikdy `.get()` (řádky z `ddl_info` v auto-loadu jsou `sqlite3.Row`).
8. **Nic nemaž natrvalo.** Soubor, který odstraňuješ z repa (R48), nejdřív zkopíruj do
   `/data/Tarzan/Cursor/_archive/2026-11-22-mylar-cleanup/` se zachovanou relativní cestou, pak `git rm`.

## Testy a prostředí

Worktree leží na Z2 pod `/share/Tarzan/Cursor/Mylar-review-2026-11-22`, Docker socket patří Z2:

```sh
docker run --rm -e PYTHONDONTWRITEBYTECODE=1 -v /share/Tarzan/Cursor/Mylar-review-2026-11-22:/src:ro mylar3:local \
  sh -c "pip install -q pytest >/dev/null 2>&1; cd /src && python3 -m pytest -q -p no:cacheprovider tests"
docker run --rm -e PYTHONDONTWRITEBYTECODE=1 -v /share/Tarzan/Cursor/Mylar-review-2026-11-22:/src:ro mylar3:local \
  sh -c "pip install -q pytest >/dev/null 2>&1; cd /src && python3 -m pytest -q -p no:cacheprovider tests_db"
```

- **Výchozí stav nejdřív:** na čistém worktree `tests` 88 passed, `tests_db` 24 passed. Zapiš do souhrnu.
- Nové testy s DB, downloadery a smyčkou `ddl_downloader` patří do `tests_db/` (skutečný balík `mylar`,
  dočasná SQLite, vzor `tests_db/conftest.py` a `tests_db/test_single_exhausted.py`). Downloadery testuj
  s podvrženou `session.get` (status, hlavičky, `iter_content`), soubory v `tmp_path`, `mylar.CONFIG.DDL_LOCATION`
  do tempu. `time.sleep` podvrhni.
- Před každým commitem: obě sady testů a `ast.parse` změněných souborů v image (příkaz v `CLAUDE.md`).
- Na konci navíc import všech modulů `mylar.*` v 3.8.2 (`sys.path[:0] = ['/src', '/src/lib']`), vzor
  `.scratch/review-2026-11-22/try_imports.py`. Výsledek musí být stejný jako v review (74 ze 76 modulů,
  po R48 bez dvou odstraněných, tedy všechny zbylé).

## Nálezy a co přesně udělat

Pořadí: R47 → R48 → R49 → R50 → R51 → R12 → R22 → R21 → R13 → R16 → R15 → R20.

### R47 (nízká, úklid): `.dockerignore`

- Doplň: `.scratch/`, `tests/`, `tests_db/`, `review/`, `screens/`, `init-scripts/`, `utilities/`,
  `.github/`, `.cursor/`, `.cursorrules`, `API_REFERENCE`, `**/__pycache__`, `**/*.py[co]`, `**/*.md`,
  `**/*.log`. Řádek `[internal]` oprav na `\[internal\]` (dnes je to třída znaků).
- **Nevyřazuj:** `requirements.txt` a `ascii_logo.nfo` (start na nich závisí, `Mylar.py:59-66`, `:81-83`),
  `comictagger.py`, `post-processing/` (výchozí `AUTO_SNATCH_SCRIPT`, `config.py:1664`), `data/`, `lib/`.
- **Ověření** (charakterizace): postav jen build kontext do dočasného image a vypiš ho, `mylar3:local`
  nepřestavuj:
  `printf 'FROM mylar3:local\nCOPY . /ctx\n' | docker build -q -t mylar-ctx-check:tmp -f - /data/Tarzan/Cursor/Mylar-review-2026-11-22`,
  pak `docker run --rm --network none mylar-ctx-check:tmp find /ctx -maxdepth 2` a `docker rmi mylar-ctx-check:tmp`.
  V kontextu nesmí být nic z vyřazeného seznamu a musí v něm být `Mylar.py`, `requirements.txt`,
  `ascii_logo.nfo`, `comictagger.py`, `mylar/`, `lib/`, `data/`, `post-processing/`. Výpis před a po dej do
  souhrnu (stačí seznam položek nejvyšší úrovně a počty).

### R48 (úklid): nepoužívané soubory bez konfliktu s upstreamem

- Odstraň (archivace podle pravidla 8): `mylar/solicit.py`, `mylar/torrent/clients/utorrent.py`,
  `lib/utorrent/`, `mylar/dbupdater.py`, `mylar/latest.py`, `mylar/wwt.py`, `lib/configobj.py`,
  `lib/deluge_client/tests.py`, šablony `data/interfaces/default/torrentinfo.html`, `futurepull.html`,
  `importlog.html`, `data/js/libs/jquery-1.11.1.min.js`, `data/js/libs/modernizr-1.7.min.js`,
  `data/interfaces/carbon/js/materialize.min.js` (duplikát `data/js/materialize.min.js`), `unicode_check.py`.
- Nepoužité JS a CSS ze seznamu review (`jquery.dataTables.rowReordering.js`, `jquery.jeditable.mini.js`,
  fancybox `*.pack.js`, `data_tables.dist.css`, `bootstrap-theme.css`, `style.less`) odstraň jen po vlastním
  ověření, že na soubor nic neodkazuje ani podle kmene jména (`asset_refs.py`, grep v `.py`, `.html`, `.js`,
  `.css`, `.less`). **Obrázky neodstraňuj** (jména se skládají dynamicky, např. ikony poskytovatelů a loga).
- Před každým odstraněním ověř, že ho upstream od `b609c28c` neměnil:
  `git diff --stat b609c28c..origin/python3-dev -- <cesta>` musí být prázdné. Když není, soubor nech a zapiš.
- Grep po odstranění: žádný import ani `templatename=`, `<%include`, `<%inherit`, `src=`/`href=` na odstraněné
  soubory. Odkazy v `CLAUDE.md` na `unicode_check.py` uprav v rámci R51.
- Netrackované artefakty buildu v kořeni hlavního stromu (`=`, `ERROR`, `[internal]`, `sha256:*`…) nech být
  (jsou mimo worktree), jen je zmiň v souhrnu pro uživatele.

### R49 (úklid): mrtvý kód forku

- Odstraň `search_filer._is_duplicate_rejected_match` (`search_filer.py:126`) a
  `_add_all_entries_to_rejected_matches` (`:830`) po ověření, že je nic nevolá (ani šablony a JS), druhý
  `import time` (`:20`/`:26`) a prázdný debug blok v `check_for_first_result` (`:2330-2336`).
- `getcomics.zip_zip` (`getcomics.py:2206`): `re.sub('.zip', …)` nahraď ořezáním přípony `.zip` na konci jména
  (bez regexu nebo s `re.escape` a `$`, bez ohledu na velikost písmen jako dnes). Test: jméno
  `Batman.zip.Collection.zip`/`Xzip.zip` dá správný základ.
- `filers.rename_file` (`filers.py:618-635`): `ext` je definované jen pro `.cbr`/`.cbz`/`.cb7`; pro jinou
  příponu použij `os.path.splitext`. Test: soubor `.pdf` se přejmenuje (dnes UnboundLocalError).
- Nesahej na `select_rejected_match` (duplicitní větve, R23 přijde v další části), `ddl_activity` v
  `loadupcoming`, fázi 2 watchdogu ani na argumenty `parsed_comic`/`filecomic`.

### R50 (konvence): české komentáře

- Přelož komentáře v `mylar/webserve.py:613-657` do angličtiny. Kód neměň. Grep diakritiky v `mylar/*.py`
  musí být po změně prázdný (kromě převzatých knihoven mimo `mylar/`).

### R51 (konvence): `CLAUDE.md`

Jediné povolené změny `CLAUDE.md`:
- „Struktura“: doplň `getcomics_parse.py` (čistý parser GetComics bez globálů, na něj míří `tests/`).
- „Vazba na repo Comics“: doplň druhého klienta API `/data/Tarzan/Cursor/scripts/apps/comics-nzb-hunter`
  (volá `getWanted`, `getComic`, `getIssueInfo`, `refreshComic`, `addComic`, `findComic`, `unqueueIssue`,
  `forceProcess`, `recheckFiles`).
- „Nasazení“: varování, že image `mylar3:local` může být pozadu za kódem nasazeným přes `docker cp`, a recreate
  kontejneru proto vyžaduje nejdřív rebuild z aktuální `python3-dev` (review R14).
- Odkazy na soubory odstraněné v R48 (např. `unicode_check.py`, pokud se zmiňuje).

### R12 (vysoká): Pixeldrain a MediaFire přijmou neúplný soubor

- Bez Range (`open_mode='wb'`) kontroluj status: jen 200 je úspěch, jiný status = selhání hosta
  (`{"success": False, …, "link_type_failure": 'GC-Pixel'/'GC-Media'}`), soubor neukládej. 206/200/416
  při resume nech, jak je.
- Po dokončení zápisu ověř velikost a obsah stejnou funkcí jako GC-Main: `helpers.validate_downloaded_archive`
  (už porovnává velikost s očekávanou, `helpers.py:6340-6454`; jak ji volá GC-Main, viz `getcomics.py:2105-2130`).
  Očekávaná velikost je `filesize` z API Pixeldrainu (`info['size']`), u MediaFiru `Content-Length` nebo
  `remote_filesize`, když je známá. Výsledek mapuj na stávající klíče, které `ddl_downloader` umí:
  krátký soubor → `incomplete` (resume), nečitelný archiv při známé velikosti → `incomplete` +
  `discard_partial`. Nové klíče nezaváděj.
- Platí i pro pack zip před `zip_zip` (rozbalovat se smí jen ověřený zip).
- Testy (`tests_db/`, podvržená `session.get`, vzor `ddl/r2`): Pixeldrain 503 s JSON tělem → selhání,
  žádný soubor, `ddl_info` není `Completed`, nic v `PP_QUEUE`; Pixeldrain useknutý (1 MB ze 3 MB) →
  `incomplete`; MediaFire useknutý → `incomplete`; úplný platný ZIP → úspěch jako dnes. GC-Main se nemění
  (stávající testy).

### R22 (střední): typ archivu podle přípony

- `helpers.validate_downloaded_archive` (`helpers.py:6393-6418`): typ urči nejdřív podle magic bytes
  (`magic_numbers`, jako `check_file_condition`), příponu ber jen když hlavička nic nepozná. Ostatní chování
  (výsledek `ok`/`short`/`discard`) beze změny.
- Testy: zdravý úplný ZIP pojmenovaný `.cbr` při známé velikosti → `ok`, soubor zůstane (vzor `ddl/r6`);
  úplný ZIP `.cbz` → `ok`; useknutý ZIP při známé velikosti → `discard` jako dnes; neznámý obsah → `unknown
  archive type` jako dnes.

### R21 (střední): Pixeldrain `filename` × `tmp_filename`

- `queue_ddl_postprocess`, `heal_completed_but_snatched`, `release_unfinished_single_ddl` a watchdog
  (`helpers.py:3423-3700`) hledají soubor jen podle `ddl_info.filename`. Hledej nejdřív `tmp_filename`, pak
  `filename` (stejně jako auto-load na `helpers.py:4623-4626`, s `try/except KeyError`, žádné `.get()` na
  řádku).
- Pixeldrain do DB nezapisuj jinak (formát se nemění), oprava je jen ve čtení.
- Testy (vzor `ddl/r4` E): řádek `filename='X.cbz'`, `tmp_filename='X[__I5__].cbz'`, soubor `X[__I5__].cbz`
  v `DDL_LOCATION` → `queue_ddl_postprocess` zařadí PP, heal ho najde, release nehlásí „file is gone“.

### R13 (vysoká): výjimka ukončí vlákno `ddl_downloader`

- Volání downloaderu v `ddl_downloader` (`helpers.py:4234-4267`) obal `try/except Exception`: výjimka se
  zaloguje s tracebackem a pokračuje se jako selhání hosta (`ddzstat = {'success': False, 'link_type':
  item['link_type'], …}`), tedy stávající cestou dalšího hosta nebo `release_exhausted_ddl_item`.
- Celé tělo jedné iterace (po `queue.get`) obal pojistkou `try/except Exception`: zaloguje traceback, položku
  dá v `ddl_info` na `Failed`, uvolní `DDL_LOCK`, odebere ID z `DDL_QUEUED` a smyčka pokračuje. Čísla neměň
  (to je nečekaná chyba, ne vyčerpaní hosté), zapiš to jako konzervativní volbu.
- `getcomics.GC.downloadit` (`getcomics.py:1747` a `:1759`): nastavení `DDL_LOCK=True` a `cookie_receipt()` přesuň
  dovnitř `try/finally`, které zámek uvolní.
- Stejnou pojistku dej kolem těla `search_queue` (`helpers.py:4783-4849`): výjimka z jedné položky nesmí
  ukončit vlákno, `SEARCHLOCK` neměň.
- Watchdog (`helpers.ddl_watchdog`, `helpers.py:3611`): když `mylar.DDLPOOL` existuje a `is_alive()` je
  `False` a aplikace se nevypíná, zaloguj ERROR a spusť vlákno znovu přes
  `mylar.queue_schedule('ddl_queue', 'start')` (`__init__.py:730-818`; vnitřní `start` vlákno nespustí, když
  staré žije). Nespouštěj druhé vlákno, když staré žije.
- Testy (vzor `ddl/r1`): Pixeldrain `session.get` vyhodí `ConnectionError` u první položky, za ní je druhá
  položka → smyčka zpracuje obě, první skončí cestou selhání hosta, `DDL_LOCK` je `False`. `cookie_receipt`
  vyhodí výjimku → `DDL_LOCK` je `False`. Watchdog s mrtvým `DDLPOOL` → nové vlákno (podvrhni start vlákna).

### R16 (střední): položka bez kontextu po `incomplete` a restartu (rozhodnutí Q11)

Cíl: neúplné stažení nesmí ztratit kontext a žádná položka nesmí po selhání nechat čísla `Snatched` bez
stahování.

- **Incomplete větev** (`helpers.py:4359-4397`): kromě `ddl_info.status='Queued'` vrať položku i do fronty
  v paměti (`queue.put`) se všemi klíči (`comicinfo`, `packinfo`, `pack_id`, `section_issues`,
  `section_annual`, `section_key`, `section`) a s `resume` podle velikosti částečného souboru (když se
  nezahodil). Výpočet resume a jména souboru sdílej s auto-loadem (`helpers.py:4617-4634`), ne kopií.
  Čítač `incomplete_attempts` a stávající prodleva zůstanou. Ověř, že auto-load stejnou položku nezařadí
  podruhé (běží jen při prázdné frontě a bere jen `status='Queued'`; položka ve frontě ani stahovaná ho
  nesplní), a v testu to pokryj.
- **Klíč `pack`:** kontroly `item.get('pack')` ve větvích „chybí `comicinfo`/`packinfo`“ (`:4470`),
  „neplatný `mainlink`“ (`:4485`) a „výjimka z `parse_downloadresults`“ (`:4520`) nikdy neplatí (klíč žádná
  položka fronty nemá). Nahraď je jednou funkcí, která pozná pack podle `packinfo['pack']`,
  `comicinfo[0]['pack']`, nebo podle `pack` z `ddl_info` (auto-load ho do položky doplní z řádku).
- **Položka bez kontextu** (obnovená z `ddl_info`, ve větvi „chybí `comicinfo`/`packinfo`“) při selhání:
  - jednotlivé číslo (ne pack, ne `manual-…`, má `issueid`) → stejně jako Q5: `release_exhausted_ddl_item`
    (`Wanted` + řádek ve `failed` s ID příspěvku; `Issue_Number` doplň z `issues`/`annuals`, když
    `comicinfo` chybí);
  - pack → vrať na `Wanted` čísla, která jsou pro ID příspěvku `Snatched` v `nzblog`
    (`get_pack_snatched_issueids`). U sub-packu `<id>-N` vracej jen čísla jeho sekce: čísla z hlavičky
    v `ddl_info.series` (`getcomics_parse.section_issue_numbers`) proti issue ID z `nzblog` pod základním ID
    příspěvku. Když čísla sekce nejdou zjistit, nic nevracej a zaloguj varování (stejně jako nezařazená sekce
    bez čísel v R4). Do `failed` nic nezapisuj (jako dnešní pack větev);
  - `manual-…` beze změny.
  Další hosty se u položky bez kontextu nezkoušejí (není z čeho, rozhodnutí Q11).
- Větve „neplatný `mainlink`“ a „výjimka z `parse_downloadresults`“ (položky s kontextem): pack vrací svou
  sekci přes `reverse_ddl_item_snatch` (oprava klíče `pack` výše). Jednotlivé číslo v nich dnes zůstává
  `Snatched` (otevřená otázka 7 z FOLLOWUPS-2026-11-21); použij i tam `release_exhausted_ddl_item` a zapiš to
  do souhrnu jako rozšíření Q5.
- Testy (`tests_db/`, vzor `.scratch/review-2026-11-22/h/test_h_repro.py` a `ddl/r5`):
  - položka s kontextem → `incomplete` → je znovu ve frontě s `comicinfo` a `resume`; další pokus 403 →
    zavolá se `parse_downloadresults` (další host), po vyčerpání `Wanted` + `failed`;
  - obnovené jednotlivé číslo (bez kontextu) selže → `Wanted` + řádek ve `failed`, `ddl_info` `Failed`;
  - obnovený pack `1` (`ddl_info.pack=1`, `nzblog` ID `1`) selže → jeho čísla `Wanted`;
  - obnovený sub-pack `1-2` se `series='Tomahawk #71 – 140'` selže → jen #71–140 `Wanted`, #1–70 `Snatched`;
  - pack s kontextem, `parse_downloadresults` vyhodí výjimku → čísla sekce `Wanted`, mapa vyčištěná;
  - auto-load nezařadí položku, která je ve frontě v paměti.

### R15 (střední): Restart Queue během stahování

- `webserve.ddl_requeue('restart_queue')` (`webserve.py:4695-4792`): když staré vlákno DDL žije a právě
  stahuje (`DDL_LOCK` je `True` nebo existuje řádek `Downloading` s čerstvým `updated_date`), restart
  neprováděj a vrať JSON s chybou „download in progress, try again when it finishes“. Když vlákno nežije
  nebo nic nestahuje, chovej se jako dnes. Řádky `Downloading` nevracej do `Queued`, dokud staré vlákno žije.
- `queue_management.html:10`: k tlačítku Restart Queue přidej potvrzení (`confirm()`), jako má „Clear rejected
  matches“ v `upcoming.html:890`. Jiné šablony neměň.
- Test (vzor `ddl/r3`, skutečné `WebInterface.ddl_requeue`): běžící podvržené stahování → restart vrátí chybu,
  živé je jedno vlákno DDL-QUEUE, řádek zůstane `Downloading`. Mrtvé vlákno → restart proběhne jako dnes.

### R20 (střední): nekonečné opakování PP z healu

- `heal_completed_but_snatched` a `release_unfinished_single_ddl` (`helpers.py:3512-3608`): počítej, kolikrát
  heal poslal stejné ID z `ddl_info` do PP (v paměti, např. slovník v `mylar`). Po 3 odmítnutích PP už ID
  znovu neposílej, nastav `ddl_info` na `Failed` a čísla vrať: jednotlivé číslo přes
  `release_exhausted_ddl_item` (`Wanted` + `failed`, příští hledání vezme jiný release), pack jen zaloguj
  varováním a čísla nech (konzervativní volba, packy PP odmítá i kvůli rozpoznání čísel). Soubor ve
  `/downloads` nemaž.
- Test (vzor `ddl/r4` D): PP vrátí „matched 0 files“ 3× → čtvrtý běh healu už PP nezařadí, `ddl_info`
  `Failed`, číslo `Wanted`, řádek ve `failed`.

## Na konci

1. Obě sady testů, `ast.parse` změněných souborů, import všech modulů v 3.8.2, kontrola build kontextu (R47).
2. Souhrn **`review/FOLLOWUPS-2026-11-22.md`** ve worktree (česky, kód v originále, časy pražsky):
   - prostředí: worktree, větev, image `mylar3:local` a jeho ID, že se kontejner nerestartoval a nic se
     nenasadilo,
   - výchozí a konečný stav testů (počty, příkazy),
   - tabulka ID | Stav (opraveno / neopraveno / nereprodukováno) | Commit | Nové testy | Poznámka (jak
     reprodukováno, co oprava dělá, dopad na stahování jednotlivých čísel přes GC-Main),
   - seznam odstraněných souborů a cesta k archivu (R48), výpis build kontextu před a po (R47),
   - otevřené otázky a konzervativní volby, které jsi udělal místo uživatele,
   - kontrola Comics a comics-nzb-hunteru: nic z oprav nemění API, schéma `ddl_info`, formát ID ani stavy
     (u nových řádků ve `failed` uveď jejich tvar),
   - postup nasazení pro uživatele: seznam změněných souborů pro `docker cp` jmenovitě (podle `CLAUDE.md`),
     že odstraněné soubory v kontejneru zůstanou (neškodí) a zmizí až po rebuildu, co ověřit v logu po
     restartu (hlášky nových větví); rebuild image (R14) a připnutí závislostí (Q8) jsou samostatný krok
     uživatele,
   - prázdná sekce „Stav po merge“.
3. Commitni souhrn ve worktree. Nepushuj, nemerguj, worktree nech být.
4. Poslední zprávou napiš, ve kterých repech a na které větvi jsi commitnul, a stav testů.
