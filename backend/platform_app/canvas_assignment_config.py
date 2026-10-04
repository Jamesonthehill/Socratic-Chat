"""Build publish-ready chatbot settings from an instructor's Canvas assignment."""

from platform_app import canvas_lms


def config_from_canvas(tool: str, assignment: dict, course_id: int, assignment_id: int) -> dict:
    title = assignment["name"][:200]
    description = assignment["description"]
    if tool == "socratic":
        return {
            "document_ids": [],
            "prompt": (
                "Help the learner reason through this Canvas assignment using only the "
                f"published course materials: {title}"
            ),
            "minimum_messages": 1,
            "canvas_context": description,
        }
    if tool == "reflections":
        return {
            "module_type": "topic_based",
            "required_topics": [title],
            "sub_topics": [title],
            "custom_notes": description,
        }
    if tool == "student-agent":
        canvas_url = f"{canvas_lms.CANVAS_ORIGIN}/courses/{course_id}/assignments/{assignment_id}"
        course_url = f"{canvas_lms.CANVAS_ORIGIN}/courses/{course_id}"
        return {
            "provider": "groq",
            "topic": {
                "id": f"canvas_{course_id}_{assignment_id}",
                "name": title,
                "resource": {"title": "Canvas assignment", "url": canvas_url},
                "alt_resource": {"title": "Canvas course", "url": course_url},
                "practice_label": title,
                "practice_prompt": (
                    f"Guide the learner through the Canvas assignment '{title}'. "
                    f"Use these assignment instructions as context:\n{description}"
                )[:10_000],
                "practice_stages": [
                    {
                        "label": "Understand",
                        "focus": "Ask the learner to restate the Canvas assignment goal and identify its criteria.",
                    },
                    {
                        "label": "Apply",
                        "focus": "Help the learner try one step using the assignment instructions, without giving the completed answer.",
                    },
                    {
                        "label": "Reflect",
                        "focus": "Ask the learner to check their work against the Canvas assignment and explain a revision.",
                    },
                ],
                "check_questions": [
                    "What does this Canvas assignment ask you to produce?",
                    "How does your approach meet the assignment instructions?",
                ],
                "final_example": (
                    "Example process, not an answer: restate the task, try one step, "
                    "compare the result with the Canvas instructions, then revise."
                ),
            },
        }
    raise ValueError(f"Unknown chatbot mode: {tool}")
