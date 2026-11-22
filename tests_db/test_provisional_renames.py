"""Registry of files named with an estimated cover date (review R29). Temp DB and library, no network."""
import os
import shutil
import threading

import pytest

import mylar
from mylar import helpers, updater, webserve


@pytest.fixture
def library(lib, tmp_path, monkeypatch):
    lib.execute('ALTER TABLE comics ADD COLUMN AlternateFileName TEXT')
    lib.execute('ALTER TABLE comics ADD COLUMN PublisherImprint TEXT')
    lib.execute('CREATE TABLE weekly (SHIPDATE TEXT, ComicID TEXT, IssueID TEXT, year TEXT, weeknumber TEXT)')
    folder = tmp_path / 'comics' / 'X (2026)'
    folder.mkdir(parents=True)
    lib.execute("INSERT INTO comics (ComicID, ComicName, ComicYear, ComicPublisher, ComicLocation, Type)"
                " VALUES ('C1', 'X', '2026', 'Image', ?, 'Print')", (str(folder),))
    cfg = mylar.CONFIG
    cfg.FILE_FORMAT = '$Series $Issue ($Year-$month)'
    cfg.RENAME_FILES = True
    cfg.ANNUALS_ON = False
    cfg.REPLACE_SPACES = False
    cfg.LOWERCASE_FILENAMES = False
    cfg.UNICODE_ISSUENUMBER = False
    cfg.FORMAT_BOOKTYPE = False
    cfg.DESTINATION_DIR = str(tmp_path / 'comics')
    monkeypatch.setattr(updater, 'forceRescan', lambda *a, **k: None)
    lib.folder = str(folder)
    return lib


def add_issue(lib, iid, num, issuedate, releasedate, location, status='Downloaded'):
    lib.execute('INSERT INTO issues (IssueID, ComicID, ComicName, Issue_Number, IssueDate, ReleaseDate, DigitalDate,'
                ' Status, Location, Int_IssueNumber) VALUES (?,?,?,?,?,?,?,?,?,?)',
                (iid, 'C1', 'X', num, issuedate, releasedate, '0000-00-00', status, location,
                 helpers.issue_number_parser(num).asInt))


def touch(lib, name, content=b'x'):
    with open(os.path.join(lib.folder, name), 'wb') as f:
        f.write(content)


def files(lib):
    return sorted(os.listdir(lib.folder))


def location(lib, iid):
    return lib.rows('SELECT Location FROM issues WHERE IssueID=?', (iid,))[0]['Location']


def test_entry_survives_a_blocked_rename_and_is_used_on_the_next_run(library):
    add_issue(library, 'I3', '3', '2026-12-01', '2026-10-14', 'X 3 (2026-12).cbz')
    touch(library, 'X 3 (2026-12).cbz', b'issue3')
    helpers.register_provisional_rename('I3', 'X 3 (2026-12).cbz')
    library.execute("UPDATE issues SET IssueDate='2027-01-01' WHERE IssueID='I3'")
    touch(library, 'X 3 (2027-01).cbz', b'stray')
    assert helpers.rename_placeholder_dated_files('C1') == 0
    assert helpers.load_provisional_renames() == {'I3': 'X 3 (2026-12).cbz'}
    os.remove(os.path.join(library.folder, 'X 3 (2027-01).cbz'))
    assert helpers.rename_placeholder_dated_files('C1') == 1
    assert location(library, 'I3') == 'X 3 (2027-01).cbz'
    assert helpers.load_provisional_renames() == {}


def test_entry_survives_while_the_file_is_missing(library, tmp_path):
    add_issue(library, 'I4', '4', '2027-01-01', '2026-10-21', 'X 4 (2026-12).cbz')
    touch(library, 'X 4 (2026-12).cbz', b'issue4')
    helpers.register_provisional_rename('I4', 'X 4 (2026-12).cbz')
    shutil.move(os.path.join(library.folder, 'X 4 (2026-12).cbz'), str(tmp_path / 'aside.cbz'))
    assert helpers.rename_placeholder_dated_files('C1') == 0
    assert helpers.load_provisional_renames() == {'I4': 'X 4 (2026-12).cbz'}
    shutil.move(str(tmp_path / 'aside.cbz'), os.path.join(library.folder, 'X 4 (2026-12).cbz'))
    assert helpers.rename_placeholder_dated_files('C1') == 1
    assert location(library, 'I4') == 'X 4 (2027-01).cbz'


def test_converted_file_with_the_estimated_name_is_still_renamed(library):
    # Comics converts .cbr to .cbz: same name, other extension, still the estimate
    add_issue(library, 'I7', '7', '2027-02-01', '2026-11-18', 'X 7 (2027-01).cbz')
    touch(library, 'X 7 (2027-01).cbz')
    helpers.register_provisional_rename('I7', 'X 7 (2027-01).cbr')
    assert helpers.rename_placeholder_dated_files('C1') == 1
    assert location(library, 'I7') == 'X 7 (2027-02).cbz'
    assert helpers.load_provisional_renames() == {}


def test_renamed_meanwhile_drops_the_entry_without_renaming(library):
    # control: Location no longer carries the estimate, nothing to correct
    add_issue(library, 'I8', '8', '2027-02-01', '2026-11-18', 'X 8 custom.cbz')
    touch(library, 'X 8 custom.cbz')
    helpers.register_provisional_rename('I8', 'X 8 (2027-01).cbz')
    assert helpers.rename_placeholder_dated_files('C1') == 0
    assert files(library) == ['X 8 custom.cbz']
    assert helpers.load_provisional_renames() == {}


def test_preview_rename_leaves_the_registry_alone(library, monkeypatch):
    add_issue(library, 'I6', '6', '0000-00-00', '2026-11-04', 'X 6 (2026-11).cbz')
    touch(library, 'X 6 (2026-11).cbz')
    helpers.register_provisional_rename('I6', 'X 6 (2026-11).cbz')
    monkeypatch.setattr(webserve, 'serve_template', lambda **kw: kw['resultlist'])
    result = webserve.WebInterface().previewRename(comicid='C1', file_format='$Series - $Issue ($monthname $Year)')
    assert result[0]['new'] == 'X - 6 (November 2026).cbz'
    assert helpers.load_provisional_renames() == {'I6': 'X 6 (2026-11).cbz'}
    assert files(library) == ['X 6 (2026-11).cbz']


def test_manual_rename_with_an_estimated_date_is_recorded(library):
    add_issue(library, 'I5', '5', '0000-00-00', '2026-10-28', 'X 5 (0000-00).cbz')
    touch(library, 'X 5 (0000-00).cbz', b'issue5')
    out = webserve.WebInterface().manualRename('C1')
    assert out == '{"status": "success"}'
    assert files(library) == ['X 5 (2026-10).cbz']
    assert helpers.load_provisional_renames() == {'I5': 'X 5 (2026-10).cbz'}


def test_manual_rename_with_a_cover_date_records_nothing(library):
    # control
    add_issue(library, 'I9', '9', '2026-09-01', '2026-07-01', 'X 9 (0000-00).cbz')
    touch(library, 'X 9 (0000-00).cbz')
    webserve.WebInterface().manualRename('C1')
    assert files(library) == ['X 9 (2026-09).cbz']
    assert helpers.load_provisional_renames() == {}


def test_real_rename_then_a_new_cover_date_does_not_loop(library):
    # control (scenario G): after the real rename the entry is gone, a later CV change renames nothing
    add_issue(library, 'I1', '1', '2026-12-01', '2026-10-14', 'X 1 (2026-11).cbz')
    touch(library, 'X 1 (2026-11).cbz')
    helpers.register_provisional_rename('I1', 'X 1 (2026-11).cbz')
    assert helpers.rename_placeholder_dated_files('C1') == 1
    library.execute("UPDATE issues SET IssueDate='2026-09-01' WHERE IssueID='I1'")
    assert helpers.rename_placeholder_dated_files('C1') == 0
    assert location(library, 'I1') == 'X 1 (2026-12).cbz'


def test_concurrent_registrations_are_all_kept(library):
    def register(prefix):
        for n in range(50):
            helpers.register_provisional_rename('%s%d' % (prefix, n), 'X %s%d.cbz' % (prefix, n))
    threads = [threading.Thread(target=register, args=(p,)) for p in ('A', 'B')]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    registry = helpers.load_provisional_renames()
    assert len(registry) == 100
    assert not [f for f in os.listdir(mylar.DATA_DIR) if f.endswith('.tmp')]
