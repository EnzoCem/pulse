# CLAUDE.md — Pulse / PersonWatch

This file gives Claude Code full context to continue development of this project.

---

## Project summary

**Pulse** (working title: PersonWatch) is a personal intelligence dashboard for tracking specific people across multiple platforms. The owner follows researchers, podcasters, and thinkers (e.g. Joe Rogan, Michael Levin, Lex Fridman) and wants a single view showing: who published what, recently, across podcast RSS, YouTube, X/Twitter, blogs/Substack, and books.

**Key design constraint:** The app is organized by *person*, not by platform. Existing tools (Feedly, Inoreader, social monitoring SaaS) are platform-first or brand-monitoring tools. This app is person-first.

---

## File structure

```
Pulse/
├── index.html    ← Entire app. Single-file HTML/CSS/JS. No build step.
├── README.md     ← Usage and architecture documentation
└── CLAUDE.md     ← This file. Context for Claude Code.
```

---

## Technical stack

- **Vanilla HTML/CSS/JS** — no framework, no bundler, no npm
- **localStorage** — all persistence (persons, seen entry IDs, notes, tags, config)
- **IndexedDB** — full episode history (iTunes) and Obsidian vault handle
- **CORS proxy chain** — corsproxy.io → allorigins.win → codetabs.com (tried in order)
- **Google Fonts** — Playfair Display, JetBrains Mono, Libre Baskerville
- **No API keys required for core features** — YouTube/podcast RSS is public, X/Twitter uses free Nitter instances, Books uses Google Books API (free)

---

## Data model

### Person (persisted in `localStorage['pw-persons']`)
```js
{
  id:          string,        // e.g. "joe-rogan-1711234567890"
  name:        string,        // display name
  desc:        string,        // optional subtitle
  website:     string,        // optional homepage URL
  avatar:      string,        // optional image URL
  type:        'person'|'source',  // person = individual, source = publication
  feeds: {
    podcast:   string,        // full RSS URL (or "Main RSS Feed" for sources)
    youtube:   string,        // UC… channel ID only
    twitter:   string,        // @username, x.com/user, or rss.app RSS URL
    blog:      string,        // full RSS URL (Substack, personal blog, etc.)
    books:     string,        // optional Google Books search query override
  },
  tags:        string[],      // person-level topics for TOPICS filter bar
  itunesId:    number|null,   // iTunes collection ID (enables full episode history)
  entries:     Entry[],       // max 20, sorted newest first
  lastUpdated: string|null,   // ISO 8601
  fetchErrors: string[],      // platforms that failed on last refresh
  loading:     boolean,       // runtime only — always false when saved
}
```

### Entry (inside person.entries)
```js
{
  id:            string,      // composite key: personId + platform + link, max 80 chars
  personId:      string,
  platform:      'podcast'|'youtube'|'twitter'|'blog'|'books',
  title:         string,
  link:          string,      // URL to open
  desc:          string,      // snippet, max 300 chars, HTML stripped
  date:          string,      // ISO 8601
  author:        string,      // article/book author
  transcriptUrl: string,      // Podcasting 2.0 <podcast:transcript> URL if present
  thumbnail:     string,      // book cover URL (books platform only)
}
```

### localStorage keys
```
'pw-persons'     → Person[]                persons list
'pw-seen'        → string[]                entry IDs opened (clears NEW badge)
'pw-listened'    → string[]                entry IDs marked as listened
'pw-entry-tags'  → Record<id, string[]>    per-entry topic tags (episode-level, not shown in TOPICS)
'pw-notes'       → Record<id, string>      per-entry manual + AI notes
'pw-config'      → object                  API keys and settings
```

---

## Key functions

| Function | Purpose |
|---|---|
| `loadState()` | Load persons + seenIds from localStorage, seed with DEMO_PERSONS if empty |
| `saveState()` | Persist persons + seenIds to localStorage |
| `fetchPerson(person)` | Fetch all feeds in parallel (30s hard cap), update entries |
| `fetchRSS(url, platform, personId)` | Fetch one RSS URL via CORS proxy chain, parse XML, return `{entries, error}` |
| `fetchBooks(query, personId)` | Query Google Books API, return English-only deduplicated Entry[] |
| `fetchTwitterHandle(handle, platform, personId)` | Try each Nitter instance, return entries from first working one |
| `refreshAll()` | Call fetchPerson() for all persons in parallel |
| `renderAllCards()` | Re-render People grid, applying activeTag + currentFilter + searchQuery |
| `renderPersonCard(person, prepend, delay)` | Render or re-render a single person card |
| `renderTimeline()` | Render the Timeline view (all entries, date-grouped) |
| `renderTagFilterRow()` | Render TOPICS bar from person.tags only (not entryTags) |
| `setTagFilter(tag)` | Toggle activeTag, re-render grid/timeline |
| `renameGlobalTag(oldTag)` | Rename tag across all persons.tags |
| `removeGlobalTag(tag)` | Remove tag from all persons.tags and entryTags |
| `rebuildAllEntries()` | Flatten all person.entries into allEntries[] |
| `openEntry(entry)` | Show detail modal, mark entry as seen |
| `setFilter(platform)` | Filter both views to a single platform |
| `switchView('people'\|'timeline'\|'person')` | Toggle between main views |
| `openPersonDetail(personId)` | Open person detail/edit panel |
| `savePersonDetail()` | Save edits from detail panel, re-fetch |
| `addPerson()` | Read form, create person object, save, fetch |
| `deletePerson(id)` | Remove person from state and DOM |
| `resolveYouTubeChannelId(raw)` | Resolve @handle/URL/username to UC… channel ID |
| `_findSourceRSS(name)` | Auto-discover RSS feed for a publication by name |
| `_looksLikeRssUrl(url)` | Returns true for RSS URLs AND bare @username Twitter handles |
| `_extractTwitterHandle(val)` | Extract bare username from @user / x.com/user; null for full URLs |

---

## CSS design system

CSS custom properties defined in `:root`:

```css
--bg         #0d0d0f   /* page background */
--surface    #131318   /* card background */
--surface2   #1a1a22   /* card header / footer */
--border     #2a2a35   /* all borders */
--accent     #e8c84a   /* gold — primary actions, NEW badge, highlights */
--accent2    #4a9eff   /* blue — secondary accent */
--text       #e8e6e0   /* primary text */
--muted      #7a7870   /* secondary text, labels */
--podcast    #e8744a   /* orange */
--youtube    #e84a4a   /* red */
--twitter    #4ab8e8   /* blue */
--blog       #a0e84a   /* green */
--books      #c084fc   /* purple */
```

Fonts: Playfair Display (headings/names), JetBrains Mono (UI/labels), Libre Baskerville (entry descriptions in modal).

---

## Topics / Tags — how they work

- **`person.tags`** — person-level tags, assigned via the inline tag editor on each card or via the Edit profile panel. These are the only tags shown in the **TOPICS** filter bar.
- **`entryTags`** — episode/entry-level tags set inside the entry modal. These are NOT shown in TOPICS and do not affect the TOPICS filter. They are separate per-episode annotations.
- **TOPICS filter** — filters `renderAllCards()` to persons whose `p.tags` includes `activeTag`. Entry-level tags do not affect this filter.
- **Global tag operations** — `renameGlobalTag` and `removeGlobalTag` operate only on `person.tags` (and `entryTags` for removal to keep data clean).

---

## Known limitations / issues

1. **CORS proxy reliability** — three public CORS proxies tried in sequence. All are free services and can be slow/rate-limited. Each proxy has a 7s timeout; the entire fetchPerson call has a 30s hard cap.
2. **X/Twitter via Nitter** — free but fragile. Nitter instances come and go as X blocks them. The `NITTER_INSTANCES` array at the top of the JS can be updated when instances go down.
3. **YouTube channel ID** — stored as `UC…` ID. The form accepts @handles and URLs and auto-resolves on save. If the stored value is not a valid `UC…` ID, YouTube fetching is silently skipped.
4. **Google Books accuracy** — `langRestrict=en` is requested and results are client-filtered to `language === 'en'`, but Google Books metadata is imperfect and some non-English editions may still appear.
5. **No auto-refresh** — Fetching only happens on user action (Refresh All or per-card ↻).
6. **Entry limit** — Each person stores max 20 entries. Cards show only the top 4.

---

## Roadmap (in priority order)

1. **Auto-refresh** — `setInterval` every N minutes, configurable, with a visual countdown
2. **Show more entries** — Expand button on cards to see all 20 (or paginate)
3. **Export/import** — JSON dump of persons list for backup and transfer
4. **Browser notifications** — `Notification API` for new items in background
5. **AI digest** — Weekly summary of each person's activity using Claude API (claude-sonnet-4-6)
6. **Self-hosted backend** — Tiny Node/Deno/Python server for:
   - Removing CORS proxy dependency
   - Background polling (cron)
   - Push notifications via WebSockets
7. **Electron wrapper** — Desktop app, no CORS issues, system tray
8. **Mobile PWA** — Service worker + manifest for home screen install

---

## Conventions for Claude Code

- Keep the app as a **single `index.html`** file until a backend/build step is explicitly introduced
- Do not add npm/node dependencies without explicit request
- CSS goes inside `<style>`, JS inside `<script>` at bottom of `<body>`
- All new JS functions should follow the pattern: pure logic separated from DOM manipulation
- Maintain the design system — use CSS variables, don't hardcode colors
- New platforms follow the same pattern as existing ones in the `PLATFORMS` constant and `hexAlpha` map
- When adding features that require API keys, store them in localStorage under `pw-config` (never hardcode)
- The accent color `--accent` (#e8c84a) is the gold used throughout — keep it consistent
- `person.tags` is for person-level TOPICS filtering only; `entryTags` is for per-episode annotations — do not mix them
