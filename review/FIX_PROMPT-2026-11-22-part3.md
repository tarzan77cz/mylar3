# Zadání: opravy nálezů z review Mylaru 2026-11-22, třetí část (escapování v JS forku)

## Kontext

**Mylar** (fork mylar3, `tarzan77cz/mylar3`) je automatický stahovač komiksů. Běží pro jednoho uživatele jen ve
vnitřní síti, ostře nad knihovnou asi 11 300 sérií. První dvě části oprav jsou v `python3-dev`, nasazené
a zapečené v image `mylar3:local` (viz kap. 9 `review/FOLLOWUPS-2026-11-22-part2.md`).

Uživatel rozhodl (kap. 11 `review/REVIEW-2026-11-22.md`, doplnění z večera 22. 11.), že bezpečnostní nálezy
R10, R11, R35, R36 a upstream část R26 jsou **přijaté riziko**. Opravuje se **jen jedna věc z R26**: místa, kde
**JavaScript, který přidal nebo změnil fork**, vkládá do stránky jako HTML texty zvenku (titulky příspěvků
z GetComics, jména souborů a složek, názvy sérií, zprávy serveru, které takové texty obsahují). Taková místa
nezávisí na tom, kdo na UI vidí: titulek `<img src=x onerror=…>` nebo soubor s tímhle jménem by spustil skript
v prohlížeči uživatele a UI nemá přihlášení ani ochranu proti CSRF. Kód forku nekoliduje s upstreamem, proto je
oprava levná.

**Hlavní riziko opravy:** rozbít zobrazení nebo ovládání UI (fronta DDL, ruční PP, picker, odmítnuté shody).
Texty se mají zobrazit stejně jako dnes, jen se nesmí vykonat jako HTML. Vzhled ani chování stránek jinak neměň.

- **Pravidla repa:** `CLAUDE.md` (Python 3.8, `sqlite3.Row` nemá `.get()`, živé služby, secrets, styl commitů,
  sekce Review). Přečti ho jako první.
- **Nález:** řádek R26 v tabulce kap. 4 `review/REVIEW-2026-11-22.md` a rozhodnutí v kap. 11. Čísla řádků
  v review platí pro starší commit, hledej podle obsahu.
- **Existující vzor escapování ve forku:** `$('<div/>').text(x).html()` (picker v `comicdetails_update.html`
  kolem `search_results[i].nzbtitle`, odmítnuté shody v `upcoming.html`, tooltip titulku v
  `queue_management.html`). Drž se ho, nebo použij `.text()` / `textContent`, když se nastavuje celý obsah prvku.

## Režim práce: bez dozoru, všechno v jedné session

Uživatel u toho není. **Na nic se neptej a nezastavuj se**, nikdo neodpoví. Když si nejsi jistý, zvol
konzervativnější variantu, zapiš ji do souhrnu jako otevřenou otázku a pokračuj.

## Rozsah

**Opravit:** klientský JS v `data/interfaces/default/*.html`, který fork přidal nebo změnil od základu forku
`b609c28c` a který vkládá do HTML (`.html()`, `innerHTML`, `.append()`/`.prepend()` s poskládaným řetězcem,
`render` funkce DataTables, hodnoty atributů v poskládaném HTML) hodnotu, která pochází zvenku nebo ji může
obsahovat. Které řádky jsou kód forku, zjisti přes `git diff b609c28c..HEAD -- data/interfaces/default/` a
`git blame`; řádek, který je beze změny z upstreamu, do rozsahu nepatří, ani když vypadá stejně.

Kandidáti (stav `python3-dev` `a27989db`, ověř každého, seznam nemusí být úplný):

- `queue_management.html`: aktivní stahování (`obj['a_series']`, `obj['a_filename']`, `obj['a_size']`,
  `statusText` kolem ř. 152–160), `amessage` se stavem ze serveru (ř. 179, 200, text obsahuje jméno souboru),
  `ajaxcallit` (`objd['message']`, ř. 220), `render` funkce sloupců tabulky fronty (`full[0]` série, `full[1]`
  a další, ř. 263 a dál).
- `manage.html`: ruční PP (`obj['message']` ř. 400, 405, 576–608; `foldername` ř. 416; interaktivní tabulka
  `series_name`, `issue_number`, `comicfilename` ř. 418; log `comic`/`issue` ř. 505–511; log souborů
  `file`/`series`/`issue`/`reason` ř. 512–526).
- `comicdetails_update.html`: zprávy pickeru a přímého DDL (`name` ř. 1403 a 1432, `obj.message` ř. 1497 a 1500,
  `xhr.responseText` ř. 1509), tabulka pickeru (ř. 1360–1375, ověř, že jsou escapované i atributy jako `link`
  a `nzbid`).
- `upcoming.html`: odmítnuté shody jsou escapované; zkontroluj zbytek kódu forku (např. `titleText`, `iconHtml`
  kolem ř. 627).
- `base.html`, `index.html`, `logs.html`, `config.html`, `history.html`, `weeklypull.html`, `data/js/script.js`:
  jen řádky forku, pokud nějaké vkládají text zvenku.

**Neopravovat (přijaté riziko, i když na to narazíš; jen případně zmiň v souhrnu):**
- serverové šablony Mako: výrazy `${}` bez `|h`, globální `default_filters` nezapínat,
- `login.html`/`auth.py` (reflected XSS, open redirect), `cv.drophtml`, stránka Logs, vydavatel a číslo
  v `index.html`, všechen upstream JS,
- R10 (autentizace, CSRF, GET akce), R11 (SSE klíč, SQL v API, `downloadNZB`), R35, R36.

**Na serveru nic neměň**, pokud to není nutné. Když zpráva ze serveru záměrně obsahuje HTML (např. `<br>`),
nejdřív zkontroluj v `webserve.py`, co přesně posílá. Když by escapování na klientu rozbilo formátování,
zvol variantu, která zachová vzhled (escapuj jen proměnnou část na klientu, nebo výjimečně `html.escape` jména na
serveru), a zapiš ji. Neměň klíče JSON odpovědí ani jejich význam. Ověř grepem, že Comics
(`/data/Tarzan/Cursor/Comics`) a comics-nzb-hunter (`/data/Tarzan/Cursor/scripts/apps/comics-nzb-hunter`)
nevolají webové endpointy, jejichž odpověď měníš (volají hlavně `/api`), a zapiš výsledek.

## Pravidla

1. **Izolace.** `git -C /data/Tarzan/Cursor/Mylar worktree add -b claude/review-2026-11-22-part3
   /data/Tarzan/Cursor/Mylar-review-2026-11-22-part3 python3-dev`. Pracuj jen tam. Hlavní strom nepřepínej
   a neměň (ani netrackované soubory). Nepushuj, nemerguj, nepřepisuj historii.
2. **Review soubory** (`REVIEW_PROMPT-*`, `REVIEW-*`, `FIX_PROMPT-*`, `FOLLOWUPS-2026-11-2*.md`) neměň, výsledky
   patří do nového `review/FOLLOWUPS-2026-11-22-part3.md`.
3. **Na živou aplikaci nesahej:** žádný `docker cp`, `docker restart`, `docker exec` do kontejneru `mylar`,
   žádné volání Mylar API ani webových akcí, žádné dotazy do `mylar.db`, nic v `/comics` a `/downloads`.
   Nečti `/config/mylar/config.ini`, `env` kontejneru ani `docker inspect mylar`. Žádná síť. Image
   `mylar3:local` nepřestavuj a nepřetaguj. Číst `docker logs mylar` smíš (časy jsou UTC, převeď na pražské).
4. **Jen tenhle nález.** Žádné refaktoringy, sjednocování šablon ani úpravy vzhledu. Nesahej na `lib/`, nepřidávej
   knihovny ani nové JS soubory, pokud to nejde jinak (pak to zdůvodni).
5. **Test dřív než oprava.** JS se v testech nespouští, proto napiš statický test v `tests/` (např.
   `tests/test_template_escaping.py`, bez importu `mylar`), který v šablonách najde konkrétní nebezpečná místa
   (každé jmenovitě, ne obecný regex přes celé soubory, ať nechytá upstream) a ověří, že hodnota prochází
   escapováním. Test musí před opravou selhat a po ní projít. Ověř to i odložením změn (`git stash` jen ve tvém
   worktree). Místa, která už escapovaná jsou, pokryj kontrolním testem a tak ho označ. Když umíš v image
   (`nodejs` v něm je) bez sítě a bez nových balíčků spustit opravenou funkci na řetězci `<img src=x onerror=1>`,
   je to vítaný doplněk, ne povinnost.
6. **Commit na šablonu** (nebo na úzce související skupinu), anglicky, jedna věta v rozkazovacím způsobu, co
   a proč, ID na konci, např. „Escape GetComics titles and file names the queue page inserts as HTML, so a
   crafted title can no longer run script in the browser (R26)“. Commit jen v repu Mylar.
7. **Nic nemaž natrvalo.** Žádný soubor z repa se neodstraňuje.

## Testy a prostředí

Worktree leží na Z2 pod `/share/Tarzan/Cursor/Mylar-review-2026-11-22-part3`, Docker socket patří Z2:

```sh
docker run --rm -e PYTHONDONTWRITEBYTECODE=1 -v /share/Tarzan/Cursor/Mylar-review-2026-11-22-part3:/src:ro mylar3:local \
  sh -c "pip install -q pytest >/dev/null 2>&1; cd /src && python3 -m pytest -q -p no:cacheprovider tests"
docker run --rm -e PYTHONDONTWRITEBYTECODE=1 -v /share/Tarzan/Cursor/Mylar-review-2026-11-22-part3:/src:ro mylar3:local \
  sh -c "pip install -q pytest >/dev/null 2>&1; cd /src && python3 -m pytest -q -p no:cacheprovider tests_db"
```

- **Výchozí stav nejdřív:** `tests` 96 passed, `tests_db` 142 passed. Zapiš do souhrnu.
- **Po každé změně šablony** ji zkompiluj Mako `TemplateLookup` nad `data/interfaces/default` v image
  (vzor `compile_templates.py` v `/data/Tarzan/Cursor/_archive/2026-11-22-mylar-review-part2-worktree/Mylar-review-2026-11-22-part2/.scratch/fix-part2/`).
  Kompilace chytí chybu Mako, ne chybu JS: zkontroluj i syntaxi upravených `<script>` bloků (např. `node --check`
  na vytaženém kódu bez Mako výrazů, když to jde).
- Na konci obě sady testů znovu. Kód v `mylar/` se měnit nemá; když se změnil, i `ast.parse` a import všech
  modulů v 3.8.2 (vzor `.scratch/review-2026-11-22/try_imports.py` v hlavním stromu, 71 ze 71).

## Na konci

1. Souhrn **`review/FOLLOWUPS-2026-11-22-part3.md`** ve worktree (česky, kód v originále, časy pražsky):
   - prostředí: worktree, větev, základ (`python3-dev` a jeho commit), image `mylar3:local` a jeho ID, že se nic
     nenasadilo ani nerestartovalo,
   - výchozí a konečný stav testů,
   - tabulka **šablona × místo (funkce, prvek) × co se vkládá × kód forku ano/ne × stav (opraveno / už escapované /
     upstream, mimo rozsah) × commit**,
   - jak se ověřilo (statický test, kompilace, případně node), co ověřit nelze (prohlížeč),
   - otevřené otázky a konzervativní volby,
   - kontrola Comics a comics-nzb-hunteru,
   - postup nasazení pro uživatele: změněné soubory jmenovitě pro `docker cp` podle `CLAUDE.md`, zda Mylar změněnou
     šablonu načte bez restartu (zjisti z nastavení `TemplateLookup` v kódu, nezkoušej na živé aplikaci), co
     zkontrolovat v UI (fronta DDL s aktivním stahováním, ruční PP, picker, odmítnuté shody); připomeň, že po
     nasazení je zase potřeba rebuild image (R14, postup v kap. 9 FOLLOWUPS druhé části),
   - prázdná sekce „Stav po merge“.
2. Commitni souhrn ve worktree. Nepushuj, nemerguj, worktree nech být.
3. Poslední zprávou napiš, ve kterých repech a na které větvi jsi commitnul, a stav testů.
