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
