"""SQLite storage for everything that belongs to a user.

Course content lives in files (see content.py); the database only references
it by subject slug + stable item id, so content can be extended freely.
"""
import sqlite3
from datetime import datetime, timezone

from flask import current_app, g

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    username TEXT NOT NULL UNIQUE COLLATE NOCASE,
    password_hash TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS login_failures (
    username TEXT NOT NULL COLLATE NOCASE,
    at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_login_failures ON login_failures (username, at);

CREATE TABLE IF NOT EXISTS item_progress (
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    subject TEXT NOT NULL,
    kind TEXT NOT NULL,
    item_id TEXT NOT NULL,
    correct_count INTEGER NOT NULL DEFAULT 0,
    wrong_count INTEGER NOT NULL DEFAULT 0,
    last_correct INTEGER NOT NULL DEFAULT 0,
    box INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (user_id, subject, kind, item_id)
);
CREATE TABLE IF NOT EXISTS attempts (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    subject TEXT NOT NULL,
    kind TEXT NOT NULL,
    score INTEGER NOT NULL,
    total INTEGER NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_attempts ON attempts (user_id, subject, created_at);

CREATE TABLE IF NOT EXISTS open_answers (
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    subject TEXT NOT NULL,
    question_id TEXT NOT NULL,
    answer TEXT NOT NULL,
    checked TEXT NOT NULL DEFAULT '[]',
    updated_at TEXT NOT NULL,
    PRIMARY KEY (user_id, subject, question_id)
);
CREATE TABLE IF NOT EXISTS highlights (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    subject TEXT NOT NULL,
    article TEXT NOT NULL,
    start_offset INTEGER NOT NULL,
    end_offset INTEGER NOT NULL,
    quote TEXT NOT NULL,
    color TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_highlights ON highlights (user_id, subject, article);

CREATE TABLE IF NOT EXISTS notes (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    subject TEXT NOT NULL,
    article TEXT,
    title TEXT NOT NULL,
    body TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_notes ON notes (user_id, subject, updated_at);
"""


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _connect(path):
    # No WAL mode: PythonAnywhere stores files on a network filesystem.
    conn = sqlite3.connect(path, timeout=20)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def get():
    if "db" not in g:
        g.db = _connect(current_app.config["DATABASE"])
    return g.db


def _close(_exc=None):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


def init_app(app):
    conn = _connect(app.config["DATABASE"])
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()
    app.teardown_appcontext(_close)


def progress_map(user_id, subject, kind):
    rows = get().execute(
        "SELECT * FROM item_progress WHERE user_id=? AND subject=? AND kind=?",
        (user_id, subject, kind),
    )
    return {r["item_id"]: r for r in rows}


def mastered_counts(user_id, subject):
    rows = get().execute(
        "SELECT kind, item_id FROM item_progress"
        " WHERE user_id=? AND subject=? AND last_correct=1",
        (user_id, subject),
    )
    result = {}
    for r in rows:
        result.setdefault(r["kind"], set()).add(r["item_id"])
    return result


def record_results(user_id, subject, kind, results):
    """results: iterable of (item_id, correct)."""
    conn = get()
    stamp = now()
    for item_id, correct in results:
        good = 1 if correct else 0
        conn.execute(
            """INSERT INTO item_progress
               (user_id, subject, kind, item_id, correct_count, wrong_count,
                last_correct, box, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?)
               ON CONFLICT (user_id, subject, kind, item_id) DO UPDATE SET
                 correct_count = correct_count + excluded.correct_count,
                 wrong_count = wrong_count + excluded.wrong_count,
                 last_correct = excluded.last_correct,
                 box = CASE WHEN excluded.last_correct = 1
                            THEN MIN(box + 1, 5) ELSE 0 END,
                 updated_at = excluded.updated_at""",
            (user_id, subject, kind, item_id, good, 1 - good, good, good, stamp),
        )
    conn.commit()


def add_attempt(user_id, subject, kind, score, total):
    conn = get()
    conn.execute(
        "INSERT INTO attempts (user_id, subject, kind, score, total, created_at)"
        " VALUES (?,?,?,?,?,?)",
        (user_id, subject, kind, score, total, now()),
    )
    conn.commit()
