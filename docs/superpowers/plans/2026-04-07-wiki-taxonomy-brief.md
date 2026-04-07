# Wiki Taxonomy Additions + Episode Brief Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the LLM wiki taxonomy with `studies/`, `resources/`, and `misc/` folders (plus broadened `themes/`), and add a new `📋 Episode Brief` button that extracts a structured per-episode reference document from a transcript.

**Architecture:** Task 1 is a prompt-only change to `buildWikiUpdatePrompt`. Tasks 2–3 add the Episode Brief feature: Task 2 installs the HTML button and wires up show/hide state; Task 3 adds the four new JS functions that drive it. All changes are in `index.html` only.

**Tech Stack:** Vanilla JS, single-file HTML app. Claude API via `callClaude()`. File System Access API via `writeObsidianNote()`. No build step.

**Spec:** `docs/superpowers/specs/2026-04-07-wiki-taxonomy-brief-design.md`

---

## File Map

| File | Change |
|------|--------|
| `index.html` | Task 1: update `buildWikiUpdatePrompt` system prompt; Task 2: add `#briefBtn` HTML, `_currentBriefMarkdown` variable, show/hide wiring, `_refreshBriefBtn`; Task 3: add `buildEpisodeBriefPrompt`, `generateEpisodeBrief`, `_renderBriefSection`, `_briefInline`, `saveEpisodeBriefToObsidian` |

---

## Task 1: Update `buildWikiUpdatePrompt` — taxonomy prompt

**Files:**
- Modify: `index.html` — `buildWikiUpdatePrompt` function (~line 6714)

This task is a pure text change inside the template literal system prompt. Nothing else changes. Search for `function buildWikiUpdatePrompt` to locate it.

- [ ] **Step 1: Broaden themes/ and add new folders to the wiki structure section**

Find this block inside the system prompt template literal (look for `themes/            ← recurring intellectual topics`):

```
    themes/            ← recurring intellectual topics (e.g. themes/free-energy-principle.md)
    guests/            ← notable people who appear with ${personName} (one page per person)
    books/             ← books ${personName} wrote or frequently references
    positions/         ← specific stated views on a defined question (e.g. positions/on-consciousness.md)
```

Replace with:

```
    themes/            ← recurring topics of any kind (intellectual, cultural, geographic, creative, etc.)
    guests/            ← notable people who appear with ${personName} (one page per person)
    books/             ← books ${personName} wrote or frequently references
    positions/         ← specific stated views on a defined question (e.g. positions/on-consciousness.md)
    studies/           ← academic papers and research cited substantively
    resources/         ← tools, supplements, products, and protocols endorsed with reasoning
    misc/              ← catch-all: anything that doesn't fit the above categories
```

- [ ] **Step 2: Update the log.md rule to add the `> studies:` tag**

Find:

```
**${safeFolder}/log.md** — Append ONE new entry at the bottom. Format:
  ## [${epDate}] ${(entry.title || 'Untitled').replace(/`/g, "'")}
  2–3 sentence factual summary of the episode.
  > tags: topic1, topic2, topic3
Never rewrite existing log entries.
```

Replace with:

```
**${safeFolder}/log.md** — Append ONE new entry at the bottom. Format:
  ## [${epDate}] ${(entry.title || 'Untitled').replace(/`/g, "'")}
  2–3 sentence factual summary of the episode.
  > tags: topic1, topic2, topic3
  > studies: Study Title (journal, year) — claim being made; Another Study — claim
Never rewrite existing log entries. The > studies: line lists ALL studies cited in the episode, even passing mentions (title + the claim being supported). Omit the > studies: line entirely if no studies are cited.
```

- [ ] **Step 3: Broaden the themes/ rule and add rules for studies/, resources/, misc/**

Find:

```
**${safeFolder}/themes/{topic}.md** — Create when a topic receives ≥2 substantive mentions across the person's episodes AND no page exists yet. One page per recurring intellectual topic. Factual, encyclopedic. Cross-link to topics/{topic}.md if a cross-person page exists.
```

Replace with:

```
**${safeFolder}/themes/{topic}.md** — Create when a topic receives ≥2 substantive mentions across the person's episodes AND no page exists yet. One page per recurring topic of any kind — intellectual, cultural, geographic, creative. Examples: themes/ancient-egypt.md, themes/cocktail-culture.md, themes/tango.md. Factual, encyclopedic. Cross-link to topics/{topic}.md if a cross-person page exists.
```

Then find:

```
**topics/{topic}.md** — Cross-person synthesis.
```

Immediately before that line, insert the three new rules:

```
**${safeFolder}/studies/{slug}.md** — The log.md entry lists ALL studies cited (even passing mentions) under > studies:. Create a dedicated page ONLY when the person cites a study substantively: they explain what it found, why it matters, or build an argument on it — enough for 2+ meaningful sentences. Include: paper title, authors (if mentioned), journal (if mentioned), year (if mentioned), the person's stated claim or interpretation, episodes where referenced.

**${safeFolder}/resources/{slug}.md** — Create for tools, supplements, apps, gear, foods, protocols, or any non-book item the person endorses with reasoning: dosing, mechanism, use case, or "why I use this." Passing name-drops without context do not qualify. Books go in books/, not here. Include: what it is, what the person says about it, any caveats or specifics, episodes where referenced.

**${safeFolder}/misc/{slug}.md** — Catch-all for content that genuinely doesn't fit themes/, guests/, books/, positions/, studies/, or resources/. Examples: a travel destination the person references repeatedly (misc/japan.md), a historical figure not appearing as a guest (misc/marcus-aurelius.md). Same substance bar: enough for 2+ meaningful sentences.

```

- [ ] **Step 4: Update the catalog type list**

Find:

```
Types: synthesis, log, theme, guest, book, position, topic
```

Replace with:

```
Types: synthesis, log, theme, guest, book, position, study, resource, misc, topic
```

- [ ] **Step 5: Add new folder examples to the output format section**

Find:

```
<wiki_file path="${safeFolder}/themes/free-energy-principle.md">
...theme page content...
</wiki_file>
<wiki_file path="topics/free-energy-principle.md">
```

Replace with:

```
<wiki_file path="${safeFolder}/themes/free-energy-principle.md">
...theme page content...
</wiki_file>
<wiki_file path="${safeFolder}/studies/omega3-bdnf-neuroplasticity.md">
...study page content...
</wiki_file>
<wiki_file path="${safeFolder}/resources/creatine-monohydrate.md">
...resource page content...
</wiki_file>
<wiki_file path="${safeFolder}/misc/ancient-egypt.md">
...misc page content...
</wiki_file>
<wiki_file path="topics/free-energy-principle.md">
```

- [ ] **Step 6: Verify in browser console**

Open `index.html` in browser. In DevTools console run:

```js
const testPages = new Map([['Test Person/_index.md', null]]);
const fakeEntry = { title: 'Test', date: '2026-04-07', platform: 'podcast' };
const fakePerson = { name: 'Test Person', id: 'test-1' };
const { system } = buildWikiUpdatePrompt(fakeEntry, fakePerson, 'transcript', testPages);
console.log('Has studies/', system.includes('studies/'));          // true
console.log('Has resources/', system.includes('resources/'));      // true
console.log('Has misc/', system.includes('misc/'));                // true
console.log('Has broadened themes', system.includes('of any kind')); // true
console.log('Has > studies: tag', system.includes('> studies:'));  // true
console.log('Has study type', system.includes('study, resource, misc')); // true
```

All six should log `true`.

- [ ] **Step 7: Commit**

```bash
cd "/Users/esen/Documents/Cem Code/Pulse"
git add index.html
git commit -m "feat(wiki): expand taxonomy — studies/, resources/, misc/, broaden themes/"
```

---

## Task 2: Episode Brief — button, state, and show/hide wiring

**Files:**
- Modify: `index.html` — HTML modal, JS variable declarations, `openEntry`/`openModal`, `closeModal`, `_refreshWikiBtn` area

This task installs the scaffolding for the Episode Brief button: the HTML element, the state variable, the show/hide logic, and the `_refreshBriefBtn` helper. No brief generation logic yet — that's Task 3.

- [ ] **Step 1: Add `#briefBtn` HTML immediately after `#wikiBtn`**

Find line 1698:
```html
      <button id="wikiBtn"        class="btn btn-ghost" style="display:none" onclick="updateWikiFromTranscript()" title="Update this person's Obsidian wiki with the loaded transcript">🧠 Update Wiki</button>
```

Insert after it:
```html
      <button id="briefBtn"       class="btn btn-ghost" style="display:none" onclick="generateEpisodeBrief()" title="Generate a structured reference brief for this episode">📋 Episode Brief</button>
```

- [ ] **Step 2: Add `_currentBriefMarkdown` state variable**

Find (~line 1929):
```js
let _currentTranscriptText = '';  // transcript/article text for current modal, used by → Calibre push
```

Add immediately after:
```js
let _currentBriefMarkdown  = null; // generated brief for current modal, used by saveEpisodeBriefToObsidian
```

- [ ] **Step 3: Declare and reset `briefBtn` in `openEntry`**

Find (~line 5254):
```js
  const wikiBtn = document.getElementById('wikiBtn');
  wikiBtn.style.display  = 'none';
  wikiBtn.disabled       = true;
  wikiBtn.style.opacity  = '';
  wikiBtn.textContent    = '🧠 Update Wiki';
```

Add immediately after those 5 lines:
```js
  const briefBtn = document.getElementById('briefBtn');
  briefBtn.style.display  = 'none';
  briefBtn.disabled       = true;
  briefBtn.style.opacity  = '';
  briefBtn.textContent    = '📋 Episode Brief';
  document.getElementById('briefSection')?.remove();
```

The last line removes any brief rendered in a previous modal session.

- [ ] **Step 4: Show `briefBtn` alongside `wikiBtn` in the YouTube branch**

Find (~line 5288):
```js
    wikiBtn.style.display = '';
```
within the `} else if (entry.platform === 'youtube') {` block (it's the only `wikiBtn.style.display = ''` in that block).

Add `briefBtn.style.display = '';` immediately after it:
```js
    wikiBtn.style.display = '';
    briefBtn.style.display = '';
```

- [ ] **Step 5: Show `briefBtn` alongside `wikiBtn` in the podcast branch**

Find (~line 5318):
```js
    wikiBtn.style.display = '';
```
within the `} else if (entry.platform === 'podcast') {` block (the one preceded by `obsBtn.style.display = '';`).

Add `briefBtn.style.display = '';` immediately after it:
```js
    wikiBtn.style.display = '';
    briefBtn.style.display = '';
```

- [ ] **Step 6: Reset `_currentBriefMarkdown` in `closeModal`**

Find (~line 6253):
```js
    _currentModalEntry = null;
```

Add `_currentBriefMarkdown = null;` immediately after:
```js
    _currentModalEntry    = null;
    _currentBriefMarkdown = null;
```

- [ ] **Step 7: Add `_refreshBriefBtn` function after `_refreshWikiBtn`**

Find the end of `_refreshWikiBtn` (~line 6007):
```js
function _refreshWikiBtn() {
  const btn = document.getElementById('wikiBtn');
  if (!btn || btn.style.display === 'none') return;
  const ready       = !!_currentTranscriptText;
  btn.disabled      = !ready;
  btn.style.opacity = ready ? '' : '0.45';
  btn.title = ready
    ? "Update this person's Obsidian wiki with the loaded transcript"
    : 'Load a transcript first, then click Update Wiki';
}
```

Add immediately after the closing `}`:
```js
function _refreshBriefBtn() {
  const btn = document.getElementById('briefBtn');
  if (!btn || btn.style.display === 'none') return;
  const ready = !!_currentTranscriptText;
  btn.disabled      = !ready;
  btn.style.opacity = ready ? '' : '0.45';
  btn.title = ready
    ? 'Generate a structured reference brief for this episode'
    : 'Load a transcript first, then click Episode Brief';
}
```

- [ ] **Step 8: Call `_refreshBriefBtn()` everywhere `_refreshWikiBtn()` is called**

Search for all occurrences of `_refreshWikiBtn()` in the file:

```bash
grep -n "_refreshWikiBtn()" index.html
```

For every line that calls `_refreshWikiBtn()`, add `_refreshBriefBtn();` on the immediately following line. There should be approximately 4–5 call sites (around lines 2460, 2526, 2596, 5365). Confirm the count with grep before editing.

- [ ] **Step 9: Verify button wiring in browser**

Open `index.html`. Open a YouTube or podcast entry modal — before loading a transcript, confirm:
- `📋 Episode Brief` button is visible but dimmed (opacity ~0.45)
- Button is disabled (clicking does nothing)

Load the transcript, then confirm:
- `📋 Episode Brief` button becomes fully opaque and enabled
- Clicking it shows `📋 Generating…` and then shows an error toast (no `generateEpisodeBrief` function yet — expected)

Also open a blog entry — confirm `📋 Episode Brief` button is hidden.

- [ ] **Step 10: Commit**

```bash
cd "/Users/esen/Documents/Cem Code/Pulse"
git add index.html
git commit -m "feat(wiki): add Episode Brief button scaffolding — HTML, state, show/hide wiring"
```

---

## Task 3: Episode Brief — functions

**Files:**
- Modify: `index.html` — add 5 new functions in the `// ── OBSIDIAN / WIKI ──` section, after `updateWikiFromTranscript`

Search for `async function updateWikiFromTranscript()` to find the insertion point. The new functions go **after** the closing `}` of `updateWikiFromTranscript`.

- [ ] **Step 1: Add `buildEpisodeBriefPrompt`**

After the closing `}` of `updateWikiFromTranscript`, insert:

```js
// ── EPISODE BRIEF ────────────────────────────────────────────────────────

/**
 * Build the Claude prompt for episode brief extraction.
 * @param {object} entry  — the current modal entry
 * @param {object} person — the tracked person object
 * @param {string} transcript — full transcript text
 * @returns {{ system: string, user: string }}
 */
function buildEpisodeBriefPrompt(entry, person, transcript) {
  const personName = person.name || 'Unknown';
  const epDate = entry.date
    ? new Date(entry.date).toISOString().slice(0, 10)
    : new Date().toISOString().slice(0, 10);

  const system = `You are extracting a structured reference document from a ${entry.platform || 'podcast'} transcript. Extract exhaustively — err on the side of inclusion rather than omission.

Output ONLY the following 7 sections as markdown with ## headings. Use bullet points within each section. Omit a section only if it genuinely has zero content.

## People Mentioned
For each person: name, role or affiliation if stated, and brief context of their mention.

## Books Referenced
For each book: title, author (if stated), and why or how it was mentioned.

## Studies Cited
For each study: title, journal or publication (if stated), and the specific claim or finding being referenced.

## Products / Supplements / Tools
For each item: the name, and what the speaker says about it (dosing, recommendation, why they use it).

## Key Concepts & Terminology
For each concept: the term and a definition as it was used or explained in this episode.

## Notable Quotes
Direct verbatim quotes only. Format each as:
> "Quote text here"
> — Speaker Name

## Episode Structure
Key topics in order. If timestamps are present in the transcript (format HH:MM:SS or MM:SS), include them. Otherwise list topics sequentially as a numbered list.
1. [00:00:00] Topic description

No preamble, no closing remarks, no meta-commentary — output only the 7 sections.`;

  const user = [
    `Episode: ${entry.title || 'Untitled'}`,
    `Date: ${epDate}`,
    `Platform: ${entry.platform || 'unknown'}`,
    `Person: ${personName}`,
    '',
    '--- Transcript ---',
    transcript,
  ].join('\n');

  return { system, user };
}
```

- [ ] **Step 2: Add `_briefInline` helper**

Immediately after `buildEpisodeBriefPrompt`:

```js
/**
 * Convert inline markdown (bold only) to safe HTML.
 * Escapes HTML first, then converts **bold** markers.
 * @param {string} text
 * @returns {string}
 */
function _briefInline(text) {
  return escHtml(text).replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
}
```

- [ ] **Step 3: Add `_renderBriefSection`**

Immediately after `_briefInline`:

```js
/**
 * Render a generated brief markdown string as HTML inside the modal,
 * below #transcriptArea. Removes any previous #briefSection first.
 * Appends a "Save to Obsidian" button inside the section.
 * @param {string} markdown — raw markdown from Claude
 */
function _renderBriefSection(markdown) {
  document.getElementById('briefSection')?.remove();

  const lines = markdown.split('\n');
  let html = '';
  let inList = false;

  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed) {
      if (inList) { html += '</ul>'; inList = false; }
      continue;
    }
    if (trimmed.startsWith('## ')) {
      if (inList) { html += '</ul>'; inList = false; }
      html += `<h3 style="font-family:'JetBrains Mono',monospace;font-size:11px;text-transform:uppercase;letter-spacing:0.08em;color:var(--accent);margin:16px 0 6px 0;padding-bottom:4px;border-bottom:1px solid var(--border)">${escHtml(trimmed.slice(3))}</h3>`;
    } else if (trimmed.startsWith('- ') || trimmed.startsWith('* ')) {
      if (!inList) { html += '<ul style="margin:2px 0 4px 16px;padding:0">'; inList = true; }
      html += `<li style="margin:2px 0;font-size:13px;color:var(--text);line-height:1.5">${_briefInline(trimmed.slice(2))}</li>`;
    } else if (trimmed.startsWith('> ')) {
      if (inList) { html += '</ul>'; inList = false; }
      html += `<blockquote style="border-left:3px solid var(--accent);margin:6px 0 6px 8px;padding:4px 10px;color:var(--muted);font-style:italic;font-size:13px">${escHtml(trimmed.slice(2))}</blockquote>`;
    } else if (/^\d+\./.test(trimmed)) {
      if (inList) { html += '</ul>'; inList = false; }
      html += `<p style="margin:2px 0 2px 16px;font-size:13px;color:var(--text);line-height:1.5">${_briefInline(trimmed.replace(/^\d+\.\s*/, ''))}</p>`;
    } else {
      if (inList) { html += '</ul>'; inList = false; }
      html += `<p style="margin:2px 0;font-size:13px;color:var(--muted);line-height:1.5">${_briefInline(trimmed)}</p>`;
    }
  }
  if (inList) html += '</ul>';

  const section = document.createElement('div');
  section.id = 'briefSection';
  section.style.cssText = 'margin-top:16px;padding:12px 16px;background:var(--surface2);border:1px solid var(--border);border-radius:6px';

  section.innerHTML = `
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px">
      <span style="font-family:'JetBrains Mono',monospace;font-size:10px;color:var(--accent);text-transform:uppercase;letter-spacing:0.1em">📋 Episode Brief</span>
      <button id="briefSaveBtn" class="btn btn-ghost" style="font-size:11px;padding:3px 8px" onclick="saveEpisodeBriefToObsidian()">📓 Save to Obsidian</button>
    </div>
    <div>${html}</div>`;

  document.getElementById('transcriptArea')?.insertAdjacentElement('afterend', section);
}
```

- [ ] **Step 4: Add `generateEpisodeBrief`**

Immediately after `_renderBriefSection`:

```js
/**
 * Generate an Episode Brief for the current modal entry.
 * Requires _currentTranscriptText and pwConfig.anthropicKey.
 * Renders the result inline in the modal via _renderBriefSection.
 */
async function generateEpisodeBrief() {
  const entry = _currentModalEntry;
  if (!entry) return;

  if (!pwConfig.anthropicKey) {
    _showToast('Add your Anthropic API key in ⚙ Settings first', 3500);
    toggleSettings();
    return;
  }
  if (!_currentTranscriptText) {
    _showToast('Load a transcript first, then click Episode Brief', 3500);
    return;
  }

  const btn = document.getElementById('briefBtn');
  if (btn) { btn.disabled = true; btn.textContent = '📋 Generating…'; }

  try {
    const person = persons.find(p => p.id === entry.personId) || {};
    const { system, user } = buildEpisodeBriefPrompt(entry, person, _currentTranscriptText);
    const responseText = await callClaude(pwConfig.anthropicKey, system, user, 4096);
    _currentBriefMarkdown = responseText;
    _renderBriefSection(responseText);
    if (btn) { btn.disabled = false; btn.textContent = '📋 Episode Brief'; }
  } catch(e) {
    if (btn) { btn.disabled = false; btn.textContent = '📋 Episode Brief'; }
    _showToast('Brief generation failed: ' + e.message, 5000);
    console.error('Brief generation error:', e);
  }
}
```

- [ ] **Step 5: Add `saveEpisodeBriefToObsidian`**

Immediately after `generateEpisodeBrief`:

```js
/**
 * Save the current _currentBriefMarkdown to the Obsidian vault.
 * Path: {safeFolder}/briefs/{YYYY-MM-DD}-{episode-slug}.md
 */
async function saveEpisodeBriefToObsidian() {
  const entry = _currentModalEntry;
  if (!_vaultHandle || !_currentBriefMarkdown || !entry) return;

  const saveBtn = document.getElementById('briefSaveBtn');
  if (saveBtn) { saveBtn.disabled = true; saveBtn.textContent = '📓 Saving…'; }

  if (!await _ensureVaultPermission()) {
    _showToast('Obsidian vault permission denied — reconnect in ⚙ Settings', 4000);
    if (saveBtn) { saveBtn.disabled = false; saveBtn.textContent = '📓 Save to Obsidian'; }
    return;
  }

  try {
    const person    = persons.find(p => p.id === entry.personId) || {};
    const safeFolder = sanitizeFileName(person.name || entry.personId);
    const epDate    = entry.date
      ? new Date(entry.date).toISOString().slice(0, 10)
      : new Date().toISOString().slice(0, 10);
    const slug = (entry.title || 'episode')
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-|-$/g, '')
      .slice(0, 50);
    const path = `${safeFolder}/briefs/${epDate}-${slug}.md`;
    const ok = await writeObsidianNote(path, _currentBriefMarkdown);
    if (ok) {
      if (saveBtn) { saveBtn.disabled = true; saveBtn.textContent = '📓 Saved ✓'; }
      _showToast(`✓ Brief saved to ${path}`);
    } else {
      throw new Error('writeObsidianNote returned false');
    }
  } catch(e) {
    if (saveBtn) { saveBtn.disabled = false; saveBtn.textContent = '📓 Save to Obsidian'; }
    _showToast('Failed to save brief: ' + e.message, 5000);
    console.error('Brief save error:', e);
  }
}
```

- [ ] **Step 6: Verify all functions are defined**

In browser DevTools console:

```js
console.log(typeof buildEpisodeBriefPrompt);  // "function"
console.log(typeof _briefInline);              // "function"
console.log(typeof _renderBriefSection);       // "function"
console.log(typeof generateEpisodeBrief);      // "function"
console.log(typeof saveEpisodeBriefToObsidian); // "function"
```

All should return `"function"`.

- [ ] **Step 7: Verify `buildEpisodeBriefPrompt` output**

```js
const fakeEntry  = { title: 'Test Episode', date: '2026-04-07', platform: 'podcast' };
const fakePerson = { name: 'Tommy Wood', id: 'tommy-wood-1' };
const { system, user } = buildEpisodeBriefPrompt(fakeEntry, fakePerson, 'Test transcript here.');

console.log('System has 7 sections:', ['People Mentioned','Books Referenced','Studies Cited','Products','Key Concepts','Notable Quotes','Episode Structure'].every(s => system.includes(s)));  // true
console.log('User starts with episode header:', user.startsWith('Episode: Test Episode'));  // true
console.log('User contains transcript:', user.includes('Test transcript here.'));  // true
```

- [ ] **Step 8: Verify `_renderBriefSection` renders correctly**

```js
_renderBriefSection(`## People Mentioned
- Karl Friston — neuroscientist, discussed free energy principle

## Books Referenced
- The Stimulated Mind by Tommy Wood — main topic of discussion

## Studies Cited
- Omega-3 BDNF study (Journal of Clinical Medicine) — exercise-induced neuroplasticity

## Products / Supplements / Tools
- Creatine Monohydrate — 10g daily for cognitive benefit

## Key Concepts & Terminology
- **BDNF** — Brain-Derived Neurotrophic Factor, mediates neuroplasticity

## Notable Quotes
> "Dance seems to have the highest effect size on mental health."
> — Tommy Wood

## Episode Structure
1. [00:00:00] Introduction
2. [00:05:00] Brain injury in newborns`);
```

Expected: A styled `#briefSection` div appears below `#transcriptArea` in the modal (if a modal is currently open), or in the DOM if not. Check with:

```js
document.getElementById('briefSection') !== null  // true if modal is open
```

If no modal is open, open any podcast/YouTube entry first, load a transcript, then run the test.

- [ ] **Step 9: End-to-end manual test**

Prerequisites: Anthropic API key in ⚙ Settings, transcript loaded.

1. Open a YouTube or podcast entry for any tracked person
2. Load the transcript (wait for it to appear)
3. `📋 Episode Brief` button should now be enabled
4. Click it — label shows `📋 Generating…`
5. Wait for response — a styled brief section appears below the transcript with 7 `##` sections
6. Verify the brief contains plausible people, concepts, and quotes from the episode
7. Click `📓 Save to Obsidian` — button shows `📓 Saving…` then `📓 Saved ✓`
8. Open Obsidian → `{Person Name}/briefs/` folder — file `{date}-{slug}.md` should exist with the brief content
9. Close the modal and reopen a different entry — `#briefSection` should be gone

- [ ] **Step 10: Commit**

```bash
cd "/Users/esen/Documents/Cem Code/Pulse"
git add index.html
git commit -m "feat(wiki): add Episode Brief — extract people, studies, resources, quotes from transcript"
```

---

## Self-Review Checklist

**Spec coverage:**

| Spec requirement | Task |
|---|---|
| `themes/` broadened to "topics of any kind" | Task 1 step 1 + 3 |
| `studies/` folder + rules + `> studies:` log tag | Task 1 steps 2–4 |
| `resources/` folder + rules | Task 1 step 3 |
| `misc/` catch-all folder + rules | Task 1 step 3 |
| Catalog type list updated | Task 1 step 4 |
| Output format examples updated | Task 1 step 5 |
| `#briefBtn` HTML after `#wikiBtn` | Task 2 step 1 |
| `_currentBriefMarkdown` variable | Task 2 step 2 |
| Button reset + `briefSection` removal on modal open | Task 2 step 3 |
| Brief button shown for YouTube and podcast only | Task 2 steps 4–5 |
| `_currentBriefMarkdown = null` in `closeModal` | Task 2 step 6 |
| `_refreshBriefBtn()` — same enable/disable pattern as `_refreshWikiBtn` | Task 2 step 7 |
| `_refreshBriefBtn()` called wherever `_refreshWikiBtn()` is called | Task 2 step 8 |
| `buildEpisodeBriefPrompt` with 7-section system prompt | Task 3 step 1 |
| `generateEpisodeBrief` — guards, Claude call, render | Task 3 step 4 |
| `_renderBriefSection` — markdown→HTML, insert below transcriptArea, Save button | Task 3 step 3 |
| `saveEpisodeBriefToObsidian` — vault write to `briefs/{date}-{slug}.md` | Task 3 step 5 |
| `_currentBriefMarkdown` stored and read by Save | Task 3 steps 4–5 |
| Brief re-generation replaces existing section | Task 3 step 3 (first line removes old section) |
| `maxTokens: 4096` for brief call | Task 3 step 4 (`callClaude(..., 4096)`) |

All spec requirements covered. No gaps found.
