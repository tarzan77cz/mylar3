"""A refresh must not drop issues it failed to read from ComicVine (review R32). No network."""
import pytest

import mylar
from mylar import cv, importer, updater

from cvxml import issue, response
from test_pp_refresh import insert, issue_row, series  # noqa: F401  (fixture)


@pytest.fixture
def logs(lib, monkeypatch):
    mylar.CONFIG.CV_ONLY = True
    seen = {'warn': [], 'error': []}
    monkeypatch.setattr(cv.logger, 'warn', lambda msg, *a, **k: seen['warn'].append(msg))
    monkeypatch.setattr(cv.logger, 'error', lambda msg, *a, **k: seen['error'].append(msg))
    return seen


def test_issue_without_number_is_left_out_with_a_warning(logs):
    res, firstdate = cv.GetIssuesInfo('111', response([
        issue(10, None, '2020-01-01'),
        issue(11, '2', '2020-02-01'),
        issue(12, None, '2020-03-01'),
    ]))
    assert [(r['Issue_ID'], r['Issue_Number']) for r in res] == [('11', '2')]
    assert any('10' in w for w in logs['warn'])
    assert any('12' in w for w in logs['warn'])


def _crashing_digital_date(monkeypatch):
    class Boom(object):
        def checkthedate(self, *a, **k):
            raise ValueError('unexpected date text')
    monkeypatch.setattr(mylar.filechecker, 'FileChecker', Boom)
    return 'Collected in print and digital on Jan 1 2020'


def test_issue_that_cannot_be_read_makes_the_issue_data_incomplete(logs, monkeypatch):
    desc = _crashing_digital_date(monkeypatch)
    monkeypatch.setattr(cv, 'pulldetails', lambda *a, **k: response([
        issue(1, '1', '2020-01-01'), issue(2, '2', '2020-02-01', description=desc), issue(3, '3', '2020-03-01')]))
    assert cv.getComic('111', 'issue') is None
    assert any('2' in e for e in logs['error'])


def test_story_arc_still_skips_an_issue_that_cannot_be_read(logs, monkeypatch):
    # control: story arcs keep today's behaviour (skip the issue, return the rest)
    desc = _crashing_digital_date(monkeypatch)
    res, firstdate = cv.GetIssuesInfo('111', response([
        issue(1, '1', '2020-01-01'), issue(2, '2', '2020-02-01', description=desc)]), arcid='A1')
    assert [r['IssueID'] for r in res] == ['1']


@pytest.fixture
def refresh(series, monkeypatch):  # noqa: F811
    """dbUpdate of C1; ``new`` holds the issues the fake ComicVine import returns."""
    cfg = mylar.CONFIG
    cfg.CV_ONLY = True
    cfg.CV_ONETIMER = 1
    cfg.ANNUALS_ON = False
    cfg.REFRESH_CACHE = 0
    monkeypatch.setattr(mylar, 'IMPORTLOCK', False, raising=False)
    monkeypatch.setattr(updater.helpers, 'havetotals', lambda refreshit=None: False)
    monkeypatch.setattr(updater, 'forceRescan', lambda *a, **k: None)
    state = {'new': [], 'warn': [], 'collected': 0}
    monkeypatch.setattr(updater.logger, 'warn', lambda msg, *a, **k: state['warn'].append(msg))

    def add(ComicID, mismatch, **kwargs):
        series.execute("UPDATE comics SET Status='Loading'")  # as the real addComictoDB does
        return {'status': 'complete', 'issuedata': [{'IssueID': 'I%s' % n, 'n': n} for n in state['new']],
                'anndata': None}

    def collection(issuedata, nostatus=None, serieslast_updated=None):
        state['collected'] += 1
        for x in issuedata:
            insert(series, issue_row(x['IssueID'], x['n']))
    monkeypatch.setattr(importer, 'addComictoDB', add)
    monkeypatch.setattr(importer, 'issue_collection', collection)
    return state


def rows(lib):
    return lib.rows('SELECT IssueID, Status, Location FROM issues ORDER BY IssueID')


def test_refresh_stops_before_deleting_a_downloaded_issue_missing_from_comicvine(series, refresh):
    insert(series, issue_row('I5', 5, status='Downloaded', location='Batman 005 (2025).cbz'))
    insert(series, issue_row('I6', 6, status='Wanted'))
    series.execute("UPDATE comics SET Status='Paused'")
    refresh['new'] = [6, 7]
    before = rows(series)
    updater.dbUpdate(['C1'])
    assert rows(series) == before
    assert refresh['collected'] == 0
    assert any('I5' in w for w in refresh['warn'])
    assert mylar.GLOBAL_MESSAGES['status'] == 'failure'
    assert 'Failure refreshing' in mylar.GLOBAL_MESSAGES['message']
    assert series.rows('SELECT Status FROM comics') == [{'Status': 'Paused'}]


def test_refresh_stops_for_a_missing_snatched_or_archived_issue_too(series, refresh):
    insert(series, issue_row('I5', 5, status='Snatched'))
    insert(series, issue_row('I6', 6, status='Archived'))
    insert(series, issue_row('I7', 7, status='Skipped', location='Batman 007 (2025).cbz'))
    refresh['new'] = [8]
    before = rows(series)
    updater.dbUpdate(['C1'])
    assert rows(series) == before
    assert any('I5' in w and 'I6' in w and 'I7' in w for w in refresh['warn'])


def test_regular_refresh_with_all_issues_still_replaces_and_restores(series, refresh):
    # control: passes before and after the fix
    insert(series, issue_row('I5', 5, status='Downloaded', location='Batman 005 (2025).cbz'))
    insert(series, issue_row('I6', 6, status='Wanted'))
    refresh['new'] = [5, 6]
    updater.dbUpdate(['C1'])
    assert refresh['collected'] == 1
    assert rows(series) == [{'IssueID': 'I5', 'Status': 'Downloaded', 'Location': 'Batman 005 (2025).cbz'},
                            {'IssueID': 'I6', 'Status': 'Wanted', 'Location': None}]


def test_missing_wanted_issue_without_a_file_does_not_stop_the_refresh(series, refresh):
    # control: passes before and after the fix (the issue is dropped as before)
    insert(series, issue_row('I5', 5, status='Wanted'))
    insert(series, issue_row('I6', 6, status='Downloaded', location='Batman 006 (2025).cbz'))
    refresh['new'] = [6]
    updater.dbUpdate(['C1'])
    assert refresh['collected'] == 1
    assert rows(series) == [{'IssueID': 'I6', 'Status': 'Downloaded', 'Location': 'Batman 006 (2025).cbz'}]
