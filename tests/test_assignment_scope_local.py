"""Local, provider-free checks for assignment-wide Socratic tutoring."""
import asyncio
from uuid import uuid4

import pytest
from fastapi import HTTPException
from app.schemas import Source
from app.answer_evaluation import QualitativeFeedback
from app.classifier import MessageClassification, _classification_from_observation
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


def test_course_term_question_uses_assignment_without_scope_confirmation(monkeypatch):
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
    result = asyncio.run(engines._socratic_message(assignment, attempt, "what is the prompt?"))
    assert result["reply"] == "A prompt asks the user for input."
    assert calls and calls[0][0] == "what is the prompt?"
    assert calls[0][1] == "learning_question"
    assert calls[0][3] == "prompt"
    assert not result.get("clarification_only")
    assert "pending_clarification" not in result["socratic"]


def test_short_reply_is_not_forced_into_clarification_by_backend(monkeypatch):
    source = Source(document_id="pdf", chunk_id="chunk-1", title="Review.pdf",
                    text="The reviewer checks the change before merging.", score=1.0)
    active_step = {"title": "Review feedback", "goal": "Understand the review comment.",
                   "scenario": "A teammate reviews an empty-list failure.", "question": "What should you check first?"}
    assignment = {"id": uuid4(), "tool": "socratic", "title": "Code review",
                  "snapshot": {"config": {"learning_steps": [active_step]},
                               "chunks": [_chunk("pdf", "Review.pdf", source.text, "Review")]}}
    attempt = {"id": uuid4(), "messages": [{"role": "assistant", "content": "Does that clarify how it works?"}],
               "engine_state": {"socratic": {"phase": "teaching", "learning_topic": "Code review",
                                              "learning_step_index": 0}}}
    generated = []

    async def classify(*_args, **_kwargs):
        return _classification_from_observation(message_role="acknowledgement")

    async def generate(*_args, **kwargs):
        generated.append(kwargs)
        return "Glad that helped."

    async def nothing(*_args, **_kwargs):
        return None

    monkeypatch.setattr(engines, "classify_message", classify)
    monkeypatch.setattr(engines, "_retrieve_assignment_sources", lambda *_args: [source])
    monkeypatch.setattr(engines, "resolve_term", nothing)
    monkeypatch.setattr(engines, "assess_student_answer_qualitatively", nothing)
    monkeypatch.setattr(engines.rag, "generate_answer", generate)
    result = asyncio.run(engines._socratic_message(assignment, attempt, "yes it is"))
    assert result["reply"] == "Glad that helped."
    assert "clarification_only" not in result
    assert generated
    assert generated[0]["active_learning_step"] == active_step


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


def test_new_subtopic_continues_without_a_clarification_choice(monkeypatch):
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
            message_role="learning_question",
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
    result = asyncio.run(engines._socratic_message(assignment, attempt, "What about payment?"))
    assert "payment" in result["reply"]
    assert result["socratic"]["learning_topic"] == "payment"
    assert "pending_clarification" not in result["socratic"]


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
