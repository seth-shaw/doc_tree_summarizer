"""Tests for cache storage and source metadata."""

import sqlite3

from summarizer.cache import Cache


def test_readable_metadata_and_shared_keys(tmp_path):
    """Verify cache keys can retain multiple readable source contexts."""
    cache = Cache(tmp_path / 'cache.sqlite3')
    first = tmp_path / 'first' / 'notes.txt'
    second = tmp_path / 'second' / 'copy.txt'
    try:
        cache.put('document', 'shared-key', 'summary', path=first,
                  model='test-model', part='chunk 1/1')
        assert cache.get('document', 'shared-key', path=second,
                         model='test-model', part='chunk 1/1') == 'summary'
        # Repeated hits do not duplicate provenance.
        cache.get('document', 'shared-key', path=second, model='test-model', part='chunk 1/1')
        rows = cache.db.execute(
            'SELECT path, filename, model, part FROM cache_entries ORDER BY path').fetchall()
        assert rows == [(str(first), 'notes.txt', 'test-model', 'chunk 1/1'),
                        (str(second), 'copy.txt', 'test-model', 'chunk 1/1')]
        assert cache.db.execute('SELECT count(*) FROM results').fetchone()[0] == 1
        # Replacing a value preserves every source association.
        cache.put('document', 'shared-key', 'updated')
        assert cache.db.execute('SELECT count(*) FROM cache_entries').fetchone()[0] == 2
        assert cache.get('document', 'shared-key') == 'updated'
    finally:
        cache.close()


def test_legacy_database_is_preserved_and_backfilled(tmp_path):
    """Verify older cache databases are upgraded safely."""
    database = tmp_path / 'old.sqlite3'
    with sqlite3.connect(database) as connection:
        connection.execute(
            'CREATE TABLE results (stage TEXT NOT NULL, key TEXT NOT NULL, '
            'value TEXT NOT NULL, PRIMARY KEY(stage,key))')
        connection.execute("INSERT INTO results VALUES ('extraction', 'old-key', 'extracted text')")
    cache = Cache(database)
    try:
        assert cache.db.execute('SELECT path, model FROM cache_entries').fetchone() == (None, None)
        source = tmp_path / 'old.txt'
        assert cache.get('extraction', 'old-key', path=source) == 'extracted text'
        row = cache.db.execute(
            'SELECT path, filename, model, part FROM cache_entries').fetchone()
        assert row == (
            str(source), 'old.txt', None, None)
        assert cache.get('document', 'missing', path=source, model='test-model') is None
        assert cache.db.execute('SELECT count(*) FROM cache_contexts').fetchone()[0] == 1
    finally:
        cache.close()
    # Opening an upgraded database again is safe and preserves metadata.
    cache = Cache(database)
    try:
        assert cache.db.execute('SELECT filename FROM cache_entries').fetchone()[0] == 'old.txt'
    finally:
        cache.close()
