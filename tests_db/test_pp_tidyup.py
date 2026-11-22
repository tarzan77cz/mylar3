"""Post-processing cleanup of the download folder after a move (review R19, decision Q15 a)."""
import pytest

import mylar
from mylar import PostProcessor


@pytest.fixture
def downloads(lib, tmp_path):
    ddl = tmp_path / 'downloads'
    for d in ('SABnzbd/incomplete', 'hunter-ddl/x'):
        (ddl / d).mkdir(parents=True)  # empty folders of other tools
    mylar.CONFIG.DDL_LOCATION = str(ddl)
    mylar.CONFIG.FILE_OPTS = 'move'
    mylar.CONFIG.IGNORE_SEARCH_WORDS = []
    return ddl


def pp(name, folder, issueid=None, ddl=True):
    return PostProcessor.PostProcessor(name, str(folder), issueid=issueid, ddl=ddl)


def foreign_dirs_kept(ddl):
    return (ddl / 'SABnzbd' / 'incomplete').is_dir() and (ddl / 'hunter-ddl' / 'x').is_dir()


def test_tidyup_single_ddl_keeps_foreign_empty_dirs(downloads):
    name = 'Batman 005 (2025)[__I5__].cbz'
    (downloads / name).write_bytes(b'x')  # copy mode would leave it; move removes it below
    p = pp(name, downloads / name, issueid='I5')
    p.tidyup(str(downloads), True, str(downloads), filename=name)
    assert foreign_dirs_kept(downloads)
    assert downloads.is_dir()
    assert not (downloads / name).exists()  # the item's own file still goes


def test_tidyup_single_ddl_in_an_empty_download_folder(downloads, tmp_path):
    for d in ('SABnzbd', 'hunter-ddl'):
        import shutil
        shutil.rmtree(str(downloads / d))
    name = 'Batman 005 (2025)[__I5__].cbz'
    p = pp(name, downloads / name, issueid='I5')
    p.tidyup(str(downloads), True, str(downloads), filename=name)
    assert downloads.is_dir()  # DDL_LOCATION itself is never removed


def test_tidyup_unpacked_pack_removes_only_its_folder(downloads):
    pack = downloads / 'Tomahawk 1-140'
    (pack / 'empty-sub').mkdir(parents=True)
    p = pp('Tomahawk 1-140', pack)
    p.tidyup(str(pack), True, str(pack), filename='Tomahawk 001 (1950).cbz')
    assert not pack.exists()
    assert foreign_dirs_kept(downloads)
    assert downloads.is_dir()


def test_tidyup_ddl_outside_the_download_folder_removes_no_directory(downloads, tmp_path):
    series = tmp_path / 'comics' / 'Batman (2025)'
    (series / 'empty-sub').mkdir(parents=True)
    name = 'Batman 005 (2025).cbz'
    p = pp(name, series / name, issueid='I5')
    p.tidyup(str(series), True, str(series), filename=name)
    assert (series / 'empty-sub').is_dir()


def test_tidyup_sab_job_folder_as_before(downloads):
    job = downloads / 'SABnzbd' / 'complete' / 'Batman.005'
    job.mkdir(parents=True)
    p = pp('Batman.005', job, ddl=False)
    p.tidyup(str(job), True, str(job), filename='Batman 005.cbz')
    assert not job.exists()
