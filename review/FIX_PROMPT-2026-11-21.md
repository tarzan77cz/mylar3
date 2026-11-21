# Zadání: opravy nálezů z review Mylaru 2026-11-21

## Kontext

**Mylar** (fork mylar3, `tarzan77cz/mylar3`) je automatický stahovač komiksů. Denně stahuje
jednotlivá nová čísla z GetComics (DDL), packů je pár za měsíc. **Stahování jednotlivých čísel se
nesmí rozbít ani potichu změnit.** Review ho prohlásilo za v pořádku, opravy se ho proto dotknou jen
tam, kde to nález výslovně žádá (R5, R7, rozhodnutí Q5).

- **Pravidla repa:** `CLAUDE.md` (Python 3.8, `sqlite3.Row` nemá `.get()`, živé služby, secrets,
  styl commitů). Přečti ho jako první.
- **Nálezy s doklady a scénáři:** `review/REVIEW-2026-11-21.md`. U každého nálezu čti jeho řádek
  v tabulce, posudek (sekce 4) a otázky (sekce 7). Tady je jen zkrácené zadání.
- **Rozhodnutí uživatele:** sekce 8 téže zprávy. Jsou závazná.
- **Reprodukce z review:** `.scratch/` v hlavním stromu (`/data/Tarzan/Cursor/Mylar/.scratch/`,
  v `.gitignore`): `harness.py`, `pack_scenarios.py` (P1 až P5), `cmp_posts.py`, `cmp_titles.py`,
  `cmp_synth_titles.py`, `ifi.py`. Použij je jako výchozí bod testů, do repa je nekopíruj.
- **Navazující repo:** `/data/Tarzan/Cursor/Comics` čte `mylar.db` (`ddl_info`, stavy issues) a volá
  Mylar API. Neměň schéma `ddl_info` (žádné nové sloupce), formát ID v `ddl_info` ani názvy stavů.
- **Referenční implementace** (jen pro srovnání): `/data/Tarzan/Cursor/scripts/apps/comics-nzb-hunter/comics_nzb/ddl/gc_parse.py`.

## Režim práce: bez dozoru, všechno v jedné session

Uživatel spí. **Na nic se neptej a nezastavuj se mezi nálezy**, nikdo neodpoví. Projdi všechny
nálezy a na konci napiš a commitni souhrn. Když něco nejde nebo si nejsi jistý, zvol
konzervativnější variantu, zapiš ji do souhrnu jako otevřenou otázku a pokračuj dalším nálezem.

## Pravidla

1. **Izolace.** Založ worktree z aktuálního `python3-dev` (review commit nad `e7e20751`):
   `git -C /data/Tarzan/Cursor/Mylar worktree add -b claude/review-2026-11-21 /data/Tarzan/Cursor/Mylar-review-2026-11-21 python3-dev`.
   Pracuj jen tam. Hlavní strom nepřepínej ani neměň (běží z něj úlohy uživatele). Nepushuj,
   nemerguj, nepřepisuj historii.
2. **Review soubory** (`review/REVIEW_PROMPT-2026-11-21.md`, `review/REVIEW-2026-11-21.md`, tohle
   zadání) i sekce „Review“ v `CLAUDE.md` jsou commitnuté v `python3-dev`, worktree je má.
   Neměň je, výsledky patří do `FOLLOWUPS`.
3. **Na živou aplikaci nesahej:** žádný `docker cp`, `docker restart`, `docker exec` do kontejneru
   `mylar`, žádné volání Mylar API, žádné dotazy do `mylar.db`, nic v `/comics` a `/downloads`.
   Nečti `/config/mylar/config.ini` ani `env` kontejneru. Žádná síť (GetComics, hosté souborů,
   ComicVine). Číst `docker logs mylar` smíš.
4. **Opravuj jen nálezy R1 až R9** a rozhodnutí Q5. Žádné refaktoringy ani vylepšení navíc. Kód
   z upstreamu v `lib/` neměň.
5. **Test dřív než oprava.** Každý test musí před opravou selhat a po ní projít. Když neselže,
   nález se nereprodukuje: neopravuj ho a napiš proč. Úklid (R9) může mít test, který před opravou
   selže na špatném logu, to je v pořádku.
6. **Commit na nález** (nebo úzce související skupinu), anglicky, jedna věta v rozkazovacím
   způsobu, co a proč, ID na konci, např. „Retry the same post section after a host fails, so a
   pack retry no longer downloads another sub-pack (R1)“. Commit jen v repu Mylar.
7. **Python 3.8.** Nic z 3.9+ (`match`, `X | Y`, `list[str]` mimo řetězce, `removeprefix`,
   `dict | dict`, `zoneinfo`). Na `sqlite3.Row` nikdy `.get()`.

## Testy a prostředí

Worktree leží na Z2 pod `/share/Tarzan/Cursor/Mylar-review-2026-11-21`, Docker socket patří Z2:

```sh
docker run --rm -e PYTHONDONTWRITEBYTECODE=1 -v /share/Tarzan/Cursor/Mylar-review-2026-11-21:/src:ro mylar3:local \
  sh -c "pip install -q pytest >/dev/null 2>&1; cd /src && python3 -m pytest -q -p no:cacheprovider tests"
```

- **Výchozí stav nejdřív:** na čistém worktree musí být 55 passed. Zapiš výsledek do souhrnu.
- `tests/conftest.py` při importu vloží do `sys.modules` stub balíku `mylar`. Testy, které
  potřebují skutečné `helpers` a SQLite (`issue_find_ids`, `reverse_the_pack_snatch`, větve
  `ddl_downloader`), s ním v jednom procesu nepoběží. Řeš to bez rozbití stávajících testů, např.
  testem, který spustí pomocný skript v podprocesu, nebo samostatnou složkou testů s vlastním
  `conftest.py` spouštěnou druhým příkazem. Vzor importu je `.scratch/ifi.py`
  (`sys.path[:0] = ['/src', '/src/lib']`, `mylar.CONFIG` stub, `mylar.DATA_DIR` v tempu).
  Druhý příkaz pak uveď v souhrnu i v `CLAUDE.md` (sekce Ověření, jediná povolená změna
  `CLAUDE.md`).
- Před každým commitem: celá sada testů a `ast.parse` změněných souborů v image (příkaz v `CLAUDE.md`).
- Na konci znovu spusť `.scratch/cmp_titles.py` a `.scratch/cmp_posts.py` proti worktree (uprav cesty
  v kopii skriptu v `.scratch/` worktree nebo přes proměnnou `REPO`). Rozdíly proti `6fd5ba76`
  u jednotlivých čísel smí být jen ty, které review popisuje jako záměrné, plus důsledky R5 a R7.
  Výsledek zapiš do souhrnu.

## Nálezy a co přesně udělat

Pořadí: R2 → R1 → R3 → R4 → Q5 → R5 → R7 → R6 → R8 → R9 (R1 a R4 stojí na R2).

### R2 (vysoká): sub-packy `<id>-N` proti základnímu ID packu

- Položka fronty (`mylar.DDL_QUEUE.put` v `_queue_section`) nese navíc `pack_id` (základní ID
  příspěvku) a čísla své sekce (např. `section_issues`, seznam intů z `section_issue_numbers`).
  Položky bez těchto klíčů (z DB po restartu, jednotlivá čísla, TPB extras, `manual-…`) se chovají
  jako dnes: `pack_id` = `item['id']`.
- **Selhání sekce** (všechny větve v `ddl_downloader`, které dnes volají
  `reverse_the_pack_snatch(item['id'], …)`): vrátit na `Wanted` jen issue ID z
  `packinfo['pack_issuelist']['issues']`, jejichž `int_iss`/číslo leží v číslech sekce (annualy
  v `'annual': True` jen když je sekce sama annualová, jinak ne). Neznámá čísla sekce (prázdný
  seznam) nebo jediná sekce = celý pack, jako dnes.
- **Úklid po úspěchu** (`helpers.py` kolem `:4186`): z `PACK_ISSUEIDS_DONT_QUEUE` odebrat issue ID
  dané sekce (párovat přes `pack_id`, ne `item['id']`).
- **`search_queue`** (`helpers.py:4640-4643`): přeskočit číslo, když je ve frontě kterákoli položka
  s jeho `pack_id`. `DDL_QUEUED` obsahuje ID položek, potřebuješ tedy mapu ID položky → `pack_id`
  nebo test prefixu `pack_id + '-'`. Zvol variantu s menším zásahem a zdůvodni ji v souhrnu.
- **Self-heal po PP** (`PostProcessor._revert_unmatched_pack_snatches`,
  `helpers.get_pack_snatched_issueids`): `nzblog.ID` je základní ID. Do `download_info` předávaného
  z `ddl_downloader` do `PP_QUEUE` přidej `pack_id` a čísla/issue ID sekce. Self-heal hledá v
  `nzblog` přes `pack_id` a vrací jen issue ID dané sekce. `mark_failed=True` zapisuje do `failed`
  `pack_id` (celý příspěvek), to ponech.
- Test: pack Tomahawk 1–140 (fixture `post_tomahawk_subpacks.html`) → položky `1-1`, `1-2` mají
  `pack_id='1'` a správná čísla sekcí. Nad dočasnou SQLite: selhání `1-2` vrátí #71–140 na `Wanted`,
  #1–70 zůstanou `Snatched`. Úspěch `1-1` odebere z mapy jen #1–70.

### R1 (vysoká): stabilní identita sekce při opakování

- Index v položce (`section`) musí ukazovat na stejnou sekci i poté, co filtr selhaných hostů
  vyprázdní jinou sekci nebo se změní pořadí. Doporučení: index do seznamu skupin sestaveného ze
  **všech** sekcí s odkazy před filtrem `site_failed` (filtr se uplatní až při výběru odkazu), plus
  kontrola klíče sekce (čísla z hlavičky + varianta, u sekcí bez čísel text hlavičky). Klíč nes
  v položce fronty. Když se sekce s tímto klíčem na stránce nenajde, vrať `success: False` (nikdy
  znovu `choose_sections`, nikdy nová ID typu `1-3-1`).
- Pozor: filtr selhaných hostů je dnes v hlavním průchodu (`getcomics.py:765`), ve fallbacku
  (`:859`) i ve druhé záloze (`:946`). Výsledek pro první pokus (bez `link_type_failure`) se nesmí
  změnit, ověř to `cmp_posts.py`.
- Test: scénář P2 z `pack_scenarios.py` (sekce 0 jen Download Now, sekce 1 a 2 Download Now +
  Pixeldrain, `ltf=['GC-Main']`): `section` pro `1-2` → zařadí se Pixeldrain sekce `#11 - 20` pod `1-2`.
  Pro `1-3` → Pixeldrain `#21 - 30` pod `1-3`, žádné `1-3-1`. Sekce, která na stránce chybí →
  `success: False`.

### R3 (střední): rok u packu jen mezi překrývajícími se sekcemi

- V `getcomics_parse.choose_sections` pro `pack=True`: sekce s hledanými čísly rozděl na skupiny
  sekcí, jejichž čísla se překrývají (spojené komponenty podle průniku). V každé skupině s víc než
  jednou sekcí zúž výběr rokem (když něco zbude), pak ze stejných čísel nech poslední. Když ve skupině
  zůstanou různé překrývající se sekce, nech tu s nejvíc hledanými čísly, při shodě poslední.
  Skupiny bez překryvu (sub-packy) zůstanou všechny. Pro `pack=False` beze změny.
- Testy: sub-packy `(1950, 1960)` a `(1960, 1972)`, `pack=True`, `year=1950` → `[0, 1]`. Plastic Man
  (`#1–64` 1943–1956, `#1–20` 1966–1967) jako pack 1–64 s rokem 1943 → jen vol. 1. Stávající testy
  `test_choose_sections_rules` a `test_volume_picked_by_year` musí projít beze změny.

### R4 (střední): částečně zařazený pack

- V `parse_downloadresults`: když `_queue_section` u některé sekce selže a jiná se zařadí, výsledek
  zůstane úspěch, ale nese seznam nezařazených sekcí (čísla, případně issue ID) a zaloguje se varování
  (`logger.warn`, se jmény sekcí).
- **Pořadí s označením Snatched:** zjisti, kde `search.py` (a `webserve.py` u výběru odmítnuté shody)
  označuje čísla packu jako `Snatched` vůči volání `parse_downloadresults`. Vrácení na `Wanted` musí
  proběhnout **až po** označení, jinak ho přepíše. Pravděpodobně v `search.py` po smyčce `foundsearch`
  (kolem `:1495-1511`): pro nezařazené sekce zavolat vrácení jen jejich čísel (stejná funkce jako
  v R2). Zapiš do souhrnu, kde přesně to proběhne.
- Když se nezařadí nic, chování zůstane (selhání).
- Test: scénář P4 (`DDL_PRIORITY_ORDER=['pixeldrain']`, sekce `#11 - 20` jen Download Now) →
  výsledek nese nezařazenou sekci 11–20, ve frontě je jen sekce 1–10. Nad SQLite: po označení a
  vrácení jsou 11–20 `Wanted`, 1–10 `Snatched`.

### Q5: jednotlivé číslo po vyčerpání všech hostů

- Platí pro větev `REDO` (`helpers.py:4346-4359`) a větev `links_exhausted` (`:4372-4385`), jen
  pro položky, které nejsou pack (`packinfo` bez `pack is True` a ID nezačíná `manual-`).
- Použij existující `reverse_the_pack_snatch(item['id'], item['comicid'], issueids=[item['issueid']],
  mark_failed=True, provider='DDL(GetComics)', nzbname=<název>)`: vrátí číslo (`issues` i `annuals`)
  ze `Snatched` na `Wanted` a zapíše řádek do `failed` s `ID` = ID příspěvku. Pro jednotlivé číslo
  přidej volitelný parametr, aby se do `failed.Issue_Number` zapsalo skutečné číslo místo `'pack'`.
  `search.FailedMark` nepoužívej: nastaví stav `Failed`, ne `Wanted`.
- Řádek `ddl_info` zůstane `Failed`, nemaže se.
- Ověř a zapiš do souhrnu: `Failed.failed_check` (volá ho `search.py:2985-2998`) hledá v `failed`
  podle `ID`, které se musí shodovat s ID příspěvku při příštím hledání (`entry['id']`). Kontrola běží
  jen při `FAILED_DOWNLOAD_HANDLING`. Hodnotu v configu nezjišťuj (`config.ini` je zakázaný), jen
  napiš, že bez ní se číslo vrátí na `Wanted` a příspěvek se může vybrat znovu.
- Zkontroluj v `/data/Tarzan/Cursor/Comics`, jestli něco čte tabulku `failed` nebo spoléhá na to, že
  číslo po selhání DDL zůstane `Snatched` (`requeue_missing_issues.py`, `check_remediated_issues.py`,
  remediace). Výsledek do souhrnu, Comics neměň.
- Test nad SQLite: jednotlivé číslo `Snatched` → po vyčerpání `Wanted`, v `failed` řádek s ID
  příspěvku a skutečným číslem. Pack se chová podle R2.

### R5 (nízká): `#…-číslice` na konci titulku

- V `check_for_pack` (`getcomics.py:2217-2224`) je titulek pack jen tehdy, když text od `#` po konec
  tokenu je čistý rozsah `\d+-\d+` (případně se stejnými mezerami jako jinde). `#-1`, `#5 X-23` nejsou
  pack. `Batman #1-3 (2025)` a `#1-15 …` zůstanou pack.
- Testy: `Zero Hour #-1 (1994)`, `Batman #5 X-23 (2025)` → `pack=False`. `Batman #1-3 (2025)` →
  `pack=True`, `issues='1-3'`. `cmp_titles.py` na 4 732 titulcích nesmí ukázat novou změnu `pack`.

### R7 (nízká): tlačítko bez `title`

- V hlavním průchodu `parse_downloadresults` ber popisek z `title`, a když chybí, z textu odkazu
  (jako referenční `_anchor_link`). Odkaz s prázdným popiskem do `gather_links` nepřidávej.
  „Read Online“ poznej i podle textu.
- Testy: syntetické stránky `missing_title_link` a `missing_title_then_read` z `cmp_posts.py` →
  Download Now bez `title` se vybere jako GC-Main, s `ltf=['GC-Main']` se vezme Pixeldrain.

### R6 (nízká): druhá záloha přiřazuje tlačítko poslední sekci

- Tlačítko nalezené druhou zálohou patří sekci, jejíž hlavička mu v dokumentu předchází. Když se to
  nedá určit a sekcí je víc, tlačítko přeskoč (s `logger.fdebug`). U stránky s jednou sekcí beze změny.
- Test: scénář P3 (dvě tlačítka v jednom `<p>` sekce `#1 - 10`, hledané #15) → stáhne se Pixeldrain
  sekce `#11 - 20`, ne Mirror sekce `#1 - 10`. `test_dlds_fallback_*` a `test_fallback_finds_current_dls_buttons` projdou.

### R8 (nízká): přímé DDL s rozsahem jen z annualů

- V `queue_direct_ddl` (`webserve.py:4416-4427`) při výpočtu kontrolního čísla odstraň i slovo
  `Annual`/`Annuals` (a `#`), takže „Annual 1-3“ projde, když jsou annualy 1–3 `Wanted`.
- Že `queue_direct_ddl` odmítne rozsah, jehož první číslo je `Downloaded`, existovalo už dřív
  a není nález. Neopravuj, jen zmiň v souhrnu.
- Test nad SQLite přes `issue_find_ids` s kontrolním číslem tak, jak ho `queue_direct_ddl` spočítá
  (výpočet vytáhni do malé funkce, ať jde testovat bez CherryPy).

### R9 (úklid): log `ignores` v `issue_find_ids`

- `ignores` má obsahovat jen čísla packu, jejichž odpovídající issue je `Downloaded`, každé jednou.
  Výběr čísel (`issueinfo`) se nesmí změnit.
- Test nad SQLite: série s #1 a #2 `Downloaded`, pack 1–5 → `ignores == [1, 2]`, issue ID beze změny.

## Na konci

1. Celá sada testů (oba příkazy), `ast.parse` změněných souborů, `cmp_titles.py` a `cmp_posts.py`.
2. Souhrn **`review/FOLLOWUPS-2026-11-21.md`** ve worktree (česky, kód v originále):
   - prostředí: worktree, větev, image `mylar3:local` a jeho ID, že se kontejner nerestartoval a nic
     se nenasadilo,
   - výchozí a konečný stav testů (počty, příkazy),
   - tabulka ID | Stav (opraveno / neopraveno / nereprodukováno) | Commit | Nové testy | Poznámka (jak
     reprodukováno, co oprava dělá, dopad na jednotlivá čísla),
   - výsledek srovnání `cmp_titles.py` / `cmp_posts.py` se `6fd5ba76`,
   - otevřené otázky a konzervativní volby, které jsi udělal místo uživatele,
   - kontrola Comics (Q5, R2),
   - postup nasazení pro uživatele: seznam změněných souborů pro `docker cp` (jmenovitě, podle
     `CLAUDE.md`), co ověřit v logu po restartu,
   - prázdná sekce „Stav po merge“ (doplní se po merge a nasazení).
3. Commitni souhrn ve worktree. Nepushuj, nemerguj, worktree nech být.
4. Poslední zprávou napiš, ve kterých repech a na které větvi jsi commitnul, a stav testů.
