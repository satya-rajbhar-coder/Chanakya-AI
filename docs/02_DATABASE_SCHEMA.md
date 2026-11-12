# Chanakya AI — Database Schema

> **Document:** `docs/02_DATABASE_SCHEMA.md`  
> **Scope:** App database entity-relationship model, table-by-table column definitions, indexes, relationships, and vector-store schema.  
> **Source of truth:** SQLAlchemy ORM models under `backend/modules/*/models.py` and `backend/database/base.py`.  
> **Diagram:** See `Architecture/Database ER Diagram.png`.

---

## 1. Entity-Relationship Overview

```
users 1 ─∞ refresh_tokens           users 1 ─∞ conversations 1 ─∞ messages
users 1 ─∞ documents  ─∞ document_assignments ∸─ users        [direct doc access]
users ∞ ─∞ clients          via user_clients (is_primary)     [analysis scope]

clients (code, name, database_name UNIQUE, client_identifier UNIQUE e.g. client147)
saved_analyses (user, client, question, database, sql)
analysis_queries (user, client, database_name, question, title, sql, status,
                  error_message, row_count, page#, page_size,
                  planning/execution/total_time_ms, query_hash, explain_plan JSONB)
chat_analysis_queries (assistant_message_id PK FK messages, analysis_query_id unique FK analysis_queries)

Vector tables (pgvector, langchain-postgres shape):
  vector_documents (content, embedding vector(3072), user_id, document_id, filename,
                    source_hash, content_hash, page, chunk_index, total_chunks, element_type)
  schema_catalog   (content "Table <n>. <note>", embedding, db, table_name)
```

Key scoping rules:
- **Documents** → scoped by `document_assignments` (a document is visible to the users listed there). `Document.client_id` is nullable legacy metadata.
- **Analysis** → scoped by `user_clients` (which clients a user may query). Each client maps to exactly one database (`clients.database_name`, unique).
- **Conversations/Messages** → per-user ownership only.
- **History/Saved** → per-user, tied to a client/database.

---

## 2. App Database Tables (PostgreSQL / SQLAlchemy)

All tables use `DeclarativeBase` (`database/base.py`). Primary keys are UUIDs (`uuid4`). Timestamps are `DateTime(timezone=True)` with `server_default=func.now()`.

### 2.1 `users`

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| `id` | UUID | NO | `uuid4` | PK |
| `name` | String(100) | NO | — | Display name |
| `email` | String(255) | NO | unique | Login identifier |
| `hashed_password` | String(255) | NO | — | Argon2 hash |
| `role` | String(10) | NO | `"user"` | `"user"` or `"admin"` |
| `is_active` | Boolean | NO | `true` | Deactivation takes effect immediately |
| `created_at` | DateTime(tz) | NO | `now()` | — |
| `updated_at` | DateTime(tz) | NO | `now()` | `onupdate=now()` |

Relationships: `conversations` (cascade delete), `messages`, `documents` (cascade delete), `refresh_tokens` (cascade delete).

### 2.2 `refresh_tokens`

Server-side refresh-token store (rotation + revocation list).

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| `id` | UUID | NO | `uuid4` | PK |
| `token_hash` | String(64) | NO | unique, indexed | SHA-256 hash of the refresh token |
| `user_id` | UUID | NO | FK `users.id` CASCADE, indexed | Owner |
| `expires_at` | DateTime(tz) | NO | indexed | Expiry |
| `revoked_at` | DateTime(tz) | YES | — | Set on revocation/logout/rotation |
| `created_at` | DateTime(tz) | NO | `now()` | — |

### 2.3 `clients`

Represents one tenant / campaign client. Each client maps to exactly one exclusive database.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| `id` | UUID | NO | `uuid4` | PK |
| `code` | String(100) | NO | unique | Short client code |
| `name` | String(200) | NO | — | Display name |
| `database_name` | String(100) | NO | unique | Target analysis DB name |
| `client_identifier` | String(100) | NO | unique | Tenant id injected into SQL (e.g. `client147`) |
| `description` | Text | YES | — | Free text |
| `is_active` | Boolean | NO | `true` | — |
| `created_at` | DateTime(tz) | NO | `now()` | — |

### 2.4 `user_clients`

Many-to-many assignment of users to clients (analysis scope). Composite PK (`user_id`, `client_id`).

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| `user_id` | UUID | NO | FK `users.id` CASCADE, PK | — |
| `client_id` | UUID | NO | FK `clients.id` CASCADE, PK | — |
| `is_primary` | Boolean | NO | `false` | Primary client flag |
| `created_at` | DateTime(tz) | NO | `now()` | — |

### 2.5 `conversations`

Chat threads. One per user; auto-titled "New Chat" until first message.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| `id` | UUID | NO | `uuid4` | PK |
| `user_id` | UUID | NO | FK `users.id`, indexed | Owner |
| `title` | String(100) | NO | — | `"New Chat"` until renamed |
| `created_at` | DateTime(tz) | NO | `now()` | — |
| `updated_at` | DateTime(tz) | NO | `now()` | `onupdate=now()` |

Index: `ix_conversations_user_updated(user_id, updated_at)` — supports newest-first listing.

### 2.6 `messages`

Chat messages. Role enum `user` / `assistant`.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| `id` | UUID | NO | `uuid4` | PK |
| `conversation_id` | UUID | NO | FK `conversations.id` CASCADE, indexed | Parent thread |
| `user_id` | UUID | NO | FK `users.id` CASCADE, indexed | Owner |
| `role` | Enum `message_role` | NO | `user` | `user` or `assistant` |
| `content` | Text | NO | — | Message body |
| `created_at` | DateTime(tz) | NO | `now()` | — |
| `updated_at` | DateTime(tz) | NO | `now()` | `onupdate=now()` |

Index: `ix_messages_conversation_created_id(conversation_id, created_at, id)` — keyset/cursor pagination.

Relationship: `analysis_query_link` (1:1 to `chat_analysis_queries`, cascade delete).

### 2.7 `documents`

Document metadata only — **file bytes are never stored**; content lives in pgvector chunks.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| `id` | UUID | NO | `uuid4` | PK |
| `user_id` | UUID | NO | FK `users.id` CASCADE, indexed | Uploader/owner |
| `client_id` | UUID | YES | FK `clients.id` SET NULL, indexed | Legacy; nullable |
| `filename` | String(255) | NO | — | Original file name |
| `content_type` | String(100) | NO | `application/octet-stream` | MIME type |
| `size_bytes` | BigInteger | NO | — | Uploaded file size |
| `chunk_count` | Integer | NO | `0` | Number of vector chunks |
| `created_at` | DateTime(tz) | NO | `now()` | — |

Relationship: `assignments` → `DocumentAssignment` (cascade delete).

### 2.8 `document_assignments`

Direct document access for specific dashboard users. Composite PK (`document_id`, `user_id`).

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| `document_id` | UUID | NO | FK `documents.id` CASCADE, PK | — |
| `user_id` | UUID | NO | FK `users.id` CASCADE, PK, indexed | Granted user |
| `created_at` | DateTime(tz) | NO | `now()` | — |

### 2.9 `saved_analyses`

User-saved analysis snapshots (title/question/sql). Re-runnable from the Saved panel.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| `id` | UUID | NO | `uuid4` | PK |
| `user_id` | UUID | NO | FK `users.id` CASCADE, indexed | Owner |
| `client_id` | UUID | YES | FK `clients.id` SET NULL, indexed | Client context |
| `title` | String(200) | NO | — | Saved title |
| `question` | Text | NO | — | Original question |
| `database` | String(100) | NO | — | Database name at save time |
| `sql` | Text | NO | — | Saved SQL snapshot |
| `created_at` | DateTime(tz) | NO | `now()` | — |

### 2.10 `analysis_queries`

History log of every analysis run (success + failure). Powers the History panel.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| `id` | UUID | NO | `uuid4` | PK |
| `user_id` | UUID | NO | FK `users.id` CASCADE, indexed | Owner |
| `client_id` | UUID | YES | FK `clients.id` SET NULL, indexed | Client context |
| `database_name` | String(100) | NO | — | DB queried |
| `question` | Text | NO | — | Original question |
| `title` | String(200) | YES | — | Query title |
| `sql` | Text | NO | — | Executed SQL |
| `status` | String(30) | NO | `"SUCCESS"` | `"SUCCESS"` or `"FAILED"` |
| `error_message` | Text | YES | — | Failure reason |
| `row_count` | Integer | YES | — | Rows returned |
| `page_number` | Integer | YES | — | Page fetched |
| `page_size` | Integer | YES | — | Page size |
| `planning_time_ms` | Numeric(12,3) | YES | — | DB planning time |
| `execution_time_ms` | Numeric(12,3) | YES | — | DB execution time |
| `total_time_ms` | Numeric(12,3) | YES | — | End-to-end time |
| `query_hash` | String(64) | YES | — | SHA-256 of SQL |
| `explain_plan` | JSONB | YES | — | EXPLAIN output |
| `created_at` | DateTime(tz) | NO | `now()` | — |

### 2.11 `chat_analysis_queries`

Links an assistant message in an intelligence conversation to the `analysis_queries` row it produced (hybrid/database path).

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| `assistant_message_id` | UUID | NO | PK, FK `messages.id` CASCADE |
| `analysis_query_id` | UUID | NO | unique, FK `analysis_queries.id` CASCADE |

---

## 3. Vector Store Schema (pgvector)

Hosted in the **Vector PostgreSQL** (separate DB or same instance), managed by `langchain-postgres` `PGVectorStore`. Initialized at startup via `init_vector_store()` (`backend/rag/vector_store.py`).

### 3.1 `vector_documents`

| Column | Type | Notes |
|--------|------|-------|
| `content` | Text | Chunk text |
| `embedding` | vector(3072) | Google Gemini embedding |
| `user_id` | UUID | Owner (scoping) |
| `document_id` | UUID | Source document |
| `filename` | Text | Source file name |
| `source_hash` | Text | SHA-256 of source file |
| `content_hash` | Text | SHA-256 of normalized chunk text |
| `page` | Integer | PDF page (optional) |
| `chunk_index` | Integer | Chunk position |
| `total_chunks` | Integer | Total chunks in doc |
| `element_type` | Text | `table` / `text` / etc. |

Chunk IDs are deterministic: `uuid5(document_id:index)`. Metadata includes all of the above.

### 3.2 `schema_catalog`

| Column | Type | Notes |
|--------|------|-------|
| `content` | Text | `"Table <name>. <note>"` |
| `embedding` | vector(3072) | Embedding of the content |
| `db` | Text | Client database name (filter key) |
| `table_name` | Text | Physical table name |

Built per-client-database by `analysis/catalog.py` (`build_catalog`), merging free-text hints from `storage/schema_notes.json`.

---

## 4. Relationships & Referential Integrity

| Parent | Child | FK | On delete |
|--------|-------|----|-----------|
| `users.id` | `refresh_tokens.user_id` | CASCADE | rows removed with user |
| `users.id` | `conversations.user_id` | CASCADE | conversations removed |
| `users.id` | `messages.user_id` | CASCADE | messages removed |
| `users.id` | `documents.user_id` | CASCADE | documents removed |
| `conversations.id` | `messages.conversation_id` | CASCADE | messages removed |
| `users.id` | `saved_analyses.user_id` | CASCADE | saved analyses removed |
| `users.id` | `analysis_queries.user_id` | CASCADE | history removed |
| `clients.id` | `saved_analyses.client_id` | SET NULL | client removal nulls ref |
| `clients.id` | `analysis_queries.client_id` | SET NULL | client removal nulls ref |
| `clients.id` | `documents.client_id` | SET NULL | client removal nulls ref |
| `clients.id` | `user_clients.client_id` | CASCADE | assignment removed |
| `users.id` | `user_clients.user_id` | CASCADE | assignment removed |
| `documents.id` | `document_assignments.document_id` | CASCADE | assignments removed |
| `users.id` | `document_assignments.user_id` | CASCADE | assignments removed |
| `messages.id` | `chat_analysis_queries.assistant_message_id` | CASCADE | link removed |
| `analysis_queries.id` | `chat_analysis_queries.analysis_query_id` | CASCADE | link removed |

---

## 5. Indexes Summary

| Table | Index | Purpose |
|-------|-------|---------|
| `users` | PK `id` | lookups |
| `users` | unique `email` | login lookup |
| `refresh_tokens` | unique `token_hash` | token validation |
| `refresh_tokens` | `user_id`, `expires_at` | cleanup/rotation |
| `clients` | unique `database_name`, `client_identifier`, `code` | uniqueness |
| `conversations` | `user_id`, `updated_at` | newest-first list |
| `messages` | `conversation_id`, `created_at`, `id` | cursor pagination |
| `documents` | `user_id`, `client_id` | scoping queries |
| `document_assignments` | `user_id` | visible-doc lookup |
| `user_clients` | composite PK | assignment lookup |
| `saved_analyses` | `user_id`, `client_id` | history/saved queries |
| `analysis_queries` | `user_id`, `client_id` | history queries |

---

## 6. Client Database Mapping (Multi-Tenancy)

Each client DB is independent and reachable only through its own connection. `backend/analysis/registry.py`:

- `get_engine(name)` — builds/caches a SQLAlchemy engine by formatting `ANALYSIS_DB_URL_TEMPLATE` with `{name}`. Name validated against `^[A-Za-z_][A-Za-z0-9_]*$`.
- Dialect map for sqlglot: `postgresql → "postgres"`, `mssql → "tsql"`.
- `get_all_database_names()` — reads active `clients.database_name` from the app DB.

Every client DB exposes shared main-DB tables through a **foreign schema `pollmatrix`** (postgres_fdw), configured by `scripts/setup_main_db_fdw.sql`. All SQL runs through the client connection only; shared tables are never reached by a direct app-DB connection.
