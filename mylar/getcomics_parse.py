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


def is_year_span(text):
    """'1941-1944 ...' / '1941 - 1944': a span of years, not an issue range."""
    return bool(re.match(r'^(?:19|20)\d{2}\s*-\s*(?:19|20)\d{2}(?!\d)', str(text or '')))


def volume_booktype(title):
    """Booktype of a volume pack: TPB(s)/GN/HC/One-Shot as a whole word anywhere in the title."""
    for token, booktype in ((r'tpbs?', 'TPB'), (r'gns?', 'GN'), (r'hcs?', 'HC'), (r'one-shots?', 'One-Shot')):
        if re.search(r'(?<![\w-])%s(?![\w-])' % token, title, re.IGNORECASE):
            return booktype
    return 'TPB/GN/HC/One-Shot'
