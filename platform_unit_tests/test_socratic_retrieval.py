from app.schemas import Source
from platform_app import engines


def test_assignment_retrieval_merges_queries_and_reranks_for_student_question(monkeypatch):
    def source(chunk_id, text):
        return Source(document_id="selected-doc", chunk_id=chunk_id,
                      title="Selected assignment", text=text, score=0.02)

    ingredients = source("ingredients", "Check bread ham and cheese before making a sandwich.")
    refund = source("refund", "Refund the customer's money when payment is insufficient.")
    menu = source("menu", "Show the customer the sandwich size menu.")
    calls = []

    def retrieve(query, _chunks, top_k):
        calls.append((query, top_k))
        return [ingredients, refund] if query.startswith("When") else [ingredients, menu]

    monkeypatch.setattr(engines.rag, "retrieve_snapshot", retrieve)
    results = engines._retrieve_assignment_sources(
        "When payment is insufficient, how does the machine refund money?",
        [{"document_id": "selected-doc"}],
        ["sandwich ingredients"],
    )

    assert [item.chunk_id for item in results] == ["refund", "ingredients", "menu"]
    assert calls == [
        ("When payment is insufficient, how does the machine refund money?", 8),
        ("sandwich ingredients", 8),
    ]


def test_primary_semantic_match_is_not_displaced_by_weak_extra_query(monkeypatch):
    primary = Source(document_id="selected-doc", chunk_id="primary", title="Selected assignment",
                     text="The machine returns excess funds after a transaction.", score=0.03)
    extra = Source(document_id="selected-doc", chunk_id="extra", title="Selected assignment",
                   text="The customer may choose a sandwich size.", score=0.03)

    def retrieve(query, _chunks, top_k):
        return [primary] if query.startswith("How") else [extra]

    monkeypatch.setattr(engines.rag, "retrieve_snapshot", retrieve)
    results = engines._retrieve_assignment_sources(
        "How does the customer get change?", [{}], ["customer sandwich"],
    )

    assert [item.chunk_id for item in results] == ["primary", "extra"]
