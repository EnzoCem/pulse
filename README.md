# Pulse — PersonWatch

A personal intelligence dashboard for tracking specific people and publications across podcasts, YouTube, X/Twitter, and blogs. Open `index.html` in any browser — no server, no install, no build step.

---

## What it does

Define a list of people you follow (podcasters, researchers, thinkers) or publications/sources (Big Think, Aeon, Quanta Magazine) and assign their public feed URLs. Pulse fetches all feeds and shows everything in one place, organised by **person** — not by platform.

- **People view** — one card per person showing their 4 most recent items with NEW badges on unseen content
- **Timeline view** — all activity from all people, sorted chronologically, grouped by date
- **Filter by platform** — Podcast / YouTube / X / Blog / Books chips in both views
- **Filter by topic** — assign tags to people and filter by them via the TOPICS bar
- **Entry detail modal** — click any item to read its description, add notes, and open it
- **AI Notes** — generate structured research notes from YouTube transcripts or article text via Claude API
- **NotebookLM** — one-click to copy a video or article URL and open your notebook
- **Obsidian** — write episode/article notes directly to your Obsidian vault
- **Sources / Publications** — add a publication (e.g. Aeon) as a source; articles show with their individual author names

All data is persisted in `localStorage`. Nothing is sent to any server except optional Claude API calls if you configure an API key.

---

## How to use

1. Open `index.html` in any browser (double-click, or run `python3 -m http.server 5500` then open `http://localhost:5500`)
2. Click **+ Add Person**, type a name, check the roles that apply (🎙 Podcaster / ▶ YouTuber / ✍ Blogger / 📚 Writer), then hit **🔍 Search** — feeds are auto-discovered per role in parallel
3. Results appear with the top match auto-selected per role; pick a different result or paste a URL override if needed, then click **✓ Add {Name}**
4. Hit **↻** on a card or **Refresh All** in the bottom bar to fetch content

---

## Feed URL reference

| Platform | What to enter | Notes |
|---|---|---|
| Podcast | Full RSS URL **or** Apple Podcasts URL | Auto-detected by Search. Pasting `podcasts.apple.com/…/id123` resolves to the real RSS feed automatically |
| YouTube | Channel ID, `@handle`, or full URL | e.g. `@PowerfulJRE` — auto-resolved to `UC…` ID on save |
| X / Twitter | `@username`, `x.com/username`, or rss.app URL | Bare handles fetched for free via public Nitter instances; rss.app also accepted |
| Blog / Main RSS | RSS URL **or** any website/section URL | e.g. `https://aeon.co/essays` — app auto-discovers the RSS feed via `<link rel="alternate">`, common path probing, and Feedly's feed database |

### YouTube tip: no channel ID needed
The YouTube field accepts any of these — all resolve automatically when you save:
- Raw channel ID: `UCzQUP1qoWDoEbmsQxvdjxgQ`
- Handle: `@PowerfulJRE`
- Full URL: `https://youtube.com/@PowerfulJRE`

### Pasting Apple Podcasts URLs
You can paste a full Apple Podcasts link (e.g. `https://podcasts.apple.com/gb/podcast/big-think/id1803050676`) directly into the Name or Podcast field. The app extracts the iTunes ID and looks up the real RSS feed automatically.

### Website URLs for blogs
If you enter a website or section URL instead of a direct RSS URL (e.g. `https://aeon.co/essays`), the app runs a 3-stage discovery:
1. Looks for `<link rel="alternate" type="application/rss+xml">` in the fetched HTML
2. Probes common RSS paths on the domain (`/feed`, `/rss.xml`, `/feed.rss`, etc.)
3. Queries Feedly's public feed-search API as a last resort

The resolved RSS URL is saved back automatically so future refreshes go directly to the feed.

---

## X / Twitter

The X / Twitter field accepts:
- `@username` or plain `username` — fetched for free via public Nitter instances (tried in sequence; first working one wins)
- `x.com/username` or `twitter.com/username` URL
- A full rss.app RSS URL (paid, most reliable)

If all Nitter instances fail, Twitter content is silently skipped for that refresh.

---

## Books

Each person automatically has their books looked up via the **Google Books API** (free, no key required) using `inauthor:"Name"`. Results are filtered to English editions only and deduplicated so each title appears once.

You can override the search query in the person's **Books** field (Edit profile) — useful for pen names or to narrow results (e.g. `Tim Ferriss self-help`). Leave it blank to use the person's name.

Books appear in cards and timeline with a 📚 purple indicator and are filterable via the **Books** chip in the toolbar.

---

## Topics / Tags

Tags are assigned to **people** (not individual entries). Use them to group and filter:

1. Open a person card, click **+ topics** (or **✎** if tags exist)
2. Type a tag name, press **Enter**, click **Save**
3. The **TOPICS** bar appears above the grid — click any tag to filter to people with that tag

**Managing tags from the TOPICS bar:**
- Click a tag label to toggle the filter on/off
- Click **✎** to rename the tag across all people
- Click **×** to remove the tag from all people

---

## Podcast features

When you open a podcast episode:

- **Clean description** — sponsor ad copy is automatically stripped. A "Show full description" link expands it if needed.
- **🔊 Open Sound** — opens the RSS audio link
- **▶ Open Video** — finds and opens the matching YouTube video automatically
- **📄 Load Transcript** — fetches YouTube captions inline (YouTube entries)
- **🔍 Find Transcript** — Google search for a podcast transcript
- **🤖 AI Notes** — fetches the YouTube transcript and generates structured research notes via Claude API
- **📔 NotebookLM** — copies the YouTube URL to clipboard and opens your notebook
- **📓 Obsidian** — writes the episode notes to your Obsidian vault

---

## Blog / Article features

When you open a blog post or article:

- **🤖 AI Notes** — fetches the full article text (via CORS proxy) and sends it to Claude for analysis. Produces: Main Argument, Key Points, Key Insights, Notable Quotes, People & Resources Mentioned, and a blank My Takeaways section.
- **📔 NotebookLM** — copies the article URL to clipboard and opens your notebook (NotebookLM accepts web URLs as sources directly)
- **📓 Obsidian** — writes the article notes to your Obsidian vault

---

## Sources / Publications

Toggle **PUBLICATION / SOURCE** in the Add Person panel to add a publication instead of an individual. Differences:

- The "Podcast RSS" field becomes "Main RSS Feed"
- Both the Main RSS Feed and Blog fields are fetched and shown as articles
- YouTube content is fetched independently alongside articles (not exclusive like for persons)
- Individual article author names are shown on each entry row

---

## Editing people

Click any person card (the name/avatar area) to open their **detail panel**:

- Edit name, description, website, avatar URL
- Add or remove topics / tags
- Update any feed URL (YouTube field auto-resolves handles)
- Click **Save Changes** → **↻** to refresh with the new feeds
- **Delete Person** to remove them entirely

---

## AI features setup

Open **⚙ Settings** (top-right gear icon) to configure:

| Setting | Where to get it |
|---|---|
| Anthropic API key | [console.anthropic.com](https://console.anthropic.com) |
| NotebookLM URL | Open your notebook, copy the URL from the browser bar |
| AI Notes prompt (extra instructions) | Optional — appended to the default prompt |
| Auto-save AI Notes to Obsidian | Toggle — requires Obsidian vault to be connected |
| Obsidian vault | Click "Connect Vault" — uses the File System Access API (no plugin needed) |

---

## Architecture

Single-file vanilla HTML/CSS/JS. No frameworks, no build step, no dependencies.

```
Pulse/
├── index.html    # Entire application — HTML + CSS + JS in one file
├── README.md     # This file
└── CLAUDE.md     # Context for Claude Code sessions
```

### CORS proxies

RSS feeds are fetched through a chain of three public CORS proxies, tried in order:

| Priority | Proxy | Best for |
|---|---|---|
| 1 | `corsproxy.io` | General RSS, podcast feeds, API calls |
| 2 | `allorigins.win/raw` | General fallback |
| 3 | `api.codetabs.com/v1/proxy` | YouTube feeds |

### External APIs used

| API | Auth | Purpose |
|---|---|---|
| iTunes Search / Lookup | None | Podcast search by name; resolves Apple Podcasts URLs to RSS feeds |
| YouTube Data (RSS) | None | Channel feed via `youtube.com/feeds/videos.xml?channel_id=…` |
| YouTube (captions) | None | Transcript fetch for AI Notes |
| Feedly feed search | None | RSS feed discovery for website URLs |
| Google Books API | None | Books lookup by author name |
| Nitter (public instances) | None | X/Twitter RSS for bare @username handles |
| Anthropic Messages API | API key (yours) | AI Notes generation |
| File System Access API | Browser prompt | Obsidian vault write |

### Data model

```js
// Person (localStorage: 'pw-persons')
{
  id:          string,        // slugified name + timestamp
  name:        string,
  desc:        string,
  website:     string,        // optional homepage URL
  avatar:      string,        // image URL, optional
  type:        'person' | 'source',  // person = individual, source = publication
  feeds: {
    podcast:   string,        // full RSS URL (or "Main RSS Feed" for sources)
    youtube:   string,        // UC… channel ID
    twitter:   string,        // @username, x.com/user, or rss.app RSS URL
    blog:      string,        // full RSS URL
    books:     string,        // optional Google Books search query override (blank = person name)
  },
  tags:        string[],      // topics for filtering
  roles:       string[],      // UI hint: ['podcaster','youtuber','blogger','writer']
  itunesId:    number|null,   // iTunes collection ID (enables full episode history)
  entries:     Entry[],       // max 20, sorted newest first
  lastUpdated: string|null,   // ISO 8601
  fetchErrors: string[],      // platforms that failed on last refresh
  loading:     boolean,       // runtime only — true during manual refresh, always false when saved
  backgroundRefreshing: boolean, // runtime only — true during background TTL refresh, always false when saved
}

// Entry
{
  id:            string,      // personId + platform + link (max 80 chars)
  personId:      string,
  platform:      'podcast'|'youtube'|'twitter'|'blog'|'books',
  title:         string,
  link:          string,      // URL to open
  desc:          string,      // snippet, max 300 chars, HTML-stripped
  date:          string,      // ISO 8601
  author:        string,      // article author (populated from dc:creator / itunes:author)
  transcriptUrl: string,      // Podcasting 2.0 <podcast:transcript> URL if present
}

// localStorage keys
'pw-persons'    → Person[]          persons list
'pw-seen'       → string[]          entry IDs the user has opened (clears NEW badge)
'pw-listened'   → string[]          entry IDs marked as listened
'pw-entry-tags' → Record<id,string[]>  per-entry topic tags
'pw-notes'      → Record<id,string>    per-entry manual + AI notes
'pw-config'     → object            API keys and settings (anthropicKey, notebookLMUrl, etc.)

// IndexedDB: 'pulse-episodes'   full episode history per person (iTunes)
// IndexedDB: 'pulse-vault'      FileSystemDirectoryHandle for Obsidian vault
```

---

## Roadmap

### Done
- [x] People view + Timeline view
- [x] Platform and topic filtering (Podcast / YouTube / X / Blog / Books)
- [x] Edit person (feeds, name, avatar, tags, website) via detail panel
- [x] Auto-search from person name (iTunes + YouTube + blog detection)
- [x] Apple Podcasts URL → RSS feed auto-resolution (iTunes lookup by ID)
- [x] YouTube handle / URL → channel ID auto-resolution
- [x] YouTube-as-podcast mode (no RSS needed for YouTube-only shows)
- [x] RSS feed autodiscovery for website URLs (3-stage: HTML link tag → path probing → Feedly API)
- [x] Podcast ad stripping from descriptions
- [x] Open Sound / Open Video buttons for podcasts
- [x] YouTube video auto-find by episode title (no channel ID needed)
- [x] Three-proxy CORS fallback chain with parallel fetching and 30s hard cap
- [x] Full podcast episode history via iTunes Lookup API
- [x] Publication / Source type (articles with per-author names)
- [x] Per-entry notes (manual text saved in localStorage)
- [x] Per-entry topic tags
- [x] AI Notes via Claude API — YouTube transcript + article text, structured output
- [x] NotebookLM one-click (video URL or article URL copied to clipboard)
- [x] Obsidian vault integration (File System Access API, no plugin needed)
- [x] Podcasting 2.0 transcript links (`<podcast:transcript>`)
- [x] Books tab — Google Books API, English-only, deduplicated by title
- [x] X/Twitter via free Nitter instances (accepts @username, no paid subscription needed)
- [x] Person-level topic tags with TOPICS filter bar (rename/remove globally)
- [x] Website field on person/source profiles
- [x] Stale-while-revalidate background refresh — feeds older than 6 hours auto-refresh on page load and card open, with pulsing badge indicator
- [x] Role-based Add Person flow — role checkboxes (Podcaster / YouTuber / Blogger / Writer) drive parallel auto-search; top result auto-selected with inline paste override per role

### Planned
- [ ] Auto-refresh on a fixed interval (e.g. every N minutes) with configurable timer and visual countdown
- [ ] Show more than 4 entries per card (expand / paginate)
- [ ] Keyword search across all entry titles and descriptions
- [ ] Export / import persons list as JSON backup
- [ ] Newsletters as a distinct platform (Substack, Beehiiv, Ghost)
- [ ] arXiv / papers platform (author RSS feeds)
- [ ] GitHub activity platform (user event feed)
- [ ] Weekly AI digest across all tracked people
- [ ] Browser push notifications for new content
- [ ] Smart collections (saved filter combos)
- [ ] Person profile page (full-screen view with all entries and books)
- [ ] Readwise / Notion integration for notes export
- [ ] Self-hosted backend (removes CORS proxy dependency, enables background polling)
- [ ] Mobile PWA (service worker + manifest)
- [ ] Electron wrapper (desktop app, no CORS issues, system tray)

---

## Development

No build step. Edit `index.html` directly.

```bash
# Serve locally (recommended over file:// — localStorage is shared across reloads)
python3 -m http.server 5500
# then open http://localhost:5500
```

> **Note:** Opening via `file://` uses a separate localStorage from a local server. Pick one and stick with it.
