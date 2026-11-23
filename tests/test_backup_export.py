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
    venture = store.add_venture("नया व्यवसाय")
    store.log_resource(venture, "expense", 125)
    path = store.export_data(tmp_path / "export.json")
    payload = json.loads(path.read_text(encoding="utf-8"))

    assert payload["format"] == "sage-export"
    assert payload["version"] == 2
    assert payload["data"]["projects"][0]["name"] == "घर का काम"
    assert len(payload["data"]["tasks"]) == 1
    assert len(payload["data"]["daily_reviews"]) == 1
    assert len(payload["data"]["decisions"]) == 1
    assert len(payload["data"]["blockers"]) == 1
    assert len(payload["data"]["ventures"]) == 1
    assert len(payload["data"]["resource_entries"]) == 1


def test_json_export_refuses_overwrite(tmp_path):
    store = SageStore(tmp_path / "sage.db")
    target = tmp_path / "export.json"
    store.export_data(target)
    try:
        store.export_data(target)
        assert False, "expected overwrite protection"
    except ValueError as error:
        assert "already exists" in str(error)


def test_restore_backup_preserves_current_database_and_restores_snapshot(tmp_path):
    store = SageStore(tmp_path / "active.db")
    store.add_project("Before backup")
    backup = store.backup(tmp_path / "safe-copy.db")
    store.add_project("After backup")

    safety_copy = store.restore_backup(backup)
    assert safety_copy is not None and safety_copy.exists()
    assert [p["name"] for p in store.list_projects()] == ["Before backup"]

    preserved = SageStore(safety_copy)
    assert [p["name"] for p in preserved.list_projects()] == [
        "Before backup", "After backup"
    ]


def test_restore_rejects_invalid_database_without_changing_active_data(tmp_path):
    store = SageStore(tmp_path / "active.db")
    store.add_project("Keep this")
    invalid = tmp_path / "not-sage.db"
    invalid.write_text("not a database", encoding="utf-8")

    try:
        store.restore_backup(invalid)
        assert False, "invalid backup should be rejected"
    except Exception as error:
        assert "integrity" in str(error).lower() or "file is not a database" in str(error).lower()

    assert [p["name"] for p in store.list_projects()] == ["Keep this"]


def test_json_export_import_round_trip_preserves_ventures_and_resource_entries(tmp_path):
    source_store = SageStore(tmp_path / "source.db")
    venture = source_store.add_venture("ABSE.INC", monthly_budget_cap=8000)
    project = source_store.add_project("Marketplace", venture_id=venture)
    source_store.add_task(project, "Validate first seller", priority=1)
    source_store.log_resource(venture, "expense", 300, project_id=project, note="Domain")
    export_path = source_store.export_data(tmp_path / "portable.json")

    restored = SageStore(tmp_path / "restored.db")
    counts = restored.import_data(export_path)
    assert counts["ventures"] == 1
    assert counts["projects"] == 1
    assert counts["tasks"] == 1
    assert counts["resource_entries"] == 1
    assert restored.list_ventures()[0]["name"] == "ABSE.INC"
    assert restored.list_projects()[0]["name"] == "Marketplace"
    assert restored.list_resource_entries()[0]["note"] == "Domain"


def test_json_import_supports_legacy_v1_exports(tmp_path):
    import json

    source_store = SageStore(tmp_path / "legacy-source.db")
    source_store.add_project("Old export project")
    export_path = source_store.export_data(tmp_path / "legacy.json")
    payload = json.loads(export_path.read_text(encoding="utf-8"))
    payload["version"] = 1
    payload["data"].pop("ventures")
    payload["data"].pop("resource_entries")
    export_path.write_text(json.dumps(payload), encoding="utf-8")

    restored = SageStore(tmp_path / "legacy-target.db")
    restored.import_data(export_path)
    assert restored.list_projects()[0]["name"] == "Old export project"
    assert restored.list_ventures() == []


def test_json_import_refuses_to_merge_into_nonempty_database(tmp_path):
    source = SageStore(tmp_path / "import-source.db")
    source.add_project("Incoming")
    export_path = source.export_data(tmp_path / "incoming.json")
    target = SageStore(tmp_path / "import-target.db")
    target.add_project("Existing")

    try:
        target.import_data(export_path)
        assert False, "import into a non-empty database must fail"
    except ValueError as error:
        assert "empty SAGE database" in str(error)
    assert [project["name"] for project in target.list_projects()] == ["Existing"]
