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
HINT_REQUEST_PATTERN = re.compile(
    r"\b(?:hint|small clue|give me a clue|nudge me|help me start)\b",
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
    r"^(?:(?:can|could|would)\s+you\s+)?(?:please\s+)?"
    r"(?:what is|what are|define|explain|describe|tell me about|help me understand)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class SocraticDecision:
    mode: str
    student_state: str
    strategy: str
    instruction: str
    disclosure_level: int = 0


DIRECT_DECISION = SocraticDecision(
    mode="direct",
    student_state="information_request",
    strategy="grounded_explanation",
    instruction=(
        "Answer the request directly and concisely from the retrieved context. "
        "Do not force a Socratic question into administrative or assignment-logistics information."
    ),
    disclosure_level=4,
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
    if DIRECT_INFORMATION_PATTERN.search(clean_message):
        return DIRECT_DECISION

    question_turns = _recent_socratic_questions(history)

    if DIRECT_REQUEST_PATTERN.search(clean_message):
        return SocraticDecision(
            mode="socratic",
            student_state="direct_answer_requested",
            strategy="return_to_reasoning",
            instruction=(
                "Keep the course-content interaction Socratic. Ask exactly one accessible question that invites "
                "the learner's best current idea without providing the answer."
            ),
        )

    if HINT_REQUEST_PATTERN.search(clean_message):
        return SocraticDecision(
            mode="socratic",
            student_state="hint_requested",
            strategy="narrow_guiding_question",
            instruction=(
                "Do not provide a hint as a statement. Ask exactly one narrower question that breaks the current "
                "reasoning task into a smaller step."
            ),
        )

    if NEW_CONCEPT_PATTERN.search(clean_message):
        return SocraticDecision(
            mode="socratic",
            student_state="prior_knowledge_unknown",
            strategy="diagnostic_recall",
            instruction=(
                "Do not lecture or reveal the complete answer yet. Ask exactly one accessible diagnostic question "
                "that connects the target concept to the learner's prior knowledge or a simple example."
            ),
            disclosure_level=0,
        )

    if UNCERTAINTY_PATTERN.search(clean_message):
        if question_turns >= 2:
            return SocraticDecision(
                mode="socratic",
                student_state="repeated_difficulty",
                strategy="decompose_or_offer_choices",
                instruction=(
                    "Do not explain the answer. Ask exactly one simple prerequisite, concrete scenario, comparison, "
                    "or choice-based question that makes the next reasoning step easier."
                ),
            )
        return SocraticDecision(
            mode="socratic",
            student_state="uncertain",
            strategy="narrow_guiding_question",
            instruction=(
                "Do not provide a hint as a statement. Rephrase the task as exactly one simpler, narrower, "
                "grounded question."
            ),
        )

    if MISCONCEPTION_PATTERN.search(clean_message):
        return SocraticDecision(
            mode="socratic",
            student_state="possible_misconception",
            strategy="guided_comparison",
            instruction=(
                "Ask exactly one guided-comparison question that helps distinguish the two relevant concepts. "
                "Do not first state whether the learner is correct."
            ),
        )

    if REASONING_PATTERN.search(clean_message):
        return SocraticDecision(
            mode="socratic",
            student_state="reasoning_in_progress",
            strategy="probe_reasoning",
            instruction=(
                "Ask exactly one question about the learner's evidence, assumption, consequence, or applicability."
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
                    "Ask exactly one reflection question about how the learner's understanding changed or what they "
                    "would revise. Do not summarize their learning for them."
                ),
            )
        if question_turns == 3:
            return SocraticDecision(
                mode="socratic",
                student_state="ready_to_synthesize",
                strategy="synthesize_understanding",
                instruction=(
                    "Ask exactly one question that requires the learner to combine relevant concepts or evidence "
                    "into an overall explanation."
                ),
            )
        if question_turns == 2:
            return SocraticDecision(
                mode="socratic",
                student_state="understanding_developing",
                strategy="examine_limitation",
                instruction=(
                    "Ask exactly one question about a limitation, alternative factor, or condition that could change "
                    "the learner's conclusion."
                ),
            )
        return SocraticDecision(
            mode="socratic",
            student_state="response_to_prompt",
            strategy="justify_or_refine",
            instruction=(
                "Assess the response against the retrieved context internally, then ask exactly one question that "
                "helps the learner justify or refine it. Do not state the assessment."
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
        disclosure_level=0,
    )


def _disclosure_instruction(level: int) -> str:
    if level >= 4:
        return "Answer directly and concisely from the retrieved context."
    return (
        "Question-only mode: output exactly one question of at most 25 words. Do not output an explanation, hint, "
        "answer, evaluation, praise, summary, or other statement before or after it."
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
        f"{decision.instruction} {_disclosure_instruction(decision.disclosure_level)} Ask only one question. "
        "Use the retrieved learning context and the learner's latest response to choose the question, but do not "
        "reveal the retrieved answer. When natural, bold only a short reasoning cue at the start "
        "of the question, such as '**What evidence**', '**Which assumption**', or '**What consequence**'. "
        f"Never invent course facts beyond the retrieved context. {emphasis_instruction}"
    )


def _target_concept(message: str) -> str:
    normalized = " ".join(message.strip().rstrip("?.!").split())
    patterns = [
        r"^(?:(?:can|could|would)\s+you\s+)?(?:please\s+)?"
        r"(?:explain|describe|tell me)\s+(?:what|who)\s+(.+?)\s+(?:is|are|means?)$",
        r"^(?:(?:can|could|would)\s+you\s+)?(?:please\s+)?"
        r"(?:what is|what are|define|explain|describe)\s+(.+)$",
        r"^(?:(?:can|could|would)\s+you\s+)?(?:please\s+)?"
        r"(?:tell me about|help me understand)\s+(.+)$",
    ]
    target = normalized
    for pattern in patterns:
        match = re.match(pattern, normalized, re.IGNORECASE)
        if match:
            target = match.group(1)
            break
    target = re.split(r"\s+(?:in|from|according to)\s+(?:the|this|our)\b", target, maxsplit=1, flags=re.IGNORECASE)[0]
    return target.strip() or "this concept"


def _comparison_targets(message: str) -> tuple[str, str] | None:
    normalized = " ".join(message.strip().rstrip("?.!").split())
    match = re.search(r"\bdifference between (.+?) and (.+)$", normalized, re.IGNORECASE)
    if not match:
        return None
    return match.group(1).strip(), match.group(2).strip()


def socratic_fallback_question(message: str, decision: SocraticDecision) -> str:
    target = _target_concept(message)
    if decision.strategy == "diagnostic_recall":
        comparison = _comparison_targets(message)
        if comparison:
            first, second = comparison
            question = f"Before we compare **{first}** and **{second}**, what difference comes to mind first?"
        else:
            question = f"Before we define **{target}**, what comes to mind when you hear that term?"
        if _word_count(question) <= 25:
            return question
        return "What do you already understand about **this concept**?"
    if decision.strategy == "guided_comparison":
        return "What distinction between the two ideas might change your conclusion?"
    if decision.strategy == "narrow_guiding_question":
        return "What smaller part of **this idea** could you reason through first?"
    if decision.strategy == "return_to_reasoning":
        return "What is your best current idea, even if you are uncertain?"
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
    if decision.strategy == "decompose_or_offer_choices":
        return "Which part should we examine first: the main concept, its purpose, or an example?"
    return f"How would you apply {target} in a new example?"


def _word_count(text: str) -> int:
    return len(re.findall(r"\b[\w'-]+\b", text))


def _split_feedback_and_question(answer: str) -> tuple[str, str]:
    question_end = answer.find("?") + 1
    through_question = answer[:question_end].strip()
    boundaries = [
        (through_question.rfind("\n"), 1, False),
        (through_question.rfind(". "), 2, True),
        (through_question.rfind("! "), 2, True),
    ]
    position, width, includes_punctuation = max(boundaries, key=lambda item: item[0])
    if position < 0:
        return "", through_question
    feedback_end = position + 1 if includes_punctuation else position
    feedback = through_question[:feedback_end].strip()
    question = through_question[position + width:].strip()
    return feedback, question


def _standalone_diagnostic_question(answer: str) -> str | None:
    """Return a safe model-authored opening question, or None when it needs replacement."""
    question = answer.strip(" -*\t\n")
    if question.count("?") != 1 or not question.endswith("?"):
        return None
    if not 3 <= _word_count(question) <= 25:
        return None
    if re.search(r"[.!]\s+", question[:-1]):
        return None
    if re.search(
        r"\b(?:these|those|such|the above|this idea|that idea|this information|that information)\b",
        question,
        re.IGNORECASE,
    ):
        return None
    return question


def enforce_socratic_response(answer: str, message: str, decision: SocraticDecision) -> str:
    """Guarantee that a Socratic turn contains exactly one focused question."""
    clean_answer = answer.strip()
    if decision.mode == "direct":
        return clean_answer

    question_count = clean_answer.count("?")
    if decision.strategy == "diagnostic_recall":
        # Preserve a concise model-authored diagnostic when it stands alone.
        # Replace lectures, multiple questions, and context-dependent questions
        # with a concept-aware fallback that reveals no course facts.
        return _standalone_diagnostic_question(clean_answer) or socratic_fallback_question(message, decision)

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
        if 3 <= _word_count(question_only) <= 25 and not depends_on_removed_context:
            return question_only
        return socratic_fallback_question(message, decision)

    if question_count == 0:
        clean_answer = socratic_fallback_question(message, decision)
    elif question_count > 1:
        # Keep only the first complete question so the learner has one clear task.
        clean_answer = clean_answer.split("?", 1)[0].strip() + "?"

    feedback, question = _split_feedback_and_question(clean_answer)
    del feedback
    depends_on_removed_context = re.search(
        r"\b(?:these|those|such|the above|this information|that information)\b",
        question,
        re.IGNORECASE,
    )
    if not question or _word_count(question) > 25 or depends_on_removed_context:
        question = socratic_fallback_question(message, decision)
    return question
