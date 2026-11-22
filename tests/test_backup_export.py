import json
import sqlite3

from sage.core import SageStore


def test_backup_is_restorable_and_preserves_all_tables(tmp_path):
    database = tmp_path / "sage.db"
    store = SageStore(database)
    project_id = store.add_project("Portfolio")
    store.add_task(project_id, "Ship feature", priority=1)
    store.save_review(priority="Ship feature")
    store.add_decision("Choose focus", "Portfolio")
    store.add_blocker("Waiting on access")
    backup = store.backup(tmp_path / "backup" / "sage-copy.db")

    with sqlite3.connect(backup) as connection:
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert connection.execute("SELECT COUNT(*) FROM projects").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM tasks").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM daily_reviews").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM decisions").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM blockers").fetchone()[0] == 1


def test_backup_refuses_overwrite_and_same_database(tmp_path):
    store = SageStore(tmp_path / "sage.db")
    target = tmp_path / "copy.db"
    store.backup(target)
    try:
        store.backup(target)
        assert False, "expected overwrite protection"
    except ValueError as error:
        assert "already exists" in str(error)
    try:
        store.backup(tmp_path / "sage.db")
        assert False, "expected same-file protection"
    except ValueError as error:
        assert "differ" in str(error)


def test_json_export_contains_every_record_type_and_unicode(tmp_path):
    store = SageStore(tmp_path / "sage.db")
    project_id = store.add_project("घर का काम")
    store.add_task(project_id, "पहला कदम")
    store.save_review(priority="आज का लक्ष्य")
    store.add_decision("निर्णय", "आगे बढ़ें")
    store.add_blocker("रुकावट")
    path = store.export_data(tmp_path / "export.json")
    payload = json.loads(path.read_text(encoding="utf-8"))

    assert payload["format"] == "sage-export"
    assert payload["version"] == 1
    assert payload["data"]["projects"][0]["name"] == "घर का काम"
    assert len(payload["data"]["tasks"]) == 1
    assert len(payload["data"]["daily_reviews"]) == 1
    assert len(payload["data"]["decisions"]) == 1
    assert len(payload["data"]["blockers"]) == 1


def test_json_export_refuses_overwrite(tmp_path):
    store = SageStore(tmp_path / "sage.db")
    target = tmp_path / "export.json"
    store.export_data(target)
    try:
        store.export_data(target)
        assert False, "expected overwrite protection"
    except ValueError as error:
        assert "already exists" in str(error)
