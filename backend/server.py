"""
Pulse Backend — Phase 1: NotebookLM Q&A proxy
Adapted from Brewing App backend/app.py
"""

import html as _html
import os
import re
import subprocess
from flask import Flask, jsonify, request, make_response
import db as _db
import requests as _requests  # for server-side RSS fetch in episode sync

try:
    from youtube_transcript_api import YouTubeTranscriptApi, NoTranscriptFound, TranscriptsDisabled, VideoUnavailable
    _yt_api = YouTubeTranscriptApi()   # v1.0+ uses instances, not class methods
    YT_TRANSCRIPT_AVAILABLE = True
except ImportError:
    YT_TRANSCRIPT_AVAILABLE = False

# ── Configuration ──────────────────────────────────────────────────────────────
DEFAULT_SKILL_PATH = os.path.expanduser(
    '~/Documents/Cem Code/PK App/.claude/skills/notebooklm'
)
SKILL_PATH = os.environ.get('NOTEBOOKLM_SKILL_PATH', DEFAULT_SKILL_PATH)
PORT = int(os.environ.get('PORT', 5001))

app = Flask(__name__)

# Initialise SQLite DB on startup — safe to call every time (CREATE IF NOT EXISTS)
_db.init_db()

# ── CORS (no flask-cors package needed) ───────────────────────────────────────
@app.after_request
def add_cors_headers(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type,Authorization'
    response.headers['Access-Control-Allow-Methods'] = 'GET,PUT,POST,DELETE,OPTIONS'
    return response

@app.route('/', defaults={'path': ''}, methods=['OPTIONS'])
@app.route('/<path:path>', methods=['OPTIONS'])
def handle_options(path):
    response = make_response()
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type,Authorization'
    response.headers['Access-Control-Allow-Methods'] = 'GET,PUT,POST,DELETE,OPTIONS'
    return response

# ── Root ───────────────────────────────────────────────────────────────────────
@app.route('/', methods=['GET'])
def index():
    skill_ok = os.path.isfile(os.path.join(SKILL_PATH, 'scripts', 'run.py'))
    return (
        f'<h2>Pulse Backend</h2>'
        f'<p>Status: ✅ running</p>'
        f'<p>NotebookLM skill: {"✅ found" if skill_ok else "❌ not found"}</p>'
        f'<p><a href="/api/health">/api/health</a></p>'
    )

# ── Health check ───────────────────────────────────────────────────────────────
@app.route('/api/health', methods=['GET'])
def health():
    skill_ok = os.path.isfile(os.path.join(SKILL_PATH, 'scripts', 'run.py'))
    return jsonify({'status': 'ok', 'notebooklm_skill': skill_ok})

# ── YouTube Transcript ────────────────────────────────────────────────────────
@app.route('/api/transcript/<video_id>', methods=['GET'])
def get_transcript(video_id):
    """Fetch a YouTube transcript using youtube-transcript-api."""
    if not YT_TRANSCRIPT_AVAILABLE:
        return jsonify({'error': 'youtube-transcript-api not installed. Run: pip install youtube-transcript-api'}), 503

    if not video_id or not re.match(r'^[a-zA-Z0-9_-]{11}$', video_id):
        return jsonify({'error': 'Invalid video ID'}), 400

    try:
        # List available transcripts to detect auto vs manual and pick best English one
        transcript_list = _yt_api.list(video_id)
        try:
            transcript = transcript_list.find_manually_created_transcript(['en', 'en-US', 'en-GB'])
            is_auto = False
        except NoTranscriptFound:
            transcript = transcript_list.find_generated_transcript(['en', 'en-US', 'en-GB'])
            is_auto = True

        lang_code = transcript.language_code
        segments  = transcript.fetch()   # returns FetchedTranscript (iterable of FetchedTranscriptSnippet)

        # Join into paragraph chunks (~15 segments ≈ 45 seconds each)
        texts = [s.text.strip() for s in segments if s.text.strip()]
        paras = [' '.join(texts[i:i+15]) for i in range(0, len(texts), 15)]
        full_text = '\n\n'.join(paras)

        return jsonify({
            'transcript': full_text,
            'segments':   len(texts),
            'auto':       is_auto,
            'language':   lang_code,
        })

    except (TranscriptsDisabled, VideoUnavailable):
        return jsonify({'error': 'NO_CAPTIONS'}), 404
    except NoTranscriptFound:
        return jsonify({'error': 'NO_CAPTIONS'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ── NotebookLM Q&A ─────────────────────────────────────────────────────────────
@app.route('/api/notebooklm/ask', methods=['POST'])
def ask_notebooklm():
    """Query a NotebookLM notebook via the notebooklm-skill subprocess."""
    data = request.json or {}
    question      = (data.get('question')     or '').strip()
    notebook_url  = (data.get('notebookUrl')  or '').strip()
    entry_context = (data.get('entryContext') or '').strip()

    if not question:
        return jsonify({'error': 'No question provided'}), 400
    if not notebook_url:
        return jsonify({'error': 'No notebook URL provided'}), 400
    if not os.path.isdir(SKILL_PATH):
        return jsonify({'error': f'NotebookLM skill directory not found: {SKILL_PATH}'}), 400
    if not os.path.isfile(os.path.join(SKILL_PATH, 'scripts', 'run.py')):
        return jsonify({'error': 'run.py not found in skill directory'}), 400

    # Prefix question with entry context when provided
    full_question = (
        f'[Context: {entry_context}]\n\n{question}' if entry_context else question
    )

    try:
        result = subprocess.run(
            ['python3', 'scripts/run.py', 'ask_question.py',
             '--question', full_question,
             '--notebook-url', notebook_url],
            cwd=SKILL_PATH,
            capture_output=True,
            text=True,
            timeout=90
        )

        output = result.stdout or ''

        # Parse answer from between === separator blocks.
        SEP = '=' * 60
        parts = output.split(SEP)
        answer = parts[2].strip() if len(parts) >= 3 else ''

        # Strip the follow-up reminder appended by the skill
        marker = 'EXTREMELY IMPORTANT:'
        if marker in answer:
            answer = answer[:answer.index(marker)].strip()

        # Strip NotebookLM citation numbers (4-pass regex from Brewing App)
        answer = re.sub(r'(?m)^\d+\s*$', '', answer)
        answer = re.sub(r'\n+([.,])', r'\1', answer)
        answer = re.sub(r'(?<=[a-zA-Z,)]) ?(\d+)( \d+)*(?=[ .,\n]|$)', '', answer)
        answer = re.sub(r'  +', ' ', answer)
        answer = re.sub(r'\n{3,}', '\n\n', answer)
        answer = answer.strip()

        if not answer:
            stderr = (result.stderr or '').strip()
            combined = output + stderr
            if 'Not authenticated' in combined:
                return jsonify({'error': (
                    'NotebookLM not authenticated. Run: '
                    'python3 scripts/run.py auth_manager.py setup '
                    f'(from {SKILL_PATH})'
                )}), 401
            if 'Timeout' in combined and 'notebooklm' in combined.lower():
                return jsonify({'error': (
                    'NotebookLM session expired — re-run auth setup from the skill directory'
                )}), 401
            if 'days old' in combined:
                return jsonify({'error': (
                    'NotebookLM browser session is stale — re-run auth setup'
                )}), 401
            debug = (output or stderr or 'No output from subprocess').strip()[:400]
            return jsonify({'error': f'No answer received. Debug: {debug}'}), 500

        return jsonify({'answer': answer})

    except subprocess.TimeoutExpired:
        return jsonify({'error': 'Request timed out (90s). NotebookLM may be slow or unreachable.'}), 504
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ═══════════════════════════════════════════════════════════════════════════════
# DB — Status
# ═══════════════════════════════════════════════════════════════════════════════

@app.route('/api/db/status/person/<person_id>', methods=['GET'])
def db_get_person_statuses(person_id):
    return jsonify(_db.get_person_statuses(person_id, path=_db.DB_PATH))


@app.route('/api/db/status/<entry_id>', methods=['GET'])
def db_get_status(entry_id):
    return jsonify({'status': _db.get_status(entry_id, path=_db.DB_PATH)})


@app.route('/api/db/status/<entry_id>', methods=['PUT'])
def db_set_status(entry_id):
    data = request.json or {}
    person_id = (data.get('person_id') or '').strip()
    platform  = (data.get('platform')  or '').strip()
    status    = (data.get('status')    or '').strip()
    if not all([person_id, platform, status]):
        return jsonify({'error': 'person_id, platform, and status are required'}), 400
    try:
        _db.set_status(entry_id, person_id, platform, status, path=_db.DB_PATH)
        return jsonify({'ok': True})
    except ValueError as e:
        return jsonify({'error': str(e)}), 400


# ═══════════════════════════════════════════════════════════════════════════════
# DB — Notes
# ═══════════════════════════════════════════════════════════════════════════════

@app.route('/api/db/notes/migrate', methods=['POST'])
def db_migrate_notes():
    data = request.json or {}
    notes = data.get('notes', {})
    person_ids = data.get('person_ids', {})
    if not isinstance(notes, dict):
        return jsonify({'error': 'notes must be a dict {entry_id: note_string}'}), 400
    count = _db.migrate_notes(notes, person_ids=person_ids, path=_db.DB_PATH)
    return jsonify({'migrated': count})


@app.route('/api/db/notes/<entry_id>', methods=['GET'])
def db_get_notes(entry_id):
    return jsonify(_db.get_notes(entry_id, path=_db.DB_PATH))


@app.route('/api/db/notes/<entry_id>', methods=['PUT'])
def db_set_notes(entry_id):
    data = request.json or {}
    person_id   = (data.get('person_id') or '').strip()
    manual_note = data.get('manual_note')   # None = don't update
    ai_note     = data.get('ai_note')       # None = don't update
    if not person_id:
        return jsonify({'error': 'person_id is required'}), 400
    _db.set_notes(entry_id, person_id, manual_note=manual_note, ai_note=ai_note,
                  path=_db.DB_PATH)
    return jsonify({'ok': True})


# ═══════════════════════════════════════════════════════════════════════════════
# DB — Calibre links
# ═══════════════════════════════════════════════════════════════════════════════

@app.route('/api/db/calibre/person/<person_id>', methods=['GET'])
def db_get_person_calibre_links(person_id):
    return jsonify(_db.get_person_calibre_links(person_id, path=_db.DB_PATH))


@app.route('/api/db/calibre/<entry_id>', methods=['GET'])
def db_get_calibre_link(entry_id):
    result = _db.get_calibre_link(entry_id, path=_db.DB_PATH)
    if result is None:
        return jsonify({'error': 'not found'}), 404
    return jsonify(result)


@app.route('/api/db/calibre/push', methods=['POST'])
def db_push_to_calibre():
    """
    Push text content to Calibre via calibredb CLI.
    Body: {entry_id, person_id, title, content, content_type}
    Returns: {calibre_id, formats}
    """
    import shutil, subprocess as _subprocess, tempfile, os as _os
    data = request.json or {}
    entry_id     = (data.get('entry_id')     or '').strip()
    person_id    = (data.get('person_id')    or '').strip()
    title        = (data.get('title')        or '').strip()
    content      = (data.get('content')      or '').strip()
    content_type = (data.get('content_type') or 'transcript').strip()

    if not all([entry_id, person_id, title, content]):
        return jsonify({'error': 'entry_id, person_id, title, content are required'}), 400

    calibredb = (shutil.which('calibredb')
                 or '/Applications/calibre.app/Contents/MacOS/calibredb')
    if not _os.path.isfile(calibredb):
        return jsonify({'error': 'calibredb not found. Is Calibre installed?'}), 503

    safe_title   = _html.escape(title)
    safe_content = _html.escape(content)
    html_doc = (f'<!DOCTYPE html><html><head><meta charset="utf-8">'
                f'<title>{safe_title}</title></head>'
                f'<body><h1>{safe_title}</h1>'
                f'<pre style="white-space:pre-wrap;font-family:serif">{safe_content}</pre>'
                f'</body></html>')

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.html', delete=False, encoding='utf-8'
        ) as f:
            f.write(html_doc)
            tmp_path = f.name

        result = _subprocess.run(
            [calibredb, 'add', tmp_path,
             f'--title={title}',
             '--authors=Pulse',
             f'--tags={content_type}'],
            capture_output=True, text=True, timeout=30
        )
        match = re.search(r'Added book ids?: (\d+)', result.stdout)
        if not match:
            err = (result.stderr or result.stdout or 'no output').strip()[:300]
            return jsonify({'error': f'calibredb add failed: {err}'}), 500

        book_id = int(match.group(1))
        _db.set_calibre_link(entry_id, person_id, book_id, title,
                             ['HTML'], content_type)
        return jsonify({'calibre_id': book_id, 'formats': ['HTML']})

    except _subprocess.TimeoutExpired:
        return jsonify({'error': 'calibredb timed out'}), 504
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if tmp_path and _os.path.exists(tmp_path):
            _os.unlink(tmp_path)


# ═══════════════════════════════════════════════════════════════════════════════
# DB — Episodes
# ═══════════════════════════════════════════════════════════════════════════════

@app.route('/api/db/episodes/<person_id>', methods=['GET'])
def db_get_episodes(person_id):
    try:
        limit  = int(request.args.get('limit', 50))
        offset = int(request.args.get('offset', 0))
    except (ValueError, TypeError):
        return jsonify({'error': 'limit and offset must be integers'}), 400
    sort   = request.args.get('sort', 'date_desc')
    return jsonify(_db.get_episodes(person_id, limit=limit, offset=offset, sort=sort,
                                    db_path=_db.DB_PATH))


@app.route('/api/db/episodes/sync/<person_id>', methods=['POST'])
def db_sync_episodes(person_id):
    """
    Fetch full episode archive from RSS and/or iTunes, upsert to SQLite.
    Body: {person_name, rss_url?, itunes_id?}
    """
    from xml.etree import ElementTree as ET
    data        = request.json or {}
    person_name = (data.get('person_name') or '').strip()
    rss_url     = (data.get('rss_url')     or '').strip() or None
    itunes_id   = data.get('itunes_id')

    if not person_name:
        return jsonify({'error': 'person_name is required'}), 400
    if not rss_url and not itunes_id:
        return jsonify({'error': 'At least one of rss_url or itunes_id is required'}), 400

    episodes = []
    now = _db._now()

    if rss_url:
        try:
            resp = _requests.get(rss_url, timeout=20,
                                 headers={'User-Agent': 'Pulse/1.0'})
            resp.raise_for_status()
            root = ET.fromstring(resp.content)
            itunes_ns = 'http://www.itunes.com/dtds/podcast-1.0.dtd'

            for item in root.findall('.//item'):
                def _get(tag):
                    el = item.find(tag)
                    return (el.text or '').strip() if el is not None else ''

                link = _get('link') or ''
                enc  = item.find('enclosure')
                if not link and enc is not None:
                    link = enc.get('url', '')
                if not link:
                    continue

                ep_id = f'{person_id}-podcast-{link}'[:80]

                dur_str = _get(f'{{{itunes_ns}}}duration')
                duration_sec = None
                if dur_str:
                    parts = dur_str.split(':')
                    try:
                        if len(parts) == 3:
                            duration_sec = int(parts[0])*3600 + int(parts[1])*60 + int(parts[2])
                        elif len(parts) == 2:
                            duration_sec = int(parts[0])*60 + int(parts[1])
                        else:
                            duration_sec = int(parts[0])
                    except (ValueError, IndexError):
                        pass

                ep_num_str = _get(f'{{{itunes_ns}}}episode')
                ep_num = int(ep_num_str) if ep_num_str.isdigit() else None

                episodes.append({
                    'id': ep_id, 'person_id': person_id, 'person_name': person_name,
                    'platform': 'podcast', 'title': _get('title'), 'link': link,
                    'description': _get('description')[:500],
                    'date': _get('pubDate'), 'duration_sec': duration_sec,
                    'episode_number': ep_num, 'itunes_episode_id': None,
                })
        except Exception as e:
            return jsonify({'error': f'RSS fetch failed: {e}'}), 500

    if itunes_id:
        try:
            url = (f'https://itunes.apple.com/lookup?id={itunes_id}'
                   f'&entity=podcastEpisode&limit=200')
            resp = _requests.get(url, timeout=20)
            resp.raise_for_status()
            existing_links = {ep['link'] for ep in episodes}
            for item in resp.json().get('results', []):
                if item.get('kind') != 'podcast-episode':
                    continue
                link = item.get('episodeUrl') or item.get('trackViewUrl') or ''
                if not link or link in existing_links:
                    continue
                existing_links.add(link)
                ep_id = f'{person_id}-podcast-{link}'[:80]
                ms = item.get('trackTimeMillis') or 0
                episodes.append({
                    'id': ep_id, 'person_id': person_id, 'person_name': person_name,
                    'platform': 'podcast',
                    'title': item.get('trackName') or '',
                    'link': link,
                    'description': (item.get('description') or '')[:500],
                    'date': item.get('releaseDate') or '',
                    'duration_sec': ms // 1000 if ms else None,
                    'episode_number': item.get('episodeNumber'),
                    'itunes_episode_id': str(item.get('trackId', '')),
                })
        except Exception as e:
            return jsonify({'error': f'iTunes fetch failed: {e}'}), 500

    _db.upsert_episodes(episodes, path=_db.DB_PATH)

    # Auto-extract guests for each episode
    for ep in episodes:
        guests = _db.extract_guests_from_title(ep['title'])
        if guests:
            _db.set_episode_guests(ep['id'],
                                   [{'name': g, 'source': 'ai_extracted'} for g in guests],
                                   path=_db.DB_PATH)

    return jsonify({'synced': len(episodes), 'total': len(episodes)})


@app.route('/api/db/episodes/<episode_id>/guests', methods=['PUT'])
def db_set_episode_guests(episode_id):
    data   = request.json or {}
    guests = data.get('guests', [])
    if not isinstance(guests, list):
        return jsonify({'error': 'guests must be a list'}), 400
    for g in guests:
        if 'name' not in g or 'source' not in g:
            return jsonify({'error': 'each guest needs name and source'}), 400
        if g['source'] not in {'manual', 'ai_extracted', 'rss_parsed'}:
            return jsonify({'error': f'invalid source: {g["source"]}'}), 400
    _db.set_episode_guests(episode_id, guests, path=_db.DB_PATH)
    return jsonify({'ok': True})


# ═══════════════════════════════════════════════════════════════════════════════
# DB — Guests
# ═══════════════════════════════════════════════════════════════════════════════

@app.route('/api/db/guests', methods=['GET'])
def db_search_guests():
    q = (request.args.get('q') or '').strip()
    if not q:
        return jsonify({'guests': []})
    return jsonify({'guests': _db.search_guests(q, path=_db.DB_PATH)})


@app.route('/api/db/guests/<int:guest_id>/episodes', methods=['GET'])
def db_get_guest_episodes(guest_id):
    try:
        limit = int(request.args.get('limit', 20))
    except (ValueError, TypeError):
        return jsonify({'error': 'limit must be an integer'}), 400
    return jsonify({'episodes': _db.get_guest_episodes(guest_id, limit=limit, path=_db.DB_PATH)})


# ═══════════════════════════════════════════════════════════════════════════════
# DB — Library
# ═══════════════════════════════════════════════════════════════════════════════

@app.route('/api/db/library', methods=['GET'])
def db_library():
    status      = request.args.get('status')    or None
    platform    = request.args.get('platform')  or None
    person_id   = request.args.get('person_id') or None
    guest_id    = request.args.get('guest_id')
    calibre_only = request.args.get('calibre_only', '').lower() in ('1', 'true')
    sort        = request.args.get('sort', 'date_desc')
    try:
        limit  = int(request.args.get('limit', 50))
        offset = int(request.args.get('offset', 0))
    except (ValueError, TypeError):
        return jsonify({'error': 'limit and offset must be integers'}), 400

    return jsonify(_db.query_library(
        status_filter=status, platform_filter=platform,
        person_id=person_id,
        guest_id=int(guest_id) if guest_id else None,
        calibre_only=calibre_only, sort=sort,
        limit=limit, offset=offset,
        db_path=_db.DB_PATH,
    ))


# ── Startup ────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    skill_ok = os.path.isfile(os.path.join(SKILL_PATH, 'scripts', 'run.py'))
    db_path  = _db.DB_PATH
    print(f'\n🔍 Pulse backend running on http://localhost:{PORT}')
    print(f'   DB path:     {db_path} ({"✅ exists" if os.path.exists(db_path) else "🆕 will be created"})')
    print(f'   Skill path:  {SKILL_PATH}')
    print(f'   Skill found: {"✅" if skill_ok else "❌ NOT FOUND — check NOTEBOOKLM_SKILL_PATH env var"}\n')
    app.run(host='0.0.0.0', port=PORT, debug=True)
