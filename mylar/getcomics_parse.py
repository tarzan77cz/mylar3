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


def direct_ddl_check_issue(issue_range):
    """Issue number a direct DDL range is checked with (queue_direct_ddl -> issue_find_ids).

    The first number of the range: '26-50' -> '26', '1-10 + Annual 1-3' -> '1', and for
    an annual-only range 'Annual 1-3' -> '1' (it used to be 'Annual 1', never valid).
    """
    text = re.sub(r'\bannuals?\b', ' ', str(issue_range or ''), flags=re.IGNORECASE)
    text = text.replace('#', ' ').strip()
    if '-' in text:
        text = text.split('-')[0].strip()
    return text


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


def section_keys(sections):
    """Identity of each post section for a retry, in page order.

    ``sections`` are dicts with ``numbers`` (header issue numbers), ``variant`` and
    ``series`` (header text). The key is variant + numbers; the header text is added when
    the section names no numbers or another section has the same numbers (two editions).
    """
    base = ['%s|%s' % (s.get('variant') or '', ','.join(str(n) for n in s.get('numbers') or []))
            for s in sections]
    keys = []
    for i, s in enumerate(sections):
        if s.get('numbers') and base.count(base[i]) == 1:
            keys.append(base[i])
        else:
            text = re.sub(r'\s+', ' ', normalize_dashes(s.get('series'))).strip().lower()
            keys.append('%s|%s' % (base[i], text))
    return keys


def find_section(keys, index, key=None):
    """Index of the section a retry is for, or None when it is not on the page.

    ``index`` is the stored position, ``key`` the stored section_keys value (older queue
    items have only the index).
    """
    try:
        index = int(index)
    except (TypeError, ValueError):
        return None
    if not key:
        return index if 0 <= index < len(keys) else None
    if 0 <= index < len(keys) and keys[index] == key:
        return index
    if key in keys:
        return keys.index(key)
    return None


def section_is_annual(series):
    """True when a section header numbers annuals: 'Batman Annual #1 - 3', not
    'Batman #1 - 50 + Annual 1 - 3' (its '#' numbers are regular issues)."""
    text = str(series or '')
    hash_at = text.find('#')
    head = text if hash_at < 0 else text[:hash_at]
    return bool(re.search(r'\bannuals?\b', head, re.IGNORECASE))


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
    - A single issue gets one section. A pack gets every remaining section; the year
      only decides between sections whose issue numbers overlap (volumes), so sub-packs
      with other year spans stay (see _choose_pack_sections).
    """
    if len(sections) <= 1:
        return list(range(len(sections)))
    wanted = set(wanted or [])
    chosen = list(range(len(sections)))
    if wanted:
        hits = [i for i in chosen if wanted & set(sections[i]['numbers'])]
        if hits:
            chosen = hits
    if pack:
        return _choose_pack_sections(sections, chosen, wanted, year)
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
    return [chosen[-1]]


def _overlap_groups(sections, indexes):
    """Connected groups of sections whose issue numbers overlap (or are equal, also when
    unknown), in page order."""
    groups = []
    for i in indexes:
        numbers = set(sections[i]['numbers'])
        touching = [
            g for g in groups
            if any((numbers & set(sections[j]['numbers'])) or sections[j]['numbers'] == sections[i]['numbers']
                   for j in g)
        ]
        merged = [i]
        for g in touching:
            merged.extend(g)
            groups.remove(g)
        groups.append(sorted(merged))
    return sorted(groups, key=lambda g: g[0])


def _choose_pack_sections(sections, chosen, wanted, year):
    """Sections of a pack: every group of overlapping sections gives one section.

    Sub-packs ("#1 - 70", "#71 - 140") do not overlap and are all kept, whatever their
    years. Within a group the year narrows the choice (volumes "#1 - 64" 1943-1956 and
    "#1 - 20" 1966-1967), the last of equal numbers is kept, and when different sections
    still overlap, the one with the most wanted issues (the last on a tie).
    """
    result = []
    for group in _overlap_groups(sections, chosen):
        if len(group) > 1 and year:
            in_year = [
                i for i in group
                if sections[i]['years'] and sections[i]['years'][0] <= year <= sections[i]['years'][1]
            ]
            if in_year:
                group = in_year
        by_numbers = {}
        for i in group:
            by_numbers[tuple(sections[i]['numbers'])] = i
        for rest in _overlap_groups(sections, sorted(by_numbers.values())):
            if len(rest) == 1:
                result.extend(rest)
                continue

            def score(i):
                numbers = set(sections[i]['numbers'])
                return (len(numbers & wanted) if wanted else len(numbers), i)
            result.append(max(rest, key=score))
    return sorted(result)


def is_year_span(text):
    """'1941-1944 ...' / '1941 - 1944': a span of years, not an issue range."""
    return bool(re.match(r'^(?:19|20)\d{2}\s*-\s*(?:19|20)\d{2}(?!\d)', str(text or '')))


def volume_booktype(title):
    """Booktype of a volume pack: TPB(s)/GN/HC/One-Shot as a whole word anywhere in the title."""
    for token, booktype in ((r'tpbs?', 'TPB'), (r'gns?', 'GN'), (r'hcs?', 'HC'), (r'one-shots?', 'One-Shot')):
        if re.search(r'(?<![\w-])%s(?![\w-])' % token, title, re.IGNORECASE):
            return booktype
    return 'TPB/GN/HC/One-Shot'
