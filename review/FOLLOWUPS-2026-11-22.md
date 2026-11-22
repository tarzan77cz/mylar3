# Opravy nálezů z review 2026-11-22, první část

Opravy nálezů R47, R48, R49, R50, R51, R12, R22, R21, R13, R16, R15 a R20 z
[REVIEW-2026-11-22.md](REVIEW-2026-11-22.md) podle [FIX_PROMPT-2026-11-22.md](FIX_PROMPT-2026-11-22.md)
a rozhodnutí uživatele v kap. 11 zprávy (Q11, Q12, Q13). Session běžela bez dozoru 22. 11. 2026
asi 14:19–15:10 SEČ (commity 14:23–14:54 SEČ, 13:23–13:54 UTC).

## 1. Prostředí

- **Worktree:** `/data/Tarzan/Cursor/Mylar-review-2026-11-22` (na Z2 `/share/Tarzan/Cursor/Mylar-review-2026-11-22`),
  větev `claude/review-2026-11-22` z `python3-dev` (`142c9003`). Hlavní strom se nepřepínal ani neměnil
  (ani netrackované soubory). Review soubory byly ve worktree commitnuté, četly se odtud a nezměnily se.
- **Image:** `mylar3:local`, `sha256:b7cfffeb59ee1b6d6c3bb459ba492bd146075392a2d6e7df8535c8a3b7c93167`
  (vytvořen 11. 9. 2026 17:21 SELČ), Python 3.8.2. Testy, import a kontrola build kontextu běžely
  v jednorázových kontejnerech, worktree jen pro čtení. Image se nepřestavoval ani nepřetagoval
  (kontrola build kontextu stavěla jen dočasný `mylar-ctx-check:tmp` nad `mylar3:local` a hned ho smazala).
- **Živá aplikace:** kontejner `mylar` se nerestartoval, nic se nenasadilo (žádný `docker cp`,
  `docker exec`, `docker inspect`), žádné volání Mylar API, žádný dotaz do `mylar.db`, nic v `/comics`
  a `/downloads`, `config.ini` ani `env` se nečetly, žádná síť. `docker logs mylar` se nečetl (nebylo
  potřeba). Nic se nepushovalo ani nemergovalo.
- **Reprodukce:** `.scratch/` z hlavního stromu zkopírovaný do worktree (v `.gitignore`, mimo git).
  Vlastní pomocné skripty jsou v `.scratch/fix-2026-11-22/`: `run_tests.sh` (obě sady + `ast.parse`),
  `ctx_check.sh` (build kontext), `r48_files.txt` a výpisy kontextu.

## 2. Testy

| | `tests/` (stuby, parser) | `tests_db/` (skutečný balík `mylar`, dočasná SQLite) |
|---|---|---|
| Výchozí stav (čistý worktree) | **88 passed** | **24 passed** |
| Konečný stav | **88 passed** | **85 passed** (61 nových) |

```sh
docker run --rm -e PYTHONDONTWRITEBYTECODE=1 -v /share/Tarzan/Cursor/Mylar-review-2026-11-22:/src:ro mylar3:local \
  sh -c "pip install -q pytest >/dev/null 2>&1; cd /src && python3 -m pytest -q -p no:cacheprovider tests"
docker run --rm -e PYTHONDONTWRITEBYTECODE=1 -v /share/Tarzan/Cursor/Mylar-review-2026-11-22:/src:ro mylar3:local \
  sh -c "pip install -q pytest >/dev/null 2>&1; cd /src && python3 -m pytest -q -p no:cacheprovider tests_db"
```

- Před každým commitem obě sady a `ast.parse` změněných souborů v image. Na konci `ast.parse` všech 15
  změněných `.py` souborů: v pořádku.
- **Import všech modulů `mylar.*` v 3.8.2** (`.scratch/review-2026-11-22/try_imports.py`): na
  `python3-dev` 74 ze 76 (`mylar.solicit` ImportError, `mylar.torrent.clients.utorrent` SyntaxError), po
  opravách **71 ze 71** (5 modulů odstraněno v R48). Z `lib/` padá jen `lib.certgen` (chybí pyOpenSSL,
  stejně jako předtím); `lib.utorrent.client` a `lib.deluge_client.tests` jsou odstraněné.
- Nové testy s DB, downloadery a smyčkou jsou v `tests_db/`. Downloadery se testují s podvrženou
  `requests.Session.get` ([fakes.py](../tests_db/fakes.py): status, hlavičky, useknuté `iter_content`),
  soubory v `tmp_path`, `time.sleep` podvržený.
- **Test dřív než oprava:** každý nový test jsem pustil před opravou. U R16 jsem to ověřil i dodatečně
  odložením změn v `mylar/` (`git stash`). V tabulce je, kolik testů před opravou padalo. Testy, které
  procházely i předtím, jsou kontrolní: hlídají, že se stávající chování (úspěch, GC-Main, „jako dřív“)
  nezměnilo.
- Reprodukce z review `.scratch/review-2026-11-22/h/test_h_repro.py` po opravách: 4 z 5 se podle
  očekávání otočily (popisovaly chybné chování R16), `test_tpb_extra_item_exhausted_marks_issue_wanted`
  dál prochází (R42, mimo tuto část).

## 3. Nálezy

| ID | Stav | Commit | Nové testy | Poznámka |
|---|---|---|---|---|
| R47 | opraveno (charakterizace) | `bec667ce` | kontrola build kontextu (`ctx_check.sh`) | `.dockerignore` doplněn o `.scratch/`, `tests/`, `tests_db/`, `review/`, `screens/`, `init-scripts/`, `utilities/`, `.github/`, `.cursor/`, `.cursorrules`, `API_REFERENCE`, `**/__pycache__`, `**/*.py[co]`, `**/*.md`, `**/*.log`; `[internal]` → `\[internal\]`. Ponecháno `requirements.txt`, `ascii_logo.nfo`, `comictagger.py`, `post-processing/`, `data/`, `lib/`. Ověřeno dočasným image: viz kap. 5. Pro realistické „před“ jsem do worktree dočasně dal `mylar/__pycache__/probe.cpython-311.pyc`, `[internal]` a `logs/probe.log` (po kontrole smazané): před změnou byly v kontextu, po ní ne. |
| R48 | opraveno (charakterizace) | `b8a2e646` | import všech modulů v 3.8.2, grep odkazů | 29 souborů odstraněno (seznam a archiv v kap. 4). U každého `git diff --stat b609c28c..origin/python3-dev` prázdné (upstream v `data/` měnil jen `config.html` a `index.html`). Volitelná statika ověřená vlastním `asset_refs.py` (nad worktree) a grepem jmen v `.py/.html/.js/.css/.less`: odkazuje jen sama na sebe. `jquery.jeditable.mini.js` je nepoužitý, šablony načítají `jquery.jeditable.js`; fancybox `*.pack.js` nepoužité, `script.js` načítá `jquery.fancybox-1.3.4.js`; `carbon/js/materialize.min.js` má stejné md5 jako `data/js/materialize.min.js`, `header.html` načítá `js/materialize.min.js`. Obrázky a `carbon/README.txt` ponechány. Grep po odstranění: žádný import, `templatename=`, `<%include`, `<%inherit`, `src=`/`href=` na odstraněné soubory. `mylar/utorrent.py` (jiný modul, importuje ho `rsscheck.py`) zůstává. `CLAUDE.md` `unicode_check.py` nezmiňoval. Obě sady testů beze změny. |
| R49 | opraveno | `d85842c0` | `tests_db/test_cleanup_fixes.py` (9, před opravou 6 padalo) | Odstraněny `search_filer._is_duplicate_rejected_match`, `_add_all_entries_to_rejected_matches` (nic je nevolá, ani šablony a JS), druhý `import time` a debug blok `alt_match` v `check_for_first_result`. `getcomics.zip_zip`: `re.sub(r'\.zip$', '', filename, flags=re.IGNORECASE)`. **Reprodukce:** `Xzip.zip` → složka `''` = rozbalení přímo do `DDL_LOCATION`, `Batman.zip.Collection.zip` → `Batman.Collection`. `filers.rename_file`: `path, ext = os.path.splitext(ofilename)` vždy, bez `file_format` se u jiné přípony bere `path` (jinak by vzniklo `X.pdf.pdf`). **Reprodukce:** `.pdf`/`.epub` → `UnboundLocalError: ext`. `.cbz`/`.cbr` beze změny (kontrolní testy). `select_rejected_match`, `ddl_activity`, fáze 2 watchdogu a `parsed_comic`/`filecomic` nedotčené. |
| R50 | opraveno (charakterizace) | `504842cd` | grep diakritiky, `ast.parse` | 7 komentářů v `webserve.py` (`comicDetails`, stahování obálky) přeloženo, kód beze změny. Grep diakritiky v `mylar/**/*.py`: 0. |
| R51 | opraveno | `6aca42aa` | — | `CLAUDE.md`: `getcomics_parse.py` ve „Struktuře“, druhý klient API `comics-nzb-hunter` s jeho voláními ve „Vazbě na repo Comics“, varování v „Nasazení“, že image může být za kódem z `docker cp` a recreate vyžaduje nejdřív rebuild z aktuální `python3-dev` (R14). Nic jiného se v `CLAUDE.md` neměnilo. |
| R12 | opraveno | `8d14ed4b` | `tests_db/test_ddl_hosts.py` (7, před opravou 5 padalo) | **Reprodukce** (skutečná smyčka, `POST_PROCESSING` zapnuté, `CHECK_CBR_INTEGRITY` vypnuté jako v produkci): Pixeldrain 503 s JSON → `Completed` a soubor 39 B jde do PP; Pixeldrain a MediaFire useknuté na 1 MB ze 3 MB → `Completed`; useknutý pack zip → pokus o rozbalení, `Failed`. **Oprava:** bez Range (`open_mode == 'wb'`) jen status 200, jinak selhání hosta (`link_type_failure` `GC-Pixel`/`GC-Media`), soubor se neotevře. 206/200/416 při resume beze změny. Po zápisu nová `helpers.ddl_host_download_check` volá stejnou `validate_downloaded_archive` jako GC-Main. Očekávaná velikost: Pixeldrain `info['size']`, MediaFire `Content-Length`, nově s fallbackem na `remote_filesize`, když hlavička chybí. Výsledek jde na stávající klíče: krátký soubor `incomplete` (soubor zůstane pro resume), nečitelný při známé velikosti `incomplete` + `discard_partial` (soubor smazán hned v downloaderu jako u GC-Main, `path: None`). Kontrola proběhne před `zip_zip`, rozbaluje se jen ověřený zip. **Dopad na GC-Main:** žádný v downloaderu (stávající testy). |
| R22 | opraveno | `cbcc8c3d` | `tests_db/test_validate_archive.py` (8, před opravou 3 padaly) | **Reprodukce:** úplný ZIP `.cbr` a `.rar` při známé velikosti → `rar open failed: Not a RAR file`, `discard=True`; přes `ddl_host_download_check` by se soubor smazal. **Oprava:** `validate_downloaded_archive` čte hlavičku vždy a určí typ podle `magic_numbers`, příponu bere jen když hlavička nic nepozná (chybová stránka `.cbz` dál padá jako ZIP). `ok`/`short`/`discard` beze změny: useknutý ZIP při stejné velikosti `discard`, krátký `short`, neznámý obsah `unknown archive type`. **Dopad na GC-Main:** funkce je společná, GC-Main, watchdog a heal teď úplný ZIP pojmenovaný `.cbr` přijmou, místo aby ho smazaly. Jinak beze změny. |
| R21 | opraveno | `14faddba` | `tests_db/test_ddl_heal.py` (4 testy R21, před opravou všechny padaly) | **Reprodukce** (vzor `ddl/r4` E): `filename='X.cbz'`, `tmp_filename='X[__I5__].cbz'`, soubor `X[__I5__].cbz` → `queue_ddl_postprocess` `False`, heal nic nezařadil, release nic nezměnil („file is gone“), krátký soubor se nevrátil do fronty. **Oprava:** nová `helpers.ddl_row_file(row)` hledá nejdřív `tmp_filename`, pak `filename` (bere první, který v `DDL_LOCATION` existuje; `try/except` pro chybějící sloupec, žádné `.get()` na řádku). Používají ji `queue_ddl_postprocess` (a tím watchdog fáze 1), `heal_completed_but_snatched` a `release_unfinished_single_ddl` (dotazy načítají i `tmp_filename`). Zápis Pixeldrainu do DB beze změny. |
| R13 | opraveno | `d2151c87` | `tests_db/test_queue_threads.py` (13, před opravou všechny padaly) | **Reprodukce** (vzor `ddl/r1`): `ConnectionError` z Pixeldrainu a z `cookie_receipt()` propadly z `ddl_downloader` ven (vlákno by skončilo), `DDL_LOCK` zůstal `True`; výjimka ze `searchforissue` ukončila `search_queue`; watchdog mrtvé vlákno nepoznal. **Oprava:** volání downloaderu je v `try/except Exception`: traceback do logu, `DDL_LOCK=False`, pokračuje jako selhání hosta (`{'success': False, 'link_type': …}`), tedy další host nebo `release_exhausted_ddl_item`. Pojistka celé iterace: `ddl_downloader` je teď supervisor kolem původní smyčky (přejmenované na `_ddl_downloader_loop`, sdílený stav `link_type_failure`, `incomplete_attempts` a právě zpracovávaná položka). Po nečekané výjimce zaloguje traceback, položku dá na `Failed`, uvolní `DDL_LOCK`, odebere ID z `DDL_QUEUED` a smyčku spustí znovu. Čísla nemění. Stejný supervisor má `search_queue` (`_search_queue_loop`), `SEARCHLOCK` beze změny. `GC.downloadit` bere `DDL_LOCK=True` a volá `cookie_receipt()` uvnitř `try/finally`. Nová `helpers.ddl_thread_check()` volaná na začátku každého kola watchdogu: když `DDLPOOL` existuje a nežije, `_INITIALIZED` je `True`, `SIGNAL` je `None` a `ENABLE_DDL` zapnuté, zaloguje ERROR a zavolá `mylar.queue_schedule('ddl_queue', 'start')`. Živé vlákno, `DDLPOOL=None`, vypínání a restart nechá být. **Dopad na GC-Main:** úspěšné stahování beze změny, zámek se dřív uvolňoval stejným `finally`. |
| R16 | opraveno | `a1e45d32` | `tests_db/test_restored_items.py` (12, před opravou 10 padalo) | **Reprodukce** (vzor `h/test_h_repro.py`, `ddl/r5`): po `incomplete` položka z fronty zmizela, další pokus z auto-loadu bez kontextu skončil `Failed` bez dalšího hosta a číslo zůstalo `Snatched`. Obnovené číslo, pack i sub-pack zůstaly `Snatched`. Pack s kontextem po výjimce z `parse_downloadresults` zůstal `Snatched` i v `PACK_ISSUEIDS_DONT_QUEUE`. **Oprava:** (1) Větev `incomplete` po stávající prodlevě vrátí kopii položky do fronty v paměti se všemi klíči (`comicinfo`, `packinfo`, `pack_id`, `section*`…), `filename`/`tmp_filename`/`remote_filesize` z aktuálního řádku `ddl_info` a `resume` z nové `helpers.ddl_row_resume` (sdílí ji auto-load i startovní načítání, dřív dvě kopie). Čítač a prodleva beze změny. (2) Nová `ddl_item_is_pack` (packinfo, comicinfo, nebo `pack` z `ddl_info`). Auto-load, startovní načítání i `webserve.ddl_requeue` doplní do položky `pack` z řádku. `ddl_item_is_single_issue` ji používá. (3) Položka bez kontextu (`ddl_item_has_context`) při selhání: `release_restored_ddl_item`. Jednotlivé číslo jde přes Q5 (`release_exhausted_ddl_item`, `Issue_Number` z `issues`/`annuals`). Pack vrací čísla `Snatched` z `nzblog` pod ID příspěvku (`get_pack_snatched_issueids`), sub-pack `<id>-N` jen čísla z hlavičky v `ddl_info.series` (`section_issue_numbers`, annualy podle `section_is_annual`); bez čísel nic, jen varování. `manual-…` beze změny. Další hosté se nezkouší (Q11). (4) Větve „neplatný mainlink“ a „výjimka z `parse_downloadresults`“ volají `release_exhausted_ddl_item`: pack vrátí svou sekci, jednotlivé číslo jde přes Q5 (**rozšíření Q5**, uzavírá otevřenou otázku 7 z FOLLOWUPS-2026-11-21). Viz kap. 6, bod 3 k vyčerpaným `incomplete` pokusům. **Dopad na GC-Main jednotlivých čísel:** první stahování beze změny. Po `incomplete` pokračuje stejná položka s kontextem, takže po pozdějším selhání se zkusí další host. |
| R15 | opraveno | `1b9d2690` | `tests_db/test_restart_queue.py` (5, před opravou 3 padaly) | **Reprodukce** (vzor `ddl/r3`, skutečné `WebInterface.ddl_requeue('restart_queue')`): při běžícím stahování (`DDL_LOCK`, nebo Pixeldrain bez zámku s čerstvým `Downloading`) restart proběhl, `queue_schedule` se zavolal a řádek se vrátil do `Queued`. U vlákna, které po `exit` nedoběhlo, se staré vlákno osiřelo a spustilo se druhé. **Oprava:** nová `helpers.ddl_download_in_progress()` (`DDL_LOCK`, nebo řádek `Downloading` s `updated_date` do 10 min, nebo jeho soubor zapsaný do 2 min). Když vlákno žije a stahuje, restart vrátí `{'status': False, 'message': 'Download in progress, try again when it finishes.'}` a nic nemění. Když po `exit` a `join(5)` vlákno pořád žije, druhé se nespustí a vrátí se stejná chyba. Staré vlákno skončí na `exit` po rozdělané položce a watchdog (R13) ho do minuty nahodí. Mrtvé nebo nečinné vlákno: chování jako dřív (kontrolní testy). Tlačítko v [queue_management.html](../data/interfaces/default/queue_management.html) se ptá `confirm()` a volá `ajaxcallit('restart_queue')`, které zobrazí zprávu serveru. `doAjaxCall` by ukázal „Restarted Queue“ i při odmítnutí. Mako šablona se zkompiluje, v prohlížeči neověřeno. |
| R20 | opraveno | `2ce6a8eb` | `tests_db/test_ddl_heal.py` (3 testy R20, před opravou 2 padaly) | **Reprodukce** (vzor `ddl/r4` D): PP vrátí „matched 0 files“ → heal pošle soubor do PP znovu v každém kole, bez limitu (4/4). **Oprava:** `heal_completed_but_snatched` počítá v `mylar.DDL_HEAL_PP_COUNT` (v paměti), kolikrát poslal ID do PP. Po `DDL_MAX_HEAL_PP_ATTEMPTS = 3` odmítnutích ho při dalším kole už neposlal a zavolá `ddl_heal_give_up`: `ddl_info` `Failed`. Jednotlivé číslo jde přes `release_exhausted_ddl_item` (`Wanted` + `failed`). Pack se jen zaloguje varováním a čísla zůstanou. Soubor v `/downloads` se nemaže. Pod limitem beze změny (kontrolní test). |

**Mimo zadání, jen zmíněno:** R41 se ukázal v testu R13: `downloadit` přidá ID do `DDL_QUEUED` podruhé a úklid
odebere jednu kopii. Test to nekontroluje, neopraveno. R42 dál platí (reprodukce prochází). Ostatní nálezy
(R10, R11, R14, R17–R19, R23–R46) se neměnily.

## 4. Odstraněné soubory (R48)

Archiv před `git rm`: `/data/Tarzan/Cursor/_archive/2026-11-22-mylar-cleanup/` (29 souborů, cesty relativně
ke kořeni repa).

- Moduly: `mylar/solicit.py`, `mylar/torrent/clients/utorrent.py`, `lib/utorrent/` (`__init__.py`,
  `client.py`, `upload.py`), `mylar/dbupdater.py`, `mylar/latest.py`, `mylar/wwt.py`, `lib/configobj.py`,
  `lib/deluge_client/tests.py`, `unicode_check.py`.
- Šablony: `data/interfaces/default/torrentinfo.html`, `futurepull.html`, `importlog.html`.
- JS: `data/js/libs/jquery-1.11.1.min.js`, `data/js/libs/modernizr-1.7.min.js`,
  `data/interfaces/carbon/js/materialize.min.js`, `data/js/libs/jquery.dataTables.rowReordering.js`,
  `data/js/libs/jquery.jeditable.mini.js`, `data/js/fancybox/jquery.easing-1.3.pack.js`,
  `jquery.fancybox-1.3.4.pack.js`, `jquery.mousewheel-3.0.4.pack.js`.
- CSS: `data/css/data_tables.dist.css`, `data/interfaces/{default,carbon}/css/data_tables.dist.css`,
  `data/interfaces/{default,carbon}/css/bootstrap-theme.css`, `data/interfaces/{default,carbon}/css/style.less`.

**Netrackované artefakty buildu v kořeni hlavního stromu** (`=`, `ERROR`, `[internal]`, `extracting`, `resolve`,
`transferring`, 8× `sha256:*`) zůstaly. Jsou mimo worktree a nesahal jsem na ně. Doporučuji je archivovat
ručně. V kontextu příštího buildu už nebudou (`.dockerignore`).

## 5. Build kontext (R47)

`printf 'FROM mylar3:local\nCOPY . /ctx\n' | docker build -q -t mylar-ctx-check:tmp -f - <worktree>`, výpis
`find /ctx`, `docker rmi mylar-ctx-check:tmp` (`.scratch/fix-2026-11-22/ctx_check.sh`, výpisy
`before.*.txt`, `after.*.txt`, `final.*.txt`).

| | Soubory | Nejvyšší úroveň |
|---|---|---|
| Před (worktree + `.scratch/` z hlavního stromu + sondy `__pycache__`, `[internal]`, `logs/*.log`) | 692 | `.gitattributes .github .scratch API_REFERENCE Mylar.py [internal] ascii_logo.nfo comictagger.py data init-scripts lib logs mylar post-processing requirements.txt review screens tests tests_db unicode_check.py utilities` |
| Po `.dockerignore` (před R48) | 487 | `.gitattributes Mylar.py ascii_logo.nfo comictagger.py data lib logs mylar post-processing requirements.txt unicode_check.py` (`logs/` jen prázdná složka sondy) |
| Konečný stav (po R48) | 458 | `.gitattributes Mylar.py ascii_logo.nfo comictagger.py data lib mylar post-processing requirements.txt` |

Před změnou: 164 souborů `.scratch/`, 2 `*.md` z `.github`, 7 z `review/`, `__pycache__` sonda, `*.log`. Po změně
0× `__pycache__`, 0× `*.md`, 0× `.scratch`. `Mylar.py`, `requirements.txt`, `ascii_logo.nfo`, `comictagger.py`,
`mylar/`, `lib/`, `data/`, `post-processing/` v kontextu jsou.

## 6. Otevřené otázky a konzervativní volby

1. **R13, supervisor místo `try` v těle smyčky.** Tělo `ddl_downloader` má přes 400 řádků. Místo přeodsazení
   jsem původní smyčku přejmenoval a obalil supervisorem, který po výjimce provede úklid položky a smyčku
   spustí znovu. Funkčně to odpovídá `try/except` kolem jedné iterace. Stav (`link_type_failure`,
   `incomplete_attempts`) se zachová, vynuluje se jen čítač logu. Po nečekané chybě je položka `Failed`
   a čísla zůstanou (zadání).
2. **R13, watchdog nestartuje vlákno při `DDLPOOL=None`** (nikdy nespuštěné). Spouští jen mrtvé existující vlákno.
3. **R16, vyčerpané `incomplete` pokusy.** Po 6 neúplných pokusech větev dřív jen nastavila `Failed` a čísla
   nechala `Snatched` (následek popsaný u R22). Podle cíle R16 („žádná položka nesmí po selhání nechat
   čísla `Snatched` bez stahování“) teď vrací čísla: s kontextem `release_exhausted_ddl_item` (jednotlivé
   číslo Q5, pack sekce), bez kontextu `release_restored_ddl_item`. Výslovně to v zadání nebylo. Když to
   nechceš, stačí v té větvi vrátit jen `Failed`.
4. **R16, ID ve `DDL_QUEUED` po `incomplete`.** Vrácená položka zůstane v `DDL_QUEUED` jako položka z auto-loadu
   (dřív se ID odebralo). Díky tomu `pack_queued_for_download` blokuje opakované hledání packu i během
   prodlevy a requeue z UI ji přeskočí jako „already in queue“. Auto-load běží jen nad prázdnou frontou
   a bere jen `status='Queued'`, takže položku ve frontě ani právě stahovanou podruhé nezařadí (test).
5. **R16, obnovený sub-pack** se pozná podle ID `^\d+-\d+$`. ID typu `<id>-N-M` (opakované TPB extras, R42) se
   bere jako celý příspěvek; pod takovým ID v `nzblog` nic není, takže se nic nevrátí.
6. **R16, úklid `PACK_ISSUEIDS_DONT_QUEUE` po úspěchu obnoveného sub-packu** (zmíněný v popisu R16) jsem neměnil.
   Po restartu je mapa prázdná a `pack_queued_for_download` stejně kontroluje i `DDL_QUEUED`. Zbylé záznamy
   po Restart Queue bez restartu tedy hledání neblokují.
7. **R16, kontext po restartu kontejneru** se dál ztrácí (Q11 varianta a, schéma `ddl_info` beze změny).
   Obnovená položka při selhání nezkusí jiný host.
8. **R15, kritérium „stahuje“** je navíc i soubor zapsaný v posledních 2 minutách (Pixeldrain a MediaFire
   nedrží `DDL_LOCK` a dlouhé stahování nemá čerstvé `updated_date`). Při nejistotě restart raději odmítne.
   Zpráva o odmítnutí se v UI ukáže zeleně (styl `ajaxcallit`), text ale říká „Download in progress“.
9. **R20, počítadlo je v paměti.** Po restartu začíná od nuly (nejvýš 3 další pokusy). Vzdává se při
   4. průchodu healu (po 3 odmítnutích), ne hned při 3. odmítnutí v `release_unfinished_single_ddl`.
   Pack se jen zaloguje (zadání).
10. **R21, `tmp_filename` vyhrává jen když jeho soubor existuje.** Když po přepnutí hostů zůstane starý soubor
    pod `tmp_filename` (Pixeldrain) a GC-Main mezitím uloží `filename`, vezme se starý soubor. Okrajový případ:
    Pixeldrain je v pořadí až za GC-Main.
11. **R49, `zip_zip` ořezává `.zip` bez ohledu na velikost písmen.** Dřív se `.zip` mazalo kdekoli ve jméně
    a jen malými písmeny. Zadání („bez ohledu na velikost písmen jako dnes“) jsem vyložil takto.
12. **R12, neznámá velikost.** Když Pixeldrain nebo MediaFire velikost nedá a archiv nejde otevřít, je výsledek
    `incomplete` s resume (stejně jako u GC-Main), po 6 pokusech platí bod 3.
13. **R48, `lib.certgen`** padá při importu i na `python3-dev` (chybí pyOpenSSL), ponecháno podle inventury.

## 7. Kontrola Comics a comics-nzb-hunteru

- **API:** žádná změna (`api.py` se neměnil), názvy stavů issue ani `ddl_info` beze změny. Schéma `ddl_info`
  beze změny (žádný nový sloupec), formát ID (`<id>`, `<id>-N`, `manual-…`) beze změny. Nové klíče (`pack`
  v položce fronty, `DDL_HEAL_PP_COUNT`) žijí jen v paměti.
- **Nové řádky ve `failed`** (R16 obnovené jednotlivé číslo, větve „neplatný mainlink“, „výjimka
  z `parse_downloadresults`“, vyčerpané `incomplete`; R20 po 3 odmítnutích PP): stejný tvar jako Q5,
  `ID` = ID příspěvku (= `ddl_info.ID`), `Status='Failed'`, `Provider='DDL(GetComics)'`, skutečné `IssueID`
  a `Issue_Number`, `ComicID`, `NZBName` = `nzbtitle` nebo `ddl_info.series`, `DateFailed`. Comics
  [requeue_missing_issues.py](../../Comics/requeue_missing_issues.py) je vypíše
  (`SELECT … FROM failed WHERE IssueID = ?`), `remediate_html_stubs.clear_failed`
  (`DELETE FROM failed WHERE ID = ? AND Provider = ?`) je smaže. Packy do `failed` nezapisují.
- **Stavy:** víc čísel se po selhání vrací na `Wanted` místo trvalého `Snatched` (záměr Q11). Comics na
  `Snatched` po selhání DDL nespoléhá (viz FOLLOWUPS-2026-11-21). Hunter bere `Wanted` přes `getWanted`
  a nově tedy uvidí i tato čísla.
- **`ddl_info.status`:** hunter čte jen `status='Completed'` (`mylar_db.ddl_pack_history`, historie stažených
  packů podle `remote_filesize`). R12 brání tomu, aby useknutý soubor z Pixeldrainu nebo MediaFiru byl
  `Completed` s chybnou velikostí. R20 přepne na `Failed` pack, který PP 3× odmítl, takže z historie hunteru
  zmizí. Odpovídá to skutečnosti (do knihovny se nedostal). Comics čte `ddl_info` podle `issueid` (nejnovější
  řádek), nové stavy nepřibyly.

## 8. Nasazení (pro uživatele)

Merge do `python3-dev`, nasazení a restart jen se souhlasem. Postup podle `CLAUDE.md`, změněné soubory jmenovitě:

```sh
docker cp mylar/helpers.py mylar:/app/mylar/mylar/helpers.py
docker cp mylar/getcomics.py mylar:/app/mylar/mylar/getcomics.py
docker cp mylar/webserve.py mylar:/app/mylar/mylar/webserve.py
docker cp mylar/search_filer.py mylar:/app/mylar/mylar/search_filer.py
docker cp mylar/filers.py mylar:/app/mylar/mylar/filers.py
docker cp mylar/downloaders/pixeldrain.py mylar:/app/mylar/mylar/downloaders/pixeldrain.py
docker cp mylar/downloaders/mediafire.py mylar:/app/mylar/mylar/downloaders/mediafire.py
docker cp data/interfaces/default/queue_management.html mylar:/app/mylar/data/interfaces/default/queue_management.html
```

- `requirements.txt` ani `Dockerfile` se nemění. `.dockerignore`, `CLAUDE.md`, `tests_db/` a `review/` se do
  kontejneru nekopírují.
- Soubory odstraněné v R48 v kontejneru zůstanou. Nic je nenačítá, neškodí a zmizí až po rebuildu.
- **Rebuild image (R14) a připnutí závislostí (Q8)** jsou samostatný krok uživatele po merge. Image je dnes za
  běžícím kódem (viz nové varování v `CLAUDE.md`).
- Před restartem `docker logs mylar --tail 50`: restart přeruší běžící DDL a PP a smaže `REJECTED_MATCHES`,
  `PACK_ISSUEIDS_DONT_QUEUE`, nové `DDL_HEAL_PP_COUNT` a položky vrácené po `incomplete` (po startu se načtou
  z `ddl_info` bez kontextu, jako dřív).

**Ověření po restartu:**

- markery: `docker exec mylar grep -c "def ddl_host_download_check" /app/mylar/mylar/helpers.py`,
  `… grep -c "def ddl_thread_check" …/helpers.py`, `… grep -c "def release_restored_ddl_item" …/helpers.py`,
  `… grep -c "DDL_MAX_HEAL_PP_ATTEMPTS" …/helpers.py`, `… grep -c "ddl_host_download_check" /app/mylar/mylar/downloaders/pixeldrain.py`
  (a `mediafire.py`), `… grep -c "Download in progress, try again" /app/mylar/mylar/webserve.py`,
  `… grep -c "ajaxcallit('restart_queue')" /app/mylar/data/interfaces/default/queue_management.html`,
  `… grep -c "_is_duplicate_rejected_match" /app/mylar/mylar/search_filer.py` (má být 0);
- `docker logs mylar --tail 50`: start bez tracebacku, `[DDL-DOWNLOADER] DDL downloader thread started and running`;
- UI: otevřít Queue Management a kliknout na Restart Queue. Musí se zeptat, při stahování odmítnout
  s „Download in progress…“, jinak „Successfully restarted Queue“. Kontrola v prohlížeči neproběhla;
- za provozu v logu: u jednotlivých čísel přes GC-Main stejné `Now downloading`/`Completed` jako dřív. Nové hlášky:
  `[PixelDrain] Download answered with status …` / `[MediaFire] …`, `[PixelDrain] Incomplete download: … Left for
  resume.`, `[DDL-DOWNLOADER] Download of … raised an error`, `[DDL-DOWNLOADER] Unexpected error while
  processing …` + `Marked item … as Failed after an unexpected error`, `[SEARCH-QUEUE] Unexpected error …`,
  `[DDL-WATCHDOG] The DDL-QUEUE thread is not running. Starting it again.`, po `incomplete` `[DDL-RETRY] Resume
  possible …` (fdebug), `[DDL-DOWNLOADER] Restored pack item … Returning N issue(s) of pack … to Wanted`,
  `[DDL-SECTIONS] Restored section … names no issue numbers`, u jednotlivých čísel `[REVERSE UNO] Marked pack
  release <id> as Failed` (text z packové větve), `[DDL-RESTART-QUEUE] A DDL download is in progress. Not
  restarting the queue.`, `[DDL-WATCHDOG] … Sent the file to post-processing (n/3).` a `[DDL-WATCHDOG]
  Post-processing rejected … 3 times …`.

## 9. Stav po merge

2026-11-22 (časy pražské):

- **Merge** v 15:14 na pokyn uživatele: `python3-dev` posunuta fast-forwardem z `142c9003` na `31782532`
  (včetně zadání druhé části), bez merge commitu. Na `python3-dev` v hlavním stromu znovu `tests/` 88 passed,
  `tests_db/` 85 passed, `ast.parse` sedmi změněných souborů v 3.8 bez chyby.
- **Nenasazeno:** žádný `docker cp`, kontejner `mylar` se nerestartoval. Postup v kap. 8.
- **Nepushnuto** na `fork`.
- Worktree `/data/Tarzan/Cursor/Mylar-review-2026-11-22` a větev `claude/review-2026-11-22` zatím zůstávají
  (celá větev je v `python3-dev`).
