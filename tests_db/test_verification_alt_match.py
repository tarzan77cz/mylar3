"""The release that is downloaded gives the link, the ID, the pack data and the name together (R28).

The fork returns a single-issue alt_match as a match with downloadit=False (upstream dropped it).
verification() sends the downloadit match to searcher(); searcher() reads the post ID, the pack
data and the name from comicinfo[0]. With the alt_match ahead of the real match in
verified_matches, the link was the real post and everything else came from the alt_match.
"""
import pytest

import mylar
from mylar import search, search_filer, updater


class FakeGC(object):
    """getcomics.GC: records what searcher() hands over instead of loading GetComics."""
    calls = []

    def __init__(self, *a, **k):
        pass

    def loadsite(self, nzbid, link):
        FakeGC.calls.append(('loadsite', nzbid, link))

    def parse_downloadresults(self, nzbid, link, comicinfo, pack_info):
        FakeGC.calls.append(('parse', nzbid, link, comicinfo[0]['nzbid'], comicinfo[0]['nzbtitle'],
                             dict(pack_info)))
        return {'success': True}


@pytest.fixture
def snatching(lib, monkeypatch):
    mylar.CONFIG.ENABLE_DDL = True
    mylar.CONFIG.FAILED_DOWNLOAD_HANDLING = True
    FakeGC.calls = []
    monkeypatch.setattr(search.getcomics, 'GC', FakeGC)
    monkeypatch.setattr(search, 'notify_snatch', lambda *a, **k: None)
    monkeypatch.setattr(updater, 'foundsearch', lambda *a, **k: None)
    monkeypatch.setattr(search_filer, '_compute_rejected_relevance', lambda *a, **k: 0.5)
    monkeypatch.setattr(search_filer, '_load_watch_context_for_issue', lambda IssueID: None)
    monkeypatch.setattr(mylar, 'REJECTED_MATCHES', {}, raising=False)
    lib.add_series('C1', 'Primary', [5], year='2020')
    return lib


def match(nzbid, title, downloadit, alt_match, pack=False, pack_issuelist=None, pack_numbers=None):
    link = 'https://getcomics.info/?p=%s' % nzbid
    return {
        'ComicName': 'Primary', 'ComicID': 'C1', 'IssueID': 'I5', 'IssueNumber': '5', 'IssueDate': '2020-05-01',
        'comyear': '2020', 'oneoff': False, 'SARC': None, 'IssueArcID': None,
        'nzbid': nzbid, 'nzbtitle': title, 'ComicTitle': title, 'modcomicname': 'Primary',
        'downloadit': downloadit, 'alt_match': alt_match,
        'pack': pack, 'pack_issuelist': pack_issuelist, 'pack_numbers': pack_numbers,
        'nzbprov': 'DDL(GetComics)', 'tmpprov': 'DDL(GetComics)', 'provider': 'DDL(GetComics)',
        'newznab': None, 'torznab': None, 'provider_stat': {'type': 'DDL(GetComics)'},
        'link': link, 'entry': {'id': nzbid, 'link': link, 'title': title, 'series': 'Primary', 'year': '2020'},
        'size': '30 MB', 'kind': 'ddl', 'pubdate': '', 'booktype': 'Print',
    }


def is_info():
    return {
        'nzbprov': 'DDL(GetComics)', 'RSS': 'no', 'ComicName': 'Primary', 'SARC': None, 'IssueArcID': None,
        'oneoff': False, 'ComicID': 'C1', 'IssueID': 'I5', 'smode': None, 'ComicYear': '2020',
        'IssueNumber': '5', 'foundc': {'status': False}, 'UseFuzzy': None,
    }


def nzblog(lib):
    return lib.rows('SELECT IssueID, ID, NZBName, PROVIDER FROM nzblog')


def test_alt_match_ahead_of_the_real_match_does_not_lend_its_id(snatching):
    vm = [match('100', 'Alt Name 005 (2020)', False, True), match('200', 'Primary 005 (2020)', True, False)]
    info = search.verification(vm, is_info())
    assert info['foundc']['status'] is True
    assert FakeGC.calls[0] == ('loadsite', '200', 'https://getcomics.info/?p=200')
    parse = FakeGC.calls[1]
    assert parse[1:5] == ('200', 'https://getcomics.info/?p=200', '200', 'Primary 005 (2020)')
    assert parse[5] == {'pack': False, 'pack_numbers': None, 'pack_issuelist': None}
    assert [(r['IssueID'], r['ID']) for r in nzblog(snatching)] == [('I5', '200')]
    # the alt_match is still offered under "Rejected matches"
    assert [m['nzbid'] for m in mylar.REJECTED_MATCHES['I5']] == ['100']


def test_alt_match_ahead_does_not_hide_a_blocked_release(snatching):
    """The failed-download check (Q5) looks at the release that would be downloaded."""
    snatching.execute("INSERT INTO failed (ID, Status, IssueID, Provider) VALUES ('200', 'Failed', 'I5', 'DDL(GetComics)')")
    vm = [match('100', 'Alt Name 005 (2020)', False, True), match('200', 'Primary 005 (2020)', True, False)]
    info = search.verification(vm, is_info())
    assert info['foundc']['status'] is False
    assert FakeGC.calls == []
    assert nzblog(snatching) == []


def test_alt_match_pack_ahead_does_not_lend_its_issue_list(snatching):
    pack_list = {'issues': [{'issueid': 'X1', 'annual': False}, {'issueid': 'X2', 'annual': False}]}
    vm = [match('100', 'Alt Name 001-012 (2020)', False, True, pack=True, pack_issuelist=pack_list,
                pack_numbers=['1', '12']),
          match('200', 'Primary 005 (2020)', True, False)]
    search.verification(vm, is_info())
    parse = FakeGC.calls[1]
    assert parse[1] == '200'
    assert parse[5] == {'pack': False, 'pack_numbers': None, 'pack_issuelist': None}
    assert [(r['IssueID'], r['ID']) for r in nzblog(snatching)] == [('I5', '200')]


# --- control (passes before the fix too) ---

def test_control_without_alt_match_nothing_changes(snatching):
    vm = [match('200', 'Primary 005 (2020)', True, False), match('300', 'Primary 005 (2020) v2', True, False)]
    info = search.verification(vm, is_info())
    assert info['foundc']['status'] is True
    assert FakeGC.calls[1][1:5] == ('200', 'https://getcomics.info/?p=200', '200', 'Primary 005 (2020)')
    assert [(r['IssueID'], r['ID']) for r in nzblog(snatching)] == [('I5', '200')]
    assert mylar.REJECTED_MATCHES == {}


def test_control_alt_match_behind_the_real_match(snatching):
    vm = [match('200', 'Primary 005 (2020)', True, False), match('100', 'Alt Name 005 (2020)', False, True)]
    search.verification(vm, is_info())
    assert FakeGC.calls[1][1:5] == ('200', 'https://getcomics.info/?p=200', '200', 'Primary 005 (2020)')
    assert [(r['IssueID'], r['ID']) for r in nzblog(snatching)] == [('I5', '200')]
