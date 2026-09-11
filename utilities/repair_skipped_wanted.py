#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""One-time repair: flip recent Skipped issues to Wanted using autowant rules."""

import argparse
import configparser
import datetime
import os
import re
import sqlite3
import sys


def load_settings(config_path):
    config = configparser.ConfigParser()
    config.read(config_path)
    general = config['General'] if config.has_section('General') else {}
    settings = {
        'autowant_all': general.getboolean('autowant_all', fallback=False),
        'autowant_upcoming': general.getboolean('autowant_upcoming', fallback=True),
    }
    try:
        settings['autowant_reeval_window'] = general.getint('autowant_reeval_window', fallback=8)
    except ValueError:
        settings['autowant_reeval_window'] = 8
    return settings


def issue_store_date_key(release_date, issue_date):
    if release_date not in (None, '', '0000-00-00'):
        dk = re.sub('-', '', release_date).strip()
    else:
        dk = re.sub('-', '', issue_date).strip()
    if dk in (None, '', '00000000'):
        return '00000000'
    return dk


def is_within_autowant_reeval_window(dk, weeks):
    if not dk or dk == '00000000':
        return False
    try:
        issue_date = datetime.datetime.strptime(dk, "%Y%m%d").date()
    except (TypeError, ValueError):
        return False
    if weeks < 0:
        weeks = 0
    cutoff = datetime.date.today() - datetime.timedelta(weeks=weeks)
    return issue_date >= cutoff


def resolve_autowant_status(release_date, issue_date, serieslast_updated, settings):
    dk = issue_store_date_key(release_date, issue_date)
    if dk == '00000000':
        return 'Skipped'
    if not is_within_autowant_reeval_window(dk, settings['autowant_reeval_window']):
        return 'Skipped'

    nowdate = datetime.datetime.now()
    now_week = datetime.datetime.strftime(nowdate, "%Y%U")
    datechk = datetime.datetime.strptime(dk, "%Y%m%d")
    issue_week = datetime.datetime.strftime(datechk, "%Y%U")

    if settings['autowant_all']:
        return 'Wanted'
    if serieslast_updated is None:
        return 'Skipped'
    if issue_week >= now_week and settings['autowant_upcoming']:
        return 'Wanted'
    if all([int(re.sub('-', '', serieslast_updated).strip()) < int(dk), settings['autowant_upcoming'] is True]):
        return 'Wanted'
    return 'Skipped'


def series_last_updated(last_updated):
    if last_updated is None:
        return None
    return datetime.datetime.strptime(last_updated, "%Y-%m-%d %H:%M:%S").strftime('%Y-%m-%d')


def find_candidates(connection):
    connection.row_factory = sqlite3.Row
    query = (
        "SELECT i.IssueID, i.ComicID, i.ComicName, i.Issue_Number, i.IssueDate, i.ReleaseDate, "
        "i.Status, i.Location, cm.Status AS SeriesStatus, cm.LastUpdated "
        "FROM issues i "
        "INNER JOIN comics cm ON cm.ComicID = i.ComicID "
        "WHERE i.Status = 'Skipped' "
        "AND cm.Status = 'Active' "
        "AND (i.Location IS NULL OR i.Location = '') "
        "AND i.ReleaseDate != '0000-00-00'"
    )
    return connection.execute(query).fetchall()


def repair(db_path, config_path, dry_run=True):
    settings = load_settings(config_path)
    connection = sqlite3.connect(db_path)
    candidates = find_candidates(connection)
    changed = []

    for row in candidates:
        new_status = resolve_autowant_status(
            row['ReleaseDate'],
            row['IssueDate'],
            series_last_updated(row['LastUpdated']),
            settings,
        )
        if new_status == 'Wanted':
            changed.append(row)
            if not dry_run:
                connection.execute(
                    "UPDATE issues SET Status = 'Wanted' WHERE IssueID = ?",
                    (row['IssueID'],),
                )

    if not dry_run and changed:
        connection.commit()
    connection.close()
    return changed


def main():
    parser = argparse.ArgumentParser(description='Repair recent Skipped issues that should be Wanted.')
    parser.add_argument('--db', default='/config/mylar/mylar.db', help='Path to mylar.db')
    parser.add_argument('--config', default='/config/mylar/config.ini', help='Path to config.ini')
    parser.add_argument('--apply', action='store_true', help='Apply changes (default is dry-run)')
    args = parser.parse_args()

    if not os.path.isfile(args.db):
        print('Database not found: %s' % args.db)
        sys.exit(1)
    if not os.path.isfile(args.config):
        print('Config not found: %s' % args.config)
        sys.exit(1)

    changed = repair(args.db, args.config, dry_run=not args.apply)
    mode = 'APPLY' if args.apply else 'DRY-RUN'
    print('[%s] %s issue(s) would be marked Wanted:' % (mode, len(changed)))
    for row in changed:
        print('  %s #%s (%s) release=%s issueid=%s' % (
            row['ComicName'],
            row['Issue_Number'],
            row['ComicID'],
            row['ReleaseDate'],
            row['IssueID'],
        ))

    if not args.apply and changed:
        print('Run again with --apply to update the database.')


if __name__ == '__main__':
    main()
