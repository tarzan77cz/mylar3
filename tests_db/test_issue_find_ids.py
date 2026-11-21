"""helpers.issue_find_ids on a temp SQLite DB: direct DDL check issue (R8) and the ignores log (R9)."""
import pytest

from mylar import getcomics_parse, helpers


@pytest.fixture
def series(lib):
    lib.add_series('C1', 'Batman', range(1, 11))
    for n in (1, 2, 3):
        lib.add_annual('C1', n)
    return lib


@pytest.mark.parametrize('issue_range', ['Annual 1-3', '1-10 + Annual 1-3', '#1 - 6', '1-5'])
def test_direct_ddl_range_is_valid_with_its_check_issue(series, issue_range):
    # queue_direct_ddl checks the range with this issue number before it queues the link.
    check = getcomics_parse.direct_ddl_check_issue(issue_range)
    info = helpers.issue_find_ids('Batman', 'C1', issue_range, check, 'manual-1')
    assert info['valid'] is True


def test_old_check_issue_rejected_annual_ranges(series):
    # queue_direct_ddl used the text before the first dash ('Annual 1'): "No Wanted issues".
    assert helpers.issue_find_ids('Batman', 'C1', 'Annual 1-3', 'Annual 1', 'manual-1')['valid'] is False


def test_direct_ddl_annual_range_marks_the_annuals(series):
    info = helpers.issue_find_ids('Batman', 'C1', 'Annual 1-3', getcomics_parse.direct_ddl_check_issue('Annual 1-3'),
                                  'manual-1')
    assert [(x['issueid'], x.get('annual', False)) for x in info['issues']] == [
        ('A1', True), ('A2', True), ('A3', True)]
