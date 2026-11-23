"""Optional, explicit-consent AI suggestions through OpenAI-compatible APIs.

No credentials are persisted. Context is previewable before it is transmitted.
AI output is advisory text only and never mutates the SAGE database.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from .core import SageStore


@dataclass(frozen=True)
class AIConfig:
    base_url: str
    model: str
    api_key: str | None = None
    timeout: float = 45.0

    @classmethod
    def from_env(cls, timeout: float = 45.0) -> "AIConfig":
        base_url = os.environ.get("SAGE_AI_BASE_URL", "").strip().rstrip("/")
        model = os.environ.get("SAGE_AI_MODEL", "").strip()
        api_key = os.environ.get("SAGE_AI_API_KEY", "").strip() or None
        if not base_url or not model:
            raise ValueError(
                "Set SAGE_AI_BASE_URL and SAGE_AI_MODEL before using AI suggestions."
            )
        parsed = urlparse(base_url)
        local_hosts = {"localhost", "127.0.0.1", "::1"}
        if parsed.scheme != "https" and not (
            parsed.scheme == "http" and parsed.hostname in local_hosts
        ):
            raise ValueError("AI endpoint must use HTTPS, except for localhost providers.")
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("SAGE_AI_BASE_URL must be a valid HTTP(S) endpoint.")
        if parsed.hostname not in local_hosts and not api_key:
            raise ValueError("Set SAGE_AI_API_KEY for remote AI providers.")
        if timeout <= 0:
            raise ValueError("AI request timeout must be positive.")
        return cls(base_url, model, api_key, timeout)


class OpenAICompatibleClient:
    """Small standard-library client for chat-completions compatible endpoints."""

    def __init__(self, config: AIConfig):
        self.config = config

    def complete(self, messages: list[dict[str, str]]) -> str:
        payload = {
            "model": self.config.model,
            "messages": messages,
            "temperature": 0.2,
        }
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"
        request = Request(
            self.config.base_url + "/chat/completions",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.config.timeout) as response:
                result = json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")[:1000]
            raise RuntimeError(
                f"AI provider returned HTTP {error.code}: {detail}"
            ) from error
        except URLError as error:
            raise RuntimeError(f"Could not reach AI provider: {error.reason}") from error
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise RuntimeError("AI provider returned an invalid JSON response.") from error
        try:
            content = result["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as error:
            raise RuntimeError("AI provider response did not contain a chat completion.") from error
        if not isinstance(content, str) or not content.strip():
            raise RuntimeError("AI provider returned an empty suggestion.")
        return content.strip()



def build_daily_briefing(store: SageStore) -> dict:
    """Build an offline, evidence-only executive briefing from recorded SAGE data."""
    from datetime import date

    today = date.today()
    plan = store.execution_plan(7, today)
    projects = [p for p in store.list_projects() if p["status"] == "active"]
    actions = store.project_next_actions()
    blockers = store.list_blockers("open")
    proposals = store.list_task_proposals("pending")
    pending_actions = store.list_action_requests("pending")
    reviews = store.list_reviews(1)
    portfolio = store.portfolio_summary(today)["ventures"]

    # Prefer an in-progress task, then the highest-priority task due soon/overdue.
    candidates = [t for t in store.list_tasks() if t["status"] != "done"
                  and any(p["id"] == t["project_id"] for p in projects)]
    candidates.sort(key=lambda t: (0 if t["status"] == "in_progress" else 1,
                                   t["priority"], t["due_date"] or "9999-12-31", t["id"]))
    master = candidates[0] if candidates else None

    risks = []
    for venture in portfolio:
        if venture.get("overdue_payables", 0) > 0:
            risks.append({"venture": venture["name"], "type": "overdue_payables",
                          "amount_inr": venture["overdue_payables"]})
        forecast = venture.get("forecast_cash_balance_30d")
        if forecast is not None and forecast < 0:
            risks.append({"venture": venture["name"], "type": "negative_30_day_cash_forecast",
                          "amount_inr": forecast})

    data_gaps = []
    if not projects:
        data_gaps.append("No active projects are recorded.")
    if not reviews:
        data_gaps.append("No daily executive review is recorded yet.")
    if any(v.get("estimated_cash_balance") is None for v in portfolio):
        data_gaps.append("Current cash is unknown for one or more ventures; no bank feed is connected.")
    if not portfolio:
        data_gaps.append("No ventures are registered; venture-level financial health cannot be assessed.")

    return {
        "as_of": today.isoformat(),
        "master_next_action": ({"task_id": master["id"], "title": master["title"],
                                "project": master.get("project_name"), "priority": master["priority"],
                                "status": master["status"], "due_date": master.get("due_date")}
                               if master else None),
        "active_project_actions": actions,
        "overdue_tasks": plan["overdue"],
        "upcoming_7_day_tasks": plan["upcoming"],
        "open_blockers": blockers,
        "pending_task_approvals": proposals,
        "pending_action_approvals": pending_actions,
        "latest_review": reviews[0] if reviews else None,
        "financial_risks": risks,
        "data_gaps": data_gaps,
        "guardrails": ["Facts above come from recorded SAGE data only.",
                       "Unknown values are not estimates.",
                       "No tasks, finances, or external systems were changed."],
    }


def format_daily_briefing(briefing: dict) -> str:
    """Render the deterministic briefing in a readable terminal format."""
    lines = [f"SAGE DAILY EXECUTIVE BRIEFING | {briefing['as_of']}", "", "MASTER NEXT ACTION"]
    master = briefing["master_next_action"]
    if master:
        due = f" | due {master['due_date']}" if master.get("due_date") else ""
        lines.append(f"{master['title']} — {master['project']} (P{master['priority']}, {master['status']}){due}")
    else:
        lines.append("No open task exists in an active project. Choose or create the first concrete action.")
    for key, label in (("overdue_tasks", "OVERDUE TASKS"),
                       ("upcoming_7_day_tasks", "UPCOMING — NEXT 7 DAYS"),
                       ("active_project_actions", "ONE ACTION PER ACTIVE PROJECT"),
                       ("open_blockers", "OPEN BLOCKERS"),
                       ("pending_task_approvals", "PENDING TASK APPROVALS"),
                       ("pending_action_approvals", "PENDING ACTION APPROVALS"),
                       ("financial_risks", "RECORDED FINANCIAL RISKS"),
                       ("data_gaps", "UNKNOWN / MISSING INPUTS")):
        items = briefing[key]
        lines.extend(["", f"{label} ({len(items)}):"])
        if not items:
            lines.append("None recorded.")
        else:
            for item in items:
                if key == "data_gaps":
                    lines.append(f"- {item}")
                elif key == "financial_risks":
                    lines.append(f"- {item['venture']}: {item['type']} (INR {item['amount_inr']:,.2f})")
                elif key == "pending_action_approvals":
                    lines.append(f"- #{item['id']} {item['summary']} [{item['status']}]")
                elif key == "active_project_actions":
                    title = item.get("task_title") or "No task recorded — define the first action"
                    lines.append(f"- {item['project_name']}: {title}")
                else:
                    title = item.get("title") or item.get("task_title") or item.get("description") or str(item)
                    lines.append(f"- {title}")
    review = briefing.get("latest_review")
    lines.extend(["", "LATEST REVIEW"])
    lines.append(f"{review['review_date']}: priority={review['priority'] or 'not recorded'}; "
                 f"tomorrow={review['tomorrow'] or 'not recorded'}" if review else "No daily review recorded.")
    lines.extend(["", "GUARDRAILS", *[f"- {item}" for item in briefing["guardrails"]]])
    return "\n".join(lines)

def preview_context(store: SageStore) -> str:
    """Return the exact business context payload intended for AI transmission."""
    return json.dumps(store.ai_context(), ensure_ascii=False, indent=2)


def generate_suggestion(
    store: SageStore, goal: str, config: AIConfig | None = None
) -> str:
    goal = goal.strip()
    if not goal:
        raise ValueError("Describe what you want SAGE to help decide or plan.")
    selected_config = config or AIConfig.from_env()
    context = preview_context(store)
    messages = [
        {
            "role": "system",
            "content": (
                "You are SAGE, a careful executive operating assistant. Use only the supplied records. "
                "Clearly label RECORDED FACTS, REASONED INTERPRETATION, RECOMMENDATION, and UNKNOWN INPUTS. "
                "Never invent revenue, costs, deadlines, cash, available hours, customer demand, or progress. "
                "Prioritize overdue work, in-progress work, blockers, and recorded financial risks. "
                "Give exactly one master next action, plus at most one action per active project. "
                "Explain which supplied record supports each recommendation. If evidence is missing, say so. "
                "Never claim to execute actions or change records; all output is advisory only."
            ),
        },
        {
            "role": "user",
            "content": (
                "USER GOAL:\n" + goal + "\n\nSAGE CONTEXT PREVIEW:\n" + context
            ),
        },
    ]
    return OpenAICompatibleClient(selected_config).complete(messages)
