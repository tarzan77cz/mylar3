# Opravy nálezů z review 2026-11-22, třetí část (escapování v JS forku)

Oprava části nálezu R26 z [REVIEW-2026-11-22.md](REVIEW-2026-11-22.md) podle
[FIX_PROMPT-2026-11-22-part3.md](FIX_PROMPT-2026-11-22-part3.md) a rozhodnutí uživatele v kap. 11 zprávy (doplnění
z večera 22. 11.: R10, R11, R35, R36 a upstream část R26 jsou přijaté riziko). Opravují se jen místa, kde JavaScript,
který fork přidal nebo změnil, vkládá do stránky jako HTML text zvenku. Session běžela bez dozoru 22. 11. 2026 asi
21:30–22:00 SEČ (commity 21:49–21:50 SEČ, 20:49–20:50 UTC).

## 1. Prostředí

- **Worktree:** `/data/Tarzan/Cursor/Mylar-review-2026-11-22-part3` (na Z2 `/share/Tarzan/Cursor/Mylar-review-2026-11-22-part3`),
  větev `claude/review-2026-11-22-part3`, založená z **`python3-dev` (`ad8bba79`)**. Hlavní strom se nepřepínal ani
  neměnil (ani netrackované soubory).
- **Image:** `mylar3:local`, `sha256:616267dfa1c56951ef72e540a4bdce2eb2f7a2b2d0c6ef2cd3f693657850d072`
  (postaven 22. 11. 2026 20:59 SEČ, kap. 9 [FOLLOWUPS-2026-11-22-part2.md](FOLLOWUPS-2026-11-22-part2.md)),
  Python 3.8.2, `node` v12.22.6. Testy, kompilace šablon a `node --check` běžely v jednorázových kontejnerech nad
  worktree jen pro čtení. Image se nepřestavoval ani nepřetagoval.
- **Živá aplikace:** nic se nenasadilo ani nerestartovalo (žádný `docker cp`, `docker exec`, `docker restart`,
  `docker inspect mylar`), žádné volání Mylar API ani webových akcí, žádný dotaz do `mylar.db`, nic v `/comics`
  a `/downloads`, `config.ini` ani `env` se nečetly, žádná síť. `docker logs mylar` se nečetl (nebylo potřeba).
  Nic se nepushovalo ani nemergovalo.
- **Kód v `mylar/` se neměnil**, server posílá stejné odpovědi. Změněné jsou jen šablony a nový test.
- **Pomocné skripty** (mimo git) v `.scratch/fix-part3/`: `compile_templates.py` (Mako `TemplateLookup` nad
  `data/interfaces/default`, vzor z druhé části), `check_js.py` (`node --check` na každý vložený `<script>` blok,
  výrazy `${}` nahrazené `0`, řádky `%`/`##` prázdné), `per_commit.sh` (strom šablon a testů každého commitu do
  `.scratch/fix-part3/commits/` pro kontrolu, že každý commit prochází sám).

## 2. Testy

| | `tests/` (stuby, parser, nově šablony) | `tests_db/` (skutečný balík `mylar`, dočasná SQLite) |
|---|---|---|
| Výchozí stav (čistý worktree) | **96 passed** | **142 passed** |
| Konečný stav | **131 passed** (35 nových) | **142 passed** |

Nový test [tests/test_template_escaping.py](../tests/test_template_escaping.py) (bez importu `mylar`):

- **Statické kontroly:** každé místo je jmenovitě vymezené kotvami v šabloně (např. od `function ajaxcallit(` po
  `function initThisPage(`). Test chce, aby hodnota prošla `escapeHtml()` (nebo šla přes `textContent`), a regexem
  hlídá, že surové spojení (`+ obj['message'] +` v `.html(…)`, `$('<div/>').text(x)` v atributu) zmizelo.
  Upstream řádky ve stejné šabloně test záměrně nekontroluje.
- **Helper:** každá z pěti šablon definuje `escapeHtml()` právě jednou a převádí `& < > " '`.
- **Dynamicky v `node`** (když je k dispozici, v image je): helper každé šablony se spustí na
  `<img src=x onerror=1>` → `&lt;img src=x onerror=1&gt;`, `" onmouseover="alert(1)` → `&quot; onmouseover=&quot;alert(1)`,
  `null` → `''`, `5` → `'5'`.
- **Kontrolní testy** (označené „control“, procházely už před opravou): buňky tabulky pickeru
  v `comicdetails_update.html` a buňky dialogu odmítnutých shod v `upcoming.html`.

Ověření, že test opravu opravdu hlídá:

- Před opravou (test napsaný, šablony beze změny): **33 failed, 2 passed** (prošly jen 2 kontrolní).
- Po opravě: **35 passed**.
- `git stash push -- data/interfaces/default/` (šablony odložené, test zůstal): zase **33 failed, 2 passed**,
  po `git stash pop` 35 passed.
- Každý commit sám (`per_commit.sh`, `pytest --noconftest` na stromu commitu): 4, 10, 26, 32 a 35 passed.
- Mako: všech pět změněných šablon (a `base.html`) se zkompiluje. `node --check`: 11 z 11 vložených skriptových
  bloků bez chyby.

## 3. Místa v šablonách

Čísla řádků platí pro konečný stav větve. „Kód forku“ = řádek přidaný nebo změněný od `b609c28c` (`git diff`,
u sporných `git blame` a `git merge-base --is-ancestor`). Fork nemá od `b609c28c` žádný merge z upstreamu.

| Šablona | Místo (funkce, prvek) | Co se vkládá | Kód forku | Stav | Commit |
|---|---|---|---|---|---|
| `queue_management.html` | `ajaxcallit`, `#ajaxMsg` (ř. 230) | zpráva `ddl_requeue`, např. `Successfully restarted <série> [<velikost>]` | ano | **opraveno** | `3fbd3a50` |
| `queue_management.html` | render sloupce Link, tooltip `title="…"` u ⓘ (ř. 291–299) | titulek článku z GetComics (`full[9]`), typ odkazu (`full[8]`) | ano | **opraveno**: titulek byl přes `$('<div/>').text().html()`, které v atributu neescapuje `"` | `3fbd3a50` |
| `queue_management.html` | `activecheck`, `#status` (`statusText`) | `Downloading` + počet auto-resume | ano | bez textu zvenku (ve větvi je `status` vždy `Downloading`), beze změny | – |
| `queue_management.html` | `activecheck`, `#active_status_div`; `updateStatusSummary` | počet PP, souhrn stavů | ano | už bezpečné (`.text()`) | – |
| `queue_management.html` | render Options (`tbl_options`) | jen `full[5]` (id fronty) do `onclick` | ano | bez textu zvenku, beze změny | – |
| `queue_management.html` | `activecheck`, `#series`, `#filename`, `#size` (ř. 163–165) | `a_series`, `a_filename`, `a_size` | ne | upstream, mimo rozsah | – |
| `queue_management.html` | `activecheck`, `#amessage` (2×) | `status` z `check_ActiveDDL` s cestou souboru a záměrným `</br>` (text i JS z upstreamu) | ne | upstream, mimo rozsah | – |
| `queue_management.html` | render sloupců Series a Size (`full[0]`, `full[1]`) | série nebo jméno balíku z `ddl_info.series`, velikost | ne | upstream, mimo rozsah | – |
| `manage.html` | `update_manual_pp_feedback`, `#manual_pp_log` (ř. 519) | `comic`, `issue`, `result` z `manual_pp_status` | ano | **opraveno** | `f57e954b` |
| `manage.html` | `update_manual_pp_feedback`, `#manual_pp_file_log` (ř. 534) | `file`, `series`, `issue`, `status`, `reason` | ano | **opraveno** (`cls` je konstanta) | `f57e954b` |
| `manage.html` | `#manual_process`, `#ajaxMsg` (3×, ř. 589, 606, 618) | zpráva `post_process`, např. `Successfully submitted <složka> for manual post-processing...` | ano | **opraveno** | `f57e954b` |
| `manage.html` | `#manual_process`, větev IN PROGRESS, `statuschk` (ř. 605) | konstantní zpráva | ano | **opraveno** (`textContent`) | `f57e954b` |
| `manage.html` | `#manual_pp_phase`, `#manual_pp_current`, `#manual_pp_summary` | fáze, aktuální soubor, souhrn | ano | už bezpečné (`.text()`) | – |
| `manage.html` | `#manual_process`, větve success a chyba, `statuschk.innerHTML` (ř. 586, 617) | zpráva `post_process` s cestou složky | ne | upstream, mimo rozsah (otázka 1) | – |
| `manage.html` | `interactive_process` (`#manual_status`, `foldername`, `#interactive_table_body`) | zpráva, jméno složky, `series_name`, `issue_number`, `comicfilename` | ne | upstream, mimo rozsah (tlačítko je navíc zakomentované) | – |
| `comicdetails_update.html` | `getAvailableDownloads`, tabulka pickeru (ř. 1370–1385) | `nzbtitle`, `provider`, `size`, `kind`, `reason` | ano | **už escapované** (mezi tagy); `link`, `nzbid`, `tmpprov` do HTML nejdou, zůstávají v `search_results` (kontrolní test) | – |
| `comicdetails_update.html` | `downloadSpecificRelease`, `#ajaxMsg` (2×, ř. 1413, 1442) | `name` = titulek vybraného vydání (GetComics, indexer) | ano | **opraveno** | `5a2a2da3` |
| `comicdetails_update.html` | `direct_download_dialog`, `#ajaxMsg` (ř. 1507, 1510, 1518–1525) | `obj.message` (série, rozsah od uživatele, text výjimky), `xhr.responseText` | ano | **opraveno**; z chybové stránky se zobrazí jen text (otázka 2) | `5a2a2da3` |
| `comicdetails_update.html` | `run_single_metatag`, `#ajaxMsg` (ř. 1193) | číslo issue | ano | **opraveno** | `5a2a2da3` |
| `comicdetails_update.html` | `#ajaxMsg` se zprávou serveru v `annual_delete`, `mark_the_issues`, `mark_the_annuals`, `add2readinglist`, `downloadthisissue`, `unqueue_issue`, `retry_issue`, `add_wanted`, `skipped2wanted`, `fix_cv_removed` (10×) | zprávy s názvem série (`unqueueissue`, `queueissue`, `addtoreadlist`, `fix_cv_removed`), u ostatních konstanta nebo počet | ano (fork řádky změnil, přidal `.stop().removeClass()`) | **opraveno** všech 10 jednotně | `5a2a2da3` |
| `comicdetails_update.html` | `#downloads_table_status` | počet výsledků, `textStatus` | ano | už bezpečné (`.text()`) | – |
| `comicdetails_update.html` | `manual_rename`, `group_metatag`, `metatag_the_issues`, `getAvailableDownloads` (`Now searching...`) | konstantní texty | ano | bez textu zvenku, beze změny | – |
| `comicdetails_update.html` | render funkce tabulek issues a annuals | data série a issues | ne | upstream, mimo rozsah | – |
| `upcoming.html` | `mark_the_issues`, `#ajaxMsg` (ř. 326) | `markissues` vrací jen `status`, zpráva je `undefined` | ano | **opraveno** (jednotně) | `8ac51ef0` |
| `upcoming.html` | render sloupce Tier, `data-issueid` odkazu na odmítnuté shody (ř. 637) | IssueID | ano | **opraveno**: atribut přes `$('<div/>').text().html()` | `8ac51ef0` |
| `upcoming.html` | dialog odmítnutých shod, tlačítko Download: `data-nzbid`, `data-link`, `data-issueid` (ř. 864–875) | nzbid a odkaz z GetComics | ano | **opraveno**: v atributu nebyly escapované uvozovky | `8ac51ef0` |
| `upcoming.html` | dialog odmítnutých shod, buňky (ř. 869–874) | title, provider, size, kind, pubdate, reason | ano | **už escapované** (kontrolní test) | – |
| `upcoming.html` | render sloupce Tier, `titleText`, `iconHtml` | konstanty a počet odmítnutých shod | ano | bez textu zvenku, beze změny | – |
| `upcoming.html` | render sloupce Status (`status`, `tip`) | stav issue a `ddl_activity` (pevná sada hodnot ze serveru), `tip` escapuje `"` | ano | bez textu zvenku, beze změny | – |
| `upcoming.html` | render sloupce Comic (`linkit`), checkbox `value`, počty v záložkách | série, oblouk, IssueID, počty | ne | upstream, mimo rozsah | – |
| `history.html` | `retryit`, `#ajaxMsg` (ř. 98) | zpráva `retryissue`, `Successfully submitted retry for <série> (<rok>) #<číslo>` | ano | **opraveno** | `4196c72e` |
| `base.html` | `clear_notifs`, `#ajaxMsg` | konstanta + počet notifikací | ano | bez textu zvenku, beze změny | – |
| `base.html` | SSE handlery (`addbyid`, `scheduler_message`, `message`, `config_check`), `check_update` | zprávy serveru | ne (fork změnil jen sousední `.removeClass()`) | upstream, mimo rozsah | – |
| `base.html` | potlačení `alert`/`confirm` | nic se do HTML nevkládá | ano | mimo nález | – |
| `logs.html` | mazání logů, `#ajaxMsg` (6×) | konstanty, počet souborů | ano | bez textu zvenku, beze změny (stránka Logs je přijaté riziko) | – |
| `weeklypull.html` | Mass Add, `#ajaxMsg` | `p_msg` s počty | ne (fork změnil jen `.removeClass()`) | upstream, mimo rozsah | – |
| `index.html` | render názvu série, `escapeHtml` | název, svazek, typ | ano (`c7396f8c`, převzato z upstreamu `5fe57c03`) | už escapované; vydavatel a číslo jsou přijaté riziko | – |
| `config.html`, `data/js/script.js` | řádky forku (`errMode`, `.stop().removeClass()`, `refreshTable`, tlačítko Restart PP) | nic se do HTML nevkládá | ano | mimo nález | – |

**Jak oprava vypadá:** do každé z pěti šablon se na začátek jejího skriptu přidal stejný malý helper
`escapeHtml(text)` (kopie helperu z `index.html`, který převzal fork z upstreamu): převádí `& < > " '` na entity
a z `null`/`undefined` dělá prázdný řetězec. Helper je v každé šabloně zvlášť, ne v `base.html`, aby se stránka
nerozbila, kdyby se při `docker cp` vynechal jiný soubor (otázka 3). Nové JS soubory ani knihovny nepřibyly.

## 4. Otevřené otázky a konzervativní volby

1. **Upstream řádky se stejným textem zůstaly.** Zadání vylučuje řádky beze změny z upstreamu. Proto zůstaly
   neescapované např. `#series`/`#filename`/`#amessage` ve frontě (`a_filename` je jméno souboru z GetComics),
   `statuschk.innerHTML` v ručním PP (vedle opraveného `#ajaxMsg` se stejnou zprávou) a sloupec Series ve frontě.
   Jsou to stejně levné opravy jako tahle část. Je na rozhodnutí uživatele, jestli je přidat k přijatému riziku,
   nebo je jednou opravit taky (u `#amessage` by se muselo escapovat jen jméno souboru, `</br>` je záměrné).
2. **Chybová odpověď přímého DDL** (`direct_download_dialog`, `xhr.responseText`): dřív se celé tělo chyby (u
   výjimky CherryPy celá HTML stránka s tracebackem) vložilo jako HTML. Teď se tělo rozparsuje v inertním
   dokumentu `DOMParser` (skripty v něm neběží, obrázky se nenačítají) a zobrazí se jen jeho text, escapovaný.
   Prostý text chyby vypadá stejně, HTML stránka chyby se ukáže jako text bez formátování. Konzervativnější
   varianta (escapovat surové tělo) by ukazovala značky HTML.
3. **Helper v pěti kopiích**, ne jednou v `base.html` nebo `script.js`. Je to jen 7 řádků, šablony jsou tak
   samostatné a nasazení jedné z nich nezávisí na ostatních. Sjednocení je případně úklid na později.
4. **`$('<div/>').text(x).html()` neescapuje uvozovky.** Podle specifikace serializace HTML se v textu escapují jen
   `&`, `<`, `>` (a NBSP), takže vzor ze zadání chrání mezi tagy, ale ne v hodnotě atributu. Na tom stály opravené
   atributy ve frontě a v odmítnutých shodách. Ověřeno čtením specifikace, ne v prohlížeči (`node` v image nemá DOM).
   Místa, kde vzor obaluje text mezi tagy, zůstala beze změny.
5. **Zprávy bez textu zvenku v šablonách, které se upravovaly, jsou escapované taky** (např. `annual_delete`,
   `markissues`, `skipped2wanted`), aby celá šablona používala jedno pravidlo a pozdější změna zprávy na serveru
   nic neotevřela. Na vzhled to nemá vliv: zprávy těch endpointů záměrné HTML neobsahují (zkontrolováno v
   `webserve.py` a `readinglist.py`). Šablony, kde by šlo jen o takové zprávy (`base.html` `clear_notifs`,
   `logs.html`), se neměnily.
6. **Drobná změna vzhledu jen u textu s entitou:** kdyby název v DB obsahoval doslova `&amp;`, ukáže se teď
   jako `&amp;`, ne `&`. U běžného `&` je výsledek stejný.
7. **Mimo nález, jen zaznamenáno:** `downloadthisissue` volá `download_checkthis`, který v `webserve.py` není
   (server má `downloadthis`), a `retry_issue` volá `retryit`, který nic nevrací, takže `JSON.parse` v těch
   callbackách selže. Neopravováno.

## 5. Kontrola Comics a comics-nzb-hunteru

Server se neměnil, odpovědi i klíče JSON jsou stejné. Grep v `/data/Tarzan/Cursor/Comics` a
`/data/Tarzan/Cursor/scripts/apps/comics-nzb-hunter` (`*.py`, `*.sh`, `*.js`, `*.ts`, `*.json`, `*.yaml`) na webové
endpointy, jejichž zprávy dotčené šablony zobrazují (`ddl_requeue`, `check_ActiveDDL`, `queueManageIt`,
`post_process`, `manual_pp_status`, `choose_specific_download`, `download_specific_release`, `select_rejected_match`,
`get_rejected_matches`, `queue_direct_ddl`, `retryissue`, `markissues`, `unqueueissue`, `queueissue`, `addtoreadlist`,
`skipped2wanted`, `fix_cv_removed`, `annualDelete`, `manual_metatag` …): jediný nález je
`comics_nzb/mylar_client.py:224` (`mark_issue` volá `/markissues` a vrací `r.text`). Odpověď `markissues` se
nemění, takže ho oprava nerozbije. Comics webové endpointy nevolá.

## 6. Nasazení (pro uživatele)

Merge, nasazení a push jen se souhlasem uživatele. Postup podle `CLAUDE.md`:

1. Zkopírovat změněné šablony (testy se nenasazují):

   ```sh
   docker cp data/interfaces/default/queue_management.html mylar:/app/mylar/data/interfaces/default/queue_management.html
   docker cp data/interfaces/default/manage.html mylar:/app/mylar/data/interfaces/default/manage.html
   docker cp data/interfaces/default/comicdetails_update.html mylar:/app/mylar/data/interfaces/default/comicdetails_update.html
   docker cp data/interfaces/default/upcoming.html mylar:/app/mylar/data/interfaces/default/upcoming.html
   docker cp data/interfaces/default/history.html mylar:/app/mylar/data/interfaces/default/history.html
   ```

2. **Restart není potřeba.** `serve_template` ve `webserve.py` (ř. 147 a 154) vytváří při každém požadavku nový
   `TemplateLookup` bez `module_directory`, takže se šablona čte a kompiluje z disku při každém načtení stránky.
   JS je přímo ve stránce, stačí stránku v prohlížeči znovu načíst.
3. Ověřit: `docker exec mylar grep -c "function escapeHtml(text)" /app/mylar/data/interfaces/default/<šablona>`
   (1 u každé z pěti) a `docker logs mylar --tail 50` po otevření stránek (chyba Mako by se ukázala tam).
4. V prohlížeči (zde neověřeno, session nesměla sahat na živou aplikaci):
   - **Fronta DDL** (`queueManage`) během aktivního stahování: sloupec Link s ⓘ a tooltipem s titulkem článku,
     tlačítka Restart/Resume/Abort a jejich hláška (název série a velikost).
   - **Ruční PP** (`manage`, záložka post-processingu): hláška po spuštění, průběžný log a „Per-file status“ se
     jmény souborů, IN PROGRESS při druhém spuštění.
   - **Picker** na stránce série (Search & Choose): tabulka výsledků, hláška „Successfully queued/downloaded …“
     s titulkem; dialog Direct Download (úspěch i chyba).
   - **Odmítnuté shody** (`upcoming`, lupa ve sloupci Tier): tabulka a tlačítko Download (musí poslat stejné
     `nzbid` a `link` jako dřív; čtou se přes `.attr()`, entity prohlížeč dekóduje).
   - **Historie**: Retry a jeho hláška.
5. **Po nasazení je zase potřeba rebuild image** (R14): změny přes `docker cp` žijí jen ve vrstvě kontejneru a
   recreate by je tiše vrátil. Postup v kap. 9 [FOLLOWUPS-2026-11-22-part2.md](FOLLOWUPS-2026-11-22-part2.md)
   (`mylar3:candidate`, kontrola md5 a testů, přetagování, recreate jen služby `mylar` přes Dockhand).

## 7. Stav po merge

2026-11-22 (časy pražské, v závorce UTC z `docker logs`), na pokyn uživatele:

- **Merge** asi ve 22:05: `python3-dev` posunuta fast-forwardem z `ad8bba79` na `99f84416`, bez merge commitu.
  Testy na tomto stavu viz kap. 2 (strom je shodný s větví).
- **Push** na pokyn uživatele: `fork/python3-dev` `ad8bba79..c539e52c` (včetně záznamu o nasazení). Na `origin` nic.
- **Před nasazením** `docker logs mylar --tail 50`: běžela jen fronta hledání (22:08, 21:08 UTC), žádné DDL
  stahování ani post-processing.
- **`docker cp`** pěti šablon podle kap. 6 z hlavního stromu. md5 všech pěti v kontejneru = repo,
  `grep -c "function escapeHtml(text)"` = 1 v každé.
- **Bez restartu** (šablony se čtou z disku při každém požadavku, kap. 6).
- **Ověření:** `curl` z devel-workstation na `http://mylar:8090` (jen GET načtení stránek): `queueManage`,
  `manage`, `comicDetails?ComicID=160511`, `upcoming`, `history` vrátily 200, každá s novým helperem, bez chyby
  Mako. `node --check` na všech 24 vložených skriptových blocích vyrenderovaných stránek bez chyby. `docker logs
  --since 5m` po načtení bez ERROR, tracebacku i hlášky Mako.
- **Neověřeno:** v prohlížeči nic (Playwright MCP se na Mylar nedostane, kap. 8 druhé části). Akce měnící stav
  (Restart/Resume/Abort ve frontě, ruční PP, picker, přímé DDL, výběr odmítnuté shody, Retry) se nespouštěly;
  co zkontrolovat za provozu je v kap. 6, bod 4.
- **Image `mylar3:local` (`616267df`) je teď o tuto část pozadu** za běžícím kódem: recreate kontejneru by
  šablony tiše vrátil. Před dalším recreate rebuild z `python3-dev` podle kap. 9 druhé části (R14).
- Worktree `/data/Tarzan/Cursor/Mylar-review-2026-11-22-part3` a větev `claude/review-2026-11-22-part3` zatím
  zůstávají (celá větev je v `python3-dev`).
