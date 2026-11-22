"""Boundary tests for the isolated Socratic engine service."""
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from platform_app import engines
from platform_app.socratic_service import app as socratic_service


def test_gateway_sends_socratic_start_to_private_service(monkeypatch):
    response = MagicMock()
    response.is_error = False
    response.json.return_value = {"messages": [], "socratic": {"phase": "teaching"}}
    client = MagicMock()
    client.post.return_value = response
    client.__enter__.return_value = client

    monkeypatch.setenv("SOCRATIC_URL", "http://socratic:8003")
    monkeypatch.setenv("PLATFORM_SERVICE_TOKEN", "service-secret")
    monkeypatch.delenv("SOCRATIC_SERVICE_MODE", raising=False)
    monkeypatch.setattr(engines.httpx, "Client", lambda **_kwargs: client)

    result = engines.start(
        {"tool": "socratic", "snapshot": {"config": {}}, "id": "assignment-1"},
        {"id": "attempt-1"},
    )

    assert result["socratic"]["phase"] == "teaching"
    client.post.assert_called_once()
    path = client.post.call_args.args[0]
    assert path == "http://socratic:8003/internal/platform/start"
    assert client.post.call_args.kwargs["json"]["assignment"]["tool"] == "socratic"


def test_socratic_service_requires_the_platform_token():
    with TestClient(socratic_service) as client:
        response = client.post("/internal/platform/start", json={"assignment": {}, "attempt": {}})

    assert response.status_code == 401


def test_socratic_service_handles_an_authorized_start(monkeypatch):
    expected = {"messages": [{"role": "assistant", "content": "What should we examine first?"}], "socratic": {}}
    monkeypatch.setenv("PLATFORM_SERVICE_TOKEN", "test-only-platform-service-secret")
    monkeypatch.setenv("SOCRATIC_SERVICE_MODE", "true")
    monkeypatch.setattr(engines, "start", lambda assignment, attempt: expected)

    with TestClient(socratic_service) as client:
        response = client.post(
            "/internal/platform/start",
            headers={"X-Platform-Service": "test-only-platform-service-secret"},
            json={"assignment": {"tool": "socratic", "snapshot": {"config": {}}}, "attempt": {}},
        )

    assert response.status_code == 200
    assert response.json() == expected


def test_socratic_service_rehydrates_public_chat_history(monkeypatch):
    observed = {}

    async def public_message(content, history, engine_state, learning_topic):
        observed["history_role"] = history[0].role
        observed["history_content"] = history[0].content
        return {"reply": "Let us examine that.", "socratic": {}}, learning_topic or "Test topic"

    monkeypatch.setenv("PLATFORM_SERVICE_TOKEN", "test-only-platform-service-secret")
    monkeypatch.setenv("SOCRATIC_SERVICE_MODE", "true")
    monkeypatch.setattr(engines, "public_socratic_message", public_message)

    with TestClient(socratic_service) as client:
        response = client.post(
            "/internal/platform/public-message",
            headers={"X-Platform-Service": "test-only-platform-service-secret"},
            json={
                "content": "What is version control?",
                "history": [{"role": "assistant", "content": "What would you like to explore?"}],
            },
        )

    assert response.status_code == 200
    assert observed == {"history_role": "assistant", "history_content": "What would you like to explore?"}


def test_compose_defines_a_private_socratic_service():
    compose = (engines.ROOT / "compose.yaml").read_text()

    assert "  socratic:\n" in compose
    assert "dockerfile: Dockerfile.socratic" in compose
    assert "SOCRATIC_URL: http://socratic:8003" in compose
    assert "socratic: {condition: service_healthy}" in compose
