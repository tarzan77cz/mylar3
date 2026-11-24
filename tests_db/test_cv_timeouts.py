"""ComicVine and pull-list requests carry a timeout and a timeout ends like any other network error (review R45).

No network: requests.get is replaced, the CV rate-limit sleep is skipped.
"""
import pytest
import requests

import mylar
from mylar import cv, locg, mb


class _Resp(object):
    def __init__(self, content=b'', status=200):
        self.content = content
        self.status_code = status
        self.headers = {}


@pytest.fixture
def http(lib, monkeypatch):
    """Record requests.get calls; ``plan`` is a list of exceptions or responses handed out in order."""
    state = {'calls': [], 'plan': []}

    def get(url, *args, **kwargs):
        state['calls'].append(kwargs)
        nxt = state['plan'].pop(0)
        if isinstance(nxt, Exception):
            raise nxt
        return nxt
    monkeypatch.setattr(requests, 'get', get)
    monkeypatch.setattr(cv.time, 'sleep', lambda s: None)
    monkeypatch.setattr(mb.time, 'sleep', lambda s: None)
    monkeypatch.setattr(mylar, 'CVURL', 'https://cv.invalid/api/', raising=False)
    monkeypatch.setattr(mylar, 'CV_HEADERS', {'User-Agent': 'test'}, raising=False)
    monkeypatch.setattr(mylar, 'BACKENDSTATUS_CV', 'up', raising=False)
    monkeypatch.setattr(mylar, 'BACKENDSTATUS_WS', 'up', raising=False)
    monkeypatch.setattr(mylar, 'USER_AGENT', 'Mylar3/1.0 (test)', raising=False)
    mylar.CONFIG.COMICVINE_API = 'x' * 40
    mylar.CONFIG.CV_VERIFY = True
    return state


def _has_timeout(kwargs):
    t = kwargs.get('timeout')
    return t is not None and t == mylar.CV_TIMEOUT


VOLUME = (b'<?xml version="1.0"?><response><number_of_total_results>1</number_of_total_results>'
          b'<results><name>Batman</name></results></response>')


def test_pulldetails_passes_a_timeout_and_a_timeout_is_handled_like_a_network_error(http):
    http['plan'] = [requests.exceptions.ReadTimeout('read timed out')]
    assert cv.pulldetails('123', 'comic') is None
    assert _has_timeout(http['calls'][0])
    assert mylar.BACKENDSTATUS_CV == 'down'


def test_the_next_good_answer_puts_comic_vine_back_up(http):
    http['plan'] = [requests.exceptions.ConnectTimeout('connect timed out'), _Resp(VOLUME)]
    assert cv.pulldetails('123', 'comic') is None
    assert mylar.BACKENDSTATUS_CV == 'down'
    dom = cv.pulldetails('123', 'comic')
    assert dom is not None and dom.getElementsByTagName('name')[0].firstChild.wholeText == 'Batman'
    assert mylar.BACKENDSTATUS_CV == 'up'
    assert all(_has_timeout(c) for c in http['calls'])


def test_db_updater_timeout_returns_false_as_before(http):
    http['plan'] = [requests.exceptions.ReadTimeout('read timed out')]
    assert cv.pulldetails(None, 'db_updater', dateinfo={'start_date': 'a', 'end_date': 'b'}) is False
    assert _has_timeout(http['calls'][0])


def test_series_lookup_after_a_timeout_returns_nothing_so_the_refresh_ends_incomplete(http):
    # importer.addComictoDB treats a falsy getComic(..., 'comic') as {'status': 'incomplete'}
    http['plan'] = [requests.exceptions.ReadTimeout('read timed out')]
    assert cv.getComic('123', 'comic', series=True) is None
    assert _has_timeout(http['calls'][0])


def test_issue_list_after_a_timeout_returns_false(http):
    mylar.CONFIG.CV_ONLY = True
    http['plan'] = [requests.exceptions.ReadTimeout('read timed out')]
    assert cv.getComic('123', 'issue') is False
    assert _has_timeout(http['calls'][0])


def test_series_search_passes_a_timeout_and_returns_nothing_on_timeout(http):
    http['plan'] = [requests.exceptions.ReadTimeout('read timed out')]
    assert mb.pullsearch('x' * 40, ['batman'], 0, 'volume') is None
    assert _has_timeout(http['calls'][0])


def test_story_arc_lookup_passes_a_timeout_and_returns_nothing_on_timeout(http, monkeypatch):
    monkeypatch.setattr(mb, 'listStoryArcs', lambda: [])
    http['plan'] = [requests.exceptions.ReadTimeout('read timed out')]
    assert mb.storyarcinfo('56789') is None
    assert _has_timeout(http['calls'][0])


def test_pull_list_passes_a_timeout_and_a_timeout_fails_the_week(http, monkeypatch):
    monkeypatch.setattr(locg, '_locg_backoff_until', None)
    mylar.CONFIG.RELEASE_PROVIDER_URL = 'https://pull.invalid'
    http['plan'] = [requests.exceptions.ReadTimeout('read timed out')]
    assert locg.locg(weeknumber='47', year='2026') == {'status': 'failure'}
    assert _has_timeout(http['calls'][0])
    assert mylar.BACKENDSTATUS_WS == 'down'
