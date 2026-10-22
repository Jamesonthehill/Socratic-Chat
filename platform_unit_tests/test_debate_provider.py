import asyncio
import logging
from types import SimpleNamespace

from fastapi import HTTPException
import openai

from platform_app import debate


def test_debate_provider_failure_logs_safe_diagnostics(monkeypatch, caplog):
    secret = "student-answer-and-secret-key"
    client_options = {}

    class ProviderFailure(Exception):
        status_code = 429
        request_id = "req_123"

    class FakeCompletions:
        async def create(self, **kwargs):
            raise ProviderFailure(secret)

    class FakeClient:
        def __init__(self, **kwargs):
            client_options.update(kwargs)
            self.chat = SimpleNamespace(completions=FakeCompletions())

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return None

    monkeypatch.setattr(
        debate.settings,
        "llm_client_config",
        lambda role: ("Groq", "secret-key", "https://api.groq.com/openai/v1", "test-model"),
    )
    monkeypatch.setattr(openai, "AsyncOpenAI", FakeClient)

    with caplog.at_level(logging.ERROR, logger="platform_app.debate"):
        try:
            asyncio.run(debate.generate_reply("A scenario", [], secret))
        except HTTPException as exc:
            assert exc.status_code == 503
            assert exc.detail == "The Debate AI has reached its request limit. Please retry later."
        else:
            raise AssertionError("Expected the provider failure to become HTTP 503")

    assert client_options["max_retries"] == 1
    assert "provider=Groq" in caplog.text
    assert "error_type=ProviderFailure" in caplog.text
    assert "status_code=429" in caplog.text
    assert "request_id=req_123" in caplog.text
    assert secret not in caplog.text
    assert "secret-key" not in caplog.text


def test_debate_provider_returns_reply_and_closes_client(monkeypatch):
    closed = []

    class FakeCompletions:
        async def create(self, **kwargs):
            assert kwargs["model"] == "test-model"
            assert [item["role"] for item in kwargs["messages"]] == ["system", "user"]
            assert "<scenario>\nA scenario\n</scenario>" in kwargs["messages"][0]["content"]
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content="  Consider the other side?  "))]
            )

    class FakeClient:
        def __init__(self, **kwargs):
            self.chat = SimpleNamespace(completions=FakeCompletions())

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            closed.append(True)

    monkeypatch.setattr(
        debate.settings,
        "llm_client_config",
        lambda role: ("Groq", "secret-key", "https://api.groq.com/openai/v1", "test-model"),
    )
    monkeypatch.setattr(openai, "AsyncOpenAI", FakeClient)

    reply = asyncio.run(debate.generate_reply("A scenario", [], "My position"))
    assert reply == "Consider the other side?"
    assert closed == [True]


def test_debate_bad_request_is_actionable_and_never_logs_provider_text(monkeypatch, caplog):
    secret = "student-answer-and-secret-key"

    class ProviderFailure(Exception):
        status_code = 400
        request_id = "req_bad_request"
        body = {"error": {"type": "invalid_request_error", "message": f"unsupported parameter: {secret}"}}

    class FakeCompletions:
        async def create(self, **kwargs):
            raise ProviderFailure(secret)

    class FakeClient:
        def __init__(self, **kwargs):
            self.chat = SimpleNamespace(completions=FakeCompletions())

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return None

    monkeypatch.setattr(
        debate.settings,
        "llm_client_config",
        lambda role: ("Groq", "secret-key", "https://api.groq.com/openai/v1", "test-model"),
    )
    monkeypatch.setattr(openai, "AsyncOpenAI", FakeClient)

    with caplog.at_level(logging.ERROR, logger="platform_app.debate"):
        try:
            asyncio.run(debate.generate_reply("A scenario", [], secret))
        except HTTPException as exc:
            assert exc.status_code == 502
            assert "rejected this request" in exc.detail
        else:
            raise AssertionError("Expected the provider bad request to become HTTP 502")

    assert "error_category=unsupported_parameter" in caplog.text
    assert "request_id=req_bad_request" in caplog.text
    assert secret not in caplog.text
    assert "secret-key" not in caplog.text
