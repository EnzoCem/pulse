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


# ── Calibre links ─────────────────────────────────────────────────────────────

def get_calibre_link(entry_id: str, path: str = DB_PATH) -> Optional[dict]:
    """Return calibre link record for entry_id, or None."""
    with get_db(path) as conn:
        row = conn.execute(
            'SELECT * FROM calibre_links WHERE entry_id = ?', (entry_id,)
        ).fetchone()
    return dict(row) if row else None


def set_calibre_link(entry_id: str, person_id: str, calibre_id: int,
                     calibre_title: str, formats: list, content_type: str,
                     path: str = DB_PATH) -> None:
    """Upsert a calibre link record."""
    with get_db(path) as conn:
        conn.execute("""
            INSERT INTO calibre_links
              (entry_id, person_id, calibre_id, calibre_title, formats, content_type, pushed_at)
            VALUES (?,?,?,?,?,?,?)
            ON CONFLICT(entry_id) DO UPDATE SET
              calibre_id=excluded.calibre_id, calibre_title=excluded.calibre_title,
              formats=excluded.formats, pushed_at=excluded.pushed_at
        """, (entry_id, person_id, calibre_id, calibre_title,
              json.dumps(formats), content_type, _now()))


def get_person_calibre_links(person_id: str, path: str = DB_PATH) -> dict:
    """Return {entry_id: {calibre_id, formats, content_type}} for a person."""
    with get_db(path) as conn:
        rows = conn.execute(
            'SELECT entry_id, calibre_id, formats, content_type FROM calibre_links WHERE person_id = ?',
            (person_id,)
        ).fetchall()
    return {r['entry_id']: {'calibre_id': r['calibre_id'],
                             'formats': json.loads(r['formats']),
                             'content_type': r['content_type']}
            for r in rows}


# ── Episodes ──────────────────────────────────────────────────────────────────

def upsert_episodes(episodes: list, path: str = DB_PATH) -> None:
    """Bulk upsert episode records. Each item is a dict matching the episodes schema."""
    now = _now()
    with get_db(path) as conn:
        for ep in episodes:
            conn.execute("""
                INSERT INTO episodes
                  (id, person_id, person_name, platform, title, link,
                   description, date, duration_sec, episode_number, itunes_episode_id, synced_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(id) DO UPDATE SET
                  title=excluded.title, description=excluded.description,
                  duration_sec=excluded.duration_sec, episode_number=excluded.episode_number,
                  synced_at=excluded.synced_at
            """, (ep['id'], ep['person_id'], ep['person_name'], ep['platform'],
                  ep['title'], ep['link'], ep.get('description'), ep.get('date'),
                  ep.get('duration_sec'), ep.get('episode_number'),
                  ep.get('itunes_episode_id'), now))


def get_episodes(person_id: str, limit: int = 50, offset: int = 0,
                 sort: str = 'date_desc', db_path: str = DB_PATH) -> dict:
    """Return paginated episodes for a person with total count."""
    order = 'date DESC' if sort == 'date_desc' else 'date ASC'
    with get_db(db_path) as conn:
        total = conn.execute(
            'SELECT COUNT(*) FROM episodes WHERE person_id = ?', (person_id,)
        ).fetchone()[0]
        rows = conn.execute(
            f'SELECT * FROM episodes WHERE person_id = ? ORDER BY {order} LIMIT ? OFFSET ?',
            (person_id, limit, offset)
        ).fetchall()
    return {'episodes': [dict(r) for r in rows], 'total': total}


# ── Guests ────────────────────────────────────────────────────────────────────

def name_to_slug(name: str) -> str:
    """Convert 'Elon Musk' → 'elon-musk'."""
    return re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')


def extract_guests_from_title(title: str) -> list:
    """
    Heuristic guest extraction from episode title.
    Looks for patterns like: 'Episode Title | Guest Name' or 'Guest Name — Topic'.
    Returns list of guest name strings (may be empty).
    """
    # Pattern: guest name between em-dash and pipe: "#431 — Elon Musk | Topic"
    between_m = re.search(r'[–—]\s+(.+?)\s*\|', title)
    if between_m:
        candidate = between_m.group(1).strip()
        words = candidate.split()
        if 1 <= len(words) <= 4 and re.match(r'^[A-Z]', candidate) and not candidate.startswith('http'):
            return [candidate]

    # Patterns where guest name comes AFTER the separator
    after_patterns = [
        r'\s*\|\s*(.+)',           # "Ep 431 | Elon Musk"
        r'\s+feat(?:uring)?\.?\s+(.+)',  # "Ep featuring Elon Musk"
        r'\s+with\s+([A-Z][^|]+)',  # "Conversation with Elon Musk"
    ]
    # Patterns where guest name comes BEFORE the separator
    before_patterns = [
        r'^(.+?)\s+[–—]\s+[A-Z]',  # "Elon Musk — Tesla and SpaceX" (guest first)
    ]

    for pattern in after_patterns:
        m = re.search(pattern, title, re.IGNORECASE)
        if m:
            guest_part = m.group(1).strip()
            # Split multiple guests on comma or &
            candidates = [g.strip() for g in re.split(r',\s*|\s+&\s+|\s+and\s+', guest_part)]
            # Keep only plausible names: 2–40 chars, starts with uppercase, no URL
            guests = [g for g in candidates
                      if 2 < len(g) <= 40
                      and not g.startswith('http')
                      and re.match(r'^[A-Z]', g)]
            if guests:
                return guests

    for pattern in before_patterns:
        m = re.match(pattern, title)
        if m:
            candidate = m.group(1).strip()
            # Must look like a name (2+ words, each capitalised, no numbers)
            words = candidate.split()
            if 2 <= len(words) <= 4 and all(w[0].isupper() for w in words):
                return [candidate]

    return []


def _upsert_guest(conn: sqlite3.Connection, name: str) -> int:
    """Ensure a guest row exists for name. Returns guest id."""
    slug = name_to_slug(name)
    existing = conn.execute(
        'SELECT id FROM guests WHERE slug = ?', (slug,)
    ).fetchone()
    if existing:
        return existing['id']
    conn.execute(
        'INSERT INTO guests (name, slug) VALUES (?,?)', (name, slug)
    )
    return conn.execute('SELECT last_insert_rowid()').fetchone()[0]


def set_episode_guests(episode_id: str, guests: list, path: str = DB_PATH) -> None:
    """
    Replace all guest associations for episode_id.
    guests is a list of {'name': str, 'source': 'manual'|'ai_extracted'|'rss_parsed'}.
    """
    with get_db(path) as conn:
        conn.execute('DELETE FROM episode_guests WHERE episode_id = ?', (episode_id,))
        for g in guests:
            guest_id = _upsert_guest(conn, g['name'])
            conn.execute(
                'INSERT OR IGNORE INTO episode_guests (episode_id, guest_id, source) VALUES (?,?,?)',
                (episode_id, guest_id, g['source'])
            )


def search_guests(query: str, path: str = DB_PATH) -> list:
    """Search guests by name prefix. Returns list of {id, name, slug, person_id}."""
    pattern = f'%{query}%'
    with get_db(path) as conn:
        rows = conn.execute(
            'SELECT id, name, slug, person_id FROM guests WHERE name LIKE ? OR slug LIKE ? LIMIT 20',
            (pattern, pattern)
        ).fetchall()
    return [dict(r) for r in rows]


def get_guest_episodes(guest_id: int, limit: int = 20, path: str = DB_PATH) -> list:
    """Return episodes for a guest, newest first."""
    with get_db(path) as conn:
        rows = conn.execute("""
            SELECT e.*, eg.source as guest_source
            FROM episodes e
            JOIN episode_guests eg ON eg.episode_id = e.id
            WHERE eg.guest_id = ?
            ORDER BY e.date DESC LIMIT ?
        """, (guest_id, limit)).fetchall()
    return [dict(r) for r in rows]


# ── Library query ─────────────────────────────────────────────────────────────

def query_library(status_filter: str = None, platform_filter: str = None,
                  person_id: str = None, guest_id: int = None,
                  calibre_only: bool = False, sort: str = 'date_desc',
                  limit: int = 50, offset: int = 0,
                  db_path: str = DB_PATH) -> dict:
    """
    Joined library query across episodes + content_status + calibre_links + guests.
    Returns {items: [...], total: int}.
    Each item includes: id, person_id, person_name, platform, title, link, date,
    episode_number, duration_sec, status, calibre_id, calibre_type, guests.
    """
    where = ['1=1']
    params = []

    if status_filter:
        if status_filter == 'unread':
            # 'unread' means status IS 'unread' OR no row exists
            where.append("COALESCE(cs.status, 'unread') = 'unread'")
        else:
            where.append('cs.status = ?')
            params.append(status_filter)

    if platform_filter:
        where.append('e.platform = ?')
        params.append(platform_filter)

    if person_id:
        where.append('e.person_id = ?')
        params.append(person_id)

    if guest_id:
        where.append('EXISTS (SELECT 1 FROM episode_guests eg WHERE eg.episode_id=e.id AND eg.guest_id=?)')
        params.append(guest_id)

    if calibre_only:
        where.append('cl.calibre_id IS NOT NULL')

    order = 'e.date DESC' if sort == 'date_desc' else 'e.date ASC'
    where_sql = ' AND '.join(where)

    joins = """
        FROM episodes e
        LEFT JOIN content_status cs ON cs.entry_id = e.id
        LEFT JOIN calibre_links cl  ON cl.entry_id = e.id
        LEFT JOIN episode_guests eg ON eg.episode_id = e.id
        LEFT JOIN guests g ON g.id = eg.guest_id
    """

    with get_db(db_path) as conn:
        total = conn.execute(
            f'SELECT COUNT(DISTINCT e.id) {joins} WHERE {where_sql}', params
        ).fetchone()[0]

        rows = conn.execute(f"""
            SELECT
              e.id, e.person_id, e.person_name, e.platform, e.title, e.link,
              e.date, e.episode_number, e.duration_sec,
              COALESCE(cs.status, 'unread') AS status,
              cl.calibre_id, cl.content_type AS calibre_type,
              GROUP_CONCAT(g.name, '||') AS guest_names,
              GROUP_CONCAT(eg.source, '||') AS guest_sources
            {joins}
            WHERE {where_sql}
            GROUP BY e.id
            ORDER BY {order}
            LIMIT ? OFFSET ?
        """, params + [limit, offset]).fetchall()

    items = []
    for r in rows:
        item = dict(r)
        # Parse guests into structured list
        names   = (item.pop('guest_names')   or '').split('||')
        sources = (item.pop('guest_sources') or '').split('||')
        item['guests'] = [
            {'name': n, 'source': s, 'verified': s == 'manual'}
            for n, s in zip(names, sources) if n
        ]
        items.append(item)

    return {'items': items, 'total': total}
