from datetime import datetime, timedelta, timezone
from copy import deepcopy
from platform_app.step_metrics import track


def test_question_counts_and_transition_survive_saved_state():
    start = datetime(2026, 11, 11, tzinfo=timezone.utc)
    state = {"learning_step_index": 0, "phase": "teaching"}
    track(state, now=start)
    saved = deepcopy(state)
    state["message_role"] = "learning_question"
    track(state, previous=saved, student_message=True, now=start + timedelta(seconds=20))
    state["message_role"] = "student_answer"
    track(state, student_message=True, now=start + timedelta(seconds=40))
    previous = deepcopy(state)
    state["learning_step_index"] = 1
    track(state, previous=previous, now=start + timedelta(seconds=60))
    assert state["step_metrics"]["0"]["elapsed_seconds"] == 60
    assert state["step_metrics"]["0"]["student_questions"] == 1
    assert state["step_metrics"]["0"]["student_messages"] == 2
    assert state["step_metrics"]["1"]["student_questions"] == 0
    state["phase"] = "ready_to_submit"
    track(state, now=start + timedelta(seconds=90))
    assert state["step_metrics"]["1"]["elapsed_seconds"] == 30
    track(state, now=start + timedelta(seconds=150))
    assert state["step_metrics"]["1"]["elapsed_seconds"] == 30


def test_basic_chat_has_no_step_metrics():
    state = {"phase": "teaching"}
    track(state, student_message=True)
    assert "step_metrics" not in state
