from __future__ import annotations

from typing import Any


async def chat_completion(api_key: str, base_url: str, request: dict[str, Any]) -> Any:
    """Finish an LLM request and close its HTTP transport before its event loop exits."""
    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=api_key, base_url=base_url)
    try:
        return await client.chat.completions.create(**request)
    finally:
        close = getattr(client, "close", None)
        if close is not None:
            await close()


async def socratic_chat_completion(api_key: str, base_url: str, request: dict[str, Any]) -> Any:
    """Retry OpenAI tutor service failures once through the configured Groq account."""
    from openai import APIConnectionError, APIStatusError
    from app import settings
    from app.pipeline_logging import log_event, write_llm_request_snapshot

    try:
        return await chat_completion(api_key, base_url, request)
    except (APIConnectionError, APIStatusError) as error:
        status = getattr(error, "status_code", None)
        retryable = status in {401, 403, 408, 409, 429} or (status is not None and status >= 500)
        openai_request = base_url.rstrip("/") == settings.OPENAI_API_BASE_URL.rstrip("/")
        if not openai_request or not settings.GROQ_API_KEY or not (retryable or isinstance(error, APIConnectionError)):
            raise

        fallback = {**request, "model": "openai/gpt-oss-120b"}
        # Groq's reasoning models use completion tokens and do not accept OpenAI's
        # verbosity and service tier parameters.
        token_limit = fallback.pop("max_tokens", None)
        if token_limit is not None:
            fallback.setdefault("max_completion_tokens", token_limit)
        fallback.pop("verbosity", None)
        fallback.pop("service_tier", None)
        fallback["reasoning_effort"] = "low"
        log_event(8, "socratic_provider_fallback_started",
                  primary_provider="OpenAI", primary_model=request.get("model"),
                  provider="Groq", model=fallback["model"],
                  error_type=type(error).__name__, status_code=status)
        write_llm_request_snapshot("tutor-provider-fallback", "Groq", fallback)
        try:
            response = await chat_completion(settings.GROQ_API_KEY, settings.GROQ_API_BASE_URL, fallback)
        except (APIConnectionError, APIStatusError) as fallback_error:
            log_event(8, "socratic_provider_fallback_failed",
                      provider="Groq", model=fallback["model"],
                      error_type=type(fallback_error).__name__,
                      status_code=getattr(fallback_error, "status_code", None))
            raise
        log_event(8, "socratic_provider_fallback_completed", provider="Groq", model=fallback["model"])
        return response
