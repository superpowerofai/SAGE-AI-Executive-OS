from datetime import date

import pytest

from sage.core import SageStore


def test_obligations_forecast_and_settlement_posts_actual_ledger_entries(tmp_path):
    store = SageStore(tmp_path / "obligations.db")
    venture = store.add_venture("Services")
    project = store.add_project("Client delivery", venture_id=venture)
    receivable = store.add_obligation(
        venture, "receivable", 25000, "2026-11-25", "Client invoice", project
    )
    payable = store.add_obligation(
        venture, "payable", 8000, "2026-11-27", "Contractor payment", project
    )

    before = store.portfolio_summary(today=date(2026, 11, 23))["ventures"][0]
    assert before["open_receivables"] == 25000
    assert before["open_payables"] == 8000
    assert before["receivables_due_30d"] == 25000
    assert before["payables_due_30d"] == 8000
    assert before["expected_obligation_cashflow_30d"] == 17000
    assert store.list_resource_entries(venture) == []

    store.settle_obligation(receivable, "2026-11-24")
    store.settle_obligation(payable, "2026-11-24")
    assert store.list_resource_entries(venture)[0]["entry_type"] in {"income", "expense"}
    assert {entry["entry_type"] for entry in store.list_resource_entries(venture)} == {
        "income", "expense"
    }

    after = store.portfolio_summary(today=date(2026, 11, 24))["ventures"][0]
    assert after["open_receivables"] == 0
    assert after["open_payables"] == 0
    assert after["month_revenue"] == 25000
    assert after["month_spend"] == 8000
    assert after["month_net_cash_flow"] == 17000
    assert {item["status"] for item in store.list_obligations()} == {"settled"}


def test_obligations_can_be_cancelled_without_posting_actuals(tmp_path):
    store = SageStore(tmp_path / "cancel-obligation.db")
    venture = store.add_venture("Cancelled")
    obligation = store.add_obligation(
        venture, "payable", 1500, "2026-11-30", "Cancelled supplier bill"
    )
    store.cancel_obligation(obligation)
    assert store.list_obligations("cancelled")[0]["id"] == obligation
    assert store.list_resource_entries() == []


def test_obligation_validation_and_cross_venture_project_guard(tmp_path):
    store = SageStore(tmp_path / "obligation-validation.db")
    one = store.add_venture("One")
    two = store.add_venture("Two")
    project = store.add_project("One project", venture_id=one)
    with pytest.raises(ValueError):
        store.add_obligation(two, "receivable", 100, "2026-11-30", "Wrong project", project)
    with pytest.raises(ValueError):
        store.add_obligation(one, "receivable", 0, "2026-11-30", "Zero")
    with pytest.raises(ValueError):
        store.add_obligation(one, "payable", 100, "not-a-date", "Invalid date")
    with pytest.raises(ValueError):
        store.add_obligation(one, "other", 100, "2026-11-30", "Invalid type")
