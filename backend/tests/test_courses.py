from __future__ import annotations

import asyncio
import unittest
from unittest.mock import patch

from fastapi import HTTPException
from starlette.requests import Request

from app import main, rag
from app.schemas import ChatRequest, CourseCreateRequest


def _request() -> Request:
    return Request({"type": "http", "method": "GET", "path": "/", "headers": []})


class CourseAuthorizationTests(unittest.TestCase):
    @patch("app.main._current_user_id", return_value="student-1")
    def test_chat_requires_a_selected_course(self, _current_user_id) -> None:
        with self.assertRaises(HTTPException) as context:
            asyncio.run(main.chat(ChatRequest(message="What is regression?"), _request()))
        self.assertEqual(context.exception.status_code, 400)
        self.assertIn("approved course", context.exception.detail)

    @patch("app.main.db.user_can_access_course", return_value=False)
    @patch("app.main.db.get_user_by_id", return_value={"user_id": "student-1"})
    @patch("app.main._current_user_id", return_value="student-1")
    def test_pending_student_cannot_access_course(
        self,
        _current_user_id,
        _get_user,
        _can_access,
    ) -> None:
        with self.assertRaises(HTTPException) as context:
            main._require_course_access(_request(), "course-1")
        self.assertEqual(context.exception.status_code, 403)
        self.assertIn("approved", context.exception.detail)

    @patch("app.main.db.create_course")
    @patch("app.main._require_authority", return_value={"user_id": "instructor-1"})
    def test_instructor_can_create_course(self, _require_authority, create_course) -> None:
        create_course.return_value = {
            "course_id": "course-1",
            "course_code": "ITCS 3153",
            "title": "Artificial Intelligence",
            "description": "Course materials",
            "instructor_id": "instructor-1",
            "instructor_name": "Professor One",
            "membership_role": None,
            "membership_status": None,
            "document_count": 0,
            "pending_request_count": 0,
        }
        response = asyncio.run(
            main.create_course(
                CourseCreateRequest(
                    course_code="ITCS 3153",
                    title="Artificial Intelligence",
                    description="Course materials",
                ),
                _request(),
            )
        )
        self.assertEqual(response.membership_role, "instructor")
        self.assertEqual(response.membership_status, "approved")


class CourseRagIsolationTests(unittest.TestCase):
    def test_same_document_in_different_courses_gets_different_ids(self) -> None:
        first = rag.document_id("syllabus.pdf", "same text", course_id="course-a")
        second = rag.document_id("syllabus.pdf", "same text", course_id="course-b")
        self.assertNotEqual(first, second)

    @patch("app.rag.load_index")
    def test_retrieval_returns_only_selected_course_chunks(self, load_index) -> None:
        load_index.return_value = [
            {
                "document_id": "doc-a",
                "chunk_id": "doc-a:0",
                "course_id": "course-a",
                "title": "A.txt",
                "text": "linear regression model",
                "tokens": ["linear", "regression", "model"],
            },
            {
                "document_id": "doc-b",
                "chunk_id": "doc-b:0",
                "course_id": "course-b",
                "title": "B.txt",
                "text": "linear regression model",
                "tokens": ["linear", "regression", "model"],
            },
        ]
        sources = rag.retrieve("linear regression", course_id="course-a")
        self.assertEqual([source.document_id for source in sources], ["doc-a"])


if __name__ == "__main__":
    unittest.main()
