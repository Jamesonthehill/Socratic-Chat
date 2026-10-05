from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, replace
from time import monotonic
from typing import Any

from app import settings
from app.pipeline_logging import (
    debug_preview,
    log_event,
    log_exception,
    update_llm_request_snapshot,
    write_llm_request_snapshot,
)
from app.schemas import ChatMessage


# The broad destination for a message; this is not the student's mastery level.
ROUTES = {
    "learning",         # A course-concept question or answer: use the teaching/RAG pipeline.
    "administrative",   # Course logistics such as deadlines or published documents.
    "session_control",  # A command to stop or end the current conversation.
    "unclear",          # Too little information to identify a useful learning target.
}
# Administrative requests that can be answered from course/application state.
# "none" means the message should continue through the learning pipeline.
OPERATIONAL_REQUESTS = {
    "none",                 # No operational lookup is requested.
    "list_documents",       # Student asks which documents are available.
    "document_visibility",  # Student asks whether a particular file is visible.
    "document_overview",    # Student asks for an overview of published files.
    "course_title",         # Student asks for the course's name.
    "course_instructor",    # Student asks who teaches the course.
    "course_scope",         # Student asks what this course/chat covers.
    "system_status",        # Student asks whether the application is working.
}
# The grammatical/task shape of a question, used to select an appropriate
# example and next question; this is distinct from the conversation state.
QUESTION_TYPES = {
    "what",         # Ask what a concept means or is.
    "why",          # Ask for a reason or purpose.
    "how",          # Ask for a process or mechanism.
    "comparison",   # Ask how two concepts differ.
    "application",  # Ask how a concept works in a scenario.
    "debugging",    # Ask why a particular result or system fails.
    "statement",    # Student offers a claim or answer rather than a question.
    "follow_up",    # Ask about something established in earlier dialogue.
    "unclear",      # The question form cannot be determined confidently.
}
# A detailed description of what the student is doing in this particular turn.
CONVERSATION_STATES = {
    "new_concept",           # Opens a concept the tutor has not explored yet.
    "answering_tutor",       # Responds to the tutor's preceding question.
    "reasoning_in_progress", # Offers a reason or chain of thought to examine.
    "uncertain",             # Explicitly expresses confusion or not knowing.
    "possible_misconception", # Offers an idea that may conflict with course evidence.
    "requesting_hint",      # Explicitly asks for a clue or smaller step.
    "requesting_answer",    # Explicitly asks the tutor to answer directly.
    "claiming_understanding", # Says they understand without demonstrating it yet.
    "acknowledging",         # Brief thanks or acknowledgement, not a new task.
    "closing",               # Says goodbye or asks to end the session.
    "changing_topic",        # Starts an unrelated main learning objective.
    "follow_up",             # Continues the current topic with a related question.
}
# A compact status used to decide whether an answer is eligible for evaluation.
DIALOGUE_STATUSES = {
    "new_topic",              # Starts a topic; there is no student answer to score yet.
    "answering_tutor",         # Supplies an answer to a tutor question; may be scored.
    "requesting_confirmation", # Asks whether their specific claim is correct.
    "claiming_understanding",  # Reports understanding but has not proved it.
    "reasoning_in_progress",   # Gives reasoning the tutor may assess.
    "uncertain",               # Needs support rather than a score.
    "requesting_support",      # Asks for assistance or a clue.
    "acknowledgement",         # Acknowledges the reply without adding reasoning.
    "closing",                 # Wants to finish the conversation.
    "changing_topic",          # Wants a different primary topic.
    "administrative_request",  # Requests course/application facts.
    "unclear",                 # Cannot safely choose a specific teaching action.
}
# The next action the controller should take, not a text response itself.
CONVERSATION_ACTIONS = {
    "continue",             # Retrieve evidence and proceed with a teaching turn.
    "verify_claim",         # Check the student's explicit claim against evidence.
    "verify_understanding", # Ask for a teach-back/prediction before trusting "I understand".
    "soft_close",           # Acknowledge a possible ending without another lesson question.
    "complete",             # Close a clearly ended conversation.
    "clarify",              # Ask what the student means before searching.
    "direct",               # Provide requested information without Socratic withholding.
}
# A turn-level LLM estimate, not the persisted 0–100 per-concept mastery score.
UNDERSTANDING_LEVELS = {
    "unknown",     # The message does not demonstrate knowledge yet.
    "beginner",    # Shows little or preliminary understanding.
    "developing",  # Shows some correct but incomplete understanding.
    "proficient",  # Shows strong understanding in this turn.
}
# Ignore these common linking/question words when checking whether an LLM-made
# retrieval subquery still contains a meaningful term from the student's text.
QUERY_STOP_WORDS = {
    "about", "after", "from", "into", "with",  # Common relationships, not a topic.
    "also", "like", "more", "other",            # Modifiers shared by unrelated topics.
    "could", "does", "have", "would",            # Helper verbs in many questions.
    "that", "their", "them", "there", "these", "this", "your",  # Context words needing a noun.
    "what", "when", "where", "which",            # Question words, not course concepts.
}

# The provider must return one structured JSON object. The schema prevents
# arbitrary labels from silently becoming routing instructions.
CLASSIFICATION_SCHEMA: dict[str, Any] = {
    "type": "object",  # The model response must be a JSON object, not prose.
    "properties": {
        "route": {"type": "string", "enum": sorted(ROUTES)},  # Broad pipeline destination.
        "question_type": {"type": "string", "enum": sorted(QUESTION_TYPES)},  # Question shape.
        "target_concepts": {
            "type": "array",  # A comparison can have more than one concept.
            "items": {"type": "string", "maxLength": 100},  # Bound each concept label.
        },
        "conversation_state": {"type": "string", "enum": sorted(CONVERSATION_STATES)},  # Student's turn-level behavior.
        "dialogue_status": {"type": "string", "enum": sorted(DIALOGUE_STATUSES)},  # Evaluation eligibility/context.
        "conversation_action": {"type": "string", "enum": sorted(CONVERSATION_ACTIONS)},  # Controller decision.
        "has_substantive_claim": {"type": "boolean"},  # True only for a meaningful student proposition.
        "student_claim": {"type": ["string", "null"], "maxLength": 500},  # Exact claim to verify, if any.
        "wants_to_continue": {"type": "boolean"},  # Distinguishes learning from an ending.
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},  # Model's classification confidence.
        "needs_clarification": {"type": "boolean"},  # Whether a specific referent is missing.
        "clarification_question": {"type": ["string", "null"], "maxLength": 200},  # One request for missing context.
        "retrieval_query": {"type": "string", "minLength": 1, "maxLength": 300},  # Standalone DB search wording.
        "retrieval_subqueries": {
            "type": "array", "items": {"type": "string", "minLength": 1, "maxLength": 300},  # Compound question parts.
            "maxItems": 3,  # Limit model-suggested searches per turn.
        },
        "operational_request": {"type": "string", "enum": sorted(OPERATIONAL_REQUESTS)},  # Course/application lookup.
        "understanding_level": {"type": "string", "enum": sorted(UNDERSTANDING_LEVELS)},  # Temporary estimate.
        "support_level": {"type": "integer", "minimum": 0, "maximum": 3},  # Amount of help to offer.
    },
    # Requiring all fields makes missing model judgments a validation error
    # instead of allowing an accidental default route or score.
    "required": [
        "route", "question_type", "target_concepts", "conversation_state",
        "dialogue_status", "conversation_action", "has_substantive_claim", "student_claim",
        "wants_to_continue", "confidence", "needs_clarification", "clarification_question",
        "retrieval_query", "retrieval_subqueries", "operational_request", "understanding_level", "support_level",
    ],
    "additionalProperties": False,  # Reject unrecognized model-created fields.
}

# Rule-based fallbacks below detect explicit wording when the classifier model
# is unavailable. They are not the complete intent-recognition system.
ADMIN_PATTERN = re.compile(
    r"\b(?:assignment|rubric|deadline|due date|submission|submit|points?|grade|"
    r"office hours?|schedule|syllabus|uploaded files?)\b",
    re.IGNORECASE,
)
# Anchor at both ends so a sentence mentioning "stop" is not mistaken for
# a command to end the lesson.
SESSION_CONTROL_PATTERN = re.compile(
    r"^(?:stop|pause|end|quit|exit)(?:\s+(?:the\s+)?(?:chat|lesson|session|questions?))?[.! ]*$",
    re.IGNORECASE,
)
HINT_PATTERN = re.compile(r"\b(?:hint|clue|nudge|help me start|guide me)\b", re.IGNORECASE)  # Explicit support request.
# An explicit preference for a direct response can override discovery mode.
DIRECT_ANSWER_PATTERN = re.compile(
    r"\b(?:just tell me|give me the answer|answer directly|no questions?|stop asking)\b", re.IGNORECASE,
)
# Asking "is that correct?" differs from merely answering the tutor.
CONFIRMATION_REQUEST_PATTERN = re.compile(
    r"(?:\b(?:is that|am i|is this|would that be|does that mean)\s+(?:right|correct|accurate)\b|"
    r"\b(?:right|correct|accurate)\s*\?)",
    re.IGNORECASE,
)
# Self-reported confusion raises support; it is not graded as an answer.
UNCERTAIN_PATTERN = re.compile(
    r"\b(?:i (?:still )?(?:do not|don't) know|not sure|unsure|confused|no idea|stuck)\b", re.IGNORECASE,
)
# Tentative contradictory phrasing is a cue to check a claim against evidence.
MISCONCEPTION_PATTERN = re.compile(
    r"\b(?:i thought|isn't it|is it not|but i think|shouldn't|cannot be|can't be)\b", re.IGNORECASE,
)
REASONING_PATTERN = re.compile(r"\b(?:because|therefore|since|which means|so that)\b", re.IGNORECASE)  # Possible reasoning.
# These openings commonly introduce a new concept rather than answer a prompt.
DEFINITION_REQUEST_PATTERN = re.compile(
    r"^(?:what (?:is|are)|define|explain|tell me about|help me understand)\b", re.IGNORECASE,
)
# The next two patterns work together: asking what a phrase means, plus a
# pointer to earlier tutor wording, should stay in the existing topic.
CONTEXTUAL_MEANING_PATTERN = re.compile(
    r"^(?:what|how|can you|could you|explain)\b.*\b(?:mean|means|meaning|refer(?:s)? to)\b",
    re.IGNORECASE,
)
CONTEXT_REFERENCE_PATTERN = re.compile(
    r'["“”]|\b(?:in (?:this|the) context|here|that phrase|this phrase|your (?:last|previous) (?:question|message))\b',
    re.IGNORECASE,
)


def is_contextual_meaning_request(message: str, history: list[ChatMessage]) -> bool:
    """A learner is asking about wording the tutor just used, not opening a new topic."""
    return bool(
        CONTEXTUAL_MEANING_PATTERN.search(message)
        and CONTEXT_REFERENCE_PATTERN.search(message)
        and any(item.role == "assistant" for item in history[-4:])
    )


@dataclass(frozen=True)
class MessageClassification:
    """Validated interpretation used to route retrieval and Socratic teaching."""

    route: str = "learning"  # Which broad pipeline handles this message.
    question_type: str = "unclear"  # What kind of question/task the learner posed.
    target_concepts: tuple[str, ...] = ()  # Named topics to keep retrieval focused.
    conversation_state: str = "new_concept"  # Detailed behavior in this turn.
    dialogue_status: str = "new_topic"  # Status used by answer-evaluation eligibility.
    conversation_action: str = "continue"  # Immediate action for the chat controller.
    has_substantive_claim: bool = False  # Whether there is a proposition to assess.
    student_claim: str | None = None  # The proposition in the student's own words.
    wants_to_continue: bool = True  # False for a closing or near-closing.
    confidence: float = 0.0  # Confidence in classification, not student mastery.
    needs_clarification: bool = False  # True when the target is too ambiguous.
    clarification_question: str | None = None  # One question for the missing context.
    target: str | None = None  # Primary concept used by downstream evaluation.
    direct_answer: str | None = None  # Deterministic reply for a guarded special case.
    rewritten_query: str | None = None  # Standalone wording for database retrieval.
    retrieval_subqueries: tuple[str, ...] = ()  # Extra searches for compound questions.
    operational_request: str = "none"  # Course/application metadata lookup, if any.
    understanding_level: str = "unknown"  # Temporary turn-level understanding label.
    support_level: int = 0  # Requested/needed scaffold, from 0 to 3.
    source: str = "rules"  # Whether labels came from rules or the model.


def _clean_concept(value: object) -> str | None:
    # Reject non-text model output before using a label as a retrieval target.
    if not isinstance(value, str):
        return None
    # Normalize whitespace/punctuation and remove articles or trailing verbs
    # so "the code review?" and "code review" share one concept label.
    concept = " ".join(value.strip(" \t\n\r?.!,;:'\"/").split())
    concept = re.sub(r"^(?:the|a|an)\s+", "", concept, flags=re.IGNORECASE)
    concept = re.sub(r"\s+(?:is|are)$", "", concept, flags=re.IGNORECASE)
    # Pronouns alone are not stable concepts; use conversation history instead.
    if not concept or concept.lower() in {"it", "this", "that", "these", "those", "they"} or len(concept) > 100:
        return None
    return concept


def _extract_concepts(message: str) -> tuple[str, ...]:
    # Rules identify obvious concepts even if the LLM classifier is offline.
    normalized = " ".join(message.strip().rstrip("?.!").split())
    # A comparison needs both named concepts rather than a single vague label.
    comparison_patterns = [
        r"\b(?:difference between|compare)\s+(.+?)\s+(?:and|with|to)\s+(.+)$",
        r"^how\s+(?:is|are)\s+(.+?)\s+and\s+(.+?)\s+different$",
        r"^how\s+(?:is|are)\s+(.+?)\s+different\s+from\s+(.+)$",
    ]
    for pattern in comparison_patterns:
        comparison = re.search(pattern, normalized, re.IGNORECASE)
        if comparison:
            values = (_clean_concept(comparison.group(1)), _clean_concept(comparison.group(2)))
            return tuple(value for value in values if value)

    # For a definition or process question, capture its subject after the
    # opening phrase (for example, "what is code review?").
    patterns = [
        r"^(?:please\s+)?(?:what (?:is|are)|define|explain(?:\s+what)?|tell me about|help me understand)\s+(.+)$",
        r"^(?:please\s+)?(?:why|how)\s+(?:does|do|is|are|can|could|would|should)\s+(.+)$",
    ]
    for pattern in patterns:
        match = re.match(pattern, normalized, re.IGNORECASE)
        if not match:
            continue
        candidate = re.split(
            r"\s+(?:work|important|useful|different|matter|affect|help|used)\b",
            match.group(1), maxsplit=1, flags=re.IGNORECASE,
        )[0]
        concept = _clean_concept(candidate)
        if concept:
            return (concept,)
    return ()


def _latest_concepts(history: list[ChatMessage]) -> tuple[str, ...]:
    # A short follow-up such as "why does it matter?" inherits the last topic.
    for item in reversed(history[-8:]):
        if item.role == "user":
            concepts = _extract_concepts(item.content)
            if concepts:
                return concepts
    return ()


def _retrieval_query(message: str, concepts: tuple[str, ...]) -> str:
    # Add any inferred concept missing from the literal message so retrieval
    # can search for the intended subject, not only a pronoun or short reply.
    clean = " ".join(message.strip().split())
    missing = [concept for concept in concepts if concept.lower() not in clean.lower()]
    return " ".join([clean, *missing]).strip()


def _rule_classification(message: str, history: list[ChatMessage]) -> MessageClassification:
    # This deterministic interpretation is the safety net and the baseline
    # against which the model's structured classification is checked.
    clean = " ".join(message.strip().split())
    lowered = clean.lower()
    concepts = _extract_concepts(clean)

    # A standalone stop/end command closes the session before retrieval.
    if SESSION_CONTROL_PATTERN.match(clean):
        return MessageClassification(
            route="session_control", question_type="statement",
            conversation_state="closing", dialogue_status="closing", conversation_action="complete",
            wants_to_continue=False, confidence=1.0,
        )

    # Explicit course-logistics wording can be routed to operational answers.
    if ADMIN_PATTERN.search(clean):
        return MessageClassification(
            route="administrative",
            question_type="what" if lowered.startswith("what") else "how",
            dialogue_status="administrative_request", conversation_action="direct",
            target_concepts=concepts, target=concepts[0] if concepts else None,
            confidence=0.98, rewritten_query=clean,
        )

    # These branches choose a temporary student state and the next action;
    # none of them calculates or stores a mastery score.
    if HINT_PATTERN.search(clean):
        state, dialogue_status, action = "requesting_hint", "requesting_support", "continue"
    elif DIRECT_ANSWER_PATTERN.search(clean):
        state, dialogue_status, action = "requesting_answer", "answering_tutor", "direct"
    elif UNCERTAIN_PATTERN.search(clean):
        state, dialogue_status, action = "uncertain", "uncertain", "continue"
    elif MISCONCEPTION_PATTERN.search(clean) and clean.endswith("?"):
        state, dialogue_status, action = "possible_misconception", "requesting_confirmation", "verify_claim"
    elif REASONING_PATTERN.search(clean):
        state, dialogue_status, action = "reasoning_in_progress", "reasoning_in_progress", "continue"
    elif re.search(r"\b(?:difference between|compare|different|differ)\b", clean, re.IGNORECASE):
        state, dialogue_status, action = "new_concept", "new_topic", "continue"
    elif lowered.startswith("why"):
        state, dialogue_status, action = "new_concept", "new_topic", "continue"
    elif lowered.startswith("how"):
        state, dialogue_status, action = "new_concept", "new_topic", "continue"
    elif DEFINITION_REQUEST_PATTERN.match(clean):
        state, dialogue_status, action = "new_concept", "new_topic", "continue"
    else:
        state = "answering_tutor" if history and any(item.role == "assistant" for item in history[-2:]) else "follow_up"
        dialogue_status = "answering_tutor" if state == "answering_tutor" else "unclear"
        action = "continue"

    # Question type guides the teaching move: explanation, comparison,
    # procedure, or response to the previous tutor turn.
    if lowered.startswith("why"):
        question_type = "why"
    elif re.search(r"\b(?:difference between|compare|different|differ)\b", clean, re.IGNORECASE):
        question_type = "comparison"
    elif lowered.startswith("how"):
        question_type = "how"
    elif lowered.startswith("what") or DEFINITION_REQUEST_PATTERN.match(clean):
        question_type = "what"
    elif clean.endswith("?"):
        question_type = "follow_up"
    else:
        question_type = "statement"

    # Recover the topic from recent student turns when the learner uses "it"
    # or another contextual reference instead of repeating the concept name.
    pronoun_follow_up = bool(re.search(r"\b(?:it|this|that|these|those|they)\b", clean, re.IGNORECASE))
    if not concepts and (question_type == "follow_up" or state != "new_concept" or pronoun_follow_up):
        concepts = _latest_concepts(history)
        if concepts and pronoun_follow_up:
            state = "follow_up"

    # A very short message with no recoverable concept is safer to clarify
    # than to search the wrong course topic.
    vague = len(clean.split()) <= 2 and not concepts and state not in {"requesting_hint", "requesting_answer"}
    return MessageClassification(
        route="unclear" if vague else "learning",
        question_type="unclear" if vague else question_type,
        target_concepts=concepts,
        conversation_state=state,
        dialogue_status="unclear" if vague else dialogue_status,
        conversation_action="clarify" if vague else action,
        confidence=0.45 if vague else 0.72,
        needs_clarification=vague,
        clarification_question="Which course concept or problem would you like to examine?" if vague else None,
        target=concepts[0] if concepts else None,
        rewritten_query=_retrieval_query(clean, concepts),
    )


def _json_object(text: str) -> dict[str, Any]:
    # Accept a JSON object even if the provider wraps it in a code fence, but
    # reject prose or a JSON array before any routing fields are used.
    cleaned = text.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, re.DOTALL | re.IGNORECASE)
    if fenced:
        cleaned = fenced.group(1)
    else:
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start >= 0 and end > start:
            cleaned = cleaned[start : end + 1]
    value = json.loads(cleaned)
    if not isinstance(value, dict):
        raise ValueError("Classifier response must be a JSON object.")
    return value


def _validated_llm_classification(
    payload: dict[str, Any], message: str, fallback: MessageClassification,
) -> MessageClassification:
    # Each model label must be from the allowlist; invalid values inherit the
    # rule-based result instead of creating an unrecognized pipeline route.
    route = payload.get("route") if payload.get("route") in ROUTES else fallback.route
    question_type = payload.get("question_type") if payload.get("question_type") in QUESTION_TYPES else fallback.question_type
    state = payload.get("conversation_state") if payload.get("conversation_state") in CONVERSATION_STATES else fallback.conversation_state
    dialogue_status = (
        payload.get("dialogue_status")
        if payload.get("dialogue_status") in DIALOGUE_STATUSES
        else fallback.dialogue_status
    )
    action = (
        payload.get("conversation_action")
        if payload.get("conversation_action") in CONVERSATION_ACTIONS
        else fallback.conversation_action
    )
    operational_request = (
        payload.get("operational_request")
        if payload.get("operational_request") in OPERATIONAL_REQUESTS
        else fallback.operational_request
    )
    understanding_level = (
        payload.get("understanding_level")
        if payload.get("understanding_level") in UNDERSTANDING_LEVELS
        else fallback.understanding_level
    )
    # Bound requested support to the policy's 0–3 range, even if the model
    # emits a number outside the schema or an unexpected text value.
    try:
        support_level = min(3, max(0, int(payload.get("support_level", fallback.support_level))))
    except (TypeError, ValueError):
        support_level = fallback.support_level
    # Clean and deduplicate model-proposed concepts before they become search
    # terms or a persistent assessment label.
    raw_concepts = payload.get("target_concepts")
    concepts: tuple[str, ...] = ()
    if isinstance(raw_concepts, list):
        cleaned_concepts = [concept for concept in (_clean_concept(item) for item in raw_concepts) if concept]
        concepts = tuple(dict.fromkeys(cleaned_concepts))
    concepts = concepts or fallback.target_concepts
    if (
        route == "administrative"
        and operational_request == "none"
        and fallback.route == "learning"
        and DEFINITION_REQUEST_PATTERN.match(message)
    ):
        # A new course concept is a learning request even when the model
        # mistakes a change of topic for an administrative action.
        route = "learning"
        concepts = fallback.target_concepts
        dialogue_status = "new_topic"
        action = "continue"
    if (
        route == "learning"
        and state == "new_concept"
        and dialogue_status == "requesting_support"
        and DEFINITION_REQUEST_PATTERN.match(message)
        and not HINT_PATTERN.search(message)
        and not UNCERTAIN_PATTERN.search(message)
    ):
        # An opening concept question is not a request for a hint merely
        # because the learner has not demonstrated understanding yet.
        dialogue_status = "new_topic"
    try:
        confidence = min(1.0, max(0.0, float(payload.get("confidence", fallback.confidence))))
    except (TypeError, ValueError):
        confidence = fallback.confidence
    # A high-confidence concrete classification should not be replaced with
    # a generic clarification question merely because the model suggested one.
    needs_clarification = bool(payload.get("needs_clarification", False)) and confidence < 0.75
    clarification = _clean_concept(payload.get("clarification_question")) if needs_clarification else None
    if needs_clarification and not clarification:
        clarification = "Which course concept or problem would you like to examine?"
    rewrite = payload.get("retrieval_query")
    if not isinstance(rewrite, str) or not rewrite.strip() or len(rewrite) > 300:
        rewrite = _retrieval_query(message, concepts)
    rewrite = " ".join(rewrite.split())
    # Model-created subqueries are accepted only if they are distinct and
    # retain meaningful terms from the student's request or main query.
    raw_subqueries = payload.get("retrieval_subqueries")
    subqueries: list[str] = []
    if isinstance(raw_subqueries, list):
        context_terms = set(re.findall(r"\b[a-zA-Z0-9]{3,}\b", f"{message} {rewrite}".lower())) - QUERY_STOP_WORDS
        for raw_subquery in raw_subqueries[:3]:
            if not isinstance(raw_subquery, str):
                continue
            subquery = " ".join(raw_subquery.split())
            subquery_terms = set(re.findall(r"\b[a-zA-Z0-9]{3,}\b", subquery.lower())) - QUERY_STOP_WORDS
            if (
                3 <= len(subquery) <= 300
                and subquery.lower() != rewrite.lower()
                and subquery.lower() not in {item.lower() for item in subqueries}
                and subquery_terms & context_terms
            ):
                subqueries.append(subquery)
    raw_claim = payload.get("student_claim")
    student_claim = " ".join(raw_claim.strip().split())[:500] if isinstance(raw_claim, str) and raw_claim.strip() else None
    # A boolean alone is insufficient: verification needs the actual claim.
    has_substantive_claim = payload.get("has_substantive_claim") is True and student_claim is not None
    if fallback.question_type == "statement" and has_substantive_claim and not message.strip().endswith("?"):
        question_type = "statement"
    wants_to_continue = payload.get("wants_to_continue") is not False
    if action in {"soft_close", "complete"}:
        wants_to_continue = False
    # Require stronger evidence for a definitive end; ambiguous endings can
    # receive a softer closing instead of prematurely finishing a lesson.
    if action == "complete" and (dialogue_status != "closing" or confidence < 0.8):
        action = "soft_close"
    # Do not fabricate a verdict if the student gave no claim to check.
    if action == "verify_claim" and not has_substantive_claim:
        action = "clarify"
        needs_clarification = True
        clarification = "What specific understanding would you like me to check?"
    elif action == "verify_claim" and not CONFIRMATION_REQUEST_PATTERN.search(message):
        # A student's answer to the tutor is evidence to evaluate, not an
        # implicit request for a direct verdict and explanation.
        state = fallback.conversation_state
        dialogue_status = fallback.dialogue_status
        action = fallback.conversation_action
        needs_clarification = fallback.needs_clarification
        clarification = fallback.clarification_question
    if action == "clarify":
        if (
            route == "learning"
            and question_type != "unclear"
            and concepts
            and confidence >= 0.75
            and payload.get("needs_clarification") is False
        ):
            # The model sometimes identifies a concrete question and search
            # target, yet labels its action "clarify". Let retrieval handle it
            # instead of replacing the question with a generic clarification.
            action = "continue"
            needs_clarification = False
            clarification = None
        else:
            needs_clarification = True
            if not clarification:
                clarification = "Could you clarify what you want to explore or verify?"
    # A declarative answer to the tutor is evidence to assess, even when it is
    # mistaken or off target. A model-suggested clarification must not bypass
    # retrieval, answer evaluation, and the next Socratic teaching turn.
    if (
        route == "learning"
        and dialogue_status == "answering_tutor"
        and has_substantive_claim
        and question_type == "statement"
        and not message.strip().endswith("?")
        and action in {"continue", "clarify"}
    ):
        action = "continue"
        needs_clarification = False
        clarification = None
    # An ordinary concept question starts a Socratic teaching turn. Only the
    # learner's explicit direct-answer wording may bypass the Socratic route.
    explicit_direct_request = bool(DIRECT_ANSWER_PATTERN.search(message))
    if fallback.route == "learning" and not explicit_direct_request and action == "direct":
        state = fallback.conversation_state
        dialogue_status = fallback.dialogue_status
        action = fallback.conversation_action
    return MessageClassification(
        route=route, question_type=question_type,
        target_concepts=concepts, conversation_state=state, dialogue_status=dialogue_status,
        conversation_action=action, has_substantive_claim=has_substantive_claim,
        student_claim=student_claim, wants_to_continue=wants_to_continue, confidence=confidence,
        needs_clarification=needs_clarification, clarification_question=clarification,
        target=concepts[0] if concepts else None,
        rewritten_query=rewrite, retrieval_subqueries=tuple(subqueries),
        operational_request=operational_request,
        understanding_level=understanding_level, support_level=support_level,
        source="llm",
    )


def _client_config() -> tuple[str, str, str, str] | None:
    if not settings.CLASSIFIER_ENABLED:
        return None
    return settings.llm_client_config("classifier")


async def _classify_with_llm(
    message: str, history: list[ChatMessage], fallback: MessageClassification,
    learning_topic: str | None = None,
) -> MessageClassification:
    from openai import AsyncOpenAI

    # The classifier asks the model for labels and a retrieval query, not for
    # the student-facing answer. If disabled, the rule-based result is used.
    config = _client_config()
    if config is None:
        return fallback
    provider, api_key, base_url, model = config
    # A bounded window gives pronouns and short replies context without
    # sending the entire transcript on every request.
    recent = history[-settings.CLASSIFIER_MAX_HISTORY :]
    conversation = "\n".join(f"{item.role}: {item.content}" for item in recent) or "(none)"
    system_prompt = (
        "Classify a student's latest course-chat message. Do not answer it. Return one JSON object only with: "
        "route (learning, administrative, session_control, unclear); question_type "
        "(what, why, how, comparison, application, debugging, statement, "
        "follow_up, unclear); target_concepts (concise noun phrases relevant to the latest message, inferred "
        "from the message and recent conversation rather than a fixed topic list); conversation_state "
        "(new_concept, answering_tutor, reasoning_in_progress, uncertain, possible_misconception, requesting_hint, "
        "requesting_answer, claiming_understanding, acknowledging, closing, changing_topic, follow_up); "
        "dialogue_status (new_topic, answering_tutor, requesting_confirmation, claiming_understanding, "
        "reasoning_in_progress, uncertain, requesting_support, acknowledgement, closing, changing_topic, "
        "administrative_request, unclear); conversation_action (continue, verify_claim, verify_understanding, "
        "soft_close, complete, clarify, direct); has_substantive_claim (boolean); student_claim (the student's "
        "actual proposition to verify or null); wants_to_continue (boolean); confidence (0 to 1); "
        "needs_clarification (boolean); clarification_question "
        "(one short question or null); retrieval_query (a concise standalone search query that preserves named "
        "course items and resolves pronouns from history); retrieval_subqueries (zero to three distinct, "
        "standalone searches for separate information needs in a compound message; use [] for one focused "
        "idea, and resolve references from history without inventing topics); operational_request (none, list_documents, "
        "document_visibility, document_overview, course_title, course_instructor, course_scope, or system_status). "
        "Also return understanding_level (unknown, beginner, developing, or proficient) for the student's currently "
        "demonstrated understanding of the target concept, and support_level (0 to 3), where 0 means no additional "
        "support, 1 means a small scaffold, 2 means the student remains confused and needs a simpler different "
        "example plus a concise explanation, and 3 means repeated difficulty needs a step-by-step worked example. "
        "Infer these from the latest message and recent conversation; never equate confidence or fluent wording with "
        "subject mastery. The objective is learning and understanding the instructor-published topic. "
        "Use an operational request only when the student explicitly asks for that application or course metadata. "
        "Ordinary learning statements that merely mention files, documents, folders, seeing, or having something "
        "must remain operational_request=none. Distinguish a bare understanding claim from a claim "
        "that contains reasoning. Treat thanks without a question as acknowledgement/soft_close, a clear goodbye "
        "as closing/complete, and a claim asking whether it is correct as requesting_confirmation/verify_claim. "
        "A declarative answer to the tutor, including an answer ending with a period, is answering_tutor/continue; "
        "do not classify it as verify_claim unless it explicitly asks whether the claim is right or correct. "
        "For a substantive declarative answer to the tutor, set needs_clarification=false and "
        "clarification_question=null even if the answer is incorrect or off target; the teaching pipeline will "
        "evaluate the answer and guide the learner within the current scenario. "
        "When the student asks what wording from the recent tutor message means, resolve names and pronouns "
        "from that message and use follow_up/continue without requesting clarification if the referent is present. "
        "A first question such as 'what is version control?' is new_topic, not requesting_support; "
        "reserve requesting_support for an explicit hint request or expressed confusion. "
        "When an original learning topic is supplied, interpret short follow-ups within that topic and keep "
        "retrieval searches connected to it. The chat's main topic is fixed: classify an explicit request to "
        "switch topics, or a clearly unrelated new concept question, as changing_topic so the application can "
        "direct the student to a new chat. Related subtopics, examples, and clarification questions remain "
        "within the original topic and are not changing_topic. "
        "Never invent a concept, claim, or intention absent from the message and recent history."
    )
    client = AsyncOpenAI(api_key=api_key, base_url=base_url)
    log_event(4, "classifier_llm_started", provider=provider, model=model)
    started = monotonic()
    response_format: dict[str, Any] = {
        "type": "json_schema",
        "json_schema": {
            "name": "course_message_classification",
            "strict": True,
            "schema": CLASSIFICATION_SCHEMA,
        },
    }
    request: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": (
                f"Original learning topic: {learning_topic or '(not set yet)'}\n\n"
                f"Recent conversation:\n{conversation}\n\nLatest message:\n{message}"
            )},
        ],
        "temperature": settings.CLASSIFIER_TEMPERATURE,
        "response_format": response_format,
    }
    request.update(settings.completion_token_parameters(provider, settings.CLASSIFIER_MAX_TOKENS))
    write_llm_request_snapshot("classifier", provider, request)
    response = await client.chat.completions.create(**request)
    raw = response.choices[0].message.content
    if not raw or not raw.strip():
        raise ValueError("Message classifier returned empty content.")
    latency_ms = round((monotonic() - started) * 1000)
    log_event(
        4, "classifier_llm_completed", provider=provider, model=model,
        latency_ms=latency_ms,
    )
    debug_preview("classifier_output", raw)
    classification = _validated_llm_classification(_json_object(raw), message, fallback)
    update_llm_request_snapshot(
        "classifier",
        raw_response=raw,
        parsed_output=asdict(classification),
        latency_ms=latency_ms,
    )
    return classification


async def classify_message(
    message: str, history: list[ChatMessage], learning_topic: str | None = None,
) -> MessageClassification:
    """Apply hard routing guards, then use an LLM for educational interpretation.

    The LLM may improve question type, concept, follow-up, and retrieval-query detection.
    It cannot override administrative or session-control rules, and malformed or
    unavailable model output falls back to deterministic behavior.
    """

    # Compute deterministic guards first. They remain available if the LLM
    # fails, returns malformed labels, or is not configured.
    fallback = _rule_classification(message, history)
    # Session commands are handled predictably; the model must not reinterpret
    # them as an ordinary topic question.
    if fallback.route == "session_control":
        return fallback
    try:
        result = await _classify_with_llm(message, history, fallback, learning_topic)
    except Exception as error:
        log_exception(4, "classifier_llm_failed", error, fallback="rules")
        return fallback

    # Preserve hard session-control boundaries after the model's output too.
    if SESSION_CONTROL_PATTERN.match(message.strip()):
        return fallback
    if result.route == "session_control":
        return replace(result, route=fallback.route, direct_answer=None)
    if fallback.route == "learning" and is_contextual_meaning_request(message, history):
        return replace(
            result, route="learning", conversation_state="follow_up",
            dialogue_status="requesting_support", conversation_action="continue",
            needs_clarification=False, clarification_question=None,
        )
    return result
