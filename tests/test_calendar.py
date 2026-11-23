from sage.core import SageStore


def test_ics_export_contains_only_open_dated_tasks_from_active_projects(tmp_path):
    store = SageStore(tmp_path / "calendar.db")
    active = store.add_project("Active project")
    paused = store.add_project("Paused project")
    store.set_project_status(paused, "paused")
    task = store.add_task(
        active, "Client, follow-up; day 2\nnotes", priority=1, due_date="2026-11-25"
    )
    done = store.add_task(active, "Already done", due_date="2026-11-26")
    store.set_task_status(done, "done")
    store.add_task(active, "No due date")

    path = store.export_calendar(tmp_path / "calendar" / "sage.ics")
    content = path.read_bytes().decode("utf-8")
    assert "BEGIN:VCALENDAR" in content
    assert "VERSION:2.0" in content
    assert "DTSTART;VALUE=DATE:20261125" in content
    assert "SUMMARY:Client\\, follow-up\\; day 2\\nnotes" in content
    assert "SUMMARY:Already done" not in content
    assert "SUMMARY:No due date" not in content
    assert "END:VCALENDAR" in content
    assert b"\r\n" in path.read_bytes()
    assert content.count("BEGIN:VEVENT") == 1


def test_ics_export_refuses_to_overwrite_without_force(tmp_path):
    store = SageStore(tmp_path / "calendar-overwrite.db")
    target = tmp_path / "calendar.ics"
    store.export_calendar(target)
    try:
        store.export_calendar(target)
        assert False, "existing calendar export should be protected"
    except ValueError as error:
        assert "already exists" in str(error)
