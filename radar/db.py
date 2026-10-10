"""Agentic Radar — persistent memory for the daily digest.

Tables:
  items        raw collected news items (one row per story)
  digests      generated daily insight reports
  links        connections the digest drew between items across time
  reflections  post-digest critiques from the reflection job
"""
from __future__ import annotations

import os
import sqlite3

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "data", "radar.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS items (
    id INTEGER PRIMARY KEY,
    day TEXT NOT NULL,            -- YYYY-MM-DD the item was collected
    beat TEXT NOT NULL,           -- e.g. 'claude-code', 'openai', 'kimi'
    title TEXT NOT NULL,
    url TEXT,
    summary TEXT,
    date_published TEXT,           -- YYYY-MM-DD of the story's publication, when known
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS digests (
    id INTEGER PRIMARY KEY,
    day TEXT UNIQUE NOT NULL,
    markdown TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS links (
    id INTEGER PRIMARY KEY,
    day TEXT NOT NULL,            -- digest day that drew the link
    item_a INTEGER NOT NULL,
    item_b INTEGER NOT NULL,
    relation TEXT NOT NULL,       -- e.g. 'follows-up', 'contradicts', 'same-trend'
    note TEXT
);
CREATE TABLE IF NOT EXISTS reflections (
    id INTEGER PRIMARY KEY,
    day TEXT NOT NULL,
    markdown TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_items_day ON items(day);
CREATE INDEX IF NOT EXISTS idx_items_beat ON items(beat);
"""


def connect() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA)
    return conn


def add_item(day: str, beat: str, title: str, url: str = "", summary: str = "",
           date_published: str | None = None) -> int:
    conn = connect()
    cur = conn.execute(
        "INSERT INTO items (day, beat, title, url, summary, date_published) VALUES (?,?,?,?,?,?)",
        (day, beat, title, url, summary, date_published))
    conn.commit()
    item_id = cur.lastrowid
    conn.close()
    return item_id


def set_date_published(item_id: int, date_published: str | None) -> None:
    conn = connect()
    conn.execute("UPDATE items SET date_published=? WHERE id=?",
                 (date_published, item_id))
    conn.commit()
    conn.close()


def items_on(day: str) -> list[dict]:
    conn = connect()
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM items WHERE day=? ORDER BY beat, id",
                        (day,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def search_history(query: str, limit: int = 20) -> list[dict]:
    """Keyword search over past items — the 'two months ago' lookup."""
    conn = connect()
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """SELECT * FROM items
           WHERE title LIKE ? OR summary LIKE ?
           ORDER BY day DESC LIMIT ?""",
        (f"%{query}%", f"%{query}%", limit)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def recent_days(n: int = 7) -> list[str]:
    conn = connect()
    rows = conn.execute(
        "SELECT DISTINCT day FROM items ORDER BY day DESC LIMIT ?", (n,)).fetchall()
    conn.close()
    return [r[0] for r in rows]


def save_digest(day: str, markdown: str) -> None:
    conn = connect()
    conn.execute("INSERT OR REPLACE INTO digests (day, markdown) VALUES (?,?)",
                 (day, markdown))
    conn.commit()
    conn.close()


def add_link(day: str, a: int, b: int, relation: str, note: str = "") -> None:
    conn = connect()
    conn.execute(
        "INSERT INTO links (day, item_a, item_b, relation, note) VALUES (?,?,?,?,?)",
        (day, a, b, relation, note))
    conn.commit()
    conn.close()


def save_reflection(day: str, markdown: str) -> None:
    conn = connect()
    conn.execute("INSERT INTO reflections (day, markdown) VALUES (?,?)", (day, markdown))
    conn.commit()
    conn.close()


def get_digest(day: str) -> str | None:
    conn = connect()
    row = conn.execute("SELECT markdown FROM digests WHERE day=?", (day,)).fetchone()
    conn.close()
    return row[0] if row else None
