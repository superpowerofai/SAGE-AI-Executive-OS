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
                "You are SAGE, a careful executive operating assistant. "
                "Use only the supplied records. Separate observed facts from assumptions. "
                "Do not invent revenue, costs, deadlines, available cash or available hours. "
                "Give one recommended master next action and, when useful, one action per active project; "
                "avoid overwhelming the user with idea lists. Explain the evidence, list missing inputs, "
                "and identify any risk. You may suggest actions but must never claim to execute "
                "them or change records. Keep advice practical and concise."
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
