import tempfile
import unittest
from pathlib import Path

from sage.core import SageStore


class SageStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.store = SageStore(Path(self.temp_dir.name) / "test.db")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_create_project_and_task(self):
        project_id = self.store.add_project("Launch website", "First milestone")
        task_id = self.store.add_task(project_id, "Write homepage copy", priority=1)

        projects = self.store.list_projects()
        tasks = self.store.list_tasks()

        self.assertEqual(projects[0]["name"], "Launch website")
        self.assertEqual(tasks[0]["id"], task_id)
        self.assertEqual(tasks[0]["title"], "Write homepage copy")
        self.assertEqual(tasks[0]["priority"], 1)

    def test_task_status_and_dashboard(self):
        project_id = self.store.add_project("SAGE")
        task_id = self.store.add_task(project_id, "Build first feature")
        self.store.set_task_status(task_id, "in_progress")

        self.assertEqual(self.store.dashboard()["in_progress_tasks"], 1)
        self.store.set_task_status(task_id, "done")
        self.assertEqual(self.store.dashboard()["completed_tasks"], 1)

    def test_reject_empty_project_name(self):
        with self.assertRaises(ValueError):
            self.store.add_project(" ")

    def test_reject_invalid_priority(self):
        project_id = self.store.add_project("SAGE")
        with self.assertRaises(ValueError):
            self.store.add_task(project_id, "Bad priority", priority=9)

    def test_reject_unknown_project(self):
        with self.assertRaises(ValueError):
            self.store.add_task(999, "No project")

    def test_project_can_be_paused(self):
        project_id = self.store.add_project("SAGE")
        self.store.set_project_status(project_id, "paused")
        self.assertEqual(self.store.list_projects()[0]["status"], "paused")


if __name__ == "__main__":
    unittest.main()



def test_execution_plan_groups_overdue_upcoming_and_unscheduled_active_work(tmp_path):
    from datetime import date

    store = SageStore(tmp_path / "plan.db")
    active = store.add_project("Active")
    paused = store.add_project("Paused")
    store.set_project_status(paused, "paused")
    store.add_task(active, "Overdue", due_date="2026-11-22")
    store.add_task(active, "Due soon", due_date="2026-11-27", priority=1)
    store.add_task(active, "No date")
    store.add_task(active, "Beyond horizon", due_date="2026-12-30")
    store.add_task(paused, "Paused work", due_date="2026-11-25")

    plan = store.execution_plan(7, today=date(2026, 11, 23))
    assert [task["title"] for task in plan["overdue"]] == ["Overdue"]
    assert [task["title"] for task in plan["upcoming"]] == ["Due soon"]
    assert [task["title"] for task in plan["unscheduled"]] == ["No date"]


def test_due_date_must_be_iso_format(tmp_path):
    store = SageStore(tmp_path / "dates.db")
    project = store.add_project("Dates")
    try:
        store.add_task(project, "Bad date", due_date="tomorrow")
    except ValueError as error:
        assert "YYYY-MM-DD" in str(error)
    else:
        raise AssertionError("Invalid due date should be rejected")


def test_store_creates_missing_database_parent_directories(tmp_path):
    database = tmp_path / "nested" / "runtime" / "sage.db"
    store = SageStore(database)
    project_id = store.add_project("Nested database")
    assert database.exists()
    assert store.list_projects()[0]["id"] == project_id
