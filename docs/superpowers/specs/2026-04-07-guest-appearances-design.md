# Guest Appearances — Design Spec
**Date:** 2026-04-07
**Status:** Approved

---

## Problem

Pulse tracks people as *authors* of content (podcaster, YouTuber, blogger, writer). But many tracked people — researchers, thinkers, scientists like Karl Friston — appear primarily as *guests* on other people's shows, or as subjects of articles and interviews they didn't author. There is currently no way to discover or store this "appearance" content on a person's profile.

---

## Goal

1. **Discovery:** Given a tracked person, find episodes/articles where they appeared as a guest or subject (semi-automated — app searches, user approves).
2. **Integration:** Show approved appearances on the person's card alongside their authored content, visually distinguished.
3. **Cross-linking:** When the host is also a tracked person, link the appearance to that host's episode bidirectionally.

---

## Approach

**A — `appearances[]` on Person + iTunes/YouTube discovery (chosen)**

- New `person.appearances: AppearanceEntry[]` field in localStorage, separate from `person.entries[]`
- "🔍 Find Appearances" button on the person detail panel triggers iTunes podcast search + YouTube search link
- User reviews candidates and approves/skips each
- Approved items render on the card mixed with authored entries, tagged **🎤 Guest on [Host]**
- One new backend endpoint to link a guest name to a tracked person ID in SQLite

---

## Data Model

### `AppearanceEntry` (stored in `person.appearances[]`, localStorage)

```js
{
  id:           string,                // "personId-appearance-<hash of link>"
  personId:     string,                // the tracked person this appearance belongs to
  platform:     'podcast' | 'youtube' | 'article' | 'other',
  title:        string,                // episode or article title
  link:         string,                // canonical URL
  desc:         string,                // snippet, max 300 chars
  date:         string,                // ISO 8601
  hostName:     string,                // e.g. "Lex Fridman", "Wired"
  hostPersonId: string | null,         // set if host is a tracked person in this app
  episodeId:    string | null,         // set if linked to a tracked host's episode in SQLite
  addedHow:     'search' | 'manual',   // provenance
}
```

### Changes to `Person` schema

```js
person.appearances = []   // AppearanceEntry[], unbounded (no CircularBuffer cap)
```

Missing key → treated as `[]` (backward-compatible).

### SQLite change — `guests.person_id`

The `guests` table already has a `person_id TEXT` column (currently unpopulated). When an appearance is approved and the host is tracked, `guests.person_id` is set to the tracked person's ID via `PATCH /api/db/guests/link`. This makes the Library's guest filter work for tracked persons automatically.

---

## Discovery Flow

### Trigger

"🔍 Find Appearances" button in the person detail panel, below the feed rows. Opens a collapsible search panel inline.

### Search sources

| Source | Method | API key needed |
|--------|--------|---------------|
| Podcast episodes | iTunes Search API: `https://itunes.apple.com/search?term={name}&media=podcast&entity=podcastEpisode&limit=20` | None |
| YouTube videos | Pre-built search URL opens in new tab: `https://youtube.com/results?search_query={name}+interview` — user copies a URL back | None |
| Articles / other | Manual URL paste field | None |

### Candidate review panel

- iTunes results appear as a compact list: title, show name, date, description snippet
- Each row: **✓ Add** / **✗ Skip** buttons (mirrors Add Person role results UI)
- Manual paste field below iTunes results — accepts any YouTube, podcast, or article URL
- On paste: app resolves title + date via YouTube oEmbed / RSS lookup / fallback to URL as title
- Deduplication: candidates whose `link` already exists in `person.appearances` are silently filtered. `_resolveAppearanceUrl` canonicalises YouTube URLs to `https://www.youtube.com/watch?v=ID` before the dedup check to handle `youtu.be` short links.

### On approval

1. Construct `AppearanceEntry` from candidate data
2. Check `persons[]` for a name match on `hostName` → set `hostPersonId` if found
3. If `hostPersonId` set and backend online: look up `episodeId` from SQLite by matching link → set `episodeId`
4. Append to `person.appearances[]`, save localStorage
5. Re-render person card

---

## Card Rendering

### Merged entry list

Before rendering a person's card, `person.appearances[]` is merged with `person.entries[]` and sorted by date descending. The card shows the top 4 items from this merged list (same cap as today).

### Appearance chip appearance

Identical to a regular entry chip except:
- Platform badge replaced with **🎤 Guest on [hostName]** in `var(--accent)` at 70% opacity
- `NEW` badge, `seen` tracking, click-to-open-modal all work identically

### Timeline view

Appearances appear in the timeline interleaved with authored content, with the same 🎤 badge.

### Platform filter bar

New **🎤 Appearances** filter chip added to the platform filter row. When active:
- Grid: shows only persons with `appearances.length > 0`
- Timeline: shows only appearance entries

---

## Entry Modal

When an appearance entry is opened:

1. **Header tag:** "🎤 Appearance" replaces the platform tag; subtitle: *"Guest on [hostName]"*
2. **Host jump link:** If `hostPersonId` is set, a small **"→ Open [hostName]'s profile"** link navigates to the host's person detail panel
3. Open →, 🔊 Sound, ▶ Video buttons work as normal based on `platform`
4. Notes, Topics, and Transcript sections work identically to regular entries

### Guest chip → tracked person jump link (existing modal enhancement)

In `_renderGuestList()`, if a guest chip's guest record has `person_id` set in SQLite, the chip gains a **"→ [Person Name]"** jump link to that person's profile. This applies to all episode modals, not just appearances.

---

## Backend Changes

### New endpoint: `PATCH /api/db/guests/link`

```
PATCH /api/db/guests/link
Body: { guest_name: str, person_id: str }
→ Finds guests row by slug match on guest_name
→ Sets guests.person_id = person_id
→ Returns { ok: true, guest_id: int } or 404 if guest not found
```

Called once per approved appearance where `hostPersonId` is resolved. Optional — appearances function without it.

### New db.py function: `link_guest_to_person(guest_name, person_id, path)`

```python
def link_guest_to_person(guest_name: str, person_id: str, path: str = DB_PATH) -> int | None:
    """Set guests.person_id for a guest matched by name/slug. Returns guest_id or None."""
```

Uses the existing `_slugify()` helper for name matching.

---

## Frontend Functions

| Function | Purpose |
|---|---|
| `openAppearanceFinder(personId)` | Toggle the Find Appearances panel on the detail view |
| `searchAppearances(personId)` | Call iTunes API via CORS proxy, render candidate list |
| `_resolveAppearanceUrl(url)` | Resolve title/date from a manually pasted URL (oEmbed / RSS / fallback) |
| `approveAppearance(personId, candidate)` | Build AppearanceEntry, resolve host, save to localStorage |
| `removeAppearance(personId, appearanceId)` | Remove from `person.appearances[]`, re-render |
| `_mergeEntriesAndAppearances(person)` | Return date-sorted merged array for card rendering |
| `renderAppearanceChip(appearance)` | Render a single appearance chip (🎤 badge variant) |
| `_resolveHostPersonId(hostName)` | Case-insensitive name match against `persons[]` |
| `linkGuestToPerson(guestName, personId)` | Call `PATCH /api/db/guests/link` |

---

## What Is Out of Scope

- **Automated periodic refresh** of appearances (no RSS equivalent for guest search)
- **YouTube Data API search** (requires API key; browser search link is sufficient for v1)
- **Listen Notes / Spotify API** integration (requires API key; iTunes covers most podcasts)
- **Appearance entries in the Library tab** (Library reads from SQLite `episodes`; appearances stay in localStorage for now)
- **Bulk import** of appearances

---

## Backward Compatibility

- `person.appearances` missing → treated as `[]` everywhere; no migration needed
- No existing localStorage keys changed
- SQLite schema unchanged (only data updated in `guests.person_id`)
