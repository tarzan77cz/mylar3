"""API commands that crashed on a broken % format or a wrong global (review R45). No network.

The comics-nzb-hunter client (``comics_nzb/mylar_client.py``, ``_get``) reads the body of
``refreshComic``: HTTP 200 with JSON ``success: true`` must reach it after the refresh is queued.
"""
import json
import queue

import pytest

import mylar
from mylar import api


@pytest.fixture
def refreshes(lib, monkeypatch):
    """Stub importer.refresh_thread and give mylar a fresh REFRESH_QUEUE."""
    calls = []
    monkeypatch.setattr(mylar, 'REFRESH_QUEUE', queue.Queue(), raising=False)
    monkeypatch.setattr(api.importer, 'refresh_thread', lambda watch: calls.append(watch))
    return calls


def call(cmd, **kwargs):
    """Run one command the way Api.fetchData does after checkParams said OK."""
    a = api.Api()
    a.data = 'OK'
    a.cmd = cmd
    a.kwargs = kwargs
    return a, a.fetchData()


def test_refresh_comic_answers_success_after_queueing_one_series(lib, refreshes):
    lib.add_series('C1', 'Batman', [1])
    a, body = call('refreshComic', id='C1')
    assert [w['comicid'] for w in refreshes[0]] == ['C1']
    resp = json.loads(body)
    assert resp['success'] is True
    assert resp['data'] == 'Refresh successfully submitted for ComicID C1.'


def test_refresh_comic_answers_success_for_several_series(lib, refreshes):
    lib.add_series('C1', 'Batman', [1])
    lib.add_series('C2', 'Robin', [1])
    a, body = call('refreshComic', id='C1,C2')
    assert [w['comicid'] for w in refreshes[0]] == ['C1', 'C2']
    resp = json.loads(body)
    assert resp['success'] is True
    assert resp['data'].startswith('Refresh successfully submitted for 2 items')


def test_refresh_comic_reports_the_queue_size_when_several_are_already_queued(lib, refreshes):
    # The check compares the bare ComicID with the queue items; put them in as plain IDs.
    lib.add_series('C1', 'Batman', [1])
    lib.add_series('C2', 'Robin', [1])
    for x in ('C1', 'C2', 'C9'):
        mylar.REFRESH_QUEUE.put(x)
    a, body = call('refreshComic', id='C1,C2')
    resp = json.loads(body)
    assert resp['success'] is True
    assert resp['data'].endswith('in a queue of 3 items.')
    assert refreshes == []


def test_refresh_comic_with_unknown_id_is_a_failure(lib, refreshes):
    # control: unchanged
    a, body = call('refreshComic', id='C404')
    resp = json.loads(body)
    assert resp['success'] is False
    assert 'C404' in resp['error']['message']
    assert refreshes == []


def test_refresh_comic_response_passes_the_hunter_client_check(lib, refreshes):
    # mylar_client._get: status < 400, body not empty and not HTML, JSON without success False.
    lib.add_series('C1', 'Batman', [1])
    a, body = call('refreshComic', id='4050-C1')
    text = body.strip()
    assert text and not text.startswith('<!')
    data = json.loads(text)
    assert isinstance(data, dict) and data.get('success') is not False


def test_change_book_type_reports_the_database_error(lib, monkeypatch):
    lib.add_series('C1', 'Batman', [1])

    def boom(self, table, values, keys):
        raise RuntimeError('database is locked')
    monkeypatch.setattr(api.db.DBConnection, 'upsert', boom)
    a, body = call('changeBookType', id='C1', booktype='TPB')
    resp = json.loads(body)
    assert resp['success'] is False
    assert resp['error']['message'] == '[C1] Unable to update Booktype for ComicID: C1. Error returned: database is locked'


@pytest.mark.parametrize('ptype, existing', [
    ('newznab', 'EXTRA_NEWZNABS'),
    ('torznab', 'EXTRA_TORZNABS'),
])
def test_add_provider_with_the_same_details_stops_at_the_name_check(lib, monkeypatch, ptype, existing):
    # control: the stored tuple starts with the provider name, so identical details always hit
    # "already exists" first and the "[%]" message after it (api.py, addProvider) is never reached
    monkeypatch.setattr(mylar, 'PROVIDER_START_ID', 7, raising=False)
    line = ('Indexer', 'https://idx.example', '1', 'k', '#7030' if ptype == 'newznab' else '7030', '1', 8)
    setattr(mylar.CONFIG, existing, [line])
    a, body = call('addProvider', providertype=ptype, name='Indexer', host='https://idx.example',
                   prov_apikey='k', categories='7030', enabled='1')
    resp = json.loads(body)
    assert resp['success'] is False
    assert resp['error']['message'] == 'Indexer already exists as a provider.'


def test_get_logs_returns_the_log_list(lib, monkeypatch):
    rows = [('2026-11-24 10:00:00', 'second', 'INFO', 'MainThread'),
            ('2026-11-24 09:59:59', 'first', 'DEBUG', 'MainThread')]
    monkeypatch.setattr(mylar, 'LOGLIST', list(rows), raising=False)
    a, body = call('getLogs')
    assert json.loads(body) == [list(r) for r in rows]


def test_clear_logs_empties_the_log_list(lib, monkeypatch):
    monkeypatch.setattr(mylar, 'LOGLIST', [('t', 'm', 'INFO', 'x')], raising=False)
    a, body = call('clearLogs')
    assert mylar.LOGLIST == []
    assert body == 'Cleared log'
