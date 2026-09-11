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
        self.assertEqual(decision.disclosure_level, 4)

    def test_direct_answer_request_remains_socratic_for_course_content(self) -> None:
        decision = choose_socratic_strategy("Just give me the answer.", [], [SOURCE])
        self.assertEqual(decision.mode, "socratic")
        self.assertEqual(decision.strategy, "return_to_reasoning")
        self.assertEqual(decision.disclosure_level, 0)

    def test_new_concept_question_starts_with_diagnostic_recall(self) -> None:
        decision = choose_socratic_strategy("What is a use case?", [], [SOURCE])
        self.assertEqual(decision.mode, "socratic")
        self.assertEqual(decision.strategy, "diagnostic_recall")
        self.assertEqual(decision.disclosure_level, 0)
        instruction = socratic_system_instruction(decision)
        self.assertIn("Ask exactly one", instruction)
        self.assertIn("Question-only mode", instruction)

    def test_comparison_question_uses_natural_diagnostic_wording(self) -> None:
        question = "What is the difference between software engineering and programming?"
        decision = choose_socratic_strategy(question, [], [SOURCE])
        answer = enforce_socratic_response("A long definition.", question, decision)
        self.assertEqual(
            answer,
            "Before we compare **software engineering** and **programming**, what difference comes to mind first?",
        )

    def test_explain_what_phrase_extracts_only_the_concept(self) -> None:
        question = "Explain what GitHub is."
        decision = choose_socratic_strategy(question, [], [SOURCE])
        answer = enforce_socratic_response("A definition without a question.", question, decision)
        self.assertEqual(
            answer,
            "Before we define **GitHub**, what comes to mind when you hear that term?",
        )

    def test_specific_standalone_diagnostic_question_is_preserved(self) -> None:
        question = "Explain what GitHub is."
        decision = choose_socratic_strategy(question, [], [SOURCE])
        model_answer = (
            "If a project exists only on your laptop, what difficulty might arise when another developer needs to contribute?"
        )
        answer = enforce_socratic_response(model_answer, question, decision)
        self.assertEqual(answer, model_answer)

    def test_polite_explain_what_phrase_uses_the_same_concept(self) -> None:
        question = "Could you please explain what GitHub is?"
        decision = choose_socratic_strategy(question, [], [SOURCE])
        answer = enforce_socratic_response("No question was generated.", question, decision)
        self.assertEqual(decision.strategy, "diagnostic_recall")
        self.assertEqual(
            answer,
            "Before we define **GitHub**, what comes to mind when you hear that term?",
        )

    def test_uncertainty_receives_a_narrower_question(self) -> None:
        decision = choose_socratic_strategy("I am not sure.", [], [SOURCE])
        self.assertEqual(decision.student_state, "uncertain")
        self.assertEqual(decision.strategy, "narrow_guiding_question")
        self.assertEqual(decision.disclosure_level, 0)

    def test_explicit_hint_request_keeps_question_only_disclosure(self) -> None:
        decision = choose_socratic_strategy("Could I have a hint?", [], [SOURCE])
        self.assertEqual(decision.strategy, "narrow_guiding_question")
        self.assertEqual(decision.disclosure_level, 0)

    def test_possible_misconception_uses_guided_comparison(self) -> None:
        decision = choose_socratic_strategy("I thought students should be inside.", [], [SOURCE])
        self.assertEqual(decision.student_state, "possible_misconception")
        self.assertEqual(decision.strategy, "guided_comparison")

    def test_repeated_difficulty_decomposes_without_explaining(self) -> None:
        history = [
            ChatMessage(role="assistant", content="Who interacts with the system?"),
            ChatMessage(role="user", content="A student."),
            ChatMessage(role="assistant", content="Is that person part of the software?"),
        ]
        decision = choose_socratic_strategy("I don't know.", history, [SOURCE])
        self.assertEqual(decision.strategy, "decompose_or_offer_choices")
        self.assertEqual(decision.disclosure_level, 0)
        self.assertIn("Do not explain", decision.instruction)

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
            "Before we define **software engineering**, what comes to mind when you hear that term?",
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
            "Before we define **mentorship**, what comes to mind when you hear that term?",
        )

    def test_tutor_instruction_uses_selective_keyword_emphasis(self) -> None:
        decision = choose_socratic_strategy("What is a use case?", [], [SOURCE])
        instruction = socratic_system_instruction(decision)
        self.assertIn("Markdown bold", instruction)
        self.assertIn("Do not bold complete sentences", instruction)
        self.assertIn("Do not output an explanation, hint", instruction)
        self.assertIn("What evidence", instruction)

    def test_explanation_is_removed_after_repeated_difficulty(self) -> None:
        history = [
            ChatMessage(role="assistant", content="What do you think?"),
            ChatMessage(role="user", content="I am unsure."),
            ChatMessage(role="assistant", content="Which detail helps?"),
        ]
        decision = choose_socratic_strategy("I still don't know.", history, [SOURCE])
        answer = enforce_socratic_response("Actors remain outside the boundary.", "I still don't know.", decision)
        self.assertNotIn("Actors remain outside", answer)
        self.assertEqual(answer.count("?"), 1)

    def test_dialogue_progresses_to_limitation_after_two_questions(self) -> None:
        history = [
            ChatMessage(role="assistant", content="What comes to mind first?"),
            ChatMessage(role="user", content="A user goal."),
            ChatMessage(role="assistant", content="How would you justify that response?"),
            ChatMessage(role="user", content="It describes what the user does."),
        ]
        decision = choose_socratic_strategy("It describes what the user does.", history, [SOURCE])
        self.assertEqual(decision.strategy, "examine_limitation")

    def test_dialogue_progresses_to_synthesis_after_three_questions(self) -> None:
        history = [
            ChatMessage(role="assistant", content="What comes to mind first?"),
            ChatMessage(role="user", content="A user goal."),
            ChatMessage(role="assistant", content="What evidence supports that?"),
            ChatMessage(role="user", content="The actor initiates it."),
            ChatMessage(role="assistant", content="What alternative factor matters?"),
            ChatMessage(role="user", content="The boundary also matters."),
        ]
        decision = choose_socratic_strategy("The boundary also matters.", history, [SOURCE])
        self.assertEqual(decision.strategy, "synthesize_understanding")

    def test_dialogue_progresses_to_reflection_after_four_questions(self) -> None:
        history = [
            ChatMessage(role="assistant", content="What comes to mind first?"),
            ChatMessage(role="user", content="A user goal."),
            ChatMessage(role="assistant", content="What evidence supports that?"),
            ChatMessage(role="user", content="The actor initiates it."),
            ChatMessage(role="assistant", content="What alternative factor matters?"),
            ChatMessage(role="user", content="The system boundary."),
            ChatMessage(role="assistant", content="How can you combine those ideas?"),
            ChatMessage(role="user", content="Actors connect to use cases."),
        ]
        decision = choose_socratic_strategy("Actors connect to use cases.", history, [SOURCE])
        self.assertEqual(decision.strategy, "reflect_on_learning")

    def test_new_concept_resets_the_dialogue_progression(self) -> None:
        history = [
            ChatMessage(role="assistant", content="What comes to mind first?"),
            ChatMessage(role="user", content="A user goal."),
            ChatMessage(role="assistant", content="What evidence supports that?"),
            ChatMessage(role="user", content="The actor initiates it."),
            ChatMessage(role="assistant", content="What alternative factor matters?"),
            ChatMessage(role="user", content="The system boundary."),
        ]
        decision = choose_socratic_strategy("What is encapsulation?", history, [SOURCE])
        self.assertEqual(decision.strategy, "diagnostic_recall")

    def test_feedback_is_removed_from_a_socratic_turn(self) -> None:
        history = [ChatMessage(role="assistant", content="What comes to mind first?")]
        decision = choose_socratic_strategy("It seems related to a user goal.", history, [SOURCE])
        answer = enforce_socratic_response(
            "Your response correctly identifies a very important relationship between the external actor and the internal system behavior in this example.\n\n"
            "What evidence supports your response?",
            "It seems related to a user goal.",
            decision,
        )
        self.assertEqual(answer, "What evidence supports your response?")

    def test_question_only_instruction_forbids_hints_and_feedback(self) -> None:
        decision = choose_socratic_strategy("Could I have a hint?", [], [SOURCE])
        instruction = socratic_system_instruction(decision)
        self.assertIn("Question-only mode", instruction)
        self.assertIn("Do not output an explanation, hint", instruction)

    def test_question_over_twenty_five_words_uses_strategy_fallback(self) -> None:
        history = [ChatMessage(role="assistant", content="What comes to mind first?")]
        decision = choose_socratic_strategy("It seems related to a user goal.", history, [SOURCE])
        long_question = (
            "What evidence from every section of the retrieved course material would you use to explain in extensive "
            "detail why your current response should be accepted as completely correct by another student?"
        )
        answer = enforce_socratic_response(long_question, "It seems related to a user goal.", decision)
        self.assertEqual(answer, "How would you justify or refine that response using the retrieved material?")


if __name__ == "__main__":
    unittest.main()
