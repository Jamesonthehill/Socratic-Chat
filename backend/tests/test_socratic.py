from __future__ import annotations

import unittest

from app.schemas import ChatMessage, Source
from app.socratic import (
    choose_socratic_strategy,
    enforce_socratic_response,
    socratic_system_instruction,
)


SOURCE = Source(
    document_id="doc-1",
    chunk_id="chunk-1",
    title="use-cases.html",
    text="Actors are outside the system boundary and use cases are inside it.",
    score=0.03,
)


class SocraticPolicyTests(unittest.TestCase):
    def test_assignment_logistics_receive_a_direct_answer(self) -> None:
        decision = choose_socratic_strategy("What are the Assignment 4 requirements?", [], [SOURCE])
        self.assertEqual(decision.mode, "direct")
        self.assertEqual(decision.strategy, "grounded_explanation")

    def test_new_concept_question_starts_with_diagnostic_recall(self) -> None:
        decision = choose_socratic_strategy("What is a use case?", [], [SOURCE])
        self.assertEqual(decision.mode, "socratic")
        self.assertEqual(decision.strategy, "diagnostic_recall")
        self.assertIn("Ask exactly one", socratic_system_instruction(decision))

    def test_uncertainty_receives_a_hint(self) -> None:
        decision = choose_socratic_strategy("I am not sure.", [], [SOURCE])
        self.assertEqual(decision.student_state, "uncertain")
        self.assertEqual(decision.strategy, "hint_then_question")

    def test_possible_misconception_uses_guided_comparison(self) -> None:
        decision = choose_socratic_strategy("I thought students should be inside.", [], [SOURCE])
        self.assertEqual(decision.student_state, "possible_misconception")
        self.assertEqual(decision.strategy, "guided_comparison")

    def test_repeated_difficulty_discloses_an_explanation(self) -> None:
        history = [
            ChatMessage(role="assistant", content="Who interacts with the system?"),
            ChatMessage(role="user", content="A student."),
            ChatMessage(role="assistant", content="Is that person part of the software?"),
        ]
        decision = choose_socratic_strategy("I don't know.", history, [SOURCE])
        self.assertEqual(decision.strategy, "explain_then_check")
        self.assertIn("Do not withhold", decision.instruction)

    def test_missing_sources_does_not_generate_an_ungrounded_question(self) -> None:
        decision = choose_socratic_strategy("What is a use case?", [], [])
        self.assertEqual(decision.mode, "direct")

    def test_noncompliant_lecture_is_replaced_by_one_diagnostic_question(self) -> None:
        decision = choose_socratic_strategy("What is mentorship in the paper?", [], [SOURCE])
        lecture = "Mentorship has three benefits:\n- Support\n- Safety\n- Learning"
        answer = enforce_socratic_response(lecture, "What is mentorship in the paper?", decision)
        self.assertEqual(answer.count("?"), 1)
        self.assertIn("mentorship", answer.lower())
        self.assertNotIn("three benefits", answer)

    def test_diagnostic_turn_always_uses_prior_knowledge_question(self) -> None:
        decision = choose_socratic_strategy("What is software engineering?", [], [SOURCE])
        model_answer = (
            "Software engineering includes policies, practices, tools, time, scale, and sustainability. "
            "How do you think sustainability affects software engineering practices?"
        )
        answer = enforce_socratic_response(model_answer, "What is software engineering?", decision)
        self.assertEqual(
            answer,
            "Before we define software engineering, what comes to mind when you hear that term?",
        )
        self.assertNotIn("policies", answer)

    def test_question_that_depends_on_removed_preamble_uses_self_contained_fallback(self) -> None:
        decision = choose_socratic_strategy("What is software engineering?", [], [SOURCE])
        model_answer = (
            "Software engineering considers time, scale, and sustainability. "
            "Where do you think these factors affect a software project?"
        )
        answer = enforce_socratic_response(model_answer, "What is software engineering?", decision)
        self.assertNotIn("these factors", answer.lower())
        self.assertIn("software engineering", answer.lower())
        self.assertEqual(answer.count("?"), 1)

    def test_multiple_model_questions_are_replaced_by_diagnostic_opening(self) -> None:
        decision = choose_socratic_strategy("What is mentorship?", [], [SOURCE])
        answer = enforce_socratic_response(
            "What do you already know? Can you give an example?",
            "What is mentorship?",
            decision,
        )
        self.assertEqual(
            answer,
            "Before we define mentorship, what comes to mind when you hear that term?",
        )

    def test_explanation_is_preserved_after_repeated_difficulty(self) -> None:
        history = [
            ChatMessage(role="assistant", content="What do you think?"),
            ChatMessage(role="user", content="I am unsure."),
            ChatMessage(role="assistant", content="Which detail helps?"),
        ]
        decision = choose_socratic_strategy("I still don't know.", history, [SOURCE])
        answer = enforce_socratic_response("Actors remain outside the boundary.", "I still don't know.", decision)
        self.assertIn("Actors remain outside", answer)
        self.assertEqual(answer.count("?"), 1)


if __name__ == "__main__":
    unittest.main()
