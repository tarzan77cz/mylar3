"""An error in the bulk/RSS branch of searchforissue must not leave SEARCHLOCK set (review R25)."""
import pytest

import mylar
from mylar import helpers, search


STORYARCS = ('CREATE TABLE storyarcs (IssueArcID TEXT, IssueID TEXT, ComicID TEXT, ComicName TEXT, IssueNumber TEXT,'
             ' Status TEXT, ReleaseDate TEXT, IssueDate TEXT, DigitalDate TEXT, StoryArc TEXT, StoryArcID TEXT,'
             ' DateAdded TEXT)')


@pytest.fixture
def rss_search(lib, monkeypatch):
    lib.execute(STORYARCS)
    lib.add_series('C1', 'Batman', [], year='2025')
    lib.execute("UPDATE comics SET ComicName_Filesafe='Batman', IgnoreType=0, AllowPacks=0")
    # I1 is broken (no ComicName in issues) and sorts first by its later store date
    for issueid, name, date in (('I1', None, '2025-02-05'), ('I2', 'Batman', '2025-01-08')):
        lib.execute("INSERT INTO issues (IssueID, ComicName, Issue_Number, Status, ComicID, IssueDate, ReleaseDate,"
                    " DigitalDate, DateAdded) VALUES (?, ?, ?, 'Wanted', 'C1', ?, ?, '0000-00-00', '2025-01-01')",
                    (issueid, name, issueid[1:], date, date))
    cfg = mylar.CONFIG
    cfg.ENABLE_DDL = True
    cfg.ENABLE_GETCOMICS = True
    cfg.EXTRA_NEWZNABS = []
    cfg.EXTRA_TORZNABS = []
    monkeypatch.setattr(mylar, 'SEARCHLOCK', False, raising=False)
    monkeypatch.setattr(search.time, 'sleep', lambda *a: None)
    monkeypatch.setattr(search, 'provider_order', lambda *a, **k: {})
    logged = {'exceptions': [], 'except_lines': []}
    monkeypatch.setattr(helpers, 'log_that_exception', lambda info: logged['except_lines'].append(info))
    monkeypatch.setattr(search.logger, 'exception', lambda msg, *a, **k: logged['exceptions'].append(str(msg)))
    rss = {'lists': []}

    def nzbdbsearch(*args, **kwargs):
        rss['lists'].append(kwargs.get('rsslist'))
        return {'entries': []}
    monkeypatch.setattr(mylar.rsscheck, 'nzbdbsearch', nzbdbsearch)
    return logged, rss


def test_item_error_is_logged_and_the_batch_goes_on(rss_search):
    logged, rss = rss_search
    search.searchforissue(rsschecker='yes')
    assert mylar.SEARCHLOCK is False
    # the original error, not an UnboundLocalError from the handler
    assert len(logged['exceptions']) == 1
    assert 'TypeError' in logged['exceptions'][0]
    assert 'UnboundLocalError' not in logged['exceptions'][0]
    assert logged['except_lines'][0]['issueid'] == 'I1'
    assert logged['except_lines'][0]['smode'] == 'want'
    # the next item of the batch went to the RSS check
    assert [x[8] for x in rss['lists'][0]] == ['I2']


def test_error_after_the_items_releases_the_search_lock(rss_search, monkeypatch):
    def broken(*args, **kwargs):
        raise RuntimeError('rss database broken')
    monkeypatch.setattr(mylar.rsscheck, 'nzbdbsearch', broken)
    with pytest.raises(RuntimeError):
        search.searchforissue(rsschecker='yes')
    assert mylar.SEARCHLOCK is False
