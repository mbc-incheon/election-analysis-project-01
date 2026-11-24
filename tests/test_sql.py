"""SQL deliverables must work with the real service and preserve review gates."""
import importlib.util
import json
import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'election-news-server'))
from core import Newsroom, sha

spec = importlib.util.spec_from_file_location('db_initializer', ROOT / 'scripts/init_db.py')
initializer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(initializer)


def test_schema_and_seed_roundtrip(tmp_path):
    assert (ROOT / 'db/001_schema.sql').read_bytes() == (ROOT / 'election-news-server/schema.sql').read_bytes()
    counts = initializer.initialize(tmp_path / 'news.sqlite', demo=True)
    assert counts == {'snapshot': 1, 'chunk': 6, 'article': 1, 'approval': 0, 'audit': 8}
    room = Newsroom(tmp_path)
    try:
        article = room.get('SQL-DEMO-ARTICLE-001')
        assert article['status'] == 'DRAFT'
        assert room.validate(article)['status'] == 'PENDING_HUMAN'
        with pytest.raises(ValueError):
            room.export(article['id'])
        previous = '0' * 64
        for prev, digest, payload in room.db.execute('SELECT previous_hash,hash,payload FROM audit ORDER BY id'):
            assert prev == previous
            assert digest == sha([prev, json.loads(payload)])
            previous = digest
        assert list(room.db.execute('PRAGMA foreign_key_check')) == []
        with pytest.raises(sqlite3.IntegrityError):
            room.db.execute('UPDATE audit SET hash=?', ('x',))
    finally:
        room.db.close()


def test_demo_init_preserves_existing_records(tmp_path):
    path = tmp_path / 'news.sqlite'
    initializer.initialize(path, demo=True)
    before = path.read_bytes()
    with pytest.raises(ValueError, match='contains records'):
        initializer.initialize(path, demo=True)
    assert path.read_bytes() == before


def test_empty_schema_and_approval_fk(tmp_path):
    path = tmp_path / 'news.sqlite'
    assert all(count == 0 for count in initializer.initialize(path).values())
    with sqlite3.connect(path) as db:
        db.execute('PRAGMA foreign_keys=ON')
        with pytest.raises(sqlite3.IntegrityError):
            db.execute("INSERT INTO approval(article_id,reviewer,reason,created_at) VALUES('missing','TEST','TEST','2026-11-24')")
