"""The series page of a series with a corrected series year (upstream code, found after review 2026-11-22).

comicDetails() put the corrected year into the comic row with comic['ComicYear'] = ..., but the
row is a sqlite3.Row, which takes no item assignment: TypeError, the page answered HTTP 500.
"""
import os

import pytest

import mylar
from mylar import webserve

EXTRA_COLUMNS = ['FilesUpdated TEXT', 'Have INT', 'Total INT', 'ForceContinuing INT', 'ComicImage TEXT',
                 'ComicImageURL TEXT', 'Description TEXT', 'DescriptionEdit TEXT', 'Collects TEXT',
                 'AgeRating TEXT']


@pytest.fixture
def page(lib, monkeypatch):
    for col in EXTRA_COLUMNS:
        lib.execute('ALTER TABLE comics ADD COLUMN %s' % col)
    shown = []
    with open(os.path.join(mylar.CONFIG.CACHE_DIR, 'C1.jpg'), 'wb') as f:
        f.write(b'jpg')  # cover cached: no ComicVine, no network
    monkeypatch.setattr(mylar.getimage, 'load_image', lambda path, size: os.path.basename(path))

    def serve(templatename, **kw):
        shown.append((kw['comicConfig']['corrected_seriesyear'], kw['comic']['ComicYear'], kw['comic']['ComicName']))
        return 'page'
    monkeypatch.setattr(webserve, 'serve_template', serve)
    monkeypatch.setattr(mylar, 'COMICSORT', None, raising=False)
    return shown


def add_series(lib, corrected):
    lib.execute("INSERT INTO comics (ComicID, ComicName, ComicYear, Corrected_SeriesYear, Type, Status, Total, Have)"
                " VALUES ('C1', 'Batman', '2016', ?, 'Print', 'Active', 10, 0)", (corrected,))


def test_series_with_a_different_corrected_year_shows_the_page(lib, page):
    add_series(lib, '2017')
    assert webserve.WebInterface().comicDetails('C1') == 'page'
    assert page == [('2017', '2017', 'Batman')]
    # the page only shows the corrected year, the database keeps both
    assert lib.rows("SELECT ComicYear, Corrected_SeriesYear FROM comics") == [
        {'ComicYear': '2016', 'Corrected_SeriesYear': '2017'}]


@pytest.mark.parametrize('corrected', [None, '', 'None', '2016'])
def test_control_series_without_a_different_corrected_year(lib, page, corrected):
    add_series(lib, corrected)
    assert webserve.WebInterface().comicDetails('C1') == 'page'
    assert page == [('2016', '2016', 'Batman')]
