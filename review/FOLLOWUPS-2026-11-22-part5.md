# Opravy nálezů z review 2026-11-22, pátá část (chyby z upstreamu na reálných cestách, blacklist DDL)

Session bez dozoru podle [FIX_PROMPT-2026-11-22-part5.md](FIX_PROMPT-2026-11-22-part5.md), nálezy R45 a R44 z
[REVIEW-2026-11-22.md](REVIEW-2026-11-22.md) (kap. 4 a rozhodnutí v kap. 11, doplnění 2026-11-24). Pořadí R45a (API)
→ R45b (timeouty ComicVine) → R45c (zbytek) → R44, u každého bodu nejdřív test, který před opravou selhal, a teprve
potom oprava. Hotovo 24. 11. 2026 kolem 10:40 SEČ.

## 1. Prostředí

- Mylar: worktree `/data/Tarzan/Cursor/Mylar-review-2026-11-22-part5` (na Z2
  `/share/Tarzan/Cursor/Mylar-review-2026-11-22-part5`), větev `claude/review-2026-11-22-part5` z `python3-dev`
  na `888b8a85`.
- Comics: worktree `/data/Tarzan/Cursor/Comics-review-2026-11-22-part5`, větev `claude/review-2026-11-22-part5`
  z `main` na `d608a30`.
- comics-nzb-hunter (`/data/Tarzan/Cursor/scripts/apps/comics-nzb-hunter`) jen čten, beze změny.
- Testy Mylaru v image `mylar3:local` `sha256:64223322346c1f5a5a279719e497a99f1b26e80dd29d364ce3996440e4bbe51e`
  (vytvořen 23. 11. 2026 0:12 SEČ), Python 3.8.2. pytest a pyflakes jen v dočasném kontejneru. Comics v jeho venv
  (Python 3.11).
- **Nic se nenasadilo ani nerestartovalo.** Žádný `docker cp`, `docker exec` do `mylar`, žádné volání API ani
  webových akcí, žádný dotaz do `mylar.db`, nic v `/comics`, `/downloads`, `/config`. Bez sítě (ComicVine, pull
  list a GetComics podvržené). Image se nepřestavoval. Hlavní stromy Mylaru a Comics nedotčené.
- Číst se smělo jen `docker logs mylar-2026-09-11` (11. 9. až 22. 11.) a `docker logs mylar` (od 22. 11.).
  Časy v logu jsou UTC, níž přepočtené na pražský čas.

## 2. Testy

| | Mylar `tests/` | Mylar `tests_db/` | Comics (příkaz z jeho `CLAUDE.md`) |
|---|---|---|---|
| Výchozí stav (čistý worktree) | **131 passed** | **176 passed** | **254 OK** (6 skipped) |
| Konečný stav | **131 passed** | **204 passed** (28 nových) | **258 OK** (6 skipped, 4 nové) |

- Nové soubory testů Mylaru: [tests_db/test_api_upstream_paths.py](../tests_db/test_api_upstream_paths.py) (10),
  [tests_db/test_cv_timeouts.py](../tests_db/test_cv_timeouts.py) (8),
  [tests_db/test_upstream_name_errors.py](../tests_db/test_upstream_name_errors.py) (6),
  [tests_db/test_failed_provider.py](../tests_db/test_failed_provider.py) (4). Comics: třída `ClearFailedTests`
  v `test_remediate_apply_plan.py` (4, dočasná SQLite přes skutečný `MylarDb`). Nový soubor v Comics nevznikl,
  aby se nemusel měnit příkaz v jeho `CLAUDE.md`.
- **Ověření odložením opravy** (`git stash` jen kódu ve worktree): `refreshComic` a spol. (`api.py`) 7 padá,
  3 kontrolní projdou; R44 Mylar (`process.py`) 1 padá, 3 kontrolní projdou; R44 Comics (`remediate_html_stubs.py`)
  2 padají. Po vrácení opravy vše prochází.
- `ast.parse` změněných modulů v 3.8.2 před každým commitem: OK.
- Import všech modulů `mylar.*` v 3.8.2 (`try_imports.py`, `--network none`): **71 ze 71 OK**. Selhání jen v `lib/`
  (`lib.certgen`, `lib.utorrent.client`, `lib.deluge_client.tests`), stejně jako dřív.
- **pyflakes `mylar/` před a po:** 758 → 752 hlášek. Zmizely přesně opravené: `api.py` (2× chybný počet argumentů),
  `PostProcessor.py` (2× `oneoff`), `helpers.py` (`dupehk`, `helpers`). Žádná nová. `api.py` 2× `[%]` a
  `search.py` `ComicID` zůstávají (nereprodukováno, viz tabulka).

## 3. Nálezy

| ID | Bod | Stav | Commit | Nové testy (padalo před opravou) | Poznámka |
|---|---|---|---|---|---|
| R45a | `_refreshComic`: `%` s jedním zástupným znakem a dvěma argumenty | **opraveno** | `dfe3688c` | 4 (4) + 1 kontrolní | Reprodukováno: refresh se zařadí (stub `refresh_thread` dostal sérii), pak `TypeError: not all arguments converted` → HTTP 500. Oprava: formát dostane jen `ref_line`. Odpověď je teď HTTP 200 `{"success": true, "data": "Refresh successfully submitted for ComicID <id>."}` (u víc sérií `for N items (...)`). Logika funkce beze změny. Kontrolní: neexistující ID → `_failureResponse` jako dřív. |
| R45a | `_refreshComic`: `'… in a queue of % items.'` | **opraveno** | `dfe3688c` | 1 (1) | `% i` není neplatný formát: je to `%i` s příznakem mezery, takže **nevyhodí výjimku**, jen zkomolí text na „in a queue of  3tems.“ (pyflakes to nehlásí). Test na text padal. Oprava na `%s`. Větev je v praxi mrtvá: `REFRESH_QUEUE` obsahuje slovníky, ale porovnává se s holým ComicID, takže „already queued“ nenastane (upstream, neopraveno). |
| R45a | `_changeBookType`: tři zástupné znaky, dva argumenty | **opraveno** | `dfe3688c` | 1 (1) | Reprodukováno: výjimka z `upsert` → `TypeError` místo chybové odpovědi (HTTP 500). Oprava: `(self.id, self.id, e)`, odpověď `[<id>] Unable to update Booktype for ComicID: <id>. Error returned: <chyba>`. |
| R45a | `_addProvider`: dvakrát `[%]` | **nereprodukováno, neopraveno** | – | 2 kontrolní (prošly i před) | Mělo vypsat `prov_id` (`[%s]`). Větev je ale mrtvá: `prov_line` začíná jménem providera a provider se stejným jménem skončí dřív hláškou „already exists“, takže shodný řádek do kontroly „exact details“ nikdy nedojde (kontrolní test pro newznab i torznab). |
| R45a | `_getLogs` / `_clearLogs`: `mylar.LOG_LIST` | **opraveno** | `dfe3688c` | 2 (2) | Reprodukováno: `getLogs` → `AttributeError` (HTTP 500), `clearLogs` založil nový atribut a log nevymazal. Oprava na `mylar.LOGLIST` (jako stránka Logs v `webserve`). `getLogs` vrací JSON pole `[čas, zpráva, úroveň, vlákno]`. Podle Q10 to nic nového nezpřístupní: stejný log ukazuje stránka Logs v UI bez přihlášení a API je stejně za API klíčem. |
| R45b | `requests.get` na ComicVine a pull list bez timeoutu | **opraveno** | `8c817571` | 8 (8) | Reprodukováno podvrženým `requests.get`, který zaznamená argumenty: žádný `timeout`. Oprava: konstanta `mylar.CV_TIMEOUT = (15, 90)` (connect, read) v `mylar/__init__.py`, předaná v `cv.pulldetails`, `mb.pullsearch`, `mb.storyarcinfo` a `locg.locg`. Nový config klíč nevznikl. `requests.exceptions.Timeout` skončí ve stávající větvi jako jiná síťová chyba (testy): `pulldetails` vrátí `None` a nastaví `BACKENDSTATUS_CV = 'down'` (pro `db_updater` `False`), `getComic(…, 'comic')` → `None`, takže `addComictoDB` skončí `incomplete`; `getComic(…, 'issue')` → `False`; `mb.pullsearch` a `storyarcinfo` → `None`; `locg` → `{'status': 'failure'}`, `BACKENDSTATUS_WS = 'down'` a backoff jako u jiné chyby spojení. Další úspěšné volání vrátí `BACKENDSTATUS_CV` na `up` (test). `BACKENDSTATUS_CV` se čte jen v `base.html` (ikona v UI). Volání `mylar.CVURL` jsou jen tato čtyři. Hodnota timeoutu viz kap. 6. |
| R45c | `PostProcessor`: one-off z pull listu, `oneoff['SHIPDATE']` | **opraveno** | `242be6d5` | 1 (1) | Cesta: dokončené NZB bez `issueid` (SAB/NZBGet, `apicall=False`) → řádek `nzblog` s `OneOff`, číslo není v `issues`/`annuals` ani v story arc, `ALT_PULL == 2`, řádek je ve `weekly`. Dnes `NameError` → `Process` zaloguje „Post-processing failed“ a vrátí `stop`, soubor zůstane ve složce stahování. Správně je `oneinfo` (stejně jako sousední větev pro `oneoff_issuelist`), tabulka `weekly` má sloupce `SHIPDATE` a `volume` (`locg.py`, `CREATE TABLE weekly`). Po opravě dostane `nzb_or_oneoff_pp` rok ze `SHIPDATE[:4]` a `volume` z `weekly`. V logu od 11. 9. tahle cesta není (žádné one-off PP ani `name 'oneoff'`). |
| R45c | `helpers.duplicate_filecheck`, oba soubory „Fixed“ | **opraveno** | `242be6d5` | 3 (2) | Cesta: PP čísla, které už je `Downloaded`/`Archived`, a nový i stávající soubor mají `(fN)`. Dnes spadne už `re.sub` nad seznamem z `re.findall` (`TypeError`), ve větvi „nižší verze“ by pak byl `NameError` (`dupehk`). Výjimka ukončí PP (`stop`), nic se nepřesune. Oprava: číslo verze z prvního nálezu (`fixed_file[0]`, `fixed_db_file[0]`) a `dupchk`. Vyšší `(f2)` nad `(f1)` → `dupe_src` (nový soubor zůstane), nižší → `dupe_file`. Kontrolní: jen nový soubor Fixed → `dupe_src` jako dřív. **Text logu** u vyšší verze má prohozené argumenty (`'%s is a higher "Fixed" version (%s) … existing version(%s)' % (fixed_file, fixed_db_file, filename)`), pro test oprava nutná nebyla, nechán. |
| R45c | `search.py`: `helpers.checkthe_id(ComicID, verified['chkit'])` | **nereprodukováno, neopraveno** | – | – | `checkthe_id` není limit API, je to cache ID skupiny trackeru **32P** (tabulka `ref32p`). Klíč `chkit` plní jen `auth32p` (32P), výsledky ze `search_filer` ho nemají, takže už `verified['chkit']` je `KeyError` v `try/except: pass`. I kdyby ho měly: `chkit` je slovník `{'id', 'series'}`, `checkthe_id` čte `up_vals[0]` a skončil by `KeyError` ve stejném `except`. Správná proměnná by byla `is_info['ComicID']`, ale oprava by nezměnila nic pozorovatelného (test nejde postavit, aby před opravou selhal), výběr ani blokování providerů neovlivní. Otevřená otázka 2. |
| R45c | `helpers.ddl_downloader`: `helpers.human2bytes` uvnitř `helpers` | **opraveno** | `242be6d5` | 2 (1) | Záložní výpočet běží jen u položky fronty **bez klíče** `remote_filesize`. Dnes ho mají všichni producenti (`getcomics` 0, `webserve` 0 nebo z DB, `ddl_downloader` z `ddl_info`), takže větev v produkci nenastává. Kdyby nastala, `NameError` spolkne `except` a `remote_filesize = 0`. To vypne jen „očekávanou velikost“ předanou downloaderu: GC-Main, MediaFire i Pixeldrain si pak velikost vezmou z `Content-Length` nebo `Content-Range` odpovědi, kontrola velikosti po stažení chybí, jen když server velikost nepošle. Oprava na `human2bytes(...)`: položka se `size` „40 MB“ předá 41943040 bajtů (test). Kontrolní: položka s `remote_filesize` beze změny. Přidal fork v R13 (`d2151c87`). |
| R44 | Mylar: `process.py` zapisuje do `failed` `Provider='DDL'` | **opraveno** (scénář z review nenastává) | `a9c9103a` | 1 (1) + 3 kontrolní | **Scénář z review se nereprodukuje:** všechny DDL položky jdou do PP s `apicall=True` (`ddl_downloader`, `helpers.queue_ddl_postprocess`, API `forceProcess`), a `process.post_process` pak PP spustí ve vlákně bez `join` a jeho výsledek (`mode: 'fail'`) nečte (kontrolní test s PP, které vrátí `fail`: žádný `FailedProcessor`, žádný řádek, i bez `issueid`). V logu od 11. 9. je „Initiating Failed Download handling for this download.“ **0×**. Jediná cesta do větve `FAILED_DOWNLOAD_HANDLING` s `provider='DDL'` je API **`forceProcess` s `ddl=1` a `failed=1`** (hunter `failed` neposílá, Comics `forceProcess` nevolá). Na ní test reprodukoval `Provider='DDL'`. Oprava: `process.py` převede `'DDL'` na `'DDL(GetComics)'` před `FailedProcessor`, jako `PostProcessor._revert_unmatched_pack_snatches`. Kontrolní: jiný provider (NZB) beze změny. `failed_check` nezměněn. Prakticky se tím dnes nic nemění; oprava jen sjednocuje zápis pro případ, že by tu cestu někdo použil. |
| R44 | Comics: `clear_failed` nesmaže řádek `Provider='DDL'` | **opraveno** | Comics `877ca22` | 2 (2) + 2 kontrolní | Reprodukováno na dočasné SQLite: řádek `('77', 'DDL')` po `clear_failed` zůstal. Oprava: `DELETE FROM failed WHERE ID = ? AND Provider IN (?, 'DDL')`. Mažou se jen řádky stejného `ID`; jiné ID (`77-2`, `78`) a jiný provider (`experimental`) zůstanou (test). `mark_failed` beze změny (kontrolní test). `clear_failed` volá i `requeue_missing_issues.py`, oprava platí i tam. |

## 4. R44: zápisy do `failed` pro DDL

| Místo | Kdy | `failed.ID` | `failed.Provider` | Odpovídající `ddl_info.ID` |
|---|---|---|---|---|
| `process.py` → `Failed.Process` (`FAILED_DOWNLOAD_HANDLING`), scénář z review: PP vrátí `fail` | **nenastává**, DDL PP má `apicall=True`, výsledek se nečte | (`download_info['id']` = ID položky fronty i s `-N`) | `DDL`, nově `DDL(GetComics)` | stejné |
| `process.py` → `Failed.Process` přes API `forceProcess` s `ddl=1` a `failed=1` | jen ručně, žádný klient to neposílá | `id`/`nzbid` z požadavku, jinak `nzblog.ID` (ID postu) | `DDL`, nově `DDL(GetComics)` | u jednoho čísla stejné; u sub-packu `<post>-N` proti `<post>` |
| `Failed.markFailed` přes `search.FailedMark` z `ddl_downloader` (větev `else` po neúspěšném stažení, `helpers.py` u `FailedMark`) | stažení selže bez další volby linku | `item['id']` | `item['site']` = `DDL(GetComics)` | řádek `ddl_info` se těsně předtím smaže |
| `helpers.reverse_the_pack_snatch(mark_failed=True)` z `release_exhausted_ddl_item` (Q5 z první části) | jedno číslo, všechny hosty selhaly | `ddl_item_pack_id(item)` = `pack_id`, jinak ID položky | `DDL(GetComics)` | ID položky; liší se jen u položky s `pack_id` (`<post>-N` × `<post>`) |
| `PostProcessor._revert_unmatched_pack_snatches` → `reverse_the_pack_snatch` | PP packu nenašlo žádný soubor | `pack_id` nebo `id` z `download_info` (ID postu) | `DDL` převedeno na `DDL(GetComics)` | `<post>` nebo `<post>-N` |
| `webserve.unqueueissue(smode='failed')` + `failed_handling` → `Failed.Process` (větev bez `nzb_name`) | ruční „Failed“ v UI | 1) řádek jen s `IssueID` a `Status` (ID a Provider prázdné), 2) `nzblog.ID` (ID postu) | 2) `nzblog.PROVIDER` = `DDL(GetComics)` | ID postu |
| Comics `mark_failed` | remediace, blacklist po N pokusech | `ddl_info.ID` | `ddl_info.site` (`DDL(GetComics)`) | stejné |

Závěr: `DDL` jako provider zapisuje jen `Failed.Process` z `process.py` a do té větve vede jen ruční `forceProcess`
s `failed=1`. Všechno ostatní píše `DDL(GetComics)`. `ID` v `failed` a `ddl_info` se může lišit (post × sub-pack
`<post>-N`), ale `clear_failed` dál maže jen řádky přesně s `ddl_info.ID` této položky, nic víc.
`nzblog` pro DDL píše `PROVIDER='DDL(GetComics)'` a `ID` = ID postu (`updater.nzblog`, `webserve`).

**Log od 11. 9.:** „Initiating Failed Download handling for this download.“ 0×, `[FAILED-DOWNLOAD]` 0×, „Marking as
a Failed Download“ 0×. Jiné DDL zápisy: „[REVERSE UNO] Marked pack release … as Failed“ 5× ve starém kontejneru,
všechny 18. 11. 2026 18:07–19:07 SEČ (17:07–18:07 UTC), packy 7372, 83727, 124847, 37737 a 31377, provider
`DDL(GetComics)`. V novém kontejneru nic.

**Dotaz pro uživatele** (jen čtení, kolik starých řádků `Provider='DDL'` v živé DB je; log před 11. 9. není):

```sh
docker exec mylar sqlite3 -readonly /config/mylar/mylar.db \
  "SELECT ID, Status, IssueID, ComicName, Issue_Number, DateFailed FROM failed WHERE Provider='DDL' ORDER BY DateFailed;"
```

## 5. R45: refreshComic v logu a zbylá `undefined name`

**`refreshComic` od 11. 9.** (hláška `[API-refreshComic] Successfully background submitted refresh`): **186 volání**,
185 ve starém kontejneru (11. 9. 2026 17:56 SELČ až 22. 11. 15:02 SEČ) a 1 v novém (23. 11. 5:11 SEČ, DC Connect
127365). Tři z nich pro víc sérií (25. 10. 17:26, 17:32 a 19:10 SEČ: 5, 5 a 4 série). Nejvíc 20. 11. (48) a 21. 11.
(55). Každé z nich podle kódu skončilo HTTP 500. **Traceback z formátu v logu Mylaru není** (0× „not all arguments
converted“): chybovou stránku vrací CherryPy a do logu Mylaru se nezapíše, access log v `docker logs` není.

**Zbylá `undefined name` a chybné formáty podle pyflakes** (neopravováno, rozbor subagentem nad kódem, dvě místa
ověřena ručně):

| Místo | Reálná cesta? | Poznámka |
|---|---|---|
| `webserve.py` `markreads` `markasRead` | **ano** | Hromadná akce „Read“ na stránce reading listu volá neexistující funkci (je to metoda), vždy HTTP 500. Ověřeno. |
| `mb.py` `storyarcinfo` `result` (3×) | **ano** | `NameError` spolkne `except`, obrázek a náhled story arc jsou vždy `cache/blankcover.jpg` (přepíše i správný obrázek z `arcdom`). Ověřeno. |
| `webserve.py` `order_edit` `old_reading_seq` | ano, zřídka | Úprava pořadí čtení arc s číslem nad počtem issues, HTTP 500. |
| `webserve.py` `testslack`/`testmattermost`/`testgotify` `username` | jen při selhání testu notifikace | HTTP 500 místo chybové hlášky. |
| `webserve.py` `searchit` `mode` | jen když `mb.findComic` vyhodí `TypeError` | HTTP 500 místo prázdného výsledku. |
| `series_metadata.py` `issued` | jen se `SERIES_METADATA_LOCAL` nebo požadavkem na series.json, série s `ComicYear` `0000` nebo končícím `-` | Nezachycený `NameError` ukončí přidání/refresh po rescanu nebo vlákno metadat. |
| `api.py` `_addProvider` `[%]` (2×) | ne | Mrtvá větev, viz tabulka v kap. 3. |
| `search.py` `ComicID` | ne (pozorovatelně) | Viz kap. 3 a otázka 2. |
| `updater.py` `importer` | jen bez `CV_ONLY` | Produkce běží s `CV_ONLY`. |
| `importer.py` `issis`, `dbcomic` | jen u sérií GCD (ComicID `G…`) / ne | Legacy. |
| `utorrent.py` `b16encode`/`b32decode` | jen s klientem uTorrent a magnet linkem s base32 hashem | |
| `ftpsshup.py` `paramiko` | jen se synchronizací na tablet (SFTP) při chybě `put` | |
| `torrent/clients/transmission.py` `'%h'` | jen s Transmission při chybě spojení | `ValueError` místo `False`. |
| `cache.py` `IssueID`, `webserve.py` `getComicArtwork` `comicID` | jen přímým voláním API `getArtistArt` s prázdným `id` / `/getComicArtwork` | Šablony je nevolají. |
| `helpers.py` `module` (`updatearc_locs`), `maintenance.py` `Error`, `versioncheck.py` `version` | ano, ale `NameError` spolkne `except` | Chování stejné jako zamýšlené, jen chybí log. |
| `config.py` `sys`, `exception`; `weeklypull.py` `send2read` (`myDB`, `pulldate`, `file`); `cmtagmylar.py` formát | prakticky ne | Jen ve výjimečných větvích (32P cookies, chyba mkdir, `SEND2READ` bez issueid, ComicTagger < 1.3.1, přibalený je 1.3.5). |
| `__init__.py` `maintenance`, `versioncheck`; `filechecker.py` `volumeprior_label`; `webserve.py` `previssdate`; `PostProcessor.py` `manual_arclist`; `search_filer.py` `parsed_comic`/`filecomic` | ne (falešné hlášky) | Jméno je za běhu vždy definované, nebo jde o záměrnou sondu v `try`, nebo chráněné `in locals()`. |
| `rsscheck.py` (3×), `auth32p.py` `s`, `helpers.py` `cmp`, `log`, `torrent_path`, `monitors`, `parseit.py` `ComicYear`, `mb.py` 312–322 a 611, `webserve.py` `page`, `comicinfo`, `dst_filename`, `getimage.py` `logger` | ne | Mrtvý kód (bez volajících, za `return`, nesplnitelná podmínka) nebo jen bez Pillow/32P/rTorrent/Deluge. |

**Navíc nalezeno, neopraveno (mimo seznam, pyflakes nehlásí):** `api.py` `_addProvider`,
`'protocol is required for % host entry' % providertype` (2×, newznab i torznab). `% h` je `%o` s délkovým
modifikátorem, takže host bez `http` dá `TypeError` (HTTP 500) místo chybové odpovědi. API `addProvider` nevolá ani
Comics, ani hunter.

## 6. Otevřené otázky a konzervativní volby

1. **Hodnota timeoutu `(15, 90)`.** Největší odpověď ComicVine v logu (`[CV-DEBUG] Response length`) má 274 kB
   (série 2127, 23. 9. 18:47 SELČ) a mezi předchozí hláškou a odpovědí uběhly 3 s včetně povinného 2s spánku, tedy
   asi 1 s na stažení. Chyby spojení na ComicVine v logu od 11. 9. nejsou (0× „Error fetching data from ComicVine“).
   Read timeout platí na jedno čtení ze socketu, ne na celou odpověď, takže 90 s je velká rezerva. Konstanta platí
   i pro pull list (`locg`); tam timeout navíc zapne backoff jako jiná chyba spojení. Nový config klíč nevznikl.
   Při timeoutu uprostřed stránkování issues vrátí `getComic(…, 'issue')` jen dosud načtená issue (`break`, jako
   u jiné chyby); smazání chybějících stažených issues hlídá `[REFRESH-GUARD]` ze čtvrté části.
2. **`checkthe_id` v `search.py` nechán.** Týká se jen 32P, oprava by nic nezměnila. Otázka: kód kolem `chkit`
   (32P) časem odstranit?
3. **R44 v Mylaru** opravuje jen cestu, kterou dnes nic nepoužívá. Hlavní účinek má změna v Comics, a jen pokud
   v DB staré řádky `Provider='DDL'` jsou (dotaz v kap. 4).
4. **Prohozené argumenty v logu dupechecku** (vyšší verze „Fixed“) nechány, nejsou potřeba pro opravu.
5. **Nalezené, ale neopravené chyby s reálnou cestou** (kap. 5): `markasRead` (reading list „Read“ vždy HTTP 500),
   obrázek story arc vždy prázdný, `addProvider` `% host`. Rozhodnout, jestli do další části.
6. Obchvat v hunteru (`mylar_client._get`, `refreshComic` s HTTP ≥ 400) bude po nasazení mrtvý, ale neškodný. Viz
   kap. 7.

## 7. Kontrola Comics a comics-nzb-hunteru

- **`refreshComic`:** místo HTTP 500 (CherryPy HTML stránka) vrací HTTP 200 a JSON
  `{"success": true, "data": "Refresh successfully submitted for ComicID <id>."}`. Hunter `_get`: status < 400,
  tělo není prázdné ani HTML, `r.json()` je slovník bez `success: false` → vrátí ho, `pipeline.py` zaloguje
  „refresh submitted {…}“ a čeká na dokončení refreshe jako dosud (test `test_refresh_comic_response_passes_the_hunter_client_check`).
  Neexistující ID dál vrací `success: false` (HTTP 200) → `_get` vyhodí `RuntimeError` → `pipeline.py` zaloguje
  „refreshComic error (continuing)“, nečeká na refresh a importuje (beze změny). **Zjednodušení v hunteru po
  nasazení:** výjimku `cmd != "refreshComic"` u `raise_for_status` a větev „Mylar returned non-JSON; treating as
  submitted“ lze odstranit; dokud běží starý Mylar, jsou potřeba. Nic se neměnilo.
- **`getLogs`** vrací JSON pole záznamů místo HTTP 500, **`clearLogs`** log opravdu vymaže. Ani Comics, ani hunter
  je nevolají (grep).
- **`changeBookType`** při chybě DB vrací chybovou odpověď místo HTTP 500. Nikdo z klientů ho nevolá.
- `getComic`, `getIssueInfo`, `getWanted`, `findComic`, `addComic`, `forceProcess`, `recheckFiles`, `unqueueIssue`
  beze změny. `findComic` a přidání série mají jen nový timeout (při zaseknutí CV teď vrátí prázdný výsledek místo
  nekonečného čekání).
- **Schéma, stavy, jména souborů:** beze změny. Nový sloupec ani stav nevznikl. V `failed` nové řádky
  z `forceProcess` s `failed=1` u DDL mají `Provider='DDL(GetComics)'` místo `DDL`. Comics `requeue_missing_issues`
  (`describe_mylar`) čte `failed` podle `IssueID` a vypisuje provider, nic jiného na něm nezávisí. Jména souborů
  po one-off PP z pull listu a po dupechecku dvou „Fixed“ souborů se tvoří stejně jako v ostatních větvích.

## 8. Nasazení (jen se souhlasem uživatele)

Mylar, změněné soubory (všechno Python, žádná šablona):

```sh
docker cp mylar/__init__.py mylar:/app/mylar/mylar/__init__.py
docker cp mylar/api.py mylar:/app/mylar/mylar/api.py
docker cp mylar/cv.py mylar:/app/mylar/mylar/cv.py
docker cp mylar/mb.py mylar:/app/mylar/mylar/mb.py
docker cp mylar/locg.py mylar:/app/mylar/mylar/locg.py
docker cp mylar/PostProcessor.py mylar:/app/mylar/mylar/PostProcessor.py
docker cp mylar/helpers.py mylar:/app/mylar/mylar/helpers.py
docker cp mylar/process.py mylar:/app/mylar/mylar/process.py
```

1. Po merge do `python3-dev` zkopírovat soubory jmenovitě (výš). Python moduly potřebují **`docker restart mylar`**,
   jen se souhlasem uživatele a když neběží DDL stahování ani PP (`docker logs mylar --tail 50`). Restart smaže
   stav v paměti (`REJECTED_MATCHES`).
2. Ověření v kontejneru:
   `docker exec mylar grep -c "CV_TIMEOUT" /app/mylar/mylar/__init__.py` (1),
   `docker exec mylar grep -c "timeout=mylar.CV_TIMEOUT" /app/mylar/mylar/cv.py` (1), v `mb.py` (2), v `locg.py` (1),
   `docker exec mylar grep -c "mylar.LOGLIST" /app/mylar/mylar/api.py` (2),
   `docker exec mylar grep -c "provider = 'DDL(GetComics)'" /app/mylar/mylar/process.py` (1),
   `docker exec mylar grep -c "oneinfo\['SHIPDATE'\]" /app/mylar/mylar/PostProcessor.py` (2).
3. Co hledat v logu po restartu: start bez tracebacku; další `[API-refreshComic] Successfully background submitted
   refresh` z hunteru a v jeho logu „refresh submitted {'success': True, …}“ místo náhradní odpovědi „Mylar returned
   non-JSON“. Při výpadku ComicVine „Error fetching data from ComicVine: … Read timed out. (read timeout=90)“ místo
   zaseknutého refreshe.
4. **Rebuild image** (R14, pozor v `CLAUDE.md`): po nasazení přes `docker cp` je image `mylar3:local` pozadu o tuto
   část. Před jakýmkoli recreate kontejneru nejdřív `docker build -t mylar3:local .` z aktuální `python3-dev`,
   recreate přes Dockhand jen služby `mylar` a se souhlasem.

Comics: merge větve `claude/review-2026-11-22-part5` do `main` (běží z repa, žádný kontejner). Starý Mylar s ní
funguje taky (smaže navíc jen řádky `DDL` téhož ID).

## 9. Stav po merge

