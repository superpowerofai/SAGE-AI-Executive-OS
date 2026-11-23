import json
from io import BytesIO
from unittest.mock import patch

import pytest

from sage.ai import AIConfig, OpenAICompatibleClient, generate_suggestion, preview_context
from sage.core import SageStore


def test_ai_config_accepts_local_openai_compatible_provider_without_key(monkeypatch):
    monkeypatch.setenv("SAGE_AI_BASE_URL", "http://127.0.0.1:11434/v1/")
    monkeypatch.setenv("SAGE_AI_MODEL", "qwen3:1.7b")
    monkeypatch.delenv("SAGE_AI_API_KEY", raising=False)
    config = AIConfig.from_env()
    assert config.base_url == "http://127.0.0.1:11434/v1"
    assert config.model == "qwen3:1.7b"
    assert config.api_key is None


def test_ai_config_requires_https_and_key_for_remote_provider(monkeypatch):
    monkeypatch.setenv("SAGE_AI_BASE_URL", "http://example.com/v1")
    monkeypatch.setenv("SAGE_AI_MODEL", "model")
    monkeypatch.setenv("SAGE_AI_API_KEY", "secret")
    with pytest.raises(ValueError, match="HTTPS"):
        AIConfig.from_env()

    monkeypatch.setenv("SAGE_AI_BASE_URL", "https://example.com/v1")
    monkeypatch.delenv("SAGE_AI_API_KEY", raising=False)
    with pytest.raises(ValueError, match="SAGE_AI_API_KEY"):
        AIConfig.from_env()


def test_openai_compatible_client_sends_chat_completion_request():
    response = BytesIO(
        json.dumps({"choices": [{"message": {"content": "One next step."}}]}).encode()
    )
    client = OpenAICompatibleClient(
        AIConfig("http://localhost:11434/v1", "test-model", timeout=3)
    )
    with patch("sage.ai.urlopen", return_value=response) as mocked:
        answer = client.complete([{"role": "user", "content": "Help"}])
    assert answer == "One next step."
    request = mocked.call_args.args[0]
    assert request.full_url.endswith("/chat/completions")
    assert json.loads(request.data)["model"] == "test-model"


def test_context_preview_and_ai_suggestion_use_read_only_snapshot(tmp_path):
    store = SageStore(tmp_path / "ai-context.db")
    venture = store.add_venture("OPERONIX AI")
    project = store.add_project("Lead automation", venture_id=venture)
    store.add_task(project, "Contact first lead", priority=1)
    preview = preview_context(store)
    assert "OPERONIX AI" in preview
    assert "Lead automation" in preview
    assert "Contact first lead" in preview
    store.add_context_note("Operating rule", "Never invent business numbers.")
    assert "Never invent business numbers" in preview_context(store)

    captured = {}
    def fake_complete(self, messages):
        captured["messages"] = messages
        return "Contact one qualified prospect."

    with patch("sage.ai.OpenAICompatibleClient.complete", fake_complete):
        answer = generate_suggestion(
            store, "What should I do next?",
            AIConfig("http://localhost:11434/v1", "test-model"),
        )
    assert answer == "Contact one qualified prospect."
    assert "What should I do next?" in captured["messages"][1]["content"]
    assert "Lead automation" in captured["messages"][1]["content"]
    assert store.list_projects()[0]["name"] == "Lead automation"


def test_daily_briefing_uses_recorded_data_and_reports_unknowns(tmp_path):
    from sage.ai import build_daily_briefing, format_daily_briefing

    store = SageStore(tmp_path / "briefing.db")
    venture = store.add_venture("Test venture")
    project = store.add_project("First project", venture_id=venture)
    task_id = store.add_task(project, "Call first prospect", priority=1)
    store.add_blocker("Waiting for customer list", project_id=project)
    store.create_action_request("calendar_export", "Export current tasks", {"filename": "tasks.ics"})
    briefing = build_daily_briefing(store)

    assert briefing["master_next_action"]["task_id"] == task_id
    assert briefing["master_next_action"]["title"] == "Call first prospect"
    assert briefing["open_blockers"][0]["title"] == "Waiting for customer list"
    assert briefing["pending_action_approvals"][0]["summary"] == "Export current tasks"
    assert any("cash is unknown" in gap for gap in briefing["data_gaps"])
    rendered = format_daily_briefing(briefing)
    assert "MASTER NEXT ACTION" in rendered
    assert "RECORDED FINANCIAL RISKS" in rendered
    assert "No tasks, finances, or external systems were changed." in rendered
    assert store.list_tasks()[0]["status"] == "todo"


def test_daily_briefing_empty_database_does_not_invent_work(tmp_path):
    from sage.ai import build_daily_briefing

    store = SageStore(tmp_path / "empty-briefing.db")
    briefing = build_daily_briefing(store)
    assert briefing["master_next_action"] is None
    assert briefing["active_project_actions"] == []
    assert briefing["financial_risks"] == []
    assert any("No active projects" in gap for gap in briefing["data_gaps"])
