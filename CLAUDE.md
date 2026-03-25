# CLAUDE.md — Pulse / PersonWatch

This file gives Claude Code full context to continue development of this project.

---

## Project summary

**Pulse** (working title: PersonWatch) is a personal intelligence dashboard for tracking specific people across multiple platforms. The owner follows researchers, podcasters, and thinkers (e.g. Joe Rogan, Michael Levin, Lex Fridman) and wants a single view showing: who published what, recently, across podcast RSS, YouTube, X/Twitter, and blogs/Substack.

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
- **localStorage** — all persistence (persons, seen entry IDs)
- **allorigins.win** — public CORS proxy for RSS fetching from browser
- **Google Fonts** — Playfair Display, JetBrains Mono, Libre Baskerville
- **No API keys required** — YouTube channel RSS is public/free, podcast RSS is public, X/Twitter requires rss.app workaround

---

## Data model

### Person (persisted in `localStorage['pw-persons']`)
```js
{
  id:          string,        // e.g. "joe-rogan-1711234567890"
  name:        string,        // display name
  desc:        string,        // optional subtitle
  avatar:      string,        // optional image URL
  feeds: {
    podcast:   string,        // full RSS URL
    youtube:   string,        // channel ID only (e.g. "UCzWQYUVCpZqtN93H8RR44Qw")
    twitter:   string,        // rss.app-generated RSS URL
    blog:      string,        // full RSS URL (Substack, personal blog, etc.)
  },
  entries:     Entry[],       // max 20, sorted newest first
  lastUpdated: string|null,   // ISO 8601
  loading:     boolean,       // runtime only — always false when saved
}
```

### Entry (inside person.entries)
```js
{
  id:        string,          // composite key: personId + platform + link, max 80 chars
  personId:  string,
  platform:  'podcast'|'youtube'|'twitter'|'blog',
  title:     string,
  link:      string,          // URL to open
  desc:      string,          // snippet, max 300 chars, HTML stripped
  date:      string,          // ISO 8601
}
```

### Seen tracking (`localStorage['pw-seen']`)
```js
seenIds: Set<string>  // entry IDs that the user has opened (removes NEW badge)
```

---

## Key functions

| Function | Purpose |
|---|---|
| `loadState()` | Load persons + seenIds from localStorage, seed with DEMO_PERSONS if empty |
| `saveState()` | Persist persons + seenIds to localStorage |
| `fetchPerson(person)` | Fetch all configured feeds for one person, update entries |
| `fetchRSS(url, platform, personId)` | Fetch one RSS URL via CORS proxy, parse XML, return Entry[] |
| `refreshAll()` | Call fetchPerson() for all persons in parallel |
| `renderAllCards()` | Re-render the entire People grid |
| `renderPersonCard(person, prepend, delay)` | Render or re-render a single person card |
| `renderTimeline()` | Render the Timeline view (all entries, date-grouped) |
| `rebuildAllEntries()` | Flatten all person.entries into allEntries[] |
| `openEntry(entry)` | Show detail modal, mark entry as seen |
| `setFilter(platform)` | Filter both views to a single platform |
| `switchView('people'\|'timeline')` | Toggle between the two main views |
| `addPerson()` | Read form, create person object, save, fetch |
| `deletePerson(id)` | Remove person from state and DOM |

---

## CSS design system

CSS custom properties defined in `:root`:

```css
--bg         #0d0d0f   /* page background */
--surface    #131318   /* card background */
--surface2   #1a1a22   /* card header / footer */
--border     #2a2a35   /* all borders */
--accent     #e8c84a   /* gold — primary actions, NEW badge, highlights */
--text       #e8e6e0   /* primary text */
--muted      #7a7870   /* secondary text, labels */
--podcast    #e8744a   /* orange */
--youtube    #e84a4a   /* red */
--twitter    #4ab8e8   /* blue */
--blog       #a0e84a   /* green */
```

Fonts: Playfair Display (headings/names), JetBrains Mono (UI/labels), Libre Baskerville (entry descriptions in modal).

---

## Known limitations / issues

1. **CORS proxy reliability** — allorigins.win is a free public service. It can be slow or rate-limited. If needed, replace `const CORS` with a self-hosted proxy URL.
2. **X/Twitter** — X killed native RSS in 2023. The only free workaround is rss.app (~$5/month) which generates RSS feeds from X profiles. The app accepts any RSS URL for the twitter field, so rss.app URLs work directly.
3. **YouTube channel ID** — The form asks for channel ID (the `UC...` string), not the full URL. Users sometimes confuse `@username` handles with channel IDs. README explains how to find it.
4. **No auto-refresh** — Fetching only happens on user action (Refresh All button or per-card ↻). A `setInterval` auto-refresh is planned.
5. **Entry limit** — Each person stores max 20 entries. Cards show only the top 4. Expand to show all is planned.
6. **No edit person** — Once added, a person's feeds can only be changed by deleting and re-adding. An edit form is planned.

---

## Roadmap (in priority order)

1. **Auto-refresh** — `setInterval` every N minutes, configurable, with a visual countdown
2. **Edit person** — Slide-out edit form to update feeds, name, avatar
3. **Show more entries** — Expand button on cards to see all 20 (or paginate)
4. **Keyword search** — Filter timeline/cards by search term across all entry titles
5. **Export/import** — JSON dump of persons list for backup and transfer
6. **Browser notifications** — `Notification API` for new items in background
7. **AI digest** — Weekly summary of each person's activity using Claude API (claude-sonnet-4-6)
8. **Self-hosted backend** — Tiny Node/Deno/Python server for:
   - Removing CORS proxy dependency
   - Background polling (cron)
   - Push notifications via WebSockets
9. **Electron wrapper** — Desktop app, no CORS issues, system tray
10. **Mobile PWA** — Service worker + manifest for home screen install

---

## Conventions for Claude Code

- Keep the app as a **single `index.html`** file until a backend/build step is explicitly introduced
- Do not add npm/node dependencies without explicit request
- CSS goes inside `<style>`, JS inside `<script>` at bottom of `<body>`
- All new JS functions should follow the pattern: pure logic separated from DOM manipulation
- Maintain the design system — use CSS variables, don't hardcode colors
- New platforms (LinkedIn, GitHub, etc.) follow the same pattern as existing ones in `PLATFORMS` constant
- When adding features that require API keys, store them in localStorage under `pw-config` (never hardcode)
- The accent color `--accent` (#e8c84a) is the gold used throughout — keep it consistent
