from pathlib import Path

import pytest

from sage.core import SageStore


def test_calendar_export_requires_approval_and_executes_once(tmp_path):
    store = SageStore(tmp_path / "sage.db")
    project = store.add_project("Launch")
    store.add_task(project, "Publish landing page", due_date="2026-12-01")

    request_id = store.create_action_request(
        "calendar_export", "Export December tasks", {"filename": "december.ics"}
    )
    assert not (tmp_path / "exports" / "december.ics").exists()
    assert store.list_action_requests("pending")[0]["id"] == request_id

    destination = store.approve_action_request(request_id)
    assert destination == (tmp_path / "exports" / "december.ics").resolve()
    assert "Publish landing page" in destination.read_text(encoding="utf-8")
    record = store.list_action_requests()[0]
    assert record["status"] == "executed"
    assert record["approved_at"] and record["completed_at"]
    assert record["result"] == str(destination)
    with pytest.raises(ValueError, match="Only pending"):
        store.approve_action_request(request_id)


def test_rejected_action_never_executes(tmp_path):
    store = SageStore(tmp_path / "sage.db")
    request_id = store.create_action_request(
        "calendar_export", "Export tasks", {"filename": "rejected.ics"}
    )
    store.reject_action_request(request_id)
    assert store.list_action_requests()[0]["status"] == "rejected"
    assert not (tmp_path / "exports" / "rejected.ics").exists()
    with pytest.raises(ValueError, match="Only pending"):
        store.approve_action_request(request_id)


@pytest.mark.parametrize("filename", ["../escape.ics", "C:/escape.ics", "folder\\file.ics", "bad.txt", "", ".hidden.ics"])
def test_action_request_rejects_unsafe_calendar_paths(tmp_path, filename):
    store = SageStore(tmp_path / "sage.db")
    with pytest.raises(ValueError, match="simple .ics filename"):
        store.create_action_request("calendar_export", "Export", {"filename": filename})


def test_only_registered_action_types_are_accepted(tmp_path):
    store = SageStore(tmp_path / "sage.db")
    with pytest.raises(ValueError, match="Unsupported action type"):
        store.create_action_request("send_email", "Send", {"to": "someone@example.com"})


def test_existing_export_is_not_overwritten_and_failure_is_recorded(tmp_path):
    store = SageStore(tmp_path / "sage.db")
    export_dir = tmp_path / "exports"
    export_dir.mkdir()
    existing = export_dir / "existing.ics"
    existing.write_text("KEEP", encoding="utf-8")
    request_id = store.create_action_request(
        "calendar_export", "Export", {"filename": "existing.ics"}
    )
    with pytest.raises(ValueError, match="already exists"):
        store.approve_action_request(request_id)
    assert existing.read_text(encoding="utf-8") == "KEEP"
    assert store.list_action_requests()[0]["status"] == "failed"


def test_action_requests_round_trip_through_json_backup(tmp_path):
    source = SageStore(tmp_path / "source.db")
    request_id = source.create_action_request(
        "calendar_export", "Backup queued export", {"filename": "backup.ics"}
    )
    export_path = source.export_data(tmp_path / "sage-export.json")
    target = SageStore(tmp_path / "restored.db")
    imported = target.import_data(export_path)
    assert imported["action_requests"] == 1
    restored = target.list_action_requests()[0]
    assert restored["id"] == request_id
    assert restored["status"] == "pending"
    assert restored["payload"] == {"filename": "backup.ics"}


def test_legacy_v9_json_without_action_queue_remains_importable(tmp_path):
    import json

    source = SageStore(tmp_path / "legacy-source.db")
    source.add_project("Legacy project")
    export_path = source.export_data(tmp_path / "current.json")
    payload = json.loads(export_path.read_text(encoding="utf-8"))
    payload["version"] = 9
    payload["data"].pop("action_requests", None)
    legacy_path = tmp_path / "legacy-v9.json"
    legacy_path.write_text(json.dumps(payload), encoding="utf-8")

    restored = SageStore(tmp_path / "legacy-restored.db")
    restored.import_data(legacy_path)
    assert restored.list_projects()[0]["name"] == "Legacy project"
    assert restored.list_action_requests() == []
