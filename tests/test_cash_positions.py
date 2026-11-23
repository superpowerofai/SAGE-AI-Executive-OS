from datetime import date

import pytest

from sage.core import SageStore


def test_manual_cash_position_and_30_day_cash_forecast(tmp_path):
    store = SageStore(tmp_path / "cash-position.db")
    venture = store.add_venture("Cash-flow venture")
    store.set_cash_position(venture, 10000, "2026-11-22", "Verified closing balance")
    store.log_income(venture, 5000, "2026-11-23", note="Paid invoice")
    store.log_resource(venture, "expense", 3000, "2026-11-23", note="Delivery cost")
    store.add_obligation(venture, "receivable", 2000, "2026-11-25", "Invoice due")
    store.add_obligation(venture, "payable", 4000, "2026-11-27", "Supplier due")

    summary = store.portfolio_summary(today=date(2026, 11, 23))["ventures"][0]
    assert summary["cash_position_date"] == "2026-11-22"
    assert summary["cash_opening_balance"] == 10000
    assert summary["estimated_cash_balance"] == 12000
    assert summary["expected_obligation_cashflow_30d"] == -2000
    assert summary["forecast_cash_balance_30d"] == 10000
    assert store.list_cash_positions()[0]["note"] == "Verified closing balance"


def test_cash_forecast_remains_unknown_without_manual_opening_balance(tmp_path):
    store = SageStore(tmp_path / "unknown-cash.db")
    venture = store.add_venture("Unknown cash")
    summary = store.portfolio_summary()["ventures"][0]
    assert summary["estimated_cash_balance"] is None
    assert summary["forecast_cash_balance_30d"] is None


def test_cash_position_validation_and_upsert(tmp_path):
    store = SageStore(tmp_path / "cash-validation.db")
    venture = store.add_venture("Cash validation")
    with pytest.raises(ValueError):
        store.set_cash_position(venture, float("nan"), "2026-11-23")
    with pytest.raises(ValueError):
        store.set_cash_position(venture, 100, "not-a-date")
    store.set_cash_position(venture, 100, "2026-11-20", "First")
    store.set_cash_position(venture, 250, "2026-11-23", "Updated")
    positions = store.list_cash_positions()
    assert len(positions) == 1
    assert positions[0]["opening_balance"] == 250
    assert positions[0]["note"] == "Updated"
    store.set_cash_position(venture, -250, "2026-11-24", "Overdraft")
    assert store.list_cash_positions()[0]["opening_balance"] == -250


def test_future_dated_cash_position_is_not_used_for_an_earlier_report(tmp_path):
    store = SageStore(tmp_path / "future-cash.db")
    venture = store.add_venture("Future cash")
    store.set_cash_position(venture, 50000, "2026-11-25", "Future balance")
    summary = store.portfolio_summary(today=date(2026, 11, 23))["ventures"][0]
    assert summary["cash_position_date"] == "2026-11-25"
    assert summary["estimated_cash_balance"] is None
    assert summary["forecast_cash_balance_30d"] is None
