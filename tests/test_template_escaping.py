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
    'manage.html',
    'comicdetails_update.html',
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


# --- manage.html -----------------------------------------------------------------------------

def test_manage_manual_pp_log_escapes_comic_and_issue():
    _check('manage.html', 'var log = s.log', "$('#manual_pp_log').html(logHtml)",
           required=["'<li>' + escapeHtml(line) + '</li>'"],
           forbidden=[r"'<li>' \+ line \+"])


def test_manage_manual_pp_file_log_escapes_file_series_status_and_reason():
    _check('manage.html', 'var fileLog = s.file_log', "$('#manual_pp_file_log').html(fileLogHtml)",
           required=['escapeHtml(fname)', 'escapeHtml(label)', 'escapeHtml(reason)'],
           forbidden=[r"\+ fname \+", r"\+ label \+ reason \+"])


def test_manage_post_process_messages_are_escaped_in_ajax_msg():
    # post_process answers e.g. 'Successfully submitted <folder> for manual post-processing...'
    _check('manage.html', "$('#manual_process').click(", 'jQuery( "#tabs" ).tabs();',
           forbidden=[RAW_OBJ_MESSAGE],
           counts={ESCAPED_OBJ_MESSAGE: 3})


def test_manage_post_process_in_progress_status_is_set_as_text():
    _check('manage.html', "else if (obj['status'] == 'IN PROGRESS')", "$('#manual_pp_phase').text('Running...')",
           required=["statuschk.textContent = obj['message']"],
           forbidden=[r"statuschk\.innerHTML"])


# --- comicdetails_update.html ----------------------------------------------------------------

@pytest.mark.parametrize('start,end', [
    ('function annual_delete(', 'function mark_the_issues('),
    ('function mark_the_issues(', 'function mark_the_annuals('),
    ('function mark_the_annuals(', 'function add2readinglist('),
    ('function add2readinglist(', 'function shizzlemedown('),     # 'Successfully added <series> ...'
    ('function downloadthisissue(', 'function unqueue_issue('),   # 'Now downloading issue #.. of <series>'
    ('function unqueue_issue(', 'function retry_issue('),         # '... status of <series> #..'
    ('function retry_issue(', 'function add_wanted('),
    ('function add_wanted(', 'function reload_tables('),          # 'Successfully submitted search for <series>'
    ('function skipped2wanted(', 'function display_date('),
    ('function fix_cv_removed(', 'function count_checks('),       # 'Successfully removed <series> ...'
])
def test_comicdetails_server_messages_are_escaped(start, end):
    _check('comicdetails_update.html', start, end,
           required=[ESCAPED_OBJ_MESSAGE],
           forbidden=[RAW_OBJ_MESSAGE])


def test_comicdetails_single_metatag_escapes_issue_number():
    _check('comicdetails_update.html', 'function run_single_metatag(', 'function runMetaIssue(',
           required=['escapeHtml(issuenumber)'],
           forbidden=[r'"\+issuenumber\+"'])


def test_comicdetails_picker_download_escapes_release_title_in_messages():
    # name is the GetComics/provider title of the release the user picked
    _check('comicdetails_update.html', 'function downloadSpecificRelease(', 'function ShowSpinner(',
           forbidden=[r"\.html\([^\n]*\+\s*name\s*\+"],
           counts={'escapeHtml(name)': 2})


def test_comicdetails_direct_download_escapes_server_message_and_error_text():
    _check('comicdetails_update.html', 'function direct_download_dialog(', 'function search4missing(',
           required=['escapeHtml(obj.message)', "escapeHtml(obj.message || 'Error')", 'escapeHtml(errText)',
                     'DOMParser'],
           forbidden=[r"\+ obj\.message \+", r"\+ \(obj\.message \|\| 'Error'\) \+",
                      r"xhr\.responseText \|\| 'Request failed'\) \+"])


def test_comicdetails_picker_table_cells_escaped_control():
    # control: already escaped before the fix (text between tags); link, nzbid and provider id stay
    # in search_results and never go into the HTML
    _check('comicdetails_update.html', 'function getAvailableDownloads(', 'function downloadSpecificRelease(',
           required=["var title = $('<div/>').text(search_results[i].nzbtitle || 'Unknown').html();",
                     "var provider = $('<div/>').text(search_results[i].provider || 'Unknown').html();",
                     "var size = $('<div/>').text(search_results[i].size || 'Unknown').html();",
                     "var kind = $('<div/>').text(search_results[i].kind || 'Unknown').html();",
                     "var reason = $('<div/>').text(search_results[i].reason || '').html();",
                     "onclick=\"downloadSpecificRelease(' + i + ');\""],
           forbidden=[r"'<td>' \+ search_results", r"search_results\[i\]\.(link|nzbid|tmpprov|rejected_)"])
