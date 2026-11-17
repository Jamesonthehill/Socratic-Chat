import asyncio
from unittest.mock import AsyncMock
from app import portfolio_demo as demo, settings


def test_guided_demo_restores_context_and_advances():
    async def run():
        start = await demo.guided_turn(demo.Turn(action="start"))
        state = start["socratic"]
        original = state["next_thinking_step"]
        state["learning_detour"] = {"question": original, "scenario": demo.STEPS[0]["scenario"]}
        resumed = await demo.guided_turn(demo.Turn(action="resume", history=start["messages"], engine_state=state))
        assert original in resumed["messages"][-1]["content"]
        assert demo.STEPS[0]["scenario"] in resumed["messages"][-1]["content"]
        state["step_readiness"] = {"ready": True}
        next_step = await demo.guided_turn(demo.Turn(action="continue", history=resumed["messages"], engine_state=state))
        assert next_step["socratic"]["learning_step_index"] == 1
        assert "step_readiness" not in next_step["socratic"]
    asyncio.run(run())


def test_demo_openai_override_is_scoped_to_request(monkeypatch):
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "test")
    monkeypatch.setattr(demo, "indexed_material", lambda: demo.CHUNKS)

    async def answer(*args):
        assert settings.llm_client_config("tutor")[0] == "OpenAI"
        return {"reply": "Why does that matter?", "socratic": {"phase": "teaching"}}
    monkeypatch.setattr(demo.engine, "_socratic_message", AsyncMock(side_effect=answer))

    async def run():
        start = await demo.guided_turn(demo.Turn(action="start"))
        result = await demo.guided_turn(demo.Turn(message="I need help", history=start["messages"], engine_state=start["socratic"]))
        assert result["messages"][-1]["content"] == "Why does that matter?"
        assert settings.PORTFOLIO_OPENAI.get() is False
    asyncio.run(run())


def test_guided_route_precedes_frontend_fallback():
    from app.main import app
    paths = [route.path for route in app.routes]
    assert paths.index("/api/public/guided") < paths.index("")
