# Zadání: opravy nálezů z review Mylaru 2026-11-22, šestá část (watchdog DDL, alt_match, fronta PP, zátěž, SQLite)

## Kontext

**Mylar** (fork mylar3, `tarzan77cz/mylar3`) je automatický stahovač komiksů. Běží pro jednoho uživatele ostře
nad knihovnou asi 11 300 sérií. Části 1–5 oprav jsou v `python3-dev`, nasazené a image `mylar3:local` je z nich
přestavěný (FOLLOWUPS části 1–5).

Tahle část opravuje pět nízkých nálezů, pořadí od nejužšího k tomu, co se dotýká všeho:

| ID | Oblast | Soubory (hledej podle jmen funkcí, čísla řádků v review platí pro starší commit) |
|---|---|---|
| R43 | watchdog DDL pošle do PP soubor, který se ještě zpracovává | `helpers.py` (`ddl_watchdog`, kontrola položek `Downloading`; `validate_downloaded_archive`; `queue_ddl_postprocess`), `downloaders/mediafire.py`, `downloaders/pixeldrain.py` (volání `zip_zip`), `getcomics.py` (`zip_zip`) |
| R28 | alt_match ve `verified_matches` před primární shodou → ID, pack a název z jiného příspěvku než link | `search_filer.py` (vracení alt_match s `downloadit=False`), `search.py` (`verification`, `searcher`: `comicinfo[0]['nzbid']`, `['pack']`, `['pack_issuelist']`, `['nzbtitle']`) |
| R34 | `postprocess_main` uvolní `APILOCK` 5 s po startu PP, PP běží dál v odpojeném vlákně | `helpers.py` (`postprocess_main`), `process.py` (`post_process`, větev `apicall`/`issueid` se `threading.Thread(...).start()` bez `join`) |
| R40 | zátěž: `REJECTED_MATCHES` bez omezení; `comicDetails` volá ComicVine synchronně při každém zobrazení série bez obálky | `search_filer.py` (`_add_or_update_rejected_match`, prořezávání kolem `count_offerable_rejected_matches`), `webserve.py` (`comicDetails`, `cv.getComic(…, 'image')` a `helpers.getImage`) |
| R37 | SQLite vrstva: tichá ztráta zápisu po vyčerpání pokusů, `upsert` ve dvou zámcích | `db.py` (`DBConnection.fetch`, `action`, `upsert`, `db_lock`) |

**Hlavní riziko opravy:** R34 a R37 jsou na cestě každého PP a každého zápisu do DB. Rozbít je znamená zastavit
stahování, PP i UI. **Stahování a PP jednotlivých čísel přes GC-Main se nesmí změnit** (kromě toho, že PP z fronty
poběží po jednom, R34). Opravy mají být úzké: chování mimo popsaný scénář zůstává.

- **Pravidla repa:** `CLAUDE.md` ve worktree (Python 3.8, `sqlite3.Row` nemá `.get()`, živé služby, secrets,
  styl commitů, sekce Review, klienti API Comics a comics-nzb-hunter). Přečti ho jako první.
- **Nálezy:** řádky R28, R34, R37, R40, R43 v tabulce kap. 4 `review/REVIEW-2026-11-22.md` a rozhodnutí v kap. 11
  (doplnění 2026-11-24 odpoledne). Reprodukce z review jsou v hlavním stromu
  `/data/Tarzan/Cursor/Mylar/.scratch/review-2026-11-22/` (R28: `ui/repro_verification.py`; R34: `cv/pp_overlap.py`).
- **Rozhodnutí, která neměň:** Q10 a přijatá rizika (R10, R11, R26, R35, R36, upstream řádky se stejnými texty,
  nové chyby z páté části, kód 32P). Opravy z částí 1–5 (hlavně R13 fronta DDL, R16 kontext položky, Q5 `Wanted`
  + řádek ve `failed`, R17, R32 `[REFRESH-GUARD]`, R44 provider `DDL(GetComics)`, R45), viz
  `review/FOLLOWUPS-2026-11-22*.md`. Jejich testy musí dál procházet.
- **Rozhodnutí uživatele k této části (kap. 11):**
  - **R34:** fronta PP počká na dokončení vlákna PP, **timeout 2 h**, po něm WARN a fronta pokračuje.
  - **R37:** úzce. Zápis ztracený po vyčerpání pokusů zalogovat jako ERROR (tabulka a text dotazu, **bez hodnot**),
    `upsert` v jednom zámku. **Bez změny schématu** (žádné UNIQUE, žádné indexy) a **bez WAL**.
  - **R40:** jen strop a stáří `REJECTED_MATCHES` a `comicDetails` bez synchronního volání CV při každém zobrazení.
    Wanted tabulku (počítání před stránkováním, auto-refresh 30 s) **neměň**, je to přijaté riziko.
- **Navazující repa (jen číst, neměnit):**
  - `/data/Tarzan/Cursor/scripts/apps/comics-nzb-hunter`: `comics_nzb/pipeline.py` po `forceProcess` čeká na stav
    `Downloaded` (kolem ř. 470–560, nastavení čekání v `config.py`). Zjisti, jak dlouho čeká, a co pro něj znamená,
    že PP z fronty teď poběží po jednom (R34).
  - `/data/Tarzan/Cursor/Comics`: `remediate_html_stubs.py` čte `ddl_info` (`ID`, `site`) podle `issueid` a zapisuje
    do `failed`; čte Mylar DB přímo (sqlite3 nebo `docker exec`). Zkontroluj dopad R28 (jiné `ddl_info.ID`) a R37.
  - Neměň schéma tabulek, názvy stavů, tvar jmen souborů ani odpovědi API.

## Režim práce: bez dozoru, všechno v jedné session

Uživatel u toho není. **Na nic se neptej a nezastavuj se mezi nálezy**, nikdo neodpoví. Projdi všech pět nálezů
a na konci napiš a commitni souhrn. Když něco nejde nebo si nejsi jistý, zvol konzervativnější variantu (ta, po které
se žádná data neztratí a nic se nepřesune ani nesmaže), zapiš ji do souhrnu jako otevřenou otázku a pokračuj.

## Pravidla

1. **Izolace.** `git -C /data/Tarzan/Cursor/Mylar worktree add -b claude/review-2026-11-22-part6
   /data/Tarzan/Cursor/Mylar-review-2026-11-22-part6 python3-dev`. Pracuj jen tam. Hlavní strom nepřepínej
   a neměň (ani netrackované soubory). Nepushuj, nemerguj, nepřepisuj historii. Comics a comics-nzb-hunter jen čti.
2. **Review soubory** (`REVIEW_PROMPT-*`, `REVIEW-*`, `FIX_PROMPT-*`, starší `FOLLOWUPS-*`) neměň, výsledky patří
   do nového `review/FOLLOWUPS-2026-11-22-part6.md` ve worktree.
3. **Na živou aplikaci nesahej:** žádný `docker cp`, `docker restart`, `docker exec` do kontejneru `mylar`,
   žádné volání Mylar API ani webových akcí, žádné dotazy do `mylar.db`, nic v `/comics`, `/downloads` a
   `/config`. Nečti `/config/mylar/config.ini`, `env` kontejneru ani `docker inspect`. Žádná síť (ComicVine,
   GetComics, Pixeldrain, MediaFire, pull list); výjimka je `pip install` pytest a pyflakes do dočasného kontejneru.
   Image `mylar3:local` nepřestavuj a nepřetaguj. **Číst smíš** `docker logs mylar` (od 24. 11. 10:54 SEČ) a
   `docker logs mylar-2026-09-11` (zastavený starý kontejner, 11. 9. až 22. 11.); časy v nich jsou UTC, do souhrnu
   je převeď na pražský čas.
4. **Opravuj jen R43, R28, R34, R40 (dvě části výše) a R37 (úzce).** Nic dalšího, ani když na to narazíš: zapiš
   do souhrnu. Žádné refaktoringy ani vylepšení navíc. `lib/` neměň.
5. **Test dřív než oprava.** Každý test musí před opravou selhat a po ní projít. Když neselže, nález se
   nereprodukuje: neopravuj ho a napiš proč. Ověř to aspoň u R34, R37 a R43 i odložením změn (`git stash` jen
   ve svém worktree). Kontrolní testy, které procházejí i před opravou, tak v souhrnu označ. Testy souběhu (R34,
   R37) musí být deterministické (události, bariéry, podvržené funkce), ne „pusť 100 vláken a doufej“.
6. **Commity.** Commit na nález (R40 klidně dva: `REJECTED_MATCHES` a `comicDetails`), anglicky, jedna věta
   v rozkazovacím způsobu, co a proč, ID na konci, např. „Let the post-processing queue wait for the running
   post-processing to finish, so two post-processing runs no longer overlap (R34)“.
7. **Python 3.8.** Nic z 3.9+ (`match`, `X | Y`, `list[str]` mimo řetězce, `removeprefix`, `dict | dict`,
   `zoneinfo`). Na `sqlite3.Row` nikdy `.get()` ani `'col' in row`; sloupce přes `row['col']`, `row.keys()` nebo
   `try/except (KeyError, IndexError)`.
8. **Nic nemaž natrvalo.** Žádný soubor z repa se neodstraňuje. Kód nesmí nově mazat soubory ani složky
   v knihovně ani ve složce stahování, ani řádky v DB.

## Testy a prostředí

Worktree leží na Z2 pod `/share/Tarzan/Cursor/Mylar-review-2026-11-22-part6`, Docker socket patří Z2:

```sh
docker run --rm -e PYTHONDONTWRITEBYTECODE=1 -v /share/Tarzan/Cursor/Mylar-review-2026-11-22-part6:/src:ro mylar3:local \
  sh -c "pip install -q pytest >/dev/null 2>&1; cd /src && python3 -m pytest -q -p no:cacheprovider tests"
docker run --rm -e PYTHONDONTWRITEBYTECODE=1 -v /share/Tarzan/Cursor/Mylar-review-2026-11-22-part6:/src:ro mylar3:local \
  sh -c "pip install -q pytest >/dev/null 2>&1; cd /src && python3 -m pytest -q -p no:cacheprovider tests_db"
```

- **Výchozí stav nejdřív:** na čistém worktree `tests` **131 passed**, `tests_db` **204 passed**. Zapiš do souhrnu.
- Nové testy patří do `tests_db/` (skutečný balík `mylar`, dočasná SQLite, `mylar.DATA_DIR` v tempu, vzory
  v `tests_db/conftest.py`, `fakes.py`, `test_ddl_queue_state.py`, `test_single_exhausted.py`,
  `test_upstream_name_errors.py`, `test_failed_provider.py`). HTTP podvrhni, `time.sleep` nahraď.
- Před každým commitem: obě sady testů a `ast.parse` změněných souborů v image (příkaz v `CLAUDE.md`).
- Na konci: import všech modulů `mylar.*` v 3.8.2 (vzor `.scratch/review-2026-11-22/try_imports.py` v hlavním
  stromu, archivní kopie v `/data/Tarzan/Cursor/_archive/2026-11-24-mylar-review-part5/`), musí zůstat 71 ze 71.
  A pyflakes nad `mylar/` před a po: žádná nová hláška.

## Nálezy a co přesně udělat

Pořadí: R43 → R28 → R34 → R40 → R37. U každého nejdřív do souhrnu napiš, kudy se na problém dá dostat a co se
dnes stane.

### R43: watchdog DDL a soubor, který se ještě zpracovává

- Scénář z review: `ddl_watchdog` každou minutu projde položky `ddl_info` se stavem `Downloading`. Když soubor
  existuje a `validate_downloaded_archive` ho uzná, nastaví `Completed` a pošle ho do PP (`queue_ddl_postprocess`).
  (a) MediaFire/Pixeldrain po stažení zipu volají `zip_zip` (rozbalení) ještě ve stavu `Downloading`; rozbalování
  delší než minuta → watchdog pošle do PP zip, který `zip_zip` vzápětí smaže, a downloader pak pošle do PP i složku =
  dvojí PP. (b) `.pdf`/`.cb7` při neznámé velikosti se neověřují, takže useknutý soubor projde jako hotový.
- **Nejdřív zjisti:** co přesně `validate_downloaded_archive` dělá pro zip, `.cbz`/`.cbr`, `.pdf`, `.cb7` se
  známou a neznámou velikostí; kdy je položka `Downloading` a kdy ji downloader přepne; proč watchdog fáze 1
  existuje (obnova po restartu, kdy downloader už neběží, a soubor, který downloader dotáhl, ale nezapsal stav).
  Ze logů zjisti, kolikrát od 11. 9. watchdog položku dokončil (`[DDL-WATCHDOG] File … is already downloaded`),
  u kterých hostů a přípon, a jestli kolem toho bylo dvojí PP.
- **Oprava:** watchdog nesmí dokončit položku, kterou DDL downloader **právě zpracovává** (stahování, rozbalení,
  zařazení do PP). Zvol nejužší spolehlivý signál (např. ID položky, kterou smyčka `ddl_downloader` drží od začátku
  zpracování do konce, nastavené a uvolněné v `try/finally`) a zdůvodni ho. Soubory, jejichž úplnost nejde ověřit
  (neznámá velikost a formát bez kontroly struktury), watchdog jako hotové **nebere**; nech je větvi „stuck“, která
  je po 10 minutách vrátí do fronty, nebo zvol konzervativnější variantu a zdůvodni ji. Nic nemaž.
- **Testy:** zip, který se právě rozbaluje (položka je zpracovávaná) → watchdog ji nedokončí a nic nepošle do PP;
  useknuté `.pdf` s neznámou velikostí → nedokončí. Kontrolní: po restartu (žádná položka se nezpracovává) úplné
  `.cbz` ve stavu `Downloading` watchdog dokončí a pošle do PP jako dnes; aktivně stahovaný soubor přeskočí jako dnes.

### R28: alt_match před primární shodou

- Scénář z review (spuštěno `ui/repro_verification.py`): fork vrací single-issue alt_match jako shodu
  s `downloadit=False` (upstream je zahazoval). Když alt_match stojí ve `verified_matches` před primární shodou,
  `searcher` vezme `nzbid`, `pack`, `pack_issuelist` a název z `comicinfo[0]` (alt_match), link z primární shody.
  Pak `nzblog`, `ddl_info.ID` a případný řádek `failed` (Q5) dostanou ID jiného příspěvku, než se stahuje.
- **Nejdřív zjisti:** kde se `verified_matches` a `comicinfo` skládají a proč může alt_match předběhnout primární
  shodu; jak často je v logu od 11. 9. alt_match uložen (`[REJECTED-MATCHES] Successfully stored alt_match`) a jestli
  v tom samém hledání pak proběhl snatch.
- **Oprava:** link, `nzbid`, `pack`, `pack_numbers`, `pack_issuelist` a název stahovaného výsledku musí pocházet
  **z téže položky**. Zvol nejužší místo (pořadí ve `verified_matches`, nebo `comicinfo` sestavené z položky, která
  se stahuje) a zdůvodni ho. Ukládání alt_match do odmítnutých shod (UI „Rejected matches“) zůstává.
- **Testy:** podle `repro_verification.py` (alt_match s ID 100 před primární shodou s ID 200) → `nzblog`/`ddl_info`
  a předané `nzbid` mají ID 200 a link `?p=200`; alt_match zůstane v `REJECTED_MATCHES`. Kontrolní: bez alt_match
  beze změny; alt_match pack (cizí `pack_issuelist`) se nepoužije.

### R34: souběžné PP z fronty

- Scénář z review: `postprocess_main` zavolá `process.Process(...).post_process()`; pro `apicall`/`issueid`
  spustí `post_process` PP ve vlákně bez `join` a vrátí se, `postprocess_main` po `sleep(5)` ve `finally` uvolní
  `APILOCK` a vezme další položku. Delší PP (pack) tak může běžet souběžně s dalším. Review: ve 3denním vzorku
  0 překryvů (`cv/pp_overlap.py`); zopakuj tu analýzu nad celým logem od 11. 9. (počet PP, nejdelší PP, počet
  překryvů), časy pražsky.
- **Oprava podle rozhodnutí:** položka z fronty PP se nevezme, dokud předchozí vlákno PP neskončí, nejdéle **2 h**.
  Po timeoutu WARN se jménem položky a fronta pokračuje (vlákno se nezabíjí). Mechanismus zvol tak, aby se neměnilo
  nic jiného: ruční PP z UI (`Manual Run`, `MANUAL_PP_LOCK`, `MANUAL_PP_STATUS`), cesta `failed`, `retry_outside`,
  `PP_DDL_IDS`/`PP_CURRENT_DDL_IDS`, výsledek pro neapicall cestu (dnes `join` a čtení fronty). Timeout jako
  konstanta v kódu, ne config klíč.
- **Hunter:** zjisti, jak dlouho po `forceProcess` čeká na `Downloaded`, a napiš, co se stane, když PP čeká ve
  frontě za jiným (nic neměň).
- **Testy (deterministické):** dvě položky ve frontě, první PP blokuje na `threading.Event` → druhá nezačne, dokud
  se událost nenastaví; PP, které nedoběhne do timeoutu (timeout v testu zkrácený monkeypatchem) → WARN a další
  položka se zpracuje. Kontrolní: jedna položka projde jako dnes, `APILOCK` je po ní `False`.

### R40: `REJECTED_MATCHES` a `comicDetails`

- **`REJECTED_MATCHES`** (paměť, slovník `{IssueID: [shoda, …]}` s celým `entry`/`verified_data`, čistí se jen
  ručně nebo restartem). Nejdřív zjisti, jak se položky přidávají, aktualizují a prořezávají, a co z nich čte UI
  (Wanted, výběr odmítnuté shody, `count_offerable_rejected_matches`). **Oprava:** strop počtu shod na issue a stáří.
  Hodnoty zvol a zdůvodni (výchozí návrh: nejvýš 50 na issue, starší než 7 dní pryč); u stropu zahazuj nejstarší
  (nebo nejméně relevantní, zdůvodni). Čas přidání ukládej do slovníku shody (jen paměť, žádný nový sloupec).
  Prořezávej při přidání; shodu, kterou uživatel právě vybírá, neodstraňuj jinak než dnes. Nový zámek přidej, jen
  když test ukáže souběh, jinak nové seznamy přiřazuj celé (žádné mazání uvnitř iterace).
- **`comicDetails`** (stránka série): u série bez obálky v cache volá při **každém** zobrazení synchronně
  `cv.getComic(…, 'image')` (s povinným spánkem ≥ 2 s) a `helpers.getImage`, což ubírá z limitu ComicVine
  200 req/h sdíleného s Comics. **Oprava:** po neúspěšném nebo provedeném pokusu o obálku dané série další pokus
  při zobrazení nejdřív za 24 h (paměť, konstanta v kódu). Stránka se zobrazí jako dnes bez obálky. Obálka se dál
  stahuje při refreshi série (ověř, že ano). Nic jiného na stránce neměň.
- **Testy:** 60 shod pro jedno issue → zůstane 50 nejnovějších; shoda starší než 7 dní zmizí při dalším přidání;
  kontrolní: čerstvé shody pod stropem beze změny. `comicDetails` dvakrát po sobě pro sérii bez obálky →
  `cv.getComic` zavolán jednou (podvržený, bez sítě); po posunu času o 24 h znovu. Kontrolní: série s obálkou CV
  nevolá vůbec.

### R37: SQLite vrstva (úzce)

- Scénář z review: `DBConnection.action()` a `fetch()` při `database is locked` / `unable to open database file`
  pětkrát zkusí znovu a pak vrátí `None`: zápis se **tiše** ztratí (jen WARN u každého pokusu), `select()` pak
  spadne na `None.fetchall()`. `upsert` dělá UPDATE a podle `total_changes` INSERT, každý v samostatném
  `with db_lock`, takže dva souběžné `upsert` téhož nového klíče můžou založit dva řádky (`issues`, `annuals`,
  `snatched`, `nzblog` nemají UNIQUE). Z logů zjisti počty od 11. 9. (`Database Error: database is locked`,
  `disk I/O error`) a jestli někdy došly všechny pokusy.
- **Oprava podle rozhodnutí:**
  - Po vyčerpání pokusů v `action()` a `fetch()` zaloguj **ERROR** s textem dotazu (u `upsert` i tabulka), **bez
    hodnot parametrů**. Návratová hodnota zůstává `None` (nevyhazovat, volající s tím dnes počítají); `select()`
    neopravuj, jen v souhrnu napiš, co se v něm stane.
  - `upsert`: UPDATE i případný INSERT pod **jedním** držením zámku. `db_lock` je dnes `threading.Lock` a `action()`
    si ho bere sám; použij `threading.RLock` (nebo jiný způsob bez zablokování) a zdůvodni. Pořadí a text dotazů
    neměň.
  - Nic dalšího: bez UNIQUE, bez indexů, bez WAL, bez změny busy-timeoutu (20 s) a počtu pokusů. Držení zámku
    během busy-timeoutu (třetí část R37) zůstává; zapiš do souhrnu, že není opravené.
- **Testy (deterministické):** dvě vlákna `upsert` téhož nového `IssueID`, první podržené mezi UPDATE a INSERT
  (podvržená funkce s `threading.Event`) → v tabulce jeden řádek. Vyčerpané pokusy (podvržené spojení, které vždy
  hlásí `database is locked`, `time.sleep` nahrazený) → ERROR v logu s dotazem a bez hodnot, návratová hodnota
  `None`. Kontrolní: běžný `upsert` (nový klíč → INSERT, existující → UPDATE) beze změny; zámek se dá vzít znovu ve
  stejném vlákně bez zablokování.

## Na konci

1. Obě sady testů, `ast.parse` změněných souborů, import všech modulů v 3.8.2, pyflakes před a po.
2. Souhrn **`review/FOLLOWUPS-2026-11-22-part6.md`** ve worktree (česky, kód v originále, časy pražsky):
   - prostředí: worktree, větev, základ (`python3-dev` a jeho commit), image `mylar3:local` a jeho ID, že se nic
     nenasadilo ani nerestartovalo,
   - výchozí a konečný stav testů,
   - tabulka ID | Bod | Stav (opraveno / neopraveno / nereprodukováno) | Commit | Nové testy (kolik padalo před
     opravou) | Poznámka (jak reprodukováno, co oprava dělá, dopad na stahování, PP, hledání, UI, API),
   - čísla z logu (R43 watchdog, R28 alt_match, R34 délky a překryvy PP, R37 zámky), časy pražsky,
   - otevřené otázky a konzervativní volby (minimálně hodnoty stropu a stáří u R40, signál u R43, timeout R34),
   - kontrola Comics a comics-nzb-hunteru: co se mění (pořadí PP, ID v `ddl_info`/`nzblog`/`failed` u R28), že
     schéma, stavy, odpovědi API a jména souborů zůstávají,
   - postup nasazení pro uživatele: změněné soubory jmenovitě pro `docker cp` podle `CLAUDE.md`; u Python modulů
     **`docker restart mylar`** (jen se souhlasem a když neběží DDL, PP ani klient API, viz pátá část kap. 9); co
     ověřit v logu po restartu; že po nasazení je potřeba rebuild image (R14, pozor v `CLAUDE.md`),
   - prázdná sekce „Stav po merge“.
3. Commitni souhrn ve worktree. Nepushuj, nemerguj, worktree nech být.
4. Poslední zprávou napiš, na které větvi jsi commitnul a stav testů.
