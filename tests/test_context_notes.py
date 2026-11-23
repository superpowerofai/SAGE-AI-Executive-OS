import pytest

from sage.core import SageStore
from sage.ai import preview_context


def test_context_notes_persist_and_appear_in_ai_context(tmp_path):
    store = SageStore(tmp_path / "notes.db")
    normal = store.add_context_note(
        "Execution preference", "Evidence first; one clear next action.",
        category="preferences", importance=1,
    )
    store.add_context_note("Business constraint", "No unverified revenue claims.", category="strategy")
    notes = store.list_context_notes()
    assert notes[0]["id"] == normal
    assert "Execution preference" in preview_context(store)
    assert "Evidence first" in preview_context(store)


def test_context_notes_can_be_archived_and_filtered(tmp_path):
    store = SageStore(tmp_path / "archive-notes.db")
    note_id = store.add_context_note("Temporary note", "This is no longer current.")
    store.archive_context_note(note_id)
    assert store.list_context_notes() == []
    assert store.list_context_notes(status="archived")[0]["id"] == note_id
    with pytest.raises(ValueError):
        store.archive_context_note(note_id)


def test_context_notes_validate_lengths_and_importance(tmp_path):
    store = SageStore(tmp_path / "note-validation.db")
    with pytest.raises(ValueError):
        store.add_context_note("", "Missing title")
    with pytest.raises(ValueError):
        store.add_context_note("Title", "")
    with pytest.raises(ValueError):
        store.add_context_note("Title", "Content", importance=6)
    with pytest.raises(ValueError):
        store.add_context_note("Title", "x" * 5001)
