# Chanakya AI — Technical Architecture

> **Document:** `docs/01_TECHNICAL_ARCHITECTURE.md`  
> **Scope:** System architecture, component interactions, data flows, deployment topology, and references to the architecture diagrams in `Architecture/`.  
> **Status:** Current as of codebase  

---

## 1. System Architecture Diagram Reference

The `Architecture/` folder contains 17 pre-rendered PNG diagrams. The following table maps each diagram to the subsystem it illustrates:

| Diagram | Subsystem / Use |
|---------|-----------------|
| `High-Level System Architecture.png` | Overall request flow: browser → proxy → FastAPI → DBs + external LLM |
| `Conversation Architecture.png` | Conversations/messages lifecycle and persistence |
| `Database Connection Architecture.png` | How the app DB, vector DB, and client DBs connect |
| `Database ER Diagram.png` | Entity-relationship model of the app database |
| `Database Schema Retrieval.png` | How table schemas are discovered for SQL generation |
| `Deployment Architecture.png` | Deployment topology and environments |
| `Document Retrieval Sequence.png` | RAG retrieval sequence (query → chunks → context → LLM) |
| `Document Storage Architecture.png` | Document upload, ingestion, vector storage flow |
| `Full Hybrid Agent Activity Diagram.png` | Intelligence hybrid agent end-to-end activity |
| `Hybrid Document + Database Query.png` | Hybrid question handling across document + database |
| `Hybrid Search Architecture.png` | Hybrid (vector + keyword-ish) search approach |
| `Query Router.png` | Intent-based query routing (database vs document vs hybrid vs general) |
| `Report Generation Architecture.png` | Report / export generation flow |
| `Security Architecture.png` | Authentication, authorization, scoping, SQL sandboxing |
| `SQL Validation Pipeline.png` | sqlglot validation pipeline for generated SQL |

> These PNGs are visual companions to this document. Where a section references a diagram, the diagram filename is noted inline.

---

## 2. Logical Architecture (Layered View)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          CLIENT / PRESENTATION LAYER                        │
│  Next.js 16 App Router · React 19 · Tailwind v4 · shadcn/ui · mermaid       │
│  • /login, /register                                                        │
│  • (protected)/  ChatHome (Documents \| Analysis tabs) · /chat/[id] · /admin│
│  • proxy.ts middleware: session bootstrap, access/refresh token rotation    │
└──────────────────┬──────────────────────────────────────────────────────────┘
                   │ HTTP + httpOnly JWT cookies (access_token, refresh_token)
                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          API GATEWAY / MIDDLEWARE LAYER                     │
│  FastAPI (uvicorn) · lifespan: create_all() + init_vector_store()           │
│  • CORS (allow-list + LAN-origin regex for 10.x/192.168.x/172.16-31.x)     │
│  • Router mounted at /api · health probe at /health                          │
│  • Auth deps: CurrentUser (cookie → JWT → User, rejects deactivated)       │
│  • Admin dep: require_admin (403)                                            │
└──────────────────┬──────────────────────────────────────────────────────────┘
                   │
         ┌─────────┼─────────┐
         ▼         ▼         ▼
┌───────────────┐ ┌────────┐ ┌─────────────────────────────────────────────┐
│  AUTH         │ │ USERS  │ │ ADMIN                                         │
│  login/       │ │ /me    │ │ clients CRUD, users CRUD, assignments,       │
│  refresh/     │ │        │ │ document re-scope, upload                     │
│  logout       │ │        │ │                                               │
└───────────────┘ └────────┘ └─────────────────────────────────────────────┘
         ┌─────────────────────────────────────────────────────────────────┐
         ▼                                                                 ▼
┌───────────────────────┐                                       ┌───────────────┐
│ CONVERSATIONS /       │                                       │ DOCUMENTS     │
│ MESSAGES (RAG chat)   │                                       │ upload, list, │
│ CRUD + cursor paging  │                                       │ delete, scope │
└───────────┬───────────┘                                       └───────┬───────┘
            │                                                           │
            ▼                                                           ▼
┌───────────────────────┐                                   ┌───────────────────────┐
│ RAG PIPELINE (rag/)   │                                   │ ANALYSIS (analysis/)  │
│ loader → chunk →      │                                   │ catalog → generator   │
│ embed (Google) →      │                                   │ (Groq) → guard (sqlglot)│
│ pgvector → retrieve   │                                   │ → executor (read-only)│
└───────────┬───────────┘                                   └───────────┬───────────┘
            │                                                           │
            └───────────────────┬───────────────────────────────────────┘
                                ▼
                       ┌─────────────────┐
                       │ INTELLIGENCE    │
                       │ (hybrid QA):    │
                       │ intent classify │
                       │ → route →       │
                       │ synthesize →    │
                       │ chart suggest   │
                       └────────┬────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              DATA LAYER                                       │
│  ┌────────────────┐  ┌──────────────────────┐  ┌──────────────────────────┐ │
│  │ App PostgreSQL │  │ Vector PostgreSQL    │  │ Client Databases         │ │
│  │ (SQLAlchemy)   │  │ (pgvector, 3072-dim) │  │ (one per client,         │ │
│  │ users, tokens, │  │ vector_documents,    │  │ PostgreSQL recommended)  │ │
│  │ conversations, │  │ schema_catalog       │  │  · postgres_fdw →        │ │
│  │ messages, docs │  │                      │  │    pollmatrix schema     │ │
│  │ clients, …     │  │                      │  │  · shared main-DB tables │ │
│  └────────────────┘  └──────────────────────┘  └──────────────────────────┘ │
│                              ▲                                               │
│                        External: Groq API (LLM) · Google GenAI (embeddings)   │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Module Boundaries & Conventions

The backend uses a **vertical-slice (module) pattern**. Each feature owns:

```
modules/<feature>/
  router.py      HTTP endpoints only; Pydantic schema validation; DI
  services.py    Business logic; raises HTTPException with proper status codes
  repository.py  All DB queries (Session-scoped)
  models.py      SQLAlchemy ORM tables (DeclarativeBase)
  schemas.py     Pydantic v2 request/response schemas
```

| Module | Responsibility |
|--------|----------------|
| `auth` | Login, refresh (rotation + server-side store), logout, password hashing, JWT |
| `users` | `/users/me` profile (get/patch/delete) |
| `admin` | Client/user CRUD, client + document assignment management |
| `conversations` | Chat threads per user, ownership, auto-titling |
| `messages` | Message CRUD, cursor pagination, RAG answer orchestration |
| `documents` | Document metadata, assignments, visibility scoping |
| `analysis` | NL→SQL: catalog, generator, guard, registry, executor, multi_executor |
| `intelligence` | Hybrid QA: intent classification, routing, synthesis, chart, persistence |
| `llm` | Groq client, optional Ollama fallback, RAG system prompt service |
| `rag` | Loader (Docling/pypdf), chunking, Google embeddings, PGVectorStore, ingest/retrieve |
| `core/config` | Single pydantic-settings `Settings` from `.env` |
| `core/security` | Argon2 hashing, JWT create/verify, refresh-token SHA-256 store |
| `core/cookies` | httpOnly access_token / refresh_token set/clear |

### Dependency injection
- `get_db()` yields one SQLAlchemy `Session` per request.
- `CurrentUser` / `AdminUser` annotated dependencies resolve identity from the auth cookie and enforce authorization.

---

## 4. Inter-Process & External Communication

| Connection | Direction | Protocol | Purpose |
|------------|-----------|----------|---------|
| Browser → Next.js proxy | inbound | HTTP (cookies) | Session bootstrap, page rendering |
| Next.js → FastAPI | outbound | HTTP + httpOnly cookies | All API calls |
| FastAPI → App PostgreSQL | outbound | SQLAlchemy / psycopg | App data (users, conversations, docs, history) |
| FastAPI → Vector PostgreSQL | outbound | SQLAlchemy / psycopg + pgvector | Document chunks, schema catalog embeddings |
| FastAPI → Client database | outbound | SQLAlchemy (per-client engine) | Read-only analysis queries via `{name}` template |
| FastAPI → Groq API | outbound | HTTPS REST | Chat, SQL generation, intent, chart, synthesis |
| FastAPI → Google GenAI | outbound | HTTPS REST | Embeddings (3072-dim) |

### Client database connectivity (multi-tenant)
- `analysis/registry.py`: `get_engine(name)` builds/caches a SQLAlchemy engine per database name by formatting `ANALYSIS_DB_URL_TEMPLATE` (identifier-validated via `^[A-Za-z_][A-Za-z0-9_]*$`).
- Dialect map for sqlglot: `postgresql → "postgres"`, `mssql → "tsql"`.
- `get_all_database_names()` reads active `clients.database_name` from the app DB.
- Each client DB exposes shared main-DB tables through a **foreign schema `pollmatrix`** (postgres_fdw), so all SQL runs through the client connection only. Setup: `scripts/setup_main_db_fdw.sql`.

---

## 5. Key Data Flows

### 5.1 Login & Session Establishment
1. User posts credentials → `POST /api/auth/login`.
2. Backend verifies email + active + password (Argon2).
3. Issues access JWT (15 min) + refresh JWT (30 days) as **httpOnly cookies**.
4. Refresh token row stored (SHA-256 hash, `expires_at`).
5. Frontend `proxy.ts` on navigation: reads cookie → `GET /users/me` (SSR); refreshes if only refresh token present.

### 5.2 Documents (RAG) Q&A Flow
1. User sends question → `POST /api/conversations/{id}/messages`.
2. Backend loads last 20 messages history (sources stripped), persists user message.
3. Retrieves context: `similarity_search_with_score(k=5)` filtered by user's visible document IDs; optional distance cutoff; neighbor expansion (±1 chunk index via direct SQL, deduped, ordered by filename+chunk index).
4. If no visible documents → static no-documents reply.
5. If retrieval empty → `NOT_FOUND` reply (no LLM cost).
6. Else calls Groq with `<context>` + history → answer + `Sources` footer.
7. Persists assistant message; returns both messages. Frontend renders Markdown + Mermaid.

### 5.3 Analysis (NL → SQL) Flow
1. Question → `POST /api/analysis/query` (single client) or `/query/global` (across accessible DBs).
2. Resolve assigned client → `database_name`, `client_identifier`.
3. Table selection: vectorized catalog (`schema_catalog`) top-3 by similarity + FK neighbors (max 5), OR logical-reflection ranking (`global_catalog`) for sharded partition tables.
4. Build bounded per-table schema string (PK/FK first, remaining columns ranked by question-word overlap, capped by `ANALYSIS_MAX_COLUMNS`).
5. Retry loop (2 attempts): `generate_sql` (Groq, JSON `{title, sql, reason}`, tenant id injected) → `validate_select` (sqlglot) → `run_page` (read-only txn + statement_timeout, page 100). On error, feed error back to LLM.
6. Persist to `analysis_queries` (history). Sign result JWT (120 min) containing `type, sub, db, client_id, sql`.
7. Return `{title, database, tables, sql, token, result}`. Frontend paginates via `/analysis/rows {token, page, size}` and exports via `/analysis/export {token}` (CSV stream, cap 1M rows).

### 5.4 Intelligence (Hybrid) Flow
1. Question → `POST /intelligence/ask`.
2. Intent classification: fast-path regex for voter-record terms; else Groq JSON classification (`database`/`document`/`hybrid`/`general` + entities).
3. Route:
   - `database` → `AnalysisService.ask` (SQL path above).
   - `document` → RAG retrieve + Groq answer.
   - `hybrid` → both, then `HYBRID_SYNTHESIS_SYSTEM` merges into one answer.
   - `general` → Groq general-answer system prompt.
4. Optional chart suggestion from DB result columns/rows (`CHART_SUGGESTION_SYSTEM`, fallback heuristic).
5. Persist user + assistant messages (+ optional `ChatAnalysisQuery` link) to conversations/messages.
6. Return `IntelligenceResponse {intent, answer, database?, document?, chart?, sources, conversation_id, ...}`.

---

## 6. Concurrency & Resilience Notes

- **Vector store init** at startup is wrapped in try/warn (startup resilience — app starts even if pgvector unavailable).
- **Analysis engine** uses `pool_pre_ping` and per-database engines (pool_size 3, max_overflow 2) to avoid exhausting connections across many client DBs.
- **SQL execution** wraps in `SET TRANSACTION READ ONLY` + `SET LOCAL statement_timeout` (15s query / 300s export). MSSQL path lacks read-only txn (PostgreSQL recommended).
- **Multi-executor** runs the same SQL on each database independently; per-DB errors are captured, not fatal. In-Python hash join/merge when `join_key` provided.
- **Refresh-token rotation**: used token revoked and replaced on each `/auth/refresh`; expired rows pruned on login.
- **Deactivation**: `get_current_user` rejects deactivated accounts immediately even with a valid cookie.

---

## 7. Deployment Topology (Reference: `Deployment Architecture.png`)

A minimal production deployment consists of:

1. **App host** — runs FastAPI (uvicorn) + Next.js (or Next.js on a separate edge host).
2. **App PostgreSQL** — primary relational store (users, tokens, conversations, documents, clients, history).
3. **Vector PostgreSQL** (can be same instance, separate database) — pgvector store for document chunks + schema catalog.
4. **Client databases** — one PostgreSQL (recommended) or MSSQL database per client, each with `pollmatrix` foreign schema pointing at shared main-DB tables.
5. **External** — Groq API, Google Generative AI.

Network: CORS allow-list plus LAN-origin regex permits local-network clients. Cookies are `Secure` in production (`COOKIE_SECURE=true`), `SameSite=lax`.

---

## 8. Diagram Cross-Reference Index

Use these diagrams alongside the detailed documents:

- **Overall system** → `High-Level System Architecture.png` (see §1)
- **Auth & session** → `Security Architecture.png` (§7 in `07_SECURITY_ARCHITECTURE.md`)
- **RAG flow** → `Document Retrieval Sequence.png`, `Document Storage Architecture.png` (§4 in `04_RAG_PIPELINE.md`)
- **NL→SQL flow** → `SQL Validation Pipeline.png`, `Database Schema Retrieval.png` (§5 in `05_NL_TO_SQL_ANALYSIS_ENGINE.md`)
- **Hybrid QA** → `Full Hybrid Agent Activity Diagram.png`, `Hybrid Document + Database Query.png`, `Query Router.png`, `Hybrid Search Architecture.png` (§6 in `06_INTELLIGENCE_MODULE.md`)
- **ER model** → `Database ER Diagram.png` (`02_DATABASE_SCHEMA.md`)
- **Connections** → `Database Connection Architecture.png` (§4)
- **Deployment** → `Deployment Architecture.png` (§7)
- **Report/export** → `Report Generation Architecture.png` (§5 in analysis doc)

---

## 9. Assumptions & Constraints Encoded in Architecture

- **PostgreSQL is the recommended target** for client databases; MSSQL execution is partial (no read-only transaction, manual offset buffering).
- **Document bytes are never stored** — only extracted text/chunks live in pgvector.
- **File upload + embedding happens inside the HTTP request** — proxy timeout must accommodate embedding latency.
- **Result tokens are signed (not encrypted)** — a user can decode their own SQL by design.
- **No registration endpoint** — first admin created server-side via `scripts/create_admin.py`.
