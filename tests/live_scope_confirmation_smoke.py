"""Optional local Ollama smoke check for assignment-scoped term questions."""
import asyncio
import os
from uuid import uuid4

from dotenv import load_dotenv

load_dotenv(".env")
os.environ["LLM_PROVIDER"] = "ollama"
os.environ["EMBEDDING_PROVIDER"] = "ollama"

from app import rag, settings  # noqa: E402
from platform_app import engines  # noqa: E402


async def main():
    passage = (
        'Prompt user "What would you like? (small/ medium/ large / off/ report )". '
        "A prompt asks for input. When the user chooses small, check resources before accepting coins."
    )
    chunk = {
        "document_id": "local-prompt-doc", "chunk_id": "local-prompt-chunk",
        "title": "Sandwich requirements.pdf", "text": passage,
        "embedding": rag.create_embeddings([passage])[0],
        "embedding_model": settings.embedding_model_name(), "metadata": {},
    }
    assignment = {
        "id": uuid4(), "tool": "socratic", "title": "Sandwich Maker",
        "snapshot": {"config": {"scope_mode": "assignment"}, "chunks": [chunk]},
    }
    attempt = {
        "id": uuid4(),
        "messages": [{"role": "assistant", "content": "The prompt asks what you would like."}],
        "engine_state": {"socratic": {"learning_topic": "Sandwich Maker"}},
    }
    question = "what is the prompt here, its like a step or order?"
    result = await engines._socratic_message(assignment, attempt, question)
    print("explanation:", " ".join(result["reply"].split()), flush=True)
    assert "prompt" in result["reply"].casefold()
    assert not result.get("clarification_only")
    assert not result["socratic"].get("clarification_options")


if __name__ == "__main__":
    asyncio.run(main())
