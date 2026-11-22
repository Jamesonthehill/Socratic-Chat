import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from app.llm_client import chat_completion


class LlmClientLifecycleTests(unittest.TestCase):
    def test_closes_client_after_success(self):
        client = SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=AsyncMock(return_value="reply"))),
            close=AsyncMock(),
        )
        with patch("openai.AsyncOpenAI", return_value=client):
            result = asyncio.run(chat_completion("local", "http://localhost", {"model": "test"}))
        self.assertEqual(result, "reply")
        client.close.assert_awaited_once()

    def test_closes_client_after_request_failure(self):
        client = SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=AsyncMock(side_effect=RuntimeError("request failed")))),
            close=AsyncMock(),
        )
        with patch("openai.AsyncOpenAI", return_value=client):
            with self.assertRaisesRegex(RuntimeError, "request failed"):
                asyncio.run(chat_completion("local", "http://localhost", {"model": "test"}))
        client.close.assert_awaited_once()


class LunaRequestTests(unittest.TestCase):
    def test_reasoning_request_preserves_schema_and_reserves_reasoning_budget(self):
        from app.llm_client import prepare_chat_request
        schema = {"type": "json_schema", "json_schema": {"name": "readiness"}}
        original = {"model": "gpt-6-luna", "temperature": 0, "top_p": .8,
                    "max_tokens": 320, "response_format": schema}
        result = prepare_chat_request(original)
        self.assertEqual(result["reasoning_effort"], "medium")
        self.assertGreaterEqual(result["max_completion_tokens"], 4096)
        self.assertEqual(result["response_format"], schema)
        self.assertNotIn("temperature", result)
        self.assertNotIn("top_p", result)
        self.assertNotIn("max_tokens", result)
        self.assertEqual(original["max_tokens"], 320)

    def test_luna_tool_calls_disable_reasoning(self):
        from app.llm_client import prepare_chat_request
        result = prepare_chat_request({"model": "gpt-6-luna", "tools": [{"type": "function"}],
                                       "reasoning_effort": "low", "max_completion_tokens": 4000})
        self.assertEqual(result["reasoning_effort"], "none")

    def test_gpt41_request_is_unchanged(self):
        from app.llm_client import prepare_chat_request
        original = {"model": "gpt-4.1-mini", "temperature": 0, "max_completion_tokens": 320}
        self.assertEqual(prepare_chat_request(original), original)
