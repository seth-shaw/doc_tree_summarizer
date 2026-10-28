import sqlite3
from pathlib import Path


class Cache:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('CREATE TABLE IF NOT EXISTS results (stage TEXT NOT NULL, key TEXT NOT NULL, value TEXT NOT NULL, PRIMARY KEY(stage,key))')
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

    def _record_context(self, stage: str, key: str, path: Path | None, model: str | None, part: str):
        if path is not None:
            source = Path(path).expanduser().resolve()
            self.db.execute('''INSERT OR IGNORE INTO cache_contexts
                (stage, key, path, filename, model, part) VALUES (?, ?, ?, ?, ?, ?)''',
                (stage, key, str(source), source.name, model or '', part))

    def get(self, stage: str, key: str, *, path: Path | None = None,
            model: str | None = None, part: str = '') -> str | None:
        row = self.db.execute('SELECT value FROM results WHERE stage=? AND key=?', (stage, key)).fetchone()
        if row is not None and path is not None:
            self._record_context(stage, key, path, model, part)
            self.db.commit()
        return row[0] if row else None

    def put(self, stage: str, key: str, value: str, *, path: Path | None = None,
            model: str | None = None, part: str = '') -> None:
        self.db.execute('''INSERT INTO results(stage,key,value) VALUES(?,?,?)
            ON CONFLICT(stage,key) DO UPDATE SET value=excluded.value''', (stage, key, value))
        self._record_context(stage, key, path, model, part)
        self.db.commit()

    def close(self):
        self.db.close()
