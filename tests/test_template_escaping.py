"""Static checks that the fork's own JavaScript escapes outside text before it goes into HTML (R26).

The JavaScript in the templates does not run here. Each check names one place in
data/interfaces/default that the fork added or changed since b609c28c and that puts a title from
GetComics, a file or folder name, a series name or a server message with such text into HTML
(.html(), innerHTML, .append() with a built string, a DataTables render function, an attribute
value). The check asserts that the value goes through escapeHtml() (or is set as text) and that the
raw concatenation is gone. Lines unchanged from upstream are left out on purpose: the review
2026-11-22 (chapter 11) accepted them as a risk.

$('<div/>').text(x).html() escapes &, < and > but not quotes, so it is enough between tags and not
inside an attribute value. Places that already used it between tags are covered by checks marked
"control": they passed before the fix and must keep passing.

When node is available (it is in the mylar3:local image), the escapeHtml() helper of each template
also runs on '<img src=x onerror=1>' and on a value that tries to leave an attribute.
"""
import json
import os
import re
import shutil
import subprocess

import pytest

TEMPLATES = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         'data', 'interfaces', 'default')

# Raw server message concatenated into the HTML of an .html() call.
RAW_OBJ_MESSAGE = r"\.html\([^\n]*\+\s*obj\['message'\]\s*\+"
ESCAPED_OBJ_MESSAGE = "escapeHtml(obj['message'])"


def _read(template):
    with open(os.path.join(TEMPLATES, template), encoding='utf-8') as f:
        return f.read()


def _region(template, start, end):
    """Text from the unique `start` anchor up to the first `end` anchor after it."""
    text = _read(template)
    assert text.count(start) == 1, '%s: anchor %r found %s times' % (template, start, text.count(start))
    begin = text.index(start)
    stop = text.find(end, begin + len(start))
    assert stop != -1, '%s: end anchor %r not found after %r' % (template, end, start)
    return text[begin:stop]


def _check(template, start, end, required=(), forbidden=(), counts=None):
    region = _region(template, start, end)
    for needle in required:
        assert needle in region, '%s [%s]: %r missing' % (template, start, needle)
    for pattern in forbidden:
        found = re.search(pattern, region)
        assert found is None, '%s [%s]: unescaped %r' % (template, start, found.group(0))
    for needle, count in (counts or {}).items():
        assert region.count(needle) == count, '%s [%s]: %r found %s times, expected %s' % (
            template, start, needle, region.count(needle), count)


def _escape_helper_source(template):
    """Source of the escapeHtml() helper the template defines (asserts it is defined once)."""
    text = _read(template)
    assert text.count('function escapeHtml(text)') == 1, '%s: escapeHtml() not defined once' % template
    lines = text[text.index('function escapeHtml(text)'):].splitlines()
    out = []
    seen_return = False
    for line in lines:
        out.append(line)
        if 'return String(text).replace(' in line:
            seen_return = True
        elif seen_return and line.strip() == '}':
            break
    assert seen_return, '%s: escapeHtml() does not replace characters' % template
    return '\n'.join(out)


HELPER_TEMPLATES = [
    'queue_management.html',
]


@pytest.mark.parametrize('template', HELPER_TEMPLATES)
def test_template_defines_escape_helper_for_text_and_attributes(template):
    source = _escape_helper_source(template)
    for char, entity in (('&', '&amp;'), ('<', '&lt;'), ('>', '&gt;'), ('"', '&quot;'), ("'", '&#39;')):
        assert entity in source, '%s: escapeHtml() does not turn %s into %s' % (template, char, entity)


@pytest.mark.skipif(shutil.which('node') is None, reason='node is not installed')
@pytest.mark.parametrize('template', HELPER_TEMPLATES)
def test_escape_helper_neutralises_markup_in_node(template):
    source = _escape_helper_source(template)
    samples = ['<img src=x onerror=1>', '" onmouseover="alert(1)', "a & b's", None, 5]
    script = source + '\nprocess.stdout.write(JSON.stringify(%s.map(escapeHtml)));' % json.dumps(samples)
    result = subprocess.run(['node', '-e', script], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == [
        '&lt;img src=x onerror=1&gt;',
        '&quot; onmouseover=&quot;alert(1)',
        'a &amp; b&#39;s',
        '',
        '5',
    ]


# --- queue_management.html -------------------------------------------------------------------

def test_queue_ajaxcallit_escapes_server_message():
    # ddl_requeue answers e.g. 'Successfully restarted <series> [<size>]'
    _check('queue_management.html', 'function ajaxcallit(', 'function initThisPage(',
           required=["escapeHtml(objd['message'])"],
           forbidden=[r"\+\s*objd\['message'\]\s*\+"])


def test_queue_link_column_escapes_article_title_tooltip_and_link_type():
    # the GetComics article title goes into a title="..." attribute: quotes must be escaped too
    _check('queue_management.html', 'var linkType = full[8]', 'return result;',
           required=['escapeHtml(articleTitle)', 'escapeHtml(linkType)'],
           forbidden=[r"\$\('<div/>'\)\.text\(articleTitle\)", r"var result = linkType;"])
