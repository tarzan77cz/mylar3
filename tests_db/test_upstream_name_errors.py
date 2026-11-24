"""Code paths that ended in NameError/TypeError (review R45): one-off PP from the pull list,
the dupecheck of two "Fixed" files and the size fallback of the DDL queue. No network.
"""
import os
import queue

import pytest

import mylar
from mylar import PostProcessor, helpers

from test_ddl_queue_state import gc_item, queued_row, recording_gc  # noqa: F401  (fixture)
from test_pp_issue_number import DefaultsConfig
from conftest import run_ddl_downloader

WEEKLY = ('CREATE TABLE weekly (SHIPDATE, PUBLISHER text, ISSUE text, COMIC VARCHAR(150), EXTRA text, STATUS text,'
          ' ComicID text, IssueID text, CV_Last_Update text, DynamicName text, weeknumber text, year text,'
          ' volume text, seriesyear text, annuallink text, format text, rowid INTEGER PRIMARY KEY)')


# --- PostProcessor: one-off from the pull list (ALT_PULL 2) ------------------------------

@pytest.fixture
def oneoff_pp(lib, tmp_path, monkeypatch):
    """A completed NZB of a pull-list one-off: nzblog row with OneOff, issue not on the watchlist."""
    monkeypatch.setattr(mylar, 'CONFIG', DefaultsConfig(str(tmp_path)))
    mylar.CONFIG.ALT_PULL = 2
    monkeypatch.setattr(mylar, 'USE_SABNZBD', 0, raising=False)
    monkeypatch.setattr(mylar, 'USE_NZBGET', 0, raising=False)
    lib.execute(WEEKLY)
    lib.execute("INSERT INTO weekly (SHIPDATE, PUBLISHER, ISSUE, COMIC, STATUS, ComicID, IssueID, volume)"
                " VALUES ('2026-11-18', 'Image', '1', 'Some One-Shot', 'Snatched', 'C77', '2001', 'v2')")
    lib.execute("INSERT INTO nzblog (IssueID, NZBName, SARC, PROVIDER, ID, OneOff)"
                " VALUES ('2001', 'Some.One-Shot.001.2026', NULL, 'nzb', 'n1', 'True')")
    folder = tmp_path / 'done'
    folder.mkdir()
    q = queue.Queue()
    pp = PostProcessor.PostProcessor('Some.One-Shot.001.2026', str(folder), queue=q)
    seen = []
    monkeypatch.setattr(pp, 'nzb_or_oneoff_pp', lambda tinfo=None, manual=None: seen.append(tinfo))
    return pp, q, seen


def test_pull_list_one_off_is_post_processed_with_the_weekly_row(oneoff_pp):
    pp, q, seen = oneoff_pp
    pp.Process()
    assert q.empty()  # no 'stop' from the error handler
    assert len(seen) == 1
    tinfo = seen[0]
    assert (tinfo['comicid'], tinfo['issueid'], tinfo['comicname'], tinfo['issuenumber']) == \
        ('C77', '2001', 'Some One-Shot', '1')
    assert (tinfo['seriesyear'], tinfo['seriesvolume'], tinfo['publisher'], tinfo['oneoff']) == \
        ('2026', 'v2', 'Image', True)


# --- duplicate_filecheck: both files are "Fixed" versions --------------------------------

@pytest.fixture
def dupe(lib, tmp_path):
    mylar.CONFIG.DUPECONSTRAINT = 'filesize'
    lib.add_series('C1', 'Batman', [], year='2020')
    lib.execute("UPDATE comics SET ComicLocation=? WHERE ComicID='C1'", (str(tmp_path / 'lib'),))
    lib.add_issue('C1', 1, status='Downloaded')

    def run(existing, new):
        lib.execute("UPDATE issues SET Location=?, ComicSize='5000' WHERE IssueID='I1'", (existing,))
        path = tmp_path / new
        path.write_bytes(b'0' * 100)
        return helpers.duplicate_filecheck(str(path), ComicID='C1', IssueID='I1')
    return run


def test_higher_fixed_version_replaces_the_existing_file(dupe, tmp_path):
    res = dupe('Batman 001 (2020) (f1).cbz', 'Batman 001 (2020) (f2).cbz')
    assert res == {'action': 'dupe_src',
                   'to_dupe': os.path.join(str(tmp_path / 'lib'), 'Batman 001 (2020) (f1).cbz')}


def test_lower_fixed_version_keeps_the_existing_file(dupe, tmp_path):
    new = str(tmp_path / 'Batman 001 (2020) (f1).cbz')
    res = dupe('Batman 001 (2020) (f3).cbz', 'Batman 001 (2020) (f1).cbz')
    assert res == {'action': 'dupe_file', 'to_dupe': new}


def test_only_the_new_file_fixed_still_wins(dupe, tmp_path):
    # control: unchanged branch
    res = dupe('Batman 001 (2020).cbz', 'Batman 001 (2020) (f1).cbz')
    assert res['action'] == 'dupe_src'


# --- ddl_downloader: size fallback for an item without remote_filesize --------------------

def test_item_without_remote_filesize_uses_its_size_text(lib, recording_gc):  # noqa: F811
    item = gc_item()
    del item['remote_filesize']
    item['size'] = '40 MB'
    queued_row(lib, '77')
    run_ddl_downloader([item])
    assert len(recording_gc.calls) == 1
    # downloadit(id, link, mainlink, resume, issueid, remote_filesize)
    assert recording_gc.calls[0][5] == 40 * 1024 * 1024


def test_item_with_remote_filesize_passes_it_on(lib, recording_gc):  # noqa: F811
    # control: every queue producer today sets remote_filesize, that path is unchanged
    item = gc_item()
    item['remote_filesize'] = 1234567
    queued_row(lib, '77')
    run_ddl_downloader([item])
    assert recording_gc.calls[0][5] == 1234567
