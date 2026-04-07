# LLM Wiki v2 — Multi-File Taxonomy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade the LLM Wiki feature from a fixed two-file structure (`index.md` + `log.md`) to a multi-file taxonomy with `_index.md` catalog navigation and cross-person `topics/` pages.

**Architecture:** Three new helper functions (`_parseCatalog`, `_extractWikiKeywords`, `_selectTopicPages`) feed an orchestration rewrite of `updateWikiFromTranscript()` and a prompt rewrite of `buildWikiUpdatePrompt()`. `parseWikiResponse()` is unchanged. All changes are in `index.html` only.

**Tech Stack:** Vanilla JS, File System Access API (`readObsidianNote` / `writeObsidianNote`), Claude API via `callClaude()`.

**Spec:** `docs/superpowers/specs/2026-04-07-wiki-restructure-design.md`

---

## File Map

| File | Change |
|------|--------|
| `index.html` | Add `_parseCatalog`, `_extractWikiKeywords`, `_selectTopicPages`; rewrite `buildWikiUpdatePrompt`; rewrite `updateWikiFromTranscript` |

All new functions live in the `// ── OBSIDIAN / WIKI ──` section near the existing wiki functions (~line 6469 in the current file). Search for `function buildWikiUpdatePrompt` to find the exact insertion point.

---

## Task 1: `_parseCatalog` helper

**Files:**
- Modify: `index.html` — add function just before `function buildWikiUpdatePrompt`

`_parseCatalog` converts a raw `_index.md` catalog string into an array of page descriptor objects. It is used by `updateWikiFromTranscript` to enumerate which files to read.

Catalog format (one entry per line):
```
themes/free-energy-principle.md | theme | Friston's core mathematical framework
log.md | log | 12 episodes ingested
```

Blank lines and lines not matching the `path | type | summary` pattern are silently skipped.

- [x] **Step 1: Add `_parseCatalog` to `index.html`**

Find the line `function buildWikiUpdatePrompt(` in `index.html`. Immediately above it, add:

```js
// ── WIKI HELPERS ──────────────────────────────────────────────────────────

/**
 * Parse a _index.md catalog string into an array of page descriptors.
 * Each non-blank line must be: path | type | one-line summary
 * Lines that don't match the pattern are silently skipped.
 * @param {string|null} catalogText — raw file content, or null if file not yet created
 * @returns {{ path: string, type: string, summary: string }[]}
 */
function _parseCatalog(catalogText) {
  if (!catalogText) return [];
  return catalogText
    .split('\n')
    .map(line => line.trim())
    .filter(line => line && line.includes('|'))
    .map(line => {
      const parts = line.split('|').map(p => p.trim());
      return parts.length >= 3
        ? { path: parts[0], type: parts[1], summary: parts[2] }
        : null;
    })
    .filter(Boolean);
}
```

- [x] **Step 2: Verify in browser console**

Open `index.html` in the browser. Open DevTools console and run:

```js
_parseCatalog(`index.md | synthesis | Core themes: free energy, consciousness
log.md | log | 12 episodes ingested
themes/predictive-coding.md | theme | Hierarchical Bayesian model
`)
```

Expected output:
```js
[
  { path: 'index.md', type: 'synthesis', summary: 'Core themes: free energy, consciousness' },
  { path: 'log.md',   type: 'log',       summary: '12 episodes ingested' },
  { path: 'themes/predictive-coding.md', type: 'theme', summary: 'Hierarchical Bayesian model' }
]
```

Also verify graceful null handling:
```js
_parseCatalog(null)   // → []
_parseCatalog('')     // → []
_parseCatalog('# just a heading\n\nbad line without pipes') // → []
```

- [x] **Step 3: Commit**

```bash
git add index.html
git commit -m "feat(wiki): add _parseCatalog helper for _index.md navigation"
```

---

## Task 2: `_extractWikiKeywords` + `_selectTopicPages` helpers

**Files:**
- Modify: `index.html` — add both functions immediately after `_parseCatalog`

These two helpers implement the client-side topic page selection from the spec (Step 2 of the update flow). No extra API call is made — keyword matching is done locally.

`_extractWikiKeywords(text)` extracts a Set of lowercase candidate keywords from a transcript:
- Collects words with an initial capital letter that are **not** the first word of a sentence (simple proper-noun heuristic)
- Collects words inside double-quotes (quoted concepts)
- Lowercases all extracted words

`_selectTopicPages(transcript, topicsCatalog)` uses the catalog descriptors from `_parseCatalog` to find which topic pages are relevant to the current transcript. It returns an array of paths (e.g. `['topics/predictive-coding.md']`) — **without** the `topics/` prefix so callers can prepend it as needed.

- [x] **Step 1: Add `_extractWikiKeywords` and `_selectTopicPages` after `_parseCatalog`**

```js
/**
 * Extract a Set of lowercase keyword candidates from a block of text.
 * Uses two signals:
 *   1. Words with an initial capital not at a sentence boundary (proper nouns)
 *   2. Words found inside double-quote pairs (quoted concepts / titles)
 * @param {string} text
 * @returns {Set<string>}
 */
function _extractWikiKeywords(text) {
  const keywords = new Set();
  if (!text) return keywords;

  // Signal 1: proper nouns — capitalised word NOT immediately after . ? ! \n
  // Match a lowercase char or start-of-string, then optional whitespace/punct,
  // then a capital-led word of at least 3 chars.
  const properNounRe = /(?:^|[.?!\n]\s*)([A-Z][a-z]{2,}(?:\s[A-Z][a-z]{2,})*)/gm;
  // Simpler heuristic: collect all words with initial cap that are not the
  // first token on a new sentence. We do this by scanning word-by-word.
  const sentences = text.split(/[.!?\n]+/);
  for (const sentence of sentences) {
    const words = sentence.trim().split(/\s+/);
    for (let i = 1; i < words.length; i++) {   // skip index 0 = sentence start
      const w = words[i].replace(/[^A-Za-z'-]/g, '');
      if (w.length >= 3 && /^[A-Z]/.test(w)) {
        keywords.add(w.toLowerCase());
      }
    }
  }

  // Signal 2: words inside double quotes
  const quotedRe = /"([^"]{3,60})"/g;
  let m;
  while ((m = quotedRe.exec(text)) !== null) {
    m[1].split(/\s+/).forEach(w => {
      const clean = w.replace(/[^A-Za-z'-]/g, '').toLowerCase();
      if (clean.length >= 3) keywords.add(clean);
    });
  }

  return keywords;
}

/**
 * Given a transcript and the parsed topics/_index.md catalog, return the
 * paths (relative to the vault subfolder root) of topic pages whose summary
 * or path contains at least one keyword from the transcript.
 * Returns full paths including the "topics/" prefix.
 * @param {string} transcript
 * @param {{ path: string, type: string, summary: string }[]} topicEntries — from _parseCatalog
 * @returns {string[]}  e.g. ['topics/predictive-coding.md', 'topics/consciousness.md']
 */
function _selectTopicPages(transcript, topicEntries) {
  if (!topicEntries.length) return [];
  const keywords = _extractWikiKeywords(transcript);
  if (!keywords.size) return [];

  return topicEntries
    .filter(entry => {
      const haystack = (entry.path + ' ' + entry.summary).toLowerCase();
      for (const kw of keywords) {
        if (haystack.includes(kw)) return true;
      }
      return false;
    })
    .map(entry => `topics/${entry.path}`);
}
```

- [x] **Step 2: Verify in browser console**

```js
const catalog = _parseCatalog(`predictive-coding.md | topic | Hierarchical Bayesian inference model of perception and action
consciousness.md | topic | The hard problem; IIT; global workspace theory
free-energy-principle.md | topic | Friston's mathematical framework for biological self-organisation`);

const transcript = `Today we discuss Karl Friston's work on the Free-Energy Principle and how it relates to
consciousness. He mentions "predictive coding" extensively.`;

_selectTopicPages(transcript, catalog);
// Expected: includes 'topics/predictive-coding.md' and 'topics/free-energy-principle.md'
// (consciousness may or may not match depending on capitalisation heuristic — acceptable)
```

Also verify empty-input safety:
```js
_selectTopicPages('', catalog)          // → []
_selectTopicPages(transcript, [])       // → []
```

- [x] **Step 3: Commit**

```bash
git add index.html
git commit -m "feat(wiki): add _extractWikiKeywords and _selectTopicPages helpers"
```

---

## Task 3: Rewrite `buildWikiUpdatePrompt`

**Files:**
- Modify: `index.html` — replace existing `buildWikiUpdatePrompt` function (~line 6605)

The new signature changes from `(entry, person, transcript, existingIndex, existingLog)` to `(entry, person, transcript, pages)` where `pages` is a `Map<string, string>` of `relativePath → fileContent` for all loaded files.

The system prompt is substantially expanded to describe the full taxonomy, catalog format, creation thresholds, writing style, and cross-person topic rules.

- [x] **Step 1: Replace `buildWikiUpdatePrompt` entirely**

Find `function buildWikiUpdatePrompt(entry, person, transcript, existingIndex, existingLog) {` and replace the entire function with:

```js
/**
 * Build the Claude prompt for a wiki update.
 * @param {object} entry  — the current modal entry (title, date, platform, etc.)
 * @param {object} person — the tracked person object
 * @param {string} transcript — full transcript text
 * @param {Map<string, string>} pages — map of relativePath → content for all loaded files.
 *   Keys are relative to the vault subfolder root, e.g.:
 *     "Karl Friston/_index.md"
 *     "Karl Friston/index.md"
 *     "topics/_index.md"
 *     "topics/predictive-coding.md"
 *   A value of null means the file does not yet exist.
 * @returns {{ system: string, user: string }}
 */
function buildWikiUpdatePrompt(entry, person, transcript, pages) {
  const personName = person.name || 'Unknown';
  const safeFolder = sanitizeFileName(personName);
  const epDate     = entry.date
    ? new Date(entry.date).toISOString().slice(0, 10)
    : new Date().toISOString().slice(0, 10);

  const system = `You maintain a personal knowledge wiki about ${personName} in Obsidian markdown.

## Wiki structure

The wiki uses a predefined taxonomy. All files live under a person folder and a shared topics folder:

  ${safeFolder}/
    _index.md          ← catalog: one line per page (path | type | one-line summary)
    index.md           ← living synthesis: recurring themes, key positions, notable quotes
    log.md             ← append-only ingest log: one ## entry per episode, never rewritten
    themes/            ← recurring intellectual topics (e.g. themes/free-energy-principle.md)
    guests/            ← notable people who appear with ${personName} (one page per person)
    books/             ← books ${personName} wrote or frequently references
    positions/         ← specific stated views on a defined question (e.g. positions/on-consciousness.md)

  topics/
    _index.md          ← catalog for cross-person topic pages
    {topic}.md         ← cross-person synthesis: what multiple tracked people say about a topic

## Rules for each file type

**${safeFolder}/index.md** — Revise and integrate on every update. Never just append. Organise by theme, not by episode. No em dashes. No editorial voice ("interestingly", "deeply"). Encyclopedic, factual tone. Direct quotes from the transcript may carry emotional weight.

**${safeFolder}/log.md** — Append ONE new entry at the bottom. Format:
  ## [${epDate}] ${(entry.title || 'Untitled').replace(/`/g, "'")}
  2–3 sentence factual summary of the episode.
  > tags: topic1, topic2, topic3
Never rewrite existing log entries.

**${safeFolder}/themes/{topic}.md** — Create when a topic receives ≥2 substantive mentions across the person's episodes AND no page exists yet. One page per recurring intellectual topic. Factual, encyclopedic. Cross-link to topics/{topic}.md if a cross-person page exists.

**${safeFolder}/guests/{name}.md** — Create when a guest appears with ${personName} more than once and there is enough material for ≥3 meaningful sentences. Note the relationship, recurring themes in their conversations, key episodes.

**${safeFolder}/books/{title}.md** — Create for books ${personName} wrote or substantively references. Include: publication context, why ${personName} references it, key ideas as they understand them.

**${safeFolder}/positions/{question}.md** — Create for specific, named positions ${personName} holds on a defined question (e.g. "on consciousness", "on AI risk"). Include the position, its development over time, any contradictions or evolution.

**topics/{topic}.md** — Cross-person synthesis. Update if this episode substantively advances understanding of the topic. Create if: (a) the topic doesn't have a page yet AND (b) the episode covers it well enough to write ≥3 meaningful sentences. Always write from the perspective of synthesising what multiple thinkers say about the topic — not just ${personName}'s view.

## Catalog maintenance (_index.md files)

The catalog format is: one line per page, pipe-separated:
  path | type | one-line summary

Types: synthesis, log, theme, guest, book, position, topic

Always return an updated ${safeFolder}/_index.md that reflects any pages you created or significantly changed. Return an updated topics/_index.md whenever you create or significantly update a topic page. The catalog must stay in sync with the actual pages.

## Output format

Return ONLY <wiki_file> blocks — no commentary, no markdown fences around the blocks:

<wiki_file path="${safeFolder}/_index.md">
...full updated catalog...
</wiki_file>
<wiki_file path="${safeFolder}/index.md">
...full updated synthesis...
</wiki_file>
<wiki_file path="${safeFolder}/log.md">
...full log with new entry appended at bottom...
</wiki_file>

Include a block for every file you update or create. Omit files you did not change.
If you create a new file that is not yet in the catalog, include an updated _index.md that lists it.`;

  // Build user message
  const lines = [
    `Episode: ${entry.title || 'Untitled'}`,
    `Date: ${epDate}`,
    `Platform: ${entry.platform || 'unknown'}`,
    `Person: ${personName}`,
    '',
  ];

  // Append each loaded page (or a "(not yet created)" notice)
  for (const [path, content] of pages) {
    lines.push(`--- ${path} ---`);
    lines.push(content ?? '(not yet created)');
    lines.push('');
  }

  lines.push('--- Transcript ---');
  lines.push(transcript);

  return { system, user: lines.join('\n') };
}
```

- [x] **Step 2: Verify function signature in console**

Open `index.html` in the browser. In DevTools console, run:

```js
const testPages = new Map([
  ['Karl Friston/_index.md', null],
  ['Karl Friston/index.md', null],
  ['Karl Friston/log.md', null],
]);
const fakeEntry = { title: 'Test Episode', date: '2026-04-07', platform: 'podcast' };
const fakePerson = { name: 'Karl Friston', id: 'karl-friston-1' };
const { system, user } = buildWikiUpdatePrompt(fakeEntry, fakePerson, 'Transcript text here.', testPages);
console.log('System length:', system.length);    // should be > 2000 chars
console.log('User preview:', user.slice(0, 200)); // should start with "Episode: Test Episode"
console.log('Pages in user:', user.includes('--- Karl Friston/_index.md ---')); // true
console.log('Transcript in user:', user.includes('Transcript text here.')); // true
```

- [x] **Step 3: Commit**

```bash
git add index.html
git commit -m "feat(wiki): rewrite buildWikiUpdatePrompt — full taxonomy prompt + Map-based pages input"
```

---

## Task 4: Rewrite `updateWikiFromTranscript`

**Files:**
- Modify: `index.html` — replace existing `updateWikiFromTranscript` function (~line 6667)

This is the main orchestration rewrite. The new flow:
1. Read `{safeFolder}/_index.md` + `topics/_index.md`
2. Parse person catalog → list of page paths to read
3. Keyword-filter topics catalog → select topic page paths to load
4. Read all selected pages in parallel
5. Build `pages` Map and call `buildWikiUpdatePrompt`
6. Call Claude with `maxTokens: 8192`
7. Parse response, validate paths, write files
8. Update button label with file count

**Backward compatibility:** If `{safeFolder}/_index.md` is null (no catalog yet), fall back to reading `index.md` + `log.md` directly — same as the old behaviour. This means first-time updates on an existing wiki work without any manual migration; the catalog gets created by Claude as part of the first new-style update.

- [x] **Step 1: Replace `updateWikiFromTranscript` entirely**

Find `async function updateWikiFromTranscript() {` and replace the entire function with:

```js
async function updateWikiFromTranscript() {
  const entry  = _currentModalEntry;
  const person = persons.find(p => p.id === entry?.personId) || {};

  if (!entry) return;

  if (!pwConfig.anthropicKey) {
    _showToast('Add your Anthropic API key in ⚙ Settings first', 3500);
    toggleSettings();
    return;
  }
  if (!_vaultHandle) {
    _showToast('No Obsidian vault connected — pick one in ⚙ Settings', 3500);
    toggleSettings();
    return;
  }
  if (!_currentTranscriptText) {
    _showToast('Load a transcript first, then click Update Wiki', 3500);
    return;
  }

  const btn = document.getElementById('wikiBtn');
  if (btn) { btn.disabled = true; btn.textContent = '🧠 Reading catalog…'; }

  if (!await _ensureVaultPermission()) {
    _showToast('Obsidian vault permission denied — reconnect in ⚙ Settings', 4000);
    if (btn) { btn.disabled = false; btn.style.opacity = ''; }
    return;
  }

  try {
    const safeFolder = sanitizeFileName(person.name || entry.personId);

    // ── Step 1: Read both catalogs ──────────────────────────────────────────
    const [personCatalogText, topicsCatalogText] = await Promise.all([
      readObsidianNote(`${safeFolder}/_index.md`),
      readObsidianNote('topics/_index.md'),
    ]);

    const personEntries = _parseCatalog(personCatalogText);
    const topicsEntries = _parseCatalog(topicsCatalogText);

    // ── Step 2: Determine which pages to load ──────────────────────────────
    // Person pages: everything listed in the catalog, or fallback to the
    // two legacy files when no catalog exists yet.
    const personPagePaths = personEntries.length
      ? personEntries.map(e => `${safeFolder}/${e.path}`)
      : [`${safeFolder}/index.md`, `${safeFolder}/log.md`];

    // Topic pages: keyword-filtered from the topics catalog
    const selectedTopicPaths = _selectTopicPages(_currentTranscriptText, topicsEntries);

    if (btn) btn.textContent = '🧠 Loading pages…';

    // ── Step 3: Read all pages in parallel ─────────────────────────────────
    const allPaths = [...personPagePaths, ...selectedTopicPaths];
    // Always include the catalog files themselves so Claude can update them
    const catalogPaths = [
      `${safeFolder}/_index.md`,
      'topics/_index.md',
    ];
    const pathsToRead = [...new Set([...catalogPaths, ...allPaths])];

    const contents = await Promise.all(pathsToRead.map(p => readObsidianNote(p)));

    // Build the pages Map — preserves insertion order for the prompt
    const pages = new Map();
    // Catalogs first so they appear at the top of the user message
    pages.set(`${safeFolder}/_index.md`, personCatalogText);
    pages.set('topics/_index.md', topicsCatalogText);
    // Then all other pages (skip the catalog paths we already added)
    pathsToRead.forEach((path, i) => {
      if (!pages.has(path)) pages.set(path, contents[pathsToRead.indexOf(path)]);
    });

    if (btn) btn.textContent = '🧠 Calling Claude…';

    // ── Step 4: Single Claude call ─────────────────────────────────────────
    const { system, user } = buildWikiUpdatePrompt(
      entry, person, _currentTranscriptText, pages
    );
    const responseText = await callClaude(pwConfig.anthropicKey, system, user, 8192);

    // ── Step 5: Parse + validate + write ───────────────────────────────────
    const returnedPages = parseWikiResponse(responseText);
    if (Object.keys(returnedPages).length === 0) {
      throw new Error('Claude returned no wiki files — unexpected response format');
    }

    if (btn) btn.textContent = '🧠 Writing…';

    // Path guard: only allow files under {safeFolder}/ or topics/
    let written = 0;
    for (const [path, content] of Object.entries(returnedPages)) {
      const allowed = path.startsWith(safeFolder + '/') || path.startsWith('topics/');
      if (!allowed) {
        console.warn('Wiki: rejected path outside allowed directories:', path);
        continue;
      }
      // Extra safety: reject path traversal attempts
      if (path.includes('..') || path.startsWith('/')) {
        console.warn('Wiki: rejected unsafe path:', path);
        continue;
      }
      const ok = await writeObsidianNote(path, content);
      if (ok) written++;
    }

    if (btn) {
      btn.disabled  = false;
      btn.textContent = `🧠 Wiki ✓ (${written} file${written !== 1 ? 's' : ''})`;
    }
    _showToast(`✓ Wiki updated — ${written} file${written !== 1 ? 's' : ''} written to Obsidian`);

  } catch(e) {
    if (btn) { btn.disabled = false; btn.textContent = '🧠 Update Wiki'; }
    _showToast('Wiki update failed: ' + e.message, 5000);
    console.error('Wiki update error:', e);
  }
}
```

- [x] **Step 2: Verify the Map-building logic produces no duplicate keys**

In DevTools console, paste this test (no vault needed):

```js
// Simulate the Map-building logic
const safeFolder = 'Karl Friston';
const personCatalogText = 'index.md | synthesis | Core themes\nlog.md | log | 5 episodes';
const topicsCatalogText = null;
const personEntries = _parseCatalog(personCatalogText);
const topicsEntries = _parseCatalog(topicsCatalogText);

const personPagePaths = personEntries.length
  ? personEntries.map(e => `${safeFolder}/${e.path}`)
  : [`${safeFolder}/index.md`, `${safeFolder}/log.md`];

const selectedTopicPaths = _selectTopicPages('Some transcript text', topicsEntries);

const allPaths = [...personPagePaths, ...selectedTopicPaths];
const catalogPaths = [`${safeFolder}/_index.md`, 'topics/_index.md'];
const pathsToRead = [...new Set([...catalogPaths, ...allPaths])];

console.log('Paths to read:', pathsToRead);
// Expected (no duplicates):
// ['Karl Friston/_index.md', 'topics/_index.md', 'Karl Friston/index.md', 'Karl Friston/log.md']

const pages = new Map();
pages.set(`${safeFolder}/_index.md`, personCatalogText);
pages.set('topics/_index.md', topicsCatalogText);
pathsToRead.forEach((path, i) => {
  if (!pages.has(path)) pages.set(path, `content of ${path}`);
});

console.log('Pages Map keys:', [...pages.keys()]);
// Expected: ['Karl Friston/_index.md', 'topics/_index.md', 'Karl Friston/index.md', 'Karl Friston/log.md']
console.log('Map size === pathsToRead.length:', pages.size === pathsToRead.length); // true
```

- [x] **Step 3: Verify path guard logic**

In DevTools console:

```js
const safeFolder = 'Karl Friston';
const testPaths = [
  'Karl Friston/_index.md',          // ✓ allowed
  'Karl Friston/themes/test.md',     // ✓ allowed
  'topics/consciousness.md',          // ✓ allowed
  'topics/_index.md',                 // ✓ allowed
  'Lex Fridman/index.md',             // ✗ rejected (different person)
  '../secrets.md',                    // ✗ rejected (path traversal)
  '/etc/passwd',                      // ✗ rejected (absolute path)
];

testPaths.forEach(path => {
  const allowed = path.startsWith(safeFolder + '/') || path.startsWith('topics/');
  const safe    = !path.includes('..') && !path.startsWith('/');
  console.log(path, '->', (allowed && safe) ? '✓ ALLOW' : '✗ REJECT');
});
// Expected:
// Karl Friston/_index.md     → ✓ ALLOW
// Karl Friston/themes/test.md → ✓ ALLOW
// topics/consciousness.md    → ✓ ALLOW
// topics/_index.md           → ✓ ALLOW
// Lex Fridman/index.md       → ✗ REJECT
// ../secrets.md              → ✗ REJECT
// /etc/passwd                → ✗ REJECT
```

- [x] **Step 4: End-to-end manual test**

Prerequisites: Anthropic API key set in ⚙ Settings, Obsidian vault connected.

1. Open a YouTube or podcast episode for a tracked person (e.g. Karl Friston)
2. Load the transcript — wait for it to appear in the transcript area
3. Click **🧠 Update Wiki**
4. Watch label progression: `Reading catalog…` → `Loading pages…` → `Calling Claude…` → `Writing…` → `Wiki ✓ (N files)`
5. Open Obsidian → navigate to `{subfolder}/Karl Friston/`
6. Verify:
   - `_index.md` exists and lists all created pages in `path | type | summary` format
   - `index.md` exists and contains a synthesis (not an episode summary)
   - `log.md` exists with a `## [YYYY-MM-DD]` entry at the bottom
   - If the transcript mentions a recurring topic (e.g. "free energy principle"), a `themes/` page may exist
7. Run the update a second time on a different episode for the same person
8. Verify:
   - `log.md` has a second entry appended (old entry is intact)
   - `index.md` is revised/integrated, not just appended
   - `_index.md` reflects any newly created pages

**Backward compatibility test** (only needed if you have an existing wiki):
1. Delete `Karl Friston/_index.md` from the vault (if it exists)
2. Run Update Wiki
3. Verify it still works — Claude creates `_index.md` listing the existing pages

- [x] **Step 5: Commit**

```bash
git add index.html
git commit -m "feat(wiki): rewrite updateWikiFromTranscript — catalog-driven multi-file flow"
```

---

## Self-Review Checklist

**Spec coverage:**

| Spec requirement | Task |
|---|---|
| `_index.md` catalog per person (`path \| type \| summary` format) | Task 1 (`_parseCatalog`), Task 3 (system prompt), Task 4 (reads + writes catalog) |
| `topics/_index.md` catalog for cross-person pages | Task 1, Task 3, Task 4 |
| Client-side keyword extraction + topic page selection | Task 2 |
| New `buildWikiUpdatePrompt` with full taxonomy + style rules | Task 3 |
| Pages passed as Map, not positional args | Task 3 (new signature), Task 4 (builds Map) |
| `maxTokens` raised to 8192 | Task 4 (Step 1, `callClaude` call) |
| Path guard: allow `{safeFolder}/*` and `topics/*` only | Task 4 (Step 1, write loop) |
| Path traversal rejection (`..`, absolute paths) | Task 4 (Step 1) |
| Button label progression (4 stages + file count) | Task 4 (Step 1) |
| Backward compat: no catalog → fallback to `index.md` + `log.md` | Task 4 (Step 1, `personEntries.length` check) |
| `parseWikiResponse` unchanged | ✅ Not touched |

All spec requirements covered. No gaps found.
