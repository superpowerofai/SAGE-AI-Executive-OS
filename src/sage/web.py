"""Minimal localhost web cockpit for SAGE; no third-party runtime dependencies."""
from __future__ import annotations

from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from .core import SageStore


def _page(store: SageStore, notice: str = "") -> str:
    projects = store.list_projects()
    ventures = store.portfolio_summary()["ventures"]
    resource_entries = store.list_resource_entries(limit=12)
    tasks = store.list_tasks()
    blockers = store.list_blockers("open")
    reviews = store.list_reviews(1)
    decisions = store.list_decisions(5)
    plan = store.execution_plan(7)
    active = [p for p in projects if p["status"] == "active"]
    active_ids = {p["id"] for p in active}
    next_task = next((t for t in tasks if t["project_id"] in active_ids and t["status"] != "done"), None)

    def e(value: object) -> str:
        return escape(str(value if value is not None else ""), quote=True)

    project_rows = "".join(
        f"<tr><td>#{p['id']}</td><td>{e(p['name'])}</td><td>{e(p.get('venture_name') or 'Unassigned')}</td>"
        f"<td>{e(p['status'])}</td><td><form method='post' action='/project-status'><input type='hidden' name='id' value='{p['id']}'>"
        f"<select name='status'><option>active</option><option>paused</option><option>completed</option></select>"
        f"<button>Update</button></form></td><td><form method='post' action='/edit-project'>"
        f"<input type='hidden' name='id' value='{p['id']}'><input name='name' placeholder='New name'>"
        f"<input name='description' placeholder='New description'><button>Edit</button></form></td></tr>" for p in projects
    ) or "<tr><td colspan='6'>No projects yet.</td></tr>"
    venture_rows = "".join(
        f"<tr><td>#{v['id']}</td><td>{e(v['name'])}</td><td>P{v['strategic_priority']}</td>"
        f"<td>{v['active_projects']}/{v['projects']}</td><td>{v['open_tasks']}</td>"
        f"<td>{'₹' + format(v['monthly_budget_cap'], ',.2f') if v['monthly_budget_cap'] is not None else 'Not set'}</td>"
        f"<td>₹{v['month_spend']:,.2f}</td>"
        f"<td>{str(v['weekly_hours_cap']) if v['weekly_hours_cap'] is not None else 'Not set'}</td>"
        f"<td>{v['week_hours_used']:g}</td><td>{e(v['allocation_signal'])}</td></tr>"
        for v in ventures
    ) or "<tr><td colspan='10'>No ventures registered yet.</td></tr>"
    resource_rows = "".join(
        f"<li>{e(r['entry_date'])} · {e(r['venture_name'])} · "
        f"{'₹' + format(r['quantity'], ',.2f') if r['entry_type'] == 'expense' else str(r['quantity']) + ' hours'}"
        f"{' · ' + e(r['note']) if r['note'] else ''}</li>" for r in resource_entries
    ) or "<li>No resource entries recorded yet.</li>"
    task_rows = "".join(
        f"<tr><td>#{t['id']}</td><td>{e(t['title'])}</td><td>{e(t['project_name'])}</td>"
        f"<td>{e(t['status'])}</td><td>P{t['priority']}</td><td>"
        f"<form method='post' action='/task-status'><input type='hidden' name='id' value='{t['id']}'>"
        f"<select name='status'><option>todo</option><option>in_progress</option><option>done</option></select>"
        f"<button>Update</button></form></td><td><form method='post' action='/edit-task'>"
        f"<input type='hidden' name='id' value='{t['id']}'><input name='title' placeholder='New title'>"
        f"<input name='priority' type='number' min='1' max='5' placeholder='Priority'>"
        f"<input name='due_date' type='date'><button>Edit</button></form></td></tr>" for t in tasks
    ) or "<tr><td colspan='7'>No tasks yet.</td></tr>"
    blocker_rows = "".join(
        f"<li><b>{e(b['title'])}</b> — {e(b['details'])} "
        f"<form class='inline' method='post' action='/resolve-blocker'>"
        f"<input type='hidden' name='id' value='{b['id']}'><button>Resolve</button></form></li>"
        for b in blockers
    ) or "<li>No open blockers.</li>"
    latest = reviews[0] if reviews else {}
    decision_rows = "".join(
        f"<li><b>{e(d['title'])}</b>: {e(d['choice'])}"
        f"{' — ' + e(d['rationale']) if d['rationale'] else ''}</li>"
        for d in decisions
    ) or "<li>No decisions recorded yet.</li>"
    plan_rows = "".join(
        f"<li><b>{e(t['title'])}</b> — {e(t['project_name'])} "
        f"({e(t['due_date'] or 'no due date')})</li>"
        for t in plan["overdue"] + plan["upcoming"][:8]
    ) or "<li>No dated work due in the next 7 days.</li>"
    focus = (f"{e(next_task['title'])} — {e(next_task['project_name'])}"
             if next_task else "No open next action in active projects.")
    notice_html = f"<p class='notice'>{e(notice)}</p>" if notice else ""
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>SAGE Executive Cockpit</title><style>
:root{{--bg:#101216;--panel:#1a1e25;--line:#303744;--text:#edf0f4;--muted:#aab3c0;--gold:#d8b878}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--text);font:15px system-ui,sans-serif}}
main{{max-width:1100px;margin:auto;padding:28px 18px}}h1,h2{{margin:0 0 14px}}h1{{font-size:28px}}h2{{font-size:18px;color:var(--gold)}}
p,.muted{{color:var(--muted)}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:14px;margin:18px 0}}
.card,section{{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:18px;margin:14px 0}}
.big{{font-size:25px;font-weight:700}}form{{display:flex;gap:8px;flex-wrap:wrap;margin:8px 0}}.inline{{display:inline-flex}}
input,select,textarea,button{{font:inherit;border-radius:8px;border:1px solid var(--line);padding:9px;background:#11151b;color:var(--text)}}
input,textarea{{min-width:150px;flex:1}}textarea{{width:100%;min-height:65px}}button{{background:var(--gold);color:#171717;border:0;font-weight:650;cursor:pointer}}
table{{width:100%;border-collapse:collapse}}th,td{{padding:9px;text-align:left;border-bottom:1px solid var(--line);vertical-align:middle}}th{{color:var(--muted)}}
.notice{{padding:10px;background:#293322;border-radius:8px}}a{{color:var(--gold)}}.scroll{{overflow-x:auto}}
</style></head><body><main>
<h1>SAGE <span style='color:var(--gold)'>EXECUTIVE COCKPIT</span></h1>
<p>Local-first command center · Your data stays in your local SQLite database.</p>{notice_html}
<div class='grid'>
<div class='card'><div class='muted'>Active projects</div><div class='big'>{len(active)}</div></div>
<div class='card'><div class='muted'>Open tasks</div><div class='big'>{sum(t['status'] != 'done' for t in tasks)}</div></div>
<div class='card'><div class='muted'>Open blockers</div><div class='big'>{len(blockers)}</div></div>
<div class='card'><div class='muted'>Paused projects</div><div class='big'>{sum(p['status'] == 'paused' for p in projects)}</div></div>
</div>
<section><h2>MASTER FOCUS</h2><div class='big'>{focus}</div><p>One next action from active projects.</p></section>
<section><h2>VENTURE PORTFOLIO</h2><p>Resource caps are optional planning inputs you enter; SAGE does not infer budgets or available hours.</p>
<div class='scroll'><table><tr><th>ID</th><th>Venture</th><th>Priority</th><th>Active projects</th><th>Open tasks</th><th>Monthly cap (₹)</th><th>Spent this month (₹)</th><th>Weekly cap (hours)</th><th>Logged this week</th><th>Allocation signal</th></tr>{venture_rows}</table></div>
<form method='post' action='/add-venture'><input name='name' placeholder='New venture name' required><input name='description' placeholder='Description'><input name='monthly_budget_cap' type='number' min='0' step='0.01' placeholder='Monthly budget cap ₹'><input name='weekly_hours_cap' type='number' min='0' step='0.5' placeholder='Weekly hours cap'><select name='priority'><option value='1'>P1</option><option value='2'>P2</option><option value='3' selected>P3</option><option value='4'>P4</option><option value='5'>P5</option></select><button>Add venture</button></form>
<form method='post' action='/log-resource'><select name='venture_id' required><option value=''>Choose venture</option>{''.join(f"<option value='{v['id']}'>{e(v['name'])}</option>" for v in ventures)}</select><select name='entry_type'><option value='expense'>Expense (₹)</option><option value='time'>Time (hours)</option></select><input name='quantity' type='number' min='0.01' step='0.01' placeholder='Amount / hours' required><input name='note' placeholder='What was spent / worked on'><button>Log resource</button></form>
<h3>Recent resource entries</h3><ul>{resource_rows}</ul></section>
<section><h2>PROJECT PORTFOLIO</h2><div class='scroll'><table><tr><th>ID</th><th>Project</th><th>Venture</th><th>Status</th><th>Change status</th><th>Edit</th></tr>{project_rows}</table></div>
<form method='post' action='/add-project'><input name='name' placeholder='New project name' required><input name='description' placeholder='Description'><select name='venture_id'><option value=''>No venture</option>{''.join(f"<option value='{v['id']}'>{e(v['name'])}</option>" for v in ventures)}</select><button>Add project</button></form>
<form method='post' action='/assign-project'><select name='project_id' required><option value=''>Choose project</option>{''.join(f"<option value='{p['id']}'>{e(p['name'])}</option>" for p in projects)}</select><select name='venture_id'><option value='0'>Unassigned</option>{''.join(f"<option value='{v['id']}'>{e(v['name'])}</option>" for v in ventures)}</select><button>Assign project</button></form></section>
<section><h2>EXECUTION</h2><div class='scroll'><table><tr><th>ID</th><th>Task</th><th>Project</th><th>Status</th><th>Priority</th><th>Update status</th><th>Edit</th></tr>{task_rows}</table></div>
<form method='post' action='/add-task'><select name='project_id' required><option value=''>Choose project</option>{''.join(f"<option value='{p['id']}'>{e(p['name'])}</option>" for p in active)}</select><input name='title' placeholder='Next action' required><select name='priority'><option value='1'>P1</option><option value='2'>P2</option><option value='3' selected>P3</option><option value='4'>P4</option><option value='5'>P5</option></select><input type='date' name='due_date'><button>Add task</button></form></section>
<section><h2>7-DAY EXECUTION PLAN</h2><ul>{plan_rows}</ul></section>
<section><h2>DECISION JOURNAL</h2><ul>{decision_rows}</ul>
<form method='post' action='/decision'><input name='title' placeholder='Decision title' required><input name='choice' placeholder='Chosen option' required><input name='rationale' placeholder='Reasoning'><button>Record decision</button></form></section>
<section><h2>7-DAY EXECUTION PLAN</h2><ul>{plan_rows}</ul></section>
<section><h2>DECISION JOURNAL</h2><ul>{decision_rows}</ul>
<form method='post' action='/decision'><input name='title' placeholder='Decision title' required><input name='choice' placeholder='Chosen option' required><input name='rationale' placeholder='Reasoning'><button>Record decision</button></form></section>
<section><h2>DAILY EXECUTIVE REVIEW</h2><p>Latest: {e(latest.get('review_date','Not recorded'))} · Priority: {e(latest.get('priority','—') or '—')}</p>
<p>Wins: {e(latest.get('wins','—') or '—')} · Tomorrow: {e(latest.get('tomorrow','—') or '—')}</p>
<form method='post' action='/review'><input name='priority' placeholder="Today's priority"><input name='wins' placeholder='Wins'><input name='blockers' placeholder='Blockers'><input name='tomorrow' placeholder="Tomorrow's first move"><button>Save review</button></form></section>
<section><h2>BLOCKERS</h2><ul>{blocker_rows}</ul>
<form method='post' action='/add-blocker'><input name='title' placeholder='Blocker' required><input name='details' placeholder='What is blocking progress?'><button>Record blocker</button></form></section>
<footer class='muted'>SAGE local web cockpit · No cloud sync, external AI calls or remote access are enabled.</footer>
</main></body></html>"""


def serve(store: SageStore, host: str = "127.0.0.1", port: int = 8765) -> None:
    if host not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("SAGE web cockpit currently binds to localhost only.")

    class Handler(BaseHTTPRequestHandler):
        def _send(self, status: int, body: str) -> None:
            payload = body.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(payload)

        def do_GET(self) -> None:
            if urlparse(self.path).path != "/":
                self._send(404, "Not found")
                return
            self._send(200, _page(store))

        def do_POST(self) -> None:
            if urlparse(self.path).path not in {
                "/add-project", "/add-venture", "/assign-project", "/log-resource", "/add-task",
                "/task-status", "/project-status", "/edit-project", "/edit-task", "/review", "/add-blocker",
                "/resolve-blocker", "/decision",
            }:
                self._send(404, "Not found")
                return
            length = int(self.headers.get("Content-Length", "0"))
            if length > 20000:
                self._send(413, "Request too large")
                return
            form = parse_qs(self.rfile.read(length).decode("utf-8"), keep_blank_values=True)
            data = {key: values[0] for key, values in form.items()}
            try:
                path = urlparse(self.path).path
                if path == "/add-project":
                    venture_id = int(data["venture_id"]) if data.get("venture_id") else None
                    store.add_project(data.get("name", ""), data.get("description", ""), venture_id)
                    notice = "Project created."
                elif path == "/add-venture":
                    budget = float(data["monthly_budget_cap"]) if data.get("monthly_budget_cap") else None
                    hours = float(data["weekly_hours_cap"]) if data.get("weekly_hours_cap") else None
                    store.add_venture(data.get("name", ""), data.get("description", ""),
                                      budget, hours, int(data.get("priority", "3")))
                    notice = "Venture created."
                elif path == "/assign-project":
                    venture_id = int(data.get("venture_id", "0"))
                    store.assign_project_to_venture(
                        int(data["project_id"]), None if venture_id == 0 else venture_id
                    )
                    notice = "Project venture assignment updated."
                elif path == "/log-resource":
                    store.log_resource(
                        int(data["venture_id"]), data.get("entry_type", "expense"),
                        float(data.get("quantity", "0")), project_id=None,
                        note=data.get("note", ""),
                    )
                    notice = "Resource entry recorded."
                elif path == "/add-task":
                    due = data.get("due_date") or None
                    store.add_task(int(data["project_id"]), data.get("title", ""),
                                   int(data.get("priority", "3")), due)
                    notice = "Task created."
                elif path == "/task-status":
                    store.set_task_status(int(data["id"]), data["status"])
                    notice = "Task status updated."
                elif path == "/project-status":
                    store.set_project_status(int(data["id"]), data["status"])
                    notice = "Project status updated."
                elif path == "/edit-project":
                    store.update_project(
                        int(data["id"]), data.get("name") or None,
                        data.get("description") or None,
                    )
                    notice = "Project updated."
                elif path == "/edit-task":
                    store.update_task(
                        int(data["id"]), data.get("title") or None,
                        int(data["priority"]) if data.get("priority") else None,
                        data.get("due_date") or None,
                    )
                    notice = "Task updated."
                elif path == "/review":
                    store.save_review(data.get("priority", ""), data.get("wins", ""),
                                      data.get("blockers", ""), data.get("tomorrow", ""))
                    notice = "Daily review saved."
                elif path == "/decision":
                    store.add_decision(data.get("title", ""), data.get("choice", ""),
                                       rationale=data.get("rationale", ""))
                    notice = "Decision recorded."
                elif path == "/add-blocker":
                    store.add_blocker(data.get("title", ""), data.get("details", ""))
                    notice = "Blocker recorded."
                else:
                    store.resolve_blocker(int(data["id"]))
                    notice = "Blocker resolved."
                self._send(200, _page(store, notice))
            except (ValueError, KeyError) as error:
                self._send(400, _page(store, f"Could not save: {error}"))

        def log_message(self, format: str, *args: object) -> None:
            return

    server = ThreadingHTTPServer((host, port), Handler)
    print(f"SAGE cockpit running at http://{host}:{port} (Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nSAGE cockpit stopped.")
    finally:
        server.server_close()
