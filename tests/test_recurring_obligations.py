from datetime import date

import pytest

from sage.core import SageStore


def test_recurring_payable_generates_open_obligations_without_auto_payment(tmp_path):
    store = SageStore(tmp_path / "recurring-payables.db")
    venture = store.add_venture("Office")
    rule = store.add_recurring_obligation(
        venture, "payable", 12000, "Office rent", "monthly",
        start_date="2026-11-01",
    )
    created = store.generate_recurring_obligations(through=date(2026, 12, 1))
    assert len(created) == 2
    assert [item["due_date"] for item in created] == ["2026-11-01", "2026-12-01"]
    assert len(store.list_obligations("open")) == 2
    assert store.list_resource_entries() == []
    assert store.list_recurring_obligations()[0]["id"] == rule
    assert store.list_recurring_obligations()[0]["next_due_date"] == "2027-01-01"


def test_recurring_income_generates_receivables_not_actual_income(tmp_path):
    store = SageStore(tmp_path / "recurring-income.db")
    venture = store.add_venture("Retainer")
    store.add_recurring_obligation(
        venture, "receivable", 30000, "Monthly retainer", "monthly",
        start_date="2026-11-01",
    )
    created = store.generate_recurring_obligations(through=date(2026, 11, 1))
    assert len(created) == 1
    assert store.list_obligations("open")[0]["obligation_type"] == "receivable"
    assert store.portfolio_summary(today=date(2026, 11, 1))["ventures"][0]["month_revenue"] == 0


def test_paused_recurring_financial_rule_does_not_generate(tmp_path):
    store = SageStore(tmp_path / "paused-recurring-finance.db")
    venture = store.add_venture("Paused venture")
    rule = store.add_recurring_obligation(
        venture, "payable", 5000, "Monthly cost", start_date="2026-11-01"
    )
    store.set_recurring_obligation_status(rule, "paused")
    assert store.generate_recurring_obligations(through=date(2026, 11, 30)) == []
    assert store.list_obligations() == []


def test_recurring_financial_rules_validate_values(tmp_path):
    store = SageStore(tmp_path / "recurring-finance-validation.db")
    venture = store.add_venture("Validation")
    with pytest.raises(ValueError):
        store.add_recurring_obligation(venture, "payable", 0, "Invalid")
    with pytest.raises(ValueError):
        store.add_recurring_obligation(venture, "other", 10, "Invalid")
    with pytest.raises(ValueError):
        store.add_recurring_obligation(venture, "payable", 10, "", "monthly")
    with pytest.raises(ValueError):
        store.add_recurring_obligation(venture, "payable", 10, "Invalid", "yearly")
