from uuid import uuid4

import pytest

from platform_app import engines
from platform_app.schemas import ReflectionConfig


@pytest.mark.parametrize("step_surveys", [{}, {"step-1": {"title": "Reflection"}}])
def test_publish_reflection_excludes_platform_metadata(monkeypatch, step_surveys):
    config = ReflectionConfig(
        required_topics=["Design"],
        sub_topics=["Requirements"],
        document_ids=[str(uuid4())],
        step_surveys=step_surveys,
        expected_depth="applied",
        custom_notes="Discuss one concrete example.",
    ).model_dump()
    assignment = {
        "id": str(uuid4()),
        "course_id": str(uuid4()),
        "title": "Reflection publishing regression",
        "tool": "reflections",
        "config": config,
    }
    requests = []

    def prepare_module(tool, method, path, **kwargs):
        requests.append((tool, method, path, kwargs["json"]))
        return {"id": assignment["id"]}

    monkeypatch.setattr(engines, "call", prepare_module)
    snapshot = engines.publish_snapshot(assignment)
    tool, method, path, payload = requests[0]
    assert (tool, method, path) == (
        "reflections", "PUT", f"/internal/platform/modules/{assignment['id']}"
    )
    assert payload["config"] == {
        "module_type": "topic_based",
        "required_topics": ["Design"],
        "sub_topics": ["Requirements"],
        "expected_depth": "applied",
        "probing_style": "supportive",
        "must_include_application": False,
        "custom_notes": "Discuss one concrete example.",
        "milestone_prompt": "",
        "historical_data": "",
    }
    assert snapshot == {"config": config, "module_id": assignment["id"]}
