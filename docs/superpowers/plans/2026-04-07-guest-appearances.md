# Guest Appearances Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add "guest appearances" to Pulse — content where a tracked person appears as a guest or subject rather than author — with semi-automated discovery via iTunes Search API and manual URL paste.

**Architecture:** A new `person.appearances[]` array in localStorage (separate from `person.entries[]`, no cap) holds `AppearanceEntry` objects. Cards merge appearances with authored entries sorted by date and render them with a 🎤 badge. A "Find Appearances" panel on the person detail view searches iTunes and accepts manual URLs. One new backend endpoint links a guest name to a tracked person ID for Library cross-linking.

**Tech Stack:** Vanilla JS / localStorage (frontend), Flask + SQLite (backend for guest linking only), iTunes Search API (free, no key), YouTube oEmbed API (free, no key).

**Spec:** `docs/superpowers/specs/2026-04-07-guest-appearances-design.md`

---

## File Map

| File | Changes |
|------|---------|
| `index.html` | All frontend changes — new functions, updated rendering, HTML additions |
| `backend/db.py` | `link_guest_to_person()`, update `get_episode_guests()` to return `person_id` |
| `backend/server.py` | `PATCH /api/db/guests/link`, update guests endpoint response |

---

## Task 1: Backend — guest-to-person linking

**Files:**
- Modify: `backend/db.py`
- Modify: `backend/server.py`
- Modify: `index.html` (add `_dbClient.linkGuestToPerson`)

- [ ] **Step 1: Add `link_guest_to_person` to `backend/db.py`**

Find the `get_episode_guests` function (~line 366). First update it to also return `person_id` from the `guests` table, then add the new linking function after it:

```python
def get_episode_guests(episode_id: str, path: str = DB_PATH) -> list:
    """Return all guests for a specific episode."""
    with get_db(path) as conn:
        rows = conn.execute("""
            SELECT g.id, g.name, g.person_id, eg.source
            FROM episode_guests eg
            JOIN guests g ON g.id = eg.guest_id
            WHERE eg.episode_id = ?
            ORDER BY g.name
        """, (episode_id,)).fetchall()
    return [dict(r) for r in rows]


def link_guest_to_person(guest_name: str, person_id: str, path: str = DB_PATH) -> int | None:
    """
    Set guests.person_id for the guest matching guest_name (by slug).
    Returns guest_id on success, None if guest not found.
    """
    slug = _slugify(guest_name)
    with get_db(path) as conn:
        row = conn.execute(
            'SELECT id FROM guests WHERE slug = ? OR name = ?', (slug, guest_name)
        ).fetchone()
        if not row:
            return None
        conn.execute('UPDATE guests SET person_id = ? WHERE id = ?', (person_id, row['id']))
    return row['id']
```

- [ ] **Step 2: Add `PATCH /api/db/guests/link` to `backend/server.py`**

Find the `db_search_guests` route (~line 557). Add the new endpoint after it:

```python
@app.route('/api/db/guests/link', methods=['PATCH'])
def db_link_guest_to_person():
    """Link a guest name to a tracked person ID."""
    data = request.json or {}
    guest_name = (data.get('guest_name') or '').strip()
    person_id  = (data.get('person_id')  or '').strip()
    if not guest_name or not person_id:
        return jsonify({'error': 'guest_name and person_id are required'}), 400
    guest_id = _db.link_guest_to_person(guest_name, person_id, path=_db.DB_PATH)
    if guest_id is None:
        return jsonify({'error': 'guest not found'}), 404
    return jsonify({'ok': True, 'guest_id': guest_id})
```

- [ ] **Step 3: Add `_dbClient.linkGuestToPerson` in `index.html`**

Find the `_dbClient` object (~line 1847). Add after `getGuestEpisodes`:

```js
linkGuestToPerson: (guestName, personId) => _dbClient._call('PATCH', '/api/db/guests/link', { guest_name: guestName, person_id: personId }),
```

- [ ] **Step 4: Restart backend and verify**

```bash
cd backend && python server.py
# In another terminal:
curl -s -X PATCH http://localhost:5001/api/db/guests/link \
  -H 'Content-Type: application/json' \
  -d '{"guest_name":"Nonexistent Person","person_id":"test"}' | python3 -m json.tool
# Expected: {"error": "guest not found"}
```

- [ ] **Step 5: Commit**

```bash
git add backend/db.py backend/server.py index.html
git commit -m "feat(appearances): backend guest-to-person link endpoint + person_id in get_episode_guests"
```

---

## Task 2: Data model + core helper functions

**Files:**
- Modify: `index.html` (new functions in the `// ── MODAL GUESTS ──` section area, or near top-level state)

- [ ] **Step 1: Add `AppearanceEntry` schema comment and `_mergeEntriesAndAppearances`**

Find the line `let _modalGuests = [];` (~line 5334, in the MODAL GUESTS block). Above it, add the schema comment and the merge function:

```js
// ── APPEARANCES ────────────────────────────────────────────────────────────
/*
 * AppearanceEntry — stored in person.appearances[] (localStorage)
 * {
 *   id:           string,              // "personId-appearance-<8-char hash>"
 *   isAppearance: true,                // distinguishes from Entry
 *   personId:     string,
 *   platform:     'podcast'|'youtube'|'article'|'other',
 *   title:        string,
 *   link:         string,
 *   desc:         string,              // max 300 chars
 *   date:         string,              // ISO 8601, may be ''
 *   hostName:     string,              // e.g. "Lex Fridman"
 *   hostPersonId: string|null,
 *   episodeId:    string|null,
 *   addedHow:     'search'|'manual',
 * }
 */

function _mergeEntriesAndAppearances(person) {
  const entries     = (person.entries     || []).map(e => ({ ...e, isAppearance: false }));
  const appearances = (person.appearances || []);
  return [...entries, ...appearances].sort((a, b) =>
    new Date(b.date || 0) - new Date(a.date || 0)
  );
}

function _resolveHostPersonId(hostName) {
  if (!hostName) return null;
  const lower = hostName.toLowerCase();
  const match = persons.find(p => p.name.toLowerCase() === lower
    || p.name.toLowerCase().includes(lower)
    || lower.includes(p.name.toLowerCase()));
  return match ? match.id : null;
}

function _makeAppearanceId(personId, link) {
  // Simple 8-char hash from link for stable IDs
  let h = 0;
  for (let i = 0; i < link.length; i++) h = (Math.imul(31, h) + link.charCodeAt(i)) | 0;
  return `${personId}-appearance-${Math.abs(h).toString(36).slice(0, 8)}`;
}
```

- [ ] **Step 2: Update `rebuildAllEntries()` to include appearances**

Find `function rebuildAllEntries` in `index.html`. It currently flattens `person.entries`. Update it to also include appearances:

```js
function rebuildAllEntries() {
  allEntries = persons.flatMap(p => _mergeEntriesAndAppearances(p));
  allEntries.sort((a, b) => new Date(b.date) - new Date(a.date));
}
```

(Replace whatever the current body is — it currently does `persons.flatMap(p => p.entries || [])` or similar.)

- [ ] **Step 3: Commit**

```bash
git add index.html
git commit -m "feat(appearances): data model, _mergeEntriesAndAppearances, _resolveHostPersonId helpers"
```

---

## Task 3: Card rendering — 🎤 chips + filter chip

**Files:**
- Modify: `index.html`

- [ ] **Step 1: Update `renderPersonCard` to use merged entries**

Find `renderPersonCard` (~line 4025). The current line:
```js
let entries = person._searchEntries || person._tagEntries || person.entries || [];
if (currentFilter !== 'all') entries = entries.filter(e => e.platform === currentFilter);
```

Replace with:
```js
let entries = person._searchEntries || person._tagEntries || _mergeEntriesAndAppearances(person);
if (currentFilter === 'appearance') {
  entries = entries.filter(e => e.isAppearance);
} else if (currentFilter !== 'all') {
  entries = entries.filter(e => !e.isAppearance && e.platform === currentFilter);
}
```

- [ ] **Step 2: Update NEW count to include appearances**

The line `const newCount = entries.filter(e => !seenIds.has(e.id)).length;` is already correct (it uses the already-filtered `entries`). No change needed.

- [ ] **Step 3: Add appearance chip branch in the entry chip HTML**

Find the `entriesHTML = entries.map(entry => {` block (~line 4064). At the top of the map callback, before the regular chip HTML, add a branch for appearances:

```js
entriesHTML = entries.slice(0, 4).map(entry => {
  const isNew = !seenIds.has(entry.id);
  if (entry.isAppearance) {
    return `
      <div class="entry-row"
           data-eid="${escHtml(entry.id)}"
           onclick="openEntry(${JSON.stringify(entry).replace(/"/g, '&quot;')})">
        <div class="entry-platform-dot" style="background:var(--accent);opacity:0.65"></div>
        <div class="entry-content">
          <div class="entry-title">${escHtml(entry.title)}</div>
          <div class="entry-meta">
            <span class="entry-platform-label">🎤 ${escHtml(entry.hostName || 'Guest')}</span>
            <span class="entry-time">${timeAgo(entry.date)}</span>
          </div>
        </div>
        ${isNew ? '<span class="new-badge">NEW</span>' : ''}
      </div>`;
  }
  const pl    = getPlatform(entry, person);
  const eTags = entryTags[entry.id] || [];
  // ... rest of existing chip HTML unchanged
```

Note: also add `.slice(0, 4)` to the `.map()` call if it isn't already there (currently the card shows all entries in `entries`, limited earlier — check whether the slice happens before or after the map and ensure only 4 show).

- [ ] **Step 4: Add 🎤 Appearances filter chip to the filter bar HTML**

Find the filter bar HTML (~line 1542, after the Article chip):

```html
<button class="filter-chip" data-filter="article" onclick="setFilter('article')">
  <span class="chip-dot" style="background:var(--article)"></span>Article
</button>
```

Add after it:

```html
<button class="filter-chip" data-filter="appearance" onclick="setFilter('appearance')">
  <span style="font-size:11px;margin-right:3px">🎤</span>Appearances
</button>
```

- [ ] **Step 5: Update `setFilter` to handle 'appearance' in `renderAllCards`**

In `renderAllCards()`, find the part that filters cards based on `currentFilter`. Add handling so that when `currentFilter === 'appearance'`, only persons with `(p.appearances||[]).length > 0` are shown:

Find `renderAllCards` and the visible persons filter. It currently does something like:
```js
let visible = persons.filter(p => { ... });
```

Add to the filter condition:
```js
if (currentFilter === 'appearance' && !(p.appearances||[]).length) return false;
```

(Place this alongside the existing platform filter checks.)

- [ ] **Step 6: Commit**

```bash
git add index.html
git commit -m "feat(appearances): card rendering — 🎤 chip + filter chip"
```

---

## Task 4: Timeline — include appearances

**Files:**
- Modify: `index.html`

- [ ] **Step 1: Find `renderTimeline`**

Find `function renderTimeline()`. It uses `allEntries` (already updated in Task 2 to include appearances). The platform filter line currently reads:
```js
if (currentFilter !== 'all') entries = entries.filter(e => e.platform === currentFilter);
```

Replace with:
```js
if (currentFilter === 'appearance') {
  entries = entries.filter(e => e.isAppearance);
} else if (currentFilter !== 'all') {
  entries = entries.filter(e => !e.isAppearance && e.platform === currentFilter);
}
```

- [ ] **Step 2: Add appearance chip rendering in the timeline**

In `renderTimeline`, find where entry chips are rendered. Add a branch for appearance entries (same pattern as Task 3 Step 3 but inside the timeline's HTML builder):

```js
if (entry.isAppearance) {
  const person = persons.find(p => p.id === entry.personId) || {};
  return `<div class="timeline-entry" onclick="openEntry(${JSON.stringify(entry).replace(/"/g,'&quot;')})">
    <div class="tl-dot" style="background:var(--accent);opacity:0.65"></div>
    <div class="tl-content">
      <div class="tl-title">${escHtml(entry.title)}</div>
      <div class="tl-meta">
        <span style="color:var(--accent)">🎤 ${escHtml(entry.hostName || 'Guest')}</span>
        · <span>${escHtml(person.name || '')}</span>
        · <span>${timeAgo(entry.date)}</span>
      </div>
    </div>
  </div>`;
}
// ... existing entry chip HTML below
```

- [ ] **Step 3: Commit**

```bash
git add index.html
git commit -m "feat(appearances): include appearances in timeline view"
```

---

## Task 5: Entry modal for appearance entries

**Files:**
- Modify: `index.html`

- [ ] **Step 1: Detect `entry.isAppearance` in `openEntry()`**

Find `function openEntry(entry)` (~line 4994). After the existing platform/person setup lines, add a branch that replaces the platform tag with a 🎤 tag for appearances. The modal content `innerHTML` string currently renders:

```js
<span class="modal-platform-tag" style="background:${pl.color}20;color:${pl.color}">
  ${pl.emoji} ${pl.label}
</span>
```

Replace this with a conditional:

```js
${entry.isAppearance
  ? `<span class="modal-platform-tag" style="background:var(--accent)20;color:var(--accent)">
       🎤 Guest Appearance
     </span>`
  : `<span class="modal-platform-tag" style="background:${pl.color}20;color:${pl.color}">
       ${pl.emoji} ${pl.label}
     </span>`
}
```

- [ ] **Step 2: Add host name subtitle and jump link for appearances**

In the modal `innerHTML`, the title line is followed by an optional author line. After the title, add a hostName subtitle for appearances:

```js
${entry.isAppearance && entry.hostName
  ? `<div style="font-family:'JetBrains Mono',monospace;font-size:11px;color:var(--accent);opacity:0.8;margin-bottom:2px">
       Guest on ${escHtml(entry.hostName)}
       ${entry.hostPersonId
         ? `<button onclick="openPersonDetail('${escHtml(entry.hostPersonId)}');closeModal()"
              style="background:none;border:none;cursor:pointer;color:var(--accent2);font-size:10px;margin-left:6px;padding:0;font-family:'JetBrains Mono',monospace">
              → Open profile
            </button>`
         : ''}
     </div>`
  : ''
}
```

Place this immediately after the `<div class="modal-title">` line.

- [ ] **Step 3: Hide podcast/wiki-specific buttons for appearances**

In the platform-specific button show/hide block (~line 5168 onward), at the very start of that section add:

```js
if (entry.isAppearance) {
  // Appearances: just show Open → and note/topic fields; no transcript buttons
  if (entry.link) _showOpen(entry.link);
  if (guestSection) guestSection.style.display = 'none';
  return; // skip all platform-specific logic below
}
```

Wait — `return` inside `openEntry` would exit too early (before notes population etc.). Instead, wrap the platform-specific block in `if (!entry.isAppearance) { ... }` rather than using early return. Make sure notes, topics, and listened button still work.

Actually, the cleaner approach: at the top of the platform block, skip only the transcript/guest section:

```js
if (entry.isAppearance) {
  if (entry.link) _showOpen(entry.link);
  if (guestSection) guestSection.style.display = 'none';
  // fall through to notes / topics (those still render normally)
} else if (entry.platform === 'youtube') {
  // ... existing youtube block
} else if (entry.platform === 'podcast') {
  // ... existing podcast block
} // etc.
```

Replace the existing `if (entry.platform === 'youtube')` chain with `else if` after the `if (entry.isAppearance)` branch.

- [ ] **Step 4: Verify modal opens correctly**

Open a podcast entry in the app → modal opens with platform tag and transcript buttons (unchanged).

Open an appearance entry (after Task 9 adds some) → modal shows "🎤 Guest Appearance" tag, "Guest on [hostName]", no transcript buttons, Open → link works.

- [ ] **Step 5: Commit**

```bash
git add index.html
git commit -m "feat(appearances): appearance entry modal — 🎤 header, host subtitle, jump link"
```

---

## Task 6: Guest chip → tracked-person jump link

**Files:**
- Modify: `index.html`

- [ ] **Step 1: Update `_renderGuestList()` to show jump link**

Find `function _renderGuestList()` (~line 5355). The chip template currently renders:

```js
<span style="color:var(--text)">${escHtml(g.name)}</span>
<button onclick="_trackGuestAsPerson(${i})" ...>➕</button>
<button onclick="_removeModalGuest(${i})" ...>×</button>
```

Add a jump-to-profile link before the ➕ button, shown only when `g.person_id` is set:

```js
${g.person_id
  ? `<button onclick="closeModal();openPersonDetail('${escHtml(g.person_id)}')"
       title="Open ${escHtml(g.name)}'s profile"
       style="background:none;border:none;cursor:pointer;color:var(--accent2);font-size:11px;padding:0 2px;line-height:1;font-family:'JetBrains Mono',monospace">→</button>`
  : ''
}
```

`g.person_id` is now returned by `getEpisodeGuests` (updated in Task 1).

- [ ] **Step 2: Commit**

```bash
git add index.html
git commit -m "feat(appearances): guest chip → tracked-person jump link in episode modal"
```

---

## Task 7: Find Appearances panel — scaffold

**Files:**
- Modify: `index.html`

- [ ] **Step 1: Add `_appearanceFinderOpen` state variable**

Near the other appearance state variables (in the `// ── APPEARANCES ──` block added in Task 2), add:

```js
let _appearanceFinderOpen = false;
let _appearanceCandidates = [];   // current iTunes results awaiting review
```

- [ ] **Step 2: Add the appearances section to `openPersonDetail`**

Find the end of `openPersonDetail` (~line 3006+), where the All Episodes section is appended. After that block, append the Find Appearances section:

```js
// Find Appearances section
const apSection = document.createElement('div');
apSection.id = 'appearance-finder-section';
apSection.style.cssText = 'margin-top:32px';
apSection.innerHTML = `
  <div class="detail-section-title" style="display:flex;align-items:center;gap:10px">
    Guest Appearances
    <span style="color:var(--muted);font-weight:400;font-size:10px">(${(currentPerson.appearances||[]).length} saved)</span>
    <button onclick="openAppearanceFinder('${person.id}')"
      class="btn btn-ghost"
      style="font-size:10px;padding:3px 10px;margin-left:auto">
      🔍 Find Appearances
    </button>
  </div>
  <div id="appearance-finder-panel" style="display:none;margin-top:12px;padding:14px;background:var(--surface2);border:1px solid var(--border);border-radius:6px"></div>
  <div id="appearance-saved-list" style="margin-top:10px"></div>`;
wrap.appendChild(apSection);

// Render saved appearances
_renderSavedAppearances(person.id);
```

- [ ] **Step 3: Implement `openAppearanceFinder(personId)`**

Add this function in the `// ── APPEARANCES ──` block:

```js
function openAppearanceFinder(personId) {
  const panel = document.getElementById('appearance-finder-panel');
  if (!panel) return;
  _appearanceFinderOpen = !_appearanceFinderOpen;
  if (!_appearanceFinderOpen) {
    panel.style.display = 'none';
    return;
  }
  panel.style.display = '';
  panel.innerHTML = `
    <div style="font-family:'JetBrains Mono',monospace;font-size:10px;color:var(--muted);margin-bottom:10px;letter-spacing:.05em">
      SEARCH PODCASTS
    </div>
    <div style="display:flex;gap:8px;margin-bottom:12px">
      <input id="ap-search-input" type="text"
        value="${escHtml(currentPerson?.name || '')}"
        placeholder="Search name…"
        style="flex:1;background:var(--bg);border:1px solid var(--border);border-radius:4px;color:var(--text);font-family:'JetBrains Mono',monospace;font-size:12px;padding:5px 8px">
      <button onclick="searchAppearances('${escHtml(personId)}')"
        class="btn btn-primary" style="font-size:11px;padding:5px 12px">Search</button>
    </div>
    <div id="ap-candidate-list"></div>
    <div style="margin-top:14px;border-top:1px solid var(--border);padding-top:12px">
      <div style="font-family:'JetBrains Mono',monospace;font-size:10px;color:var(--muted);margin-bottom:8px;letter-spacing:.05em">
        OR PASTE A URL (YouTube, podcast, article)
      </div>
      <div style="display:flex;gap:8px">
        <input id="ap-url-input" type="text" placeholder="https://…"
          style="flex:1;background:var(--bg);border:1px solid var(--border);border-radius:4px;color:var(--text);font-family:'JetBrains Mono',monospace;font-size:12px;padding:5px 8px"
          onkeydown="if(event.key==='Enter')addAppearanceFromUrl('${escHtml(personId)}')">
        <button onclick="addAppearanceFromUrl('${escHtml(personId)}')"
          class="btn btn-ghost" style="font-size:11px;padding:5px 12px">Add</button>
      </div>
      <div id="ap-url-status" style="font-size:11px;color:var(--muted);margin-top:6px;font-family:'JetBrains Mono',monospace"></div>
    </div>`;
}
```

- [ ] **Step 4: Commit**

```bash
git add index.html
git commit -m "feat(appearances): Find Appearances panel scaffold in person detail view"
```

---

## Task 8: iTunes search + candidate list rendering

**Files:**
- Modify: `index.html`

- [ ] **Step 1: Implement `searchAppearances(personId)`**

Add in the `// ── APPEARANCES ──` block:

```js
async function searchAppearances(personId) {
  const input = document.getElementById('ap-search-input');
  const listEl = document.getElementById('ap-candidate-list');
  if (!input || !listEl) return;

  const query = input.value.trim();
  if (!query) return;

  listEl.innerHTML = '<div style="color:var(--muted);font-size:11px;font-family:\'JetBrains Mono\',monospace">Searching iTunes…</div>';
  _appearanceCandidates = [];

  try {
    const url = `https://itunes.apple.com/search?term=${encodeURIComponent(query)}&media=podcast&entity=podcastEpisode&limit=20`;
    const resp = await fetch(url);
    if (!resp.ok) throw new Error(`iTunes returned ${resp.status}`);
    const data = await resp.json();
    const results = data.results || [];

    // Filter out already-saved appearances
    const person = persons.find(p => p.id === personId);
    const savedLinks = new Set((person?.appearances || []).map(a => a.link));

    _appearanceCandidates = results
      .filter(r => r.episodeUrl && !savedLinks.has(r.episodeUrl))
      .map(r => ({
        title:    r.trackName    || 'Untitled',
        hostName: r.collectionName || '',
        link:     r.episodeUrl,
        desc:     (r.description || '').slice(0, 300),
        date:     r.releaseDate  || '',
        platform: 'podcast',
        addedHow: 'search',
      }));

    _renderAppearanceCandidates(personId, listEl);
  } catch (err) {
    listEl.innerHTML = `<div style="color:var(--youtube);font-size:11px;font-family:'JetBrains Mono',monospace">Search failed: ${escHtml(err.message)}</div>`;
  }
}
```

- [ ] **Step 2: Implement `_renderAppearanceCandidates(personId, listEl)`**

```js
function _renderAppearanceCandidates(personId, listEl) {
  if (!_appearanceCandidates.length) {
    listEl.innerHTML = '<div style="color:var(--muted);font-size:11px;font-family:\'JetBrains Mono\',monospace;padding:8px 0">No new results found.</div>';
    return;
  }
  listEl.innerHTML = _appearanceCandidates.map((c, i) => `
    <div id="ap-cand-${i}" style="display:flex;gap:10px;align-items:flex-start;padding:8px 0;border-bottom:1px solid var(--border)">
      <div style="flex:1;min-width:0">
        <div style="font-size:12px;color:var(--text);font-family:'JetBrains Mono',monospace;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${escHtml(c.title)}</div>
        <div style="font-size:10px;color:var(--muted);margin-top:2px">
          🎙 ${escHtml(c.hostName)} · ${c.date ? new Date(c.date).toLocaleDateString('en-US',{month:'short',year:'numeric'}) : ''}
        </div>
        ${c.desc ? `<div style="font-size:10px;color:var(--muted);margin-top:3px;line-height:1.4;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden">${escHtml(c.desc)}</div>` : ''}
      </div>
      <div style="display:flex;gap:4px;flex-shrink:0">
        <button onclick="approveAppearance('${escHtml(personId)}', ${i})"
          style="background:var(--accent);border:none;border-radius:4px;color:#000;font-family:'JetBrains Mono',monospace;font-size:10px;padding:3px 8px;cursor:pointer">✓ Add</button>
        <button onclick="skipAppearanceCandidate(${i})"
          style="background:none;border:1px solid var(--border);border-radius:4px;color:var(--muted);font-family:'JetBrains Mono',monospace;font-size:10px;padding:3px 8px;cursor:pointer">✗</button>
      </div>
    </div>`).join('');
}

function skipAppearanceCandidate(idx) {
  const el = document.getElementById(`ap-cand-${idx}`);
  if (el) el.remove();
}
```

- [ ] **Step 3: Commit**

```bash
git add index.html
git commit -m "feat(appearances): iTunes podcast search + candidate list rendering"
```

---

## Task 9: Approve candidate + `approveAppearance()`

**Files:**
- Modify: `index.html`

- [ ] **Step 1: Implement `approveAppearance(personId, idx)`**

```js
async function approveAppearance(personId, idx) {
  const candidate = _appearanceCandidates[idx];
  if (!candidate) return;

  const person = persons.find(p => p.id === personId);
  if (!person) return;

  // Build AppearanceEntry
  const hostPersonId = _resolveHostPersonId(candidate.hostName);
  const appearance = {
    id:           _makeAppearanceId(personId, candidate.link),
    isAppearance: true,
    personId,
    platform:     candidate.platform || 'podcast',
    title:        candidate.title,
    link:         candidate.link,
    desc:         candidate.desc  || '',
    date:         candidate.date  || '',
    hostName:     candidate.hostName || '',
    hostPersonId: hostPersonId,
    episodeId:    null,
    addedHow:     candidate.addedHow || 'search',
  };

  // Deduplication guard
  if ((person.appearances || []).some(a => a.link === appearance.link)) {
    skipAppearanceCandidate(idx);
    return;
  }

  person.appearances = [...(person.appearances || []), appearance];
  saveState();
  rebuildAllEntries();
  renderPersonCard(person, false);
  _renderSavedAppearances(personId);
  skipAppearanceCandidate(idx);

  // Update count label
  const countEl = document.querySelector('#appearance-finder-section .detail-section-title span');
  if (countEl) countEl.textContent = `(${person.appearances.length} saved)`;

  // Link guest in SQLite if host is tracked and backend is online
  if (hostPersonId && _backendOnline && candidate.hostName) {
    _dbClient.linkGuestToPerson(candidate.hostName, personId).catch(() => {});
  }
}
```

- [ ] **Step 2: Implement `_renderSavedAppearances(personId)`**

This renders the list of already-saved appearances in the detail panel:

```js
function _renderSavedAppearances(personId) {
  const listEl = document.getElementById('appearance-saved-list');
  if (!listEl) return;
  const person = persons.find(p => p.id === personId);
  const appearances = person?.appearances || [];
  if (!appearances.length) {
    listEl.innerHTML = '<div style="color:var(--muted);font-size:11px;font-family:\'JetBrains Mono\',monospace;padding:8px 0">No appearances saved yet.</div>';
    return;
  }
  listEl.innerHTML = appearances
    .slice().sort((a, b) => new Date(b.date || 0) - new Date(a.date || 0))
    .map(a => `
      <div class="detail-entry-row"
           data-eid="${escHtml(a.id)}"
           onclick="openEntry(${JSON.stringify(a).replace(/"/g,'&quot;')})">
        <div class="detail-entry-dot" style="background:var(--accent);opacity:0.65"></div>
        <div class="detail-entry-body">
          <div class="detail-entry-title">${escHtml(a.title)}</div>
          <div class="detail-entry-meta">
            <span>🎤 ${escHtml(a.hostName || 'Guest')}</span>
            <span>${a.date ? timeAgo(a.date) : ''}</span>
          </div>
        </div>
        <button onclick="event.stopPropagation();removeAppearance('${escHtml(personId)}','${escHtml(a.id)}')"
          title="Remove this appearance"
          style="flex-shrink:0;background:none;border:none;cursor:pointer;color:var(--muted);font-size:14px;padding:2px 4px;line-height:1;opacity:0;transition:opacity .15s"
          class="detail-entry-delete">✕</button>
      </div>`).join('');
}
```

- [ ] **Step 3: Implement `removeAppearance(personId, appearanceId)`**

```js
function removeAppearance(personId, appearanceId) {
  const person = persons.find(p => p.id === personId);
  if (!person) return;
  person.appearances = (person.appearances || []).filter(a => a.id !== appearanceId);
  saveState();
  rebuildAllEntries();
  renderPersonCard(person, false);
  _renderSavedAppearances(personId);
  const countEl = document.querySelector('#appearance-finder-section .detail-section-title span');
  if (countEl) countEl.textContent = `(${person.appearances.length} saved)`;
}
```

- [ ] **Step 4: Verify approve flow**

1. Open a person detail (e.g. Karl Friston)
2. Click "🔍 Find Appearances"
3. The panel opens with Karl's name pre-filled
4. Click Search — iTunes results appear
5. Click ✓ Add on a result — it disappears from the candidate list
6. Saved appearances list at the bottom updates
7. Close and reopen person detail — appearance is still there (localStorage persisted)
8. Karl's card now shows the appearance mixed with his entries

- [ ] **Step 5: Commit**

```bash
git add index.html
git commit -m "feat(appearances): approveAppearance, _renderSavedAppearances, removeAppearance"
```

---

## Task 10: Manual URL paste + `_resolveAppearanceUrl()`

**Files:**
- Modify: `index.html`

- [ ] **Step 1: Implement `_extractYouTubeId(url)` if not already present**

Check if `_extractYouTubeId` already exists in the file (search for it). If not, add it:

```js
function _extractYouTubeId(url) {
  if (!url) return null;
  // youtu.be/ID, youtube.com/watch?v=ID, youtube.com/shorts/ID, youtube.com/embed/ID
  const m = url.match(/(?:youtu\.be\/|youtube\.com\/(?:watch\?v=|shorts\/|embed\/|v\/))([A-Za-z0-9_-]{11})/);
  return m ? m[1] : null;
}
```

- [ ] **Step 2: Implement `_resolveAppearanceUrl(url)`**

```js
async function _resolveAppearanceUrl(url) {
  // Returns { title, date, platform, hostName, desc, link }
  // Canonicalises YouTube URLs, tries oEmbed for title
  if (!url || !url.startsWith('http')) return null;

  const ytId = _extractYouTubeId(url);
  if (ytId) {
    const canonical = `https://www.youtube.com/watch?v=${ytId}`;
    try {
      const resp = await fetch(
        `https://www.youtube.com/oembed?url=${encodeURIComponent(canonical)}&format=json`
      );
      if (resp.ok) {
        const d = await resp.json();
        return { title: d.title || canonical, date: '', platform: 'youtube',
                 hostName: d.author_name || '', desc: '', link: canonical };
      }
    } catch (e) { /* fall through */ }
    return { title: url, date: '', platform: 'youtube', hostName: '', desc: '', link: canonical };
  }

  // Non-YouTube: return URL as title, unknown platform
  return { title: url, date: '', platform: 'other', hostName: '', desc: '', link: url };
}
```

- [ ] **Step 3: Implement `addAppearanceFromUrl(personId)`**

```js
async function addAppearanceFromUrl(personId) {
  const input    = document.getElementById('ap-url-input');
  const statusEl = document.getElementById('ap-url-status');
  if (!input || !statusEl) return;

  const raw = input.value.trim();
  if (!raw) return;

  statusEl.textContent = 'Resolving…';

  const resolved = await _resolveAppearanceUrl(raw);
  if (!resolved) {
    statusEl.textContent = 'Could not resolve URL.';
    return;
  }

  const person = persons.find(p => p.id === personId);
  if (!person) return;

  // Dedup
  if ((person.appearances || []).some(a => a.link === resolved.link)) {
    statusEl.textContent = 'Already saved.';
    return;
  }

  const hostPersonId = _resolveHostPersonId(resolved.hostName);
  const appearance = {
    id:           _makeAppearanceId(personId, resolved.link),
    isAppearance: true,
    personId,
    platform:     resolved.platform,
    title:        resolved.title,
    link:         resolved.link,
    desc:         resolved.desc || '',
    date:         resolved.date || '',
    hostName:     resolved.hostName || '',
    hostPersonId,
    episodeId:    null,
    addedHow:     'manual',
  };

  person.appearances = [...(person.appearances || []), appearance];
  saveState();
  rebuildAllEntries();
  renderPersonCard(person, false);
  _renderSavedAppearances(personId);

  const countEl = document.querySelector('#appearance-finder-section .detail-section-title span');
  if (countEl) countEl.textContent = `(${person.appearances.length} saved)`;

  input.value = '';
  statusEl.textContent = `Added: ${resolved.title.slice(0, 60)}`;
  setTimeout(() => { if (statusEl) statusEl.textContent = ''; }, 3000);

  if (hostPersonId && _backendOnline && resolved.hostName) {
    _dbClient.linkGuestToPerson(resolved.hostName, personId).catch(() => {});
  }
}
```

- [ ] **Step 4: Verify manual paste**

1. Open Find Appearances panel for Karl Friston
2. Paste a YouTube URL (e.g. a Lex Fridman episode featuring Karl)
3. Click Add — status shows "Resolving…" then "Added: [title]"
4. Appearance appears in the saved list
5. Open it — modal shows "🎤 Guest Appearance" header, Open Video button works

- [ ] **Step 5: Commit**

```bash
git add index.html
git commit -m "feat(appearances): manual URL paste — _resolveAppearanceUrl + addAppearanceFromUrl"
```

---

## Task 11: Detail panel filter + appearances count in header

**Files:**
- Modify: `index.html`

- [ ] **Step 1: Add 'appearance' to the detail panel filter buttons**

In `openPersonDetail`, find the `filterBtns` construction (~line 2859):

```js
const filterBtns = ['all', 'podcast', 'youtube', 'twitter', 'blog', 'article'].map(f => {
```

Add `'appearance'` to this array:

```js
const filterBtns = ['all', 'podcast', 'youtube', 'twitter', 'blog', 'article', 'appearance'].map(f => {
  if (f === 'appearance') {
    if (!(currentPerson.appearances||[]).length) return '';
    const active = _detailFilter === 'appearance';
    return `<button class="filter-chip${active?' active':''}" onclick="setDetailFilter('appearance')">🎤 Appearances</button>`;
  }
  // ... existing logic unchanged
```

- [ ] **Step 2: Update `setDetailFilter` to handle 'appearance'**

Find `function setDetailFilter` (or wherever `_detailFilter` is set and the entry list re-renders). Currently it filters `person.entries` by platform. Update the entry list rendering to use the merged list when filter is 'appearance':

In the `openPersonDetail` entry list section (~line 2853):
```js
let entries = [...(person.entries || [])];
if (_detailFilter !== 'all') entries = entries.filter(e => e.platform === _detailFilter);
```

Update to:
```js
let entries = _detailFilter === 'appearance'
  ? []   // appearances shown in their own section below, not here
  : [...(person.entries || [])];
if (_detailFilter !== 'all' && _detailFilter !== 'appearance')
  entries = entries.filter(e => e.platform === _detailFilter);
```

(The saved appearances list `#appearance-saved-list` already handles the appearance view; no need to show them in the main entry list too.)

- [ ] **Step 3: Update the "Content" section title to show total count including appearances**

Find (~line 2978):
```js
<span style="..."> (${person.entries?.length || 0} entries)</span>
```

Update to:
```js
<span style="...">(${(person.entries?.length||0) + (person.appearances?.length||0)} items)</span>
```

- [ ] **Step 4: Final end-to-end verification**

Run through the complete flow:

1. Open Karl Friston's detail panel → "0 saved" appearances count shown
2. Click "🔍 Find Appearances" → panel opens, Karl's name pre-filled
3. Click Search → iTunes results load (podcast episodes mentioning Karl)
4. Add 2–3 results → count updates to "3 saved"
5. Paste a YouTube URL → resolves and adds as manual appearance
6. Close detail panel, reopen → all appearances persisted
7. Karl's card shows 🎤 chips mixed with his book entries, sorted by date
8. Click a 🎤 chip → modal shows "🎤 Guest Appearance", "Guest on [Show]"
9. Filter bar → click "🎤 Appearances" → only cards with appearances shown
10. Timeline view → appearances appear with 🎤 bullet
11. Saved appearances in detail panel → click ✕ to remove one → count decrements

- [ ] **Step 5: Commit**

```bash
git add index.html
git commit -m "feat(appearances): appearance filter in detail panel + item count in header"
```

---

## Self-Review

### Spec coverage check

| Spec requirement | Task |
|---|---|
| `AppearanceEntry` type + `person.appearances[]` | Task 2 |
| "🔍 Find Appearances" button on detail panel | Task 7 |
| iTunes Search API discovery | Task 8 |
| YouTube search link (opens browser) | Task 7 Step 3 — panel HTML includes a note; YouTube is handled via manual paste in Task 10 |
| Manual URL paste field | Task 10 |
| Candidate review with ✓/✗ | Task 8–9 |
| Deduplication on `link` + YouTube canonicalization | Task 10 Step 2 (`_resolveAppearanceUrl`) |
| Appearances merged with entries on card, top 4 | Task 3 |
| 🎤 badge on card chips | Task 3 Step 3 |
| 🎤 Appearances filter chip | Task 3 Step 4 |
| Entry modal — 🎤 header + host subtitle + jump link | Task 5 |
| Guest chip → person jump link | Task 6 |
| `PATCH /api/db/guests/link` backend | Task 1 |
| `link_guest_to_person` called on approve | Task 9 Step 1 |
| `hostPersonId` + `episodeId` resolution | Task 9 Step 1 (`_resolveHostPersonId`), `episodeId` left null (not in scope for v1) |
| Remove appearance | Task 9 Step 3 |
| Backward-compat (`appearances || []`) | Task 2, 3, 9 — all access via `|| []` |
| Appearances in timeline | Task 4 |
| `rebuildAllEntries` includes appearances | Task 2 Step 2 |

**One gap found:** The spec says "YouTube search link opens in a new tab" as a distinct step in the discovery flow. The current panel has a manual URL paste field but no explicit YouTube search link button. **Fix:** In Task 7 Step 3, add a "🔍 Search YouTube" link below the iTunes section:

```html
<a href="https://www.youtube.com/results?search_query=${encodeURIComponent(name)}+interview"
   target="_blank" rel="noopener"
   style="font-size:10px;color:var(--accent2);font-family:'JetBrains Mono',monospace">
  🔍 Search YouTube ↗
</a>
<span style="font-size:10px;color:var(--muted);font-family:'JetBrains Mono',monospace"> — copy a URL and paste it below</span>
```

Add this to the panel HTML in Task 7 Step 3, between the iTunes section and the manual paste section. The `name` value should be the person's name (use `escHtml(currentPerson?.name||'')`).

### Type consistency check ✅
- `_makeAppearanceId` defined in Task 2, used in Task 9 and 10
- `_resolveHostPersonId` defined in Task 2, used in Task 9 and 10
- `_mergeEntriesAndAppearances` defined in Task 2, used in Task 3 and 4
- `_renderSavedAppearances` defined in Task 9, called in Task 7 and 9
- `approveAppearance(personId, idx)` — idx is the index into `_appearanceCandidates[]`, consistent with Task 8 onclick
- `removeAppearance(personId, appearanceId)` — id string, consistent with Task 9 Step 3

### Placeholder scan ✅
No TBDs, no "implement later", all steps have code.
