"""A single issue whose every host failed goes back to Wanted, the post is blacklisted (decision Q5)."""
import pytest

from mylar import helpers

from conftest import run_ddl_downloader
from test_pack_sections import FakeGC


@pytest.fixture
def fake_gc(monkeypatch):
    FakeGC.download = {'success': False, 'link_type': 'GC-Main'}
    FakeGC.redo = {'success': False, 'links_exhausted': ['GC-Main']}
    FakeGC.calls = []
    monkeypatch.setattr(helpers.getcomics, 'GC', FakeGC)
    monkeypatch.setattr(helpers.time, 'sleep', lambda *a: None)
    return FakeGC


def single_item(issueid, number, post_id='77'):
    comicinfo = [{'pack': False, 'IssueID': issueid, 'ComicID': 'C1', 'IssueNumber': number, 'booktype': 'Print',
                  'oneoff': False, 'nzbtitle': 'Batman #%s (2025)' % number}]
    return {
        'link': 'https://getcomics.org/dls/one', 'mainlink': 'https://getcomics.org/dc/batman-%s-2025/' % number,
        'series': 'Batman #%s' % number, 'year': '2025', 'size': '40 MB', 'comicid': 'C1', 'issueid': issueid,
        'oneoff': False, 'id': post_id, 'link_type': 'GC-Main', 'filename': None, 'comicinfo': comicinfo,
        'packinfo': {'pack': False, 'pack_numbers': None, 'pack_issuelist': None}, 'site': 'DDL(GetComics)',
        'remote_filesize': 0, 'resume': None, 'section': None, 'pack_id': post_id, 'section_issues': [5],
        'section_annual': False,
    }


@pytest.mark.parametrize('download', [
    {'success': False, 'link_type': 'GC-Main'},                                 # REDO branch
    {'success': False, 'link_type': 'GC-Main', 'links_exhausted': ['GC-Main']},  # links_exhausted branch
])
def test_exhausted_single_issue_is_wanted_and_blacklisted(lib, fake_gc, download):
    fake_gc.download = download
    lib.add_series('C1', 'Batman', [4, 5, 6], year='2025')
    lib.set_status(['I5'], 'Snatched')
    lib.execute("INSERT INTO ddl_info (ID, status, issueid) VALUES ('77', 'Queued', 'I5')")
    run_ddl_downloader([single_item('I5', '5')])
    assert lib.status('I5') == 'Wanted'
    assert lib.status('I4') == 'Wanted' and lib.status('I6') == 'Wanted'
    failed = lib.rows('SELECT ID, Status, IssueID, ComicID, Provider, Issue_Number, NZBName FROM failed')
    assert failed == [{'ID': '77', 'Status': 'Failed', 'IssueID': 'I5', 'ComicID': 'C1',
                       'Provider': 'DDL(GetComics)', 'Issue_Number': '5', 'NZBName': 'Batman #5 (2025)'}]
    assert lib.rows("SELECT status FROM ddl_info WHERE ID='77'") == [{'status': 'Failed'}]


def test_exhausted_single_annual_is_wanted(lib, fake_gc):
    lib.add_series('C1', 'Batman', [1], year='2025')
    lib.add_annual('C1', 2, status='Snatched')
    lib.execute("INSERT INTO ddl_info (ID, status, issueid) VALUES ('78', 'Queued', 'A2')")
    run_ddl_downloader([single_item('A2', '2', post_id='78')])
    assert lib.status('A2') == 'Wanted'
    assert [r['ID'] for r in lib.rows('SELECT ID FROM failed')] == ['78']


def test_downloaded_single_issue_is_left_alone(lib, fake_gc):
    lib.add_series('C1', 'Batman', [5], year='2025')
    lib.set_status(['I5'], 'Downloaded')
    lib.execute("INSERT INTO ddl_info (ID, status, issueid) VALUES ('77', 'Queued', 'I5')")
    run_ddl_downloader([single_item('I5', '5')])
    assert lib.rows("SELECT status FROM ddl_info WHERE ID='77'") == [{'status': 'Failed'}]
    assert lib.status('I5') == 'Downloaded'


def test_manual_item_keeps_the_pack_path(lib, fake_gc):
    lib.add_series('C1', 'Batman', [5], year='2025')
    lib.set_status(['I5'], 'Snatched')
    item = single_item('I5', '5', post_id='manual-abc')
    lib.execute("INSERT INTO ddl_info (ID, status, issueid) VALUES ('manual-abc', 'Queued', 'I5')")
    run_ddl_downloader([item])
    assert lib.rows('SELECT * FROM failed') == []
    assert lib.rows("SELECT status FROM ddl_info WHERE ID='manual-abc'") == [{'status': 'Failed'}]
