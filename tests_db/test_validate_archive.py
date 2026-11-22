"""validate_downloaded_archive tells the archive type from the content, not the extension (R22)."""
import os

import pytest

from mylar import helpers

from fakes import make_zip

ZIP = make_zip(n_files=4, size=60000)  # about 240 KB, above MIN_PLAUSIBLE_ARCHIVE_BYTES


def write(tmp_path, name, data):
    path = tmp_path / name
    path.write_bytes(data)
    return str(path)


@pytest.mark.parametrize('name', ['Batman 001 (2025).cbr', 'Batman 001 (2025).cbz', 'Batman 001 (2025).rar'])
def test_complete_zip_is_ok_whatever_its_extension(lib, tmp_path, name):
    path = write(tmp_path, name, ZIP)
    result = helpers.validate_downloaded_archive(path, len(ZIP))
    assert result['ok'] is True, result
    assert result['discard'] is False and result['short'] is False
    assert os.path.isfile(path)


def test_mislabelled_zip_from_a_host_is_kept_and_completed(lib, tmp_path):
    path = write(tmp_path, 'Batman 001 (2025)[__I1__].cbr', ZIP)
    assert helpers.ddl_host_download_check(path, len(ZIP), 'PixelDrain') is None
    assert os.path.getsize(path) == len(ZIP)


def test_broken_zip_with_the_full_size_is_discarded(lib, tmp_path):
    broken = ZIP[:len(ZIP) - 2000]
    path = write(tmp_path, 'Batman 001 (2025).cbz', broken)
    result = helpers.validate_downloaded_archive(path, len(broken))
    assert result['ok'] is False
    assert result['discard'] is True


def test_short_zip_is_resumed(lib, tmp_path):
    path = write(tmp_path, 'Batman 001 (2025).cbr', ZIP[:150000])
    result = helpers.validate_downloaded_archive(path, len(ZIP))
    assert result['ok'] is False and result['short'] is True and result['discard'] is False


def test_unknown_content_is_an_unknown_archive_type(lib, tmp_path):
    path = write(tmp_path, 'Batman 001 (2025).bin', b'\x00' * 200000)
    result = helpers.validate_downloaded_archive(path, 200000)
    assert result['reason'] == 'unknown archive type'
    assert result['discard'] is True


def test_html_named_cbz_still_fails_as_a_zip(lib, tmp_path):
    path = write(tmp_path, 'Batman 001 (2025).cbz', b'<html>' + b' ' * 200000)
    result = helpers.validate_downloaded_archive(path, 0)
    assert result['ok'] is False and result['short'] is True
    assert result['reason'].startswith('zip open failed')
