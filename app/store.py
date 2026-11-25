import os
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


def _path():
    return Path(os.getenv("NEURAVALE_DB", "./data/neuravale.sqlite3"))


@contextmanager
def connect():
    path = _path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def initialize():
    with connect() as db:
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("CREATE TABLE IF NOT EXISTS conversations (id TEXT PRIMARY KEY, title TEXT NOT NULL, created_at TEXT NOT NULL)")
        db.execute("CREATE TABLE IF NOT EXISTS messages (id TEXT PRIMARY KEY, conversation_id TEXT NOT NULL, role TEXT NOT NULL, content TEXT NOT NULL, created_at TEXT NOT NULL, FOREIGN KEY(conversation_id) REFERENCES conversations(id))")
        db.execute("CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(conversation_id, created_at)")


def create_conversation(title):
    conversation_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    with connect() as db:
        db.execute("INSERT INTO conversations VALUES (?, ?, ?)", (conversation_id, title[:90], now))
    return conversation_id


def conversation_exists(conversation_id):
    with connect() as db:
        return db.execute("SELECT 1 FROM conversations WHERE id=?", (conversation_id,)).fetchone() is not None


def append_message(conversation_id, role, content):
    with connect() as db:
        db.execute("INSERT INTO messages VALUES (?, ?, ?, ?, ?)", (str(uuid.uuid4()), conversation_id, role, content, datetime.now(timezone.utc).isoformat()))


def messages(conversation_id):
    with connect() as db:
        return [dict(row) for row in db.execute("SELECT role, content, created_at FROM messages WHERE conversation_id=? ORDER BY created_at, rowid", (conversation_id,))]


def list_conversations():
    with connect() as db:
        return [dict(row) for row in db.execute("SELECT * FROM conversations ORDER BY created_at DESC LIMIT 100")]
