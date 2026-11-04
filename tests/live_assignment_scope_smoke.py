"""Optional local-only smoke test: run with Ollama already listening on 11434."""
import asyncio
import os
from uuid import uuid4

from dotenv import load_dotenv

load_dotenv(".env")
os.environ["LLM_PROVIDER"] = "ollama"
os.environ["EMBEDDING_PROVIDER"] = "ollama"

from app import rag, settings  # noqa: E402
from platform_app import engines  # noqa: E402


def main():
    examples = [
        ("requirements.pdf", "Inventory", "Before accepting coins, the sandwich machine checks whether enough bread, ham, and cheese remain. If any ingredient is missing, it explains that the order cannot be made and does not charge the customer."),
        ("main.py", "Payment", "def accept_payment(inserted, price):\n    if inserted < price:\n        return 'insufficient coins'\n    return inserted - price"),
    ]
    vectors = rag.create_embeddings([text for _, _, text in examples])
    chunks = [{
        "document_id": f"test-doc-{index}", "chunk_id": f"test-chunk-{index}",
        "title": title, "text": text, "embedding": vector,
        "embedding_model": settings.embedding_model_name(),
        "metadata": {"section_path": [section]},
    } for index, ((title, section, text), vector) in enumerate(zip(examples, vectors, strict=True))]
    snapshot = {"config": {"scope_mode": "assignment", "prompt": ""}, "chunks": chunks,
                "concept_map": engines.assignment_concept_map(chunks)}
    assignment = {"id": uuid4(), "tool": "socratic", "title": "Sandwich Maker", "snapshot": snapshot}
    opening = engines.start(assignment, {"id": uuid4()})
    attempt = {"id": uuid4(), "messages": opening["messages"],
               "engine_state": {"socratic": opening["socratic"]}}
    print("opening:", opening["messages"][0]["content"][:260], flush=True)
    for index, question in enumerate(("How should inventory be checked before accepting payment?",
                                      "Now, what should the code do when the customer inserts too few coins?")):
        result = asyncio.run(engines._socratic_message(assignment, attempt, question))
        print("question:", question, flush=True)
        print("reply:", " ".join(result["reply"].split())[:700], flush=True)
        print("sources:", [source["title"] for source in result.get("sources", [])], flush=True)
        assert result.get("sources"), "A selected document must support each response."
        if index == 1:
            assert any(term in result["reply"].lower() for term in (
                "insufficient", "too few", "not enough", "fewer coins", "enough money",
                "enough coins", "less than the price",
            )), (
                "The follow-up must address insufficient payment, not return to inventory."
            )
        attempt["messages"].extend([{"role": "user", "content": question},
                                    {"role": "assistant", "content": result["reply"]}])
        attempt["engine_state"]["socratic"] = result["socratic"]


if __name__ == "__main__":
    main()
