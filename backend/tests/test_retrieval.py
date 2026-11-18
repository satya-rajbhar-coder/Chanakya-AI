"""Unit tests for the RAG retrieval layer (no database required).

These tests exercise :func:`rag.service.retrieve` and :func:`rag.service._rrf_combine`
with stubbed vector/keyword backends so they run without PostgreSQL.
"""

from uuid import uuid4

from langchain_core.documents import Document as LCDocument

from ai_agent.rag.service import RetrievedChunk, _rrf_combine, format_context, retrieve


def test_format_context_excludes_internal_chunk_metadata():
    context = format_context(
        [
            RetrievedChunk(
                content="Party composition: Shiv Sena 3",
                filename="ward-report.pdf",
                page=11,
                distance=0.1,
                chunk_index=62,
            )
        ]
    )

    assert context == "Party composition: Shiv Sena 3"
    assert "chunk" not in context.lower()
    assert "ward-report.pdf" not in context


def _chunk(document_id, chunk_index, content, distance=0.1):
    return LCDocument(
        page_content=content,
        metadata={
            "document_id": str(document_id),
            "chunk_index": chunk_index,
            "filename": "doc.pdf",
            "page": 1,
            "element_type": "text",
        },
    )


def test_rrf_combine_orders_by_fusion_score():
    document_id = uuid4()
    vector_keys = [(document_id, 0), (document_id, 1), (document_id, 2)]
    keyword_keys = [(document_id, 2), (document_id, 0)]
    ranked = _rrf_combine(vector_keys, keyword_keys, top_k=10)
    # (d,0): 1/61 + 1/62 > (d,2): 1/63 + 1/61 > (d,1): 1/62
    assert ranked == [(document_id, 0), (document_id, 2), (document_id, 1)]


def test_rrf_combine_caps_at_top_k():
    document_id = uuid4()
    vector_keys = [(document_id, i) for i in range(5)]
    keyword_keys = [(document_id, i) for i in range(5)]
    assert len(_rrf_combine(vector_keys, keyword_keys, top_k=3)) == 3


def test_retrieve_keeps_rrf_order_not_document_order(monkeypatch):
    """Fused chunks must reach the LLM in relevance order, not chunk-index order."""
    document_id = uuid4()
    chunks = {
        10: _chunk(document_id, 10, "chunk A content"),
        20: _chunk(document_id, 20, "chunk B content"),
        30: _chunk(document_id, 30, "chunk C content"),
        40: _chunk(document_id, 40, "chunk D content"),
    }

    class FakeStore:
        def similarity_search_with_score(self, query, k, filter):
            return [(chunks[10], 0.1), (chunks[20], 0.2), (chunks[30], 0.3)]

    def fake_neighbors(document_id, chunk_index, window, distance):
        return [
            RetrievedChunk(
                content=f"neighbor {chunk_index - 1}",
                filename="doc.pdf",
                page=1,
                distance=distance,
                chunk_index=chunk_index - 1,
            ),
            RetrievedChunk(
                content=chunks[chunk_index].page_content,
                filename="doc.pdf",
                page=1,
                distance=distance,
                chunk_index=chunk_index,
            ),
            RetrievedChunk(
                content=f"neighbor {chunk_index + 1}",
                filename="doc.pdf",
                page=1,
                distance=distance,
                chunk_index=chunk_index + 1,
            ),
        ]

    def fake_keyword(document_ids, query, k):
        return [
            {
                "document_id": str(document_id),
                "chunk_index": 20,
                "content": "chunk B content",
                "filename": "doc.pdf",
                "page": 1,
                "element_type": "text",
            },
            {
                "document_id": str(document_id),
                "chunk_index": 40,
                "content": "chunk D content",
                "filename": "doc.pdf",
                "page": 1,
                "element_type": "text",
            },
        ]

    monkeypatch.setattr("ai_agent.rag.service.get_pgvector_store", lambda: FakeStore())
    monkeypatch.setattr("ai_agent.rag.service._keyword_search", fake_keyword)

    result = retrieve([document_id], "any query")

    # RRF scores: chunk 20 (in both passes) > chunk 10 > chunk 40 > chunk 30.
    # Results stay in fusion (relevance) order, not chunk-index order.
    assert [c.chunk_index for c in result] == [20, 10, 40, 30]


def test_retrieve_dedups_chunks_found_by_both_passes(monkeypatch):
    document_id = uuid4()

    class FakeStore:
        def similarity_search_with_score(self, query, k, filter):
            return [(_chunk(document_id, 0, "shared"), 0.1)]

    def fake_keyword(document_ids, query, k):
        return [
            {
                "document_id": str(document_id),
                "chunk_index": 0,
                "content": "shared",
                "filename": "doc.pdf",
                "page": 1,
                "element_type": "text",
            }
        ]

    monkeypatch.setattr("ai_agent.rag.service.get_pgvector_store", lambda: FakeStore())
    monkeypatch.setattr("ai_agent.rag.service._keyword_search", fake_keyword)

    result = retrieve([document_id], "query")
    assert [c.chunk_index for c in result] == [0]
