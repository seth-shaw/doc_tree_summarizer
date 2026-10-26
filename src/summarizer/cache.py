import sqlite3
from pathlib import Path

class Cache:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('CREATE TABLE IF NOT EXISTS results (stage TEXT NOT NULL, key TEXT NOT NULL, value TEXT NOT NULL, PRIMARY KEY(stage,key))')
        self.db.commit()

    def get(self, stage: str, key: str) -> str | None:
        row = self.db.execute('SELECT value FROM results WHERE stage=? AND key=?', (stage, key)).fetchone()
        return row[0] if row else None

    def put(self, stage: str, key: str, value: str) -> None:
        self.db.execute('INSERT OR REPLACE INTO results(stage,key,value) VALUES(?,?,?)', (stage, key, value))
        self.db.commit()

    def close(self):
        self.db.close()
