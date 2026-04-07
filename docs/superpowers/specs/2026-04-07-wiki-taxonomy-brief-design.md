# Wiki Taxonomy Additions + Episode Brief — Design Spec

**Date:** 2026-04-07
**Status:** Approved

---

## Overview

Two complementary features that close the gap between what Pulse captures and what a thorough episode reference (e.g. Tim Ferriss's "Selected Links" PDFs) would contain:

- **Part A — Wiki Taxonomy Additions**: Add `studies/` and `resources/` folders to the existing multi-file wiki taxonomy. Prompt-only change to `buildWikiUpdatePrompt`.
- **Part B — Episode Brief**: A new per-episode reference extraction feature. Generates a structured document (people, books, studies, products, concepts, quotes, structure) from a transcript. Displays inline in the modal; optionally saved to Obsidian.

---

## Part A: Wiki Taxonomy Additions

### Motivation

The existing taxonomy (`index.md`, `log.md`, `themes/`, `guests/`, `books/`, `positions/`) covers recurring themes and people well but has no structure for:
- Academic studies a person cites as evidence
- Non-book resources (supplements, tools, apps, gear) a person endorses
- Content that doesn't fit any specific category (travel, culture, recipes, historical references, etc.)

### `studies/` folder

**Purpose:** Academic papers and research the tracked person cites substantively.

**Creation threshold (hybrid):**
- The `log.md` entry for each episode lists ALL studies cited, even passing mentions (title + the claim being supported). This ensures nothing is lost.
- A dedicated `studies/{slug}.md` page is created only when the person cites a study substantively: they explain what it found, why it matters, or build an argument on it — enough material for 2+ meaningful sentences.

**Page fields:**
- Paper title
- Authors (if mentioned)
- Journal / publication (if mentioned)
- Year (if mentioned)
- The person's stated claim or interpretation
- Episodes where referenced

**File naming:** Slugified from paper title, e.g. `studies/omega3-bdnf-neuroplasticity.md`

### `resources/` folder

**Purpose:** Tools, supplements, apps, and products the tracked person endorses with reasoning. Books are excluded (they have their own `books/` folder).

**Creation threshold:** One page per item, only when the person endorses with reasoning — dosing, mechanism, use case, or "why I use this." Passing name-drops without context do not qualify.

**Covered categories:** Supplements, pharmaceuticals, hardware/gear, apps, protocols, foods — anything non-book the person specifically recommends.

**Page fields:**
- What it is (category, brief description)
- What the person says about it (their recommendation, reasoning)
- Any caveats, dosing, or specifics they mention
- Episodes where referenced

**File naming:** Slugified from item name, e.g. `resources/creatine-monohydrate.md`, `resources/eight-sleep.md`

### `themes/` folder (broadened)

The existing `themes/` folder is redefined from "recurring intellectual topics" to **"recurring topics of any kind"**. This makes it the natural home for any domain the person returns to repeatedly — history, travel, food, culture, philosophy, science, sport — regardless of whether it's strictly academic or intellectual.

Examples: `themes/ancient-egypt.md`, `themes/cocktail-culture.md`, `themes/tango.md`, `themes/high-altitude-training.md` all qualify if the person discusses them across multiple episodes.

### `misc/` folder (new catch-all)

**Purpose:** Anything that genuinely doesn't fit `themes/`, `guests/`, `books/`, `positions/`, `studies/`, or `resources/`. Prevents Claude from either inventing arbitrary new top-level folders or force-fitting content into the wrong category.

**Creation threshold:** Same substance bar as other folders — enough material for 2+ meaningful sentences. One-off mentions that don't fit elsewhere go in `log.md` only.

**Examples:** A one-off travel destination that becomes a recurring reference (`misc/japan.md`), a cultural movement the person references frequently (`misc/stoicism-in-practice.md` if not fitting `themes/`), a person who isn't a guest but is frequently cited (`misc/marcus-aurelius.md`).

**File naming:** Slugified from topic name, e.g. `misc/ancient-rome.md`, `misc/fermented-foods.md`

### Implementation

This is a **prompt-only change** to `buildWikiUpdatePrompt`. The updated system prompt:
- Adds `studies/`, `resources/`, and `misc/` to the wiki structure description
- Broadens `themes/` description from "recurring intellectual topics" to "recurring topics of any kind"
- Adds creation rules for each new folder under "Rules for each file type"
- Specifies that `log.md` entries list all cited studies (even passing mentions) under a `> studies:` tag
- Updates the output format example to include paths like `{safeFolder}/studies/omega3-bdnf.md`, `{safeFolder}/resources/creatine.md`, and `{safeFolder}/misc/ancient-egypt.md`
- Updates the `_index.md` catalog type list to include `study`, `resource`, and `misc` types

The `updateWikiFromTranscript` orchestration, `_index.md` catalog mechanics, and path guard (`path.startsWith(safeFolder + '/')`) all handle new folders automatically — no orchestration changes needed.

**Complete taxonomy after this change:**

```
{safeFolder}/
  _index.md        ← catalog
  index.md         ← living synthesis
  log.md           ← append-only ingest log
  themes/          ← recurring topics of any kind (intellectual, cultural, geographic, etc.)
  guests/          ← notable guests
  books/           ← books written or referenced
  positions/       ← specific stated views on named questions
  studies/         ← academic papers cited substantively (new)
  resources/       ← tools, supplements, products endorsed with reasoning (new)
  misc/            ← anything that doesn't fit the above categories (new)

topics/
  _index.md        ← cross-person catalog
  {topic}.md       ← cross-person synthesis
```

---

## Part B: Episode Brief

### Motivation

The wiki is a compounding cross-episode synthesis. The Episode Brief is the complementary episode-specific reference: an exhaustive extraction of every person, study, product, concept, and quote from one episode — equivalent to what Tim Ferriss publishes as "Selected Links" PDFs.

### Sections

The brief always contains these 7 sections (Claude omits a section only if truly nothing belongs in it):

1. **People Mentioned** — name, role/affiliation if stated, context of mention
2. **Books Referenced** — title, author, why/how mentioned
3. **Studies Cited** — title, journal if mentioned, the specific claim being supported
4. **Products / Supplements / Tools** — item name, what the person says about it
5. **Key Concepts & Terminology** — term + definition as used in the episode
6. **Notable Quotes** — verbatim direct quotes with speaker attribution
7. **Episode Structure** — key topics in order (timestamps if detectable in transcript, otherwise topic sequence)

### UI

**New button:** `📋 Episode Brief` added to the modal action bar (`.modal-actions`) immediately after `#wikiBtn` in the HTML.

**Visibility:** Shown for YouTube and podcast entries only. Hidden for blog, twitter, books, appearances.

**State:**
- Hidden on modal open (`display:none` in HTML, same as `wikiBtn`)
- Shown but disabled (`display:''`, `disabled=true`) at the same points where `wikiBtn` is shown — i.e., when the platform is YouTube or podcast
- Enabled (`disabled=false`) when `_currentTranscriptText` is set, controlled by `_refreshBriefBtn()` (called wherever `_refreshWikiBtn()` is called)
- Disabled while generating, re-enabled after

**Output flow:**
1. User clicks `📋 Episode Brief`
2. Button shows `📋 Generating…`, disabled
3. Single Claude call: `callClaude(apiKey, system, user, 4096)`
4. Response rendered as `<div id="briefSection">` inserted below `#transcriptArea` in the modal
5. Brief section contains the 7-section markdown rendered as HTML, plus a `📓 Save to Obsidian` button
6. Button resets to `📋 Episode Brief` (enabled)
7. If user clicks Save: writes `{safeFolder}/briefs/{date}-{episode-slug}.md` to Obsidian vault; button shows `📓 Saved ✓`

**Re-generation:** Clicking `📋 Episode Brief` again replaces the existing `#briefSection` with the new output.

**`_currentBriefMarkdown`:** Module-level variable (alongside `_currentTranscriptText`) that holds the raw markdown from the latest brief generation. Used by the Save function.

### Claude Prompt

`buildEpisodeBriefPrompt(entry, person, transcript)` → `{ system, user }`

**System prompt** instructs Claude to:
- Extract exhaustively — err on the side of inclusion
- Output clean markdown with the 7 sections as `##` headings
- Use bullet points within each section
- For quotes: use `>` blockquote format with `— Speaker Name` attribution
- For episode structure: use numbered list; include timestamps if present in transcript (format: `[HH:MM:SS] Topic`)
- No preamble, no closing remarks — just the 7 sections

**User message:** Episode title, date, platform, person name, then the full transcript.

Output is used directly as markdown — no `<wiki_file>` block parsing needed.

### Obsidian Save

`saveEpisodeBriefToObsidian()`:
- Guards: `_vaultHandle` present, `_currentBriefMarkdown` set
- Calls `_ensureVaultPermission()`
- File path: `{safeFolder}/briefs/{epDate}-{slug}.md` where `slug` is derived from the episode title (slugified, max 50 chars)
- Calls `writeObsidianNote(path, content)`
- On success: Save button shows `📓 Saved ✓` (disabled)
- On failure: toast with error message

### New Functions

| Function | Purpose |
|---|---|
| `buildEpisodeBriefPrompt(entry, person, transcript)` | Build Claude `{ system, user }` for brief extraction |
| `generateEpisodeBrief()` | Orchestration: guards → Claude call → render |
| `_renderBriefSection(markdown)` | Render brief HTML in modal, insert Save button |
| `_refreshBriefBtn()` | Enable/disable brief button based on `_currentTranscriptText` |
| `saveEpisodeBriefToObsidian()` | Write `_currentBriefMarkdown` to vault |

### Module-level variable

```js
let _currentBriefMarkdown = null;  // set by generateEpisodeBrief, read by saveEpisodeBriefToObsidian
```

Reset to `null` in `closeModal()` (alongside `_currentTranscriptText`).

---

## Relationship Between A and B

The two features are **independent but complementary**:

- The Episode Brief captures everything from a single episode (extraction-first, exhaustive)
- The wiki `studies/` and `resources/` pages capture what compounds across episodes (synthesis-first, selective)

They share no code. Running both on the same episode produces different outputs: the brief is a flat reference list; the wiki pages integrate the new material into the growing knowledge base.

The `log.md` entry (wiki) will list cited studies under `> studies:` tags, which means the Episode Brief's studies section and the log entry reinforce each other — but they're written by different Claude calls with different prompts.

---

## Files Changed

| File | Change |
|---|---|
| `index.html` | Update `buildWikiUpdatePrompt` system prompt (Part A); add `briefBtn` HTML, `_currentBriefMarkdown`, `buildEpisodeBriefPrompt`, `generateEpisodeBrief`, `_renderBriefSection`, `_refreshBriefBtn`, `saveEpisodeBriefToObsidian` (Part B) |

All changes in `index.html` only. No backend changes. No new dependencies.
