"""REJECTED_MATCHES keeps at most 50 matches per issue and drops matches not seen for 7 days (R40).

The cache lives only in memory and used to grow until a restart or a manual clear.
"""
import pytest

import mylar
from mylar import search_filer

DAY = 24 * 3600.0


@pytest.fixture
def clock(lib, monkeypatch):
    now = {'t': 1800000000.0}
    monkeypatch.setattr(search_filer.time, 'time', lambda: now['t'])
    monkeypatch.setattr(mylar, 'REJECTED_MATCHES', {}, raising=False)
    monkeypatch.setattr(search_filer, '_REJECTED_MATCHES_SWEPT_AT', 0.0, raising=False)
    return now


def add(issueid, n):
    link = 'https://getcomics.org/?p=%s' % n
    data = {'title': 'Batman %s' % n, 'link': link, 'nzbid': str(n), 'reason': 'Booktype mismatch',
            'relevance_score': 0.9, 'verified_data': {'nzbprov': 'DDL(GetComics)'}, 'initial_added': False}
    assert search_filer._add_or_update_rejected_match(issueid, link, str(n), data)


def ids(issueid):
    return [m['nzbid'] for m in mylar.REJECTED_MATCHES.get(issueid, [])]


def test_sixty_matches_keep_the_fifty_newest(clock):
    for n in range(60):
        clock['t'] += 60
        add('I1', n)
    assert ids('I1') == [str(n) for n in range(10, 60)]


def test_match_not_seen_for_seven_days_goes_at_the_next_add(clock):
    add('I1', 1)
    clock['t'] += 7 * DAY + 1
    add('I1', 2)
    assert ids('I1') == ['2']


def test_issue_with_only_old_matches_goes_when_another_issue_gets_one(clock):
    add('I1', 1)
    clock['t'] += 7 * DAY + 1
    add('I2', 2)
    assert 'I1' not in mylar.REJECTED_MATCHES
    assert ids('I2') == ['2']


# --- control (passes before the fix too) ---

def test_control_match_seen_again_stays(clock):
    add('I1', 1)
    clock['t'] += 6 * DAY
    add('I1', 1)  # the same post found again by a later search: updated, not added
    clock['t'] += 2 * DAY
    add('I1', 2)
    assert ids('I1') == ['1', '2']


def test_control_fresh_matches_under_the_cap_stay_as_they_are(clock):
    for n in range(5):
        clock['t'] += 60
        add('I1', n)
    clock['t'] += 6 * DAY
    add('I2', 9)
    assert ids('I1') == ['0', '1', '2', '3', '4']
    assert ids('I2') == ['9']


def test_control_update_only_does_not_add(clock):
    link = 'https://getcomics.org/?p=7'
    assert search_filer._add_or_update_rejected_match('I1', link, '7', {'title': 'x'}, update_only=True) is False
    assert ids('I1') == []
