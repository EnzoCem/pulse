# Add Person Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the flat URL-input Add Person form with a role-checkbox + auto-search flow where the user picks what a person does (Podcaster / YouTuber / Blogger / Writer), hits Search, and gets auto-selected results with inline paste overrides.

**Architecture:** All changes are inside `index.html` (single-file app). The new flow adds three runtime state variables (`_formRoles`, `_roleResults`, `_roleSelections`), rewrites `searchPersonByName()` to branch on `_addType` and dispatch role-scoped API calls in parallel, adds a `renderRoleResults()` rendering function, and updates `addPerson()` to read from the new state instead of DOM inputs. Source mode is unchanged. The existing `#f-podcast`, `#f-youtube`, `#f-blog`, `#f-books`, `#f-twitter` inputs become `type="hidden"` so `addPerson()` still has a single read path.

**Tech Stack:** Vanilla JS, single HTML file, iTunes Search API, `_findYouTube()` (Google Custom Search scrape), Open Library API (already powering `fetchBooks()`), CSS custom properties.

---

## File map

| File | Action | What changes |
|---|---|---|
| `index.html` (CSS ~line 159) | Modify | Add `.role-chip-grid`, `.role-chip`, `.role-chip.checked`, `.role-result-section`, `.role-result-header`, `.role-result-row`, `.role-result-dot`, `.role-results-grid`, `.role-books-grid`, `.role-book-card`, `.role-book-thumb`, `.inline-override-input`, `.role-no-results`, `.twitter-hint` |
| `index.html` (HTML lines 1012–1103) | Replace | New Add Person panel markup: role chips, `#roleResultsArea`, hidden legacy inputs, no `.feed-inputs` visible in person mode |
| `index.html` (JS ~line 2254) | Modify | `toggleAddPanel()` — also clears `_formRoles`, `_roleResults`, `_roleSelections`, role chip state |
| `index.html` (JS ~line 2267) | Modify | `setAddType()` — toggle `#rolePickerWrap` and `#feedInputsSection` visibility, call `_updateSearchBtn()` |
| `index.html` (JS ~line 2284) | Modify | Add `let _formRoles`, `let _roleResults`, `let _roleSelections` globals alongside `let _suggestions` |
| `index.html` (JS ~line 2490) | Replace | `searchPersonByName()` — source mode unchanged; person mode runs role-scoped parallel search |
| `index.html` (JS after `searchPersonByName`) | Add | `renderRoleResults(query)`, `selectRoleResult(role, idx)`, `toggleRole(role)`, `_updateSearchBtn()` |
| `index.html` (JS ~line 2641) | Modify | `addPerson()` — person mode reads from `_roleSelections` + override inputs; source mode unchanged |

---

## Task 1: CSS — role chips and results panel styles

**Files:**
- Modify: `index.html` (CSS block, after `.feed-row` styles ~line 180)

- [ ] **Step 1: Locate the insertion point**

  Find the line in `index.html` that reads:
  ```css
  .form-actions { display: flex; gap: 10px; justify-content: flex-end; }
  ```
  The new CSS block goes **immediately before** this line.

- [ ] **Step 2: Insert the new CSS**

  Insert the following block before `.form-actions`:

  ```css
  /* ── ADD PERSON — ROLE CHIPS ── */
  .role-chip-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 6px;
  }
  .role-chip {
    display: flex; align-items: center; gap: 8px;
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: 4px;
    padding: 8px 10px;
    cursor: pointer;
    font-family: 'JetBrains Mono', monospace;
    font-size: 11px;
    color: var(--text);
    text-align: left;
    transition: border-color 0.15s, background 0.15s;
  }
  .role-chip:hover { border-color: var(--accent); }
  .role-chip.checked {
    border-color: var(--accent);
    background: rgba(232,200,74,0.06);
  }
  .role-dot {
    width: 12px; height: 12px; flex-shrink: 0;
    border: 1.5px solid var(--border);
    border-radius: 2px;
    transition: background 0.15s, border-color 0.15s;
  }
  .role-chip.checked .role-dot {
    background: var(--accent);
    border-color: var(--accent);
  }
  .twitter-hint {
    font-size: 10px; color: var(--muted);
    margin-top: 6px; margin-bottom: 2px;
  }

  /* ── ADD PERSON — ROLE RESULTS ── */
  .role-results-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 14px;
    margin: 14px 0 6px;
  }
  .role-result-section { display: flex; flex-direction: column; gap: 4px; }
  .role-result-header {
    font-size: 10px; letter-spacing: 0.08em; text-transform: uppercase;
    padding-bottom: 5px;
    border-bottom: 1px solid var(--border);
    margin-bottom: 4px;
  }
  .podcast-color { color: var(--podcast); }
  .youtube-color { color: var(--youtube); }
  .blog-color    { color: var(--blog); }
  .books-color   { color: #c084fc; }

  .role-result-row {
    display: flex; align-items: flex-start; gap: 8px;
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: 4px;
    padding: 7px 9px;
    cursor: pointer;
    transition: border-color 0.12s;
  }
  .role-result-row:hover { border-color: var(--accent); }
  .role-result-row.selected { border-color: var(--accent); background: rgba(232,200,74,0.04); }
  .role-result-dot {
    width: 8px; height: 8px; border-radius: 50%;
    border: 1.5px solid var(--muted);
    flex-shrink: 0; margin-top: 3px;
    transition: background 0.12s, border-color 0.12s;
  }
  .role-result-row.selected .role-result-dot {
    background: var(--accent); border-color: var(--accent);
  }
  .role-result-title {
    font-family: 'JetBrains Mono', monospace;
    font-size: 11px; color: var(--text); line-height: 1.4;
  }
  .role-result-sub { font-size: 10px; color: var(--muted); }
  .role-no-results { font-size: 11px; color: var(--muted); padding: 6px 0; font-style: italic; }

  .inline-override-input {
    background: var(--bg);
    border: 1px dashed var(--border);
    border-radius: 4px;
    color: var(--muted);
    font-family: 'JetBrains Mono', monospace;
    font-size: 11px;
    padding: 6px 9px;
    width: 100%; box-sizing: border-box;
    margin-top: 2px;
    transition: border-color 0.15s, color 0.15s;
  }
  .inline-override-input:focus {
    outline: none; border-color: var(--accent); color: var(--text);
  }
  .inline-override-input::placeholder { color: var(--muted); }

  /* Books grid inside results */
  .role-books-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 6px;
    margin-bottom: 4px;
  }
  .role-book-card {
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: 4px;
    padding: 7px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 10px;
  }
  .role-book-thumb {
    width: 100%; aspect-ratio: 2/3;
    object-fit: cover; border-radius: 2px;
    margin-bottom: 5px;
  }
  .role-book-title { color: var(--text); font-size: 10px; line-height: 1.3; margin-bottom: 2px; }
  ```

- [ ] **Step 3: Verify — open `index.html` in browser**

  Open the file directly in a browser (File → Open). The page should load without errors. The Add Person panel styles aren't visible yet (no HTML change yet) — just confirm no CSS parse errors in the console.

- [ ] **Step 4: Commit**

  ```bash
  cd "/Users/esen/Documents/Cem Code/Pulse"
  git add index.html
  git commit -m "style(add-person): add role chip and results panel CSS"
  ```

---

## Task 2: HTML — Replace the Add Person panel markup

**Files:**
- Modify: `index.html` lines 1012–1103 (the entire `<div class="add-panel" id="addPanel">` block)

- [ ] **Step 1: Locate the block to replace**

  The block starts at:
  ```html
  <div class="add-panel" id="addPanel">
    <h3 id="addPanelTitle">+ Track a New Person</h3>
  ```
  And ends at (inclusive):
  ```html
    <div class="form-actions">
      <button class="btn btn-ghost" onclick="toggleAddPanel()">Cancel</button>
      <button class="btn btn-primary" onclick="addPerson()">Add Person</button>
    </div>
  </div>
  ```

- [ ] **Step 2: Replace the entire block with**

  ```html
  <div class="add-panel" id="addPanel">
    <h3 id="addPanelTitle">+ Track a New Person</h3>

    <!-- Person / Source toggle -->
    <div class="type-toggle">
      <button class="type-btn active" id="typePersonBtn" onclick="setAddType('person')">👤 Person</button>
      <button class="type-btn"        id="typeSourceBtn" onclick="setAddType('source')">📰 Publication / Source</button>
    </div>

    <!-- Name + Search -->
    <div class="form-row" style="margin-bottom:12px">
      <label id="f-name-label">Name *</label>
      <div class="search-name-row">
        <input type="text" id="f-name" placeholder="e.g. Tim Ferriss"
               oninput="_updateSearchBtn()"
               onkeydown="if(event.key==='Enter')searchPersonByName()">
        <button class="btn-search" id="searchBtn" onclick="searchPersonByName()" disabled>🔍 Search</button>
      </div>
    </div>

    <!-- Role checkboxes — PERSON mode only -->
    <div id="rolePickerWrap">
      <div class="form-row" style="margin-bottom:8px">
        <label>What do they do? <span style="color:var(--border)">(pick at least one)</span></label>
        <div class="role-chip-grid">
          <button class="role-chip" id="role-podcaster" onclick="toggleRole('podcaster')">
            <span class="role-dot"></span><span style="color:var(--podcast)">🎙 Podcaster</span>
          </button>
          <button class="role-chip" id="role-youtuber" onclick="toggleRole('youtuber')">
            <span class="role-dot"></span><span style="color:var(--youtube)">▶ YouTuber</span>
          </button>
          <button class="role-chip" id="role-blogger" onclick="toggleRole('blogger')">
            <span class="role-dot"></span><span style="color:var(--blog)">✍ Blogger</span>
          </button>
          <button class="role-chip" id="role-writer" onclick="toggleRole('writer')">
            <span class="role-dot"></span><span style="color:#c084fc">📚 Writer</span>
          </button>
        </div>
      </div>
      <div class="twitter-hint">💡 X / Twitter: add via ✎ edit after the person is created</div>
    </div>

    <!-- Dynamic results (role search results + inline overrides) — PERSON mode -->
    <div id="roleResultsArea"></div>

    <!-- Suggestion area — SOURCE mode only -->
    <div id="suggestArea"></div>

    <!-- Feed inputs — SOURCE mode only (hidden in person mode) -->
    <div id="feedInputsSection" style="display:none">
      <div class="feed-section-title">Feed URLs — paste any you have (leave blank to skip)</div>
      <div class="feed-inputs">
        <div class="feed-row">
          <div class="platform-badge" style="background:#2a1a10; font-size:16px;" id="f-podcast-icon">🎙</div>
          <div class="form-row" style="flex:1">
            <label id="f-podcast-label">Podcast RSS</label>
            <input type="text" id="f-podcast" placeholder="https://feeds.example.com/...">
          </div>
        </div>
        <div class="feed-row">
          <div class="platform-badge" style="background:#1a0f0f; font-size:16px;">▶️</div>
          <div class="form-row" style="flex:1">
            <label>YouTube Channel ID, @handle, or URL</label>
            <input type="text" id="f-youtube" placeholder="UCxxxxxxx  or  @handle  or  youtube.com/@…">
          </div>
        </div>
        <div class="feed-row">
          <div class="platform-badge" style="background:#0f1e2a; font-size:16px;">𝕏</div>
          <div class="form-row" style="flex:1">
            <label>X / Twitter RSS (via rss.app or Nitter)</label>
            <input type="text" id="f-twitter" placeholder="https://rss.app/feeds/…  or  @username">
          </div>
        </div>
        <div class="feed-row">
          <div class="platform-badge" style="background:#162010; font-size:16px;">✍️</div>
          <div class="form-row" style="flex:1">
            <label>Blog / Substack RSS</label>
            <input type="text" id="f-blog" placeholder="https://example.substack.com/feed">
          </div>
        </div>
        <div class="feed-row">
          <div class="platform-badge" style="background:#1a1030; font-size:16px;">📚</div>
          <div class="form-row" style="flex:1">
            <label>Books search query</label>
            <input type="text" id="f-books" placeholder="e.g. Tim Ferriss  or  leave blank for auto">
          </div>
        </div>
      </div>
    </div>

    <!-- Optional details (both modes) -->
    <div class="form-grid" style="margin-top:12px">
      <div class="form-row">
        <label>Description</label>
        <input type="text" id="f-desc" placeholder="e.g. Author, investor…">
      </div>
      <div class="form-row">
        <label>Avatar URL (optional)</label>
        <input type="text" id="f-avatar" placeholder="https://…">
      </div>
    </div>

    <!-- Tags (both modes) -->
    <div class="form-row" style="margin-bottom:12px">
      <label>Topics / Tags <span style="color:var(--muted);font-weight:400">(Enter or comma to add)</span></label>
      <div class="tag-input-wrap" id="tagInputWrap" onclick="document.getElementById('f-tag-input').focus()">
        <div id="tagChipsContainer" style="display:contents"></div>
        <input id="f-tag-input" type="text" placeholder="e.g. consciousness, biology…"
               onkeydown="handleTagKeydown(event)">
      </div>
    </div>

    <div class="form-actions">
      <button class="btn btn-ghost" onclick="toggleAddPanel()">Cancel</button>
      <button class="btn btn-primary" id="addPersonBtn" onclick="addPerson()">Add Person</button>
    </div>
  </div>
  ```

- [ ] **Step 3: Verify — open in browser**

  Open `index.html`. Click the **+ Add** button (or however the panel is opened). You should see:
  - Name field + disabled Search button
  - Four role chip buttons (unchecked)
  - Twitter hint text
  - Description, Avatar, Topics fields
  - Cancel + Add Person buttons
  - No feed URL inputs visible

- [ ] **Step 4: Commit**

  ```bash
  cd "/Users/esen/Documents/Cem Code/Pulse"
  git add index.html
  git commit -m "feat(add-person): replace feed inputs with role chip panel HTML"
  ```

---

## Task 3: JS — New state variables + `toggleRole()` + `_updateSearchBtn()`

**Files:**
- Modify: `index.html` JS section — find `let _suggestions = [];` (~line 2284) and the `toggleAddPanel()` function (~line 2255)

- [ ] **Step 1: Add state variables next to `_suggestions`**

  Find:
  ```js
  // ── AUTO-DISCOVER BY NAME ──
  let _suggestions = [];
  ```

  Replace with:
  ```js
  // ── AUTO-DISCOVER BY NAME ──
  let _suggestions  = [];
  let _formRoles    = new Set();   // which role chips are checked
  let _roleResults  = {};          // { podcaster: [...], youtuber: [...], writer: [...] }
  let _roleSelections = {};        // { podcaster: 0, youtuber: 0, writer: 'query-string' }
  ```

- [ ] **Step 2: Add `toggleRole()` and `_updateSearchBtn()` functions**

  Find the comment `// ── helpers ──` (a few lines after `let _suggestions`) and insert the two functions immediately after it:

  ```js
  function toggleRole(role) {
    if (_formRoles.has(role)) {
      _formRoles.delete(role);
    } else {
      _formRoles.add(role);
    }
    const chip = document.getElementById('role-' + role);
    if (chip) chip.classList.toggle('checked', _formRoles.has(role));
    _updateSearchBtn();
  }

  function _updateSearchBtn() {
    const name = (document.getElementById('f-name')?.value || '').trim();
    const btn  = document.getElementById('searchBtn');
    if (!btn) return;
    if (_addType === 'source') {
      btn.disabled = !name;
    } else {
      btn.disabled = !name || _formRoles.size === 0;
    }
  }
  ```

- [ ] **Step 3: Update `toggleAddPanel()` to clear role state on open**

  Find:
  ```js
  function toggleAddPanel() {
    const panel = document.getElementById('addPanel');
    panel.classList.toggle('open');
    if (panel.classList.contains('open')) {
      document.getElementById('suggestArea').innerHTML = '';
      _suggestions = [];
      _formTags = []; renderFormTagChips();
      setAddType('person'); // always reset to person mode
      document.getElementById('f-name').focus();
    }
  }
  ```

  Replace with:
  ```js
  function toggleAddPanel() {
    const panel = document.getElementById('addPanel');
    panel.classList.toggle('open');
    if (panel.classList.contains('open')) {
      document.getElementById('suggestArea').innerHTML  = '';
      document.getElementById('roleResultsArea').innerHTML = '';
      _suggestions    = [];
      _formRoles      = new Set();
      _roleResults    = {};
      _roleSelections = {};
      // Reset role chip visual state
      ['podcaster','youtuber','blogger','writer'].forEach(r => {
        document.getElementById('role-' + r)?.classList.remove('checked');
      });
      _formTags = []; renderFormTagChips();
      // Reset Add button label
      const addBtn = document.getElementById('addPersonBtn');
      if (addBtn) addBtn.textContent = 'Add Person';
      setAddType('person');
      document.getElementById('f-name').focus();
    }
  }
  ```

- [ ] **Step 4: Verify in browser**

  Open the Add Person panel. Click a role chip — it should gain a gold border and a filled dot. Click again — it should uncheck. The Search button should only become active (gold) when a name is typed AND at least one role is checked.

- [ ] **Step 5: Commit**

  ```bash
  cd "/Users/esen/Documents/Cem Code/Pulse"
  git add index.html
  git commit -m "feat(add-person): add role state, toggleRole(), _updateSearchBtn()"
  ```

---

## Task 4: JS — Update `setAddType()` for person/source mode toggle

**Files:**
- Modify: `index.html` — `setAddType()` function (~line 2267)

- [ ] **Step 1: Replace `setAddType()`**

  Find:
  ```js
  function setAddType(type) {
    _addType = type;
    document.getElementById('typePersonBtn').classList.toggle('active', type === 'person');
    document.getElementById('typeSourceBtn').classList.toggle('active', type === 'source');

    const isSource = type === 'source';
    document.getElementById('addPanelTitle').textContent   = isSource ? '+ Track a Publication or Source' : '+ Track a New Person';
    document.getElementById('f-name-label').textContent    = isSource ? 'Source Name *' : 'Name *';
    document.getElementById('f-name').placeholder          = isSource ? 'e.g. Big Think, Quanta Magazine, Aeon' : 'e.g. Michael Pollan — press Search to auto-fill';
    document.getElementById('f-podcast-label').textContent = isSource ? 'Main RSS Feed' : 'Podcast RSS';
    document.getElementById('f-podcast-icon').textContent  = isSource ? '📰' : '🎙';
    // Clear suggestions when switching type
    document.getElementById('suggestArea').innerHTML = '';
    _suggestions = [];
  }
  ```

  Replace with:
  ```js
  function setAddType(type) {
    _addType = type;
    document.getElementById('typePersonBtn').classList.toggle('active', type === 'person');
    document.getElementById('typeSourceBtn').classList.toggle('active', type === 'source');

    const isSource = type === 'source';
    document.getElementById('addPanelTitle').textContent = isSource ? '+ Track a Publication or Source' : '+ Track a New Person';
    document.getElementById('f-name-label').textContent  = isSource ? 'Source Name *' : 'Name *';
    document.getElementById('f-name').placeholder        = isSource
      ? 'e.g. Big Think, Quanta Magazine, Aeon'
      : 'e.g. Tim Ferriss';

    // Show/hide role picker vs feed inputs
    const roleWrap   = document.getElementById('rolePickerWrap');
    const feedInputs = document.getElementById('feedInputsSection');
    if (roleWrap)   roleWrap.style.display   = isSource ? 'none' : '';
    if (feedInputs) feedInputs.style.display = isSource ? ''     : 'none';

    // Source mode labels on the feed section
    if (isSource) {
      const pl = document.getElementById('f-podcast-label');
      const pi = document.getElementById('f-podcast-icon');
      if (pl) pl.textContent = 'Main RSS Feed';
      if (pi) pi.textContent = '📰';
    }

    // Clear results areas when switching
    document.getElementById('suggestArea').innerHTML     = '';
    document.getElementById('roleResultsArea').innerHTML = '';
    _suggestions    = [];
    _roleResults    = {};
    _roleSelections = {};

    _updateSearchBtn();
  }
  ```

- [ ] **Step 2: Verify in browser**

  Open Add Person panel. It should default to Person mode (role chips visible, feed inputs hidden). Click "Publication / Source" tab — feed URL inputs should appear, role chips should disappear. Switch back — roles visible again. Search button enables/disables correctly in both modes.

- [ ] **Step 3: Commit**

  ```bash
  cd "/Users/esen/Documents/Cem Code/Pulse"
  git add index.html
  git commit -m "feat(add-person): update setAddType() to show/hide role vs feed sections"
  ```

---

## Task 5: JS — Rewrite `searchPersonByName()` with role-aware parallel search

**Files:**
- Modify: `index.html` — `searchPersonByName()` function (~line 2490)

- [ ] **Step 1: Replace the entire `searchPersonByName()` function**

  Find the function starting with:
  ```js
  async function searchPersonByName() {
    const query = document.getElementById('f-name').value.trim();
    if (!query) { document.getElementById('f-name').focus(); return; }

    const btn  = document.getElementById('searchBtn');
    const area = document.getElementById('suggestArea');
    btn.disabled = true; btn.textContent = 'Searching…';
    _suggestions = [];

    // ── SOURCE mode: skip iTunes, use RSS autodiscovery + YouTube search ──
    if (_addType === 'source') {
  ```

  Replace the **entire function** (from `async function searchPersonByName()` up to and including its closing `}`) with:

  ```js
  async function searchPersonByName() {
    const query = document.getElementById('f-name').value.trim();
    if (!query) { document.getElementById('f-name').focus(); return; }

    const btn = document.getElementById('searchBtn');
    btn.disabled = true; btn.textContent = 'Searching…';

    // ── SOURCE mode: unchanged behavior ──
    if (_addType === 'source') {
      const area = document.getElementById('suggestArea');
      _suggestions = [];
      area.innerHTML = '<div class="suggest-status">Searching YouTube channel and RSS feed…</div>';
      const [ytId, rssUrl] = await Promise.all([
        _findYouTube(query, ''),
        _findSourceRSS(query),
      ]);
      btn.disabled = false; btn.textContent = '🔍 Search';
      if (ytId)   document.getElementById('f-youtube').value = ytId;
      if (rssUrl) document.getElementById('f-podcast').value = rssUrl;
      const found = [ytId ? 'YouTube' : '', rssUrl ? 'RSS feed' : ''].filter(Boolean);
      if (found.length) {
        area.innerHTML = `<div class="suggest-status" style="text-align:left">
          ✓ Auto-filled: ${found.join(' + ')} — review and adjust below.</div>`;
      } else {
        area.innerHTML = `<div class="suggest-status">No feeds found automatically — paste the RSS URL and YouTube channel below.</div>`;
      }
      return;
    }

    // ── PERSON mode: role-based parallel search ──
    _roleResults    = {};
    _roleSelections = {};
    const resultsArea = document.getElementById('roleResultsArea');
    resultsArea.innerHTML = '<div class="suggest-status">Searching…</div>';

    // Build role-scoped API calls
    const tasks = [];

    if (_formRoles.has('podcaster')) {
      tasks.push((async () => {
        const applePodcastIdMatch = query.match(/[?&/]id(\d{7,12})(?:[/?&]|$)/i)
          || query.match(/podcasts\.apple\.com.*\/id(\d{7,12})/i);
        const data = await (applePodcastIdMatch
          ? fetch(
              `https://itunes.apple.com/lookup?id=${applePodcastIdMatch[1]}&entity=podcast`,
              { signal: AbortSignal.timeout(8000) }
            ).then(r => r.json()).catch(() => ({ results: [] }))
          : fetch(
              `https://itunes.apple.com/search?term=${encodeURIComponent(query)}&media=podcast&entity=podcast&limit=4`,
              { signal: AbortSignal.timeout(8000) }
            ).then(r => r.json()).catch(() => ({ results: [] }))
        );
        _roleResults.podcaster = (data.results || [])
          .filter(r => r.feedUrl)
          .slice(0, 3)
          .map(r => ({
            label:      r.collectionName || r.artistName || query,
            sub:        `${r.trackCount || '?'} episodes · iTunes`,
            podcastUrl: r.feedUrl,
            itunesId:   r.collectionId || null,
            avatar:     (r.artworkUrl600 || r.artworkUrl100 || '').replace('100x100bb', '600x600bb'),
          }));
      })());
    }

    if (_formRoles.has('youtuber')) {
      tasks.push((async () => {
        const ytId = await _findYouTube(query, '');
        _roleResults.youtuber = ytId
          ? [{ label: query, sub: ytId, youtubeId: ytId }]
          : [];
      })());
    }

    if (_formRoles.has('writer')) {
      tasks.push((async () => {
        const books = await fetchBooks(query, '__preview__');
        _roleResults.writer = books.slice(0, 6).map(b => ({
          label:     b.title,
          sub:       b.date ? (new Date(b.date).getFullYear() || '') : '',
          booksQuery: query,
          link:      b.link,
          thumbnail: b.thumbnail,
        }));
      })());
    }

    // Blogger has no auto-search — paste field is shown immediately
    if (_formRoles.has('blogger')) {
      _roleResults.blogger = [];
    }

    await Promise.allSettled(tasks);

    btn.disabled = false; btn.textContent = '🔍 Search';
    renderRoleResults(query);
  }
  ```

- [ ] **Step 2: Verify — test Podcaster search**

  Open Add Person panel. Check Podcaster. Type "Tim Ferriss". Hit Search. Console should show no errors. `_roleResults.podcaster` should contain up to 3 iTunes results (check in DevTools: `_roleResults`).

- [ ] **Step 3: Commit**

  ```bash
  cd "/Users/esen/Documents/Cem Code/Pulse"
  git add index.html
  git commit -m "feat(add-person): rewrite searchPersonByName() with role-scoped parallel search"
  ```

---

## Task 6: JS — Add `renderRoleResults()` and `selectRoleResult()`

**Files:**
- Modify: `index.html` — insert new functions immediately after `searchPersonByName()`

- [ ] **Step 1: Find the insertion point**

  Find the line immediately after the closing `}` of `searchPersonByName()`. The next function should be `applySuggestion()`. Insert the new functions between `searchPersonByName` and `applySuggestion`.

- [ ] **Step 2: Insert `renderRoleResults()` and `selectRoleResult()`**

  ```js
  function renderRoleResults(query) {
    const resultsArea = document.getElementById('roleResultsArea');
    const roles = ['podcaster', 'youtuber', 'blogger', 'writer'].filter(r => _formRoles.has(r));
    let sectionsHtml = '';

    // Podcast
    if (_formRoles.has('podcaster')) {
      const results = _roleResults.podcaster || [];
      if (results.length > 0) _roleSelections.podcaster = 0;
      sectionsHtml += `<div class="role-result-section">
        <div class="role-result-header podcast-color">🎙 Podcast</div>`;
      if (results.length === 0) {
        sectionsHtml += `<div class="role-no-results">Nothing found on iTunes</div>`;
      } else {
        results.forEach((r, i) => {
          sectionsHtml += `<div class="role-result-row${i === 0 ? ' selected' : ''}"
              onclick="selectRoleResult('podcaster', ${i})">
            <span class="role-result-dot"></span>
            <span class="role-result-title">${escHtml(r.label)}<br>
              <span class="role-result-sub">${escHtml(r.sub)}</span>
            </span>
          </div>`;
        });
      }
      sectionsHtml += `<input class="inline-override-input" id="override-podcast"
          placeholder="↳ or paste RSS URL directly…">
      </div>`;
    }

    // YouTube
    if (_formRoles.has('youtuber')) {
      const results = _roleResults.youtuber || [];
      if (results.length > 0) _roleSelections.youtuber = 0;
      sectionsHtml += `<div class="role-result-section">
        <div class="role-result-header youtube-color">▶ YouTube</div>`;
      if (results.length === 0) {
        sectionsHtml += `<div class="role-no-results">Channel not found automatically</div>`;
      } else {
        results.forEach((r, i) => {
          sectionsHtml += `<div class="role-result-row${i === 0 ? ' selected' : ''}"
              onclick="selectRoleResult('youtuber', ${i})">
            <span class="role-result-dot"></span>
            <span class="role-result-title">${escHtml(r.label)}<br>
              <span class="role-result-sub">${escHtml(r.sub)}</span>
            </span>
          </div>`;
        });
      }
      sectionsHtml += `<input class="inline-override-input" id="override-youtube"
          placeholder="↳ or paste channel ID / @handle / URL…">
      </div>`;
    }

    // Blogger (no auto-search — paste field only)
    if (_formRoles.has('blogger')) {
      sectionsHtml += `<div class="role-result-section">
        <div class="role-result-header blog-color">✍ Blog</div>
        <input class="inline-override-input" id="override-blog"
            placeholder="↳ paste blog / Substack RSS URL…">
      </div>`;
    }

    // Writer (books grid)
    if (_formRoles.has('writer')) {
      const results = _roleResults.writer || [];
      if (results.length > 0) _roleSelections.writer = query;
      sectionsHtml += `<div class="role-result-section" style="grid-column:1/-1">
        <div class="role-result-header books-color">📚 Books (Open Library)</div>`;
      if (results.length === 0) {
        sectionsHtml += `<div class="role-no-results">No books found — try a different spelling</div>`;
      } else {
        sectionsHtml += `<div class="role-books-grid">`;
        results.forEach(r => {
          sectionsHtml += `<div class="role-book-card">
            ${r.thumbnail
              ? `<img src="${escHtml(r.thumbnail)}" class="role-book-thumb"
                   onerror="this.style.display='none'">`
              : ''}
            <div class="role-book-title">${escHtml(r.label)}</div>
            <div class="role-result-sub">${r.sub || ''}</div>
          </div>`;
        });
        sectionsHtml += `</div>`;
      }
      sectionsHtml += `<input class="inline-override-input" id="override-books"
          placeholder="↳ or paste Open Library / Goodreads author URL…">
      </div>`;
    }

    resultsArea.innerHTML = sectionsHtml
      ? `<div class="role-results-grid">${sectionsHtml}</div>`
      : '';

    // Update Add button label dynamically
    const name   = document.getElementById('f-name').value.trim();
    const addBtn = document.getElementById('addPersonBtn');
    if (addBtn && name) addBtn.textContent = `✓ Add ${name}`;
  }

  function selectRoleResult(role, idx) {
    _roleSelections[role] = idx;
    // Update visual selection within this role's section
    // Each .role-result-row has an onclick with the role name — find all rows for this role
    const allRows = document.querySelectorAll(`#roleResultsArea .role-result-row`);
    let roleIdx = 0;
    allRows.forEach(row => {
      if (row.getAttribute('onclick')?.includes(`'${role}'`)) {
        row.classList.toggle('selected', roleIdx === idx);
        roleIdx++;
      }
    });
  }
  ```

- [ ] **Step 3: Verify in browser**

  Check Podcaster + YouTuber. Type "Lex Fridman". Hit Search. After a few seconds you should see:
  - Two-column layout: Podcast results on the left, YouTube on the right
  - First podcast result auto-selected (gold border)
  - Inline "or paste RSS URL" input below podcast results
  - Clicking a different podcast result switches the selection (gold dot moves)
  - Add button label changes to "✓ Add Lex Fridman"

- [ ] **Step 4: Commit**

  ```bash
  cd "/Users/esen/Documents/Cem Code/Pulse"
  git add index.html
  git commit -m "feat(add-person): add renderRoleResults() and selectRoleResult()"
  ```

---

## Task 7: JS — Update `addPerson()` to read from role selections

**Files:**
- Modify: `index.html` — `addPerson()` function (~line 2641)

- [ ] **Step 1: Find the current `addPerson()` function**

  It starts with:
  ```js
  async function addPerson() {
    const name = document.getElementById('f-name').value.trim();
    if (!name) { alert('Name is required'); return; }

    // Resolve YouTube input (handle, URL, or raw ID) → bare channel ID
    const ytRaw = document.getElementById('f-youtube').value.trim();
  ```

- [ ] **Step 2: Replace the feed-reading portion**

  Find this block inside `addPerson()`:
  ```js
    // Resolve YouTube input (handle, URL, or raw ID) → bare channel ID
    const ytRaw = document.getElementById('f-youtube').value.trim();
    const addBtn = document.querySelector('.btn-primary[onclick="addPerson()"]');
    let ytId = '';
    if (ytRaw) {
      if (addBtn) { addBtn.textContent = 'Resolving…'; addBtn.disabled = true; }
      ytId = await resolveYouTubeChannelId(ytRaw);
      if (addBtn) { addBtn.textContent = 'Add Person'; addBtn.disabled = false; }
    }

    // Pick itunesId from whichever suggestion was applied (matched by podcast URL)
    const podcastUrl = document.getElementById('f-podcast').value.trim();
    const matchedSug = _suggestions.find(s => s.podcastUrl && s.podcastUrl === podcastUrl);

    // Auto-derive website from podcast RSS URL if not filled in
    const websiteInput = document.getElementById('f-website').value.trim();
    const derivedWebsite = websiteInput || (() => {
      try { const u = new URL(podcastUrl); return u.origin; } catch(_) { return ''; }
    })();
  ```

  Replace with:
  ```js
    // Helper: read an inline override input (may not exist in DOM if role not checked)
    const getOverride = id => (document.getElementById(id)?.value || '').trim();
    const addBtn = document.getElementById('addPersonBtn');

    let podcastUrl  = '';
    let ytId        = '';
    let blogUrl     = '';
    let booksQuery  = '';
    let itunesId    = null;

    if (_addType === 'person') {
      // ── PERSON mode: read from role selections + inline overrides ──

      // Podcast
      const overridePodcast = getOverride('override-podcast');
      const selPodcast = (_roleResults.podcaster || [])[_roleSelections.podcaster ?? -1];
      podcastUrl = overridePodcast || selPodcast?.podcastUrl || '';
      itunesId   = selPodcast?.itunesId || null;

      // YouTube — override may be a handle/URL, needs resolution
      const overrideYoutube = getOverride('override-youtube');
      const selYt = (_roleResults.youtuber || [])[_roleSelections.youtuber ?? -1];
      if (overrideYoutube) {
        if (addBtn) { addBtn.textContent = 'Resolving…'; addBtn.disabled = true; }
        ytId = await resolveYouTubeChannelId(overrideYoutube);
        if (addBtn) { addBtn.textContent = `✓ Add ${name}`; addBtn.disabled = false; }
      } else {
        ytId = selYt?.youtubeId || '';
      }

      // Blog
      blogUrl = getOverride('override-blog');

      // Books: override URL wins, else use stored query
      booksQuery = getOverride('override-books') || _roleSelections.writer || name;

    } else {
      // ── SOURCE mode: read from visible feed input fields (unchanged) ──
      const ytRaw     = document.getElementById('f-youtube').value.trim();
      podcastUrl      = document.getElementById('f-podcast').value.trim();
      blogUrl         = document.getElementById('f-blog').value.trim();
      booksQuery      = document.getElementById('f-books')?.value.trim() || '';
      const matchedSug = _suggestions.find(s => s.podcastUrl && s.podcastUrl === podcastUrl);
      itunesId        = matchedSug?.itunesId || null;
      if (ytRaw) {
        if (addBtn) { addBtn.textContent = 'Resolving…'; addBtn.disabled = true; }
        ytId = await resolveYouTubeChannelId(ytRaw);
        if (addBtn) { addBtn.textContent = 'Add Person'; addBtn.disabled = false; }
      }
    }

    // Auto-derive website from podcast RSS URL if not filled in
    const websiteInput = document.getElementById('f-website')?.value.trim() || '';
    const derivedWebsite = websiteInput || (() => {
      try { const u = new URL(podcastUrl); return u.origin; } catch(_) { return ''; }
    })();
  ```

- [ ] **Step 3: Update the `person` object construction in `addPerson()`**

  Find:
  ```js
    const person = {
      id:   name.toLowerCase().replace(/\s+/g, '-') + '-' + Date.now(),
      name,
      type:    _addType,   // 'person' | 'source'
      desc:    document.getElementById('f-desc').value.trim(),
      website: derivedWebsite,
      avatar:  document.getElementById('f-avatar').value.trim(),
      feeds: {
        podcast: podcastUrl,
        youtube: ytId,
        twitter: document.getElementById('f-twitter').value.trim(),
        blog:    document.getElementById('f-blog').value.trim(),
        books:   document.getElementById('f-books')?.value.trim() || '',
      },
      itunesId: matchedSug?.itunesId || null,
      entries: [], lastUpdated: null, loading: false,
      tags: [..._formTags],
    };
  ```

  Replace with:
  ```js
    const person = {
      id:   name.toLowerCase().replace(/\s+/g, '-') + '-' + Date.now(),
      name,
      type:    _addType,
      desc:    document.getElementById('f-desc').value.trim(),
      website: derivedWebsite,
      avatar:  document.getElementById('f-avatar').value.trim(),
      feeds: {
        podcast: podcastUrl,
        youtube: ytId,
        twitter: _addType === 'source' ? (document.getElementById('f-twitter')?.value.trim() || '') : '',
        blog:    blogUrl,
        books:   booksQuery,
      },
      itunesId: itunesId,
      roles:   _addType === 'person' ? [..._formRoles] : [],
      entries: [], lastUpdated: null, loading: false,
      tags: [..._formTags],
    };
  ```

- [ ] **Step 4: Update the cleanup section at the bottom of `addPerson()`**

  Find:
  ```js
    ['f-name','f-desc','f-website','f-avatar','f-podcast','f-youtube','f-twitter','f-blog','f-books'].forEach(id => {
      document.getElementById(id).value = '';
    });
    document.getElementById('suggestArea').innerHTML = '';
    _suggestions = [];
  ```

  Replace with:
  ```js
    ['f-name','f-desc','f-website','f-avatar','f-podcast','f-youtube','f-twitter','f-blog','f-books'].forEach(id => {
      const el = document.getElementById(id);
      if (el) el.value = '';
    });
    document.getElementById('suggestArea').innerHTML     = '';
    document.getElementById('roleResultsArea').innerHTML = '';
    _suggestions    = [];
    _formRoles      = new Set();
    _roleResults    = {};
    _roleSelections = {};
    ['podcaster','youtuber','blogger','writer'].forEach(r => {
      document.getElementById('role-' + r)?.classList.remove('checked');
    });
    const addBtn2 = document.getElementById('addPersonBtn');
    if (addBtn2) addBtn2.textContent = 'Add Person';
  ```

- [ ] **Step 5: Full end-to-end test**

  1. Open `index.html` in browser
  2. Open Add Person panel
  3. Type "Tim Ferriss"
  4. Check **Podcaster** + **YouTuber** + **Writer**
  5. Click Search — wait for results
  6. Verify: podcast results shown, YouTube channel shown, book grid shown
  7. Click "✓ Add Tim Ferriss"
  8. Verify: person card appears in the grid with name "Tim Ferriss"
  9. Open person card — click ↻ Refresh
  10. Verify: podcast entries load (if iTunes found a feed)
  11. Open Add Person again → check Blogger only → type "Wait But Why" → Search
  12. Verify: only a Blog paste field shown (no other sections)
  13. Paste `https://waitbutwhy.com/feed` in the blog override field
  14. Click Add → card should appear with blog feed populated

- [ ] **Step 6: Test Source mode is unaffected**

  1. Open Add Person panel
  2. Click "Publication / Source" tab
  3. Verify: feed URL inputs appear, role chips hidden
  4. Type "Aeon" → Search → verify YouTube + RSS auto-fill works as before

- [ ] **Step 7: Commit**

  ```bash
  cd "/Users/esen/Documents/Cem Code/Pulse"
  git add index.html
  git commit -m "feat(add-person): update addPerson() to read from role selections"
  ```

---

## Task 8: Final polish + regression check

**Files:**
- Modify: `index.html` (minor CSS fix + name input placeholder)

- [ ] **Step 1: Check responsive layout of results grid**

  Open `index.html`. Narrow the browser window to ~600px. The `.role-results-grid` is currently `grid-template-columns: 1fr 1fr`. Add a responsive fallback:

  Find the CSS rule:
  ```css
  .role-results-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 14px;
    margin: 14px 0 6px;
  }
  ```

  After it (still inside `<style>`), add:
  ```css
  @media (max-width: 560px) {
    .role-results-grid { grid-template-columns: 1fr; }
    .role-books-grid   { grid-template-columns: repeat(2, 1fr); }
  }
  ```

- [ ] **Step 2: Verify existing demo persons still load**

  Reload the page. The demo persons (Joe Rogan, Lex Fridman, etc.) should be visible and their ↻ refresh buttons should still work. No JavaScript errors in the console.

- [ ] **Step 3: Verify tag filtering is unaffected**

  If any persons have tags, verify that the TOPICS bar still appears and filtering still works.

- [ ] **Step 4: Verify the detail/edit modal still works**

  Click any person card entry to open the detail modal. Click ✎ Edit. Verify the edit form opens correctly (it has separate feed URL inputs — those are unaffected by this change).

- [ ] **Step 5: Final commit**

  ```bash
  cd "/Users/esen/Documents/Cem Code/Pulse"
  git add index.html
  git commit -m "feat(add-person): responsive layout + regression verification complete"
  ```

---

## Self-review checklist

### Spec coverage

| Spec requirement | Covered by task |
|---|---|
| Name + role chips on same screen | Task 2 |
| Search disabled until name + at least one role | Task 3 (`_updateSearchBtn`) |
| All roles unchecked by default | Task 2 (no `checked` class in HTML) + Task 3 (`_formRoles = new Set()`) |
| Parallel API calls per role | Task 5 (`Promise.allSettled(tasks)`) |
| Auto-select top result per role | Task 6 (`_roleSelections.role = 0` for first result) |
| Click to switch result selection | Task 6 (`selectRoleResult()`) + Task 2 (`onclick`) |
| Inline paste override per role | Task 6 (`<input class="inline-override-input" id="override-*">`) |
| Override wins over selected result | Task 7 (`overridePodcast || selPodcast?.podcastUrl`) |
| Blogger = paste field only | Task 5 (no API call) + Task 6 (renders paste field immediately) |
| Writer = Open Library search + optional URL override | Task 5 (`fetchBooks()`) + Task 6 + Task 7 |
| X/Twitter not in role flow | Confirmed — no twitter role chip; field stays in source/edit |
| `_findBlog()` no longer called | Task 5 (removed from person mode search) |
| `resolveYouTubeChannelId` called only for manual override | Task 7 (branched on `overrideYoutube`) |
| `itunesId` captured from selected result | Task 7 (`selPodcast?.itunesId`) |
| Add Source flow unaffected | Task 5 (source branch preserved) + Task 4 (`setAddType`) |
| Demo persons still load | Task 8 step 2 |
| `person` object shape unchanged | Task 7 (same fields + optional `roles` array) |
| Responsive layout | Task 8 step 1 |

### Placeholder scan
No TBD, TODO, or "similar to Task N" phrases. All code steps contain complete code.

### Type consistency
- `_roleResults.podcaster[n].podcastUrl` — defined in Task 5, read in Task 7 ✓
- `_roleResults.youtuber[n].youtubeId` — defined in Task 5, read in Task 7 ✓
- `_roleResults.writer[n].label/thumbnail/sub` — defined in Task 5, rendered in Task 6 ✓
- `_roleSelections.podcaster` — set as `0` in Task 6, read as index in Task 7 ✓
- `_roleSelections.writer` — set as `query` string in Task 6, used as `booksQuery` in Task 7 ✓
- `selectRoleResult(role, idx)` — defined Task 6, called in Task 6 HTML `onclick` ✓
- `toggleRole(role)` — defined Task 3, called in Task 2 HTML `onclick` ✓
- `_updateSearchBtn()` — defined Task 3, called in Task 3 `toggleAddPanel` + Task 4 `setAddType` ✓
- `getOverride(id)` — defined and used within Task 7 `addPerson()` only ✓
- `renderRoleResults(query)` — defined Task 6, called at end of Task 5 ✓
