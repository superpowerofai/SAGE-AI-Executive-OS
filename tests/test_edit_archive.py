from sage.core import SageStore


def test_project_and_task_can_be_edited_and_archived(tmp_path):
    store = SageStore(tmp_path / "edit.db")
    project_id = store.add_project("Old name", "Old description")
    task_id = store.add_task(project_id, "Old task", priority=4, due_date="2026-11-25")

    store.update_project(project_id, name="New name", description="Updated description")
    store.update_task(task_id, title="New task", priority=1, due_date="2026-11-27")
    project = store.list_projects()[0]
    task = store.list_tasks()[0]
    assert project["name"] == "New name"
    assert project["description"] == "Updated description"
    assert task["title"] == "New task"
    assert task["priority"] == 1
    assert task["due_date"] == "2026-11-27"

    store.update_task(task_id, clear_due_date=True)
    assert store.list_tasks()[0]["due_date"] is None

    store.set_task_status(task_id, "done")
    store.set_project_status(project_id, "completed")
    assert store.list_projects()[0]["status"] == "completed"
    assert store.list_tasks()[0]["status"] == "done"


def test_edit_operations_reject_empty_or_invalid_changes(tmp_path):
    store = SageStore(tmp_path / "validation.db")
    project_id = store.add_project("Project")
    task_id = store.add_task(project_id, "Task")

    for operation in (
        lambda: store.update_project(project_id, name=" "),
        lambda: store.update_project(project_id),
        lambda: store.update_task(task_id, priority=0),
        lambda: store.update_task(task_id, due_date="next week"),
        lambda: store.update_task(task_id, clear_due_date=True, due_date="2026-11-25"),
        lambda: store.update_task(task_id),
    ):
        try:
            operation()
            assert False, "invalid edit should be rejected"
        except ValueError:
            pass
