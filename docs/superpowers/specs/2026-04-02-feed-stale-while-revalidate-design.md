# Feed Stale-While-Revalidate Design

**Date:** 2026-04-02
**Project:** Pulse (PersonWatch)
**Status:** Approved

## Problem

`person.lastUpdated` is stored as an ISO timestamp after every fetch but is never
checked to determine whether a refresh is needed. All refreshes are manual. Users
who open the app after hours away see stale feeds with no automatic update.

## Goal

Show cached feed data instantly on app open and on person card open, while
silently refreshing stale feeds in the background. No disruption to manual
refresh behavior.

## Approach: `ensureFresh(person)`

Keep `fetchPerson` unchanged. Add a thin decision function that wraps it with
TTL logic. Call it from two trigger points.

### Constant

```js
const FEED_TTL_MS = 6 * 60 * 60 * 1000  // 6 hours
```

### New Person Flag

`person.backgroundRefreshing` — boolean, default `false`. Set to `true` before
a background fetch begins, cleared in `.finally()` when `fetchPerson` completes.
Controls badge visibility. Never overlaps with `person.loading` (the full spinner).

### `ensureFresh(person)`

```js
function ensureFresh(person) {
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

**Decision table:**

| State                        | Action                              |
|------------------------------|-------------------------------------|
| Already loading/refreshing   | No-op (guard)                       |
| Never fetched                | `fetchPerson` (no await) — spinner  |
| Age < 6h                     | No-op                               |
| Age ≥ 6h                     | `fetchPerson` void — badge          |

### Trigger 1 — Page Load

After `renderAllCards()` in the init sequence:

```js
persons.forEach((person, i) => {
  setTimeout(() => ensureFresh(person), i * 600)
})
```

- 600ms stagger between persons — avoids hammering CORS proxies simultaneously
- 10 persons = all checks started within 6 seconds
- Non-blocking — UI is fully interactive immediately
- Fresh persons are skipped instantly (no fetch fired)

### Trigger 2 — Person Card Open

Inside `openPersonDetail(personId)`, one line added:

```js
function openPersonDetail(personId) {
  const person = persons.find(p => p.id === personId)
  if (!person) return
  ensureFresh(person)   // new
  // ... rest unchanged
}
```

## Badge Indicator

A small pulsing dot in the card's top-right corner. Distinct from the full
spinner (which is for manual/blocking fetches). Appears only when
`person.backgroundRefreshing === true`.

### CSS

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
}

@keyframes pulse-dot {
  0%, 100% { transform: scale(1);   opacity: 0.85; }
  50%       { transform: scale(1.5); opacity: 0.4;  }
}
```

### HTML injection in `renderPersonCard`

The dot is injected into the card markup conditionally:

```js
const bgDot = person.backgroundRefreshing
  ? `<div class="bg-refresh-dot"></div>`
  : ''
```

Added to the card's top-level container (which already has `position: relative`).
`renderPersonCard` is already called by `fetchPerson` on completion, so the dot
disappears automatically when the fetch finishes.

## What Is Not Changed

- `fetchPerson` — untouched, no new parameters
- `refreshAll`, `refreshDetailPerson` — untouched, still force-fetch
- `saveState` / `loadState` — no schema changes; `backgroundRefreshing` is
  transient and must be excluded from serialization. `saveState` spreads persons
  with `loading: false`; the same spread must also set `backgroundRefreshing: false`.

## Files Changed

- `index.html` — all changes (single-file project):
  - Add `FEED_TTL_MS` constant near other constants
  - Add `ensureFresh` function near `fetchPerson`
  - Add `.bg-refresh-dot` CSS and `@keyframes pulse-dot`
  - Modify `renderPersonCard` to inject dot conditionally
  - Modify `openPersonDetail` to call `ensureFresh`
  - Modify init sequence to stagger `ensureFresh` calls after `renderAllCards()`
