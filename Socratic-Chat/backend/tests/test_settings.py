from __future__ import annotations

import unittest
from unittest.mock import patch

from app import settings


class LlmProviderConfigTests(unittest.TestCase):
    def test_only_qualitative_feedback_uses_groq_20b_override(self) -> None:
        with (
            patch.object(settings, "LLM_PROVIDER", "ollama"),
            patch.object(settings, "SOCRATIC_FEEDBACK_PROVIDER", "groq"),
            patch.object(settings, "SOCRATIC_FEEDBACK_MODEL", "openai/gpt-oss-20b"),
            patch.object(settings, "GROQ_API_KEY", "groq-test-key"),
            patch.object(settings, "GROQ_MODEL", "openai/gpt-oss-120b"),
            patch.object(settings, "OLLAMA_MODEL", "qwen3.5:9b-q4_K_M"),
            patch.object(settings, "OLLAMA_ANSWER_EVALUATION_MODEL", "qwen3.5:9b-q4_K_M"),
        ):
            self.assertEqual(settings.llm_client_config("qualitative_feedback")[0::3],
                             ("Groq", "openai/gpt-oss-20b"))
            self.assertEqual(settings.llm_client_config("evaluation")[0::3],
                             ("Ollama", "qwen3.5:9b-q4_K_M"))

    def test_only_socratic_tutor_uses_groq_override(self) -> None:
        with (
            patch.object(settings, "LLM_PROVIDER", "ollama"),
            patch.object(settings, "SOCRATIC_TUTOR_PROVIDER", "groq"),
            patch.object(settings, "SOCRATIC_TUTOR_MODEL", "openai/gpt-oss-20b"),
            patch.object(settings, "SOCRATIC_CLASSIFIER_PROVIDER", ""),
            patch.object(settings, "GROQ_API_KEY", "groq-test-key"),
            patch.object(settings, "OLLAMA_MODEL", "qwen3.5:9b-q4_K_M"),
            patch.object(settings, "OLLAMA_CLASSIFIER_MODEL", "qwen3.5:9b-q4_K_M"),
            patch.object(settings, "OLLAMA_ANSWER_EVALUATION_MODEL", "qwen3.5:9b-q4_K_M"),
        ):
            self.assertEqual(settings.llm_client_config("tutor")[0::3], ("Groq", "openai/gpt-oss-20b"))
            for role in ("generation", "classifier", "evaluation"):
                with self.subTest(role=role):
                    self.assertEqual(settings.llm_client_config(role)[0::3], ("Ollama", "qwen3.5:9b-q4_K_M"))

    def test_tutor_override_without_groq_key_does_not_silently_use_qwen(self) -> None:
        with (patch.object(settings, "LLM_PROVIDER", "ollama"),
              patch.object(settings, "SOCRATIC_TUTOR_PROVIDER", "groq"),
              patch.object(settings, "GROQ_API_KEY", "")):
            self.assertIsNone(settings.llm_client_config("tutor"))
            self.assertEqual(settings.llm_client_config("generation")[0], "Ollama")

    def test_classifier_and_tutor_can_use_groq_20b_while_other_roles_use_qwen(self) -> None:
        with (
            patch.object(settings, "LLM_PROVIDER", "ollama"),
            patch.object(settings, "SOCRATIC_TUTOR_PROVIDER", "groq"),
            patch.object(settings, "SOCRATIC_TUTOR_MODEL", "openai/gpt-oss-20b"),
            patch.object(settings, "SOCRATIC_CLASSIFIER_PROVIDER", "groq"),
            patch.object(settings, "GROQ_CLASSIFIER_MODEL", "openai/gpt-oss-20b"),
            patch.object(settings, "GROQ_API_KEY", "groq-test-key"),
            patch.object(settings, "OLLAMA_MODEL", "qwen3.5:9b-q4_K_M"),
        ):
            for role in ("classifier", "tutor"):
                with self.subTest(role=role):
                    self.assertEqual(settings.llm_client_config(role)[0::3], ("Groq", "openai/gpt-oss-20b"))
            for role in ("generation", "evaluation"):
                with self.subTest(role=role):
                    self.assertEqual(settings.llm_client_config(role)[0::3], ("Ollama", "qwen3.5:9b-q4_K_M"))

    def test_setup_can_use_groq_without_switching_other_local_roles(self) -> None:
        with (
            patch.object(settings, "LLM_PROVIDER", "ollama"),
            patch.object(settings, "SOCRATIC_SETUP_PROVIDER", "groq"),
            patch.object(settings, "GROQ_API_KEY", "groq-test-key"),
            patch.object(settings, "GROQ_MODEL", "openai/gpt-oss-20b"),
            patch.object(settings, "OLLAMA_MODEL", "qwen3.5:9b-q4_K_M"),
        ):
            self.assertEqual(settings.llm_client_config("setup")[0::3], ("Groq", "openai/gpt-oss-20b"))
            self.assertEqual(settings.llm_client_config("generation")[0::3], ("Ollama", "qwen3.5:9b-q4_K_M"))

    def test_local_qwen_roles_and_visible_output_parameters(self) -> None:
        with (
            patch.object(settings, "LLM_PROVIDER", "ollama"),
            patch.object(settings, "OLLAMA_MODEL", "qwen3.5:9b-q4_K_M"),
            patch.object(settings, "SOCRATIC_CLASSIFIER_PROVIDER", ""),
            patch.object(settings, "OLLAMA_CLASSIFIER_MODEL", ""),
            patch.object(settings, "OLLAMA_ANSWER_EVALUATION_MODEL", ""),
        ):
            for role in ("generation", "classifier", "evaluation"):
                config = settings.llm_client_config(role)
                self.assertEqual(config[0], "Ollama")
                self.assertEqual(config[3], "qwen3.5:9b-q4_K_M")
            self.assertEqual(settings.completion_token_parameters("Ollama", 600),
                             {"max_tokens": 600, "reasoning_effort": "none"})

    def test_embeddings_stay_on_openai_when_chat_uses_groq(self) -> None:
        with (
            patch.object(settings, "LLM_PROVIDER", "groq"),
            patch.object(settings, "EMBEDDING_PROVIDER", "openai"),
            patch.object(settings, "OPENAI_API_KEY", "embedding-test-key"),
            patch.object(settings, "OPENAI_API_BASE_URL", "https://api.openai.com/v1"),
            patch.object(settings, "EMBEDDING_MODEL", "text-embedding-3-small"),
        ):
            self.assertEqual(settings.embedding_client_config(), (
                "OpenAI", "embedding-test-key", "https://api.openai.com/v1",
                "text-embedding-3-small",
            ))
            self.assertEqual(settings.embedding_model_name(), "text-embedding-3-small")

    def test_missing_openai_key_does_not_fall_back_to_chat_embeddings(self) -> None:
        with patch.object(settings, "EMBEDDING_PROVIDER", "openai"), patch.object(settings, "OPENAI_API_KEY", ""), patch.object(settings, "GROQ_API_KEY", "groq-test-key"):
            self.assertIsNone(settings.embedding_client_config())

    def test_local_qwen_embeddings_do_not_change_groq_chat(self) -> None:
        with (
            patch.object(settings, "EMBEDDING_PROVIDER", "ollama"),
            patch.object(settings, "EMBEDDING_MODEL", "qwen3-embedding:0.6b"),
            patch.object(settings, "OLLAMA_API_BASE_URL", "http://127.0.0.1:11434/v1"),
            patch.object(settings, "OPENAI_API_KEY", ""),
            patch.object(settings, "LLM_PROVIDER", "groq"),
            patch.object(settings, "GROQ_API_KEY", "test-groq-key"),
        ):
            self.assertEqual(settings.embedding_client_config()[0], "Ollama")
            self.assertEqual(settings.embedding_client_config()[2:], ("http://127.0.0.1:11434/v1", "qwen3-embedding:0.6b"))
            self.assertEqual(settings.llm_client_config()[0], "Groq")

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
