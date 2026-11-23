from pathlib import Path

import pytest

from sage.calendar_io import import_icalendar_proposals
from sage.core import SageStore


SAMPLE = r"""BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
UID:launch-001@example.test
DTSTART;VALUE=DATE:20261201
SUMMARY:Prepare\, product launch
END:VEVENT
BEGIN:VEVENT
UID:weekly-001@example.test
DTSTART:20261202T090000Z
SUMMARY:Weekly review
RRULE:FREQ=WEEKLY
END:VEVENT
BEGIN:VEVENT
UID:cancelled-001@example.test
DTSTART;VALUE=DATE:20261203
SUMMARY:Cancelled event
STATUS:CANCELLED
END:VEVENT
BEGIN:VEVENT
UID:missing-date@example.test
SUMMARY:No date
END:VEVENT
END:VCALENDAR
"""


def test_ics_import_creates_pending_proposals_and_is_idempotent(tmp_path):
    store = SageStore(tmp_path / "sage.db")
    project = store.add_project("Imported calendar")
    source = tmp_path / "calendar.ics"
    source.write_text(SAMPLE, encoding="utf-8")

    first = import_icalendar_proposals(store, source, project)
    assert first == {"created": 1, "duplicates": 0, "skipped": 3}
    proposal = store.list_task_proposals("pending")[0]
    assert proposal["title"] == "Prepare, product launch"
    assert proposal["due_date"] == "2026-12-01"
    assert proposal["source_uid"].startswith("ics:")
    assert store.list_tasks() == []

    second = import_icalendar_proposals(store, source, project)
    assert second == {"created": 0, "duplicates": 1, "skipped": 3}
    assert len(store.list_task_proposals()) == 1

    task_id = store.approve_task_proposal(proposal["id"])
    assert store.list_tasks()[0]["id"] == task_id


def test_ics_import_requires_valid_file_project_and_limit(tmp_path):
    store = SageStore(tmp_path / "sage.db")
    project = store.add_project("Calendar")
    bad = tmp_path / "bad.ics"
    bad.write_text("not an icalendar file", encoding="utf-8")
    with pytest.raises(ValueError, match="complete iCalendar"):
        import_icalendar_proposals(store, bad, project)
    valid = tmp_path / "valid.ics"
    valid.write_text(SAMPLE, encoding="utf-8")
    with pytest.raises(ValueError, match="does not exist"):
        import_icalendar_proposals(store, valid, 999)
    with pytest.raises(ValueError, match="between 1 and 500"):
        import_icalendar_proposals(store, valid, project, 0)


def test_ics_import_skips_over_limit_and_rejects_non_ics_files(tmp_path):
    store = SageStore(tmp_path / "sage.db")
    project = store.add_project("Calendar")
    source = tmp_path / "calendar.txt"
    source.write_text(SAMPLE, encoding="utf-8")
    with pytest.raises(ValueError, match="existing .ics"):
        import_icalendar_proposals(store, source, project)
    source = tmp_path / "many.ics"
    source.write_text(SAMPLE, encoding="utf-8")
    with pytest.raises(ValueError, match="more than the 1 event import limit"):
        import_icalendar_proposals(store, source, project, 1)


def test_cli_import_ics_routes_events_to_approval_queue(tmp_path, capsys):
    from sage.cli import main

    database = str(tmp_path / "cli.db")
    assert main(["--db", database, "add-project", "Calendar imports"]) == 0
    capsys.readouterr()
    source = tmp_path / "cli.ics"
    source.write_text(SAMPLE, encoding="utf-8")
    assert main(["--db", database, "import-ics", str(source), "--project-id", "1"]) == 0
    output = capsys.readouterr().out
    assert "PENDING TASK PROPOSALS ONLY" in output
    assert "Created: 1" in output and "Skipped: 3" in output
    store = SageStore(database)
    assert len(store.list_task_proposals("pending")) == 1
    assert store.list_tasks() == []
