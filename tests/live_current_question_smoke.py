"""Optional Ollama check that feedback follows the latest tutor question."""
import asyncio
import os
from uuid import uuid4

from dotenv import load_dotenv

load_dotenv(".env")
os.environ["LLM_PROVIDER"] = "ollama"
os.environ["EMBEDDING_PROVIDER"] = "ollama"

from app.schemas import Source  # noqa: E402
from platform_app import engines  # noqa: E402


async def main():
    source = Source(
        document_id="sandwich-requirements",
        chunk_id="sequence-1",
        title="Sandwich Maker Machine.pdf p. 1",
        text=(
            "First, users select the size of the sandwich. Then the machine checks "
            "whether there are enough resources. If ingredients are insufficient, "
            "it reports the missing resource and stops that order. Otherwise, it "
            "prompts the user to insert coins."
        ),
        score=1,
    )
    assignment = {
        "id": uuid4(), "tool": "socratic", "title": "Sandwich Maker",
        "snapshot": {"config": {"scope_mode": "assignment"}, "chunks": [
            {"document_id": source.document_id, "chunk_id": source.chunk_id,
             "title": source.title, "text": source.text, "metadata": {}},
        ]},
    }
    attempt = {
        "id": uuid4(),
        "messages": [
            {"role": "assistant", "content": "What is a prompt?"},
            {"role": "user", "content": "The question on the screen."},
            {"role": "assistant", "content": (
                "After you choose small, what does the machine do before asking for coins?"
            )},
        ],
        "engine_state": {"socratic": {
            "learning_topic": "prompt", "stable_concept": "prompt",
            "active_concept": "prompt",
        }},
    }
    engines._retrieve_assignment_sources = lambda *_args: [source]
    result = await engines._socratic_message(
        assignment, attempt, "it probably adds my order to the list",
    )
    print("Tutor reply:", result["reply"], flush=True)
    print("Feedback concept:", result["socratic"].get("latest_feedback", {}).get("concept"), flush=True)
    assert any(word in result["reply"].casefold() for word in ("resource", "ingredient"))
    assert "prompt is" not in result["reply"].casefold()
    assert "right that it might add" not in result["reply"].casefold()


if __name__ == "__main__":
    asyncio.run(main())
