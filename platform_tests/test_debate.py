from uuid import uuid4

from fastapi import HTTPException

from platform_app import engines
from app.schemas import Source


def create_debate(client, roster, **config_changes):
    config = {
        "scenario": "Should a university require AI-use disclosures on every assignment?",
        "opening_prompt": "Take a position and explain your strongest reason.",
        "minimum_messages": 2,
        **config_changes,
    }
    response = client.post(
        "/api/platform/assignments",
        headers=roster["headers"]["prof"],
        json={
            "course_id": roster["course"],
            "tool": "debate",
            "title": "AI disclosure debate",
            "instructions": "Defend your position and respond to counterarguments.",
            "audience": "selected",
            "recipient_ids": [roster["student"]],
            "config": config,
        },
    )
    assert response.status_code == 201, response.text
    return response.json(), config


def test_debate_assignment_uses_native_lifecycle(client, roster, monkeypatch):
    item, config = create_debate(client, roster)
    path = f"/api/platform/assignments/{item['id']}"
    professor_headers = roster["headers"]["prof"]
    student_headers = roster["headers"]["student"]

    published = client.post(f"{path}/publish", headers=professor_headers)
    assert published.status_code == 200, published.text

    student_view = client.get(path, headers=student_headers).json()
    assert "config" not in student_view
    assert student_view["student_config"] == {
        "scenario": config["scenario"],
        "minimum_messages": 2,
        "reflection_required": True,
    }

    started = client.post(f"{path}/start", headers=student_headers)
    assert started.status_code == 200, started.text
    assert started.json()["messages"] == [
        {"role": "assistant", "content": config["opening_prompt"]}
    ]
    assert started.json()["engine_state"]["debate"] == {
        "phase": "debating", "stage": "take_a_position", "student_turns": 0,
    }

    calls = []

    async def challenge(scenario, history, student_message, sources=None):
        calls.append((scenario, history.copy(), student_message, sources))
        return "That identifies a benefit, but what assumption makes it outweigh the cost?"

    monkeypatch.setattr(engines.debate, "generate_reply", challenge)
    first_request = {
        "message": "Disclosures improve trust because readers can evaluate how work was produced.",
        "request_id": str(uuid4()),
    }
    first = client.post(f"{path}/messages", headers=student_headers, json=first_request)
    assert first.status_code == 200, first.text
    assert calls[0][0] == config["scenario"]
    assert calls[0][1] == started.json()["messages"]
    assert calls[0][2] == first_request["message"]
    assert calls[0][3] == []
    assert first.json()["messages"][-1]["role"] == "assistant"
    duplicate_first = client.post(f"{path}/messages", headers=student_headers, json=first_request)
    assert duplicate_first.status_code == 200
    assert duplicate_first.json()["messages"] == first.json()["messages"]
    resumed = client.get(f"{path}/attempt", headers=student_headers)
    assert resumed.status_code == 200
    assert resumed.json()["engine_state"]["debate"]["student_turns"] == 1

    assert client.post(f"{path}/complete", headers=student_headers).status_code == 422
    oversized = client.post(f"{path}/reflection", headers=student_headers, json={
        "summary": "x" * 4001, "request_id": str(uuid4()),
    })
    assert oversized.status_code == 422
    second = client.post(
        f"{path}/messages",
        headers=student_headers,
        json={"message": "The policy should also define meaningful assistance.", "request_id": str(uuid4())},
    )
    assert second.status_code == 200, second.text
    assert second.json()["engine_state"]["debate"]["phase"] == "awaiting_reflection"
    assert "shared with your instructor" in second.json()["messages"][-1]["content"]
    assert client.post(f"{path}/complete", headers=student_headers).status_code == 422
    reflection_request = {
        "summary": "I now see that meaningful assistance needs a clear boundary, and I would revise my position to distinguish editing from generation.",
        "request_id": str(uuid4()),
    }
    reflected = client.post(f"{path}/reflection", headers=student_headers, json=reflection_request)
    assert reflected.status_code == 200, reflected.text
    assert reflected.json()["engine_state"]["debate"]["phase"] == "ready_to_submit"
    duplicate = client.post(f"{path}/reflection", headers=student_headers, json=reflection_request)
    assert duplicate.status_code == 200
    assert duplicate.json()["messages"] == reflected.json()["messages"]
    completed = client.post(f"{path}/complete", headers=student_headers)
    assert completed.status_code == 200, completed.text
    assert completed.json()["status"] == "completed"
    assert completed.json()["result"] == {
        "message_count": 2,
        "student_reflection": reflection_request["summary"],
    }
    assert client.post(f"{path}/messages", headers=student_headers, json={
        "message": "A late extra turn", "request_id": str(uuid4()),
    }).status_code == 409

    review = client.get(f"{path}/debate-review", headers=professor_headers)
    assert review.status_code == 200, review.text
    assert review.json()["students"][0]["student_reflection"] == reflection_request["summary"]
    assert review.json()["students"][0]["status"] == "completed"
    assert client.get(f"{path}/debate-review", headers=student_headers).status_code == 403
    assert client.get(f"{path}/debate-review", headers=roster["headers"]["other_prof"]).status_code == 403


def test_debate_requires_a_substantive_scenario(client, roster):
    response = client.post(
        "/api/platform/assignments",
        headers=roster["headers"]["prof"],
        json={
            "course_id": roster["course"],
            "tool": "debate",
            "title": "Invalid debate",
            "audience": "selected",
            "recipient_ids": [roster["student"]],
            "config": {"scenario": "Too short"},
        },
    )
    assert response.status_code == 422


def test_debate_ai_failure_keeps_the_turn_retryable(client, roster, monkeypatch):
    item, _ = create_debate(client, roster)
    path = f"/api/platform/assignments/{item['id']}"
    professor_headers = roster["headers"]["prof"]
    student_headers = roster["headers"]["student"]
    assert client.post(path + "/publish", headers=professor_headers).status_code == 200
    started = client.post(path + "/start", headers=student_headers).json()

    async def unavailable(*_args, **_kwargs):
        raise HTTPException(503, "The Debate AI is unavailable. Please retry shortly.")

    monkeypatch.setattr(engines.debate, "generate_reply", unavailable)
    request = {"message": "Disclosures can make authorship clearer.", "request_id": str(uuid4())}
    failed = client.post(path + "/messages", headers=student_headers, json=request)
    assert failed.status_code == 503
    unchanged = client.get(path + "/attempt", headers=student_headers).json()
    assert unchanged["messages"] == started["messages"]
    assert unchanged["engine_state"]["debate"]["student_turns"] == 0

    async def recovered(*_args, **_kwargs):
        return "What important exception should the policy address?"

    monkeypatch.setattr(engines.debate, "generate_reply", recovered)
    retried = client.post(path + "/messages", headers=student_headers, json=request)
    assert retried.status_code == 200
    assert retried.json()["engine_state"]["debate"]["student_turns"] == 1


def test_debate_uses_optional_published_documents(client, roster, monkeypatch):
    monkeypatch.setattr(
        engines.db,
        "list_rag_files",
        lambda **_: [{"document_id": "doc-1"}],
    )
    item, config = create_debate(client, roster, document_ids=["doc-1"])
    path = f"/api/platform/assignments/{item['id']}"
    monkeypatch.setattr(
        engines.db,
        "snapshot_document_chunks",
        lambda *_: [
            {
                "document_id": "doc-1",
                "chunk_id": "chunk-1",
                "title": "Course policy",
                "text": "Disclosures should distinguish editing from generating content.",
                "embedding": [0.1, 0.2],
            }
        ],
    )
    assert client.post(path + "/publish", headers=roster["headers"]["prof"]).status_code == 200

    source = Source(
        document_id="doc-1",
        chunk_id="chunk-1",
        title="Course policy",
        text="Disclosures should distinguish editing from generating content.",
        score=1.0,
    )
    retrievals = []
    monkeypatch.setattr(
        engines.rag,
        "retrieve_snapshot",
        lambda query, chunks, top_k: retrievals.append((query, chunks, top_k)) or [source],
    )
    received_sources = []

    async def challenge(scenario, history, student_message, sources=None):
        received_sources.extend(sources or [])
        return "The policy distinguishes types of assistance. Where should it draw the line?"

    monkeypatch.setattr(engines.debate, "generate_reply", challenge)
    student_headers = roster["headers"]["student"]
    assert client.post(path + "/start", headers=student_headers).status_code == 200
    response = client.post(
        path + "/messages",
        headers=student_headers,
        json={"message": "All AI use should be disclosed.", "request_id": str(uuid4())},
    )
    assert response.status_code == 200, response.text
    assert retrievals[0][2] == 4
    assert config["scenario"] in retrievals[0][0]
    assert received_sources == [source]
    assert response.json()["engine_state"]["sources"][0]["title"] == "Course policy"
