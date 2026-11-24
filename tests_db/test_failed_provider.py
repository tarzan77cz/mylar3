"""Provider of the failed row Failed Download Handling writes for a DDL download (review R44).

Every other DDL write to ``failed`` (nzblog, Q5, pack revert, Comics mark_failed) uses the
provider name of ``ddl_info.site``, 'DDL(GetComics)'. No network.
"""
import pytest

import mylar
import mylar.Failed  # noqa: F401  (process.py reaches it as mylar.Failed)
import mylar.PostProcessor  # noqa: F401
from mylar import process


@pytest.fixture
def snatched(lib):
    mylar.CONFIG.FAILED_DOWNLOAD_HANDLING = True
    mylar.CONFIG.FAILED_AUTO = False
    lib.add_series('C1', 'Batman', [], year='2025')
    lib.add_issue('C1', 5, status='Snatched', issueid='5005')
    lib.execute("INSERT INTO nzblog (IssueID, NZBName, PROVIDER, ID, OneOff)"
                " VALUES ('5005', 'Batman.005.2025', 'DDL(GetComics)', '77', 'False')")
    return lib


def failed_rows(lib):
    return lib.rows('SELECT ID, Provider, IssueID, Status FROM failed')


def test_forced_failed_ddl_download_is_recorded_under_the_ddl_info_site(snatched, tmp_path):
    # forceProcess with ddl=1 and failed=1: download_info {'provider': 'DDL', 'id': <id>}
    process.Process('Batman.005.2025', str(tmp_path), failed='1', comicid='C1', apicall=True, ddl=True,
                    download_info={'provider': 'DDL', 'id': '77'}).post_process()
    assert failed_rows(snatched) == [{'ID': '77', 'Provider': 'DDL(GetComics)', 'IssueID': '5005',
                                      'Status': 'Failed'}]


def test_failed_nzb_download_keeps_its_provider(snatched, tmp_path):
    # control: other providers are written as they come
    process.Process('Batman.005.2025', str(tmp_path), failed='1', comicid='C1',
                    download_info={'provider': 'experimental', 'id': 'abc'}).post_process()
    assert failed_rows(snatched) == [{'ID': 'abc', 'Provider': 'experimental', 'IssueID': '5005',
                                      'Status': 'Failed'}]


@pytest.mark.parametrize('issueid', ['5005', None])
def test_ddl_post_processing_result_fail_is_not_read(snatched, tmp_path, monkeypatch, issueid):
    # control: ddl_downloader queues every DDL item with apicall=True, so post_process starts
    # the PP thread without reading its result and a 'fail' never reaches Failed Download Handling
    calls = []

    class FailingPP(object):
        def __init__(self, *a, **k):
            self.queue = k.get('queue')

        def Process(self):
            self.queue.put([{'mode': 'fail', 'annchk': 'no'}])

    class RecordingFailed(object):
        def __init__(self, *a, **k):
            calls.append(k)

    monkeypatch.setattr(mylar.PostProcessor, 'PostProcessor', FailingPP)
    monkeypatch.setattr(mylar.Failed, 'FailedProcessor', RecordingFailed)
    process.Process('Batman 005 (2025).cbz', str(tmp_path), failed=False, issueid=issueid, comicid='C1',
                    apicall=True, ddl=True, download_info={'provider': 'DDL', 'id': '77'}).post_process()
    assert calls == []
    assert failed_rows(snatched) == []
