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


def test_web_server_refuses_non_local_binding(tmp_path):
    import pytest
    with pytest.raises(ValueError, match="localhost only"):
        serve(SageStore(tmp_path / "web.db"), "0.0.0.0", 8765)
