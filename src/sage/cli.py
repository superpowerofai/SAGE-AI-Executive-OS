"""Command-line interface for the SAGE local execution tracker."""
from __future__ import annotations

import argparse
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

    restore = commands.add_parser("restore", help="Restore a verified SQLite backup")
    restore.add_argument("source", help="Backup database file to restore")
    restore.add_argument("--yes", action="store_true", help="Confirm replacing the active database")

    commands.add_parser("context-preview", help="Preview the exact SAGE context prepared for AI")
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
                    f"₹{venture['monthly_budget_cap']:,.2f}/month cap"
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
                f"Known caps entered: ₹{summary['known_monthly_budget_caps']:,.2f}/month "
                f"across {summary['budget_cap_entries']} ventures; "
                f"{summary['known_weekly_hours_caps']:g} hours/week "
                f"across {summary['hours_cap_entries']} ventures."
            )
            for venture in summary["ventures"]:
                budget_left = (
                    f"₹{venture['month_budget_remaining']:,.2f} remaining this month"
                    if venture["month_budget_remaining"] is not None else "monthly spend cap unknown"
                )
                hours_left = (
                    f"{venture['week_hours_remaining']:g} hours remaining this week"
                    if venture["week_hours_remaining"] is not None else "weekly hours cap unknown"
                )
                print(
                    f"  Usage — {venture['name']}: ₹{venture['month_revenue']:,.2f} income, "
                    f"₹{venture['month_spend']:,.2f} expenses, "
                    f"₹{venture['month_net_cash_flow']:,.2f} net this month; "
                    f"{venture['week_hours_used']:g} hours logged this week; "
                    f"{budget_left}; {hours_left}"
                )
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
                quantity = f"₹{entry['quantity']:,.2f}" if entry["entry_type"] == "expense" else f"{entry['quantity']:g} hours"
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
