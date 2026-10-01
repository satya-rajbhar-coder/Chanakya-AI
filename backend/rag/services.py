"""RAG pipeline: split -> embed -> store (ingest) and embed query -> search (retrieve)."""

import logging
from dataclasses import dataclass
from uuid import UUID

from langchain_core.documents import Document as LCDocument
from langchain_text_splitters import RecursiveCharacterTextSplitter

from core.config import settings

from .loader import EmptyDocumentError, extract_pages
from .vector_store import get_pgvector_store

logger = logging.getLogger(__name__)

SOURCES_MARKER = "\n\n---\n**Sources:**"
EMBED_BATCH_SIZE = 32


@dataclass(frozen=True)
class RetrievedChunk:
    content: str
    filename: str
    page: int | None
    distance: float


# ------------------------------------------------------------------ ingest
def ingest_document(
    *, user_id: UUID, document_id: UUID, filename: str, data: bytes
) -> int:
    """Extract, chunk, embed and store a document. Returns the chunk count."""
    pages = extract_pages(filename, data)

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.CHUNK_SIZE,
        chunk_overlap=settings.CHUNK_OVERLAP,
    )

    chunks: list[LCDocument] = []
    for page in pages:
        for piece in splitter.split_text(page.text):
            piece = piece.strip()
            if not piece:
                continue
            metadata: dict[str, str | int] = {
                "user_id": str(user_id),
                "document_id": str(document_id),
                "filename": filename,
            }
            if page.page is not None:
                metadata["page"] = page.page
            chunks.append(LCDocument(page_content=piece, metadata=metadata))

    if not chunks:
        raise EmptyDocumentError("No text could be extracted from this file")

    ids = [f"{document_id}:{i}" for i in range(len(chunks))]
    store = get_pgvector_store()

    try:
        for start in range(0, len(chunks), EMBED_BATCH_SIZE):
            end = start + EMBED_BATCH_SIZE
            store.add_documents(chunks[start:end], ids=ids[start:end])
    except Exception:
        delete_document_chunks(document_id)
        raise

    return len(chunks)


# ------------------------------------------------------------------ delete
def _delete_where(where: dict[str, str]) -> None:
    store = get_pgvector_store()
    existing = store.get(where=where)
    ids = existing.get("ids", [])
    if ids:
        store.delete(ids=ids)


def delete_document_chunks(document_id: UUID) -> None:
    _delete_where({"document_id": str(document_id)})


def delete_user_chunks(user_id: UUID) -> None:
    _delete_where({"user_id": str(user_id)})


# ---------------------------------------------------------------- retrieve
def retrieve(user_id: UUID, query: str, k: int | None = None) -> list[RetrievedChunk]:
    """Top-k chunks from this user's documents only."""
    store = get_pgvector_store()
    results = store.similarity_search_with_score(
        query,
        k=k or settings.RETRIEVER_K,
        filter={"user_id": str(user_id)},
    )

    chunks: list[RetrievedChunk] = []
    for doc, distance in results:
        if (
            settings.RAG_MAX_DISTANCE is not None
            and distance > settings.RAG_MAX_DISTANCE
        ):
            continue
        chunks.append(
            RetrievedChunk(
                content=doc.page_content,
                filename=str(doc.metadata.get("filename", "document")),
                page=doc.metadata.get("page"),
                distance=float(distance),
            )
        )
    return chunks


# -------------------------------------------------------------- formatting
def format_context(chunks: list[RetrievedChunk]) -> str:
    blocks = []
    for index, chunk in enumerate(chunks, start=1):
        location = f", page {chunk.page}" if chunk.page is not None else ""
        blocks.append(f"[{index}] {chunk.filename}{location}\n{chunk.content}")
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


def strip_sources(text: str) -> str:
    return text.split(SOURCES_MARKER, 1)[0]
