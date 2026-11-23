"""Core local-first project and task operations for SAGE.

This module deliberately uses only the Python standard library.
It stores data in a SQLite database on the user's machine.
"""
from __future__ import annotations

import calendar
import json
import math
import os
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator


SCHEMA = """
CREATE TABLE IF NOT EXISTS ventures (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    description TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'paused', 'completed')),
    monthly_budget_cap REAL,
    weekly_hours_cap REAL,
    strategic_priority INTEGER NOT NULL DEFAULT 3
        CHECK (strategic_priority BETWEEN 1 AND 5),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    description TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'paused', 'completed')),
    venture_id INTEGER REFERENCES ventures(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS blockers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    details TEXT NOT NULL DEFAULT '',
    project_id INTEGER,
    task_id INTEGER,
    status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'resolved')),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    resolved_at TEXT,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE SET NULL,
    FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    decision_date TEXT NOT NULL,
    title TEXT NOT NULL,
    context TEXT NOT NULL DEFAULT '',
    choice TEXT NOT NULL,
    rationale TEXT NOT NULL DEFAULT '',
    revisit_date TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS daily_reviews (
    review_date TEXT PRIMARY KEY,
    priority TEXT NOT NULL DEFAULT '',
    wins TEXT NOT NULL DEFAULT '',
    blockers TEXT NOT NULL DEFAULT '',
    tomorrow TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    priority INTEGER NOT NULL DEFAULT 3
        CHECK (priority BETWEEN 1 AND 5),
    status TEXT NOT NULL DEFAULT 'todo'
        CHECK (status IN ('todo', 'in_progress', 'done')),
    due_date TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS recurring_obligations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    venture_id INTEGER NOT NULL,
    project_id INTEGER,
    obligation_type TEXT NOT NULL CHECK (obligation_type IN ('receivable', 'payable')),
    amount REAL NOT NULL CHECK (amount > 0),
    description TEXT NOT NULL,
    frequency TEXT NOT NULL CHECK (frequency IN ('daily', 'weekly', 'monthly')),
    frequency_interval INTEGER NOT NULL DEFAULT 1 CHECK (frequency_interval BETWEEN 1 AND 365),
    next_due_date TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'paused', 'completed')),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (venture_id) REFERENCES ventures(id) ON DELETE CASCADE,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS financial_obligations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    venture_id INTEGER NOT NULL,
    project_id INTEGER,
    obligation_type TEXT NOT NULL CHECK (obligation_type IN ('receivable', 'payable')),
    amount REAL NOT NULL CHECK (amount > 0),
    due_date TEXT NOT NULL,
    description TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'settled', 'cancelled')),
    settled_date TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (venture_id) REFERENCES ventures(id) ON DELETE CASCADE,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS task_proposals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    rationale TEXT NOT NULL DEFAULT '',
    priority INTEGER NOT NULL DEFAULT 3 CHECK (priority BETWEEN 1 AND 5),
    due_date TEXT,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected')),
    approved_task_id INTEGER,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    decided_at TEXT,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
    FOREIGN KEY (approved_task_id) REFERENCES tasks(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS recurring_tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    priority INTEGER NOT NULL DEFAULT 3 CHECK (priority BETWEEN 1 AND 5),
    frequency TEXT NOT NULL CHECK (frequency IN ('daily', 'weekly', 'monthly')),
    frequency_interval INTEGER NOT NULL DEFAULT 1 CHECK (frequency_interval BETWEEN 1 AND 365),
    next_due_date TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'paused', 'completed')),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS resource_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    venture_id INTEGER NOT NULL,
    project_id INTEGER,
    entry_type TEXT NOT NULL CHECK (entry_type IN ('expense', 'time')),
    quantity REAL NOT NULL CHECK (quantity > 0),
    entry_date TEXT NOT NULL,
    note TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (venture_id) REFERENCES ventures(id) ON DELETE CASCADE,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS income_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    venture_id INTEGER NOT NULL,
    project_id INTEGER,
    amount REAL NOT NULL CHECK (amount > 0),
    entry_date TEXT NOT NULL,
    note TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (venture_id) REFERENCES ventures(id) ON DELETE CASCADE,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE SET NULL
);

"""


class SageStore:
    """Small SQLite-backed store for projects and their next actions."""

    def __init__(self, database: str | Path = "sage.db") -> None:
        database_path = Path(database).expanduser()
        if str(database) != ":memory:":
            database_path.parent.mkdir(parents=True, exist_ok=True)
        self.database = str(database_path)
        with self._connect() as connection:
            connection.executescript(SCHEMA)
            project_columns = {
                row["name"] for row in connection.execute("PRAGMA table_info(projects)")
            }
            if "venture_id" not in project_columns:
                connection.execute(
                    "ALTER TABLE projects ADD COLUMN venture_id INTEGER "
                    "REFERENCES ventures(id) ON DELETE SET NULL"
                )

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        """Open a transaction-scoped connection and always close its handle."""
        connection = sqlite3.connect(self.database)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
        except Exception:
            connection.rollback()
            raise
        else:
            connection.commit()
        finally:
            connection.close()


    @staticmethod
    def _optional_nonnegative_number(value: float | None, label: str) -> float | None:
        if value is None:
            return None
        number = float(value)
        if not math.isfinite(number) or number < 0:
            raise ValueError(f"{label} must be a finite non-negative number.")
        return number

    def add_venture(
        self, name: str, description: str = "",
        monthly_budget_cap: float | None = None,
        weekly_hours_cap: float | None = None,
        strategic_priority: int = 3,
    ) -> int:
        name = name.strip()
        if not name:
            raise ValueError("Venture name cannot be empty.")
        if strategic_priority not in range(1, 6):
            raise ValueError("Strategic priority must be between 1 (highest) and 5 (lowest).")
        budget = self._optional_nonnegative_number(monthly_budget_cap, "Monthly budget cap")
        hours = self._optional_nonnegative_number(weekly_hours_cap, "Weekly hours cap")
        with self._connect() as connection:
            cursor = connection.execute(
                """INSERT INTO ventures
                   (name, description, monthly_budget_cap, weekly_hours_cap, strategic_priority)
                   VALUES (?, ?, ?, ?, ?)""",
                (name, description.strip(), budget, hours, strategic_priority),
            )
            return int(cursor.lastrowid)

    def list_ventures(self, status: str | None = None) -> list[dict[str, Any]]:
        query = "SELECT * FROM ventures"
        values: tuple[Any, ...] = ()
        if status is not None:
            if status not in {"active", "paused", "completed"}:
                raise ValueError("Invalid venture status.")
            query += " WHERE projects.status = ?"
            values = (status,)
        query += " ORDER BY strategic_priority, created_at, id"
        with self._connect() as connection:
            return [dict(row) for row in connection.execute(query, values)]

    def set_venture_status(self, venture_id: int, status: str) -> None:
        if status not in {"active", "paused", "completed"}:
            raise ValueError("Status must be active, paused, or completed.")
        with self._connect() as connection:
            cursor = connection.execute(
                "UPDATE ventures SET status = ? WHERE id = ?", (status, venture_id)
            )
            if cursor.rowcount == 0:
                raise ValueError(f"Venture {venture_id} does not exist.")

    def assign_project_to_venture(self, project_id: int, venture_id: int | None) -> None:
        with self._connect() as connection:
            if venture_id is not None and connection.execute(
                "SELECT 1 FROM ventures WHERE id = ?", (venture_id,)
            ).fetchone() is None:
                raise ValueError(f"Venture {venture_id} does not exist.")
            cursor = connection.execute(
                "UPDATE projects SET venture_id = ? WHERE id = ?", (venture_id, project_id)
            )
            if cursor.rowcount == 0:
                raise ValueError(f"Project {project_id} does not exist.")


    def log_resource(
        self, venture_id: int, entry_type: str, quantity: float,
        entry_date: str | None = None, project_id: int | None = None, note: str = "",
    ) -> int:
        """Record actual rupee expense or hours worked against a venture."""
        if entry_type not in {"expense", "time"}:
            raise ValueError("Resource entry type must be expense or time.")
        amount = self._optional_nonnegative_number(quantity, "Resource quantity")
        if amount is None or amount <= 0:
            raise ValueError("Resource quantity must be greater than zero.")
        day = entry_date or date.today().isoformat()
        try:
            date.fromisoformat(day)
        except ValueError as error:
            raise ValueError("Entry date must use YYYY-MM-DD format.") from error
        with self._connect() as connection:
            if connection.execute(
                "SELECT 1 FROM ventures WHERE id = ?", (venture_id,)
            ).fetchone() is None:
                raise ValueError(f"Venture {venture_id} does not exist.")
            if project_id is not None:
                project = connection.execute(
                    "SELECT venture_id FROM projects WHERE id = ?", (project_id,)
                ).fetchone()
                if project is None:
                    raise ValueError(f"Project {project_id} does not exist.")
                if project["venture_id"] != venture_id:
                    raise ValueError("Linked project must belong to the selected venture.")
            cursor = connection.execute(
                """INSERT INTO resource_entries
                   (venture_id, project_id, entry_type, quantity, entry_date, note)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (venture_id, project_id, entry_type, amount, day, note.strip()),
            )
            return int(cursor.lastrowid)


    def log_income(
        self, venture_id: int, amount: float, entry_date: str | None = None,
        project_id: int | None = None, note: str = "",
    ) -> int:
        """Record actual income in INR against a venture."""
        value = self._optional_nonnegative_number(amount, "Income amount")
        if value is None or value <= 0:
            raise ValueError("Income amount must be greater than zero.")
        day = entry_date or date.today().isoformat()
        try:
            date.fromisoformat(day)
        except ValueError as error:
            raise ValueError("Income date must use YYYY-MM-DD format.") from error
        with self._connect() as connection:
            if connection.execute(
                "SELECT 1 FROM ventures WHERE id = ?", (venture_id,)
            ).fetchone() is None:
                raise ValueError(f"Venture {venture_id} does not exist.")
            if project_id is not None:
                project = connection.execute(
                    "SELECT venture_id FROM projects WHERE id = ?", (project_id,)
                ).fetchone()
                if project is None or project["venture_id"] != venture_id:
                    raise ValueError("Linked project must belong to the selected venture.")
            cursor = connection.execute(
                """INSERT INTO income_entries
                   (venture_id, project_id, amount, entry_date, note)
                   VALUES (?, ?, ?, ?, ?)""",
                (venture_id, project_id, value, day, note.strip()),
            )
            return int(cursor.lastrowid)

    def list_resource_entries(
        self, venture_id: int | None = None, limit: int = 100
    ) -> list[dict[str, Any]]:
        if not 1 <= limit <= 1000:
            raise ValueError("Resource entry limit must be between 1 and 1000.")
        query = """SELECT resource_entries.*, ventures.name AS venture_name,
                          projects.name AS project_name
                   FROM resource_entries
                   JOIN ventures ON ventures.id = resource_entries.venture_id
                   LEFT JOIN projects ON projects.id = resource_entries.project_id"""
        values: tuple[Any, ...] = ()
        if venture_id is not None:
            query += " WHERE resource_entries.venture_id = ?"
            values = (venture_id,)
        query += " ORDER BY entry_date DESC, id DESC LIMIT ?"
        values += (limit,)
        with self._connect() as connection:
            entries = [dict(row) for row in connection.execute(query, values)]
            income_query = """SELECT income_entries.id, income_entries.venture_id,
                                     income_entries.project_id, 'income' AS entry_type,
                                     income_entries.amount AS quantity, income_entries.entry_date,
                                     income_entries.note, income_entries.created_at,
                                     ventures.name AS venture_name, projects.name AS project_name
                              FROM income_entries
                              JOIN ventures ON ventures.id = income_entries.venture_id
                              LEFT JOIN projects ON projects.id = income_entries.project_id"""
            income_values: tuple[Any, ...] = ()
            if venture_id is not None:
                income_query += " WHERE income_entries.venture_id = ?"
                income_values = (venture_id,)
            income_query += " ORDER BY income_entries.entry_date DESC, income_entries.id DESC LIMIT ?"
            income_values += (limit,)
            entries.extend(dict(row) for row in connection.execute(income_query, income_values))
        entries.sort(key=lambda item: (item["entry_date"], item["id"]), reverse=True)
        return entries[:limit]

    def portfolio_summary(self, today: date | None = None) -> dict[str, Any]:
        """Summarize venture ownership and explicitly entered resource caps."""
        ventures = self.list_ventures()
        as_of = today or date.today()
        month_start = as_of.replace(day=1).isoformat()
        week_start = (as_of - timedelta(days=as_of.weekday())).isoformat()
        forecast_end = (as_of + timedelta(days=30)).isoformat()
        with self._connect() as connection:
            summaries = []
            for venture in ventures:
                row = connection.execute(
                    """SELECT COUNT(DISTINCT p.id) AS projects,
                              COUNT(DISTINCT CASE WHEN p.status = 'active' THEN p.id END) AS active_projects,
                              SUM(CASE WHEN t.status != 'done' THEN 1 ELSE 0 END) AS open_tasks,
                              SUM(CASE WHEN t.status = 'in_progress' THEN 1 ELSE 0 END) AS in_progress_tasks
                       FROM projects p LEFT JOIN tasks t ON t.project_id = p.id
                       WHERE p.venture_id = ?""",
                    (venture["id"],),
                ).fetchone()
                usage = connection.execute(
                    """SELECT
                         COALESCE(SUM(CASE WHEN entry_type = 'expense'
                           AND entry_date BETWEEN ? AND ? THEN quantity ELSE 0 END), 0) AS month_spend,
                         COALESCE(SUM(CASE WHEN entry_type = 'time'
                           AND entry_date BETWEEN ? AND ? THEN quantity ELSE 0 END), 0) AS week_hours
                       FROM resource_entries WHERE venture_id = ?""",
                    (month_start, as_of.isoformat(), week_start, as_of.isoformat(), venture["id"]),
                ).fetchone()
                month_spend = float(usage["month_spend"])
                week_hours = float(usage["week_hours"])
                income_usage = connection.execute(
                    """SELECT COALESCE(SUM(amount), 0) FROM income_entries
                       WHERE venture_id = ? AND entry_date BETWEEN ? AND ?""",
                    (venture["id"], month_start, as_of.isoformat()),
                ).fetchone()[0]
                month_revenue = float(income_usage)
                obligations = connection.execute(
                    """SELECT
                         COALESCE(SUM(CASE WHEN obligation_type = 'receivable'
                           AND status = 'open' THEN amount ELSE 0 END), 0) AS receivables,
                         COALESCE(SUM(CASE WHEN obligation_type = 'payable'
                           AND status = 'open' THEN amount ELSE 0 END), 0) AS payables,
                         COALESCE(SUM(CASE WHEN obligation_type = 'receivable'
                           AND status = 'open' AND due_date BETWEEN ? AND ? THEN amount ELSE 0 END), 0) AS due_receivables,
                         COALESCE(SUM(CASE WHEN obligation_type = 'payable'
                           AND status = 'open' AND due_date BETWEEN ? AND ? THEN amount ELSE 0 END), 0) AS due_payables,
                         COALESCE(SUM(CASE WHEN obligation_type = 'receivable'
                           AND status = 'open' AND due_date < ? THEN amount ELSE 0 END), 0) AS overdue_receivables,
                         COALESCE(SUM(CASE WHEN obligation_type = 'payable'
                           AND status = 'open' AND due_date < ? THEN amount ELSE 0 END), 0) AS overdue_payables
                       FROM financial_obligations WHERE venture_id = ?""",
                    (as_of.isoformat(), forecast_end, as_of.isoformat(), forecast_end,
                     as_of.isoformat(), as_of.isoformat(), venture["id"]),
                ).fetchone()
                open_receivables = float(obligations["receivables"])
                open_payables = float(obligations["payables"])
                due_receivables_30d = float(obligations["due_receivables"])
                due_payables_30d = float(obligations["due_payables"])
                overdue_receivables = float(obligations["overdue_receivables"])
                overdue_payables = float(obligations["overdue_payables"])
                budget_cap = venture["monthly_budget_cap"]
                hours_cap = venture["weekly_hours_cap"]
                active_projects = int(row["active_projects"] or 0)
                open_tasks = int(row["open_tasks"] or 0)
                budget_remaining = budget_cap - month_spend if budget_cap is not None else None
                hours_remaining = hours_cap - week_hours if hours_cap is not None else None
                missing_caps = []
                if budget_cap is None:
                    missing_caps.append("monthly budget")
                if hours_cap is None:
                    missing_caps.append("weekly hours")
                if venture["status"] != "active":
                    signal = "Inactive venture: exclude from new resource allocation."
                elif (budget_remaining is not None and budget_remaining < 0) or (
                    hours_remaining is not None and hours_remaining < 0
                ):
                    signal = "Recorded cap exceeded: review commitments before adding resources."
                elif overdue_payables > 0:
                    signal = "Open payables are overdue; review settlement before adding new commitments."
                elif due_payables_30d > due_receivables_30d:
                    signal = "Recorded payables due within 30 days exceed recorded receivables; cash balance is unknown, so review liquidity before new commitments."
                elif active_projects == 0:
                    signal = "No active projects: decide whether to start work or keep this venture paused."
                elif venture["strategic_priority"] == 1 and missing_caps:
                    signal = "Highest user-set priority; capacity is unknown until " + " and ".join(missing_caps) + " cap(s) are entered."
                elif venture["strategic_priority"] == 1:
                    signal = "Highest user-set priority with recorded cap headroom: consider its next approved action."
                else:
                    signal = "Continue current execution; compare outcomes before increasing allocation."
                summaries.append({
                    **venture,
                    "projects": int(row["projects"] or 0),
                    "active_projects": active_projects,
                    "open_tasks": open_tasks,
                    "in_progress_tasks": int(row["in_progress_tasks"] or 0),
                    "month_spend": month_spend,
                    "month_revenue": month_revenue,
                    "month_net_cash_flow": month_revenue - month_spend,
                    "open_receivables": open_receivables,
                    "open_payables": open_payables,
                    "receivables_due_30d": due_receivables_30d,
                    "payables_due_30d": due_payables_30d,
                    "overdue_receivables": overdue_receivables,
                    "overdue_payables": overdue_payables,
                    "expected_obligation_cashflow_30d": due_receivables_30d - due_payables_30d,
                    "month_budget_remaining": budget_remaining,
                    "week_hours_used": week_hours,
                    "week_hours_remaining": hours_remaining,
                    "allocation_signal": signal,
                })
            unassigned = connection.execute(
                "SELECT COUNT(*) FROM projects WHERE venture_id IS NULL"
            ).fetchone()[0]
        return {
            "ventures": summaries,
            "unassigned_projects": int(unassigned),
            "known_monthly_budget_caps": sum(
                item["monthly_budget_cap"] or 0 for item in summaries
                if item["monthly_budget_cap"] is not None
            ),
            "budget_cap_entries": sum(
                item["monthly_budget_cap"] is not None for item in summaries
            ),
            "known_weekly_hours_caps": sum(
                item["weekly_hours_cap"] or 0 for item in summaries
                if item["weekly_hours_cap"] is not None
            ),
            "hours_cap_entries": sum(
                item["weekly_hours_cap"] is not None for item in summaries
            ),
        }

    def add_project(
        self, name: str, description: str = "", venture_id: int | None = None
    ) -> int:
        name = name.strip()
        if not name:
            raise ValueError("Project name cannot be empty.")
        with self._connect() as connection:
            if venture_id is not None and connection.execute(
                "SELECT 1 FROM ventures WHERE id = ?", (venture_id,)
            ).fetchone() is None:
                raise ValueError(f"Venture {venture_id} does not exist.")
            cursor = connection.execute(
                "INSERT INTO projects (name, description, venture_id) VALUES (?, ?, ?)",
                (name, description.strip(), venture_id),
            )
            return int(cursor.lastrowid)

    def project_next_actions(self) -> list[dict[str, Any]]:
        """Choose one non-completed next action for every active project."""
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT projects.id AS project_id, projects.name AS project_name,
                          ventures.name AS venture_name, ventures.strategic_priority AS venture_priority,
                          tasks.id AS task_id, tasks.title AS task_title,
                          tasks.priority AS task_priority, tasks.status AS task_status,
                          tasks.due_date AS due_date
                   FROM projects
                   LEFT JOIN ventures ON ventures.id = projects.venture_id
                   LEFT JOIN tasks ON tasks.project_id = projects.id AND tasks.status != 'done'
                   WHERE projects.status = 'active'
                   ORDER BY COALESCE(ventures.strategic_priority, 3), projects.id,
                            CASE tasks.status WHEN 'in_progress' THEN 0 ELSE 1 END,
                            tasks.priority, (tasks.due_date IS NULL), tasks.due_date, tasks.id"""
            ).fetchall()
        actions: dict[int, dict[str, Any]] = {}
        for row in rows:
            item = dict(row)
            project_id = item["project_id"]
            if project_id not in actions:
                actions[project_id] = {
                    "project_id": project_id,
                    "project_name": item["project_name"],
                    "venture_name": item["venture_name"],
                    "venture_priority": item["venture_priority"] or 3,
                    "task_id": item["task_id"],
                    "task_title": item["task_title"],
                    "task_priority": item["task_priority"],
                    "task_status": item["task_status"],
                    "due_date": item["due_date"],
                }
        return list(actions.values())

    def list_projects(self, status: str | None = None) -> list[dict[str, Any]]:
        query = "SELECT projects.*, ventures.name AS venture_name FROM projects LEFT JOIN ventures ON ventures.id = projects.venture_id"
        values: tuple[Any, ...] = ()
        if status is not None:
            if status not in {"active", "paused", "completed"}:
                raise ValueError("Invalid project status.")
            query += " WHERE status = ?"
            values = (status,)
        query += " ORDER BY created_at, id"
        with self._connect() as connection:
            return [dict(row) for row in connection.execute(query, values)]





    def add_recurring_obligation(
        self, venture_id: int, obligation_type: str, amount: float,
        description: str, frequency: str = "monthly", frequency_interval: int = 1,
        start_date: str | None = None, project_id: int | None = None,
    ) -> int:
        value = self._optional_nonnegative_number(amount, "Recurring obligation amount")
        if value is None or value <= 0:
            raise ValueError("Recurring obligation amount must be greater than zero.")
        if obligation_type not in {"receivable", "payable"}:
            raise ValueError("Obligation type must be receivable or payable.")
        if frequency not in {"daily", "weekly", "monthly"}:
            raise ValueError("Frequency must be daily, weekly or monthly.")
        if frequency_interval not in range(1, 366):
            raise ValueError("Repeat interval must be between 1 and 365.")
        description = description.strip()
        if not description:
            raise ValueError("Description cannot be empty.")
        due = start_date or date.today().isoformat()
        try:
            date.fromisoformat(due)
        except ValueError as error:
            raise ValueError("Start date must use YYYY-MM-DD format.") from error
        with self._connect() as connection:
            if connection.execute(
                "SELECT 1 FROM ventures WHERE id = ?", (venture_id,)
            ).fetchone() is None:
                raise ValueError(f"Venture {venture_id} does not exist.")
            if project_id is not None:
                project = connection.execute(
                    "SELECT venture_id FROM projects WHERE id = ?", (project_id,)
                ).fetchone()
                if project is None or project["venture_id"] != venture_id:
                    raise ValueError("Linked project must belong to the selected venture.")
            cursor = connection.execute(
                """INSERT INTO recurring_obligations
                   (venture_id, project_id, obligation_type, amount, description,
                    frequency, frequency_interval, next_due_date)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (venture_id, project_id, obligation_type, value, description,
                 frequency, frequency_interval, due),
            )
            return int(cursor.lastrowid)

    def list_recurring_obligations(
        self, status: str | None = None
    ) -> list[dict[str, Any]]:
        query = """SELECT recurring_obligations.*, ventures.name AS venture_name
                   FROM recurring_obligations
                   JOIN ventures ON ventures.id = recurring_obligations.venture_id"""
        values: tuple[Any, ...] = ()
        if status is not None:
            if status not in {"active", "paused", "completed"}:
                raise ValueError("Invalid recurring obligation status.")
            query += " WHERE recurring_obligations.status = ?"
            values = (status,)
        query += " ORDER BY next_due_date, recurring_obligations.id"
        with self._connect() as connection:
            return [dict(row) for row in connection.execute(query, values)]

    def set_recurring_obligation_status(self, rule_id: int, status: str) -> None:
        if status not in {"active", "paused", "completed"}:
            raise ValueError("Status must be active, paused or completed.")
        with self._connect() as connection:
            cursor = connection.execute(
                "UPDATE recurring_obligations SET status = ? WHERE id = ?",
                (status, rule_id),
            )
            if cursor.rowcount == 0:
                raise ValueError(f"Recurring obligation rule {rule_id} does not exist.")

    def generate_recurring_obligations(
        self, through: date | None = None, limit: int = 100
    ) -> list[dict[str, Any]]:
        """Create due receivable/payable records without settling or paying them."""
        if not 1 <= limit <= 1000:
            raise ValueError("Generation limit must be between 1 and 1000.")
        as_of = through or date.today()
        created: list[dict[str, Any]] = []
        with self._connect() as connection:
            rules = connection.execute(
                """SELECT recurring_obligations.*, ventures.status AS venture_status,
                          ventures.name AS venture_name
                   FROM recurring_obligations
                   JOIN ventures ON ventures.id = recurring_obligations.venture_id
                   WHERE recurring_obligations.status = 'active'
                     AND ventures.status = 'active'
                     AND recurring_obligations.next_due_date <= ?
                   ORDER BY recurring_obligations.next_due_date, recurring_obligations.id""",
                (as_of.isoformat(),),
            ).fetchall()
            remaining = limit
            for row in rules:
                rule = dict(row)
                due = date.fromisoformat(rule["next_due_date"])
                while due <= as_of and remaining > 0:
                    cursor = connection.execute(
                        """INSERT INTO financial_obligations
                           (venture_id, project_id, obligation_type, amount, due_date, description)
                           VALUES (?, ?, ?, ?, ?, ?)""",
                        (rule["venture_id"], rule["project_id"], rule["obligation_type"],
                         rule["amount"], due.isoformat(), rule["description"]),
                    )
                    created.append({
                        "obligation_id": int(cursor.lastrowid),
                        "recurring_id": rule["id"],
                        "venture_name": rule["venture_name"],
                        "obligation_type": rule["obligation_type"],
                        "amount": rule["amount"],
                        "due_date": due.isoformat(),
                        "description": rule["description"],
                    })
                    due = self._next_recurring_date(
                        due, rule["frequency"], rule["frequency_interval"]
                    )
                    remaining -= 1
                connection.execute(
                    "UPDATE recurring_obligations SET next_due_date = ? WHERE id = ?",
                    (due.isoformat(), rule["id"]),
                )
                if remaining == 0:
                    break
        return created

    def add_obligation(
        self, venture_id: int, obligation_type: str, amount: float,
        due_date: str, description: str, project_id: int | None = None,
    ) -> int:
        value = self._optional_nonnegative_number(amount, "Obligation amount")
        if value is None or value <= 0:
            raise ValueError("Obligation amount must be greater than zero.")
        if obligation_type not in {"receivable", "payable"}:
            raise ValueError("Obligation type must be receivable or payable.")
        try:
            date.fromisoformat(due_date)
        except ValueError as error:
            raise ValueError("Due date must use YYYY-MM-DD format.") from error
        description = description.strip()
        if not description:
            raise ValueError("Obligation description cannot be empty.")
        with self._connect() as connection:
            if connection.execute(
                "SELECT 1 FROM ventures WHERE id = ?", (venture_id,)
            ).fetchone() is None:
                raise ValueError(f"Venture {venture_id} does not exist.")
            if project_id is not None:
                project = connection.execute(
                    "SELECT venture_id FROM projects WHERE id = ?", (project_id,)
                ).fetchone()
                if project is None or project["venture_id"] != venture_id:
                    raise ValueError("Linked project must belong to the selected venture.")
            cursor = connection.execute(
                """INSERT INTO financial_obligations
                   (venture_id, project_id, obligation_type, amount, due_date, description)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (venture_id, project_id, obligation_type, value, due_date, description),
            )
            return int(cursor.lastrowid)

    def list_obligations(
        self, status: str | None = None, venture_id: int | None = None
    ) -> list[dict[str, Any]]:
        query = """SELECT financial_obligations.*, ventures.name AS venture_name,
                          projects.name AS project_name
                   FROM financial_obligations
                   JOIN ventures ON ventures.id = financial_obligations.venture_id
                   LEFT JOIN projects ON projects.id = financial_obligations.project_id"""
        clauses: list[str] = []
        values: list[Any] = []
        if status is not None:
            if status not in {"open", "settled", "cancelled"}:
                raise ValueError("Invalid obligation status.")
            clauses.append("financial_obligations.status = ?")
            values.append(status)
        if venture_id is not None:
            clauses.append("financial_obligations.venture_id = ?")
            values.append(venture_id)
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY due_date, financial_obligations.id"
        with self._connect() as connection:
            return [dict(row) for row in connection.execute(query, tuple(values))]

    def settle_obligation(self, obligation_id: int, settled_date: str | None = None) -> int:
        day = settled_date or date.today().isoformat()
        try:
            date.fromisoformat(day)
        except ValueError as error:
            raise ValueError("Settlement date must use YYYY-MM-DD format.") from error
        with self._connect() as connection:
            obligation = connection.execute(
                "SELECT * FROM financial_obligations WHERE id = ?", (obligation_id,)
            ).fetchone()
            if obligation is None:
                raise ValueError(f"Obligation {obligation_id} does not exist.")
            if obligation["status"] != "open":
                raise ValueError("Only open obligations can be settled.")
            if obligation["obligation_type"] == "receivable":
                cursor = connection.execute(
                    """INSERT INTO income_entries
                       (venture_id, project_id, amount, entry_date, note)
                       VALUES (?, ?, ?, ?, ?)""",
                    (obligation["venture_id"], obligation["project_id"],
                     obligation["amount"], day, obligation["description"]),
                )
            else:
                cursor = connection.execute(
                    """INSERT INTO resource_entries
                       (venture_id, project_id, entry_type, quantity, entry_date, note)
                       VALUES (?, ?, 'expense', ?, ?, ?)""",
                    (obligation["venture_id"], obligation["project_id"],
                     obligation["amount"], day, obligation["description"]),
                )
            connection.execute(
                """UPDATE financial_obligations SET status = 'settled',
                   settled_date = ? WHERE id = ?""",
                (day, obligation_id),
            )
            return int(cursor.lastrowid)

    def cancel_obligation(self, obligation_id: int) -> None:
        with self._connect() as connection:
            cursor = connection.execute(
                """UPDATE financial_obligations SET status = 'cancelled'
                   WHERE id = ? AND status = 'open'""",
                (obligation_id,),
            )
            if cursor.rowcount == 0:
                exists = connection.execute(
                    "SELECT 1 FROM financial_obligations WHERE id = ?", (obligation_id,)
                ).fetchone()
                if exists is None:
                    raise ValueError(f"Obligation {obligation_id} does not exist.")
                raise ValueError("Only open obligations can be cancelled.")

    def create_task_proposal(
        self, project_id: int, title: str, rationale: str = "",
        priority: int = 3, due_date: str | None = None,
    ) -> int:
        title = title.strip()
        if not title:
            raise ValueError("Proposed task title cannot be empty.")
        if priority not in range(1, 6):
            raise ValueError("Priority must be between 1 (highest) and 5 (lowest).")
        if due_date is not None:
            try:
                date.fromisoformat(due_date)
            except ValueError as error:
                raise ValueError("Due date must use YYYY-MM-DD format.") from error
        with self._connect() as connection:
            if connection.execute(
                "SELECT 1 FROM projects WHERE id = ?", (project_id,)
            ).fetchone() is None:
                raise ValueError(f"Project {project_id} does not exist.")
            cursor = connection.execute(
                """INSERT INTO task_proposals
                   (project_id, title, rationale, priority, due_date)
                   VALUES (?, ?, ?, ?, ?)""",
                (project_id, title, rationale.strip(), priority, due_date),
            )
            return int(cursor.lastrowid)

    def list_task_proposals(self, status: str | None = None) -> list[dict[str, Any]]:
        query = """SELECT task_proposals.*, projects.name AS project_name,
                          tasks.title AS approved_task_title
                   FROM task_proposals
                   JOIN projects ON projects.id = task_proposals.project_id
                   LEFT JOIN tasks ON tasks.id = task_proposals.approved_task_id"""
        values: tuple[Any, ...] = ()
        if status is not None:
            if status not in {"pending", "approved", "rejected"}:
                raise ValueError("Invalid task proposal status.")
            query += " WHERE task_proposals.status = ?"
            values = (status,)
        query += " ORDER BY CASE task_proposals.status WHEN 'pending' THEN 0 ELSE 1 END, task_proposals.id DESC"
        with self._connect() as connection:
            return [dict(row) for row in connection.execute(query, values)]

    def approve_task_proposal(self, proposal_id: int) -> int:
        with self._connect() as connection:
            proposal = connection.execute(
                "SELECT * FROM task_proposals WHERE id = ?", (proposal_id,)
            ).fetchone()
            if proposal is None:
                raise ValueError(f"Task proposal {proposal_id} does not exist.")
            if proposal["status"] != "pending":
                raise ValueError("Only pending task proposals can be approved.")
            cursor = connection.execute(
                """INSERT INTO tasks (project_id, title, priority, due_date)
                   VALUES (?, ?, ?, ?)""",
                (proposal["project_id"], proposal["title"], proposal["priority"], proposal["due_date"]),
            )
            task_id = int(cursor.lastrowid)
            connection.execute(
                """UPDATE task_proposals SET status = 'approved',
                   approved_task_id = ?, decided_at = ? WHERE id = ?""",
                (task_id, datetime.now().isoformat(timespec="seconds"), proposal_id),
            )
            return task_id

    def reject_task_proposal(self, proposal_id: int) -> None:
        with self._connect() as connection:
            cursor = connection.execute(
                """UPDATE task_proposals SET status = 'rejected',
                   decided_at = ? WHERE id = ? AND status = 'pending'""",
                (datetime.now().isoformat(timespec="seconds"), proposal_id),
            )
            if cursor.rowcount == 0:
                exists = connection.execute(
                    "SELECT 1 FROM task_proposals WHERE id = ?", (proposal_id,)
                ).fetchone()
                if exists is None:
                    raise ValueError(f"Task proposal {proposal_id} does not exist.")
                raise ValueError("Only pending task proposals can be rejected.")

    def add_recurring_task(
        self, project_id: int, title: str, priority: int = 3,
        frequency: str = "weekly", frequency_interval: int = 1,
        start_date: str | None = None,
    ) -> int:
        title = title.strip()
        if not title:
            raise ValueError("Recurring task title cannot be empty.")
        if priority not in range(1, 6):
            raise ValueError("Priority must be between 1 (highest) and 5 (lowest).")
        if frequency not in {"daily", "weekly", "monthly"}:
            raise ValueError("Frequency must be daily, weekly or monthly.")
        if frequency_interval not in range(1, 366):
            raise ValueError("Repeat interval must be between 1 and 365.")
        due = start_date or date.today().isoformat()
        try:
            date.fromisoformat(due)
        except ValueError as error:
            raise ValueError("Start date must use YYYY-MM-DD format.") from error
        with self._connect() as connection:
            if connection.execute(
                "SELECT 1 FROM projects WHERE id = ?", (project_id,)
            ).fetchone() is None:
                raise ValueError(f"Project {project_id} does not exist.")
            cursor = connection.execute(
                """INSERT INTO recurring_tasks
                   (project_id, title, priority, frequency, frequency_interval, next_due_date)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (project_id, title, priority, frequency, frequency_interval, due),
            )
            return int(cursor.lastrowid)

    def list_recurring_tasks(self, status: str | None = None) -> list[dict[str, Any]]:
        query = """SELECT recurring_tasks.*, projects.name AS project_name
                   FROM recurring_tasks JOIN projects ON projects.id = recurring_tasks.project_id"""
        values: tuple[Any, ...] = ()
        if status is not None:
            if status not in {"active", "paused", "completed"}:
                raise ValueError("Invalid recurring-task status.")
            query += " WHERE recurring_tasks.status = ?"
            values = (status,)
        query += " ORDER BY next_due_date, recurring_tasks.id"
        with self._connect() as connection:
            return [dict(row) for row in connection.execute(query, values)]

    def set_recurring_task_status(self, recurring_id: int, status: str) -> None:
        if status not in {"active", "paused", "completed"}:
            raise ValueError("Status must be active, paused or completed.")
        with self._connect() as connection:
            cursor = connection.execute(
                "UPDATE recurring_tasks SET status = ? WHERE id = ?",
                (status, recurring_id),
            )
            if cursor.rowcount == 0:
                raise ValueError(f"Recurring task {recurring_id} does not exist.")

    @staticmethod
    def _next_recurring_date(current: date, frequency: str, interval: int) -> date:
        if frequency == "daily":
            return current + timedelta(days=interval)
        if frequency == "weekly":
            return current + timedelta(days=7 * interval)
        month_index = current.year * 12 + current.month - 1 + interval
        year, month_zero = divmod(month_index, 12)
        month = month_zero + 1
        day = min(current.day, calendar.monthrange(year, month)[1])
        return date(year, month, day)

    def generate_recurring_tasks(
        self, through: date | None = None, limit: int = 100
    ) -> list[dict[str, Any]]:
        """Create due recurring task instances, bounded to avoid runaway backlogs."""
        if not 1 <= limit <= 1000:
            raise ValueError("Generation limit must be between 1 and 1000.")
        as_of = through or date.today()
        created: list[dict[str, Any]] = []
        with self._connect() as connection:
            rules = connection.execute(
                """SELECT recurring_tasks.*, projects.name AS project_name, projects.status AS project_status
                   FROM recurring_tasks JOIN projects ON projects.id = recurring_tasks.project_id
                   WHERE recurring_tasks.status = 'active'
                     AND projects.status = 'active'
                     AND recurring_tasks.next_due_date <= ?
                   ORDER BY recurring_tasks.next_due_date, recurring_tasks.id""",
                (as_of.isoformat(),),
            ).fetchall()
            remaining = limit
            for row in rules:
                rule = dict(row)
                due = date.fromisoformat(rule["next_due_date"])
                while due <= as_of and remaining > 0:
                    cursor = connection.execute(
                        """INSERT INTO tasks (project_id, title, priority, due_date)
                           VALUES (?, ?, ?, ?)""",
                        (rule["project_id"], rule["title"], rule["priority"], due.isoformat()),
                    )
                    created.append({
                        "task_id": int(cursor.lastrowid),
                        "recurring_id": rule["id"],
                        "project_id": rule["project_id"],
                        "project_name": rule["project_name"] if "project_name" in rule else None,
                        "title": rule["title"],
                        "due_date": due.isoformat(),
                    })
                    due = self._next_recurring_date(
                        due, rule["frequency"], rule["frequency_interval"]
                    )
                    remaining -= 1
                connection.execute(
                    "UPDATE recurring_tasks SET next_due_date = ? WHERE id = ?",
                    (due.isoformat(), rule["id"]),
                )
                if remaining == 0:
                    break
        return created

    def add_task(
        self,
        project_id: int,
        title: str,
        priority: int = 3,
        due_date: str | None = None,
    ) -> int:
        title = title.strip()
        if not title:
            raise ValueError("Task title cannot be empty.")
        if not 1 <= priority <= 5:
            raise ValueError("Priority must be between 1 (highest) and 5 (lowest).")
        if due_date is not None:
            try:
                date.fromisoformat(due_date)
            except ValueError as error:
                raise ValueError("Due date must use YYYY-MM-DD format.") from error
        with self._connect() as connection:
            project = connection.execute(
                "SELECT id FROM projects WHERE id = ?", (project_id,)
            ).fetchone()
            if project is None:
                raise ValueError(f"Project {project_id} does not exist.")
            cursor = connection.execute(
                """INSERT INTO tasks (project_id, title, priority, due_date)
                   VALUES (?, ?, ?, ?)""",
                (project_id, title, priority, due_date),
            )
            return int(cursor.lastrowid)

    def list_tasks(self, project_id: int | None = None) -> list[dict[str, Any]]:
        query = """
            SELECT tasks.*, projects.name AS project_name
            FROM tasks JOIN projects ON projects.id = tasks.project_id
        """
        values: tuple[Any, ...] = ()
        if project_id is not None:
            query += " WHERE tasks.project_id = ?"
            values = (project_id,)
        query += """
            ORDER BY CASE tasks.status WHEN 'in_progress' THEN 0
                       WHEN 'todo' THEN 1 ELSE 2 END,
                     tasks.priority ASC, tasks.id ASC
        """
        with self._connect() as connection:
            return [dict(row) for row in connection.execute(query, values)]

    def update_project(
        self, project_id: int, name: str | None = None, description: str | None = None
    ) -> None:
        if name is not None and not name.strip():
            raise ValueError("Project name cannot be empty.")
        if name is None and description is None:
            raise ValueError("Provide a new project name or description.")
        with self._connect() as connection:
            cursor = connection.execute(
                """UPDATE projects SET
                   name = COALESCE(?, name),
                   description = COALESCE(?, description)
                   WHERE id = ?""",
                (name.strip() if name is not None else None,
                 description.strip() if description is not None else None, project_id),
            )
            if cursor.rowcount == 0:
                raise ValueError(f"Project {project_id} does not exist.")

    def update_task(
        self, task_id: int, title: str | None = None, priority: int | None = None,
        due_date: str | None = None, clear_due_date: bool = False,
    ) -> None:
        if title is not None and not title.strip():
            raise ValueError("Task title cannot be empty.")
        if priority is not None and priority not in range(1, 6):
            raise ValueError("Priority must be between 1 (highest) and 5 (lowest).")
        if due_date is not None:
            try:
                date.fromisoformat(due_date)
            except ValueError as error:
                raise ValueError("Due date must use YYYY-MM-DD format.") from error
        if clear_due_date and due_date is not None:
            raise ValueError("Choose either a due date or --clear-due-date, not both.")
        if title is None and priority is None and due_date is None and not clear_due_date:
            raise ValueError("Provide at least one task field to update.")
        with self._connect() as connection:
            cursor = connection.execute(
                """UPDATE tasks SET
                   title = COALESCE(?, title),
                   priority = COALESCE(?, priority),
                   due_date = CASE WHEN ? THEN NULL ELSE COALESCE(?, due_date) END
                   WHERE id = ?""",
                (title.strip() if title is not None else None, priority,
                 int(clear_due_date), due_date, task_id),
            )
            if cursor.rowcount == 0:
                raise ValueError(f"Task {task_id} does not exist.")

    def set_task_status(self, task_id: int, status: str) -> None:
        if status not in {"todo", "in_progress", "done"}:
            raise ValueError("Status must be todo, in_progress, or done.")
        with self._connect() as connection:
            cursor = connection.execute(
                "UPDATE tasks SET status = ? WHERE id = ?", (status, task_id)
            )
            if cursor.rowcount == 0:
                raise ValueError(f"Task {task_id} does not exist.")

    def set_project_status(self, project_id: int, status: str) -> None:
        if status not in {"active", "paused", "completed"}:
            raise ValueError("Status must be active, paused, or completed.")
        with self._connect() as connection:
            cursor = connection.execute(
                "UPDATE projects SET status = ? WHERE id = ?",
                (status, project_id),
            )
            if cursor.rowcount == 0:
                raise ValueError(f"Project {project_id} does not exist.")

    def save_review(
        self,
        priority: str = "",
        wins: str = "",
        blockers: str = "",
        tomorrow: str = "",
        review_date: str | None = None,
    ) -> dict[str, Any]:
        """Create or update one daily executive review."""
        day = review_date or date.today().isoformat()
        try:
            date.fromisoformat(day)
        except ValueError as error:
            raise ValueError("Review date must use YYYY-MM-DD format.") from error
        values = tuple(value.strip() for value in (priority, wins, blockers, tomorrow))
        if not any(values):
            raise ValueError("Add at least one review field.")
        with self._connect() as connection:
            existing = connection.execute(
                "SELECT * FROM daily_reviews WHERE review_date = ?", (day,)
            ).fetchone()
            previous = dict(existing) if existing else {}
            merged = {
                "priority": values[0] or previous.get("priority", ""),
                "wins": values[1] or previous.get("wins", ""),
                "blockers": values[2] or previous.get("blockers", ""),
                "tomorrow": values[3] or previous.get("tomorrow", ""),
            }
            connection.execute(
                """INSERT INTO daily_reviews
                   (review_date, priority, wins, blockers, tomorrow)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(review_date) DO UPDATE SET
                     priority=excluded.priority, wins=excluded.wins,
                     blockers=excluded.blockers, tomorrow=excluded.tomorrow,
                     updated_at=CURRENT_TIMESTAMP""",
                (day, merged["priority"], merged["wins"],
                 merged["blockers"], merged["tomorrow"]),
            )
            row = connection.execute(
                "SELECT * FROM daily_reviews WHERE review_date = ?", (day,)
            ).fetchone()
            return dict(row)

    def list_reviews(self, limit: int = 7) -> list[dict[str, Any]]:
        """Return the most recent daily reviews."""
        if not 1 <= limit <= 365:
            raise ValueError("Review limit must be between 1 and 365.")
        with self._connect() as connection:
            return [
                dict(row) for row in connection.execute(
                    "SELECT * FROM daily_reviews ORDER BY review_date DESC LIMIT ?",
                    (limit,),
                )
            ]

    def add_blocker(
        self, title: str, details: str = "",
        project_id: int | None = None, task_id: int | None = None,
    ) -> int:
        title = title.strip()
        if not title:
            raise ValueError("Blocker title cannot be empty.")
        with self._connect() as connection:
            if project_id is not None and connection.execute(
                "SELECT 1 FROM projects WHERE id = ?", (project_id,)
            ).fetchone() is None:
                raise ValueError(f"Project {project_id} does not exist.")
            if task_id is not None and connection.execute(
                "SELECT 1 FROM tasks WHERE id = ?", (task_id,)
            ).fetchone() is None:
                raise ValueError(f"Task {task_id} does not exist.")
            cursor = connection.execute(
                """INSERT INTO blockers (title, details, project_id, task_id)
                   VALUES (?, ?, ?, ?)""",
                (title, details.strip(), project_id, task_id),
            )
            return int(cursor.lastrowid)

    def list_blockers(self, status: str = "open") -> list[dict[str, Any]]:
        if status not in {"open", "resolved", "all"}:
            raise ValueError("Blocker status must be open, resolved, or all.")
        query = """
            SELECT blockers.*, projects.name AS project_name, tasks.title AS task_title
            FROM blockers
            LEFT JOIN projects ON projects.id = blockers.project_id
            LEFT JOIN tasks ON tasks.id = blockers.task_id
        """
        if status != "all":
            query += " WHERE blockers.status = ?"
        query += " ORDER BY blockers.created_at DESC, blockers.id DESC"
        with self._connect() as connection:
            rows = connection.execute(query, () if status == "all" else (status,))
            return [dict(row) for row in rows]

    def resolve_blocker(self, blocker_id: int) -> None:
        with self._connect() as connection:
            cursor = connection.execute(
                """UPDATE blockers SET status = 'resolved',
                   resolved_at = CURRENT_TIMESTAMP
                   WHERE id = ? AND status = 'open'""",
                (blocker_id,),
            )
            if cursor.rowcount == 0:
                raise ValueError(f"Open blocker {blocker_id} does not exist.")

    def add_decision(
        self,
        title: str,
        choice: str,
        context: str = "",
        rationale: str = "",
        decision_date: str | None = None,
        revisit_date: str | None = None,
    ) -> int:
        """Record a decision and the reasoning behind it."""
        title, choice = title.strip(), choice.strip()
        if not title or not choice:
            raise ValueError("Decision title and choice cannot be empty.")
        decided = decision_date or date.today().isoformat()
        for label, value in (("Decision date", decided), ("Revisit date", revisit_date)):
            if value:
                try:
                    date.fromisoformat(value)
                except ValueError as error:
                    raise ValueError(f"{label} must use YYYY-MM-DD format.") from error
        with self._connect() as connection:
            cursor = connection.execute(
                """INSERT INTO decisions
                   (decision_date, title, context, choice, rationale, revisit_date)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (decided, title, context.strip(), choice, rationale.strip(), revisit_date),
            )
            return int(cursor.lastrowid)

    def list_decisions(self, limit: int = 20) -> list[dict[str, Any]]:
        if not 1 <= limit <= 500:
            raise ValueError("Decision limit must be between 1 and 500.")
        with self._connect() as connection:
            return [
                dict(row) for row in connection.execute(
                    "SELECT * FROM decisions ORDER BY decision_date DESC, id DESC LIMIT ?",
                    (limit,),
                )
            ]

    def review_summary(self, days: int = 7, today: date | None = None) -> dict[str, Any]:
        """Summarize daily reviews over the last 7 or 30 calendar days."""
        if days not in {7, 30}:
            raise ValueError("Review summary period must be 7 or 30 days.")
        end = today or date.today()
        start = end - timedelta(days=days - 1)
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT * FROM daily_reviews
                   WHERE review_date BETWEEN ? AND ?
                   ORDER BY review_date DESC""",
                (start.isoformat(), end.isoformat()),
            ).fetchall()
        entries = [dict(row) for row in rows]
        return {
            "start": start.isoformat(),
            "end": end.isoformat(),
            "days": days,
            "reviewed_days": len(entries),
            "entries": entries,
        }

    def dashboard(self) -> dict[str, int]:
        with self._connect() as connection:
            projects = connection.execute(
                "SELECT COUNT(*) FROM projects WHERE status = 'active'"
            ).fetchone()[0]
            open_tasks = connection.execute(
                "SELECT COUNT(*) FROM tasks WHERE status != 'done'"
            ).fetchone()[0]
            in_progress = connection.execute(
                "SELECT COUNT(*) FROM tasks WHERE status = 'in_progress'"
            ).fetchone()[0]
            completed = connection.execute(
                "SELECT COUNT(*) FROM tasks WHERE status = 'done'"
            ).fetchone()[0]
        return {
            "active_projects": int(projects),
            "open_tasks": int(open_tasks),
            "in_progress_tasks": int(in_progress),
            "completed_tasks": int(completed),
        }


    def execution_plan(self, days: int = 7, today: date | None = None) -> dict[str, Any]:
        """Return overdue, upcoming and unscheduled work for active projects."""
        if days not in {7, 30}:
            raise ValueError("Plan horizon must be 7 or 30 days.")
        start = today or date.today()
        end = start + timedelta(days=days)
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT tasks.*, projects.name AS project_name
                FROM tasks
                JOIN projects ON projects.id = tasks.project_id
                WHERE projects.status = 'active' AND tasks.status != 'done'
                ORDER BY CASE tasks.status WHEN 'in_progress' THEN 0 ELSE 1 END,
                         tasks.priority ASC, tasks.due_date ASC, tasks.id ASC
                """
            ).fetchall()

        overdue: list[dict[str, Any]] = []
        upcoming: list[dict[str, Any]] = []
        unscheduled: list[dict[str, Any]] = []
        for row in rows:
            task = dict(row)
            due = task["due_date"]
            if not due:
                unscheduled.append(task)
                continue
            due_day = date.fromisoformat(due)
            if due_day < start:
                overdue.append(task)
            elif due_day <= end:
                upcoming.append(task)

        return {
            "start": start.isoformat(),
            "end": end.isoformat(),
            "days": days,
            "overdue": overdue,
            "upcoming": upcoming,
            "unscheduled": unscheduled,
        }


    def ai_context(self) -> dict[str, Any]:
        """Build a bounded, read-only context snapshot for an explicitly approved AI request."""
        return {
            "as_of": date.today().isoformat(),
            "portfolio": self.portfolio_summary(),
            "projects": self.list_projects(),
            "project_next_actions": self.project_next_actions(),
            "tasks": self.list_tasks()[:60],
            "open_blockers": self.list_blockers("open")[:25],
            "recent_reviews": self.list_reviews(7),
            "recent_decisions": self.list_decisions(15),
            "recent_resource_entries": self.list_resource_entries(limit=30),
            "recurring_tasks": self.list_recurring_tasks()[:30],
            "pending_task_proposals": self.list_task_proposals("pending")[:30],
            "open_obligations": self.list_obligations("open")[:30],
            "recurring_obligations": self.list_recurring_obligations()[:30],
        }

    def backup(self, destination: str | Path, overwrite: bool = False) -> Path:
        """Create a consistent SQLite backup without interrupting normal reads."""
        target = Path(destination).expanduser().resolve()
        source = Path(self.database).expanduser().resolve()
        if target == source:
            raise ValueError("Backup destination must differ from the active database.")
        if target.exists() and not overwrite:
            raise ValueError(f"Backup already exists: {target} (use --force to replace it).")
        target.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as source_connection:
            destination_connection = sqlite3.connect(str(target))
            try:
                source_connection.backup(destination_connection)
                destination_connection.execute("PRAGMA integrity_check")
                result = destination_connection.execute("PRAGMA integrity_check").fetchone()
                if not result or result[0] != "ok":
                    raise OSError("Backup integrity check failed.")
            finally:
                destination_connection.close()
        return target


    def import_data(self, source_path: str | Path) -> dict[str, int]:
        """Import a versioned SAGE JSON export into an empty database atomically."""
        source = Path(source_path).expanduser().resolve()
        if not source.is_file():
            raise ValueError(f"JSON export does not exist: {source}")
        try:
            payload = json.loads(source.read_text(encoding="utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ValueError("JSON export is not valid UTF-8 JSON.") from error
        if not isinstance(payload, dict) or payload.get("format") != "sage-export":
            raise ValueError("File is not a recognized SAGE JSON export.")
        version = payload.get("version")
        if version not in {1, 2, 3, 4, 5, 6, 7}:
            raise ValueError(f"Unsupported SAGE export version: {version}")
        data = payload.get("data")
        if not isinstance(data, dict):
            raise ValueError("SAGE export is missing its data object.")
        tables = (
            "ventures", "projects", "tasks", "daily_reviews",
            "decisions", "blockers", "resource_entries", "income_entries", "recurring_tasks", "task_proposals", "financial_obligations", "recurring_obligations",
        )
        for table in tables:
            if table not in data and version in {1, 2, 3, 4, 5, 6} and table in {"ventures", "resource_entries", "income_entries", "recurring_tasks", "task_proposals", "financial_obligations", "recurring_obligations"}:
                data[table] = []
            if not isinstance(data.get(table), list):
                raise ValueError(f"SAGE export table '{table}' must be a list.")
        imported: dict[str, int] = {}
        with self._connect() as connection:
            for table in tables:
                count = connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                if count:
                    raise ValueError(
                        "JSON import requires an empty SAGE database. Choose a new database file."
                    )
            connection.execute("BEGIN IMMEDIATE")
            for table in tables:
                rows = data[table]
                columns = [row["name"] for row in connection.execute(
                    f"PRAGMA table_info({table})"
                )]
                imported[table] = 0
                for record in rows:
                    if not isinstance(record, dict):
                        raise ValueError(f"Records in '{table}' must be JSON objects.")
                    unknown = set(record) - set(columns)
                    if unknown:
                        raise ValueError(
                            f"Unknown fields in '{table}': {', '.join(sorted(unknown))}"
                        )
                    names = [column for column in columns if column in record]
                    if not names:
                        raise ValueError(f"Record in '{table}' contains no recognized fields.")
                    placeholders = ", ".join("?" for _ in names)
                    sql = (
                        f"INSERT INTO {table} ({', '.join(names)}) "
                        f"VALUES ({placeholders})"
                    )
                    connection.execute(sql, tuple(record[name] for name in names))
                    imported[table] += 1
            violations = connection.execute("PRAGMA foreign_key_check").fetchall()
            if violations:
                raise ValueError("JSON export contains invalid project or venture references.")
        return imported

    def restore_backup(self, source_path: str | Path) -> Path | None:
        """Restore a verified SQLite backup, preserving the current DB first."""
        source = Path(source_path).expanduser().resolve()
        target = Path(self.database).expanduser().resolve()
        if not source.is_file():
            raise ValueError(f"Backup file does not exist: {source}")
        if source == target:
            raise ValueError("Restore source must differ from the active database.")
        temporary = target.with_name(target.name + ".restore.tmp")
        if temporary.exists():
            raise ValueError(f"Temporary restore file already exists: {temporary}")
        safety_copy: Path | None = None
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            source_connection = sqlite3.connect(str(source))
            try:
                check = source_connection.execute("PRAGMA integrity_check").fetchone()
                if not check or check[0] != "ok":
                    raise ValueError("Restore source failed SQLite integrity check.")
                tables = {
                    row[0] for row in source_connection.execute(
                        "SELECT name FROM sqlite_master WHERE type = 'table'"
                    )
                }
                if not {"projects", "tasks"}.issubset(tables):
                    raise ValueError("Restore source is not a recognized SAGE database.")
                restored = sqlite3.connect(str(temporary))
                try:
                    source_connection.backup(restored)
                    result = restored.execute("PRAGMA integrity_check").fetchone()
                    if not result or result[0] != "ok":
                        raise OSError("Restored database failed integrity check.")
                finally:
                    restored.close()
            finally:
                source_connection.close()
            if target.exists():
                stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
                safety_copy = target.with_name(target.name + f".pre-restore-{stamp}.bak")
                current = sqlite3.connect(str(target))
                backup = sqlite3.connect(str(safety_copy))
                try:
                    current.backup(backup)
                finally:
                    backup.close()
                    current.close()
            os.replace(temporary, target)
            return safety_copy
        finally:
            if temporary.exists():
                temporary.unlink()


    @staticmethod
    def _ics_escape(value: str) -> str:
        return (
            value.replace("\\", "\\\\")
            .replace(";", "\\;")
            .replace(",", "\\,")
            .replace("\r\n", "\\n")
            .replace("\n", "\\n")
            .replace("\r", "")
        )

    def export_calendar(self, destination: str | Path, overwrite: bool = False) -> Path:
        """Export open tasks with due dates from active projects as all-day ICS events."""
        target = Path(destination).expanduser().resolve()
        if target.exists() and not overwrite:
            raise ValueError(f"Calendar export already exists: {target} (use --force to replace it).")
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT tasks.*, projects.name AS project_name,
                          ventures.name AS venture_name
                   FROM tasks
                   JOIN projects ON projects.id = tasks.project_id
                   LEFT JOIN ventures ON ventures.id = projects.venture_id
                   WHERE projects.status = 'active'
                     AND tasks.status != 'done'
                     AND tasks.due_date IS NOT NULL
                   ORDER BY tasks.due_date, tasks.priority, tasks.id"""
            ).fetchall()
        lines = [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//SAGE//Executive OS//EN",
            "CALSCALE:GREGORIAN",
            "METHOD:PUBLISH",
        ]
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        for row in rows:
            task = dict(row)
            due = date.fromisoformat(task["due_date"])
            description = (
                f"Project: {task['project_name']}\n"
                f"Venture: {task['venture_name'] or 'Unassigned'}\n"
                f"Priority: P{task['priority']}\nStatus: {task['status']}"
            )
            lines.extend([
                "BEGIN:VEVENT",
                f"UID:sage-task-{task['id']}@local.sage",
                f"DTSTAMP:{stamp}",
                f"DTSTART;VALUE=DATE:{due.strftime('%Y%m%d')}",
                f"DTEND;VALUE=DATE:{(due + timedelta(days=1)).strftime('%Y%m%d')}",
                f"SUMMARY:{self._ics_escape(task['title'])}",
                f"DESCRIPTION:{self._ics_escape(description)}",
                "END:VEVENT",
            ])
        lines.append("END:VCALENDAR")
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(target.name + ".tmp")
        try:
            temporary.write_text("\r\n".join(lines) + "\r\n", encoding="utf-8")
            temporary.replace(target)
        finally:
            if temporary.exists():
                temporary.unlink()
        return target

    def export_data(self, destination: str | Path, overwrite: bool = False) -> Path:
        """Export all SAGE records as portable, versioned UTF-8 JSON."""
        target = Path(destination).expanduser().resolve()
        if target.exists() and not overwrite:
            raise ValueError(f"Export already exists: {target} (use --force to replace it).")
        target.parent.mkdir(parents=True, exist_ok=True)
        tables = ("ventures", "projects", "tasks", "daily_reviews", "decisions", "blockers", "resource_entries", "income_entries", "recurring_tasks", "task_proposals", "financial_obligations")
        with self._connect() as connection:
            payload = {
                "format": "sage-export",
                "version": 7,
                "exported_at": date.today().isoformat(),
                "data": {
                    table: [dict(row) for row in connection.execute(
                        f"SELECT * FROM {table} ORDER BY rowid"
                    )]
                    for table in tables
                },
            }
        temporary = target.with_name(target.name + ".tmp")
        try:
            temporary.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            temporary.replace(target)
        finally:
            if temporary.exists():
                temporary.unlink()
        return target
