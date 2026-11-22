"""Renaming a series folder from the placeholder year 2099 (review R30). Real folders in tmp_path."""
import os

import pytest

from mylar import importer


@pytest.fixture
def warns(lib, monkeypatch, tmp_path):
    seen = []
    monkeypatch.setattr(importer.logger, 'warn', lambda msg, *a, **k: seen.append(msg))
    (tmp_path / 'comics').mkdir()
    return seen


def folder(tmp_path, *parts, files=()):
    path = os.path.join(str(tmp_path), 'comics', *parts)
    os.makedirs(path)
    for f in files:
        open(os.path.join(path, f), 'w').close()
    return path


def tree(root):
    out = []
    root = os.path.join(str(root), 'comics')
    for base, dirs, files in os.walk(root):
        for f in files:
            out.append(os.path.relpath(os.path.join(base, f), root))
    return sorted(out)


def test_only_the_year_in_the_folder_name_is_replaced(tmp_path, warns):
    # passes before the fix too (the old code took the right-most 2099 when there were several)
    old = folder(tmp_path, 'Marvel', 'Spider-Man 2099 (2099)', files=['a.cbz'])
    new = importer.rename_2099_folder(old, '2099', '2014')
    assert new == os.path.join(str(tmp_path), 'comics', 'Marvel', 'Spider-Man 2099 (2014)')
    assert tree(tmp_path) == ['Marvel/Spider-Man 2099 (2014)/a.cbz']


def test_folder_without_a_year_is_not_renamed(tmp_path, warns):
    old = folder(tmp_path, 'Marvel', 'Spider-Man 2099', files=['a.cbz'])
    assert importer.rename_2099_folder(old, '2099', '2014') == old
    assert tree(tmp_path) == ['Marvel/Spider-Man 2099/a.cbz']


def test_2099_in_the_base_path_is_left_alone(tmp_path, warns):
    # passes before the fix too (right-most 2099)
    old = folder(tmp_path, '2099', 'Y (2099)', files=['a.cbz'])
    new = importer.rename_2099_folder(old, '2099', '2026')
    assert new == os.path.join(str(tmp_path), 'comics', '2099', 'Y (2026)')
    assert tree(tmp_path) == ['2099/Y (2026)/a.cbz']


def test_2099_only_in_the_base_path_renames_nothing(tmp_path, warns):
    old = folder(tmp_path, '2099', 'Y', files=['a.cbz'])
    assert importer.rename_2099_folder(old, '2099', '2026') == old
    assert tree(tmp_path) == ['2099/Y/a.cbz']


def test_existing_target_folder_is_not_merged_into(tmp_path, warns):
    old = folder(tmp_path, 'Y (2099)', files=['Y 1.cbz'])
    folder(tmp_path, 'Y (2026)', files=['Other Y 1.cbz'])
    assert importer.rename_2099_folder(old, '2099', '2026') == old
    assert tree(tmp_path) == ['Y (2026)/Other Y 1.cbz', 'Y (2099)/Y 1.cbz']
    assert any('Y (2099)' in w and 'Y (2026)' in w for w in warns)


def test_plain_rename_without_collision(tmp_path, warns):
    # control: passes before and after the fix
    old = folder(tmp_path, 'Y (2099)', files=['Y 1.cbz'])
    new = importer.rename_2099_folder(old, '2099', '2026')
    assert new == os.path.join(str(tmp_path), 'comics', 'Y (2026)')
    assert tree(tmp_path) == ['Y (2026)/Y 1.cbz']


def test_missing_old_folder_takes_the_existing_new_one(tmp_path, warns):
    # control: the series was already moved by hand
    new = folder(tmp_path, 'Y (2026)')
    assert importer.rename_2099_folder(os.path.join(str(tmp_path), 'comics', 'Y (2099)'), '2099', '2026') == new


def test_no_rename_when_the_stored_year_is_not_2099(tmp_path, warns):
    # control
    old = folder(tmp_path, 'Y (2020)')
    assert importer.rename_2099_folder(old, '2020', '2026') == old
