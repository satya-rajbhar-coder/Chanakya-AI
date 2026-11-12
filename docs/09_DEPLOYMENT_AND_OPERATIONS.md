# Chanakya AI — Deployment & Operations

> **Document:** `docs/09_DEPLOYMENT_AND_OPERATIONS.md`  
> **Scope:** Environments, configuration, deployment steps, runbook, logging, and known limitations.  
> **Diagram:** `Architecture/Deployment Architecture.png`.  
> **Source:** `backend/core/config.py`, `backend/main.py`, `backend/scripts/`, `backend/README.md`, `frontend/README.md`.

---

## 1. Deployment Topology

A minimal production deployment consists of:

1. **App host** — runs FastAPI (uvicorn) + Next.js (or Next.js on a separate edge host).
2. **App PostgreSQL** — primary relational store (users, tokens, conversations, documents, clients, history).
3. **Vector PostgreSQL** (can be same instance, separate database) — pgvector store for document chunks + schema catalog.
4. **Client databases** — one PostgreSQL (recommended) or MSSQL database per client, each with `pollmatrix` foreign schema pointing at shared main-DB tables.
5. **External services** — Groq API (LLM), Google Generative AI (embeddings).

Network: CORS allow-list plus LAN-origin regex permits local-network clients. Cookies are `Secure` in production (`COOKIE_SECURE=true`), `SameSite=lax`.

---

## 2. Backend Configuration (`.env`)

`backend/core/config.py` — a single pydantic-settings `Settings`, loaded from `.env` (`model_config = SettingsConfigDict(env_file=".env", extra="ignore")`).

| Group | Setting | Default | Purpose |
|-------|---------|---------|---------|
| Core | `DATABASE_URL` | (required) | App DB connection |
| Core | `SECRET_KEY` | (required, ≥32) | JWT signing |
| Core | `ALGORITHM` | `HS256` | JWT algorithm |
| Auth | `ACCESS_TOKEN_EXPIRE_MINUTES` | 15 | Access TTL |
| Auth | `REFRESH_TOKEN_EXPIRE_DAYS` | 30 | Refresh TTL |
| Cookie | `COOKIE_SECURE` | `false` | Cookie Secure flag (true in prod) |
| Cookie | `COOKIE_SAMESITE` | `lax` | lax / strict / none |
| Core | `SQL_ECHO` | `false` | SQLAlchemy echo |
| LLM | `GROQ_MODEL_NAME` | `openai/gpt-oss-120b` | ChatGroq model |
| LLM | `GROQ_API_KEY` | (required) | Groq API key |
| LLM | `GOOGLE_API_KEY` | (required) | Google GenAI API key |
| LLM | `LLM_TIMEOUT_SECONDS` | 120.0 | LLM call timeout |
| RAG | `GOOGLE_EMBEDDING_MODEL` | (required) | Embedding model |
| RAG | `VECTOR_STORE_URL` | (required) | Vector PostgreSQL URL |
| RAG | `VECTOR_COLLECTION` | `vector_documents` | Collection name |
| RAG | `VECTOR_DIMENSION` | 3072 | Embedding dimension |
| RAG | `CHUNK_SIZE` | 1000 | Chunk size (chars) |
| RAG | `CHUNK_OVERLAP` | 150 | Chunk overlap (chars) |
| RAG | `RETRIEVER_K` | 5 | Retrieval top-K |
| RAG | `RAG_MAX_DISTANCE` | (optional) | Distance cut-off |
| RAG | `MAX_UPLOAD_MB` | 20 | Max upload size |
| Analysis | `ANALYSIS_DB_URL_TEMPLATE` | (required) | `{name}` placeholder → per-client DB URL |
| Analysis | `ANALYSIS_MAIN_DB_SCHEMA` | `pollmatrix` | FDW foreign schema |
| Analysis | `ANALYSIS_SCHEMA_TABLE` | `schema_catalog` | Vector catalog table |
| Analysis | `ANALYSIS_NOTES_FILE` | `storage/schema_notes.json` | Free-text table hints |
| Analysis | `ANALYSIS_TOP_TABLES` | 3 | Tables selected per question |
| Analysis | `ANALYSIS_MAX_COLUMNS` | 0 | Column truncation cap (0 = unbounded) |
| Analysis | `ANALYSIS_PAGE_SIZE` | 100 | Default page size |
| Analysis | `ANALYSIS_MAX_PAGE_SIZE` | 500 | Max page size |
| Analysis | `ANALYSIS_TIMEOUT_MS` | 15,000 | Query statement timeout |
| Analysis | `ANALYSIS_EXPORT_TIMEOUT_MS` | 300,000 | Export timeout |
| Analysis | `ANALYSIS_EXPORT_MAX_ROWS` | 1,000,000 | CSV row cap |
| Analysis | `ANALYSIS_TOKEN_MINUTES` | 120 | Result JWT TTL |

> `.env` is real/secret and **never committed**; `.env.example` is the template.

---

## 3. Backend Deployment Steps

```bash
# 1. Install dependencies
cd backend
uv sync

# 2. Configure environment
cp .env.example .env
# edit .env with DATABASE_URL, SECRET_KEY, GROQ_API_KEY, GOOGLE_API_KEY, VECTOR_STORE_URL, ANALYSIS_DB_URL_TEMPLATE, …

# 3. Bootstrap the first admin (server-side only)
uv run python -m scripts.create_admin admin@company.com

# 4. (Existing installs) Run client-migration + FDW setup
#   scripts/002_client_migration.sql   (adds clients/UserClient + doc scoping)
#   scripts/setup_main_db_fdw.sql      (creates pollmatrix foreign schema in each client DB)

# 5. Run the server
uv run uvicorn main:app
# health probe: GET /health
```

- **lifespan:** `Base.metadata.create_all(bind=engine)` then `init_vector_store()` (vector init failure is logged as a warning — app still starts).
- CORS allow-list + LAN-origin regex configured in `main.py`.
- Router mounted at `/api`; OpenAPI at `/api/openapi.json`; Swagger `/api/docs`; ReDoc `/api/redoc`.

---

## 4. Client Database Provisioning

For each client:
1. Create the client database (PostgreSQL recommended).
2. Create the `pollmatrix` foreign schema pointing at shared main-DB tables via `scripts/setup_main_db_fdw.sql`.
3. Register the client via admin UI (`POST /api/admin/clients`) or API — this validates DB reachability + non-empty schema, enforces unique `database_name`/`client_identifier`, and auto-builds the schema catalog.

---

## 5. Frontend Deployment Steps

```bash
cd frontend
npm install   # (or yarn / pnpm / bun)
npm run dev   # dev server at http://localhost:3000
# or
npm run build && npm start
```

- Set `NEXT_PUBLIC_API_URL` (default `http://localhost:8000/api`).
- Default dev ports: API 8000, FE 3000 (both LAN-origins pre-permitted server-side).
- Deploy: Vercel (recommended per README) or any Node host.

---

## 6. Logging

- App logs: Python `logging` (INFO) to stdout.
- Analysis queries: file handler `storage/logs/analysis_queries.log` (INFO) — every run logged with user/db/question/sql.
- Analysis queries also persisted to `analysis_queries` table (status, row_count, timings, query_hash, explain_plan JSONB).

---

## 7. Operational Runbook

| Task | Command / Action |
|------|-----------------|
| Create first admin | `uv run python -m scripts.create_admin <email>` |
| Run smoke test | `uv run python -m scripts.smoke_test` |
| Lint | `uv run ruff check backend` (line length 88, py311) |
| Run tests | `uv run --with pytest --with httpx python -m pytest -q` |
| Migrate existing install | `scripts/002_client_migration.sql` + `scripts/setup_main_db_fdw.sql` |
| Rotate secrets | Regenerate `SECRET_KEY`; reissue all sessions (users must re-login) |
| Rebuild global catalog | `POST /api/analysis/catalog/global/build` (admin) |
| Re-scope legacy documents | `PUT /api/admin/documents/{id}/assignments` (vectors reused, no re-embed) |

---

## 8. Known Limitations & Operational Notes

- **MSSQL execution is partial** (no read-only transaction; manual offset buffering; PostgreSQL `LIMIT/OFFSET` dialect mismatch) — target **PostgreSQL** for full guarantees.
- **Document upload processes + embeds inside the HTTP request** — set adequate proxy timeouts to avoid mid-ingest timeouts.
- Legacy uploads start **unassigned** and invisible to users; scope them via the admin `PUT /documents/{id}/assignments` API (vector reuse, no re-embed).
- `schema_catalog` + document vectors live in the **app/vector PostgreSQL**, never in analysis DBs; analysts cannot (re)build catalogs.
- Guard is defense-in-depth only — the analysis DB role itself must be read-only and restricted.
- Analysis tokens are **signed, not encrypted** — a user can decode their own SQL by design.
- No streaming/typing effect in chat (single request/response per turn).
