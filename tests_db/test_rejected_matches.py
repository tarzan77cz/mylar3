"""Selecting a rejected match from the Upcoming dialog (review R23, R46)."""
import json

import pytest

import mylar
from mylar import search, search_filer, updater, webserve


@pytest.fixture
def selecting(lib, monkeypatch):
    lib.add_series('C1', 'Batman', [], year='2016')
    lib.execute("INSERT INTO issues (IssueID, ComicName, Issue_Number, Status, ComicID, IssueDate, Int_IssueNumber)"
                " VALUES ('I1', 'Batman', '5', 'Wanted', 'C1', '2020-05-01', 5000)")
    calls = []

    def searcher(*args, **kwargs):
        calls.append({'nzbname': args[1], 'comicinfo': args[2], 'links': args[3]})
        return {'nzbname': 'Batman 005', 'sent_to': 'DDL', 'nzbid': args[2][0].get('nzbid')}
    monkeypatch.setattr(search, 'searcher', searcher)
    monkeypatch.setattr(updater, 'foundsearch', lambda *a, **k: None)
    monkeypatch.setattr(search_filer, '_load_watch_context_for_issue', lambda IssueID: None)
    monkeypatch.setattr(mylar, 'REJECTED_MATCHES', {}, raising=False)
    return calls


def match(n, reason='Booktype mismatch', score=0.9, verified=True):
    link = 'https://getcomics.org/?p=%s' % n
    return {
        'title': 'Batman %s' % n, 'provider': 'DDL(GetComics)', 'link': link, 'nzbid': str(n),
        'reason': reason, 'relevance_score': score,
        'verified_data': {'nzbprov': 'DDL(GetComics)'} if verified else None,
        'entry': {} if verified else {'link': link, 'id': str(n), 'title': 'Batman %s' % n},
    }


def select(n=None, **kwargs):
    if n is not None:
        kwargs.update({'nzbid': str(n), 'link': 'https://getcomics.org/?p=%s' % n})
    return json.loads(webserve.WebInterface().select_rejected_match('I1', **kwargs))


def stored_ids():
    return [m['nzbid'] for m in mylar.REJECTED_MATCHES.get('I1', [])]


@pytest.mark.parametrize('verified', [True, False])
def test_select_rejected_match_removes_the_chosen_match(selecting, verified):
    hidden = match(1, reason='', verified=False)  # no reason and no verified data: never offered
    mylar.REJECTED_MATCHES['I1'] = [hidden, match(2, verified=verified), match(3, verified=verified)]
    result = select(3)
    assert result['status'] == 'success'
    assert len(selecting) == 1
    assert stored_ids() == ['1', '2']
    again = select(3)
    assert again['status'] == 'error'
    assert len(selecting) == 1  # searcher not called a second time


@pytest.mark.parametrize('verified', [True, False])
def test_select_when_every_match_is_offered(selecting, verified):
    mylar.REJECTED_MATCHES['I1'] = [match(2, verified=verified), match(3, verified=verified)]
    assert select(2)['status'] == 'success'
    assert stored_ids() == ['3']
    assert select(2)['status'] == 'error'
    assert len(selecting) == 1


def test_select_the_last_match_clears_the_issue(selecting):
    mylar.REJECTED_MATCHES['I1'] = [match(2)]
    assert select(2)['status'] == 'success'
    assert 'I1' not in mylar.REJECTED_MATCHES


def test_select_by_index_removes_that_match(selecting):
    mylar.REJECTED_MATCHES['I1'] = [match(1, reason='', verified=False), match(2, score=0.5), match(3, score=0.9)]
    result = select(match_index=0)  # sorted by relevance: match 3 first
    assert result['status'] == 'success'
    assert selecting[0]['comicinfo'][0]['nzbid'] == '3'
    assert stored_ids() == ['1', '2']


@pytest.mark.parametrize('verified', [True, False])
def test_select_passes_the_issue_date(selecting, verified):
    # R46: 'IssueDate' in row tests the values of a sqlite3.Row, not its column names
    mylar.REJECTED_MATCHES['I1'] = [match(2, verified=verified)]
    assert select(2)['status'] == 'success'
    assert selecting[0]['comicinfo'][0]['IssueDate'] == '2020-05-01'
