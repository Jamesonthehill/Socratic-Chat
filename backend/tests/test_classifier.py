from __future__ import annotations

import asyncio
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app import classifier, settings
from app.classifier import MessageClassification, classify_message
from app.schemas import ChatMessage


class MessageClassifierTests(unittest.TestCase):
    def classify_with_rules(
        self, message: str, history: list[ChatMessage] | None = None,
    ) -> MessageClassification:
        with patch.object(settings, "CLASSIFIER_ENABLED", False):
            return asyncio.run(classify_message(message, history or []))

    def test_extracts_clean_concept_from_explain_what_question(self) -> None:
        result = self.classify_with_rules("Explain what GitHub is.")
        self.assertEqual(result.route, "learning")
        self.assertEqual(result.student_intent, "definition")
        self.assertEqual(result.target_concepts, ("GitHub",))
        self.assertEqual(result.target, "GitHub")

    def test_administrative_questions_are_protected_by_rules(self) -> None:
        result = self.classify_with_rules("What are the Assignment 4 submission requirements?")
        self.assertEqual(result.route, "administrative")
        self.assertEqual(result.student_intent, "administrative")
        self.assertFalse(result.needs_clarification)

    def test_follow_up_resolves_the_recent_course_concept(self) -> None:
        history = [
            ChatMessage(role="user", content="What is version control?"),
            ChatMessage(role="assistant", content="Imagine two developers edit one file. What problem might appear?"),
        ]
        result = self.classify_with_rules("Why is that important?", history)
        self.assertEqual(result.target_concepts, ("version control",))
        self.assertIn("version control", result.rewritten_query or "")

    def test_natural_comparison_question_finds_both_concepts(self) -> None:
        result = self.classify_with_rules("How are Git and GitHub different?")
        self.assertEqual(result.student_intent, "comparison")
        self.assertEqual(result.question_type, "comparison")
        self.assertEqual(result.target_concepts, ("Git", "GitHub"))

    def test_short_ambiguous_message_requests_clarification(self) -> None:
        result = self.classify_with_rules("configuration")
        self.assertTrue(result.needs_clarification)
        self.assertEqual(result.route, "unclear")
        self.assertIn("course concept", result.clarification_question or "")

    def test_llm_output_is_validated_and_used_for_learning_message(self) -> None:
        payload = """{
            "route": "learning",
            "student_intent": "comparison",
            "question_type": "comparison",
            "target_concepts": ["Git", "GitHub"],
            "conversation_state": "new_concept",
            "confidence": 0.94,
            "needs_clarification": false,
            "clarification_question": null,
            "retrieval_query": "Git GitHub differences"
        }"""

        class Completions:
            async def create(self, **_kwargs):
                return SimpleNamespace(
                    choices=[SimpleNamespace(message=SimpleNamespace(content=payload))]
                )

        class FakeAsyncOpenAI:
            def __init__(self, **_kwargs):
                self.chat = SimpleNamespace(completions=Completions())

        with (
            patch.object(settings, "CLASSIFIER_ENABLED", True),
            patch.object(settings, "GROQ_API_KEY", "test-key"),
            patch.dict(sys.modules, {"openai": SimpleNamespace(AsyncOpenAI=FakeAsyncOpenAI)}),
        ):
            result = asyncio.run(classify_message("How are Git and GitHub different?", []))

        self.assertEqual(result.source, "llm")
        self.assertEqual(result.student_intent, "comparison")
        self.assertEqual(result.target_concepts, ("Git", "GitHub"))
        self.assertEqual(result.rewritten_query, "Git GitHub differences")

    def test_invalid_llm_output_falls_back_to_rules(self) -> None:
        class Completions:
            async def create(self, **_kwargs):
                return SimpleNamespace(
                    choices=[SimpleNamespace(message=SimpleNamespace(content="not json"))]
                )

        class FakeAsyncOpenAI:
            def __init__(self, **_kwargs):
                self.chat = SimpleNamespace(completions=Completions())

        with (
            patch.object(settings, "CLASSIFIER_ENABLED", True),
            patch.object(settings, "GROQ_API_KEY", "test-key"),
            patch.dict(sys.modules, {"openai": SimpleNamespace(AsyncOpenAI=FakeAsyncOpenAI)}),
        ):
            result = asyncio.run(classify_message("What is version control?", []))

        self.assertEqual(result.source, "rules")
        self.assertEqual(result.target_concepts, ("version control",))


if __name__ == "__main__":
    unittest.main()
