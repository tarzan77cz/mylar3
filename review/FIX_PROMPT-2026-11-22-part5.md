# Zadání: opravy nálezů z review Mylaru 2026-11-22, pátá část (chyby z upstreamu na reálných cestách, blacklist DDL)

## Kontext

**Mylar** (fork mylar3, `tarzan77cz/mylar3`) je automatický stahovač komiksů. Běží pro jednoho uživatele ostře
nad knihovnou asi 11 300 sérií. Části 1–4 oprav jsou v `python3-dev`, nasazené a image `mylar3:local` je z nich
přestavěný (FOLLOWUPS části 1–4).

Tahle část opravuje dva nízké nálezy:

| ID | Oblast | Soubory (hledej podle jmen funkcí, čísla řádků v review platí pro starší commit) |
|---|---|---|
| R45 | chyby na reálných cestách podle pyflakes (hlavně upstream) a volání ComicVine bez timeoutu | `api.py` (`_refreshComic`, `_changeBookType`, `_getLogs`, `_clearLogs`, dva formáty kolem ř. 1423 a 1470), `cv.py` (`pulldetails`), `mb.py` (hledání a story arc), `locg.py`, `PostProcessor.py` (one-off větev, `oneoff`), `helpers.py` (`duplicate_filecheck`, `dupehk`; `ddl_downloader`, `helpers.human2bytes`), `search.py` (`checkthe_id(ComicID, …)`) |
| R44 | řádek, který do `failed` zapíše PP po neúspěšném DDL, Comics `clear_failed` nesmaže | `process.py` (větev `FAILED_DOWNLOAD_HANDLING`), `Failed.py` (`Process`, `failed_check`); repo Comics `remediate_html_stubs.py` (`clear_failed`) |

**Hlavní riziko opravy:** rozbít API, které volají Comics a comics-nzb-hunter, refresh sérií, hledání a PP.
**Stahování a PP jednotlivých čísel přes GC-Main se nesmí změnit.** Opravy mají být úzké: chování mimo popsaný
scénář zůstává.

- **Pravidla repa:** `CLAUDE.md` ve worktree (Python 3.8, `sqlite3.Row` nemá `.get()`, živé služby, secrets,
  styl commitů, sekce Review, klienti API Comics a comics-nzb-hunter). Přečti ho jako první. U Comics jeho
  vlastní `CLAUDE.md` (Python 3.11 ve venv, `unittest`, conventional commits).
- **Nálezy:** řádky R44 a R45 v tabulce kap. 4 `review/REVIEW-2026-11-22.md` a rozhodnutí v kap. 11 (doplnění
  2026-11-24).
- **Rozhodnutí, která neměň:** Q10 (bezpečnost je přijaté riziko: UI běží jen ve vnitřní síti bez autentizace,
  R10, R11, R26 v upstream kódu se neopravují). Opravy z částí 1–4 (hlavně R13 fronty DDL, R16 kontext položky,
  Q5 `Wanted` + řádek ve `failed`, R17, R32 `[REFRESH-GUARD]`), viz `review/FOLLOWUPS-2026-11-22*.md`. Jejich
  testy musí dál procházet.
- **Navazující repa:**
  - `/data/Tarzan/Cursor/scripts/apps/comics-nzb-hunter`: `comics_nzb/mylar_client.py` (`_get`, kolem ř. 63–85)
    dnes bere HTTP 500 z `refreshComic` jako „zařazeno“. Volá i `getComic`, `getIssueInfo`, `getWanted`,
    `findComic`, `addComic`, `forceProcess`, `recheckFiles`, `unqueueIssue`. **Hunter neměň**, jen ověř, že
    opravená odpověď `refreshComic` (HTTP 200, JSON `success: true`) projde jeho `_get` i `pipeline.py`
    (kolem ř. 500–515) a co hunter dělá, když `refreshComic` vrátí `success: false`.
  - `/data/Tarzan/Cursor/Comics`: `remediate_html_stubs.py` (`lookup` z `ddl_info`: `ID`, `site`; `mark_failed`,
    `clear_failed`), `requeue_missing_issues.py` (`describe_mylar` čte `failed` podle `IssueID`). Comics čte
    a zapisuje Mylar DB přímo.
  - Neměň schéma tabulek, názvy stavů, tvar jmen souborů ani odpovědi API kromě toho, co nález opravuje
    (`refreshComic` místo HTTP 500 vrátí úspěch).

## Režim práce: bez dozoru, všechno v jedné session

Uživatel u toho není. **Na nic se neptej a nezastavuj se mezi nálezy**, nikdo neodpoví. Projdi oba nálezy a na
konci napiš a commitni souhrn. Když něco nejde nebo si nejsi jistý, zvol konzervativnější variantu (ta, po které
se žádná data neztratí a nic se nepřesune), zapiš ji do souhrnu jako otevřenou otázku a pokračuj.

## Pravidla

1. **Izolace.**
   - Mylar: `git -C /data/Tarzan/Cursor/Mylar worktree add -b claude/review-2026-11-22-part5
     /data/Tarzan/Cursor/Mylar-review-2026-11-22-part5 python3-dev`.
   - Comics (jen R44): `git -C /data/Tarzan/Cursor/Comics worktree add -b claude/review-2026-11-22-part5
     /data/Tarzan/Cursor/Comics-review-2026-11-22-part5 main`.
   - Pracuj jen tam. Hlavní stromy nepřepínej a neměň (ani netrackované soubory). Nepushuj, nemerguj,
     nepřepisuj historii. comics-nzb-hunter jen čti.
2. **Review soubory** (`REVIEW_PROMPT-*`, `REVIEW-*`, `FIX_PROMPT-*`, starší `FOLLOWUPS-*`) neměň, výsledky patří
   do nového `review/FOLLOWUPS-2026-11-22-part5.md` v Mylar worktree.
3. **Na živou aplikaci nesahej:** žádný `docker cp`, `docker restart`, `docker exec` do kontejneru `mylar`,
   žádné volání Mylar API ani webových akcí, žádné dotazy do `mylar.db`, nic v `/comics`, `/downloads` a
   `/config`. Nečti `/config/mylar/config.ini`, `env` kontejneru ani `docker inspect`. Žádná síť (ComicVine,
   GetComics, pull list); výjimka je `pip install` pytest a pyflakes do dočasného kontejneru. Image
   `mylar3:local` nepřestavuj a nepřetaguj. Comics skripty nespouštěj v režimu `run`/`--apply`. **Číst smíš**
   `docker logs mylar` (od 22. 11.) a `docker logs mylar-2026-09-11` (zastavený starý kontejner, historie
   od 11. 9. do 22. 11.); časy v nich jsou UTC, do souhrnu je převeď na pražský čas.
4. **Opravuj jen R44 a R45.** Ostatní (R28, R34, R37, R40, R43 a přijaté R10, R11, R26, R35, R36) nech být, i když
   na ně narazíš. Žádné refaktoringy ani vylepšení navíc. `lib/` neměň. Další `undefined name` z pyflakes mimo
   seznam níže neopravuj, jen je v souhrnu vypiš s jednou větou, jestli na ně vede reálná cesta.
5. **Test dřív než oprava.** Každý test musí před opravou selhat a po ní projít. Když neselže, nález se
   nereprodukuje: neopravuj ho a napiš proč. Ověř to aspoň u `refreshComic` a R44 i odložením změn (`git stash`
   jen ve svém worktree). Kontrolní testy, které procházejí i před opravou, tak v souhrnu označ.
6. **Commity.**
   - Mylar: commit na bod nebo úzce související skupinu (R45 klidně ve 3–5 commitech: API, timeouty ComicVine,
     PP a dupecheck, fronta DDL), anglicky, jedna věta v rozkazovacím způsobu, co a proč, ID na konci, např.
     „Answer refreshComic with success instead of HTTP 500 after queueing the refresh, so API clients see the
     real result (R45)“.
   - Comics: conventional commit podle jeho `CLAUDE.md` (předmět do 72 znaků, např. `fix: clear the DDL
     blacklist row Mylar's post-processing writes (R44)`), podrobnosti v těle.
7. **Python 3.8 v Mylaru.** Nic z 3.9+ (`match`, `X | Y`, `list[str]` mimo řetězce, `removeprefix`, `dict | dict`,
   `zoneinfo`). Na `sqlite3.Row` nikdy `.get()` ani `'col' in row`; sloupce přes `row['col']`, `row.keys()` nebo
   `try/except (KeyError, IndexError)`.
8. **Nic nemaž natrvalo.** Žádný soubor z repa se neodstraňuje. Kód nesmí nově mazat soubory ani složky
   v knihovně. Nová mazání řádků z `failed` jen v rozsahu R44.

## Testy a prostředí

Worktree Mylaru leží na Z2 pod `/share/Tarzan/Cursor/Mylar-review-2026-11-22-part5`, Docker socket patří Z2:

```sh
docker run --rm -e PYTHONDONTWRITEBYTECODE=1 -v /share/Tarzan/Cursor/Mylar-review-2026-11-22-part5:/src:ro mylar3:local \
  sh -c "pip install -q pytest >/dev/null 2>&1; cd /src && python3 -m pytest -q -p no:cacheprovider tests"
docker run --rm -e PYTHONDONTWRITEBYTECODE=1 -v /share/Tarzan/Cursor/Mylar-review-2026-11-22-part5:/src:ro mylar3:local \
  sh -c "pip install -q pytest >/dev/null 2>&1; cd /src && python3 -m pytest -q -p no:cacheprovider tests_db"
```

- **Výchozí stav nejdřív:** na čistém worktree `tests` **131 passed**, `tests_db` **176 passed**. Zapiš do
  souhrnu.
- Nové testy Mylaru patří do `tests_db/` (skutečný balík `mylar`, dočasná SQLite, `mylar.DATA_DIR` v tempu,
  vzory v `tests_db/conftest.py`, `fakes.py`, `cvxml.py`). HTTP podvrhni (`requests.get` přes `monkeypatch`),
  `importer.refresh_thread` nahraď stubem.
- Comics: jen moduly, kterých se změna týká, plus celý příkaz z jeho `CLAUDE.md`, z worktree s absolutními
  cestami: `RAR_PATH=/data/Tarzan/Cursor/Comics/rar/rar/rar /data/Tarzan/Cursor/Comics/venv/bin/python -m
  unittest …`. Výchozí a konečný počet zapiš.
- Před každým commitem Mylaru: obě sady testů a `ast.parse` změněných souborů v image (příkaz v `CLAUDE.md`).
- Na konci: import všech modulů `mylar.*` v 3.8.2 (`sys.path[:0] = ['/src', '/src/lib']`, vzor
  `.scratch/review-2026-11-22/try_imports.py` v hlavním stromu), musí zůstat 71 ze 71. A pyflakes nad změněnými
  soubory: opravené `undefined name` a chybné `%` formáty zmizí, žádné nové nepřibude (srovnej před a po).

## Nálezy a co přesně udělat

Pořadí: R45 (API) → R45 (ComicVine timeouty) → R45 (zbytek) → R44.

### R45a: chybné `%` formáty a `LOG_LIST` v `api.py`

- **`_refreshComic`:** `self._successResponse('Refresh successfully submitted %s.' % (self.id, ref_line))` má
  jeden zástupný znak a dva argumenty. Refresh se zařadí, pak `TypeError` a klient dostane HTTP 500. Oprav na
  jeden argument (`ref_line`). Stejná funkce: větev pro víc už zařazených sérií má `'… in a queue of % items.'`
  (`% i` je neplatný formát), oprav na `%s`. Jinak logiku funkce neměň.
- **`_changeBookType`:** `'[%s] Unable to update Booktype for ComicID: %s. Error returned: %s' % (self.id, e)`,
  tři zástupné znaky, dva argumenty. Oprav.
- **Dva formáty s `%]`** (pyflakes „unsupported format character ']'“, kolem ř. 1423 a 1470): zjisti, co mají
  vypsat, a oprav.
- **`_getLogs` / `_clearLogs`:** používají `mylar.LOG_LIST`, které neexistuje (logger plní `mylar.LOGLIST`).
  `getLogs` končí `AttributeError`, `clearLogs` jen založí nový atribut a log nevymaže. Oprav na `LOGLIST`. Podle
  Q10 to nic nového nezpřístupní: stejný log ukazuje stránka Logs v UI, které běží bez přihlášení. Zapiš to.
- **Ze logů zjisti** (`docker logs mylar` a `mylar-2026-09-11`): kolikrát od 11. 9. přišlo `refreshComic`
  (hlášky `[API-refreshComic] Successfully background submitted refresh`) a jestli je v logu traceback
  z tohoto formátu. Do souhrnu počet a rozsah dat.
- **Testy:** `_refreshComic` s jednou sérií v DB → `self.data` je úspěch s textem, žádná výjimka, refresh se
  zavolal se správnou sérií; víc sérií, z nichž některé už jsou ve frontě → žádná výjimka; neexistující ID →
  `_failureResponse` jako dnes (kontrolní). `_changeBookType` s `upsert`, který vyhodí výjimku → chybová
  odpověď s textem výjimky. `getLogs` vrátí obsah `mylar.LOGLIST`, `clearLogs` ho vyprázdní. Ověř i tvar celé
  HTTP odpovědi `refreshComic` (jak ji `Api.fetchData` serializuje) proti `mylar_client._get` hunteru: dnešní
  obchvat pro HTTP 500 zůstane mrtvý, ale neškodný. Napiš, jestli ho jde v hunteru později zjednodušit.

### R45b: volání ComicVine a pull listu bez timeoutu

- `cv.pulldetails` (`requests.get(PULLURL, …)`), `mb.py` (hledání série a story arc, dvě volání) a `locg.py`
  (pull list) volají `requests.get` bez `timeout`. Zaseknuté spojení zablokuje navždy vlákno refreshe, DB
  updateru, hledání nebo pull listu.
- Oprava: přidej `timeout` (jedna konstanta v kódu, např. `(15, 90)` jako connect/read; hodnotu zdůvodni podle
  toho, jak dlouho podle logu trvají největší odpovědi CV, pokud to z logu jde zjistit). Nový config klíč
  nezakládej. Ověř, že `requests.exceptions.Timeout` skončí ve stávající větvi `except Exception` stejně jako
  jiná síťová chyba (vrátí `None`/`False`, refresh skončí `incomplete`, nic se nesmaže) a že
  `BACKENDSTATUS_CV = 'down'` se jen zobrazuje v UI a další úspěšné volání ho vrátí na `up`. Projdi i jiná volání
  `mylar.CVURL` v `mylar/` a ty, které vedou z refreshe, DB updateru, hledání nebo přidání série, oprav stejně;
  ostatní jen vypiš.
- **Testy:** podvržený `requests.get`, který kontroluje, že dostal `timeout`, a jednou vyhodí
  `requests.exceptions.Timeout` → `pulldetails` vrátí jako u jiné chyby, žádná výjimka ven. To samé pro `mb.py`
  a `locg.py`, aspoň po jednom testu.

### R45c: zbylé chyby na reálných cestách

Před každou opravou napiš do souhrnu, kudy se na řádek dá dostat a co se dnes stane.

- **`PostProcessor.py`, one-off větev s `oneinfo` z pull listu:** `OSeriesYear = oneoff['SHIPDATE'][:4]`
  a `OSeriesVolume = oneoff['volume']`, `oneoff` neexistuje (`NameError`). Zjisti, jestli je správně `oneinfo`
  a jestli má řádek klíče `SHIPDATE` a `volume` (tabulka `weekly`), a oprav.
- **`helpers.py`, `duplicate_filecheck`, větev, kdy jsou „Fixed“ (`(f1)`, `(f2)`) oba soubory:** `dupehk`
  (`NameError`, správně `dupchk`) a navíc `re.sub` nad seznamem z `re.findall` (`TypeError`). Oprav obojí, aby
  se porovnala čísla verzí a vyšší verze zůstala. Pozor na text logu, který má prohozené argumenty: oprav jen
  když je to nutné pro test, jinak to napiš.
- **`search.py`:** `helpers.checkthe_id(ComicID, verified['chkit'])` je v `try/except: pass`, `ComicID` v té
  funkci není, takže se `checkthe_id` nikdy nezavolá. Zjisti, co `checkthe_id` dělá (limit API hitů providera?),
  kterou proměnnou tam předat, a jestli zapnutí změní chování hledání. Když by změnilo, jaký provider se použije
  nebo zablokuje, **neopravuj**, zapiš jako otevřenou otázku.
- **`helpers.py`, `ddl_downloader`, záložní výpočet velikosti:** `helpers.human2bytes(...)` uvnitř modulu
  `helpers` je `NameError`, `except Exception` ho spolkne a `remote_filesize` je 0. Přidal to fork v R13
  (`d2151c87`), ne upstream, v review to není. Zjisti, kdy položka fronty nemá `remote_filesize` a co
  `remote_filesize = 0` vypne (kontrola velikosti po stažení?). Oprav na `human2bytes(...)` a zapiš to pod R45.
- **Testy:** na každý bod aspoň jeden, který před opravou spadne na `NameError`/`TypeError` nebo ukáže špatný
  výsledek.

### R44: blacklist DDL, který Comics nesmaže

- Scénář z review: PP po DDL selže (`mode: 'fail'`), `process.py` při `FAILED_DOWNLOAD_HANDLING` předá
  `FailedProcessor` `prov=self.download_info['provider']` a `id=self.download_info['id']`. Pro DDL je provider
  `'DDL'` (`helpers.ddl_download_info`, zařazení PP v `helpers.py` s `'download_info': {'provider': 'DDL',
  'id': ddl_id}`, `api.py` `forceProcess`) a ID je ID položky fronty (u sub-packu `<post>-N`). `Failed.Process` zapíše do `failed`
  `ID`, `Provider='DDL'`, `NZBName`. Comics `clear_failed` maže `WHERE ID=? AND Provider=?` s `ddl_info.site`
  (`DDL(GetComics)`), takže řádek zůstane. `failed_check` hledá jen podle `ID`, takže položka zůstane na
  blacklistu i po requeue z Comics.
- **Nejdřív zjisti a do souhrnu dej tabulku** všech míst, která zapisují do `failed` pro DDL (`Failed.Process`,
  `Failed.markFailed` přes `search.FailedMark`, `helpers.reverse_the_pack_snatch`, Q5 z první části,
  `webserve` kolem `smode == 'failed'`, Comics `mark_failed`): jaké `ID` a `Provider` zapíšou a jaké `ID` má
  odpovídající řádek `ddl_info` (`ddl_info.ID` je ID položky fronty i se `-N`, nebo ID postu?). Z toho vyplyne,
  co má `clear_failed` mazat.
- **Oprava v Mylaru:** `process.py` před `FailedProcessor` převede provider `'DDL'` na `'DDL(GetComics)'`, stejně
  jako `PostProcessor._revert_unmatched_pack_snatches`. Nové řádky pak mají stejný `Provider` jako `ddl_info.site`
  a ostatní DDL zápisy. `failed_check` neměň.
- **Oprava v Comics:** `clear_failed` smaže i starší řádky, které Mylar zapsal s `Provider='DDL'`, tj. `WHERE ID=?
  AND Provider IN (?, 'DDL')`. Když z tabulky výše vyjde, že se `ID` v `failed` a `ddl_info` liší (post vs.
  sub-pack), napiš to a zvol variantu, která smaže jen řádky téhle položky, nic víc. `mark_failed` neměň, pokud
  to tabulka nežádá.
- Kolik řádků `Provider='DDL'` je dnes v živé DB, nezjišťuj (DB je zakázaná). V souhrnu dej uživateli dotaz
  jen pro čtení (`SELECT … FROM failed WHERE Provider='DDL'`), který si může spustit sám.
- Ze logů zjisti, kolikrát od 11. 9. proběhlo `Initiating Failed Download handling for this download.` u DDL
  (hlášky kolem, `prov  : DDL`) a pro jaké položky.
- **Testy:**
  - Mylar: PP vrátí `mode: 'fail'` u DDL položky s `FAILED_DOWNLOAD_HANDLING` → řádek ve `failed` má
    `Provider='DDL(GetComics)'` a ID položky (podvrhni `PostProcessor` a `queueit`, ať nic nehledá). Kontrolní:
    jiný provider (např. NZB) se nemění.
  - Comics (`unittest` + dočasná SQLite se sloupci tabulky `failed`, vzor `test_remediate_apply_plan.py`,
    `test_requeue_missing_issues.py`): řádek `Provider='DDL'` se stejným `ID` → `clear_failed` ho smaže; řádek
    `DDL(GetComics)` → smaže jako dnes (kontrolní); řádek jiného `ID` nebo jiného providera (NZB) zůstane.

## Na konci

1. Obě sady testů Mylaru, `ast.parse` změněných souborů, import všech modulů v 3.8.2, pyflakes před a po.
   Testy Comics.
2. Souhrn **`review/FOLLOWUPS-2026-11-22-part5.md`** v Mylar worktree (česky, kód v originále, časy pražsky):
   - prostředí: oba worktree, větve, základy (`python3-dev`, Comics `main` a jejich commity), image
     `mylar3:local` a jeho ID, že se nic nenasadilo ani nerestartovalo,
   - výchozí a konečný stav testů (Mylar obě sady, Comics),
   - tabulka ID | Bod | Stav (opraveno / neopraveno / nereprodukováno) | Commit | Nové testy (kolik padalo před
     opravou) | Poznámka (jak reprodukováno, co oprava dělá, dopad na API, refresh, hledání, PP),
   - u R44 tabulka zápisů do `failed` a dotaz pro uživatele; u R45 počty z logu a seznam zbylých `undefined name`,
   - otevřené otázky a konzervativní volby (minimálně `checkthe_id`, hodnota timeoutu),
   - kontrola Comics a comics-nzb-hunteru: co se mění v odpovědích API (`refreshComic`, `getLogs`, chybové
     odpovědi), že schéma, stavy a jména souborů zůstávají, a co by šlo zjednodušit v hunteru (nic neměnit),
   - postup nasazení pro uživatele: změněné soubory Mylaru jmenovitě pro `docker cp` podle `CLAUDE.md`; u Python
     modulů je potřeba **`docker restart mylar`** (jen se souhlasem a když neběží DDL ani PP); co ověřit v logu
     po restartu; že po nasazení je potřeba rebuild image (R14, pozor v `CLAUDE.md`). Comics: merge do `main`
     (běží z repa, žádný kontejner),
   - prázdná sekce „Stav po merge“.
3. Commitni souhrn v Mylar worktree. Nepushuj, nemerguj, worktree nech být.
4. Poslední zprávou napiš, ve kterých repech a na které větvi jsi commitnul, a stav testů.
