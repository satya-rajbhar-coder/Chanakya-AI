# Chanakya AI — company administration and analyst dashboard

FastAPI backend + Next.js frontend. Documents are uploaded by company admins and visible to dashboard users assigned to the same **client**. Analysis queries run against the databases assigned to that user. The `/` page contains document Q&A and analysis (with persistent History); `/admin` manages clients, users, assignments and ingestion.

## Before deploying

1. Back up the app database and pgvector storage. `Base.metadata.create_all()` creates new tables but does not migrate existing columns; for existing deployments apply `scripts/002_client_migration.sql` in PostgreSQL before restarting. Existing documents start unassigned and are invisible to dashboard users until an admin scopes each with `PUT /api/admin/documents/{id}/assignments` and `{"user_ids": [...]}`.
2. Set `DATABASE_URL`, `VECTOR_STORE_URL`, Groq and Google keys, and a **new random `SECRET_KEY` (at least 32 chars)** in `.env` (see `.env.example`). Never commit `.env`. Rotate any keys previously exposed in plaintext. The vector table is initialized at startup (see `rag/vector_store.py`) before ingesting documents.
3. Configure `ANALYSIS_DB_URL_TEMPLATE` with a **read-only login**; `{name}` is replaced with the database name the admin creates. Creating a client verifies connectivity and **builds the schema catalog automatically**. Tune `ANALYSIS_TOP_TABLES` and `ANALYSIS_MAX_COLUMNS` if needed. Each client needs an **exclusive** database (unique constraint enforced).
4. Install backend dependencies with `uv sync` (Python 3.11+), then start once using `uv run uvicorn main:app`. Create the first company admin from the server with `uv run python -m scripts.create_admin admin@company.com`. No public registration or browser-based admin promotion exists.
5. Set frontend `NEXT_PUBLIC_API_URL` and run `npm install`, `npm run dev` from `frontend/`. Login as admin, create the client, create users with assignments, then upload PDF/TXT/MD in `/admin`.

Every successful analysis query is stored and shown in the **History** panel; users can re-run or delete past queries, and CSV export works from any result. A user sees only documents in assigned clients; document retrieval filters vector matches by the set of currently visible document IDs. A revoked assignment takes effect immediately for document search, new queries, history/saved re-runs, pagination and exports. Deactivation blocks login, refresh and subsequent requests, even with an existing access cookie. Analysis JWTs are signed, not encrypted; users can read their own SQL.

## Operational limits

- The analysis SQL guard permits SELECT against selected allowed tables, but **the source DB role must also be read-only and limited to allowed tables**; use database permissions/RLS for any sensitive rows or columns. MSSQL execution currently lacks PostgreSQL's read-only transaction and uses PostgreSQL-style `LIMIT/OFFSET`; use PostgreSQL for this setup or adapt the executor for MSSQL.
- Upload processing and embedding occur during the HTTP request; allow sufficient reverse-proxy timeout. Legacy unscoped uploads can be assigned via the admin document-scope API; vectors are reused without re-embedding.
- `schema_catalog` and document vector store reside in the app PostgreSQL database, not in the analysis database. The catalog is never created/rebuilt by an analyst query.

## Tests

`uv run --with pytest --with httpx python -m pytest -q`
