from __future__ import annotations

import unittest
from unittest.mock import patch

from app import settings


class LlmProviderConfigTests(unittest.TestCase):
    def test_ollama_qwen_is_used_for_each_conversational_role(self) -> None:
        with (
            patch.object(settings, "LLM_PROVIDER", "ollama"),
            patch.object(settings, "OLLAMA_API_KEY", "ollama"),
            patch.object(settings, "OLLAMA_API_BASE_URL", "http://127.0.0.1:11434/v1"),
            patch.object(settings, "OLLAMA_MODEL", "qwen3.5:9b-q4_K_M"),
            patch.object(settings, "OLLAMA_CLASSIFIER_MODEL", "qwen3.5:9b-q4_K_M"),
            patch.object(settings, "OLLAMA_ANSWER_EVALUATION_MODEL", "qwen3.5:9b-q4_K_M"),
        ):
            for role in ("generation", "classifier", "evaluation"):
                with self.subTest(role=role):
                    self.assertEqual(
                        settings.llm_client_config(role),
                        (
                            "Ollama",
                            "ollama",
                            "http://127.0.0.1:11434/v1",
                            "qwen3.5:9b-q4_K_M",
                        ),
                    )

    def test_unknown_provider_does_not_fall_through_to_openai(self) -> None:
        with (
            patch.object(settings, "LLM_PROVIDER", "unknown"),
            patch.object(settings, "OPENAI_API_KEY", "openai-test-key"),
        ):
            self.assertIsNone(settings.llm_client_config("generation"))

    def test_ollama_embedding_configuration_is_local(self) -> None:
        with (
            patch.object(settings, "EMBEDDING_PROVIDER", "ollama"),
            patch.object(settings, "OLLAMA_API_KEY", "ollama"),
            patch.object(settings, "OLLAMA_API_BASE_URL", "http://127.0.0.1:11434/v1"),
            patch.object(settings, "OLLAMA_EMBEDDING_MODEL", "qwen3-embedding:0.6b"),
            patch.object(settings, "OPENAI_API_KEY", "unused-openai-key"),
        ):
            self.assertEqual(
                settings.embedding_client_config(),
                (
                    "Ollama",
                    "ollama",
                    "http://127.0.0.1:11434/v1",
                    "qwen3-embedding:0.6b",
                ),
            )

    def test_unknown_embedding_provider_does_not_use_openai(self) -> None:
        with (
            patch.object(settings, "EMBEDDING_PROVIDER", "unknown"),
            patch.object(settings, "OPENAI_API_KEY", "unused-openai-key"),
        ):
            self.assertIsNone(settings.embedding_client_config())

    def test_ollama_uses_supported_max_tokens_parameter(self) -> None:
        self.assertEqual(
            settings.completion_token_parameters("Ollama", 500),
            {"max_tokens": 500, "reasoning_effort": "none"},
        )
        self.assertEqual(
            settings.completion_token_parameters("OpenAI", 500),
            {"max_completion_tokens": 500},
        )

    def test_groq_chat_configuration_is_separate_from_openai_embeddings(self) -> None:
        with (
            patch.object(settings, "LLM_PROVIDER", "groq"),
            patch.object(settings, "GROQ_API_KEY", "groq-test-key"),
            patch.object(settings, "GROQ_API_BASE_URL", "https://api.groq.com/openai/v1"),
            patch.object(settings, "GROQ_MODEL", "openai/gpt-oss-120b"),
            patch.object(settings, "OPENAI_API_KEY", "embedding-test-key"),
        ):
            config = settings.llm_client_config("generation")

        self.assertEqual(
            config,
            ("Groq", "groq-test-key", "https://api.groq.com/openai/v1", "openai/gpt-oss-120b"),
        )

    def test_groq_120b_is_used_for_each_conversational_role(self) -> None:
        with (
            patch.object(settings, "LLM_PROVIDER", "groq"),
            patch.object(settings, "GROQ_API_KEY", "groq-test-key"),
            patch.object(settings, "GROQ_API_BASE_URL", "https://api.groq.com/openai/v1"),
            patch.object(settings, "GROQ_MODEL", "openai/gpt-oss-120b"),
            patch.object(settings, "GROQ_CLASSIFIER_MODEL", "openai/gpt-oss-120b"),
            patch.object(settings, "GROQ_ANSWER_EVALUATION_MODEL", "openai/gpt-oss-120b"),
        ):
            for role in ("generation", "classifier", "evaluation"):
                with self.subTest(role=role):
                    self.assertEqual(
                        settings.llm_client_config(role),
                        (
                            "Groq",
                            "groq-test-key",
                            "https://api.groq.com/openai/v1",
                            "openai/gpt-oss-120b",
                        ),
                    )


if __name__ == "__main__":
    unittest.main()
