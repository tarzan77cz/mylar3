"""Series start year from the issue cover dates (review R31). ComicVine is faked, no network."""
import datetime

import pytest

import mylar
from mylar import cv, helpers, importer

from cvxml import issue, response


@pytest.fixture
def cvonly(lib):
    mylar.CONFIG.CV_ONLY = True
    return lib


def test_firstdate_is_the_earliest_cover_date_of_a_series(cvonly):
    res, firstdate = cv.GetIssuesInfo('111', response([
        issue(2, '2', '2018-07-01', '2018-05-09'),
        issue(1, '1', '2018-06-01', '2018-04-11'),
    ]))
    assert firstdate == '2018-06-01'
    assert [r['Issue_ID'] for r in res] == ['2', '1']


def test_firstdate_ignores_issues_without_a_cover_date(cvonly):
    # 0000-00-00 sorts before any real date but must not become the series start
    res, firstdate = cv.GetIssuesInfo('111', response([
        issue(1, '1', '0000-00-00'),
        issue(2, '2', '2019-03-01'),
    ]))
    assert firstdate == '2019-03-01'


def test_firstdate_stays_2099_without_any_date(cvonly):
    # control: passes before and after the fix
    res, firstdate = cv.GetIssuesInfo('111', response([issue(1, '1', '0000-00-00'), issue(2, '2', None)]))
    assert firstdate == '2099-00-00'
    assert len(res) == 2


def test_getcomic_issue_reports_the_earliest_cover_date(cvonly, monkeypatch):
    monkeypatch.setattr(cv, 'pulldetails', lambda *a, **k: response([
        issue(1, '1', '2018-06-01'), issue(2, '2', '2018-07-01')]))
    issued = cv.getComic('111', 'issue')
    assert issued['firstdate'] == '2018-06-01'


class _Stop(Exception):
    pass


def _series_year(lib, monkeypatch, issues):
    """Run addComictoDB for a new series whose CV volume has no start year; return the ComicYear it picks."""
    lib.execute('CREATE TABLE weekly (ComicID TEXT, IssueID TEXT, SHIPDATE TEXT)')
    monkeypatch.setattr(helpers, 'ComicSort', lambda *a, **k: None)
    real_getcomic = cv.getComic
    comic = {'ComicName': 'Old Series', 'ComicYear': '0000', 'FirstIssueID': '1', 'ComicURL': 'u',
             'Type': 'Print', 'ComicVersion': 'None', 'incorrect_volume': None, 'ComicIssues': str(len(issues)),
             'ComicPublisher': 'P', 'PublisherImprint': None}

    def fake_getcomic(comicid, rtype, *a, **k):
        if rtype == 'comic':
            return dict(comic)
        if rtype == 'firstissue':
            return '0000'  # first issue without a cover date
        return real_getcomic(comicid, rtype, *a, **k)
    monkeypatch.setattr(cv, 'getComic', fake_getcomic)
    monkeypatch.setattr(cv, 'pulldetails', lambda *a, **k: response(issues))

    picked = {}

    class Folder(object):
        def __init__(self, comic=None, **k):
            picked['year'] = comic['ComicYear']
            raise _Stop()
    monkeypatch.setattr(importer.filers, 'FileHandlers', Folder)
    with pytest.raises(_Stop):
        importer.addComictoDB('111')
    return str(picked['year'])


def test_series_without_cv_start_year_takes_the_year_of_its_first_issue(cvonly, monkeypatch):
    assert _series_year(cvonly, monkeypatch, [issue(1, '1', '2018-06-01'), issue(2, '2', '2018-07-01')]) == '2018'


def test_series_without_any_date_still_falls_back_to_the_current_year(cvonly, monkeypatch):
    # control: passes before and after the fix
    year = _series_year(cvonly, monkeypatch, [issue(1, '1', '0000-00-00')])
    assert year == str(datetime.datetime.now().year)
