"""Manual download from the search picker and retry from history for DDL (review R24)."""
import json

import pytest

import mylar
from mylar import search, updater, webserve

MANUALRESULTS = ('CREATE TABLE manualresults (provider TEXT, id TEXT, kind TEXT, comicname TEXT, volume TEXT,'
                 ' oneoff TEXT, fullprov TEXT, issuenumber TEXT, modcomicname TEXT, name TEXT, link TEXT, size TEXT,'
                 ' pack_numbers TEXT, pack_issuelist TEXT, comicyear TEXT, issuedate TEXT, tmpprov TEXT, pack TEXT,'
                 ' issueid TEXT, comicid TEXT, sarc TEXT, issuearcid TEXT)')
SNATCHED = ('CREATE TABLE snatched (IssueID TEXT, ComicName TEXT, Issue_Number TEXT, Size INTEGER, DateAdded TEXT,'
            ' Status TEXT, FolderName TEXT, ComicID TEXT, Provider TEXT, Hash TEXT, crc TEXT)')
POST = 'https://getcomics.info/?p=402258'
MAINLINK = 'https://getcomics.org/dc/batman-5-2025/'


REAL_GC = search.getcomics.GC


class FakeGC(object):
    """getcomics.GC without network: the page load and queueing are recorded."""
    calls = []
    result = {'success': True}

    def __init__(self, *args, **kwargs):
        self.kwargs = kwargs

    def check_for_pack(self, title, issue_in_pack=None):
        return REAL_GC(**self.kwargs).check_for_pack(title, issue_in_pack)

    def loadsite(self, nzbid, link):
        FakeGC.calls.append(('loadsite', nzbid, link))

    def parse_downloadresults(self, nzbid, link, comicinfo, pack_info, *args, **kwargs):
        FakeGC.calls.append(('parse_downloadresults', nzbid, link, comicinfo, pack_info))
        return dict(FakeGC.result)


@pytest.fixture
def ddl(lib, monkeypatch):
    lib.execute(MANUALRESULTS)
    lib.execute(SNATCHED)
    lib.add_series('C1', 'Batman', range(1, 11), year='2025')
    lib.execute("UPDATE issues SET IssueDate='2025-01-01'")
    mylar.CONFIG.ENABLE_DDL = True
    FakeGC.calls = []
    FakeGC.result = {'success': True}
    monkeypatch.setattr(search.getcomics, 'GC', FakeGC)
    found = []
    monkeypatch.setattr(updater, 'foundsearch', lambda *a, **k: found.append((a, k)))
    monkeypatch.setattr(updater, 'nzblog', lambda *a, **k: None)
    monkeypatch.setattr(search, 'notify_snatch', lambda *a, **k: None)
    return found


def add_result(lib, pack='0', pack_numbers=None, name='Batman 005 (2025)'):
    lib.execute("INSERT INTO manualresults (provider, id, kind, comicname, oneoff, fullprov, issuenumber,"
                " modcomicname, name, link, size, pack_numbers, comicyear, issuedate, tmpprov, pack, issueid,"
                " comicid) VALUES ('DDL(GetComics)', '402258', 'torrent', 'Batman', '0', 'DDL(GetComics)', '5',"
                " 'Batman', ?, ?, '40 MB', ?, '2025', '2025-01-01', 'DDL(GetComics)', ?, 'I5', 'C1')",
                (name, POST, pack_numbers, pack))


def pick(name='Batman 005 (2025)'):
    return json.loads(webserve.WebInterface().download_specific_release('402258', 'DDL(GetComics)', name))


def queued():
    return [c for c in FakeGC.calls if c[0] == 'parse_downloadresults']


def test_download_specific_release_ddl_queues(lib, ddl):
    add_result(lib)
    result = pick()
    assert result['status'] == 'success'
    (call,) = queued()
    _, nzbid, link, comicinfo, pack_info = call
    assert (nzbid, link) == ('402258', POST)
    assert comicinfo[0]['nzbid'] == '402258'
    assert comicinfo[0]['IssueID'] == 'I5' and comicinfo[0]['ComicID'] == 'C1'
    assert pack_info == {'pack': False, 'pack_numbers': None, 'pack_issuelist': None}
    assert [a for a, k in ddl] == [('C1', 'I5')]


def test_download_specific_release_ddl_pack(lib, ddl):
    add_result(lib, pack='1', pack_numbers='1-10', name='Batman #1-10 (2025)')
    assert pick('Batman #1-10 (2025)')['status'] == 'success'
    (call,) = queued()
    pack_info = call[4]
    assert pack_info['pack'] is True and pack_info['pack_numbers'] == '1-10'
    assert pack_info['pack_issuelist']['valid'] is True
    assert sorted(x['issueid'] for x in pack_info['pack_issuelist']['issues']) == sorted('I%s' % n for n in range(1, 11))


def test_download_specific_release_pack_range_from_the_title(lib, ddl, monkeypatch):
    add_result(lib, pack='1', pack_numbers=None, name='Batman #1 - 10 (2025)')
    mylar.CONFIG.SECURE_DIR = lib.path.rsplit('/', 1)[0]
    monkeypatch.setattr(mylar, 'GC_URL', 'https://getcomics.org', raising=False)
    assert pick('Batman #1 - 10 (2025)')['status'] == 'success'
    pack_info = queued()[0][4]
    assert pack_info['pack'] is True
    assert len(pack_info['pack_issuelist']['issues']) == 10


def test_download_specific_release_reports_a_failure(lib, ddl):
    add_result(lib)
    FakeGC.result = {'success': False}
    result = pick()
    assert result['status'] == 'error'
    assert result['error']
    assert ddl == []  # not marked Snatched


def test_download_specific_release_unknown_result(lib, ddl):
    result = pick('nothing like it')
    assert result['status'] == 'error'
    assert queued() == []


@pytest.fixture
def snatched_ddl(lib, ddl):
    lib.execute("INSERT INTO snatched (IssueID, ComicName, Issue_Number, DateAdded, Status, ComicID, Provider)"
                " VALUES ('I5', 'Batman', '5', '2025-01-08', 'Snatched', 'C1', 'DDL(GetComics)')")
    lib.execute("INSERT INTO nzblog (IssueID, NZBName, PROVIDER, ID) VALUES ('I5', 'Batman #5 (2025)',"
                " 'DDL(GetComics)', '402258')")
    lib.execute("INSERT INTO ddl_info (ID, status, issueid, comicid, mainlink, site, pack)"
                " VALUES ('402258', 'Failed', 'I5', 'C1', ?, 'DDL(GetComics)', 0)", (MAINLINK,))
    return ddl


def retry():
    return json.loads(webserve.WebInterface().retryissue('I5', 'C1', ComicName='Batman', IssueNumber='5'))


def test_retry_ddl_from_history(lib, snatched_ddl):
    result = retry()
    assert result['status'] == 'success'
    (call,) = queued()
    _, nzbid, link, comicinfo, pack_info = call
    assert (nzbid, link) == ('402258', MAINLINK)
    assert comicinfo[0]['nzbid'] == '402258'
    assert pack_info['pack'] is False


def test_retry_ddl_failure_is_reported_not_raised(lib, snatched_ddl, monkeypatch):
    lib.execute("UPDATE ddl_info SET mainlink=''")  # e.g. a direct download without a post page

    class NoPage(FakeGC):
        def loadsite(self, nzbid, link):
            raise ValueError('Invalid or empty mainlink URL')
    monkeypatch.setattr(search.getcomics, 'GC', NoPage)
    result = retry()
    assert result['status'] == 'failure'
