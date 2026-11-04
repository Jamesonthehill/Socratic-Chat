"""Provider-free checks for source ownership in saved tutor messages."""

from platform_app import engines
from platform_app.routes import apply_state
from app.classifier import _classification_from_observation
from app.schemas import ChatMessage


def test_apply_state_keeps_retrieved_sources_on_the_reply_that_used_them():
    previous_source = {"chunk_id": "menu-1", "title": "Menu.pdf", "text": "Choose a size."}
    current_source = {"chunk_id": "payment-1", "title": "Payment.pdf", "text": "Insert coins."}
    attempt = {
        "messages": [{"role": "assistant", "content": "Which size?", "sources": [previous_source]}],
        "engine_state": {},
        "status": "in_progress",
    }

    apply_state(attempt, {"reply": "How will you pay?", "sources": [current_source],
                          "socratic": {"next_thinking_step": "How will you pay?"}}, "small")

    assert attempt["messages"][0]["sources"] == [previous_source]
    assert attempt["messages"][1] == {"role": "user", "content": "small"}
    assert attempt["messages"][2]["sources"] == [current_source]
    assert attempt["messages"][2]["next_thinking_step"] == "How will you pay?"


def test_question_inside_a_code_example_does_not_replace_the_current_question():
    answer = "For example, write `print(What would you like? (small/ medium/ large/ off/ report))`."
    assert engines._next_thinking_step(answer) == ""

    class Classification:
        target_concepts = ()
        target = ""
        conversation_action = "continue"

    state = {"next_thinking_step": "What prompt would you show for all five choices?"}
    result = engines._socratic_result(answer, [], state, Classification())
    assert result["socratic"]["next_thinking_step"] == "What prompt would you show for all five choices?"


def test_acknowledgement_only_clarifies_an_actual_open_tutor_question():
    classification = _classification_from_observation(message_role="acknowledgement")
    open_question = [ChatMessage(role="assistant", content="What are the five menu choices?")]
    closing_reply = [ChatMessage(role="assistant", content="Take your time. I'm here when you're ready.")]
    stale_state = {"next_thinking_step": "How would you apply this to the assignment?", "conversation_status": "paused"}

    assert engines._clarify_unanswered_acknowledgement("ok", open_question, stale_state, classification).needs_clarification
    assert engines._clarify_unanswered_acknowledgement("ok", closing_reply, stale_state, classification) is classification


def test_soft_close_does_not_create_a_generic_thinking_step():
    class Classification:
        target_concepts = ()
        target = ""
        conversation_action = "soft_close"

    state = {"next_thinking_step": "What are the five menu choices?"}
    result = engines._socratic_result("Take your time. I'm here when you're ready.", [], state, Classification())
    assert result["socratic"]["next_thinking_step"] == ""
