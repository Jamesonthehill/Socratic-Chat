"""Hidden per-step timing and student question counts stored with each attempt."""
from datetime import datetime, timezone

QUESTION_ROLES = {"learning_question", "follow_up", "confirmation_request", "direct_answer_request"}


def track(state, *, previous=None, student_message=False, now=None):
    if "learning_step_index" not in state:
        return
    now = now or datetime.now(timezone.utc)
    metrics = dict((previous or state).get("step_metrics") or {})
    index = str(state["learning_step_index"])
    previous_index = str((previous or state).get("learning_step_index", index))
    if previous_index != index:
        finish(metrics.get(previous_index), now)
    current = dict(metrics.get(index) or {})
    if not current:
        current = {
            "started_at": now.isoformat(), "ended_at": None,
            "elapsed_seconds": 0, "student_messages": 0, "student_questions": 0,
        }
    if student_message and not current["ended_at"]:
        current["student_messages"] += 1
        current["student_questions"] += int(state.get("message_role") in QUESTION_ROLES)
    metrics[index] = current
    if state.get("phase") in {"ready_to_submit", "completed"}:
        finish(current, now)
    elif not current["ended_at"]:
        current["elapsed_seconds"] = elapsed(current, now)
    state["step_metrics"] = metrics


def elapsed(metric, now):
    return max(0, round((now - datetime.fromisoformat(metric["started_at"])).total_seconds()))


def finish(metric, now):
    if metric and not metric.get("ended_at"):
        metric["elapsed_seconds"] = elapsed(metric, now)
        metric["ended_at"] = now.isoformat()
