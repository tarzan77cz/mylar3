"""Pixeldrain and MediaFire downloads are checked like GC-Main before they count as complete (R12, R22)."""
import json
import os

import pytest

import mylar
from mylar import helpers

from conftest import run_ddl_downloader
from fakes import install_router, make_zip, mediafire_route, pixeldrain_route

ZIP = make_zip()  # about 3 MB


@pytest.fixture
def ddl_dir(lib, tmp_path, monkeypatch):
    ddl = tmp_path / 'dl'
    ddl.mkdir()
    mylar.CONFIG.DDL_LOCATION = str(ddl)
    mylar.CONFIG.POST_PROCESSING = True
    mylar.CONFIG.SECURE_DIR = str(tmp_path)  # getcomics.GC() keeps its cookie file there (zip_zip)
    monkeypatch.setattr(mylar, 'GC_URL', 'https://getcomics.org', raising=False)
    monkeypatch.setattr(helpers.time, 'sleep', lambda *a: None)
    return ddl


def host_item(id_, link, link_type):
    """An item as auto-load rebuilds it from ddl_info (no search context)."""
    return {
        'link': link, 'mainlink': '', 'series': 'Batman #1', 'year': '2025', 'size': '3 MB',
        'comicid': 'C1', 'issueid': 'I1', 'oneoff': False, 'id': id_, 'link_type': link_type,
        'filename': None, 'tmp_filename': None, 'comicinfo': None, 'packinfo': None,
        'site': 'DDL(GetComics)', 'remote_filesize': 0, 'resume': None,
    }


def run_host(lib, id_, link, link_type):
    lib.execute("INSERT INTO ddl_info (ID, status, issueid, comicid, link, link_type, site) VALUES (?,?,?,?,?,?,?)",
                (id_, 'Queued', 'I1', 'C1', link, link_type, 'DDL(GetComics)'))
    run_ddl_downloader([host_item(id_, link, link_type)])
    row = lib.rows('SELECT status FROM ddl_info WHERE ID=?', (id_,))[0]
    pp = []
    while not mylar.PP_QUEUE.empty():
        pp.append(mylar.PP_QUEUE.get())
    return row['status'], pp


def files(ddl):
    return {f: os.path.getsize(os.path.join(str(ddl), f)) for f in os.listdir(str(ddl))}


def test_pixeldrain_error_status_is_a_host_failure(lib, ddl_dir, monkeypatch):
    body = json.dumps({'success': False, 'value': 'internal'}).encode()
    install_router(monkeypatch, pixeldrain_route(body, status=503, size=len(ZIP)))
    status, pp = run_host(lib, 'P1', 'https://pixeldrain.com/u/abc', 'GC-Pixel')
    assert status != 'Completed'
    assert pp == []
    assert files(ddl_dir) == {}


def test_pixeldrain_cut_off_body_is_incomplete(lib, ddl_dir, monkeypatch):
    install_router(monkeypatch, pixeldrain_route(ZIP, truncate_at=1048576))
    status, pp = run_host(lib, 'P2', 'https://pixeldrain.com/u/abc', 'GC-Pixel')
    assert status == 'Queued'  # incomplete: left for resume, not Completed and not Failed
    assert pp == []
    assert files(ddl_dir) == {'Batman 001 (2025)[__I1__].cbz': 1048576}


def test_pixeldrain_complete_zip_is_post_processed(lib, ddl_dir, monkeypatch):
    install_router(monkeypatch, pixeldrain_route(ZIP))
    status, pp = run_host(lib, 'P3', 'https://pixeldrain.com/u/abc', 'GC-Pixel')
    assert status == 'Completed'
    assert [(p['nzb_name'], p['issueid']) for p in pp] == [('Batman 001 (2025)[__I1__].cbz', 'I1')]
    assert files(ddl_dir) == {'Batman 001 (2025)[__I1__].cbz': len(ZIP)}


def test_pixeldrain_cut_off_pack_zip_is_not_unzipped(lib, ddl_dir, monkeypatch):
    install_router(monkeypatch, pixeldrain_route(ZIP, truncate_at=1048576, name='Batman 001-012 (2025).zip'))
    status, pp = run_host(lib, 'P4', 'https://pixeldrain.com/u/abc', 'GC-Pixel')
    assert status == 'Queued'
    assert pp == []
    assert files(ddl_dir) == {'Batman 001-012 (2025)[__I1__].zip': 1048576}


def test_mediafire_cut_off_body_is_incomplete(lib, ddl_dir, monkeypatch):
    install_router(monkeypatch, mediafire_route(ZIP, truncate_at=1048576))
    status, pp = run_host(lib, 'M1', 'https://download.mediafire.com/x/Batman.cbz', 'GC-Media')
    assert status == 'Queued'
    assert pp == []
    assert files(ddl_dir) == {'Batman 001 (2025)[__I1__].cbz': 1048576}


def test_mediafire_error_status_is_a_host_failure(lib, ddl_dir, monkeypatch):
    install_router(monkeypatch, mediafire_route(b'<html>busy</html>', status=503))
    status, pp = run_host(lib, 'M2', 'https://download.mediafire.com/x/Batman.cbz', 'GC-Media')
    assert status != 'Completed'
    assert pp == []
    assert files(ddl_dir) == {}


def test_mediafire_complete_zip_is_post_processed(lib, ddl_dir, monkeypatch):
    install_router(monkeypatch, mediafire_route(ZIP))
    status, pp = run_host(lib, 'M3', 'https://download.mediafire.com/x/Batman.cbz', 'GC-Media')
    assert status == 'Completed'
    assert [(p['nzb_name'], p['issueid']) for p in pp] == [('Batman 001 (2025)[__I1__].cbz', 'I1')]
