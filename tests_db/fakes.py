"""Fake HTTP responses for the DDL host downloaders (Pixeldrain, MediaFire): no network."""
import io
import os
import zipfile

import requests


def make_zip(n_files=50, size=60000):
    """A valid stored ZIP of about n_files * size bytes."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_STORED) as zf:
        for i in range(n_files):
            zf.writestr('p%03d.jpg' % i, os.urandom(size))
    return buf.getvalue()


class FakeResponse(object):
    """Enough of requests.Response for the downloaders: status, headers, url, iter_content, json."""

    def __init__(self, status=200, body=b'', headers=None, url='', truncate_at=None, json_data=None, raise_exc=None):
        self.status_code = status
        self.body = body
        self.headers = requests.structures.CaseInsensitiveDict(headers or {})
        self.url = url
        self.truncate_at = truncate_at
        self._json = json_data
        self.raise_exc = raise_exc

    def iter_content(self, chunk_size=1):
        data = self.body if self.truncate_at is None else self.body[:self.truncate_at]
        for i in range(0, len(data), chunk_size):
            yield data[i:i + chunk_size]

    def close(self):
        pass

    def json(self):
        return self._json

    @property
    def text(self):
        return self.body.decode('latin-1')


def install_router(monkeypatch, route):
    """Route every requests.Session.get(url, headers=...) through route(url, headers) -> FakeResponse."""
    calls = []

    def get(session, url, **kwargs):
        headers = dict(kwargs.get('headers') or {})
        calls.append((url, headers))
        return route(url, headers)

    monkeypatch.setattr(requests.Session, 'get', get)
    return calls


def pixeldrain_route(body, status=200, truncate_at=None, name='Batman 001 (2025).cbz', size=None):
    """Pixeldrain: /u/<id> page, /api/file/<id>/info JSON and the file itself at /api/file/<id>."""
    info = {'availability': '', 'name': name, 'size': len(body) if size is None else size, 'can_download': True}

    def route(url, headers):
        if url.endswith('/info'):
            return FakeResponse(200, url=url, json_data=info)
        if '/api/file/' in url:
            return FakeResponse(status, body, {'Content-Length': str(len(body))}, url=url, truncate_at=truncate_at)
        return FakeResponse(200, b'<html/>', url=url)
    return route


def mediafire_route(body, status=200, truncate_at=None, name='Batman 001 (2025).cbz'):
    """MediaFire: the download link answers with Content-Disposition and the file."""
    def route(url, headers):
        return FakeResponse(status, body, {'Content-Length': str(len(body)),
                                           'Content-Disposition': 'attachment; filename="%s"' % name},
                            url=url, truncate_at=truncate_at)
    return route
