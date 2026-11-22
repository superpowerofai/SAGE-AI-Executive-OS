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
        print(f"\\n{label} ({len(tasks)}):")
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
        print(f"\\n{review['review_date']} | Priority: {review['priority'] or '—'}")
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
        print(f"\\n{entry['review_date']} — Priority: {entry['priority'] or '—'}")
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
        print(f"\\n#{entry['id']} {entry['decision_date']} — {entry['title']}{revisit}")
        print(f"  Decision: {entry['choice']}")
        if entry["context"]:
            print(f"  Context: {entry['context']}")
        if entry["rationale"]:
            print(f"  Rationale: {entry['rationale']}")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    store = SageStore(Path(args.db))

    try:
        if args.command == "add-project":
            project_id = store.add_project(args.name, args.description)
            print(f"Created project #{project_id}: {args.name}")
        elif args.command == "projects":
            for project in store.list_projects():
                print(
                    f"#{project['id']} [{project['status']}] "
                    f"{project['name']} — {project['description']}"
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
        elif args.command == "dashboard":
            for label, value in store.dashboard().items():
                print(f"{label.replace('_', ' ').title()}: {value}")
        elif args.command == "focus":
            _show_focus(store)
    except (ValueError, OSError) as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
