from __future__ import annotations

import asyncio
import unittest
from unittest.mock import patch

from starlette.requests import Request

from app import main
from app.guided_lessons import initial_lesson_state
from app.schemas import ChatRequest, Source


def _request() -> Request:
    return Request({"type": "http", "method": "POST", "path": "/api/chat", "headers": []})


SOURCE = Source(
    document_id="doc-1",
    chunk_id="chunk-1",
    title="use-case-diagrams.html",
    text="Use case diagrams show actors, use cases, associations, and a system boundary.",
    score=0.1,
)


class GuidedLessonChatIntegrationTests(unittest.TestCase):
    def _patch_chat_dependencies(self, stored_state=None):
        return (
            patch("app.main._current_user_id", return_value="student-1"),
            patch("app.main._require_course_access", return_value={}),
            patch("app.main.db.is_enabled", return_value=True),
            patch("app.main.db.ensure_conversation", return_value="conversation-1"),
            patch("app.main.db.conversation_belongs_to_course", return_value=True),
            patch("app.main.db.get_messages", return_value=[]),
            patch("app.main.db.add_message"),
            patch("app.main.db.get_pending_clarification", return_value=None),
            patch("app.main.db.get_guided_lesson_state", return_value=stored_state),
            patch("app.main.db.save_guided_lesson_state"),
            patch("app.main.db.list_rag_files", return_value=[]),
            patch("app.main.db.get_course", return_value=None),
            patch("app.main.retrieve", return_value=[SOURCE]),
        )

    def test_use_case_question_starts_and_persists_guided_lesson(self) -> None:
        patches = self._patch_chat_dependencies()
        mocks = [item.start() for item in patches]
        self.addCleanup(lambda: [item.stop() for item in reversed(patches)])

        response = asyncio.run(
            main.chat(
                ChatRequest(
                    message="I have no idea what use case diagrams are.",
                    conversation_id="conversation-1",
                    course_id="course-1",
                ),
                _request(),
            )
        )

        self.assertIn("ATM", response.answer)
        self.assertEqual(response.answer.count("?"), 1)
        mocks[9].assert_called_once()

    def test_active_lesson_uses_saved_step_for_the_next_turn(self) -> None:
        patches = self._patch_chat_dependencies(initial_lesson_state())
        [item.start() for item in patches]
        self.addCleanup(lambda: [item.stop() for item in reversed(patches)])

        response = asyncio.run(
            main.chat(
                ChatRequest(
                    message="I withdraw cash and check my balance.",
                    conversation_id="conversation-1",
                    course_id="course-1",
                ),
                _request(),
            )
        )

        self.assertIn("Who", response.answer)
        self.assertIn("services", response.answer)


if __name__ == "__main__":
    unittest.main()
