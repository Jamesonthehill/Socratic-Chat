from platform_app import shared_rag


def test_ingest_uses_platform_embedding_configuration(monkeypatch):
    chunks = [{"text": "First section"}, {"text": "Second section"}]
    vectors = [[1.0, 0.0], [0.0, 1.0]]
    calls = []

    def pipeline(method, path, **kwargs):
        calls.append((method, path, kwargs))
        assert path == "/internal/platform/rag/parse"
        return {"chunks": chunks}

    monkeypatch.setattr(shared_rag, "pipeline", pipeline)
    monkeypatch.setattr(shared_rag, "create_embeddings", lambda texts: vectors)
    monkeypatch.setattr(shared_rag.db, "save_rag_file", lambda *_args, **_kwargs: "file-1")
    replace = lambda *args, **kwargs: calls.append(("replace", args, kwargs))
    monkeypatch.setattr(shared_rag.db, "replace_document_chunks", replace)

    result = shared_rag.ingest(
        "course-1",
        {"user_id": "instructor-1"},
        "lesson.pdf",
        "application/pdf",
        b"document",
    )

    assert result["file_id"] == "file-1"
    assert result["chunk_count"] == 2
    assert [call[1] for call in calls if call[0] != "replace"] == [
        "/internal/platform/rag/parse",
    ]
    replace_call = next(call for call in calls if call[0] == "replace")
    assert replace_call[1][3] == chunks
    assert replace_call[1][4] == vectors
