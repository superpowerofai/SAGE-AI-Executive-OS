from urllib.request import Request, urlopen
from urllib.error import HTTPError
from threading import Thread
from time import sleep
import socket

from sage.core import SageStore
from sage.web import serve


def _free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def test_local_web_cockpit_renders_and_accepts_project(tmp_path, monkeypatch):
    db = tmp_path / "web.db"
    store = SageStore(db)
    port = _free_port()
    thread = Thread(target=serve, args=(store, "127.0.0.1", port), daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{port}"
    for _ in range(50):
        try:
            with urlopen(url, timeout=0.2) as response:
                page = response.read().decode()
            break
        except OSError:
            sleep(0.02)
    else:
        raise AssertionError("Local SAGE server did not start")

    assert "SAGE" in page and "EXECUTIVE COCKPIT" in page
    assert "DAILY EXECUTIVE BRIEFING" in page
    assert "UNKNOWN / MISSING INPUTS" in page
    assert page.count("7-DAY EXECUTION PLAN") == 1
    assert page.count("DECISION JOURNAL") == 1
    request = Request(
        url + "/add-project",
        data=b"name=Test%20venture&description=Local%20web",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urlopen(request, timeout=2) as response:
        updated = response.read().decode()
    assert "Project created." in updated
    assert "Test venture" in updated
    assert store.list_projects()[0]["name"] == "Test venture"

    decision_request = Request(
        url + "/decision",
        data=b"title=Market%20entry&choice=Agencies&rationale=Fastest%20route",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urlopen(decision_request, timeout=2) as response:
        decision_page = response.read().decode()
    assert "Decision recorded." in decision_page
    assert "Market entry" in decision_page
    assert store.list_decisions()[0]["choice"] == "Agencies"

    venture_request = Request(
        url + "/add-venture",
        data=b"name=OPERONIX%20AI&monthly_budget_cap=12000&weekly_hours_cap=15&priority=1",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urlopen(venture_request, timeout=2) as response:
        venture_page = response.read().decode()
    assert "Venture created." in venture_page
    assert "OPERONIX AI" in venture_page
    venture_id = store.list_ventures()[0]["id"]

    project_request = Request(
        url + "/add-project",
        data=f"name=Sales%20automation&venture_id={venture_id}".encode(),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urlopen(project_request, timeout=2) as response:
        project_page = response.read().decode()
    assert "Project created." in project_page
    assert next(p for p in store.list_projects() if p["name"] == "Sales automation")["venture_id"] == venture_id

    resource_request = Request(
        url + "/log-resource",
        data=f"venture_id={venture_id}&entry_type=expense&quantity=1250&note=Hosting".encode(),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urlopen(resource_request, timeout=2) as response:
        resource_page = response.read().decode()
    assert "Resource entry recorded." in resource_page
    assert store.list_resource_entries(venture_id)[0]["quantity"] == 1250

    cash_position_request = Request(
        url + "/set-cash-position",
        data=b"venture_id=1&opening_balance=10000&as_of_date=2026-11-22&note=Verified%20balance",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urlopen(cash_position_request, timeout=2) as response:
        cash_page = response.read().decode()
    assert "Manual cash position saved." in cash_page
    assert store.list_cash_positions()[0]["opening_balance"] == 10000

    note_request = Request(
        url + "/add-note",
        data=b"category=preferences&title=Operating%20rule&content=Evidence%20first&importance=1",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urlopen(note_request, timeout=2) as response:
        note_page = response.read().decode()
    assert "SAGE context note saved." in note_page
    assert store.list_context_notes()[0]["title"] == "Operating rule"

    income_request = Request(
        url + "/log-resource",
        data=f"venture_id={venture_id}&entry_type=income&quantity=5000&note=Client%20payment".encode(),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urlopen(income_request, timeout=2) as response:
        income_page = response.read().decode()
    assert "Resource entry recorded." in income_page
    assert any(item["entry_type"] == "income" for item in store.list_resource_entries(venture_id))

    edit_project_request = Request(
        url + "/edit-project",
        data=b"id=1&name=Edited%20project&description=Updated%20description",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urlopen(edit_project_request, timeout=2) as response:
        edited_page = response.read().decode()
    assert "Project updated." in edited_page
    assert store.list_projects()[0]["name"] == "Edited project"

    add_task_request = Request(
        url + "/add-task",
        data=b"project_id=1&title=Task%20to%20edit&priority=3",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urlopen(add_task_request, timeout=2) as response:
        response.read()
    edit_task_request = Request(
        url + "/edit-task",
        data=b"id=1&title=Updated%20task&priority=1",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urlopen(edit_task_request, timeout=2) as response:
        edited_task_page = response.read().decode()
    assert "Task updated." in edited_task_page
    assert store.list_tasks()[0]["title"] == "Updated task"

    from sage import ai
    received = {}
    def fake_suggestion(current_store, goal, config=None):
        received["goal"] = goal
        received["config"] = config.model
        return "One evidence-led next action."

    monkeypatch.setattr(ai, "generate_suggestion", fake_suggestion)
    monkeypatch.setenv("SAGE_AI_BASE_URL", "http://127.0.0.1:11434/v1")
    monkeypatch.setenv("SAGE_AI_MODEL", "test-local-model")
    suggest_request = Request(
        url + "/suggest",
        data=b"goal=Choose%20the%20next%20step&send_context=on",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urlopen(suggest_request, timeout=2) as response:
        suggestion_page = response.read().decode()
    assert "AI suggestion generated" in suggestion_page
    assert "One evidence-led next action." in suggestion_page
    assert received == {
        "goal": "Choose the next step",
        "config": "test-local-model",
    }

    no_consent_request = Request(
        url + "/suggest",
        data=b"goal=Do%20something",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        urlopen(no_consent_request, timeout=2)
        assert False, "AI context must not be sent without explicit consent"
    except HTTPError as error:
        assert error.code == 400
    assert received["goal"] == "Choose the next step"

    from datetime import date
    add_recurring_request = Request(
        url + "/add-recurring",
        data=f"project_id=1&title=Daily%20pipeline%20review&frequency=daily&every=1&priority=1&start_date={date.today().isoformat()}".encode(),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urlopen(add_recurring_request, timeout=2) as response:
        recurring_page = response.read().decode()
    assert "Recurring task rule created." in recurring_page
    assert len(store.list_recurring_tasks()) == 1

    generate_request = Request(
        url + "/generate-recurring",
        data=b"",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urlopen(generate_request, timeout=2) as response:
        generated_page = response.read().decode()
    assert "Generated 1 recurring task(s)." in generated_page
    assert any(task["title"] == "Daily pipeline review" for task in store.list_tasks())

    proposal_request = Request(
        url + "/propose-task",
        data=b"project_id=1&title=Proposed%20follow-up&rationale=Revenue%20action&priority=1",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urlopen(proposal_request, timeout=2) as response:
        proposal_page = response.read().decode()
    assert "Task proposal submitted for approval." in proposal_page
    assert len(store.list_task_proposals("pending")) == 1

    approve_request = Request(
        url + "/approve-proposal",
        data=b"id=1",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urlopen(approve_request, timeout=2) as response:
        approved_page = response.read().decode()
    assert "Proposal approved. Task" in approved_page
    assert any(task["title"] == "Proposed follow-up" for task in store.list_tasks())

    obligation_request = Request(
        url + "/add-obligation",
        data=b"venture_id=1&obligation_type=receivable&amount=4000&due_date=2026-12-01&description=Client%20invoice",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urlopen(obligation_request, timeout=2) as response:
        obligation_page = response.read().decode()
    assert "Financial obligation recorded." in obligation_page
    assert len(store.list_obligations("open")) == 1

    settle_request = Request(
        url + "/settle-obligation",
        data=b"id=1",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urlopen(settle_request, timeout=2) as response:
        settled_page = response.read().decode()
    assert "Obligation settled" in settled_page
    assert store.list_obligations("settled")[0]["description"] == "Client invoice"

    recurring_obligation_request = Request(
        url + "/add-recurring-obligation",
        data=b"venture_id=1&obligation_type=payable&amount=1500&description=Monthly%20hosting&frequency=monthly&every=1&start_date=2026-11-23",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urlopen(recurring_obligation_request, timeout=2) as response:
        recurring_finance_page = response.read().decode()
    assert "Recurring financial rule created." in recurring_finance_page
    generate_finance_request = Request(
        url + "/generate-recurring-obligations",
        data=b"",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urlopen(generate_finance_request, timeout=2) as response:
        generated_finance_page = response.read().decode()
    assert "Generated 1 financial obligation(s)." in generated_finance_page
    assert any(item["description"] == "Monthly hosting" for item in store.list_obligations("open"))


def test_web_server_refuses_non_local_binding(tmp_path):
    import pytest
    with pytest.raises(ValueError, match="localhost only"):
        serve(SageStore(tmp_path / "web.db"), "0.0.0.0", 8765)


def test_web_cockpit_rejects_cross_origin_mutations(tmp_path):
    db = tmp_path / "csrf.db"
    store = SageStore(db)
    port = _free_port()
    thread = Thread(target=serve, args=(store, "127.0.0.1", port), daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{port}"
    for _ in range(50):
        try:
            with urlopen(url, timeout=0.2):
                break
        except OSError:
            sleep(0.02)
    else:
        raise AssertionError("Local SAGE server did not start")

    request = Request(
        url + "/add-project",
        data=b"name=Injected",
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Origin": "https://malicious.example",
        },
        method="POST",
    )
    try:
        urlopen(request, timeout=2)
        assert False, "cross-origin request should be rejected"
    except HTTPError as error:
        assert error.code == 403
    assert store.list_projects() == []
