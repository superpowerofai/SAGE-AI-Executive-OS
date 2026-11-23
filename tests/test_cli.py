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

    assert main(["--db", database, "ventures"]) == 0
    output = capsys.readouterr().out
    assert "OPERONIX AI" in output
    assert "₹1,200.00 spent this month" in output
    assert "2.5 hours logged this week" in output

    assert main(["--db", database, "resources", "--venture-id", "1"]) == 0
    assert "Hosting" in capsys.readouterr().out
