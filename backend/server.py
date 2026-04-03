"""
Pulse Backend — Phase 1: NotebookLM Q&A proxy
Adapted from Brewing App backend/app.py
"""

import os
import re
import subprocess
from flask import Flask, jsonify, request, make_response

# ── Configuration ──────────────────────────────────────────────────────────────
DEFAULT_SKILL_PATH = os.path.expanduser(
    '~/Documents/Cem Code/PK App/.claude/skills/notebooklm'
)
SKILL_PATH = os.environ.get('NOTEBOOKLM_SKILL_PATH', DEFAULT_SKILL_PATH)
PORT = int(os.environ.get('PORT', 5001))

app = Flask(__name__)

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

# ── Startup ────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    skill_ok = os.path.isfile(os.path.join(SKILL_PATH, 'scripts', 'run.py'))
    print(f'\n🔍 Pulse backend running on http://localhost:{PORT}')
    print(f'   Skill path:  {SKILL_PATH}')
    print(f'   Skill found: {"✅" if skill_ok else "❌ NOT FOUND — check NOTEBOOKLM_SKILL_PATH env var"}\n')
    app.run(host='0.0.0.0', port=PORT, debug=True)
