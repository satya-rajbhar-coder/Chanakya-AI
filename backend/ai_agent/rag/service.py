import logging
import re
from dataclasses import dataclass
from uuid import NAMESPACE_URL, UUID, uuid5

from langchain_core.documents import Document as LCDocument
from langchain_text_splitters import RecursiveCharacterTextSplitter
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from core.config import settings
from database.session import engine

from .loader import EmptyDocumentError, PageText, extract_pages
from .vector_store import get_pgvector_store

logger = logging.getLogger(__name__)

SOURCES_MARKER = "\n\n---\n**Sources:**"
EMBED_BATCH_SIZE = 32
_TABLE_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _vector_table() -> str:
    table = settings.VECTOR_COLLECTION
    if not _TABLE_PATTERN.fullmatch(table):
        raise ValueError(f"Invalid vector table name: {table!r}")
    return table


@dataclass(frozen=True)
class RetrievedChunk:
    content: str
    filename: str
    page: int | None
    distance: float
    chunk_index: int = 0


def _safe_int(value) -> int | None:
    try:
        return None if value is None else int(value)
    except (TypeError, ValueError):
        return None


def _build_chunks(
    *,
    user_id: UUID,
    document_id: UUID,
    filename: str,
    pages: list[PageText],
) -> list[LCDocument]:
    """Split extracted pages into chunks. Only the metadata PGVectorStore
    persists is stored: user_id, document_id, filename, page, chunk_index.
    Chunk identity is the deterministic UUIDv5 id created in
    :func:`ingest_document`; no manual content hashes are kept.
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.CHUNK_SIZE,
        chunk_overlap=settings.CHUNK_OVERLAP,
    )

    chunks: list[LCDocument] = []
    chunk_index = 0
    for page in pages:
        text = (page.text or "").strip()
        if not text:
            continue

        for piece in splitter.split_text(text):
            piece = piece.strip()
            if not piece:
                continue

            chunks.append(
                LCDocument(
                    page_content=piece,
                    metadata={
                        "user_id": str(user_id),
                        "document_id": str(document_id),
                        "filename": filename,
                        "page": page.page,
                        "chunk_index": chunk_index,
                    },
                )
            )
            chunk_index += 1
    return chunks


def _create_chunk_id(document_id: UUID, chunk_index: int) -> str:
    return str(uuid5(NAMESPACE_URL, f"{document_id}:{chunk_index}"))


def ingest_document(
    *, user_id: UUID, document_id: UUID, filename: str, data: bytes
) -> int:
    logger.info("Starting ingestion: filename=%s document_id=%s", filename, document_id)

    pages = extract_pages(filename, data)
    chunks = _build_chunks(
        user_id=user_id,
        document_id=document_id,
        filename=filename,
        pages=pages,
    )
    if not chunks:
        raise EmptyDocumentError("No text could be extracted from this file")

    ids = [_create_chunk_id(document_id, i) for i in range(len(chunks))]
    store = get_pgvector_store()

    try:
        for start in range(0, len(chunks), EMBED_BATCH_SIZE):
            end = start + EMBED_BATCH_SIZE
            store.add_documents(chunks[start:end], ids=ids[start:end])
            logger.info(
                "Stored chunks %s-%s/%s for %s",
                start,
                min(end, len(chunks)),
                len(chunks),
                filename,
            )
    except (SQLAlchemyError, ValueError, RuntimeError):
        logger.exception("Ingestion failed. Rolling back chunks: %s", document_id)
        try:
            delete_document_chunks(document_id)
        except SQLAlchemyError:
            logger.exception("Rollback of chunks failed for %s", document_id)
        raise

    logger.info("Ingestion complete: filename=%s chunks=%s", filename, len(chunks))
    return len(chunks)


def _delete_where(column: str, value: str) -> None:
    if column not in {"document_id", "user_id"}:
        raise ValueError("Invalid column")
    table = _vector_table()
    with engine.begin() as conn:
        conn.execute(text(f'DELETE FROM "{table}" WHERE {column} = :v'), {"v": value})


def delete_document_chunks(document_id: UUID) -> None:
    _delete_where("document_id", str(document_id))


def delete_user_chunks(user_id: UUID) -> None:
    _delete_where("user_id", str(user_id))


def _keyword_search(document_ids: list[str], query: str, k: int) -> list[dict]:
    """Full-text keyword search over document chunks using PostgreSQL FTS."""
    table = _vector_table()
    params: dict = {"q": query, "k": k}
    id_clauses = []
    for i, doc_id in enumerate(document_ids):
        param_name = f"doc_id_{i}"
        params[param_name] = doc_id
        id_clauses.append(f":{param_name}")
    id_list = ", ".join(id_clauses)

    sql = text(f"""
    SELECT document_id, chunk_index, content, filename, page,
               ts_rank_cd(to_tsvector('english', content), plainto_tsquery('english', :q)) AS rank
        FROM "{table}"
        WHERE document_id IN ({id_list})
          AND to_tsvector('english', content) @@ plainto_tsquery('english', :q)
        ORDER BY rank DESC
        LIMIT :k
        """)

    with engine.connect() as conn:
        rows = conn.execute(sql, params).mappings().all()

    return [
        {
            "document_id": str(r["document_id"]),
            "chunk_index": int(r["chunk_index"] or 0),
            "content": r["content"],
            "filename": r["filename"] or "document",
            "page": _safe_int(r["page"]),
        }
        for r in rows
    ]


def _rrf_combine(
    vector_keys: list[tuple[str, int]],
    keyword_keys: list[tuple[str, int]],
    top_k: int,
    rrf_k: int = 60,
) -> list[tuple[str, int]]:
    """Combine vector and keyword rankings via Reciprocal Rank Fusion."""
    scores: dict[tuple[str, int], float] = {}
    for rank, key in enumerate(vector_keys, start=1):
        scores[key] = scores.get(key, 0.0) + 1.0 / (rrf_k + rank)
    for rank, key in enumerate(keyword_keys, start=1):
        scores[key] = scores.get(key, 0.0) + 1.0 / (rrf_k + rank)

    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    return [key for key, _ in ranked[:top_k]]


def retrieve(
    document_ids: list[UUID],
    query: str,
    k: int | None = None,
) -> list[RetrievedChunk]:
    """Hybrid retrieval: vector similarity + PostgreSQL full-text search fused
    with Reciprocal Rank Fusion. Results stay in relevance (fusion) order so
    the most useful excerpts reach the LLM first.
    """
    if not document_ids:
        return []
    store = get_pgvector_store()
    top_k = k if k is not None else settings.RETRIEVER_K
    visible = {str(doc_id) for doc_id in document_ids}

    # --- 1) Vector similarity pass ---
    vector_results = store.similarity_search_with_score(
        query,
        k=top_k,
        filter={"document_id": {"$in": sorted(visible)}},
    )
    vector_keys: list[tuple[str, int]] = []
    vector_meta: dict[tuple[str, int], dict] = {}
    vector_distances: dict[tuple[str, int], float] = {}
    for doc, raw_distance in vector_results:
        distance = float(raw_distance)
        if (
            settings.RAG_MAX_DISTANCE is not None
            and distance > settings.RAG_MAX_DISTANCE
        ):
            continue

        metadata = doc.metadata or {}
        document_id = str(metadata.get("document_id", ""))
        if document_id not in visible:
            continue
        chunk_index = _safe_int(metadata.get("chunk_index")) or 0
        key = (document_id, chunk_index)
        vector_keys.append(key)
        vector_distances.setdefault(key, distance)
        vector_meta.setdefault(
            key,
            {
                "content": doc.page_content,
                "filename": str(metadata.get("filename", "document")),
                "page": _safe_int(metadata.get("page")),
            },
        )

    # --- 2) Full-text keyword pass (hybrid boost) ---
    keyword_keys: list[tuple[str, int]] = []
    keyword_meta: dict[tuple[str, int], dict] = {}
    try:
        rows = _keyword_search(sorted(visible), query, top_k)
        for row in rows:
            key = (row["document_id"], row["chunk_index"])
            keyword_keys.append(key)
            keyword_meta.setdefault(key, row)
    except Exception:
        # Keyword search is a best-effort boost; never fail the whole retrieval.
        logger.exception("Keyword search failed; continuing with vector-only results")

    # --- 3) Reciprocal Rank Fusion ---
    fused_keys = _rrf_combine(vector_keys, keyword_keys, top_k)

    # --- 4) Build final chunks in fusion order, deduplicated ---
    final: list[RetrievedChunk] = []
    seen: set[tuple[str, int]] = set()
    for document_id, chunk_index in fused_keys:
        if document_id not in visible:
            continue
        key = (document_id, chunk_index)
        if key in seen:
            continue
        seen.add(key)

        meta = vector_meta.get(key) or keyword_meta.get(key)
        if meta is None:
            continue

        final.append(
            RetrievedChunk(
                content=meta["content"],
                filename=meta["filename"],
                page=meta["page"],
                distance=vector_distances.get(key, 0.0),
                chunk_index=chunk_index,
            )
        )

    return final


def format_context(chunks: list[RetrievedChunk]) -> str:
    return "\n\n---\n\n".join(chunk.content for chunk in chunks)


def format_sources(chunks: list[RetrievedChunk]) -> str:
    by_file: dict[str, set[int]] = {}
    for chunk in chunks:
        pages = by_file.setdefault(chunk.filename.replace("`", "'"), set())
        if chunk.page is not None:
            pages.add(chunk.page)

    parts = []
    for filename, pages in by_file.items():
        if pages:
            label = ", ".join(str(p) for p in sorted(pages))
            parts.append(f"`{filename}` (p. {label})")
        else:
            parts.append(f"`{filename}`")
    return f"{SOURCES_MARKER} " + " · ".join(parts)


def strip_sources(value: str) -> str:
    return value.split(SOURCES_MARKER, 1)[0]
