"""
Pulse DB — SQLite enrichment layer.
Single source of truth for all database operations.
DB file: backend/pulse.db (created automatically on init_db()).
"""

import json
import os
import re
import sqlite3
from datetime import datetime, timezone
from typing import Optional

DB_PATH = os.environ.get(
    'PULSE_DB_PATH',
    os.path.join(os.path.dirname(__file__), 'pulse.db')
)

VALID_STATUSES = {'unread', 'want_to_read', 'in_progress', 'done', 'skipped'}

_SCHEMA = """
CREATE TABLE IF NOT EXISTS content_status (
  entry_id   TEXT PRIMARY KEY,
  person_id  TEXT NOT NULL,
  platform   TEXT NOT NULL,
  status     TEXT NOT NULL DEFAULT 'unread',
  updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_status_person ON content_status(person_id);
CREATE INDEX IF NOT EXISTS idx_status_status ON content_status(status);

CREATE TABLE IF NOT EXISTS notes (
  entry_id    TEXT PRIMARY KEY,
  person_id   TEXT NOT NULL,
  manual_note TEXT,
  ai_note     TEXT,
  updated_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_notes_person ON notes(person_id);

CREATE TABLE IF NOT EXISTS calibre_links (
  entry_id      TEXT PRIMARY KEY,
  person_id     TEXT NOT NULL,
  calibre_id    INTEGER NOT NULL,
  calibre_title TEXT NOT NULL,
  formats       TEXT NOT NULL,
  content_type  TEXT NOT NULL,
  pushed_at     TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_calibre_person ON calibre_links(person_id);

CREATE TABLE IF NOT EXISTS episodes (
  id                TEXT PRIMARY KEY,
  person_id         TEXT NOT NULL,
  person_name       TEXT NOT NULL,
  platform          TEXT NOT NULL,
  title             TEXT NOT NULL,
  link              TEXT NOT NULL,
  description       TEXT,
  date              TEXT,
  duration_sec      INTEGER,
  episode_number    INTEGER,
  itunes_episode_id TEXT,
  synced_at         TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_episodes_person ON episodes(person_id);
CREATE INDEX IF NOT EXISTS idx_episodes_date   ON episodes(date);

CREATE TABLE IF NOT EXISTS guests (
  id        INTEGER PRIMARY KEY AUTOINCREMENT,
  name      TEXT NOT NULL UNIQUE,
  slug      TEXT NOT NULL UNIQUE,
  aliases   TEXT,
  person_id TEXT
);
CREATE INDEX IF NOT EXISTS idx_guests_slug ON guests(slug);

CREATE TABLE IF NOT EXISTS episode_guests (
  episode_id TEXT    NOT NULL REFERENCES episodes(id) ON DELETE CASCADE,
  guest_id   INTEGER NOT NULL REFERENCES guests(id)   ON DELETE CASCADE,
  source     TEXT    NOT NULL,
  PRIMARY KEY (episode_id, guest_id)
);
CREATE INDEX IF NOT EXISTS idx_epguests_guest ON episode_guests(guest_id);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_db(path: str = DB_PATH) -> sqlite3.Connection:
    """Return a connection with Row factory and FK enforcement on."""
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    return conn


def init_db(path: str = DB_PATH) -> None:
    """Create all tables if they don't exist. Safe to call on every startup."""
    with get_db(path) as conn:
        conn.executescript(_SCHEMA)


# ── Status ────────────────────────────────────────────────────────────────────

def get_status(entry_id: str, path: str = DB_PATH) -> str:
    """Return status for entry_id, defaulting to 'unread' if not set."""
    with get_db(path) as conn:
        row = conn.execute(
            'SELECT status FROM content_status WHERE entry_id = ?', (entry_id,)
        ).fetchone()
    return row['status'] if row else 'unread'


def set_status(entry_id: str, person_id: str, platform: str,
               status: str, path: str = DB_PATH) -> None:
    """Upsert status. Raises ValueError for invalid status values."""
    if status not in VALID_STATUSES:
        raise ValueError(f'Invalid status: {status!r}. Must be one of {VALID_STATUSES}')
    with get_db(path) as conn:
        conn.execute("""
            INSERT INTO content_status (entry_id, person_id, platform, status, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(entry_id) DO UPDATE SET status=excluded.status, updated_at=excluded.updated_at
        """, (entry_id, person_id, platform, status, _now()))


def get_person_statuses(person_id: str, path: str = DB_PATH) -> dict:
    """Return {entry_id: status} for all entries belonging to person_id."""
    with get_db(path) as conn:
        rows = conn.execute(
            'SELECT entry_id, status FROM content_status WHERE person_id = ?',
            (person_id,)
        ).fetchall()
    return {r['entry_id']: r['status'] for r in rows}


# ── Notes ─────────────────────────────────────────────────────────────────────

def get_notes(entry_id: str, path: str = DB_PATH) -> dict:
    """Return {manual_note, ai_note, updated_at} for entry_id."""
    with get_db(path) as conn:
        row = conn.execute(
            'SELECT manual_note, ai_note, updated_at FROM notes WHERE entry_id = ?',
            (entry_id,)
        ).fetchone()
    if not row:
        return {'manual_note': None, 'ai_note': None, 'updated_at': None}
    return dict(row)


def set_notes(entry_id: str, person_id: str,
              manual_note: Optional[str] = None,
              ai_note: Optional[str] = None,
              path: str = DB_PATH) -> None:
    """Upsert notes. Only updates the fields that are explicitly passed (not None)."""
    with get_db(path) as conn:
        existing = conn.execute(
            'SELECT manual_note, ai_note FROM notes WHERE entry_id = ?', (entry_id,)
        ).fetchone()
        if existing:
            new_manual = manual_note if manual_note is not None else existing['manual_note']
            new_ai     = ai_note     if ai_note     is not None else existing['ai_note']
            conn.execute(
                'UPDATE notes SET manual_note=?, ai_note=?, updated_at=? WHERE entry_id=?',
                (new_manual, new_ai, _now(), entry_id)
            )
        else:
            conn.execute(
                'INSERT INTO notes (entry_id, person_id, manual_note, ai_note, updated_at) VALUES (?,?,?,?,?)',
                (entry_id, person_id, manual_note, ai_note, _now())
            )


def migrate_notes(legacy: dict, path: str = DB_PATH) -> int:
    """
    Migrate pw-notes from localStorage. legacy is {entry_id: note_string}.
    Skips entries that already have a row in the notes table.
    Returns count of rows inserted.
    """
    count = 0
    with get_db(path) as conn:
        for entry_id, note_text in legacy.items():
            existing = conn.execute(
                'SELECT 1 FROM notes WHERE entry_id = ?', (entry_id,)
            ).fetchone()
            if existing:
                continue
            conn.execute(
                'INSERT INTO notes (entry_id, person_id, manual_note, ai_note, updated_at) VALUES (?,?,?,?,?)',
                (entry_id, 'unknown', note_text, None, _now())
            )
            count += 1
    return count
