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
- [ ] Edit and archive workflows
- [ ] Export and backup

## v0.3 — Executive review

- [x] Daily review record and recent review history (CI-verified on Python 3.10, 3.11 and 3.12)
- [x] 7-day and 30-day review summaries (implemented; awaiting fresh CI run)
- [x] Structured blocker tracking with project/task links and resolution state (awaiting fresh CI run)
- [x] Decision journal with context, choice, rationale and revisit date (awaiting fresh CI run)

## v0.4 — Optional AI assistance

- [ ] Provider-neutral model adapter
- [ ] Context preview before external transmission
- [ ] AI-generated plans clearly labeled as suggestions
- [ ] Human approval for consequential actions

## Release discipline

A checkbox is marked complete only after code exists and the documented behavior has been verified. The presence of a workflow or test file alone is not proof of a passing test run. Planned integrations must not be described as active capabilities.
