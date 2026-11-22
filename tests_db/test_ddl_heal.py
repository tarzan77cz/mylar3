"""Watchdog heal of finished DDL files: Pixeldrain names (R21), retry limit after PP rejects a file (R20)."""
import os

import pytest

import mylar
from mylar import db, helpers

from fakes import make_zip

ZIP = make_zip(n_files=4, size=60000)
OLD = '2026-01-01 00:00'


@pytest.fixture
def ddl_dir(lib, tmp_path, monkeypatch):
    ddl = tmp_path / 'dl'
    ddl.mkdir()
    mylar.CONFIG.DDL_LOCATION = str(ddl)
    mylar.CONFIG.POST_PROCESSING = True
    monkeypatch.setattr(mylar, 'PP_CURRENT_DDL_IDS', set(), raising=False)
    return ddl


def pixeldrain_row(lib, ddl, status='Completed', data=ZIP):
    """A Pixeldrain download: bare name in filename, real file name in tmp_filename."""
    lib.add_series('C1', 'Batman', [5], status='Snatched', year='2025')
    (ddl / 'X[__I5__].cbz').write_bytes(data)
    lib.execute("INSERT INTO ddl_info (ID, series, status, issueid, comicid, filename, tmp_filename, remote_filesize,"
                " updated_date, link_type, site) VALUES ('P5', 'Batman #5', ?, 'I5', 'C1', 'X.cbz', 'X[__I5__].cbz', ?, ?,"
                " 'GC-Pixel', 'DDL(GetComics)')", (status, str(len(data)), OLD))


def pp_items():
    items = []
    while not mylar.PP_QUEUE.empty():
        items.append(mylar.PP_QUEUE.get())
    return items


def test_queue_ddl_postprocess_finds_the_pixeldrain_file(lib, ddl_dir):
    pixeldrain_row(lib, ddl_dir)
    row = db.DBConnection().selectone("SELECT * FROM ddl_info WHERE ID='P5'").fetchone()
    assert helpers.queue_ddl_postprocess(row) is True
    [item] = pp_items()
    assert item['nzb_name'] == 'X[__I5__].cbz'
    assert item['nzb_folder'] == os.path.join(str(ddl_dir), 'X[__I5__].cbz')
    assert item['issueid'] == 'I5'


def test_heal_sends_the_pixeldrain_file_to_post_processing(lib, ddl_dir):
    pixeldrain_row(lib, ddl_dir)
    helpers.heal_completed_but_snatched()
    assert [x['nzb_name'] for x in pp_items()] == ['X[__I5__].cbz']


def test_release_after_pp_finds_the_pixeldrain_file(lib, ddl_dir):
    pixeldrain_row(lib, ddl_dir)
    helpers.release_unfinished_single_ddl({'provider': 'DDL', 'id': 'P5'}, None, 'matched 0 files')
    row = lib.rows("SELECT status, updated_date FROM ddl_info WHERE ID='P5'")[0]
    # the readable file was found: it stays Completed for the next heal (not 'file is gone')
    assert row['status'] == 'Completed'
    assert row['updated_date'] != OLD


def test_release_requeues_a_short_pixeldrain_file(lib, ddl_dir):
    pixeldrain_row(lib, ddl_dir, data=ZIP[:150000])
    lib.execute("UPDATE ddl_info SET remote_filesize=? WHERE ID='P5'", (str(len(ZIP)),))
    helpers.release_unfinished_single_ddl({'provider': 'DDL', 'id': 'P5'}, None, 'post-processing failed')
    assert lib.rows("SELECT status FROM ddl_info WHERE ID='P5'") == [{'status': 'Queued'}]


def finished_row(lib, ddl, pack=0):
    """A readable finished single DDL file that post-processing keeps rejecting."""
    lib.add_series('C1', 'Batman', [1], status='Snatched', year='2025')
    fname = 'Batman 001 (2025)[__I1__].cbz'
    (ddl / fname).write_bytes(ZIP)
    lib.execute("INSERT INTO ddl_info (ID, series, status, issueid, comicid, filename, remote_filesize, updated_date,"
                " link_type, site, pack) VALUES ('D1', 'Batman #1 (2025)', 'Completed', 'I1', 'C1', ?, ?, ?,"
                " 'GC-Main', 'DDL(GetComics)', ?)", (fname, str(len(ZIP)), OLD, pack))
    return fname


def heal_and_reject(rounds):
    """Run heal; every post-processing it starts gives up like PostProcessor does at 'matched 0 files'."""
    queued = []
    for _ in range(rounds):
        helpers.heal_completed_but_snatched()
        items = pp_items()
        queued.append(len(items))
        for item in items:
            mylar.PP_DDL_IDS.discard(item['download_info']['id'])
            helpers.release_unfinished_single_ddl(item['download_info'], item['nzb_folder'], 'matched 0 files')
        db.DBConnection().upsert('ddl_info', {'updated_date': OLD}, {'id': 'D1'})  # ten minutes pass
    return queued


@pytest.fixture
def heal_counts(monkeypatch):
    monkeypatch.setattr(mylar, 'DDL_HEAL_PP_COUNT', {}, raising=False)


def test_heal_gives_up_after_three_rejections(lib, ddl_dir, heal_counts):
    fname = finished_row(lib, ddl_dir)
    assert heal_and_reject(4) == [1, 1, 1, 0]
    assert lib.rows("SELECT status FROM ddl_info WHERE ID='D1'") == [{'status': 'Failed'}]
    assert lib.status('I1') == 'Wanted'
    failed = lib.rows('SELECT ID, IssueID, Issue_Number, Provider FROM failed')
    assert failed == [{'ID': 'D1', 'IssueID': 'I1', 'Issue_Number': '1', 'Provider': 'DDL(GetComics)'}]
    assert os.path.isfile(os.path.join(str(ddl_dir), fname))  # the file in /downloads is kept


def test_heal_gives_up_on_a_pack_but_leaves_its_issues(lib, ddl_dir, heal_counts):
    finished_row(lib, ddl_dir, pack=1)
    assert heal_and_reject(4) == [1, 1, 1, 0]
    assert lib.rows("SELECT status FROM ddl_info WHERE ID='D1'") == [{'status': 'Failed'}]
    assert lib.status('I1') == 'Snatched'
    assert lib.rows('SELECT * FROM failed') == []


def test_heal_keeps_retrying_below_the_limit(lib, ddl_dir, heal_counts):
    finished_row(lib, ddl_dir)
    assert heal_and_reject(3) == [1, 1, 1]
    assert lib.rows("SELECT status FROM ddl_info WHERE ID='D1'") == [{'status': 'Completed'}]
    assert lib.status('I1') == 'Snatched'
