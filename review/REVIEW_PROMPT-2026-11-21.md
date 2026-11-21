# Zadání pro review Mylaru: opravy stahování z GetComics

## Úkol

Udělej nezávislé review změn ve forku Mylaru (`tarzan77cz/mylar3`, větev `python3-dev`):
**`git diff 6fd5ba76..e7e20751`** (4 commity, asi +1 200 / −450 řádků včetně testů a fixtures).

Výstupem je **jediný nový soubor `review/REVIEW-2026-11-21.md`** ve formátu popsaném níže.
Kód neměň, neopravuj a necommituj. Opravy přijdou až potom, podle samostatného zadání.

Když máš skill `/code-review`, použij ho na tento rozsah jako první průchod (úroveň `high`).
Jeho nálezy pak ověř čtením kódu nebo reprodukcí. Co při ověření neobstojí, uveď v sekci
„Zamítnuto při ověření“, ne mezi nálezy.

## Kontext

**Mylar** je automatický stahovač komiksů (watchlist, ComicVine, pull list). Tenhle fork stahuje
denně z GetComics (DDL): v listopadu 126 stažení, v říjnu 172, skoro žádná selhání. Jde hlavně
o jednotlivá nová čísla, packů je pár za měsíc. **Hlavní riziko je, že změny rozbijí nebo
potichu změní stahování jednotlivých čísel.** Na to se dívej nejdřív.

- **Pravidla repa:** `CLAUDE.md` (Python 3.8, `sqlite3.Row` nemá `.get()`, živé služby,
  nasazení). Přečti ho jako první.
- **Na Mylar navazuje** repo `/data/Tarzan/Cursor/Comics`: čte `mylar.db` (mimo jiné
  `ddl_info`) a volá Mylar API. Změna sloupců, stavů issue nebo ID v `ddl_info` ho může rozbít.
- **Referenční implementace** stejného parseru, kde jsou podobné chyby opravené:
  `/data/Tarzan/Cursor/scripts/apps/comics-nzb-hunter/comics_nzb/ddl/` (`gc_parse.py`,
  `hosts.py`, `download.py`). Je to srovnání, ne vzor, který má automaticky pravdu.

## Co je v rozsahu

| Commit | Oblast | Hlavní soubory |
|---|---|---|
| `f5ba6ebc` | parser titulků a výsledků hledání: rozsahy packů, rok, `&`, TPB, velikost z karty, filtr Week+, postupné načítání stránek výsledků | `mylar/getcomics.py` (`search`, `parse_search_result`, `check_for_pack`, `issue_list`), nový `mylar/getcomics_parse.py`, `tests/` |
| `17f2f3c3` | výběr sekce příspěvku a hosta: sekce podle hledaného čísla, filtr selhaných hostů i v záloze `/dlds/`, ukončení opakování po vyčerpání odkazů | `getcomics.py` (`parse_downloadresults`, `_wanted_issues`, `_queue_section`), `getcomics_parse.py`, `helpers.py` (`ddl_downloader`) |
| `fe732f00` | rozsahy packů a annualy | `helpers.py` (`issue_find_ids`), `search.py` a `webserve.py` (`foundsearch` s `want_ann`) |
| `e7e20751` | odkazy `/dls/` vedle `/dlds/` | `downloaders/pixeldrain.py`, `webserve.py` (`queue_direct_ddl`, requeue), `helpers.py` (SQL, `resolve_getcomics_dlds`), `getcomics.py` (záloha) |

Výběr hosta v `_queue_section` (dřívější tělo `parse_downloadresults` od `tmp_links = []` dál)
se v těchto commitech neměnil, jen přesunul do metody. Čti ho, jen když na něm závisí nález.

## Prostředí a testy

Produkce běží na Pythonu 3.8.2 v image `mylar3:local`. Docker socket patří hostu Z2, proto
připojuj cestu `/share/...`:

```sh
docker run --rm -e PYTHONDONTWRITEBYTECODE=1 -v /share/Tarzan/Cursor/Mylar:/src:ro mylar3:local \
  sh -c "pip install -q pytest >/dev/null 2>&1; cd /src && python3 -m pytest -q -p no:cacheprovider tests"
```

Očekávaný stav na `e7e20751`: 55 passed. Jiný výsledek zapiš do „Výsledek testů“.

- Celou aplikaci lze importovat v jednorázovém kontejneru: `sys.path[:0] = ['/src', '/src/lib']`
  a `import mylar`. Funkce s databází zkoušej proti dočasné SQLite (`mylar.DATA_DIR` do tempu).
- Starou verzi souboru vytáhneš přes `git show 6fd5ba76:<cesta>`. Hodí se ke srovnání chování
  staré a nové verze na stejném vstupu.
- Skutečné titulky a průběh stahování najdeš v `docker logs mylar` (jen čtení, čas v logu je UTC).
- Reprodukční skripty dej do `.scratch/` (je v `.gitignore`) nebo mimo repo.

## Pravidla

1. **Kód neměň.** Jediný zapsaný soubor je `review/REVIEW-2026-11-21.md`.
2. **Na živou aplikaci nesahej:** žádný `docker cp` ani restart kontejneru `mylar`, žádné volání
   Mylar API, žádné dotazy do `mylar.db`, nic v `/comics` a `/downloads`. Nečti
   `/config/mylar/config.ini` ani `env` kontejneru.
3. **Žádná síť:** nic nestahuj z GetComics, z hostů souborů ani z ComicVine. Pracuj s fixtures
   v `tests/fixtures/getcomics/`, titulky z logu a syntetickým HTML.
4. **Žádné tajné údaje** ve zprávě ani ve skriptech.
5. **Každý nález musí mít scénář,** podle kterého jde chybu zopakovat, a stav ověření. Hypotézy
   označ jako neověřené a odděl je od doložených chyb. Nevymýšlej nálezy, aby jich bylo víc.
6. **Nehlas jako chybu vědomé rozhodnutí.** Když si myslíš, že je špatné, napiš to do
   „Posudek rozhodnutí“. Vědomá rozhodnutí v rozsahu:
   - U příspěvku s více sekcemi se vybírají sekce podle hledaného čísla, pak podle roku. Když se
     nedá rozhodnout (nebo jde o dvě vydání téhož čísla), dostane jednotlivé číslo **poslední**
     sekci (dřívější chování). Pack dostane všechny pasující sekce jako `id-1`, `id-2`, ….
   - Položka fronty nese index sekce (`section`), aby opakování po selhání nezařadilo všechny
     sekce znovu. Položky načtené z DB po restartu ho nemají.
   - Když opakování po selhání hosta nenajde použitelný odkaz, `ddl_info` je Failed a volá se
     `reverse_the_pack_snatch` (jednotlivé číslo zůstane Snatched, stejně jako v ostatních
     větvích selhání).
   - `issue_find_ids` hledá annualy jen tam, kde je rozsah očísluje („Annual 1-3“). Bere první
     nestažený annual s daným číslem.
   - U normální sekce s „Download Now“ i „Mirror Download“ Mylar dál preferuje Mirror
     (`site_position` přepíše `normal:main`). Záměrně nezměněno.
   - Velikost z karty výsledku se přijme, jen když vypadá jako velikost, jinak `None`
     (search_filer pak limity velikosti přeskočí).

## Na co se zaměřit

### A. Jednotlivá čísla (hlavní riziko)

- Může se u stránky s jedinou sekcí změnit vybraný odkaz, `link_type`, `ddl_info.series`,
  `year`, `size` nebo `tmp_filename` oproti `6fd5ba76`? Srovnej starou a novou verzi na
  fixtures i na syntetických stránkách (HD-Upscaled / HD-Digital s Read Online i bez něj,
  odkazy před první hlavičkou, hlavička bez tlačítek, chybějící `title` u odkazu).
- `check_for_pack` na běžných titulcích jednotlivých čísel: změní se `pack`, `series`,
  `gc_booktype` nebo `year`? Vzorek skutečných titulků je v logu (řádky
  `check_for_pack … filename:`).
- `search()` s generátorem místo seznamu: stejný výsledek, výjimky, `PACK_PRIORITY`, manuální
  režim.

### B. Packy a příspěvky s více sekcemi

- Seskupení sekcí (`groups`) a `choose_sections`: varianty, sub-packy, svazky, vydání, sekce bez
  čísla, hlavička s rozsahem přes `+` (`#1 – 125 + 503 – 655`).
- Několik položek fronty z jednoho příspěvku (`id-1`, `id-2`): opakování po selhání,
  `PACK_ISSUEIDS_DONT_QUEUE`, `ddl_cleanup`, `nzblog`, post-processing, Comics.
- Rozsahy bez `#`, rozsahy na konci titulku, rozpětí let, svazky (`Vol1`, `Vol. 10 - 12`).

### C. Opakování po selhání hosta

- Může opakování ještě někdy zacyklit? Co když se mezi pokusy změní stránka (jiný počet sekcí)?
- Nová větev v `ddl_downloader`: stavy v `ddl_info`, `DDL_QUEUED`, `link_type_failure`, souběh
  s watchdogem.

### D. `issue_find_ids` a annualy

- Chování pro rozsahy, které dřív prošly (`#1 - 6`, `1 - 5`, `0-25`), a pro ty, které dřív
  padaly. Výjimky a jejich zachycení u volajících (`search_filer`, `queue_direct_ddl`, requeue).
- `want_ann` ve všech místech, která označují issues z packu. Nezůstalo nějaké volání
  `foundsearch` s annualem a režimem `want`?

### E. `/dls/` a resolve

- `resolve_getcomics_dlds` se `stream=True`: zavření spojení, chování u Main, Pixeldrain,
  Mediafire.
- SQL filtry nevyřešených odkazů proti řádkům, které `parse_downloadresults` zapisuje s
  `link_type`.

### F. Python 3.8, SQLite a pravidla z `CLAUDE.md`

- Nic z 3.9+, žádné `.get()` na `sqlite3.Row`, žádné logování klíčů (ComicVine klíč jde v URL).
- Commit zprávy anglicky, jedna věta v rozkazovacím způsobu.

### G. Testy

Co klíčového testy nepokrývají, a jaký test by to chytil. Jsou stuby v `tests/conftest.py`
dost věrné, aby testy neprocházely jen díky nim?

## Formát výstupu `review/REVIEW-2026-11-21.md`

Piš česky, kód a identifikátory nech v originále.

1. **Úvod:** rozsah (`6fd5ba76..e7e20751`), kdo a jak review dělal (session bez kontextu vývoje,
   `/code-review` a úroveň, kde běžely reprodukce), že se kód neměnil.
2. **Výsledek testů:** příkazy, počty, prostředí, co se nespustilo.
3. **Nálezy:** tabulka se sloupci ID, Závažnost, Oblast, Popis, Scénář selhání, Umístění
   (`soubor:řádek` na `e7e20751`), Ověření.
   - ID od **R1** (první review v tomto repu).
   - Závažnost: kritická, vysoká, střední, nízká, úklid, konvence.
   - Ověření: spuštěno (s výsledkem), čtení kódu, neověřeno.
   - Seřaď podle závažnosti.
   - Pod tabulkou **„Zamítnuto při ověření“:** hlášení `/code-review` nebo vlastní hypotézy,
     které neplatí, a proč.
4. **Posudek rozhodnutí:** ke každému vědomému rozhodnutí z pravidla 6 krátce souhlas, nebo
   nesouhlas s důvodem.
5. **Co klíčového testy nepokrývají.**
6. **Celkové hodnocení:** dá se změnám věřit u běžného stahování jednotlivých čísel? Co je
   dobře, největší rizika (nejvýš pět), doporučené pořadí oprav.
7. **Otázky k rozhodnutí:** u nálezů, kde je víc rozumných oprav, varianty a jejich dopad.
8. **Rozhodnutí:** jen nadpis a věta „Doplní uživatel.“

Na konci uveď, kolik času zabraly testy a ID použitého image
(`docker image inspect mylar3:local --format '{{.Id}}'`).
