"""Core local-first project and task operations for SAGE.

This module deliberately uses only the Python standard library.
It stores data in a SQLite database on the user's machine.
"""
from __future__ import annotations

import sqlite3
from datetime import date, timedelta
from pathlib import Path
from typing import Any


SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    description TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'paused', 'completed')),
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
"""


class SageStore:
    """Small SQLite-backed store for projects and their next actions."""

    def __init__(self, database: str | Path = "sage.db") -> None:
        self.database = str(database)
        with self._connect() as connection:
            connection.executescript(SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def add_project(self, name: str, description: str = "") -> int:
        name = name.strip()
        if not name:
            raise ValueError("Project name cannot be empty.")
        with self._connect() as connection:
            cursor = connection.execute(
                "INSERT INTO projects (name, description) VALUES (?, ?)",
                (name, description.strip()),
            )
            return int(cursor.lastrowid)

    def list_projects(self, status: str | None = None) -> list[dict[str, Any]]:
        query = "SELECT * FROM projects"
        values: tuple[Any, ...] = ()
        if status is not None:
            if status not in {"active", "paused", "completed"}:
                raise ValueError("Invalid project status.")
            query += " WHERE status = ?"
            values = (status,)
        query += " ORDER BY created_at, id"
        with self._connect() as connection:
            return [dict(row) for row in connection.execute(query, values)]

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
