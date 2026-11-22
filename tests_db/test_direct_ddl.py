"""Direct DDL of an issue range from the series page and its requeue (review R39)."""
import json
import queue

import pytest

import mylar
from mylar import updater, webserve

URL = 'https://cdn.example/Batman%201-5.zip'  # not a GetComics button: queued as GC-Main, no network


@pytest.fixture
def direct(lib, monkeypatch):
    lib.add_series('C1', 'Batman', range(1, 6), year='2025')
    for n in (1, 2, 3):
        lib.add_annual('C1', n)
    monkeypatch.setattr(mylar, 'DDL_QUEUE', queue.Queue(), raising=False)
    snatched = []

    def foundsearch(ComicID, IssueID, mode=None, provider=None, **kwargs):
        snatched.append(IssueID)
        lib.set_status([IssueID], 'Snatched')
    monkeypatch.setattr(updater, 'foundsearch', foundsearch)
    logged = []
    monkeypatch.setattr(updater, 'nzblog', lambda IssueID, *a, **k: logged.append(IssueID))
    return {'snatched': snatched, 'nzblog': logged}


def queue_range(issue_range='1-5'):
    return json.loads(webserve.WebInterface().queue_direct_ddl(ComicID='C1', issue_range=issue_range, url=URL))


def test_direct_ddl_range_keeps_archived_issues(lib, direct):
    lib.set_status(['I3'], 'Archived')
    assert queue_range()['status'] == 'success'
    assert lib.status('I3') == 'Archived'
    assert 'I3' not in direct['snatched'] and 'I3' not in direct['nzblog']
    assert sorted(direct['snatched']) == ['I1', 'I2', 'I4', 'I5']


def test_direct_ddl_range_marks_skipped_issues_as_before(lib, direct):
    # the user chose the range by hand: Skipped and Ignored issues are queued as before
    lib.set_status(['I2'], 'Skipped')
    lib.set_status(['I4'], 'Ignored')
    assert queue_range()['status'] == 'success'
    assert lib.statuses(['I2', 'I4']) == {'Snatched'}


def test_two_direct_ddl_requests_in_one_second_get_two_ids(lib, direct, monkeypatch):
    monkeypatch.setattr(webserve.time, 'time', lambda: 1770040500.25)
    assert queue_range('1-2')['status'] == 'success'
    lib.set_status(['I1', 'I2'], 'Wanted')
    assert queue_range('1-2')['status'] == 'success'
    ids = [r['ID'] for r in lib.rows('SELECT ID FROM ddl_info')]
    assert len(ids) == 2 and len(set(ids)) == 2
    assert all(x.startswith('manual-') and x[len('manual-'):].isdigit() for x in ids)
    assert sorted(x['id'] for x in list(mylar.DDL_QUEUE.queue)) == sorted(ids)


@pytest.mark.parametrize('issue_range', ['Annual 1-3', '1-5 + Annual 1-3', '#1 - 5'])
def test_requeue_of_a_direct_ddl_range_keeps_its_context(lib, direct, issue_range):
    lib.execute("INSERT INTO ddl_info (ID, series, year, issues, issueid, comicid, link, mainlink, site, pack,"
                " link_type, status, size) VALUES ('manual-1770040500', ?, '2025', ?, 'A1', 'C1', ?, '',"
                " 'DDL(GetComics)', 1, 'GC-Main', 'Failed', '')",
                ('Batman (2025) %s' % issue_range, issue_range, URL))
    result = json.loads(webserve.WebInterface().ddl_requeue('requeue', id='manual-1770040500'))
    assert result['status'] is True
    (item,) = list(mylar.DDL_QUEUE.queue)
    assert item['comicinfo'] is not None
    assert item['packinfo']['pack_issuelist']['valid'] is True
    assert item['packinfo']['pack_numbers'] == issue_range
