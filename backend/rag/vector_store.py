import logging

from langchain_postgres import Column
from langchain_postgres.v2.engine import PGEngine
from langchain_postgres.v2.vectorstores import PGVectorStore

from core.config import settings
from rag.embeddings import get_google_embeddings

logger = logging.getLogger(__name__)

_pg_engine: PGEngine | None = None
_vector_store: PGVectorStore | None = None

METADATA_COLUMNS = [
    "user_id",
    "document_id",
    "filename",
    "source_hash",
    "content_hash",
    "page",
    "chunk_index",
    "total_chunks",
    "element_type",
]


def get_pg_engine() -> PGEngine:
    global _pg_engine
    if _pg_engine is None:
        _pg_engine = PGEngine.from_connection_string(url=settings.VECTOR_STORE_URL)
    return _pg_engine


def init_vector_store() -> None:
    get_pg_engine().init_vectorstore_table(
        table_name=settings.VECTOR_COLLECTION,
        vector_size=settings.VECTOR_DIMENSION,
        metadata_columns=[
            Column("user_id", "TEXT"),
            Column("document_id", "TEXT"),
            Column("filename", "TEXT"),
            Column("source_hash", "TEXT"),
            Column("content_hash", "TEXT"),
            Column("page", "INTEGER"),
            Column("chunk_index", "INTEGER"),
            Column("total_chunks", "INTEGER"),
            Column("element_type", "TEXT"),
        ],
        overwrite_existing=False,
    )
    logger.info("Vector store table ready: %s", settings.VECTOR_COLLECTION)


def get_pgvector_store() -> PGVectorStore:
    global _vector_store
    if _vector_store is None:
        _vector_store = PGVectorStore.create_sync(
            engine=get_pg_engine(),
            table_name=settings.VECTOR_COLLECTION,
            embedding_service=get_google_embeddings(),
            metadata_columns=METADATA_COLUMNS,
        )
    return _vector_store
