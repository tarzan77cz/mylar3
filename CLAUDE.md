# Mylar (fork mylar3)

**S uživatelem komunikuj vždy česky** (odpovědi, otázky, shrnutí i plány). Kód a vše ostatní
podle sekce Jazyk.

Vlastní fork [mylar3](https://github.com/mylar3/mylar3), automatického stahovače komiksů
(watchlist, ComicVine, pull list, DDL z GetComics). Úpravy forku: DDL stahování a jeho chyby,
výběr z odmítnutých shod (rejected matches), data vydání z ComicVine a pull listu, přejmenování
souborů, fronta a UI. Na Mylar navazuje pipeline v repu `Comics` (konverze, tagování, Komga).

Tento soubor čte Claude Code i Cursor. Pravidla pro agenty patří sem, ne do `.cursor/rules/`.

## Jazyk

- Identifikátory, komentáře, docstringy, `print` a logy anglicky.
- Commit zprávy anglicky: jedna věta v rozkazovacím způsobu, která říká co a proč
  (viz `git log`, např. „Keep DDL downloads from discarding complete files after server errors“).

## Git a fork

- `origin` = upstream `mylar3/mylar3`, jen fetch, **nikdy push**. `fork` = `tarzan77cz/mylar3`.
- Pracovní větev `python3-dev` sleduje `fork/python3-dev`. Push jen po potvrzení uživatele.
- Změny z upstreamu (`origin/python3-dev`) se přebírají jen na pokyn uživatele.

## Struktura

- `Mylar.py` – start aplikace. `mylar/` – balík:
  - `__init__.py` (globální stav, scheduler), `config.py`, `db.py`, `helpers.py`,
  - `webserve.py` (CherryPy, stránky UI a jejich akce), `api.py` (REST API; volá ho i Comics),
  - `search.py`, `search_filer.py` (hledání, skórování a výběr shod),
  - `getcomics.py`, `downloaders/` (DDL), `PostProcessor.py`, `filechecker.py`,
  - `cv.py` (ComicVine), `weeklypull.py`, `locg.py` (pull list), `updater.py`.
- `data/interfaces/default/*.html` – Mako šablony UI; `data/js/`, `data/css/`.
- `lib/` – knihovny převzaté z upstreamu. Neupravovat bez nutnosti.
- `utilities/` – jednorázové skripty. `post-processing/`, `init-scripts/` – upstream, v Dockeru
  se nepoužívají.
- `.vscode/` – úlohy uživatele pro ruční kopírování do kontejneru (Ctrl+/ m).

## Python 3.8

Produkce běží na **Pythonu 3.8.2** (`python:3.8.2-alpine3.11`), lokální `venv/` je 3.11, takže
lokální běh chybu nenajde. Nepoužívej nic z 3.9+: `match`, `X | Y` v anotacích, `list[str]` /
`dict[str, int]` mimo řetězce, `str.removeprefix` / `removesuffix`, `dict | dict`, `zoneinfo`,
závorkované víceřádkové `with (...)`. Nové závislosti musí jít na 3.8 a Alpine.

## SQLite

- Řádky jsou `sqlite3.Row`, který **nemá `.get()`**. Nikdy `row.get('key')`, vždy `row['key']`.
- Platí pro všechno z `myDB.select()`, `myDB.selectone()`, `.fetchone()` (proměnné `row`,
  `active`, `si`, `oi`, `x`, `db_item`, `item` …) i pro volitelné sloupce: `row['col']` nebo
  `try/except KeyError`, ne `row.get('col', default)`.
- Před každou úpravou kódu, který čte z `myDB` nebo z tabulek `ddl_info`, `comics`, `issues`,
  zkontroluj, že se na výsledný řádek nevolá `.get()`.

## Ověření

Testy jsou jen pro parser GetComics (`tests/`, fixtures se skutečnými stránkami v
`tests/fixtures/getcomics/`). `tests/conftest.py` nahradí globály Mylaru stuby, takže testy
nespouštějí aplikaci ani síť. Pouštěj je Pythonem 3.8 z image (Docker socket patří Z2, proto
hostitelská cesta `/share/...`; pytest se doinstaluje jen do dočasného kontejneru):

```sh
docker run --rm -e PYTHONDONTWRITEBYTECODE=1 -v /share/Tarzan/Cursor/Mylar:/src:ro mylar3:local sh -c "pip install -q pytest >/dev/null 2>&1; cd /src && python3 -m pytest -q -p no:cacheprovider tests"
```

Před nasazením zkontroluj i syntaxi změněných souborů:

```sh
docker run --rm -v /share/Tarzan/Cursor/Mylar:/src:ro mylar3:local python3 -c "import ast,sys; [ast.parse(open(f).read(), f) for f in sys.argv[1:]]" /src/mylar/helpers.py /src/mylar/webserve.py
```

`ast.parse` chytí jen syntaxi, ne volání z novějšího Pythonu (`str.removeprefix`), na ta dej
pozor sám. Chyby v Mako šablonách se ukážou až za běhu: po nasazení otevři dotčenou stránku.

## Review

Review a jeho opravy jsou v `review/`. Zadání review `REVIEW_PROMPT-<datum>.md`, zpráva
`REVIEW-<datum>.md` (nálezy `R<n>`, ID navazují na minulé review), souhrn oprav
`FOLLOWUPS-<datum>.md`. Review dělá samostatná session bez kontextu vývoje a kód nemění.
U opravy nálezu nejdřív napiš test, který před opravou selže a po ní projde. Když neselže, nález
se nereprodukuje: neopravuj ho a napiš proč. Reprodukční skripty patří do `.scratch/` (mimo git).

## Nasazení (kontejner `mylar`, stack `comics`, Z2)

Kód je zapečený v image `mylar3:local` (`/app/mylar/`), není bind mount. Config a DB jsou
v `/config` (host `/home/docker/comics/mylar/config`). Výchozí postup:

1. Zkopíruj každý změněný soubor na stejnou cestu pod `/app/mylar/`:
   `docker cp mylar/search_filer.py mylar:/app/mylar/mylar/search_filer.py`,
   `docker cp data/interfaces/default/upcoming.html mylar:/app/mylar/data/interfaces/default/upcoming.html`.
2. `docker restart mylar` **jen po souhlasu uživatele**. Restart přeruší běžící DDL stahování
   a post-processing a smaže stav v paměti (např. `REJECTED_MATCHES`). Před dotazem se podívej
   do `docker logs mylar --tail 50`, jestli něco neběží, a řekni to.
3. Ověř: `docker exec mylar grep -c "<marker>" /app/mylar/<soubor>` a `docker logs mylar --tail 50`.
   Změnu UI zkontroluj v prohlížeči přes Playwright MCP; když kontrola neproběhla, řekni to.

`.vscode/copy_all_changed_to_mylar.sh` kopíruje jen necommitnuté změny (`git diff HEAD`),
agent proto kopíruje soubory jmenovitě.

Rebuild `docker build -t mylar3:local .` jen když nestačí `docker cp` (změna `requirements.txt`
nebo `Dockerfile`, rozbitý kontejner) nebo na výslovný pokyn. Kontejner se pak recreatuje
přes Dockhand (skill `dockhand`, jen služba `mylar`), vždy se souhlasem uživatele.

## Živé služby a secrets

Mylar běží ostře nad knihovnou `/share/Comics`. Bez souhlasu uživatele:

- žádná volání Mylar API, která mění stav (`queueIssue`, `forceSearch`, `recheckFiles`,
  refresh série, změna stavu issue),
- žádné dotazy ani zápisy do `mylar.db` (`docker exec … sqlite3`),
- nic nemazat ani nepřesouvat v `/comics` a `/downloads`,
- žádné hromadné dotazy na ComicVine (limit 200 req/h sdílí Mylar s pipeline Comics).

Bez ptaní je čtení kódu v kontejneru (`docker exec mylar grep/ls/cat /app/mylar/...`) a logů
(`docker logs mylar`).

`/config/mylar/config.ini` obsahuje API klíče (ComicVine, Mylar, downloadery). **Nikdy ho
nečti ani nevypisuj**, stejně tak `env` kontejneru. Kód nesmí logovat klíče (ComicVine klíč
jde v URL).

## Vazba na repo Comics

`T:\Cursor\Comics` volá Mylar API a čte jeho DB (`comics_mylar_rename.py`, remediace,
`requeue_missing_issues.py`, `check_remediated_issues.py`). Změna API, stavů issue, sloupců
nebo pojmenování souborů může Comics rozbít, proto tam volání zkontroluj.
