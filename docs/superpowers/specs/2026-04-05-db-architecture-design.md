# Pulse — DB Architecture Design

**Date:** 2026-04-05
**Status:** Approved for implementation planning
**Scope:** Phase 1 (SQLite enrichment layer) + Phase 2 outline (full migration)

---

## 1. Goal

Add a persistent, profile-independent content layer to Pulse. Currently all data lives in browser localStorage/IndexedDB, which is isolated per Chrome profile. The new architecture adds SQLite (via the existing Flask backend) for enrichment data — status, notes, Calibre links, full episode archive, and guest relationships — while leaving the existing localStorage/IndexedDB layer untouched in Phase 1.

---

## 2. Architecture Decision

**Chosen approach: Phased hybrid (C)**

- **Phase 1 (now):** SQLite as an additive enrichment layer. localStorage and IndexedDB are unchanged. New data (status, notes, Calibre links, episode archive, guest graph) goes to SQLite exclusively. Existing `pw-notes` and `pw-seen`/`pw-listened` in localStorage are migrated to SQLite on first backend connection and then deprecated.
- **Phase 2 (future):** Migrate persons and entries to SQLite. localStorage becomes a write-through cache. Full profile independence for all data.

**Why this approach:**
- Ships new features immediately without a big-bang migration
- Backend is already optional; Phase 1 keeps it optional for basic use (persons, recent feeds still work offline)
- Entry IDs are deterministic composite keys (`personId + platform + link`) — SQLite enrichment links back correctly regardless of which Chrome profile fetched the entry
- Clear upgrade path to full independence in Phase 2

---

## 3. Phase 1 — SQLite Schema

SQLite database file: `backend/pulse.db`
Initialised automatically on first backend start via `CREATE TABLE IF NOT EXISTS`.

### 3.1 `content_status`

Tracks read/watch/listen state per content entry. Replaces `pw-listened` in localStorage. `pw-seen` is NOT migrated — it only tracks whether the entry modal was opened (clears the NEW badge), which does not imply the content was consumed. `pw-seen` continues to function as-is for the NEW badge; `content_status` is the authoritative read state going forward.

```sql
CREATE TABLE IF NOT EXISTS content_status (
  entry_id   TEXT PRIMARY KEY,   -- same composite key as Entry.id in localStorage
  person_id  TEXT NOT NULL,      -- for indexed queries per person
  platform   TEXT NOT NULL,      -- podcast|youtube|twitter|blog|books
  status     TEXT NOT NULL DEFAULT 'unread',
             -- unread | want_to_read | in_progress | done | skipped
  updated_at TEXT NOT NULL       -- ISO 8601
);
CREATE INDEX IF NOT EXISTS idx_status_person ON content_status(person_id);
CREATE INDEX IF NOT EXISTS idx_status_status ON content_status(status);
```

Status values and meaning:
| Value | Meaning |
|---|---|
| `unread` | Default. Not yet opened. |
| `want_to_read` | Bookmarked for later. |
| `in_progress` | Partially consumed. |
| `done` | Fully read/watched/listened. |
| `skipped` | Deliberately passing on this one. |

### 3.2 `notes`

Manual and AI notes per entry. Replaces `pw-notes` in localStorage. Split into two columns so AI notes can be overwritten without touching manual notes and vice versa.

```sql
CREATE TABLE IF NOT EXISTS notes (
  entry_id    TEXT PRIMARY KEY,
  person_id   TEXT NOT NULL,
  manual_note TEXT,
  ai_note     TEXT,
  updated_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_notes_person ON notes(person_id);
```

**Migration:** On first backend connection, the frontend reads `pw-notes` from localStorage, sends all entries to `POST /api/db/notes/migrate`, then removes `pw-notes` from localStorage.

### 3.3 `calibre_links`

Links a content entry to a book record in Calibre. Covers all content types — book, podcast transcript, article, video transcript.

```sql
CREATE TABLE IF NOT EXISTS calibre_links (
  entry_id      TEXT PRIMARY KEY,
  person_id     TEXT NOT NULL,
  calibre_id    INTEGER NOT NULL,   -- Calibre book ID
  calibre_title TEXT NOT NULL,
  formats       TEXT NOT NULL,      -- JSON array e.g. ["PDF","EPUB","TXT"]
  content_type  TEXT NOT NULL,      -- transcript | article | book
  pushed_at     TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_calibre_person ON calibre_links(person_id);
```

**Push-to-Calibre flow:**
1. User fetches a transcript or article (already works via backend for YouTube; podcast via `podcast:transcript` URL; blog via full-text RSS or scrape)
2. User clicks **→ Calibre** button in the entry modal or episode row
3. Frontend calls `POST /api/db/calibre/push` with `{ entry_id, person_id, title, content, content_type }`
4. Backend uploads the content to Calibre Content Server via its REST API, retrieves the new `book_id`, inserts a row into `calibre_links`, returns `{ calibre_id, formats }`
5. UI replaces the **→ Calibre** button with a **📚** icon linking to `{calibreUrl}/browse/book/{calibre_id}`

### 3.4 `episodes`

Full episode archive for selected podcasters. Replaces IndexedDB `pulse-episodes`. Richer than the IndexedDB version — adds `duration_sec`, `episode_number`, `person_name` (denormalised for fast queries).

```sql
CREATE TABLE IF NOT EXISTS episodes (
  id                TEXT PRIMARY KEY,  -- personId + "podcast" + link, max 80 chars
  person_id         TEXT NOT NULL,
  person_name       TEXT NOT NULL,     -- denormalised; avoids join to localStorage
  platform          TEXT NOT NULL,     -- podcast | youtube
  title             TEXT NOT NULL,
  link              TEXT NOT NULL,
  description       TEXT,
  date              TEXT,              -- ISO 8601
  duration_sec      INTEGER,
  episode_number    INTEGER,
  itunes_episode_id TEXT,
  synced_at         TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_episodes_person ON episodes(person_id);
CREATE INDEX IF NOT EXISTS idx_episodes_date   ON episodes(date);
```

**Sync strategy:**
- Full episode archive is opt-in per person (toggle in the Edit panel: "Download full episode archive")
- On sync, fetches the full RSS feed (all pages if paginated) and all available iTunes episodes, deduplicates by `id`, upserts into SQLite
- Sync runs on demand (button in person panel) or on a configurable interval

### 3.5 `guests`

Canonical guest records. One row per unique guest. Supports aliases for fuzzy matching across inconsistent RSS feeds.

```sql
CREATE TABLE IF NOT EXISTS guests (
  id        INTEGER PRIMARY KEY AUTOINCREMENT,
  name      TEXT NOT NULL UNIQUE,   -- canonical display name e.g. "Elon Musk"
  slug      TEXT NOT NULL UNIQUE,   -- "elon-musk" for matching
  aliases   TEXT,                   -- JSON array e.g. ["Elon","Mr. Musk"]
  person_id TEXT                    -- nullable; set if guest is also a tracked person
);
CREATE INDEX IF NOT EXISTS idx_guests_slug ON guests(slug);
```

### 3.6 `episode_guests`

Many-to-many join between episodes and guests. Tracks how each guest association was established.

```sql
CREATE TABLE IF NOT EXISTS episode_guests (
  episode_id TEXT    NOT NULL REFERENCES episodes(id) ON DELETE CASCADE,
  guest_id   INTEGER NOT NULL REFERENCES guests(id)   ON DELETE CASCADE,
  source     TEXT    NOT NULL,  -- manual | ai_extracted | rss_parsed
  PRIMARY KEY (episode_id, guest_id)
);
CREATE INDEX IF NOT EXISTS idx_epguests_guest ON episode_guests(guest_id);
```

**Guest extraction strategy:**
- **Auto (ai_extracted):** On episode sync, the backend parses the episode title and subtitle using a simple heuristic (text after ` | `, ` — `, or ` with ` is treated as guest name). Matched against `guests.slug` + `aliases`; new guest row created if no match. Marked `source = 'ai_extracted'`.
- **Manual:** User can add/edit/remove guests from the episode detail view. Marked `source = 'manual'`.
- **Unverified indicator:** Auto-extracted guests show a **⚠** badge in the UI until a user confirms them (confirmation updates `source` to `manual`).

---

## 4. Phase 2 — Future Migration (outline only)

Not built in Phase 1. Included here for planning continuity.

```sql
-- persons: replaces pw-persons in localStorage
CREATE TABLE IF NOT EXISTS persons (
  id           TEXT PRIMARY KEY,
  name         TEXT NOT NULL,
  type         TEXT NOT NULL,  -- person | source
  desc         TEXT,
  avatar       TEXT,
  website      TEXT,
  feeds_json   TEXT,           -- JSON blob of feeds object
  feeds_enabled_json TEXT,     -- JSON blob of feedsEnabled object
  tags_json    TEXT,           -- JSON array
  roles_json   TEXT,           -- JSON array
  itunes_id    INTEGER,
  last_updated TEXT,
  created_at   TEXT
);

-- entries: replaces person.entries[] in localStorage
CREATE TABLE IF NOT EXISTS entries (
  id             TEXT PRIMARY KEY,
  person_id      TEXT NOT NULL REFERENCES persons(id),
  platform       TEXT NOT NULL,
  title          TEXT,
  link           TEXT,
  description    TEXT,
  date           TEXT,
  author         TEXT,
  transcript_url TEXT,
  thumbnail      TEXT,
  created_at     TEXT
);
```

Phase 2 trigger: when Export/Import feature is built, migrating persons to SQLite makes the export trivial (SQLite dump).

---

## 5. Backend API Endpoints (Phase 1)

All new endpoints added to `backend/server.py`. SQLite accessed via Python's built-in `sqlite3` module. DB file: `backend/pulse.db`.

### Status
| Method | Route | Body / Params | Returns |
|---|---|---|---|
| `GET` | `/api/db/status/<entry_id>` | — | `{ status }` or `{ status: 'unread' }` if not set |
| `PUT` | `/api/db/status/<entry_id>` | `{ person_id, platform, status }` | `{ ok: true }` |
| `GET` | `/api/db/status/person/<person_id>` | — | `{ [entry_id]: status }` — bulk fetch for a person |

### Notes
| Method | Route | Body | Returns |
|---|---|---|---|
| `GET` | `/api/db/notes/<entry_id>` | — | `{ manual_note, ai_note, updated_at }` |
| `PUT` | `/api/db/notes/<entry_id>` | `{ person_id, manual_note?, ai_note? }` | `{ ok: true }` |
| `POST` | `/api/db/notes/migrate` | `{ notes: { [entry_id]: string } }` | `{ migrated: N }` |

### Calibre
| Method | Route | Body | Returns |
|---|---|---|---|
| `POST` | `/api/db/calibre/push` | `{ entry_id, person_id, title, content, content_type }` | `{ calibre_id, formats }` |
| `GET` | `/api/db/calibre/<entry_id>` | — | `{ calibre_id, calibre_title, formats, content_type }` or `404` |
| `GET` | `/api/db/calibre/person/<person_id>` | — | `{ [entry_id]: { calibre_id, formats } }` — bulk |

### Episodes
| Method | Route | Body / Params | Returns |
|---|---|---|---|
| `GET` | `/api/db/episodes/<person_id>` | `?limit=50&offset=0&sort=date_desc` | `{ episodes: [...], total: N }` |
| `POST` | `/api/db/episodes/sync/<person_id>` | `{ person_name, rss_url?, itunes_id? }` | `{ synced: N, total: N }` |

### Guests
| Method | Route | Body | Returns |
|---|---|---|---|
| `GET` | `/api/db/guests` | `?q=elon` | `{ guests: [...] }` — search |
| `GET` | `/api/db/guests/<guest_id>/episodes` | `?limit=20` | `{ episodes: [...] }` — all appearances |
| `PUT` | `/api/db/episodes/<episode_id>/guests` | `{ guests: [{ name, source }] }` | `{ ok: true }` |

### Library
| Method | Route | Params | Returns |
|---|---|---|---|
| `GET` | `/api/db/library` | `?status=&platform=&person_id=&guest_id=&calibre_only=&sort=&limit=&offset=` | `{ items: [...], total: N }` — joined query across content_status + episodes + calibre_links |

---

## 6. Frontend Changes (Phase 1)

### 6.1 Library tab
- New top-level nav item **📚 Library** alongside People and Timeline
- Filter bar: status chips · platform chips · In Calibre toggle · Guest picker · Sort
- Rows show: status dot · title · person name · date · guest names (⚠ if unverified) · platform badge · Calibre badge
- Fetches from `GET /api/db/library` when backend is online; degrades gracefully (empty state with message) when backend is offline
- Infinite scroll / "Load more" pagination

### 6.2 Person panel — All Episodes tab
- New **All Episodes** tab in the person detail panel (alongside Recent, Notes, Edit)
- Fetches from `GET /api/db/episodes/<person_id>`
- Each row: episode number · title · guest names · status chip · **→ Calibre** button (if transcript available) · 📚 icon (if already in Calibre)
- "Download full archive" toggle in Edit tab triggers `POST /api/db/episodes/sync/<person_id>`

### 6.3 Status controls
- Status dot on every entry row (Library, episode list, timeline) — click to cycle or open a picker
- Status picker: five options with colour-coded chips
- Status written to `PUT /api/db/status/<entry_id>` immediately on change
- Status loaded in bulk (`GET /api/db/status/person/<person_id>`) when a person's content is rendered

### 6.4 Push to Calibre button
- Appears in entry modal (for youtube/podcast/blog entries) when transcript/article has been fetched
- Label: **→ Calibre** (purple, matches `--books` CSS variable)
- On click: calls `POST /api/db/calibre/push`, shows spinner, then replaces button with **📚 in Calibre** link
- For books: existing auto-detect behaviour unchanged; `calibre_links` row inserted automatically when a book match is found

### 6.5 Guest unverified indicator
- Auto-extracted guest names show **⚠** badge
- Clicking **⚠** opens a small inline form: confirm name / correct it / remove
- Confirming updates `source` to `manual` via `PUT /api/db/episodes/<id>/guests`

### 6.6 Migration (notes + status)
- On page load, if `_backendOnline` is true and `pw-notes` exists in localStorage:
  - Call `POST /api/db/notes/migrate` with the full notes object
  - On success, delete `pw-notes` from localStorage
  - Set `localStorage['pw-notes-migrated'] = true` so migration never reruns
- Same pattern for `pw-listened`: entries in `pw-listened` are migrated to `content_status` with `status = 'done'`, then `pw-listened` is removed from localStorage
- `pw-seen` is NOT migrated — it continues to drive the NEW badge only and is not equivalent to `done`

---

## 7. What Stays Unchanged

- `pw-persons` — persons list, feeds, tags, roles. Unchanged until Phase 2.
- `pw-entry-tags` — episode-level topic tags. Unchanged (Phase 2 candidate).
- `pw-config` — API keys, Calibre URL/auth, settings. Unchanged.
- `pulse-episodes` IndexedDB — kept as offline fallback; SQLite is the primary after first sync.
- All existing fetch logic, CORS proxy chain, feed status dots, feed toggles — untouched.
- App works fully offline / without backend for existing features (People, Timeline, refresh).

---

## 8. File Changes

| File | Change |
|---|---|
| `backend/server.py` | Add DB init, 15 new endpoints, guest extraction helper |
| `backend/requirements.txt` | No new deps (`sqlite3` is stdlib) |
| `index.html` | Library tab, All Episodes tab, status controls, push-to-Calibre button, migration on load |
| `backend/pulse.db` | Created automatically on first backend start (gitignored) |
| `.gitignore` | Add `backend/pulse.db` |

---

## 9. Out of Scope (Phase 1)

- Full-text search across notes or transcripts
- Cross-device sync (requires Phase 2 + network-accessible backend)
- Auto-push to Calibre without user action
- Tags migration to SQLite
- persons / entries migration to SQLite (Phase 2)
