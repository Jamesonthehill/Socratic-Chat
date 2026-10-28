"""Source-grounded Socratic setup drafting checks (no live model calls)."""
from __future__ import annotations

import asyncio
import json
import sys
import unittest
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "Socratic-Chat/backend"))

from platform_app import engines, routes, socratic_setup
from platform_app.schemas import SocraticConfig


class SocraticSetupTests(unittest.TestCase):
    def test_material_reference_resolves_only_selected_published_pages(self):
        assignment = {"tool": "socratic", "status": "published", "snapshot": {
            "config": {"document_ids": ["selected"]}, "chunks": [
                {"document_id": "other", "page_number": 1, "title": "Private.pdf",
                 "text": "Sample output must stay private."},
                {"document_id": "selected", "page_number": 2, "title": "Selected.pdf",
                 "text": "Table 1 lists the choices."},
                {"document_id": "selected", "page_number": 3, "title": "Selected.pdf",
                 "text": "Sample output: What would you like?"},
            ]}}
        account = {"authority_level": 2, "user_id": "student"}

        @contextmanager
        def connection():
            yield object()

        with patch.object(routes.store, "connection", side_effect=connection), \
             patch.object(routes, "get_assignment", return_value=assignment):
            resolved = routes.assignment_material_reference(uuid4(), "sample output", "other", account)
            self.assertEqual((resolved["document_id"], resolved["page_number"]), ("selected", 3))
            self.assertEqual(routes.assignment_material_reference(uuid4(), "page 2", None, account)["page_number"], 2)
            with self.assertRaises(HTTPException) as not_found:
                routes.assignment_material_reference(uuid4(), "page 1", None, account)
            self.assertEqual(not_found.exception.status_code, 404)

    def test_guided_learning_path_duration_is_instructor_configurable(self):
        self.assertEqual(SocraticConfig().learning_path_minutes, 7)
        config = {"minimum_messages": 1, "guidance_mode": "guided", "learning_path_minutes": 20,
                  "learning_steps": [{"title": "Choose size", "goal": "Read the menu"}]}
        assignment = {"tool": "socratic", "status": "published", "config": config,
                      "snapshot": {"config": config, "chunks": []}}
        self.assertEqual(routes.public_assignment(assignment)["student_config"]["learning_path_time_limit_seconds"], 1200)
        for invalid in (0, 181):
            with self.assertRaises(ValueError):
                SocraticConfig.model_validate({"learning_path_minutes": invalid})

    def test_student_step_visual_uses_only_selected_published_source(self):
        config = {"minimum_messages": 1, "guidance_mode": "guided", "document_ids": ["selected"],
                  "learning_steps": [
                      {"title": "Choose size", "goal": "Read the menu", "source_chunk_id": "chunk-1",
                       "evidence_quote": "What would you like? (small/ medium/ large/ off/ report)"},
                      {"title": "Other", "goal": "Private", "source_chunk_id": "chunk-2",
                       "evidence_quote": "Private course text."},
                  ]}
        assignment = {"tool": "socratic", "status": "published", "config": config,
                      "snapshot": {"config": config, "chunks": [
                          {"document_id": "selected", "chunk_id": "chunk-1", "title": "menu.pdf",
                           "page_number": 3, "text": config["learning_steps"][0]["evidence_quote"]},
                          {"document_id": "other", "chunk_id": "chunk-2", "title": "private.pdf",
                           "text": "Private course text."},
                      ]}}
        student_config = routes.public_assignment(assignment)["student_config"]
        steps = student_config["learning_steps"]
        self.assertEqual(student_config["learning_path_time_limit_seconds"], 420)
        self.assertEqual(steps[0]["source"]["title"], "menu.pdf")
        self.assertEqual(steps[0]["source"]["document_id"], "selected")
        self.assertEqual(steps[0]["source"]["page_number"], 3)
        self.assertIsNone(steps[1]["source"])
        self.assertEqual(routes.socratic_step_source(assignment, config["learning_steps"][0]), steps[0]["source"])
        self.assertIsNone(routes.socratic_step_source(assignment, config["learning_steps"][1]))

    def test_student_material_reader_exposes_only_published_selection(self):
        assignment = {"tool": "socratic", "status": "published", "course_id": uuid4(),
                      "snapshot": {"config": {"document_ids": ["selected"]}, "chunks": [
                          {"document_id": "selected", "chunk_id": "chunk-1", "title": "Selected", "page_number": 2,
                           "text": "Check ingredients before payment."},
                          {"document_id": "other", "chunk_id": "chunk-2", "title": "Other", "text": "Private course text."},
                      ]}}
        account = {"authority_level": 2, "user_id": "student"}
        original = {"filename": "assignment.pdf", "content_type": "application/pdf", "file_size": 3, "content": b"pdf"}

        @contextmanager
        def connection():
            yield object()

        with patch.object(routes.store, "connection", side_effect=connection), \
             patch.object(routes, "get_assignment", return_value=assignment), \
             patch.object(routes.db, "get_course_rag_file", return_value=original) as lookup:
            manifest = routes.assignment_materials(uuid4(), account)
            self.assertEqual([item["document_id"] for item in manifest["materials"]], ["selected"])
            self.assertEqual(manifest["materials"][0]["title"], "assignment.pdf")
            response = routes.download_assignment_material(uuid4(), "selected", account)
            self.assertEqual(response.body, b"pdf")
            self.assertIn("attachment", response.headers["content-disposition"])
            self.assertEqual(lookup.call_args.kwargs, {"include_content": True})
            with self.assertRaises(HTTPException) as denied:
                routes.download_assignment_material(uuid4(), "other", account)
            self.assertEqual(denied.exception.status_code, 404)

    def test_deleted_original_cannot_be_downloaded(self):
        assignment = {"tool": "socratic", "status": "published", "course_id": uuid4(),
                      "snapshot": {"config": {"document_ids": ["selected"]}, "chunks": [
                          {"document_id": "selected", "chunk_id": "chunk-1", "title": "assignment.pdf",
                           "page_number": 1, "text": "Read the requirements."},
                      ]}}

        @contextmanager
        def connection():
            yield object()

        with patch.object(routes.store, "connection", side_effect=connection), \
             patch.object(routes, "get_assignment", return_value=assignment), \
             patch.object(routes.db, "get_course_rag_file", return_value=None):
            with self.assertRaises(HTTPException) as missing:
                routes.download_assignment_material(uuid4(), "selected", {"authority_level": 2})
            self.assertEqual(missing.exception.status_code, 404)

    def test_every_selected_file_contributes_indexed_evidence(self):
        files = [
            {"id": "file-1", "filename": "assignment.pdf"},
            {"id": "file-2", "filename": "skeleton.py"},
        ]
        def chunks(file_id):
            return [{"chunk_id": file_id + "-chunk", "text": "A documented concept.", "title": file_id}]
        with patch.object(socratic_setup.db, "get_document_chunks_for_objectives", side_effect=chunks):
            evidence, ids, sources = socratic_setup.selected_evidence(files)
        self.assertIn("assignment.pdf", evidence)
        self.assertIn("skeleton.py", evidence)
        self.assertEqual(ids, {"file-1-chunk", "file-2-chunk"})
        self.assertEqual(sources["file-1-chunk"], "assignment.pdf")

    def test_unindexed_file_cannot_generate_draft(self):
        with patch.object(socratic_setup.db, "get_document_chunks_for_objectives", return_value=[]):
            with self.assertRaisesRegex(ValueError, "no indexed text"):
                socratic_setup.selected_evidence([{"id": "file-1", "filename": "assignment.pdf"}])

    def test_long_file_includes_submission_directions_near_the_end(self):
        chunks = [
            {"chunk_id": f"chunk-{index}", "text": "General material " + "x" * 2500, "title": "Assignment"}
            for index in range(20)
        ]
        chunks[-1]["text"] = "Turn in the Python file through Canvas."
        with patch.object(socratic_setup.db, "get_document_chunks_for_objectives", return_value=chunks):
            evidence, ids, _ = socratic_setup.selected_evidence([{"id": "file-1", "filename": "assignment.pdf"}])
        self.assertIn("Turn in the Python file", evidence)
        self.assertIn("chunk-19", ids)

    def test_model_draft_must_cite_selected_evidence(self):
        result = {
            "keywords": ["Branching"], "opening_prompt": "Suppose you change one feature. What would you do first?",
            "student_instructions": "Discuss branching in chat.", "minimum_messages": 3,
            "learning_steps": [
                {"title": "Choose a branch", "goal": "Explain why you would choose a branch.", "evidence_quote": "Choose a branch before editing.", "source_chunk_id": "selected-chunk"},
                {"title": "Review the change", "goal": "Explain how you would review the change.", "evidence_quote": "Review the change before merging.", "source_chunk_id": "selected-chunk"},
            ],
            "source_chunk_ids": ["other-course-chunk"],
        }
        with self.assertRaisesRegex(ValueError, "ungrounded"):
            socratic_setup.validate_draft(json.dumps(result), {"selected-chunk"})
        result["source_chunk_ids"] = ["selected-chunk"]
        evidence = '<file name="assignment.pdf">\n[chunk_id=selected-chunk] Choose a branch before editing. Review the change before merging.\n</file>'
        self.assertEqual(socratic_setup.validate_draft(json.dumps(result), {"selected-chunk"}, evidence)["source_chunk_ids"], ["selected-chunk"])
        result["learning_steps"][1]["evidence_quote"] = "An invented requirement."
        repaired = socratic_setup.validate_draft(json.dumps(result), {"selected-chunk"}, evidence)
        self.assertEqual(repaired["learning_steps"][1]["evidence_quote"], "Review the change before merging.")

    def test_generation_uses_model_and_keeps_editable_fields(self):
        payload = {
            "opening_prompt": "Imagine the sandwich machine asks for a size. What would you choose?",
            "student_instructions": "Discuss the menu choices and submit the code through Canvas.",
            "minimum_messages": 4,
            "learning_steps": [
                {"title": "Choose a size", "goal": "Explain how the user selects a size.", "scenario": "The machine asks a customer to choose a sandwich size.", "question": "Which size would you choose, and why?", "evidence_quote": "Choose a sandwich size.", "source_chunk_id": "chunk-1"},
                {"title": "Submit the code", "goal": "Explain what code you will submit.", "scenario": "After working through the machine, you prepare its code for submission.", "question": "How would you prepare the code for submission?", "evidence_quote": "Submit the code through Canvas.", "source_chunk_id": "chunk-1"},
            ],
            "source_chunk_ids": ["chunk-1"],
        }
        async def fake_completion(_key, _url, request):
            self.assertIn("[chunk_id=chunk-1]", request["messages"][1]["content"])
            self.assertIn("Canvas description: Submit the code through Canvas", request["messages"][1]["content"])
            self.assertIn("EVERY step its own concrete", request["messages"][0]["content"])
            self.assertIn("Do not invent quantities", request["messages"][0]["content"])
            self.assertNotIn("max_tokens", request)
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(payload)))])
        with patch.object(socratic_setup.db, "get_document_chunks_for_objectives", return_value=[
            {"chunk_id": "chunk-1", "text": "Choose a sandwich size. Submit the code through Canvas.", "title": "Assignment"}
        ]), patch.object(socratic_setup.settings, "llm_client_config", return_value=("Ollama", "test", "http://localhost", "model")), patch.object(
            socratic_setup, "chat_completion", side_effect=fake_completion,
        ):
            result = asyncio.run(socratic_setup.generate_setup(
                [{"id": "file-1", "filename": "assignment.pdf"}],
                "Sandwich Maker", "Submit the code through Canvas",
            ))
        self.assertEqual(result["minimum_messages"], 4)
        self.assertEqual(result["prompt"], payload["opening_prompt"])
        self.assertEqual(result["instructions"], payload["student_instructions"])
        self.assertEqual([step["title"] for step in result["learning_steps"]], ["Choose a size", "Submit the code"])
        self.assertEqual(result["learning_steps"][1]["question"], payload["learning_steps"][1]["question"])
        self.assertEqual(result["learning_steps"][0]["source_file"], "assignment.pdf")

    def test_hosted_generation_has_no_application_output_token_cap(self):
        requests = []

        async def fake_completion(_key, _url, request):
            requests.append(request.copy())
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="{}"))])

        with patch.object(socratic_setup.db, "get_document_chunks_for_objectives", return_value=[
            {"chunk_id": "chunk-1", "text": "Choose a sandwich size.", "title": "Assignment"}
        ]), patch.object(socratic_setup.settings, "llm_client_config", return_value=("Groq", "test", "https://example.invalid", "openai/gpt-oss-20b")), patch.object(
            socratic_setup, "chat_completion", side_effect=fake_completion,
        ):
            with self.assertRaises(ValueError):
                asyncio.run(socratic_setup.generate_setup(
                    [{"id": "file-1", "filename": "assignment.pdf"}], "Sandwich Maker", ""
                ))
        self.assertEqual(len(requests), 2)
        self.assertTrue(all("max_completion_tokens" not in request and "max_tokens" not in request
                            for request in requests))

    def test_basic_opening_generation_only_returns_grounded_question(self):
        responses = [
            {"opening_prompt": "Which sandwich would you choose?", "source_chunk_id": "another-course"},
            {"opening_prompt": "The machine checks its supplies before taking coins. What should it check first?", "source_chunk_id": "chunk-1"},
        ]
        requests = []

        async def fake_completion(_key, _url, request):
            requests.append(request)
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(responses.pop(0))))])

        with patch.object(socratic_setup.db, "get_document_chunks_for_objectives", return_value=[
            {"chunk_id": "chunk-1", "text": "The machine checks its supplies before taking coins.", "title": "Assignment"}
        ]), patch.object(socratic_setup.settings, "llm_client_config", return_value=("Ollama", "test", "http://localhost", "model")), patch.object(
            socratic_setup, "chat_completion", side_effect=fake_completion,
        ):
            prompt = asyncio.run(socratic_setup.generate_opening_prompt(
                [{"id": "file-1", "filename": "assignment.pdf"}],
                "Sandwich Maker", "Explain how the machine handles an order.",
            ))
        self.assertEqual(prompt, "The machine checks its supplies before taking coins. What should it check first?")
        self.assertIn("[chunk_id=chunk-1]", requests[0]["messages"][1]["content"])
        self.assertIn("50 to 90 words", requests[0]["messages"][0]["content"])
        self.assertNotIn("learning_steps", requests[0]["response_format"]["json_schema"]["schema"]["properties"])

    def test_rich_source_retries_a_brief_first_example_without_losing_valid_draft(self):
        source = ("A teammate reviews the code before merging and notices that an empty list crashes the function. "
                  "The developer needs to decide how to respond and what to test next. ") * 12
        payload = {
            "opening_prompt": "A teammate reviews your change. What would you check first?",
            "student_instructions": "You will discuss the review and plan a response.",
            "minimum_messages": 2,
            "learning_steps": [
                {"title": "Review feedback", "goal": "Explain what the reviewer found.",
                 "scenario": "A teammate notices an empty-list crash.",
                 "question": "How should you respond to this review?",
                 "evidence_quote": "A teammate reviews the code before merging", "source_chunk_id": "chunk-1"},
                {"title": "Plan a test", "goal": "Choose an edge-case test.",
                 "scenario": "The same team prepares another test.",
                 "question": "Which input should the team test next?",
                 "evidence_quote": "an empty list crashes the function", "source_chunk_id": "chunk-1"},
            ],
            "source_chunk_ids": ["chunk-1"],
        }
        longer = dict(payload)
        longer["learning_steps"] = [
            {**payload["learning_steps"][0], "scenario": (
                "You are the developer who has just opened a change for review. A teammate tries the function "
                "with an empty list and sees it crash, even though ordinary lists worked. The change is not "
                "merged yet, so you can investigate the problem and discuss it with your teammate. You need "
                "to decide what to check before changing the code."
            )},
            {**payload["learning_steps"][1], "scenario": (
                "The same developer has discussed the crash with the reviewer, and the change is still waiting "
                "to be merged. Ordinary lists worked, but an empty list caused the function to fail. The team "
                "now needs a test that captures what happened before they change the code. You are deciding "
                "which input to try next and why it matters for this review."
            )},
        ]
        responses = [payload, longer]
        requests = []

        async def fake_completion(_key, _url, request):
            requests.append(len(request["messages"]))
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(responses.pop(0))))])

        with patch.object(socratic_setup.db, "get_document_chunks_for_objectives", return_value=[
            {"chunk_id": "chunk-1", "text": source, "title": "Code review"}
        ]), patch.object(socratic_setup.settings, "llm_client_config", return_value=("Ollama", "test", "http://localhost", "model")), patch.object(
            socratic_setup, "chat_completion", side_effect=fake_completion,
        ):
            result = asyncio.run(socratic_setup.generate_setup(
                [{"id": "file-1", "filename": "review.pdf"}], "Code review", "Discuss the review."
            ))
        self.assertEqual(requests, [2, 3])
        self.assertTrue(result["learning_steps"][0]["scenario"].startswith("You are the developer"))
        self.assertNotIn("first_example_needs_review", result)
        self.assertNotIn("brief_steps_needing_review", result)

    def test_rich_source_retries_a_brief_later_scene(self):
        source = ("A teammate reviews the code before merging and notices that an empty list crashes the function. "
                  "The developer needs to decide how to respond and what to test next. ") * 12
        first = ("You are the developer reviewing a proposed change with a teammate. The function behaves well "
                 "for populated lists, but the reviewer found that it crashes on an empty list. The code has "
                 "not been merged yet, and both of you want to understand what went wrong before editing it. "
                 "You can inspect the feedback and decide what needs attention first.")
        brief = {"title": "Plan a test", "goal": "Choose an edge-case test.",
                 "scenario": "The same team prepares another test.",
                 "question": "Which input should the team test next?",
                 "evidence_quote": "an empty list crashes the function", "source_chunk_id": "chunk-1"}
        payload = {"opening_prompt": "A teammate reviews your change. What would you check first?",
                   "student_instructions": "You will discuss the review and plan a response.",
                   "minimum_messages": 2, "source_chunk_ids": ["chunk-1"],
                   "learning_steps": [{"title": "Review feedback", "goal": "Explain what the reviewer found.",
                                       "scenario": first, "question": "How should you respond to this review?",
                                       "evidence_quote": "A teammate reviews the code before merging",
                                       "source_chunk_id": "chunk-1"}, brief]}
        improved = {**payload, "learning_steps": [payload["learning_steps"][0], {**brief, "scenario": (
            "The same developer and reviewer are still examining the empty-list crash before merging. A "
            "populated list worked, but the empty list did not, so an ordinary test would miss the issue. "
            "The reviewer wants a test that makes the failure visible while the developer investigates. "
            "You need to decide which input will show the problem and what result you expect to observe."
        )}]}
        replies = [payload, improved]
        with patch.object(socratic_setup.db, "get_document_chunks_for_objectives", return_value=[
            {"chunk_id": "chunk-1", "text": source, "title": "Code review"}
        ]), patch.object(socratic_setup.settings, "llm_client_config", return_value=("Ollama", "test", "http://localhost", "model")), patch.object(
            socratic_setup, "chat_completion", side_effect=lambda *_args: SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(replies.pop(0))))]
            ),
        ) as completion:
            result = asyncio.run(socratic_setup.generate_setup(
                [{"id": "file-1", "filename": "review.pdf"}], "Code review", "Discuss the review."
            ))
        self.assertEqual(completion.call_count, 2)
        self.assertGreaterEqual(len(result["learning_steps"][1]["scenario"].split()), 45)
        self.assertNotIn("brief_steps_needing_review", result)

    def test_short_scene_is_flagged_even_when_it_has_a_question_and_concrete_details(self):
        source = "The machine asks the customer to choose a size before checking ingredients. " * 12
        scene = (
            "You walk up to the machine and see its size menu. You decide to order a small ham "
            "sandwich. The machine will check whether it has enough ingredients before asking you "
            "to pay, and you need to decide what should happen next."
        )
        self.assertTrue(socratic_setup.brief_opening(scene, source))

    def test_student_as_tutor_is_rejected(self):
        payload = {
            "opening_prompt": "Imagine choosing a sandwich size. What would you do?",
            "student_instructions": "You will act as a tutor helping me.",
            "minimum_messages": 3,
            "learning_steps": [
                {"title": "Choose a size", "goal": "Explain how you choose a size.", "evidence_quote": "Choose a sandwich size.", "source_chunk_id": "chunk-1"},
                {"title": "Discuss the size", "goal": "Explain why that size fits.", "evidence_quote": "Choose a sandwich size.", "source_chunk_id": "chunk-1"},
            ],
            "source_chunk_ids": ["chunk-1"],
        }
        evidence = '<file name="assignment.pdf">\n[chunk_id=chunk-1] Choose a sandwich size.\n</file>'
        with self.assertRaisesRegex(ValueError, "ungrounded"):
            socratic_setup.validate_draft(json.dumps(payload), {"chunk-1"}, evidence)
        payload["student_instructions"] = "Discuss sandwich sizes in chat."
        self.assertEqual(
            socratic_setup.validate_draft(json.dumps(payload), {"chunk-1"}, evidence)["prompt"],
            payload["opening_prompt"],
        )

    def test_student_start_uses_the_instructor_edited_opening(self):
        opening = "Imagine the sandwich machine asks for a size. Which size would you try?"
        started = engines.start({
            "tool": "socratic", "title": "Sandwich Maker",
            "snapshot": {
                "config": {"scope_mode": "keywords", "prompt": opening},
                "approved_keywords": ["menu choice"], "chunks": [],
            },
        }, {})
        self.assertEqual(started["messages"][0]["content"], opening)

    def test_start_route_attaches_the_selected_source_to_the_opening_message(self):
        assignment = {"tool": "socratic", "title": "Sandwich Maker", "snapshot": {
            "config": {"document_ids": ["selected"], "learning_steps": [{
                "title": "Choose a size", "scenario": "A customer sees the sandwich menu.",
                "question": "Which menu option would you choose?", "source_chunk_id": "menu-page",
                "evidence_quote": "What would you like? (small/ medium/ large)"}]},
            "chunks": [{"document_id": "selected", "chunk_id": "menu-page", "title": "Sandwich.pdf",
                        "page_number": 3, "text": "What would you like? (small/ medium/ large)"}],
        }}
        attempt = {"status": "in_progress", "messages": [], "engine_state": {}}
        connection = SimpleNamespace(execute=lambda *_: SimpleNamespace(fetchone=lambda: attempt))
        @contextmanager
        def locked(_assignment_id, _student_id):
            yield connection, None
        with patch.object(routes.store, "locked_attempt", side_effect=locked), \
             patch.object(routes, "get_assignment", return_value=assignment), \
             patch.object(routes.store, "save_attempt"):
            result = routes.start(uuid4(), {"user_id": "student"})
        self.assertEqual(result["messages"][0]["step_source"]["page_number"], 3)
        self.assertEqual(result["messages"][0]["step_source"]["document_id"], "selected")

    def test_student_start_tracks_first_generated_step(self):
        started = engines.start({
            "tool": "socratic", "title": "Sandwich Maker",
            "snapshot": {"config": {"prompt": "How would you begin?", "learning_steps": [
                {"title": "Choose size", "goal": "Choose a sandwich size.",
                 "scenario": "A customer arrives at the sandwich machine and sees the size menu.",
                 "question": "How should the program handle the customer's first choice?"},
                {"title": "Check bread", "goal": "Check available bread."},
            ]}, "chunks": []},
        }, {})
        self.assertEqual(started["socratic"]["learning_step_index"], 0)
        self.assertEqual(started["socratic"]["step_started_at_message_count"], 1)
        self.assertEqual(started["socratic"]["next_thinking_step"], "How should the program handle the customer's first choice?")
        self.assertIn("A customer arrives at the sandwich machine", started["messages"][0]["content"])
        self.assertTrue(started["messages"][0]["content"].endswith("How should the program handle the customer's first choice?"))
        self.assertNotIn("How would you begin?", started["messages"][0]["content"])

    def test_student_start_adds_question_when_first_step_has_only_scenario(self):
        started = engines.start({
            "tool": "socratic", "title": "Sandwich Maker",
            "snapshot": {"config": {"prompt": "Which choice should the program handle first?", "learning_steps": [
                {"title": "Choose size", "goal": "Choose a sandwich size.",
                 "scenario": "A customer arrives at the sandwich machine and sees the size menu."},
            ]}, "chunks": []},
        }, {})
        self.assertIn("A customer arrives", started["messages"][0]["content"])
        self.assertTrue(started["messages"][0]["content"].endswith("Which choice should the program handle first?"))

    def test_guided_start_adds_story_and_question_when_step_has_no_scenario(self):
        started = engines.start({
            "tool": "socratic", "title": "Code Review",
            "snapshot": {"config": {"prompt": "You have opened a pull request for review.", "learning_steps": [
                {"title": "Acknowledge the observation", "goal": "Recognize useful peer feedback.",
                 "question": "How would you thank your teammate for noticing the empty-list bug?"},
            ]}, "chunks": []},
        }, {})
        self.assertIn("You have opened a pull request for review.", started["messages"][0]["content"])
        self.assertTrue(started["messages"][0]["content"].endswith("How would you thank your teammate for noticing the empty-list bug?"))

    def test_untouched_story_only_attempt_receives_first_question(self):
        story = "Your teammate notices the function crashes on an empty list."
        question = "How would you respond to your teammate's observation?"
        assignment = {"tool": "socratic", "title": "Code Review", "snapshot": {"config": {
            "prompt": story, "learning_steps": [{"title": "Acknowledge the observation",
                "goal": "Recognize useful feedback.", "scenario": story, "question": question}],
        }, "chunks": []}}
        attempt = {"status": "in_progress", "messages": [{"role": "assistant", "content": story}],
                   "engine_state": {"socratic": {"phase": "teaching", "learning_step_index": 0}}}
        self.assertTrue(engines.repair_legacy_socratic_opening(assignment, attempt))
        self.assertIn(story, attempt["messages"][0]["content"])
        self.assertTrue(attempt["messages"][0]["content"].endswith(question))
        self.assertEqual(attempt["engine_state"]["socratic"]["next_thinking_step"], question)
        self.assertFalse(engines.repair_legacy_socratic_opening(assignment, attempt))
        answered = {"status": "in_progress", "messages": [{"role": "assistant", "content": story},
                    {"role": "user", "content": "I would thank them."}], "engine_state": {"socratic": {}}}
        self.assertFalse(engines.repair_legacy_socratic_opening(assignment, answered))

    def test_basic_mode_uses_professor_question_without_exposing_steps(self):
        config = {"guidance_mode": "basic", "prompt": "What would you try first?", "minimum_messages": 1,
                  "learning_steps": [{"title": "Hidden step", "goal": "This step is not active."}]}
        assignment = {"tool": "socratic", "title": "Sandwich Maker", "status": "published",
                      "config": config, "snapshot": {"config": config, "chunks": []}}
        started = engines.start(assignment, {})
        self.assertEqual(started["messages"][0]["content"], config["prompt"])
        self.assertNotIn("learning_step_index", started["socratic"])
        self.assertEqual(routes.public_assignment(assignment)["student_config"]["learning_steps"], [])
        self.assertIsNone(routes.public_assignment(assignment)["student_config"]["learning_path_time_limit_seconds"])
        self.assertEqual(SocraticConfig.model_validate({"learning_steps": []}).guidance_mode, "basic")
        self.assertEqual(SocraticConfig.model_validate({"learning_steps": [{
            "title": "Choose size", "goal": "Explain the first choice.",
            "evidence_quote": "Choose a sandwich size.", "source_chunk_id": "chunk-1",
        }]}).guidance_mode, "guided")

    def test_guided_mode_requires_steps_before_publish(self):
        assignment = {"tool": "socratic", "course_id": uuid4(),
                      "config": {"guidance_mode": "guided", "document_ids": ["doc-1"], "learning_steps": []}}
        with patch.object(engines.db, "list_rag_files", return_value=[{"document_id": "doc-1"}]):
            with self.assertRaisesRegex(HTTPException, "Generate and review learning steps"):
                engines.publish_snapshot(assignment)

    def test_next_step_waits_for_a_response_then_advances_once(self):
        assignment = {"tool": "socratic", "snapshot": {"config": {"document_ids": ["selected"], "learning_steps": [
            {"title": "Choose a size", "goal": "Explain how you choose a size."},
            {"title": "Check ingredients", "goal": "Explain when to check ingredients.",
             "scenario": "The customer chooses a small sandwich, so the same machine now checks its ingredients.",
             "question": "What should it verify before asking for coins?",
             "source_chunk_id": "ingredient-page", "evidence_quote": "Check ingredients before taking coins."},
        ]}, "chunks": [{"document_id": "selected", "chunk_id": "ingredient-page", "title": "Sandwich.pdf",
                       "page_number": 2, "text": "Check ingredients before taking coins."}]}}
        attempt = {"status": "in_progress", "messages": [{"role": "assistant", "content": "Which size?"}],
                   "engine_state": {"socratic": {"phase": "teaching", "learning_step_index": 0,
                                                   "step_started_at_message_count": 1}}, "processed_requests": []}
        @contextmanager
        def locked(_assignment_id, _student_id):
            yield object(), attempt
        with patch.object(routes.store, "locked_attempt", side_effect=locked), \
             patch.object(routes, "get_assignment", return_value=assignment), \
             patch.object(routes.store, "save_attempt") as save:
            with self.assertRaisesRegex(HTTPException, "Discuss this step"):
                routes.next_socratic_step(uuid4(), {"user_id": "student"})
            attempt["messages"].append({"role": "user", "content": "I would choose small."})
            result = routes.next_socratic_step(uuid4(), {"user_id": "student"})
            self.assertEqual(result["engine_state"]["socratic"]["learning_step_index"], 1)
            self.assertIn("Check ingredients", result["messages"][-1]["content"])
            self.assertIn("same machine now checks", result["messages"][-1]["content"])
            self.assertTrue(result["messages"][-1]["content"].endswith("What should it verify before asking for coins?"))
            self.assertEqual(result["engine_state"]["socratic"]["next_thinking_step"], "What should it verify before asking for coins?")
            self.assertEqual(result["messages"][-1]["step_source"]["page_number"], 2)
            self.assertNotIn("What would you try first?", result["messages"][-1]["content"])
            save.assert_called_once()

    def test_next_step_fallback_does_not_narrate_scenario_continuity(self):
        assignment = {"tool": "socratic", "snapshot": {"config": {"learning_steps": [
            {"title": "Choose a size"},
            {"title": "Check ingredients", "evidence_quote": "Check supplies before accepting payment."},
        ]}}}
        attempt = {"status": "in_progress", "messages": [
            {"role": "assistant", "content": "Which size?"},
            {"role": "user", "content": "Small."},
        ], "engine_state": {"socratic": {"phase": "teaching", "learning_step_index": 0,
                                          "step_started_at_message_count": 1}}, "processed_requests": []}

        @contextmanager
        def locked(_assignment_id, _student_id):
            yield object(), attempt

        with patch.object(routes.store, "locked_attempt", side_effect=locked), \
             patch.object(routes, "get_assignment", return_value=assignment), \
             patch.object(routes.store, "save_attempt"):
            result = routes.next_socratic_step(uuid4(), {"user_id": "student"})

        message = result["messages"][-1]["content"]
        self.assertIn("From the assignment: “Check supplies before accepting payment.”", message)
        self.assertNotIn("Continuing the same assignment example", message)
        self.assertNotIn("Continue the same assignment example", message)
        self.assertTrue(message.endswith("How would you approach check ingredients in this assignment?"))


if __name__ == "__main__":
    unittest.main()
