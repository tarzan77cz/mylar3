"""GC.parse_downloadresults on real GetComics post pages: sections, hosts, failed-host retry."""
import pytest

from conftest import read_fixture

MAINLINK = 'https://getcomics.org/?p=1'


def _single(issue, comyear='1950', issuedate='0000-00-00'):
    return [{'booktype': 'Print', 'pack': False, 'IssueID': 'I1', 'ComicID': 'C1', 'oneoff': False,
             'IssueNumber': issue, 'comyear': comyear, 'IssueDate': issuedate}]


def _run(env, html, comicinfo, packinfo=None, ltf=None, section=None, post_id='1', **kwargs):
    gc = env.module.GC(issueid='I1', comicid='C1', oneoff=False)
    with open(gc._html_cache_path(post_id) + '.html', 'w', encoding='utf-8') as fh:
        fh.write(html)
    result = gc.parse_downloadresults(post_id, MAINLINK, comicinfo, packinfo, ltf, section=section, **kwargs)
    return result, env.mylar.DDL_QUEUE.items


def _hrefs(queued):
    return [q['link'].split('/dls/')[-1][:8] for q in queued]


# ---- several sections on one page (bug 16) -------------------------------------------


def test_single_issue_takes_its_own_subpack(gc_env):
    res, queued = _run(gc_env, read_fixture('post_tomahawk_subpacks.html'), _single('75'))
    assert res['success'] is True
    assert len(queued) == 1
    # Mylar prefers the mirror of a normal section (site_position keeps the last 'normal:main').
    assert queued[0]['link_type'] == 'GC-Mirror'
    assert _hrefs(queued) == ['tL7bKzrJ']  # mirror of "#71 - 140"
    assert queued[0]['series'] == 'Tomahawk #71 – 140'


def test_single_issue_in_first_subpack(gc_env):
    res, queued = _run(gc_env, read_fixture('post_tomahawk_subpacks.html'), _single('5'))
    assert _hrefs(queued) == ['Tk21XqaT']  # mirror of "#1 - 70" (used to be the "#71 - 140" one)
    assert queued[0]['series'] == 'Tomahawk #1 – 70'
    upserted = [vals for table, vals, ctrl in gc_env.db.upserts if table == 'ddl_info']
    assert upserted[0]['series'] == 'Tomahawk #1 – 70'


def test_pack_queues_every_matching_subpack(gc_env):
    packinfo = {'pack': True, 'pack_numbers': '1 - 140',
                'pack_issuelist': {'issue_range': list(range(1, 141)), 'issues': [], 'valid': True}}
    comicinfo = [dict(_single('1')[0], pack=True)]
    res, queued = _run(gc_env, read_fixture('post_tomahawk_subpacks.html'), comicinfo, packinfo)
    assert res['success'] is True
    assert [q['id'] for q in queued] == ['1-1', '1-2']
    assert [q['section'] for q in queued] == [0, 1]
    assert [q['series'] for q in queued] == ['Tomahawk #1 – 70', 'Tomahawk #71 – 140']


def test_subpacks_carry_the_pack_id_and_their_issues(gc_env):
    # Review R2: PACK_ISSUEIDS_DONT_QUEUE and nzblog hold the post id '1', not '1-1' / '1-2'.
    packinfo = {'pack': True, 'pack_numbers': '1 - 140',
                'pack_issuelist': {'issue_range': list(range(1, 141)), 'issues': [], 'valid': True}}
    comicinfo = [dict(_single('1')[0], pack=True)]
    res, queued = _run(gc_env, read_fixture('post_tomahawk_subpacks.html'), comicinfo, packinfo)
    assert [q['pack_id'] for q in queued] == ['1', '1']
    assert [q['section_issues'] for q in queued] == [list(range(1, 71)), list(range(71, 141))]
    assert [q['section_annual'] for q in queued] == [False, False]


def test_single_issue_item_has_its_own_pack_id(gc_env):
    res, queued = _run(gc_env, read_fixture('post_tomahawk_subpacks.html'), _single('75'))
    assert queued[0]['pack_id'] == '1'
    assert queued[0]['id'] == '1'


def test_retry_of_one_section_keeps_its_id(gc_env):
    packinfo = {'pack': True, 'pack_numbers': '1 - 140',
                'pack_issuelist': {'issue_range': list(range(1, 141)), 'issues': [], 'valid': True}}
    comicinfo = [dict(_single('1')[0], pack=True)]
    res, queued = _run(gc_env, read_fixture('post_tomahawk_subpacks.html'), comicinfo, packinfo,
                       ltf=['GC-Mirror'], section=1, post_id='1-2')
    assert [q['id'] for q in queued] == ['1-2']
    assert queued[0]['link_type'] == 'GC-Main'
    assert _hrefs(queued) == ['dAdyh5Z3']  # Download Now of "#71 - 140"


# ---- retry of one section of a pack (review R1) --------------------------------------

HDR = ('<p style="text-align: center;"><strong>%s</strong><br /><strong>Language :</strong> English | '
       '<strong>Year :</strong> %s | <strong>Size :</strong> %s</p>\n')
BTN = '<p style="text-align: center;"><div class="aio-pulse"><a href="%s" title="%s">%s</a></div></p>\n'
READ = BTN % ('https://getcomics.org/read/x', 'Read Online', 'Read Online')
END = '<p style="text-align: center;">Click HERE to give us your support and donation.</p>\n'


def _btn(slug, title):
    return BTN % ('https://getcomics.org/dls/' + slug, title, title)


def _packinfo(lo, hi):
    return {'pack': True, 'pack_numbers': '%s - %s' % (lo, hi),
            'pack_issuelist': {'issue_range': list(range(lo, hi + 1)), 'issues': [], 'valid': True}}


def _packci():
    return [dict(_single('1', '1952', '1952-01-01')[0], pack=True)]


# Section 0 has only Download Now, sections 1 and 2 also Pixeldrain (review scenario P2).
P2_HTML = (HDR % ('Old Comic #1 - 10', '1952', '300 MB') + _btn('s0-main', 'Download Now') + READ
           + HDR % ('Old Comic #11 - 20', '1952', '300 MB') + _btn('s1-main', 'Download Now')
           + _btn('s1-pixel', 'PIXELDRAIN Link') + READ
           + HDR % ('Old Comic #21 - 30', '1952', '300 MB') + _btn('s2-main', 'Download Now')
           + _btn('s2-pixel', 'PIXELDRAIN Link') + READ + END)


def _p2_first_queue(gc_env):
    res, queued = _run(gc_env, P2_HTML, _packci(), _packinfo(1, 30))
    first = list(queued)
    gc_env.mylar.DDL_QUEUE.items[:] = []
    assert [q['id'] for q in first] == ['1-1', '1-2', '1-3']
    return first


@pytest.mark.parametrize('n,slug', [(1, 's1-pixel'), (2, 's2-pixel')])
def test_section_retry_after_host_failure_keeps_its_section(gc_env, n, slug):
    item = _p2_first_queue(gc_env)[n]
    res, queued = _run(gc_env, P2_HTML, _packci(), _packinfo(1, 30), ltf=['GC-Main'],
                       section=item['section'], post_id=item['id'], pack_id=item['pack_id'],
                       section_key=item['section_key'])
    assert res['success'] is True
    assert [q['id'] for q in queued] == [item['id']]  # never '1-3-1'
    assert [q['link'] for q in queued] == ['https://getcomics.org/dls/' + slug]
    assert queued[0]['section'] == item['section']
    assert queued[0]['section_key'] == item['section_key']


@pytest.mark.parametrize('section,post_id,slug', [(1, '1-2', 's1-pixel'), (2, '1-3', 's2-pixel')])
def test_section_index_survives_the_failed_host_filter(gc_env, section, post_id, slug):
    # Items queued before the section key existed carry only the index.
    res, queued = _run(gc_env, P2_HTML, _packci(), _packinfo(1, 30), ltf=['GC-Main'],
                       section=section, post_id=post_id)
    assert [q['id'] for q in queued] == [post_id]
    assert [q['link'] for q in queued] == ['https://getcomics.org/dls/' + slug]


def test_section_retry_fails_when_the_section_is_gone(gc_env):
    item = _p2_first_queue(gc_env)[1]
    changed = P2_HTML.replace('Old Comic #11 - 20', 'Old Comic #11 - 19')
    res, queued = _run(gc_env, changed, _packci(), _packinfo(1, 30), ltf=['GC-Main'],
                       section=item['section'], post_id=item['id'], pack_id=item['pack_id'],
                       section_key=item['section_key'])
    assert res['success'] is False
    assert queued == []


def test_section_retry_out_of_range_fails(gc_env):
    res, queued = _run(gc_env, P2_HTML, _packci(), _packinfo(1, 30), ltf=['GC-Main'],
                       section=7, post_id='1-8', pack_id='1')
    assert res['success'] is False
    assert queued == []


def test_section_retry_finds_a_moved_section_by_key(gc_env):
    item = _p2_first_queue(gc_env)[2]
    # A new section in front of it: the stored index points at the wrong one now.
    moved = HDR % ('Old Comic #0', '1952', '30 MB') + _btn('new-pixel', 'PIXELDRAIN Link') + READ + P2_HTML
    res, queued = _run(gc_env, moved, _packci(), _packinfo(1, 30), ltf=['GC-Main'],
                       section=item['section'], post_id=item['id'], pack_id=item['pack_id'],
                       section_key=item['section_key'])
    assert [q['link'] for q in queued] == ['https://getcomics.org/dls/s2-pixel']
    assert [q['id'] for q in queued] == ['1-3']


@pytest.mark.parametrize('issuedate,expected', [
    ('1944-03-01', 'Plastic Man Vol. 1 #1 – 64'),
    ('1966-12-01', 'Plastic Man Vol. 2 #1 – 20'),
])
def test_volume_picked_by_year(gc_env, issuedate, expected):
    res, queued = _run(gc_env, read_fixture('post_plastic_man_volumes.html'), _single('5', '1943', issuedate))
    assert [q['series'] for q in queued] == [expected]


EDITIONS_HTML = """
<div class="post-contents">
<p style="text-align: center;"><strong>The Forged #15 (Empire)</strong><br /><strong>Language :</strong> English | <strong>Year :</strong> 2026 | <strong>Size :</strong> 120 MB</p>
<p style="text-align: center;"><div class="aio-pulse"><a href="https://getcomics.org/dls/empire-main" title="Download Now">Download Now</a></div></p>
<p style="text-align: center;"><strong>The Forged #15 (Series)</strong><br /><strong>Language :</strong> English | <strong>Year :</strong> 2026 | <strong>Size :</strong> 128 MB</p>
<p style="text-align: center;"><div class="aio-pulse"><a href="https://getcomics.org/dls/series-main" title="Download Now">Download Now</a></div></p>
<p style="text-align: center;">Click HERE to give us your support and donation.</p>
</div>
"""


def test_two_editions_of_one_issue_keep_the_last_section(gc_env):
    # Same download as before the fix (the last section), now with its own header text.
    res, queued = _run(gc_env, EDITIONS_HTML, _single('15', '2026'))
    assert [q['link'] for q in queued] == ['https://getcomics.org/dls/series-main']
    assert queued[0]['series'] == 'The Forged #15 (Series)'


VARIANTS_HTML = """
<p style="text-align: center;"><strong>Batman #123 (HD-Upscaled)</strong><br/><strong>Language :</strong> English | <strong>Year :</strong> 2023 | <strong>Size :</strong> 120 MB</p>
<p style="text-align: center;"><div class="aio-pulse"><a href="https://getcomics.org/dls/up-main" title="Download Now">Download Now</a></div></p>
<p style="text-align: center;"><div class="aio-pulse"><a href="https://getcomics.org/dls/up-mirror" title="Mirror Download">Mirror</a></div></p>
<p style="text-align: center;"><div class="aio-pulse"><a href="https://getcomics.org/read/1" title="Read Online">Read Online</a></div></p>
<p style="text-align: center;"><strong>Batman #123 (HD-Digital)</strong><br/><strong>Language :</strong> English | <strong>Year :</strong> 2023 | <strong>Size :</strong> 40 MB</p>
<p style="text-align: center;"><div class="aio-pulse"><a href="https://getcomics.org/dls/hd-main" title="Download Now">Download Now</a></div></p>
<p style="text-align: center;"><div class="aio-pulse"><a href="https://getcomics.org/dls/hd-pixel" title="PIXELDRAIN Link">PIXELDRAIN</a></div></p>
<p style="text-align: center;"><div class="aio-pulse"><a href="https://getcomics.org/read/2" title="Read Online">Read Online</a></div></p>
<p style="text-align: center;">Please consider support and donation</p>
"""


def test_variants_stay_one_download(gc_env):
    res, queued = _run(gc_env, VARIANTS_HTML, _single('123', '2023'))
    assert len(queued) == 1
    assert queued[0]['link'] == 'https://getcomics.org/dls/up-main'
    assert queued[0]['link_type'] == 'GC-Main'


# ---- failed hosts (bugs 1 and 8) ---------------------------------------------------


def test_failed_main_keeps_mirror(gc_env):
    # A failed GC-Main used to exclude "Mirror Download" too.
    res, queued = _run(gc_env, VARIANTS_HTML, _single('123', '2023'), ltf=['GC-Main'])
    assert queued[0]['link'] == 'https://getcomics.org/dls/up-mirror'
    assert queued[0]['link_type'] == 'GC-Mirror'


def test_single_section_hosts_in_priority_order(gc_env):
    res, queued = _run(gc_env, read_fixture('post_dynomutt_hosts.html'), _single('3', '1977'))
    assert queued[0]['link_type'] == 'GC-Main'
    gc_env.mylar.DDL_QUEUE.items[:] = []
    res, queued = _run(gc_env, read_fixture('post_dynomutt_hosts.html'), _single('3', '1977'), ltf=['GC-Main'])
    assert queued[0]['link_type'] == 'GC-Pixel'


def test_direct_main_link_post(gc_env):
    res, queued = _run(gc_env, read_fixture('post_journey_direct_main.html'), _single('5', '1952'))
    assert queued[0]['link_type'] == 'GC-Mirror'
    gc_env.mylar.DDL_QUEUE.items[:] = []
    res, queued = _run(gc_env, read_fixture('post_journey_direct_main.html'), _single('5', '1952'), ltf=['GC-Mirror'])
    assert queued[0]['link_type'] == 'GC-Main'
    assert queued[0]['link'].startswith('https://light.getcomics.info/')
    gc_env.mylar.DDL_QUEUE.items[:] = []
    res, queued = _run(gc_env, read_fixture('post_journey_direct_main.html'), _single('5', '1952'), ltf=['GC-Mirror', 'GC-Main'])
    assert queued[0]['link_type'] == 'GC-Media'


FALLBACK_HTML = """
<p style="text-align: center;"><strong>Old Comic #1 - 10</strong><br/><strong>Language :</strong> English | <strong>Year :</strong> 1952 | <strong>Size :</strong> 300 MB</p>
<p style="text-align: center;"><div class="aio-pulse"><a href="https://getcomics.org/dlds/px1" title="PIXELDRAIN Link">PIXELDRAIN</a></div></p>
<p style="text-align: center;">Please consider support and donation</p>
<a href="https://getcomics.org/dlds/main1" title="Download Now">Download Now</a>
"""


def test_dlds_fallback_finds_plain_main_button(gc_env):
    res, queued = _run(gc_env, FALLBACK_HTML, _single('3', '1952'))
    assert queued[0]['link'] == 'https://getcomics.org/dlds/main1'


def test_dlds_fallback_skips_failed_main(gc_env):
    # The fallback used to add the failed main button back, so the retry looped on it.
    res, queued = _run(gc_env, FALLBACK_HTML, _single('3', '1952'), ltf=['GC-Main'])
    assert queued[0]['link'] == 'https://getcomics.org/dlds/px1'
    gc_env.mylar.DDL_QUEUE.items[:] = []
    res, queued = _run(gc_env, FALLBACK_HTML, _single('3', '1952'), ltf=['GC-Main', 'GC-Pixel'])
    assert queued == []
    assert res['success'] is False


def test_fallback_finds_current_dls_buttons(gc_env):
    # GetComics moved its buttons from /dlds/ to /dls/; the fallback only knew /dlds/.
    html = FALLBACK_HTML.replace('/dlds/main1', '/dls/main1')
    res, queued = _run(gc_env, html, _single('3', '1952'))
    assert queued[0]['link'] == 'https://getcomics.org/dls/main1'


# ---- second fallback on a page with several sections (review R6) -----------------------

# Review scenario P3: section #1 - 10 has Pixeldrain and Mirror in one <p> (the main pass
# reads only the first <a>), section #11 - 20 only Pixeldrain.
P3_HTML = (HDR % ('Old Comic #1 - 10', '1952', '300 MB')
           + '<p style="text-align: center;"><div class="aio-pulse"><a href="https://getcomics.org/dls/s0-pixel"'
             ' title="PIXELDRAIN Link">PIXELDRAIN</a> <a href="https://getcomics.org/dls/s0-mirror"'
             ' title="Mirror Download">Mirror</a></div></p>\n' + READ
           + HDR % ('Old Comic #11 - 20', '1952', '300 MB') + _btn('s1-pixel', 'PIXELDRAIN Link') + READ + END)


def test_fallback_button_belongs_to_the_section_before_it(gc_env):
    res, queued = _run(gc_env, P3_HTML, _single('15', '1953', '1953-01-01'))
    assert [q['link'] for q in queued] == ['https://getcomics.org/dls/s1-pixel']
    gc_env.mylar.DDL_QUEUE.items[:] = []
    res, queued = _run(gc_env, P3_HTML, _single('5', '1953', '1953-01-01'))
    # #5 lives in section #1 - 10: its Mirror (found by the fallback) beats Pixeldrain.
    assert [(q['link'], q['series']) for q in queued] == [
        ('https://getcomics.org/dls/s0-mirror', 'Old Comic #1 - 10')]


def test_fallback_button_without_a_section_is_skipped(gc_env):
    html = ('<a href="https://getcomics.org/dls/stray" title="Download Now">Download Now</a>\n'
            + HDR % ('Old Comic #1 - 10', '1952', '300 MB') + _btn('s0-pixel', 'PIXELDRAIN Link') + READ
            + HDR % ('Old Comic #11 - 20', '1952', '300 MB') + _btn('s1-pixel', 'PIXELDRAIN Link') + READ + END)
    res, queued = _run(gc_env, html, _single('15', '1953', '1953-01-01'))
    assert [q['link'] for q in queued] == ['https://getcomics.org/dls/s1-pixel']


# ---- buttons without a title attribute (review R7) -------------------------------------

BTN_NOTITLE = '<p style="text-align: center;"><div class="aio-pulse"><a href="%s">%s</a></div></p>\n'
MISSING_TITLE_LINK = (HDR % ('Batman #123', '2023', '40 MB')
                      + BTN_NOTITLE % ('https://getcomics.org/dls/nt', 'Download Now')
                      + _btn('n-pixel', 'PIXELDRAIN Link') + READ + END)
MISSING_TITLE_THEN_READ = (HDR % ('Batman #123', '2023', '40 MB') + _btn('n-main', 'Download Now')
                           + BTN_NOTITLE % ('https://getcomics.org/read/1', 'Read Online')
                           + HDR % ('Batman #123 (Variant)', '2023', '41 MB') + _btn('v-pixel', 'PIXELDRAIN Link')
                           + READ + END)


def test_button_without_title_is_read_from_its_text(gc_env):
    res, queued = _run(gc_env, MISSING_TITLE_LINK, _single('123', '2023'))
    assert [(q['link'], q['link_type']) for q in queued] == [('https://getcomics.org/dls/nt', 'GC-Main')]


def test_button_without_title_and_failed_hosts(gc_env):
    res, queued = _run(gc_env, MISSING_TITLE_LINK, _single('123', '2023'), ltf=['GC-Main'])
    assert [q['link_type'] for q in queued] == ['GC-Pixel']
    gc_env.mylar.DDL_QUEUE.items[:] = []
    # The working Download Now without a title used to be lost once Pixeldrain failed.
    res, queued = _run(gc_env, MISSING_TITLE_LINK, _single('123', '2023'), ltf=['GC-Pixel'])
    assert res['success'] is True
    assert [(q['link'], q['link_type']) for q in queued] == [('https://getcomics.org/dls/nt', 'GC-Main')]


def test_read_online_without_title_is_not_a_download(gc_env):
    res, queued = _run(gc_env, MISSING_TITLE_THEN_READ, _single('123', '2023'))
    assert res['success'] is True
    assert [q['link'] for q in queued] == ['https://getcomics.org/dls/v-pixel']
    gc_env.mylar.DDL_QUEUE.items[:] = []
    res, queued = _run(gc_env, MISSING_TITLE_THEN_READ, _single('123', '2023'), ltf=['GC-Pixel'])
    assert [q['link'] for q in queued] == ['https://getcomics.org/dls/n-main']


@pytest.mark.parametrize('url,expected', [
    ('https://getcomics.org/dls/abc', True),
    ('https://getcomics.org/dlds/abc', True),
    ('https://pixeldrain.com/u/abc', False),
    ('https://getcomics.org/other-comics/dls-review/', False),
    (None, False),
])
def test_is_button_link(gc_parse, url, expected):
    assert gc_parse.is_button_link(url) is expected


# ---- pure helpers ------------------------------------------------------------------


@pytest.mark.parametrize('site,failures,expected', [
    ('download now', ['GC-Main'], True),
    ('mirror download', ['GC-Main'], False),
    ('mirror download', ['GC-Mirror'], True),
    ('pixeldrain', ['GC-Pixel'], True),
    ('mediafire', ['GC-Pixel'], False),
    ('ufile', ['GC-Main', 'GC-Mirror'], False),
    ('download now', None, False),
])
def test_site_failed(gc_parse, site, failures, expected):
    assert gc_parse.site_failed(site, failures) is expected


def test_choose_sections_rules(gc_parse):
    subpacks = [{'numbers': list(range(1, 71)), 'years': (1950, 1972)},
                {'numbers': list(range(71, 141)), 'years': (1950, 1972)}]
    assert gc_parse.choose_sections(subpacks, [80]) == [1]
    assert gc_parse.choose_sections(subpacks, [5]) == [0]
    assert gc_parse.choose_sections(subpacks, list(range(1, 141)), pack=True) == [0, 1]
    unknown = [{'numbers': [], 'years': None}, {'numbers': [], 'years': None}]
    assert gc_parse.choose_sections(unknown, [5]) == [1]
    assert gc_parse.choose_sections([{'numbers': [5], 'years': None}], [7]) == [0]


# ---- year of a pack decides only between overlapping sections (review R3) -------------


def test_pack_keeps_subpacks_with_other_years(gc_parse):
    subpacks = [{'numbers': list(range(1, 71)), 'years': (1950, 1960)},
                {'numbers': list(range(71, 141)), 'years': (1960, 1972)}]
    assert gc_parse.choose_sections(subpacks, list(range(1, 141)), 1950, pack=True) == [0, 1]
    assert gc_parse.choose_sections(subpacks, list(range(1, 141)), 1965, pack=True) == [0, 1]


def test_pack_year_picks_the_volume(gc_parse):
    volumes = [{'numbers': list(range(1, 65)), 'years': (1943, 1956)},
               {'numbers': list(range(1, 21)), 'years': (1966, 1967)}]
    assert gc_parse.choose_sections(volumes, list(range(1, 65)), 1943, pack=True) == [0]
    assert gc_parse.choose_sections(volumes, list(range(1, 21)), 1966, pack=True) == [1]


def test_pack_overlap_without_year_keeps_most_wanted_then_last(gc_parse):
    volumes = [{'numbers': list(range(1, 65)), 'years': None},
               {'numbers': list(range(1, 21)), 'years': None}]
    assert gc_parse.choose_sections(volumes, list(range(1, 65)), None, pack=True) == [0]
    same = [{'numbers': list(range(1, 11)), 'years': None},
            {'numbers': list(range(5, 15)), 'years': None}]
    assert gc_parse.choose_sections(same, list(range(5, 11)), None, pack=True) == [1]


def test_pack_overlap_groups_and_free_subpacks(gc_parse):
    # Two volumes of #1-10 (overlap, year decides) next to a sub-pack #11-20 of its own.
    sections = [{'numbers': list(range(1, 11)), 'years': (1950, 1952)},
                {'numbers': list(range(1, 11)), 'years': (1990, 1992)},
                {'numbers': list(range(11, 21)), 'years': (1953, 1955)}]
    assert gc_parse.choose_sections(sections, list(range(1, 21)), 1950, pack=True) == [0, 2]


def test_plastic_man_pack_takes_only_its_volume(gc_env):
    packinfo = {'pack': True, 'pack_numbers': '1 - 64',
                'pack_issuelist': {'issue_range': list(range(1, 65)), 'issues': [], 'valid': True}}
    comicinfo = [dict(_single('1', '1943', '1943-08-01')[0], pack=True)]
    res, queued = _run(gc_env, read_fixture('post_plastic_man_volumes.html'), comicinfo, packinfo)
    assert [q['series'] for q in queued] == ['Plastic Man Vol. 1 #1 – 64']


# ---- a pack queued only partly (review R4) ---------------------------------------------

# Review scenario P4: only Pixeldrain is allowed, sub-pack #11 - 20 has only Download Now.
P4_HTML = (HDR % ('Old Comic #1 - 10', '1952', '300 MB') + _btn('s0-pixel', 'PIXELDRAIN Link') + READ
           + HDR % ('Old Comic #11 - 20', '1952', '300 MB') + _btn('s1-main', 'Download Now') + READ + END)


def test_partly_queued_pack_reports_the_missing_section(gc_env):
    gc_env.config.DDL_PRIORITY_ORDER = ['pixeldrain']
    res, queued = _run(gc_env, P4_HTML, _packci(), _packinfo(1, 20))
    assert res['success'] is True
    assert [q['id'] for q in queued] == ['1-1']
    assert res['unqueued_sections'] == [
        {'series': 'Old Comic #11 - 20', 'issues': list(range(11, 21)), 'annual': False}
    ]


def test_fully_queued_pack_has_no_missing_sections(gc_env):
    res, queued = _run(gc_env, P4_HTML, _packci(), _packinfo(1, 20))
    assert res['success'] is True
    assert len(queued) == 2
    assert not res.get('unqueued_sections')


def test_pack_with_nothing_queued_still_fails(gc_env):
    gc_env.config.DDL_PRIORITY_ORDER = ['mega']
    res, queued = _run(gc_env, P4_HTML, _packci(), _packinfo(1, 20))
    assert res['success'] is False
    assert queued == []
