from datetime import date

from sage.core import SageStore


def test_overdue_obligations_are_not_double_counted_in_forward_cash_forecast(tmp_path):
    store = SageStore(tmp_path / "forecast-boundaries.db")
    venture = store.add_venture("Forecast integrity")
    store.set_cash_position(venture, 10000, "2026-11-20")
    store.add_obligation(venture, "receivable", 3000, "2026-11-19", "Already overdue")
    store.add_obligation(venture, "payable", 2000, "2026-11-21", "Past due")
    store.add_obligation(venture, "receivable", 1500, "2026-11-25", "Future receivable")
    store.add_obligation(venture, "payable", 500, "2026-11-28", "Future payable")

    item = store.portfolio_summary(today=date(2026, 11, 23))["ventures"][0]
    assert item["overdue_receivables"] == 3000
    assert item["overdue_payables"] == 2000
    assert item["receivables_due_30d"] == 1500
    assert item["payables_due_30d"] == 500
    assert item["estimated_cash_balance"] == 10000
    assert item["forecast_cash_balance_30d"] == 11000


def test_future_dated_cash_position_does_not_create_present_cash_estimate(tmp_path):
    store = SageStore(tmp_path / "future-cash.db")
    venture = store.add_venture("Future cash")
    store.set_cash_position(venture, 25000, "2026-11-30", "Future-dated statement")
    item = store.portfolio_summary(today=date(2026, 11, 23))["ventures"][0]
    assert item["cash_position_date"] == "2026-11-30"
    assert item["cash_opening_balance"] == 25000
    assert item["estimated_cash_balance"] is None
    assert item["forecast_cash_balance_30d"] is None


def test_venture_status_filter_uses_venture_status(tmp_path):
    store = SageStore(tmp_path / "venture-filter.db")
    active = store.add_venture("Active")
    paused = store.add_venture("Paused")
    store.set_venture_status(paused, "paused")
    assert [item["id"] for item in store.list_ventures("active")] == [active]
    assert [item["id"] for item in store.list_ventures("paused")] == [paused]
