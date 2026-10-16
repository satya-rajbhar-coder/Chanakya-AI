from uuid import uuid4

import pytest
from langchain_core.documents import Document as Chunk

from core.config import settings
from modules.analysis import catalog
from rag import service as rag_service


def test_select_tables_only_uses_assigned_database(monkeypatch):
    monkeypatch.setattr(settings, "ANALYSIS_TOP_TABLES", 3)
    calls = []
    class Store:
        def similarity_search_with_score(self, question, *, k, filter):
            calls.append(filter)
            return [(Chunk(page_content="", metadata={"db": "b", "table_name": "private"}), 0),
                    (Chunk(page_content="", metadata={"db": "a", "table_name": "allowed"}), 0)]
    monkeypatch.setattr(catalog, "get_schema_store", lambda: Store())
    monkeypatch.setattr(catalog, "describe_table", lambda db, table, question="": ("allowed(id int)", ()))
    assert catalog.select_tables("question", "a") == ("a", ["allowed"])
    assert calls == [{"db": "a"}]


def test_rejects_invalid_database_names():
    with pytest.raises(LookupError):
        catalog.select_tables("question", "other/assembly")


def test_description_bounds_columns(monkeypatch):
    monkeypatch.setattr(settings, "ANALYSIS_MAX_COLUMNS", 4)
    class Inspector:
        def has_table(self, table, schema=None):
            return True
        def get_pk_constraint(self, table, schema=None):
            return {"constrained_columns": ["id"]}
        def get_foreign_keys(self, table, schema=None):
            return []
        def get_columns(self, table, schema=None):
            return [{"name": "id", "type": "INT"}] + [
                {"name": f"extra_{i}", "type": "TEXT"} for i in range(100)
            ] + [{"name": "votes_total", "type": "INT"}]
        def get_table_names(self, schema=None):
            return ["records"]
    monkeypatch.setattr(catalog, "inspect", lambda engine: Inspector())
    monkeypatch.setattr(catalog, "get_engine", lambda db: None)
    catalog.describe_table.cache_clear()
    schema, _ = catalog.describe_table("records", "records", "votes total")
    assert "votes_total" in schema and "id" in schema
    assert schema.count(",") == 3


def test_rag_retrieval_filters_visible_document_ids(monkeypatch):
    doc_id = uuid4()
    calls = []
    class Store:
        def similarity_search_with_score(self, query, *, k, filter):
            calls.append(filter)
            return [(Chunk(page_content="allowed", metadata={"document_id": str(doc_id), "filename": "visible.txt"}), 0),
                    (Chunk(page_content="private", metadata={"document_id": str(uuid4())}), 0)]
    monkeypatch.setattr(rag_service, "get_pgvector_store", lambda: Store())
    monkeypatch.setattr(rag_service, "_get_neighbor_chunks", lambda **kw: [])
    assert rag_service.retrieve([], "question") == []
    chunks = rag_service.retrieve([doc_id], "question")
    assert [chunk.content for chunk in chunks] == ["allowed"]
    assert calls == [{"document_id": {"$in": [str(doc_id)]}}]
