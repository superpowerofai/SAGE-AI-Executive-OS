"""Minimal localhost web cockpit for SAGE; no third-party runtime dependencies."""
from __future__ import annotations

from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from .core import SageStore


def _page(store: SageStore, notice: str = "", suggestion: str = "") -> str:
    projects = store.list_projects()
    ventures = store.portfolio_summary()["ventures"]
    resource_entries = store.list_resource_entries(limit=12)
    project_actions = store.project_next_actions()
    recurring_rules = store.list_recurring_tasks()
    proposals = store.list_task_proposals()
    action_requests = store.list_action_requests()
    obligations = store.list_obligations()
    recurring_obligations = store.list_recurring_obligations()
    cash_positions = store.list_cash_positions()
    context_notes = store.list_context_notes()
    tasks = store.list_tasks()
    blockers = store.list_blockers("open")
    reviews = store.list_reviews(1)
    decisions = store.list_decisions(5)
    plan = store.execution_plan(7)
    active = [p for p in projects if p["status"] == "active"]
    active_ids = {p["id"] for p in active}
    next_task = next((t for t in tasks if t["project_id"] in active_ids and t["status"] != "done"), None)
    from .ai import build_daily_briefing, format_daily_briefing
    briefing_html = f"<section><h2>DAILY EXECUTIVE BRIEFING</h2><pre class='suggestion'>{escape(format_daily_briefing(build_daily_briefing(store)))}</pre></section>"

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
        f"<td>₹{v['month_revenue']:,.2f}</td><td>₹{v['month_spend']:,.2f}</td>"
        f"<td>₹{v['month_net_cash_flow']:,.2f}</td>"
        f"<td>₹{v['open_receivables']:,.2f}</td><td>₹{v['open_payables']:,.2f}</td>"
        f"<td>₹{v['expected_obligation_cashflow_30d']:,.2f}</td>"
        f"<td>{'Not set' if v['estimated_cash_balance'] is None else '₹' + format(v['estimated_cash_balance'], ',.2f')}</td>"
        f"<td>{'Not set' if v['forecast_cash_balance_30d'] is None else '₹' + format(v['forecast_cash_balance_30d'], ',.2f')}</td>"
        f"<td>{str(v['weekly_hours_cap']) if v['weekly_hours_cap'] is not None else 'Not set'}</td>"
        f"<td>{v['week_hours_used']:g}</td><td>{e(v['allocation_readiness'])}</td>"
        f"<td>{e('; '.join(v['allocation_blockers']) or 'No recorded blockers')}</td>"
        f"<td>{e('; '.join(v['allocation_data_gaps']) or 'No identified data gaps')}</td>"
        f"<td>{e(v['allocation_signal'])}</td></tr>"
        for v in ventures
    ) or "<tr><td colspan='20'>No ventures registered yet.</td></tr>"
    recurring_obligation_rows = "".join(
        f"<tr><td>#{rule['id']}</td><td>{e(rule['venture_name'])}</td><td>{e(rule['obligation_type'])}</td>"
        f"<td>INR {rule['amount']:,.2f}</td><td>{e(rule['description'])}</td>"
        f"<td>{e(rule['frequency'])} × {rule['frequency_interval']}</td>"
        f"<td>{e(rule['next_due_date'])}</td><td>{e(rule['status'])}</td><td>"
        f"<form method='post' action='/recurring-obligation-status'><input type='hidden' name='id' value='{rule['id']}'>"
        f"<select name='status'><option>active</option><option>paused</option><option>completed</option></select>"
        f"<button>Update</button></form></td></tr>" for rule in recurring_obligations
    ) or "<tr><td colspan='9'>No recurring financial rules.</td></tr>"
    context_note_rows = "".join(
        f"<tr><td>#{note['id']}</td><td>{e(note['category'])}</td><td>{e(note['title'])}</td>"
        f"<td>P{note['importance']}</td><td>{e(note['content'])}</td><td>"
        f"<form method='post' action='/archive-note'><input type='hidden' name='id' value='{note['id']}'>"
        f"<button class='secondary'>Archive</button></form></td></tr>" for note in context_notes
    ) or "<tr><td colspan='6'>No active context notes.</td></tr>"
    obligation_rows = "".join(
        f"<tr><td>#{o['id']}</td><td>{e(o['venture_name'])}</td><td>{e(o['obligation_type'])}</td>"
        f"<td>INR {o['amount']:,.2f}</td><td>{e(o['due_date'])}</td><td>{e(o['description'])}</td>"
        f"<td>{e(o['status'])}</td><td>" + (
            f"<form method='post' action='/settle-obligation'><input type='hidden' name='id' value='{o['id']}'><button>Settle</button></form>"
            f"<form method='post' action='/cancel-obligation'><input type='hidden' name='id' value='{o['id']}'><button class='secondary'>Cancel</button></form>"
            if o["status"] == "open" else "—"
        ) + "</td></tr>" for o in obligations
    ) or "<tr><td colspan='8'>No financial obligations recorded.</td></tr>"
    proposal_rows = "".join(
        f"<tr><td>#{p['id']}</td><td>{e(p['project_name'])}</td><td>{e(p['title'])}</td>"
        f"<td>{e(p['rationale'])}</td><td>P{p['priority']}</td><td>{e(p['status'])}</td><td>"
        + (
            f"<form method='post' action='/approve-proposal'><input type='hidden' name='id' value='{p['id']}'><button>Approve → create task</button></form>"
            f"<form method='post' action='/reject-proposal'><input type='hidden' name='id' value='{p['id']}'><button class='secondary'>Reject</button></form>"
            if p["status"] == "pending" else "—"
        ) + "</td></tr>" for p in proposals
    ) or "<tr><td colspan='7'>No task proposals.</td></tr>"
    recurring_rows = "".join(
        f"<tr><td>#{rule['id']}</td><td>{e(rule['project_name'])}</td><td>{e(rule['title'])}</td>"
        f"<td>{e(rule['frequency'])} × {rule['frequency_interval']}</td><td>{e(rule['next_due_date'])}</td>"
        f"<td>{e(rule['status'])}</td><td><form method='post' action='/recurring-status'>"
        f"<input type='hidden' name='id' value='{rule['id']}'><select name='status'>"
        f"<option>active</option><option>paused</option><option>completed</option></select>"
        f"<button>Update</button></form></td></tr>" for rule in recurring_rules
    ) or "<tr><td colspan='7'>No recurring task rules.</td></tr>"
    action_rows = "".join(
        f"<tr><td>#{a['id']}</td><td>{e(a['action_type'])}</td><td>{e(a['summary'])}</td>"
        f"<td>{e(a['status'])}</td><td>{e(a.get('result') or a.get('error') or 'Awaiting decision')}</td><td>" + (
            f"<form method='post' action='/approve-action'><input type='hidden' name='id' value='{a['id']}'><button>Approve & execute</button></form>"
            f"<form method='post' action='/reject-action'><input type='hidden' name='id' value='{a['id']}'><button class='secondary'>Reject</button></form>"
            if a['status'] == 'pending' else "—"
        ) + "</td></tr>" for a in action_requests
    ) or "<tr><td colspan='6'>No action requests.</td></tr>"
    project_action_rows = "".join(
        f"<li><strong>{e(a['venture_name'] or 'Unassigned')} · {e(a['project_name'])}</strong>: "
        f"{e(a['task_title']) if a['task_id'] is not None else 'No open task — add the first action'}"
        f"{' · P' + str(a['task_priority']) if a['task_priority'] is not None else ''}"
        f"{' · due ' + e(a['due_date']) if a['due_date'] else ''}</li>"
        for a in project_actions
    ) or "<li>No active projects.</li>"
    resource_rows = "".join(
        f"<li>{e(r['entry_date'])} · {e(r['venture_name'])} · "
        f"{'₹' + format(r['quantity'], ',.2f') if r['entry_type'] in {'expense', 'income'} else str(r['quantity']) + ' hours'}"
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
    suggestion_html = f"<pre class='suggestion'>{e(suggestion)}</pre>" if suggestion else ""
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
 .notice{{padding:10px;background:#293322;border-radius:8px}}.suggestion{{white-space:pre-wrap;overflow-wrap:anywhere;background:#11151b;padding:14px;border-radius:8px;border:1px solid var(--line)}}a{{color:var(--gold)}}.scroll{{overflow-x:auto}}
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
{briefing_html}
<section><h2>SAGE CONTEXT NOTES</h2><p>Store durable operating preferences, constraints and business context for the local AI advisor. Do not store passwords, bank account numbers or other secrets.</p>
<div class='scroll'><table><tr><th>ID</th><th>Category</th><th>Title</th><th>Importance</th><th>Content</th><th>Action</th></tr>{context_note_rows}</table></div>
<form method='post' action='/add-note'><input name='category' placeholder='Category (e.g. preferences, strategy)' value='general'><input name='title' placeholder='Short note title' required><textarea name='content' placeholder='Durable context for SAGE' required></textarea><select name='importance'><option value='1'>P1 · Critical</option><option value='2'>P2 · High</option><option value='3' selected>P3 · Normal</option><option value='4'>P4 · Low</option><option value='5'>P5 · Reference</option></select><button>Save context note</button></form></section>
<section><h2>RECURRING FINANCIAL OBLIGATIONS</h2><p>Rules generate future receivables/payables for review; they never pay or collect automatically.</p>
<div class='scroll'><table><tr><th>ID</th><th>Venture</th><th>Type</th><th>Amount</th><th>Description</th><th>Frequency</th><th>Next due</th><th>Status</th><th>Change status</th></tr>{recurring_obligation_rows}</table></div>
<form method='post' action='/add-recurring-obligation'><select name='venture_id' required><option value=''>Choose venture</option>{''.join(f"<option value='{v['id']}'>{e(v['name'])}</option>" for v in ventures)}</select><select name='obligation_type'><option value='payable'>Recurring cost / payable</option><option value='receivable'>Recurring income / receivable</option></select><input name='amount' type='number' min='0.01' step='0.01' placeholder='Amount INR' required><input name='description' placeholder='Rent, retainer, payroll...' required><select name='frequency'><option>daily</option><option>weekly</option><option selected>monthly</option></select><input name='every' type='number' min='1' max='365' value='1'><input name='start_date' type='date'><button>Add recurring financial rule</button></form>
<form method='post' action='/generate-recurring-obligations'><button>Generate due obligations</button></form></section>
<section><h2>RECEIVABLES & PAYABLES</h2><p>Open obligations are forecasts, not cash balances. Settling one posts the actual income or expense to the ledger; cancelling does not.</p>
<div class='scroll'><table><tr><th>ID</th><th>Venture</th><th>Type</th><th>Amount</th><th>Due date</th><th>Description</th><th>Status</th><th>Actions</th></tr>{obligation_rows}</table></div>
<form method='post' action='/add-obligation'><select name='venture_id' required><option value=''>Choose venture</option>{''.join(f"<option value='{v['id']}'>{e(v['name'])}</option>" for v in ventures)}</select><select name='obligation_type'><option value='receivable'>Receivable</option><option value='payable'>Payable</option></select><input name='amount' type='number' min='0.01' step='0.01' placeholder='Amount INR' required><input name='due_date' type='date' required><input name='description' placeholder='What is owed / due?' required><button>Add obligation</button></form></section>
<section><h2>HUMAN APPROVAL QUEUE</h2><p>Proposed tasks do not enter the execution plan until you approve them. Approval creates the task; rejection records the decision.</p>
<div class='scroll'><table><tr><th>ID</th><th>Project</th><th>Proposed task</th><th>Rationale</th><th>Priority</th><th>Status</th><th>Decision</th></tr>{proposal_rows}</table></div>
<form method='post' action='/propose-task'><select name='project_id' required><option value=''>Choose project</option>{''.join(f"<option value='{p['id']}'>{e(p['name'])}</option>" for p in projects)}</select><input name='title' placeholder='Proposed next task' required><input name='rationale' placeholder='Why this task?'><select name='priority'><option value='1'>P1</option><option value='2'>P2</option><option value='3' selected>P3</option><option value='4'>P4</option><option value='5'>P5</option></select><input name='due_date' type='date'><button>Submit for approval</button></form></section>
<section><h2>CONTROLLED ACTIONS</h2><p>Only allow-listed actions can run. Requests are inert until you approve them. Current built-in action: create a local calendar export in the SAGE exports folder. No email, payment, or remote action is enabled.</p>
<div class='scroll'><table><tr><th>ID</th><th>Action</th><th>Preview</th><th>Status</th><th>Result</th><th>Decision</th></tr>{action_rows}</table></div>
<form method='post' action='/request-calendar-export'><input name='filename' value='sage-calendar.ics' required><button>Request calendar export (approval required)</button></form></section>
<section><h2>RECURRING TASKS</h2><p>Rules generate dated task instances only when you press Generate due tasks. Generation is bounded to 100 instances per request.</p>
<div class='scroll'><table><tr><th>ID</th><th>Project</th><th>Task</th><th>Frequency</th><th>Next due</th><th>Status</th><th>Change status</th></tr>{recurring_rows}</table></div>
<form method='post' action='/add-recurring'><select name='project_id' required><option value=''>Choose project</option>{''.join(f"<option value='{p['id']}'>{e(p['name'])}</option>" for p in projects if p['status'] == 'active')}</select><input name='title' placeholder='Recurring task' required><select name='frequency'><option>daily</option><option selected>weekly</option><option>monthly</option></select><input name='every' type='number' min='1' max='365' value='1' title='Repeat every N units'><select name='priority'><option value='1'>P1</option><option value='2'>P2</option><option value='3' selected>P3</option><option value='4'>P4</option><option value='5'>P5</option></select><input name='start_date' type='date'><button>Add recurring rule</button></form>
<form method='post' action='/generate-recurring'><button>Generate due tasks</button></form></section>
<section><h2>ONE ACTION PER ACTIVE PROJECT</h2><ul>{project_action_rows}</ul></section>
<section><h2>VENTURE PORTFOLIO</h2><p>Cash estimates use your manually entered opening balance plus recorded ledger entries. The 30-day forecast adds open obligations due by then; it is not a bank feed and excludes unrecorded transactions.</p><p>Resource caps are optional planning inputs you enter; SAGE does not infer budgets or available hours.</p>
<div class='scroll'><table><tr><th>ID</th><th>Venture</th><th>Priority</th><th>Active projects</th><th>Open tasks</th><th>Monthly cap (₹)</th><th>Income this month (₹)</th><th>Expenses this month (₹)</th><th>Net this month (₹)</th><th>Open receivables (₹)</th><th>Open payables (₹)</th><th>30-day obligation net (₹)</th><th>Estimated cash (₹)</th><th>30-day cash forecast (₹)</th><th>Weekly cap (hours)</th><th>Logged this week</th><th>Readiness</th><th>Allocation blockers</th><th>Missing inputs</th><th>Allocation signal</th></tr>{venture_rows}</table></div>
<form method='post' action='/set-cash-position'><select name='venture_id' required><option value=''>Choose venture</option>{''.join(f"<option value='{v['id']}'>{e(v['name'])}</option>" for v in ventures)}</select><input name='opening_balance' type='number' step='0.01' placeholder='Verified opening cash INR' required><input name='as_of_date' type='date' required><input name='note' placeholder='Source / account note'><button>Set cash position</button></form>
<form method='post' action='/add-venture'><input name='name' placeholder='New venture name' required><input name='description' placeholder='Description'><input name='monthly_budget_cap' type='number' min='0' step='0.01' placeholder='Monthly budget cap ₹'><input name='weekly_hours_cap' type='number' min='0' step='0.5' placeholder='Weekly hours cap'><select name='priority'><option value='1'>P1</option><option value='2'>P2</option><option value='3' selected>P3</option><option value='4'>P4</option><option value='5'>P5</option></select><button>Add venture</button></form>
<form method='post' action='/log-resource'><select name='venture_id' required><option value=''>Choose venture</option>{''.join(f"<option value='{v['id']}'>{e(v['name'])}</option>" for v in ventures)}</select><select name='entry_type'><option value='expense'>Expense (₹)</option><option value='income'>Income (₹)</option><option value='time'>Time (hours)</option></select><input name='quantity' type='number' min='0.01' step='0.01' placeholder='Amount / hours' required><input name='note' placeholder='What was spent / worked on'><button>Log resource</button></form>
<h3>Recent resource entries</h3><ul>{resource_rows}</ul></section>
<section><h2>PROJECT PORTFOLIO</h2><div class='scroll'><table><tr><th>ID</th><th>Project</th><th>Venture</th><th>Status</th><th>Change status</th><th>Edit</th></tr>{project_rows}</table></div>
<form method='post' action='/add-project'><input name='name' placeholder='New project name' required><input name='description' placeholder='Description'><select name='venture_id'><option value=''>No venture</option>{''.join(f"<option value='{v['id']}'>{e(v['name'])}</option>" for v in ventures)}</select><button>Add project</button></form>
<form method='post' action='/assign-project'><select name='project_id' required><option value=''>Choose project</option>{''.join(f"<option value='{p['id']}'>{e(p['name'])}</option>" for p in projects)}</select><select name='venture_id'><option value='0'>Unassigned</option>{''.join(f"<option value='{v['id']}'>{e(v['name'])}</option>" for v in ventures)}</select><button>Assign project</button></form></section>
<section><h2>EXECUTION</h2><div class='scroll'><table><tr><th>ID</th><th>Task</th><th>Project</th><th>Status</th><th>Priority</th><th>Update status</th><th>Edit</th></tr>{task_rows}</table></div>
<form method='post' action='/add-task'><select name='project_id' required><option value=''>Choose project</option>{''.join(f"<option value='{p['id']}'>{e(p['name'])}</option>" for p in active)}</select><input name='title' placeholder='Next action' required><select name='priority'><option value='1'>P1</option><option value='2'>P2</option><option value='3' selected>P3</option><option value='4'>P4</option><option value='5'>P5</option></select><input type='date' name='due_date'><button>Add task</button></form></section>
<section><h2>7-DAY EXECUTION PLAN</h2><ul>{plan_rows}</ul></section>
<section><h2>DECISION JOURNAL</h2><ul>{decision_rows}</ul>
<form method='post' action='/decision'><input name='title' placeholder='Decision title' required><input name='choice' placeholder='Chosen option' required><input name='rationale' placeholder='Reasoning'><button>Record decision</button></form></section>
<section><h2>SAGE AI ADVISOR</h2><p>Optional. Review <code>sage context-preview</code> first. Submitting this form sends the current bounded business context and your goal to the configured AI endpoint. AI output is advisory only; no records are changed.</p>
<form method='post' action='/suggest'><input name='goal' placeholder='What decision or next step should SAGE help with?' required>
<label><input type='checkbox' name='send_context' value='on' required> I approve sending the current SAGE context to the configured AI provider.</label><button>Generate AI suggestion</button></form>{suggestion_html}</section>
<section><h2>DAILY EXECUTIVE REVIEW</h2><p>Latest: {e(latest.get('review_date','Not recorded'))} · Priority: {e(latest.get('priority','—') or '—')}</p>
<p>Wins: {e(latest.get('wins','—') or '—')} · Tomorrow: {e(latest.get('tomorrow','—') or '—')}</p>
<form method='post' action='/review'><input name='priority' placeholder="Today's priority"><input name='wins' placeholder='Wins'><input name='blockers' placeholder='Blockers'><input name='tomorrow' placeholder="Tomorrow's first move"><button>Save review</button></form></section>
<section><h2>BLOCKERS</h2><ul>{blocker_rows}</ul>
<form method='post' action='/add-blocker'><input name='title' placeholder='Blocker' required><input name='details' placeholder='What is blocking progress?'><button>Record blocker</button></form></section>
<footer class='muted'>SAGE local web cockpit · No cloud sync or remote access. The optional AI Advisor sends context only when configured and explicitly approved.</footer>
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
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'none'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(payload)

        def _local_request_allowed(self) -> bool:
            allowed_hosts = {"127.0.0.1", "localhost", "::1"}
            try:
                host = urlparse("//" + self.headers.get("Host", "")).hostname
                host_port = urlparse("//" + self.headers.get("Host", "")).port
                if host not in allowed_hosts or host_port not in (None, self.server.server_port):
                    return False
                origin = self.headers.get("Origin")
                if origin:
                    parsed_origin = urlparse(origin)
                    if (
                        parsed_origin.scheme != "http"
                        or parsed_origin.hostname not in allowed_hosts
                        or parsed_origin.port != self.server.server_port
                    ):
                        return False
            except ValueError:
                return False
            return True

        def do_GET(self) -> None:
            if not self._local_request_allowed():
                self._send(403, "Local requests only")
                return
            if urlparse(self.path).path != "/":
                self._send(404, "Not found")
                return
            self._send(200, _page(store))

        def do_POST(self) -> None:
            if not self._local_request_allowed():
                self._send(403, "Local requests only")
                return
            if urlparse(self.path).path not in {
                "/add-project", "/add-venture", "/assign-project", "/log-resource", "/add-task",
                "/task-status", "/project-status", "/edit-project", "/edit-task", "/suggest", "/add-note", "/archive-note", "/set-cash-position", "/add-obligation", "/settle-obligation", "/cancel-obligation", "/add-recurring-obligation", "/recurring-obligation-status", "/generate-recurring-obligations", "/propose-task", "/approve-proposal", "/reject-proposal", "/add-recurring", "/recurring-status", "/generate-recurring", "/review", "/add-blocker",
                "/resolve-blocker", "/decision", "/request-calendar-export", "/approve-action", "/reject-action",
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
                suggestion = ""
                if path == "/suggest":
                    if data.get("send_context") != "on":
                        raise ValueError("Explicit context approval is required.")
                    from .ai import AIConfig, generate_suggestion
                    suggestion = generate_suggestion(
                        store, data.get("goal", ""), AIConfig.from_env()
                    )
                    notice = "AI suggestion generated. No SAGE records were changed."
                elif path == "/add-note":
                    store.add_context_note(
                        data.get("title", ""), data.get("content", ""),
                        data.get("category", "general"), int(data.get("importance", "3")),
                    )
                    notice = "SAGE context note saved."
                elif path == "/archive-note":
                    store.archive_context_note(int(data["id"]))
                    notice = "SAGE context note archived."
                elif path == "/set-cash-position":
                    store.set_cash_position(
                        int(data["venture_id"]), float(data.get("opening_balance", "0")),
                        data.get("as_of_date", ""), data.get("note", ""),
                    )
                    notice = "Manual cash position saved. Forecast uses only recorded obligations."
                elif path == "/add-recurring-obligation":
                    store.add_recurring_obligation(
                        int(data["venture_id"]), data.get("obligation_type", "payable"),
                        float(data.get("amount", "0")), data.get("description", ""),
                        data.get("frequency", "monthly"), int(data.get("every", "1")),
                        data.get("start_date") or None,
                    )
                    notice = "Recurring financial rule created."
                elif path == "/recurring-obligation-status":
                    store.set_recurring_obligation_status(int(data["id"]), data["status"])
                    notice = "Recurring financial rule status updated."
                elif path == "/generate-recurring-obligations":
                    generated = store.generate_recurring_obligations(limit=100)
                    notice = f"Generated {len(generated)} financial obligation(s)."
                elif path == "/add-obligation":
                    store.add_obligation(
                        int(data["venture_id"]), data.get("obligation_type", "receivable"),
                        float(data.get("amount", "0")), data.get("due_date", ""),
                        data.get("description", ""),
                    )
                    notice = "Financial obligation recorded."
                elif path == "/settle-obligation":
                    store.settle_obligation(int(data["id"]))
                    notice = "Obligation settled and posted to the actual ledger."
                elif path == "/cancel-obligation":
                    store.cancel_obligation(int(data["id"]))
                    notice = "Obligation cancelled."
                elif path == "/request-calendar-export":
                    filename = data.get("filename", "sage-calendar.ics")
                    request_id = store.create_action_request(
                        "calendar_export", f"Export open dated tasks to {filename}", {"filename": filename}
                    )
                    notice = f"Calendar export request #{request_id} queued. Nothing was exported; approve it in Controlled Actions."
                elif path == "/approve-action":
                    destination = store.approve_action_request(int(data["id"]))
                    notice = f"Approved and executed action. Calendar export created at {destination}."
                elif path == "/reject-action":
                    store.reject_action_request(int(data["id"]))
                    notice = "Action request rejected. Nothing was executed."
                elif path == "/propose-task":
                    store.create_task_proposal(
                        int(data["project_id"]), data.get("title", ""),
                        data.get("rationale", ""), int(data.get("priority", "3")),
                        data.get("due_date") or None,
                    )
                    notice = "Task proposal submitted for approval."
                elif path == "/approve-proposal":
                    task_id = store.approve_task_proposal(int(data["id"]))
                    notice = f"Proposal approved. Task #{task_id} created."
                elif path == "/reject-proposal":
                    store.reject_task_proposal(int(data["id"]))
                    notice = "Proposal rejected."
                elif path == "/add-recurring":
                    store.add_recurring_task(
                        int(data["project_id"]), data.get("title", ""),
                        int(data.get("priority", "3")), data.get("frequency", "weekly"),
                        int(data.get("every", "1")), data.get("start_date") or None,
                    )
                    notice = "Recurring task rule created."
                elif path == "/recurring-status":
                    store.set_recurring_task_status(int(data["id"]), data["status"])
                    notice = "Recurring task status updated."
                elif path == "/generate-recurring":
                    generated = store.generate_recurring_tasks(limit=100)
                    notice = f"Generated {len(generated)} recurring task(s)."
                elif path == "/add-project":
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
                    entry_type = data.get("entry_type", "expense")
                    quantity = float(data.get("quantity", "0"))
                    if entry_type == "income":
                        store.log_income(
                            int(data["venture_id"]), quantity, note=data.get("note", "")
                        )
                    else:
                        store.log_resource(
                            int(data["venture_id"]), entry_type, quantity,
                            project_id=None, note=data.get("note", ""),
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
                self._send(200, _page(store, notice, suggestion))
            except (ValueError, KeyError, RuntimeError, OSError) as error:
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
