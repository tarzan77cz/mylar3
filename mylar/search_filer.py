# -*- coding: utf-8 -*-
# This file is part of Mylar.
#
# Mylar is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Mylar is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Mylar.  If not, see <http://www.gnu.org/licenses/>.

import re
import email.utils
import datetime
import time
import difflib
from wsgiref.handlers import format_date_time

import mylar
from mylar import logger, filechecker, helpers, search
import time


def _normalize_id_value(value):
    """Normalize nzbid/link id values so None and '' compare equal."""
    if value is None:
        return ''
    return str(value).strip()


def _extract_getcomics_post_id(value):
    """Return numeric GetComics post id from a raw id/link, or None."""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.isdigit():
        return text
    # Handle full / already-normalized URLs and accidental double-wraps.
    if '?p=' in text:
        try:
            candidate = text.split('?p=', 1)[1].split('&', 1)[0].strip()
            # Unwrap nested ?p=https://getcomics.info/?p=123
            while '?p=' in candidate:
                candidate = candidate.split('?p=', 1)[1].split('&', 1)[0].strip()
            if candidate.isdigit():
                return candidate
        except Exception:
            return None
    return None


def _normalize_ddl_rejected_ids(entry, nzbid=None, provider=None, mutate_entry=False):
    """Normalize DDL(GetComics) link/id for rejected-match storage and download.

    RSS results often store only the numeric post id in ``link`` (e.g. ``402258``)
    without ``id``. Download via searcher requires a full GetComics URL and nzbid.

    By default this does not mutate ``entry``. Mutating before RSS matching would
    turn a numeric link into a full URL and then the RSS path would double-wrap it
    (breaking html_cache filenames that embed the nzbid).
    """
    if not isinstance(entry, dict):
        return _normalize_id_value(entry), _normalize_id_value(nzbid) or None

    entry_link = entry.get('link', '') or ''
    entry_id = nzbid if nzbid not in (None, '') else entry.get('id')
    site = str(entry.get('site') or '')
    provider_name = str(provider or site or '')
    is_getcomics = (
        ('DDL' in provider_name and 'GetComics' in provider_name)
        or ('DDL' in site and 'GetComics' in site)
    )

    if is_getcomics:
        link_str = str(entry_link).strip()
        post_id = (
            _extract_getcomics_post_id(entry_id)
            or _extract_getcomics_post_id(link_str)
            or _extract_getcomics_post_id(entry.get('id'))
        )
        if post_id:
            entry_id = post_id
            # Prefer a stable canonical URL; keep pretty getcomics.org links as-is.
            if (
                not link_str
                or not link_str.startswith('http')
                or '/cat/' in link_str
                or '?p=' in link_str
            ):
                entry_link = 'https://getcomics.info/?p=%s' % post_id
        elif link_str and not link_str.startswith('http'):
            # Non-numeric id-only link fallback
            entry_id = link_str
            entry_link = 'https://getcomics.info/?p=%s' % entry_id

        if mutate_entry:
            if entry_id not in (None, ''):
                entry['id'] = entry_id
            if entry_link:
                entry['link'] = entry_link
            if not entry.get('filename') and entry.get('title'):
                entry['filename'] = entry['title']

    if entry_id in (None, ''):
        entry_id = None
    return entry_link, entry_id


def _rejected_ids_match(stored_link, stored_nzbid, link, nzbid):
    """Compare rejected-match identifiers, treating None/'' as equivalent."""
    return (
        _normalize_id_value(stored_link) == _normalize_id_value(link)
        and _normalize_id_value(stored_nzbid) == _normalize_id_value(nzbid)
    )


def _is_duplicate_rejected_match(IssueID, link, nzbid):
    """Check if rejected match with given link and nzbid already exists for IssueID"""
    if IssueID not in mylar.REJECTED_MATCHES:
        return False
    for match in mylar.REJECTED_MATCHES[IssueID]:
        if _rejected_ids_match(match.get('link'), match.get('nzbid'), link, nzbid):
            return True
    return False


def _find_rejected_match_index(IssueID, link, nzbid):
    """Find index of rejected match with given link and nzbid, or None if not found"""
    if IssueID not in mylar.REJECTED_MATCHES:
        return None
    for idx, match in enumerate(mylar.REJECTED_MATCHES[IssueID]):
        if _rejected_ids_match(match.get('link'), match.get('nzbid'), link, nzbid):
            return idx
    # Fallback: match by link alone when nzbid was missing on either side
    if _normalize_id_value(link):
        link_matches = [
            idx for idx, match in enumerate(mylar.REJECTED_MATCHES[IssueID])
            if _normalize_id_value(match.get('link')) == _normalize_id_value(link)
        ]
        if len(link_matches) == 1:
            return link_matches[0]
    if _normalize_id_value(nzbid):
        nzbid_matches = [
            idx for idx, match in enumerate(mylar.REJECTED_MATCHES[IssueID])
            if _normalize_id_value(match.get('nzbid')) == _normalize_id_value(nzbid)
        ]
        if len(nzbid_matches) == 1:
            return nzbid_matches[0]
    return None


def _pack_year_bounds(year_value):
    """Parse pack/issue year into inclusive (start, end) ints.

    Accepts values like ``2014``, ``2014-2015``, or messy strings containing
    one or more 19xx/20xx years. Returns None when no usable year is present.
    """
    if year_value is None:
        return None
    year_str = str(year_value).strip()
    if not year_str or year_str.lower() == 'none':
        return None

    range_match = re.match(r'^(\d{4})\s*[-–—]\s*(\d{4})$', year_str)
    if range_match:
        start_year = int(range_match.group(1))
        end_year = int(range_match.group(2))
        if start_year > end_year:
            start_year, end_year = end_year, start_year
        return start_year, end_year

    if re.match(r'^\d{4}$', year_str):
        year_int = int(year_str)
        return year_int, year_int

    found_years = [int(y) for y in re.findall(r'(?:19|20)\d{2}', year_str)]
    if not found_years:
        return None
    return min(found_years), max(found_years)


def _years_overlap(bounds_a, bounds_b):
    """Return True when inclusive year ranges overlap."""
    if not bounds_a or not bounds_b:
        return False
    return bounds_a[0] <= bounds_b[1] and bounds_b[0] <= bounds_a[1]


OFFERABLE_MIN_RELEVANCE = 0.15


def _normalize_series_name(name):
    """Normalize a series/title string for fuzzy comparison."""
    if not name:
        return ''
    return helpers.cleanName(str(name)).strip()


def _parsed_year_empty(parsed_year):
    """Return True when a parsed year value is missing or unusable."""
    if parsed_year is None:
        return True
    year_str = str(parsed_year).strip()
    return year_str in ('', 'None', 'Unknown')


def _single_year_compatible(parsed_year, is_info, bypass_volume_year=False, comvers_chk=None):
    """Return True when parsed year is absent or compatible with the watched comic."""
    if _parsed_year_empty(parsed_year):
        return True

    UseFuzzy = is_info['UseFuzzy'] if 'UseFuzzy' in is_info else None
    if UseFuzzy == "1":
        return True

    if bypass_volume_year:
        return True

    if comvers_chk == 0 and _parsed_year_empty(parsed_year):
        return True

    ComicYear = is_info['ComicYear']
    comyear = ComicYear
    IssDateFix = is_info['IssDateFix'] if 'IssDateFix' in is_info else 'no'

    if not any(
        [
            UseFuzzy == "0",
            UseFuzzy == "2",
            UseFuzzy is None,
            IssDateFix != "no",
        ]
    ):
        return True

    year_str = str(parsed_year).strip()
    if not any(
        [
            len(year_str) >= 4 and year_str[:-2] == '19',
            len(year_str) >= 4 and year_str[:-2] == '20',
        ]
    ):
        return True

    if str(comyear) == year_str:
        return True

    if UseFuzzy == "2":
        try:
            ComUp = int(ComicYear) + 1
            ComDwn = int(ComicYear) - 1
            if str(ComUp) in year_str or str(ComDwn) in year_str:
                return True
        except Exception:
            pass

    if IssDateFix != "no" and UseFuzzy != "2":
        try:
            if IssDateFix in ("01", "02", "03"):
                ComicYearFix = int(ComicYear) - 1
            else:
                ComicYearFix = int(ComicYear) + 1
            if str(ComicYearFix) in year_str:
                return True
        except Exception:
            pass

    return False


def _pack_year_compatible(pack_year_str, is_info):
    """Return True when a pack year range overlaps the watched series/issue years."""
    if _parsed_year_empty(pack_year_str):
        return True

    UseFuzzy = is_info['UseFuzzy'] if 'UseFuzzy' in is_info else None
    if UseFuzzy == "1":
        return True

    pack_bounds = _pack_year_bounds(pack_year_str)
    if pack_bounds is None:
        return True

    ComicYear = is_info['ComicYear']
    SeriesYear = is_info['SeriesYear'] if 'SeriesYear' in is_info else None
    comyear = ComicYear

    ref_years = []
    for year_candidate in (SeriesYear, ComicYear, comyear):
        if year_candidate is None:
            continue
        try:
            year_digits = re.sub(r'[^0-9]', '', str(year_candidate))
            if len(year_digits) < 4:
                continue
            year_int = int(year_digits[:4])
        except Exception:
            continue
        if 1900 <= year_int <= 2100:
            ref_years.append(year_int)

    if not ref_years:
        return True

    ref_bounds = (min(ref_years) - 1, max(ref_years) + 1)
    return _years_overlap(pack_bounds, ref_bounds)


def _compute_rejected_relevance(
    is_info,
    entry,
    reason,
    parsed_comic=None,
    filecomic=None,
    alt_match=False,
    verified=False,
):
    """Compute a 0-1 relevance score for a rejected match vs the watched issue."""
    comic_name = is_info['ComicName'] if 'ComicName' in is_info else ''
    issue_number = is_info['IssueNumber'] if 'IssueNumber' in is_info else None
    comic_version = is_info['ComicVersion'] if 'ComicVersion' in is_info else None

    title = ''
    if isinstance(entry, dict):
        title = entry.get('title', '') or entry.get('nzbtitle', '') or entry.get('ComicTitle', '')

    candidate_series = title
    candidate_year = None
    candidate_issue = None
    candidate_volume = None

    if parsed_comic:
        if parsed_comic.get('series_name'):
            candidate_series = parsed_comic['series_name']
        elif parsed_comic.get('comicfilename'):
            candidate_series = parsed_comic['comicfilename']
        candidate_year = parsed_comic.get('issue_year')
        candidate_issue = parsed_comic.get('issue_number')
        candidate_volume = parsed_comic.get('series_volume')

    if filecomic and filecomic.get('justthedigits') is not None:
        candidate_issue = filecomic['justthedigits']

    norm_expected = _normalize_series_name(comic_name)
    norm_candidate = _normalize_series_name(candidate_series)
    norm_title = _normalize_series_name(title)

    name_ratio = 0.0
    if norm_expected and norm_candidate:
        name_ratio = difflib.SequenceMatcher(None, norm_expected, norm_candidate).ratio()
    if norm_expected and norm_title:
        name_ratio = max(name_ratio, difflib.SequenceMatcher(None, norm_expected, norm_title).ratio())

    name_score = name_ratio * 0.50

    issue_score = 0.08
    if issue_number is not None and candidate_issue is not None:
        try:
            expected_int = helpers.issue_number_parser(issue_number).asInt
            found_int = helpers.issue_number_parser(candidate_issue).asInt
            if expected_int == found_int:
                issue_score = 0.25
            else:
                issue_score = 0.05
        except Exception:
            issue_score = 0.10
    elif candidate_issue is None:
        issue_score = 0.12

    if _parsed_year_empty(candidate_year):
        year_score = 0.08
    elif _single_year_compatible(candidate_year, is_info):
        year_score = 0.15
    else:
        year_score = 0.0

    volume_score = 0.0
    if comic_version and candidate_volume:
        try:
            expected_vol = re.sub('[^0-9]', '', str(comic_version))
            found_vol = re.sub('[^0-9]', '', str(candidate_volume))
            if expected_vol and found_vol and expected_vol == found_vol:
                volume_score = 0.10
        except Exception:
            pass

    score = name_score + issue_score + year_score + volume_score

    if verified:
        score = min(1.0, score + 0.15)
    if alt_match:
        score = max(0.0, score - 0.05)

    reason_lower = (reason or '').lower()
    if 'issue number matches' in reason_lower or 'issue #' in reason_lower:
        score = min(1.0, score + 0.10)
    if 'alternate series' in reason_lower:
        score = min(1.0, max(score, 0.55))

    return round(min(1.0, max(0.0, score)), 4)


def _remove_rejected_match(IssueID, link, nzbid):
    """Remove a rejected match from the in-memory cache."""
    try:
        if IssueID not in mylar.REJECTED_MATCHES:
            return False
        match_idx = _find_rejected_match_index(IssueID, link, nzbid)
        if match_idx is None:
            return False
        removed = mylar.REJECTED_MATCHES[IssueID].pop(match_idx)
        if not mylar.REJECTED_MATCHES[IssueID]:
            del mylar.REJECTED_MATCHES[IssueID]
        logger.fdebug(
            '[REJECTED-MATCHES] Removed rejected match for IssueID %s: %s'
            % (IssueID, removed.get('title', 'Unknown'))
        )
        return True
    except Exception as e:
        logger.fdebug('[REJECTED-MATCHES] Error removing rejected match: %s' % e)
        return False


def _prune_unprocessed_rejected_matches(IssueID):
    """Drop raw search dumps that never received a rejection reason."""
    if IssueID not in mylar.REJECTED_MATCHES:
        return
    pruned = [
        match for match in mylar.REJECTED_MATCHES[IssueID]
        if not (
            match.get('initial_added')
            and not (match.get('reason') or '').strip()
            and not match.get('verified_data')
        )
    ]
    if pruned:
        mylar.REJECTED_MATCHES[IssueID] = pruned
    else:
        del mylar.REJECTED_MATCHES[IssueID]


def _filter_offerable_rejected_matches(matches):
    """Return rejected matches that should be shown to the user."""
    offerable = []
    for match in matches:
        reason = (match.get('reason') or '').strip()
        reason_lower = reason.lower()
        if not reason and not match.get('verified_data'):
            continue
        if 'year mismatch' in reason_lower or 'pack year mismatch' in reason_lower:
            continue
        relevance = match.get('relevance_score', 0.0)
        if relevance < OFFERABLE_MIN_RELEVANCE and not match.get('verified_data'):
            continue
        offerable.append(match)
    return offerable


def count_offerable_rejected_matches(IssueID):
    """Count rejected matches that would be shown in the Upcoming dialog."""
    if IssueID not in mylar.REJECTED_MATCHES:
        return 0
    return len(_filter_offerable_rejected_matches(mylar.REJECTED_MATCHES[IssueID]))


def _add_or_update_rejected_match(IssueID, link, nzbid, match_data, update_only=False):
    """Add new or update existing rejected match. Returns True if added/updated, False otherwise."""
    try:
        if IssueID not in mylar.REJECTED_MATCHES:
            mylar.REJECTED_MATCHES[IssueID] = []
        
        match_idx = _find_rejected_match_index(IssueID, link, nzbid)
        
        if match_idx is not None:
            # Update existing match - merge new data with existing data
            existing_match = mylar.REJECTED_MATCHES[IssueID][match_idx]
            # Preserve original data and update with new data
            existing_match.update(match_data)
            existing_match['last_updated'] = time.time()
            logger.fdebug('[REJECTED-MATCHES] Updated rejected match for IssueID %s: %s' % 
                         (IssueID, match_data.get('title', 'Unknown')))
            return True
        elif not update_only:
            # Add new match
            match_data['last_updated'] = time.time()
            if 'initial_added' not in match_data:
                match_data['initial_added'] = True
            mylar.REJECTED_MATCHES[IssueID].append(match_data)
            logger.fdebug('[REJECTED-MATCHES] Added new rejected match for IssueID %s: %s' % 
                         (IssueID, match_data.get('title', 'Unknown')))
            return True
        
        return False
    except Exception as e:
        logger.fdebug('[REJECTED-MATCHES] Error in _add_or_update_rejected_match: %s' % e)
        return False


class search_check(object):

    def __init__(self):
        pass

    def _store_rejected_match(
        self,
        entry,
        is_info,
        reason,
        comsize_m=None,
        pubdate=None,
        nzbid=None,
        parsed_comic=None,
        filecomic=None,
        alt_match=False,
        verified_data=None,
    ):
        """Helper function to store rejected matches for user review - uses update mechanism"""
        if not is_info or 'IssueID' not in is_info:
            return

        try:
            IssueID = is_info['IssueID']
            provider = is_info.get('nzbprov', 'Unknown')
            entry_link, entry_id = _normalize_ddl_rejected_ids(entry, nzbid=nzbid, provider=provider)

            if parsed_comic is not None:
                parsed_year = parsed_comic.get('issue_year')
                if parsed_year is not None and not _single_year_compatible(parsed_year, is_info):
                    _remove_rejected_match(IssueID, entry_link, entry_id)
                    return

            relevance_score = _compute_rejected_relevance(
                is_info,
                entry,
                reason,
                parsed_comic=parsed_comic,
                filecomic=filecomic,
                alt_match=alt_match,
                verified=verified_data is not None,
            )

            if relevance_score < OFFERABLE_MIN_RELEVANCE and verified_data is None:
                _remove_rejected_match(IssueID, entry_link, entry_id)
                return

            entry_title = 'Unknown'
            if isinstance(entry, dict):
                entry_title = entry.get('title', entry.get('nzbtitle', 'Unknown'))

            rejected_match = {
                "title": entry_title,
                "provider": provider,
                "size": comsize_m if comsize_m else 'Unknown',
                "kind": entry.get('kind', 'Unknown') if isinstance(entry, dict) else 'Unknown',
                "link": entry_link,
                "pubdate": pubdate if pubdate else (entry.get('pubdate', '') if isinstance(entry, dict) else ''),
                "reason": reason,
                "nzbid": entry_id,
                "entry": entry,
                "relevance_score": relevance_score,
                "verified_data": verified_data,
                "initial_added": False,
            }

            _add_or_update_rejected_match(IssueID, entry_link, entry_id, rejected_match, update_only=False)
            logger.fdebug(
                '[REJECTED-MATCHES] Stored/updated rejected match for IssueID %s: %s'
                ' (Reason: %s, Score: %s)'
                % (IssueID, entry_title, reason, relevance_score)
            )
        except Exception as e:
            logger.fdebug('[REJECTED-MATCHES] Error storing rejected match: %s' % e)

    def _add_all_entries_to_rejected_matches(self, entries, is_info):
        """Add all entries from search to rejected matches with minimal data"""
        if not is_info or 'IssueID' not in is_info:
            return
        
        try:
            IssueID = is_info['IssueID']
            nzbprov = is_info.get('nzbprov', 'Unknown')
            
            for entry in entries:
                provider = entry.get('site', nzbprov)
                entry_link, entry_id = _normalize_ddl_rejected_ids(entry, nzbid=entry.get('id'), provider=provider)
                
                # Create minimal match data - will be updated later when we know more
                minimal_match = {
                    "title": entry.get('title', 'Unknown'),
                    "provider": provider,
                    "size": entry.get('length', 'Unknown'),
                    "kind": "Unknown",  # Will be determined later
                    "link": entry_link,
                    "pubdate": entry.get('pubdate', ''),
                    "reason": "",  # No reason yet - will be updated when we know why it was rejected
                    "nzbid": entry_id,
                    "entry": entry,
                    "relevance_score": 0.0,  # Will be updated later
                    "verified_data": None,
                    "initial_added": True  # Mark as added from initial search
                }
                
                # Use _add_or_update_rejected_match - it will only add if doesn't exist
                _add_or_update_rejected_match(IssueID, entry_link, entry_id, minimal_match, update_only=False)
            
            logger.fdebug('[REJECTED-MATCHES] Added %d entries to rejected matches for IssueID %s' % 
                         (len(entries), IssueID))
        except Exception as e:
            logger.fdebug('[REJECTED-MATCHES] Error adding entries to rejected matches: %s' % e)

    def _process_entry(self, entry, is_info):
        if is_info:
            ComicName = is_info['ComicName']
            nzbprov = is_info['nzbprov']
            RSS = is_info['RSS']
            UseFuzzy = is_info['UseFuzzy']
            StoreDate = is_info['StoreDate']
            IssueDate = is_info['IssueDate']
            digitaldate = is_info['digitaldate']
            booktype = is_info['booktype']
            ignore_booktype = is_info['ignore_booktype']
            SeriesYear = is_info['SeriesYear']
            ComicVersion = is_info['ComicVersion']
            IssDateFix = is_info['IssDateFix']
            ComicYear = comyear = is_info['ComicYear']
            IssueID = is_info['IssueID']
            ComicID = is_info['ComicID']
            IssueNumber = is_info['IssueNumber']
            manual = is_info['manual']
            newznab_host = is_info['newznab_host']
            torznab_host = is_info['torznab_host']
            oneoff = is_info['oneoff']
            tmpprov = is_info['tmpprov']
            SARC = is_info['SARC']
            IssueArcID = is_info['IssueArcID']
            cmloopit = is_info['cmloopit']
            findcomiciss = is_info['findcomiciss']
            intIss = is_info['intIss']
            chktpb = is_info['chktpb']
            provider_stat = is_info['provider_stat']

        try:
            pack = entry['pack']
        except Exception:
            pack = False

        alt_match = False
        #logger.fdebug('entry: %s' % (entry,))

        logger.fdebug("checking search result: %s" % entry['title'])
        # some nzbsites feel that comics don't deserve a nice regex to strip
        # the crap from the header, the end result is that we're dealing with
        # the actual raw header which causes incorrect matches below. This is a
        # temporary cut from the experimental search option (findcomicfeed) as
        # it does this part well usually.
        except_list = [
            'releases',
            'gold line',
            'distribution',
            '0-day',
            '0 day',
        ]
        splitTitle = entry['title'].split("\"")
        _digits = re.compile(r'\d')

        ComicTitle = entry['title']
        for subs in splitTitle:
            logger.fdebug('sub: %s' % subs)
            try:
                if (
                    len(subs) >= len(ComicName)
                    and not any(d in subs.lower() for d in except_list)
                    and bool(_digits.search(subs)) is True
                ):
                    if subs.lower().startswith('for'):
                        if ComicName.lower().startswith('for'):
                            pass
                        else:
                            # this is the crap we ignore. Continue
                            continue
                        logger.fdebug(
                            'Detected crap within header. Ignoring this portion'
                            ' of the result in order to see if it\'s a valid'
                            ' match.'
                        )
                    ComicTitle = subs
                    break
            except Exception:
                break

        ignored = []
        for x in mylar.CONFIG.IGNORE_SEARCH_WORDS:
            if x.lower() in ComicTitle.lower():
                ignored.append(x)

        if ignored:
            logger.fdebug('[IGNORE_SEARCH_WORDS] %s exists within the search result (%s). Ignoring this result.' % (ignored, ComicTitle))
            return None

        comsize_m = 0
        if nzbprov != "dognzb":
            # rss for experimental doesn't have the size constraints embedded.
            # So we do it here.
            if RSS == "yes":
                comsize_b = entry['length']
            else:
                # Experimental already has size constraints done.
                if nzbprov == 'experimental':
                    # we only want the size from the rss as
                    # the search/api has it already.
                    comsize_b = entry['length']
                else:
                    try:
                        if entry['site'] == 'DDL(GetComics)':
                            comsize_b = entry['size']
                            if comsize_b is not None:
                                cb2 = re.sub(r'[^0-9]', '', comsize_b).strip()
                                if cb2 == '':
                                    logger.warn(
                                        'Invalid filesize encountered. Ignoring'
                                    )
                                    comsize_b = None
                                else:
                                    comsize_b = helpers.human2bytes(entry['size'])
                        elif entry['site'] == 'DDL(External)':
                            comsize_b = '0' #External links ! filesize
                        elif entry['site'] == 'AirDCPP':
                            # Use size_bytes if available, otherwise use the formatted size string
                            if 'size_bytes' in entry and entry['size_bytes']:
                                comsize_b = entry['size_bytes']
                            else:
                                comsize_b = helpers.human2bytes(entry['size'])
                    except Exception:
                        tmpsz = entry.enclosures[0]
                        comsize_b = tmpsz['length']

            logger.fdebug('comsize_b: %s' % comsize_b)
            # file restriction limitation here
            # Experimental (has it embeded in search and rss checks)

            if comsize_b is None or comsize_b == '0':
                logger.fdebug(
                    'Size of file cannot be retrieved.'
                    ' Ignoring size-comparison and continuing.'
                )
                # comsize_b = 0
            else:
                if entry['title'][:17] != '0-Day Comics Pack':
                    comsize_m = helpers.human_size(comsize_b)
                    logger.fdebug('size given as: %s' % comsize_m)
                    # ----size constraints.
                    # if it's not within size constaints - dump it now.
                    if mylar.CONFIG.USE_MINSIZE:
                        conv_minsize = helpers.human2bytes(
                            mylar.CONFIG.MINSIZE + "M"
                        )
                        logger.fdebug(
                            'comparing Min threshold %s .. to .. nzb %s'
                            % (conv_minsize, comsize_b)
                        )
                        if int(conv_minsize) > int(comsize_b):
                            logger.fdebug(
                                'Failure to meet the Minimum size threshold'
                                ' - skipping'
                            )
                            return None
                    if mylar.CONFIG.USE_MAXSIZE:
                        conv_maxsize = helpers.human2bytes(
                            mylar.CONFIG.MAXSIZE + "M"
                        )
                        logger.fdebug(
                            'comparing Max threshold %s .. to .. nzb %s'
                            % (conv_maxsize, comsize_b)
                        )
                        if int(comsize_b) > int(conv_maxsize):
                            logger.fdebug(
                                'Failure to meet the Maximium size threshold'
                                ' - skipping'
                            )
                            return None

        if mylar.CONFIG.IGNORE_COVERS is True:
            cvrchk = re.sub(r'[\s\s+\_\.]', '', entry['title']).lower()
            if any(['coversonly' in cvrchk, 'coveronly' in cvrchk]):
                logger.fdebug('Cover(s) only detected. Ignoring result.')
                return None

        # ---- date constaints.
        # if the posting date is prior to the publication date,
        # dump it and save the time.
        # logger.fdebug('entry: %s' % entry)
        if nzbprov == 'experimental':
            pubdate = entry['pubdate']
        else:
            try:
                pubdate = entry['updated']
            except Exception:
                try:
                    pubdate = entry['pubdate']
                except Exception as e:
                    logger.fdebug(
                        'Invalid date found. Unable to continue'
                        ' - skipping result. Error returned: %s' % e
                    )
                    return None

        if UseFuzzy == "1" or nzbprov.lower() == 'airdcpp':
            logger.fdebug(
                'Year has been fuzzied for this series, or provider is AirDC++'
                ' ignoring store date comparison entirely.'
            )
            postdate_int = None
            issuedate_int = None
        else:
            # use store date instead of publication date for comparisons since
            # publication date is usually +2 months
            if StoreDate is None or StoreDate == '0000-00-00':
                if IssueDate is None or IssueDate == '0000-00-00':
                    logger.fdebug(
                        'Invalid store date & issue date detected - you'
                        ' probably should refresh the series or wait for CV'
                        ' to correct the data'
                    )
                    return None
                else:
                    stdate = IssueDate
                logger.fdebug('issue date used is : %s' % stdate)
            else:
                stdate = StoreDate
                logger.fdebug('store date used is : %s' % stdate)
            logger.fdebug('date used is : %s' % stdate)

            postdate_int = None
            if all(['DDL' in nzbprov, len(pubdate) == 10]):
                postdate_int = pubdate
                logger.fdebug(
                    '[%s] postdate_int (%s): %s'
                    % (nzbprov, type(postdate_int), postdate_int)
                )
            if any(
                [postdate_int is None, type(postdate_int) != int]
            ) or not RSS == 'no':
                # convert it to a tuple
                dateconv = email.utils.parsedate_tz(pubdate)

                try:
                    dateconv2 = datetime.datetime(*dateconv[:6])
                except TypeError as e:
                    logger.warn(
                        'Unable to convert timestamp from : %s [%s]'
                        % ((dateconv,), e)
                    )
                try:
                    # convert it to a numeric time, then subtract the
                    # timezone difference (+/- GMT)
                    if dateconv[-1] is not None:
                        postdate_int = (
                            time.mktime(dateconv[: len(dateconv) - 1])
                            - dateconv[-1]
                        )
                    else:
                        postdate_int = time.mktime(
                            dateconv[: len(dateconv) - 1]
                        )
                except Exception as e:
                    logger.warn(
                        'Unable to parse posting date from provider result set'
                        ' for : %s. Error returned: %s' % (entry['title'], e)
                    )
                    return None

            if all([digitaldate != '0000-00-00', digitaldate is not None]):
                i = 0
            else:
                digitaldate_int = '00000000'
                i = 1

            while i <= 1:
                if i == 0:
                    usedate = digitaldate
                else:
                    usedate = stdate
                logger.fdebug('usedate: %s' % usedate)
                # convert it to a Thu, 06 Feb 2014 00:00:00 format
                issue_converted = datetime.datetime.strptime(
                    usedate.rstrip(), '%Y-%m-%d'
                )
                issue_convert = issue_converted + datetime.timedelta(days=-1)
                # to get past different locale's os-dependent dates, let's
                # convert it to a generic datetime format
                try:
                    stamp = time.mktime(issue_convert.timetuple())
                    issconv = format_date_time(stamp)
                except OverflowError as e:
                    logger.fdebug(
                        'Error converting the timestamp into a generic format:'
                        ' %s' % e
                    )
                    issconv = issue_convert.strftime('%a, %d %b %Y %H:%M:%S')
                # convert it to a tuple
                econv = email.utils.parsedate_tz(issconv)
                econv2 = datetime.datetime(*econv[:6])
                # convert it to a numeric and drop the GMT/Timezone
                try:
                    usedate_int = time.mktime(econv[: len(econv) - 1])
                except OverflowError:
                    logger.fdebug(
                        'Unable to convert timestamp to integer format.'
                        ' Forcing things through.'
                    )
                    isyear = econv[1]
                    epochyr = '1970'
                    if int(isyear) <= int(epochyr):
                        tm = datetime.datetime(1970, 1, 1)
                        try:
                            usedate_int = int(time.mktime(tm.timetuple()))
                        except Exception as e:
                            logger.warn(
                                '[%s] Failed to convert tm of [%s]' % (e,tm)
                            )
                            logger.fdebug('issconv: %s' % issconv)
                            diff = issue_convert - tm
                            logger.fdebug('diff: %s' % diff)
                            usedate_int = diff.total_seconds()
                    else:
                        continue
                if i == 0:
                    digitaldate_int = usedate_int
                    digconv2 = econv2
                else:
                    issuedate_int = usedate_int
                    issconv2 = econv2
                i += 1

            try:
                # try new method to get around issues populating in a diff
                # timezone thereby putting them in a different day.
                # logger.info('digitaldate: %s' % digitaldate)
                # logger.info('dateconv2: %s' % dateconv2.date())
                # logger.info('digconv2: %s' % digconv2.date())
                if (
                    digitaldate != '0000-00-00'
                    and dateconv2.date() >= digconv2.date()
                ):
                    logger.fdebug(
                        '%s is after DIGITAL store date of %s'
                        % (pubdate, digitaldate)
                    )
                elif dateconv2.date() < issconv2.date():
                    logger.fdebug(
                        '[CONV] pubdate: %s  < storedate: %s'
                        % (dateconv2.date(), issconv2.date())
                    )
                    logger.fdebug(
                        '%s is before store date of %s. Ignoring search result'
                        ' as this is not the right issue.'
                        % (pubdate, stdate)
                    )
                    # Store rejected match for user review
                    try:
                        nzbid = entry.get('id') if 'id' in entry else None
                        # Only pass comsize_m if it was actually calculated (not the initial 0)
                        size_val = comsize_m if 'comsize_m' in locals() and comsize_m != 0 else None
                        self._store_rejected_match(
                            entry,
                            is_info,
                            "Publication date (%s) is before store date (%s)" % (pubdate, stdate),
                            comsize_m=size_val,
                            pubdate=pubdate,
                            nzbid=nzbid,
                            parsed_comic=parsed_comic if 'parsed_comic' in locals() else None,
                            filecomic=filecomic if 'filecomic' in locals() else None,
                        )
                    except Exception as e:
                        logger.fdebug('[REJECTED-MATCHES] Error storing date-based rejection: %s' % e)
                    return None
                else:
                    logger.fdebug(
                        '[CONV] %s is after store date of %s'
                        % (pubdate, stdate)
                    )
            except Exception as e:
                # if the above fails, drop down to the integer compare method
                # as a failsafe.
                if digitaldate is not None and all(
                    [
                        digitaldate != '0000-00-00',
                        postdate_int >= digitaldate_int
                    ]
                ):
                    logger.fdebug(
                        '%s is after DIGITAL store date of %s'
                        % (pubdate, digitaldate)
                    )
                elif postdate_int < issuedate_int:
                    logger.fdebug(
                        '[INT]pubdate: %s  < storedate: %s'
                        % (postdate_int, issuedate_int)
                    )
                    logger.fdebug(
                        '%s is before store date of %s. Ignoring search result'
                        ' as this is not the right issue.'
                        % (pubdate, stdate)
                    )
                    # Store rejected match for user review
                    try:
                        nzbid = entry.get('id') if 'id' in entry else None
                        # Only pass comsize_m if it was actually calculated (not the initial 0)
                        size_val = comsize_m if 'comsize_m' in locals() and comsize_m != 0 else None
                        self._store_rejected_match(
                            entry,
                            is_info,
                            "Publication date (%s) is before store date (%s)" % (pubdate, stdate),
                            comsize_m=size_val,
                            pubdate=pubdate,
                            nzbid=nzbid,
                            parsed_comic=parsed_comic if 'parsed_comic' in locals() else None,
                            filecomic=filecomic if 'filecomic' in locals() else None,
                        )
                    except Exception as e:
                        logger.fdebug('[REJECTED-MATCHES] Error storing date-based rejection: %s' % e)
                    return None
                else:
                    logger.fdebug(
                        '[INT] %s is after store date of %s' % (pubdate, stdate)
                    )
        # -- end size constaints.
        if '(digital first)' in ComicTitle.lower():
            dig_moving = re.sub(
                r'\(digital first\)', '', ComicTitle.lower()
            ).strip()
            dig_moving = re.sub(r'[\s+]', ' ', dig_moving)
            dig_mov_end = '%s (Digital First)' % dig_moving
            thisentry = dig_mov_end
        else:
            thisentry = ComicTitle

        logger.fdebug('Entry: %s' % thisentry)
        cleantitle = thisentry

        if 'mixed format' in cleantitle.lower():
            cleantitle = re.sub('mixed format', '', cleantitle).strip()
            logger.fdebug(
                'removed extra information after issue # that'
                ' is not necessary: %s' % cleantitle
            )
        # only send it to parser if it's not a DDL + pack (already parsed)
        if pack is True and 'DDL' in entry.get('site', ''):
            logger.fdebug('parsing pack...')
            # DDL entries may have 'series' or only 'title' depending on source
            series_name = entry.get('series') or entry.get('title') or thisentry
            ffc = filechecker.FileChecker()
            dnr = ffc.dynamic_replace(series_name)
            parsed_comic = {'booktype': entry.get('gc_booktype', 'issue'),
                            'comicfilename': entry.get('filename') or series_name,
                            'series_name': series_name,
                            'series_name_decoded': series_name,
                            'issueid': None,
                            'dynamic_name': dnr['mod_seriesname'],
                            'issues': entry.get('issues'),
                            'series_volume': None,
                            'alt_series': None,
                            'alt_issue': None,
                            'issue_year': entry.get('year'),
                            'issue_number': None,
                            'scangroup': None,
                            'reading_order': None,
                            'sub': None,
                            'comiclocation': None,
                            'parse_status': 'success'}


        # send it to the parser here.
        else:
            p_comic = filechecker.FileChecker(file=ComicTitle, watchcomic=ComicName)
            parsed_comic = p_comic.listFiles()
            # For DDL (GetComics) single-issue: use year from card when title has no year
            if 'DDL' in entry.get('site', '') and entry.get('year') is not None and parsed_comic.get('issue_year') is None:
                parsed_comic['issue_year'] = entry['year']

        logger.fdebug('parsed_info: %s' % parsed_comic)
        logger.fdebug(
            'booktype: %s / parsed_booktype: %s [ignore_booktype: %s]'
            % (booktype, parsed_comic['booktype'], ignore_booktype)
        )
        if parsed_comic['parse_status'] == 'success' and (
            all([booktype is None, parsed_comic['booktype'] == 'issue'])
            or all([booktype == 'Print', parsed_comic['booktype'] == 'issue'])
            or all(
                [booktype == 'One-Shot', any(
                    [parsed_comic['booktype'] == 'issue',
                    'One-Shot' in parsed_comic['booktype']
                     ]
                )
                ]
            )
            or all(
                [booktype != parsed_comic['booktype'], ignore_booktype is True]
            )
            or re.sub('None', 'issue', str(booktype)) in parsed_comic['booktype']
        ):
            try:
                fcomic = filechecker.FileChecker(watchcomic=ComicName)
                filecomic = fcomic.matchIT(parsed_comic)
            except Exception as e:
                logger.error('[PARSE-ERROR]: %s' % e)
                return None
            else:
                logger.fdebug('match_check: %s' % filecomic)
                if filecomic['process_status'] == 'fail':
                    logger.fdebug(
                        '%s was not a match to %s (%s)'
                        % (cleantitle, ComicName, SeriesYear)
                    )
                    # Check if this is a relevant match worth storing (issue number and year match)
                    # even though series name doesn't match exactly
                    is_relevant = False
                    reason = "Series name mismatch"
                    
                    # Debug logging
                    logger.fdebug('[REJECTED-MATCHES] Checking fail match: filecomic.justthedigits=%s, parsed_comic.issue_number=%s' % 
                                (filecomic.get('justthedigits', 'NOT_SET'), parsed_comic.get('issue_number', 'NOT_SET')))
                    
                    # Check if issue number matches - try filecomic first, then parsed_comic as fallback
                    issue_number_found = None
                    try:
                        if filecomic.get('justthedigits') is not None:
                            issue_number_found = filecomic['justthedigits']
                        elif parsed_comic.get('issue_number') is not None:
                            issue_number_found = parsed_comic['issue_number']
                        
                        if issue_number_found is not None:
                            comintIss = helpers.issue_number_parser(issue_number_found).asInt
                            # Get expected issue number
                            if IssueNumber is not None:
                                intIss = helpers.issue_number_parser(IssueNumber).asInt
                                if intIss == comintIss:
                                    is_relevant = True
                                    reason = "Series name mismatch (issue number matches)"
                                    logger.fdebug('[REJECTED-MATCHES] Issue number match found: %s == %s' % (comintIss, intIss))
                            elif cmloopit == 4:
                                # For One-Shot searches, any issue number match is relevant
                                is_relevant = True
                                reason = "Series name mismatch (issue number found: %s)" % issue_number_found
                                logger.fdebug('[REJECTED-MATCHES] One-Shot search, issue number found: %s' % issue_number_found)
                    except Exception as e:
                        logger.error('[REJECTED-MATCHES] Error checking issue number match: %s' % e)
                        import traceback
                        logger.fdebug('[REJECTED-MATCHES] Traceback: %s' % traceback.format_exc())
                    
                    # Also check if year matches
                    if is_relevant:
                        try:
                            parsed_year = parsed_comic.get('issue_year')
                            if parsed_year and str(parsed_year) == str(ComicYear):
                                reason = "Series name mismatch (issue #%s and year %s match)" % (
                                    issue_number_found if issue_number_found else '?', parsed_year
                                )
                                logger.fdebug('[REJECTED-MATCHES] Year also matches: %s == %s' % (parsed_year, ComicYear))
                        except Exception as e:
                            logger.fdebug('[REJECTED-MATCHES] Error checking year match: %s' % e)
                    
                    # Store rejected match if relevant
                    if is_relevant:
                        parsed_year = parsed_comic.get('issue_year') if parsed_comic else None
                        if parsed_year is not None and not _single_year_compatible(parsed_year, is_info):
                            logger.fdebug(
                                '[REJECTED-MATCHES] Fail match with issue # but incompatible year'
                                ' - not offering'
                            )
                            return None
                        logger.fdebug('[REJECTED-MATCHES] Attempting to store fail match: title=%s, IssueID=%s, reason=%s' % 
                                    (entry.get('title', 'Unknown'), IssueID if 'IssueID' in locals() else 'NOT_SET', reason))
                        try:
                            nzbid = entry.get('id') if 'id' in entry else None
                            size_val = comsize_m if 'comsize_m' in locals() and comsize_m != 0 else None
                            self._store_rejected_match(
                                entry,
                                is_info,
                                reason,
                                comsize_m=size_val,
                                pubdate=pubdate if 'pubdate' in locals() else None,
                                nzbid=nzbid,
                                parsed_comic=parsed_comic,
                                filecomic=filecomic if 'filecomic' in locals() else None,
                            )
                            logger.fdebug('[REJECTED-MATCHES] Successfully stored fail match for IssueID %s' % IssueID)
                        except Exception as e:
                            logger.error('[REJECTED-MATCHES] Error storing failed match: %s' % e)
                            import traceback
                            logger.fdebug('[REJECTED-MATCHES] Traceback: %s' % traceback.format_exc())
                    else:
                        logger.fdebug('[REJECTED-MATCHES] Fail match not relevant: issue_number_found=%s, IssueNumber=%s, cmloopit=%s' % 
                                    (issue_number_found if issue_number_found else 'None', IssueNumber, cmloopit))
                    
                    return None
                elif filecomic['process_status'] == 'alt_match':
                    # if it's an alternate series match, we'll retain each value
                    # until the search has compeletely run, compiling matches.
                    # If at any point it's a standard match (ie. non-alternate
                    # series) that will be accepted as the one match and
                    # ignore the alts. Once all the search options have been
                    # exhausted and no matches aside from alternate series then
                    # we go get the best result from that list
                    logger.fdebug(
                        '%s was a match due to alternate matching.  Continuing'
                        ' to search, but retaining this result just in case.'
                        % ComicTitle
                    )
                    alt_match = True
        elif booktype != parsed_comic['booktype'] and ignore_booktype is False:
            logger.fdebug(
                'Booktypes do not match. Looking for %s, this is a %s.'
                ' Ignoring this result.' % (booktype, parsed_comic['booktype'])
            )
            # Store rejected match for user review
            try:
                nzbid = entry.get('id') if 'id' in entry else None
                size_val = comsize_m if 'comsize_m' in locals() and comsize_m != 0 else None
                self._store_rejected_match(
                    entry,
                    is_info,
                    "Booktype mismatch: found %s, expected %s" % (parsed_comic['booktype'], booktype),
                    comsize_m=size_val,
                    pubdate=pubdate if 'pubdate' in locals() else None,
                    nzbid=nzbid,
                    parsed_comic=parsed_comic,
                    filecomic=filecomic if 'filecomic' in locals() else None,
                )
            except Exception as e:
                logger.fdebug('[REJECTED-MATCHES] Error storing booktype rejection: %s' % e)
            return None
        else:
            logger.fdebug(
                'Unable to parse name properly: %s. Ignoring this result'
                % parsed_comic
            )
            return None

        # adjust for covers only by removing them entirely...
        vers4year = "no"
        vers4vol = "no"
        versionfound = "no"

        if ComicVersion:
            ComVersChk = re.sub("[^0-9]", "", ComicVersion)
            if ComVersChk == '' or ComVersChk == '1':
                ComVersChk = 0
        else:
            ComVersChk = 0

        fndcomicversion = None

        if parsed_comic['series_volume'] is not None:
            versionfound = "yes"
            if len(parsed_comic['series_volume'][1:]) == 4 and (
                parsed_comic['series_volume'][1:].isdigit()
            ):  # v2013
                logger.fdebug(
                    "[Vxxxx] Version detected as %s"
                    % (parsed_comic['series_volume'])
                )
                vers4year = "yes"
                fndcomicversion = parsed_comic['series_volume']
            elif len(parsed_comic['series_volume'][1:]) == 1 and (
                parsed_comic['series_volume'][1:].isdigit()
            ):  # v2
                logger.fdebug(
                    "[Vx] Version detected as %s"
                    % parsed_comic['series_volume']
                )
                vers4vol = parsed_comic['series_volume']
                fndcomicversion = parsed_comic['series_volume']
            elif (
                parsed_comic['series_volume'][1:].isdigit()
                and len(parsed_comic['series_volume']) < 4
            ):
                logger.fdebug(
                    '[Vxxx] Version detected as %s'
                    % parsed_comic['series_volume']
                )
                vers4vol = parsed_comic['series_volume']
                fndcomicversion = parsed_comic['series_volume']
            elif (
                parsed_comic['series_volume'].isdigit()
                and len(parsed_comic['series_volume']) <= 4
            ):
                # this stuff is necessary for 32P volume manipulation
                if len(parsed_comic['series_volume']) == 4:
                    vers4year = "yes"
                    fndcomicversion = parsed_comic['series_volume']
                elif len(parsed_comic['series_volume']) == 1:
                    vers4vol = parsed_comic['series_volume']
                    fndcomicversion = parsed_comic['series_volume']
                elif len(parsed_comic['series_volume']) < 4:
                    vers4vol = parsed_comic['series_volume']
                    fndcomicversion = parsed_comic['series_volume']
                else:
                    logger.fdebug(
                        "error - unknown length for : %s"
                        % parsed_comic['series_volume']
                    )

        yearmatch = False
        #logger.fdebug('UseFuzzy: %s / ComVersChk: %s / IssDateFix: %s' % (UseFuzzy, ComVersChk, IssDateFix))
        if vers4vol != "no" or vers4year != "no":
            logger.fdebug(
                'Series Year not provided but Series Volume detected of %s.'
                ' Bypassing Year Match.'
                % fndcomicversion
            )
            yearmatch = True
        elif ComVersChk == 0 and parsed_comic['issue_year'] is None:
            logger.fdebug(
                'Series version detected as V1 (only series in existance with'
                ' that title). Bypassing Year/Volume check'
            )
            yearmatch = True
        elif (
            any(
                [
                    UseFuzzy == "0",
                    UseFuzzy == "2",
                    UseFuzzy is None,
                    IssDateFix != "no",
                ]
            )
            and parsed_comic['issue_year'] is not None
        ):
            if any(
                [
                    parsed_comic['issue_year'][:-2] == '19',
                    parsed_comic['issue_year'][:-2] == '20',
                ]
            ):
                if str(comyear) == parsed_comic['issue_year']:
                    logger.fdebug('%s - right years match baby!' % comyear)
                    yearmatch = True
                else:
                    logger.fdebug(
                        '%s - not right - years do not match' % comyear
                    )
                    yearmatch = False
                    if UseFuzzy == "2":
                        # Fuzzy the year +1 and -1
                        ComUp = int(ComicYear) + 1
                        ComDwn = int(ComicYear) - 1
                        if (
                            str(ComUp) in parsed_comic['issue_year']
                            or str(ComDwn) in parsed_comic['issue_year']
                        ):
                            logger.fdebug(
                                'Fuzzy Logicd the Year and matched to a year'
                                ' of %s' % parsed_comic['issue_year']
                            )
                            yearmatch = True
                        else:
                            logger.fdebug(
                                '%s Fuzzy logicd the Year and year still did'
                                ' not match.' % comyear
                            )
                    # let's do this here and save a few extra loops ;)
                    # fix for issue dates between Nov-Dec/Jan
                    if IssDateFix != "no" and UseFuzzy != "2":
                        if (
                            IssDateFix == "01"
                            or IssDateFix == "02"
                            or IssDateFix == "03"
                        ):
                            ComicYearFix = int(ComicYear) - 1
                            if str(ComicYearFix) in parsed_comic['issue_year']:
                                logger.fdebug(
                                    'Further analysis reveals this was'
                                    ' published inbetween Nov-Jan, decreasing'
                                    ' year to %s has resulted in a match!'
                                    % ComicYearFix
                                )
                                yearmatch = True
                            else:
                                logger.fdebug(
                                    '%s- not the right year.' % comyear
                                )
                        else:
                            ComicYearFix = int(ComicYear) + 1
                            if str(ComicYearFix) in parsed_comic['issue_year']:
                                logger.fdebug(
                                    'Further analysis reveals this was'
                                    ' published inbetween Nov-Jan, incrementing'
                                    ' year to %s has resulted in a match!'
                                    % ComicYearFix
                                )
                                yearmatch = True
                            else:
                                logger.fdebug(
                                    '%s - not the right year.' % comyear
                                )
        elif UseFuzzy == "1":
            yearmatch = True

        # Pack titles often include both a volume and a year range
        # (e.g. "Vampirella Vol. 2 #1-22 (2001-2003)"). Volume alone must not
        # allow that pack onto a different era of the same title (e.g. Dynamite
        # Vampirella 2014 marked as v2 on the watchlist).
        if pack is True:
            pack_year_str = None
            if parsed_comic is not None:
                pack_year_str = parsed_comic.get('issue_year')
            if pack_year_str is None and entry.get('year') is not None:
                pack_year_str = entry.get('year')
            pack_bounds = _pack_year_bounds(pack_year_str)
            if pack_bounds is not None:
                ref_years = []
                for year_candidate in (SeriesYear, ComicYear, comyear):
                    if year_candidate is None:
                        continue
                    try:
                        year_digits = re.sub(r'[^0-9]', '', str(year_candidate))
                        if len(year_digits) < 4:
                            continue
                        year_int = int(year_digits[:4])
                    except Exception:
                        continue
                    if 1900 <= year_int <= 2100:
                        ref_years.append(year_int)
                if ref_years:
                    # ±1 covers Nov/Jan store-date edge cases around year boundaries
                    ref_bounds = (min(ref_years) - 1, max(ref_years) + 1)
                    if not _years_overlap(pack_bounds, ref_bounds):
                        logger.fdebug(
                            '[PACK-YEAR] Pack years %s do not overlap series/issue'
                            ' years %s-%s. Ignoring possible match.'
                            % (pack_year_str, min(ref_years), max(ref_years))
                        )
                        yearmatch = False
                        try:
                            nzbid = entry.get('id') if 'id' in entry else None
                            entry_link, entry_id = _normalize_ddl_rejected_ids(
                                entry,
                                nzbid=nzbid,
                                provider=is_info.get('nzbprov', 'Unknown'),
                            )
                            logger.fdebug(
                                '[REJECTED-MATCHES] Pack year mismatch (found %s, expected around'
                                ' %s-%s) - not offering'
                                % (pack_year_str, min(ref_years), max(ref_years))
                            )
                            _remove_rejected_match(IssueID, entry_link, entry_id)
                        except Exception as e:
                            logger.fdebug('[REJECTED-MATCHES] Error removing pack year rejection: %s' % e)
                        return None
                    yearmatch = True

        if yearmatch is False and pack is False:
            try:
                nzbid = entry.get('id') if 'id' in entry else None
                entry_link, entry_id = _normalize_ddl_rejected_ids(
                    entry,
                    nzbid=nzbid,
                    provider=is_info.get('nzbprov', 'Unknown'),
                )
                parsed_year = parsed_comic.get('issue_year', 'Unknown') if parsed_comic else 'Unknown'
                logger.fdebug(
                    '[REJECTED-MATCHES] Year mismatch (found %s, expected %s) - not offering'
                    % (parsed_year, ComicYear)
                )
                _remove_rejected_match(IssueID, entry_link, entry_id)
            except Exception as e:
                logger.fdebug('[REJECTED-MATCHES] Error removing year rejection: %s' % e)
            return None

        annualize = False
        if 'annual' in ComicName.lower():
            logger.fdebug(
                "IssueID of : %s This is an annual...let's adjust." % IssueID
            )
            annualize = True

        D_ComicVersion = 1
        F_ComicVersion = None

        if versionfound == "yes" or annualize is True:
            logger.fdebug("volume detection commencing - adjusting length.")
            logger.fdebug("watch comicversion is %s" % ComicVersion)
            logger.fdebug("version found: %s" % fndcomicversion)
            logger.fdebug("vers4year: %s" % vers4year)
            logger.fdebug("vers4vol: %s" % vers4vol)

            if vers4year != "no" or vers4vol != "no":
                # if the volume is None, assume it's a V1 to increase % hits
                if ComVersChk == 0:
                    D_ComicVersion = 1
                else:
                    D_ComicVersion = ComVersChk

            # if this is a one-off, SeriesYear will be None and cause errors.
            S_ComicVersion = 0
            if all([SeriesYear is not None, annualize is False]):
                S_ComicVersion = str(SeriesYear)

            if fndcomicversion:
                F_ComicVersion = re.sub("[^0-9]", "", fndcomicversion)
                # if found volume is a vol.0, up it to vol.1 (since there is no V0)
                if F_ComicVersion == '0':
                    if annualize is True:
                        F_ComicVersion = parsed_comic['issue_year']
                    else:
                        # need to convert dates to just be yyyy-mm-dd and do comparison,
                        # time operator in the below calc
                        F_ComicVersion = '1'
            else:
                F_ComicVersion = '1'

            logger.fdebug('FCVersion: %s' % F_ComicVersion)
            logger.fdebug('DCVersion: %s' % D_ComicVersion)
            logger.fdebug('SCVersion: %s' % S_ComicVersion)
            logger.fdebug('ComicYear: %s' % ComicYear)

            # here's the catch, sometimes annuals get posted as the Pub Year
            # instead of the Series they belong to (V2012 vs V2013)
            if all(
                    [
                        annualize is True,
                        parsed_comic['issue_number'] is not None,
                    ]
            ) and any(
                    [
                        int(ComicYear) == int(F_ComicVersion),
                        int(ComicYear) == int(parsed_comic['issue_number']),
                    ]
            ):
                logger.fdebug(
                    "We matched on versions for annuals %s (%s = %s = %s)"
                    % (ComicYear, fndcomicversion, F_ComicVersion, parsed_comic['issue_number'])
                )
            elif all(
                    [
                         booktype != 'TPB',
                         booktype != 'HC',
                         booktype != 'GN',
                         booktype != 'TPB/GN/HC/One-Shot',
                    ]
                ) and (
                    int(F_ComicVersion) == int(D_ComicVersion)
                    or int(F_ComicVersion) == int(S_ComicVersion)
            ):
                logger.fdebug("We matched on versions...%s" % fndcomicversion)
            else:
                if any(
                       [
                           booktype == 'TPB',
                           booktype == 'HC',
                           booktype == 'GN',
                           booktype == 'TPB/GN/HC/One-Shot',
                       ]
                    ) and any([
                       all(
                       [
                           int(F_ComicVersion) == int(findcomiciss)
                           and filecomic['justthedigits'] is None
                       ]
                    ), all(
                       [
                           int(F_ComicVersion) == int(findcomiciss)
                           and ComicYear == parsed_comic['issue_year']
                       ]
                    )
                ]):
                    logger.fdebug(
                        '%s detected - reassigning volume %s to match as the'
                        ' issue number based on Volume'
                        % (booktype, fndcomicversion)
                    )
                elif all(
                         [
                             booktype == 'TPB',
                             booktype == 'HC',
                             booktype == 'GN',
                             booktype == 'TPB/GN/HC/One-Shot',
                         ]
                    ) and all(
                    [
                        int(F_ComicVersion) == int(findcomiciss),
                        fndcomicversion is not None,
                        booktype in filecomic['booktype'],
                        filecomic['justthedigits'] is None,
                    ]
                ):
                    logger.fdebug(
                        '%s detected - reassigning volume %s to match as the issue number'
                        % (booktype, fndcomicversion)
                    )
                else:
                    logger.fdebug("Versions wrong. Ignoring possible match.")
                    # Store rejected match for user review
                    try:
                        nzbid = entry.get('id') if 'id' in entry else None
                        size_val = comsize_m if 'comsize_m' in locals() and comsize_m != 0 else None
                        self._store_rejected_match(
                            entry,
                            is_info,
                            "Volume/version mismatch: found %s, expected %s"
                            % (
                                fndcomicversion if 'fndcomicversion' in locals() and fndcomicversion else 'Unknown',
                                ComicVersion if ComicVersion else 'V1',
                            ),
                            comsize_m=size_val,
                            pubdate=pubdate if 'pubdate' in locals() else None,
                            nzbid=nzbid,
                            parsed_comic=parsed_comic,
                            filecomic=filecomic if 'filecomic' in locals() else None,
                        )
                    except Exception as e:
                        logger.fdebug('[REJECTED-MATCHES] Error storing version rejection: %s' % e)
                    return None

        downloadit = False

        if all(['DDL' in nzbprov, pack is True]):
            logger.fdebug(
                '[PACK-QUEUE] %s Pack detected for %s.'
                % (nzbprov, entry['filename'])
            )

            # find the pack range.
            pack_issuelist = None
            issueid_info = None
            try:
                if not entry['title'].startswith('0-Day Comics Pack'):
                    pack_issuelist = entry['issues']
                    issueid_info = helpers.issue_find_ids(
                        ComicName, ComicID, pack_issuelist, IssueNumber, entry['id']
                    )
                    if issueid_info['valid'] is True:
                        logger.info(
                            'Issue Number %s exists within pack. Continuing.'
                            % IssueNumber
                        )
                    else:
                        logger.fdebug(
                            'Issue Number %s does NOT exist within this pack.'
                            ' Skipping' % IssueNumber
                        )
                        return None
            except Exception as e:
                logger.error(
                    'Unable to identify pack range for %s. Error returned: %s'
                    % (entry['title'], e)
                )
                return None
            # pack support.
            nowrite = False
            if 'DDL' in nzbprov:
                if 'getcomics' in entry['link']:
                    nzbid = entry['id']
            else:
                nzbid = search.generate_id(provider_stat, entry['link'], ComicName)
            if all([manual is not True, alt_match is False]):
                downloadit = True
            else:
                for x in mylar.COMICINFO:
                    if (
                        all(
                            [
                                x['link'] == entry['link'],
                                x['tmpprov'] == tmpprov,
                            ]
                        )
                        or all(
                            [x['nzbid'] == nzbid, x['newznab'] == newznab_host]
                        )
                        or all(
                            [x['nzbid'] == nzbid, x['torznab'] == torznab_host]
                        )
                    ):
                        nowrite = True
                        break

            if nowrite is False:
                if any(
                    [
                        nzbprov == 'experimental',
                        'newznab' in nzbprov,
                    ]
                ):
                    tprov = nzbprov
                    kind = 'usenet'
                    if newznab_host is not None:
                        tprov = newznab_host[0]
                else:
                    tprov = nzbprov
                    kind = 'torrent'
                    if torznab_host is not None:
                        tprov = torznab_host[0]

                # Store alt_match results in rejected matches before returning
                if alt_match and IssueID:
                    logger.fdebug('[REJECTED-MATCHES] Attempting to store alt_match: title=%s, IssueID=%s, alt_match=%s' % 
                                (entry.get('title', 'Unknown'), IssueID, alt_match))
                    try:
                        self._store_rejected_match(
                            entry,
                            is_info,
                            "Alternate series match (not primary match)",
                            comsize_m=comsize_m if 'comsize_m' in locals() else None,
                            pubdate=pubdate if 'pubdate' in locals() else None,
                            nzbid=nzbid,
                            parsed_comic=parsed_comic,
                            filecomic=filecomic if 'filecomic' in locals() else None,
                            alt_match=True,
                        )
                        logger.fdebug('[REJECTED-MATCHES] Successfully stored alt_match for IssueID %s' % IssueID)
                    except Exception as e:
                        logger.error('[REJECTED-MATCHES] Error storing alt_match in pack section: %s' % e)
                        import traceback
                        logger.fdebug('[REJECTED-MATCHES] Traceback: %s' % traceback.format_exc())
                else:
                    if alt_match:
                        logger.fdebug('[REJECTED-MATCHES] alt_match=True but IssueID missing: IssueID=%s, is_info=%s' % 
                                    (IssueID if 'IssueID' in locals() else 'NOT_SET', 'IssueID' in is_info if is_info else 'is_info is None'))

                return {
                    "ComicName": ComicName,
                    "ComicID": ComicID,
                    "IssueID": IssueID,
                    "ComicVolume": ComicVersion,
                    "IssueNumber": IssueNumber,
                    "IssueDate": IssueDate,
                    "comyear": comyear,
                    "pack": True,
                    "pack_numbers": pack_issuelist,
                    "pack_issuelist": issueid_info,
                    "modcomicname": entry['title'],
                    "oneoff": oneoff,
                    "nzbprov": nzbprov,
                    "nzbtitle": entry['title'],
                    "nzbid": nzbid,
                    "provider": tprov,
                    "link": entry['link'],
                    "pubdate": pubdate,
                    "size": comsize_m,
                    "tmpprov": tmpprov,
                    "kind": kind,
                    "SARC": SARC,
                    "booktype": booktype,
                    "IssueArcID": IssueArcID,
                    "newznab": newznab_host,
                    "torznab": torznab_host,
                    "downloadit": downloadit,
                    "alt_match": alt_match,
                    "ComicTitle": ComicTitle,
                    "entry": entry,
                    "provider_stat": provider_stat,
                }
        else:
            if filecomic['process_status'] == 'match' or filecomic['process_status'] == 'alt_match':
                if cmloopit != 4:
                    logger.fdebug(
                        "issue we are looking for is : %s" % findcomiciss
                    )
                    logger.fdebug(
                        "integer value of issue we are looking for : %s"
                        % intIss
                    )
                else:
                    if intIss is None and all(
                        [
                            booktype == 'One-Shot',
                            helpers.issue_number_parser(parsed_comic['issue_number']).asInt
                            == helpers.issue_number_to_int(1, None),
                        ]
                    ):
                        intIss = helpers.issue_number_to_int(1,None)
                    else:
                        if annualize is True:
                            if parsed_comic['issue_number'] is None:
                                # if issue_number is None, assume it's #1 of the annual
                                intIss = helpers.issue_number_to_int(1, None)
                            elif len(re.sub('[^0-9]', '', parsed_comic['issue_number']).strip()) == 4:
                                intIss = helpers.issue_number_to_int(1, None)
                            elif parsed_comic['issue_number'] is not None:
                                intIss = helpers.issue_number_parser(parsed_comic['issue_number']).asInt
                        else:
                            # TODO: Does this special case still exist / get referenced anywhere after further clean up?
                            intIss = 9999999999
                if filecomic['justthedigits'] is not None:
                    logger.fdebug(
                        "issue we found for is : %s"
                        % filecomic['justthedigits']
                    )
                    if annualize is True and len(re.sub('[^0-9]', '', filecomic['justthedigits']).strip()) == 4:
                        comintIss = helpers.issue_number_to_int(1, None)
                    else:
                        comintIss = helpers.issue_number_parser(filecomic['justthedigits']).asInt
                    logger.fdebug(
                        "integer value of issue we have found : %s" % comintIss
                    )
                else:
                    comintIss = helpers.issue_number_to_int(11111111, None)

                # do this so that we don't touch the actual value but just
                # use it for comparisons
                if filecomic['justthedigits'] is None:
                    pc_in = None
                else:
                    pc_in = helpers.issue_number_parser(filecomic['justthedigits']).asInt
                # issue comparison now as well
                if (
                    all([intIss is not None, comintIss is not None])
                    and int(intIss) == int(comintIss)
                    or (any(
                        [
                            filecomic['booktype'] == 'TPB',
                            filecomic['booktype'] == 'GN',
                            filecomic['booktype'] == 'HC',
                            filecomic['booktype'] == 'TPB/GN/HC/One-Shot',
                        ]
                        ) and all(
                            [
                                chktpb != 0,
                                pc_in is None,
                                helpers.issue_number_parser(F_ComicVersion).asInt == intIss,
                            ]
                    ))
                    or (any(
                        [
                            filecomic['booktype'] == 'TPB',
                            filecomic['booktype'] == 'GN',
                            filecomic['booktype'] == 'HC',
                            filecomic['booktype'] == 'TPB/GN/HC/One-Shot',
                        ]
                        )  and all(
                            [
                                chktpb == 2,
                                pc_in is None,
                                cmloopit == 1,
                            ]
                    ))
                    or all([cmloopit == 4, findcomiciss is None, pc_in is None])
                    or all([cmloopit == 4, findcomiciss is None, pc_in == 1])
                    or all([cmloopit == 4, findcomiciss == 1, pc_in is None])
                ):
                    nowrite = False
                    logger.info('[nzbprov:%s] provider_stat: %s' % (nzbprov, provider_stat,))
                    if nzbprov == 'torznab' or provider_stat['type'] == 'torznab':
                        nzbid = search.generate_id(provider_stat, entry['id'], ComicName)
                    elif 'DDL' in nzbprov:
                        if 'GetComics' in nzbprov:
                            # Idempotent normalization: numeric RSS ids, full URLs,
                            # and accidental double-wraps all resolve to post id + ?p= URL.
                            post_id = (
                                _extract_getcomics_post_id(entry.get('id'))
                                or _extract_getcomics_post_id(entry.get('link'))
                            )
                            if post_id:
                                entry['id'] = post_id
                                entry['link'] = 'https://getcomics.info/?p=%s' % post_id
                            elif RSS == "yes":
                                entry['id'] = entry['link']
                                entry['link'] = 'https://getcomics.info/?p=' + str(
                                    entry['id']
                                )
                            elif '/cat/' in str(entry.get('link') or ''):
                                entry['link'] = 'https://getcomics.info/?p=%s' % entry['id']
                            if not entry.get('filename'):
                                entry['filename'] = entry.get('title')
                        entry['title'] = entry['filename']
                        nzbid = entry['id']
                    else:
                        try:
                            logger.fdebug('title_id: %s' % (entry['id'],))
                            if 'details' in entry['id']:
                                nzbid = search.generate_id(provider_stat, entry['id'], ComicName)
                            else:
                                nzbid = search.generate_id(provider_stat, entry['link'], ComicName)
                        except Exception as e:
                            nzbid = search.generate_id(provider_stat, entry['link'], ComicName)
                    if all([manual is not True, alt_match is False]):
                        downloadit = True
                    else:
                        for x in mylar.COMICINFO:
                            if (
                                all(
                                    [
                                        x['link'] == entry['link'],
                                        x['tmpprov'] == tmpprov,
                                    ]
                                )
                                or all(
                                    [
                                        x['nzbid'] == nzbid,
                                        x['newznab'] == newznab_host,
                                    ]
                                )
                                or all(
                                    [
                                        x['nzbid'] == nzbid,
                                        x['torznab'] == torznab_host,
                                    ]
                                )
                            ):
                                nowrite = True
                                break

                    # modify the name for annualization to be displayed properly
                    if annualize is True:
                        modcomicname = '%s Annual' % ComicName
                    else:
                        modcomicname = ComicName

                    if IssueID is None:
                        cyear = ComicYear
                    else:
                        cyear = comyear

                    if nowrite is False:
                        if any(
                            [
                                nzbprov == 'experimental',
                                'newznab' in nzbprov,
                                provider_stat['type'] == 'newznab',
                            ]
                        ):
                            tprov = nzbprov
                            kind = 'usenet'
                            if newznab_host is not None:
                                tprov = newznab_host[0]
                        else:
                            kind = 'torrent'
                            tprov = nzbprov
                            if torznab_host is not None:
                                tprov = torznab_host[0]

                        # Store alt_match results in rejected matches before returning
                        if alt_match and IssueID:
                            logger.fdebug('[REJECTED-MATCHES] Attempting to store alt_match: title=%s, IssueID=%s, alt_match=%s' % 
                                        (entry.get('title', 'Unknown'), IssueID, alt_match))
                            try:
                                self._store_rejected_match(
                                    entry,
                                    is_info,
                                    "Alternate series match (not primary match)",
                                    comsize_m=comsize_m if 'comsize_m' in locals() else None,
                                    pubdate=pubdate if 'pubdate' in locals() else None,
                                    nzbid=nzbid,
                                    parsed_comic=parsed_comic,
                                    filecomic=filecomic if 'filecomic' in locals() else None,
                                    alt_match=True,
                                )
                                logger.fdebug('[REJECTED-MATCHES] Successfully stored alt_match for IssueID %s' % IssueID)
                            except Exception as e:
                                logger.error('[REJECTED-MATCHES] Error storing alt_match in normal match section: %s' % e)
                                import traceback
                                logger.fdebug('[REJECTED-MATCHES] Traceback: %s' % traceback.format_exc())
                        else:
                            if alt_match:
                                logger.fdebug('[REJECTED-MATCHES] alt_match=True but IssueID missing: IssueID=%s, is_info=%s' % 
                                            (IssueID if 'IssueID' in locals() else 'NOT_SET', 'IssueID' in is_info if is_info else 'is_info is None'))

                        return {
                            "ComicName": ComicName,
                            "ComicID": ComicID,
                            "IssueID": IssueID,
                            "ComicVolume": ComicVersion,
                            "IssueNumber": IssueNumber,
                            "IssueDate": IssueDate,
                            "comyear": cyear,
                            "pack": False,
                            "pack_numbers": None,
                            "pack_issuelist": None,
                            "modcomicname": modcomicname,
                            "oneoff": oneoff,
                            "nzbprov": nzbprov,
                            "provider": tprov,
                            "nzbtitle": entry['title'],
                            "nzbid": nzbid,
                            "link": entry['link'],
                            "pubdate": pubdate,
                            "size": comsize_m,
                            "tmpprov": tmpprov,
                            "kind": kind,
                            "booktype": booktype,
                            "SARC": SARC,
                            "IssueArcID": IssueArcID,
                            "newznab": newznab_host,
                            "torznab": torznab_host,
                            "downloadit": downloadit,
                            "alt_match": alt_match,
                            "ComicTitle": ComicTitle,
                            "entry": entry,
                            "provider_stat": provider_stat,
                            # Add this line to preserve the search_instance_id
                            "search_instance_id": entry.get('search_instance_id')
                        }
                else:
                    #log2file = log2file + "issues don't match.." + "\n"
                    downloadit = False
                    #foundc['status'] = False
                    # Store rejected match if entry was relevant but issue number didn't match
                    if is_info and 'IssueID' in is_info and 'filecomic' in locals():
                        try:
                            # Get issue number found in file
                            found_issue = filecomic.get('justthedigits', 'Unknown') if filecomic else 'Unknown'
                            expected_issue = is_info.get('IssueNumber', 'Unknown')
                            reason = "Issue number mismatch: expected %s, found %s" % (expected_issue, found_issue)
                            
                            # Use _store_rejected_match which handles duplicates and updates automatically
                            self._store_rejected_match(
                                entry,
                                is_info,
                                reason,
                                comsize_m=comsize_m if 'comsize_m' in locals() else None,
                                pubdate=pubdate if 'pubdate' in locals() else None,
                                nzbid=nzbid if 'nzbid' in locals() else None,
                                parsed_comic=parsed_comic if 'parsed_comic' in locals() else None,
                                filecomic=filecomic if 'filecomic' in locals() else None,
                            )
                        except Exception as e:
                            logger.fdebug('[REJECTED-MATCHES] Error storing rejected match: %s' % e)
        return None

    def checker(self, entries, is_info=None):
        mylar.COMICINFO = []
        hold_the_matches = []

        #logger.fdebug('entries: %s' % (entries,))
        for entry in entries:
            maybe_value = self._process_entry(entry, is_info)
            if maybe_value is not None:
                mylar.COMICINFO.append(maybe_value)
                hold_the_matches.append(maybe_value)

        if is_info and 'IssueID' in is_info:
            _prune_unprocessed_rejected_matches(is_info['IssueID'])

        #logger.fdebug('returning hold_the_matches: %s' % (hold_the_matches,))
        return hold_the_matches

    def check_for_first_result(self, entries, is_info, prefer_pack=False):
        candidate = None
        for entry in entries:
            maybe_value = self._process_entry(entry, is_info)
            #logger.fdebug('maybe_value: %s' % maybe_value)
            if maybe_value is not None:
                # Store alt_match results immediately, regardless of pack preference
                if maybe_value.get('alt_match', False) and maybe_value.get('IssueID'):
                    try:
                        # Already stored in _process_entry, but add debug log
                        logger.fdebug('[REJECTED-MATCHES] alt_match result processed in check_for_first_result: %s (IssueID: %s)' % 
                                    (maybe_value.get('nzbtitle', maybe_value.get('ComicTitle', 'Unknown')), maybe_value.get('IssueID')))
                    except Exception as e:
                        logger.fdebug('[REJECTED-MATCHES] Error in check_for_first_result: %s' % e)
                
                # If we have a value which matches our pack/not-pack
                # preference, return it: otherwise, store it for return if we
                # don't find a better candidate
                is_pack = maybe_value["pack"]
                if (prefer_pack and is_pack) or (not prefer_pack and not is_pack):
                    # (This reduces to prefer_pack == is_pack, but that's harder to grok)
                    return maybe_value
                candidate = maybe_value
        logger.info('candidate: %s' % candidate)
        return candidate
