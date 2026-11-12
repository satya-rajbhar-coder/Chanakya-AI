# Chanakya AI — NL → SQL Analysis Engine

> **Document:** `docs/05_NL_TO_SQL_ANALYSIS_ENGINE.md`  
> **Scope:** The Analysis subsystem: natural-language → guarded SQL generation, execution, pagination, CSV export, result tokens, history, and saved analyses.  
> **Source:** `backend/modules/analysis/` (`service.py`, `catalog.py`, `generator.py`, `guard.py`, `registry.py`, `executor.py`, `multi_executor.py`, `repository.py`, `router.py`, `schemas.py`) + `backend/prompts/main_prompt.py` + `backend/storage/schema_notes.json`.  
> **Diagrams:** `Architecture/SQL Validation Pipeline.png`, `Architecture/Database Schema Retrieval.png`, `Architecture/Report Generation Architecture.png`, `Architecture/Hybrid Document + Database Query.png`.

---

## 1. Overview

The Analysis engine lets analysts ask natural-language questions against their **assigned client database** and receive a generated, guarded, read-only SQL query with paginated results, CSV export, history, and saved analyses.

```
question → resolve client → table selection → bounded schema →
Groq NL→SQL (JSON) → sqlglot guard → read-only execution →
result JWT → rows / CSV export → history + saved analyses
```

**Target:** PostgreSQL is the recommended client database. MSSQL execution is partial (no read-only transaction, manual offset buffering, dialect mismatch).

---

## 2. Module Components

| File | Responsibility |
|------|----------------|
| `service.py` | Orchestration: client scoping, plan-and-run retry loop, result JWT signing, history/saved CRUD |
| `catalog.py` | Per-database vectorized table catalog + bounded per-table schema |
| `global_catalog.py` | Reflection-based logical table discovery for sharded partition tables |
| `generator.py` | Groq NL→SQL call using the 23 KB system prompt |
| `guard.py` | sqlglot defense-in-depth SELECT-only validator |
| `registry.py` | Per-database engine cache + dialect map |
| `executor.py` | `run_page` / `stream_csv` (read-only txn, timeouts) |
| `multi_executor.py` | Same SQL across N DBs + in-Python hash join/merge |
| `repository.py` | History / saved-analyses persistence |
| `router.py` | `/api/analysis/*` endpoints |
| `schemas.py` | `AskRequest`, `AnalysisResponse`, `ResultPage`, `TokenRequest`, history schemas |

---

## 3. Client Scoping & Database Resolution

`AnalysisService.assigned_database(user_id, client_id)` returns `(database_name, client_uuid, client_identifier)`:

- `client_id is None`:
  - Exactly one assigned client → use it.
  - None assigned → **403** "You are not assigned to any client".
  - Several assigned without a `client_id` → **400** "Select a client for this question".
- `client_id` provided:
  - Admin (`role == "admin"`) → may use any client.
  - Regular user → must be assigned (`get_client_database_name_for_user(client_id, user_id, False)`); else **403**.
- `client_identifier` (e.g. `client147`) is injected into generated SQL as the tenant filter (`{{client_id}}`).

---

## 4. Schema Discovery (Two Generations, Both in Use)

### 4.1 `catalog.py` — Vectorized per-database catalog

- `build_catalog(db)`: reflects table names (incl. shared `pollmatrix.*` tables), merges free-text hints from `storage/schema_notes.json`, vector-embeds `"Table <name>. <note>"` into the `schema_catalog` pgvector table (delete+insert per db).
- `select_tables(question, db)`: top-`ANALYSIS_TOP_TABLES` (3) matching tables by similarity (filtered by `db` metadata), then greedily appends FK-neighbor tables (max 5).
- `describe_table(db, table, question)`: bounded lazy reflection — PK/FK parts pinned first, remaining columns ranked by **overlap of question words with column name parts**, truncated to `ANALYSIS_MAX_COLUMNS`, formatted `col type [PK] [FK->table.col] …`. LRU-cached (512) per `(db, table, question)`.

### 4.2 `global_catalog.py` — Reflection-based logical discovery (shards)

- Understands sharded client DBs carry **partition-suffix table names** (`user_master__partition_client147` …).
- Computes **logical table names** by stripping known suffix patterns: `__partition_clientNN`, `__clientNN`, `_clientNN`, `_partitionN`.
- Keyword-ranks logical tables against the question (exact / substring / word-overlap + "in more DBs" weight).
- Auto-builds / clears reflection caches. No vectors.

---

## 5. SQL Generation (`generator.py`)

- Calls Groq (`openai/gpt-oss-120b`) with a **hardcoded 23 KB system prompt** (`SYSTEM` in `backend/prompts/main_prompt.py`, mirrored in `backend/modules/analysis/prompts.py`).
- The prompt encodes:
  - Shared tables: `client_master`, `executive_master`, `user_master`, `hitchintak_master_pollmatrix_new`, `karyakarni_master_pollmatrix_new`.
  - Client-side tables: `dw_voters_info`, `voter_details_corp`, `activity_details_corp/sir`, `contact_sync_corp/sir`.
  - Columns and dozens of semantic business rules (colour_code R/G/Y, status_type D/A/O, marnmar/marnmar_det caste codes, SIR 2002 columns, survey fields…).
  - 18 documented logical joins; join-safety rules (never invent `ac_no` on `dw_voters_info`, avoid fan-out, no guessed master tables).
  - Safety rules: read-only SELECT, no secrets (`client_key`, `password`), no LIMIT unless asked, inline literal params, JSON output contract.
- Multi-language support: English, Hindi, Marathi, Hinglish…
- `{{client_id}}` placeholder substituted with the client's `client_identifier`.
- Output contract: exactly one JSON object `{title, sql|null, reason}`. Fenced ``` stripped; non-JSON → `{sql: null, reason:"did not return valid JSON"}`.
- `generate_sql(question, dialect, schema, client_id, previous_sql=None, error=None)`: supports refinement (previous SQL + error fed back to the LLM).

---

## 6. SQL Guard (`guard.py`) — sqlglot Defense-in-Depth

`validate_select(sql, dialect, allowed_tables, known_tables=(), resolve=None)`:

1. Parse with sqlglot (`read=dialect`); exactly **1 statement**.
2. Must be `exp.Query` (SELECT/WITH).
3. Forbidden node types: `Insert`, `Update`, `Delete`, `Drop`, `Create`, `Alter`, `Merge`, `Command`, `Into`, `TruncateTable`.
4. Blocks dangerous functions: `pg_*`, `lo_*`, `dblink*`, `pg_sleep`, `current_setting`, `current_database`, `version`.
5. **Every query must touch a table** (blocks `SELECT 'Paris'` cop-outs).
6. Schema-qualification allowed **only** for `pollmatrix.*` (FDW schema); all other cross-schema/cross-db rejected.
7. Bare table names must be: CTEs, in the allowed top-k, or known real tables — else rewritten logical→physical via `resolve`.
8. Returns normalized SQL re-rendered in the target dialect.

Raises `UnsafeSQL` on violation.

---

## 7. Execution (`executor.py` / `multi_executor.py`)

### 7.1 `run_page(database, sql, offset, page_size)`
- Wraps SQL as `SELECT * FROM (… ) AS q LIMIT page+1 OFFSET off` (colons escaped `:` → `\:`).
- Opens connection with `SET TRANSACTION READ ONLY` + `SET LOCAL statement_timeout` (15 s query).
- MSSQL path: no read-only txn; buffers one page after `fetchmany(offset)` skip (no ORDER BY needed).
- Returns `{columns, rows(jsonable_encoder), page, page_size, has_more, total_time_ms}`.

### 7.2 `stream_csv(database, sql)`
- Streams chunks of 1,000 rows as CSV (header first).
- Cap: 1,000,000 rows; export timeout 300 s.
- Returned as `StreamingResponse` (`text/csv`, `attachment; filename="export.csv"`).

### 7.3 `multi_executor`
- Runs the same SQL on each database independently; per-DB errors captured, not fatal.
- Returns `{databases: {db: page}, merged_result?, join_key, join_type}`.
- In-Python **hash join / merge** across DB results when `join_key` provided.

---

## 8. Service Orchestration (`service.py`)

### 8.1 `plan_and_run(question, user_id, client_id)`
Retry loop (max 2 attempts):
1. `generate_sql(question, dialect, schema, client_identifier, previous_sql, error)`.
2. On LLM call failure → set error, retry once.
3. If no SQL produced → set reason, retry.
4. `validate_select` (guard) → on `UnsafeSQL` or `SQLAlchemyError` → feed error back to LLM, retry.
5. `run_page` → success → break.
6. Total failure → persist `analysis_queries` with status `FAILED`, raise:
   - **502** if LLM failed; else **422** with `OUT_OF_SCOPE` or last error.

### 8.2 `ask(data, user_id)`
- Runs `plan_and_run`, persists `analysis_queries` (status `SUCCESS`, row_count, timings, `query_hash` = SHA-256 of SQL).
- Mints a **signed result JWT** (`sign_result`): payload `{type: "analysis", sub: user_id, db, client_id, sql, exp: now + ANALYSIS_TOKEN_MINUTES (120)}`.
- Returns `{title, database, tables, sql, analysis_query_id, token, result}`.

### 8.3 Result token verification (`open_result`)
- Decodes JWT; verifies `type == "analysis"`, `sub == user_id`.
- If `client_id` present: re-resolves `assigned_database`; if `database` changed → **403** "Database assignment has changed".
- Used by `/analysis/rows` (pagination) and `/analysis/export` (CSV) to re-verify ownership + assignment.

### 8.4 History & Saved Analyses
- Every run logged to `analysis_queries` (status, row_count, timings, query_hash, explain_plan JSONB).
- **History** (`/analysis/history`): users see own rows (SQL excluded); admins see all (SQL included). Filterable by `client_id`.
- **Re-run** (`/analysis/history/{id}/run`): re-executes stored SQL (no regeneration); re-validates with guard; re-checks assignment; mints new token.
- **Delete** (`/analysis/history/{id}`): user-owned only.
- **Save** (`/analysis/saved`): snapshot `{token, question, title}` → `saved_analyses`. Re-run + delete semantics identical to history; both re-check assignment-change before executing.

---

## 9. Configuration (`core/config.py` — Analysis group)

| Setting | Default | Purpose |
|---------|---------|---------|
| `ANALYSIS_DB_URL_TEMPLATE` | (required) | `{name}` placeholder → per-client DB URL |
| `ANALYSIS_MAIN_DB_SCHEMA` | `pollmatrix` | FDW foreign schema in each client DB |
| `ANALYSIS_SCHEMA_TABLE` | `schema_catalog` | Vector catalog table name |
| `ANALYSIS_NOTES_FILE` | `storage/schema_notes.json` | Free-text table hints |
| `ANALYSIS_TOP_TABLES` | 3 | Tables selected per question |
| `ANALYSIS_MAX_COLUMNS` | 0 (unbounded) | Column truncation cap |
| `ANALYSIS_PAGE_SIZE` | 100 | Default page size |
| `ANALYSIS_MAX_PAGE_SIZE` | 500 | Max page size |
| `ANALYSIS_TIMEOUT_MS` | 15,000 | Query statement timeout |
| `ANALYSIS_EXPORT_TIMEOUT_MS` | 300,000 | Export timeout |
| `ANALYSIS_EXPORT_MAX_ROWS` | 1,000,000 | CSV row cap |
| `ANALYSIS_TOKEN_MINUTES` | 120 | Result JWT TTL |

---

## 10. Endpoints (Summary)

See `docs/03_API_REFERENCE.md` §9 for full request/response schemas. Key endpoints:

- `GET /analysis/clients` — assigned clients
- `POST /analysis/query` — single-client NL→SQL
- `POST /analysis/query/global` — multi-DB NL→SQL
- `POST /analysis/rows` `{token, page, page_size}` — paginated rows (token-verified)
- `POST /analysis/export` `{token}` — CSV stream (token-verified, cap 1M rows)
- `GET /analysis/history[?client_id]` — user history (no SQL)
- `GET /analysis/admin/history` — admin history (with SQL)
- `POST /analysis/history/{id}/run` — re-run stored query
- `DELETE /analysis/history/{id}` — delete history
- `POST /analysis/saved` / `GET /analysis/saved` / `POST …/saved/{id}/run` / `DELETE …/saved/{id}` — saved analyses
- `POST /analysis/catalog/global/build` (admin) — rebuild global catalog

---

## 11. Security Properties

- **Read-only transactions** + **statement timeouts** on every analysis query.
- **sqlglot guard** blocks DML/DDL, dangerous functions, cross-schema access (except `pollmatrix.*`), and table-less queries.
- **Client scoping** re-verified on token rows / export / history / saved re-runs — assignment change → 403.
- Generated SQL is told to filter by `client_id`; shared tables reachable only via the `pollmatrix` FDW foreign schema of the connected client DB.
- Result tokens are **signed, not encrypted** — a user can decode their own SQL by design.
- Defense-in-depth only: the analysis DB role itself should be read-only and restricted.
