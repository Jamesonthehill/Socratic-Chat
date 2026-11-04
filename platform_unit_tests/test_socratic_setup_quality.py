"""Regression coverage for generated scenes that reveal the lesson too early."""
import asyncio
import json
from types import SimpleNamespace

from platform_app import socratic_setup


def test_setup_retries_when_a_scene_explains_the_answer(monkeypatch):
    source = "[chunk_id=source-1] The team reviews feedback and adapts its plan."
    base_step = {
        "title": "Review feedback",
        "goal": "Decide how the team responds to user feedback.",
        "question": "What should the team do with the feedback?",
        "evidence_quote": "The team reviews feedback and adapts its plan.",
        "source_chunk_id": "source-1",
    }
    scene = "Students say the signup form is hard to use on a phone. The team has to decide what to examine next."
    first = {
        "opening_prompt": "What should the team examine?",
        "student_instructions": "Discuss the feedback with your tutor.",
        "learning_steps": [
            {**base_step, "scenario": scene + " This illustrates adaptation."},
            {**base_step, "title": "Choose a change", "scenario": scene},
        ],
        "source_chunk_ids": ["source-1"],
    }
    improved = {**first, "learning_steps": [
        {**base_step, "scenario": scene},
        first["learning_steps"][1],
    ]}
    calls = []
    requests = []

    async def complete(_key, _url, request):
        requests.append(request.copy())
        calls.append([message["content"] for message in request["messages"]])
        payload = first if len(calls) == 1 else improved
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(payload)))])

    async def checks(draft, *_args):
        return draft

    monkeypatch.setattr(socratic_setup.settings, "llm_client_config", lambda _purpose: (
        "Ollama", "test", "http://localhost", "test-model",
    ))
    monkeypatch.setattr(socratic_setup, "selected_evidence", lambda _files: (
        f'<file name="lesson.pdf">\n{source}\n</file>', {"source-1"}, {"source-1": "lesson.pdf"},
    ))
    monkeypatch.setattr(socratic_setup, "setup_completion", complete)
    monkeypatch.setattr(socratic_setup, "add_step_checks", checks)

    result = asyncio.run(socratic_setup.generate_setup(
        [{"id": "file-1", "filename": "lesson.pdf"}], "Scrum", "",
    ))
    assert len(calls) == 2
    assert requests[0]["temperature"] == 0
    assert "clearly hypothetical, everyday analogy" in calls[0][0]
    assert "prefer a familiar activity students can picture immediately" in calls[0][0]
    assert "Do not copy a software project example from the source merely because it is available" in calls[0][0]
    assert "Never let a joke replace the reasoning task" in calls[0][0]
    assert "explain the answer before the student can reason" in calls[1][-1]
    assert result["learning_steps"][0]["scenario"] == scene
    assert "explanatory_steps_needing_review" not in result


def test_explanatory_scene_is_flagged_for_instructor_review():
    steps = [
        {"scenario": ("You join a student team building a campus event registration app. "
                      "The instructor explains that requirements change often. Students report that mobile "
                      "signup is frustrating. The team learns from results rather than guessing. "
                      "This means adapting what they do next based on evidence.")},
        {"scenario": "The instructor explains the concept before anyone tries the task."},
        {"scenario": "Students report a signup problem. What will the team do next?"},
    ]
    assert socratic_setup.explanatory_step_indices(steps) == [1, 2]
