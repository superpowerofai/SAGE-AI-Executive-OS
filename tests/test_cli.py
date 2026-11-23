from sage.cli import main


def test_cli_project_task_and_dashboard_flow(tmp_path, capsys):
    database = str(tmp_path / "sage.db")
    assert main(["--db", database, "add-project", "Portfolio", "--description", "Build real projects"]) == 0
    assert "Created project #1: Portfolio" in capsys.readouterr().out

    assert main(["--db", database, "add-task", "1", "Ship first feature", "--priority", "1"]) == 0
    assert "Created task #1: Ship first feature" in capsys.readouterr().out

    assert main(["--db", database, "tasks"]) == 0
    task_output = capsys.readouterr().out
    assert "Ship first feature" in task_output
    assert "Portfolio" in task_output

    assert main(["--db", database, "dashboard"]) == 0
    dashboard_output = capsys.readouterr().out
    assert "SAGE EXECUTIVE COCKPIT" in dashboard_output
    assert "Portfolio: 1 active projects" in dashboard_output
    assert "Execution: 1 open tasks" in dashboard_output


def test_cli_can_update_task_status(tmp_path, capsys):
    database = str(tmp_path / "sage.db")
    main(["--db", database, "add-project", "SAGE"])
    capsys.readouterr()
    main(["--db", database, "add-task", "1", "Run tests"])
    capsys.readouterr()

    assert main(["--db", database, "set-task-status", "1", "done"]) == 0
    assert "Updated task #1 to done" in capsys.readouterr().out

    main(["--db", database, "dashboard"])
    dashboard_output = capsys.readouterr().out
    assert "Execution: 0 open tasks" in dashboard_output
    assert "1 completed" in dashboard_output


def test_cli_focus_shows_active_paused_and_one_next_action(tmp_path, capsys):
    database = str(tmp_path / "sage.db")
    main(["--db", database, "add-project", "Active project"])
    capsys.readouterr()
    main(["--db", database, "add-project", "Paused project"])
    capsys.readouterr()
    main(["--db", database, "set-project-status", "2", "paused"])
    capsys.readouterr()
    main(["--db", database, "add-task", "1", "Important task", "--priority", "1"])
    capsys.readouterr()
    main(["--db", database, "add-task", "2", "Paused task", "--priority", "1"])
    capsys.readouterr()

    assert main(["--db", database, "focus"]) == 0
    output = capsys.readouterr().out
    assert "Active projects (1):" in output
    assert "Active project" in output
    assert "Paused projects (1):" in output
    assert "Paused project" in output
    assert "ONE NEXT ACTION:" in output
    assert "Important task" in output
    assert "Paused task" not in output


def test_cli_venture_and_resource_tracking(tmp_path, capsys):
    database = str(tmp_path / "venture.db")
    assert main(["--db", database, "add-venture", "OPERONIX AI",
                 "--priority", "1", "--monthly-budget-cap", "20000",
                 "--weekly-hours-cap", "15"]) == 0
    assert "Created venture #1" in capsys.readouterr().out

    assert main(["--db", database, "add-project", "Lead system",
                 "--venture-id", "1"]) == 0
    capsys.readouterr()

    assert main(["--db", database, "log-expense", "1", "1200",
                 "--note", "Hosting"]) == 0
    assert "Recorded expense" in capsys.readouterr().out

    assert main(["--db", database, "log-time", "1", "2.5",
                 "--note", "Workflow build"]) == 0
    assert "Recorded time" in capsys.readouterr().out
    assert main(["--db", database, "log-income", "1", "9500",
                 "--note", "First client payment"]) == 0
    assert "Recorded income" in capsys.readouterr().out

    assert main(["--db", database, "ventures"]) == 0
    output = capsys.readouterr().out
    assert "OPERONIX AI" in output
    assert "INR 9,500.00 income" in output
    assert "INR 1,200.00 expenses" in output
    assert "2.5 hours logged this week" in output

    assert main(["--db", database, "resources", "--venture-id", "1"]) == 0
    assert "Hosting" in capsys.readouterr().out


def test_cli_restore_requires_explicit_confirmation(tmp_path):
    import pytest

    database = str(tmp_path / "active.db")
    with pytest.raises(SystemExit):
        main(["--db", database, "restore", str(tmp_path / "backup.db")])


def test_cli_backup_export_and_confirmed_restore(tmp_path, capsys):
    database = str(tmp_path / "active.db")
    backup = str(tmp_path / "backup.db")
    exported = str(tmp_path / "export.json")

    main(["--db", database, "add-project", "Keep this"])
    capsys.readouterr()
    assert main(["--db", database, "backup", backup]) == 0
    assert "Database backup created" in capsys.readouterr().out

    main(["--db", database, "add-project", "Remove after restore"])
    capsys.readouterr()
    assert main(["--db", database, "export-json", exported]) == 0
    assert "JSON export created" in capsys.readouterr().out

    assert main(["--db", database, "restore", backup, "--yes"]) == 0
    output = capsys.readouterr().out
    assert "Restored database from" in output
    assert "Previous database preserved at" in output

    main(["--db", database, "projects"])
    project_output = capsys.readouterr().out
    assert "Keep this" in project_output
    assert "Remove after restore" not in project_output


def test_cli_serve_invokes_local_web_cockpit(tmp_path, monkeypatch):
    from sage import web

    called = {}
    def fake_serve(store, host, port):
        called.update(host=host, port=port, database=store.database)

    monkeypatch.setattr(web, "serve", fake_serve)
    database = str(tmp_path / "serve.db")
    assert main(["--db", database, "serve", "--host", "localhost", "--port", "9876"]) == 0
    assert called == {"host": "localhost", "port": 9876, "database": database}


def test_cli_edit_and_archive_commands(tmp_path, capsys):
    database = str(tmp_path / "edit-cli.db")
    main(["--db", database, "add-project", "Draft project"])
    capsys.readouterr()
    main(["--db", database, "add-task", "1", "Draft task"])
    capsys.readouterr()

    assert main(["--db", database, "edit-project", "1",
                 "--name", "Final project"]) == 0
    assert "Updated project #1" in capsys.readouterr().out
    assert main(["--db", database, "edit-task", "1",
                 "--title", "Final task", "--priority", "1"]) == 0
    assert "Updated task #1" in capsys.readouterr().out

    assert main(["--db", database, "archive-task", "1"]) == 0
    assert "Archived task #1" in capsys.readouterr().out
    assert main(["--db", database, "archive-project", "1"]) == 0
    assert "Archived project #1" in capsys.readouterr().out


def test_cli_ai_suggestion_requires_explicit_context_consent(tmp_path):
    import pytest

    with pytest.raises(SystemExit):
        main(["--db", str(tmp_path / "ai.db"), "suggest", "Choose my next priority"])


def test_cli_recurring_task_commands(tmp_path, capsys):
    database = str(tmp_path / "recurring-cli.db")
    main(["--db", database, "add-project", "Operations"])
    capsys.readouterr()

    assert main(["--db", database, "add-recurring-task", "1", "Daily review",
                 "--frequency", "daily", "--start-date", "2026-11-23"]) == 0
    assert "Created recurring rule #1" in capsys.readouterr().out

    assert main(["--db", database, "generate-recurring", "--through", "2026-11-24"]) == 0
    assert "Generated 2 recurring task(s)" in capsys.readouterr().out

    assert main(["--db", database, "recurring-tasks"]) == 0
    assert "next 2026-11-25" in capsys.readouterr().out

    assert main(["--db", database, "set-recurring-status", "1", "paused"]) == 0
    assert "set to paused" in capsys.readouterr().out


def test_cli_task_proposals_require_approval(tmp_path, capsys):
    database = str(tmp_path / "proposal-cli.db")
    main(["--db", database, "add-project", "Sales"])
    capsys.readouterr()

    assert main(["--db", database, "propose-task", "1", "Contact a prospect",
                 "--rationale", "Direct revenue action", "--priority", "1"]) == 0
    assert "submitted for human approval" in capsys.readouterr().out

    assert main(["--db", database, "tasks"]) == 0
    assert "Contact a prospect" not in capsys.readouterr().out

    assert main(["--db", database, "approve-proposal", "1"]) == 0
    assert "created task #1" in capsys.readouterr().out
    assert main(["--db", database, "tasks"]) == 0
    assert "Contact a prospect" in capsys.readouterr().out


def test_cli_obligation_tracking_and_settlement(tmp_path, capsys):
    database = str(tmp_path / "obligation-cli.db")
    main(["--db", database, "add-venture", "Service venture"])
    capsys.readouterr()
    main(["--db", database, "add-obligation", "1", "receivable", "12500",
          "2026-12-01", "Client invoice"])
    assert "Created receivable obligation #1" in capsys.readouterr().out
    assert main(["--db", database, "obligations", "--status", "open"]) == 0
    assert "INR 12,500.00" in capsys.readouterr().out
    assert main(["--db", database, "settle-obligation", "1",
                 "--date", "2026-11-23"]) == 0
    assert "posted actual ledger entry" in capsys.readouterr().out
    assert main(["--db", database, "ventures"]) == 0
    output = capsys.readouterr().out
    assert "INR 12,500.00 income" in output


def test_cli_recurring_financial_obligation_commands(tmp_path, capsys):
    database = str(tmp_path / "recurring-finance-cli.db")
    main(["--db", database, "add-venture", "Office"])
    capsys.readouterr()
    assert main(["--db", database, "add-recurring-obligation", "1", "payable",
                 "9000", "Office rent", "--frequency", "monthly",
                 "--start-date", "2026-11-23"]) == 0
    assert "Created recurring payable rule #1" in capsys.readouterr().out
    assert main(["--db", database, "generate-recurring-obligations",
                 "--through", "2026-11-23"]) == 0
    assert "Generated 1 financial obligation(s)" in capsys.readouterr().out
    assert main(["--db", database, "obligations", "--status", "open"]) == 0
    assert "Office rent" in capsys.readouterr().out


def test_cli_manual_cash_position(tmp_path, capsys):
    database = str(tmp_path / "cash-cli.db")
    main(["--db", database, "add-venture", "Cash venture"])
    capsys.readouterr()
    assert main(["--db", database, "set-cash-position", "1", "15000",
                 "2026-11-22", "--note", "Verified balance"]) == 0
    assert "Cash position saved" in capsys.readouterr().out
    assert main(["--db", database, "cash-positions"]) == 0
    output = capsys.readouterr().out
    assert "INR 15,000.00" in output
    assert "Verified balance" in output
