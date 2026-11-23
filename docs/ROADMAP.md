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
- [x] GitHub Actions matrix for Python 3.10, 3.11 and 3.12
- [x] Confirm a successful clean CI run across the matrix (run 45061884697)

## v0.2 — Usability

- [x] CLI focus view for active/paused projects and one prioritized next action (CI-verified on Python 3.10, 3.11 and 3.12)
- [x] Local interactive web cockpit for projects, tasks, reviews and blockers (CI-verified on Python 3.10, 3.11 and 3.12)
- [x] 7-day and 30-day execution plan with overdue, upcoming and unscheduled work
- [x] Edit project/task details and archive by completing projects or tasks (CI-verified)
- [x] Income and expense logging with monthly net cash-flow snapshots (CI-verified)
- [ ] Recurring costs, receivables/payables, full cash-flow forecasting, ROI-aware allocation recommendations and evidence-based prioritization beyond current rule-based signals
- [x] Integrity-checked SQLite backup, versioned JSON export/import and confirmed restore with pre-restore safety copy (CI-verified)
- [x] Venture portfolio registry, project ownership, strategic priority and optional resource caps (CI-verified)
- [x] Actual expense and time logging with monthly/weekly cap usage summaries (CI-verified)

## v0.3 — Executive review

- [x] Daily review record and recent review history (CI-verified on Python 3.10, 3.11 and 3.12)
- [x] 7-day and 30-day review summaries (CI-verified on Python 3.10, 3.11 and 3.12)
- [x] Structured blocker tracking with project/task links and resolution state (CI-verified on Python 3.10, 3.11 and 3.12)
- [x] Decision journal with context, choice, rationale and revisit date (CI-verified on Python 3.10, 3.11 and 3.12)

## v0.4 — Optional AI assistance

- [x] Provider-neutral OpenAI-compatible chat-completion adapter (CI-verified)
- [x] Bounded context preview and explicit opt-in before external transmission (CI-verified)
- [x] AI-generated suggestions labeled advisory-only; no automatic database mutations (CI-verified)
- [ ] Human approval for consequential actions

## Release discipline

A checkbox is marked complete only after code exists and the documented behavior has been verified. The presence of a workflow or test file alone is not proof of a passing test run. Planned integrations must not be described as active capabilities.
