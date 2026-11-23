# SAGE AI Executive OS

**A local-first, human-in-the-loop execution system for turning projects into clear next actions.**

SAGE v0.1 provides a Python command-line interface and a localhost web cockpit backed by SQLite. It can create and list projects, create and list tasks, update project/task statuses, and summarize execution counts. It is an early working foundation—not yet a hosted dashboard or autonomous AI agent.

## Current capabilities

- Create projects with a name, optional description and optional venture owner.
- Register ventures with strategic priority plus optional monthly budget and weekly hours caps.
- Assign and reassign projects to ventures; compare project/task load and explicitly entered resource caps in a portfolio summary.
- Log actual INR expenses and hours worked against ventures (optionally linked to a project), and compare month-to-date / week-to-date usage with caps.
- Track project status: active, paused, completed.
- Add tasks with priority 1 (highest) through 5 (lowest).
- Track task status: todo, in_progress, done.
- List tasks ordered by status and priority.
- View an executive cockpit with portfolio counts, master focus, open blockers, and the latest daily review.
- Launch a browser-based local cockpit to create projects/tasks, update statuses, record daily reviews, and manage blockers.
- View a focus summary showing active and paused projects plus one next action from active projects.
- View a 7-day or 30-day execution plan grouped into overdue, upcoming, and unscheduled active work.
- Save a daily executive review with one priority, wins, blockers, and tomorrow's first move; update a date's review without creating duplicates.
- Browse recent daily reviews for accountability and continuity.
- Generate 7-day and 30-day executive review summaries from recorded priorities, wins, blockers, and next moves.
- Keep a decision journal with context, chosen option, rationale, and optional revisit date.
- Track open and resolved blockers, optionally linked to a project or task.
- Validate new due dates in YYYY-MM-DD format. The command selects one open task from active projects, preferring in-progress work, then higher priority, and excludes paused projects and completed tasks.
- Persist data in a local SQLite database.
- Create an integrity-checked SQLite backup without interrupting normal reads.
- Export all stored records (ventures, projects, tasks, daily reviews, decisions, blockers and resource entries) to versioned UTF-8 JSON.

## Requirements

- Python 3.10 or newer
- pip

The application runtime uses only the Python standard library. Pytest and a Python 3.10 TOML compatibility dependency are used for tests.

## Install locally

Clone the repository, then from its root directory run:

```bash
python -m venv .venv
```

Activate the environment:

- Windows PowerShell: `.venv\\Scripts\\Activate.ps1`
- macOS/Linux: `source .venv/bin/activate`

Install the package and test tools:

```bash
python -m pip install -e .
python -m pip install pytest
```

Run the test suite:

```bash
python -m pytest -q
```

## Quick start

Create a project:

```bash
sage add-project "Launch website" --description "First business milestone"
```

Add a task (use the project ID printed by the previous command):

```bash
sage add-task 1 "Write homepage copy" --priority 1
```

View projects and tasks:

```bash
sage projects
sage tasks
```

View the focus summary:

```bash
sage focus
sage add-venture "OPERONIX AI" --priority 1 --monthly-budget-cap 25000 --weekly-hours-cap 18
sage add-project "Lead follow-up system" --venture-id 1
sage ventures
sage log-expense 1 1250 --note "Hosting"
sage log-time 1 2.5 --note "Build automation"
sage resources --venture-id 1
sage plan --days 7
sage plan --days 30
```

Update a task and view the dashboard:

```bash
sage set-task-status 1 in_progress
sage dashboard
```

Use `--db path/to/file.db` before any command to choose a database file. By default, SAGE creates `sage.db` in the current working directory.

You can also launch the CLI with `python -m sage` after installing the package.

## GitHub Actions

The SAGE CI workflow runs the automated test suite on pushes, pull requests, and manual dispatch. It checks Python 3.10, 3.11, and 3.12. A configured workflow is not proof of a passing run; check the repository's Actions tab for the latest result.

## Architecture

- `src/sage/core.py`: SQLite schema/migrations, venture portfolio, resource ledger, project/task operations, backup and JSON export.
- `src/sage/cli.py`: command-line interface.
- `src/sage/__main__.py`: `python -m sage` entry point.
- `tests/`: configuration, core behavior and CLI workflow tests.

## Current limitations

- Local single-user database; no cloud sync or hosted accounts.
- The web cockpit is intentionally local-only; it does not yet provide user accounts, remote access, or cloud sync.
- No AI model or external messaging integration.
- No recurring tasks, calendar sync, or multi-user permissions. Daily reviews are manually entered; SAGE does not yet infer wins or blockers from external apps.
- Due dates are stored as supplied; advanced date validation and reminders are not implemented.

## Product principles

1. Evidence before claims.
2. One clear next action over overwhelming task lists.
3. Human approval before consequential external actions.
4. Privacy-conscious local-first storage.
5. Features are marked complete only after implementation and verification.

## Roadmap

See [docs/ROADMAP.md](docs/ROADMAP.md) and [the 21-project portfolio plan](docs/PORTFOLIO_21_PROJECTS.md).

## License

No open-source license has been selected. Until one is added, no license is granted to reuse, modify, or distribute this code.
