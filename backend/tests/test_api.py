import json
import pytest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import db as db_module

# Patch DB_PATH before importing server so endpoints use the test DB
@pytest.fixture(autouse=True)
def patch_db(tmp_path, monkeypatch):
    path = str(tmp_path / 'test.db')
    db_module.init_db(path)
    monkeypatch.setattr(db_module, 'DB_PATH', path)
    return path

@pytest.fixture
def client():
    import server
    server.app.config['TESTING'] = True
    with server.app.test_client() as c:
        yield c

# ── Status endpoints ───────────────────────────────────────────────────────────

def test_get_status_default_unread(client):
    resp = client.get('/api/db/status/entry-abc')
    assert resp.status_code == 200
    assert resp.get_json()['status'] == 'unread'


def test_put_status_and_retrieve(client):
    resp = client.put('/api/db/status/entry-abc',
                      json={'person_id': 'p1', 'platform': 'podcast', 'status': 'done'})
    assert resp.status_code == 200
    assert resp.get_json()['ok'] is True
    resp2 = client.get('/api/db/status/entry-abc')
    assert resp2.get_json()['status'] == 'done'


def test_put_status_rejects_invalid(client):
    resp = client.put('/api/db/status/entry-abc',
                      json={'person_id': 'p1', 'platform': 'podcast', 'status': 'read'})
    assert resp.status_code == 400


def test_get_person_statuses(client):
    client.put('/api/db/status/e1', json={'person_id': 'p1', 'platform': 'podcast', 'status': 'done'})
    client.put('/api/db/status/e2', json={'person_id': 'p1', 'platform': 'youtube', 'status': 'skipped'})
    resp = client.get('/api/db/status/person/p1')
    data = resp.get_json()
    assert data == {'e1': 'done', 'e2': 'skipped'}


# ── Notes endpoints ────────────────────────────────────────────────────────────

def test_get_notes_empty(client):
    resp = client.get('/api/db/notes/entry-xyz')
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['manual_note'] is None


def test_put_and_get_notes(client):
    client.put('/api/db/notes/entry-1',
               json={'person_id': 'p1', 'manual_note': 'Great episode'})
    resp = client.get('/api/db/notes/entry-1')
    assert resp.get_json()['manual_note'] == 'Great episode'


def test_migrate_notes(client):
    resp = client.post('/api/db/notes/migrate',
                       json={'notes': {'e1': 'Note A', 'e2': 'Note B'}})
    assert resp.status_code == 200
    assert resp.get_json()['migrated'] == 2


# ── Calibre endpoints ──────────────────────────────────────────────────────────

def test_get_calibre_link_404(client):
    resp = client.get('/api/db/calibre/no-entry')
    assert resp.status_code == 404


def test_get_calibre_link_after_set(client, patch_db):
    db_module.set_calibre_link('e1', 'p1', 42, 'Title', ['HTML'], 'transcript', patch_db)
    resp = client.get('/api/db/calibre/e1')
    assert resp.status_code == 200
    assert resp.get_json()['calibre_id'] == 42


def test_get_person_calibre_links(client, patch_db):
    db_module.set_calibre_link('e1', 'p1', 10, 'T1', ['HTML'], 'transcript', patch_db)
    db_module.set_calibre_link('e2', 'p1', 11, 'T2', ['HTML'], 'article', patch_db)
    resp = client.get('/api/db/calibre/person/p1')
    data = resp.get_json()
    assert set(data.keys()) == {'e1', 'e2'}


# ── Episodes endpoints ─────────────────────────────────────────────────────────

def test_get_episodes_empty(client):
    resp = client.get('/api/db/episodes/p1')
    assert resp.status_code == 200
    assert resp.get_json() == {'episodes': [], 'total': 0}


def test_get_episodes_with_data(client, patch_db):
    db_module.upsert_episodes([{
        'id': 'ep-1', 'person_id': 'p1', 'person_name': 'Lex',
        'platform': 'podcast', 'title': 'Ep 1', 'link': 'http://x.com/1',
        'description': '', 'date': '2026-01-01', 'duration_sec': None,
        'episode_number': 1, 'itunes_episode_id': None
    }], patch_db)
    resp = client.get('/api/db/episodes/p1')
    data = resp.get_json()
    assert data['total'] == 1


# ── Guests endpoints ───────────────────────────────────────────────────────────

def test_search_guests_empty(client):
    resp = client.get('/api/db/guests?q=elon')
    assert resp.status_code == 200
    assert resp.get_json()['guests'] == []


def test_put_episode_guests_and_search(client, patch_db):
    db_module.upsert_episodes([{
        'id': 'ep-1', 'person_id': 'p1', 'person_name': 'Lex',
        'platform': 'podcast', 'title': 'With Elon', 'link': 'http://x.com/1',
        'description': '', 'date': '2026-01-01', 'duration_sec': None,
        'episode_number': None, 'itunes_episode_id': None
    }], patch_db)
    resp = client.put('/api/db/episodes/ep-1/guests',
                      json={'guests': [{'name': 'Elon Musk', 'source': 'manual'}]})
    assert resp.status_code == 200
    resp2 = client.get('/api/db/guests?q=elon')
    assert len(resp2.get_json()['guests']) == 1


# ── Library endpoint ───────────────────────────────────────────────────────────

def test_library_empty(client):
    resp = client.get('/api/db/library')
    assert resp.status_code == 200
    assert resp.get_json() == {'items': [], 'total': 0}


def test_library_with_episode(client, patch_db):
    db_module.upsert_episodes([{
        'id': 'ep-1', 'person_id': 'p1', 'person_name': 'Lex',
        'platform': 'podcast', 'title': 'Ep 1', 'link': 'http://x.com/1',
        'description': '', 'date': '2026-01-01', 'duration_sec': 3600,
        'episode_number': 1, 'itunes_episode_id': None
    }], patch_db)
    resp = client.get('/api/db/library')
    data = resp.get_json()
    assert data['total'] == 1
    assert data['items'][0]['status'] == 'unread'
