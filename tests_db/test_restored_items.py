"""Incomplete downloads keep their context; items restored from ddl_info release their issues (R16, Q11)."""
import queue

import pytest

import mylar
from mylar import helpers

from conftest import run_ddl_downloader
from test_single_exhausted import single_item

MAINLINK = 'https://getcomics.org/other-comics/tomahawk-1-140/'


class ScriptedGC(object):
    """getcomics.GC: downloadit answers from a script, parse_downloadresults is recorded."""
    downloads = []
    download_calls = []
    redo = {'success': False, 'links_exhausted': ['GC-Main']}
    raise_on_redo = False
    redo_calls = []

    def __init__(self, *args, **kwargs):
        pass

    def downloadit(self, id, link, mainlink, resume=None, issueid=None, remote_filesize=0, link_type=None):
        ScriptedGC.download_calls.append({'id': id, 'resume': resume})
        result = ScriptedGC.downloads.pop(0) if ScriptedGC.downloads else {'success': False, 'link_type': 'GC-Main'}
        return dict(result)

    def parse_downloadresults(self, id, mainlink, comicinfo, packinfo, link_type_failure, **kwargs):
        ScriptedGC.redo_calls.append({'id': id, 'comicinfo': comicinfo, 'packinfo': packinfo,
                                      'failed': list(link_type_failure)})
        if ScriptedGC.raise_on_redo:
            raise Exception('page gone')
        return dict(ScriptedGC.redo)


class _Stop(BaseException):
    pass


@pytest.fixture
def gc(lib, tmp_path, monkeypatch):
    ddl = tmp_path / 'dl'
    ddl.mkdir()
    mylar.CONFIG.DDL_LOCATION = str(ddl)
    mylar.CONFIG.DDL_AUTORESUME = True
    ScriptedGC.downloads = []
    ScriptedGC.download_calls = []
    ScriptedGC.redo = {'success': False, 'links_exhausted': ['GC-Main']}
    ScriptedGC.raise_on_redo = False
    ScriptedGC.redo_calls = []
    monkeypatch.setattr(helpers.getcomics, 'GC', ScriptedGC)
    monkeypatch.setattr(helpers.time, 'sleep', lambda *a: None)
    return ddl


def run_once(items):
    """Run the loop on items + 'exit' and return what is left in the queue after the exit."""
    q = queue.Queue()
    for item in items:
        q.put(item)
    q.put('exit')
    helpers.ddl_downloader(q)
    left = []
    while not q.empty():
        left.append(q.get_nowait())
    return left


def restored_item(issueid, post_id, series='Batman #5', pack=None, link_type='GC-Main'):
    """What auto-load rebuilds from a ddl_info row: no comicinfo, packinfo, pack_id."""
    return {'link': 'https://getcomics.org/dls/x', 'mainlink': MAINLINK, 'series': series, 'year': '2025',
            'size': '40 MB', 'comicid': 'C1', 'issueid': issueid, 'oneoff': False, 'id': post_id,
            'link_type': link_type, 'filename': None, 'tmp_filename': None, 'comicinfo': None, 'packinfo': None,
            'pack': pack, 'site': 'DDL(GetComics)', 'remote_filesize': 0, 'resume': None}


# --- incomplete keeps the context -------------------------------------------------------------

def test_incomplete_item_goes_back_to_the_queue_with_its_context(lib, gc):
    lib.add_series('C1', 'Batman', [5], year='2025')
    lib.set_status(['I5'], 'Snatched')
    lib.execute("INSERT INTO ddl_info (ID, status, issueid, filename, link_type) VALUES ('77', 'Queued', 'I5',"
                " 'Batman 005 (2025).cbz', 'GC-Main')")
    (gc / 'Batman 005 (2025).cbz').write_bytes(b'x' * 1000)
    ScriptedGC.downloads = [{'success': False, 'incomplete': True, 'path': str(gc / 'Batman 005 (2025).cbz'),
                             'link_type': 'GC-Main'}]
    item = single_item('I5', '5', post_id='77')
    [retry] = run_once([item])
    assert retry['comicinfo'] == item['comicinfo'] and retry['packinfo'] == item['packinfo']
    assert retry['pack_id'] == '77' and retry['section_issues'] == [5]
    assert retry['resume'] == 1000
    assert retry['filename'] == 'Batman 005 (2025).cbz'
    assert lib.rows("SELECT status FROM ddl_info WHERE ID='77'") == [{'status': 'Queued'}]
    assert '77' in mylar.DDL_QUEUED  # like an auto-loaded item: it is in the queue

    # the next attempt fails with a 403: the next host is asked, then Q5
    ScriptedGC.downloads = [{'success': False, 'link_type': 'GC-Main'}]
    assert run_once([retry]) == []
    assert ScriptedGC.download_calls[-1] == {'id': '77', 'resume': 1000}
    assert len(ScriptedGC.redo_calls) == 1
    assert ScriptedGC.redo_calls[0]['comicinfo'] == item['comicinfo']
    assert lib.status('I5') == 'Wanted'
    assert [r['ID'] for r in lib.rows('SELECT ID FROM failed')] == ['77']


def test_discarded_partial_is_retried_from_the_start(lib, gc):
    lib.add_series('C1', 'Batman', [5], year='2025')
    lib.execute("INSERT INTO ddl_info (ID, status, issueid, filename, link_type) VALUES ('77', 'Queued', 'I5',"
                " 'Batman 005 (2025).cbz', 'GC-Main')")
    ScriptedGC.downloads = [{'success': False, 'incomplete': True, 'discard_partial': True, 'path': None,
                             'link_type': 'GC-Main'}]
    [retry] = run_once([single_item('I5', '5', post_id='77')])
    assert retry['resume'] is None
    assert retry['comicinfo'] is not None


def test_incomplete_retry_is_not_auto_loaded_a_second_time(lib, gc, monkeypatch):
    lib.add_series('C1', 'Batman', [5], year='2025')
    lib.set_status(['I5'], 'Snatched')
    lib.execute("INSERT INTO ddl_info (ID, status, issueid, comicid, link, link_type, site) VALUES ('77', 'Queued',"
                " 'I5', 'C1', 'https://getcomics.org/dls/one', 'GC-Main', 'DDL(GetComics)')")
    monkeypatch.setattr(mylar, 'DDL_STARTUP_LOADED', True, raising=False)
    ScriptedGC.downloads = [{'success': False, 'incomplete': True, 'path': None, 'link_type': 'GC-Main'},
                            {'success': True, 'filename': 'Batman 005 (2025).cbz', 'path': str(gc)}]

    def sleep(seconds):
        if len(ScriptedGC.download_calls) >= 2 and seconds == 5:
            raise _Stop()  # the queue is empty and auto-load found nothing more
    monkeypatch.setattr(helpers.time, 'sleep', sleep)
    q = queue.Queue()
    q.put(single_item('I5', '5', post_id='77'))
    with pytest.raises(_Stop):
        helpers.ddl_downloader(q)
    assert [c['id'] for c in ScriptedGC.download_calls] == ['77', '77']
    assert lib.rows("SELECT status FROM ddl_info WHERE ID='77'") == [{'status': 'Completed'}]


def test_incomplete_after_the_last_attempt_releases_the_issue(lib, gc, monkeypatch):
    lib.add_series('C1', 'Batman', [5], year='2025')
    lib.set_status(['I5'], 'Snatched')
    lib.execute("INSERT INTO ddl_info (ID, status, issueid) VALUES ('77', 'Queued', 'I5')")
    monkeypatch.setattr(helpers, 'DDL_MAX_INCOMPLETE_ATTEMPTS', 1)
    ScriptedGC.downloads = [{'success': False, 'incomplete': True, 'path': None, 'link_type': 'GC-Main'}]
    assert run_once([single_item('I5', '5', post_id='77')]) == []
    assert lib.rows("SELECT status FROM ddl_info WHERE ID='77'") == [{'status': 'Failed'}]
    assert lib.status('I5') == 'Wanted'
    assert [r['ID'] for r in lib.rows('SELECT ID FROM failed')] == ['77']


# --- items restored from ddl_info --------------------------------------------------------------

def test_restored_single_issue_failure_is_wanted_and_blacklisted(lib, gc):
    lib.add_series('C1', 'Batman', [4, 5], year='2025')
    lib.set_status(['I5'], 'Snatched')
    lib.execute("INSERT INTO ddl_info (ID, status, issueid) VALUES ('77', 'Queued', 'I5')")
    run_ddl_downloader([restored_item('I5', '77')])
    assert lib.rows("SELECT status FROM ddl_info WHERE ID='77'") == [{'status': 'Failed'}]
    assert lib.status('I5') == 'Wanted' and lib.status('I4') == 'Wanted'
    failed = lib.rows('SELECT ID, Status, IssueID, ComicID, Provider, Issue_Number, NZBName FROM failed')
    assert failed == [{'ID': '77', 'Status': 'Failed', 'IssueID': 'I5', 'ComicID': 'C1',
                       'Provider': 'DDL(GetComics)', 'Issue_Number': '5', 'NZBName': 'Batman #5'}]
    assert ScriptedGC.redo_calls == []  # no context: no other host to try (Q11)


def tomahawk(lib, last=140):
    lib.add_series('C1', 'Tomahawk', range(1, last + 1))
    ids = ['I%s' % n for n in range(1, last + 1)]
    lib.set_status(ids, 'Snatched')
    for x in ids:
        lib.execute('INSERT INTO nzblog (IssueID, NZBName, PROVIDER, ID) VALUES (?,?,?,?)',
                    (x, 'Tomahawk #1 - %s' % last, 'DDL(GetComics)', '1'))
    return ids


def test_restored_pack_failure_reverts_its_issues(lib, gc):
    ids = tomahawk(lib, 20)
    lib.execute("INSERT INTO ddl_info (ID, status, pack, issueid) VALUES ('1', 'Queued', 1, 'I5')")
    run_ddl_downloader([restored_item('I5', '1', series='Tomahawk #1 - 20', pack=1)])
    assert lib.rows("SELECT status FROM ddl_info WHERE ID='1'") == [{'status': 'Failed'}]
    assert lib.statuses(ids) == {'Wanted'}
    assert lib.rows('SELECT * FROM failed') == []


def test_restored_subpack_reverts_only_its_section(lib, gc):
    ids = tomahawk(lib)
    lib.execute("INSERT INTO ddl_info (ID, status, pack, issueid, series) VALUES ('1-2', 'Queued', 1, 'I5',"
                " 'Tomahawk #71 – 140')")
    run_ddl_downloader([restored_item('I5', '1-2', series='Tomahawk #71 – 140', pack=1)])
    assert lib.statuses(ids[70:]) == {'Wanted'}
    assert lib.statuses(ids[:70]) == {'Snatched'}
    assert lib.rows('SELECT * FROM failed') == []


def test_restored_subpack_without_numbers_is_left_alone(lib, gc):
    ids = tomahawk(lib)
    lib.execute("INSERT INTO ddl_info (ID, status, pack, issueid, series) VALUES ('1-2', 'Queued', 1, 'I5',"
                " 'Tomahawk Complete Collection')")
    run_ddl_downloader([restored_item('I5', '1-2', series='Tomahawk Complete Collection', pack=1)])
    assert lib.statuses(ids) == {'Snatched'}


def test_auto_load_marks_a_pack_from_ddl_info(lib, gc, monkeypatch):
    ids = tomahawk(lib, 20)
    lib.execute("INSERT INTO ddl_info (ID, status, pack, issueid, comicid, series, link, link_type, site,"
                " updated_date) VALUES ('1', 'Queued', 1, 'I5', 'C1', 'Tomahawk #1 - 20',"
                " 'https://getcomics.org/dls/x', 'GC-Main', 'DDL(GetComics)', '2026-11-22 08:00')")
    monkeypatch.setattr(mylar, 'DDL_STARTUP_LOADED', True, raising=False)

    def sleep(seconds):
        if ScriptedGC.download_calls and seconds == 5:
            raise _Stop()
    monkeypatch.setattr(helpers.time, 'sleep', sleep)
    with pytest.raises(_Stop):
        helpers.ddl_downloader(queue.Queue())
    assert [c['id'] for c in ScriptedGC.download_calls] == ['1']
    assert lib.statuses(ids) == {'Wanted'}


# --- items with context: invalid mainlink, exception from parse_downloadresults ----------------

def pack_item():
    packinfo = {'pack': True, 'pack_numbers': '1 - 20',
                'pack_issuelist': helpers.issue_find_ids('Tomahawk', 'C1', '1 - 20', '5', '1')}
    comicinfo = [{'pack': True, 'IssueID': 'I5', 'ComicID': 'C1', 'IssueNumber': '5', 'booktype': 'Print',
                  'oneoff': False}]
    return {'link': 'https://getcomics.org/dls/x', 'mainlink': MAINLINK, 'series': 'Tomahawk #1 - 20',
            'year': '1950', 'size': '1 GB', 'comicid': 'C1', 'issueid': 'I5', 'oneoff': False, 'id': '1',
            'link_type': 'GC-Main', 'filename': None, 'comicinfo': comicinfo, 'packinfo': packinfo,
            'site': 'DDL(GetComics)', 'remote_filesize': 0, 'resume': None, 'section': None,
            'pack_id': '1', 'section_issues': list(range(1, 21)), 'section_annual': False}


def test_pack_with_context_parse_exception_reverts_its_section(lib, gc):
    ids = tomahawk(lib, 20)
    item = pack_item()  # issue_find_ids maps the pack issues in PACK_ISSUEIDS_DONT_QUEUE
    assert sorted(mylar.PACK_ISSUEIDS_DONT_QUEUE) == sorted(ids)
    ScriptedGC.raise_on_redo = True
    lib.execute("INSERT INTO ddl_info (ID, status) VALUES ('1', 'Queued')")
    run_ddl_downloader([item])
    assert lib.rows("SELECT status FROM ddl_info WHERE ID='1'") == [{'status': 'Failed'}]
    assert lib.statuses(ids) == {'Wanted'}
    assert mylar.PACK_ISSUEIDS_DONT_QUEUE == {}


@pytest.mark.parametrize('case', ['parse_exception', 'invalid_mainlink'])
def test_single_issue_with_context_is_wanted_and_blacklisted(lib, gc, case):
    lib.add_series('C1', 'Batman', [5], year='2025')
    lib.set_status(['I5'], 'Snatched')
    lib.execute("INSERT INTO ddl_info (ID, status, issueid) VALUES ('77', 'Queued', 'I5')")
    item = single_item('I5', '5', post_id='77')
    if case == 'parse_exception':
        ScriptedGC.raise_on_redo = True
    else:
        item['mainlink'] = ''
    run_ddl_downloader([item])
    assert lib.rows("SELECT status FROM ddl_info WHERE ID='77'") == [{'status': 'Failed'}]
    assert lib.status('I5') == 'Wanted'
    assert [(r['ID'], r['Issue_Number']) for r in lib.rows('SELECT ID, Issue_Number FROM failed')] == [('77', '5')]
