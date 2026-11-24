"""SQLite layer: a write lost after the last retry is logged, upsert runs under one lock (R37).

No schema change: the tables still have no UNIQUE key, so upsert itself must not let two
threads both decide that a new key needs an INSERT.
"""
import sqlite3
import threading

import pytest

import mylar
from mylar import db


class Recorder(object):
    def __init__(self):
        self.lines = []

    def __call__(self, msg, *a, **k):
        self.lines.append(str(msg))


@pytest.fixture
def logs(lib, monkeypatch):
    rec = {'error': Recorder(), 'warn': Recorder()}
    monkeypatch.setattr(db.logger, 'error', rec['error'])
    monkeypatch.setattr(db.logger, 'warn', rec['warn'])
    monkeypatch.setattr(db.time, 'sleep', lambda *a: None)
    return rec


class LockedConnection(object):
    """A connection on which every statement fails with 'database is locked'."""
    total_changes = 0

    def execute(self, *a, **k):
        raise sqlite3.OperationalError('database is locked')

    executemany = execute

    def cursor(self):
        return self

    def commit(self):
        pass


def locked_db():
    myDB = db.DBConnection()
    myDB.connection = LockedConnection()
    return myDB


def test_lost_write_is_an_error_with_the_query_and_no_values(lib, logs):
    result = locked_db().action('UPDATE issues SET Status=? WHERE IssueID=?', ['Downloaded', 'SECRET-1'])
    assert result is None
    assert len(logs['warn'].lines) >= 5  # every attempt still warns as before
    errors = logs['error'].lines
    assert len(errors) == 1
    assert 'UPDATE issues SET Status=? WHERE IssueID=?' in errors[0]
    assert all('SECRET-1' not in line and 'Downloaded' not in line for line in errors + logs['warn'].lines)


def test_lost_read_is_an_error_with_the_query_and_no_values(lib, logs):
    result = locked_db().fetch('SELECT * FROM issues WHERE IssueID=?', ['SECRET-2'])
    assert result is None
    errors = logs['error'].lines
    assert len(errors) == 1
    assert 'SELECT * FROM issues WHERE IssueID=?' in errors[0]
    assert all('SECRET-2' not in line for line in errors + logs['warn'].lines)


def test_lost_upsert_names_the_table(lib, logs):
    locked_db().upsert('ddl_info', {'status': 'Completed'}, {'id': 'SECRET-3'})
    errors = logs['error'].lines
    assert errors and all('ddl_info' in line for line in errors)
    assert all('SECRET-3' not in line and 'Completed' not in line for line in errors + logs['warn'].lines)


def test_lock_can_be_taken_again_by_the_same_thread(lib):
    assert db.db_lock.acquire(timeout=1)
    try:
        assert db.db_lock.acquire(timeout=1), 'db_lock is not re-entrant: upsert would block itself'
        db.db_lock.release()
    finally:
        db.db_lock.release()


def test_two_upserts_of_the_same_new_issue_make_one_row(lib, monkeypatch):
    """Thread A is held between its UPDATE (no row yet) and its INSERT while thread B upserts too."""
    between = threading.Event()
    go_on = threading.Event()
    b_trying = threading.Event()
    b_done = threading.Event()
    real_action = db.DBConnection.action

    def action(self, query, args=None, executemany=False):
        result = real_action(self, query, args, executemany)
        if threading.current_thread().name == 'upsert-A' and query.startswith('UPDATE'):
            between.set()
            assert go_on.wait(10)
        return result
    monkeypatch.setattr(db.DBConnection, 'action', action)

    class SpyLock(object):
        """db_lock as it is, telling when thread B asks for it."""
        def __init__(self, inner):
            self.inner = inner

        def __enter__(self):
            if threading.current_thread().name == 'upsert-B':
                b_trying.set()
            self.inner.acquire()
            return self

        def __exit__(self, *exc):
            self.inner.release()
            return False

        def acquire(self, *a, **k):
            return self.inner.acquire(*a, **k)

        def release(self):
            self.inner.release()
    monkeypatch.setattr(db, 'db_lock', SpyLock(db.db_lock))

    def upsert(status, done=None):
        db.DBConnection().upsert('issues', {'Status': status, 'ComicID': 'C1'}, {'IssueID': 'NEW1'})
        if done is not None:
            done.set()

    a = threading.Thread(target=upsert, args=('Snatched',), name='upsert-A')
    b = threading.Thread(target=upsert, args=('Wanted', b_done), name='upsert-B')
    a.start()
    try:
        assert between.wait(10)
        b.start()
        assert b_trying.wait(10)
        # Without one lock over UPDATE and INSERT, B runs its whole upsert now (UPDATE finds no
        # row, so it INSERTs). With it, B waits for A. Either way A goes on only after this.
        b_done.wait(0.5)
    finally:
        go_on.set()
        a.join(10)
        b.join(10)
    rows = lib.rows("SELECT IssueID, Status FROM issues WHERE IssueID='NEW1'")
    assert len(rows) == 1, rows
    assert rows[0]['Status'] == 'Wanted'  # A inserted, B then updated the same row


class PartlyLocked(object):
    """A real connection on which the statements starting with one of `locked` fail with 'database is locked'."""

    def __init__(self, con, locked):
        self.con = con
        self.locked = tuple(locked)

    def execute(self, query, *args):
        if query.lstrip().upper().startswith(self.locked):
            raise sqlite3.OperationalError('database is locked')
        return self.con.execute(query, *args)

    def cursor(self):
        return self

    def commit(self):
        self.con.commit()

    @property
    def total_changes(self):
        return self.con.total_changes


def partly_locked_db(*locked):
    myDB = db.DBConnection()
    myDB.connection = PartlyLocked(myDB.connection, locked)
    return myDB


def test_lost_update_of_an_existing_row_does_not_add_a_second_row(lib, logs):
    lib.execute("INSERT INTO issues (IssueID, Status, ComicID, Issue_Number) VALUES ('I1', 'Wanted', 'C1', '1')")
    partly_locked_db('UPDATE').upsert('issues', {'Status': 'Downloaded'}, {'IssueID': 'I1'})
    # the update is lost (logged), but no half row with only IssueID and Status appears
    assert lib.rows("SELECT IssueID, Status, ComicID FROM issues") == [
        {'IssueID': 'I1', 'Status': 'Wanted', 'ComicID': 'C1'}]
    assert any('issues' in line for line in logs['error'].lines)
    assert all('Downloaded' not in line for line in logs['error'].lines)


def test_lost_update_and_unreadable_row_does_not_insert(lib, logs):
    lib.execute("INSERT INTO issues (IssueID, Status, ComicID) VALUES ('I1', 'Wanted', 'C1')")
    partly_locked_db('UPDATE', 'SELECT').upsert('issues', {'Status': 'Downloaded'}, {'IssueID': 'I1'})
    assert lib.rows("SELECT IssueID, Status FROM issues") == [{'IssueID': 'I1', 'Status': 'Wanted'}]


def test_lost_update_of_a_unique_row_does_not_raise(lib, logs):
    lib.execute("INSERT INTO ddl_info (ID, status) VALUES ('D1', 'Downloading')")
    partly_locked_db('UPDATE').upsert('ddl_info', {'status': 'Completed'}, {'id': 'D1'})
    assert lib.rows("SELECT ID, status FROM ddl_info") == [{'ID': 'D1', 'status': 'Downloading'}]


# --- control (passes before the fix too) ---

def test_control_lost_update_of_a_new_key_still_inserts(lib, logs):
    partly_locked_db('UPDATE').upsert('nzblog', {'NZBName': 'Batman 005', 'ID': '200'},
                                      {'IssueID': 'I5', 'Provider': 'DDL(GetComics)'})
    assert lib.rows("SELECT IssueID, PROVIDER, ID FROM nzblog") == [
        {'IssueID': 'I5', 'PROVIDER': 'DDL(GetComics)', 'ID': '200'}]


def test_control_upsert_inserts_a_new_key_and_updates_an_existing_one(lib):
    myDB = db.DBConnection()
    myDB.upsert('ddl_info', {'status': 'Queued', 'series': 'Batman'}, {'id': 'D1'})
    assert lib.rows("SELECT ID, status, series FROM ddl_info") == [{'ID': 'D1', 'status': 'Queued', 'series': 'Batman'}]
    myDB.upsert('ddl_info', {'status': 'Completed'}, {'id': 'D1'})
    assert lib.rows("SELECT ID, status, series FROM ddl_info") == [{'ID': 'D1', 'status': 'Completed', 'series': 'Batman'}]


def test_control_action_and_select_work_as_before(lib, logs):
    myDB = db.DBConnection()
    myDB.action("INSERT INTO failed (ID, Status) VALUES (?, ?)", ['F1', 'Failed'])
    assert [r['ID'] for r in myDB.select('SELECT ID FROM failed')] == ['F1']
    assert myDB.selectone('SELECT ID FROM failed WHERE ID=?', ['F1']).fetchone()['ID'] == 'F1'
    assert logs['error'].lines == []


def test_control_other_database_errors_still_raise(lib, logs):
    with pytest.raises(sqlite3.OperationalError):
        db.DBConnection().action('UPDATE no_such_table SET x=1')
