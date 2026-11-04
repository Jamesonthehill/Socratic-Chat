"""Import safety, model output validation, and instructor access boundaries."""
import asyncio
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from platform_app.main import app
from platform_app import reflection_analysis as analysis, routes


def annotation(**changes):
    return {"primary_labels_selected": ["python_and_coding"], "resolution_primary_labels": ["unresolved"],
            "urgency": "high", "reflection_summary": "The student cannot run their Python code.",
            "instructor_suggestions": "Offer a debugging walkthrough.", **changes}


def test_csv_import_preserves_ids_quotes_newlines_and_reports_skipped_rows():
    body = analysis.ImportInput(content='\ufeffStudent_ID,Name,Q1,Grade\r\n 001 ,"Doe, Alex","Still stuck\non loops",83\r\n001,Alex,Need help,NaN\r\n,Empty,Blank ID,100\r\n002,Blank,,90\r\n',
                                id_column="Student_ID", name_column="Name", response_columns=["Q1"], grade_column="Grade")
    result = analysis.parse_csv(body)
    assert len(result["records"]) == 2
    assert result["records"][0] == {"student_id": "001", "name": "Doe, Alex", "text": "Q1: Still stuck\non loops", "grade": 83.0}
    assert result["records"][1]["grade"] is None
    assert len(result["warnings"]) == 4


def test_csv_inspection_and_tsv_conversion():
    inspected = analysis.parse_csv(analysis.ImportInput(content="ID\tResponse\n001\tA challenge\n"))
    assert inspected["columns"] == ["ID", "Response"]
    assert inspected["row_count"] == 1
    result = analysis.parse_csv(analysis.ImportInput(content="ID\tResponse\n001\tA challenge\n", id_column="ID", response_columns=["Response"]))
    assert result["records"][0]["student_id"] == "001"


@pytest.mark.parametrize("content,columns", [
    ("ID,ID\n1,2", ["ID"]),
    ("ID,Q\n1,hello,extra", ["Q"]),
    ("ID,Q\n1", ["Q"]),
    ("ID,Q\n1,hello", ["ID"]),
    ("ID,Q\n1,hello", ["Missing"]),
])
def test_bad_csv_or_mapping_is_rejected(content, columns):
    with pytest.raises(HTTPException) as exc:
        analysis.parse_csv(analysis.ImportInput(content=content, id_column="ID", response_columns=columns))
    assert exc.value.status_code == 422


@pytest.mark.parametrize("changes", [
    {"primary_labels_selected": ["invented_topic"]},
    {"resolution_primary_labels": []},
    {"resolution_primary_labels": ["resolved", "unresolved"]},
    {"urgency": "critical"},
    {"primary_labels_selected": ["none", "github"]},
    {"primary_labels_selected": ["none"], "resolution_primary_labels": ["no_challenge"], "urgency": "high"},
])
def test_model_schema_rejects_invalid_annotations(monkeypatch, changes):
    async def completion(*args):
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(annotation(**changes))))])
    monkeypatch.setattr(analysis, "chat_completion", completion)
    with pytest.raises(ValueError):
        asyncio.run(analysis.classify(analysis.ReflectionRecord(student_id="1", text="I am stuck"), "", ("Groq", "secret", "url", "model")))


def test_batch_keeps_partial_results_and_hides_provider_errors(monkeypatch):
    monkeypatch.setattr(analysis.settings, "llm_client_config", lambda _: ("Groq", "private-key", "url", "model"))
    async def completion(record, *_):
        if record.student_id == "2":
            raise RuntimeError("Provider error containing private-key and sensitive request")
        return annotation()
    monkeypatch.setattr(analysis, "classify", completion)
    body = analysis.AnalysisInput(records=[{"student_id": "1", "text": "I am stuck", "grade": 80}, {"student_id": "2", "text": "Me too"}])
    result = asyncio.run(analysis.analyze(body, account={"authority_level": 1}))
    assert result["summary"]["analyzed"] == 1
    assert result["summary"]["failed"] == 1
    assert result["summary"]["average_grade"] == 80
    assert result["summary"]["topics"] == [{"topic": "python_and_coding", "count": 1, "unresolved": 1}]
    assert "private-key" not in json.dumps(result)


@pytest.mark.parametrize("role,status", [(1, 200), (2, 403)])
def test_all_endpoints_require_professor_access(monkeypatch, role, status):
    monkeypatch.setattr(analysis.settings, "llm_client_config", lambda _: None)
    app.dependency_overrides[routes.user] = lambda: {"authority_level": role}
    try:
        client = TestClient(app)
        assert client.get("/api/platform/reflection-analysis/config").status_code == status
        assert client.post("/api/platform/reflection-analysis/import", json={"content": "ID,Q\n1,hello"}).status_code == status
        response = client.post("/api/platform/reflection-analysis/analyze", json={"records": [{"student_id": "1", "text": "hello"}]})
        assert response.status_code == (503 if role == 1 else 403)
    finally:
        app.dependency_overrides.pop(routes.user, None)


def test_unauthenticated_import_is_rejected():
    response = TestClient(app).post("/api/platform/reflection-analysis/import", json={"content": "ID,Q\n1,hello"})
    assert response.status_code == 401
