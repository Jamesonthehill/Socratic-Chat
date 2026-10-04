from uuid import uuid4

import pytest

from platform_app.canvas_assignment_config import config_from_canvas
from platform_app import engines
from platform_app.schemas import AssignmentInput, ReflectionConfig


@pytest.mark.parametrize("tool", ["socratic", "reflections", "student-agent"])
def test_canvas_assignment_provides_valid_chatbot_settings(tool):
    assignment = {
        "name": "Compare two architecture choices",
        "description": "Explain one tradeoff and support it with evidence.",
    }
    config = config_from_canvas(tool, assignment, 77, 88)
    validated = AssignmentInput(
        course_id=uuid4(),
        tool=tool,
        title=assignment["name"],
        instructions=assignment["description"],
        config=config,
    ).config

    if tool == "socratic":
        assert assignment["name"] in validated["prompt"]
        assert validated["canvas_context"] == assignment["description"]
    elif tool == "reflections":
        ReflectionConfig.model_validate(validated).validate_publish()
        assert validated["custom_notes"] == assignment["description"]
    else:
        assert validated["topic"]["name"] == assignment["name"]
        assert assignment["description"] in validated["topic"]["practice_prompt"]
        assert validated["topic"]["resource"]["url"].endswith("/courses/77/assignments/88")


def test_long_canvas_description_stays_within_config_limits():
    assignment = {"name": "Essay", "description": "A" * 10_000}
    config = config_from_canvas("student-agent", assignment, 77, 88)
    assert len(config["topic"]["practice_prompt"]) == 10_000
    AssignmentInput(
        course_id=uuid4(),
        tool="student-agent",
        title=assignment["name"],
        config=config,
    )


def test_canvas_socratic_assignment_can_publish_without_separate_documents(monkeypatch):
    monkeypatch.setattr(engines.db, "list_rag_files", lambda **kwargs: [])
    monkeypatch.setattr(engines.db, "get_course", lambda course_id: {"title": "Software Engineering"})
    assignment = {
        "id": str(uuid4()),
        "course_id": str(uuid4()),
        "tool": "socratic",
        "title": "Compare two architecture choices",
        "config": config_from_canvas(
            "socratic",
            {
                "name": "Compare two architecture choices",
                "description": "Explain one tradeoff and support it with evidence.",
            },
            77,
            88,
        ),
    }

    snapshot = engines.publish_snapshot(assignment)

    assert len(snapshot["chunks"]) == 1
    assert snapshot["chunks"][0]["metadata"]["source"] == "canvas_assignment"
    assert "Explain one tradeoff" in snapshot["chunks"][0]["text"]
    monkeypatch.setattr(engines.rag, "create_embeddings", lambda texts: [[1.0, 0.0]])
    sources = engines.rag.retrieve_snapshot("architecture choices", snapshot["chunks"])
    assert sources[0].title.startswith("Canvas assignment:")


@pytest.mark.parametrize("tool", ["reflections", "student-agent"])
def test_other_canvas_chatbot_modes_have_publishable_settings(monkeypatch, tool):
    monkeypatch.setattr(engines, "call", lambda *args, **kwargs: {"id": "canvas-module"})
    assignment = {"name": "Architecture tradeoffs", "description": "Compare two designs."}
    validated = AssignmentInput(
        course_id=uuid4(),
        tool=tool,
        title=assignment["name"],
        config=config_from_canvas(tool, assignment, 77, 88),
    )

    snapshot = engines.publish_snapshot({"id": str(uuid4()), **validated.model_dump()})

    assert snapshot["config"] == validated.config
