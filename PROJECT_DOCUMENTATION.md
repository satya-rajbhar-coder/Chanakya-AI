# Chanakya AI — Full Project Documentation

> **What it is:** A multi-tenant, client-scoped **AI analytics & document Q&A workspace**.
> Company admins ingest documents and register client databases; analysts (dashboard users)
> ask **natural-language questions** and either (a) get answers grounded in uploaded PDF/TXT/MD
> documents (RAG), or (b) get a **generated, guarded, read-only SQL query** executed against
> their assigned PostgreSQL/MSSQL database, with paginated results, CSV export, history and
> saved analyses.
>
> **Stack:** FastAPI (Python 3.11+, uv) backend + Next.js 16 / React 19 frontend.
> LLM: **Groq** (`openai/gpt-oss-120b`). Embeddings: **Google** (`gemini` embedding, 3072-dim).
> Vector store: **PostgreSQL + pgvector** (langchain-postgres).

---

## Table of Contents

1. [High-Level Architecture](#1-high-level-architecture)
2. [Repository Layout](#2-repository-layout)
3. [Backend](#3-backend)
   - 3.1 [Structure & Conventions](#31-backend-structure--conventions)
   - 3.2 [Configuration (`core/config.py`)](#32-configuration)
   - 3.3 [Security & Authentication](#33-security--authentication)
   - 3.4 [Database Layer](#34-database-layer)
   - 3.5 [Data Model (ER overview)](#35-data-model-er-overview)
   - 3.6 [Module: auth / users](#36-module-auth--users)
   - 3.7 [Module: admin](#37-module-admin)
   - 3.8 [RAG Pipeline (`rag/`)](#38-rag-pipeline-rag)
   - 3.9 [LLM Client (`llm/`)](#39-llm-client-llm)
   - 3.10 [Module: conversations / messages](#310-module-conversations--messages)
   - 3.11 [Module: documents](#311-module-documents)
   - 3.12 [Module: analysis (NLP → SQL)](#312-module-analysis-nlp--sql)
   - 3.13 [Full API Surface](#313-full-api-surface)
   - 3.14 [Tests, Scripts & Tooling](#314-tests-scripts--tooling)
4. [Frontend](#4-frontend)
   - 4.1 [Structure & Stack](#41-frontend-structure--stack)
   - 4.2 [Auth/session flow (`proxy.ts`, axios, server session)](#42-authsession-flow)
   - 4.3 [Routing & Layout](#43-routing--layout)
   - 4.4 [State Management (`WorkspaceProvider`)](#44-state-management)
   - 4.5 [Service Layer](#45-service-layer)
   - 4.6 [Chat UI (Documents + Analysis tabs)](#46-chat-ui)
   - 4.7 [Markdown / Mermaid rendering](#47-markdown--mermaid-rendering)
   - 4.8 [Admin Panel](#48-admin-panel)
5. [End-to-End Flows](#5-end-to-end-flows)
6. [Security Model Summary](#6-security-model-summary)
7. [Environments & Deployment](#7-environments--deployment)
8. [Known Limitations & Operational Notes](#8-known-limitations--operational-notes)

---

## 1. High-Level Architecture

```
┌────────────────────────────────────────────────────────────────────────────┐
│                              BROWSER (user)                                │
│   Next.js 16 App Router · React 19 · Tailwind 4 · shadcn/ui                │
│   (protected)/ chat · /admin              login /register                  │
└────────────▲───────────────────────────────────────────────▲────────────────┘
             │ cookies (httpOnly access_token + refresh_token)│ /users/me (SSR)
             ▼                                               │
┌───────────────────────────────┐   ┌─────────────────────────┴──────────────┐
│ proxy.ts (Next middleware)    │   │ Route/session bootstrap: on Navigate,  │
│ redirect unauth → /login,     │   │ reads cookie → calls FastAPI /users/me │
│ transparent token refresh     │   └────────────────────────────────────────┘
└───────────────────────────────┘
             │  all API traffic: http(s)://…:8000/api
             ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                      FASTAPI BACKEND (uvicorn)                             │
│  lifespan: create_all() tables + init pgvector tables                      │
│                                                                            │
│  api/router.py ── auth ─ users ─ admin                                     │
│               └─ conversations ─ messages ─ documents ─ analysis           │
│                                                                            │
│  RAG path:   rag/loader → rag/service (chunks) → pgvector → llm/service    │
│  SQL path:   catalog/global_catalog → generator (Groq) → guard (sqlglot)   │
│              → executor/multi_executor → result-JWT → rows/export          │
└───────┬──────────────────┬─────────────────────────┬────────────────────────┘
        │                  │                         │
        ▼                  ▼                         ▼
┌───────────────┐  ┌────────────────────┐  ┌──────────────────────────────────┐
│ App PostgreSQL│  │ Vector PostgreSQL  │  │ Client databases (one per client)│
│ (SQLAlchemy)  │  │ (pgvector via      │  │ ANALYSIS_DB_URL_TEMPLATE={name}  │
│ users, tokens,│  │ langchain-postgres │  │ e.g. client147, client152 …      │
│ conversations │  │ google embeddings  │  │ Each exposes shared main-DB      │
│ messages,docs,│  │ vector_documents & │  │ tables through the postgres_fdw  │
│ clients, u-cl,│  │ schema_catalog     │  │ schema  pollmatrix.<table>       │
│ saved/history │  └────────────────────┘  │ (scripts/setup_main_db_fdw.sql)  │
└───────────────┘                          └──────────────────────────────────┘
        external: Groq API (text LLM) · Google Generative AI (embeddings)
```

- **Two chat modes in one workspace:** *Documents* (RAG Q&A, persistent conversations) and
  *Analysis* (NL → SQL over assigned client databases) — selected by a tab toggle.
- **Multi-tenant scoping:** everything is scoped by **client** (`clients` a.k.a. `UserClient`
  assignment) — documents via `document_assignments`, analysis via `user_clients`, and each
  client maps to one **exclusive database** (unique `database_name`).
- **Shared main-database tables** (client_master, executive_master, user_master,…) are never
  accessed by direct connection: every client DB holds a **foreign schema `pollmatrix`**
  (postgres_fdw) pointing at the main DB, so *all* SQL runs through the client connection only.

---

## 2. Repository Layout

```
D:\Satya\chanakya-ai\
├── Architecture\            ← 17 pre-rendered diagrams (PNG): hybrid search, query router,
│                               ER, deployment, security, SQL validation pipeline, …
└── chanakya-ai\
    ├── backend\
    │   ├── main.py                FastAPI app + CORS + lifespan
    │   ├── core\                  config (pydantic-settings), security (JWT/pwd), cookies
    │   ├── database\              SQLAlchemy base + engine/session (`get_db` dep)
    │   ├── api\                   Aggregated router + auth dependencies (CurrentUser/Admin)
    │   ├── modules\               Vertical slices, each: router/services/repository/schemas/models
    │   │   ├── auth\  users\  admin\
    │   │   ├── conversations\  messages\
    │   │   ├── documents\
    │   │   └── analysis\          catalog · global_catalog · generator · prompts · guard ·
    │   │                          registry · executor · multi_executor · service · repository
    │   ├── llm\                   langchain clients (Groq + optional Ollama) & RAG prompt service
    │   ├── rag\                   loader (Docling/pypdf) · embeddings (Google) ·
    │   │                          vector_store (PGVectorStore) · service (ingest/retrieve)
    │   ├── storage\               schema_notes.json (free-text table hints for the catalog)
    │   ├── scripts\               SQL migrations (FDW setup, client migration), create_admin, smoke test
    │   └── tests\                 pytest: test_api, test_guard, test_scope, test_executor
    └── frontend\
        ├── proxy.ts               Next.js proxy/middleware (session bootstrap + refresh)
        ├── app\                   app router: login, register, (protected)/
        ├── components\           chat\ · admin\ · auth\ · markdown\ · ui\ (shadcn)
        ├── services\             typed API clients (axios + fetch) + server session
        └── lib\  hooks\          axios instance (401-refresh interceptor), utils
```

---

## 3. Backend

### 3.1 Backend structure & conventions

- **FastAPI + SQLAlchemy 2.0 (`DeclarativeBase`, `Mapped[...]`) + Pydantic v2.**
- **Vertical-module pattern** — each feature owns `router → services → repository → models/schemas`:
  - `router.py`: HTTP endpoints only (validation via Pydantic schemas, dependency injection).
  - `services.py`: business logic; raises `HTTPException` with proper status codes.
  - `repository.py`: all DB queries (`Session`-scoped).
  - `models.py`: SQLAlchemy ORM tables.
- **Dependency injection:** `get_db()` yields a session per request; `CurrentUser` /
  `AdminUser` annotated dependencies resolve identity from the auth cookie.
- **App entry `main.py`:**
  - `lifespan`: `Base.metadata.create_all(bind=engine)` then `init_vector_store()`.
  - CORS with allow-list (`FRONTEND_ORIGIN` + `CORS_ORIGINS`) plus a **LAN-origin regex**
    fallback (10.x / 192.168.x / 172.16-31.x) so LAN clients pass preflight.
  - Router mounted at **`/api`**, health probe at **`/health`**.
  - Uses `uv` (`uv sync`, `uv run uvicorn main:app`). Python ≥ 3.11.

### 3.2 Configuration

`core/config.py` — a single pydantic-settings `Settings`, loaded from `.env`:

| Group | Setting | Purpose |
|---|---|---|
| Core | `DATABASE_URL`, `SECRET_KEY` (min 32), `ALGORITHM=HS256` | app DB + JWT signing |
| Auth | `ACCESS_TOKEN_EXPIRE_MINUTES=15`, `REFRESH_TOKEN_EXPIRE_DAYS=30` | JWT TTLs |
| Cookie | `COOKIE_SECURE`, `COOKIE_SAMESITE=lax` | cookie flags |
| LLM | `GROQ_MODEL_NAME=openai/gpt-oss-120b`, `GROQ_API_KEY`, `GOOGLE_API_KEY`, `LLM_TIMEOUT_SECONDS=120` | ChatGroq + Google embeddings |
| RAG | `GOOGLE_EMBEDDING_MODEL`, `VECTOR_STORE_URL`, `VECTOR_COLLECTION=vector_documents`, `VECTOR_DIMENSION=3072`, `CHUNK_SIZE=1000`, `CHUNK_OVERLAP=150`, `RETRIEVER_K=5`, `RAG_MAX_DISTANCE`, `MAX_UPLOAD_MB=20` | vector pipeline |
| Analysis | `ANALYSIS_DB_URL_TEMPLATE` (`{name}` placeholder), `ANALYSIS_MAIN_DB_SCHEMA=pollmatrix`, `ANALYSIS_SCHEMA_TABLE=schema_catalog`, `ANALYSIS_NOTES_FILE=storage/schema_notes.json`, `ANALYSIS_TOP_TABLES=3`, `ANALYSIS_MAX_COLUMNS`, `ANALYSIS_PAGE_SIZE=100` (max 500), `ANALYSIS_TIMEOUT_MS=15_000`, `ANALYSIS_EXPORT_TIMEOUT_MS=300_000`, `ANALYSIS_EXPORT_MAX_ROWS=1_000_000`, `ANALYSIS_TOKEN_MINUTES=120` | client DBs, catalog, execution limits |

### 3.3 Security & authentication

**Password hashing** — `pwdlib PasswordHash.recommended()` (Argon2 extras installed).

**JWTs** — PyJWT HS256 with `SECRET_KEY`; access (15 min) & refresh (30 days) carry
`iat/exp/type/sub(user UUID)`; refresh tokens also carry a random `jti`. Verify functions
strictly check `type` and that `sub` is a UUID.

**Cookie transport** — `core/cookies.py` sets **httpOnly** cookies `access_token` /
`refresh_token` (`path=/`, SameSite laxed by default, `secure` toggled per env). Frontend never
reads these (httpOnly) — every auth transition is browser-automatic.

**Refresh-token rotation + server-side store** — `RefreshToken` table stores only the **SHA-256
hash** of the token (unique, indexed), `expires_at`, `revoked_at`. On `/auth/refresh`, the used
refresh token is **revoked and replaced** (rotation). Expired rows are pruned on login. Revoked
or unknown hash ⇒ 401 + cookies cleared.

**Request authentication** — `api/dependencies.py :: get_current_user` reads the `access_token`
cookie, verifies JWT, loads the `User`, and **rejects deactivated accounts** even with a valid
cookie (deactivation takes effect immediately). `require_admin` gates admin endpoints (403).

### 3.4 Database layer

- `database/session.py`: single engine for the **app database** (pool 5 + 10 overflow, `pool_pre_ping`), `SessionLocal`, `get_db` dependency.
- `database/base.py`: `Base(DeclarativeBase)` shared by every module.
- **Vector engine:** separate `PGEngine.from_connection_string(VECTOR_STORE_URL)` inside
  `rag/vector_store.py` (double-checked-locking singletons; `init_vector_store()` creates the
  `vector_documents` table at startup with typed metadata columns).
- **Client database registry** (`analysis/registry.py`): `get_engine(name)` builds/caches
  engines per database name by formatting `ANALYSIS_DB_URL_TEMPLATE` (identifier-validated).
  `get_all_database_names()` reads active `clients.database_name` from the app DB.
  Dialect map: `postgresql → "postgres"`, `mssql → "tsql"` for sqlglot.

### 3.5 Data model (ER overview)

```
users 1─∞ refresh_tokens            users 1─∞ conversations 1─∞ messages
users 1─∞ documents  ─∞  document_assignments (∞─ users)   [direct doc access]
users ∞─∞ clients        via user_clients (is_primary)      [analysis scope]

clients (code, name, database_name UNIQUE, client_identifier UNIQUE e.g. client147)
saved_analyses (user, client, question, database, sql)
analysis_queries (user, client, database_name, question, title, sql, status,
                  error_message, row_count, page#, page_size,
                  planning/execution/total_time_ms, query_hash, explain_plan JSONB)

Vector tables (pgvector, langchain-postgres shape):
  vector_documents (content, embedding vector(3072), user_id, document_id, filename,
                    source_hash, content_hash, page, chunk_index, total_chunks, element_type)
  schema_catalog   (content "Table <n>. <note>", embedding, db, table_name)
```

Table notes and semantics are documented inside the analysis prompts (§below).

### 3.6 Module auth / users

| Endpoint | Description |
|---|---|
| `POST /api/auth/login` | verify email+active+password → issue & rotate access/refresh cookies |
| `POST /api/auth/refresh` | verify + revoke stored refresh → set fresh cookie pair |
| `POST /api/auth/logout` | revoke refresh row (if present) → clear cookies |
| `GET /api/users/me` | current user profile (used by the SSR `getSession`) |
| `PATCH /api/users/me` | change name/display fields |
| `DELETE /api/users/me` | delete own account (cascades) |

No public registration: the first (and any subsequent) company admin is created **server-side**
via `uv run python -m scripts.create_admin <email>`.

### 3.7 Module admin

Admin-only management surface (`require_admin`):

- **Clients:** `GET/POST/PATCH/DELETE /api/admin/clients`. Creating a client
  validates reachability + non-empty schema of the target database, enforces unique
  `database_name` and `client_identifier`, then **auto-builds its schema catalog**
  (`build_catalog`) and runs `setup_main_db_fdw` expectations — i.e. each client DB must
  expose the shared tables through the `pollmatrix` foreign schema.
- **Users:** list/create/patch/delete accounts; `PUT /api/admin/users/{id}/assignments`
  replaces that user's client assignments atomically (diff against current rows; unknown
  client ⇒ 400). Revocation is effective immediately (see scoping below).
- **Documents:** `PUT /api/admin/documents/{id}/assignments` re-scopes an existing document
  to a new `user_ids` list; **vectors are reused (no re-embedding)**.

### 3.8 RAG pipeline (`rag/`)

**Loader (`rag/loader.py`)**
- Supported files: `.pdf`, `.txt`, `.md` (extension-checked, max `MAX_UPLOAD_MB`).
- PDF: primary path uses **Docling** (`DoclingLoader`, markdown export) on a temp file; the
  markdown is split into **table elements** (pipe-table detection) and text blocks (≤3000 chars);
  fallback path is **pypdf** page-by-page (empty-TX and encrypted-PDF handled; password-protected → error; empty note that OCR would be needed).
- TXT/MD decoded as UTF-8 (errors replaced).

**Chunking (`rag/service.py`)**
- Markdown tables are **normalized** to "Row N: Header: value" form so they embed and read well.
- `RecursiveCharacterTextSplitter` with domain separators (`\n\n`, `\n`, sentence/period
  separators, `。`, `！`, etc.), `CHUNK_SIZE=1000`, `CHUNK_OVERLAP=150`.
- Every chunk metadata: `user_id`, `document_id`, `filename`, `source_hash` (file SHA-256),
  `element_type`, `content_hash` (normalized text SHA-256), optional `page`,
  `chunk_index`/`total_chunks`. Deterministic chunk IDs via `uuid5(document_id:index)`.

**Embeddings (`rag/embeddings.py`)** — cached Google `GoogleGenerativeAIEmbeddings`,
`output_dimensionality=VECTOR_DIMENSION (3072)`.

**Vector store (`rag/vector_store.py`)** — `langchain_postgres.PGVectorStore` over
`VECTOR_STORE_URL`, table `vector_documents`, initialized at startup if missing.

**Ingestion (`ingest_document`)** — extract→chunk→batched add (32/request) with ids; on failure
**rolls back** (deletes all chunks of `document_id`). Returns chunk count (stored on the Document row).

**Retrieval (`retrieve`)** — `similarity_search_with_score(query, k=RETRIEVER_K)` **filtered by
the caller's visible document_ids** (`$in`), optional `RAG_MAX_DISTANCE` cut-off, then
**neighbor expansion** (±`window=1` chunk indexes per hit via direct SQL, deduped, ordered by
filename+chunk index → coherent context blocks).

**Context formatting** — `format_context` produces numbered `[i] file (page p) [chunk N]` blocks;
`format_sources` appends a `--- **Sources:** file (p. 3, 5) · …` footer; `strip_sources` removes
it when replaying history.

### 3.9 LLM client (`llm/`)

- `client.py`: `groq_llm = ChatGroq(model=GROQ_MODEL_NAME, temperature=0.3)`; an optional
  **local fallback** `ChatOllama(model="qwen3.5", localhost:11434)` (currently commented out in the
  generation call).
- `service.py` (documents Q&A):
  - Hard `RAG_SYSTEM_PROMPT`: *"answer ONLY from `<context>` excerpts, Markdown OK, valid
    Mermaid rules, otherwise reply exactly `NOT_FOUND`"* — hallucination-guarded.
  - `generate_reply(history, user_content, context)` builds
    `[System(context)] + history(Human/AI/…) + Human` and invokes Groq.
  - `ENABLED_REMOVAL_OF_REASONING` — `<think>…</think>` blocks are stripped
    (`clean_model_text`), and `is_not_found()` detects the refusal token so callers replace it
    with a friendly message.

### 3.10 Module conversations / messages

- **Conversations:** CRUD + per-user ownership; index `(user_id, updated_at)`; auto title
  "New Chat" until a first message renames it to the question (first 60 chars).
- **Messages:** role enum (`user`/`assistant`); cursor-paginated listing
  (`(created_at,id)` keyset, urlsafe-base64 cursor, `limit≤100`) returning newest-first page
  `{items, next_cursor}`; edit/delete allowed only on **own user messages** (403 rules).
- **Chat answering orchestration (`MessageService.create_and_reply`)**
  1. Load last **20 messages history** (sources stripped).
  2. Persist the user message & bump `Conversation.updated_at`.
  3. If user has **no visible documents** → static `NO_DOCUMENTS_REPLY`.
  4. Retrieve context (short questions (<80 chars) are prefixed with the previous user message
     to form a better query). Retrieval errors → **502** (never silent "not found").
  5. If retrieval empty → `NOT_FOUND_REPLY` without LLM cost.
  6. Else call `generate_reply` (needs Groq; failure → 502) →
     `answer = raw + format_sources(chunks)` or `NOT_FOUND_REPLY` if refused.
  7. Persist assistant message; first-message title update; commit; return **both messages**.

### 3.11 Module documents

- `Document` rows carry metadata only — **file bytes are never stored** (content lives in
  vectors). `chunk_count` tracks ingestion size. `client_id` currently nullable (legacy).
- `DocumentAssignment` join table scopes each document to selected dashboard users.
- Upload flow (admin): validate extension/size → create row + assignments → **synchronously
  ingest via `run_in_threadpool`** (I/O light but embedding happens in-request; proxy timeout
  applies) → rollback chunks on any post-commit failure; **DB commit after vectors succeed**.
- Visibility: `get_all` is scoped — admins see everything; users see documents assigned to them
  (via `document_assignments`). Deletion removes vectors first, then the row.

### 3.12 Module analysis (NLP → SQL)

The most sophisticated subsystem. Pieces:

**a) Schema discovery (2 generations, both in use)**
- **`catalog.py` (per-database vectorized catalog):** `build_catalog(db)` reflects table names
  (+ shared `pollmatrix.*` ones), merges free-text hints from `storage/schema_notes.json`, and
  vector-embeds *"Table <name>. <note>"* into the `schema_catalog` pgvector table (delete+insert
  per db). `select_tables(question, db)` returns top-`ANALYSIS_TOP_TABLES`(3) matching tables by
  similarity (filtered by `db` metadata), then greedily appends FK-neighbor tables (max 5).
- **`describe_table(db, table, question)`**: bounded lazy reflection — PK/FK parts are pinned
  first, remaining columns ranked by **overlap of question words with column name parts**,
  truncated to `ANALYSIS_MAX_COLUMNS`, formatted `col type [PK] [FK->table.col] ...`. Result is
  LRU-cached (512) per (db,table,question).
- **`global_catalog.py` (reflection-based, no vectors):** understands that sharded client DBs
  carry **partition-suffix table names** (`user_master__partition_client147`...) and computes
  **logical table names** by stripping known suffix patterns (`__partition_clientNN`,
  `__clientNN`, `_clientNN`, `_partitionN`). Keyword-ranks logical tables against the question
  (exact/substring/word-overlap + "in more DBs" weight), and auto-builds/clears reflection caches.

**b) SQL generation (`generator.py`)**
- **Hardcoded giant system prompt (`generator.SYSTEM`, mirrored in `prompts.py`)** encoding the
  full business schema: shared tables (`client_master`, `executive_master`, `user_master`,
  `hitchintak_master_pollmatrix_new`, `karyakarni_master_pollmatrix_new`) and client-side tables
  (`dw_voters_info`, `voter_details_corp`, `activity_details_corp/sir`, `contact_sync_corp/sir`),
  each with columns and dozens of semantic business rules (colour_code R/G/Y, status_type D/A/O,
  marnmar/marnmar_det caste codes, SIR 2002 columns, survey fields...), 18 documented logical
  joins, join-safety rules (never invent ac_no on dw_voters_info, avoid fan-out, no guessed
  master tables), safety rules (read-only SELECT, no secrets `client_key`/`password`, no LIMIT
  unless asked, inline literal params, JSON output contract).
- Multi-line-language support: **English, Hindi, Marathi, Hinglish …**
- Template placeholder `{{client_id}}` is substituted with the client's `client_identifier`
  so generated SQL filters to the right tenant.
- Output contract: exactly one JSON object `{title, sql|null, reason}`; model output is fenced
  ``` stripped; non-JSON → `{sql: null, reason:"did not return valid JSON"}`.

**c) SQL guard (`guard.py`)** — **sqlglot** based defense-in-depth `validate_select`:
- exactly **1 statement**, must be `exp.Query` (SELECT/WITH);
- forbidden node types: Insert/Update/Delete/Drop/Create/Alter/Merge/Command/Into/TruncateTable;
- blocks dangerous functions (`pg_*`, `lo_*`, `dblink*`, `pg_sleep`, `current_setting`,
  `current_database`, `version`);
- **every query must touch a table** (blocks `SELECT 'Paris'` style LLM cop-outs);
- schema-qualification allowed **only** for the FDW schema `pollmatrix.*` (all other
  cross-schema/cross-db rejected). Bare table names must be CTEs, in the allowed top-k,
  or **known real tables** (a model reaching a genuinely existing table outside the top-k is
  fine), or → rewritten from logical→physical name via `resolve`.
- Returns normalized SQL re-rendered in the target dialect.

**d) Execution (`executor.py` / `multi_executor.py`)**
- Wraps SQL as `SELECT * FROM (… ) AS q LIMIT page+1 OFFSET off` (positional escaping `:` →
  `\:`), opens connection with `SET TRANSACTION READ ONLY` + `SET LOCAL statement_timeout`
  (15s query / 300s export). MSSQL path has no read-only txn and buffers one page after
  `fetchmany(offset)` skip (no ORDER BY needed) — **PostgreSQL is the recommended target**.
- `run_page` returns columns/rows(`jsonable_encoder`)-page/page_size/`has_more`/`total_time_ms`.
- `stream_csv` streams chunks of 1000 rows as CSV (header first), cap 1,000,000 rows.
- **`multi_executor`:** runs the same SQL on each database independently (errors captured
  per-db, not fatal), returns `{databases: {db: page}, merged_result?, join_key, join_type}`
  with an in-Python **hash join/merge across DB results** when `join_key` provided.

**e) Service orchestration (`service.py`)**
- **Scoping:** `assigned_database(user, client_id)` — admin may use any client; users must be
  assigned (`user_clients`); exactly none ⇒ 403, several supplied ⇒ "select a client" 400.
  Returns `(database_name, client_uuid, client_identifier)`.
- **`ask` / `ask_global` pipeline:**
  select tables → build bounded schema string → **retry loop (2 attempts)**:
  `generate_sql(question, dialect, schema, client_identifier, previous_sql, error)` →
  `validate_select` (retry with refreshed real-table reflection when "Table not available") →
  `run_page` → on UnsafeSQL/SQLAlchemy error, feed `error` back into the LLM for a corrected
  query. Total failure ⇒ 422 with `OUT_OF_SCOPE` or the last error/model reason.
- **Result tokens:** successful runs are minted as a **signed JWT** (`sign_result`: `type`,
  `sub`, `db`, `client_id`, `sql`; expiry `ANALYSIS_TOKEN_MINUTES`=120h→2h) — pagination and CSV
  export re-verify ownership + that **assignment still matches** (`open_result`,
  `_check_multi_access` also covers multi-db payloads). Every run is logged to
  `analysis_queries` (status, row_count, timings, hash) — powering **History**; users may
  **re-run or delete** history, and save a token as `saved_analyses` (title/question/sql snapshot),
  with the same re-run & delete semantics; both re-check assignment-change before executing.

### 3.13 Full API surface (42 routes, all under `/api` unless noted)

```
Health        GET  /health
Auth          POST /api/auth/login, /api/auth/refresh, /api/auth/logout
Users         GET/PATCH/DELETE /api/users/me
Admin         GET/POST /api/admin/clients · PATCH/DELETE /api/admin/clients/{id}
              GET/POST /api/admin/users · PATCH/DELETE /api/admin/users/{id}
              PUT /api/admin/users/{id}/assignments
              PUT /api/admin/documents/{id}/assignments
Conversations POST/GET /api/conversations · GET/PATCH/DELETE /api/conversations/{id}
Messages      POST/GET /api/conversations/{id}/messages · GET/PATCH/DELETE …/messages/{mid}
Documents     POST (admin upload, multipart) · GET (scoped list) · DELETE /api/documents/{id}
Analysis      GET /api/analysis/clients
              POST /api/analysis/query  (single client, previous_sql refinement)
              POST /api/analysis/query/global (across accessible DBs, table_type_filter)
              POST /api/analysis/rows        {token, page, page_size}
              POST /api/analysis/export      {token} → CSV stream
              POST /api/analysis/catalog/global/build (admin)
              POST /api/analysis/saved · GET /api/analysis/saved · POST …/saved/{id}/run ·
                DELETE …/saved/{id}
              GET /api/analysis/history[?client_id] · POST …/history/{id}/run ·
                DELETE …/history/{id}
```

### 3.14 Tests, scripts & tooling

- **pytest** (`test_api`, `test_guard`, `test_scope`, `test_executor` + `conftest`), run:
  `uv run --with pytest --with httpx python -m pytest -q`. `pytest.ini`/`.pytest_cache` present.
- **ruff** lint (line 88, py311), lockfile `uv.lock`, `.python-version`.
- **scripts/**: `001_admin_scope.sql`, `002_client_migration.sql` (adds clients/UserClient and
  client-scoping to docs; pre-deploy for existing installs), `setup_main_db_fdw.sql` (creates the
  `pollmatrix` foreign schema in every client DB), `create_admin.py`, `smoke_test.py`.

---

## 4. Frontend

### 4.1 Frontend structure & stack

Next.js **16.3.6** App Router + **React 19**, **Tailwind CSS v4** (+ typography), shadcn-style
UI in `components/ui` (Radix primitives: dialog, tabs, select, tooltip, sidebar, scroll-area…),
`axios`, `next-themes`, `lucide-react`, **react-markdown + remark-gfm + rehype-raw** and
**mermaid** for diagram rendering. Env: `NEXT_PUBLIC_API_URL` (defaults `http://localhost:8000/api`).

```
app/
  layout.tsx        <ThemeProvider> root
  login/page.tsx · register/page.tsx
  (protected)/        ← session-guarded group (server layout redirects on failure)
      layout.tsx    getSession → redirect → DialogProvider>WorkspaceProvider>SidebarProvider>AppSidebar
      page.tsx      ChatHome (tabs: Documents | Analysis)
      chat/[id]/    DocumentsChat for a persisted conversation
      admin/page.tsx (admin)
components/ chat/{ChatHome,ChatTabs,DocumentsChat,AnalysisChat,ChatInput,ChatMessages,
            MarkdownContent,ResultTable} · admin/AdminPanel · auth/LoginForm ·
            documents-panel.tsx · app-sidebar.tsx · workspace-provider.tsx ·
            markdown/{MarkdownComponents,CodeBlock,MermaidDiagram} · ui/*
services/   auth · session (server-only) · conversations · messages · documents ·
            analysis (fetch-based) · admin · error
lib/        axios.ts (client singleton + 401 auto-refresh) · utils.ts
```

### 4.2 Auth/session flow

Three cooperating mechanisms (cookie-based; **no tokens in localStorage**):

1. **`proxy.ts` (Next proxy/middleware)** runs on every non-static route:
   - `/login?reason=expired` wipes stale cookies (server layout signalled invalid session).
   - Valid access token → pass (public page → redirect `/`).
   - Only refresh token → call `POST /auth/refresh` server-side, **splice fresh Set-Cookies**
     into the current request headers (so this request's server components see it) *and*
     forward to the browser.
   - Invalid → redirect `/login`; stale refresh → clear cookies and stop retry loops.
2. **`lib/axios.ts`** client instance: `withCredentials`, response interceptor treats any 401
   (except on `auth/*` or already-retried) as lapsed access token → single-flight
   `refreshPromise` refresh → replay original request; failure → hard `window.location.replace('/login?reason=expired')`.
3. **`services/session.ts (**server-only**)**: `getSession()` forwards the browser cookie header
   to `GET /users/me`; `(protected)/layout.tsx` redirects unauthenticated visitors
   (`?reason=expired`) before rendering any protected page.

### 4.3 Routing & layout

- `(protected)` group enforces auth once for chat, chat/[id], admin, temporary.
- `DocumentLayout`-style shell: **AppSidebar** (conversation history, documents panel, admin
  entry), `SidebarInset` full-height content, theme via `next-themes`, global
  `DialogProvider` (confirm/alert helpers) and `WorkspaceProvider` (below).
- New chat = `/` → `ChatHome` with tab switcher `documents | analysis` (both kept mounted).
- `/chat/[id]` renders `DocumentsChat conversationId=id` (server component passing `id`).

### 4.4 State management

`components/workspace-provider.tsx` — React context loaded on mount with:
`conversations` and `documents` lists, `refreshConversations`, `refreshDocuments`,
`removeConversation`, plus a cross-page **flashError** store (e.g. surfaced by DocumentsChat).
`useWorkspace()`. Documents/Analysis chat use local component state for turns/messages.

### 4.5 Service layer

- `auth.ts` (login/logout via axios), `conversations.ts`, `messages.ts`
  (`getAllConversationMessages` → `MessagePage {items, next_cursor}` cursor paging, newest first),
  `documents.ts` (admin `uploadDocument` sends FormData with `file` + `JSON.stringify(user_ids)`),
  `admin.ts`, `error.ts` (`getApiErrorMessage` handles FastAPI `detail` string/array).
- `analysis.ts` uses **raw fetch** (not axios) with its own 401→refresh→retry logic; sends
  `credentials: "include"`; typed models `AnalysisResponse {title, database, tables, sql, token,
  result: ResultPage}`, `HistoryItem`, `SavedAnalysis`, `AnalysisClient`, and helpers
  `listClients`, `askAnalysis`, `askGlobalAnalysis`, `fetchRows` (pagination), `exportCsv`
  (Blob), `saveAnalysis`, `listSaved`, `runSaved`, `listHistory`, `runHistory`, deletes.

### 4.6 Chat UI

**DocumentsChat** (chat page or tab):
- Optimistic UX — user message appended immediately with temp id; loading indicator;
  `sendMessage(conversationId, content)` posts and appends **both** returned messages (temp
  replaced); creates a conversation on first message and `router.replace`/updates to the
  new `/chat/[id]`; sidebar list refreshed via workspace context.
- Message history with cursor pagination; markdown rendering; errors surfaced inline;
  refusal path shows the backend's friendly "couldn't find the answer…" message.

**AnalysisChat** (tab):
- Turns model `{id, question, status: loading|done|error, data, error}`.
- Sends `askGlobalAnalysis({question})`; on success renders **title / SQL / result table /
  timing** via `ResultTable` plus **token-gated client actions**: paginate (`fetchRows` with
  token+page) and **CSV export** (`exportCsv(token)` → Blob download), **save analysis**
  (`saveAnalysis(token, question, title)`), and error/alert dialogs via `useDialogs`.
- **History** panel lists past queries (re-run = `runHistory`; delete with confirm); **Saved**
  panel lists saved analyses (open = `runSaved`); re-runs appear as new turns.

**documents-panel.tsx / app-sidebar.tsx** — sidebar navigation of conversations/documents.

### 4.7 Markdown / mermaid rendering

`components/markdown/*` — `MarkdownContent` (chat) maps GFM elements through
`MarkdownComponents` with `CodeBlock` (copy button) and `MermaidDiagram` (async
`mermaid.render`, themed, error-fallback box) — matching the backend prompt's Mermaid syntax rules.

### 4.8 Admin panel

`components/admin/AdminPanel.tsx` (route `/admin`): clients CRUD (database name, client
identifier), users CRUD, **client assignments editor** (replace-style PUT), **document
upload/re-scope/delete** (accepted `.pdf, .txt, .md`), lists from `services/admin.ts`.

---

## 5. End-to-End Flows

**A. Login → chat messages (.Documents)**
```
login → FastAPI sets httpOnly cookies → next navigation renders (protected)
 → getSession() → workspace loads conversations+documents
 → question posted: POST /conversations/{id}/messages
 → backend: history → ingest user msg → retrieval (scoped doc ids; ±1 neighbor chunks)
 → Groq with <context> (+history) → answer +Sources footer → persisted → both messages returned
 (NOT_FOUND if refusals / empty retrieval; 502 on retrieval/LLM infra errors)
 → UI renders Markdown/Mermaid
```

**B. Analysis question (NL → SQL)**
```
question → POST /analysis/query[global]
 → resolve assigned client → database_name + client_identifier
 → table selection (vectorized catalog or logical-reflection ranking) + shared main tables
 → bounded per-table schema string → Groq NL→SQL (JSON {title,sql,reason}), tenant id injected
 → sqlglot guard (1 statement, SELECT-only, no dangerous fns, table whitelist/rewrite, FDW-only schema)
 → execute read-only txn + statement_timeout, page 100
 → persist analysis_queries (history) → sign result JWT (120 min)
 → {title, database, tables, sql, token, result}
 UI: table w/ pagination via /analysis/rows {token,page,size}
     export via /analysis/export {token} (Streaming CSV)
     save via /analysis/saved {token,…} → re-runnable from History/Saved panels
```

**C. Admin ingestion (docs)**
```
/admin upload .pdf/.txt/.md (+user_ids) → POST /documents (multipart)
 → validate type/size → Document row + assignments → Docling/pypdf extract → chunk →
 batched Google embeddings → pgvector (ids per document/chunk; rollback on failure)
 → chunk_count saved.  Vector visibility always filtered to the viewer's assigned docs.
```

---

## 6. Security Model Summary

- **AuthN/Z:** httpOnly JWT cookies; refresh **rotation + server-side revocation list**;
  immediate lock-out on deactivation; role `admin` gates admin routes; per-user data isolation
  (conversations, messages, history, saved, documents).
- **Client scoping:** documents → `document_assignments`; SQL → `user_clients` (re-verified on
  token row/export/history/save re-runs — assignment change ⇒ 403).
- **LLM output sandboxing for SQL:** restrictive sqlglot guard + **read-only DB transactions**
  + statement timeouts; expected read-only DB logins; sensitive columns (`client_key`,
  `password`) barred by prompt; queries always touch real tables.
- **No client-level data mixing:** generated SQL is told to filter by `client_id`; shared tables
  reachable only via the FDW foreign schema of the connected client DB.
- **Result tokens are signed, not encrypted** — a user can decode their own SQL (by design).
- Upload limits (20 MB), extension whitelist; LAN CORS fallback for the local network.

---

## 7. Environments & Deployment

**Backend `.env` (see `.env.example`)** — `DATABASE_URL`, `SECRET_KEY`(≥32), `GROQ_API_KEY`,
`GOOGLE_API_KEY`, `GOOGLE_EMBEDDING_MODEL`, `VECTOR_STORE_URL`, `ANALYSIS_DB_URL_TEMPLATE`
(read-only login; `{name}` substituted), optional `CORS_ORIGINS`, `COOKIE_SECURE`,
`ANALYSIS_MAIN_DB_SCHEMA=pollmatrix`, limits. Startup: `uv sync`; `uv run uvicorn main:app`;
create first admin: `uv run python -m scripts.create_admin admin@company.com`;
migration for existing installs: `scripts/002_client_migration.sql` + FDW
(`scripts/setup_main_db_fdw.sql`).

**Frontend** — `NEXT_PUBLIC_API_URL`; `npm install; npm run dev` (or build/start).
Default dev ports: API 8000, FE 3000 (both LAN-origins pre-permitted server-side).

---

## 8. Known Limitations & Operational Notes (from README/code)

- **MSSQL execution is partial** (no read-only txn; manual offset buffering; postgres `LIMIT/OFFSET`
  dialect mismatch) — target **PostgreSQL** for full guarantees.
- Document upload processes & embeds **inside the HTTP request** — set adequate proxy timeouts.
- Legacy uploads start **unassigned** & invisible to users; scope them via the admin
  `PUT /documents/{id}/assignments` API (vector reuse, no re-embed).
- `schema_catalog` + document vectors live in the **app/vector PostgreSQL**, never in analysis DBs;
  analysts cannot (re)build catalogs.
- Guard is defense-in-depth only — the analysis DB role itself must be read-only and restricted.
- Analysis tokens are signed, so users can read their own SQL; no streaming/typing effect in chat
  (single request/response per turn).

---

## Appendix A — Complete Current File / Folder Tree

Sizes in parentheses mark notable files. Generated artifacts (`node_modules`, `.next`,
`__pycache__`, `.pytest_cache`, `.ruff_cache`) are excluded.

```
chanakya-ai/
+-- .vscode/
|   +-- settings.json
+-- backend/
|   +-- api/                              Router aggregation + auth dependencies
|   |   |-- dependencies.py               get_current_user / require_admin (cookie → JWT → User)
|   |   +-- router.py                     Mounts all 7 module routers under /api
|   +-- core/                             App-wide plumbing
|   |   |-- config.py                     pydantic-settings (all env vars)
|   |   |-- cookies.py                    httpOnly access/refresh cookie set/clear
|   |   +-- security.py                   Argon2 hashing, JWT create/verify, token SHA-256
|   +-- database/
|   |   |-- base.py                       DeclarativeBase
|   |   +-- session.py                    App-DB engine + SessionLocal + get_db()
|   +-- llm/
|   |   |-- __init__.py
|   |   |-- client.py                     ChatGroq (openai/gpt-oss-120b) + optional ChatOllama
|   |   +-- service.py                    RAG system prompt, generate_reply, NOT_FOUND detection
|   +-- modules/                          Vertical feature slices
|   |   +-- admin/                        Company admin: clients, users, assignments
|   |   |   |-- __init__.py
|   |   |   |-- repository.py
|   |   |   |-- router.py
|   |   |   |-- schemas.py
|   |   |   +-- services.py               Client create → validate DB + auto-build catalog
|   |   +-- analysis/                     NL → SQL subsystem (the core)
|   |   |   |-- __init__.py
|   |   |   |-- catalog.py                Per-DB vectorized table-name catalog + bounded schema
|   |   |   |-- executor.py               run_page / stream_csv (read-only txn, timeouts)
|   |   |   |-- generator.py              Groq NL→SQL call (23 KB system prompt)
|   |   |   |-- global_catalog.py         Reflection-based logical table discovery (shards)
|   |   |   |-- guard.py                  sqlglot SELECT-only validator
|   |   |   |-- models.py                 Client, UserClient, SavedAnalysis, AnalysisQuery
|   |   |   |-- multi_executor.py         Same SQL across N DBs + Python merge/join
|   |   |   |-- prompts.py                Alternate copy of the SQL system prompt
|   |   |   |-- registry.py               Engine-per-database cache, dialect map
|   |   |   |-- replace_prompt.py         Prompt variant (query refinement)
|   |   |   |-- repository.py             History / saved-analyses persistence
|   |   |   |-- router.py                 /api/analysis endpoints
|   |   |   |-- schemas.py                AskRequest / RowsRequest / TokenRequest etc.
|   |   |   +-- service.py                Orchestration + signed result JWTs
|   |   +-- auth/                         Login/refresh/logout + RefreshToken model
|   |   |   |-- models.py  repository.py  router.py  schemas.py  services.py
|   |   +-- conversations/                Chat threads per user
|   |   |   |-- models.py  repository.py  router.py  schemas.py  services.py
|   |   +-- documents/                    Document rows + user-scope assignments
|   |   |   |-- __init__.py
|   |   |   |-- models.py  repository.py  router.py  schemas.py  services.py
|   |   +-- messages/                     Messages + RAG answer orchestration
|   |   |   |-- models.py  repository.py  router.py  schemas.py  services.py
|   |   +-- users/                        /users/me profile endpoints
|   |       |-- models.py  repository.py  router.py  schemas.py  services.py
|   +-- rag/                              Retrieval pipeline
|   |   |-- __init__.py
|   |   |-- embeddings.py                 GoogleGenerativeAIEmbeddings (3072-dim)
|   |   |-- loader.py                     Docling/pypdf extraction, table detection
|   |   |-- service.py                    Chunking, ingest, retrieve (+neighbor window)
|   |   +-- vector_store.py               PGVectorStore singleton + table init
|   +-- scripts/
|   |   |-- 001_admin_scope.sql
|   |   |-- 002_client_migration.sql      Clients/UserClient + doc scoping migration
|   |   |-- create_admin.py               First admin bootstrap (server-side)
|   |   |-- setup_main_db_fdw.sql         postgres_fdw foreign schema (pollmatrix)
|   |   +-- smoke_test.py
|   +-- storage/
|   |   +-- schema_notes.json             Free-text table hints merged into the catalog
|   +-- tests/
|   |   |-- conftest.py
|   |   |-- test_api.py
|   |   |-- test_executor.py
|   |   |-- test_guard.py
|   |   +-- test_scope.py
|   |-- .env / .env.example               Real / template config (never commit .env)
|   |-- .gitignore  .python-version
|   |-- HR-Policy.pdf                     Sample document used in testing
|   |-- main.py                           FastAPI app entry + CORS + lifespan
|   |-- pyproject.toml  pytest.ini  requirements.txt  requirements-analysis.txt
|   +-- uv.lock
+-- frontend/
    +-- app/                              Next.js 16 App Router
    |   +-- (protected)/                  Auth-guarded group (server layout redirect)
    |   |   +-- admin/page.tsx            Admin panel entry
    |   |   +-- chat/[id]/page.tsx        Persisted conversation (DocumentsChat)
    |   |   +-- temporary/page.tsx
    |   |   |-- layout.tsx                getSession → AppSidebar + providers
    |   |   +-- page.tsx                  ChatHome (Documents | Analysis tabs)
    |   +-- login/page.tsx  register/page.tsx
    |   |-- favicon.ico  globals.css  layout.tsx (ThemeProvider)
    +-- components/
    |   +-- admin/AdminPanel.tsx          Clients/users/documents management (33 KB)
    |   +-- auth/LoginForm.tsx
    |   +-- chat/
    |   |   |-- AnalysisChat.tsx          NL→SQL chat turns, history/saved panels
    |   |   |-- ChatHome.tsx  ChatInput.tsx  ChatMessages.tsx  ChatTabs.tsx
    |   |   |-- DocumentsChat.tsx         RAG conversation UI
    |   |   |-- MarkdownContent.tsx
    |   |   +-- ResultTable.tsx           Paginated result grid + CSV export (21 KB)
    |   +-- markdown/
    |   |   |-- CodeBlock.tsx  MarkdownComponents.tsx  markdown-utils.ts
    |   |   +-- MermaidDiagram.tsx        Mermaid render with fallback
    |   +-- ui/                           shadcn/Radix primitives (button, dialog, sidebar…)
    |   |-- app-sidebar.tsx               Navigation + conversation list
    |   |-- documents-panel.tsx
    |   |-- theme-provider.tsx
    |   +-- workspace-provider.tsx        Global context: conversations, documents, flashError
    +-- hooks/use-mobile.ts
    +-- lib/
    |   |-- axios.ts                      Client instance + 401 auto-refresh interceptor
    |   +-- utils.ts                      cn() + generateId
    +-- public/                           SVG assets
    +-- services/                         Typed API clients
    |   |-- admin.ts  analysis.ts (fetch)  auth.ts  conversations.ts
    |   |-- documents.ts  error.ts  messages.ts
    |   +-- session.ts                    server-only getSession (cookie → /users/me)
    |-- .env  .env.local.example  .gitignore
    |-- AGENTS.md  CLAUDE.md  README.md  SIMPLE_UI_SUMMARY.md
    |-- components.json  eslint.config.mjs  next.config.ts  next-env.d.ts
    |-- package.json  package-lock.json  postcss.config.mjs
    |-- proxy.ts                          Middleware: session bootstrap + refresh
    +-- tsconfig.json
|-- AI_Database_Assistant_Testing_Question_Bank.md   Test question bank (46 KB)
|-- code.ipynb                                        Research notebook (318 KB)
|-- Markdown to PDF.pdf
+-- PROJECT_DOCUMENTATION.md                          This document
```
