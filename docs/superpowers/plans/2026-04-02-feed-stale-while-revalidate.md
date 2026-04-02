# Feed Stale-While-Revalidate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Automatically refresh stale feeds (> 6 hours old) in the background on page load and when a person card is opened, while showing cached data instantly.

**Architecture:** Add a thin `ensureFresh(person)` function that checks `person.lastUpdated` against a 6-hour TTL and either no-ops, fires a background `fetchPerson`, or blocks for a first-ever fetch. Two trigger points: staggered page load and `openPersonDetail`. A pulsing dot badge on the card signals background activity without disrupting the existing full-spinner for manual refreshes.

**Tech Stack:** Vanilla JS, single `index.html` file, no build step. All changes are in `index.html`.

---

## File Map

| Location | Change |
|----------|--------|
| `index.html:1309` | Add `FEED_TTL_MS` constant after `CORS_FALLBACK2` |
| `index.html:392` | Add `.bg-refresh-dot` CSS + `@keyframes pulse-dot` after existing `@keyframes spin` |
| `index.html:~256` | Add `position: relative` to `.person-card` CSS rule (new rule) |
| `index.html:1870` | Update `saveState` to also reset `backgroundRefreshing: false` |
| `index.html:~3052` | Add `ensureFresh(person)` function after `fetchPerson` closes |
| `index.html:2812` | Inject `bgDot` HTML into `renderPersonCard` card template |
| `index.html:1982` | Call `ensureFresh(person)` inside `openPersonDetail` |
| `index.html:4789` | Add staggered `ensureFresh` calls after `renderAllCards()` in init |

---

## Task 1: Add `FEED_TTL_MS` constant

**Files:**
- Modify: `index.html:1309`

- [ ] **Step 1: Add the constant**

Find this line (line 1309):
```js
const CORS_FALLBACK2 = 'https://api.codetabs.com/v1/proxy?quest=';
```

Add immediately after it:
```js
const FEED_TTL_MS = 6 * 60 * 60 * 1000  // 6 hours — background refresh threshold
```

- [ ] **Step 2: Verify**

Open `index.html` in a browser. Open DevTools console. Run:
```js
console.log(FEED_TTL_MS) // Expected: 21600000
```

- [ ] **Step 3: Commit**

```bash
cd "/Users/esen/Documents/Cem Code/Pulse"
git add index.html
git commit -m "feat(pulse): add FEED_TTL_MS constant (6h)"
```

---

## Task 2: Add badge CSS

**Files:**
- Modify: `index.html:~393` (after `@keyframes spin` block)

- [ ] **Step 1: Add `.person-card` position rule**

Find this CSS rule (around line 256):
```css
  @keyframes cardIn {
    from { opacity:0; transform:translateY(12px); }
    to   { opacity:1; transform:translateY(0); }
  }
```

Add immediately after it:
```css

  .person-card { position: relative; }
```

- [ ] **Step 2: Add dot CSS**

Find this block (around line 392):
```css
  .card-refresh-btn.spinning { animation: spin 0.8s linear infinite; }
  @keyframes spin { to { transform: rotate(360deg); } }
```

Add immediately after it:
```css

  .bg-refresh-dot {
    position: absolute;
    top: 8px;
    right: 8px;
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--accent, #7c6af7);
    opacity: 0.85;
    animation: pulse-dot 1.4s ease-in-out infinite;
    pointer-events: none;
  }
  @keyframes pulse-dot {
    0%, 100% { transform: scale(1);   opacity: 0.85; }
    50%       { transform: scale(1.5); opacity: 0.4;  }
  }
```

- [ ] **Step 3: Verify CSS exists**

Open `index.html` in a browser. In DevTools console run:
```js
const d = document.createElement('div')
d.className = 'bg-refresh-dot'
document.body.appendChild(d)
// Expected: a small pulsing purple dot appears in top-left of viewport
setTimeout(() => d.remove(), 3000)
```

- [ ] **Step 4: Commit**

```bash
cd "/Users/esen/Documents/Cem Code/Pulse"
git add index.html
git commit -m "feat(pulse): add bg-refresh-dot badge CSS"
```

---

## Task 3: Update `saveState` to exclude `backgroundRefreshing`

**Files:**
- Modify: `index.html:1870`

- [ ] **Step 1: Update the serialization spread**

Find this line (line 1870):
```js
    localStorage.setItem('pw-persons',    JSON.stringify(persons.map(p => ({ ...p, loading: false }))));
```

Replace it with:
```js
    localStorage.setItem('pw-persons',    JSON.stringify(persons.map(p => ({ ...p, loading: false, backgroundRefreshing: false }))));
```

There is a second occurrence of this same pattern at line ~1933 (inside the feed migration block). Find it:
```js
      localStorage.setItem('pw-persons', JSON.stringify(persons.map(p => ({ ...p, loading: false }))));
```

Replace it with:
```js
      localStorage.setItem('pw-persons', JSON.stringify(persons.map(p => ({ ...p, loading: false, backgroundRefreshing: false }))));
```

- [ ] **Step 2: Verify transient state is not persisted**

Open `index.html` in browser. In DevTools console:
```js
// Simulate backgroundRefreshing on a person
persons[0].backgroundRefreshing = true
saveState()
const saved = JSON.parse(localStorage.getItem('pw-persons'))
console.log(saved[0].backgroundRefreshing) // Expected: false
```

- [ ] **Step 3: Commit**

```bash
cd "/Users/esen/Documents/Cem Code/Pulse"
git add index.html
git commit -m "feat(pulse): exclude backgroundRefreshing from localStorage serialization"
```

---

## Task 4: Add `ensureFresh` function

**Files:**
- Modify: `index.html:~3052` (after `fetchPerson` closing brace)

- [ ] **Step 1: Locate insertion point**

Find the end of `fetchPerson`. It ends with (around line 3051):
```js
  if (btn) btn.classList.remove('spinning');
}
```

Immediately after that closing brace, add:

```js

// ── STALE-WHILE-REVALIDATE ──
// Checks person.lastUpdated against FEED_TTL_MS.
// - Never fetched       → fetchPerson (fire-and-forget, full spinner)
// - Age >= FEED_TTL_MS  → fetchPerson in background, show dot badge
// - Age <  FEED_TTL_MS  → no-op (still fresh)
// Guards against concurrent fetches (loading or backgroundRefreshing already set).
function ensureFresh(person) {
  if (!person) return
  if (person.loading || person.backgroundRefreshing) return

  if (!person.lastUpdated) {
    fetchPerson(person)
    return
  }

  const age = Date.now() - new Date(person.lastUpdated).getTime()
  if (age < FEED_TTL_MS) return

  person.backgroundRefreshing = true
  renderPersonCard(person, false)

  fetchPerson(person).finally(() => {
    person.backgroundRefreshing = false
  })
}
```

- [ ] **Step 2: Verify function exists**

Open `index.html` in browser. In DevTools console:
```js
console.log(typeof ensureFresh) // Expected: "function"
```

- [ ] **Step 3: Test the guard (no-op when loading)**

```js
const p = persons[0]
p.loading = true
ensureFresh(p) // should be a no-op
console.log('guard OK — no double fetch triggered')
p.loading = false
```

- [ ] **Step 4: Test the fresh path (no-op within TTL)**

```js
const p = persons[0]
p.lastUpdated = new Date().toISOString() // just now
ensureFresh(p) // should be a no-op
console.log('fresh path OK — no fetch triggered')
```

- [ ] **Step 5: Test the stale path (background fetch fires)**

```js
const p = persons[0]
p.lastUpdated = new Date(Date.now() - 7 * 60 * 60 * 1000).toISOString() // 7 hours ago
ensureFresh(p)
console.log('backgroundRefreshing:', p.backgroundRefreshing) // Expected: true
// Badge dot should now be visible on first card
```

- [ ] **Step 6: Commit**

```bash
cd "/Users/esen/Documents/Cem Code/Pulse"
git add index.html
git commit -m "feat(pulse): add ensureFresh() stale-while-revalidate function"
```

---

## Task 5: Inject badge dot into `renderPersonCard`

**Files:**
- Modify: `index.html:2802` (inside `renderPersonCard`)

- [ ] **Step 1: Add `bgDot` variable**

Find this block (around line 2802):
```js
  const lastUpdated = person.lastUpdated ? 'Updated ' + timeAgo(new Date(person.lastUpdated)) : 'Never fetched';
  const fetchErrors = person.fetchErrors || [];
```

Add one line before it:
```js
  const bgDot       = person.backgroundRefreshing ? '<div class="bg-refresh-dot"></div>' : '';
  const lastUpdated = person.lastUpdated ? 'Updated ' + timeAgo(new Date(person.lastUpdated)) : 'Never fetched';
  const fetchErrors = person.fetchErrors || [];
```

- [ ] **Step 2: Inject dot into card template**

Find this line inside the `card.innerHTML` template (around line 2812):
```js
  card.innerHTML = `
    <div class="card-header" onclick="openPersonDetail('${person.id}')">
```

Replace it with:
```js
  card.innerHTML = `
    ${bgDot}
    <div class="card-header" onclick="openPersonDetail('${person.id}')">
```

- [ ] **Step 3: Verify dot renders and disappears**

Open `index.html` in browser. In DevTools console:
```js
const p = persons[0]
p.backgroundRefreshing = true
renderPersonCard(p, false)
// Expected: small pulsing purple dot visible in top-right of first card

setTimeout(() => {
  p.backgroundRefreshing = false
  renderPersonCard(p, false)
  console.log('dot removed OK')
}, 3000)
```

- [ ] **Step 4: Commit**

```bash
cd "/Users/esen/Documents/Cem Code/Pulse"
git add index.html
git commit -m "feat(pulse): render bg-refresh-dot badge in person cards"
```

---

## Task 6: Wire `ensureFresh` into `openPersonDetail`

**Files:**
- Modify: `index.html:1980`

- [ ] **Step 1: Add `ensureFresh` call**

Find `openPersonDetail` (line 1980):
```js
function openPersonDetail(personId) {
  const person = persons.find(p => p.id === personId);
  if (!person) return;
  currentPerson   = person;
```

Replace with:
```js
function openPersonDetail(personId) {
  const person = persons.find(p => p.id === personId);
  if (!person) return;
  ensureFresh(person);
  currentPerson   = person;
```

- [ ] **Step 2: Verify in browser**

Open `index.html`. Set a person's `lastUpdated` to 7 hours ago via console:
```js
persons[0].lastUpdated = new Date(Date.now() - 7 * 60 * 60 * 1000).toISOString()
saveState()
```

Reload the page. Click on that person's card.
Expected: badge dot appears on the card, fetch runs silently in the background, dot disappears when done.

- [ ] **Step 3: Verify fresh person is not re-fetched**

```js
persons[0].lastUpdated = new Date().toISOString() // just now
saveState()
```

Reload. Click the card.
Expected: no badge dot, no fetch triggered (check Network tab — no RSS/feed requests).

- [ ] **Step 4: Commit**

```bash
cd "/Users/esen/Documents/Cem Code/Pulse"
git add index.html
git commit -m "feat(pulse): trigger ensureFresh on person card open"
```

---

## Task 7: Wire staggered `ensureFresh` into page load

**Files:**
- Modify: `index.html:4788`

- [ ] **Step 1: Add staggered init calls**

Find the init sequence at the bottom of the file (around line 4785):
```js
loadState();
loadConfig();
_restoreVaultHandle();  // async — restores Obsidian vault handle if permission still granted
_checkBackend();        // async — detect if Pulse backend is running on localhost:5001
renderAllCards();
renderTagFilterRow();
updateStatus();
```

Replace with:
```js
loadState();
loadConfig();
_restoreVaultHandle();  // async — restores Obsidian vault handle if permission still granted
_checkBackend();        // async — detect if Pulse backend is running on localhost:5001
renderAllCards();
renderTagFilterRow();
updateStatus();
// Stale-while-revalidate: check each person after UI is rendered.
// 600ms stagger avoids hammering CORS proxies simultaneously on load.
persons.forEach((person, i) => {
  setTimeout(() => ensureFresh(person), i * 600)
})
```

- [ ] **Step 2: Verify stagger timing in browser**

Open `index.html`. Open DevTools Network tab, filter by "Fetch/XHR".

Set all persons to stale (7h ago) via console before reload:
```js
persons.forEach(p => { p.lastUpdated = new Date(Date.now() - 7*60*60*1000).toISOString() })
saveState()
```

Reload the page.
Expected:
- UI renders instantly with cached data
- Network requests start arriving ~600ms apart (not all at once)
- Badge dots appear on stale cards progressively, disappear as fetches complete

- [ ] **Step 3: Verify fresh persons are skipped on load**

```js
persons.forEach(p => { p.lastUpdated = new Date().toISOString() })
saveState()
```

Reload. Check Network tab.
Expected: no feed fetch requests fired on load.

- [ ] **Step 4: Commit**

```bash
cd "/Users/esen/Documents/Cem Code/Pulse"
git add index.html
git commit -m "feat(pulse): auto-refresh stale feeds on page load with 600ms stagger"
```

---

## Task 8: End-to-end smoke test

No code changes. Manual verification that all paths work together correctly.

- [ ] **Step 1: First-ever fetch path**

Open DevTools. Set `lastUpdated` to null for one person and delete their entries:
```js
persons[0].lastUpdated = null
persons[0].entries = []
saveState()
```
Reload. Expected: full spinner (not badge dot) appears on that card, entries populate when done.

- [ ] **Step 2: Stale path — page load**

```js
persons.forEach(p => { p.lastUpdated = new Date(Date.now() - 7*60*60*1000).toISOString() })
saveState()
```
Reload. Expected: existing entries show immediately, badge dots appear staggered, dots disappear as refreshes complete, entries update.

- [ ] **Step 3: Fresh path — page load**

```js
persons.forEach(p => { p.lastUpdated = new Date().toISOString() })
saveState()
```
Reload. Expected: no fetches, no dots.

- [ ] **Step 4: Stale path — card open**

```js
persons[1].lastUpdated = new Date(Date.now() - 7*60*60*1000).toISOString()
saveState()
```
Reload. Click the second person's card. Expected: detail view opens instantly, badge dot visible on the card in the background, dot disappears when fetch completes.

- [ ] **Step 5: Manual refresh still works**

Click any card's `↻` button. Expected: full spinner (not dot), entries refresh. Confirm `backgroundRefreshing` guard prevents double-fire if `ensureFresh` also triggers.

- [ ] **Step 6: Final commit**

```bash
cd "/Users/esen/Documents/Cem Code/Pulse"
git add index.html
git commit -m "feat(pulse): stale-while-revalidate feed refresh complete"
```
