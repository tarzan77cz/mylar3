"""Extra items of a GetComics "TPBs" list do not decide the issue's status (review R42)."""
import pytest

import mylar
from mylar import helpers

from conftest import run_ddl_downloader
from test_pack_sections import FakeGC
from test_single_exhausted import single_item


@pytest.fixture
def tpb(lib, monkeypatch):
    FakeGC.download = {'success': False, 'link_type': 'GC-Main'}
    FakeGC.redo = {'success': False, 'links_exhausted': ['GC-Main']}
    FakeGC.calls = []
    monkeypatch.setattr(helpers.getcomics, 'GC', FakeGC)
    monkeypatch.setattr(helpers.time, 'sleep', lambda *a: None)
    lib.add_series('C1', 'Batman', [1], year='2025')
    lib.set_status(['I1'], 'Snatched')
    lib.execute("INSERT INTO nzblog (IssueID, NZBName, PROVIDER, ID) VALUES ('I1', 'Batman Vol. 1 TPB',"
                " 'DDL(GetComics)', '77')")
    return FakeGC


def tpb_item(item_id, extra):
    item = single_item('I1', '1', post_id='77')
    item['comicinfo'][0]['booktype'] = 'TPB'
    item.update({'id': item_id, 'pack_id': '77'})
    if extra:
        item['tpb_extra'] = True
        for key in ('section_issues', 'section_annual'):
            item.pop(key)
    return item


def row(lib, item_id, pack=0):
    lib.execute("INSERT INTO ddl_info (ID, status, issueid, comicid, pack) VALUES (?, 'Queued', 'I1', 'C1', ?)",
                (item_id, pack))


@pytest.mark.parametrize('download', [
    {'success': False, 'link_type': 'GC-Main'},                                 # REDO branch
    {'success': False, 'link_type': 'GC-Main', 'links_exhausted': ['GC-Main']},  # links_exhausted branch
])
def test_failed_tpb_extra_leaves_the_issue_snatched(lib, tpb, download):
    tpb.download = download
    row(lib, '77-1')
    run_ddl_downloader([tpb_item('77-1', extra=True)])
    assert lib.rows("SELECT status FROM ddl_info WHERE ID='77-1'") == [{'status': 'Failed'}]
    assert lib.status('I1') == 'Snatched'  # the main link '77-2' still downloads it
    assert lib.rows('SELECT * FROM failed') == []


def test_failed_main_link_of_a_tpb_page_still_goes_the_q5_way(lib, tpb):
    row(lib, '77-2')
    run_ddl_downloader([tpb_item('77-2', extra=False)])
    assert lib.status('I1') == 'Wanted'
    assert [r['ID'] for r in lib.rows('SELECT ID FROM failed')] == ['77']


def test_restored_tpb_list_item_is_only_failed(lib, tpb):
    # restored from ddl_info: no context, '<post>-N' with pack=0 is not taken as the single issue
    row(lib, '77-1')
    item = {'link': 'https://getcomics.org/dls/x', 'mainlink': 'https://getcomics.org/x/', 'series': 'X',
            'year': '2025', 'size': '40 MB', 'comicid': 'C1', 'issueid': 'I1', 'oneoff': False, 'id': '77-1',
            'link_type': 'GC-Main', 'filename': None, 'tmp_filename': None, 'comicinfo': None,
            'packinfo': None, 'pack': 0, 'site': 'DDL(GetComics)', 'remote_filesize': 0, 'resume': None}
    run_ddl_downloader([item])
    assert lib.rows("SELECT status FROM ddl_info WHERE ID='77-1'") == [{'status': 'Failed'}]
    assert lib.status('I1') == 'Snatched'
    assert lib.rows('SELECT * FROM failed') == []


def test_restored_single_issue_still_goes_the_q5_way(lib, tpb):
    row(lib, '77')
    item = {'link': 'https://getcomics.org/dls/x', 'mainlink': 'https://getcomics.org/x/', 'series': 'X',
            'year': '2025', 'size': '40 MB', 'comicid': 'C1', 'issueid': 'I1', 'oneoff': False, 'id': '77',
            'link_type': 'GC-Main', 'filename': None, 'tmp_filename': None, 'comicinfo': None,
            'packinfo': None, 'pack': 0, 'site': 'DDL(GetComics)', 'remote_filesize': 0, 'resume': None}
    run_ddl_downloader([item])
    assert lib.status('I1') == 'Wanted'
    assert [r['ID'] for r in lib.rows('SELECT ID FROM failed')] == ['77']


def test_finished_tpb_extra_touches_no_pack_issue(lib, tpb):
    mylar.CONFIG.POST_PROCESSING = True
    tpb.download = {'success': True, 'filename': 'Batman Vol. 2 (2025).cbz', 'path': '/downloads'}
    mylar.PACK_ISSUEIDS_DONT_QUEUE['I1'] = '77'
    row(lib, '77-1')
    run_ddl_downloader([tpb_item('77-1', extra=True)])
    assert mylar.PACK_ISSUEIDS_DONT_QUEUE == {'I1': '77'}  # the main link still downloads
    info = mylar.PP_QUEUE.get_nowait()['download_info']
    assert info['section_issueids'] == []  # PP self-heal reverts nothing for an extra
