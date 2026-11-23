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


def test_resource_logs_calculate_monthly_spend_and_weekly_hours(tmp_path):
    from datetime import date

    store = SageStore(tmp_path / "usage.db")
    venture = store.add_venture(
        "OPERONIX AI", monthly_budget_cap=20000, weekly_hours_cap=20
    )
    project = store.add_project("Client automation", venture_id=venture)
    store.log_resource(venture, "expense", 4500, "2026-11-05", project, "Software")
    store.log_resource(venture, "expense", 1500, "2026-10-31", project, "Prior month")
    store.log_resource(venture, "time", 6.5, "2026-11-23", project, "Build")
    store.log_resource(venture, "time", 4, "2026-11-16", project, "Prior week")
    summary = store.portfolio_summary(today=date(2026, 11, 23))
    item = summary["ventures"][0]
    assert item["month_spend"] == 4500
    assert item["month_budget_remaining"] == 15500
    assert item["week_hours_used"] == 6.5
    assert item["week_hours_remaining"] == 13.5
    assert len(store.list_resource_entries(venture)) == 4


def test_resource_log_rejects_project_from_another_venture(tmp_path):
    store = SageStore(tmp_path / "resource-link.db")
    first = store.add_venture("First")
    second = store.add_venture("Second")
    project = store.add_project("First project", venture_id=first)
    try:
        store.log_resource(second, "expense", 100, project_id=project)
        assert False, "cross-venture resource assignment must fail"
    except ValueError as error:
        assert "belong" in str(error)


def test_resource_log_rejects_zero_or_invalid_quantity(tmp_path):
    store = SageStore(tmp_path / "resource-validation.db")
    venture = store.add_venture("Validation")
    for amount in (0, -2, float("nan")):
        try:
            store.log_resource(venture, "time", amount)
            assert False, "invalid resource quantity must fail"
        except ValueError:
            pass


def test_allocation_signal_uses_priority_and_actual_cap_usage(tmp_path):
    from datetime import date

    store = SageStore(tmp_path / "signals.db")
    priority = store.add_venture(
        "Priority venture", monthly_budget_cap=10000, weekly_hours_cap=10,
        strategic_priority=1,
    )
    project = store.add_project("Approved work", venture_id=priority)
    store.add_task(project, "Next action")
    store.log_resource(priority, "expense", 2500, "2026-11-23")
    store.log_resource(priority, "time", 3, "2026-11-23")

    signal = store.portfolio_summary(today=date(2026, 11, 23))["ventures"][0]["allocation_signal"]
    assert "Highest user-set priority" in signal
    assert "cap headroom" in signal

    store.log_resource(priority, "expense", 9000, "2026-11-23")
    signal = store.portfolio_summary(today=date(2026, 11, 23))["ventures"][0]["allocation_signal"]
    assert "cap exceeded" in signal


def test_income_ledger_calculates_monthly_net_cash_flow(tmp_path):
    from datetime import date

    store = SageStore(tmp_path / "income.db")
    venture = store.add_venture("Revenue venture", monthly_budget_cap=10000)
    project = store.add_project("Paid service", venture_id=venture)
    store.log_income(venture, 18000, "2026-11-23", project, "Client invoice paid")
    store.log_resource(venture, "expense", 6500, "2026-11-23", project, "Delivery cost")
    summary = store.portfolio_summary(today=date(2026, 11, 23))["ventures"][0]
    assert summary["month_revenue"] == 18000
    assert summary["month_spend"] == 6500
    assert summary["month_net_cash_flow"] == 11500
    entries = store.list_resource_entries(venture)
    assert {entry["entry_type"] for entry in entries} == {"income", "expense"}


def test_project_next_actions_selects_one_per_active_project(tmp_path):
    store = SageStore(tmp_path / "daily-actions.db")
    venture = store.add_venture("Priority venture", strategic_priority=1)
    first = store.add_project("First project", venture_id=venture)
    second = store.add_project("Second project", venture_id=venture)
    paused = store.add_project("Paused project", venture_id=venture)
    store.set_project_status(paused, "paused")
    store.add_task(first, "High priority todo", priority=1)
    store.add_task(first, "Already in progress", priority=4)
    store.set_task_status(2, "in_progress")

    actions = store.project_next_actions()
    assert len(actions) == 2
    assert actions[0]["project_name"] == "First project"
    assert actions[0]["task_title"] == "Already in progress"
    assert actions[1]["project_name"] == "Second project"
    assert actions[1]["task_id"] is None


def test_allocation_readiness_distinguishes_missing_data_from_review_ready(tmp_path):
    from datetime import date

    store = SageStore(tmp_path / "allocation-readiness.db")
    ready = store.add_venture(
        "Ready", monthly_budget_cap=5000, weekly_hours_cap=12,
        strategic_priority=1,
    )
    ready_project = store.add_project("Ready project", venture_id=ready)
    store.add_task(ready_project, "Approved next step")
    store.set_cash_position(ready, 20000, "2026-11-23", "Bank statement")

    incomplete = store.add_venture("Incomplete")
    incomplete_project = store.add_project("Incomplete project", venture_id=incomplete)
    store.add_task(incomplete_project, "Gather data")

    items = {
        item["name"]: item
        for item in store.portfolio_summary(today=date(2026, 11, 23))["ventures"]
    }
    assert items["Ready"]["allocation_readiness"] == "ready_for_review"
    assert items["Ready"]["allocation_blockers"] == []
    assert items["Ready"]["allocation_data_gaps"] == []
    assert items["Incomplete"]["allocation_readiness"] == "needs_data"
    assert "monthly budget cap" in items["Incomplete"]["allocation_data_gaps"]
    assert "verified cash position" in items["Incomplete"]["allocation_data_gaps"]


def test_allocation_readiness_holds_when_recorded_budget_cap_is_exceeded(tmp_path):
    from datetime import date

    store = SageStore(tmp_path / "allocation-hold.db")
    venture = store.add_venture(
        "Over-cap", monthly_budget_cap=100, weekly_hours_cap=10
    )
    project = store.add_project("Delivery", venture_id=venture)
    store.add_task(project, "Deliver customer work")
    store.set_cash_position(venture, 10000, "2026-11-23")
    store.log_resource(venture, "expense", 150, "2026-11-23")

    item = store.portfolio_summary(today=date(2026, 11, 23))["ventures"][0]
    assert item["allocation_readiness"] == "hold"
    assert "recorded resource cap exceeded" in item["allocation_blockers"]
