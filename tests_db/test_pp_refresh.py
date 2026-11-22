"""Post-processing while the same series is refreshed (review R17). No ComicVine: importer is faked."""
import pytest

import mylar
from mylar import importer, updater

SNATCHED = ('CREATE TABLE snatched (IssueID TEXT, ComicName TEXT, Issue_Number TEXT, Size INTEGER, DateAdded TEXT,'
            ' Status TEXT, FolderName TEXT, ComicID TEXT, Provider TEXT, Hash TEXT, crc TEXT)')
WEEKLY = 'CREATE TABLE weekly (ComicID TEXT, IssueID TEXT, Status TEXT, COMIC TEXT, ISSUE TEXT)'
ISSUE_COLUMNS = ('IssueID', 'ComicName', 'Issue_Number', 'Status', 'ComicID', 'IssueDate', 'Int_IssueNumber',
                 'ReleaseDate', 'DigitalDate', 'Location', 'ComicSize')


@pytest.fixture
def series(lib):
    lib.execute(SNATCHED)
    lib.execute(WEEKLY)
    lib.add_series('C1', 'Batman', [], year='2025')
    lib.execute("UPDATE comics SET LastUpdated='2025-01-01 00:00:00', Status='Active'")
    return lib


def issue_row(issueid, number, status=None, location=None):
    return (issueid, 'Batman', str(number), status, 'C1', '2025-01-01', number * 1000, '2025-01-08',
            '0000-00-00', location, None)


def insert(lib, row):
    lib.execute('INSERT INTO issues (%s) VALUES (%s)' % (', '.join(ISSUE_COLUMNS), ', '.join('?' * len(row))), row)


def test_foundsearch_waits_for_the_refresh_to_put_the_issue_back(series, monkeypatch):
    sleeps = []

    def refresh_done(seconds):
        sleeps.append(seconds)
        if len(sleeps) == 2:  # the refresh reinserts the issue while PP waits
            insert(series, issue_row('I5', 5))
    monkeypatch.setattr(updater.time, 'sleep', refresh_done)
    result = updater.foundsearch('C1', 'I5', down='True', module='[TEST]')
    assert result is not False
    assert series.status('I5') == 'Downloaded'
    assert series.rows('SELECT IssueID, Status FROM snatched') == [{'IssueID': 'I5', 'Status': 'Downloaded'}]


def test_foundsearch_gives_up_with_an_error_when_the_issue_stays_gone(series, monkeypatch):
    sleeps = []
    monkeypatch.setattr(updater.time, 'sleep', lambda s: sleeps.append(s))
    errors = []
    monkeypatch.setattr(updater.logger, 'error', lambda msg, *a, **k: errors.append(msg))
    result = updater.foundsearch('C1', 'I5', down='True', module='[TEST]')
    assert result is False
    assert 0 < len(sleeps) <= 30
    assert any('I5' in e for e in errors)
    assert series.rows('SELECT * FROM issues') == []  # no partial row created


def test_foundsearch_with_the_issue_present_does_not_wait(series, monkeypatch):
    insert(series, issue_row('I5', 5, status='Snatched'))
    monkeypatch.setattr(updater.time, 'sleep', lambda s: pytest.fail('waited'))
    updater.foundsearch('C1', 'I5', down='True', module='[TEST]')
    assert series.status('I5') == 'Downloaded'


@pytest.fixture
def refresh(series, monkeypatch):
    """dbUpdate of C1 with a fake ComicVine import; ``during`` runs right after the reinsert."""
    cfg = mylar.CONFIG
    cfg.CV_ONLY = True
    cfg.CV_ONETIMER = 1
    cfg.ANNUALS_ON = False
    cfg.REFRESH_CACHE = 0
    monkeypatch.setattr(mylar, 'IMPORTLOCK', False, raising=False)
    monkeypatch.setattr(updater.helpers, 'havetotals', lambda refreshit=None: False)
    monkeypatch.setattr(updater, 'forceRescan', lambda *a, **k: None)
    state = {'during': None}

    def add(ComicID, mismatch, **kwargs):
        return {'status': 'complete', 'issuedata': [5, 6], 'anndata': None}

    def collection(issuedata, nostatus=None, serieslast_updated=None):
        for n in issuedata:
            insert(series, issue_row('I%s' % n, n))  # CV data, no status yet
        if state['during']:
            state['during']()
    monkeypatch.setattr(importer, 'addComictoDB', add)
    monkeypatch.setattr(importer, 'issue_collection', collection)
    return state


def test_refresh_does_not_overwrite_a_download_filed_meanwhile(series, refresh):
    insert(series, issue_row('I5', 5, status='Snatched'))
    insert(series, issue_row('I6', 6, status='Downloaded', location='Batman 006 (2025).cbz'))

    def pp_files_issue_5():
        series.execute("UPDATE issues SET Status='Downloaded', Location='Batman 005 (2025).cbz' WHERE IssueID='I5'")
    refresh['during'] = pp_files_issue_5
    updater.dbUpdate(['C1'])
    rows = series.rows('SELECT IssueID, Status, Location FROM issues ORDER BY IssueID')
    assert rows == [{'IssueID': 'I5', 'Status': 'Downloaded', 'Location': 'Batman 005 (2025).cbz'},
                    {'IssueID': 'I6', 'Status': 'Downloaded', 'Location': 'Batman 006 (2025).cbz'}]


def test_refresh_restores_statuses_as_before(series, refresh):
    insert(series, issue_row('I5', 5, status='Snatched'))
    insert(series, issue_row('I6', 6, status='Downloaded', location='Batman 006 (2025).cbz'))
    updater.dbUpdate(['C1'])
    rows = series.rows('SELECT IssueID, Status, Location FROM issues ORDER BY IssueID')
    assert rows == [{'IssueID': 'I5', 'Status': 'Snatched', 'Location': None},
                    {'IssueID': 'I6', 'Status': 'Downloaded', 'Location': 'Batman 006 (2025).cbz'}]
