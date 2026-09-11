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
    success_feedback: str
    hint: str
    explanation: str


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
        success_feedback="You identified services the ATM provides.",
        hint="Think about cash and account information.",
        explanation="ATM services include actions such as withdrawing cash or checking a balance.",
    ),
    LessonStep(
        step_id="person_role",
        concept="external participant",
        prompt="**Who** performs those actions?",
        evidence_groups=((r"\bi\b", r"\bme\b", r"customer", r"user", r"person", r"cardholder", r"client"),),
        success_feedback="That identifies the person interacting with the system.",
        hint="Focus on the person standing at the machine.",
        explanation="The ATM customer performs those actions.",
    ),
    LessonStep(
        step_id="actor_label",
        concept="actor",
        prompt="In a system model, **what might we call** a role that interacts with the system?",
        evidence_groups=((r"actor", r"user"),),
        success_feedback="In use case diagrams, that external role is an **actor**.",
        hint="The term begins with 'a' and describes an external role.",
        explanation="A role that interacts with the modeled system is called an **actor**.",
    ),
    LessonStep(
        step_id="external_actor",
        concept="external system actor",
        prompt="**Why could** an external bank service also be modeled as an actor?",
        evidence_groups=(
            (r"yes", r"can", r"could", r"external", r"outside"),
            (r"interact", r"communicat", r"service", r"system", r"boundary"),
        ),
        success_feedback="Actors can be people or external systems outside the boundary.",
        hint="Actors are defined by interaction across the chosen system boundary.",
        explanation="An external system can be an actor when it interacts across the modeled boundary.",
    ),
    LessonStep(
        step_id="use_case_label",
        concept="use case",
        prompt="What might we call a user **goal or service**, such as withdrawing cash?",
        evidence_groups=((r"use case", r"goal", r"service", r"function"),),
        success_feedback="That system-provided goal is a **use case**.",
        hint="The name focuses on a user's goal, not an internal code function.",
        explanation="A service or goal the system provides to an actor is a **use case**.",
    ),
    LessonStep(
        step_id="association",
        concept="association",
        prompt="If actors mean who and use cases mean what, **how are they related**?",
        evidence_groups=((r"perform", r"participat", r"interact", r"connect", r"initiat", r"association", r"line"),),
        success_feedback="The line represents an **association** between actor and use case.",
        hint="Think about the line connecting the external role to the goal.",
        explanation="An association connects an actor to a use case it participates in.",
    ),
    LessonStep(
        step_id="use_case_boundary",
        concept="use cases inside boundary",
        prompt="**Where should use cases appear** relative to the system boundary?",
        evidence_groups=((r"inside", r"within", r"internal"),),
        success_feedback="Use cases belong inside the system boundary.",
        hint="Ask where the system's own behavior belongs.",
        explanation="Use cases are placed inside the system boundary because they belong to the modeled system.",
    ),
    LessonStep(
        step_id="actor_boundary",
        concept="actors outside boundary",
        prompt="**Where should actors appear** relative to that boundary?",
        evidence_groups=((r"outside", r"external"),),
        success_feedback="Actors remain outside the boundary they interact with.",
        hint="Ask whether the actor is part of the software itself.",
        explanation="Actors are placed outside because they interact with the modeled system from its environment.",
    ),
    LessonStep(
        step_id="include_relationship",
        concept="include relationship",
        prompt="Borrowing always checks availability. **Which UML relationship** represents that required behavior?",
        evidence_groups=((r"include", r"required", r"mandatory", r"always"),),
        success_feedback="Required reused behavior is modeled with **<<include>>**.",
        hint="**<<include>>** represents behavior that always occurs.",
        explanation="Use **<<include>>** when the included behavior is required by the base use case.",
    ),
    LessonStep(
        step_id="extend_relationship",
        concept="extend relationship",
        prompt="Two-factor authentication happens only sometimes. **Which relationship** represents that optional behavior?",
        evidence_groups=((r"extend", r"optional", r"conditional", r"sometimes"),),
        success_feedback="Optional conditional behavior is modeled with **<<extend>>**.",
        hint="**<<extend>>** represents optional behavior triggered under a condition.",
        explanation="Use **<<extend>>** when additional behavior occurs only under a condition.",
    ),
    LessonStep(
        step_id="library_transfer",
        concept="transfer",
        prompt="For a library system, **which actor and use case** could you identify?",
        evidence_groups=(
            (r"student", r"librarian", r"member", r"administrator", r"patron"),
            (r"borrow", r"return", r"search", r"reserve", r"register", r"inventory"),
        ),
        success_feedback="You transferred the model to a new domain.",
        hint="Try a role such as student and a goal involving books.",
        explanation="For example, a student actor can participate in the Borrow Book use case.",
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
        success_feedback="You connected actors, use cases, and the system boundary.",
        hint="Use who, what, and inside versus outside.",
        explanation="Actors stay outside, use cases stay inside, and associations connect them across the boundary.",
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


def _answer_with_next(feedback: str, next_prompt: str | None) -> str:
    if next_prompt:
        return f"{feedback}\n\n{next_prompt}"
    return f"{feedback}\n\nThe guided lesson is complete."


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
            answer=_answer_with_next(step.success_feedback, next_prompt),
            state={
                "lesson_id": LESSON_ID,
                "step_index": min(next_index, len(USE_CASE_STEPS) - 1),
                "attempts": 0,
                "mastered_components": mastered,
                "completed": completed,
            },
        )

    attempts += 1
    if attempts < 2:
        return GuidedTurn(
            answer=f"{step.hint}\n\n{step.prompt}",
            state={
                "lesson_id": LESSON_ID,
                "step_index": step_index,
                "attempts": attempts,
                "mastered_components": mastered,
                "completed": False,
            },
        )

    next_index = step_index + 1
    completed = next_index >= len(USE_CASE_STEPS)
    next_prompt = None if completed else USE_CASE_STEPS[next_index].prompt
    return GuidedTurn(
        answer=_answer_with_next(step.explanation, next_prompt),
        state={
            "lesson_id": LESSON_ID,
            "step_index": min(next_index, len(USE_CASE_STEPS) - 1),
            "attempts": 0,
            "mastered_components": mastered,
            "completed": completed,
        },
    )
