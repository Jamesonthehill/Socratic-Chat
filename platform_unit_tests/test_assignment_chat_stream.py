import asyncio
import json
from uuid import uuid4

from app.pipeline_logging import publish_event
from platform_app import routes
from platform_app.schemas import MessageInput


def test_assignment_message_stream_reports_real_stages_then_saved_attempt(monkeypatch):
    assignment_id = uuid4()
    body = MessageInput(message="My answer", request_id=uuid4())

    def save_message(received_id, received_body, account):
        assert received_id == assignment_id
        assert received_body == body
        assert account == {"user_id": "student"}
        publish_event("assignment_chat_received")
        publish_event("classifier_llm_started")
        publish_event("message_classification_completed", retrieval_query="how the machine checks bread")
        publish_event("llm_request_started")
        return {"id": "attempt-1", "messages": [{"role": "assistant", "content": "Reply"}]}

    monkeypatch.setattr(routes, "message", save_message)

    async def receive():
        response = await routes.message_stream(assignment_id, body, {"user_id": "student"})
        return [json.loads(line) async for line in response.body_iterator]

    events = asyncio.run(receive())
    assert [event.get("stage") for event in events[:-1]] == ["received", "understanding", "understood", "drafting"]
    assert events[-2]["understanding"] == "how the machine checks bread"
    assert events[-1]["type"] == "result"
    assert events[-1]["data"]["messages"][0]["content"] == "Reply"
