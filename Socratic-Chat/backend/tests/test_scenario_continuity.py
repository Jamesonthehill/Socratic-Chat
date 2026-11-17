import unittest
import asyncio
import json
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from app import rag
from app.answer_evaluation import AnswerEvaluation, QualitativeFeedback
from app.classifier import MessageClassification, is_contextual_meaning_request
from app.schemas import ChatMessage, Source
from app.socratic import choose_socratic_strategy, conversation_scenario, socratic_system_instruction


SCENARIO = "Imagine you and a friend share a document and want to preserve earlier versions. What would you do?"
SOURCE = Source(document_id="doc", chunk_id="chunk", title="Version control", text="Version control preserves revisions.", score=1)
CLASSIFICATION = MessageClassification( dialogue_status="answering_tutor", target="version control")
EVALUATION = AnswerEvaluation(concept="version control", keyword_coverage=0.7, semantic_alignment=0.8,
    rubric_score=0.8, total_score=80, correctness=3, completeness=3, reasoning=3,
    application=None, supported_concepts=("revision history",), missing_concepts=(),
    critical_misconception=False, misconception=None, feedback="You explained preserved revisions.",
    confidence=0.9, progress_status="developing")


class ScenarioContinuityTests(unittest.TestCase):
    def test_confirmation_request_answers_claim_without_current_step_detour(self):
        reply = json.dumps({
            "lead_in": "Almost: it includes the Product Backlog items selected for this Sprint, not the whole Product Backlog.",
            "next_question": "",
        })
        complete = AsyncMock(return_value=SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=reply))],
        ))
        source = Source(document_id="scrum", chunk_id="backlog", title="Scrum guide",
                        text="The Sprint Backlog includes the Sprint Goal, selected Product Backlog items, and a plan.", score=1)
        with patch("app.rag.generation_client_config", return_value=(
            "Ollama", "ollama", "http://127.0.0.1:11434/v1", "test-model"
        )), patch("app.rag.chat_completion", complete):
            answer = asyncio.run(rag.generate_answer(
                "So the Sprint Backlog includes the Sprint Goal, Product Backlog, and a plan?",
                [ChatMessage(role="assistant", content="How would you adjust the Sprint Goal for mobile signup?")],
                [source], classification=replace(CLASSIFICATION, message_role="confirmation_request"),
                assignment_scope=True,
                active_learning_step={"title": "Adapt the plan", "scenario": "Mobile signup is difficult."},
            ))
        instruction = complete.call_args.args[2]["messages"][1]["content"]
        self.assertIn("verify their own claim", instruction)
        self.assertNotIn("Mobile signup is difficult", instruction)
        self.assertIn("not the whole Product Backlog", answer)

    def test_assignment_tutor_receives_feedback_about_an_off_target_answer(self):
        feedback = QualitativeFeedback(
            concept="Sprint Backlog components",
            supported_concepts=(),
            missing_concepts=("Sprint Goal", "selected Product Backlog items", "delivery plan"),
            critical_misconception=False,
            misconception=None,
            feedback="The student named the three pillars of empiricism instead of Sprint Backlog components.",
        )
        reply = json.dumps({
            "lead_in": "Those are the pillars of empiricism. The Sprint Backlog instead contains a goal, selected work, and a plan.",
            "next_question": "If your team selected two items for this Sprint, what else would its Sprint Backlog need?",
        })
        complete = AsyncMock(return_value=SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=reply))],
        ))
        source = Source(document_id="scrum", chunk_id="backlog", title="Scrum guide",
                        text="The Sprint Backlog contains the Sprint Goal, selected Product Backlog items, and a plan.", score=1)
        with patch("app.rag.generation_client_config", return_value=(
            "Ollama", "ollama", "http://127.0.0.1:11434/v1", "test-model"
        )), patch("app.rag.chat_completion", complete):
            answer = asyncio.run(rag.generate_answer(
                "trasnpracny, adoptation, and inspect",
                [ChatMessage(role="assistant", content="What belongs in a Sprint Backlog?")],
                [source], classification=replace(CLASSIFICATION, message_role="student_answer"),
                evaluation=feedback, assignment_scope=True,
                active_learning_step={"title": "Sprint Backlog", "question": "What belongs in it?"},
            ))
        prompt = complete.call_args.args[2]["messages"][1]["content"]
        self.assertIn("formative_observation", prompt)
        self.assertIn("three pillars of empiricism", prompt)
        self.assertIn("named a related but different concept", prompt)
        self.assertIn("Those are the pillars of empiricism", answer)

    def test_off_target_answer_repairs_generic_clarity_question(self):
        feedback = QualitativeFeedback(
            concept="Sprint Backlog components", supported_concepts=(),
            missing_concepts=("Sprint Goal", "selected items", "delivery plan"),
            critical_misconception=False, misconception=None,
            feedback="You named transparency, inspection, and adaptation, which are empiricism pillars rather than Sprint Backlog parts.",
        )
        first = json.dumps({
            "lead_in": "The Sprint Backlog has a goal, selected work, and a plan.",
            "next_question": "Does that clarify what the Sprint Backlog includes?",
        })
        repaired = json.dumps({
            "lead_in": "You named the three empiricism pillars. The Sprint Backlog instead lists a goal, selected work, and a plan.",
            "next_question": "If your team chose two tasks for a Sprint, what would guide that work?",
        })
        complete = AsyncMock(side_effect=[
            SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])
            for content in (first, repaired)
        ])
        source = Source(document_id="scrum", chunk_id="backlog", title="Scrum guide",
                        text="The Sprint Backlog contains the Sprint Goal, selected Product Backlog items, and a plan.", score=1)
        with patch("app.rag.generation_client_config", return_value=(
            "Ollama", "ollama", "http://127.0.0.1:11434/v1", "test-model"
        )), patch("app.rag.chat_completion", complete):
            answer = asyncio.run(rag.generate_answer(
                "transparency, adaptation, and inspection",
                [ChatMessage(role="assistant", content="What belongs in a Sprint Backlog?")],
                [source], classification=replace(CLASSIFICATION, message_role="student_answer"),
                evaluation=feedback, assignment_scope=True,
            ))
        self.assertEqual(complete.await_count, 2)
        self.assertIn("You named the three empiricism pillars", answer)
        self.assertNotIn("Does that clarify", answer)

    def test_feedback_in_next_question_is_moved_out_of_thinking_box(self):
        turn = rag.one_question_socratic_turn({
            "lead_in": "",
            "next_question": (
                "Maya would refuse the order **because there's not enough bread.**\n\n"
                "**How would the machine respond to the customer?**"
            ),
        })
        self.assertEqual(turn["lead_in"], "Maya would refuse the order **because there's not enough bread.**")
        self.assertEqual(turn["next_question"], "**How would the machine respond to the customer?**")

    def test_tutor_can_explain_its_own_scenario_actor_without_a_document_match(self):
        published_scenario = (
            'A customer types "small" into the kiosk. The kitchen’s manager, Maya, '
            'wonders if the order can be fulfilled. What would Maya do with only 1 slice of bread?'
        )
        self.assertTrue(is_contextual_meaning_request(
            "who is maya?", [ChatMessage(role="assistant", content=published_scenario)],
            published_scenario,
        ))
        history = [ChatMessage(role="assistant", content=(
            "The machine checks inventory before asking for payment. "
            "What would Maya do if only 1 slice of bread were left?"
        ))]
        self.assertTrue(is_contextual_meaning_request("Maya is customer or developer?", history))
        self.assertTrue(is_contextual_meaning_request("who is maya?", history))
        self.assertFalse(is_contextual_meaning_request("Maya is customer or developer?", []))
        self.assertFalse(is_contextual_meaning_request("What is the machine's price?", history))
        later_history = history + [ChatMessage(role="user", content="I see.")] * 9
        self.assertFalse(is_contextual_meaning_request("Maya is customer or developer?", later_history))
        self.assertTrue(is_contextual_meaning_request(
            "Maya is customer or developer?", later_history, history[0].content,
        ))

        model_reply = json.dumps({
            "lead_in": "I hadn't said who Maya was. I meant the customer in that example.",
            "next_question": "",
        })
        response = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=model_reply))])
        create = AsyncMock(return_value=response)
        client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
        with patch("app.rag.generation_client_config", return_value=(
            "Ollama", "ollama", "http://127.0.0.1:11434/v1", "test-model"
        )), patch("openai.AsyncOpenAI", return_value=client):
            answer = asyncio.run(rag.generate_answer(
                "Maya is customer or developer?", later_history, [], assignment_scope=True,
                active_learning_step={"scenario": history[0].content},
            ))
        self.assertIn("I hadn't said who Maya was", answer)
        self.assertIn("If you never established the person's role", create.call_args.kwargs["messages"][0]["content"])

    def test_quoted_refund_message_is_not_split_into_thinking_step(self):
        model_reply = json.dumps({
            "lead_in": "The required message is '**Sorry, that**'s not enough money.",
            "next_question": "Money refunded.' Does your answer match that exact text from the requirements?",
        })
        response = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=model_reply))])
        create = AsyncMock(return_value=response)
        client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
        with patch("app.rag.generation_client_config", return_value=(
            "openai", "test-key", "https://api.openai.com/v1", "test-model"
        )), patch("openai.AsyncOpenAI", return_value=client):
            answer = asyncio.run(rag.generate_answer(
                "The inserted money must be refunded", [], [SOURCE], assignment_scope=True,
            ))
        self.assertEqual(answer.replace("**", ""), "The required message is 'Sorry, that's not enough money. Money refunded.'")
        self.assertIn("never split a quote across the fields", create.call_args.kwargs["messages"][3]["content"])

    def test_exact_text_confirmation_is_removed_without_affecting_application_question(self):
        self.assertTrue(rag.confirms_answer_just_supplied(
            "Does your answer match that exact text from the requirements?"
        ))
        self.assertFalse(rag.confirms_answer_just_supplied(
            "If the customer pays too little, what should the machine do with the coins?"
        ))

    def test_tutor_emphasis_selects_reason_and_core_question(self):
        self.assertEqual(rag.ensure_tutor_emphasis(
            "The order cannot continue. The machine has no bread.", "The machine has no bread."
        ), "The order cannot continue. **The machine has no bread.**")
        self.assertEqual(rag.ensure_tutor_emphasis(
            "The order cannot continue. **The machine has no bread.**"
        ), "The order cannot continue. **The machine has no bread.**")
        self.assertEqual(rag.ensure_tutor_emphasis(
            "Before asking for money, what should the machine check?", purpose="question"
        ), "Before asking for money, **what should the machine check?**")
        self.assertEqual(rag.ensure_tutor_emphasis(
            "The machine stops because it lacks bread."
        ), "The machine stops **because it lacks bread.**")
        self.assertEqual(rag.ensure_tutor_emphasis(
            "Since you have the bill, what message should appear?", "Since you have the bill", purpose="question"
        ), "Since you have the bill, **what message should appear?**")

    def test_tutor_uses_model_selected_clauses_in_both_reply_parts(self):
        model_reply = json.dumps({
            "lead_in": "There is no bread. The order must stop before payment.",
            "next_question": "Before taking money, what should the machine check?",
            "lead_emphasis": "The order must stop before payment.",
            "question_emphasis": "what should the machine check?",
        })
        complete = AsyncMock(return_value=SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=model_reply))],
        ))
        with patch("app.rag.generation_client_config", return_value=(
            "Ollama", "ollama", "http://127.0.0.1:11434/v1", "test-model"
        )), patch("app.rag.chat_completion", complete):
            answer = asyncio.run(rag.generate_answer("The customer paid", [], [SOURCE], assignment_scope=True))
        self.assertEqual(answer, "There is no bread. **The order must stop before payment.**\n\n"
                         "Before taking money, **what should the machine check?**")
        required = complete.call_args.args[2]["response_format"]["json_schema"]["schema"]["required"]
        self.assertIn("lead_emphasis", required)
        self.assertIn("question_emphasis", required)

    def test_guided_answer_without_question_or_quiz_invitation_is_repaired(self):
        first = json.dumps({
            "lead_in": "Saving the revision preserves an earlier version for the team.",
            "next_question": "", "lead_emphasis": "", "question_emphasis": "",
        })
        repaired = json.dumps({
            "lead_in": "Saving the revision preserves an earlier version for the team.",
            "next_question": "If a teammate changes it tomorrow, how could you compare the versions?",
            "lead_emphasis": "preserves an earlier version", "question_emphasis": "how could you compare the versions?",
        })
        complete = AsyncMock(side_effect=[
            SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=first))]),
            SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=repaired))]),
        ])
        with patch("app.rag.generation_client_config", return_value=(
            "Ollama", "ollama", "http://127.0.0.1:11434/v1", "test-model"
        )), patch("app.rag.chat_completion", complete):
            answer = asyncio.run(rag.generate_answer(
                "I would save the previous version", [ChatMessage(role="assistant", content="How could the team preserve an earlier version?")],
                [SOURCE], assignment_scope=True,
                active_learning_step={"title": "Version history", "goal": "Compare revisions"},
                classification=MessageClassification(message_role="student_answer", conversation_action="continue"),
            ))
        self.assertEqual(complete.await_count, 2)
        self.assertIn("how could you compare the versions?", answer)

    def test_assignment_tutor_does_not_rewrite_a_similar_follow_up(self):
        question = (
            "Based on the example where a user inserted $3.00 for a $1.75 sandwich, "
            "what exact text should the machine display to show the correct change?"
        )
        history = [ChatMessage(role="assistant", content=(
            "**Your next thinking step**\n" + question
        ))]
        model_reply = json.dumps({
            "lead_in": "The change is $1.25. The required message is 'Here is $1.25 in change'.",
            "next_question": question,
        })
        response = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=model_reply))])
        create = AsyncMock(return_value=response)
        client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
        with patch("app.rag.generation_client_config", return_value=(
            "openai", "test-key", "https://api.openai.com/v1", "test-model"
        )), patch("openai.AsyncOpenAI", return_value=client):
            answer = asyncio.run(rag.generate_answer(
                "1.25$ refunded", history, [SOURCE], assignment_scope=True,
            ))
        self.assertEqual(create.await_count, 1)
        self.assertIn(question, answer.replace("**", ""))
        self.assertIn("acknowledge the correct substance", create.call_args_list[0].kwargs["messages"][1]["content"])

    def test_numbered_follow_ups_are_reduced_to_one_question(self):
        turn = {
            "lead_in": (
                "In your registration project, think about priorities and teamwork.\n\n"
                "1. Who chooses what gets built first?\n"
                "2. Who helps the team work through obstacles?\n"
                "3. Who builds and tests the feature?"
            ),
            "next_question": "",
        }
        result = rag.one_question_socratic_turn(turn)
        self.assertEqual(result["lead_in"], "In your registration project, think about priorities and teamwork.")
        self.assertEqual(result["next_question"], "Who chooses what gets built first?")

    def test_inline_follow_up_does_not_include_its_answer_or_second_question(self):
        turn = {
            "lead_in": (
                "The Product Owner orders the backlog. "
                "In this example, who decides whether students need search or event details? "
                "That is the Product Owner. Who builds the registration feature? Those are the Developers."
            ),
            "next_question": "",
        }
        result = rag.one_question_socratic_turn(turn)
        self.assertEqual(result["lead_in"], "The Product Owner orders the backlog.")
        self.assertEqual(result["next_question"],
                         "In this example, who decides whether students need search or event details?")

    def test_subtopic_explanation_checks_clarity_then_confirmation_resumes_application(self):
        explanation = json.dumps({
            "lead_in": "A backlog is the team's ordered list of work. In this example, fixing signup is one item.",
            "next_question": "Does that example clarify what a backlog item is, or which part is still unclear?",
        })
        confirmation_draft = json.dumps({"lead_in": "Glad that helped.", "next_question": ""})
        resumed = json.dumps({
            "lead_in": "Glad that helped.",
            "next_question": "If students struggle with signup, where would you place that work in the team's list?",
        })
        responses = [
            SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])
            for content in (explanation, confirmation_draft, resumed)
        ]
        create = AsyncMock(side_effect=responses)
        client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
        step = {"title": "Plan the work", "goal": "Prioritize the backlog",
                "scenario": "Students find the signup form confusing.", "question": "What should the team do first?"}
        source = Source(document_id="scrum", chunk_id="backlog", title="Scrum guide",
                        text="The Product Backlog is an ordered list of work for the product. "
                             "For example, the campus registration team may prioritize fixing signup.", score=1)
        with patch("app.rag.generation_client_config", return_value=(
            "Ollama", "ollama", "http://127.0.0.1:11434/v1", "test-model"
        )), patch("openai.AsyncOpenAI", return_value=client):
            first = asyncio.run(rag.generate_answer(
                "What is a backlog item?", [], [source], assignment_scope=True, active_learning_step=step,
            ))
            second = asyncio.run(rag.generate_answer(
                "Yes, that helps.", [ChatMessage(role="assistant", content=first)], [source],
                classification=replace(CLASSIFICATION, message_role="understanding_claim",
                                       conversation_action="verify_understanding"),
                assignment_scope=True, active_learning_step=step,
            ))
        self.assertIn("Does that example clarify", first)
        self.assertIn("where would you place", second)
        self.assertEqual(create.await_count, 3)
        self.assertIn("ask one short, specific confirmation question", create.call_args_list[0].kwargs["messages"][1]["content"])
        self.assertIn("Ground explanations and new questions in the retrieved passages", create.call_args_list[0].kwargs["messages"][1]["content"])
        self.assertIn("This is not evidence of mastery", create.call_args_list[2].kwargs["messages"][-1]["content"])

    def test_assignment_tutor_uses_brief_conversational_style_without_losing_explanation_option(self):
        model_reply = json.dumps({"lead_in": "That makes sense.", "next_question": "What would you tell the team about the slowdown?"})
        response = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=model_reply))])
        create = AsyncMock(return_value=response)
        client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
        with patch("app.rag.generation_client_config", return_value=(
            "openai", "test-key", "https://api.openai.com/v1", "test-model"
        )), patch("openai.AsyncOpenAI", return_value=client):
            answer = asyncio.run(rag.generate_answer(
                "We should tell the team about the slowdown.", [], [SOURCE],
                assignment_scope=True,
                active_learning_step={"title": "Apply Scrum values", "scenario": "The location filter is slow."},
            ))
        instruction = create.call_args.kwargs["messages"][1]["content"]
        self.assertIn("friendly, informal tone without slang", instruction)
        self.assertIn("Sound like a helpful classmate", instruction)
        self.assertIn("not a textbook defining terms", instruction)
        self.assertIn("Start with the student's situation in everyday words", instruction)
        self.assertIn("answer that exact request in plain language first", instruction)
        self.assertIn("explain what the retrieved document says", instruction)
        self.assertIn("Use the document's own example if it has one", instruction)
        self.assertIn("If the student explicitly asks for a different example or the recent exchange shows they remain stuck", instruction)
        self.assertIn("Never end with a generic comprehension check", instruction)
        self.assertIn("two or three short sentences", instruction)
        self.assertIn("one meaningful sentence or clause in the tutor explanation", instruction)
        self.assertIn("one meaningful sentence or clause in the next thinking question", instruction)
        self.assertIn("document's own example when it applies", instruction)
        self.assertIn("a reply that is too much to read", instruction)
        self.assertIn("current example is hard to picture", instruction)
        self.assertIn("first give a short explanation or hint using the current example", instruction)
        self.assertIn("If that explanation has already failed", instruction)
        self.assertIn("Explicitly label it hypothetical and connect it", instruction)
        self.assertIn("give the missing idea or answer in one or two plain sentences", instruction)
        self.assertIn("unexplained specialist term", instruction)
        self.assertIn("Do not introduce another cast of characters", instruction)
        self.assertIn("do not add another scenario just to extend the exchange", instruction)
        self.assertIn("use enough words to answer clearly", instruction)
        self.assertEqual(create.call_args.kwargs["response_format"]["json_schema"]["name"], "socratic_turn")
        self.assertEqual(answer.replace("**", ""), "That makes sense.\n\nWhat would you tell the team about the slowdown?")

    def test_assignment_tutor_allows_question_without_lead_in(self):
        model_reply = json.dumps({"lead_in": "", "next_question": "What would you try first?"})
        complete = AsyncMock(return_value=SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=model_reply))],
        ))
        with patch("app.rag.generation_client_config", return_value=(
            "Ollama", "ollama", "http://127.0.0.1:11434/v1", "test-model"
        )), patch("app.rag.chat_completion", complete):
            answer = asyncio.run(rag.generate_answer(
                "Let's start.", [], [SOURCE], assignment_scope=True,
            ))
        schema = complete.call_args.args[2]["response_format"]["json_schema"]["schema"]
        self.assertEqual(schema["properties"]["lead_in"], {"type": "string"})
        self.assertEqual(answer.replace("**", ""), "What would you try first?")

    def test_requested_different_analogy_overrides_current_example(self):
        model_reply = json.dumps({"lead_in": "Think of a bakery choosing what to bake next.", "next_question": ""})
        response = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=model_reply))])
        create = AsyncMock(return_value=response)
        client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
        with patch("app.rag.generation_client_config", return_value=(
            "openai", "test-key", "https://api.openai.com/v1", "test-model"
        )), patch("openai.AsyncOpenAI", return_value=client):
            asyncio.run(rag.generate_answer(
                "Please give me a different, simple hypothetical example", [], [SOURCE],
                assignment_scope=True,
                active_learning_step={"title": "Scrum artifacts", "scenario": "The campus team plans registration."},
            ))
        instruction = create.call_args.kwargs["messages"][1]["content"]
        self.assertIn("overrides the usual preference to stay with the current example", instruction)
        self.assertIn("different everyday setting", instruction)

    def test_repeated_confusion_can_use_hypothetical_after_grounded_help(self):
        model_reply = json.dumps({
            "lead_in": "Hypothetically, suppose a bakery changes today's plan when an oven breaks. A Sprint Backlog is also a plan the team can adjust.",
            "next_question": "What would your Scrum team update if its planned work changed?",
        })
        complete = AsyncMock(return_value=SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=model_reply))],
        ))
        history = [
            ChatMessage(role="assistant", content="What belongs in the Sprint Backlog?"),
            ChatMessage(role="user", content="I don't know."),
            ChatMessage(role="assistant", content="It includes the Sprint Goal, selected items, and a plan."),
        ]
        with patch("app.rag.generation_client_config", return_value=(
            "Ollama", "ollama", "http://127.0.0.1:11434/v1", "test-model"
        )), patch("app.rag.chat_completion", complete):
            answer = asyncio.run(rag.generate_answer(
                "I still don't get it.", history, [SOURCE],
                replace(CLASSIFICATION, message_role="support_request"),
                assignment_scope=True,
                active_learning_step={"title": "Sprint Backlog", "question": "What belongs in it?"},
            ))
        messages = complete.call_args.args[2]["messages"]
        self.assertIn("I don't know.", str(messages))
        self.assertIn("recent exchange shows they remain stuck", messages[1]["content"])
        self.assertIn("clearly hypothetical", messages[1]["content"])
        self.assertIn("bakery", answer)

    def test_assignment_support_reply_keeps_subtopic_without_rewriting(self):
        first = json.dumps({
            "lead_in": "Scrum’s empirical pillars are transparency, inspection, and adaptation. " * 7 + "",
            "next_question": "How could the team adapt after finding a problem?",
        })
        complete = AsyncMock(return_value=SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=first))],
        ))
        with patch("app.rag.generation_client_config", return_value=(
            "Ollama", "ollama", "http://127.0.0.1:11434/v1", "test-model"
        )), patch("app.rag.chat_completion", complete):
            answer = asyncio.run(rag.generate_answer(
                "I don’t know what Scrum’s empirical pillars are.",
                [ChatMessage(role="assistant", content="Who orders the Product Backlog?")],
                [SOURCE], replace(CLASSIFICATION, message_role="support_request"),
                assignment_scope=True,
                learning_detour={"question": "Who orders the Product Backlog?"},
            ))
        self.assertIn("transparency, inspection, and adaptation", answer)
        self.assertIn("How could the team adapt", answer)
        self.assertEqual(complete.await_count, 1)

    def test_assignment_support_keeps_one_model_written_application_question(self):
        reply = json.dumps({
            "lead_in": "The Product Owner orders the backlog according to value.",
            "next_question": "What student need would help them choose between search and event details?",
        })
        complete = AsyncMock(return_value=SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=reply))],
        ))
        with patch("app.rag.generation_client_config", return_value=(
            "Ollama", "ollama", "http://127.0.0.1:11434/v1", "test-model"
        )), patch("app.rag.chat_completion", complete):
            answer = asyncio.run(rag.generate_answer(
                "Please explain this more simply.",
                [ChatMessage(role="assistant", content="Who orders the Product Backlog?")],
                [SOURCE], replace(CLASSIFICATION, message_role="support_request"),
                assignment_scope=True,
                active_learning_step={"title": "Scrum roles", "question": "Who orders the Product Backlog?"},
            ))
        self.assertIn("What student need would help them choose", answer)
        self.assertEqual(complete.await_count, 1)

    def test_support_rephrased_who_question_is_repaired(self):
        history = [ChatMessage(role="assistant", content="Who orders the Product Backlog?")]
        self.assertTrue(rag.repeats_identity_question("In a kitchen, who chooses what to cook first?", history))
        self.assertFalse(rag.repeats_identity_question("What would guide the order of the work?", history))

    def test_contextual_wording_request_keeps_previous_tutor_question_in_prompt(self):
        previous = (
            "Alex explains his payment bug fix to Sam without changing his original approach. "
            "How can he make the logic clear?"
        )
        history = [ChatMessage(role="assistant", content=previous)]
        model_reply = "His original approach means Alex's existing method for fixing the payment bug."
        response = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=model_reply))])
        create = AsyncMock(return_value=response)
        client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
        with patch("app.rag.generation_client_config", return_value=(
            "Ollama", "ollama", "http://127.0.0.1:11434/v1", "test-model"
        )), patch("openai.AsyncOpenAI", return_value=client):
            answer = asyncio.run(rag.generate_answer(
                'what is the "his original approach meaning" in the context', history, [],
            ))
        messages = create.call_args.kwargs["messages"]
        self.assertIn({"role": "assistant", "content": previous}, messages)
        self.assertIn("Resolve references from the conversation", messages[0]["content"])
        self.assertIn("documented spelling", messages[0]["content"])
        self.assertIn("Do not redirect a terminology question", messages[0]["content"])
        self.assertEqual(answer, model_reply)

    def test_verified_term_resolution_is_included_in_generation_prompt(self):
        history = [
            ChatMessage(role="assistant", content="Ask the reviewer to PTAL after the update."),
            ChatMessage(role="assistant", content="Would you use PATL here?"),
        ]
        response = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(
            content="I think you mean PTAL: please take another look."
        ))])
        create = AsyncMock(return_value=response)
        client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
        with patch("app.rag.generation_client_config", return_value=(
            "Ollama", "ollama", "http://127.0.0.1:11434/v1", "test-model"
        )), patch("openai.AsyncOpenAI", return_value=client):
            answer = asyncio.run(rag.generate_answer(
                "I don't know what the PATL is", history, [SOURCE],
                term_resolution=("PATL", "PTAL"),
            ))
        messages = create.call_args.kwargs["messages"]
        self.assertIn("learner wrote 'PATL'", messages[1]["content"])
        self.assertIn("published material uses 'PTAL'", messages[1]["content"])
        self.assertEqual(answer, "I think you mean PTAL: please take another look.")

    def test_generation_receives_old_example_plus_recent_exchange(self):
        history = [ChatMessage(role="assistant", content=SCENARIO)]
        history += [ChatMessage(role="user", content="Save a revision."), ChatMessage(role="assistant", content="Why preserve it?")] * 8
        model_reply = "You identified the value of saving a revision.\n\nWhy would saving that revision help you and your friend with the shared document?"
        response = SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content=json.dumps({
                        "lead_in": "You identified the value of saving a revision.",
                        "next_question": "Why would saving that revision help you and your friend with the shared document?",
                    }))
                )
            ]
        )
        create = AsyncMock(return_value=response)
        client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
        with patch("app.rag.generation_client_config", return_value=("openai", "test-key", "https://api.openai.com/v1", "test-model")), patch("openai.AsyncOpenAI", return_value=client):
            answer = asyncio.run(rag.generate_answer(
                "We can restore earlier work.", history, [SOURCE], CLASSIFICATION, EVALUATION,
                learning_topic="What is version control?",
            ))
        messages = create.call_args.kwargs["messages"]
        self.assertIn("Imagine you and a friend share a document and want to preserve earlier versions.", messages[1]["content"])
        self.assertNotIn("What would you do", messages[1]["content"])
        self.assertNotIn("What would you do?</scenario>", messages[1]["content"])
        self.assertIn("do not repeat or paraphrase", messages[1]["content"])
        self.assertIn("<learning_topic>What is version control?</learning_topic>", messages[1]["content"])
        self.assertIn("primary teaching objective", messages[1]["content"])
        self.assertIn("Do not keep quizzing the student on the detail's inner workings", messages[1]["content"])
        self.assertIn("Earlier tutor-generated examples are conversation context, not course evidence", messages[0]["content"])
        self.assertNotIn("Why preserve it?", str(messages))
        self.assertEqual(sum(item["role"] == "assistant" for item in messages), 0)
        self.assertEqual(create.call_args.kwargs["response_format"]["json_schema"]["name"], "socratic_turn")
        self.assertEqual(answer.replace("**", ""), model_reply)

    def test_complete_answer_advances_josh_scenario_without_old_question_in_prompt(self):
        prior_question = "How does this allow Josh to recover from a mistake without tracking versions?"
        history = [
            ChatMessage(role="assistant", content=f"Imagine Josh working on a project. {prior_question}"),
            ChatMessage(role="user", content="Josh can restore an earlier project state."),
            ChatMessage(role="assistant", content=prior_question),
        ]
        evaluation = replace(
            EVALUATION, total_score=79.17, correctness=4, completeness=3, reasoning=3,
            missing_concepts=(), progress_status="developing",
        )
        response = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(
            content=json.dumps({"lead_in": "", "next_question": "What should Josh decide before restoring an older project state?"})
        ))])
        create = AsyncMock(return_value=response)
        client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
        with patch("app.rag.generation_client_config", return_value=(
            "Ollama", "ollama", "http://127.0.0.1:11434/v1", "test-model"
        )), patch("openai.AsyncOpenAI", return_value=client):
            asyncio.run(rag.generate_answer(
                "Josh can restore an earlier project state without tracking versions.",
                history, [SOURCE], CLASSIFICATION, evaluation,
            ))
        messages = create.call_args.kwargs["messages"]
        self.assertNotIn(prior_question.rstrip("?"), str(messages))
        self.assertIn("next grounded decision", messages[1]["content"])
        self.assertNotIn("Convert the most important missing concept", messages[1]["content"])

    def test_repeated_difficulty_requires_model_generated_follow_up_field(self):
        history = [ChatMessage(
            role="assistant",
            content="Imagine Alex submits a payment fix to Sam for review. What should Sam check?",
        )]
        evaluation = replace(EVALUATION, total_score=40.5, understanding_improved=False)
        model_reply = json.dumps({
            "lead_in": "Sam can read Alex's change and check whether it follows the team's style.",
            "next_question": "What should Sam check next to decide whether the payment fix is safe?",
        })
        response = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=model_reply))])
        create = AsyncMock(return_value=response)
        client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
        with patch("app.rag.generation_client_config", return_value=(
            "Ollama", "ollama", "http://127.0.0.1:11434/v1", "test-model"
        )), patch("openai.AsyncOpenAI", return_value=client):
            answer = asyncio.run(rag.generate_answer(
                "Code review keeps the team's style consistent.", history, [SOURCE], CLASSIFICATION,
                evaluation, learning_topic="What is code review?", stable_concept="code review",
            ))
        request = create.call_args.kwargs
        self.assertIn("Strategy: feedback_then_question", request["messages"][1]["content"])
        self.assertIn("Target concept: code review", request["messages"][1]["content"])
        self.assertEqual(request["response_format"]["json_schema"]["schema"]["required"], [
            "lead_in", "next_question", "lead_emphasis", "question_emphasis",
        ])
        self.assertTrue(answer.replace("**", "").endswith("What should Sam check next to decide whether the payment fix is safe?"))

    def test_support_request_keeps_only_latest_unresolved_tutor_question(self):
        old_question = "Why does code consistency matter later?"
        unresolved_question = "What is the primary goal of reviewing Alex's patch?"
        history = [
            ChatMessage(role="assistant", content=old_question),
            ChatMessage(role="user", content="It helps other engineers read the code."),
            ChatMessage(role="assistant", content=unresolved_question),
        ]
        classification = replace(
            CLASSIFICATION,
            message_role="support_request",
            dialogue_status="requesting_support",
            has_substantive_claim=False,
        )
        model_reply = json.dumps({
            "lead_in": "A reviewer checks whether Alex's patch is healthy for the codebase.",
            "next_question": "Should the reviewer focus on protecting code health or preparing a presentation?",
        })
        response = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=model_reply))])
        create = AsyncMock(return_value=response)
        client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))

        with patch("app.rag.generation_client_config", return_value=(
            "Ollama", "ollama", "http://127.0.0.1:11434/v1", "test-model"
        )), patch("openai.AsyncOpenAI", return_value=client):
            asyncio.run(rag.generate_answer(
                "I'm not sure.", history, [SOURCE], classification,
                learning_topic="What is code review?", stable_concept="code review",
            ))

        messages = create.call_args.kwargs["messages"]
        self.assertIn({"role": "assistant", "content": unresolved_question}, messages)
        self.assertNotIn(old_question, str(messages))
        self.assertIn("exact support request", messages[1]["content"])
        self.assertIn("relevance concern", messages[1]["content"])
        self.assertIn("do not automatically retry", messages[1]["content"])

    def test_student_stuck_after_answer_was_given_can_receive_explanation_without_repeat(self):
        history = [ChatMessage(role="assistant", content=(
            "If bread is missing, show 'Sorry there is not enough bread.' "
            "What exact phrase should appear on the screen?"
        ))]
        classification = replace(CLASSIFICATION, message_role="support_request",
                                 dialogue_status="requesting_support", has_substantive_claim=False)
        model_reply = json.dumps({
            "lead_in": "The screen should say 'Sorry there is not enough bread.' The machine cannot make that order.",
            "next_question": "",
        })
        response = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=model_reply))])
        create = AsyncMock(return_value=response)
        client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
        with patch("app.rag.generation_client_config", return_value=(
            "Ollama", "ollama", "http://127.0.0.1:11434/v1", "test-model"
        )), patch("openai.AsyncOpenAI", return_value=client):
            answer = asyncio.run(rag.generate_answer("I don't know", history, [SOURCE], classification))
        self.assertEqual(answer.replace("**", ""), json.loads(model_reply)["lead_in"])
        prompt = create.call_args.kwargs["messages"]
        self.assertIn("a response with no new question is valid", prompt[1]["content"])
        self.assertIn("use an empty string", prompt[3]["content"])

    def test_similar_support_question_does_not_trigger_a_repair_call(self):
        previous = "If you chose small with one slice of bread, what exact phrase should appear on the screen?"
        history = [ChatMessage(role="assistant", content=previous)]
        classification = replace(CLASSIFICATION, message_role="support_request",
                                 dialogue_status="requesting_support", has_substantive_claim=False)
        model_reply = json.dumps({"lead_in": "Let's try again.", "next_question": previous})
        create = AsyncMock(return_value=SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=model_reply))]
        ))
        client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
        with patch("app.rag.generation_client_config", return_value=(
            "Ollama", "ollama", "http://127.0.0.1:11434/v1", "test-model"
        )), patch("openai.AsyncOpenAI", return_value=client):
            answer = asyncio.run(rag.generate_answer("I don't know", history, [SOURCE], classification))
        self.assertEqual(create.await_count, 1)
        self.assertIn(previous, answer.replace("**", ""))

    def test_original_example_survives_beyond_eight_messages(self):
        history = [ChatMessage(role="assistant", content=SCENARIO)]
        history += [ChatMessage(role="user", content="Save a revision."), ChatMessage(role="assistant", content="Why preserve it?")] * 8
        decision = choose_socratic_strategy("We can restore earlier work.", history, [SOURCE], CLASSIFICATION, EVALUATION)
        self.assertEqual(decision.scenario_anchor, SCENARIO)
        self.assertIn("Imagine you and a friend share a document and want to preserve earlier versions.", socratic_system_instruction(decision))
        self.assertNotIn("What would you do", socratic_system_instruction(decision))
        self.assertNotIn("What would you do?</scenario>", socratic_system_instruction(decision))
        self.assertEqual(decision.strategy, "feedback_then_question")

    def test_difficulty_simplifies_existing_example(self):
        decision = choose_socratic_strategy(
            "I am stuck.", [ChatMessage(role="assistant", content=SCENARIO)], [SOURCE],
            replace(CLASSIFICATION, message_role="support_request", dialogue_status="requesting_support"),
        )
        self.assertEqual(decision.example_type, "simplified_current_example")
        self.assertEqual(decision.scenario_anchor, SCENARIO)
        self.assertIn("same people", decision.instruction)

    def test_explicit_uncertainty_overrides_incorrect_new_concept_classification(self):
        misclassified = replace(
            CLASSIFICATION,
            target="version control",
        )
        decision = choose_socratic_strategy(
            "I don't know why we have to do this in software engineering",
            [ChatMessage(role="assistant", content=SCENARIO)],
            [SOURCE],
            misclassified,
        )

        self.assertEqual(decision.student_state, "support_requested")
        self.assertEqual(decision.strategy, "respond_to_support")
        self.assertEqual(decision.scenario_anchor, SCENARIO)


    def test_evidence_drives_moves(self):
        cases = [(replace(EVALUATION, correctness=0), "feedback_then_question"),
                 (replace(EVALUATION, critical_misconception=True), "guided_comparison"),
                 (replace(EVALUATION, missing_concepts=("restoration",)), "feedback_then_question"),
                 (EVALUATION, "feedback_then_question")]
        for evaluation, expected in cases:
            with self.subTest(expected=expected):
                decision = choose_socratic_strategy("My answer", [], [SOURCE], CLASSIFICATION, evaluation)
                self.assertEqual(decision.strategy, expected)

    def test_critical_misconception_targets_first_missing_concept(self):
        evaluation = replace(
            EVALUATION,
            correctness=1,
            critical_misconception=True,
            missing_concepts=("creating a snapshot", "mailing the change to reviewers"),
            feedback="Create a patch and description, then mail it to reviewers.",
            progress_status="mastered",
        )

        decision = choose_socratic_strategy(
            "I could schedule a meeting and practice a presentation.",
            [ChatMessage(role="assistant", content=SCENARIO)],
            [SOURCE], CLASSIFICATION, evaluation,
        )

        self.assertEqual(decision.strategy, "guided_comparison")
        self.assertIn("creating a snapshot", decision.instruction)
        self.assertIn("Do not ask about another dimension", decision.instruction)

    def test_evaluation_overrides_a_provisional_misconception_label(self):
        classified = replace(CLASSIFICATION)
        decision = choose_socratic_strategy(
            "A merge conflict can happen when changes cannot be combined automatically.",
            [ChatMessage(role="assistant", content="What happens when both teammates edit the same file?")],
            [SOURCE], classified, EVALUATION,
        )
        self.assertEqual(decision.strategy, "feedback_then_question")






    def test_plain_good_answer_cannot_be_forced_into_grounded_claim_explanation(self):
        software_scenario = (
            "Imagine two developers edit the same file in a shared project, and neither wants to overwrite the "
            "other's work. What problem should they solve before combining their changes?"
        )
        misclassified = replace(
            CLASSIFICATION,
            conversation_action="verify_claim",
            has_substantive_claim=True,
            target="version control",
        )
        decision = choose_socratic_strategy(
            "It reduces code conflicts in a team.",
            [ChatMessage(role="assistant", content=software_scenario)],
            [SOURCE],
            misclassified,
            replace(EVALUATION, correctness=3, missing_concepts=()),
        )
        self.assertEqual(decision.strategy, "feedback_then_question")



    def test_explicit_example_change_resets_anchor(self):
        history = [ChatMessage(role="assistant", content=SCENARIO)]
        decision = choose_socratic_strategy("Use a different example.", history, [SOURCE], CLASSIFICATION)
        self.assertIsNone(decision.scenario_anchor)
        history += [ChatMessage(role="user", content="Use a different example."),
                    ChatMessage(role="assistant", content="Suppose your team tests a login feature. Where would you work?")]
        self.assertIn("login feature", conversation_scenario(history))

    def test_topic_change_classification_does_not_reset_scenario(self):
        classification = replace(
            CLASSIFICATION,
            target_concepts=("code review",), target="code review",
        )
        decision = choose_socratic_strategy(
            "what is the code review/",
            [ChatMessage(role="assistant", content=SCENARIO)],
            [SOURCE], classification,
        )
        self.assertEqual(decision.strategy, "adaptive_diagnostic")
        self.assertEqual(decision.scenario_anchor, SCENARIO)

    def test_turn_targets_cannot_replace_the_teaching_concept(self):
        classification = replace(
            CLASSIFICATION, target_concepts=("maintainability", "naming conventions"),
            target="maintainability",
        )
        decision = choose_socratic_strategy(
            "Sam can understand Alex's change.",
            [ChatMessage(role="assistant", content="What should Sam examine in Alex's change?")],
            [SOURCE], classification, stable_concept="code review",
        )
        self.assertEqual(decision.target_concept, "code review")
        self.assertIn("Target concept: code review", socratic_system_instruction(decision))

    def test_high_score_does_not_change_the_original_example(self):
        decision = choose_socratic_strategy("I can explain it.", [ChatMessage(role="assistant", content=SCENARIO)], [SOURCE], CLASSIFICATION,
            replace(EVALUATION, progress_status="mastered"))
        self.assertEqual(decision.scenario_anchor, SCENARIO)
        self.assertNotEqual(decision.strategy, "mastery_verification")
