"""Local pull-list fallback when the provider is down (review R33). Temp DB, no network."""
import datetime
import re

import pytest

import mylar
from mylar import helpers, weeklypull

WEEKLY = ('CREATE TABLE weekly (SHIPDATE, PUBLISHER text, ISSUE text, COMIC VARCHAR(150), EXTRA text, STATUS text,'
          ' ComicID text, IssueID text, CV_Last_Update text, DynamicName text, weeknumber text, year text,'
          ' volume text, seriesyear text, annuallink text, format text, rowid INTEGER PRIMARY KEY)')
WEEK, YEAR = 47, 2026


@pytest.fixture
def pull(lib):
    lib.execute(WEEKLY)
    mylar.CONFIG.writeconfig = lambda values=None: None
    start = datetime.datetime.strptime(helpers.weekly_info(WEEK, YEAR)['startweek'], '%B %d, %Y')
    lib.day = start.strftime('%Y-%m-%d')
    lib.other_day = (start - datetime.timedelta(days=21)).strftime('%Y-%m-%d')
    for cid, name in (('C1', 'Batman'), ('C2', 'Saga')):
        lib.execute("INSERT INTO comics (ComicID, ComicName, ComicYear, ComicPublisher, Status)"
                    " VALUES (?, ?, '2025', 'DC', 'Active')", (cid, name))
    return lib


def dyn(name):
    info = mylar.filechecker.FileChecker().dynamic_replace(name)
    return re.sub(r'[\|\s]', '', info['mod_seriesname'].lower()).strip()


def add_issue(lib, iid, cid, name, num, release):
    lib.execute('INSERT INTO issues (IssueID, ComicID, ComicName, Issue_Number, ReleaseDate, IssueDate, Status)'
                " VALUES (?,?,?,?,?, '0000-00-00', 'Skipped')", (iid, cid, name, num, release))


def add_weekly(lib, iid, cid, name, num, shipdate, status, week=WEEK, year=YEAR):
    lib.execute('INSERT INTO weekly (SHIPDATE, PUBLISHER, ISSUE, COMIC, STATUS, ComicID, IssueID, DynamicName,'
                ' weeknumber, year) VALUES (?,?,?,?,?,?,?,?,?,?)',
                (shipdate, 'DC', num, name, status, cid, iid, dyn(name), str(week), str(year)))


def weekly(lib):
    return lib.rows('SELECT SHIPDATE, ISSUE, COMIC, STATUS, ComicID, IssueID, weeknumber, year FROM weekly'
                    ' ORDER BY rowid')


def test_fallback_keeps_the_provider_rows_and_adds_missing_issues(pull):
    # provider rows: one issue without a CV store date (Wanted thanks to the ship date), one with
    add_issue(pull, 'I1', 'C1', 'Batman', '1', '0000-00-00')
    add_weekly(pull, 'I1', 'C1', 'Batman', '1', pull.day, 'Wanted')
    add_issue(pull, 'I2', 'C1', 'Batman', '2', pull.day)
    add_weekly(pull, 'I2', 'C1', 'Batman', '2', pull.day, 'Snatched')
    add_weekly(pull, None, None, 'Unwatched Book', '5', pull.day, 'Skipped')
    add_issue(pull, 'I3', 'C2', 'Saga', '70', pull.day)  # only CV knows it
    before = weekly(pull)
    result = weeklypull.weekly_local_fallback(WEEK, YEAR)
    assert result['status'] == 'success'
    after = weekly(pull)
    assert after[:3] == before
    assert [(r['IssueID'], r['STATUS'], r['SHIPDATE'], r['weeknumber'], r['year']) for r in after[3:]] == [
        ('I3', 'Skipped', pull.day, str(WEEK), str(YEAR))]


def test_provider_row_without_issueid_is_not_duplicated(pull):
    add_issue(pull, 'I2', 'C1', 'Batman', '2', pull.day)
    add_weekly(pull, None, None, 'Batman', '2', pull.day, 'Skipped')
    before = weekly(pull)
    weeklypull.weekly_local_fallback(WEEK, YEAR)
    assert weekly(pull) == before


def test_same_issue_in_another_week_is_left_alone(pull):
    add_issue(pull, 'I2', 'C1', 'Batman', '2', pull.day)
    add_weekly(pull, 'I9', 'C1', 'Batman', '2', pull.other_day, 'Wanted', week=WEEK - 3)
    other = weekly(pull)
    weeklypull.weekly_local_fallback(WEEK, YEAR)
    after = weekly(pull)
    assert after[0] == other[0]
    assert [(r['IssueID'], r['weeknumber']) for r in after[1:]] == [('I2', str(WEEK))]


def test_empty_week_is_filled_as_before(pull):
    # control: passes before and after the fix
    add_issue(pull, 'I2', 'C1', 'Batman', '2', pull.day)
    add_issue(pull, 'I3', 'C2', 'Saga', '70', pull.day)
    result = weeklypull.weekly_local_fallback(WEEK, YEAR)
    assert result == {'status': 'success', 'count': 2, 'weeknumber': WEEK, 'year': YEAR}
    assert sorted((r['IssueID'], r['STATUS'], r['ISSUE']) for r in weekly(pull)) == [
        ('I2', 'Skipped', '2'), ('I3', 'Skipped', '70')]
