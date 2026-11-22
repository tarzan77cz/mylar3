"""Which issue a file is filed as when post-processing has no issueid (review R18, decision Q14 a).

The file goes through the real filechecker (listFiles + matchIT, as the PP of a DDL pack or a
Manual Run does) and PostProcessor._issue_for_file picks the issue against a temp DB.
"""
import pytest

import mylar
from mylar import PostProcessor, db, filechecker

from conftest import _Config


class DefaultsConfig(_Config):
    """The test config with Mylar's default values (filechecker reads many of them)."""
    ANNUALS_ON = False
    IGNORE_COVERS = True
    IGNORE_SEARCH_WORDS = []
    FOLDER_SCAN_LOG_VERBOSE = False

    def __getattr__(self, name):
        from mylar.config import _CONFIG_DEFINITIONS
        if name in _CONFIG_DEFINITIONS:
            return _CONFIG_DEFINITIONS[name][2]
        return None


@pytest.fixture
def pick(lib, tmp_path, monkeypatch):
    monkeypatch.setattr(mylar, 'CONFIG', DefaultsConfig(str(tmp_path)))

    def run(series, numbers, filename, annuals=()):
        lib.add_series('C1', series, [], year='2000')
        for n in numbers:
            lib.add_issue('C1', n)
        for n in annuals:
            lib.add_annual('C1', n)
        folder = tmp_path / 'in'
        folder.mkdir()
        (folder / filename).write_bytes(b'0' * 4096)
        fl = filechecker.FileChecker(str(folder), justparse=True, pp_mode=True).listFiles()['comiclist'][0]
        watch = {'SeriesYear': '2000', 'LatestDate': '2020-01-01', 'ForceContinuing': 0, 'LatestIssue': '12',
                 'LatestIssueInt': 12000, 'ComicVersion': None, 'AgeRating': None, 'Type': 'Print',
                 'Publisher': None, 'Total': len(numbers), 'ComicID': 'C1', 'IsArc': False}
        cs = {'ComicName': series, 'ComicPublisher': None, 'AlternateSearch': None, 'ComicID': 'C1',
              'WatchValues': watch}
        wm = filechecker.FileChecker(watchcomic=series, Publisher=None, AlternateSearch=None, manual=watch)
        watchmatch = wm.matchIT(fl)
        assert watchmatch['process_status'] != 'fail'
        pp = PostProcessor.PostProcessor('Manual Run', str(folder))
        picked = pp._issue_for_file(cs, watchmatch, fl, db.DBConnection(), '[TEST]')
        if picked in (None, 'error'):
            return picked
        issuechk, fcdigit, temploc, annchk = picked
        return [r['IssueID'] for r in issuechk] if issuechk else []
    return run


@pytest.mark.parametrize('series, numbers, filename, issueid', [
    ('Top 10', [5, 10], 'Top 10 005 (2000).cbz', 'I5'),
    ('Kick-Ass 3', [3, 5], 'Kick-Ass 3 005 (2014).cbz', 'I5'),
    ('Infinity 8', [3, 8], 'Infinity 8 003 (2017).cbz', 'I3'),
    ('Spider-Man 2099', [5], 'Spider-Man 2099 005 (2015).cbz', 'I5'),
])
def test_pp_prefers_filechecker_issue_number(pick, series, numbers, filename, issueid):
    assert pick(series, numbers, filename) == [issueid]


def test_top_10_005_is_not_filed_over_issue_10(pick, lib):
    lib.execute("UPDATE issues SET Status='Downloaded', Location='Top 10 010 (2000).cbz' WHERE IssueID='I10'")
    assert pick('Top 10', [5, 10], 'Top 10 005 (2000).cbz') == ['I5']


def test_pack_files_go_to_their_own_issues(pick, lib, tmp_path):
    # "Top 10 #1-12": every file on its own number, none on #10 because of the series name
    results = {}
    for n in (1, 5, 12):
        for x in ('in',):
            folder = tmp_path / x
            if folder.exists():
                import shutil
                shutil.rmtree(str(folder))
        lib.execute('DELETE FROM comics')
        lib.execute('DELETE FROM issues')
        results[n] = pick('Top 10', range(1, 13), 'Top 10 %03d (2000).cbz' % n)
    assert results == {1: ['I1'], 5: ['I5'], 12: ['I12']}


def test_number_only_among_the_candidates_is_still_found(pick):
    # filechecker picks 005, the series has no #5: the other number of the name is still tried
    assert pick('Spider-Man 2099', [2099], 'Spider-Man 2099 005 (2015).cbz') == ['I2099']
