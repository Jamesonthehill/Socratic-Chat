import asyncio
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from openai import APIConnectionError, BadRequestError, PermissionDeniedError, RateLimitError

from app import llm_client, settings


def provider_error(error_type, status):
    response = httpx.Response(status, request=httpx.Request("POST", "https://provider.test"))
    return error_type("simulated provider failure", response=response, body=None)


@pytest.mark.parametrize("error", [
    APIConnectionError(request=httpx.Request("POST", "https://provider.test")),
    provider_error(RateLimitError, 429),
    provider_error(PermissionDeniedError, 403),
])
def test_openai_service_failure_uses_groq_once(error):
    request = {"model": "gpt-4.1-mini", "messages": [{"role": "user", "content": "Help"}], "max_tokens": 200}
    result = object()
    completion = AsyncMock(side_effect=[error, result])
    with patch.object(llm_client, "chat_completion", completion), patch.object(settings, "GROQ_API_KEY", "test-groq"):
        assert asyncio.run(llm_client.socratic_chat_completion("test-openai", settings.OPENAI_API_BASE_URL, request)) is result
    key, url, fallback = completion.call_args.args
    assert (key, url, fallback["model"]) == ("test-groq", settings.GROQ_API_BASE_URL, "openai/gpt-oss-120b")
    assert fallback["messages"] == request["messages"]
    assert fallback["max_completion_tokens"] == 200
    assert "max_tokens" not in fallback
    assert request["model"] == "gpt-4.1-mini"


def test_bad_request_does_not_switch_provider():
    completion = AsyncMock(side_effect=provider_error(BadRequestError, 400))
    with patch.object(llm_client, "chat_completion", completion), patch.object(settings, "GROQ_API_KEY", "test"):
        with pytest.raises(BadRequestError):
            asyncio.run(llm_client.socratic_chat_completion("test", settings.OPENAI_API_BASE_URL, {"model": "gpt-4.1-mini"}))
    assert completion.await_count == 1


def test_groq_permission_failure_is_not_retried():
    completion = AsyncMock(side_effect=provider_error(PermissionDeniedError, 403))
    with patch.object(llm_client, "chat_completion", completion), patch.object(settings, "GROQ_API_KEY", "test"):
        with pytest.raises(PermissionDeniedError):
            asyncio.run(llm_client.socratic_chat_completion("test", settings.GROQ_API_BASE_URL, {"model": "openai/gpt-oss-120b"}))
    assert completion.await_count == 1
