from platform_app import engines


def test_basic_assignment_opens_with_selected_material_and_question():
    assignment = {
        "tool": "socratic", "title": "Assignment 6",
        "snapshot": {"config": {"prompt": ""}, "chunks": [
            {"text": "When a teammate checks a proposed change, they look for correctness before merging it."},
        ]},
    }
    result = engines.start(assignment, {})
    opening = result["messages"][0]["content"]
    assert "When a teammate checks a proposed change" in opening
    assert opening.endswith("What would you do first, and why?")
    assert result["socratic"]["assignment_scope"] is True


def test_basic_assignment_uses_instructor_opening_question():
    assignment = {
        "tool": "socratic",
        "title": "Code review",
        "snapshot": {
            "config": {"prompt": "What should a reviewer check, and why?"},
            "chunks": [{"text": "When a reviewer reads a patch, they check correctness before merging."}],
        },
    }
    assert engines.start(assignment, {})["messages"][0]["content"] == "What should a reviewer check, and why?"


def test_basic_assignment_without_long_source_uses_assignment_fallback():
    assignment = {
        "tool": "socratic",
        "title": "Code review",
        "snapshot": {
            "config": {},
            "chunks": [{"text": "A brief note."}],
        },
    }
    opening = engines.start(assignment, {})["messages"][0]["content"]
    assert "example" not in opening.casefold()
    assert "Code review" in opening
    assert opening.endswith("Which requirement or design choice should we examine first?")
