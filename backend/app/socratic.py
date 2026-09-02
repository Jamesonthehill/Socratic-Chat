from __future__ import annotations

import re
from dataclasses import dataclass

from app.schemas import ChatMessage, Source


DIRECT_INFORMATION_PATTERN = re.compile(
    r"\b(?:assignment|projects?|rubric|deadline|due date|submission|submit|points?|grade|"
    r"office hours?|schedule|syllabus|uploaded files?|documents?)\b",
    re.IGNORECASE,
)
DIRECT_REQUEST_PATTERN = re.compile(
    r"\b(?:just tell me|give me the answer|answer directly|no questions?|"
    r"stop asking|explain it directly)\b",
    re.IGNORECASE,
)
UNCERTAINTY_PATTERN = re.compile(
    r"\b(?:i (?:still )?(?:do not|don't) know|not sure|unsure|confused|no idea|i'm stuck|i am stuck)\b",
    re.IGNORECASE,
)
MISCONCEPTION_PATTERN = re.compile(
    r"\b(?:i thought|isn't it|is it not|but i think|shouldn't|cannot be|can't be)\b",
    re.IGNORECASE,
)
REASONING_PATTERN = re.compile(r"\b(?:because|therefore|since|which means|so that)\b", re.IGNORECASE)
NEW_CONCEPT_PATTERN = re.compile(
    r"^(?:what is|what are|define|explain|tell me about|help me understand)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class SocraticDecision:
    mode: str
    student_state: str
    strategy: str
    instruction: str


DIRECT_DECISION = SocraticDecision(
    mode="direct",
    student_state="information_request",
    strategy="grounded_explanation",
    instruction=(
        "Answer the request directly and concisely from the retrieved context. "
        "Do not force a Socratic question into administrative or assignment-logistics information."
    ),
)


def _recent_socratic_questions(history: list[ChatMessage]) -> int:
    recent_history = history[-10:]
    for index in range(len(recent_history) - 1, -1, -1):
        message = recent_history[index]
        if message.role == "assistant" and message.content.lstrip().startswith("Before we define"):
            recent_history = recent_history[index:]
            break
    return sum(
        1
        for message in recent_history
        if message.role == "assistant" and message.content.rstrip().endswith("?")
    )


def choose_socratic_strategy(
    message: str,
    history: list[ChatMessage],
    sources: list[Source],
) -> SocraticDecision:
    """Choose one explainable teaching action after document retrieval."""
    clean_message = " ".join(message.strip().split())
    if not sources:
        return DIRECT_DECISION
    if DIRECT_INFORMATION_PATTERN.search(clean_message) or DIRECT_REQUEST_PATTERN.search(clean_message):
        return DIRECT_DECISION

    if NEW_CONCEPT_PATTERN.search(clean_message):
        return SocraticDecision(
            mode="socratic",
            student_state="prior_knowledge_unknown",
            strategy="diagnostic_recall",
            instruction=(
                "Do not lecture or reveal the complete answer yet. Ask exactly one accessible diagnostic question "
                "that connects the target concept to the learner's prior knowledge or a simple example."
            ),
        )

    question_turns = _recent_socratic_questions(history)

    if UNCERTAINTY_PATTERN.search(clean_message):
        if question_turns >= 2:
            return SocraticDecision(
                mode="socratic",
                student_state="repeated_difficulty",
                strategy="explain_then_check",
                instruction=(
                    "Give a concise, evidence-grounded explanation now. Then ask exactly one short application "
                    "question that checks understanding. Do not withhold the explanation again."
                ),
            )
        return SocraticDecision(
            mode="socratic",
            student_state="uncertain",
            strategy="hint_then_question",
            instruction=(
                "Give one small hint grounded in the retrieved context, without revealing the entire answer. "
                "Then ask exactly one focused question that uses the hint."
            ),
        )

    if MISCONCEPTION_PATTERN.search(clean_message):
        return SocraticDecision(
            mode="socratic",
            student_state="possible_misconception",
            strategy="guided_comparison",
            instruction=(
                "Briefly acknowledge the learner's idea without calling it correct or incorrect. Ask exactly one "
                "guided-comparison question that helps distinguish the two relevant concepts."
            ),
        )

    if REASONING_PATTERN.search(clean_message):
        return SocraticDecision(
            mode="socratic",
            student_state="reasoning_in_progress",
            strategy="probe_reasoning",
            instruction=(
                "Refer briefly to the learner's reasoning and ask exactly one question about its evidence, "
                "assumption, consequence, or applicability."
            ),
        )

    latest_assistant = next((item for item in reversed(history) if item.role == "assistant"), None)
    if latest_assistant and latest_assistant.content.rstrip().endswith("?"):
        if question_turns >= 4:
            return SocraticDecision(
                mode="socratic",
                student_state="ready_to_reflect",
                strategy="reflect_on_learning",
                instruction=(
                    "Give one specific, neutral observation about the learner's progress. Then ask exactly one "
                    "reflection question about how their understanding changed or what they would revise."
                ),
            )
        if question_turns == 3:
            return SocraticDecision(
                mode="socratic",
                student_state="ready_to_synthesize",
                strategy="synthesize_understanding",
                instruction=(
                    "Give specific, neutral feedback in one short sentence. Then ask exactly one question that "
                    "requires the learner to combine relevant concepts or evidence into an overall explanation."
                ),
            )
        if question_turns == 2:
            return SocraticDecision(
                mode="socratic",
                student_state="understanding_developing",
                strategy="examine_limitation",
                instruction=(
                    "Give specific, neutral feedback in one short sentence. Then ask exactly one question about "
                    "a limitation, alternative factor, or condition that could change the learner's conclusion."
                ),
            )
        return SocraticDecision(
            mode="socratic",
            student_state="response_to_prompt",
            strategy="justify_or_refine",
            instruction=(
                "Assess the response against the retrieved context. Give specific, neutral feedback in one short "
                "sentence, then ask exactly one question that helps the learner justify or refine the response."
            ),
        )

    return SocraticDecision(
        mode="socratic",
        student_state="prior_knowledge_unknown",
        strategy="diagnostic_recall",
        instruction=(
            "Do not lecture or reveal the complete answer yet. Ask exactly one accessible diagnostic question "
            "that connects the target concept to the learner's prior knowledge or a simple example."
        ),
    )


def socratic_system_instruction(decision: SocraticDecision) -> str:
    emphasis_instruction = (
        "Use Markdown bold for one to three short, important concept terms when emphasis helps the learner. "
        "Do not bold complete sentences or routine conversational words."
    )
    if decision.mode == "direct":
        return f"{decision.instruction} {emphasis_instruction}"
    return (
        f"Socratic teaching state: {decision.student_state}. Strategy: {decision.strategy}. "
        f"{decision.instruction} Keep the whole response under three sentences. Ask only one question. "
        "Anchor feedback and questions in the retrieved learning context and the learner's latest response. "
        "Put the final question in its own paragraph. When natural, bold only a short reasoning cue at the start "
        "of the question, such as '**What evidence**', '**Which assumption**', or '**What consequence**'. "
        "Use specific feedback instead of generic praise such as 'Excellent' or 'Good job'. "
        f"Never invent course facts beyond the retrieved context. {emphasis_instruction}"
    )


def _target_concept(message: str) -> str:
    normalized = " ".join(message.strip().rstrip("?.!").split())
    patterns = [
        r"^(?:what is|what are|define|explain)\s+(.+)$",
        r"^(?:tell me about|help me understand)\s+(.+)$",
    ]
    target = normalized
    for pattern in patterns:
        match = re.match(pattern, normalized, re.IGNORECASE)
        if match:
            target = match.group(1)
            break
    target = re.split(r"\s+(?:in|from|according to)\s+(?:the|this|our)\b", target, maxsplit=1, flags=re.IGNORECASE)[0]
    return target.strip() or "this concept"


def socratic_fallback_question(message: str, decision: SocraticDecision) -> str:
    target = _target_concept(message)
    if decision.strategy == "diagnostic_recall":
        return f"Before we define **{target}**, what comes to mind when you hear that term?"
    if decision.strategy == "guided_comparison":
        return "What distinction between the two ideas might change your conclusion?"
    if decision.strategy == "hint_then_question":
        return "Which detail in the retrieved material seems most useful for working this out?"
    if decision.strategy == "probe_reasoning":
        return "What evidence from the retrieved material supports that reasoning?"
    if decision.strategy == "justify_or_refine":
        return "How would you justify or refine that response using the retrieved material?"
    if decision.strategy == "examine_limitation":
        return "**What limitation or alternative factor** might change that conclusion?"
    if decision.strategy == "synthesize_understanding":
        return "**How can you combine** the relevant concepts and evidence into one explanation?"
    if decision.strategy == "reflect_on_learning":
        return "**How has your understanding changed**, and what would you revise in your first response?"
    return f"How would you apply {target} in a new example?"


def enforce_socratic_response(answer: str, message: str, decision: SocraticDecision) -> str:
    """Guarantee that a Socratic turn contains exactly one focused question."""
    clean_answer = answer.strip()
    if decision.mode == "direct":
        return clean_answer

    question_count = clean_answer.count("?")
    if decision.strategy == "diagnostic_recall":
        # The opening turn is a prior-knowledge check. Never allow a model
        # definition or summary to precede it, even when the model also asks a
        # valid question afterward.
        return socratic_fallback_question(message, decision)

    strict_discovery = decision.strategy in {"diagnostic_recall", "guided_comparison"}
    if strict_discovery and question_count:
        # Early discovery must not reveal the answer before asking the learner
        # to reason. Retain only the first question sentence, discarding any
        # model-generated definition, summary, or bullet list before it.
        question_end = clean_answer.index("?") + 1
        question_start = max(
            clean_answer.rfind(".", 0, question_end),
            clean_answer.rfind("!", 0, question_end),
            clean_answer.rfind("\n", 0, question_end),
        ) + 1
        question_only = clean_answer[question_start:question_end].strip(" -*\t\n")
        depends_on_removed_context = re.search(
            r"\b(?:these|those|such|the above|this idea|that idea)\b",
            question_only,
            re.IGNORECASE,
        )
        if 3 <= len(question_only.split()) <= 30 and not depends_on_removed_context:
            return question_only
        return socratic_fallback_question(message, decision)

    if question_count == 1:
        return clean_answer
    if question_count == 0:
        fallback = socratic_fallback_question(message, decision)
        if decision.strategy == "explain_then_check" and clean_answer:
            return f"{clean_answer}\n\n{fallback}"
        return fallback

    # Keep only the first complete question so the learner has one clear task.
    return clean_answer.split("?", 1)[0].strip() + "?"
