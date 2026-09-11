from __future__ import annotations

import re
from dataclasses import dataclass

from app.schemas import Source


LESSON_ID = "use_case_diagrams_v1"
LESSON_TOPIC_PATTERN = re.compile(r"\buse case(?:s)?(?: diagram(?:s)?)?\b", re.IGNORECASE)
LESSON_LOGISTICS_PATTERN = re.compile(
    r"\b(?:assignment|rubric|deadline|due date|submission|submit|points?|grade)\b",
    re.IGNORECASE,
)
LESSON_EXIT_PATTERN = re.compile(
    r"\b(?:stop|end|leave|pause|quit)\s+(?:the\s+)?(?:lesson|tutorial|practice)\b",
    re.IGNORECASE,
)
NEW_TOPIC_PATTERN = re.compile(
    r"^(?:what is|what are|define|explain|tell me about|help me understand)\b",
    re.IGNORECASE,
)
RELATED_TOPIC_PATTERN = re.compile(
    r"\b(?:use case|actor|association|system boundary|include|extend|atm|library)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class LessonStep:
    step_id: str
    concept: str
    prompt: str
    evidence_groups: tuple[tuple[str, ...], ...]
    support_questions: tuple[str, str]


@dataclass(frozen=True)
class GuidedTurn:
    answer: str
    state: dict[str, object]


USE_CASE_STEPS = (
    LessonStep(
        step_id="atm_actions",
        concept="system services",
        prompt="Think about using an ATM. **What actions** might you perform?",
        evidence_groups=((r"withdraw", r"deposit", r"balance", r"cash", r"transfer", r"account"),),
        support_questions=(
            "What is one task involving cash or your account that you might perform at an ATM?",
            "When you approach an ATM, what result are you trying to obtain?",
        ),
    ),
    LessonStep(
        step_id="person_role",
        concept="external participant",
        prompt="**Who** performs those actions?",
        evidence_groups=((r"\bi\b", r"\bme\b", r"customer", r"user", r"person", r"cardholder", r"client"),),
        support_questions=(
            "Who initiates a withdrawal before the ATM processes it?",
            "Is the action initiated by the machine or by someone using it?",
        ),
    ),
    LessonStep(
        step_id="actor_label",
        concept="actor",
        prompt="In a system model, **what might we call** a role that interacts with the system?",
        evidence_groups=((r"actor", r"user"),),
        support_questions=(
            "What word might describe an external role that acts on a system?",
            "Which term suits an external participant: attribute, actor, or algorithm?",
        ),
    ),
    LessonStep(
        step_id="external_actor",
        concept="external system actor",
        prompt="**Why could** an external bank service also be modeled as an actor?",
        evidence_groups=(
            (r"yes", r"can", r"could", r"external", r"outside"),
            (r"interact", r"communicat", r"service", r"system", r"boundary"),
        ),
        support_questions=(
            "Does something need to be human to interact across a system boundary?",
            "What matters more here: being human or interacting from outside the boundary?",
        ),
    ),
    LessonStep(
        step_id="use_case_label",
        concept="use case",
        prompt="What might we call a user **goal or service**, such as withdrawing cash?",
        evidence_groups=((r"use case", r"goal", r"service", r"function"),),
        support_questions=(
            "Does withdrawing cash describe an external role or a goal the system provides?",
            "Which term describes what an actor wants the system to accomplish?",
        ),
    ),
    LessonStep(
        step_id="association",
        concept="association",
        prompt="If actors mean who and use cases mean what, **how are they related**?",
        evidence_groups=((r"perform", r"participat", r"interact", r"connect", r"initiat", r"association", r"line"),),
        support_questions=(
            "What could the line between an actor and a use case communicate?",
            "Does that line represent participation, inheritance, or physical distance?",
        ),
    ),
    LessonStep(
        step_id="use_case_boundary",
        concept="use cases inside boundary",
        prompt="**Where should use cases appear** relative to the system boundary?",
        evidence_groups=((r"inside", r"within", r"internal"),),
        support_questions=(
            "Do use cases describe behavior belonging to the system or its environment?",
            "Which side of the boundary should contain behavior the system provides?",
        ),
    ),
    LessonStep(
        step_id="actor_boundary",
        concept="actors outside boundary",
        prompt="**Where should actors appear** relative to that boundary?",
        evidence_groups=((r"outside", r"external"),),
        support_questions=(
            "Is an actor part of the modeled system or something interacting with it?",
            "Which side represents entities from the system's environment?",
        ),
    ),
    LessonStep(
        step_id="include_relationship",
        concept="include relationship",
        prompt="Borrowing always checks availability. **Which UML relationship** represents that required behavior?",
        evidence_groups=((r"include", r"required", r"mandatory", r"always"),),
        support_questions=(
            "Is checking availability required every time borrowing occurs?",
            "Which relationship represents behavior that must always occur?",
        ),
    ),
    LessonStep(
        step_id="extend_relationship",
        concept="extend relationship",
        prompt="Two-factor authentication happens only sometimes. **Which relationship** represents that optional behavior?",
        evidence_groups=((r"extend", r"optional", r"conditional", r"sometimes"),),
        support_questions=(
            "Is two-factor authentication required every time or only under some conditions?",
            "Which relationship represents behavior added only under a condition?",
        ),
    ),
    LessonStep(
        step_id="library_transfer",
        concept="transfer",
        prompt="For a library system, **which actor and use case** could you identify?",
        evidence_groups=(
            (r"student", r"librarian", r"member", r"administrator", r"patron"),
            (r"borrow", r"return", r"search", r"reserve", r"register", r"inventory"),
        ),
        support_questions=(
            "Who might approach a library system with a goal involving a book?",
            "What book-related result might that person ask the system to provide?",
        ),
    ),
    LessonStep(
        step_id="reflection",
        concept="integrated model",
        prompt="In one sentence, **how do actors, use cases, and the system boundary fit together**?",
        evidence_groups=(
            (r"actor",),
            (r"use case",),
            (r"boundary", r"inside", r"outside"),
        ),
        support_questions=(
            "Which element represents who, and which represents what the system provides?",
            "Where would you place each element relative to the system boundary?",
        ),
    ),
)


def matches_use_case_lesson(message: str) -> bool:
    return bool(LESSON_TOPIC_PATTERN.search(message) and not LESSON_LOGISTICS_PATTERN.search(message))


def lesson_exit_requested(message: str) -> bool:
    return bool(LESSON_EXIT_PATTERN.search(message))


def unrelated_new_topic(message: str) -> bool:
    return bool(NEW_TOPIC_PATTERN.search(message) and not RELATED_TOPIC_PATTERN.search(message))


def lesson_search_query(message: str) -> str:
    return (
        "use case diagrams actors use cases associations system boundary include extend "
        f"{message}"
    )


def sources_support_use_case_lesson(sources: list[Source]) -> bool:
    for source in sources:
        context = " ".join(f"{source.title} {source.text}".lower().split())
        explicitly_names_diagram = bool(
            re.search(r"\buse case(?:s)? diagram(?:s)?\b", context)
        )
        teaches_core_notation = (
            "use case" in context
            and "actor" in context
            and ("system boundary" in context or "association" in context)
        )
        if explicitly_names_diagram or teaches_core_notation:
            return True
    return False


def initial_lesson_state() -> dict[str, object]:
    return {
        "lesson_id": LESSON_ID,
        "step_index": 0,
        "attempts": 0,
        "mastered_components": [],
        "completed": False,
    }


def _matches_step_evidence(message: str, step: LessonStep) -> bool:
    normalized = " ".join(message.lower().split())
    return all(
        any(re.search(pattern, normalized) for pattern in group)
        for group in step.evidence_groups
    )


def start_use_case_lesson() -> GuidedTurn:
    state = initial_lesson_state()
    return GuidedTurn(answer=USE_CASE_STEPS[0].prompt, state=state)


def advance_use_case_lesson(message: str, state: dict[str, object]) -> GuidedTurn:
    step_index = max(0, min(int(state.get("step_index", 0)), len(USE_CASE_STEPS) - 1))
    attempts = max(0, int(state.get("attempts", 0)))
    mastered = [str(item) for item in state.get("mastered_components", [])]
    step = USE_CASE_STEPS[step_index]

    if _matches_step_evidence(message, step):
        if step.step_id not in mastered:
            mastered.append(step.step_id)
        next_index = step_index + 1
        completed = next_index >= len(USE_CASE_STEPS)
        next_prompt = None if completed else USE_CASE_STEPS[next_index].prompt
        return GuidedTurn(
            answer=next_prompt or "The guided lesson is complete.",
            state={
                "lesson_id": LESSON_ID,
                "step_index": min(next_index, len(USE_CASE_STEPS) - 1),
                "attempts": 0,
                "mastered_components": mastered,
                "completed": completed,
            },
        )

    attempts += 1
    if attempts == 1:
        support_question = step.support_questions[0]
    elif attempts == 2:
        support_question = step.support_questions[1]
    else:
        support_question = "Which word or relationship in this question feels unclear?"
    return GuidedTurn(
        answer=support_question,
        state={
            "lesson_id": LESSON_ID,
            "step_index": step_index,
            "attempts": attempts,
            "mastered_components": mastered,
            "completed": False,
        },
    )
