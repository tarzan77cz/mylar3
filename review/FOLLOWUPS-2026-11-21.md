# Opravy nálezů z review 2026-11-21

Opravy nálezů R1 až R9 a rozhodnutí Q5 z [REVIEW-2026-11-21.md](REVIEW-2026-11-21.md) podle
[FIX_PROMPT-2026-11-21.md](FIX_PROMPT-2026-11-21.md). Session běžela bez dozoru 21.–22. 11. 2026
(konec 22. 11. 2026 kolem 01:00 SEČ).

## 1. Prostředí

- **Worktree:** `/data/Tarzan/Cursor/Mylar-review-2026-11-21` (na Z2 `/share/Tarzan/Cursor/Mylar-review-2026-11-21`),
  větev `claude/review-2026-11-21` z `python3-dev` (`8624757b`). Hlavní strom se nepřepínal ani neměnil.
- **Image:** `mylar3:local`, `sha256:b7cfffeb59ee1b6d6c3bb459ba492bd146075392a2d6e7df8535c8a3b7c93167`
  (vytvořen 11. 9. 2026 17:21 SELČ), Python 3.8.2. Testy a srovnávací skripty běžely v jednorázových
  kontejnerech s worktree připojeným jen pro čtení.
- **Živá aplikace:** kontejner `mylar` se nerestartoval, nic se nenasadilo (`docker cp` ani `docker exec` ne),
  žádné volání Mylar API, žádný dotaz do `mylar.db`, žádná síť, `config.ini` ani `env` se nečetly.
  Nic se nepushovalo ani nemergovalo.
- **Reprodukční skripty:** `.scratch/` z hlavního stromu zkopírovaný do worktree (v `.gitignore`, mimo git).

## 2. Testy

| | `tests/` (stuby, parser) | `tests_db/` (skutečný balík `mylar`, dočasná SQLite) |
|---|---|---|
| Výchozí stav (čistý worktree) | **55 passed** | sada neexistovala |
| Konečný stav | **88 passed** | **24 passed** |

```sh
docker run --rm -e PYTHONDONTWRITEBYTECODE=1 -v /share/Tarzan/Cursor/Mylar-review-2026-11-21:/src:ro mylar3:local \
  sh -c "pip install -q pytest >/dev/null 2>&1; cd /src && python3 -m pytest -q -p no:cacheprovider tests"
docker run --rm -e PYTHONDONTWRITEBYTECODE=1 -v /share/Tarzan/Cursor/Mylar-review-2026-11-21:/src:ro mylar3:local \
  sh -c "pip install -q pytest >/dev/null 2>&1; cd /src && python3 -m pytest -q -p no:cacheprovider tests_db"
```

- **Nová sada `tests_db/`:** [conftest.py](../tests_db/conftest.py) importuje skutečný balík `mylar`
  (vzor `.scratch/ifi.py`), každý test dostane vlastní `mylar.db` v tempu (`mylar.DATA_DIR`, tabulky `comics`,
  `issues`, `annuals`, `nzblog`, `failed`, `ddl_info`) a vlastní globály (`PACK_ISSUEIDS_DONT_QUEUE`,
  `DDL_QUEUED`, `PP_QUEUE`). Testy větví `ddl_downloader` pouštějí **skutečnou smyčku** `helpers.ddl_downloader`
  s položkou a `'exit'` ve frontě a podvrženým `getcomics.GC`. Se stuby z `tests/` v jednom procesu nepoběží,
  proto druhý příkaz. Doplněno do `CLAUDE.md` (sekce Ověření, jediná změna `CLAUDE.md`).
- Před každým commitem: obě sady a `ast.parse` změněných souborů v image. Na konci navíc import
  `mylar.search`, `mylar.webserve`, `mylar.PostProcessor`, `mylar.helpers`, `mylar.getcomics` v 3.8: v pořádku.
- Každý nový test před opravou selhal ze správného důvodu (výjimky jsou v tabulce). Ověřeno i odložením změn
  v `mylar/` (`git stash`) u R2 a R6.

## 3. Nálezy

| ID | Stav | Commit | Nové testy | Poznámka |
|---|---|---|---|---|
| R2 | opraveno | `d02e276b` | `tests/test_getcomics_post.py`: `test_subpacks_carry_the_pack_id_and_their_issues`, `test_single_issue_item_has_its_own_pack_id`; `tests_db/test_pack_sections.py` (8 testů) | **Reprodukce:** nad SQLite Tomahawk #1–140 jako pack `1`, položka `1-2`: selhání ve větvi REDO i `links_exhausted` nic nevrátilo (#71–140 zůstala `Snatched`), úspěch `1-1` nevyčistil mapu, self-heal PP `1-2` nenašel nic v `nzblog`. **Oprava:** položka fronty nese `pack_id`, `section_issues` (čísla z hlavičky), `section_annual` (a od R1 `section_key`). Nové funkce v [helpers.py](../mylar/helpers.py): `ddl_item_pack_id`, `pack_section_issueids` (párování přes `issue_number_parser(n).asInt == int_iss`), `ddl_item_section_issueids`, `reverse_ddl_item_snatch`, `ddl_download_info`, `pack_queued_for_download`. Všech pět volání `reverse_the_pack_snatch(item['id'], …)` v `ddl_downloader` jde přes `reverse_ddl_item_snatch`: vícesekční pack vrací jen čísla sekce (průnik s `pack_issuelist['issues']`, annualy jen u annualové sekce), jediná sekce nebo neznámá čísla = celý pack přes mapu jako dřív. Úklid po úspěchu páruje přes `pack_id` a maže jen issue ID sekce. `download_info` do `PP_QUEUE` nese `pack_id` a `section_issueids` (None = celý pack), `_revert_unmatched_pack_snatches` hledá v `nzblog` přes `pack_id` a filtruje na sekci, `failed` dál dostává `pack_id`. Položky bez nových klíčů (z `ddl_info` po restartu, TPB extras, `manual-…`) mají `pack_id = item['id']`, chovají se jako dřív. **`search_queue`:** zvolen test prefixu (`pack_queued_for_download`: ID ve `DDL_QUEUED` je `pack_id` nebo začíná `pack_id + '-'`). Menší zásah než mapa ID položky → `pack_id`: žádný nový globál, žádné udržování mapy ve všech místech, která do `DDL_QUEUED` přidávají a odebírají (watchdog, requeue, startup). ID příspěvků jsou unikátní čísla, `12-` neodpovídá `123-1`; TPB extras `id-N` patří ke stejnému příspěvku. **Jednotlivá čísla:** beze změny chování (nová pole jen navíc). |
| R1 | opraveno | `e59f4110` | `tests/test_getcomics_post.py`: `test_section_retry_after_host_failure_keeps_its_section` (2×), `test_section_index_survives_the_failed_host_filter` (2×), `test_section_retry_fails_when_the_section_is_gone`, `test_section_retry_out_of_range_fails`, `test_section_retry_finds_a_moved_section_by_key` | **Reprodukce:** scénář P2, opakování `1-2` s `ltf=['GC-Main']` stáhlo `s2-pixel` (cizí sub-pack), `1-3` zařadilo `1-3-1` a `1-3-2`. **Oprava** ([getcomics.py](../mylar/getcomics.py) `parse_downloadresults`): hlavní průchod selhaný odkaz nezahodí, jen ho označí `failed`; skupiny se staví dvakrát: `all_groups` ze všech sekcí s odkazem (index a klíč do položky fronty) a `groups` jen s použitelnými odkazy (výběr přes `choose_sections` jako dřív). Opakování (`section` zadaný) hledá sekci přes `getcomics_parse.find_section` (index, pak klíč `getcomics_parse.section_keys`: varianta + čísla z hlavičky, text hlavičky když čísla chybí nebo se opakují); nenajde-li ji, vrátí `success: False` a nikdy znovu nevolá `choose_sections`. Selhaní hosté se odfiltrují až při výběru odkazu. `links_found_in_paragraphs` a `existing_hrefs` počítají jen použitelné odkazy, fallbacky se proto spouštějí stejně jako dřív. `ddl_downloader` předává `section_key`. **Jednotlivá čísla:** `cmp_posts.py` po R1 bajtově shodný s výstupem review (256 kombinací včetně `link_type_failure`). |
| R3 | opraveno | `8942ae7d` | `test_pack_keeps_subpacks_with_other_years`, `test_pack_year_picks_the_volume`, `test_pack_overlap_without_year_keeps_most_wanted_then_last`, `test_pack_overlap_groups_and_free_subpacks`, `test_plastic_man_pack_takes_only_its_volume` | **Reprodukce:** sub-packy `(1950, 1960)` a `(1960, 1972)`, `pack=True`, rok 1950 → `[0]`. **Oprava:** `choose_sections` pro `pack=True` volá `_choose_pack_sections`: sekce s hledanými čísly se rozdělí na spojené skupiny překrývajících se čísel (stejná čísla, i prázdná, se počítají jako překryv); ve skupině s víc sekcemi zúží výběr rok (když něco zbude), ze stejných čísel zůstane poslední, a když se zbylé sekce pořád překrývají, ta s nejvíc hledanými čísly (při shodě poslední). Pro `pack=False` beze změny. `test_volume_picked_by_year`, `test_plastic_man_pack_takes_only_its_volume` a `test_pack_year_picks_the_volume` procházely už před opravou (hlídají, že se volba volume nerozbila). |
| R4 | opraveno | `107095ba` | `test_partly_queued_pack_reports_the_missing_section`, `test_fully_queued_pack_has_no_missing_sections`, `test_pack_with_nothing_queued_still_fails`; `tests_db/test_pack_partial.py` (3 testy) | **Reprodukce:** scénář P4 vrátil tichý `{'success': True}`. **Oprava:** `parse_downloadresults` u vícesekčního packu, kde se něco zařadilo a něco ne, vrací úspěch s `unqueued_sections` (`series`, `issues`, `annual`) a loguje `logger.warn('[DDL-SECTIONS] Only part of this pack could be queued. Not queued: […]')`. Nic nezařazeno = selhání jako dřív. `helpers.revert_unqueued_pack_sections` vrací čísla těch sekcí na `Wanted` (přes `reverse_the_pack_snatch(..., issueids=…)`, bez zápisu do `failed`, ostatní sekce stahují dál). **Kde přesně:** `search.searcher` vrací `unqueued_sections` v `return_val`; vrácení proběhne v `search.verification` hned za smyčkou `updater.nzblog` + `updater.foundsearch` přes `issinfo['issues']` ([search.py:1512-1520](../mylar/search.py#L1512-L1520)), tedy **až po** označení Snatched. Ve `webserve.select_rejected_match` (obě větve, [webserve.py:4149](../mylar/webserve.py#L4149), [:4313](../mylar/webserve.py#L4313)) se označuje Snatched jen vybrané `IssueID`, proto se po `foundsearch` vrací jen to (`only_issueids=[IssueID]`), když leží v nezařazené sekci. `queue_direct_ddl` a requeue `parse_downloadresults` nevolají, netýká se jich. |
| Q5 | opraveno | `89aadeed` | `tests_db/test_single_exhausted.py` (5 testů) | **Reprodukce:** jednotlivé číslo `Snatched`, všechny hosty selhaly (REDO i `links_exhausted`) → zůstalo `Snatched`, v `failed` nic. **Oprava:** obě větve volají `helpers.release_exhausted_ddl_item`: jednotlivé číslo (`ddl_item_is_single_issue`: ne `manual-…`, `packinfo['pack']` ani `comicinfo[0]['pack']` není `True`) jde přes `reverse_the_pack_snatch(pack_id, comicid, issueids=[issueid], mark_failed=True, provider='DDL(GetComics)', nzbname=<nzbtitle>, issue_number=<číslo>)`, takže `issues` i `annuals` jdou ze `Snatched` na `Wanted` a do `failed` se zapíše řádek s `ID` = ID příspěvku, skutečným `Issue_Number` a `IssueID`. Nový volitelný parametr `issue_number` v `reverse_the_pack_snatch` (bez něj dál `'pack'`). Pack jde dál přes R2. Řádek `ddl_info` zůstane `Failed`. `search.FailedMark` se nepoužívá. **`failed_check`:** `search.searcher` volá `Failed.FailedProcessor(id=nzbid, …).failed_check()` jen při `FAILED_DOWNLOAD_HANDLING` (a `nzbid`, `IssueID`, ne one-off); hledá `SELECT * FROM failed WHERE ID=?`. U GetComics je `nzbid` ID příspěvku, stejné jako `ddl_info.ID` jednotlivého čísla, takže se příspěvek při příštím hledání odmítne (`downloadchk-fail`) a `verification` vezme další shodu. Hodnota `FAILED_DOWNLOAD_HANDLING` v configu se nezjišťovala. **Bez ní se číslo jen vrátí na `Wanted` a příští hledání může vybrat stejný příspěvek znovu.** |
| R5 | opraveno | `d618442c` | `tests/test_getcomics_parse.py`: `test_dash_after_hash_needs_a_clean_range` (3×), `test_short_range_at_end_of_title_is_a_pack` | **Reprodukce:** `Zero Hour #-1 (1994)`, `Batman #5 X-23 (2025)` → `pack=True`. **Oprava:** větev `#…-číslice` v `check_for_pack` bere titulek jako pack jen když text od `#` po konec tokenu odpovídá `^\d+\s*-\s*\d+(?![\w-])`. `X-Men #0-A` procházel už dřív. **Dopad:** `cmp_titles.py` na 4 732 skutečných titulcích bajtově shodný se stavem před opravami (52 rozdílů proti `6fd5ba76`, `pack` 6×, jako v review). `cmp_synth_titles.py`: `#-1`, `#5 X-23` zase jednotlivá čísla, `Batman #1-3` pack; navíc `Wolverine #12 X-23 Variant (2025)` a `Batman #1 (2025) 1-25 Variant`, které stará i nová verze braly jako pack s nesmyslným rozsahem (`12 X-23`, `1  1-25`), jsou teď jednotlivá čísla. |
| R7 | opraveno | `cabcfbba` | `test_button_without_title_is_read_from_its_text`, `test_button_without_title_and_failed_hosts`, `test_read_online_without_title_is_not_a_download` | **Reprodukce:** `missing_title_link`: vybral se Pixeldrain místo Main, s `ltf=['GC-Pixel']` `success: False`. **Oprava:** hlavní průchod bere popisek z `title`, když chybí, z textu odkazu; „Read Online“ pozná i podle textu; odkaz bez popisku do `gather_links` nepřidá (log `fdebug`). `test_read_online_without_title_is_not_a_download` procházel i před opravou (Read Online bez `title` dřív skončil jako odkaz se `site=''`, který `_queue_section` ignoroval), hlídá, že se nerozbije. **Dopad:** v `cmp_posts.py` se proti review změnilo 6 kombinací, všechny na stránce `missing_title_link` (Main bez `title` místo Pixeldrainu u `default`/`upscaled`, Main místo `success: False` po selhání Pixeldrainu u všech čtyř konfigurací). |
| R6 | opraveno | `72c979e6` | `test_fallback_button_belongs_to_the_section_before_it`, `test_fallback_button_without_a_section_is_skipped` | **Reprodukce:** scénář P3, hledané #15 stáhlo Mirror sekce `#1 - 10`. **Oprava:** sekce si z hlavního průchodu pamatuje svůj hlavičkový `<p>`; druhá záloha na stránce s víc sekcemi přiřadí tlačítko sekci nejbližší předcházející hlavičky (`a.previous_elements`) a do odkazu dá její `series`/`year`/`size`. Když hlavičku nenajde, tlačítko přeskočí (`logger.fdebug('[FALLBACK-DLDS] Cannot tell which section …')`). Stránka s jednou sekcí beze změny. Pozor: `id` je v `parse_downloadresults` parametr a zastiňuje vestavěnou funkci, hlavičky se proto porovnávají přes `is`. **Dopad:** `cmp_posts.py` beze změny proti stavu po R7, `test_dlds_fallback_*` a `test_fallback_finds_current_dls_buttons` procházejí. |
| R8 | opraveno | `19bdc783` | `tests/test_getcomics_parse.py`: `test_direct_ddl_check_issue` (7×); `tests_db/test_issue_find_ids.py`: `test_direct_ddl_range_is_valid_with_its_check_issue` (4×), `test_old_check_issue_rejected_annual_ranges`, `test_direct_ddl_annual_range_marks_the_annuals` | **Reprodukce:** `issue_find_ids('Annual 1-3', 'Annual 1')` → `valid=False` (stará kontrola, test `test_old_check_issue_rejected_annual_ranges`). **Oprava:** výpočet kontrolního čísla vytažen do `getcomics_parse.direct_ddl_check_issue` (odstraní `Annual`/`Annuals` a `#`, vezme text před první pomlčkou), `queue_direct_ddl` ho volá. `Annual 1-3` → `1` → `valid=True`, annualy A1–A3 označené. `1-10 + Annual 1-3`, `#1 - 6`, `0-25`, `26-50` dávají stejné číslo jako dřív. **Neopraveno (není nález):** `queue_direct_ddl` dál odmítne rozsah, jehož první číslo je `Downloaded` (`valid` vyžaduje, aby kontrolní číslo bylo mezi nestaženými). Existovalo už dřív. |
| R9 | opraveno | `470604ab` | `tests_db/test_issue_find_ids.py`: `test_ignores_lists_each_downloaded_issue_once`, `test_ignores_not_logged_without_downloaded_issues` | **Reprodukce:** #1 a #2 `Downloaded`, pack 1–5 → log `[[1, 1, 2, 2, 3, 3, 4, 4, 5, 5]]`. **Oprava:** `else: ignores.append(iss)` pryč; číslo packu jde do `ignores` jednou, jen když pro něj nebylo vybráno nestažené issue a existuje issue se stejným `Int_IssueNumber` ve stavu `Downloaded`. Výběr čísel beze změny: test ověřuje `['I3', 'I4', 'I5']` a `.scratch/ifi.py` (15 rozsahů) dává na worktree i hlavním stromu shodný výstup. |

## 4. Srovnání se starou verzí (`6fd5ba76`)

Skripty z `.scratch/` (stará verze v `.scratch/old/getcomics.py`), spuštěné proti worktree v image:

- **`cmp_titles.py`** (4 732 skutečných titulků z `docker logs mylar`): výstup bajtově shodný se stavem
  `python3-dev` před opravami: 52 odlišných titulků, `{'year': 18, 'gc_booktype': 17, 'series': 20, 'title': 20,
  'pack': 6, 'volume': 1, 'issues': 2}`. Opravy nepřinesly žádnou novou změnu `pack`.
- **`cmp_posts.py`** (4 fixtures + 12 syntetických stránek × 4 konfigurace × 4 stavy `link_type_failure`):
  odlišných kombinací 119/256 jako v review. Proti výstupu review (`cmp_posts.out`) se liší jen 6 kombinací
  stránky `missing_title_link` (R7, viz tabulka). R1, R3, R4, R6 a R9 jednotlivá čísla nezměnily (výstup po R1,
  R3, R4 i po R6 ověřen zvlášť).
- **`pack_scenarios.py`:** P1 zařadí oba sub-packy (`1-1`, `1-2`) i s různými roky; P2 opakování `1-2` vezme
  `s1-pixel`, `1-3` vezme `s2-pixel` bez `1-3-1`; P3 stáhne Pixeldrain sekce `#11 - 20` (jako stará verze);
  P4 vrátí `unqueued_sections` se sekcí `#11 - 20`; P5 beze změny (u jednotlivého čísla po selhání GC-Main
  druhé vydání, posudek review to přijal).

## 5. Otevřené otázky a konzervativní volby

1. **Annualy v hlavičce sub-packu (R2).** Sekce je annualová, jen když slovo `Annual` stojí v hlavičce před `#`
   (`getcomics_parse.section_is_annual`). U hlavičky `Batman #1 - 50 + Annual 1 - 3` patří k sekci jen běžná
   čísla 1–50 (`section_issue_numbers` čte jen rozsah za `#`); když taková sekce ve vícesekčním packu selže,
   její annualy zůstanou `Snatched`. Zvoleno, aby se nevracela čísla, která může stahovat jiná sekce.
2. **Nezařazená sekce bez čísel (R4)** se nevrací (neví se, která čísla obsahuje), jen se zaloguje varování.
3. **`DDL_QUEUED` (R2, `search_queue`).** ID položky se do `DDL_QUEUED` dostane až když ji `ddl_downloader`
   vezme z fronty (nebo při načtení z DB), ne při `DDL_QUEUE.put`. Ochrana před dvojím zařazením tedy platí jen
   pro právě stahovanou položku. Tak to bylo i dřív, neměnil jsem to.
4. **Klíč sekce (R1).** Když se mezi pokusy změní text hlavičky sekce bez čísel nebo přibude sekce se stejnými
   čísly, klíč se nenajde a opakování selže (`success: False`, čísla sekce se vrátí podle R2). Sekce, kterou
   otevřel jen první fallback (`<div class="aio-pulse">` mimo `<p>`) a jejíž jediný odkaz selhal, v `all_groups`
   chybí; index pak nesedí, ale kontrola klíče to zachytí a opakování selže. Selhané odkazy si pamatuje jen
   hlavní průchod, aby se fallbacky spouštěly přesně jako dřív.
5. **Q5 a story arcy.** `reverse_the_pack_snatch` mění jen `issues` a `annuals`. Položka story arcu s
   `IssueArcID` se do `failed` zapíše, ale stav v `storyarcs` se nevrátí. Mimo zadání.
6. **Q5 a zápis do `failed` bez vrácení.** Když číslo mezitím není `Snatched` (např. `Downloaded` jinou cestou),
   stav se nemění, ale řádek do `failed` se zapíše (příspěvek opravdu selhal). Test
   `test_downloaded_single_issue_is_left_alone` ověřuje jen stav.
7. **Q5 jen ve dvou větvích.** Větve „chybí `comicinfo`/`packinfo`“, „neplatný `mainlink`“ a výjimka
   z `parse_downloadresults` vracejí dál jen pack a `manual-…` (zadání Q5 je vyjmenovává jen pro REDO
   a `links_exhausted`).
8. **R3 bez hledaných čísel.** Když `choose_sections` nedostane hledaná čísla, rozhoduje ve skupině
   překrývajících se sekcí počet čísel v hlavičce (pak poslední).

## 6. Kontrola repa Comics (Q5, R2)

- **Tabulka `failed`:** [requeue_missing_issues.py](../../Comics/requeue_missing_issues.py) ji čte jen pro výpis
  (`SELECT ID, Provider, DateFailed FROM failed WHERE IssueID = ?`) a přes `remediate_html_stubs.clear_failed`
  maže `DELETE FROM failed WHERE ID = ? AND Provider = ?` (Provider `DDL(GetComics)`). Nový řádek z Q5 má
  `ID` = ID příspěvku (= `ddl_info.ID`), `Provider='DDL(GetComics)'` a skutečné `IssueID`, takže ho výpis ukáže
  a soft retry smaže. [remediate_html_stubs.py](../../Comics/remediate_html_stubs.py) zapisuje do `failed`
  řádky ve stejném tvaru.
- **Stav `Snatched` po selhání DDL:** v Comics na něj nic nespoléhá (`check_remediated_issues.py` stavy nečte,
  `requeue_missing_issues.py` volá `queueIssue`, který číslo stejně nastaví na `Wanted`).
- **`ddl_info`:** schéma, formát ID (`<id>`, `<id>-N`, `manual-…`) ani názvy stavů se nezměnily. Nové klíče
  (`pack_id`, `section_issues`, `section_annual`, `section_key`, v `download_info` `pack_id`
  a `section_issueids`) žijí jen v paměti (položky fronty, `PP_QUEUE`). Mylar API se neměnilo.

## 7. Nasazení (pro uživatele)

Merge do `python3-dev`, nasazení a restart jen se souhlasem. Postup podle `CLAUDE.md`, změněné soubory
jmenovitě:

```sh
docker cp mylar/getcomics.py mylar:/app/mylar/mylar/getcomics.py
docker cp mylar/getcomics_parse.py mylar:/app/mylar/mylar/getcomics_parse.py
docker cp mylar/helpers.py mylar:/app/mylar/mylar/helpers.py
docker cp mylar/search.py mylar:/app/mylar/mylar/search.py
docker cp mylar/webserve.py mylar:/app/mylar/mylar/webserve.py
docker cp mylar/PostProcessor.py mylar:/app/mylar/mylar/PostProcessor.py
```

Šablony, `requirements.txt` ani `Dockerfile` se nemění, rebuild není potřeba. `tests/`, `tests_db/`
a `CLAUDE.md` se do kontejneru nekopírují.

Před restartem `docker logs mylar --tail 50` (běžící DDL nebo post-processing se restartem přeruší, zmizí
`REJECTED_MATCHES` a `PACK_ISSUEIDS_DONT_QUEUE`). Ověření po restartu:

- markery: `docker exec mylar grep -c "def release_exhausted_ddl_item" /app/mylar/mylar/helpers.py`,
  `docker exec mylar grep -c "def find_section" /app/mylar/mylar/getcomics_parse.py`,
  `docker exec mylar grep -c "section_key" /app/mylar/mylar/getcomics.py`,
  `docker exec mylar grep -c "unqueued_sections" /app/mylar/mylar/search.py`;
- `docker logs mylar --tail 50`: start bez tracebacku, `[DDL-DOWNLOADER] DDL downloader thread started`;
- za provozu v logu: u jednotlivých čísel stejné `[DDL-GATHERER-OF-LINKAGE]` a `Now downloading` jako dřív;
  u packů nové hlášky `[DDL-SECTIONS] Only part of this pack could be queued`, `[DDL-SECTIONS] Section … is no
  longer on the page`, `[DDL-SECTIONS] Returning … issue(s) of pack … to Wanted`; u jednotlivého čísla po
  vyčerpání hostů `[REVERSE UNO] Marked pack release <id> as Failed` (text hlášky zůstal z packové větve)
  a číslo ve stavu `Wanted`;
- stránka s odmítnutými shodami (`select_rejected_match`) a přímé DDL (`queue_direct_ddl`) se změnily jen
  v Pythonu, šablony ne. Přesto po nasazení otevřít detail série a zkusit přímé DDL s rozsahem `Annual 1-3`
  u série s chtěnými annualy.

## 8. Stav po merge

Doplní se po merge a nasazení.
