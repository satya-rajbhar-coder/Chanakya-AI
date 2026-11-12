# Chanakya AI — RAG Pipeline (Documents Q&A)

> **Document:** `docs/04_RAG_PIPELINE.md`  
> **Scope:** Document ingestion, chunking, embeddings, vector storage, retrieval, neighbor expansion, and context formatting for the Documents (RAG) chat mode.  
> **Source:** `backend/rag/` (`loader.py`, `service.py`, `embeddings.py`, `vector_store.py`) + `backend/llm/service.py` + `backend/modules/messages/services.py`.  
> **Diagrams:** `Architecture/Document Retrieval Sequence.png`, `Architecture/Document Storage Architecture.png`, `Architecture/Hybrid Search Architecture.png`.

---

## 1. Overview

The RAG pipeline answers user questions using **only** uploaded PDF/TXT/MD documents. It is a retrieve-then-generate flow:

1. **Ingest** (admin upload): extract text → chunk → embed → store in pgvector.
2. **Retrieve** (user query): embed query → similarity search (scoped to user's visible docs) → neighbor expansion → context blocks.
3. **Generate**: Groq LLM answers strictly from `<context>` excerpts; refuses with `NOT_FOUND` if unsupported.

File bytes are **never stored** — only extracted text and embeddings live in the vector store.

---

## 2. Supported Files & Limits

| Setting | Value | Source |
|---------|-------|--------|
| Extensions | `.pdf`, `.txt`, `.md` | extension-checked in loader/service |
| Max upload size | `MAX_UPLOAD_MB` (default 20) | `core/config.py` |
| Chunk size | `CHUNK_SIZE` (default 1000 chars) | `core/config.py` |
| Chunk overlap | `CHUNK_OVERLAP` (default 150 chars) | `core/config.py` |
| Retriever top-K | `RETRIEVER_K` (default 5) | `core/config.py` |
| Max distance cut-off | `RAG_MAX_DISTANCE` (optional) | `core/config.py` |
| Embedding dimension | `VECTOR_DIMENSION` (default 3072) | `core/config.py` |
| Embedding model | `GOOGLE_EMBEDDING_MODEL` | `core/config.py` |

---

## 3. Ingestion Flow (`POST /api/documents`, admin only)

```
admin upload (.pdf/.txt/.md + user_ids JSON)
        │
        ▼
validate extension + size (≤ MAX_UPLOAD_MB)
        │
        ▼
create Document row + DocumentAssignments (user_ids)
        │
        ▼
EXTRACT (loader.py)
├─ PDF → DoclingLoader (markdown export) on temp file
│    ├─ table elements (pipe-table detection)
│    └─ text blocks (≤3000 chars)
│    └─ fallback: pypdf page-by-page
│         ├─ empty-text & encrypted-PDF handled
│         └─ password-protected → error
│         └─ empty note: OCR would be needed
├─ TXT/MD → decoded UTF-8 (errors replaced)
        │
        ▼
CHUNK (service.py)
├─ Markdown tables normalized → "Row N: Header: value"
├─ RecursiveCharacterTextSplitter
│   separators: \n\n, \n, sentence/period, 。, ！, …
│   CHUNK_SIZE=1000, CHUNK_OVERLAP=150
└─ metadata per chunk: user_id, document_id, filename,
    source_hash (file SHA-256), element_type, content_hash
    (normalized text SHA-256), page, chunk_index, total_chunks
    deterministic chunk id: uuid5(document_id:index)
        │
        ▼
EMBED (embeddings.py)
└─ GoogleGenerativeAIEmbeddings, output_dimensionality=3072
        │
        ▼
STORE (vector_store.py)
└─ langchain-postgres PGVectorStore, table vector_documents,
   batched add (32/request) with ids
        │
        ▼
on failure → rollback (delete all chunks of document_id)
on success → commit DB, save chunk_count on Document row
```

**Visibility:** `get_all` is scoped — admins see all documents; users see only documents assigned to them via `document_assignments`. Deletion removes vectors first, then the Document row.

**Legacy note:** Uploads start unassigned (client_id nullable) and invisible to users; scope them via `PUT /api/admin/documents/{id}/assignments` — vectors are **reused** (no re-embedding).

---

## 4. Retrieval Flow (per user question)

1. Resolve the caller's **visible document_ids** (documents assigned to the user; admins see all).
2. `retrieve(visible_ids, question)`:
   - `similarity_search_with_score(query, k=RETRIEVER_K)` filtered by `document_ids` (`$in`).
   - Optional `RAG_MAX_DISTANCE` cut-off.
   - **Neighbor expansion:** ±`window=1` chunk index per hit via direct SQL; deduped; ordered by `filename + chunk_index` → coherent context blocks.
3. `format_context(chunks)` → numbered `[i] file (page p) [chunk N]` blocks.
4. `format_sources(chunks)` → appends `--- **Sources:** file (p. 3, 5) · …` footer.
5. `strip_sources()` removes the footer when replaying history.

---

## 5. Generation Flow (`llm/service.py`)

- **LLM:** `groq_llm = ChatGroq(model="openai/gpt-oss-120b", temperature=0.3)`. Optional local fallback `ChatOllama(model="qwen3.5", localhost:11434)` (commented out in generation call).
- **System prompt (`RAG_SYSTEM_PROMPT`):** "answer ONLY from `<context>` excerpts, Markdown OK, valid Mermaid rules, otherwise reply exactly `NOT_FOUND`" — hallucination-guarded.
- `generate_reply(history, user_content, context)` builds:
  `[System(context)] + history(Human/AI/…) + Human` and invokes Groq.
- `ENABLED_REMOVAL_OF_REASONING` — ````…``` blocks are stripped (`clean_model_text`).
- `is_not_found()` detects the refusal token so callers replace it with a friendly message.

---

## 6. Message Orchestration (`modules/messages/services.py`)

`MessageService.create_and_reply`:

1. Load last **20 messages** history (sources stripped).
2. Persist user message + bump `Conversation.updated_at`.
3. If user has **no visible documents** → static `NO_DOCUMENTS_REPLY`.
4. Retrieve context:
   - Short questions (<80 chars) are prefixed with the previous user message to form a better query.
   - Retrieval errors → **502** (never silent "not found").
5. If retrieval empty → `NOT_FOUND_REPLY` (no LLM cost).
6. Else call `generate_reply` (needs Groq; failure → 502) → `answer = raw + format_sources(chunks)` or `NOT_FOUND_REPLY` if refused.
7. Persist assistant message; first-message title update; commit; return **both messages**.

---

## 7. Vector Store (`rag/vector_store.py`)

- `PGEngine.from_connection_string(VECTOR_STORE_URL)` — separate engine from the app DB.
- `langchain_postgres.PGVectorStore` over table `vector_documents`, initialized at startup (`init_vector_store()` creates table if missing).
- Double-checked-locking singleton pattern.
- Typed metadata columns: `user_id`, `document_id`, `filename`, `source_hash`, `content_hash`, `page`, `chunk_index`, `total_chunks`, `element_type`.

---

## 8. Embeddings (`rag/embeddings.py`)

- Cached `GoogleGenerativeAIEmbeddings` instance.
- `output_dimensionality=VECTOR_DIMENSION (3072)`.
- Used both at ingest (chunks) and retrieve (query embedding).

---

## 9. Data Flow Summary

```
User question
    │
    ▼
Embed query (Google, 3072-dim)
    │
    ▼
pgvector similarity_search (k=5, filtered by visible doc_ids)
    │
    ▼
Optional distance cut-off (RAG_MAX_DISTANCE)
    │
    ▼
Neighbor expansion ±1 chunk index (direct SQL, dedupe, order by file+chunk)
    │
    ▼
format_context → numbered [i] blocks
    │
    ▼
Groq: System(<context>) + history + Human
    │
    ├─ NOT_FOUND → friendly reply (no sources)
    └─ answer + format_sources footer
    │
    ▼
Persist assistant message → return both messages
```

---

## 10. Limitations & Operational Notes

- Upload processing + embedding happens **inside the HTTP request** — set adequate proxy timeouts.
- Password-protected PDFs return an error; scanned/image-only PDFs need OCR (not implemented — empty note produced).
- `schema_catalog` + document vectors live in the **app/vector PostgreSQL**, never in analysis DBs; analysts cannot (re)build catalogs.
- Retrieval is scoped per-user; a user cannot retrieve chunks from documents they are not assigned to.
