from datetime import date

from sage.core import SageStore


def test_daily_recurring_rule_generates_due_tasks_and_advances_next_date(tmp_path):
    store = SageStore(tmp_path / "recurring.db")
    project = store.add_project("Daily operations")
    rule = store.add_recurring_task(
        project, "Review lead pipeline", priority=1, frequency="daily",
        start_date="2026-11-20",
    )
    created = store.generate_recurring_tasks(through=date(2026, 11, 23))
    assert len(created) == 4
    assert [item["due_date"] for item in created] == [
        "2026-11-20", "2026-11-21", "2026-11-22", "2026-11-23"
    ]
    assert store.list_recurring_tasks()[0]["id"] == rule
    assert store.list_recurring_tasks()[0]["next_due_date"] == "2026-11-24"
    assert store.generate_recurring_tasks(through=date(2026, 11, 23)) == []
    assert len(store.list_tasks()) == 4


def test_recurring_generation_respects_frequency_interval_and_limit(tmp_path):
    store = SageStore(tmp_path / "recurring-limit.db")
    project = store.add_project("Weekly operations")
    store.add_recurring_task(
        project, "Weekly review", frequency="weekly", frequency_interval=2,
        start_date="2026-11-01",
    )
    created = store.generate_recurring_tasks(through=date(2026, 11, 30), limit=1)
    assert len(created) == 1
    assert created[0]["due_date"] == "2026-11-01"
    assert store.list_recurring_tasks()[0]["next_due_date"] == "2026-11-15"
    created_again = store.generate_recurring_tasks(through=date(2026, 11, 30), limit=5)
    assert [item["due_date"] for item in created_again] == ["2026-11-15", "2026-11-29"]


def test_paused_rules_and_paused_projects_do_not_generate(tmp_path):
    store = SageStore(tmp_path / "recurring-paused.db")
    active_project = store.add_project("Active")
    paused_project = store.add_project("Paused")
    store.set_project_status(paused_project, "paused")
    active_rule = store.add_recurring_task(active_project, "Active routine", start_date="2026-11-20")
    paused_rule = store.add_recurring_task(paused_project, "Paused routine", start_date="2026-11-20")
    store.set_recurring_task_status(active_rule, "paused")

    assert store.generate_recurring_tasks(through=date(2026, 11, 23)) == []
    assert store.list_tasks() == []
    assert store.list_recurring_tasks()[0]["status"] == "paused"
    assert store.list_recurring_tasks()[1]["status"] == "active"


def test_monthly_recurring_rule_clamps_invalid_month_days(tmp_path):
    store = SageStore(tmp_path / "monthly.db")
    project = store.add_project("Monthly close")
    store.add_recurring_task(
        project, "Month end close", frequency="monthly", start_date="2026-01-31"
    )
    created = store.generate_recurring_tasks(through=date(2026, 3, 31))
    assert [item["due_date"] for item in created] == [
        "2026-01-31", "2026-02-28", "2026-03-28"
    ]


def test_recurring_rules_validate_inputs(tmp_path):
    store = SageStore(tmp_path / "recurring-validation.db")
    project = store.add_project("Validation")
    for kwargs in (
        {"frequency": "yearly"},
        {"frequency_interval": 0},
        {"priority": 6},
        {"start_date": "tomorrow"},
    ):
        try:
            store.add_recurring_task(project, "Invalid", **kwargs)
            assert False, "invalid recurring rule must be rejected"
        except ValueError:
            pass
