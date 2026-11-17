import httpx
import pytest

from platform_app import canvas_lms


def mock_client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_lists_paginated_active_courses_without_leaking_token():
    requests = []

    def handler(request):
        requests.append(request)
        if request.url.params.get("page") == "2":
            return httpx.Response(200, json=[{"id": 2, "name": "Second"}])
        return httpx.Response(
            200,
            json=[{"id": 1, "name": "First", "course_code": "ITSC 3155"}],
            headers={
                "Link": '<https://instructure.charlotte.edu/api/v1/courses?page=2>; rel="next"'
            },
        )

    with mock_client(handler) as client:
        result = canvas_lms.list_courses("student-token", client=client)

    assert [course["id"] for course in result] == ["1", "2"]
    assert requests[0].url.params["enrollment_state"] == "active"
    assert requests[0].headers["Authorization"] == "Bearer student-token"
    assert "student-token" not in str(requests[0].url)


def test_rejects_pagination_outside_unc_charlotte_canvas():
    def handler(request):
        return httpx.Response(
            200,
            json=[],
            headers={"Link": '<https://attacker.example/api/v1/courses?page=2>; rel="next"'},
        )

    with mock_client(handler) as client, pytest.raises(canvas_lms.CanvasAPIError) as caught:
        canvas_lms.list_courses("student-token", client=client)

    assert caught.value.status_code == 502
    assert "unsafe pagination" in caught.value.detail


def test_uses_configured_canvas_api_origin(monkeypatch):
    requests = []
    monkeypatch.setattr(
        canvas_lms.settings,
        "CANVAS_API_ORIGIN",
        "https://canvaslite.instructure.com",
    )

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json=[])

    with mock_client(handler) as client:
        canvas_lms.list_courses("student-token", client=client)

    assert requests[0].url.host == "canvaslite.instructure.com"
    assert requests[0].url.path == "/api/v1/courses"


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

    assert requests[0].url.path == "/api/v1/courses/7/assignments/42"
    assert assignment["description"] == "Explain one tradeoff."
    assert assignment["due_at"] == "2026-10-01T16:00:00Z"


def test_canvas_assignment_preserves_links_without_fetching_private_files():
    description = (
        '<p>Read <a class="instructure_file_link" '
        'href="/courses/7/files/99/download?download_frd=1" '
        'data-api-endpoint="https://instructure.charlotte.edu/api/v1/files/99" '
        'data-api-returntype="File">Modular Sandwich Maker Machine.pdf</a>.</p>'
        '<p><a href="https://github.com/example/skeleton">Download code skeleton</a></p>'
    )
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json={"id": 42, "description": description})

    with mock_client(handler) as client:
        assignment = canvas_lms.get_assignment(7, 42, "teacher-token", client=client)

    assert len(requests) == 1
    assert "[Modular Sandwich Maker Machine.pdf](https://instructure.charlotte.edu/courses/7/files/99/download?download_frd=1)" in assignment["description"]
    assert "[Download code skeleton](https://github.com/example/skeleton)" in assignment["description"]


def test_canvas_description_rejects_unsafe_links_and_ignores_scripts():
    description = (
        '<a href="javascript:alert(1)">unsafe</a>'
        '<a href="https://example.org/docs">[Guide]</a>'
        '<script><a href="https://example.org/secret">secret</a></script>'
    )
    result = canvas_lms.description_with_links(description)
    assert "unsafe" in result
    assert "javascript:" not in result
    assert "[\\[Guide\\]](https://example.org/docs)" in result
    assert "secret" not in result
