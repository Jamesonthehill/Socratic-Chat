import httpx
import pytest
from fastapi import HTTPException
from uuid import uuid4

from platform_app import canvas_lms
from platform_app import routes
from platform_app.schemas import CanvasFileImportRequest


def test_finds_only_files_linked_in_the_selected_canvas_course():
    instructions = (
        "[Project PDF](https://instructure.charlotte.edu/courses/7/files/99/download) "
        "[Again](https://instructure.charlotte.edu/courses/7/files/99?wrap=1) "
        "[Other course](https://instructure.charlotte.edu/courses/8/files/33/download) "
        "[External](https://example.org/files/44)"
    )
    assert canvas_lms.linked_file_ids(instructions, 7) == [99]


def test_only_supported_visible_bounded_files_can_be_imported():
    base = {"id": 99, "filename": "project.pdf", "size": 100, "url": "https://instructure.charlotte.edu/files/99/download"}
    assert canvas_lms.file_import_reason(base) is None
    assert "type" in canvas_lms.file_import_reason({**base, "filename": "source.zip"})
    assert "hidden" in canvas_lms.file_import_reason({**base, "hidden": True})
    assert "currently available" in canvas_lms.file_import_reason({**base, "unlock_at": "2099-01-01T00:00:00Z"})
    assert "10 MB" in canvas_lms.file_import_reason({**base, "size": 11 * 1024 * 1024})


def test_download_follows_trusted_redirect_without_forwarding_canvas_token():
    requests = []

    def handler(request):
        requests.append(request)
        if request.url.host == "instructure.charlotte.edu":
            return httpx.Response(302, headers={"Location": "https://bucket.s3.amazonaws.com/project.pdf"})
        return httpx.Response(200, content=b"%PDF-1.7\nexample")

    metadata = {"filename": "project.pdf", "size": 16, "url": "https://instructure.charlotte.edu/files/99/download"}
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        content = canvas_lms.download_course_file(metadata, "secret-token", client=client)

    assert content.startswith(b"%PDF")
    assert requests[0].headers["Authorization"] == "Bearer secret-token"
    assert "Authorization" not in requests[1].headers


def test_download_rejects_untrusted_redirect_and_oversized_response():
    metadata = {"filename": "project.pdf", "size": 16, "url": "https://instructure.charlotte.edu/files/99/download"}
    with httpx.Client(transport=httpx.MockTransport(
        lambda request: httpx.Response(302, headers={"Location": "https://localhost/private"})
    )) as client:
        with pytest.raises(canvas_lms.CanvasAPIError, match="unsupported file download host"):
            canvas_lms.download_course_file(metadata, "token", client=client)

    with httpx.Client(transport=httpx.MockTransport(
        lambda request: httpx.Response(200, content=b"x" * (canvas_lms.MAX_IMPORT_FILE_BYTES + 1))
    )) as client:
        with pytest.raises(canvas_lms.CanvasAPIError, match="exceeds the 10 MB"):
            canvas_lms.download_course_file(metadata, "token", client=client)


def test_import_endpoint_only_indexes_explicitly_selected_linked_files(monkeypatch):
    assignment_id = uuid4()
    course_id = uuid4()
    calls = []
    item = {"id": assignment_id, "course_id": course_id}
    monkeypatch.setattr(routes, "canvas_assignment_files_context", lambda *_: (item, 7, [99], "token"))
    monkeypatch.setattr(routes.db, "list_rag_files", lambda **_: [])
    monkeypatch.setattr(routes.canvas_lms, "get_course_file", lambda *_: {
        "id": 99, "filename": "project.pdf", "size": 11,
        "url": "https://instructure.charlotte.edu/files/99/download",
    })
    monkeypatch.setattr(routes.canvas_lms, "download_course_file", lambda *_: b"%PDF-1.7\n")
    monkeypatch.setattr(routes.db, "save_rag_file", lambda *args, **kwargs: calls.append((args, kwargs)) or str(uuid4()))
    monkeypatch.setattr(routes.rag, "ingest_file", lambda *args, **kwargs: ("document-99", 3))

    with pytest.raises(HTTPException) as caught:
        routes.import_canvas_assignment_files(
            assignment_id, CanvasFileImportRequest(file_ids=[100]), {"user_id": uuid4()}
        )
    assert caught.value.status_code == 422
    assert not calls

    result = routes.import_canvas_assignment_files(
        assignment_id, CanvasFileImportRequest(file_ids=[99]), {"user_id": uuid4()}
    )
    assert result["imported"][0]["document_id"] == "document-99"
    assert calls[0][0][0] == "Canvas 99 - project.pdf"
    assert calls[0][1]["course_id"] == str(course_id)
