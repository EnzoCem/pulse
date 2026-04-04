# Add Person Redesign — Spec

**Date:** 2026-04-04
**Status:** Approved — ready for implementation
**Scope:** `index.html` — Add Person panel only (no backend changes)

---

## Problem statement

The current Add Person form is a flat list of 5 manual URL inputs (podcast RSS, YouTube channel ID, Twitter RSS, blog URL, books query). It requires the user to know what a channel ID is, where to find an RSS URL, and how each platform works. This is a barrier for new users and slows down adding well-known people.

The new design makes role checkboxes the primary intent signal and auto-discovers feeds from the person's name — with inline manual overrides available for power users.

---

## Design decisions (from brainstorm session)

| Question | Decision |
|---|---|
| Where do role checkboxes appear? | Same screen as name field — no separate step |
| What happens after search with multiple roles? | Auto-select top match per role; user taps another result to override |
| How does Writer role work? | Auto-search Google Books by name + optional Open Library/Goodreads URL override |
| Default checkbox state? | All unchecked — user must pick at least one before Search activates |
| What happens to manual URL fields? | Inline "or paste URL" input below each role's result section |
| X/Twitter in role checkboxes? | No — added manually via card ✎ edit after person is created |

---

## UI flow

### State 1 — Empty panel (before any input)

```
┌─────────────────────────────────────────┐
│ PERSON NAME                             │
│ [____________________________] [🔍]     │
│                                         │
│ WHAT DO THEY DO? (pick at least one)    │
│ ┌─────────────┐ ┌─────────────┐         │
│ │ ☐ 🎙 Podcaster│ │ ☐ ▶ YouTuber│         │
│ └─────────────┘ └─────────────┘         │
│ ┌─────────────┐ ┌─────────────┐         │
│ │ ☐ ✍ Blogger │ │ ☐ 📚 Writer │         │
│ └─────────────┘ └─────────────┘         │
│                                         │
│ [Search — select a role first] (grey)   │
│                                         │
│ 💡 X/Twitter: add via ✎ edit after      │
│    person is created                    │
└─────────────────────────────────────────┘
```

- Search button is **disabled** until at least one role is checked AND name is non-empty
- Roles are presented as toggle chips — gold border + filled dot when checked
- Hint about X/Twitter always visible at the bottom

### State 2 — Roles selected, ready to search

- Name filled in, one or more roles checked → Search button turns gold and activates
- Pressing Search triggers parallel API calls for all checked roles

### State 3 — Results shown (after search)

Each checked role gets its own results section. Layout:
- **Podcast** and **YouTube** results: side by side (2-column grid)
- **Books**: full-width row (3-column book grid)
- **Blogger**: no search results — just the inline URL paste field (Blogger has no auto-discovery)

Per role result section:

```
🎙 PODCAST
┌──────────────────────────────────────┐
│ ● The Tim Ferriss Show               │  ← auto-selected (top match)
│   195 episodes · iTunes              │
└──────────────────────────────────────┘
┌──────────────────────────────────────┐
│ ○ Tim Ferriss Radio                  │  ← alternative (tap to select)
│   12 episodes                        │
└──────────────────────────────────────┘
  ↳ or paste RSS URL directly…         ← inline override input (dashed border)
```

Books section:

```
📚 BOOKS (top English editions)
┌────────────┐ ┌────────────┐ ┌────────────┐
│ ● 4-Hour   │ │ ○ 4-Hour   │ │ ○ Tools of │
│   Workweek │ │   Body     │ │   Titans   │
│ 2007       │ │ 2010       │ │ 2016       │
└────────────┘ └────────────┘ └────────────┘
  ↳ or paste Open Library / Goodreads author URL…
```

Blogger section (no auto-search):

```
✍ BLOG
  ↳ paste blog/Substack RSS URL…
```

### State 4 — Optional details + confirm

Below the results sections, collapsed by default but visible:

```
OPTIONAL DETAILS
[Description ___________] [Avatar URL ___________]
[Topics/tags: ___________]

[  Cancel  ]
[ ✓ Add {Name} ]
```

- **Add button label** dynamically shows the entered name: `✓ Add Tim Ferriss`
- Topics/tags field is free-text, comma-separated (same as current)

---

## Data model changes

No changes to the stored data model. The role checkboxes are **UI-only** — they determine which searches to run and which form fields to show. The resulting `person` object is the same shape as today:

```js
{
  feeds: {
    podcast: string,   // RSS URL (from search result or manual paste)
    youtube: string,   // channel ID (from search result or manual paste)
    blog:    string,   // RSS URL (manual paste only)
    books:   string,   // author name query OR Open Library URL
    twitter: string,   // rss.app/Nitter URL — added via edit, not Add Person
  }
}
```

Optional addition — store which roles were checked so future edit form can reflect them. Skip if it adds complexity.

```js
{
  roles: ['podcaster', 'youtuber', 'writer']   // optional, UI-only hint
}
```

---

## API calls per role

| Role | API | Notes |
|---|---|---|
| Podcaster | iTunes Search API (`entity=podcast`) | Reuse existing iTunes fetch from `searchPersonByName()`; capture `itunesId` from selected result |
| YouTuber | `_findYouTube(name)` — Google Custom Search + handle resolution | Already implemented; returns bare channel ID |
| Blogger | None — manual URL only | Show paste field immediately; `_findBlog()` is no longer called |
| Writer | Google Books API (`volumes?q=inauthor:NAME&langRestrict=en`) | Reuse `fetchBooks()` logic; if user pastes Open Library URL, detect by `openlibrary.org` prefix |

---

## Search result selection logic

For each role:
1. Run API call in parallel with other roles
2. Sort results by relevance (existing ranking from API)
3. Auto-select index 0 (first result)
4. Show up to 3 alternatives the user can tap to switch selection
5. If API returns 0 results → show "Nothing found" message + paste field only

---

## Edge cases

| Scenario | Behaviour |
|---|---|
| Name is empty when Search clicked | Search button stays disabled — no action |
| No roles checked | Search button stays disabled |
| Role checked but API returns no results | Show "Nothing found for [role]" + inline paste field |
| User clears auto-selected result and pastes URL | Paste field value takes priority over selected result |
| Both result selected AND paste field filled | Paste field value wins |
| Blogger checked | Skip auto-search, show paste field immediately |
| Only Writer checked | Search Google Books by name, show book grid |
| Adding duplicate person (same name) | No guard — same as today |

---

## What is NOT changing

- **Add Source tab** — unchanged; still accepts a raw RSS URL for non-person sources
- **X/Twitter handling** — still managed via card ✎ edit, uses Nitter instance fallback
- **Person card rendering** — unchanged; roles stored but not displayed on card (future enhancement)
- **Edit person panel** — out of scope for this spec; will be addressed separately
- **Single-file constraint** — entire change lives inside `index.html`
- **`resolveYouTubeChannelId()`** — still called when user pastes a YouTube URL/handle manually into the inline override field; not needed when a search result is selected (result already contains a bare channel ID)

---

## Success criteria

1. User can add Tim Ferriss (Podcaster + YouTuber + Writer) in under 30 seconds without knowing any feed URLs
2. User can add a niche blogger whose podcast isn't on iTunes by pasting the RSS URL manually
3. The existing demo persons still load correctly after the change
4. No regression in `fetchPerson()`, `renderPersonCard()`, or tag filtering
5. The Add Source flow is unaffected

---

## Out of scope / future

- Role badges displayed on person cards
- Edit person using the same role-based UI
- LinkedIn role
- GitHub role
- Auto-refresh countdown timer
