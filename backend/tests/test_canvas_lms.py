import httpx
import pytest

from platform_app import canvas_lms


def mock_client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_lists_only_active_instructor_courses_without_leaking_token():
    requests = []

    def handler(request):
        requests.append(request)
        if request.url.path == "/api/v1/users/self/enrollments":
            return httpx.Response(200, json=[
                {"course_id": 1, "type": "TeacherEnrollment", "enrollment_state": "active"},
                {"course_id": 2, "type": "StudentEnrollment", "enrollment_state": "active"},
                {"course_id": 3, "type": "TaEnrollment", "enrollment_state": "active"},
                {"course_id": 3, "type": "TaEnrollment", "enrollment_state": "active"},
                {"course_id": 4, "type": "DesignerEnrollment", "enrollment_state": "active"},
                {"course_id": 5, "type": "ObserverEnrollment", "enrollment_state": "active"},
                {"course_id": 6, "type": "TeacherEnrollment", "enrollment_state": "invited"},
                {"course_id": 7, "type": "TeacherEnrollment", "role": "Custom Instructor", "enrollment_state": "active"},
            ])
        if request.url.params.get("page") == "2":
            return httpx.Response(200, json=[
                {"id": 3, "name": "Third"},
                {"id": 4, "name": "Fourth"},
                {"id": 5, "name": "Fifth"},
                {"id": 6, "name": "Sixth"},
                {"id": 7, "name": "Seventh"},
            ])
        return httpx.Response(
            200,
            json=[{"id": 1, "name": "First", "course_code": "ITSC 3155"}, {"id": 2, "name": "Second"}],
            headers={
                "Link": '<https://instructure.charlotte.edu/api/v1/courses?page=2>; rel="next"'
            },
        )

    with mock_client(handler) as client:
        result = canvas_lms.list_courses("canvas-token", client=client)

    assert [course["id"] for course in result] == ["1", "3", "4", "7"]
    assert [course["enrollment_role"] for course in result] == ["teacher", "ta", "designer", "teacher"]
    assert requests[0].url.path == "/api/v1/users/self/enrollments"
    assert set(requests[0].url.params.get_list("type[]")) == set(canvas_lms.INSTRUCTOR_ENROLLMENT_TYPES)
    assert requests[0].url.params["state[]"] == "active"
    assert requests[1].url.params["enrollment_state"] == "active"
    assert all(request.headers["Authorization"] == "Bearer canvas-token" for request in requests)
    assert all("canvas-token" not in str(request.url) for request in requests)


def test_rejects_pagination_outside_unc_charlotte_canvas():
    def handler(request):
        if request.url.path == "/api/v1/users/self/enrollments":
            return httpx.Response(200, json=[
                {"course_id": 1, "type": "TeacherEnrollment", "enrollment_state": "active"},
            ])
        return httpx.Response(
            200,
            json=[],
            headers={"Link": '<https://attacker.example/api/v1/courses?page=2>; rel="next"'},
        )

    with mock_client(handler) as client, pytest.raises(canvas_lms.CanvasAPIError) as caught:
        canvas_lms.list_courses("student-token", client=client)

    assert caught.value.status_code == 502
    assert "unsafe pagination" in caught.value.detail


def test_maps_canvas_authentication_failure_to_validation_error():
    with mock_client(lambda request: httpx.Response(401, json={"errors": []})) as client:
        with pytest.raises(canvas_lms.CanvasAPIError) as caught:
            canvas_lms.list_courses("expired-token", client=client)

    assert caught.value.status_code == 422
    assert "rejected the access token" in caught.value.detail


def test_assignment_description_is_plain_text_and_exact_endpoint_is_used():
    requests = []

    def handler(request):
        requests.append(request)
        if request.url.path == "/api/v1/users/self/enrollments":
            return httpx.Response(200, json=[
                {"course_id": 7, "type": "TeacherEnrollment", "enrollment_state": "active"},
            ])
        return httpx.Response(
            200,
            json={
                "id": 42,
                "name": "Architecture reflection",
                "description": "<p>Explain <strong>one</strong> tradeoff.</p><script>secret()</script>",
                "due_at": "2026-10-01T16:00:00Z",
                "html_url": "https://instructure.charlotte.edu/courses/7/assignments/42",
            },
        )

    with mock_client(handler) as client:
        assignment = canvas_lms.get_assignment(7, 42, "student-token", client=client)

    assert requests[0].url.path == "/api/v1/users/self/enrollments"
    assert requests[0].url.params["state[]"] == "active"
    assert requests[1].url.path == "/api/v1/courses/7/assignments/42"
    assert assignment["description"] == "Explain one tradeoff."
    assert assignment["due_at"] == "2026-10-01T16:00:00Z"


@pytest.mark.parametrize("enrollments", [
    [{"course_id": 7, "type": "StudentEnrollment", "enrollment_state": "active"}],
    [{"course_id": 7, "type": "TeacherEnrollment", "enrollment_state": "invited"}],
    [{"course_id": 8, "type": "TeacherEnrollment", "enrollment_state": "active"}],
    [],
])
def test_assignment_access_rejects_course_without_active_instructor_role(enrollments):
    paths = []

    def handler(request):
        paths.append(request.url.path)
        assert request.url.path == "/api/v1/users/self/enrollments"
        return httpx.Response(200, json=enrollments)

    with mock_client(handler) as client:
        with pytest.raises(canvas_lms.CanvasAPIError) as caught:
            canvas_lms.list_assignments(7, "canvas-token", client=client)
        with pytest.raises(canvas_lms.CanvasAPIError):
            canvas_lms.get_assignment(7, 42, "canvas-token", client=client)
        with pytest.raises(canvas_lms.CanvasAPIError):
            canvas_lms.get_instructor_course(7, "canvas-token", client=client)

    assert caught.value.status_code == 403
    assert paths == ["/api/v1/users/self/enrollments"] * 3
