# Chanakya AI — Technical Documentation Overview

> **Project:** Chanakya AI  
> **Purpose:** A multi-tenant, client-scoped AI analytics & document Q&A workspace for political campaign intelligence.  
> **Audience:** Developers, architects, DevOps engineers, and security reviewers.  
> **Location:** `D:\Satya\chanakya-ai\chanakya-ai\`  
> **Status:** Active development  

---

## 1. What Chanakya AI Does

Chanakya AI lets company administrators ingest campaign documents (PDF/TXT/MD) and register client databases; analysts (dashboard users) then ask **natural-language questions** and receive answers from one of two paths:

| Mode | What it does | Technology |
|------|--------------|------------|
| **Documents (RAG)** | Ask questions grounded in uploaded PDF/TXT/MD documents. Answers are extracted from document excerpts only, with source citations. | Google embeddings (3072-dim) + PostgreSQL pgvector + Groq LLM |
| **Analysis (NL → SQL)** | Ask questions against assigned client PostgreSQL/MSSQL databases. The system generates a guarded, read-only SQL query, executes it, and returns paginated results with CSV export, history, and saved analyses. | Groq LLM + sqlglot guard + SQLAlchemy + read-only transactions |

A third **Intelligence (hybrid)** mode classifies each question by intent — `database`, `document`, `hybrid`, or `general` — and routes it to the appropriate source(s), optionally attaching an AI-suggested chart config.

Everything is **multi-tenant / client-scoped**: documents are scoped via `document_assignments`; analysis is scoped via `user_clients`; each client maps to exactly one exclusive database.

---

## 2. Technology Stack

| Layer | Technology | Version / Notes |
|-------|------------|-----------------|
| Backend language/runtime | Python | 3.11+ (managed with `uv`) |
| Backend framework | FastAPI | `uvicorn`, async lifespan |
| ORM | SQLAlchemy | 2.0 (`DeclarativeBase`, `Mapped[...]`) |
| Migrations | None (create_all at startup) | SQL scripts under `backend/scripts/` |
| Vector store | PostgreSQL + pgvector | `langchain-postgres` `PGVectorStore`, table `vector_documents`, `vector(3072)` |
| LLM (chat) | Groq | `openai/gpt-oss-120b`, temperature 0.3 |
| Embeddings | Google Generative AI | `gemini` embedding, `output_dimensionality=3072` |
| SQL parsing/validation | sqlglot | Dialect map: postgresql → `postgres`, mssql → `tsql` |
| Password hashing | pwdlib | Argon2 (recommended) |
| JWT | PyJWT | HS256, `SECRET_KEY` ≥ 32 chars |
| Frontend framework | Next.js | 16.3.6 App Router |
| Frontend UI library | React | 19 |
| Styling | Tailwind CSS | v4 |
| UI components | shadcn-style / Radix primitives | dialog, tabs, select, tooltip, sidebar, scroll-area |
| Markdown/mermaid | react-markdown + remark-gfm + rehype-raw + mermaid | chat rendering |
| HTTP client | axios (client) + fetch (analysis service) | 401 auto-refresh interceptor |

### External services
- **Groq API** — text LLM (chat, SQL generation, intent classification, chart suggestion).
- **Google Generative AI** — embeddings only.

---

## 3. Repository Layout

```
chanakya-ai/
├── Architecture/                 17 pre-rendered architecture diagrams (PNG)
├── docs/                         This technical documentation suite
├── backend/
│   ├── main.py                   FastAPI app entry + CORS + lifespan
│   ├── core/                     config (pydantic-settings), security (JWT/pwd), cookies
│   ├── database/                 SQLAlchemy base + engine/session (get_db dep)
│   ├── api/                      Aggregated router + auth dependencies (CurrentUser/Admin)
│   ├── llm/                      langchain clients (Groq + optional Ollama) & RAG prompt service
│   ├── rag/                      loader (Docling/pypdf) · embeddings (Google) · vector_store (PGVectorStore) · service (ingest/retrieve)
│   ├── modules/                  Vertical slices (router → services → repository → models/schemas)
│   │   ├── auth/                 login / refresh / logout + RefreshToken model
│   │   ├── users/                /users/me profile endpoints
│   │   ├── admin/                clients, users, document/client assignments
│   │   ├── conversations/        chat threads per user
│   │   ├── messages/             messages + RAG answer orchestration
│   │   ├── documents/            document rows + user-scope assignments
│   │   ├── analysis/             NL→SQL subsystem: catalog, generator, guard, registry, executor, multi_executor, service, repository
│   │   └── intelligence/         hybrid QA: intent classification, routing, synthesis, chart, persistence
│   ├── prompts/                  main SQL system prompt (main_prompt.py)
│   ├── scripts/                  SQL migrations + create_admin + smoke_test
│   ├── storage/                  schema_notes.json (free-text table hints for catalog)
│   ├── tests/                    pytest: test_api, test_guard, test_scope, test_executor
│   ├── .env / .env.example       real / template config (.env never committed)
│   ├── pyproject.toml, requirements.txt, uv.lock
│   └── HR-Policy.pdf             sample document used in testing
└── frontend/
    ├── proxy.ts                  Next.js middleware: session bootstrap + refresh
    ├── app/                      Next.js 16 App Router (login, register, (protected)/)
    ├── components/               chat · admin · auth · markdown · ui (shadcn)
    ├── services/                 typed API clients (axios + fetch) + server session
    ├── lib/                      axios instance (401-refresh interceptor), utils
    ├── hooks/                    use-mobile
    ├── package.json, tsconfig.json, next.config.ts, eslint.config.mjs
    └── public/                   SVG assets
```

---

## 4. Documentation Suite Map

| Document | Covers |
|----------|--------|
| `01_TECHNICAL_ARCHITECTURE.md` | System architecture, component interactions, data-flow diagrams, references to `Architecture/*.png` |
| `02_DATABASE_SCHEMA.md` | App database ER diagram, table-by-table definitions, vector tables, client DB mapping |
| `03_API_REFERENCE.md` | Complete endpoint reference: methods, paths, auth, request/response schemas, error codes |
| `04_RAG_PIPELINE.md` | Document ingestion, chunking, embeddings, vector storage, retrieval, neighbor expansion, context formatting |
| `05_NL_TO_SQL_ANALYSIS_ENGINE.md` | Schema discovery, SQL generation, sqlglot guard, execution, pagination, CSV export, result JWTs, history/saved |
| `06_INTELLIGENCE_MODULE.md` | Hybrid QA: intent classification, database/document/hybrid/general routing, synthesis, chart config, chat persistence |
| `07_SECURITY_ARCHITECTURE.md` | Authentication, JWT/cookie transport, refresh rotation, authorization, client scoping, SQL sandboxing |
| `08_FRONTEND_ARCHITECTURE.md` | Next.js App Router, state management, service layer, auth/session flow, chat UI, admin panel |
| `09_DEPLOYMENT_AND_OPERATIONS.md` | Environments, configuration, deployment steps, runbook, logging, known limitations |
| `10_TESTING_AND_QUALITY.md` | Test strategy, linting (ruff), type-checking, CI notes, known limitations |

---

## 5. High-Level Data Flow (Summary)

```
Browser (Next.js 16 / React 19)
        │ httpOnly JWT cookies
        ▼
proxy.ts (Next middleware) ─ session bootstrap + token refresh
        │ all API traffic → http(s)://:8000/api
        ▼
FastAPI backend (uvicorn)
  ├─ lifespan: create_all() + init_vector_store()
  ├─ api/router.py  (auth · users · admin · conversations · messages · documents · analysis · intelligence)
  │
  ├─ RAG path:  loader → chunk → embed (Google, 3072-dim) → pgvector → Groq (context-only)
  │
  └─ SQL path:  catalog/global_catalog → generator (Groq) → guard (sqlglot) →
                executor/read-only txn → result JWT → rows / CSV export
        │              │                         │
        ▼              ▼                         ▼
 App PostgreSQL  Vector PostgreSQL    Client databases (one per client)
 (SQLAlchemy)    (pgvector)           (postgres_fdw → pollmatrix schema)
 users, tokens,  vector_documents,    each exposes shared main-DB tables
 conversations,  schema_catalog
 messages, docs,
 clients, ...
```

---

## 6. Relationship to Existing Documentation

- `PROJECT_DOCUMENTATION.md` (root) — the original consolidated project document. This suite expands on it with implementation-level detail, the `intelligence` module, a full API reference, database schema definitions, and an operations runbook.
- `Architecture/*.png` — 17 pre-rendered diagrams referenced throughout this suite (high-level architecture, conversation flow, database ER, deployment, security, SQL validation pipeline, hybrid search, query router, report generation, etc.).
- `backend/README.md`, `frontend/README.md` — service-specific getting-started notes.
