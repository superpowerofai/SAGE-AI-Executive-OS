from sage.core import SageStore


def test_venture_portfolio_tracks_projects_tasks_and_user_entered_capacity(tmp_path):
    store = SageStore(tmp_path / "portfolio.db")
    venture = store.add_venture(
        "OPERONIX AI", monthly_budget_cap=25000, weekly_hours_cap=18,
        strategic_priority=1,
    )
    project = store.add_project("Lead follow-up system", venture_id=venture)
    store.add_task(project, "Build first workflow", priority=1)
    store.add_task(project, "Contact first prospect", priority=2)
    summary = store.portfolio_summary()

    assert len(summary["ventures"]) == 1
    item = summary["ventures"][0]
    assert item["name"] == "OPERONIX AI"
    assert item["projects"] == 1
    assert item["active_projects"] == 1
    assert item["open_tasks"] == 2
    assert item["monthly_budget_cap"] == 25000
    assert item["weekly_hours_cap"] == 18
    assert summary["known_monthly_budget_caps"] == 25000
    assert summary["budget_cap_entries"] == 1
    assert summary["known_weekly_hours_caps"] == 18
    assert summary["hours_cap_entries"] == 1
    assert summary["unassigned_projects"] == 0


def test_projects_can_be_assigned_and_unassigned(tmp_path):
    store = SageStore(tmp_path / "assignment.db")
    project = store.add_project("Existing project")
    venture = store.add_venture("HOUSE OF JAI")
    store.assign_project_to_venture(project, venture)
    assert store.portfolio_summary()["ventures"][0]["projects"] == 1
    store.assign_project_to_venture(project, None)
    assert store.portfolio_summary()["unassigned_projects"] == 1


def test_venture_rejects_invalid_resource_caps_and_priority(tmp_path):
    store = SageStore(tmp_path / "validation.db")
    for kwargs in (
        {"monthly_budget_cap": -1},
        {"weekly_hours_cap": float("inf")},
        {"strategic_priority": 6},
    ):
        try:
            store.add_venture("Invalid", **kwargs)
            assert False, "invalid venture data should be rejected"
        except ValueError:
            pass


def test_venture_status_can_be_changed(tmp_path):
    store = SageStore(tmp_path / "status.db")
    venture = store.add_venture("ABSE.INC")
    store.set_venture_status(venture, "paused")
    assert store.list_ventures()[0]["status"] == "paused"


def test_existing_database_gets_venture_column_without_losing_projects(tmp_path):
    import sqlite3

    database = tmp_path / "legacy.db"
    with sqlite3.connect(database) as connection:
        connection.execute(
            """CREATE TABLE projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                description TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'active',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )"""
        )
        connection.execute(
            "INSERT INTO projects (name, description) VALUES ('Legacy project', 'keep me')"
        )
    store = SageStore(database)
    legacy = store.list_projects()[0]
    assert legacy["name"] == "Legacy project"
    assert legacy["venture_id"] is None
    venture = store.add_venture("Migrated portfolio")
    store.assign_project_to_venture(legacy["id"], venture)
    assert store.portfolio_summary()["ventures"][0]["projects"] == 1
