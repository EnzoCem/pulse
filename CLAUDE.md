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
- **localStorage** — all persistence (persons, seen entry IDs, notes, tags, config); **isolated per Chrome profile** — different accounts cannot share data
- **IndexedDB** — full episode history (iTunes) and Obsidian vault handle
- **CORS proxy chain** — corsproxy.io → allorigins.win → codetabs.com (tried in order)
- **Google Fonts** — Playfair Display, JetBrains Mono, Libre Baskerville
- **No API keys required for core features** — YouTube/podcast RSS is public, X/Twitter uses free Nitter instances, Books uses Google Books API (free)
- **Flask backend** (`backend/server.py`, port 5001) — optional; enables reliable YouTube transcript fetching via `youtube-transcript-api`
- **Shared utilities** — `Main Rules/utilities/js/` functions inlined in `<script>` block: `sleep`, `withTimeout`, `sequential`, `CircularBuffer`, `memoizeWithTTLAsync`, `toError`, `errorMessage`, `isAbortError`

---

## Data model

### Person (persisted in `localStorage['pw-persons']`)
```js
{
  id:          string,        // e.g. "joe-rogan-1711234567890"
  name:        string,        // display name
  desc:           string,        // optional subtitle
  website:        string,        // optional homepage URL
  transcriptsUrl: string,        // optional URL to the person's transcripts page (podcast entries)
  avatar:         string,        // optional image URL
  type:        'person'|'source',  // person = individual, source = publication
  feeds: {
    podcast:   string,        // full RSS URL (or "Main RSS Feed" for sources)
    youtube:   string,        // UC… channel ID only
    twitter:   string,        // @username, x.com/user, or rss.app RSS URL
    blog:      string,        // full RSS URL (Substack, personal blog, etc.)
    books:     string,        // optional Google Books search query override
  },
  feedsEnabled: {             // per-feed enable/disable toggle (all default true; missing key = enabled)
    podcast:   boolean,
    youtube:   boolean,
    twitter:   boolean,
    blog:      boolean,
    books:     boolean,
  },
  tags:        string[],      // person-level topics for TOPICS filter bar
  roles:       string[],      // UI-only hint: ['podcaster','youtuber','blogger','writer'] — set at Add Person time
  itunesId:    number|null,   // iTunes collection ID (enables full episode history)
  entries:     Entry[],       // max 20, sorted newest first
  lastUpdated: string|null,   // ISO 8601
  fetchErrors: string[],      // platforms that failed on last refresh
  loading:     boolean,       // runtime only — true during manual/first fetch, always false when saved
  backgroundRefreshing: boolean, // runtime only — true during TTL background refresh, always false when saved
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

### Appearance (inside person.appearances)
```js
{
  id:           string,              // "personId-appearance-<8-char hash>"
  isAppearance: true,                // distinguishes from Entry — always true
  personId:     string,              // the tracked person who appeared as guest
  platform:     'podcast'|'youtube'|'article'|'other',
  title:        string,              // episode title
  link:         string,              // URL to episode
  desc:         string,              // episode description
  date:         string,              // ISO 8601
  hostName:     string,              // name of the show/host (e.g. "Lex Fridman Podcast")
  hostPersonId: string|undefined,    // personId of host if they are also tracked in Pulse
}
```

Appearances are stored in `person.appearances[]` (separate from `person.entries[]`). They are merged for display via `_mergeEntriesAndAppearances(person)` which tags each entry with `isAppearance: true/false`.

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
| `ensureFresh(person)` | Stale-while-revalidate: no-op if fresh (<6h), background refresh if stale, blocking fetch if never fetched |
| `fetchPerson(person)` | Sequential queue wrapper around `_fetchPersonCore` — prevents race conditions on double-refresh |
| `_fetchPersonCore(person)` | Fetch all enabled feeds in parallel (30s hard cap via `withTimeout`), update entries via `CircularBuffer` |
| `fetchRSS(url, platform, personId)` | Fetch one RSS URL via CORS proxy chain, parse XML, return `{entries, error}` |
| `fetchBooks(query, personId)` | Query Google Books API, return English-only deduplicated Entry[] |
| `fetchTwitterHandle(handle, platform, personId)` | Try each Nitter instance, return entries from first working one |
| `refreshAll()` | Call fetchPerson() for all persons in parallel |
| `feedOn(key)` | Returns `true` if a feed is enabled; `person.feedsEnabled?.[key] !== false` (backward-compatible) |
| `toggleFeedEnabled(personId, feedKey, enabled)` | Toggle a feed on/off; saves state immediately, updates dot color without full re-render |
| `_checkBackend()` | Ping `localhost:5001/api/health`; sets `_backendOnline` flag used by transcript loader |
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
| `addPerson()` | Read role selections + override inputs (person mode) or feed URL fields (source mode), create person object, save, fetch |
| `deletePerson(id)` | Remove person from state and DOM |
| `searchPersonByName()` | Source mode: unchanged (YouTube + RSS auto-detect). Person mode: role-scoped parallel API calls via `Promise.allSettled`, then `renderRoleResults()` |
| `renderRoleResults(query)` | Render search results per role into `#roleResultsArea` — auto-selects top result, shows inline override input per role |
| `selectRoleResult(role, idx)` | Switch selected result for a role; updates `_roleSelections[role]` and toggles `.selected` CSS |
| `toggleRole(role)` | Toggle a role chip checked state; updates `_formRoles` Set and calls `_updateSearchBtn()` |
| `_updateSearchBtn()` | Enable/disable Search button: source mode requires name only; person mode requires name + at least one role |
| `resolveYouTubeChannelId(raw)` | Resolve @handle/URL/username to UC… channel ID — Step 0 tries `forHandle` RSS endpoint before legacy methods |
| `_findSourceRSS(name)` | Auto-discover RSS feed for a publication by name |
| `_looksLikeRssUrl(url)` | Returns true for RSS URLs AND bare @username Twitter handles |
| `_extractTwitterHandle(val)` | Extract bare username from @user / x.com/user; null for full URLs |
| `callClaude(apiKey, systemPrompt, userContent, maxTokens)` | Call Claude API (claude-sonnet-4-6); `maxTokens` optional, defaults to 1024 |
| `readObsidianNote(relativePath)` | Read a file from the connected Obsidian vault; returns `null` if missing or permission denied |
| `writeObsidianNote(relativePath, content)` | Write markdown to vault subfolder, creating directories as needed |
| `buildWikiUpdatePrompt(entry, person, transcript, pages)` | Build Claude `{ system, user }` messages for wiki maintenance; `pages` is a `Map<relativePath, content\|null>` of all loaded wiki files |
| `parseWikiResponse(text)` | Extract `<wiki_file path="...">` blocks from Claude response into `{ path: content }` map |
| `updateWikiFromTranscript()` | Orchestrate full wiki update: read existing → call Claude → parse → write to Obsidian |
| `_refreshWikiBtn()` | Enable/disable `#wikiBtn` based on whether `_currentTranscriptText` is set |
| `buildEpisodeBriefPrompt(entry, person, transcript)` | Build Claude `{ system, user }` for episode brief extraction (7-section structured reference doc) |
| `generateEpisodeBrief()` | Orchestrate brief generation: guards → `callClaude(4096)` → `_renderBriefSection` |
| `_renderBriefSection(markdown)` | Convert 7-section markdown to HTML, insert below `#transcriptArea`, add Save button |
| `_refreshBriefBtn()` | Enable/disable `#briefBtn` based on `_currentTranscriptText` (mirrors `_refreshWikiBtn`) |
| `saveEpisodeBriefToObsidian()` | Write `_currentBriefMarkdown` to `{safeFolder}/briefs/{date}-{slug}.md` in vault |
| `_mergeEntriesAndAppearances(person)` | Merge `person.entries` and `person.appearances` into a single sorted array; tags each with `isAppearance: true/false` |

---

## LLM Wiki (Obsidian integration)

Pulse can maintain a compounding personal knowledge wiki in Obsidian for each tracked person. The wiki is written by Claude and grows richer with every episode ingested.

**How it works:**
1. Open a YouTube, podcast, or guest appearance entry modal
2. Load a transcript (YouTube: "📄 Load Transcript"; podcast: find/load transcript)
3. Once transcript is loaded, **🧠 Update Wiki** and **📋 Episode Brief** buttons become active

**Update Wiki** — reads existing wiki files for that person, calls Claude API, writes back:
- `{safeFolder}/_index.md` — catalog of all wiki pages (`path | type | summary`)
- `{safeFolder}/index.md` — living synthesis (themes, positions, key quotes, guests)
- `{safeFolder}/log.md` — append-only ingest log; lists ALL cited studies under `> studies:` tag
- `{safeFolder}/themes/` — recurring topics of any kind (intellectual, cultural, geographic, creative)
- `{safeFolder}/guests/` — notable guests and collaborators
- `{safeFolder}/books/` — books written or referenced
- `{safeFolder}/positions/` — specific stated views on named questions
- `{safeFolder}/studies/` — academic papers cited substantively (2+ meaningful sentences)
- `{safeFolder}/resources/` — tools, supplements, products endorsed with reasoning
- `{safeFolder}/misc/` — catch-all for anything that doesn't fit the above categories
- `topics/` — cross-person synthesis pages + catalog

**Episode Brief** — separate Claude call (4096 tokens) that extracts a structured per-episode reference document (like a "Selected Links" PDF) with 7 sections: People Mentioned, Books Referenced, Studies Cited, Products/Supplements/Tools, Key Concepts & Terminology, Notable Quotes, Episode Structure. Renders inline in the modal. Optional "Save to Obsidian" writes to `{safeFolder}/briefs/{date}-{slug}.md`.

**Requirements:** Anthropic API key in Settings + Obsidian vault connected in Settings (vault required for save operations only).

**Button visibility:** Update Wiki and Episode Brief shown for YouTube, podcast, and guest appearance entries. Starts disabled; enabled by `_refreshWikiBtn()` / `_refreshBriefBtn()` once transcript loads.

**Path safety:** `updateWikiFromTranscript` validates Claude's returned file paths with a prefix check: only paths under `{safeFolder}/` or `topics/` are written. Paths with `..` or starting with `/` are also rejected. Warnings are logged for rejected paths.

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

## Add Person flow (person mode)

The Add Person panel has two modes toggled at the top:

**Person mode (default):**
1. Type a name — Search button is disabled until at least one role is also checked
2. Check role chips: 🎙 Podcaster / ▶ YouTuber / ✍ Blogger / 📚 Writer (any combination)
3. Hit Search — each checked role fires its API call in parallel (`Promise.allSettled`)
4. Results panel appears with auto-selected top match per role + inline "or paste URL" override
5. Optionally click a different result to override, or paste a URL directly
6. Fill optional Description / Avatar / Topics fields
7. Click "✓ Add {Name}"

Runtime state (cleared on panel open/close):
- `_formRoles` — `Set<string>` of currently checked roles
- `_roleResults` — `{ podcaster: [...], youtuber: [...], writer: [...], blogger: [] }` from API
- `_roleSelections` — `{ podcaster: 0, youtuber: 0, writer: 'query-string' }` — selected index per role

**Source mode:** unchanged from before — shows feed URL inputs, auto-detects YouTube + RSS by name.

**X/Twitter:** Not a role chip. Always added manually via card ✎ edit after person is created.

---

## Feed status dots (in Edit panel)

Each feed row in the Edit / Detail panel shows a colour-coded status dot:

| Colour | Meaning |
|--------|---------|
| 🟢 Green | Feed fetched successfully and has entries |
| 🔴 Red | Feed was attempted but failed (in `fetchErrors`) |
| 🟡 Yellow | Feed was fetched but returned zero entries |
| ⚫ Grey | Feed never fetched, or feed is disabled |

The Books dot uses `person.name` as fallback query when the books field is blank (so the dot shows even without an explicit query override).

Each feed also has an enable/disable toggle checkbox. Disabling a feed skips it on the next refresh without removing the URL. The `feedOn(key)` helper checks `person.feedsEnabled?.[key] !== false` so existing persons without `feedsEnabled` default to all-enabled.

---

## Backend (`backend/server.py`)

Optional Flask server on port 5001. Start with:
```bash
cd backend && python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python server.py
```

Endpoints:

| Endpoint | Purpose |
|----------|---------|
| `GET /api/health` | Health check; returns `{"status":"ok"}` |
| `GET /api/transcript/<video_id>` | Fetch YouTube transcript via `youtube-transcript-api`; returns `{transcript, segments, auto, language}` |
| `POST /api/notebooklm/ask` | Query a NotebookLM notebook via the notebooklm-skill subprocess |

The frontend checks `_backendOnline` (set by `_checkBackend()` on page load) and routes `loadYouTubeTranscript()` through the backend when available, falling back to CORS proxy scrape.

---

## Known limitations / issues

1. **CORS proxy reliability** — three public CORS proxies tried in sequence. All are free services and can be slow/rate-limited. Each proxy has a 7s timeout; the entire fetchPerson call has a 30s hard cap.
2. **X/Twitter via Nitter** — free but fragile. Nitter instances come and go as X blocks them. The `NITTER_INSTANCES` array at the top of the JS can be updated when instances go down.
3. **YouTube channel ID** — stored as `UC…` ID. The form accepts @handles and URLs and auto-resolves on save via the `forHandle` RSS endpoint (Step 0) then legacy methods. If the stored value is not a valid `UC…` ID, YouTube fetching is silently skipped.
4. **Google Books accuracy** — `langRestrict=en` is requested and results are client-filtered to `language === 'en'`, but Google Books metadata is imperfect and some non-English editions may still appear.
5. **Background refresh (TTL-based)** — `ensureFresh()` fires automatically on page load (staggered 600ms apart) and on `openPersonDetail`. Feeds older than 6 hours (`FEED_TTL_MS`) are refreshed in the background; a pulsing dot badge indicates progress. Manual refresh (↻ / Refresh All) always fetches immediately regardless of age.
6. **Entry limit** — Each person stores max 20 non-book entries (CircularBuffer capacity 20) + 15 book entries. Cards show only the top 4.
7. **localStorage profile isolation** — localStorage is scoped to the browser profile (Chrome account). Opening Pulse in a different Chrome profile shows an empty persons list. Use the same profile consistently; export/import (planned) will allow transfer.

---

## Roadmap (in priority order)

1. **Export/import** — JSON dump of persons list for backup and cross-profile transfer (high priority; localStorage is profile-isolated)
2. **Auto-refresh on interval** — `setInterval` every N minutes, configurable, with a visual countdown (TTL-based background refresh on load/open is already done)
3. **Show more entries** — Expand button on cards to see all 20 (or paginate)
4. **Browser notifications** — `Notification API` for new items in background
5. **AI digest** — Weekly summary of each person's activity using Claude API (claude-sonnet-4-6)
6. **Self-hosted backend** — Extend `backend/server.py` for:
   - Removing CORS proxy dependency
   - Background polling (cron)
   - Push notifications via WebSockets
7. **Electron wrapper** — Desktop app, no CORS issues, system tray
8. **Mobile PWA** — Service worker + manifest for home screen install

### Completed features (recent)
- ✅ **Wiki taxonomy expansion** — added `studies/`, `resources/`, `misc/` folders; broadened `themes/` to any recurring topic; `log.md` now lists all cited studies under `> studies:` tag
- ✅ **Episode Brief** — `📋 Episode Brief` button extracts a 7-section structured reference doc from a transcript (people, books, studies, products, concepts, quotes, structure); renders inline in modal, optionally saved to `{safeFolder}/briefs/`
- ✅ **Guest Appearances** — `APPEARANCES` filter shows all people; appearance modals show same transcript/AI processing buttons as podcast/youtube (Load Transcript, NotebookLM, AI Notes, Obsidian, Update Wiki, Episode Brief)
- ✅ **LLM Wiki v2** — multi-file taxonomy with `_index.md` catalog, cross-person `topics/` pages, keyword-based topic page selection to avoid token overload
- ✅ **LLM Wiki v1** — "🧠 Update Wiki" button in entry modal; calls Claude API with loaded transcript to maintain a compounding per-person Obsidian wiki
- ✅ **DB architecture Phase 1** — SQLite enrichment layer (status, notes, Calibre links, episode archive, guest graph, library view)
- ✅ **Library tab** — paginated view of all tracked content with status/platform/guest filters
- ✅ **All Episodes** — full episode archive per person with sync from RSS + iTunes

---

## Guest Appearances

Appearances track episodes where a person appeared as a **guest** on someone else's show — separate from their own feed entries.

**Data:** Stored in `person.appearances[]` (not `person.entries[]`). Each appearance has `isAppearance: true`, a `hostName`, and optionally a `hostPersonId` if the host is also tracked in Pulse.

**APPEARANCES filter:** Shows all tracked people (same as other platform filters). Cards show only `isAppearance` entries. People with no appearances yet show "No entries yet."

**Platform filters (PODCAST, YOUTUBE, etc.):** Appearances are deliberately excluded from platform filters — they show only feed-sourced content. Appearances are only visible under ALL and APPEARANCES.

**Modal buttons:** Appearance modals show the same processing buttons as the underlying platform:
- YouTube appearance → Load Transcript, NotebookLM, AI Notes, Obsidian, Update Wiki, Episode Brief
- Podcast appearance → Find/Load Transcript (using `entry.hostName` for Google search query), NotebookLM, AI Notes, Obsidian, Update Wiki, Episode Brief

**Adding appearances:** Via the person detail panel → "Guest Appearances" section → `openAppearanceFinder(personId)`. Supports AI-assisted search and manual URL paste.

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
- **Use shared utilities from `Main Rules/utilities/js/`** — inline them in the utilities block in `<script>`. Do not re-implement `sleep`, `withTimeout`, `sequential`, `CircularBuffer`, `memoizeWithTTLAsync`, `toError`, `errorMessage`, `isAbortError`
- **Concurrent refresh protection** — always use `fetchPerson()` (the `sequential` wrapper), never call `_fetchPersonCore()` directly from outside
- **Feed enable/disable** — always use `feedOn(key)` helper to check if a feed should be fetched; never read `feedsEnabled` directly
