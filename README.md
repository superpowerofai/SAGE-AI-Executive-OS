# SAGE AI Executive OS

**A local-first, human-in-the-loop execution system for turning projects into clear next actions.**

SAGE v0.1 provides a Python command-line interface and a localhost web cockpit backed by SQLite. It can create and list projects, create and list tasks, update project/task statuses, and summarize execution counts. It is an early working foundation—not yet a hosted dashboard or autonomous AI agent.

## Current capabilities

- Create projects with a name, optional description and optional venture owner.
- Register ventures with strategic priority plus optional monthly budget and weekly hours caps.
- Assign and reassign projects to ventures; compare project/task load and explicitly entered resource caps in a portfolio summary.
- Log actual INR income, expenses and hours worked against ventures (optionally linked to a project); track receivables and payables, settle them into actual ledger entries, and see a 30-day obligation forecast. Compare monthly income, expenses and net cash flow plus weekly time usage with caps.
- Submit proposed tasks to a human approval queue; only approved proposals become executable tasks, and rejected proposals remain recorded.
- Create recurring daily, weekly or monthly task rules, pause/resume them, and generate due instances on demand with a safe per-run limit.
- Edit project names/descriptions and task titles/priorities/due dates; archive projects and tasks by marking them completed/done.
- Track project status: active, paused, completed.
- Add tasks with priority 1 (highest) through 5 (lowest).
- Track task status: todo, in_progress, done.
- List tasks ordered by status and priority.
- View an executive cockpit with portfolio counts, master focus, open blockers, and the latest daily review.
- Launch a browser-based local cockpit to manage ventures, project ownership, income/expense/time logs, projects/tasks, statuses, daily reviews, blockers and decisions.
- Export open dated tasks from active projects to an iCalendar `.ics` file for import into calendar apps.
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
- Restore a verified SQLite backup only with explicit confirmation; the current database is preserved as a pre-restore safety copy.
- Export all stored records (ventures, projects, tasks, daily reviews, decisions, blockers, resource entries, income entries and recurring task rules) to versioned UTF-8 JSON, and import compatible exports atomically into an empty database.
- Store durable local context notes (preferences, constraints and operating rules) that are included in AI context previews.
- Preview the exact bounded business context prepared for AI; external transmission requires explicit `--send-context` approval in the CLI or an approval checkbox in the local cockpit.
- Request advisory AI suggestions from local or remote OpenAI-compatible chat-completion endpoints; SAGE never lets the model mutate records.

## Requirements

- Python 3.10 or newer
- pip

The application runtime uses only the Python standard library. The optional AI adapter uses the standard library HTTP client. Pytest and a Python 3.10 TOML compatibility dependency are used for tests.

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
sage log-income 1 9500 --note "Client payment"
sage add-obligation 1 receivable 25000 2026-12-01 "Client invoice"
sage add-recurring-obligation 1 payable 9000 "Office rent" --frequency monthly --start-date 2026-12-01
sage generate-recurring-obligations
sage obligations --status open
sage set-cash-position 1 50000 2026-11-23 --note "Verified opening cash"
sage cash-positions
sage add-note "Operating rule" "Evidence first; one clear next action." --category preferences --importance 1
sage notes
sage settle-obligation 1
sage log-time 1 2.5 --note "Build automation"
sage resources --venture-id 1
sage export-ics exports/sage-calendar.ics
sage propose-task 1 "Contact a qualified prospect" --rationale "Direct revenue action" --priority 1
sage proposals
sage approve-proposal 1
sage add-recurring-task 1 "Review pipeline" --frequency weekly --start-date 2026-11-23
sage generate-recurring
sage backup backups/sage.db
sage export-json exports/sage.json
sage --db data/imported.db import-json exports/sage.json  # new, empty database
sage restore backups/sage.db --yes
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

On Windows, double-click `start_sage.bat` from the project folder to launch the local cockpit. It uses `runtime/data/sage.db` and binds only to `127.0.0.1:8765`. Keep the terminal window open while using the cockpit.

Optional daily automation (Windows): run `powershell -ExecutionPolicy Bypass -File .\\install_sage_scheduler.ps1`. The installer asks for a daily time (default 08:00). The scheduled job generates due recurring tasks and receivables/payables; it does not pay or collect money. It runs in your Windows user session and logs to `runtime/logs/daily-generation.log`. Remove it with `powershell -ExecutionPolicy Bypass -File .\\remove_sage_scheduler.ps1`.

## Optional AI suggestions

SAGE supports OpenAI-compatible chat-completion endpoints. It does not store API credentials.

The Windows launcher defaults to the local Ollama endpoint at `http://127.0.0.1:11434/v1` with `qwen3:1.7b`; override these environment variables if needed. For another local endpoint, configure the base URL and model in your shell:

```powershell
$env:SAGE_AI_BASE_URL = "http://127.0.0.1:11434/v1"
$env:SAGE_AI_MODEL = "your-local-model"
```

For a remote provider, use its HTTPS base URL and set `SAGE_AI_API_KEY` in the environment. Do not store passwords, account numbers or highly sensitive secrets in SAGE notes. Do not put API secrets in source files or commit them.

Preview the context first, then explicitly approve transmission:

```bash
sage context-preview
sage suggest "What should receive my next focused work block?" --send-context
```

The local cockpit includes an AI Advisor form with an explicit consent checkbox. AI responses are suggestions only. They are not automatically saved as decisions, tasks, or actions. The context preview includes venture records, project/task lists, open blockers, recent reviews/decisions, and recent resource entries; inspect it before sending.

## GitHub Actions

The SAGE CI workflow runs the automated test suite on pushes, pull requests, and manual dispatch. It checks Python 3.10, 3.11, and 3.12. A configured workflow is not proof of a passing run; check the repository's Actions tab for the latest result.

## Architecture

- `src/sage/core.py`: SQLite schema/migrations, venture portfolio, resource ledger, project/task operations, backup and JSON export.
- `src/sage/cli.py`: command-line interface.
- `src/sage/__main__.py`: `python -m sage` entry point.
- `tests/`: configuration, core behavior and CLI workflow tests.

## Current limitations

- Local single-user database; no cloud sync or hosted accounts.
- The web cockpit is intentionally local-only; it does not yet provide user accounts, remote access, or cloud sync. It checks Host/Origin headers, blocks cross-origin mutations, and applies restrictive browser security headers.
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
