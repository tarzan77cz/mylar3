"""State of the DDL queue and of the manual post-processing (review R41, R38)."""
import json
import threading

import pytest

import mylar
from mylar import PostProcessor, getcomics, helpers, webserve

from conftest import run_ddl_downloader
from fakes import FakeResponse, install_router, make_zip
from test_single_exhausted import single_item

FILE_URL = 'https://cdn.example/Batman%20005%20(2025).cbz'


@pytest.fixture
def gc_main(lib, tmp_path, monkeypatch):
    """The real GC-Main downloader on a fake HTTP session (no FlareSolverr, no network)."""
    ddl = tmp_path / 'dl'
    ddl.mkdir()
    mylar.CONFIG.DDL_LOCATION = str(ddl)
    mylar.CONFIG.SECURE_DIR = str(tmp_path)
    mylar.CONFIG.POST_PROCESSING = True
    monkeypatch.setattr(mylar, 'GC_URL', 'https://getcomics.org', raising=False)
    monkeypatch.setattr(mylar, 'DDL_ABORT_REQUESTED', False, raising=False)
    monkeypatch.setattr(helpers.time, 'sleep', lambda *a: None)
    monkeypatch.setattr(getcomics.GC, 'cookie_receipt', lambda self, *a, **k: None)
    redo = []

    def parse_downloadresults(self, *args, **kwargs):
        redo.append(args)
        return {'success': False}
    monkeypatch.setattr(getcomics.GC, 'parse_downloadresults', parse_downloadresults)
    lib.add_series('C1', 'Batman', [5, 6], year='2025')
    lib.set_status(['I5', 'I6'], 'Snatched')
    return redo


def queued_row(lib, id_, issueid='I5'):
    lib.execute("INSERT INTO ddl_info (ID, status, issueid, comicid, site, link_type)"
                " VALUES (?, 'Queued', ?, 'C1', 'DDL(GetComics)', 'GC-Main')", (id_, issueid))


def gc_item(issueid='I5', number='5', post_id='77'):
    item = single_item(issueid, number, post_id=post_id)
    item['link'] = FILE_URL
    return item


def serve(monkeypatch, body, status=200, during=None):
    """Answer the file request; ``during(n)`` runs before chunk n of the body."""
    class Streamed(FakeResponse):
        def iter_content(self, chunk_size=1):
            for n, i in enumerate(range(0, len(self.body), chunk_size)):
                if during:
                    during(n)
                yield self.body[i:i + chunk_size]

    def route(url, headers):
        return Streamed(status, body, {'Content-Length': str(len(body))}, url=FILE_URL)
    return install_router(monkeypatch, route)


# --- R41: downloadit must not add the ID to DDL_QUEUED a second time -------------------

def test_gc_main_success_leaves_no_id_in_ddl_queued(lib, gc_main, monkeypatch):
    serve(monkeypatch, make_zip(5, 1000))
    queued_row(lib, '77')
    run_ddl_downloader([gc_item()])
    assert lib.rows("SELECT status FROM ddl_info WHERE ID='77'") == [{'status': 'Completed'}]
    assert mylar.DDL_QUEUED == []


def test_gc_main_failure_leaves_no_id_in_ddl_queued(lib, gc_main, monkeypatch):
    serve(monkeypatch, b'gone', status=404)
    queued_row(lib, '77')
    run_ddl_downloader([gc_item()])
    assert len(gc_main) == 1  # the next host was asked, none left
    assert lib.rows("SELECT status FROM ddl_info WHERE ID='77'") == [{'status': 'Failed'}]
    assert mylar.DDL_QUEUED == []


# --- R41: an item whose ddl_info row was deleted is not downloaded ----------------------

class RecordingGC(object):
    calls = []

    def __init__(self, *a, **k):
        pass

    def downloadit(self, *args, **kwargs):
        RecordingGC.calls.append(args)
        return {'success': False, 'link_type': 'GC-Main'}

    def parse_downloadresults(self, *args, **kwargs):
        return {'success': False}


@pytest.fixture
def recording_gc(lib, monkeypatch):
    RecordingGC.calls = []
    monkeypatch.setattr(helpers.getcomics, 'GC', RecordingGC)
    monkeypatch.setattr(helpers.time, 'sleep', lambda *a: None)
    lib.add_series('C1', 'Batman', [5, 6], year='2025')
    lib.set_status(['I5', 'I6'], 'Snatched')
    return RecordingGC


def test_item_without_its_row_is_skipped(lib, recording_gc):
    mylar.DDL_QUEUED.append('77')
    run_ddl_downloader([gc_item()])
    assert recording_gc.calls == []
    assert lib.rows('SELECT * FROM ddl_info') == []
    assert mylar.DDL_QUEUED == []
    assert lib.status('I5') == 'Snatched'  # nothing else changes


@pytest.mark.parametrize('action', ['clear_queue', 'remove'])
def test_cleared_or_removed_items_are_not_downloaded(lib, recording_gc, action):
    queued_row(lib, '77')
    queued_row(lib, '78', issueid='I6')
    items = [gc_item(), gc_item('I6', '6', post_id='78')]
    if action == 'clear_queue':
        result = webserve.WebInterface().ddl_requeue('clear_queue')
        removed = ['77', '78']
    else:
        result = webserve.WebInterface().ddl_requeue('remove', id='77')
        removed = ['77']
    assert json.loads(result)['status'] is True
    run_ddl_downloader(items)
    downloaded = [c[0] for c in recording_gc.calls]
    assert not set(removed) & set(downloaded)
    assert [r['ID'] for r in lib.rows('SELECT ID FROM ddl_info')] == sorted(set(['77', '78']) - set(removed))


def test_item_with_its_row_is_still_downloaded(lib, recording_gc):
    queued_row(lib, '77')
    run_ddl_downloader([gc_item()])
    assert [c[0] for c in recording_gc.calls] == ['77']


# --- R38: an abort applies only to the download it was meant for ------------------------

def test_stale_abort_flag_does_not_cancel_the_next_download(lib, gc_main, monkeypatch):
    serve(monkeypatch, make_zip(5, 1000))
    queued_row(lib, '77')
    mylar.DDL_ABORT_REQUESTED = True  # left over from an abort of a Pixeldrain download
    run_ddl_downloader([gc_item()])
    assert lib.rows("SELECT status FROM ddl_info WHERE ID='77'") == [{'status': 'Completed'}]


def test_abort_of_another_item_does_not_stop_this_download(lib, gc_main, monkeypatch):
    def abort_other(n):
        if n == 1:
            json.loads(webserve.WebInterface().ddl_requeue('abort', id='99'))
    serve(monkeypatch, make_zip(30, 100000), during=abort_other)  # three 1 MB chunks
    queued_row(lib, '77')
    lib.execute("INSERT INTO ddl_info (ID, status, issueid, comicid, site, link_type, series)"
                " VALUES ('99', 'Downloading', 'I6', 'C1', 'DDL(GetComics)', 'GC-Main', 'Batman #6')")
    run_ddl_downloader([gc_item()])
    assert lib.rows("SELECT status FROM ddl_info WHERE ID='77'") == [{'status': 'Completed'}]


def test_abort_of_the_running_download_stops_it(lib, gc_main, monkeypatch):
    def abort_this(n):
        if n == 1:
            json.loads(webserve.WebInterface().ddl_requeue('abort', id='77'))
    serve(monkeypatch, make_zip(30, 100000), during=abort_this)
    queued_row(lib, '77')
    run_ddl_downloader([gc_item()])
    assert lib.rows("SELECT status FROM ddl_info WHERE ID='77'") == [{'status': 'Failed'}]


def test_abort_of_a_queued_item_sets_no_flag(lib, monkeypatch):
    monkeypatch.setattr(mylar, 'DDL_ABORT_REQUESTED', False, raising=False)
    lib.add_series('C1', 'Batman', [5], year='2025')
    queued_row(lib, '77')
    webserve.WebInterface().ddl_requeue('abort', id='77')
    assert not mylar.DDL_ABORT_REQUESTED
    assert lib.rows("SELECT status FROM ddl_info WHERE ID='77'") == [{'status': 'Failed'}]


# --- R41: a manual post-processing that raises does not stay "running" ------------------

class SyncThread(object):
    def __init__(self, target=None, name=None, args=(), kwargs=None, **_):
        self.target, self.args, self.kwargs = target, args, kwargs or {}

    def start(self):
        self.target(*self.args, **self.kwargs)


def test_manual_pp_error_ends_running(lib, tmp_path, monkeypatch):
    folder = tmp_path / 'manual'
    folder.mkdir()
    mylar.CONFIG.MANUAL_PP_FOLDER = str(folder)
    mylar.CONFIG.DESTINATION_DIR = str(tmp_path / 'comics')
    mylar.CONFIG.IGNORE_SEARCH_WORDS = []
    monkeypatch.setattr(mylar, 'MANUAL_PP_LOCK', False, raising=False)
    monkeypatch.setattr(mylar, 'APILOCK', False, raising=False)
    monkeypatch.setattr(mylar, 'MANUAL_PP_STATUS', {'running': False, 'phase': 'idle', 'file_log': []},
                        raising=False)

    def boom(self):
        raise RuntimeError('filechecker blew up')
    monkeypatch.setattr(PostProcessor.PostProcessor, '_process_body', boom)
    monkeypatch.setattr(webserve.threading, 'Thread', SyncThread)
    out = list(webserve.WebInterface().post_process('Manual Run', str(folder)))
    assert json.loads(out[0])['status'] == 'success'
    assert mylar.MANUAL_PP_STATUS['running'] is False
    assert mylar.MANUAL_PP_LOCK is False
    status = json.loads(webserve.WebInterface().manual_pp_status())
    assert status['running'] is False
