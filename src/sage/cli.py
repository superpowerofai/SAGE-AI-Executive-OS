"""Command-line interface for the SAGE local execution tracker."""
from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

from .core import SageStore


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sage",
        description="A local-first project and next-action tracker.",
    )
    parser.add_argument(
        "--db", default="sage.db", help="SQLite database path (default: sage.db)"
    )
    commands = parser.add_subparsers(dest="command", required=True)

    project_add = commands.add_parser("add-project", help="Create a project")
    project_add.add_argument("name")
    project_add.add_argument("--description", default="")
    project_add.add_argument("--venture-id", type=int)

    venture_add = commands.add_parser("add-venture", help="Create a business or venture")
    venture_add.add_argument("name")
    venture_add.add_argument("--description", default="")
    venture_add.add_argument("--monthly-budget-cap", type=float)
    venture_add.add_argument("--weekly-hours-cap", type=float)
    venture_add.add_argument("--priority", type=int, choices=[1, 2, 3, 4, 5], default=3)

    commands.add_parser("ventures", help="List ventures and resource capacity")
    for command_name, help_text, quantity_name in (
        ("log-expense", "Record an expense in INR", "amount"),
        ("log-income", "Record income in INR", "amount"),
        ("log-time", "Record hours worked", "hours"),
    ):
        resource = commands.add_parser(command_name, help=help_text)
        resource.add_argument("venture_id", type=int)
        resource.add_argument(quantity_name, type=float)
        resource.add_argument("--project-id", type=int)
        resource.add_argument("--date", dest="entry_date")
        resource.add_argument("--note", default="")
    resource_list = commands.add_parser("resources", help="List recent resource entries")
    resource_list.add_argument("--venture-id", type=int)
    resource_list.add_argument("--limit", type=int, default=100)

    assign = commands.add_parser("assign-project", help="Assign a project to a venture")
    assign.add_argument("project_id", type=int)
    assign.add_argument("venture_id", type=int, help="Use 0 to unassign")

    commands.add_parser("projects", help="List projects")

    task_add = commands.add_parser("add-task", help="Add a task to a project")
    task_add.add_argument("project_id", type=int)
    task_add.add_argument("title")
    task_add.add_argument("--priority", type=int, default=3)
    task_add.add_argument("--due-date")

    task_list = commands.add_parser("tasks", help="List tasks")
    task_list.add_argument("--project-id", type=int)

    recurring_add = commands.add_parser("add-recurring-task", help="Create a recurring task rule")
    recurring_add.add_argument("project_id", type=int)
    recurring_add.add_argument("title")
    recurring_add.add_argument("--frequency", choices=["daily", "weekly", "monthly"], default="weekly")
    recurring_add.add_argument("--every", type=int, default=1, help="Repeat every N frequency units")
    recurring_add.add_argument("--priority", type=int, choices=[1, 2, 3, 4, 5], default=3)
    recurring_add.add_argument("--start-date")
    commands.add_parser("recurring-tasks", help="List recurring task rules")
    recurring_status = commands.add_parser("set-recurring-status", help="Pause, resume or complete a recurring rule")
    recurring_status.add_argument("recurring_id", type=int)
    recurring_status.add_argument("status", choices=["active", "paused", "completed"])

    propose = commands.add_parser("propose-task", help="Submit a task for human approval")
    propose.add_argument("project_id", type=int)
    propose.add_argument("title")
    propose.add_argument("--rationale", default="")
    propose.add_argument("--priority", type=int, choices=[1, 2, 3, 4, 5], default=3)
    propose.add_argument("--due-date")
    proposal_list = commands.add_parser("proposals", help="List task proposals")
    proposal_list.add_argument("--status", choices=["pending", "approved", "rejected"])
    approve = commands.add_parser("approve-proposal", help="Approve a proposal and create its task")
    approve.add_argument("proposal_id", type=int)
    reject = commands.add_parser("reject-proposal", help="Reject a pending task proposal")
    reject.add_argument("proposal_id", type=int)

    action_request = commands.add_parser("request-calendar-export", help="Queue a calendar export for explicit approval")
    action_request.add_argument("--filename", default="sage-calendar.ics")
    commands.add_parser("actions", help="List approval-gated action requests")
    action_history = commands.add_parser("action-history", help="Show the action approval and execution audit trail")
    action_history.add_argument("--request-id", type=int)
    action_history.add_argument("--limit", type=int, default=50)
    approve_action = commands.add_parser("approve-action", help="Approve and execute one queued local action")
    approve_action.add_argument("request_id", type=int)
    reject_action = commands.add_parser("reject-action", help="Reject a queued action request")
    reject_action.add_argument("request_id", type=int)
    import_ics = commands.add_parser("import-ics", help="Import calendar events as pending task proposals")
    import_ics.add_argument("source")
    import_ics.add_argument("--project-id", type=int, required=True)
    import_ics.add_argument("--limit", type=int, default=100)

    add_obligation = commands.add_parser("add-obligation", help="Record a receivable or payable")
    add_obligation.add_argument("venture_id", type=int)
    add_obligation.add_argument("obligation_type", choices=["receivable", "payable"])
    add_obligation.add_argument("amount", type=float)
    add_obligation.add_argument("due_date")
    add_obligation.add_argument("description")
    add_obligation.add_argument("--project-id", type=int)
    obligations = commands.add_parser("obligations", help="List receivables and payables")
    obligations.add_argument("--status", choices=["open", "settled", "cancelled"])
    obligations.add_argument("--venture-id", type=int)
    settle = commands.add_parser("settle-obligation", help="Settle an obligation and post the actual ledger entry")
    settle.add_argument("obligation_id", type=int)
    settle.add_argument("--date", dest="settled_date")
    cancel = commands.add_parser("cancel-obligation", help="Cancel an open obligation")
    cancel.add_argument("obligation_id", type=int)

    recurring_obligation = commands.add_parser("add-recurring-obligation", help="Create a recurring receivable or payable rule")
    recurring_obligation.add_argument("venture_id", type=int)
    recurring_obligation.add_argument("obligation_type", choices=["receivable", "payable"])
    recurring_obligation.add_argument("amount", type=float)
    recurring_obligation.add_argument("description")
    recurring_obligation.add_argument("--frequency", choices=["daily", "weekly", "monthly"], default="monthly")
    recurring_obligation.add_argument("--every", type=int, default=1)
    recurring_obligation.add_argument("--start-date")
    recurring_obligation.add_argument("--project-id", type=int)
    commands.add_parser("recurring-obligations", help="List recurring financial obligation rules")
    recurring_obligation_status = commands.add_parser("set-recurring-obligation-status", help="Pause, resume or complete a recurring financial rule")
    recurring_obligation_status.add_argument("rule_id", type=int)
    recurring_obligation_status.add_argument("status", choices=["active", "paused", "completed"])
    generate_obligations = commands.add_parser("generate-recurring-obligations", help="Generate due receivable/payable records")
    generate_obligations.add_argument("--through")
    generate_obligations.add_argument("--limit", type=int, default=100)
    cash_position = commands.add_parser("set-cash-position", help="Set a venture's manually verified opening cash balance")
    cash_position.add_argument("venture_id", type=int)
    cash_position.add_argument("opening_balance", type=float)
    cash_position.add_argument("as_of_date")
    cash_position.add_argument("--note", default="")
    commands.add_parser("cash-positions", help="List manually entered venture cash positions")

    add_note = commands.add_parser("add-note", help="Save a persistent SAGE context note")
    add_note.add_argument("title")
    add_note.add_argument("content")
    add_note.add_argument("--category", default="general")
    add_note.add_argument("--importance", type=int, choices=[1, 2, 3, 4, 5], default=3)
    note_list = commands.add_parser("notes", help="List active SAGE context notes")
    note_list.add_argument("--category")
    archive_note = commands.add_parser("archive-note", help="Archive a context note")
    archive_note.add_argument("note_id", type=int)
    generate_recurring = commands.add_parser("generate-recurring", help="Create due recurring task instances")
    generate_recurring.add_argument("--through", help="Generate occurrences due through YYYY-MM-DD")
    generate_recurring.add_argument("--limit", type=int, default=100)

    task_status = commands.add_parser("set-task-status", help="Update a task")
    task_status.add_argument("task_id", type=int)
    task_status.add_argument("status", choices=["todo", "in_progress", "done"])

    project_status = commands.add_parser(
        "set-project-status", help="Update a project"
    )
    project_status.add_argument(
        "project_id", type=int, help="Project ID"
    )
    project_status.add_argument(
        "status", choices=["active", "paused", "completed"]
    )
    edit_project = commands.add_parser("edit-project", help="Edit a project's name or description")
    edit_project.add_argument("project_id", type=int)
    edit_project.add_argument("--name")
    edit_project.add_argument("--description")
    archive_project = commands.add_parser("archive-project", help="Mark a project completed")
    archive_project.add_argument("project_id", type=int)

    edit_task = commands.add_parser("edit-task", help="Edit a task's title, priority or due date")
    edit_task.add_argument("task_id", type=int)
    edit_task.add_argument("--title")
    edit_task.add_argument("--priority", type=int)
    edit_task.add_argument("--due-date")
    edit_task.add_argument("--clear-due-date", action="store_true")
    archive_task = commands.add_parser("archive-task", help="Mark a task done")
    archive_task.add_argument("task_id", type=int)

    plan = commands.add_parser("plan", help="Show a 7-day or 30-day execution plan")
    plan.add_argument("--days", type=int, choices=[7, 30], default=7)

    review = commands.add_parser("review", help="Save or update today's executive review")
    review.add_argument("--priority", default="")
    review.add_argument("--wins", default="")
    review.add_argument("--blockers", default="")
    review.add_argument("--tomorrow", default="")
    review.add_argument("--date", dest="review_date")

    reviews = commands.add_parser("reviews", help="Show recent executive reviews")
    reviews.add_argument("--limit", type=int, default=7)

    review_summary = commands.add_parser(
        "review-summary", help="Summarize the last 7 or 30 days of reviews"
    )
    review_summary.add_argument("--days", type=int, choices=[7, 30], default=7)

    decision = commands.add_parser("decide", help="Record an executive decision")
    decision.add_argument("title")
    decision.add_argument("--choice", required=True)
    decision.add_argument("--context", default="")
    decision.add_argument("--rationale", default="")
    decision.add_argument("--date", dest="decision_date")
    decision.add_argument("--revisit")

    decisions = commands.add_parser("decisions", help="Show the decision journal")
    decisions.add_argument("--limit", type=int, default=20)

    blocker = commands.add_parser("block", help="Record an execution blocker")
    blocker.add_argument("title")
    blocker.add_argument("--details", default="")
    blocker.add_argument("--project-id", type=int)
    blocker.add_argument("--task-id", type=int)

    blocker_list = commands.add_parser("blockers", help="List blockers")
    blocker_list.add_argument("--status", choices=["open", "resolved", "all"], default="open")

    resolve = commands.add_parser("resolve-blocker", help="Resolve an open blocker")
    resolve.add_argument("blocker_id", type=int)

    serve = commands.add_parser("serve", help="Launch the local web executive cockpit")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8765)

    backup = commands.add_parser("backup", help="Create a consistent SQLite backup")
    backup.add_argument("destination", help="Backup database file path")
    backup.add_argument("--force", action="store_true", help="Replace an existing destination")

    export_json = commands.add_parser("export-json", help="Export all SAGE data as portable JSON")
    export_json.add_argument("destination", help="JSON output file path")
    export_json.add_argument("--force", action="store_true", help="Replace an existing destination")
    import_json = commands.add_parser("import-json", help="Import a SAGE JSON export into an empty database")
    import_json.add_argument("source", help="JSON export file")

    export_ics = commands.add_parser("export-ics", help="Export dated active tasks as an iCalendar file")
    export_ics.add_argument("destination", help="Calendar .ics output path")
    export_ics.add_argument("--force", action="store_true", help="Replace an existing destination")

    restore = commands.add_parser("restore", help="Restore a verified SQLite backup")
    restore.add_argument("source", help="Backup database file to restore")
    restore.add_argument("--yes", action="store_true", help="Confirm replacing the active database")

    commands.add_parser("context-preview", help="Preview the exact SAGE context prepared for AI")
    briefing = commands.add_parser("briefing", help="Build an evidence-only daily executive briefing")
    briefing.add_argument("--ai", action="store_true", help="Ask the configured AI to interpret the briefing")
    briefing.add_argument("--send-context", action="store_true", help="Approve sending the current SAGE context to the AI provider")
    briefing.add_argument("--timeout", type=float, default=45.0)
    suggest = commands.add_parser("suggest", help="Ask an external AI for an advisory suggestion")
    suggest.add_argument("goal", help="What you want help deciding or planning")
    suggest.add_argument("--send-context", action="store_true",
                         help="Explicitly approve sending the context preview to the configured provider")
    suggest.add_argument("--timeout", type=float, default=45.0)

    commands.add_parser("dashboard", help="Show a summary")
    commands.add_parser("focus", help="Show active projects and one next action")
    return parser


def _show_focus(store: SageStore) -> None:
    projects = store.list_projects()
    active_projects = [project for project in projects if project["status"] == "active"]
    paused_projects = [project for project in projects if project["status"] == "paused"]
    active_ids = {project["id"] for project in active_projects}

    print("SAGE FOCUS")
    print(f"Active projects ({len(active_projects)}):")
    for project in active_projects:
        print(f"  #{project['id']} {project['name']}")

    print(f"Paused projects ({len(paused_projects)}):")
    for project in paused_projects:
        print(f"  #{project['id']} {project['name']}")

    print("ONE ACTION PER ACTIVE PROJECT:")
    project_actions = store.project_next_actions()
    if not project_actions:
        print("  No active projects.")
    for action in project_actions:
        venture = f"[{action['venture_name']}] " if action["venture_name"] else ""
        if action["task_id"] is None:
            print(f"  {venture}{action['project_name']}: no open task; add the first action.")
        else:
            due = f" | due {action['due_date']}" if action["due_date"] else ""
            print(
                f"  {venture}{action['project_name']}: "
                f"{action['task_title']} (P{action['task_priority']}, {action['task_status']}){due}"
            )

    next_task = next(
        (
            task
            for task in store.list_tasks()
            if task["project_id"] in active_ids and task["status"] != "done"
        ),
        None,
    )

    print("ONE NEXT ACTION:")
    if next_task is None:
        print("  No open tasks in active projects.")
    else:
        print(
            f"  #{next_task['id']} [{next_task['status']}] "
            f"P{next_task['priority']} {next_task['title']} "
            f"(project: {next_task['project_name']})"
        )


def _show_plan(store: SageStore, days: int) -> None:
    plan = store.execution_plan(days)
    print(f"SAGE {days}-DAY EXECUTION PLAN ({plan['start']} to {plan['end']})")
    sections = (
        ("OVERDUE", plan["overdue"]),
        ("UPCOMING", plan["upcoming"]),
        ("UNSCHEDULED ACTIVE WORK", plan["unscheduled"]),
    )
    for label, tasks in sections:
        print(f"\n{label} ({len(tasks)}):")
        if not tasks:
            print("  Nothing here.")
            continue
        for task in tasks:
            due = f" · due {task['due_date']}" if task["due_date"] else ""
            print(
                f"  P{task['priority']} [{task['status']}] {task['title']} "
                f"— {task['project_name']}{due}"
            )


def _show_review(store: SageStore, args: argparse.Namespace) -> None:
    review = store.save_review(
        priority=args.priority, wins=args.wins, blockers=args.blockers,
        tomorrow=args.tomorrow, review_date=args.review_date,
    )
    print(f"SAGE DAILY EXECUTIVE REVIEW — {review['review_date']}")
    for label, key in (("Today's priority", "priority"), ("Wins", "wins"),
                       ("Blockers", "blockers"), ("Tomorrow's first move", "tomorrow")):
        print(f"{label}: {review[key] or '—'}")


def _show_reviews(store: SageStore, limit: int) -> None:
    reviews = store.list_reviews(limit)
    print(f"SAGE REVIEW HISTORY ({len(reviews)})")
    if not reviews:
        print("No daily reviews saved yet.")
        return
    for review in reviews:
        print(f"\n{review['review_date']} | Priority: {review['priority'] or '—'}")
        print(f"  Wins: {review['wins'] or '—'}")
        print(f"  Blockers: {review['blockers'] or '—'}")
        print(f"  Tomorrow: {review['tomorrow'] or '—'}")


def _show_review_summary(store: SageStore, days: int) -> None:
    summary = store.review_summary(days)
    print(
        f"SAGE {days}-DAY EXECUTIVE REVIEW "
        f"({summary['start']} to {summary['end']})"
    )
    print(f"Days reviewed: {summary['reviewed_days']} / {days}")
    if not summary["entries"]:
        print("No reviews recorded in this period.")
        return
    for entry in summary["entries"]:
        print(f"\n{entry['review_date']} — Priority: {entry['priority'] or '—'}")
        if entry["wins"]:
            print(f"  Wins: {entry['wins']}")
        if entry["blockers"]:
            print(f"  Blockers: {entry['blockers']}")
        if entry["tomorrow"]:
            print(f"  Next move: {entry['tomorrow']}")


def _show_decisions(store: SageStore, limit: int) -> None:
    entries = store.list_decisions(limit)
    print(f"SAGE DECISION JOURNAL ({len(entries)})")
    if not entries:
        print("No decisions recorded yet.")
        return
    for entry in entries:
        revisit = f" | revisit {entry['revisit_date']}" if entry["revisit_date"] else ""
        print(f"\n#{entry['id']} {entry['decision_date']} — {entry['title']}{revisit}")
        print(f"  Decision: {entry['choice']}")
        if entry["context"]:
            print(f"  Context: {entry['context']}")
        if entry["rationale"]:
            print(f"  Rationale: {entry['rationale']}")


def _show_blockers(store: SageStore, status: str) -> None:
    entries = store.list_blockers(status)
    print(f"SAGE BLOCKERS — {status.upper()} ({len(entries)})")
    if not entries:
        print("No blockers found.")
        return
    for entry in entries:
        linked = entry["project_name"] or "Unassigned"
        if entry["task_title"]:
            linked += f" / {entry['task_title']}"
        print(f"\n#{entry['id']} [{entry['status']}] {entry['title']} — {linked}")
        if entry["details"]:
            print(f"  Details: {entry['details']}")


def _show_dashboard(store: SageStore) -> None:
    stats = store.dashboard()
    projects = store.list_projects()
    open_blockers = store.list_blockers("open")
    latest_review = store.list_reviews(1)
    print("SAGE EXECUTIVE COCKPIT")
    print(
        f"Portfolio: {stats['active_projects']} active projects | "
        f"{sum(1 for p in projects if p['status'] == 'paused')} paused"
    )
    print(
        f"Execution: {stats['open_tasks']} open tasks | "
        f"{stats['in_progress_tasks']} in progress | "
        f"{stats['completed_tasks']} completed"
    )
    print(f"Attention: {len(open_blockers)} open blockers")
    if open_blockers:
        for item in open_blockers[:3]:
            print(f"  ! {item['title']}")
    print("\nMASTER FOCUS")
    _show_focus(store)
    print("\nLATEST DAILY REVIEW")
    if latest_review:
        review = latest_review[0]
        print(f"  {review['review_date']} | Priority: {review['priority'] or '—'}")
        print(f"  Wins: {review['wins'] or '—'}")
        print(f"  Tomorrow: {review['tomorrow'] or '—'}")
    else:
        print("  No daily review recorded yet.")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    store = SageStore(Path(args.db))

    try:
        if args.command == "add-project":
            project_id = store.add_project(args.name, args.description, args.venture_id)
            print(f"Created project #{project_id}: {args.name}")
        elif args.command == "add-venture":
            venture_id = store.add_venture(
                args.name, args.description, args.monthly_budget_cap,
                args.weekly_hours_cap, args.priority,
            )
            print(f"Created venture #{venture_id}: {args.name}")
        elif args.command == "ventures":
            summary = store.portfolio_summary()
            print("SAGE VENTURE PORTFOLIO")
            for venture in summary["ventures"]:
                budget = (
                    f"INR {venture['monthly_budget_cap']:,.2f}/month cap"
                    if venture["monthly_budget_cap"] is not None else "budget cap not set"
                )
                hours = (
                    f"{venture['weekly_hours_cap']:g} hours/week cap"
                    if venture["weekly_hours_cap"] is not None else "hours cap not set"
                )
                print(
                    f"\n#{venture['id']} [{venture['status']}] P{venture['strategic_priority']} "
                    f"{venture['name']} | {venture['active_projects']}/{venture['projects']} active projects "
                    f"| {venture['open_tasks']} open tasks | {budget} | {hours}"
                )
            print(f"Unassigned projects: {summary['unassigned_projects']}")
            print(
                f"Known caps entered: INR {summary['known_monthly_budget_caps']:,.2f}/month "
                f"across {summary['budget_cap_entries']} ventures; "
                f"{summary['known_weekly_hours_caps']:g} hours/week "
                f"across {summary['hours_cap_entries']} ventures."
            )
            for venture in summary["ventures"]:
                budget_left = (
                    f"INR {venture['month_budget_remaining']:,.2f} remaining this month"
                    if venture["month_budget_remaining"] is not None else "monthly spend cap unknown"
                )
                hours_left = (
                    f"{venture['week_hours_remaining']:g} hours remaining this week"
                    if venture["week_hours_remaining"] is not None else "weekly hours cap unknown"
                )
                print(
                    f"  Usage — {venture['name']}: INR {venture['month_revenue']:,.2f} income, "
                    f"INR {venture['month_spend']:,.2f} expenses, "
                    f"INR {venture['month_net_cash_flow']:,.2f} net this month; "
                    f"{venture['week_hours_used']:g} hours logged this week; "
                    f"{budget_left}; {hours_left}; "
                    f"open receivables INR {venture['open_receivables']:,.2f}; "
                    f"open payables INR {venture['open_payables']:,.2f}; "
                    f"30-day expected obligations net INR {venture['expected_obligation_cashflow_30d']:,.2f}; "
                    f"estimated cash {'unknown' if venture['estimated_cash_balance'] is None else 'INR ' + format(venture['estimated_cash_balance'], ',.2f')}; "
                    f"30-day cash forecast {'unknown' if venture['forecast_cash_balance_30d'] is None else 'INR ' + format(venture['forecast_cash_balance_30d'], ',.2f')}"
                )
                print(f"  Allocation readiness — {venture['allocation_readiness']}")
                if venture["allocation_blockers"]:
                    print("  Allocation blockers — " + "; ".join(venture["allocation_blockers"]))
                if venture["allocation_data_gaps"]:
                    print("  Missing allocation inputs — " + "; ".join(venture["allocation_data_gaps"]))
                print(f"  Allocation signal — {venture['allocation_signal']}")
        elif args.command in {"log-expense", "log-income", "log-time"}:
            kind = {
                "log-expense": "expense", "log-income": "income", "log-time": "time"
            }[args.command]
            quantity = args.hours if kind == "time" else args.amount
            if kind == "income":
                entry_id = store.log_income(
                    args.venture_id, quantity, args.entry_date, args.project_id, args.note
                )
            else:
                entry_id = store.log_resource(
                    args.venture_id, kind, quantity, args.entry_date, args.project_id, args.note
                )
            unit = "hours" if kind == "time" else "INR"
            print(f"Recorded {kind} #{entry_id}: {quantity} {unit} for venture #{args.venture_id}")
        elif args.command == "resources":
            entries = store.list_resource_entries(args.venture_id, args.limit)
            print(f"SAGE RESOURCE LOG ({len(entries)})")
            for entry in entries:
                quantity = f"INR {entry['quantity']:,.2f}" if entry["entry_type"] in {"expense", "income"} else f"{entry['quantity']:g} hours"
                linked = f" / {entry['project_name']}" if entry["project_name"] else ""
                print(
                    f"#{entry['id']} {entry['entry_date']} | {entry['venture_name']}{linked} "
                    f"| {entry['entry_type']}: {quantity} | {entry['note']}"
                )
        elif args.command == "assign-project":
            store.assign_project_to_venture(
                args.project_id, None if args.venture_id == 0 else args.venture_id
            )
            print(f"Assigned project #{args.project_id} to " +
                  ("no venture" if args.venture_id == 0 else f"venture #{args.venture_id}"))
        elif args.command == "projects":
            for project in store.list_projects():
                print(
                    f"#{project['id']} [{project['status']}] "
                    f"{project['name']} — {project['description']} "
                    f"(venture: {project.get('venture_name') or 'Unassigned'})"
                )
        elif args.command == "add-task":
            task_id = store.add_task(
                args.project_id, args.title, args.priority, args.due_date
            )
            print(f"Created task #{task_id}: {args.title}")
        elif args.command == "tasks":
            for task in store.list_tasks(args.project_id):
                print(
                    f"#{task['id']} [{task['status']}] "
                    f"P{task['priority']} {task['title']} "
                    f"(project: {task['project_name']})"
                )
        elif args.command == "set-task-status":
            store.set_task_status(args.task_id, args.status)
            print(f"Updated task #{args.task_id} to {args.status}")
        elif args.command == "add-recurring-task":
            recurring_id = store.add_recurring_task(
                args.project_id, args.title, args.priority, args.frequency,
                args.every, args.start_date,
            )
            print(f"Created recurring rule #{recurring_id}: {args.title}")
        elif args.command == "recurring-tasks":
            rules = store.list_recurring_tasks()
            print(f"SAGE RECURRING TASKS ({len(rules)})")
            for rule in rules:
                print(
                    f"#{rule['id']} [{rule['status']}] {rule['title']} "
                    f"| {rule['frequency']} every {rule['frequency_interval']} "
                    f"| next {rule['next_due_date']} | project: {rule['project_name']}"
                )
        elif args.command == "set-recurring-status":
            store.set_recurring_task_status(args.recurring_id, args.status)
            print(f"Recurring rule #{args.recurring_id} set to {args.status}")
        elif args.command == "propose-task":
            proposal_id = store.create_task_proposal(
                args.project_id, args.title, args.rationale, args.priority, args.due_date
            )
            print(f"Task proposal #{proposal_id} submitted for human approval.")
        elif args.command == "proposals":
            proposals = store.list_task_proposals(args.status)
            print(f"SAGE TASK PROPOSALS ({len(proposals)})")
            for proposal in proposals:
                print(
                    f"#{proposal['id']} [{proposal['status']}] {proposal['title']} "
                    f"| project: {proposal['project_name']} | P{proposal['priority']} "
                    f"| {proposal['rationale']}"
                )
        elif args.command == "approve-proposal":
            task_id = store.approve_task_proposal(args.proposal_id)
            print(f"Approved proposal #{args.proposal_id}; created task #{task_id}.")
        elif args.command == "reject-proposal":
            store.reject_task_proposal(args.proposal_id)
            print(f"Rejected proposal #{args.proposal_id}.")
        elif args.command == "request-calendar-export":
            request_id = store.create_action_request(
                "calendar_export", f"Export open dated tasks to {args.filename}", {"filename": args.filename}
            )
            print(f"Action request #{request_id} queued as pending. Nothing was exported; approve it with 'sage approve-action {request_id}'.")
        elif args.command == "actions":
            requests = store.list_action_requests()
            print(f"SAGE ACTION APPROVAL QUEUE ({len(requests)})")
            for request in requests:
                print(f"#{request['id']} [{request['status']}] {request['action_type']} | {request['summary']} | {request.get('result') or request.get('error') or 'awaiting decision'}")
        elif args.command == "action-history":
            events = store.list_action_events(args.request_id, args.limit)
            print(f"SAGE ACTION AUDIT HISTORY ({len(events)})")
            for event in events:
                print(
                    f"#{event['id']} | request #{event['action_request_id']} | "
                    f"{event['event_type']} | {event['created_at']} | {event['details']}"
                )
        elif args.command == "approve-action":
            destination = store.approve_action_request(args.request_id)
            print(f"Approved and executed action #{args.request_id}. Calendar file created: {destination}")
        elif args.command == "reject-action":
            store.reject_action_request(args.request_id)
            print(f"Rejected action request #{args.request_id}. No action was executed.")
        elif args.command == "import-ics":
            from .calendar_io import import_icalendar_proposals
            result = import_icalendar_proposals(store, args.source, args.project_id, args.limit)
            print("SAGE CALENDAR IMPORT — PENDING TASK PROPOSALS ONLY")
            print(f"Created: {result['created']} | Duplicates ignored: {result['duplicates']} | Skipped: {result['skipped']}")
            print("Review each item with 'sage proposals' and approve individually.")
        elif args.command == "add-obligation":
            obligation_id = store.add_obligation(
                args.venture_id, args.obligation_type, args.amount, args.due_date,
                args.description, args.project_id,
            )
            print(f"Created {args.obligation_type} obligation #{obligation_id}.")
        elif args.command == "obligations":
            entries = store.list_obligations(args.status, args.venture_id)
            print(f"SAGE FINANCIAL OBLIGATIONS ({len(entries)})")
            for item in entries:
                print(
                    f"#{item['id']} [{item['status']}] {item['obligation_type']} "
                    f"INR {item['amount']:,.2f} due {item['due_date']} "
                    f"| {item['venture_name']} | {item['description']}"
                )
        elif args.command == "settle-obligation":
            ledger_id = store.settle_obligation(args.obligation_id, args.settled_date)
            print(
                f"Settled obligation #{args.obligation_id}; posted actual ledger entry #{ledger_id}."
            )
        elif args.command == "cancel-obligation":
            store.cancel_obligation(args.obligation_id)
            print(f"Cancelled obligation #{args.obligation_id}.")
        elif args.command == "add-recurring-obligation":
            rule_id = store.add_recurring_obligation(
                args.venture_id, args.obligation_type, args.amount, args.description,
                args.frequency, args.every, args.start_date, args.project_id,
            )
            print(f"Created recurring {args.obligation_type} rule #{rule_id}.")
        elif args.command == "recurring-obligations":
            rules = store.list_recurring_obligations()
            print(f"SAGE RECURRING FINANCIAL RULES ({len(rules)})")
            for rule in rules:
                print(
                    f"#{rule['id']} [{rule['status']}] {rule['obligation_type']} "
                    f"INR {rule['amount']:,.2f} | {rule['description']} | "
                    f"{rule['frequency']} every {rule['frequency_interval']} | "
                    f"next {rule['next_due_date']} | {rule['venture_name']}"
                )
        elif args.command == "set-recurring-obligation-status":
            store.set_recurring_obligation_status(args.rule_id, args.status)
            print(f"Recurring financial rule #{args.rule_id} set to {args.status}")
        elif args.command == "generate-recurring-obligations":
            through = date.fromisoformat(args.through) if args.through else None
            generated = store.generate_recurring_obligations(through, args.limit)
            print(f"Generated {len(generated)} financial obligation(s).")
            for item in generated:
                print(
                    f"  #{item['obligation_id']} {item['obligation_type']} "
                    f"INR {item['amount']:,.2f} due {item['due_date']} "
                    f"| {item['venture_name']} | {item['description']}"
                )
        elif args.command == "set-cash-position":
            store.set_cash_position(
                args.venture_id, args.opening_balance, args.as_of_date, args.note
            )
            print(f"Cash position saved for venture #{args.venture_id} as of {args.as_of_date}.")
        elif args.command == "cash-positions":
            positions = store.list_cash_positions()
            print(f"SAGE CASH POSITIONS ({len(positions)})")
            for position in positions:
                print(
                    f"{position['venture_name']}: INR {position['opening_balance']:,.2f} "
                    f"as of {position['as_of_date']} | {position['note']}"
                )
        elif args.command == "add-note":
            note_id = store.add_context_note(
                args.title, args.content, args.category, args.importance
            )
            print(f"Saved SAGE context note #{note_id}.")
        elif args.command == "notes":
            notes = store.list_context_notes(category=args.category)
            print(f"SAGE CONTEXT NOTES ({len(notes)})")
            for note in notes:
                print(
                    f"#{note['id']} [{note['category']}] P{note['importance']} "
                    f"{note['title']}: {note['content']}"
                )
        elif args.command == "archive-note":
            store.archive_context_note(args.note_id)
            print(f"Archived SAGE context note #{args.note_id}.")
        elif args.command == "generate-recurring":
            through = date.fromisoformat(args.through) if args.through else None
            generated = store.generate_recurring_tasks(through, args.limit)
            print(f"Generated {len(generated)} recurring task(s).")
            for task in generated:
                print(f"  #{task['task_id']} {task['due_date']} {task['title']} ({task['project_name']})")
        elif args.command == "set-project-status":
            store.set_project_status(args.project_id, args.status)
            print(f"Updated project #{args.project_id} to {args.status}")
        elif args.command == "edit-project":
            store.update_project(args.project_id, args.name, args.description)
            print(f"Updated project #{args.project_id}")
        elif args.command == "archive-project":
            store.set_project_status(args.project_id, "completed")
            print(f"Archived project #{args.project_id} (status: completed)")
        elif args.command == "edit-task":
            store.update_task(
                args.task_id, args.title, args.priority, args.due_date,
                args.clear_due_date,
            )
            print(f"Updated task #{args.task_id}")
        elif args.command == "archive-task":
            store.set_task_status(args.task_id, "done")
            print(f"Archived task #{args.task_id} (status: done)")
        elif args.command == "plan":
            _show_plan(store, args.days)
        elif args.command == "review":
            _show_review(store, args)
        elif args.command == "reviews":
            _show_reviews(store, args.limit)
        elif args.command == "review-summary":
            _show_review_summary(store, args.days)
        elif args.command == "decide":
            decision_id = store.add_decision(
                args.title, args.choice, args.context, args.rationale,
                args.decision_date, args.revisit,
            )
            print(f"Recorded decision #{decision_id}: {args.title}")
        elif args.command == "decisions":
            _show_decisions(store, args.limit)
        elif args.command == "block":
            blocker_id = store.add_blocker(
                args.title, args.details, args.project_id, args.task_id
            )
            print(f"Recorded blocker #{blocker_id}: {args.title}")
        elif args.command == "blockers":
            _show_blockers(store, args.status)
        elif args.command == "resolve-blocker":
            store.resolve_blocker(args.blocker_id)
            print(f"Resolved blocker #{args.blocker_id}")
        elif args.command == "serve":
            from .web import serve
            serve(store, args.host, args.port)
        elif args.command == "backup":
            destination = store.backup(args.destination, overwrite=args.force)
            print(f"Database backup created: {destination}")
        elif args.command == "export-json":
            destination = store.export_data(args.destination, overwrite=args.force)
            print(f"JSON export created: {destination}")
        elif args.command == "import-json":
            imported = store.import_data(args.source)
            print("SAGE JSON IMPORT COMPLETE")
            for table, count in imported.items():
                print(f"  {table}: {count}")
        elif args.command == "export-ics":
            destination = store.export_calendar(args.destination, overwrite=args.force)
            print(f"Calendar export created: {destination}")
        elif args.command == "restore":
            if not args.yes:
                raise ValueError("Restore replaces the active database. Re-run with --yes to confirm.")
            safety_copy = store.restore_backup(args.source)
            print(f"Restored database from: {Path(args.source).expanduser().resolve()}")
            if safety_copy:
                print(f"Previous database preserved at: {safety_copy}")
            else:
                print("No previous database existed; no pre-restore copy was needed.")
        elif args.command == "context-preview":
            from .ai import preview_context
            print(preview_context(store))
        elif args.command == "briefing":
            from .ai import build_daily_briefing, format_daily_briefing
            briefing_data = build_daily_briefing(store)
            print(format_daily_briefing(briefing_data))
            if args.ai:
                if not args.send_context:
                    raise ValueError("AI context transmission requires --send-context. Review 'sage context-preview' first.")
                from .ai import AIConfig, generate_suggestion
                print("\nAI INTERPRETATION — ADVISORY ONLY")
                print(generate_suggestion(store, "Prepare today's executive briefing. Use the supplied records; distinguish facts, interpretation, recommendation and unknowns. Respect the one-master-action rule.", AIConfig.from_env(timeout=args.timeout)))
            elif args.send_context:
                raise ValueError("--send-context is only valid together with --ai.")
        elif args.command == "suggest":
            if not args.send_context:
                raise ValueError(
                    "SAGE context is not sent automatically. Review 'sage context-preview' "
                    "then re-run with --send-context to approve external transmission."
                )
            from .ai import AIConfig, generate_suggestion
            config = AIConfig.from_env(timeout=args.timeout)
            print("SAGE AI SUGGESTION — ADVISORY ONLY; NO RECORDS WERE CHANGED")
            print(generate_suggestion(store, args.goal, config))
        elif args.command == "dashboard":
            _show_dashboard(store)
        elif args.command == "focus":
            _show_focus(store)
    except (ValueError, OSError) as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
