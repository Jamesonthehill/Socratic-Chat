import asyncio
from copy import deepcopy
from uuid import uuid4

from app.answer_evaluation import QualitativeFeedback
from app.classifier import MessageClassification
from app.schemas import Source
from platform_app import engines


def test_support_explanation_clears_previous_unanswered_question():
    classification = MessageClassification(message_role="support_request", conversation_action="continue")
    state = {"next_thinking_step": "What exact phrase should appear on the screen?"}

    result = engines._socratic_result(
        "The material says: 'Sorry there is not enough bread.'", [], state, classification,
    )

    assert result["socratic"]["next_thinking_step"] == ""


def test_snapshot_retrieval_uses_frozen_embeddings_and_text(monkeypatch):
    chunks = [
        {
            "document_id": "doc-a",
            "chunk_id": "chunk-a",
            "title": "Unrelated notes",
            "text": "A separate topic with no matching terms.",
            "embedding": [0.0, 1.0],
        },
        {
            "document_id": "doc-b",
            "chunk_id": "chunk-b",
            "title": "Version control",
            "text": "Version control records revision history for a team.",
            "embedding": [1.0, 0.0],
        },
    ]
    frozen = deepcopy(chunks)
    monkeypatch.setattr(engines.rag, "create_embeddings", lambda _texts: [[1.0, 0.0]])

    sources = engines.rag.retrieve_snapshot("How does version control track revisions?", chunks)

    assert [source.chunk_id for source in sources] == ["chunk-b"]
    assert chunks == frozen


def test_assignment_message_uses_classifier_evaluation_and_mastery_state(monkeypatch):
    calls = []

    async def classify(message, history, learning_topic=None):
        calls.append(("classify", message, len(history)))
        return MessageClassification(
            route="learning",
            question_type="follow_up",
            target_concepts=("version control",),
            conversation_state="answering_tutor",
            dialogue_status="answering_tutor",
            conversation_action="continue",
            has_substantive_claim=True,
            target="version control",
            rewritten_query="version control tracks changes",
            confidence=0.95,
            source="rules",
        )

    source = Source(
        document_id="doc",
        chunk_id="chunk",
        title="Notes",
        text="Version control tracks revisions.",
        score=1.0,
    )
    evaluation = QualitativeFeedback(
        concept="version control",
        supported_concepts=("revision history",),
        missing_concepts=(),
        critical_misconception=False,
        misconception=None,
        feedback="You connected version control to revision history.",
    )

    async def evaluate(message, history, sources, classification, **kwargs):
        calls.append(("evaluate", len(sources)))
        return evaluation

    async def generate(message, history, sources, classification=None, evaluation=None, **kwargs):
        calls.append(("generate", classification.target, evaluation.concept))
        return "That identifies revision history. How does it help two developers collaborate?"

    monkeypatch.setattr(engines, "classify_message", classify)
    monkeypatch.setattr(engines, "assess_student_answer_qualitatively", evaluate)
    monkeypatch.setattr(engines.rag, "retrieve_snapshot", lambda *_args, **_kwargs: [source])
    monkeypatch.setattr(engines.rag, "generate_answer", generate)

    assignment = {
        "id": uuid4(),
        "snapshot": {"config": {}, "chunks": [{"document_id": "doc"}]},
    }
    attempt = {
        "id": uuid4(),
        "messages": [{"role": "assistant", "content": "Why does version control help a team?"}],
        "engine_state": {},
    }
    result = asyncio.run(engines._socratic_message(assignment, attempt, "It tracks changes."))

    assert result["reply"].endswith("collaborate?")
    assert result["sources"][0]["document_id"] == "doc"
    assert result["socratic"]["active_concept"] == "version control"
    assert result["socratic"]["next_thinking_step"] == "How does it help two developers collaborate?"
    assert result["socratic"]["keywords"] == ["version control"]
    assert "last_score" not in result["socratic"]
    assert result["socratic"]["latest_feedback"]["concept"] == "version control"
    assert [call[0] for call in calls] == ["classify", "evaluate", "generate"]


def test_third_substantive_answer_adds_one_persisted_concept_check(monkeypatch):
    calls = []

    async def classify(message, history, learning_topic=None, **kwargs):
        calls.append("classify")
        return MessageClassification(
            message_role="student_answer",
            route="learning",
            target_concepts=("version control",),
            dialogue_status="answering_tutor",
            conversation_action="continue",
            has_substantive_claim=True,
            target="version control",
            rewritten_query="version control",
            keyword_scope_match=True,
        )

    evaluation = QualitativeFeedback(
        concept="version control",
        supported_concepts=("revision history",),
        missing_concepts=(),
        critical_misconception=False,
        misconception=None,
        feedback="Good connection.",
    )

    async def evaluate(*args, **kwargs):
        calls.append("evaluate")
        return evaluation

    async def generate(*args, **kwargs):
        calls.append("generate")
        return "How would you apply this idea on a team?"

    async def resolve(*args, **kwargs):
        return None

    monkeypatch.setattr(engines, "classify_message", classify)
    monkeypatch.setattr(engines, "assess_student_answer_qualitatively", evaluate)
    monkeypatch.setattr(engines, "resolve_term", resolve)
    monkeypatch.setattr(engines.rag, "retrieve_snapshot", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(engines.rag, "generate_answer", generate)

    assignment = {
        "id": uuid4(),
        "snapshot": {
            "config": {},
            "approved_keywords": ["version control", "branching", "merging"],
            "keyword_glossary": [
                {
                    "keyword": "version control",
                    "definition": "Version control records and organizes changes over time.",
                },
                {
                    "keyword": "branching",
                    "definition": "Branching creates an independent line of development.",
                },
                {
                    "keyword": "merging",
                    "definition": "Merging combines changes from separate development lines.",
                },
            ],
            "chunks": [],
        },
    }
    attempt = {
        "id": uuid4(),
        "messages": [
            {"role": "assistant", "content": "Why does version control help?"},
        ],
        "engine_state": {
            "socratic": {
                "answered_question_count": 2,
                "objective_keywords": ["version control", "branching", "merging"],
            }
        },
    }

    result = asyncio.run(
        engines._socratic_message(assignment, attempt, "It preserves history.")
    )

    check = result["socratic"]["concept_check"]
    assert result["socratic"]["answered_question_count"] == 3
    assert check["id"] == "after-3-answers"
    assert check["question"] == (
        'Which situation is the best example of using "version control" in practice?'
    )
    assert len(check["options"]) == 3
    assert all(set(option) == {"id", "text"} for option in check["options"])
    assert all(
        option["text"].startswith("A team sees this in practice")
        for option in check["options"]
    )
    assert "correct" not in str(check).lower()

    attempt["engine_state"]["socratic"] = result["socratic"]
    attempt["messages"].extend(
        [
            {"role": "user", "content": "It preserves history."},
            {"role": "assistant", "content": result["reply"]},
        ]
    )
    calls_before_quiz = calls.copy()
    correct_text = engines._concept_example(assignment["snapshot"]["keyword_glossary"][0])
    correct_index = next(index for index, option in enumerate(check["options"]) if option["text"] == correct_text)
    quiz_result = asyncio.run(
        engines._socratic_message(
            assignment,
            attempt,
            check["options"][correct_index]["text"],
            concept_check_option=correct_index,
        )
    )

    assert calls == calls_before_quiz
    assert quiz_result["quiz_only"] is True
    assert "reply" not in quiz_result and "student_message" not in quiz_result
    assert "concept_check" not in quiz_result["socratic"]
    assert quiz_result["socratic"]["concept_check_completed"] is True
    assert quiz_result["socratic"]["concept_check_response"]["correct"] is True
    assert quiz_result["socratic"]["concept_check_response"]["correct_option"] == check["options"][correct_index]

    wrong_index = next(index for index in range(len(check["options"])) if index != correct_index)
    wrong_result = asyncio.run(
        engines._socratic_message(
            assignment,
            attempt,
            check["options"][wrong_index]["text"],
            concept_check_option=wrong_index,
        )
    )
    assert wrong_result["socratic"]["concept_check_response"]["correct"] is False
    assert calls == calls_before_quiz
