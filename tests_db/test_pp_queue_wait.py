"""The post-processing queue takes the next item only when the previous post-processing ended (R34).

process.Process.post_process() starts the post-processing of an API/DDL item in a thread and
returns at once. postprocess_main() used to release APILOCK 5 seconds later and take the next
item, so a long post-processing (a pack) could run next to the following one.
"""
import queue as queue_mod
import threading

import pytest

import mylar
from mylar import helpers, process


class FakePostProcessor(object):
    """PostProcessor stand-in: takes APILOCK for API calls like the real one and blocks on demand."""
    runs = []
    gates = {}      # nzb_name -> Event the run waits for
    started = {}    # nzb_name -> Event set when the run starts

    def __init__(self, nzb_name, nzb_folder, issueid=None, queue=None, comicid=None, apicall=False, ddl=False,
                 download_info=None):
        self.nzb_name = nzb_name
        self.apicall = apicall
        if apicall is True:
            mylar.APILOCK = True

    def Process(self):
        try:
            FakePostProcessor.runs.append(('start', self.nzb_name))
            if self.nzb_name in FakePostProcessor.started:
                FakePostProcessor.started[self.nzb_name].set()
            gate = FakePostProcessor.gates.get(self.nzb_name)
            if gate is not None:
                assert gate.wait(30)
            FakePostProcessor.runs.append(('end', self.nzb_name))
        finally:
            if self.apicall is True:
                mylar.APILOCK = False


@pytest.fixture
def ppq(lib, monkeypatch):
    FakePostProcessor.runs = []
    FakePostProcessor.gates = {}
    FakePostProcessor.started = {}
    monkeypatch.setattr(mylar.PostProcessor, 'PostProcessor', FakePostProcessor)
    monkeypatch.setattr(helpers.time, 'sleep', lambda *a: None)
    monkeypatch.setattr(mylar, 'APILOCK', False, raising=False)
    monkeypatch.setattr(mylar, 'PP_CURRENT_DDL_IDS', set(), raising=False)
    warnings = []
    real_warn = helpers.logger.warn

    def warn(msg, *a, **k):
        warnings.append(msg)
        return real_warn(msg, *a, **k)
    monkeypatch.setattr(helpers.logger, 'warn', warn)
    return warnings


def item(name, ddl_id=None):
    it = {'nzb_name': name, 'nzb_folder': '/downloads/%s' % name, 'failed': False, 'issueid': None,
          'comicid': 'C1', 'apicall': True, 'ddl': True}
    if ddl_id is not None:
        it['download_info'] = {'provider': 'DDL', 'id': ddl_id}
        mylar.PP_DDL_IDS.add(ddl_id)
    return it


def pp_queue(*items):
    q = queue_mod.Queue()
    for it in items:
        q.put(it)
    q.put('exit')
    return q


def test_second_item_waits_for_the_first_post_processing(ppq, monkeypatch):
    pack, single = 'Pack 001-213', 'Single 005'
    release = threading.Event()
    FakePostProcessor.gates[pack] = release
    FakePostProcessor.started[pack] = threading.Event()
    FakePostProcessor.started[single] = threading.Event()
    # Either the queue waits for the pack's thread (join) or it starts the next item: whichever
    # comes first sets `moved`, so the test never has to guess with a sleep.
    moved = threading.Event()
    joining = []
    real_join = threading.Thread.join

    def join(self, timeout=None):
        if threading.current_thread().name == 'PP-QUEUE-TEST':
            joining.append(self)
            moved.set()
        return real_join(self, timeout)
    monkeypatch.setattr(threading.Thread, 'join', join)
    FakePostProcessor.started[single] = moved

    worker = threading.Thread(target=helpers.postprocess_main, args=(pp_queue(item(pack), item(single)),),
                              name='PP-QUEUE-TEST')
    worker.start()
    try:
        assert FakePostProcessor.started[pack].wait(10)
        assert moved.wait(10)
        # the queue is waiting for the pack, the single issue has not started
        assert ('start', single) not in FakePostProcessor.runs
        assert joining
    finally:
        release.set()
        worker.join(10)
    assert not worker.is_alive()
    assert FakePostProcessor.runs == [('start', pack), ('end', pack), ('start', single), ('end', single)]
    assert mylar.APILOCK is False
    assert ppq == []


def test_post_processing_that_overruns_the_wait_is_left_running(ppq, monkeypatch):
    monkeypatch.setattr(helpers, 'PP_THREAD_WAIT', 0.2, raising=False)
    stuck, nxt = 'Stuck Pack 001-050', 'Next 001'
    release = threading.Event()
    FakePostProcessor.gates[stuck] = release
    try:
        helpers.postprocess_main(pp_queue(item(stuck), item(nxt)))
        # the next item ran while the stuck one was still going (its thread is not killed)
        assert ('start', nxt) in FakePostProcessor.runs
        assert ('end', stuck) not in FakePostProcessor.runs
    finally:
        release.set()
    assert any(stuck in w for w in ppq), ppq
    assert mylar.APILOCK is False


# --- control (passes before the fix too) ---

def test_control_single_item_runs_and_releases_the_lock(ppq):
    helpers.postprocess_main(pp_queue(item('Single 005', ddl_id='77')))
    assert FakePostProcessor.runs[0] == ('start', 'Single 005')
    assert mylar.APILOCK is False
    assert '77' not in mylar.PP_DDL_IDS and '77' not in mylar.PP_CURRENT_DDL_IDS


def test_control_non_api_post_processing_still_joins_and_reads_the_result(lib, monkeypatch):
    """The SAB/NZBGet path (no apicall, no issueid) waits for the thread and reads its result as before."""
    seen = []

    class Done(object):
        def __init__(self, nzb_name, nzb_folder, issueid=None, queue=None, **k):
            self.queue = queue

        def Process(self):
            seen.append('ran')
            self.queue.put([{'mode': 'stop'}])
    monkeypatch.setattr(mylar.PostProcessor, 'PostProcessor', Done)
    result = process.Process('Batman 005', '/downloads/Batman 005').post_process()
    assert result is None
    assert seen == ['ran']
