"""SQLite cache for summaries and their source metadata."""

import sqlite3
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CacheContext:
    """Identify the source and generation details associated with a cache value."""

    path: Path | None = None
    model: str | None = None
    part: str = ''


class Cache:
    """Store reusable extraction and summary results in SQLite."""

    def __init__(self, path: Path):
        """Open or initialize the cache database at *path*."""
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute(
            'CREATE TABLE IF NOT EXISTS results '
            '(stage TEXT NOT NULL, key TEXT NOT NULL, value TEXT NOT NULL, '
            'PRIMARY KEY(stage,key))'
        )
        # A content-based result can be reused by multiple source paths.
        self.db.execute('''CREATE TABLE IF NOT EXISTS cache_contexts (
            stage TEXT NOT NULL, key TEXT NOT NULL, path TEXT NOT NULL,
            filename TEXT NOT NULL, model TEXT NOT NULL, part TEXT NOT NULL,
            PRIMARY KEY(stage, key, path, model, part),
            FOREIGN KEY(stage, key) REFERENCES results(stage, key)
        )''')
        self.db.execute('''CREATE VIEW IF NOT EXISTS cache_entries AS
            SELECT r.stage, r.key, c.path, c.filename,
                   NULLIF(c.model, '') AS model, NULLIF(c.part, '') AS part, r.value
            FROM results AS r LEFT JOIN cache_contexts AS c
            ON r.stage = c.stage AND r.key = c.key''')
        self.db.commit()

    def _record_context(self, stage: str, key: str, context: CacheContext) -> None:
        """Associate a result with the source that produced or reused it."""
        if context.path is not None:
            source = Path(context.path).expanduser().resolve()
            self.db.execute('''INSERT OR IGNORE INTO cache_contexts
                (stage, key, path, filename, model, part) VALUES (?, ?, ?, ?, ?, ?)''',
                (stage, key, str(source), source.name, context.model or '', context.part))

    def get(self, stage: str, key: str, *,
            context: CacheContext = CacheContext()) -> str | None:
        """Return a cached value and record source metadata on a cache hit."""
        query = 'SELECT value FROM results WHERE stage=? AND key=?'
        row = self.db.execute(query, (stage, key)).fetchone()
        if row is not None and context.path is not None:
            self._record_context(stage, key, context)
            self.db.commit()
        return row[0] if row else None

    def put(self, stage: str, key: str, value: str, *,
            context: CacheContext = CacheContext()) -> None:
        """Store a value, optionally recording its source metadata."""
        self.db.execute('''INSERT INTO results(stage,key,value) VALUES(?,?,?)
            ON CONFLICT(stage,key) DO UPDATE SET value=excluded.value''', (stage, key, value))
        self._record_context(stage, key, context)
        self.db.commit()

    def close(self):
        """Close the underlying SQLite connection."""
        self.db.close()
