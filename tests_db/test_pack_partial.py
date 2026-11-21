"""A pack whose sections could be queued only partly (review R4)."""
from mylar import helpers

UNQUEUED = [{'series': 'Old Comic #11 - 20', 'issues': list(range(11, 21)), 'annual': False}]


def _snatched_pack(lib):
    lib.add_series('C1', 'Old Comic', range(1, 21))
    pack_issuelist = helpers.issue_find_ids('Old Comic', 'C1', '1 - 20', '1', '1')
    # search.py marks every issue of the pack Snatched (updater.foundsearch) after the snatch.
    lib.set_status([x['issueid'] for x in pack_issuelist['issues']], 'Snatched')
    return pack_issuelist


def test_unqueued_section_goes_back_to_wanted(lib):
    pack_issuelist = _snatched_pack(lib)
    reverted = helpers.revert_unqueued_pack_sections('1', 'C1', pack_issuelist, UNQUEUED)
    assert sorted(reverted) == sorted('I%s' % n for n in range(11, 21))
    assert lib.statuses('I%s' % n for n in range(11, 21)) == {'Wanted'}
    assert lib.statuses('I%s' % n for n in range(1, 11)) == {'Snatched'}
    assert lib.rows('SELECT * FROM failed') == []  # the rest of the pack still downloads


def test_unqueued_section_only_for_the_issues_marked(lib):
    # select_rejected_match marks only the chosen issue Snatched.
    pack_issuelist = _snatched_pack(lib)
    helpers.revert_unqueued_pack_sections('1', 'C1', pack_issuelist, UNQUEUED, only_issueids=['I15', 'I3'])
    assert lib.status('I15') == 'Wanted'
    assert lib.status('I3') == 'Snatched'
    assert lib.status('I16') == 'Snatched'


def test_unqueued_section_without_numbers_is_left_alone(lib):
    pack_issuelist = _snatched_pack(lib)
    reverted = helpers.revert_unqueued_pack_sections(
        '1', 'C1', pack_issuelist, [{'series': 'Old Comic Extras', 'issues': [], 'annual': False}])
    assert reverted == []
    assert lib.statuses('I%s' % n for n in range(1, 21)) == {'Snatched'}
