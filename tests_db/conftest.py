"""Tests that need the real ``mylar`` package (helpers, db) on a temporary SQLite DB.

tests/conftest.py replaces ``mylar`` with a stub package, so these tests cannot run in the
same process. Run them with a second pytest command on this folder (see CLAUDE.md).
No network, no live database: ``mylar.DATA_DIR`` points at a temp folder per test.
"""
import os
import queue
import sqlite3
import sys

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [REPO, os.path.join(REPO, 'lib')]

import mylar  # noqa: E402
from mylar import helpers  # noqa: E402

SCHEMA = [
    'CREATE TABLE comics (ComicID TEXT UNIQUE, ComicName TEXT, ComicYear TEXT, Type TEXT, Corrected_Type TEXT)',
    'CREATE TABLE issues (IssueID TEXT, ComicName TEXT, Issue_Number TEXT, Status TEXT, ComicID TEXT,'
    ' IssueDate TEXT, Int_IssueNumber INT)',
    'CREATE TABLE annuals (IssueID TEXT, Issue_Number TEXT, Status TEXT, ComicID TEXT, Int_IssueNumber INT,'
    ' ComicName TEXT, Deleted INT DEFAULT 0)',
    'CREATE TABLE nzblog (IssueID TEXT, NZBName TEXT, SARC TEXT, PROVIDER TEXT, ID TEXT, AltNZBName TEXT, OneOff TEXT)',
    'CREATE TABLE failed (ID TEXT, Status TEXT, ComicID TEXT, IssueID TEXT, Provider TEXT, ComicName TEXT,'
    ' Issue_Number TEXT, NZBName TEXT, DateFailed TEXT)',
    'CREATE TABLE ddl_info (ID TEXT UNIQUE, series TEXT, year TEXT, filename TEXT, size TEXT, issueid TEXT,'
    ' comicid TEXT, link TEXT, status TEXT, remote_filesize TEXT, updated_date TEXT, mainlink TEXT, issues TEXT,'
    ' site TEXT, submit_date TEXT, pack INTEGER, link_type TEXT, tmp_filename TEXT)',
]


class _Config(object):
    ZERO_LEVEL = False
    ZERO_LEVEL_N = 'none'
    POST_PROCESSING = False
    DDL_LOCATION = None
    FAILED_DOWNLOAD_HANDLING = True

    def __init__(self, cache_dir):
        self.CACHE_DIR = cache_dir

    def __getattr__(self, name):
        return None


class Library(object):
    """A temp mylar.db with one series and helpers to read it back."""

    def __init__(self, path):
        self.path = path

    def execute(self, sql, args=()):
        con = sqlite3.connect(self.path)
        try:
            con.execute(sql, args)
            con.commit()
        finally:
            con.close()

    def rows(self, sql, args=()):
        con = sqlite3.connect(self.path)
        con.row_factory = sqlite3.Row
        try:
            return [dict(r) for r in con.execute(sql, args).fetchall()]
        finally:
            con.close()

    def add_series(self, comicid, name, numbers, status='Wanted', year='1950'):
        self.execute('INSERT INTO comics (ComicID, ComicName, ComicYear, Type) VALUES (?,?,?,?)',
                     (comicid, name, year, 'Print'))
        for n in numbers:
            self.add_issue(comicid, n, status)

    def add_issue(self, comicid, number, status='Wanted', issueid=None):
        self.execute(
            'INSERT INTO issues (IssueID, ComicName, Issue_Number, Status, ComicID, Int_IssueNumber)'
            ' VALUES (?,?,?,?,?,?)',
            (issueid or 'I%s' % number, 'X', str(number), status, comicid,
             helpers.issue_number_parser(str(number)).asInt))

    def add_annual(self, comicid, number, status='Wanted', issueid=None):
        self.execute(
            'INSERT INTO annuals (IssueID, Issue_Number, Status, ComicID, Int_IssueNumber, Deleted)'
            ' VALUES (?,?,?,?,?,0)',
            (issueid or 'A%s' % number, str(number), status, comicid,
             helpers.issue_number_parser(str(number)).asInt))

    def set_status(self, issueids, status):
        for x in issueids:
            self.execute('UPDATE issues SET Status=? WHERE IssueID=?', (status, x))
            self.execute('UPDATE annuals SET Status=? WHERE IssueID=?', (status, x))

    def status(self, issueid):
        rows = self.rows('SELECT Status FROM issues WHERE IssueID=?', (issueid,))
        if not rows:
            rows = self.rows('SELECT Status FROM annuals WHERE IssueID=?', (issueid,))
        return rows[0]['Status'] if rows else None

    def statuses(self, issueids):
        return set(self.status(x) for x in issueids)


@pytest.fixture
def lib(tmp_path, monkeypatch):
    path = str(tmp_path / 'mylar.db')
    con = sqlite3.connect(path)
    for sql in SCHEMA:
        con.execute(sql)
    con.commit()
    con.close()
    monkeypatch.setattr(mylar, 'DATA_DIR', str(tmp_path), raising=False)
    monkeypatch.setattr(mylar, 'CONFIG', _Config(str(tmp_path)), raising=False)
    monkeypatch.setattr(mylar, 'PACK_ISSUEIDS_DONT_QUEUE', {}, raising=False)
    monkeypatch.setattr(mylar, 'DDL_QUEUED', [], raising=False)
    monkeypatch.setattr(mylar, 'DDL_LOCK', False, raising=False)
    monkeypatch.setattr(mylar, 'GLOBAL_MESSAGES', None, raising=False)
    monkeypatch.setattr(mylar, 'PP_QUEUE', queue.Queue(), raising=False)
    monkeypatch.setattr(mylar, 'PP_DDL_IDS', set(), raising=False)
    return Library(path)


def run_ddl_downloader(items):
    """Run the real ddl_downloader loop on ``items`` and stop it with 'exit'."""
    q = queue.Queue()
    for item in items:
        q.put(item)
    q.put('exit')
    helpers.ddl_downloader(q)
