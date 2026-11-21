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

"""Pure GetComics parsing helpers shared by getcomics.py and helpers.py.

No Mylar globals and no I/O, so tests can load this module without starting Mylar.
"""

import re

# Weekly bundles ("Marvel Week+ (11.19.2026)", "Image Week ...") are never a series match.
_WEEKLY_PACK_RE = re.compile(r'\bWeek\+|\bImage Week\b', re.IGNORECASE)

# " & " is a pack receipt only when it introduces extras ("Daredevil #1 - 50 & Annuals"),
# not inside a series name ("Batman & Robin").
AMP_RECEIPT_RE = re.compile(
    r'\s+&\s+(?:Annuals?|TPBs?|Specials?|One[- ]?Shots?|Extras?|Deluxe Books?)\b.*$',
    re.IGNORECASE,
)

# Largest range expanded by issue_numbers; protects against typos like "1-100000".
_MAX_RANGE = 5000


def normalize_dashes(text):
    """En and em dashes to '-' (GetComics titles and section headers use both)."""
    return str(text or '').replace('–', '-').replace('—', '-')


def is_weekly_pack(title):
    return bool(_WEEKLY_PACK_RE.search(str(title or '')))


def issue_numbers(text):
    """Whole issue numbers named by a range text, sorted.

    '1-5, 7 + TPBs' -> [1, 2, 3, 4, 5, 7], '#1 - 21' -> 1..21, '12 - 15' -> 12..15.
    Non-integer tokens ('TPBs', '1.5') are ignored.
    """
    if not text:
        return []
    text = re.sub(r'\s*-\s*', '-', normalize_dashes(text).replace('#', ' '))
    found = set()
    for token in re.split(r'[\s,+&]+', text):
        m = re.match(r'^(\d+)-(\d+)$', token)
        if m:
            lo, hi = int(m.group(1)), int(m.group(2))
            if lo <= hi and hi - lo <= _MAX_RANGE:
                found.update(range(lo, hi + 1))
        elif token.isdigit():
            found.add(int(token))
    return sorted(found)


def split_annual_numbers(pack):
    """Regular and annual issue numbers of a pack range.

    '1-50 + Annual 1-3' -> ([1..50], [1, 2, 3], True); '1-5, 7-9' -> ([1..5, 7..9], [], False).
    The third value tells whether the text mentions annuals at all.
    """
    text = str(pack or '')
    m = re.search(r'annuals?', text, re.IGNORECASE)
    if not m:
        return issue_numbers(text), [], False
    return issue_numbers(text[:m.start()]), issue_numbers(text[m.end():]), True


def title_year(title):
    """Year of a post title: a bracketed year wins ('2000 AD #1999 (2016)' -> '2016'),
    then a 'YYYY-YYYY' span, then the first 19xx/20xx that is not an issue number."""
    m = re.search(r'\(((?:19|20)\d{2}(?:-(?:19|20)\d{2})?)\)', title)
    if m:
        return m.group(1)
    m = re.search(r'\d{4}-\d{4}', title)
    if m:
        return m.group()
    for m in re.finditer(r'\d{4}', title):
        if m.start() > 0 and title[m.start() - 1] == '#':
            continue
        if m.group().startswith(('19', '20')):
            return m.group()
    return None


def number_start_before(title, dash):
    """Start index of the number left of ``dash`` ('Batman 12 - 15' -> index of '1'), else -1."""
    i = dash - 1
    while i >= 0 and title[i] == ' ':
        i -= 1
    if i < 0 or not title[i].isdigit():
        return -1
    j = i
    while j >= 0 and title[j].isdigit():
        j -= 1
    # A number glued to a word is not an issue number, except "Vol1 - 5".
    if j >= 0 and title[j].isalnum() and not title[:j + 1].lower().endswith('vol'):
        return -1
    return j + 1


_BUTTON_PATH_RE = re.compile(r'/dld?s/')


def is_button_link(url):
    """GetComics button redirect: '/dls/...' (current site) or the older '/dlds/...'."""
    return bool(_BUTTON_PATH_RE.search(str(url or '')))


def link_type_for_site(site):
    """Queue link_type of a GetComics button label ('download now', 'mirror download', 'mega link' ...)."""
    low = re.sub(r'\blink\b', '', str(site or '').lower()).strip()
    if low in ('download now', 'main server'):
        return 'GC-Main'
    if low == 'mirror download':
        return 'GC-Mirror'
    if 'mega' in low:
        return 'GC-Mega'
    if 'pixel' in low:
        return 'GC-Pixel'
    if 'mediafire' in low:
        return 'GC-Media'
    return None


def site_failed(site, link_type_failure):
    """True when the button's host already failed for this download.

    A failed GC-Main excludes only "Download Now", not "Mirror Download" (the old check
    matched every label containing "download").
    """
    if not link_type_failure:
        return False
    link_type = link_type_for_site(site)
    if link_type is None:
        return False
    failed = set(str(x).lower() for x in link_type_failure if x)
    return link_type.lower() in failed


def section_issue_numbers(series):
    """Issue numbers a section header names: 'Tomahawk #71 - 140' -> 71..140,
    'Journey Into Mystery #1 - 125 + 503 - 655' -> 1..125 and 503..655. [] when unknown."""
    m = re.search(r'#\s*(\d[\d\s,+\-]*)', normalize_dashes(series))
    return issue_numbers(m.group(1)) if m else []


def year_bounds(text):
    """(first, last) year named in a text ('1950-1972', '1952-1966 + 1996-2013'), else None."""
    years = [int(y) for y in re.findall(r'(?<!\d)(?:19|20)\d{2}(?!\d)', str(text or ''))]
    return (min(years), max(years)) if years else None


def leading_int(value):
    """15 for '15', '15.1' or '15AU'; None when the value does not start with digits."""
    m = re.match(r'^\s*#?\s*(\d+)', str(value or ''))
    return int(m.group(1)) if m else None


def choose_sections(sections, wanted=None, year=None, pack=False):
    """Indexes of the post sections to download.

    ``sections`` is a list of dicts with ``numbers`` (issue numbers of the header) and
    ``years`` (year_bounds of the header), in page order. A post can hold sub-packs
    ("#1 - 70", "#71 - 140"), volumes or two editions of one issue.

    - Sections that contain a wanted issue are kept; then a section whose years include
      ``year``, when that narrows the choice.
    - Sections with the same issue numbers are alternatives: the last one is kept
      (Mylar used to download the last section of a page).
    - A single issue gets one section. A pack gets every remaining section.
    """
    if len(sections) <= 1:
        return list(range(len(sections)))
    wanted = set(wanted or [])
    chosen = list(range(len(sections)))
    if wanted:
        hits = [i for i in chosen if wanted & set(sections[i]['numbers'])]
        if hits:
            chosen = hits
    if year and len(chosen) > 1:
        in_year = [
            i for i in chosen
            if sections[i]['years'] and sections[i]['years'][0] <= year <= sections[i]['years'][1]
        ]
        if in_year:
            chosen = in_year
    by_numbers = {}
    for i in chosen:
        by_numbers[tuple(sections[i]['numbers'])] = i
    chosen = sorted(by_numbers.values())
    if not pack:
        return [chosen[-1]]
    return chosen


def is_year_span(text):
    """'1941-1944 ...' / '1941 - 1944': a span of years, not an issue range."""
    return bool(re.match(r'^(?:19|20)\d{2}\s*-\s*(?:19|20)\d{2}(?!\d)', str(text or '')))


def volume_booktype(title):
    """Booktype of a volume pack: TPB(s)/GN/HC/One-Shot as a whole word anywhere in the title."""
    for token, booktype in ((r'tpbs?', 'TPB'), (r'gns?', 'GN'), (r'hcs?', 'HC'), (r'one-shots?', 'One-Shot')):
        if re.search(r'(?<![\w-])%s(?![\w-])' % token, title, re.IGNORECASE):
            return booktype
    return 'TPB/GN/HC/One-Shot'
