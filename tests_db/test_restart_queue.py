"""Restart Queue must not start a second DDL thread while a download is running (R15)."""
import datetime
import json
import queue
import threading

import pytest

import mylar
from mylar import webserve


def now():
    return datetime.datetime.now().strftime('%Y-%m-%d %H:%M')


@pytest.fixture
def ddl_queue(lib, tmp_path, monkeypatch):
    ddl = tmp_path / 'dl'
    ddl.mkdir()
    mylar.CONFIG.DDL_LOCATION = str(ddl)
    monkeypatch.setattr(mylar, 'DDL_QUEUE', queue.Queue(), raising=False)
    monkeypatch.setattr(mylar, 'PP_CURRENT_DDL_IDS', set(), raising=False)
    starts = []
    monkeypatch.setattr(mylar, 'queue_schedule', lambda queuetype, mode: starts.append((queuetype, mode)),
                        raising=False)
    lib.add_series('C1', 'Batman', [1, 2], status='Snatched', year='2025')
    return starts


class FakeDDLThread(object):
    """A running DDL-QUEUE thread; ``ignore_exit`` keeps it busy after the exit signal."""

    def __init__(self, ignore_exit=False):
        self.stop = threading.Event()
        self.ignore_exit = ignore_exit
        self.thread = threading.Thread(target=self.run, name='DDL-QUEUE', daemon=True)
        self.thread.start()

    def run(self):
        while not self.stop.is_set():
            try:
                item = mylar.DDL_QUEUE.get(timeout=0.1)
            except queue.Empty:
                continue
            if item == 'exit' and not self.ignore_exit:
                return

    def close(self):
        self.stop.set()
        self.thread.join()


def ddl_threads():
    return [t for t in threading.enumerate() if t.name == 'DDL-QUEUE' and t.is_alive()]


def add_row(lib, id_, status, updated, issueid='I1', link_type='GC-Main'):
    lib.execute("INSERT INTO ddl_info (ID, series, year, status, issueid, comicid, link, link_type, site, updated_date)"
                " VALUES (?, 'Batman #1', '2025', ?, ?, 'C1', 'https://cdn.example/x.cbz', ?, 'DDL(GetComics)', ?)",
                (id_, status, issueid, link_type, updated))


@pytest.mark.parametrize('lock, link_type', [(True, 'GC-Main'), (False, 'GC-Pixel')])
def test_restart_queue_refuses_while_downloading(lib, ddl_queue, monkeypatch, lock, link_type):
    worker = FakeDDLThread()
    try:
        monkeypatch.setattr(mylar, 'DDLPOOL', worker.thread, raising=False)
        mylar.DDL_LOCK = lock  # Pixeldrain and MediaFire downloads do not take the lock
        add_row(lib, 'X1', 'Downloading', now(), link_type=link_type)
        add_row(lib, 'X2', 'Queued', now(), issueid='I2')
        result = json.loads(webserve.WebInterface().ddl_requeue('restart_queue'))
        assert result['status'] is False
        assert 'in progress' in result['message']
        assert lib.rows("SELECT status FROM ddl_info WHERE ID='X1'") == [{'status': 'Downloading'}]
        assert mylar.DDLPOOL is worker.thread and worker.thread.is_alive()
        assert len(ddl_threads()) == 1
        assert ddl_queue == []
        assert mylar.DDL_LOCK is lock
    finally:
        worker.close()


def test_restart_queue_with_a_dead_thread_restarts_as_before(lib, ddl_queue, monkeypatch):
    dead = threading.Thread(target=lambda: None, name='DDL-QUEUE')
    dead.start()
    dead.join()
    monkeypatch.setattr(mylar, 'DDLPOOL', dead, raising=False)
    mylar.DDL_LOCK = True  # left over from the dead thread
    add_row(lib, 'X1', 'Downloading', now())
    result = json.loads(webserve.WebInterface().ddl_requeue('restart_queue'))
    assert result['status'] is True
    assert ddl_queue == [('ddl_queue', 'start')]
    assert lib.rows("SELECT status FROM ddl_info WHERE ID='X1'") == [{'status': 'Queued'}]
    assert mylar.DDL_LOCK is False
    assert [x['id'] for x in list(mylar.DDL_QUEUE.queue)] == ['X1']


def test_restart_queue_with_an_idle_thread_restarts_as_before(lib, ddl_queue, monkeypatch):
    worker = FakeDDLThread()
    try:
        monkeypatch.setattr(mylar, 'DDLPOOL', worker.thread, raising=False)
        add_row(lib, 'X1', 'Downloading', '2026-01-01 00:00')  # stale row, nothing writes its file
        result = json.loads(webserve.WebInterface().ddl_requeue('restart_queue'))
        assert result['status'] is True
        assert not worker.thread.is_alive()  # it took the exit signal
        assert ddl_queue == [('ddl_queue', 'start')]
        assert lib.rows("SELECT status FROM ddl_info WHERE ID='X1'") == [{'status': 'Queued'}]
    finally:
        worker.close()


def test_restart_queue_keeps_one_consumer_when_the_thread_does_not_stop(lib, ddl_queue, monkeypatch):
    worker = FakeDDLThread(ignore_exit=True)  # e.g. it took the next queued item before the exit
    try:
        monkeypatch.setattr(mylar, 'DDLPOOL', worker.thread, raising=False)
        add_row(lib, 'X1', 'Downloading', '2026-01-01 00:00')
        result = json.loads(webserve.WebInterface().ddl_requeue('restart_queue'))
        assert result['status'] is False
        assert mylar.DDLPOOL is worker.thread
        assert ddl_queue == []
        assert len(ddl_threads()) == 1
        assert lib.rows("SELECT status FROM ddl_info WHERE ID='X1'") == [{'status': 'Downloading'}]
    finally:
        worker.close()
