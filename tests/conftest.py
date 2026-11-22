"""Load mylar/getcomics.py without starting Mylar.

Importing the ``mylar`` package runs mylar/__init__.py (scheduler, config, every provider
module). The parser only needs a few globals, so the tests put a stub ``mylar`` package
into sys.modules whose ``__path__`` points at the real sources, plus stub ``db``,
``logger``, ``helpers`` and ``search_filer`` modules. No network, no database.
"""
import importlib.util
import os
import sys
import types

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURES = os.path.join(REPO, 'tests', 'fixtures', 'getcomics')


class _Config(object):
    CACHE_DIR = None
    SECURE_DIR = None
    DDL_PRIORITY_ORDER = ['main', 'pixeldrain', 'mediafire']
    DDL_PREFER_UPSCALED = False
    PACK_PRIORITY = False
    ENABLE_PROXY = False
    ENABLE_FLARESOLVERR = False
    DDL_QUERY_DELAY = 0


class _Queue(object):
    def __init__(self):
        self.items = []

    def put(self, item):
        self.items.append(item)

    def qsize(self):
        return len(self.items)


class _Logger(types.ModuleType):
    def __getattr__(self, name):
        return lambda *args, **kwargs: None


class _Result(object):
    def __init__(self, row):
        self.row = row

    def fetchone(self):
        return self.row


class _DB(object):
    upserts = []
    rows = {}  # ddl_info rows by ID, e.g. {'1-1': {'status': 'Downloading'}}

    def upsert(self, table, vals, ctrl):
        _DB.upserts.append((table, dict(vals), dict(ctrl)))

    def selectone(self, query, args=None):
        return _Result(_DB.rows.get(str(args[0])) if args else None)


def _install_stubs():
    if 'mylar.getcomics' in sys.modules:
        return sys.modules['mylar.getcomics']
    mylar = types.ModuleType('mylar')
    mylar.__path__ = [os.path.join(REPO, 'mylar')]
    mylar.CONFIG = _Config
    mylar.GC_URL = 'https://getcomics.org'
    mylar.DDL_QUEUE = _Queue()
    db = types.ModuleType('mylar.db')
    db.DBConnection = _DB
    logger = _Logger('mylar.logger')
    helpers = types.ModuleType('mylar.helpers')
    search_filer = types.ModuleType('mylar.search_filer')
    mylar.db, mylar.logger, mylar.helpers, mylar.search_filer = db, logger, helpers, search_filer
    sys.modules.update({
        'mylar': mylar,
        'mylar.db': db,
        'mylar.logger': logger,
        'mylar.helpers': helpers,
        'mylar.search_filer': search_filer,
    })
    spec = importlib.util.spec_from_file_location(
        'mylar.getcomics', os.path.join(REPO, 'mylar', 'getcomics.py')
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules['mylar.getcomics'] = module
    spec.loader.exec_module(module)
    mylar.getcomics = module
    return module


GC_MODULE = _install_stubs()


def read_fixture(name):
    with open(os.path.join(FIXTURES, name), encoding='utf-8') as fh:
        return fh.read()


@pytest.fixture
def gc_env(tmp_path):
    """Fresh queue, DB log and config for one test; html cache in tmp_path."""
    mylar = sys.modules['mylar']
    mylar.DDL_QUEUE = _Queue()
    _DB.upserts = []
    _DB.rows = {}
    _Config.CACHE_DIR = str(tmp_path)
    _Config.SECURE_DIR = str(tmp_path)
    _Config.DDL_PRIORITY_ORDER = ['main', 'pixeldrain', 'mediafire']
    _Config.DDL_PREFER_UPSCALED = False
    _Config.PACK_PRIORITY = False
    return types.SimpleNamespace(module=GC_MODULE, mylar=mylar, config=_Config, db=_DB)


@pytest.fixture
def gc_parse():
    return sys.modules['mylar.getcomics_parse']
