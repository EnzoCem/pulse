# Pulse — PersonWatch

A personal intelligence dashboard for tracking specific people across podcasts, YouTube, X/Twitter, and blogs. Open `index.html` in any browser — no server, no install, no API keys required.

---

## What it does

Define a list of people you follow (podcasters, researchers, thinkers, etc.) and assign their public feed URLs. Pulse fetches all feeds and shows everything in one place, organised by **person** — not by platform.

- **People view** — one card per person showing their 4 most recent items with NEW badges on unseen content
- **Timeline view** — all activity from all people, sorted chronologically, grouped by date
- **Filter by platform** — Podcast / YouTube / X / Blog filter chips in both views
- **Filter by topic** — tag-based filtering across all people
- **Entry detail modal** — click any item to read its description, add topics, and open it

All data is persisted in `localStorage`. Nothing is sent to any server.

---

## How to use

1. Open `index.html` in any browser (double-click, or run `python3 -m http.server 5500` then open `http://localhost:5500`)
2. Click **+ Add Person**, type a name, and hit **🔍 Search** — feeds are auto-detected from iTunes, YouTube, and common blog patterns
3. Review the auto-filled fields, adjust if needed, click **Add Person**
4. Hit **↻** on a card or **Refresh All** in the bottom bar to fetch content

---

## Feed URL reference

| Platform | What to enter | Notes |
|---|---|---|
| Podcast | Full RSS URL | e.g. `https://feeds.megaphone.fm/…` — auto-detected by Search |
| YouTube | Channel ID, `@handle`, or full URL | e.g. `@PowerfulJRE` or `https://youtube.com/@PowerfulJRE` — auto-resolved to `UC…` ID on save |
| X / Twitter | rss.app RSS URL | Create a feed at [rss.app](https://rss.app) (~$5/mo), paste the generated URL |
| Blog | RSS or Atom feed URL | e.g. `yourname.substack.com/feed` — auto-detected by Search |

### YouTube tip: no channel ID needed
The YouTube field accepts any of these — all resolve automatically when you save:
- Raw channel ID: `UCzQUP1qoWDoEbmsQxvdjxgQ`
- Handle: `@PowerfulJRE`
- Full URL: `https://youtube.com/@PowerfulJRE`
- Username: `PowerfulJRE`

### YouTube-only podcasts (e.g. JRE)
If a podcast is published exclusively on YouTube, leave **Podcast RSS** blank and enter only the YouTube channel. Episodes will appear with podcast styling (🎙 orange) and work without any audio/RSS feed.

---

## Podcast episode features

When you open a podcast episode, the modal shows:

- **Clean description** — sponsor ad copy is automatically stripped. A "Show full description (includes sponsors)" link expands it if needed.
- **🔊 Open Sound** — opens the RSS / Spotify audio link
- **▶ Open Video** — finds and opens the matching YouTube video automatically (searches by episode title, no channel ID required). Shows "🔍 Finding video…" while searching.

---

## Editing people

Click any person card (the name/avatar area) to open their **detail panel**. From there you can:

- Edit name, description, avatar URL
- Add or remove topics / tags
- Update any feed URL (YouTube field auto-resolves handles)
- Click **Save Changes** — then **↻** to refresh with the new feeds
- **Delete Person** to remove them entirely

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

RSS feeds are fetched through a chain of three public CORS proxies — each tried in order until one succeeds:

| Priority | Proxy | Good for |
|---|---|---|
| 1 | `corsproxy.io` | General RSS, podcast feeds |
| 2 | `allorigins.win/raw` | General fallback |
| 3 | `api.codetabs.com/v1/proxy` | YouTube feeds, YouTube search |

YouTube-specific fetches (channel resolution, video search) always use codetabs as it reliably returns YouTube's embedded JSON.

### Data model

```js
// Person (localStorage: 'pw-persons')
{
  id:          string,        // slugified name + timestamp
  name:        string,
  desc:        string,
  avatar:      string,        // image URL, optional
  feeds: {
    podcast:   string,        // full RSS URL
    youtube:   string,        // UC… channel ID (auto-resolved from handle/URL on save)
    twitter:   string,        // rss.app RSS URL
    blog:      string,        // full RSS URL
  },
  tags:        string[],      // topics for filtering
  entries:     Entry[],       // max 20, sorted newest first
  lastUpdated: string|null,   // ISO 8601
  fetchErrors: string[],      // platforms that failed on last refresh
}

// Entry
{
  id:        string,          // personId + platform + link (max 80 chars)
  personId:  string,
  platform:  'podcast'|'youtube'|'twitter'|'blog',
  title:     string,
  link:      string,          // RSS/Spotify/blog URL
  desc:      string,          // snippet, max 300 chars, HTML-stripped
  date:      string,          // ISO 8601
}

// Seen tracking (localStorage: 'pw-seen')
seenIds: Set<string>          // entry IDs the user has opened (clears NEW badge)
```

---

## Roadmap

### Done
- [x] People view + Timeline view
- [x] Platform and topic filtering
- [x] Edit person (feeds, name, avatar, tags) via detail panel
- [x] Auto-search from person name (iTunes + YouTube + blog detection)
- [x] YouTube handle / URL → channel ID auto-resolution
- [x] YouTube-as-podcast mode (no RSS needed)
- [x] Podcast ad stripping from descriptions
- [x] Dual Open Sound / Open Video buttons for podcasts
- [x] YouTube video auto-find by episode title search (no channel ID needed)
- [x] Three-proxy CORS fallback chain

### Planned
- [ ] Auto-refresh every N minutes with visual countdown
- [ ] Show more than 4 entries per card (expand / paginate)
- [ ] Keyword search across all entry titles
- [ ] Export / import people list as JSON backup
- [ ] Browser push notifications for new content
- [ ] AI weekly digest via Claude API (claude-sonnet-4-6)
- [ ] Self-hosted backend (removes CORS proxy dependency, enables background polling)
- [ ] Electron wrapper (desktop app, no CORS issues, system tray)
- [ ] Mobile PWA (service worker + manifest)

---

## Development

No build step. Edit `index.html` directly.

```bash
# Serve locally (recommended over file:// — localStorage is shared across reloads)
python3 -m http.server 5500
# then open http://localhost:5500
```

> **Note:** Opening the file directly via `file://` uses a separate localStorage from any local server. Pick one and stick with it.
