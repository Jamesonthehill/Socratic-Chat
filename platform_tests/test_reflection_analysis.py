from uuid import uuid4

from psycopg.types.json import Jsonb

from platform_app import store


def test_reflection_analysis_uses_saved_responses_and_course_access(client, roster):
    assignment_id = uuid4()
    with store.connection() as conn:
        conn.execute("""INSERT INTO assignments_platform
            (id, course_id, creator_id, tool, title, instructions, audience, config, status)
            VALUES (%s, %s, %s, 'reflections', 'Project check-in', 'Reflect.', 'selected', %s, 'published')""",
            (assignment_id, roster["course"], roster["prof"], Jsonb({"module_type": "topic_based"})))
        conn.execute("INSERT INTO assignment_recipients_platform(assignment_id, student_id) VALUES (%s, %s)",
                     (assignment_id, roster["student"]))
        conn.execute("""INSERT INTO assignment_attempts_platform
            (id, assignment_id, student_id, status, messages)
            VALUES (%s, %s, %s, 'completed', %s)""",
            (uuid4(), assignment_id, roster["student"], Jsonb([
                {"role": "assistant", "content": "What interests you?"},
                {"role": "user", "content": "I want to study campus transit."},
            ])))

    path = f"/api/platform/assignments/{assignment_id}/reflection-analysis"
    response = client.get(path, headers=roster["headers"]["prof"])
    assert response.status_code == 200, response.text
    analysis = response.json()
    assert analysis["summary"] == {"assigned": 1, "started": 1, "completed": 1, "responses": 1}
    assert analysis["students"][0]["responses"] == ["I want to study campus transit."]
    assert client.get(path, headers=roster["headers"]["other_prof"]).status_code == 403
    assert client.get(path, headers=roster["headers"]["student"]).status_code == 403
