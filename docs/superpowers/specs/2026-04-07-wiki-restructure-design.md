# Wiki Restructure — Multi-File + Catalog Design

**Date:** 2026-04-07
**Feature:** LLM Wiki v2 — multi-file taxonomy with `_index.md` catalog navigation
**File:** `index.html` only

---

## Background

The current LLM Wiki feature writes exactly two files per person: `{Person}/index.md` (synthesis) and `{Person}/log.md` (ingest log). Claude reads both files blind on every update. This works for 5–10 episodes but doesn't scale: the synthesis grows monolithic, there's no structure for drilling into specific topics or guests, and there's no way to maintain cross-person topic pages.

The new design introduces a predefined taxonomy with per-page files, `_index.md` catalog files for navigation, and a shared `topics/` directory for cross-person synthesis.

---

## File Structure

```
{Obsidian vault}/
  topics/
    _index.md                        ← topics catalog: all topic pages + summaries
    predictive-coding.md
    consciousness.md
    free-energy-principle.md
  Karl Friston/
    _index.md                        ← per-person catalog: all pages + summaries
    log.md                           ← append-only ingest log (unchanged)
    index.md                         ← synthesis (unchanged name, backward compat)
    themes/
      predictive-coding.md
      free-energy-principle.md
    guests/
      lex-fridman.md
    books/
      the-free-energy-principle.md
    positions/
      on-consciousness.md
  Lex Fridman/
    _index.md
    log.md
    index.md
    themes/
    guests/
    ...
```

### Page Type Taxonomy

| Directory | What goes here |
|-----------|---------------|
| `index.md` | Living synthesis — recurring themes, key positions, notable quotes. Revised and integrated each update; never just appended. |
| `log.md` | Append-only chronological ingest log. One `## [YYYY-MM-DD] Title` entry per episode. Never rewritten. |
| `themes/` | Recurring intellectual topics this person returns to (e.g. `free-energy-principle.md`). Created when a topic gets ≥2 substantive mentions. |
| `guests/` | Notable people who appear with this person. One page per recurring guest. |
| `books/` | Books this person wrote or frequently references. |
| `positions/` | Specific stated views or arguments on a defined question (e.g. `on-consciousness.md`). |
| `topics/` (top-level) | Cross-person synthesis pages. Same topic appearing across multiple tracked people. Updated in the same pass as person pages. |

### `_index.md` Catalog Format

Each entry is one line:
```
{path} | {type} | {one-line summary}
```

Example — `Karl Friston/_index.md`:
```
index.md | synthesis | Core themes: free energy, active inference, predictive coding, consciousness
log.md | log | 12 episodes ingested
themes/free-energy-principle.md | theme | Friston's core mathematical framework for biological self-organisation
themes/predictive-coding.md | theme | Hierarchical Bayesian inference model of perception and action
guests/lex-fridman.md | guest | Three appearances; conversations centre on consciousness and AI
positions/on-consciousness.md | position | Consciousness as inference; IIT critique; relationship to active inference
```

---

## Update Flow

```
1. READ CATALOGS
   Read {Person}/_index.md       → know what person pages exist
   Read topics/_index.md          → know what topic pages exist
   (Both may be null on first update — handled gracefully)

2. SELECT TOPIC PAGES  (client-side, no extra API call)
   Extract keywords from transcript (proper nouns, named concepts, titles)
   Match keywords against topic catalog entry descriptions
   Select topic pages with ≥1 keyword match

3. READ CONTENT
   Read ALL pages listed in {Person}/_index.md
   Read selected topic pages from topics/
   (On first update: read index.md + log.md if they exist — legacy migration)

4. SINGLE CLAUDE CALL
   Input: both catalogs + all loaded page contents + transcript
   Output: <wiki_file path="..."> blocks for all updated/new files
   Claude decides:
     - Which existing pages to update
     - Which new pages to create (respecting creation thresholds)
     - Which topic pages in topics/ to update
     - Whether _index.md catalogs need new entries

5. WRITE
   Write all returned files
   Path guard: allow {safeFolder}/* and topics/* — reject anything else
```

### Keyword Extraction (client-side)

Simple extraction — no NLP library needed:
- Split transcript into words, filter stop words
- Collect proper nouns (words with initial capital not at sentence start) + quoted phrases
- Match against topic `_index.md` lines (case-insensitive substring match)

If `topics/_index.md` does not exist yet, skip topic page selection — no topic pages are loaded.

---

## Claude Prompt Design

### System Prompt (new)

Covers:
- Full taxonomy description (what each directory/file type is for)
- Page creation threshold: create a new themed page when a topic gets ≥2 substantive mentions across episodes and no page exists yet
- Catalog format: one line per page — `path | type | one-line summary`
- Catalog maintenance: always return updated `_index.md` if any pages were added, renamed, or meaningfully changed
- Log format: `## [YYYY-MM-DD] Episode Title` + 2–3 sentence summary + `> tags: topic1, topic2`
- Writing style: encyclopedic, factual, no AI editorial voice (per wiki-gen conventions)
- Cross-person topics: if a topic in `topics/` is substantively advanced by this episode, update it; if a relevant topic doesn't have a page yet and the episode covers it well, create it

### User Message Structure

```
Episode: {title}
Date: {date}
Platform: {platform}
Person: {personName}

--- {safeFolder}/_index.md ---
{catalog content or "(not yet created)"}

--- topics/_index.md ---
{topics catalog or "(not yet created)"}

--- {safeFolder}/index.md ---
{synthesis content or "(not yet created)"}

--- {safeFolder}/log.md ---
{log content or "(not yet created)"}

--- {safeFolder}/themes/free-energy-principle.md ---
{content}

... (all other loaded pages)

--- Transcript ---
{transcript}
```

### Output Format

Same `<wiki_file>` format — now with more blocks:

```xml
<wiki_file path="Karl Friston/_index.md">…</wiki_file>
<wiki_file path="Karl Friston/index.md">…</wiki_file>
<wiki_file path="Karl Friston/log.md">…</wiki_file>
<wiki_file path="Karl Friston/themes/free-energy-principle.md">…</wiki_file>
<wiki_file path="topics/free-energy-principle.md">…</wiki_file>
<wiki_file path="topics/_index.md">…</wiki_file>
```

### Token Budget

- `maxTokens` raised from 4096 → 8192
- Input tokens: catalogs (~500) + person pages (~3000 for mature wiki) + topic pages (~1000) + transcript (~3000) ≈ 7500 input tokens — well within Sonnet/Opus context window

---

## Code Changes (`index.html` only)

### 1. `updateWikiFromTranscript()` — orchestration rewrite

```
OLD: read index.md + log.md → 1 Claude call → write 2 files
NEW: read catalogs → read all person pages + selected topic pages
     → 1 Claude call → write N files
```

- Read `{safeFolder}/_index.md` and `topics/_index.md`
- Parse person catalog to get list of existing page paths; read each
- Run keyword filter on transcript vs topic catalog; read matching topic pages
- Assemble prompt, call Claude with `maxTokens: 8192`
- Write all returned files; update button label with file count: `🧠 Wiki ✓ (N files)`
- **Path guard**: `path.startsWith(safeFolder + '/') || path.startsWith('topics/')` — reject anything else

### 2. `buildWikiUpdatePrompt()` — expanded

- New system prompt with full taxonomy, creation thresholds, catalog format, style rules
- User message assembles all loaded pages with `--- path ---` separators
- Returns `{ system, user }` as before

### 3. `parseWikiResponse()` — unchanged

Already handles arbitrary `<wiki_file path="...">` blocks.

### 4. Button label progression

```
🧠 Reading catalog…  →  🧠 Loading pages…  →  🧠 Calling Claude…  →  🧠 Writing…  →  🧠 Wiki ✓ (N files)
```

---

## Backward Compatibility

- Existing wikis (`index.md` + `log.md` only) work without migration
- On first new-style update, `_index.md` is created listing the existing files
- `index.md` keeps its name — no rename to `overview.md`
- If `{safeFolder}/_index.md` doesn't exist, step 3 falls back to reading `index.md` + `log.md` directly (same as current behavior)

---

## Out of Scope

- A second Claude call for page selection (using single call + client-side keyword filter instead)
- UI for browsing the wiki from within Pulse (Obsidian handles this)
- Automatic wiki linting / health-check (future feature)
- "Save this answer to the wiki" from AI Notes panel (future feature)
