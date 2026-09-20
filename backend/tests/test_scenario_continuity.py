import unittest
import asyncio
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from app import rag
from app.answer_evaluation import AnswerEvaluation
from app.classifier import MessageClassification
from app.schemas import ChatMessage, Source
from app.socratic import choose_socratic_strategy, conversation_scenario, enforce_socratic_response, socratic_system_instruction


SCENARIO = "Imagine you and a friend share a document and want to preserve earlier versions. What would you do?"
SOURCE = Source(document_id="doc", chunk_id="chunk", title="Version control", text="Version control preserves revisions.", score=1)
CLASSIFICATION = MessageClassification(student_intent="reflection", conversation_state="answering_tutor", dialogue_status="answering_tutor", target="version control")
EVALUATION = AnswerEvaluation(concept="version control", keyword_coverage=0.7, semantic_alignment=0.8,
    rubric_score=0.8, total_score=80, correctness=3, completeness=3, reasoning=3,
    application=None, supported_concepts=("revision history",), missing_concepts=(),
    critical_misconception=False, misconception=None, feedback="You explained preserved revisions.",
    confidence=0.9, progress_status="developing")


class ScenarioContinuityTests(unittest.TestCase):
    def test_generation_receives_old_example_plus_recent_exchange(self):
        history = [ChatMessage(role="assistant", content=SCENARIO)]
        history += [ChatMessage(role="user", content="Save a revision."), ChatMessage(role="assistant", content="Why preserve it?")] * 8
        create = AsyncMock(return_value=SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(
            content="You preserved earlier work.\n\nWhy would saving the shared document's previous version help your friend?"))]))
        client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
        with patch("app.rag.generation_client_config", return_value=("openai", "test-key", "https://api.openai.com/v1", "test-model")), patch("openai.AsyncOpenAI", return_value=client):
            answer = asyncio.run(rag.generate_answer("We can restore earlier work.", history, [SOURCE], CLASSIFICATION, EVALUATION))
        messages = create.call_args.kwargs["messages"]
        self.assertIn(SCENARIO, messages[1]["content"])
        self.assertEqual(sum(item["role"] == "assistant" for item in messages), 4)
        self.assertIn("shared document", answer)

    def test_original_example_survives_beyond_eight_messages(self):
        history = [ChatMessage(role="assistant", content=SCENARIO)]
        history += [ChatMessage(role="user", content="Save a revision."), ChatMessage(role="assistant", content="Why preserve it?")] * 8
        decision = choose_socratic_strategy("We can restore earlier work.", history, [SOURCE], CLASSIFICATION, EVALUATION)
        self.assertEqual(decision.scenario_anchor, SCENARIO)
        self.assertIn(SCENARIO, socratic_system_instruction(decision))
        self.assertEqual(decision.strategy, "probe_reasoning")

    def test_difficulty_simplifies_existing_example(self):
        decision = choose_socratic_strategy("I am stuck.", [ChatMessage(role="assistant", content=SCENARIO)], [SOURCE],
            replace(CLASSIFICATION, support_level=2))
        self.assertEqual(decision.example_type, "simplified_current_example")
        self.assertEqual(decision.scenario_anchor, SCENARIO)
        self.assertIn("same people", decision.instruction)

    def test_evidence_drives_moves(self):
        cases = [(replace(EVALUATION, correctness=0), "scaffold_then_question"),
                 (replace(EVALUATION, critical_misconception=True), "guided_comparison"),
                 (replace(EVALUATION, missing_concepts=("restoration",)), "extend_scenario"),
                 (EVALUATION, "probe_reasoning"),
                 (replace(EVALUATION, progress_status="ready_for_verification"), "mastery_verification")]
        for evaluation, expected in cases:
            with self.subTest(expected=expected):
                decision = choose_socratic_strategy("My answer", [], [SOURCE], CLASSIFICATION, evaluation)
                self.assertEqual(decision.strategy, expected)

    def test_fallback_does_not_introduce_another_project(self):
        decision = choose_socratic_strategy("Save copies.", [ChatMessage(role="assistant", content=SCENARIO)], [SOURCE], CLASSIFICATION, EVALUATION)
        answer = enforce_socratic_response("", "Save copies.", decision)
        self.assertIn("In our example", answer)
        self.assertNotIn("new situation", answer)

    def test_partial_answer_extends_the_same_scenario_without_supplying_facts(self):
        evaluation = replace(EVALUATION, correctness=2, missing_concepts=("clarity", "maintainability"))
        decision = choose_socratic_strategy(
            "It verifies the code structure.",
            [ChatMessage(role="assistant", content=SCENARIO)],
            [SOURCE],
            replace(CLASSIFICATION, target="code review"),
            evaluation,
        )
        answer = enforce_socratic_response(
            "Partly—you are on the right track. Code review also checks correctness, clarity, and maintainability.",
            "It verifies the code structure.",
            decision,
        )
        self.assertEqual(decision.strategy, "extend_scenario")
        self.assertTrue(answer.startswith("Stay with this example"))
        self.assertIn("friend share a document", answer)
        self.assertNotIn("Partly", answer)
        self.assertNotIn("correctness", answer)
        self.assertEqual(answer.count("?"), 1)

    def test_generated_same_scenario_complication_is_preserved(self):
        evaluation = replace(EVALUATION, correctness=2, missing_concepts=("clarity",))
        decision = choose_socratic_strategy(
            "It verifies the code structure.",
            [ChatMessage(role="assistant", content=SCENARIO)],
            [SOURCE],
            replace(CLASSIFICATION, target="code review"),
            evaluation,
        )
        candidate = (
            "Now suppose the code works, but another teammate cannot understand the variable names. "
            "What else should the reviewer examine?"
        )
        self.assertEqual(
            enforce_socratic_response(candidate, "It verifies the code structure.", decision),
            candidate,
        )

    def test_fallback_repeats_concrete_details_from_the_original_software_scenario(self):
        software_scenario = (
            "Consider a team of developers working together on a software project. Each developer edits files on "
            "their own computer, but sometimes their changes conflict or overwrite each other. How might a system help?"
        )
        evaluation = replace(EVALUATION, correctness=2, missing_concepts=("history",))
        decision = choose_socratic_strategy(
            "Maybe reduce the code conflicts?",
            [ChatMessage(role="assistant", content=software_scenario)],
            [SOURCE],
            replace(CLASSIFICATION, target="version control"),
            evaluation,
        )
        answer = enforce_socratic_response(
            "Partly. Version control also provides history.",
            "Maybe reduce the code conflicts?",
            decision,
        )
        self.assertIn("team of developers", answer)
        self.assertIn("software project", answer)
        self.assertIn("edits files", answer)
        self.assertNotIn("same people encounter another complication", answer)
        self.assertEqual(answer.count("?"), 1)

    def test_explicit_example_change_resets_anchor(self):
        history = [ChatMessage(role="assistant", content=SCENARIO)]
        decision = choose_socratic_strategy("Use a different example.", history, [SOURCE], CLASSIFICATION)
        self.assertIsNone(decision.scenario_anchor)
        history += [ChatMessage(role="user", content="Use a different example."),
                    ChatMessage(role="assistant", content="Suppose your team tests a login feature. Where would you work?")]
        self.assertIn("login feature", conversation_scenario(history))

    def test_transfer_keeps_original_example_available(self):
        decision = choose_socratic_strategy("I can explain it.", [ChatMessage(role="assistant", content=SCENARIO)], [SOURCE], CLASSIFICATION,
            replace(EVALUATION, progress_status="ready_for_verification"))
        self.assertEqual(decision.scenario_anchor, SCENARIO)
        self.assertIn("change only one condition", decision.instruction)
