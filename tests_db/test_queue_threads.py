"""An exception in one queue item must not end the DDL or search thread (R13)."""
import threading

import pytest
import requests

import mylar
from mylar import getcomics, helpers

from conftest import run_ddl_downloader
from fakes import install_router
from test_pack_sections import FakeGC
from test_single_exhausted import single_item


@pytest.fixture
def ddl_env(lib, tmp_path, monkeypatch):
    ddl = tmp_path / 'dl'
    ddl.mkdir()
    mylar.CONFIG.DDL_LOCATION = str(ddl)
    mylar.CONFIG.SECURE_DIR = str(tmp_path)
    monkeypatch.setattr(mylar, 'GC_URL', 'https://getcomics.org', raising=False)
    monkeypatch.setattr(helpers.time, 'sleep', lambda *a: None)
    return ddl


def test_downloader_exception_is_a_host_failure_and_the_loop_goes_on(lib, ddl_env, monkeypatch):
    def route(url, headers):
        raise requests.exceptions.ConnectionError('pixeldrain unreachable')
    install_router(monkeypatch, route)
    FakeGC.download = {'success': True, 'filename': 'Batman 006 (2025).cbz', 'path': str(ddl_env)}
    FakeGC.redo = {'success': False, 'links_exhausted': ['GC-Main', 'GC-Pixel']}
    FakeGC.calls = []
    monkeypatch.setattr(helpers.getcomics, 'GC', FakeGC)

    lib.add_series('C1', 'Batman', [5, 6], year='2025')
    lib.set_status(['I5', 'I6'], 'Snatched')
    lib.execute("INSERT INTO ddl_info (ID, status, issueid) VALUES ('77', 'Queued', 'I5')")
    lib.execute("INSERT INTO ddl_info (ID, status, issueid) VALUES ('78', 'Queued', 'I6')")
    first = single_item('I5', '5', post_id='77')
    first.update({'link': 'https://pixeldrain.com/u/abc', 'link_type': 'GC-Pixel'})
    second = single_item('I6', '6', post_id='78')

    run_ddl_downloader([first, second])

    # the first item went the host-failure way: next host asked, then Q5
    assert len(FakeGC.calls) == 1
    assert lib.rows("SELECT status FROM ddl_info WHERE ID='77'") == [{'status': 'Failed'}]
    assert lib.status('I5') == 'Wanted'
    assert [r['ID'] for r in lib.rows('SELECT ID FROM failed')] == ['77']
    # and the item behind it was still downloaded
    assert lib.rows("SELECT status FROM ddl_info WHERE ID='78'") == [{'status': 'Completed'}]
    assert mylar.DDL_LOCK is False


def test_cookie_receipt_error_releases_the_ddl_lock(lib, ddl_env, monkeypatch):
    def boom(self, *a, **k):
        raise requests.exceptions.ConnectionError('flaresolverr down')
    monkeypatch.setattr(getcomics.GC, 'cookie_receipt', boom)
    gc = getcomics.GC()
    with pytest.raises(requests.exceptions.ConnectionError):
        gc.downloadit('B1', 'https://cdn.example/one.cbz', 'https://getcomics.org/dc/one/')
    assert mylar.DDL_LOCK is False


def test_cookie_receipt_error_in_the_loop_fails_only_that_item(lib, ddl_env, monkeypatch):
    def boom(self, *a, **k):
        raise requests.exceptions.ConnectionError('flaresolverr down')
    monkeypatch.setattr(getcomics.GC, 'cookie_receipt', boom)
    lib.add_series('C1', 'Batman', [5], year='2025')
    lib.execute("INSERT INTO ddl_info (ID, status, issueid) VALUES ('B1', 'Queued', 'I5')")
    item = single_item('I5', '5', post_id='B1')
    item.update({'comicinfo': None, 'packinfo': None, 'mainlink': ''})
    run_ddl_downloader([item])
    assert lib.rows("SELECT status FROM ddl_info WHERE ID='B1'") == [{'status': 'Failed'}]
    assert mylar.DDL_LOCK is False
    # downloadit no longer appends the ID a second time, so the cleanup leaves none (R41)
    assert mylar.DDL_QUEUED == []


def test_unexpected_error_in_an_item_fails_it_and_the_loop_goes_on(lib, ddl_env, monkeypatch):
    FakeGC.download = {'success': True, 'filename': 'Batman 006 (2025).cbz', 'path': str(ddl_env)}
    monkeypatch.setattr(helpers.getcomics, 'GC', FakeGC)

    def broken_check(path):
        raise RuntimeError('unexpected')
    calls = {'n': 0}

    def check_once(path):
        calls['n'] += 1
        if calls['n'] == 1:
            broken_check(path)
        return {'status': True, 'type': 'ZIP', 'quality': 'ok'}
    monkeypatch.setattr(helpers, 'check_file_condition', check_once)
    lib.add_series('C1', 'Batman', [5, 6], year='2025')
    lib.set_status(['I5', 'I6'], 'Snatched')
    lib.execute("INSERT INTO ddl_info (ID, status, issueid) VALUES ('77', 'Queued', 'I5')")
    lib.execute("INSERT INTO ddl_info (ID, status, issueid) VALUES ('78', 'Queued', 'I6')")
    run_ddl_downloader([single_item('I5', '5', post_id='77'), single_item('I6', '6', post_id='78')])
    assert lib.rows("SELECT status FROM ddl_info WHERE ID='77'") == [{'status': 'Failed'}]
    assert lib.status('I5') == 'Snatched'  # unexpected error: the issues are left as they are
    assert lib.rows("SELECT status FROM ddl_info WHERE ID='78'") == [{'status': 'Completed'}]
    assert '77' not in mylar.DDL_QUEUED
    assert mylar.DDL_LOCK is False


class _Stop(BaseException):
    pass


@pytest.fixture
def thread_env(lib, monkeypatch):
    starts = []
    monkeypatch.setattr(mylar, 'queue_schedule', lambda queuetype, mode: starts.append((queuetype, mode)),
                        raising=False)
    monkeypatch.setattr(mylar, '_INITIALIZED', True, raising=False)
    monkeypatch.setattr(mylar, 'SIGNAL', None, raising=False)
    mylar.CONFIG.ENABLE_DDL = True
    dead = threading.Thread(target=lambda: None, name='DDL-QUEUE')
    dead.start()
    dead.join()
    monkeypatch.setattr(mylar, 'DDLPOOL', dead, raising=False)
    return starts


def test_watchdog_restarts_a_dead_ddl_thread(thread_env):
    helpers.ddl_thread_check()
    assert thread_env == [('ddl_queue', 'start')]


def test_watchdog_loop_checks_the_ddl_thread(thread_env, monkeypatch):
    sleeps = {'n': 0}

    def sleep(seconds):
        sleeps['n'] += 1
        if sleeps['n'] > 1:
            raise _Stop()
    monkeypatch.setattr(helpers.time, 'sleep', sleep)
    monkeypatch.setattr(mylar, 'PP_CURRENT_DDL_IDS', set(), raising=False)
    with pytest.raises(_Stop):
        helpers.ddl_watchdog()
    assert thread_env == [('ddl_queue', 'start')]


def test_watchdog_leaves_a_live_ddl_thread_alone(thread_env, monkeypatch):
    stop = threading.Event()
    alive = threading.Thread(target=stop.wait, name='DDL-QUEUE')
    alive.start()
    try:
        monkeypatch.setattr(mylar, 'DDLPOOL', alive)
        helpers.ddl_thread_check()
    finally:
        stop.set()
        alive.join()
    assert thread_env == []


@pytest.mark.parametrize('change', [
    {'SIGNAL': 'shutdown'}, {'SIGNAL': 'restart'}, {'_INITIALIZED': False}, {'DDLPOOL': None},
])
def test_watchdog_does_not_restart_while_shutting_down(thread_env, monkeypatch, change):
    for name, value in change.items():
        monkeypatch.setattr(mylar, name, value)
    helpers.ddl_thread_check()
    assert thread_env == []


def test_watchdog_does_not_restart_when_ddl_is_off(thread_env):
    mylar.CONFIG.ENABLE_DDL = False
    helpers.ddl_thread_check()
    assert thread_env == []


def test_search_queue_survives_an_item_error(lib, monkeypatch):
    monkeypatch.setattr(helpers.time, 'sleep', lambda *a: None)
    monkeypatch.setattr(mylar, 'SEARCHLOCK', False, raising=False)
    monkeypatch.setattr(helpers, 'is_issue_still_wanted', lambda item: True)
    monkeypatch.setattr(helpers, 'pack_queued_for_download', lambda issueid: False)

    class NoLocalFile(object):
        def __init__(self, *a, **k):
            pass

        def walk_the_walk(self):
            return {'status': False}
    monkeypatch.setattr(mylar.filers, 'FileHandlers', NoLocalFile)
    searched = []

    def searchforissue(issueid, manual=False):
        searched.append(issueid)
        if issueid == 'I1':
            raise RuntimeError('search blew up')
    monkeypatch.setattr(mylar.search, 'searchforissue', searchforissue)
    import queue as queue_mod
    q = queue_mod.Queue()
    q.put({'comicid': 'C1', 'issueid': 'I1'})
    q.put({'comicid': 'C1', 'issueid': 'I2'})
    q.put('exit')
    helpers.search_queue(q)
    assert searched == ['I1', 'I2']
