from __future__ import annotations

import asyncio
import json
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import HTTPException
from starlette.requests import Request

from app import db, main, rag
from app.answer_evaluation import AnswerEvaluation
from app.schemas import ChatMessage, ChatRequest, Source


def _request() -> Request:
    return Request({"type": "http", "method": "POST", "path": "/", "headers": []})


class CompletionTests(unittest.TestCase):
    def test_summary_uses_original_question_student_words_and_course_evidence(self) -> None:
        evaluation = AnswerEvaluation(
            concept="code review", keyword_coverage=1, semantic_alignment=1,
            rubric_score=1, total_score=100, correctness=4, completeness=4,
            reasoning=4, application=None, supported_concepts=("readability",),
            missing_concepts=(), critical_misconception=False,
            misconception="Code review only checks style.", feedback="You explained readability.",
            confidence=1,
        )
        response_payload = {
            "final_comment": "You explained why Sam checks readability.",
            "misconception_correction": "Sam also checks correctness.",
            "scenario_wrap_up": "Sam reviews Alex's bug fix for correctness and clarity before release.",
            "opening_answer": "Code review is another engineer's examination of a change.",
        }
        create = AsyncMock(return_value=SimpleNamespace(choices=[SimpleNamespace(
            message=SimpleNamespace(content=json.dumps(response_payload)),
        )]))
        client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
        history = [
            ChatMessage(role="user", content="What is code review?"),
            ChatMessage(role="assistant", content="Imagine Alex submits a bug fix and Sam reviews it. What should Sam check?"),
            ChatMessage(role="user", content="Please give me a hint."),
            ChatMessage(role="user", content="Sam checks readability.", total_score=72),
        ]
        source = Source(document_id="doc", chunk_id="chunk", title="ch09.html",
                        text="Reviewers check correctness and clarity.", score=1)
        with (
            patch("app.rag.generation_client_config", return_value=("Ollama", "key", "http://local", "qwen")),
            patch("app.rag.settings.completion_token_parameters", return_value={"max_tokens": 600}),
            patch("openai.AsyncOpenAI", return_value=client),
            patch("app.rag.write_llm_request_snapshot"),
            patch("app.rag.update_llm_request_snapshot"),
        ):
            summary = asyncio.run(rag.generate_completion_summary(
                "What is code review?", "Sam checks correctness too.", history, [source], evaluation,
            ))
        self.assertEqual(summary.original_question, "What is code review?")
        self.assertEqual(summary.demonstrated, ["Sam checks readability.", "Sam checks correctness too."])
        self.assertEqual(summary.misconception_correction, "Sam also checks correctness.")
        prompt = create.await_args.kwargs["messages"][1]["content"]
        self.assertIn("What is code review?", prompt)
        self.assertIn("Imagine Alex submits a bug fix", prompt)
        self.assertIn("ch09.html", prompt)
        self.assertNotIn("Please give me a hint.", prompt)

    def test_submit_requires_ownership_and_completed_summary(self) -> None:
        with (
            patch("app.main._current_user_id", return_value="student-1"),
            patch("app.main.db.is_enabled", return_value=True),
            patch("app.main.db.conversation_belongs_to", return_value=True),
            patch("app.main.db.submit_conversation", return_value="2026-10-05T19:00:00+00:00"),
        ):
            submitted = asyncio.run(main.submit_conversation("chat-1", _request()))
        self.assertEqual(submitted.submitted_at, "2026-10-05T19:00:00+00:00")

        with (
            patch("app.main._current_user_id", return_value="student-1"),
            patch("app.main.db.is_enabled", return_value=True),
            patch("app.main.db.conversation_belongs_to", return_value=True),
            patch("app.main.db.submit_conversation", return_value=None),
        ):
            with self.assertRaises(HTTPException) as missing:
                asyncio.run(main.submit_conversation("chat-1", _request()))
        self.assertEqual(missing.exception.status_code, 409)

        with (
            patch("app.main._current_user_id", return_value="student-1"),
            patch("app.main.db.is_enabled", return_value=True),
            patch("app.main.db.conversation_belongs_to", return_value=False),
            patch("app.main.db.submit_conversation") as submit,
        ):
            with self.assertRaises(HTTPException) as missing:
                asyncio.run(main.submit_conversation("chat-2", _request()))
        self.assertEqual(missing.exception.status_code, 404)
        submit.assert_not_called()

    def test_finished_chat_rejects_another_teaching_turn(self) -> None:
        with (
            patch("app.main._current_user_id", return_value="student-1"),
            patch("app.main._require_course_access", return_value={"user_id": "student-1"}),
            patch("app.main.db.is_enabled", return_value=True),
            patch("app.main._ensure_course_conversation", return_value=("chat-1", False)),
            patch("app.main.db.get_messages", return_value=[ChatMessage(role="user", content="What is code review?")]),
            patch("app.main.db.get_conversation_completion", return_value=({"original_question": "What is code review?"}, None)),
            patch("app.main.db.add_message") as add_message,
        ):
            with self.assertRaises(HTTPException) as finished:
                asyncio.run(main._run_chat_pipeline(ChatRequest(
                    message="One more question", course_id="course-1", conversation_id="chat-1",
                ), _request()))
        self.assertEqual(finished.exception.status_code, 409)
        add_message.assert_not_called()

    def test_submitted_chat_cannot_be_deleted(self) -> None:
        cursor = MagicMock()
        cursor.fetchone.return_value = ("2026-10-05T19:00:00+00:00",)
        connection = MagicMock()
        connection.__enter__.return_value.cursor.return_value.__enter__.return_value = cursor
        with patch("app.db.init_db"), patch("app.db.get_connection", return_value=connection):
            deleted = db.delete_conversation("chat-1")
        self.assertFalse(deleted)
        self.assertTrue(all("DELETE" not in call.args[0] for call in cursor.execute.call_args_list))
