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
