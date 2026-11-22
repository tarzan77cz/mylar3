# Zadání pro review Mylaru: celý repozitář forku

## Úkol

Udělej nezávislé review **celého repozitáře** forku Mylaru (`tarzan77cz/mylar3`, větev `python3-dev`,
stav `a4d24a40`). Nejde o jeden diff, ale o tři otázky:

1. **Jsou v kódu větší problémy?** Hlavně ve změnách forku proti upstreamu, které ještě nikdo
   nerevidoval, a v bezpečnosti a spolehlivosti toho, co v produkci opravdu běží.
2. **Které soubory a složky se nepoužívají** a do repa (nebo do Docker image) nepatří.
3. **Platí opravy minulého review** (`review/REVIEW-2026-11-21.md`, `review/FOLLOWUPS-2026-11-21.md`).

Výstupem je **jediný nový soubor `review/REVIEW-2026-11-22.md`** ve formátu popsaném níže.
Kód ani soubory neměň, nic nemaž, nepřesouvej a necommituj. Opravy a úklid přijdou až potom,
podle samostatného zadání a rozhodnutí uživatele.

Když máš skill `/code-review`, použij ho jako první průchod (úroveň `high`) na změny forku
`git diff b609c28c..python3-dev` (oblast A). Jeho nálezy pak ověř čtením kódu nebo reprodukcí.
Co při ověření neobstojí, uveď v „Zamítnuto při ověření“, ne mezi nálezy.

Rozsah je velký (asi 66 000 řádků v `mylar/` a `Mylar.py`, k tomu `lib/`, `data/`). Celý ho
do hloubky nepřečteš, a to se ani nečeká. Postupuj podle priorit v „Na co se zaměřit“ a ve
zprávě poctivě napiš, co jsi četl do hloubky, co jen prolétl a co vůbec ne. K inventuře souborů
(oblast D) můžeš použít subagenty, závěry si ale ověř sám.

## Kontext

**Mylar** je automatický stahovač komiksů (watchlist, ComicVine, pull list). Tenhle fork běží
ostře nad knihovnou asi 11 300 sérií a stahuje denně z GetComics (DDL), v listopadu přes 120
stažení. **Hlavní riziko je ztráta nebo poškození dat v knihovně** (mazání, přesun, přejmenování
souborů, přepis stavů issue v DB) a **tiché selhání stahování jednotlivých čísel**.

- **Pravidla repa:** `CLAUDE.md` (Python 3.8, `sqlite3.Row` nemá `.get()`, živé služby,
  nasazení, review). Přečti ho jako první.
- **Upstream:** `origin` = `mylar3/mylar3`. Fork se odpojil na `b609c28c` (2026-01-01). Od té doby
  je na forku 74 commitů (+12 000 / −1 600 řádků v 68 souborech), na `origin/python3-dev` podle
  posledního fetch nic nového. Smíš udělat `git fetch origin` a zkontrolovat, jestli upstream
  mezitím něco neopravil (hlavně bezpečnost).
- **Už revidováno:** commity `6fd5ba76..e7e20751` (GetComics) a jejich opravy `d02e276b..470604ab`.
  Znovu je čti jen v rámci oblasti H. Všechny starší commity forku (`89ac088d` až `657fb712`:
  DDL fronta a watchdog, rejected matches, přímé DDL, ComicVine, pull list, přejmenování podle
  data, post-processing, UI fronty) **nikdy review neprošly**.
- **Co v produkci opravdu běží** zjisti z kódu a z `docker logs mylar` (jen čtení), ne z configu.
  Podle logu: jediný poskytovatel hledání je `DDL(GetComics)` (0 NZB poskytovatelů), SABnzbd je
  nakonfigurovaný (test spojení při startu), plánovače pull listu (4 h), RSS (20 min), DB updater
  (denně), ComicTagger 1.3.5. Torrent klienti, 32P, Mega a další integrace z upstreamu jsou
  nejspíš vypnuté. Ověř to, než o nich něco tvrdíš.
- **Nasazení:** kód je zapečený v image `mylar3:local` (postavený 2026-09-11) a změny se do běžícího
  kontejneru `mylar` kopírují přes `docker cp`. Kontejner nepublikuje porty, UI a API jsou dostupné
  přes Docker síť stacku `comics`.
- **Na Mylar navazuje** repo `/data/Tarzan/Cursor/Comics` (jen čtení): volá Mylar API a čte
  `mylar.db` (`comics_mylar_rename.py`, `requeue_missing_issues.py`, `check_remediated_issues.py`,
  remediace). Změna API, stavů issue, sloupců nebo pojmenování souborů ho může rozbít.

## Co je v rozsahu

| Oblast | Co | Hlavní místa |
|---|---|---|
| Změny forku | `git diff b609c28c..python3-dev` bez už revidovaných GetComics commitů | `helpers.py` (+2 000), `webserve.py` (+1 700), `getcomics.py`, `search_filer.py` (+1 200), `cv.py`, `PostProcessor.py`, `updater.py`, `api.py`, `filechecker.py`, `weeklypull.py`, `locg.py`, `mb.py`, `downloaders/`, šablony v `data/interfaces/default/` |
| Upstream kód, který běží | DDL, hledání, post-processing, přejmenování, webový server, API, plánovače | `Mylar.py`, `mylar/__init__.py`, `webstart.py`, `auth.py`, `api.py`, `PostProcessor.py`, `filechecker.py`, `filers.py`, `cmtagmylar.py`, `db.py`, `config.py` |
| Celý strom | inventura souborů a složek | root, `utilities/`, `post-processing/`, `init-scripts/`, `screens/`, `lib/`, `data/`, `mylar/` |
| Build | co a jak se dostane do image | `Dockerfile`, `.dockerignore`, `requirements.txt` |
| Minulé review | R1 až R9 a Q5 | `review/*-2026-11-21.md` |

`lib/` jsou knihovny převzaté z upstreamu. Nehledej v nich chyby řádek po řádku. Zajímá nás, které
se vůbec importují a jestli některá nemá známou zranitelnost nebo nefunguje na 3.8.

## Prostředí a testy

Produkce běží na Pythonu 3.8.2 v image `mylar3:local`. Docker socket patří hostu Z2, proto
připojuj cestu `/share/...`:

```sh
docker run --rm -e PYTHONDONTWRITEBYTECODE=1 -v /share/Tarzan/Cursor/Mylar:/src:ro mylar3:local \
  sh -c "pip install -q pytest >/dev/null 2>&1; cd /src && python3 -m pytest -q -p no:cacheprovider tests"
docker run --rm -e PYTHONDONTWRITEBYTECODE=1 -v /share/Tarzan/Cursor/Mylar:/src:ro mylar3:local \
  sh -c "pip install -q pytest >/dev/null 2>&1; cd /src && python3 -m pytest -q -p no:cacheprovider tests_db"
```

Očekávaný stav na `a4d24a40`: `tests` 88 passed, `tests_db` 24 passed. Jiný výsledek zapiš do
„Výsledek testů“.

- Celou aplikaci lze importovat v jednorázovém kontejneru: `sys.path[:0] = ['/src', '/src/lib']`
  a `import mylar`. Funkce s databází zkoušej proti dočasné SQLite (`mylar.DATA_DIR` do tempu,
  vzor je v `tests_db/conftest.py`).
- Kód v běžícím kontejneru smíš číst (`docker exec mylar ls|cat|grep|md5sum /app/mylar/...`) a
  porovnat ho s repem. `/config` v kontejneru nečti.
- Starou verzi souboru vytáhneš přes `git show b609c28c:<cesta>`.
- Statickou analýzu (`pyflakes`, `vulture`, `bandit`, `pip-audit` apod.) instaluj jen do
  jednorázového kontejneru, ne do repa ani do `venv/`. Výstup ber jako podklad, ne jako nálezy.
- Reprodukční skripty dej do `.scratch/` (je v `.gitignore`) nebo mimo repo.

## Pravidla

1. **Kód ani soubory neměň.** Jediný zapsaný soubor v repu je `review/REVIEW-2026-11-22.md`.
   I zjevné smetí jen zapiš do inventury, nemaž ho.
2. **Na živou aplikaci nesahej:** žádný `docker cp`, restart ani rebuild, žádné volání Mylar API,
   žádné dotazy do `mylar.db`, nic v `/comics` a `/downloads`. Nečti `/config/mylar/config.ini`,
   `env` kontejneru ani `docker inspect mylar` (obsahuje proměnné prostředí).
3. **Síť jen na `git fetch origin`** a na instalaci analytických nástrojů do jednorázového
   kontejneru. Nic nestahuj z GetComics, z hostů souborů ani z ComicVine (limit 200 req/h sdílí
   Mylar s pipeline Comics). Bezpečnostní nálezy dokládej čtením kódu a lokální reprodukcí proti
   dočasné instanci nebo funkci, nikdy proti živé aplikaci.
4. **Žádné tajné údaje** ve zprávě ani ve skriptech. Když narazíš na klíč nebo heslo v repu nebo
   v logu, uveď jen soubor, řádek a typ údaje, hodnotu ne.
5. **Každý nález musí mít scénář,** podle kterého jde chybu zopakovat, a stav ověření. Hypotézy
   označ jako neověřené a odděl je od doložených chyb. Nevymýšlej nálezy, aby jich bylo víc.
6. **Opakující se vzory slučuj.** Holé `except:`, formátování logů, chybějící `with` u souborů
   a podobné styly z upstreamu nepiš po jednom. Jeden nález s počtem výskytů a příklady, a jen
   když z něj plyne skutečné riziko.
7. **Nehlas jako chybu vědomé rozhodnutí.** Když si myslíš, že je špatné, napiš to do
   „Posudek rozhodnutí“. Vědomá rozhodnutí a známá omezení:
   - Produkce zůstává na Pythonu 3.8.2 (`python:3.8.2-alpine3.11`). Upgrade můžeš doporučit
     v „Otázkách k rozhodnutí“ s odhadem dopadu, ale chybějící 3.9+ syntax není chyba.
   - `lib/` se upravuje jen z nutnosti. Dvě drobné úpravy forku v `lib/comictaggerlib/` jsou záměrné.
   - Nasazení přes `docker cp` do běžícího kontejneru a rebuild image jen výjimečně (viz `CLAUDE.md`).
   - `post-processing/` a `init-scripts/` se v Dockeru nepoužívají (jsou z upstreamu). Jestli je
     smazat, je otázka pro inventuru, ne nález.
   - Otevřené otázky z `review/FOLLOWUPS-2026-11-21.md` (Q5 a `FAILED_DOWNLOAD_HANDLING`,
     kontrola dvojího zařazení packu podle prefixu ID, annualy v hlavičce sub-packu, sekce bez
     čísel) jsou známé. Hlas je jen s novým argumentem nebo scénářem.
   - Mylar UI a API nejsou vystavené do internetu přímo (kontejner nepublikuje porty). To ale
     neznamená, že je chybějící autentizace v pořádku: posuď ji, jen u závažnosti zohledni dosah.

## Na co se zaměřit

### A. Nerevidované změny forku (nejvyšší priorita)

Commity `89ac088d..657fb712` (viz `git log --oneline b609c28c..6fd5ba76`). Pro každou oblast:
může změna ztratit data, nechat issue v nesprávném stavu, zacyklit se, nebo potichu přestat
stahovat?

- **DDL fronta a watchdog** (`helpers.py`: `ddl_downloader`, watchdog, `ddl_load_queued_items`,
  restart fronty, `DDL_QUEUED`, `DDL_LOCK`): souběh vláken, zámky, co se stane po restartu
  uprostřed stahování, duplicitní položky, nekonečné opakování.
- **Stahování a kontrola souborů** (`downloaders/pixeldrain.py`, `mediafire.py`, retry po chybách
  serveru, kontrola useknutých archivů, chunked zápis): může se smazat kompletní soubor, nebo
  naopak přijmout neúplný?
- **Rejected matches a přímé DDL** (`search_filer.py`, `webserve.py`: `select_rejected_match`,
  `queue_direct_ddl`, requeue, UI fronty): validace vstupů z formuláře, stavy issue, `REJECTED_MATCHES`.
- **ComicVine a data vydání** (`cv.py`, `updater.py`, `weeklypull.py`, `locg.py`, `mb.py`):
  odhadovaná data obálky, přejmenování placeholderů `0000-00`, záloha z pull listu, rok 2099.
  Může refresh série přepsat nebo smazat řádky issues, které mezitím zpracovává post-processing?
- **Post-processing a přejmenování** (`PostProcessor.py`, `filechecker.py`, `filers.py`):
  mazání prázdných adresářů, přesuny, přejmenování podle data. Může se smazat nebo přepsat
  soubor v knihovně, který tam patří?
- **API pro Comics** (`api.py`): změněné příkazy a jejich odpovědi, kompatibilita s voláními
  v repu Comics.

### B. Bezpečnost

- Autentizace a autorizace UI a API (`webstart.py`, `auth.py`, `api.py`, OPDS, `webviewer.py`):
  které akce jdou zavolat bez přihlášení nebo bez API klíče, CSRF u akcí měnících stav.
- Path traversal u všeho, co bere cestu nebo jméno souboru z požadavku (čtečka, OPDS, stahování
  souborů, logy, obrázky, `cblimport`, ruční post-processing).
- Spouštění příkazů (`subprocess`, `os.system`, shell=True) s hodnotami z DB, názvů souborů nebo
  požadavku (`cmtagmylar.py`, unrar, ComicTagger, skripty po stažení).
- SQL skládané formátováním řetězců s hodnotami z požadavku nebo z webu.
- SSRF: URL z formuláře nebo z GetComics, které server sám stahuje (`queue_direct_ddl`,
  `resolve_getcomics_dlds`, obrázky přes `curl_cffi`).
- XSS v Mako šablonách (`${...}` bez escapování, hlavně u textů z GetComics a ComicVine) a
  v JavaScriptu nových stránek forku.
- Logování tajných údajů (ComicVine klíč v URL, API klíče, hesla downloaderů) a jejich výpis v UI
  (`config_dump.html`, stránka logů).
- `pickle`, `eval`, `yaml.load` a podobná místa.

### C. Spolehlivost a provoz

- Vlákna a plánovače (`__init__.py`, APScheduler, fronty): sdílený globální stav bez zámků,
  výjimky, které tiše ukončí vlákno fronty.
- SQLite: souběžný zápis z více vláken, transakce, `db.py`. Pravidlo `.get()` na `sqlite3.Row`
  v celém `mylar/` (ne jen v nových změnách).
- Python 3.8: nic z 3.9+ v celém `mylar/`, `Mylar.py`, `utilities/`.
- Závislosti: `requirements.txt` má jen spodní hranice (`>=`), image se staví z PyPI v okamžiku
  buildu. Co se stane při příštím `docker build`? Které nainstalované verze (viz log
  `check_the_pip`) mají známé zranitelnosti nebo už nepodporují 3.8? `cfscrape` + `nodejs`,
  `urllib3<2`.
- Image: Alpine 3.11 a Python 3.8.2 jsou dávno bez podpory. Popiš riziko a možnosti, rozhodnutí
  nech na uživateli (pravidlo 7).

### D. Inventura souborů: co se nepoužívá

Projdi celý strom a pro každý soubor nebo složku, která není zjevně potřeba, zjisti, jestli se
používá. Důkaz uveď konkrétně: import, odkaz ze šablony nebo JS, volání z `Dockerfile`, výskyt
v logu, nebo naopak žádný odkaz nikde. Kandidáti (seznam není úplný):

- **Root:** prázdné soubory `=`, `ERROR`, `[internal]`, `extracting`, `resolve`, `transferring`,
  osm `sha256:*` (vypadají jako artefakty přesměrovaného výstupu `docker build`; jsou v
  `.gitignore` i `.dockerignore` místo smazání), `unicode_check.py`, `comictagger.py`,
  `.LAST_RELEASE`, `API_REFERENCE`, `ascii_logo.nfo`, `screens/`, `venv/` (lokální 3.11).
- **Kód:** `mylar/test.py`, `mylar/req_test.py`, `auth32p.py`, `wwt.py`, `comicbookdb.py`,
  `utorrent.py` vedle `torrent/clients/utorrent.py`, `findcomicfeed.py`, `ftpsshup.py`,
  `maintenance*.py`, `carepackage.py`, `encrypted.py` a další moduly bez importu.
- **`lib/`:** které knihovny se importují (`deluge_client`, `rtorrent`, `utorrent`,
  `transmissionrpc`, `qbittorrent`, `mega`, `natsort` vedle `natsort` z PyPI, `rarfile` vedle
  `rarfile` z PyPI, `configobj`), `lib/rarfile/doc/`, `lib/deluge_client/tests.py`.
- **`data/`:** nepoužité šablony (`searchfix-2.html`, `searchfix.html`, `torrentinfo.html` …),
  rozhraní `carbon`, duplicitní verze jQuery (`jquery-1.7.2`, `1.11.1`, `2.2.4`), dvě verze
  DataTables a Modernizr, nepoužité obrázky.
- **Ostatní:** `utilities/`, `post-processing/`, `init-scripts/`, `.github/ISSUE_TEMPLATE/`
  (šablony upstreamu), `.vscode/` (úlohy uživatele, viz `CLAUDE.md`).

U každé položky doporuč jedno z: **ponechat**, **přesunout** (kam a proč), **odstranit z repa**
(uživatel archivuje mimo repo, nic se nemaže natrvalo), **doplnit do `.gitignore`/`.dockerignore`**.
Odstranění z upstream souborů zvaž i z pohledu budoucího přebírání změn z `origin` (konflikty).

### E. Build a obsah image

- Co všechno `COPY . /app/mylar` do image dostane? Projdi `.dockerignore` proti stromu: testy,
  `tests_db/`, `review/`, `.scratch/`, `utilities/`, `screens/`, `venv/` a jestli se do image
  nemůže dostat něco citlivého nebo velkého.
- Rozdíl mezi repem (`python3-dev`) a kódem v běžícím kontejneru (`/app/mylar`): soubory,
  které se liší nebo chybí na jedné straně (porovnej `md5sum`).

### F. Pravidla z `CLAUDE.md`

Dodržuje je celý repozitář, ne jen nové změny? Hlavně `.get()` na `sqlite3.Row`, 3.9+ syntax,
logování klíčů. Je `CLAUDE.md` aktuální vůči stavu repa (struktura, příkazy, cesty)?

### G. Testy

Testy pokrývají jen parser GetComics a část DDL fronty. Které oblasti z A až C by měly test
dostat jako první, a jaký (název, vstup, očekávání)? Nepiš je, jen je navrhni.

### H. Kontrola oprav minulého review

Ke každému nálezu R1 až R9 a k rozhodnutí Q5 verdikt (opraveno, částečně, neopraveno, oprava
zavedla novou chybu) s krátkou poznámkou. Opravy jsou v commitech `d02e276b..470604ab`.

## Formát výstupu `review/REVIEW-2026-11-22.md`

Piš česky, kód a identifikátory nech v originále.

1. **Úvod:** rozsah (celý repozitář na `a4d24a40`, priority podle zadání), kdo a jak review dělal
   (session bez kontextu vývoje, `/code-review` a úroveň, kde běžely reprodukce a analýza), že se
   kód neměnil, že ID navazují na review z 2026-11-21.
2. **Pokrytí:** tabulka oblast × hloubka (do hloubky, prolétnuto, nečteno) × poznámka.
3. **Výsledek testů a analýzy:** příkazy, počty, prostředí, použité nástroje a jejich verze,
   co se nespustilo a proč.
4. **Nálezy:** tabulka se sloupci ID, Závažnost, Oblast, Popis, Scénář selhání, Umístění
   (`soubor:řádek` na `a4d24a40`), Ověření.
   - ID od **R10** (minulé review skončilo R9).
   - Závažnost: kritická, vysoká, střední, nízká, úklid, konvence.
   - Ověření: spuštěno (s výsledkem), čtení kódu, neověřeno.
   - Seřaď podle závažnosti.
   - Pod tabulkou **„Zamítnuto při ověření“:** hlášení `/code-review`, analytických nástrojů
     nebo vlastní hypotézy, které neplatí, a proč.
5. **Inventura souborů:** tabulka Cesta | Používá se? | Důkaz | Doporučení | Riziko změny.
   Soubory se stejným závěrem seskup (např. „8× `sha256:*` v rootu“). Nálezy z inventury,
   které jsou skutečný problém (citlivý soubor v image, mrtvý kód s chybou, který se přesto
   načítá), dej i do tabulky nálezů.
6. **Kontrola oprav minulého review:** nález × verdikt × poznámka.
7. **Posudek rozhodnutí:** ke každému vědomému rozhodnutí z pravidla 7 krátce souhlas, nebo
   nesouhlas s důvodem.
8. **Co klíčového testy nepokrývají** a navržené testy (oblast G).
9. **Celkové hodnocení:** v jakém stavu je fork, co je dobře, největší rizika (nejvýš pět),
   doporučené pořadí oprav a úklidu. Odděl rychlý úklid (bez změny chování) od oprav chyb.
10. **Otázky k rozhodnutí:** u nálezů s více rozumnými řešeními varianty a dopad. Patří sem i
    upgrade Pythonu a Alpine, připnutí závislostí a odstranění upstream složek.
11. **Rozhodnutí:** jen nadpis a věta „Doplní uživatel.“

Na konci uveď, kolik času zabraly testy a analýza a ID použitého image
(`docker image inspect mylar3:local --format '{{.Id}}'`).
