"""Small fork bugs found during the cleanup review (R49): pack folder name and renaming other extensions."""
import os
import zipfile

import pytest

import mylar
from mylar import db, filers, getcomics


def _zip(path, member='Issue 001.cbz'):
    with zipfile.ZipFile(str(path), 'w') as zf:
        zf.writestr(member, b'x' * 100)


@pytest.mark.parametrize('filename, folder', [
    ('Xzip.zip', 'Xzip'),
    ('Batman.zip.Collection.zip', 'Batman.zip.Collection'),
    ('Batman 001-012 (2025).ZIP', 'Batman 001-012 (2025)'),
])
def test_zip_zip_strips_only_the_trailing_zip(lib, tmp_path, filename, folder):
    ddl = tmp_path / 'downloads'
    ddl.mkdir()
    mylar.CONFIG.DDL_LOCATION = str(ddl)
    dst = ddl / (filename[:-4] + '.zip')
    _zip(dst)
    gc = getcomics.GC.__new__(getcomics.GC)
    result = gc.zip_zip('1', str(dst), filename)
    assert result['success'] is True
    assert result['path'] == os.path.join(str(ddl), folder)
    assert os.path.isfile(os.path.join(str(ddl), folder, 'Issue 001.cbz'))


def _handler(lib):
    lib.add_series('C1', 'Batman', [], year='2025')
    lib.execute("INSERT INTO issues (IssueID, ComicName, Issue_Number, Status, ComicID, IssueDate, Int_IssueNumber)"
                " VALUES ('I5', 'Batman', '5', 'Wanted', 'C1', '2025-06-01', 5000)")
    fh = filers.FileHandlers.__new__(filers.FileHandlers)
    fh.myDB = db.DBConnection()
    fh.comicid = 'C1'
    fh.issueid = 'I5'
    fh.comic = {'ComicPublisher': 'DC Comics', 'ComicName': 'Batman', 'AlternateFileName': None,
                'ComicYear': '2025', 'ComicLocation': '/comics/Batman (2025)', 'ComicVersion': None,
                'Corrected_Type': None, 'Type': 'Print'}
    return fh


@pytest.mark.parametrize('ofilename, expected', [
    ('Batman 005.cbz', 'Batman 5 (2025).cbz'),
    ('Batman 005.CBR', 'Batman 5 (2025).cbr'),
    ('Batman 005.pdf', 'Batman 5 (2025).pdf'),
    ('Batman 005.epub', 'Batman 5 (2025).epub'),
])
def test_rename_file_keeps_any_extension(lib, ofilename, expected):
    result = _handler(lib).rename_file(ofilename, issue='5', file_format='$Series $Issue ($Year)')
    assert result['nfilename'] == expected
    assert result['destination_dir'] == os.path.join('/comics/Batman (2025)', expected)


@pytest.mark.parametrize('ofilename, expected', [
    ('Batman.005.cbz', 'Batman.005.cbz'),
    ('Batman.005.pdf', 'Batman.005.pdf'),
])
def test_rename_file_without_format_keeps_the_name(lib, ofilename, expected):
    result = _handler(lib).rename_file(ofilename, issue='5', file_format='')
    assert result['nfilename'] == expected
