from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from zipfile import ZipFile

import pytest
from fastapi import HTTPException

from app import rag
from app import office_documents as office
from platform_app import shared_rag


def office_archive(parts):
    output = BytesIO()
    with ZipFile(output, "w") as archive:
        for name, content in parts.items():
            archive.writestr(name, content)
    return output.getvalue()


def sample_docx():
    return office_archive({
        "word/document.xml": """<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
          <w:body><w:p><w:r><w:t>Review the design.</w:t></w:r></w:p>
          <w:tbl><w:tr><w:tc><w:p><w:r><w:t>Check edge cases.</w:t></w:r></w:p></w:tc></w:tr></w:tbl>
          <w:p><w:hyperlink><w:r><w:t>Read the guide.</w:t></w:r></w:hyperlink></w:p>
          </w:body></w:document>""",
    })


def sample_pptx():
    return office_archive({
        "ppt/presentation.xml": """<p:presentation xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"
          xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
          <p:sldIdLst><p:sldId id="256" r:id="rId2"/><p:sldId id="257" r:id="rId1"/></p:sldIdLst>
          </p:presentation>""",
        "ppt/_rels/presentation.xml.rels": """<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
          <Relationship Id="rId1" Target="slides/slide1.xml"/>
          <Relationship Id="rId2" Target="slides/slide2.xml"/></Relationships>""",
        "ppt/slides/slide1.xml": """<p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"
          xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"><p:cSld><p:spTree>
          <p:sp><p:txBody><a:p><a:r><a:t>Second slide: testing</a:t></a:r></a:p></p:txBody></p:sp>
          </p:spTree></p:cSld></p:sld>""",
        "ppt/slides/slide2.xml": """<p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"
          xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"><p:cSld><p:spTree>
          <p:sp><p:txBody><a:p><a:r><a:t>First slide: requirements</a:t></a:r></a:p></p:txBody></p:sp>
          </p:spTree></p:cSld></p:sld>""",
        "ppt/slides/_rels/slide2.xml.rels": """<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
          <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/notesSlide"
          Target="../notesSlides/notesSlide2.xml"/></Relationships>""",
        "ppt/notesSlides/notesSlide2.xml": """<p:notes xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"
          xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"><p:cSld><p:spTree>
          <p:sp><p:txBody><a:p><a:r><a:t>Ask about edge cases.</a:t></a:r></a:p></p:txBody></p:sp>
          </p:spTree></p:cSld></p:notes>""",
    })


def test_docx_extracts_paragraphs_tables_and_hyperlink_labels(tmp_path):
    path = tmp_path / "notes.docx"
    path.write_bytes(sample_docx())
    sections = office.parse_office_document(path)
    assert len(sections) == 1
    assert "Review the design." in sections[0].text
    assert "Check edge cases." in sections[0].text
    assert "Read the guide." in sections[0].text


def test_pptx_uses_presentation_order_and_slide_metadata():
    chunks = shared_rag._parse_office("lecture.pptx", sample_pptx())
    assert len(chunks) == 2
    assert chunks[0]["text"].startswith("Slide 1:")
    assert "First slide: requirements" in chunks[0]["text"]
    assert "Speaker notes: Ask about edge cases." in chunks[0]["text"]
    assert chunks[0]["metadata"]["slide"] == 1
    assert chunks[1]["text"].startswith("Slide 2:")
    assert "Second slide: testing" in chunks[1]["text"]
    assert chunks[1]["metadata"]["slide"] == 2


def test_course_upload_indexes_word_without_calling_sdl(monkeypatch):
    stored = {}
    monkeypatch.setattr(shared_rag, "pipeline", lambda *args, **kwargs: pytest.fail("SDL parser was called"))
    monkeypatch.setattr(shared_rag, "create_embeddings", lambda texts: [[0.1] for _ in texts])
    monkeypatch.setattr(shared_rag.db, "save_rag_file", lambda *args, **kwargs: "file-1")
    monkeypatch.setattr(shared_rag.db, "replace_document_chunks", lambda *args, **kwargs: stored.update(chunks=args[3]))
    result = shared_rag.ingest("course-1", {"user_id": "teacher-1"}, "notes.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", sample_docx())
    assert result["file_id"] == "file-1"
    assert result["chunk_count"] >= 1
    assert "Check edge cases." in stored["chunks"][0]["text"]


def test_socratic_course_upload_indexes_powerpoint(monkeypatch, tmp_path):
    path = tmp_path / "lecture.pptx"
    path.write_bytes(sample_pptx())
    stored = {}
    monkeypatch.setattr(rag, "create_embeddings", lambda texts: [[0.1] for _ in texts])
    monkeypatch.setattr(rag.db, "replace_document_chunks", lambda *args, **kwargs: stored.update(chunks=args[3]) or len(args[3]))
    _, count = rag.ingest_file(path, course_id="course-1", file_id="file-1")
    assert count == 2
    assert stored["chunks"][0]["metadata"]["slide"] == 1


@pytest.mark.parametrize("filename", ["broken.docx", "broken.pptx"])
def test_invalid_office_file_is_a_validation_error(filename):
    with pytest.raises(HTTPException) as error:
        shared_rag._parse_office(filename, b"not an Office archive")
    assert error.value.status_code == 422


@pytest.mark.parametrize("suffix,executable", [(".doc", "antiword"), (".ppt", "catppt")])
def test_legacy_office_files_use_text_extractors(monkeypatch, tmp_path, suffix, executable):
    path = tmp_path / ("legacy" + suffix)
    path.write_bytes(b"legacy office bytes")
    monkeypatch.setattr(office.shutil, "which", lambda command: "/usr/bin/" + command)
    calls = []

    def run(command, **kwargs):
        calls.append(command)
        return SimpleNamespace(returncode=0, stdout=b"Legacy course notes\fSecond slide" if suffix == ".ppt" else b"Legacy course notes")

    monkeypatch.setattr(office.subprocess, "run", run)
    sections = office.parse_office_document(path)
    assert sections[0].text == "Legacy course notes"
    if suffix == ".ppt":
        assert sections[1] == office.OfficeSection("Second slide", slide=2)
    assert Path(calls[0][0]).name == executable
