# Pulse — PersonWatch

A personal intelligence dashboard. Open it in any browser, no server required.

## What it does

You define a list of people you follow (podcasters, researchers, thinkers, etc.) and assign their public feed URLs. Pulse fetches all feeds and shows you in one place:

- **People view** — one card per person showing their 4 most recent items across all platforms, with NEW badges on unseen content
- **Timeline view** — all activity from all people, sorted chronologically, grouped by date

Clicking any item shows a detail modal and marks it as seen. All data is persisted in `localStorage`.

---

## How to use

1. Open `index.html` in any browser (double-click it, or serve with `npx serve .`)
2. Click **+ Add Person**, fill in name and any feed URLs
3. Hit **Refresh All** (bottom bar) to fetch all feeds

---

## Feed URL reference

| Platform  | What to enter                              | Where to find it                                      |
|-----------|--------------------------------------------|-------------------------------------------------------|
| Podcast   | RSS feed URL                               | Podcast website, podcast host (Simplecast, Buzzsprout, etc.) |
| YouTube   | Channel ID (`UCxxxxxxxxxx`)                | From the channel URL: `youtube.com/channel/UCXXX`     |
| X/Twitter | rss.app RSS URL                            | Create at [rss.app](https://rss.app) (~$5/mo), enter the generated feed URL |
| Blog      | RSS feed URL                               | `yourname.substack.com/feed`, or website `/feed`      |

### YouTube Channel ID tip
If a channel URL looks like `youtube.com/@username`, go to the channel, right-click → View Source, search for `"channelId"` to find the `UC...` ID. Or use tools like [commentpicker.com/youtube-channel-id.php](https://commentpicker.com/youtube-channel-id.php).

---

## Architecture

Single-file vanilla HTML/CSS/JS. No frameworks, no build step, no dependencies.

```
Pulse/
├── index.html       # Entire application — HTML + CSS + JS in one file
├── README.md        # This file
└── CLAUDE.md        # Context for Claude Code sessions
```

### Key JS structures

```js
// Person object (stored in localStorage as 'pw-persons')
{
  id:          string,        // slugified name + timestamp
  name:        string,
  desc:        string,
  avatar:      string,        // URL, optional
  feeds: {
    podcast:   string,        // RSS URL
    youtube:   string,        // Channel ID only (not full URL)
    twitter:   string,        // rss.app RSS URL
    blog:      string,        // RSS URL
  },
  entries:     Entry[],       // fetched and cached
  lastUpdated: ISO string | null,
  loading:     boolean,       // runtime only, not persisted
}

// Entry object
{
  id:        string,          // personId + platform + link (truncated)
  personId:  string,
  platform:  'podcast'|'youtube'|'twitter'|'blog',
  title:     string,
  link:      string,
  desc:      string,          // max 300 chars, HTML-stripped
  date:      ISO string,
}

// Seen tracking (localStorage 'pw-seen')
seenIds: Set<string>          // entry IDs the user has clicked/opened
```

### CORS proxy

All RSS fetches go through `https://api.allorigins.win/get?url=` to bypass browser CORS restrictions. This is a free public service — fine for personal use, but if reliability becomes an issue, consider:

- Self-hosting [allorigins](https://github.com/gnuns/allorigins)
- Running a tiny Express/Deno proxy locally
- Converting to an Electron app (no CORS restrictions)

---

## Planned enhancements

- [ ] Auto-refresh every N minutes (background `setInterval`)
- [ ] Browser push notifications for new content
- [ ] Keyword search/filter across all entries
- [ ] Edit person feeds after adding
- [ ] Export/import people list as JSON
- [ ] Dark/light theme toggle
- [ ] Show full entry count per card (not just top 4)
- [ ] Electron wrapper for offline/desktop use (no CORS proxy needed)
- [ ] Replace allorigins with self-hosted proxy or local backend
- [ ] AI-generated digest: summarize each person's week via Claude API

---

## Development

No build step needed. Edit `index.html` directly.

To serve locally (prevents some browser restrictions on `file://`):
```bash
npx serve .
# or
python3 -m http.server 8080
```

Then open `http://localhost:8080`.
