"""Fake ComicVine XML responses for cv.GetIssuesInfo / cv.getComic('issue') (no network)."""
from xml.dom.minidom import parseString


def issue(iid, num, cover, store='0000-00-00', volume='111'):
    num_xml = '<issue_number>%s</issue_number>' % num if num is not None else ''
    cover_xml = '<cover_date>%s</cover_date>' % cover if cover is not None else ''
    return ('<issue><id>%s</id><name>Issue %s</name>%s%s'
            '<store_date>%s</store_date><volume><id>%s</id><name>Fake</name></volume></issue>'
            % (iid, iid, num_xml, cover_xml, store, volume))


def response(issues, total=None):
    if total is None:
        total = len(issues)
    xml = ('<?xml version="1.0"?><response><number_of_total_results>%d</number_of_total_results>'
           '<results>%s</results></response>' % (total, ''.join(issues)))
    return parseString(xml)
