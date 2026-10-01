import hashlib
import logging
from dataclasses import dataclass
from uuid import NAMESPACE_URL, UUID, uuid5

from langchain_core.documents import Document as LCDocument
from langchain_text_splitters import RecursiveCharacterTextSplitter
from sqlalchemy import text

from core.config import settings
from database.session import engine

from .loader import EmptyDocumentError, PageText, extract_pages
from .vector_store import get_pgvector_store

logger = logging.getLogger(__name__)

SOURCES_MARKER = "\n\n---\n**Sources:**"
EMBED_BATCH_SIZE = 32
DEFAULT_NEIGHBOR_WINDOW = 1
_TABLE = settings.VECTOR_COLLECTION  # trusted config value


@dataclass(frozen=True)
class RetrievedChunk:
    content: str
    filename: str
    page: int | None
    distance: float
    chunk_index: int = 0
    element_type: str = "text"


# ------------------------------------------------------------ helpers
def calculate_file_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def calculate_text_hash(value: str) -> str:
    normalized = " ".join(value.lower().split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _safe_int(value) -> int | None:
    try:
        return None if value is None else int(value)
    except TypeError, ValueError:
        return None


def _normalize_table(value: str) -> str:
    lines = [l.strip() for l in value.splitlines() if l.strip()]
    if len(lines) < 2 or "|" not in lines[0]:
        return value

    headers = [c.strip() for c in lines[0].strip("|").split("|")]
    start = 1
    if all(set(c.strip()) <= {"-", ":", " "} for c in lines[1].strip("|").split("|")):
        start = 2

    rows = []
    for line in lines[start:]:
        if "|" not in line:
            continue
        values = [c.strip() for c in line.strip("|").split("|")]
        parts = []
        for i, v in enumerate(values):
            if not v:
                continue
            header = (
                headers[i] if i < len(headers) and headers[i] else f"Column {i + 1}"
            )
            parts.append(f"{header}: {v}")
        if parts:
            rows.append(" | ".join(parts))

    if not rows:
        return value
    return "Table:\n" + "\n".join(f"Row {i}: {r}" for i, r in enumerate(rows, start=1))


def _normalize_element(page: PageText) -> str:
    value = page.text.strip()
    if not value:
        return ""
    if page.element_type == "table":
        return _normalize_table(value)
    return value


def _build_chunks(
    *,
    user_id: UUID,
    document_id: UUID,
    filename: str,
    pages: list[PageText],
    source_hash: str,
) -> list[LCDocument]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.CHUNK_SIZE,
        chunk_overlap=settings.CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", "。 ", "! ", "? ", "; ", ", ", " ", ""],
    )

    chunks: list[LCDocument] = []
    for page in pages:
        normalized = _normalize_element(page)
        if not normalized:
            continue

        for piece in splitter.split_text(normalized):
            piece = piece.strip()
            if not piece:
                continue

            metadata: dict[str, str | int] = {
                "user_id": str(user_id),
                "document_id": str(document_id),
                "filename": filename,
                "source_hash": source_hash,
                "element_type": page.element_type,
                "content_hash": calculate_text_hash(piece),
            }
            if page.page is not None:
                metadata["page"] = page.page
            for key, value in (page.metadata or {}).items():
                metadata.setdefault(key, value)

            chunks.append(LCDocument(page_content=piece, metadata=metadata))

    total = len(chunks)
    for index, chunk in enumerate(chunks):
        chunk.metadata["chunk_index"] = index
        chunk.metadata["total_chunks"] = total
    return chunks


def _create_chunk_id(document_id: UUID, chunk_index: int) -> str:
    return str(uuid5(NAMESPACE_URL, f"{document_id}:{chunk_index}"))


def ingest_document(
    *, user_id: UUID, document_id: UUID, filename: str, data: bytes
) -> int:
    source_hash = calculate_file_hash(data)
    logger.info("Starting ingestion: filename=%s document_id=%s", filename, document_id)

    pages = extract_pages(filename, data)
    chunks = _build_chunks(
        user_id=user_id,
        document_id=document_id,
        filename=filename,
        pages=pages,
        source_hash=source_hash,
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
    except Exception:
        logger.exception("Ingestion failed. Rolling back chunks: %s", document_id)
        try:
            delete_document_chunks(document_id)
        except Exception:
            logger.exception("Rollback of chunks failed for %s", document_id)
        raise

    logger.info("Ingestion complete: filename=%s chunks=%s", filename, len(chunks))
    return len(chunks)


def _delete_where(column: str, value: str) -> None:
    if column not in {"document_id", "user_id"}:
        raise ValueError("Invalid column")
    with engine.begin() as conn:
        conn.execute(text(f'DELETE FROM "{_TABLE}" WHERE {column} = :v'), {"v": value})


def delete_document_chunks(document_id: UUID) -> None:
    _delete_where("document_id", str(document_id))


def delete_user_chunks(user_id: UUID) -> None:
    _delete_where("user_id", str(user_id))


def _get_neighbor_chunks(
    *, user_id: UUID, document_id: str, chunk_index: int, window: int, distance: float
) -> list[RetrievedChunk]:
    sql = text(f'''
        SELECT content, filename, page, chunk_index, element_type
        FROM "{_TABLE}"
        WHERE user_id = :u AND document_id = :d
          AND chunk_index BETWEEN :lo AND :hi
        ORDER BY chunk_index
        ''')

    with engine.connect() as conn:
        rows = (
            conn.execute(
                sql,
                {
                    "u": str(user_id),
                    "d": document_id,
                    "lo": max(0, chunk_index - window),
                    "hi": chunk_index + window,
                },
            )
            .mappings()
            .all()
        )

    return [
        RetrievedChunk(
            content=r["content"],
            filename=r["filename"] or "document",
            page=r["page"],
            distance=distance,
            chunk_index=r["chunk_index"] or 0,
            element_type=r["element_type"] or "text",
        )
        for r in rows
    ]


def retrieve(
    user_id: UUID,
    query: str,
    k: int | None = None,
    neighbor_window: int = DEFAULT_NEIGHBOR_WINDOW,
) -> list[RetrievedChunk]:
    store = get_pgvector_store()
    top_k = k if k is not None else settings.RETRIEVER_K

    results = store.similarity_search_with_score(
        query,
        k=top_k,
        filter={"user_id": str(user_id)},
    )

    final: list[RetrievedChunk] = []
    seen: set[tuple[str, int]] = set()

    for doc, distance in results:
        distance = float(distance)
        if (
            settings.RAG_MAX_DISTANCE is not None
            and distance > settings.RAG_MAX_DISTANCE
        ):
            continue

        metadata = doc.metadata or {}
        document_id = str(metadata.get("document_id", ""))
        chunk_index = _safe_int(metadata.get("chunk_index")) or 0

        neighbors = _get_neighbor_chunks(
            user_id=user_id,
            document_id=document_id,
            chunk_index=chunk_index,
            window=neighbor_window,
            distance=distance,
        ) or [
            RetrievedChunk(
                content=doc.page_content,
                filename=str(metadata.get("filename", "document")),
                page=_safe_int(metadata.get("page")),
                distance=distance,
                chunk_index=chunk_index,
                element_type=str(metadata.get("element_type", "text")),
            )
        ]

        for n in neighbors:
            key = (document_id, n.chunk_index)
            if key in seen:
                continue
            seen.add(key)
            final.append(n)

    final.sort(key=lambda c: (c.filename, c.chunk_index))
    return final


def format_context(chunks: list[RetrievedChunk]) -> str:
    blocks = []
    for index, chunk in enumerate(chunks, start=1):
        location = f", page {chunk.page}" if chunk.page is not None else ""
        blocks.append(
            f"[{index}] {chunk.filename}{location} [chunk {chunk.chunk_index}]\n{chunk.content}"
        )
    return "\n\n".join(blocks)


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
