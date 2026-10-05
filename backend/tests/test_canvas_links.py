import httpx

from platform_app import canvas_lms


def test_import_description_preserves_canvas_file_and_external_links():
    description = (
        '<p>Read <a href="/courses/7/files/99/download?download_frd=1">'
        'Sandwich Maker Machine- Document.pdf</a>.</p>'
        '<p>Download <a href="https://example.org/source?part=1&amp;copy=2">'
        'Source code</a>.</p>'
    )

    result = canvas_lms.description_text(description, preserve_links=True)

    assert "[Sandwich Maker Machine- Document.pdf]" in result
    assert "(https://instructure.charlotte.edu/courses/7/files/99/download?download_frd=1)" in result
    assert "[Source code](https://example.org/source?part=1&copy=2)" in result


def test_import_description_rejects_script_links_and_keeps_visible_text():
    description = (
        '<a href="javascript:alert(1)">Unsafe</a> '
        '<a href="data:text/html,evil">Also unsafe</a> '
        '<a href="https://example.org/a(b)">Safe</a>'
    )

    result = canvas_lms.description_text(description, preserve_links=True)

    assert "Unsafe" in result and "Also unsafe" in result
    assert "javascript:" not in result and "data:text" not in result
    assert "[Safe](https://example.org/a%28b%29)" in result


def test_original_canvas_link_must_point_to_canvas():
    assert canvas_lms.safe_canvas_assignment_url(
        "https://instructure.charlotte.edu/courses/7/assignments/42"
    )
    assert canvas_lms.safe_canvas_assignment_url("https://example.org/fake") is None


def test_get_assignment_keeps_file_link_for_import(monkeypatch):
    monkeypatch.setattr(canvas_lms, "require_instructor_course", lambda *args, **kwargs: "teacher")

    def handler(request):
        assert request.url.path == "/api/v1/courses/7/assignments/42"
        return httpx.Response(
            200,
            json={
                "id": 42,
                "name": "Sandwich Maker",
                "description": '<p>Read <a href="/courses/7/files/99/download">the PDF</a>.</p>',
            },
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        assignment = canvas_lms.get_assignment(7, 42, "token", client=client)

    assert "[the PDF](https://instructure.charlotte.edu/courses/7/files/99/download)" in assignment["description"]
