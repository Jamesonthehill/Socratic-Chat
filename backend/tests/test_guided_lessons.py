from __future__ import annotations

import unittest

from app.guided_lessons import (
    USE_CASE_STEPS,
    advance_use_case_lesson,
    matches_use_case_lesson,
    sources_support_use_case_lesson,
    start_use_case_lesson,
    unrelated_new_topic,
)
from app.schemas import Source


SOURCE = Source(
    document_id="doc-1",
    chunk_id="chunk-1",
    title="use-case-diagrams.html",
    text="A use case diagram shows actors, use cases, associations, and a system boundary.",
    score=0.1,
)


class GuidedUseCaseLessonTests(unittest.TestCase):
    def test_topic_detection_does_not_replace_assignment_logistics(self) -> None:
        self.assertTrue(matches_use_case_lesson("What is a use case diagram?"))
        self.assertFalse(matches_use_case_lesson("What are the use case diagram assignment requirements?"))

    def test_sources_must_support_the_lesson_topic(self) -> None:
        self.assertTrue(sources_support_use_case_lesson([SOURCE]))
        unrelated = SOURCE.model_copy(update={"text": "Version control records changes."})
        self.assertFalse(sources_support_use_case_lesson([unrelated]))

    def test_lesson_starts_with_one_concrete_scenario_question(self) -> None:
        turn = start_use_case_lesson()
        self.assertEqual(turn.answer.count("?"), 1)
        self.assertIn("ATM", turn.answer)
        self.assertEqual(turn.state["step_index"], 0)
        self.assertFalse(turn.state["completed"])

    def test_successful_responses_complete_the_guided_sequence(self) -> None:
        responses = [
            "I withdraw cash and check my balance.",
            "I am the customer.",
            "A user or actor.",
            "Yes, because the external service interacts across the boundary.",
            "A function or use case.",
            "The actor participates in and connects to the use case.",
            "Inside the system boundary.",
            "Outside the boundary.",
            "The include relationship because it is required.",
            "The extend relationship because it is optional.",
            "A student actor can borrow a book.",
            "Actors outside the boundary connect to use cases inside the boundary.",
        ]
        state = start_use_case_lesson().state
        for index, response in enumerate(responses):
            turn = advance_use_case_lesson(response, state)
            state = turn.state
            if index < len(responses) - 1:
                self.assertEqual(turn.answer.count("?"), 1)

        self.assertTrue(state["completed"])
        self.assertEqual(len(state["mastered_components"]), len(USE_CASE_STEPS))
        self.assertIn("guided lesson is complete", turn.answer.lower())

    def test_two_failed_attempts_provide_help_and_advance_one_step(self) -> None:
        state = start_use_case_lesson().state
        hint_turn = advance_use_case_lesson("I do not know.", state)
        self.assertEqual(hint_turn.state["step_index"], 0)
        self.assertEqual(hint_turn.state["attempts"], 1)
        self.assertEqual(hint_turn.answer.count("?"), 1)

        explanation_turn = advance_use_case_lesson("I still do not know.", hint_turn.state)
        self.assertEqual(explanation_turn.state["step_index"], 1)
        self.assertEqual(explanation_turn.state["attempts"], 0)
        self.assertEqual(explanation_turn.answer.count("?"), 1)
        self.assertEqual(explanation_turn.state["mastered_components"], [])

    def test_unrelated_concept_question_can_exit_the_lesson(self) -> None:
        self.assertTrue(unrelated_new_topic("What is version control?"))
        self.assertFalse(unrelated_new_topic("What is an actor?"))

    def test_scripted_feedback_stays_brief_and_specific(self) -> None:
        for step in USE_CASE_STEPS:
            self.assertLessEqual(len(step.success_feedback.split()), 10)
            self.assertNotRegex(step.success_feedback.lower(), r"\b(?:excellent|great|good job)\b")


if __name__ == "__main__":
    unittest.main()
