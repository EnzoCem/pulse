# Pulse V2.0 — Phase 1: Hybrid Backend + NotebookLM Q&A

**Date:** 2026-03-30
**Status:** Approved
**Author:** Cem Ugur

---

## Overview

Phase 1 introduces a minimal Python/Flask backend alongside the existing Pulse V1.0 single-file frontend. The backend's sole purpose in this phase is to proxy NotebookLM queries via the `notebooklm-skill` — enabling the new **"Ask My Sources"** feature in entry modals.

Everything in V1.0 (RSS fetching, AI Notes, Calibre check, Obsidian integration, tag system) continues working unchanged. The backend adds capability without replacing anything.

---

## Goals

1. Add a Python/Flask backend that runs on `localhost:5001`
2. Wire the existing `notebooklm-skill` (already installed and authenticated) to a REST endpoint
3. Add an **"🔍 Ask My Sources"** button to the Pulse entry modal
4. Add a **NotebookLM Library** settings section mapping TOPICS tags to notebook URLs
5. Route queries to the correct notebook based on entry tags, with manual override

---

## Non-Goals (Phase 1)

- SQLite database migration (localStorage stays as-is)
- Auto-refresh / background polling
- Information-centered views (Books page, Podcasts page)
- Spaced repetition / daily review
- Chat with entire library
- Home Assistant integration

---

## Architecture

```
Pulse/
├── index.html              ← V1.0 (modified: new button + settings section)
├── backend/
│   ├── server.py           ← Flask app (new)
│   ├── requirements.txt    ← flask only (new)
│   └── start.sh            ← One-command startup (new)
├── docs/
│   └── superpowers/specs/  ← This file
├── README.md
└── CLAUDE.md
```

**Runtime flow:**
```
User opens Pulse (file:// or http://localhost)
    → Backend health check: GET http://localhost:5001/api/health
    → If online: "🔍 Ask My Sources" button visible in modals
    → If offline: button hidden with tooltip

User clicks "🔍 Ask My Sources" in entry modal
    → POST http://localhost:5001/api/notebooklm/ask
    → Flask calls: python3 scripts/run.py ask_question.py --question "..." --notebook-url "..."
    → NotebookLM opens in background browser, answers from curated sources
    → Cleaned answer returned to frontend, displayed in modal
    → User can save answer as entry note
```

---

## Backend (`backend/server.py`)

### Source

Adapted directly from `/Users/esen/Documents/Cem Code/Brewing App/backend/app.py`.
Reuses: Flask setup, manual CORS pattern, subprocess call, output parsing, citation cleanup, error handling.

### Endpoints

#### `GET /api/health`
```
Response: { "status": "ok", "notebooklm_skill": true|false }
```
Returns 200 if server is running. Also checks if the skill directory exists.
Used by frontend on load to show/hide the Ask My Sources button.

#### `POST /api/notebooklm/ask`
```
Request body:
{
  "question":    string,   // User's typed question (required)
  "notebookUrl": string,   // Resolved notebook URL (required)
  "entryContext": string   // Optional: "Title by Person (platform)" for context prefix
}

Success response:
{ "answer": string }

Error response:
{ "error": string }  — with appropriate HTTP status code
```

**Internal logic:**
1. Validate `question` and `notebookUrl` present
2. Confirm skill directory exists at configured path
3. Optionally prefix question with entry context: `"[Context: {entryContext}]\n\n{question}"`
4. Run subprocess: `python3 scripts/run.py ask_question.py --question "..." --notebook-url "..."`
5. Parse output (split on `"=" * 60` separators, take `parts[2]`)
6. Strip follow-up marker (`"EXTREMELY IMPORTANT:"`)
7. Strip NotebookLM citation numbers (4-pass regex — reused from Brewing App)
8. Return `{ "answer": cleaned_text }`

**Timeout:** 90 seconds (matches Brewing App)

**Error cases:**
- No question → 400
- No notebook URL → 400
- Skill directory not found → 400
- Not authenticated → 401 with re-auth instructions
- Session stale/expired → 401 with re-auth instructions
- Subprocess timeout → 504
- No answer in output → 500 with debug info

### Flask Setup

Reused directly from Brewing App — manual CORS via `@app.after_request` (no `flask-cors` package needed):

```python
@app.after_request
def add_cors_headers(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type,Authorization'
    response.headers['Access-Control-Allow-Methods'] = 'GET,PUT,POST,DELETE,OPTIONS'
    return response

@app.route('/<path:path>', methods=['OPTIONS'])
@app.route('/', methods=['OPTIONS'])
def handle_options(path=''):
    response = make_response()
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type,Authorization'
    response.headers['Access-Control-Allow-Methods'] = 'GET,PUT,POST,DELETE,OPTIONS'
    return response
```

### Configuration

The skill path is set as a constant in `server.py` with an environment variable override:

```python
DEFAULT_SKILL_PATH = os.path.expanduser(
    '~/Documents/Cem Code/PK App/.claude/skills/notebooklm'
)
SKILL_PATH = os.environ.get('NOTEBOOKLM_SKILL_PATH', DEFAULT_SKILL_PATH)
```

No database needed for Phase 1. Notebook URL is passed per-request from the frontend.

### `requirements.txt`
```
flask>=3.0
```
Single dependency. The `re`, `os`, `subprocess` modules are stdlib.

### `start.sh`
```bash
#!/bin/bash
cd "$(dirname "$0")"
python3 -m venv .venv 2>/dev/null || true
source .venv/bin/activate
pip install -q -r requirements.txt
python3 server.py
```

Creates a local venv on first run, installs Flask, starts the server.
**Port:** 5001 (avoids conflict with Brewing App on 5010, Pocket App on 8080).

---

## Frontend Changes (`index.html`)

### 1. Backend Health Check on Load

On `loadState()` / app init, ping the backend:

```javascript
let _backendOnline = false;

async function _checkBackend() {
  try {
    const r = await fetch('http://localhost:5001/api/health', { signal: AbortSignal.timeout(2000) });
    _backendOnline = r.ok;
  } catch { _backendOnline = false; }
}
```

Called once on startup. Result stored in `_backendOnline`. The Ask My Sources button visibility depends on this flag.

### 2. New Button in Entry Modal

Added to the existing modal action buttons row (between obsidianBtn and calibreBtn):

```html
<button id="askSourcesBtn" class="btn btn-ghost" style="display:none" onclick="askMySourcesToggle()">
  🔍 Ask My Sources
</button>
```

**Visibility rules:**
- Hidden if `_backendOnline === false` (with `title="Start the Pulse backend to enable"`)
- Hidden if no notebooks configured in `pw-config.notebookLibrary`
- Shown for all entry types (podcast, YouTube, blog, books) — NotebookLM is topic-agnostic

### 3. Ask My Sources Interaction (in modal)

When button is clicked, an inline question area expands below the modal action buttons:

```
┌─────────────────────────────────────────────────┐
│ Ask your NotebookLM sources:                    │
│ ┌─────────────────────────────────────────────┐ │
│ │ e.g. What do my sources say about NMN?     │ │
│ └─────────────────────────────────────────────┘ │
│ Notebook: [Supplements ▼]        [Ask →]        │
└─────────────────────────────────────────────────┘
```

**Notebook auto-selection logic:**
1. Collect entry's tags: `entryTags[entry.id] || []` plus `person.tags`
2. For each tag, check `pw-config.notebookLibrary[tag]`
3. First match wins → pre-select that notebook in dropdown
4. If no match → dropdown shows all notebooks, user must select
5. Dropdown always shows all notebooks so user can override

**On submit:**
1. Button shows `⏳ Querying… (up to 90s)`
2. `POST http://localhost:5001/api/notebooklm/ask` with question + notebookUrl + entryContext
3. On success: answer displayed in `#ask-sources-area` with notebook name header
4. `[💾 Save as Note]` button appears — appends answer to entry notes (same as AI Notes)
5. On error: error message shown in red
6. Button resets to `🔍 Ask My Sources`

### 4. New Settings Section: NotebookLM Library

Added between the existing "AI Notes — Article & Blog Prompt" and "Calibre Library" sections:

```
── NotebookLM Library ──────────────────────────────
Skill path  [~/Documents/Cem Code/PK App/.claude/skills/notebooklm    ]

Tag → Notebook mapping:
┌────────────────┬──────────────────────────────────┬────┐
│ supplements    │ https://notebooklm.google.com/…  │ ✎× │
│ fermentation   │ https://notebooklm.google.com/…  │ ✎× │
│ brewing        │ https://notebooklm.google.com/…  │ ✎× │
└────────────────┴──────────────────────────────────┴────┘
[+ Add notebook]
```

**Stored in `pw-config`:**
```javascript
pwConfig.notebookLibrary = {
  "supplements": "https://notebooklm.google.com/notebook/abc...",
  "fermentation": "https://notebooklm.google.com/notebook/def...",
  "brewing":      "https://notebooklm.google.com/notebook/4651b63a..."
}
pwConfig.notebookSkillPath = "~/Documents/Cem Code/PK App/.claude/skills/notebooklm"
```

Tags in the library don't need to exist as TOPICS tags — any string key works.

---

## Data Flow (End-to-End)

```
1. User opens Pulse — _checkBackend() runs
   → _backendOnline = true  (if backend is running)

2. User opens Peter Attia podcast entry
   → Entry tags: ["supplements", "health"]  (from entryTags + person.tags)
   → askSourcesBtn shown

3. User clicks "🔍 Ask My Sources"
   → Inline question area expands
   → Auto-selected notebook: "Supplements" (from notebookLibrary["supplements"])
   → Dropdown populated with all configured notebooks

4. User types: "What do my sources say about Metformin?"
   → Clicks "Ask →"

5. Frontend POST to http://localhost:5001/api/notebooklm/ask:
   {
     "question": "What do my sources say about Metformin?",
     "notebookUrl": "https://notebooklm.google.com/notebook/abc...",
     "entryContext": "Peter Attia MD — 'Longevity compounds' (podcast)"
   }

6. Backend:
   → Constructs question: "[Context: Peter Attia MD — 'Longevity compounds' (podcast)]\n\nWhat do my sources say about Metformin?"
   → subprocess.run(['python3', 'scripts/run.py', 'ask_question.py', '--question', '...', '--notebook-url', '...'], timeout=90)
   → Parses output, strips citations
   → Returns { "answer": "Based on your sources, Metformin is..." }

7. Frontend displays answer in #ask-sources-area
   → [💾 Save as Note] button appears

8. User clicks Save as Note
   → Appended to entryNotes[entry.id]
   → saveState() called
   → Notes textarea updated
```

---

## Reused Code Map

| Component | Source | Reuse |
|---|---|---|
| Flask init + CORS | Brewing App `app.py` lines 1-50 | Direct copy, remove unused imports |
| `ask_brewing` endpoint | Brewing App `app.py` lines 3194-3280 | Copy, rename, make notebookUrl a request param |
| Citation cleanup regex | Brewing App `app.py` (4-pass regex) | Direct copy |
| Error message strings | Brewing App `app.py` | Direct copy |
| `subprocess.run` pattern | Brewing App `app.py` | Direct copy |
| Output parser (`SEP = '=' * 60`) | Brewing App `app.py` | Direct copy |
| Health check endpoint | New (trivial) | — |
| Frontend fetch to backend | Existing `callClaude()` pattern | Adapt |
| Modal button row | Existing modal HTML | Add one button |
| Settings panel | Existing settings HTML | Add one section |
| Tag lookup | Existing `entryTags` + `person.tags` | Reuse directly |
| Save as Note | Existing `saveEntryNote()` | Reuse directly |

---

## Testing Checklist

- [ ] `./backend/start.sh` creates venv, installs Flask, starts on port 5001
- [ ] `GET /api/health` returns 200 with `notebooklm_skill: true`
- [ ] App loads: Ask My Sources button visible in modal when backend is online
- [ ] App loads: Ask My Sources button hidden when backend is offline
- [ ] No notebook configured: button disabled with tooltip
- [ ] Correct notebook auto-selected based on entry tags
- [ ] Manual notebook override via dropdown works
- [ ] Question submitted → answer appears within 90s
- [ ] "Save as Note" appends to entry notes and persists
- [ ] Auth error → clear error message shown
- [ ] Timeout → clear error message shown
- [ ] V1.0 features unaffected (RSS, AI Notes, Calibre, Obsidian all work)

---

## Setup Instructions (for README)

```bash
# 1. Start the Pulse backend (one-time setup, then keep running)
cd "/Users/esen/Documents/Cem Code/Pulse/backend"
chmod +x start.sh
./start.sh
# → Running on http://localhost:5001

# 2. Open Pulse as usual
open index.html

# 3. Configure notebooks: ⚙ Settings → NotebookLM Library → Add notebooks

# 4. NotebookLM authentication (if not already done from Brewing App)
cd "/Users/esen/Documents/Cem Code/PK App/.claude/skills/notebooklm"
python3 scripts/run.py auth_manager.py setup
```

The notebooklm-skill is already installed and authenticated from the Brewing App.
No additional setup needed beyond starting the Flask server.
