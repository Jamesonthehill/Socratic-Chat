"""Local, provider-free checks for assignment-wide Socratic tutoring."""
import asyncio
from uuid import uuid4

import pytest
from fastapi import HTTPException
from app.schemas import ChatMessage, Source
from app.answer_evaluation import QualitativeFeedback
from app.classifier import MessageClassification, _classification_from_observation
from app.socratic import choose_socratic_strategy
from platform_app import engines, shared_rag


def _chunk(document_id, title, text, section):
    return {
        "document_id": document_id, "chunk_id": str(uuid4()),
        "title": title, "text": text, "metadata": {"section_path": [section]},
        "embedding": [1.0, 0.0],
    }


def test_legacy_keyword_scope_no_longer_rejects_a_supported_subtopic(monkeypatch):
    pdf = _chunk("pdf", "Sandwich.pdf", "The machine checks resources, then requests coins.", "Payment")
    assignment = {
        "id": uuid4(), "tool": "socratic", "title": "Sandwich Maker",
        "snapshot": {
            "config": {"scope_mode": "keywords"},
            "approved_keywords": ["bread"], "chunks": [pdf],
        },
    }
    attempt = {
        "id": uuid4(), "messages": [],
        "engine_state": {"socratic": {"objective_keywords": ["bread"], "learning_topic": "bread"}},
    }
    observed = {}

    async def classify(message, _history, **kwargs):
        observed["classifier_options"] = kwargs
        return _classification_from_observation(
            message_role="learning_question", concepts=("payment",), rewritten_query=message,
        )

    async def answer(_message, _history, _sources, **kwargs):
        observed["generation_options"] = kwargs
        return "The machine asks for coins after checking resources. Why is that order useful?"

    async def no_resolution(*_args, **_kwargs):
        return None

    monkeypatch.setattr(engines, "classify_message", classify)
    monkeypatch.setattr(engines, "resolve_term", no_resolution)
    monkeypatch.setattr(engines, "_retrieve_assignment_sources", lambda *_args: [
        Source(document_id="pdf", chunk_id=pdf["chunk_id"], title=pdf["title"], text=pdf["text"], score=1),
    ])
    monkeypatch.setattr(engines.rag, "generate_answer", answer)
    result = asyncio.run(engines._socratic_message(assignment, attempt, "What if there is not enough money?"))
    assert "asks for coins" in result["reply"]
    assert "allowed_keywords" not in observed["classifier_options"]
    assert "allowed_keywords" not in observed["generation_options"]
    assert "objective_keywords" not in result["socratic"]


def test_ambiguous_tutor_term_asks_scope_before_generation():
    history = [ChatMessage(role="assistant", content="You see the prompt asking what you would like.")]
    paraphrased_history = [
        *history,
        ChatMessage(role="user", content="What is the prompt?"),
        ChatMessage(role="assistant", content="Imagine the machine asks what you would like."),
    ]
    classification = _classification_from_observation(
        message_role="learning_question", concepts=("prompt",),
        rewritten_query="definition of prompt",
    )
    for message in ("what is the prompt?", "what is the prompt here, its like a step or order?"):
        clarified = engines._clarify_term_scope(message, history, classification)
        assert clarified.needs_clarification
        assert clarified.target_concepts == ("prompt",)
        assert [option.label for option in clarified.clarification_options] == [
            "In this assignment", "Generally, another example",
        ]
        assert all(option.message_role == "direct_answer_request" for option in clarified.clarification_options)
        assert engines._clarify_term_scope(message, paraphrased_history, classification).needs_clarification
    assert not engines._clarify_term_scope(
        "what is the prompt in general?", history, classification,
    ).needs_clarification
    assert not engines._clarify_term_scope(
        "How many slices of bread are needed?", history, classification,
    ).needs_clarification
    selected = engines._clarify_term_scope("what is the prompt?", history, classification).clarification_options[1]
    decision = choose_socratic_strategy(
        selected.resolved_message, history, [Source(
            document_id="pdf", chunk_id="pdf:1", title="Sandwich.pdf",
            text="Prompt user to choose a sandwich size.", score=1,
        )], _classification_from_observation(message_role=selected.message_role),
    )
    assert decision.mode == "direct"
    assert choose_socratic_strategy(
        "What does prompt mean?", [], [Source(
            document_id="pdf", chunk_id="pdf:1", title="Sandwich.pdf",
            text="Prompt user to choose a sandwich size.", score=1,
        )], _classification_from_observation(message_role="direct_answer_request"),
    ).mode == "direct"


def test_scope_confirmation_pauses_then_resumes_with_selected_meaning(monkeypatch):
    pdf = _chunk("pdf", "Sandwich.pdf", "Prompt user to choose small, medium, large, off, or report.", "Menu")
    assignment = {
        "id": uuid4(), "tool": "socratic", "title": "Sandwich Maker",
        "snapshot": {"config": {"scope_mode": "assignment"}, "chunks": [pdf]},
    }
    attempt = {
        "id": uuid4(), "messages": [{"role": "assistant", "content": "The prompt asks what you would like."}],
        "engine_state": {"socratic": {"learning_topic": "Sandwich Maker"}},
    }
    calls = []

    async def classify(message, _history, **_kwargs):
        return _classification_from_observation(
            message_role="learning_question", concepts=("prompt",), rewritten_query=message,
        )

    async def resolve(*_args, **_kwargs):
        return None

    async def answer(message, answer_history, _sources, **kwargs):
        calls.append((message, kwargs["classification"].message_role,
                      answer_history, kwargs["learning_topic"]))
        return "A prompt asks the user for input."

    monkeypatch.setattr(engines, "classify_message", classify)
    monkeypatch.setattr(engines, "resolve_term", resolve)
    monkeypatch.setattr(engines, "_retrieve_assignment_sources", lambda *_args: [
        Source(document_id="pdf", chunk_id=pdf["chunk_id"], title=pdf["title"], text=pdf["text"], score=1),
    ])
    monkeypatch.setattr(engines.rag, "generate_answer", answer)
    first = asyncio.run(engines._socratic_message(assignment, attempt, "what is the prompt?"))
    assert first["clarification_only"]
    assert "reply" not in first
    assert "in this assignment" in first["socratic"]["pending_clarification"]["question"]
    assert first["socratic"]["pending_clarification"]["inline"]
    assert len(first["socratic"]["clarification_options"]) == 2
    assert calls == []  # No answer generation until the learner selects a meaning.

    attempt["engine_state"]["socratic"] = first["socratic"]
    attempt["messages"].append({"role": "user", "content": "what is the prompt?"})
    second = asyncio.run(engines._socratic_message(
        assignment, attempt, "Generally, another example", clarification_index=1,
    ))
    assert second["reply"] == "A prompt asks the user for input."
    assert calls and calls[0][1] == "direct_answer_request"
    assert "different, simple hypothetical example" in calls[0][0]
    assert calls[0][2] == []
    assert calls[0][3] == "prompt"
    assert "pending_clarification" not in second["socratic"]
    assert second["socratic"]["classification"]["target_concepts"] == ["prompt"]


@pytest.mark.parametrize("tutor_message", [
    "Why review an empty list?",
    "**Your next thinking step**\nWhy review an empty list?\n\nSee the selected source above.",
    "Let's review the selected source above.",
])
def test_acknowledgement_after_unanswered_question_clarifies_without_generating(monkeypatch, tutor_message):
    assignment = {"id": uuid4(), "tool": "socratic", "title": "Code review",
                  "snapshot": {"config": {}, "chunks": []}}
    attempt = {"id": uuid4(), "messages": [{"role": "assistant", "content": tutor_message}],
               "engine_state": {"socratic": {"phase": "teaching", "learning_topic": "Code review",
                                              "next_thinking_step": "Why review an empty list?" if "?" not in tutor_message else ""}}}
    generated = []

    async def classify(*_args, **_kwargs):
        return _classification_from_observation(message_role="acknowledgement")

    async def generate(*_args, **_kwargs):
        generated.append(True)
        return "This must not be generated."

    monkeypatch.setattr(engines, "classify_message", classify)
    monkeypatch.setattr(engines.rag, "generate_answer", generate)
    result = asyncio.run(engines._socratic_message(assignment, attempt, "ok"))
    assert result["clarification_only"]
    assert "reply" not in result
    assert not generated
    assert result["socratic"]["conversation_action"] == "clarify"
    assert "When you say “ok,”" in result["socratic"]["pending_clarification"]["question"]
    assert "ready to answer the question I just asked" in result["socratic"]["pending_clarification"]["question"]
    assert [option["label"] for option in result["socratic"]["pending_clarification"]["options"]] == [
        "Repeat the question", "Give me a hint",
    ]


def test_typed_clarification_resumes_the_pending_question(monkeypatch):
    pdf = _chunk("pdf", "Sandwich.pdf", "The prompt asks the customer to choose a sandwich size.", "Menu")
    assignment = {"id": uuid4(), "tool": "socratic", "title": "Sandwich Maker",
                  "snapshot": {"config": {}, "chunks": [pdf]}}
    attempt = {"id": uuid4(), "messages": [
        {"role": "assistant", "content": "What does the prompt ask?"},
        {"role": "user", "content": "What is the prompt?"},
    ], "engine_state": {"socratic": {"learning_topic": "Sandwich Maker", "pending_clarification": {
        "original_question": "What is the prompt?", "inline": True, "options": [], "concepts": ["prompt"],
    }}}}
    observed = []

    async def classify(_message, _history, **_kwargs):
        return _classification_from_observation(message_role="support_request", concepts=("prompt",))

    async def answer(message, _history, _sources, **_kwargs):
        observed.append(message)
        return "A prompt asks the customer for a choice."

    async def resolve(*_args, **_kwargs):
        return None

    monkeypatch.setattr(engines, "classify_message", classify)
    monkeypatch.setattr(engines, "resolve_term", resolve)
    monkeypatch.setattr(engines, "_retrieve_assignment_sources", lambda *_args: [
        Source(document_id="pdf", chunk_id=pdf["chunk_id"], title=pdf["title"], text=pdf["text"], score=1),
    ])
    monkeypatch.setattr(engines.rag, "generate_answer", answer)
    result = asyncio.run(engines._socratic_message(
        assignment, attempt, "I mean the word used in this assignment", clarification_text=True,
    ))
    assert result["reply"] == "A prompt asks the customer for a choice."
    assert "What is the prompt?" in observed[0]
    assert "pending_clarification" not in result["socratic"]
    with pytest.raises(HTTPException) as exc:
        asyncio.run(engines._socratic_message(assignment, {**attempt, "engine_state": {"socratic": {}}},
                                              "No pending question", clarification_text=True))
    assert exc.value.status_code == 422


def test_uncertain_subtopic_offers_a_choice_without_forcing_the_old_focus():
    classification = _classification_from_observation(
        message_role="ambiguous", concepts=("payment",),
        missing_context="whether to continue with payment or return to the prompt",
    )
    choice, topics = engines._clarify_uncertain_topic_shift(
        "What about payment?", "prompt", classification,
    )
    assert choice.needs_clarification
    assert topics == ("payment", "prompt")
    assert [option.label for option in choice.clarification_options] == [
        "Explore this topic", "Return to earlier topic",
    ]
    assert "payment" in choice.clarification_options[0].resolved_message
    assert "prompt" in choice.clarification_options[1].resolved_message


def test_uncertain_subtopic_choice_continues_the_selected_focus(monkeypatch):
    pdf = _chunk("pdf", "Sandwich.pdf", "Check resources before asking for coins.", "Payment")
    assignment = {
        "id": uuid4(), "tool": "socratic", "title": "Sandwich Maker",
        "snapshot": {"config": {"scope_mode": "assignment"}, "chunks": [pdf]},
    }
    attempt = {
        "id": uuid4(), "messages": [],
        "engine_state": {"socratic": {
            "learning_topic": "prompt", "stable_concept": "prompt", "active_concept": "prompt",
        }},
    }

    async def classify(message, _history, **_kwargs):
        return _classification_from_observation(
            message_role="ambiguous" if message == "What about payment?" else "learning_question",
            concepts=("payment",), rewritten_query="payment after resource check",
        )

    async def no_resolution(*_args, **_kwargs):
        return None

    async def answer(_message, _history, _sources, **_kwargs):
        return "Let's look at payment. What happens after the resource check?"

    monkeypatch.setattr(engines, "classify_message", classify)
    monkeypatch.setattr(engines, "resolve_term", no_resolution)
    monkeypatch.setattr(engines, "_retrieve_assignment_sources", lambda *_args: [
        Source(document_id="pdf", chunk_id=pdf["chunk_id"], title=pdf["title"], text=pdf["text"], score=1),
    ])
    monkeypatch.setattr(engines.rag, "generate_answer", answer)
    first = asyncio.run(engines._socratic_message(assignment, attempt, "What about payment?"))
    assert first["clarification_only"]
    assert first["socratic"]["pending_clarification"]["topic_choices"] == ["payment", "prompt"]
    attempt["engine_state"]["socratic"] = first["socratic"]
    attempt["messages"].append({"role": "user", "content": "What about payment?"})
    second = asyncio.run(engines._socratic_message(
        assignment, attempt, "Explore this topic", clarification_index=0,
    ))
    assert "payment" in second["reply"]
    assert second["socratic"]["learning_topic"] == "payment"
    assert "pending_clarification" not in second["socratic"]


def test_student_answer_is_checked_against_latest_tutor_question(monkeypatch):
    pdf = _chunk(
        "pdf", "Sandwich requirements.pdf",
        "After choosing a size, check resources. If sufficient, request coins.", "Sequence",
    )
    assignment = {
        "id": uuid4(), "tool": "socratic", "title": "Sandwich Maker",
        "snapshot": {"config": {"scope_mode": "assignment"}, "chunks": [pdf]},
    }
    latest_question = "After choosing small, what does the machine do before asking for coins?"
    attempt = {
        "id": uuid4(),
        "messages": [
            {"role": "assistant", "content": "What is a prompt?"},
            {"role": "user", "content": "The displayed question."},
            {"role": "assistant", "content": latest_question},
        ],
        "engine_state": {"socratic": {
            "learning_topic": "prompt", "stable_concept": "prompt", "active_concept": "prompt",
        }},
    }
    seen = {}

    async def classify(message, _history, **_kwargs):
        return _classification_from_observation(
            message_role="student_answer", concepts=("order list",),
            rewritten_query="order list after choosing small",
        )

    async def evaluate(_message, evaluation_history, _sources, _classification, **kwargs):
        seen["evaluation_history"] = evaluation_history
        seen["evaluation_options"] = kwargs
        return None

    async def answer(_message, generation_history, _sources, **kwargs):
        seen["generation_history"] = generation_history
        seen["generation_options"] = kwargs
        return "The machine checks its ingredients first. What happens if bread is insufficient?"

    async def no_resolution(*_args, **_kwargs):
        return None

    monkeypatch.setattr(engines, "classify_message", classify)
    monkeypatch.setattr(engines, "assess_student_answer_qualitatively", evaluate)
    monkeypatch.setattr(engines, "resolve_term", no_resolution)
    monkeypatch.setattr(engines, "_retrieve_assignment_sources", lambda *_args: [
        Source(document_id="pdf", chunk_id=pdf["chunk_id"], title=pdf["title"], text=pdf["text"], score=1),
    ])
    monkeypatch.setattr(engines.rag, "generate_answer", answer)

    result = asyncio.run(engines._socratic_message(
        assignment, attempt, "it probably adds my order to the list",
    ))
    assert "checks its ingredients" in result["reply"]
    assert seen["evaluation_history"][-1].content == latest_question
    assert "concept_hint" not in seen["evaluation_options"]
    assert seen["generation_history"][-1].content == latest_question
    assert seen["generation_options"]["stable_concept"] is None


def test_assignment_scope_requires_explicit_indexed_materials(monkeypatch):
    pdf = _chunk("pdf-doc", "Sandwich requirements.pdf", "Check inventory before accepting payment.", "Inventory")
    code = _chunk("code-doc", "main.py", "def make_sandwich():\n    pass", "Functions")
    monkeypatch.setattr(engines.db, "list_rag_files", lambda **_kw: [
        {"document_id": "pdf-doc"}, {"document_id": "code-doc"}, {"document_id": "other-doc"},
    ])
    monkeypatch.setattr(engines.db, "snapshot_document_chunks", lambda _course, chosen: [
        chunk for chunk in (pdf, code) if chunk["document_id"] in chosen
    ])
    monkeypatch.setattr(engines.db, "get_course", lambda _course: {"title": "Software Engineering"})
    assignment = {
        "tool": "socratic", "course_id": uuid4(), "title": "Sandwich Maker",
        "config": {"scope_mode": "assignment", "document_ids": ["pdf-doc", "code-doc"],
                   "keywords": [], "learning_objective_id": None, "prompt": "", "minimum_messages": 1},
    }
    snapshot = engines.publish_snapshot(assignment)
    assert {item["document_id"] for item in snapshot["concept_map"]} == {"pdf-doc", "code-doc"}
    assert {chunk["document_id"] for chunk in snapshot["chunks"]} == {"pdf-doc", "code-doc"}
    assert engines._assignment_keywords(snapshot) == ()
    assert "Inventory" in snapshot["concept_map"][0]["topics"]
    opening = engines.start({"tool": "socratic", "title": "Sandwich Maker", "snapshot": snapshot}, {"id": uuid4()})
    assert "Check inventory" in opening["messages"][0]["content"]

    assignment["config"] = {**assignment["config"], "document_ids": []}
    try:
        engines.publish_snapshot(assignment)
    except Exception as error:
        assert "Select indexed assignment materials" in str(error)
    else:
        raise AssertionError("Assignment-wide mode must not silently include all course documents")


def test_python_skeleton_is_text_only_and_indexable():
    chunks = shared_rag._parse_python("main.py", b"def make_sandwich():\n    return 'ready'\n")
    assert chunks and "def make_sandwich" in chunks[0]["text"]
    assert chunks[0]["metadata"]["source_type"] == "python"


def test_students_can_move_between_document_subtopics_but_not_outside_evidence(monkeypatch):
    pdf = _chunk("pdf-doc", "Sandwich requirements.pdf", "Check inventory before payment.", "Inventory")
    code = _chunk("code-doc", "main.py", "def accept_coins(amount): return amount", "Payment")
    assignment = {
        "id": uuid4(), "title": "Sandwich Maker", "tool": "socratic",
        "snapshot": {"config": {"scope_mode": "assignment", "minimum_messages": 1},
                     "chunks": [pdf, code], "concept_map": []},
    }
    attempt = {"id": uuid4(), "messages": [], "engine_state": {"socratic": {"learning_topic": "Sandwich Maker"}}}

    async def classify(message, _history, **_kwargs):
        concept = "inventory" if "inventory" in message.lower() else "payment" if "payment" in message.lower() else "unrelated"
        return MessageClassification(
            message_role="learning_question" if concept == "inventory" else "topic_change",
            route="learning", target_concepts=(concept,), target=concept,
            rewritten_query=message, confidence=0.9,
        )

    async def no_resolution(*_args, **_kwargs):
        return None

    async def no_evaluation(*_args, **_kwargs):
        return None

    async def answer(_message, _history, sources, **_kwargs):
        return f"Let's reason from {sources[0].title}. What would you check next?"

    def retrieve(query, _chunks, _extra=()):
        if "inventory" in query.lower():
            return [Source(document_id="pdf-doc", chunk_id=pdf["chunk_id"], title=pdf["title"], text=pdf["text"], score=1.0)]
        if "payment" in query.lower():
            return [Source(document_id="code-doc", chunk_id=code["chunk_id"], title=code["title"], text=code["text"], score=1.0)]
        return []

    monkeypatch.setattr(engines, "classify_message", classify)
    monkeypatch.setattr(engines, "resolve_term", no_resolution)
    monkeypatch.setattr(engines, "assess_student_answer_qualitatively", no_evaluation)
    monkeypatch.setattr(engines, "_retrieve_assignment_sources", retrieve)
    monkeypatch.setattr(engines.rag, "generate_answer", answer)

    first = asyncio.run(engines._socratic_message(assignment, attempt, "How should inventory be checked?"))
    assert "Sandwich requirements.pdf" in first["reply"]
    attempt["engine_state"]["socratic"] = first["socratic"]
    second = asyncio.run(engines._socratic_message(assignment, attempt, "Now, how should payment work?"))
    assert "main.py" in second["reply"]
    assert second["socratic"]["stable_concept"] == "payment"
    outside = asyncio.run(engines._socratic_message(assignment, attempt, "What about astronomy?"))
    assert "couldn't find support" in outside["reply"]


def test_simple_document_question_gets_direct_answer_without_tutor_generation(monkeypatch):
    pdf = _chunk("pdf-doc", "Sandwich requirements.pdf", "Submit the Python file.", "Turn in")
    assignment = {
        "id": uuid4(), "title": "Sandwich Maker", "tool": "socratic",
        "snapshot": {"config": {"scope_mode": "assignment"}, "chunks": [pdf],
                     "course": {"title": "Software Engineering"}},
    }
    attempt = {"id": uuid4(), "messages": [], "engine_state": {"socratic": {"learning_topic": "Sandwich Maker"}}}

    async def classify(*_args, **_kwargs):
        return MessageClassification(message_role="administrative", route="administrative",
                                     operational_request="list_documents")

    monkeypatch.setattr(engines, "classify_message", classify)
    result = asyncio.run(engines._socratic_message(assignment, attempt, "Which materials are available?"))
    assert "Sandwich requirements.pdf" in result["reply"]
    assert "?" not in result["reply"]


def test_assignment_scope_can_finish_without_a_keyword_quiz(monkeypatch):
    pdf = _chunk("pdf-doc", "Sandwich requirements.pdf", "Check inventory before accepting payment.", "Inventory")
    assignment = {"id": uuid4(), "title": "Sandwich Maker", "tool": "socratic",
                  "snapshot": {"config": {"scope_mode": "assignment"}, "chunks": [pdf]}}
    attempt = {"id": uuid4(), "messages": [{"role": "assistant", "content": "Why check inventory first?"}],
               "engine_state": {"socratic": {"learning_topic": "inventory", "stable_concept": "inventory",
                                             "answered_question_count": 2}}}
    source = Source(document_id="pdf-doc", chunk_id=pdf["chunk_id"], title=pdf["title"], text=pdf["text"], score=1.0)

    async def classify(*_args, **_kwargs):
        return MessageClassification(message_role="student_answer", route="learning",
                                     dialogue_status="answering_tutor", has_substantive_claim=True,
                                     target_concepts=("inventory",), target="inventory")

    async def no_resolution(*_args, **_kwargs):
        return None

    async def evaluate(*_args, **_kwargs):
        return QualitativeFeedback(concept="inventory", supported_concepts=("inventory",),
                                   missing_concepts=(), critical_misconception=False,
                                   misconception=None, feedback="Good reasoning.")

    async def answer(*_args, **_kwargs):
        return "Yes, check inventory first. What happens if bread is missing?"

    monkeypatch.setattr(engines, "classify_message", classify)
    monkeypatch.setattr(engines, "resolve_term", no_resolution)
    monkeypatch.setattr(engines, "assess_student_answer_qualitatively", evaluate)
    monkeypatch.setattr(engines, "_retrieve_assignment_sources", lambda *_args, **_kwargs: [source])
    monkeypatch.setattr(engines.rag, "generate_answer", answer)
    result = asyncio.run(engines._socratic_message(assignment, attempt, "To avoid charging before we know we can make it."))
    assert result["socratic"]["phase"] == "teaching"
    assert result["socratic"]["latest_feedback"]["concept"] == "inventory"
    assert "last_score" not in result["socratic"]
    assert "assessment" not in result
    assert result["socratic"].get("concept_check") is None
