"""GetComics title and search page parsing (GC.check_for_pack, parse_search_result)."""
import pytest

from conftest import read_fixture


def _gc(env, comicname='Batman', issue='1', year='2016'):
    return env.module.GC(
        query={'comicname': comicname, 'issue': issue, 'year': year},
        provider_stat={'lastrun': 0, 'hits': 0},
    )


# ---- check_for_pack ----------------------------------------------------------------


def test_single_issue_is_not_a_pack(gc_env):
    info = _gc(gc_env).check_for_pack('Batman #123 (2023)')
    assert info['pack'] is False
    assert info['year'] == '2023'
    assert info['series'] == info['title'] == 'Batman #123 (2023)'
    assert info['gc_booktype'] == 'issue'


def test_hyphenated_series_is_not_a_pack(gc_env):
    assert _gc(gc_env).check_for_pack('Spider-Man #5 (2019)')['pack'] is False
    assert _gc(gc_env).check_for_pack('Star Wars - The High Republic #5 (2023)')['pack'] is False


def test_year_span_is_not_an_issue_range(gc_env):
    info = _gc(gc_env).check_for_pack('Miss Fury Sensational Sundays 1941-1944 (2013)')
    assert info['pack'] is False


def test_range_with_hash(gc_env, gc_parse):
    info = _gc(gc_env).check_for_pack('Western Outlaws #1 - 21 (1954-1957)')
    assert info['pack'] is True
    assert info['year'] == '1954-1957'
    assert info['series'] == 'Western Outlaws'
    assert gc_parse.issue_numbers(info['issues']) == list(range(1, 22))


def test_range_without_hash_keeps_first_digit(gc_env, gc_parse):
    # Used to give "2 - 15".
    info = _gc(gc_env).check_for_pack('Batman 12 - 15 (1940)')
    assert info['pack'] is True
    assert gc_parse.issue_numbers(info['issues']) == [12, 13, 14, 15]


def test_range_at_end_of_title(gc_env):
    # "#1-15" as the last token was not a pack.
    info = _gc(gc_env).check_for_pack('Batman #1-15 (1940)')
    assert info['pack'] is True
    assert info['issues'] == '1-15'


@pytest.mark.parametrize('title', ['Zero Hour #-1 (1994)', 'Batman #5 X-23 (2025)', 'X-Men #0-A (1995)'])
def test_dash_after_hash_needs_a_clean_range(gc_env, title):
    # Review R5: a single issue with a dash after '#' was taken for a pack.
    assert _gc(gc_env).check_for_pack(title)['pack'] is False


def test_short_range_at_end_of_title_is_a_pack(gc_env):
    info = _gc(gc_env).check_for_pack('Batman #1-3 (2025)')
    assert info['pack'] is True
    assert info['issues'] == '1-3'


def test_ampersand_inside_series_name(gc_env):
    # " & " used to cut the series down to "Batman".
    info = _gc(gc_env).check_for_pack('Batman & Robin #1 - 26 (2009-2011)')
    assert info['pack'] is True
    assert info['series'] == 'Batman & Robin'


def test_ampersand_annuals_receipt(gc_env):
    info = _gc(gc_env).check_for_pack('Daredevil #1 - 50 & Annuals (1964-1969)')
    assert info['pack'] is True
    assert info['annuals'] is True
    assert info['series'] == 'Daredevil'


def test_bracketed_year_wins(gc_env):
    # The first four digits used to be taken: 2000.
    assert _gc(gc_env).check_for_pack('2000 AD #1999 (2016)')['year'] == '2016'


@pytest.mark.parametrize('title,booktype', [
    ('Saga Vol. 1 - 9 TPB (2012-2018)', 'TPB'),   # TPB in the last 6 characters was missed
    ('Signal Vol. 1 - 3 (2015)', 'TPB/GN/HC/One-Shot'),  # "gn" inside a word is not GN
])
def test_volume_pack_booktype(gc_env, gc_parse, title, booktype):
    info = _gc(gc_env).check_for_pack(title)
    assert info['pack'] is True
    assert info['gc_booktype'] == booktype


def test_volume_pack_two_digit_start(gc_env, gc_parse):
    info = _gc(gc_env).check_for_pack('Saga Vol. 10 - 12 (2022)')
    assert info['pack'] is True
    assert gc_parse.issue_numbers(info['issues']) == [10, 11, 12]


# ---- range helpers -----------------------------------------------------------------


@pytest.mark.parametrize('text,expected', [
    ('1-5, 7 + TPBs', [1, 2, 3, 4, 5, 7]),
    ('#1 - 21', list(range(1, 22))),
    ('1-5, 7-9', [1, 2, 3, 4, 5, 7, 8, 9]),
    ('1 - 5', [1, 2, 3, 4, 5]),
    ('1 – 125 + 503 – 505', list(range(1, 126)) + [503, 504, 505]),
    ('', []),
    (None, []),
])
def test_issue_numbers(gc_parse, text, expected):
    assert gc_parse.issue_numbers(text) == expected


def test_gc_issue_list_returns_numbers(gc_env):
    assert _gc(gc_env).issue_list('1 - 3, 5') == [1, 2, 3, 5]


@pytest.mark.parametrize('text,expected', [
    ('1-50 + Annual 1-3', (list(range(1, 51)), [1, 2, 3], True)),
    ('#1 - 4 & Annuals', ([1, 2, 3, 4], [], True)),
    ('1-5, 7-9', ([1, 2, 3, 4, 5, 7, 8, 9], [], False)),
])
def test_split_annual_numbers(gc_parse, text, expected):
    assert gc_parse.split_annual_numbers(text) == expected


@pytest.mark.parametrize('issue_range,expected', [
    ('Annual 1-3', '1'),           # review R8: used to be 'Annual 1'
    ('Annuals #2 - 4', '2'),
    ('1-10 + Annual 1-3', '1'),
    ('#1 - 6', '1'),
    ('0-25', '0'),
    ('26-50', '26'),
    ('7', '7'),
])
def test_direct_ddl_check_issue(gc_parse, issue_range, expected):
    assert gc_parse.direct_ddl_check_issue(issue_range) == expected


# ---- search result page ------------------------------------------------------------


def test_search_page_real(gc_env):
    results, next_url = _gc(gc_env, 'Plastic Man', '1', '2018').parse_search_result(
        read_fixture('search_plastic_man_p1.html'), 200
    )
    assert next_url == 'https://getcomics.org/page/2/?s=Plastic+Man'
    assert len(results) == 12
    single = [r for r in results if r['title'] == 'Plastic Man No More! #4 (2024)'][0]
    assert single['pack'] is False and single['size'] == '97M' and single['year'] == '2024'
    pack = results[-1]
    assert pack['pack'] is True and pack['issues'] == '#1 - 6' and pack['year'] == '2018'


def test_search_page_without_results(gc_env):
    results, next_url = _gc(gc_env).parse_search_result(read_fixture('search_no_results.html'), 200)
    assert results == [] and next_url is None


SEARCH_HTML = """
<html><body>
<article id="post-1">
  <h1 class="post-title"><a href="https://getcomics.org/marvel/week-1/">Marvel Week+ (11.19.2026)</a></h1>
  <p style="text-align: center;"><strong>Year :</strong> 2026 | <strong>Size :</strong> 2 GB</p>
  <time datetime="2026-11-19">Nov 19</time>
</article>
<article id="post-2">
  <h1 class="post-title"><a href="https://getcomics.org/dc/batman-1/">Batman #1 (2016)</a></h1>
  <p style="text-align: center;"><strong>Year :</strong> 2016 | <strong>Size :</strong> 40 MB</p>
  <time datetime="2016-06-01">Jun 1</time>
</article>
<article id="post-3">
  <h1 class="post-title"><a href="https://getcomics.org/dc/batman-2/">Batman #2 (2016)</a></h1>
  <p style="text-align: center;"><strong>Year :</strong> 2016</p>
  <time datetime="2016-06-15">Jun 15</time>
</article>
</body></html>
"""


def test_weekly_bundles_are_skipped(gc_env):
    results, _ = _gc(gc_env).parse_search_result(SEARCH_HTML, 200)
    assert [r['id'] for r in results] == ['2', '3']


def test_weekly_bundle_kept_when_searched_for(gc_env):
    results, _ = _gc(gc_env, comicname='Marvel Week+').parse_search_result(SEARCH_HTML, 200)
    assert '1' in [r['id'] for r in results]


def test_post_without_size_does_not_inherit_previous_size(gc_env):
    results, _ = _gc(gc_env).parse_search_result(SEARCH_HTML, 200)
    by_id = {r['id']: r for r in results}
    assert by_id['2']['size'] == '40M'
    # No Size field: no size (search_filer then skips the size limits), not "Jun15".
    assert by_id['3']['size'] is None
