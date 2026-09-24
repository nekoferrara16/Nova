"""SQLite storage. Money is always persisted as integer cents."""
import sqlite3
from contextlib import contextmanager
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
 id INTEGER PRIMARY KEY, username TEXT NOT NULL UNIQUE COLLATE NOCASE,
 password_hash TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS sessions (
 token_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 csrf TEXT NOT NULL, expires_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS accounts (
 id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id),
 name TEXT NOT NULL, institution TEXT NOT NULL DEFAULT '', kind TEXT NOT NULL,
 opening_cents INTEGER NOT NULL, opening_date TEXT NOT NULL,
 UNIQUE(user_id, name)
);
CREATE TABLE IF NOT EXISTS transactions (
 id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id),
 account_id INTEGER NOT NULL REFERENCES accounts(id), date TEXT NOT NULL,
 description TEXT NOT NULL, amount_cents INTEGER NOT NULL,
 category TEXT NOT NULL, kind TEXT NOT NULL, source TEXT NOT NULL DEFAULT 'manual',
 fingerprint TEXT, transfer_group TEXT,
 UNIQUE(user_id, account_id, fingerprint)
);
CREATE INDEX IF NOT EXISTS transactions_user_date ON transactions(user_id, date);
CREATE TABLE IF NOT EXISTS budgets (
 user_id INTEGER NOT NULL REFERENCES users(id), month TEXT NOT NULL,
 category TEXT NOT NULL, limit_cents INTEGER NOT NULL,
 PRIMARY KEY(user_id, month, category)
);
CREATE TABLE IF NOT EXISTS import_drafts (
 id TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id),
 account_id INTEGER NOT NULL REFERENCES accounts(id), payload TEXT NOT NULL,
 expires_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS login_attempts (
 key TEXT PRIMARY KEY, attempts INTEGER NOT NULL, window_start INTEGER NOT NULL
);
"""


class Store:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript(SCHEMA)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys = ON')
        try:
            with db:
                yield db
        finally:
            db.close()
