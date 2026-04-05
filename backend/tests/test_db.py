import pytest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from db import init_db, get_db, get_status, set_status, get_person_statuses

VALID_STATUSES = {'unread', 'want_to_read', 'in_progress', 'done', 'skipped'}

@pytest.fixture
def db(tmp_path):
    path = str(tmp_path / 'test.db')
    init_db(path)
    return path


def test_init_creates_all_tables(db):
    with get_db(db) as conn:
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )}
    assert {'content_status', 'notes', 'calibre_links',
            'episodes', 'guests', 'episode_guests'}.issubset(tables)


def test_get_status_returns_unread_by_default(db):
    result = get_status('entry-abc', db)
    assert result == 'unread'


def test_set_and_get_status(db):
    set_status('entry-abc', 'person-1', 'podcast', 'done', db)
    assert get_status('entry-abc', db) == 'done'


def test_set_status_rejects_invalid_value(db):
    with pytest.raises(ValueError):
        set_status('entry-abc', 'person-1', 'podcast', 'invalid', db)


def test_get_person_statuses_returns_dict(db):
    set_status('entry-1', 'person-1', 'podcast', 'done', db)
    set_status('entry-2', 'person-1', 'youtube', 'want_to_read', db)
    result = get_person_statuses('person-1', db)
    assert result == {'entry-1': 'done', 'entry-2': 'want_to_read'}


def test_get_person_statuses_empty_for_unknown_person(db):
    assert get_person_statuses('no-such-person', db) == {}


from db import get_notes, set_notes, migrate_notes


def test_get_notes_returns_empty_for_unknown_entry(db):
    result = get_notes('entry-xyz', db)
    assert result == {'manual_note': None, 'ai_note': None, 'updated_at': None}


def test_set_and_get_manual_note(db):
    set_notes('entry-1', 'person-1', manual_note='Great episode', path=db)
    result = get_notes('entry-1', db)
    assert result['manual_note'] == 'Great episode'
    assert result['ai_note'] is None


def test_set_ai_note_does_not_overwrite_manual(db):
    set_notes('entry-1', 'person-1', manual_note='My note', path=db)
    set_notes('entry-1', 'person-1', ai_note='AI summary', path=db)
    result = get_notes('entry-1', db)
    assert result['manual_note'] == 'My note'
    assert result['ai_note'] == 'AI summary'


def test_migrate_notes_inserts_all(db):
    legacy = {
        'entry-a': 'Note for A',
        'entry-b': 'Note for B',
    }
    count = migrate_notes(legacy, db)
    assert count == 2
    assert get_notes('entry-a', db)['manual_note'] == 'Note for A'


def test_migrate_notes_skips_already_migrated(db):
    set_notes('entry-a', 'person-1', manual_note='Existing', path=db)
    count = migrate_notes({'entry-a': 'New value'}, db)
    assert count == 0  # already exists, skip
    assert get_notes('entry-a', db)['manual_note'] == 'Existing'


from db import (get_calibre_link, set_calibre_link, get_person_calibre_links,
                upsert_episodes, get_episodes,
                name_to_slug, extract_guests_from_title,
                search_guests, set_episode_guests)


# ── Calibre ───────────────────────────────────────────────────────────────────

def test_set_and_get_calibre_link(db):
    set_calibre_link('entry-1', 'person-1', 42, 'Lex #431', ['HTML'], 'transcript', db)
    result = get_calibre_link('entry-1', db)
    assert result['calibre_id'] == 42
    assert result['calibre_title'] == 'Lex #431'
    assert result['content_type'] == 'transcript'


def test_get_calibre_link_returns_none_for_unknown(db):
    assert get_calibre_link('no-entry', db) is None


def test_get_person_calibre_links(db):
    set_calibre_link('e1', 'person-1', 10, 'Title A', ['HTML'], 'transcript', db)
    set_calibre_link('e2', 'person-1', 11, 'Title B', ['HTML'], 'article', db)
    result = get_person_calibre_links('person-1', db)
    assert set(result.keys()) == {'e1', 'e2'}
    assert result['e1']['calibre_id'] == 10


# ── Episodes ──────────────────────────────────────────────────────────────────

def test_upsert_episodes_inserts_new(db):
    eps = [{'id': 'ep-1', 'person_id': 'p1', 'person_name': 'Lex Fridman',
            'platform': 'podcast', 'title': 'Ep 1', 'link': 'http://ex.com/1',
            'description': 'desc', 'date': '2026-01-01', 'duration_sec': 3600,
            'episode_number': 1, 'itunes_episode_id': None}]
    upsert_episodes(eps, db)
    result = get_episodes('p1', db_path=db)
    assert result['total'] == 1
    assert result['episodes'][0]['title'] == 'Ep 1'


def test_upsert_episodes_updates_on_conflict(db):
    ep = {'id': 'ep-1', 'person_id': 'p1', 'person_name': 'Lex',
          'platform': 'podcast', 'title': 'Old Title', 'link': 'http://ex.com/1',
          'description': '', 'date': '2026-01-01', 'duration_sec': None,
          'episode_number': None, 'itunes_episode_id': None}
    upsert_episodes([ep], db)
    ep['title'] = 'New Title'
    upsert_episodes([ep], db)
    result = get_episodes('p1', db_path=db)
    assert result['total'] == 1
    assert result['episodes'][0]['title'] == 'New Title'


def test_get_episodes_pagination(db):
    eps = [{'id': f'ep-{i}', 'person_id': 'p1', 'person_name': 'Lex',
            'platform': 'podcast', 'title': f'Ep {i}', 'link': f'http://ex.com/{i}',
            'description': '', 'date': f'2026-01-{i:02d}', 'duration_sec': None,
            'episode_number': i, 'itunes_episode_id': None}
           for i in range(1, 6)]
    upsert_episodes(eps, db)
    result = get_episodes('p1', limit=2, offset=0, db_path=db)
    assert result['total'] == 5
    assert len(result['episodes']) == 2


# ── Guests ────────────────────────────────────────────────────────────────────

def test_name_to_slug():
    assert name_to_slug('Elon Musk') == 'elon-musk'
    assert name_to_slug('Yuval Noah Harari') == 'yuval-noah-harari'


def test_extract_guests_from_pipe_separator():
    guests = extract_guests_from_title('#431 — Elon Musk | Tesla & SpaceX')
    assert 'Elon Musk' in guests


def test_extract_guests_from_dash_separator():
    guests = extract_guests_from_title('Michael Levin — Intelligence Beyond the Brain')
    assert 'Michael Levin' in guests


def test_extract_guests_returns_empty_for_no_guest():
    assert extract_guests_from_title('Weekly News Roundup') == []


def test_set_episode_guests_and_search(db):
    ep = {'id': 'ep-1', 'person_id': 'p1', 'person_name': 'Lex',
          'platform': 'podcast', 'title': 'With Elon Musk', 'link': 'http://x.com/1',
          'description': '', 'date': '2026-01-01', 'duration_sec': None,
          'episode_number': None, 'itunes_episode_id': None}
    upsert_episodes([ep], db)
    set_episode_guests('ep-1', [{'name': 'Elon Musk', 'source': 'manual'}], db)
    results = search_guests('elon', db)
    assert len(results) == 1
    assert results[0]['name'] == 'Elon Musk'
