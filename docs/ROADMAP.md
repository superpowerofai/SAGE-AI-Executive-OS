# SAGE Development Roadmap

This roadmap distinguishes implemented code from behavior that has actually been verified.

## v0.1 — Local execution core

- [x] SQLite-backed project and task model
- [x] CLI commands for projects and tasks
- [x] Priority and status handling
- [x] Dashboard counts
- [x] Core unit tests
- [x] CLI workflow tests
- [x] `python -m sage` entry point
- [x] GitHub Actions matrix for Python 3.10, 3.11, 3.12 and 3.13
- [x] Confirm a successful clean CI run across the matrix (run 45095550695)

## v0.2 — Usability

- [x] CLI focus view for active/paused projects, one next action per active project and one master priority (CI-verified on Python 3.10, 3.11, 3.12 and 3.13)
- [x] Local interactive web cockpit for projects, tasks, reviews and blockers (CI-verified on Python 3.10, 3.11, 3.12 and 3.13)
- [x] 7-day and 30-day execution plan with overdue, upcoming and unscheduled work
- [x] Edit project/task details and archive by completing projects or tasks (CI-verified)
- [x] Income and expense logging with monthly net cash-flow snapshots (CI-verified)
- [ ] Recurring costs, receivables/payables, full cash-flow forecasting, ROI-aware allocation recommendations and evidence-based prioritization beyond current rule-based signals
- [x] Integrity-checked SQLite backup, versioned JSON export/import and confirmed restore with pre-restore safety copy (CI-verified)
- [x] Venture portfolio registry, project ownership, strategic priority and optional resource caps (CI-verified)
- [x] Actual income, expense and time logging with monthly cash-flow and weekly cap usage summaries (CI-verified)
- [x] Recurring daily/weekly/monthly task rules with bounded on-demand generation (CI-verified)
- [x] One-way iCalendar export for open dated tasks (CI-verified)
- [ ] Desktop notifications and automatic scheduled recurring-task generation

## v0.3 — Executive review

- [x] Daily review record and recent review history (CI-verified on Python 3.10, 3.11, 3.12 and 3.13)
- [x] 7-day and 30-day review summaries (CI-verified on Python 3.10, 3.11, 3.12 and 3.13)
- [x] Structured blocker tracking with project/task links and resolution state (CI-verified on Python 3.10, 3.11, 3.12 and 3.13)
- [x] Decision journal with context, choice, rationale and revisit date (CI-verified on Python 3.10, 3.11, 3.12 and 3.13)

## v0.4 — Optional AI assistance

- [x] Provider-neutral OpenAI-compatible chat-completion adapter (CI-verified)
- [x] Bounded context preview and explicit opt-in before external transmission (CI-verified)
- [x] AI-generated suggestions labeled advisory-only; no automatic database mutations (CI-verified)
- [x] Local cockpit AI Advisor with explicit context-consent checkbox (CI-verified)
- [x] Human approval queue for task proposals; approval creates the task, rejection records the decision (CI-verified)
- [ ] Approval gates for future external actions and automated workflows

## v0.5 — Local desktop operations\n\n- [x] Windows one-click launcher and desktop shortcut\n- [x] Local Ollama connection with context preview and explicit consent\n- [x] Local-only HTTP cockpit with Host/Origin checks and security headers\n- [ ] User authentication, multi-device sync and hosted deployment\n- [ ] Two-way calendar and email integrations\n\n## Release discipline

A checkbox is marked complete only after code exists and the documented behavior has been verified. The presence of a workflow or test file alone is not proof of a passing test run. Planned integrations must not be described as active capabilities.
