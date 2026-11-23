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


def test_local_web_cockpit_renders_and_accepts_project(tmp_path):
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


def test_web_server_refuses_non_local_binding(tmp_path):
    import pytest
    with pytest.raises(ValueError, match="localhost only"):
        serve(SageStore(tmp_path / "web.db"), "0.0.0.0", 8765)
