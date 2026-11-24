"""The series page tries to fetch a missing cover at most once a day per series (R40).

comicDetails() used to call ComicVine (cv.getComic(..., 'image'), with its own wait) and
helpers.getImage on every view of a series without a cached cover. ComicVine allows 200 requests
an hour, shared with the Comics pipeline.
"""
import os

import pytest

import mylar
from mylar import helpers, webserve

DAY = 24 * 3600.0
EXTRA_COLUMNS = ['FilesUpdated TEXT', 'Have INT', 'Total INT', 'ForceContinuing INT', 'ComicImage TEXT',
                 'ComicImageURL TEXT', 'Description TEXT', 'DescriptionEdit TEXT', 'Collects TEXT',
                 'AgeRating TEXT']


@pytest.fixture
def page(lib, monkeypatch):
    for col in EXTRA_COLUMNS:
        lib.execute('ALTER TABLE comics ADD COLUMN %s' % col)
    now = {'t': 1800000000.0}
    monkeypatch.setattr(webserve.time, 'time', lambda: now['t'])
    monkeypatch.setattr(webserve, '_COVER_TRIED_AT', {}, raising=False)
    calls = {'cv': [], 'image': [], 'pages': []}

    def get_comic(comicid, kind):
        calls['cv'].append((comicid, kind))
        return {'image': 'https://comicvine.example/covers/%s.jpg' % comicid, 'image_alt': None}

    def get_image(comicid, url, **kwargs):
        calls['image'].append((comicid, url))
        return {'status': 'retry', 'coversize': 0}
    monkeypatch.setattr(mylar.cv, 'getComic', get_comic)
    monkeypatch.setattr(helpers, 'getImage', get_image)
    monkeypatch.setattr(mylar.getimage, 'load_image', lambda path, size: os.path.basename(path))
    monkeypatch.setattr(webserve, 'serve_template',
                        lambda templatename, **kw: calls['pages'].append(kw['comicConfig']['ComicImage']) or 'page')
    monkeypatch.setattr(mylar, 'COMICSORT', None, raising=False)
    monkeypatch.setattr(mylar, 'PROG_DIR', '/nonexistent', raising=False)
    calls['now'] = now
    return calls


def add_series(lib, comicid):
    lib.execute("INSERT INTO comics (ComicID, ComicName, ComicYear, Type, Status, Total, Have) "
                "VALUES (?, 'Batman', '2016', 'Print', 'Active', 10, 0)", (comicid,))


def view(comicid):
    assert webserve.WebInterface().comicDetails(comicid) == 'page'


def test_second_view_does_not_ask_comicvine_again(lib, page):
    add_series(lib, 'C1')
    view('C1')
    view('C1')
    assert page['cv'] == [('4050-C1', 'image')]
    assert len(page['image']) == 1
    # the page itself is shown both times, with the blank placeholder
    assert page['pages'] == ['data:image/gif;base64,blank.gif'] * 2


def test_next_try_after_a_day(lib, page):
    add_series(lib, 'C1')
    view('C1')
    page['now']['t'] += DAY - 60
    view('C1')
    assert len(page['cv']) == 1
    page['now']['t'] += 120
    view('C1')
    assert len(page['cv']) == 2


def test_the_wait_is_per_series(lib, page):
    add_series(lib, 'C1')
    add_series(lib, 'C2')
    view('C1')
    view('C2')
    view('C1')
    assert [c[0] for c in page['cv']] == ['4050-C1', '4050-C2']


# --- control (passes before the fix too) ---

def test_control_series_with_a_cached_cover_never_asks_comicvine(lib, page):
    add_series(lib, 'C1')
    with open(os.path.join(mylar.CONFIG.CACHE_DIR, 'C1.jpg'), 'wb') as f:
        f.write(b'jpg')
    view('C1')
    view('C1')
    assert page['cv'] == [] and page['image'] == []
    assert page['pages'] == ['data:image/webp;base64,C1.jpg'] * 2


def test_control_first_view_still_fetches_the_cover(lib, page):
    add_series(lib, 'C1')
    view('C1')
    assert page['cv'] == [('4050-C1', 'image')]
    assert page['image'] == [('C1', 'https://comicvine.example/covers/4050-C1.jpg')]
