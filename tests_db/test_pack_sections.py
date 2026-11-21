"""Sub-packs '<id>-N' of one GetComics post against the pack's base id (review R2)."""
import pytest

import mylar
from mylar import helpers, PostProcessor

from conftest import run_ddl_downloader

MAINLINK = 'https://getcomics.org/other-comics/tomahawk-1-140/'


class FakeGC(object):
    """getcomics.GC with a scripted download result and no usable alternate link."""
    download = {'success': False, 'link_type': 'GC-Main'}
    redo = {'success': False, 'links_exhausted': ['GC-Main']}
    calls = []

    def __init__(self, *args, **kwargs):
        pass

    def downloadit(self, *args, **kwargs):
        return dict(FakeGC.download)

    def parse_downloadresults(self, *args, **kwargs):
        FakeGC.calls.append((args, kwargs))
        return dict(FakeGC.redo)


@pytest.fixture
def tomahawk(lib, monkeypatch):
    """Tomahawk #1-140 snatched as one pack (post id '1'), queued as sub-packs 1-1 and 1-2."""
    lib.add_series('C1', 'Tomahawk', range(1, 141))
    packinfo = {'pack': True, 'pack_numbers': '1 - 140',
                'pack_issuelist': helpers.issue_find_ids('Tomahawk', 'C1', '1 - 140', '5', '1')}
    issueids = [x['issueid'] for x in packinfo['pack_issuelist']['issues']]
    assert len(issueids) == 140
    lib.set_status(issueids, 'Snatched')  # what search.py does after the snatch
    for x in issueids:
        lib.execute('INSERT INTO nzblog (IssueID, NZBName, PROVIDER, ID) VALUES (?,?,?,?)',
                    (x, 'Tomahawk #1 - 140', 'DDL(GetComics)', '1'))
    FakeGC.download = {'success': False, 'link_type': 'GC-Main'}
    FakeGC.redo = {'success': False, 'links_exhausted': ['GC-Main']}
    FakeGC.calls = []
    monkeypatch.setattr(helpers.getcomics, 'GC', FakeGC)
    monkeypatch.setattr(helpers.time, 'sleep', lambda *a: None)
    return packinfo


def subpack_item(packinfo, n, numbers):
    comicinfo = [{'pack': True, 'IssueID': 'I5', 'ComicID': 'C1', 'IssueNumber': '5', 'booktype': 'Print',
                  'oneoff': False}]
    return {
        'link': 'https://getcomics.org/dls/sub%s' % n, 'mainlink': MAINLINK,
        'series': 'Tomahawk #%s - %s' % (numbers[0], numbers[-1]), 'year': '1950-1972', 'size': '1.3 GB',
        'comicid': 'C1', 'issueid': 'I5', 'oneoff': False, 'id': '1-%s' % n, 'link_type': 'GC-Main',
        'filename': None, 'comicinfo': comicinfo, 'packinfo': packinfo, 'site': 'DDL(GetComics)',
        'remote_filesize': 0, 'resume': None, 'section': n - 1,
        'pack_id': '1', 'section_issues': list(numbers),
    }


def ids(numbers):
    return ['I%s' % n for n in numbers]


@pytest.mark.parametrize('download', [
    {'success': False, 'link_type': 'GC-Main'},                                 # REDO branch
    {'success': False, 'link_type': 'GC-Main', 'links_exhausted': ['GC-Main']},  # links_exhausted branch
])
def test_failed_subpack_reverts_only_its_issues(lib, tomahawk, download):
    FakeGC.download = download
    lib.execute("INSERT INTO ddl_info (ID, status) VALUES ('1-2', 'Queued')")
    run_ddl_downloader([subpack_item(tomahawk, 2, range(71, 141))])
    assert lib.statuses(ids(range(71, 141))) == {'Wanted'}
    assert lib.statuses(ids(range(1, 71))) == {'Snatched'}
    assert lib.rows("SELECT status FROM ddl_info WHERE ID='1-2'") == [{'status': 'Failed'}]
    # the other sub-pack still downloads: its issues stay in the dont-queue map
    assert sorted(mylar.PACK_ISSUEIDS_DONT_QUEUE) == sorted(ids(range(1, 71)))


def test_finished_subpack_clears_only_its_issues(lib, tomahawk):
    mylar.CONFIG.POST_PROCESSING = True
    FakeGC.download = {'success': True, 'filename': None, 'path': '/downloads/Tomahawk 1-70'}
    run_ddl_downloader([subpack_item(tomahawk, 1, range(1, 71))])
    assert sorted(mylar.PACK_ISSUEIDS_DONT_QUEUE) == sorted(ids(range(71, 141)))
    pp = mylar.PP_QUEUE.get_nowait()
    info = pp['download_info']
    assert info['id'] == '1-1'
    assert info['pack_id'] == '1'
    assert sorted(info['section_issueids']) == sorted(ids(range(1, 71)))


def test_search_queue_sees_a_queued_subpack(lib, tomahawk):
    mylar.DDL_QUEUED = ['1-2']
    assert helpers.pack_queued_for_download('I100') is True
    assert helpers.pack_queued_for_download('I5') is True  # same post, other sub-pack
    mylar.DDL_QUEUED = ['12-1', '11']
    assert helpers.pack_queued_for_download('I5') is False
    mylar.DDL_QUEUED = ['1']
    assert helpers.pack_queued_for_download('I5') is True
    assert helpers.pack_queued_for_download('I999') is False


def _pp(download_info):
    pp = PostProcessor.PostProcessor.__new__(PostProcessor.PostProcessor)
    pp.ddl = True
    pp.comicid = 'C1'
    pp.issueid = None
    pp.module = '[TEST]'
    pp.nzb_name = 'Tomahawk #71 - 140'
    pp.download_info = download_info
    return pp


def test_pp_self_heal_of_a_subpack(lib, tomahawk):
    lib.set_status(ids(range(1, 71)), 'Downloaded')  # first sub-pack filed fine
    info = {'provider': 'DDL', 'id': '1-2', 'pack_id': '1', 'section_issueids': ids(range(71, 141))}
    reverted = _pp(info)._revert_unmatched_pack_snatches(reason='matched 0 files')
    assert sorted(reverted) == sorted(ids(range(71, 141)))
    assert lib.statuses(ids(range(71, 141))) == {'Wanted'}
    failed = lib.rows('SELECT ID, Issue_Number FROM failed')
    assert failed == [{'ID': '1', 'Issue_Number': 'pack'}]


def test_pp_self_heal_reverts_only_its_section(lib, tomahawk):
    info = {'provider': 'DDL', 'id': '1-2', 'pack_id': '1', 'section_issueids': ids(range(71, 141))}
    _pp(info)._revert_unmatched_pack_snatches(reason='matched 0 files')
    assert lib.statuses(ids(range(71, 141))) == {'Wanted'}
    assert lib.statuses(ids(range(1, 71))) == {'Snatched'}  # 1-1 may still be downloading


def test_single_section_pack_reverts_whole_pack(lib, tomahawk):
    item = subpack_item(tomahawk, 1, range(1, 141))
    item.update({'id': '1', 'pack_id': '1', 'section': None})
    lib.execute("INSERT INTO ddl_info (ID, status) VALUES ('1', 'Queued')")
    run_ddl_downloader([item])
    assert lib.statuses(ids(range(1, 141))) == {'Wanted'}


def test_section_issueids_annuals(lib):
    lib.add_series('C2', 'Batman', range(1, 11))
    for n in (1, 2):
        lib.add_annual('C2', n)
    packinfo = {'pack': True, 'pack_numbers': '1-10 + Annual 1-2',
                'pack_issuelist': helpers.issue_find_ids('Batman', 'C2', '1-10 + Annual 1-2', '5', '7')}
    assert sorted(helpers.pack_section_issueids(packinfo, [1, 2, 3])) == ['I1', 'I2', 'I3']
    assert sorted(helpers.pack_section_issueids(packinfo, [1, 2], section_annual=True)) == ['A1', 'A2']
    assert helpers.pack_section_issueids(packinfo, []) is None
