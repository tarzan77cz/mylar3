"""The DDL watchdog leaves the item the DDL downloader is working on alone (R43).

Phase 1 of the watchdog marks 'Downloading' rows Completed and sends them to post-processing
when their file looks complete. It must not do that to the item the downloader is still
downloading, unzipping or queueing, and it must not take a file it cannot check (unknown size,
no structure test) for a complete one.
"""
import datetime
import os
import threading

import pytest

import mylar
from mylar import helpers

from conftest import run_ddl_downloader
from fakes import install_router, make_zip, pixeldrain_route

ZIP = make_zip(n_files=20, size=40000)


class _Stop(BaseException):
    pass


@pytest.fixture
def ddl_dir(lib, tmp_path, monkeypatch):
    ddl = tmp_path / 'dl'
    ddl.mkdir()
    mylar.CONFIG.DDL_LOCATION = str(ddl)
    mylar.CONFIG.POST_PROCESSING = True
    mylar.CONFIG.SECURE_DIR = str(tmp_path)  # getcomics.GC() keeps its cookie file there (zip_zip)
    monkeypatch.setattr(mylar, 'GC_URL', 'https://getcomics.org', raising=False)
    monkeypatch.setattr(mylar, 'PP_CURRENT_DDL_IDS', set(), raising=False)
    monkeypatch.setattr(mylar, 'DDLPOOL', None, raising=False)
    monkeypatch.setattr(mylar, 'DDL_HEAL_PP_COUNT', {}, raising=False)
    watchdog_thread = threading.current_thread()
    calls = {'n': 0}

    def sleep(seconds):
        # time.sleep is shared by every thread: only the watchdog (this thread) is stopped,
        # after its first round; the downloader thread does not wait at all.
        if threading.current_thread() is watchdog_thread:
            calls['n'] += 1
            if calls['n'] > 1:
                raise _Stop()
    monkeypatch.setattr(helpers.time, 'sleep', sleep)
    return ddl


def watchdog_round():
    with pytest.raises(_Stop):
        helpers.ddl_watchdog()


def pp_items():
    items = []
    while not mylar.PP_QUEUE.empty():
        items.append(mylar.PP_QUEUE.get())
    return items


def ago(minutes):
    return (datetime.datetime.now() - datetime.timedelta(minutes=minutes)).strftime('%Y-%m-%d %H:%M')


def age_file(path, minutes):
    t = (datetime.datetime.now() - datetime.timedelta(minutes=minutes)).timestamp()
    os.utime(path, (t, t))


def downloading_row(lib, id_, tmp_filename, remote_filesize, updated, pack=0, issueid='I1'):
    lib.execute(
        "INSERT INTO ddl_info (ID, series, status, issueid, comicid, tmp_filename, filename, remote_filesize,"
        " updated_date, pack, site, link_type) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (id_, 'Batman', 'Downloading', issueid, 'C1', tmp_filename, tmp_filename, remote_filesize, updated, pack,
         'DDL(GetComics)', 'GC-Pixel'))


def status(lib, id_):
    return lib.rows('SELECT status FROM ddl_info WHERE ID=?', (id_,))[0]['status']


def test_watchdog_does_not_complete_a_pack_zip_that_is_being_unzipped(lib, ddl_dir, monkeypatch):
    """Pixeldrain unzips the pack while the row is still Downloading: the watchdog must wait."""
    import zipfile
    install_router(monkeypatch, pixeldrain_route(ZIP, name='Batman 001-012 (2025).zip'))
    lib.add_series('C1', 'Batman', [1], year='2025')
    lib.execute("INSERT INTO ddl_info (ID, status, issueid, comicid, link, link_type, site, pack, series)"
                " VALUES ('P1', 'Queued', 'I1', 'C1', 'https://pixeldrain.com/u/abc', 'GC-Pixel',"
                " 'DDL(GetComics)', 1, 'Batman')")
    unzipping = threading.Event()
    release = threading.Event()
    original = zipfile.ZipFile.extractall

    def slow_extractall(self, *a, **k):
        unzipping.set()
        assert release.wait(10)
        return original(self, *a, **k)
    monkeypatch.setattr(zipfile.ZipFile, 'extractall', slow_extractall)
    item = {
        'link': 'https://pixeldrain.com/u/abc', 'mainlink': '', 'series': 'Batman', 'year': '2025',
        'size': '3 MB', 'comicid': 'C1', 'issueid': 'I1', 'oneoff': False, 'id': 'P1', 'link_type': 'GC-Pixel',
        'filename': None, 'tmp_filename': None, 'comicinfo': None, 'packinfo': None, 'pack': 1,
        'site': 'DDL(GetComics)', 'remote_filesize': 0, 'resume': None,
    }
    downloader = threading.Thread(target=run_ddl_downloader, args=([item],))
    downloader.start()
    try:
        assert unzipping.wait(10)
        # the zip is complete on disk and the row is still Downloading: what the watchdog sees
        assert status(lib, 'P1') == 'Downloading'
        watchdog_round()
        assert status(lib, 'P1') == 'Downloading'
        assert mylar.PP_QUEUE.empty()
    finally:
        release.set()
        downloader.join(10)
    assert not downloader.is_alive()
    # the downloader finishes the item itself: one post-processing run, for the unzipped folder
    assert status(lib, 'P1') == 'Completed'
    assert [p['nzb_name'] for p in pp_items()] == ['Batman 001-012 (2025)[__I1__]']
    assert getattr(mylar, 'DDL_ACTIVE_ID', None) is None


@pytest.mark.parametrize('name, body', [
    ('Batman 001 (2025)[__I1__].pdf', b'%PDF-1.4\n' + b'x' * 300000),
    ('Batman 001 (2025)[__I1__].cb7', b"7z\xbc\xaf\x27\x1c" + b'x' * 300000),
], ids=['pdf', 'cb7'])
def test_watchdog_does_not_complete_a_file_it_cannot_check(lib, ddl_dir, name, body):
    """A cut-off .pdf/.cb7 with no known size looks like any complete one: not Completed, no PP."""
    path = os.path.join(str(ddl_dir), name)
    with open(path, 'wb') as f:
        f.write(body)
    age_file(path, 30)
    downloading_row(lib, 'D1', name, None, ago(30))
    watchdog_round()
    assert status(lib, 'D1') != 'Completed'
    assert mylar.PP_QUEUE.empty()
    # left to the stuck branch: back to the queue, where resume asks the host for the rest
    assert status(lib, 'D1') == 'Queued'
    assert os.path.getsize(path) == len(body)  # nothing deleted


def test_watchdog_leaves_an_unchecked_file_alone_while_it_is_written(lib, ddl_dir):
    name = 'Batman 001 (2025)[__I1__].pdf'
    path = os.path.join(str(ddl_dir), name)
    with open(path, 'wb') as f:
        f.write(b'%PDF-1.4\n' + b'x' * 300000)
    downloading_row(lib, 'D1', name, None, ago(1))
    watchdog_round()
    assert status(lib, 'D1') == 'Downloading'
    assert mylar.PP_QUEUE.empty()


def test_watchdog_heal_does_not_send_the_item_being_unzipped_to_pp(lib, ddl_dir, monkeypatch):
    """GC-Main marks the row Completed before it unzips: the heal step must not take the zip either."""
    name = 'Batman 001-012 (2025)[__I1__].zip'
    with open(os.path.join(str(ddl_dir), name), 'wb') as f:
        f.write(ZIP)
    lib.add_series('C1', 'Batman', [1], year='2025')
    lib.set_status(['I1'], 'Snatched')
    downloading_row(lib, 'G1', name, str(len(ZIP)), ago(11), pack=1)
    lib.execute("UPDATE ddl_info SET status='Completed' WHERE ID='G1'")
    monkeypatch.setattr(mylar, 'DDL_ACTIVE_ID', 'G1', raising=False)
    helpers.heal_completed_but_snatched()
    assert mylar.PP_QUEUE.empty()


# --- control: behaviour that stays as it was (these pass before the fix too) ---

def test_control_watchdog_completes_a_finished_cbz_after_a_restart(lib, ddl_dir, monkeypatch):
    monkeypatch.setattr(mylar, 'DDL_ACTIVE_ID', None, raising=False)
    name = 'Batman 001 (2025)[__I1__].cbz'
    with open(os.path.join(str(ddl_dir), name), 'wb') as f:
        f.write(ZIP)
    downloading_row(lib, 'D1', name, str(len(ZIP)), ago(30))
    watchdog_round()
    assert status(lib, 'D1') == 'Completed'
    assert [(p['nzb_name'], p['issueid']) for p in pp_items()] == [(name, 'I1')]


def test_control_watchdog_completes_a_finished_pdf_of_known_size(lib, ddl_dir):
    name = 'Batman 001 (2025)[__I1__].pdf'
    body = b'%PDF-1.4\n' + b'x' * 300000
    with open(os.path.join(str(ddl_dir), name), 'wb') as f:
        f.write(body)
    downloading_row(lib, 'D1', name, str(len(body)), ago(30))
    watchdog_round()
    assert status(lib, 'D1') == 'Completed'
    assert [p['nzb_name'] for p in pp_items()] == [name]


def test_control_watchdog_skips_a_file_that_is_still_being_written(lib, ddl_dir):
    name = 'Batman 001 (2025)[__I1__].cbz'
    with open(os.path.join(str(ddl_dir), name), 'wb') as f:
        f.write(ZIP[:200000])
    downloading_row(lib, 'D1', name, str(len(ZIP)), ago(30))
    watchdog_round()
    assert status(lib, 'D1') == 'Downloading'
    assert mylar.PP_QUEUE.empty()


def test_control_heal_sends_a_finished_file_to_pp_when_nothing_works_on_it(lib, ddl_dir, monkeypatch):
    monkeypatch.setattr(mylar, 'DDL_ACTIVE_ID', None, raising=False)
    name = 'Batman 001 (2025)[__I1__].cbz'
    with open(os.path.join(str(ddl_dir), name), 'wb') as f:
        f.write(ZIP)
    lib.add_series('C1', 'Batman', [1], year='2025')
    lib.set_status(['I1'], 'Snatched')
    downloading_row(lib, 'G1', name, str(len(ZIP)), ago(11))
    lib.execute("UPDATE ddl_info SET status='Completed' WHERE ID='G1'")
    helpers.heal_completed_but_snatched()
    assert [p['nzb_name'] for p in pp_items()] == [name]
