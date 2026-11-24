# Opravy nálezů z review 2026-11-22, šestá část (watchdog DDL, alt_match, fronta PP, zátěž, SQLite)

Session bez dozoru podle [FIX_PROMPT-2026-11-22-part6.md](FIX_PROMPT-2026-11-22-part6.md), nálezy R43, R28, R34, R40
(dvě části) a R37 z [REVIEW-2026-11-22.md](REVIEW-2026-11-22.md) (kap. 4 a rozhodnutí v kap. 11, doplnění 2026-11-24
odpoledne). Pořadí R43 → R28 → R34 → R40 → R37, u každého bodu nejdřív test, který před opravou selhal, a teprve potom
oprava. Hotovo 24. 11. 2026 večer (SEČ).

## 1. Prostředí

- Worktree `/data/Tarzan/Cursor/Mylar-review-2026-11-22-part6` (na Z2 `/share/Tarzan/Cursor/Mylar-review-2026-11-22-part6`),
  větev `claude/review-2026-11-22-part6` z `python3-dev` na `f575beb0`.
- Testy v image `mylar3:local` `sha256:9210596da2a22a428593e5ac816a207f1002308340adf2b43bc2cec1df577940`
  (přestavěn 24. 11. 2026 11:25 SEČ, viz pátá část kap. 9), Python 3.8.2. pytest a pyflakes jen v dočasném kontejneru.
- **Nic se nenasadilo ani nerestartovalo.** Žádný `docker cp`, `docker exec` do `mylar`, žádné volání API ani
  webových akcí, žádný dotaz do `mylar.db`, nic v `/comics`, `/downloads`, `/config`. Bez sítě (GetComics, Pixeldrain,
  ComicVine i HTTP podvržené). Image se nepřestavoval ani nepřetagoval. Hlavní strom Mylaru, Comics a
  comics-nzb-hunter jen čtené.
- Číst se smělo jen `docker logs mylar-2026-09-11` (11. 9. až 22. 11.) a `docker logs mylar` (od 22. 11.). Časy v logu
  jsou UTC, níž přepočtené na pražský čas (do 25. 10. SELČ = UTC+2, potom SEČ = UTC+1).
- Pomocné skripty a výtahy z logu v `.scratch/part6/` (mimo git): `pp_durations.py` (R34), `r28_repeat.py` (R28),
  `pyflakes_before.txt` / `pyflakes_after.txt`, `try_imports.py`.

## 2. Testy

| | `tests/` | `tests_db/` |
|---|---|---|
| Výchozí stav (čistý worktree) | **131 passed** | **204 passed** |
| Konečný stav | **131 passed** | **241 passed** (37 nových) |

- Nové soubory: [test_watchdog_active_item.py](../tests_db/test_watchdog_active_item.py) (R43, 9),
  [test_verification_alt_match.py](../tests_db/test_verification_alt_match.py) (R28, 5),
  [test_pp_queue_wait.py](../tests_db/test_pp_queue_wait.py) (R34, 4),
  [test_rejected_matches_limits.py](../tests_db/test_rejected_matches_limits.py) (R40, 6),
  [test_series_page_cover.py](../tests_db/test_series_page_cover.py) (R40, 5),
  [test_db_layer.py](../tests_db/test_db_layer.py) (R37, 8). Kontrolní testy (procházejí i před opravou) mají
  v názvu `test_control_`.
- **Ověření odložením opravy** (`git stash` jen `mylar/` ve worktree, testy nechány): R43 5 padá / 4 kontrolní
  projdou, R34 2 / 2, R37 5 / 3. U R28 a R40 testy padaly na kódu před opravou při psaní (R28 3 / 2, R40
  `REJECTED_MATCHES` 3 / 3, `comicDetails` 3 / 2). Po vrácení opravy vše prochází.
- Testy souběhu jsou deterministické: R34 drží první PP na `threading.Event` a zjišťuje, jestli fronta čeká v `join`
  (podvržený `Thread.join`), nebo spustila další položku; R37 drží první `upsert` mezi UPDATE a INSERT a druhé vlákno
  hlásí pokus o zámek (obal `db_lock`); R43 drží `extractall` na `Event` uprostřed skutečného běhu `ddl_downloader`
  (Pixeldrain s podvrženým HTTP). `time.sleep` je všude nahrazený.
- `ast.parse` změněných modulů a testů v 3.8.2 před každým commitem: OK. Nic z 3.9+.
- Import všech modulů `mylar.*` v 3.8.2 (`try_imports.py`, `--network none`): **71 ze 71 OK** před i po. Selhání jen
  v `lib/` (`lib.certgen`, `lib.utorrent.client`, `lib.deluge_client.tests`) jako dřív.
- **pyflakes `mylar/` před a po:** 752 → 752, hlášky bez čísel řádků totožné. Žádná nová.

## 3. Nálezy

| ID | Bod | Stav | Commit | Nové testy (padalo před opravou) | Poznámka |
|---|---|---|---|---|---|
| R43 | watchdog dokončí položku, kterou downloader ještě zpracovává (rozbalovaný zip) | **opraveno** | `a90ad071` | 2 (2) | Cesta: Pixeldrain/MediaFire/Mega po stažení zipu volají `zip_zip` ve stavu `Downloading`; watchdog fáze 1 najde úplný zip, `validate_downloaded_archive` ho uzná → `Completed` a `queue_ddl_postprocess` zipu, downloader pak pošle do PP i složku. Reprodukováno skutečným `ddl_downloader` s Pixeldrainem a `extractall` drženým na `Event`: dnes `Completed` uprostřed rozbalování a dvě položky ve frontě PP (zip a složka). **Oprava:** signál `mylar.DDL_ACTIVE_ID` = ID položky, kterou smyčka `ddl_downloader` vzala z fronty; nastaví se hned po `queue.get`, uvolní na začátku dalšího kola smyčky a ve `finally` kolem smyčky (výjimka, `exit`). Watchdog fáze 1 takovou položku přeskočí celou (`[DDL-WATCHDOG] … is being worked on by the DDL downloader. Skipping.`, fdebug), stejně tak `heal_completed_but_snatched` (GC-Main nastaví `Completed` ještě **před** `zip_zip`, takže rozbalování delší než 10 min by tam poslalo zip do PP). Proč tenhle signál: je to přesně „downloader drží položku“ (stahování, ověření, rozbalení, zařazení do PP, čekání před vrácením do fronty), nezávisí na `DDL_LOCK` (ten Pixeldrain a MediaFire neberou) ani na čase souboru (zip při rozbalování nemění `mtime`). Downloader stav položky nastaví sám ve všech větvích. Po restartu nebo když vlákno downloaderu neběží, je signál `None` a watchdog funguje jako dřív (kontrolní test). Fáze 2 (`DDL_LOCK` je `True`, GC-Main) beze změny. |
| R43 | useknuté `.pdf`/`.cb7` neznámé velikosti projde jako hotové | **opraveno** | `a90ad071` | 3 (3) | `validate_downloaded_archive` u 7Z/PDF neověřuje strukturu; bez známé velikosti tak vrací `ok` pro jakkoli useknutý soubor. Reprodukováno (`.pdf` i `.cb7`, 300 kB bez `remote_filesize`): `Completed` a PP. **Oprava:** výsledek má nový klíč `unverified` (7Z/PDF a `expected == 0`), watchdog fáze 1 takový soubor jako hotový nebere. Spadne do stávající větve: soubor zapisovaný v posledních 2 min přeskočí, jinak po 10 min (řádek i soubor) vrátí položku do `Queued`; auto-load pak navazuje (`ddl_row_resume`), a když je soubor ve skutečnosti celý, host odpoví 416 s plnou velikostí a downloader stahování přeskočí jako hotové (GC-Main, Pixeldrain, MediaFire to umějí). Nic se nemaže. Ostatní volající `validate_downloaded_archive` (downloadery, heal, PP) klíč nečtou, chování beze změny. Kontrolní: `.pdf` známé velikosti a úplné `.cbz` po restartu watchdog dokončí a pošle do PP jako dřív; zapisovaný `.cbz` přeskočí. |
| R28 | alt_match před primární shodou: ID, pack a název z jiného příspěvku než link | **opraveno** | `766d5b8c` | 3 (3) + 2 kontrolní | Cesta: `checker` vrací všechny shody v pořadí výsledků; `verification` volá `searcher(…, verified_matches, links=<stahovaná shoda>, …)` a `searcher` čte `nzbid`, `pack`, `pack_numbers`, `pack_issuelist` a název z `comicinfo[0]`. Po smyčce se `nzblog` píše z `verified_matches[verified_index]`, kde `verified_index` se u shod s `downloadit=False` neposouvá. Reprodukováno skutečným `searcher` s podvrženým `getcomics.GC`: `loadsite('100', '?p=200')`, `parse_downloadresults(nzbid='100', link='?p=200')` (tedy `ddl_info.ID` 100 s linkem 200) a `nzblog.ID='100'`. **Navíc:** kontrola blacklistu (`Failed.failed_check`, Q5) běží nad `comicinfo[0]['nzbid']`, takže alt_match před primární shodou **obešel blokovaný příspěvek** (test: 200 ve `failed`, stáhlo se). **Oprava (nejužší místo, `verification`):** `searcher` a `nzbname_create` dostanou `comicinfo = [stahovaná shoda] + zbytek` a `verified_index` po úspěchu ukazuje na stahovanou shodu. Po opravě: link, `nzbid`, pack data i název z položky 200, `nzblog`/`ddl_info` 200, blokovaný příspěvek se nestáhne, cizí `pack_issuelist` alt_match packu se nepoužije. Alt_match zůstává v `REJECTED_MATCHES` (UI „Rejected matches“). Kontrolní: bez alt_match a s alt_match za primární shodou beze změny. |
| R34 | `postprocess_main` uvolní `APILOCK` 5 s po startu PP, PP běží dál | **opraveno** | `b3b94eda` | 2 (2) + 2 kontrolní | Reprodukováno: druhá položka fronty startuje, zatímco první (pack) ještě běží. **Oprava:** `process.Process` si vlákno PP spuštěné bez `join` (větev `apicall`/`issueid`/`Manual Run`) uloží do `self.pp_thread`; `postprocess_main` na něj počká `join(PP_THREAD_WAIT)`, konstanta **600 s** v `helpers.py`. Když PP do té doby neskončí: `[POST-PROCESS-QUEUE] Post-processing of <nzb_name> is still running after 600 seconds. Going on with the next item; that post-processing keeps running.` (WARN), vlákno se nezabíjí a fronta pokračuje jako dnes (`finally` uvolní `APILOCK`). Beze změny: návratová hodnota `post_process()` (dál `None`), neapicall cesta (vlastní `join` a čtení fronty, kontrolní test), `failed`, `retry_outside`, ruční PP z UI (`Manual Run` jde přes `PostProcessor` a `MANUAL_PP_LOCK`, ne přes frontu), API `forceProcess` (dál jen vloží položku do fronty a hned odpoví), `sleep(5)` po PP. Jediný vedlejší účinek: ID z `PP_CURRENT_DDL_IDS` se uvolní až po skončení PP (dřív 5 s po startu), takže watchdog heal ho po celou dobu PP nepošle znovu. |
| R40 | `REJECTED_MATCHES` bez omezení | **opraveno** | `06be03e6` | 3 (3) + 3 kontrolní | Reprodukováno: 60 shod pro jedno issue → 60 v paměti; shoda stará 7 dní zůstává. **Oprava v `_add_or_update_rejected_match` při přidání nové shody:** zahodí shody issue, které žádné hledání nenašlo déle než **7 dní**, a nad stropem **50** ty nejdéle neviděné (pořadí v seznamu zůstává). Seznam se přiřadí celý, nic se nemaže uvnitř iterace. Navíc nejvýš jednou za hodinu (při přidání) zmizí issue, jejichž shody jsou všechny starší než 7 dní (jinak by čísla, která se už nehledají, zůstala v paměti napořád); částečně staré seznamy se proříznou při dalším přidání do nich. Čas: stávající `last_updated` (nastaví se při přidání a obnoví, když shodu najde další hledání), nový klíč se nepřidával, viz kap. 5. Výběr shody v UI (`select_rejected_match`) drží objekt shody a maže ji podle link/nzbid, takže přiřazení nového seznamu ho nerozbije; jinak než dnes ho nic neodstraní. Nový zámek nepřidán (test souběhu není, změna jen přiřazuje celé seznamy a maže celé klíče). |
| R40 | `comicDetails` volá ComicVine při každém zobrazení série bez obálky | **opraveno** | `30ed9a46` | 3 (3) + 2 kontrolní | Cesta: obálka chybí v cache → když DB nemá `ComicImageURL`/`ComicImage`, `cv.getComic(…, 'image')`, pak `helpers.getImage` (spí ≥ 2 s); při selhání znovu při každém zobrazení. Reprodukováno: dvě zobrazení = dvě volání CV. **Oprava:** pokus o obálku (CV i `getImage`) ze stránky série nejvýš jednou za **24 h** na sérii (`COVER_RETRY_WAIT`, slovník v paměti). Stránka se zobrazí jako dřív s prázdnou obálkou (`blank.gif`), i když pokus čeká. Série s obálkou v cache CV nevolá vůbec (kontrolní), první zobrazení obálku zkusí stáhnout jako dřív (kontrolní). Obálka se dál stahuje při refreshi série (`importer.addComictoDB` → `helpers.getImage`, když chybí v cache; v logu 171× z `mass-add`/`mass-refresh`). |
| R37 | zápis ztracený po vyčerpání pokusů je tichý | **opraveno** | `bb8ff324` | 3 (3) | Reprodukováno podvrženým spojením, které vždy hlásí `database is locked`: `action()` i `fetch()` vrátí po 5 pokusech `None` jen s WARN. **Oprava:** po vyčerpání pokusů ERROR `[DB] Gave up after 5 attempts, the write was not done: <dotaz>` (v `fetch` „the read returns nothing“). Jen text dotazu, **bez hodnot**; u `upsert` je v dotazu tabulka (`UPDATE ddl_info SET …`), test to ověřuje. Návratová hodnota zůstává `None`, počet pokusů (5) a busy-timeout (20 s) beze změny. |
| R37 | `upsert` ve dvou zámcích → duplicitní řádek | **opraveno** | `bb8ff324` | 2 (2) + 3 kontrolní | Reprodukováno: vlákno A podržené mezi UPDATE (0 řádků) a INSERT, vlákno B mezitím udělá celý `upsert` → v `issues` dva řádky `NEW1`. **Oprava:** `db_lock` je `threading.RLock` a `upsert` drží zámek přes UPDATE i INSERT; `action()` si ho uvnitř bere znovu (proto re-entrantní; s obyčejným `Lock` by se `upsert` zablokoval sám). Pořadí a text dotazů beze změny, bez UNIQUE, bez indexů, bez WAL. Po opravě B čeká, pak UPDATE najde řádek od A → jeden řádek. Kontrolní: běžný `upsert` (nový klíč INSERT, existující UPDATE), `action`/`select`, jiná chyba DB dál vyhodí výjimku. |
| R37 | `select()` po vyčerpání pokusů | **neopraveno** (podle zadání) | – | – | `select()` volá `self.fetch(...).fetchall()`; po vyčerpání pokusů je `fetch` `None` a `select` spadne na `AttributeError: 'NoneType' object has no attribute 'fetchall'` (teď s ERROR řádkem před tím). `selectone()` vrátí `[]` a volající `.fetchone()` na seznamu spadne taky. |
| R37 | držení zámku během busy-timeoutu | **neopraveno** (podle zadání) | – | – | Globální `db_lock` se dál drží i během 20s busy-timeoutu × 5 pokusů. Dlouhé čtení `mylar.db` zvenku (Comics, sqlite CLI) tak může zastavit všechna vlákna Mylaru až na ~100 s. Nově to platí i pro celý `upsert` (UPDATE + INSERT), dřív pro každý dotaz zvlášť. |

## 4. Čísla z logu (časy pražské)

**R43, watchdog** (`[DDL-WATCHDOG] File … is already downloaded`): **8×**, všechno starý kontejner, v novém 0×.
Ve **všech 8 případech downloader položku ještě zpracovával** a sám ji dokončil o 2–4 s později, zip Conan o 50 s
(žádný případ po restartu). Host „GC-Main“ je odvozený: v okně stahování nejsou hlášky Pixeldrain ani MediaFire.

| Kdy | Soubor | Host | Následek |
|---|---|---|---|
| 15. 9. 19:17:24 | Inglorious X-Force 009 `.cbz` | GC-Main (v okně žádné hlášky Pixeldrain/MediaFire) | jen `Completed` (`queue_ddl_postprocess` přidán až 25. 9.) |
| 17. 9. 09:50:51 | Redcoat 015 `.cbr` | pravděpodobně Pixeldrain (celá série šla přes něj) | jen `Completed` |
| 1. 10. 23:25:39 | Superman – Kingdom of Zod Special 001 `.cbz` | GC-Main | **dvojí PP**, druhé „Could not find file … Skipping“ |
| 1. 10. 23:43:41 | Amazing Venom 001 `.cbz` | GC-Main | **dvojí PP**, druhé nic nenašlo |
| 2. 11. 22:08:46 | Thor 007 `.cbz` | GC-Main | **dvojí PP**, druhé nic nenašlo |
| 11. 11. 18:49:00 | Jeff the Land Shark – Superstar 005 `.cbz` | GC-Main | **dvojí PP**, druhé nic nenašlo |
| 18. 11. 18:36:20 | Conan The Barbarian Vol. 1 #1–213 + Annuals `.zip` (9,4 GB) | Pixeldrain, `zip_zip` 18:33:41–18:37:08 | `Completed` uprostřed rozbalování |
| 18. 11. 18:56:33 | War Comics (001-049) `.zip` | Pixeldrain, `zip_zip` 18:56:10–18:56:35 | `Completed` uprostřed rozbalování |

U obou zipů tehdejší `queue_ddl_postprocess` hledal holé jméno souboru (`filename`), které na disku není (soubor je
`…[__id__].zip`), proto zip do PP nešel. Dnešní kód (`ddl_row_file`, nejdřív `tmp_filename`, R21 z první části) by
**zip do PP poslal** — dvojí PP z review by teď nastalo. U jednotlivých čísel stačilo okno pár sekund mezi dopsáním
souboru a zápisem `Completed` downloaderem. Přípony: 5× `.cbz`, 1× `.cbr`, 2× `.zip`; `.pdf`/`.cb7` ani jednou.

**R28, alt_match** (`[REJECTED-MATCHES] Successfully stored alt_match`): **12×**, jen starý kontejner. 11× IssueID
1114057 (G.I. Joe #1, alt_match „G.I. Joe – Cold Slither #1“) každých 90 min od 11. 9. 20:09 do 12. 9. 12:09:
`verified_matches` obsahoval jen alt_match (`downloadit=False`), snatch neproběhl. 1× 1. 10. 23:20:06 IssueID 1006177
(Fire and Ice #1, alt_match „Welcome to Smallville“): `verified_matches` jen primární shoda, snatch `?p=311173` a
`nzblog` 311173 správně. **Situace z review (alt_match před primární shodou) v logu nenastala.** Kontrola blacklistu
(„Marked as a bad download“, DEBUG) 513×, nikdy dvakrát v jednom hledání (druhý kandidát po neúspěchu prvního se
nezkoušel), takže změna `comicinfo` na stahovanou shodu nemění nic, co by se v logu dělo.

**R34, PP z fronty** (vlákno PP = první až poslední řádek vlákna, které se ozve do 10 s po načtení položky z fronty,
`pp_durations.py`): **758 běhů**, nejdelší **32 s** (Conan #1–213 + Annuals, 18. 11. 18:37:10), dál 28 s (Mangaverse –
Ghostlocke 01, 26. 9. 5:43), 27 s (Giant-Size Youngblood 001, 13. 9. 15:19), 27 s (Ciruelo – Lord of the Dragons,
24. 11. 3:55, nový kontejner). **Žádný nad 5 min.** Konstanta 600 s má tedy rezervu ~19×. **Překryvy: 23 dvojic
(37 běhů)** v 10 dnech mezi 16. 9. a 19. 11., v novém kontejneru 0. Překryv 0–10 s (5× do 1 s, nejvíc 10 s): delší PP
(> 5 s) běželo, když fronta po `sleep(5)` vzala další položku. Patří sem i dvojí PP z R43 (1. 10., 2. 11., 11. 11.).
Review ve 3denním vzorku napočítal 0, nad celým logem jich je 23; dvě PP stejného čísla se v nich překrývala jen
u dvojího PP z R43.

**R37, SQLite** (`Database Error: database is locked`): **6×**, vše starý kontejner. 16. 10. 2:46:04 (`UPDATE
exceptions_log`), 4:13:06 (`INSERT INTO rssdb`), 4:30:17 (`UPDATE rssdb`) po jednom pokusu; 20. 11. 0:05:50, 0:06:11,
0:06:33 tři pokusy téhož `UPDATE jobhistory` (každý ~21 s = busy-timeout + 1 s), čtvrtý prošel. **Všech 5 pokusů
nedošlo nikdy.** `disk I/O error` 1× (16. 10. 2:14:22, `INSERT INTO jobhistory`) — ta chyba se neopakuje a vyhodí
výjimku hned, oprava se jí netýká. `fetch` žádný locked. Duplicity v `issues` by šlo zjistit jen dotazem do živé DB
(viz kap. 5).

**R40:** „Added new rejected match“ (DEBUG) 2 919× pro 99 issue, 6 issue s víc než 50 přidáními (nejvíc 940 pro
IssueID 1192089, 656 pro 1191029). Je to horní odhad délky seznamu (počítá i opětovné přidání po odebrání a nevidí
restarty), ukazuje ale, že strop 50 se u pár čísel uplatní. Obálka ze stránky série (`CP Server` vlákna, „Attempting to
retrieve the comic image“ / „[comicDetails] Failed to download cover image“): **0×** od 11. 9. Oprava je tedy
pojistka; dnes se stránky sérií bez obálky prakticky nezobrazují.

## 5. Otevřené otázky a konzervativní volby

1. **R43, signál.** `mylar.DDL_ACTIVE_ID` je jedno ID (smyčka zpracovává položky po jedné). Watchdog aktivní položku
   přeskočí **celou**, i větve „stuck“ (vrácení do `Queued` po 10 min). Důvod: dokud ji downloader drží, nastaví stav
   sám, a vrácení do fronty by stejně nic nespustilo (auto-load běží v tom samém vlákně). Kdyby se vlákno downloaderu
   zaseklo napořád (např. čtení bez timeoutu), řádek zůstane `Downloading` místo `Queued`; stahovat to nezačne ani
   dnes. Fáze 2 (`DDL_LOCK`, GC-Main) zůstala, jak byla, i se smazáním „zaseknutého“ souboru.
2. **R43, `.pdf`/`.cb7` po restartu.** Úplný `.pdf` neznámé velikosti ve stavu `Downloading` už watchdog nedokončí sám;
   po 10 min ho vrátí do fronty a downloader ho ověří u hosta (416 s plnou velikostí = hotovo). Stojí to jeden dotaz na
   hosta, nic se nemaže. V logu takový případ nebyl.
3. **R28, druhý kandidát po blacklistu.** Oprava platí pro každou stahovanou shodu, nejen za alt_match: když první
   kandidát skončí `downloadchk-fail` (je ve `failed`), druhý se teď kontroluje proti **svému** `nzbid` (dřív proti
   prvnímu, takže taky skončil jako blokovaný). Je to stejná vada (link z jedné položky, ID z jiné), v logu nenastala.
4. **R34, timeout 600 s** (konstanta `PP_THREAD_WAIT`, rozhodnutí uživatele). Nejdelší PP 32 s. Tlačítko
   „Restart PP queue“ (`restart_pp_queue`) během čekání frontu nepopostrčí: vloží `exit`, počká 5 s, `exit` z fronty
   zase vybere a nové vlákno nespustí, protože staré žije (`queue_schedule` → `start` kontroluje `is_alive`). Fronta
   tedy dál čeká na běžící PP nejvýš do konce 10 min a pak pokračuje; dva workery fronty nevzniknou.
5. **R40, hodnoty.** Strop **50** na issue (log: jen 6 issue nad 50 přidání, UI je řadí podle relevance), stáří
   **7 dní** od posledního nálezu, úklid celých issue nejvýš jednou za hodinu. Nad stropem se zahazují **nejdéle
   neviděné** shody, ne nejméně relevantní: relevance je skóre jména, ne čerstvost, a staré výsledky už často nejsou
   ke stažení. Stáří se počítá od `last_updated` (poslední nález hledáním), ne od prvního přidání: shoda, kterou hledání
   pořád nachází, je pořád nabídnutelná. Nový klíč `added_at` se nepřidal, `last_updated` už v slovníku je a u shody,
   kterou nic znovu nenašlo, je to čas přidání.
6. **R40, `comicDetails`:** 24 h jen v paměti, restart čekání vynuluje.
7. **R37, `upsert` po ztraceném UPDATE.** Když UPDATE vyčerpá pokusy, `total_changes` se nezmění a `upsert` zkusí
   INSERT; kdyby ten prošel u **existujícího** klíče, vznikne duplicitní řádek. Upstream chování, podle zadání
   neměněno (teď aspoň zaloguje ERROR u UPDATE). Rozhodnout, jestli v takovém případě INSERT přeskočit.
8. **R37, duplicity v živé DB** (jen čtení, se souhlasem):
   ```sh
   docker exec mylar sqlite3 -readonly /config/mylar/mylar.db \
     "SELECT 'issues', IssueID, COUNT(*) FROM issues GROUP BY IssueID HAVING COUNT(*) > 1
      UNION ALL SELECT 'annuals', IssueID, COUNT(*) FROM annuals GROUP BY IssueID HAVING COUNT(*) > 1
      UNION ALL SELECT 'nzblog', IssueID || '/' || PROVIDER, COUNT(*) FROM nzblog GROUP BY IssueID, PROVIDER HAVING COUNT(*) > 1;"
   ```
9. **Mimo rozsah, při čtení kódu (neověřeno):** `comicDetails` přiřazuje `comic['ComicYear'] = comic['Corrected_SeriesYear']`
   do `sqlite3.Row`, což vyhodí `TypeError`, když má série opravený rok jiný než `ComicYear` (stránka série by pak
   skončila HTTP 500). Neopraveno.

## 6. Kontrola Comics a comics-nzb-hunteru

- **comics-nzb-hunter, `forceProcess` (R34):** `force_process_and_wait` po `forceProcess` čeká v
  `wait_mylar_downloaded` nejvýš `wait_s` = **120 s** (výchozí, CLI `--wait-s`), dotaz na stav každé 3 s. API
  `forceProcess` dál jen vloží položku do fronty PP a hned odpoví (beze změny). Nově ale položka čeká, dokud neskončí PP
  před ní (dřív startovala po ~5 s bez ohledu na běžící PP). Při běžných délkách (do 32 s + 5 s) se do 120 s vejde
  i několik položek před ní. Když ne (např. pack a několik DDL čísel ve frontě), hunter job označí `import_pending`:
  soubor zůstane nachystaný ve `/downloads` a úklid SAB se přeskočí. Položka ve frontě PP Mylaru ale zůstává a PP ji
  zpracuje, až na ni přijde řada, takže číslo skončí `Downloaded`; jen hunter to v tom běhu nepotvrdí (import jde
  zopakovat, např. CLI `import`). Nic se neztratí ani nesmaže. Hunter se neměnil.
- **Comics `remediate_html_stubs.py` (R28):** čte `ddl_info` (`ID`, `site`) nejnovějšího řádku podle `issueid`
  a zapisuje/maže řádek ve `failed` s tímto `ID`. Po opravě R28 má `ddl_info.ID` (a `nzblog.ID`, `failed.ID` z Q5)
  vždy ID **stahovaného** příspěvku; dřív při alt_match před primární shodou ID alt_match (v logu to nenastalo).
  Blacklist z Comics tak blokuje ten příspěvek, který se opravdu stáhl.
- **R37:** Comics čte a zapisuje `mylar.db` přímo (sqlite3 / `docker exec`), jiný proces; `db_lock` se ho netýká.
  Dlouhé čtení z Comics dál může Mylar blokovat (bod R37 o busy-timeoutu, neopraveno).
- **Beze změny:** schéma tabulek (žádný sloupec, UNIQUE ani index), názvy stavů (`Downloading`, `Completed`, `Queued`,
  `Failed`, `Snatched`, `Downloaded`), tvar jmen souborů, odpovědi API (`getWanted`, `getComic`, `getIssueInfo`,
  `forceProcess`, `refreshComic`, `addComic`, `findComic`, `unqueueIssue`, `recheckFiles`). `REJECTED_MATCHES` API
  nevystavuje.

## 7. Nasazení (jen se souhlasem uživatele)

Změněné soubory (všechno Python, žádná šablona):

```sh
docker cp mylar/__init__.py mylar:/app/mylar/mylar/__init__.py
docker cp mylar/db.py mylar:/app/mylar/mylar/db.py
docker cp mylar/helpers.py mylar:/app/mylar/mylar/helpers.py
docker cp mylar/process.py mylar:/app/mylar/mylar/process.py
docker cp mylar/search.py mylar:/app/mylar/mylar/search.py
docker cp mylar/search_filer.py mylar:/app/mylar/mylar/search_filer.py
docker cp mylar/webserve.py mylar:/app/mylar/mylar/webserve.py
```

1. Po merge do `python3-dev` zkopírovat soubory jmenovitě (výš). Python moduly potřebují **`docker restart mylar`**,
   jen se souhlasem uživatele a když neběží DDL stahování, PP ani klient API (`docker logs mylar --tail 50`, viz pátá
   část kap. 9). Restart smaže stav v paměti (`REJECTED_MATCHES`, nově i čekání obálek).
2. Ověření v kontejneru (počet výskytů):
   `docker exec mylar grep -c "DDL_ACTIVE_ID" /app/mylar/mylar/helpers.py` (4), v `__init__.py` (1),
   `docker exec mylar grep -c "PP_THREAD_WAIT" /app/mylar/mylar/helpers.py` (4),
   `docker exec mylar grep -c "pp_thread" /app/mylar/mylar/process.py` (3),
   `docker exec mylar grep -c "match_index" /app/mylar/mylar/search.py` (2),
   `docker exec mylar grep -c "REJECTED_MATCHES_MAX_PER_ISSUE" /app/mylar/mylar/search_filer.py` (4),
   `docker exec mylar grep -c "_cover_download_due" /app/mylar/mylar/webserve.py` (2),
   `docker exec mylar grep -c "threading.RLock()" /app/mylar/mylar/db.py` (1),
   `docker exec mylar grep -c "Gave up after" /app/mylar/mylar/db.py` (2).
3. Co hledat v logu po restartu: start bez tracebacku, `[DDL-WATCHDOG] DDL Watchdog thread started`, PP fronta
   a `[DDL-DOWNLOADER] DDL downloader thread started`. Při dalším DDL stahování: žádné `[DDL-WATCHDOG] File … is already
   downloaded` těsně před „successfully downloaded“ downloaderu; v DEBUG případně `… is being worked on by the DDL
   downloader. Skipping.`. Při PP z fronty: další „Now loading from post-processing queue“ až po skončení předchozího
   vlákna PP; `Post-processing of … is still running after 600 seconds` by znamenalo PP delší než 10 min. `[DB] Gave up
   after` by znamenalo ztracený zápis (dřív tichý). Stránka série: otevřít jednu sérii v UI (Playwright), že se
   zobrazí (změna `comicDetails`).
4. **Rebuild image** (R14, pozor v `CLAUDE.md`): po nasazení přes `docker cp` je `mylar3:local` pozadu o tuto část.
   Před jakýmkoli recreate kontejneru nejdřív `docker build -t mylar3:local .` z aktuální `python3-dev`, recreate přes
   Dockhand jen služby `mylar` a se souhlasem.

## 8. Stav po merge

Doplněno 24. 11. 2026 kolem 14:15 SEČ (časy pražské, v závorce UTC).

- **Merge:** `python3-dev` posunuta fast-forwardem z `f575beb0` na `2f74230b`, bez merge commitu. Testy na `python3-dev`:
  `tests/` 131 passed, `tests_db/` 241 passed (image `mylar3:local` `sha256:9210596d…`).
- **Před restartem:** DDL fronta prázdná (`DDL_LOCK: False`, `Queue size: 0`, `DDL_QUEUED count: 0`), žádné PP ani volání
  API. Běžela jen fronta hledání z pravidelného „Search for Wanted“ (každých 30 min, další běh ji znovu naplní);
  restart přerušil hledání Masters of the Universe (2015) #6 (blokovaný pack 113116, `FAILED_DOWNLOAD_CHECKER` ho
  správně odmítl).
- **Nasazení:** `docker cp` sedmi modulů podle kap. 7 a **`docker restart mylar`**, start v 14:09:07 (13:09:07 UTC).
  Kontejner běží dál na image `mylar3:2026-11-22-part2` s kódem přes `docker cp`.
- **Ověření v kontejneru:** všechny značky z kap. 7, bod 2 sedí (`DDL_ACTIVE_ID` 4 + 1, `PP_THREAD_WAIT` 4, `pp_thread` 3,
  `match_index` 2, `REJECTED_MATCHES_MAX_PER_ISSUE` 4, `_cover_download_due` 2, `threading.RLock()` 1, `Gave up after` 2).
  md5 všech 95 souborů `mylar/*.py`, `mylar/downloaders/*.py` a `data/interfaces/default/*.html` v `/app/mylar/` = `HEAD`
  `2f74230b`.
- **Log po restartu (do 14:10):** start bez chyby a tracebacku, Search Queuer, Post-Processing Queuer, `[DDL-DOWNLOADER]
  DDL downloader thread started and running`, `[DDL-WATCHDOG] DDL Watchdog thread started`, `[DDL-STARTUP] No queued
  items`. Žádné `[DB] Gave up after`.
- **UI:** stránka série (`comicDetails?ComicID=167814`, The Savage Sword of Conan: Reforged) vrací HTTP 200 s názvem
  a obálkou, bez chyby v logu. Ověřeno přímým GET z devel-workstation (`curl` na `192.168.113.37:8090`); Playwright na
  macvlan adresu Mylaru nedosáhne (`ERR_ADDRESS_UNREACHABLE`) a Mylar v NPM nemá proxy host, takže v prohlížeči se
  stránka nekontrolovala.
- **Neověřeno v provozu:** watchdog s aktivní položkou, čekání fronty PP, strop `REJECTED_MATCHES` a ERROR po
  vyčerpání pokusů DB se projeví až při dalším DDL stahování, PP, hledání a zamčené DB; zatím ověřeno jen testy.
- **Push** (24. 11. po nasazení): `python3-dev` do `fork` (`f575beb0..8908d881`), na `origin` nic.
- **Image (R14):** předchozí `mylar3:local` (`sha256:9210596d…`, 24. 11. 11:25) otagován jako `mylar3:2026-11-24`, nový
  `mylar3:local` `sha256:a86ea711…` přestavěn z `python3-dev` (`8908d881`) 24. 11. v 16:09. md5 všech 95 souborů v něm
  = `HEAD`, testy v něm 131 a 241 passed. Recreate se neprováděl, kontejner běží dál na `mylar3:2026-11-22-part2` s kódem
  přes `docker cp`. Rollbacky `mylar3:2026-11-24`, `mylar3:2026-11-23`, `mylar3:2026-11-22-part2` a `mylar3:2026-09-11`
  zůstávají.
- **Úklid:** worktree `/data/Tarzan/Cursor/Mylar-review-2026-11-22-part6` odstraněný a větev
  `claude/review-2026-11-22-part6` smazaná (`git branch -d`, mergnutá). Netrackovaný `.scratch/part6/` (výtahy z logu,
  analytické skripty, pyflakes před a po, `try_imports.py`) archivován do
  `/data/Tarzan/Cursor/_archive/2026-11-24-mylar-review-part6/Mylar-review-2026-11-22-part6/.scratch/`.
