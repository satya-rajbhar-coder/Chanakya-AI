# Chanakya AI — API Reference

> **Document:** `docs/03_API_REFERENCE.md`  
> **Scope:** Complete backend HTTP API surface.  
> **Base path:** All routes are mounted under `/api` (except `/health` at root).  
> **Auth:** Cookie-based (httpOnly `access_token` / `refresh_token`). No bearer tokens, no localStorage.  
> **Source:** `backend/api/router.py` + module routers.  

---

## 1. Conventions

| Item | Convention |
|------|------------|
| Base URL | `http(s)://<host>:8000` |
| API prefix | `/api` |
| Health | `GET /health` (no auth) |
| Content-Type | `application/json` (multipart for document upload) |
| Auth transport | httpOnly cookies: `access_token`, `refresh_token` (`path=/`, `SameSite=lax`, `Secure` toggled by env) |
| Errors | FastAPI `HTTPException` → JSON `{"detail": "..."}`; status codes per endpoint |
| IDs | UUIDs (string form in JSON) |
| Timestamps | ISO-8601 with timezone |
| Pagination (messages) | Keyset/cursor: `next_cursor` (urlsafe-base64), newest-first, `limit ≤ 100` |
| Pagination (analysis rows) | `page` (0-based) + `page_size` (1–500, default 100) |

### Authentication dependencies (`backend/api/dependencies.py`)
- `CurrentUser` — resolves `access_token` cookie → verifies HS256 JWT → loads `User` → rejects if `is_active == false`. Returns 401 if missing/invalid.
- `AdminUser` — `CurrentUser` + `role == "admin"`, else 403.

---

## 2. Health

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `GET` | `/health` | None | Returns `{"status": "ok"}` |

---

## 3. Authentication (`/api/auth`)

All three endpoints set/clear httpOnly cookie pairs (`access_token` 15 min, `refresh_token` 30 days). Refresh tokens are stored server-side (SHA-256 hash) and rotated on use.

| Method | Endpoint | Auth | Request | Response |
|--------|----------|------|---------|----------|
| `POST` | `/auth/login` | None | `LoginRequest { email: EmailStr, password: str }` | `AuthMessage { message }` + sets `access_token` + `refresh_token` cookies |
| `POST` | `/auth/refresh` | refresh cookie | `refresh_token` cookie | `AuthMessage { message }` + rotates cookies (old revoked, new issued) |
| `POST` | `/auth/logout` | refresh cookie (optional) | `refresh_token` cookie | `AuthMessage { message }` + clears cookies |

**Notes:**
- Login verifies email + `is_active` + password (Argon2). No public registration; the first admin is created server-side via `uv run python -m scripts.create_admin <email>`.
- On `/refresh`, the used refresh token is revoked and replaced (rotation). Expired rows are pruned on login. Revoked/unknown hash → 401 + cookies cleared.
- On `/logout`, the refresh row (if present) is revoked and cookies cleared.

---

## 4. Users (`/api/users`)

| Method | Endpoint | Auth | Request | Response |
|--------|----------|------|---------|----------|
| `GET` | `/users/me` | CurrentUser | — | User profile `{ id, name, email, role, is_active, created_at, updated_at }` |
| `PATCH` | `/users/me` | CurrentUser | `{ name?: str }` | Updated user profile |
| `DELETE` | `/users/me` | CurrentUser | — | 204 (cascades conversations, messages, documents, refresh tokens) |

---

## 5. Admin (`/api/admin`)

Requires `AdminUser` (`role == "admin"`).

### Clients

| Method | Endpoint | Request | Response |
|--------|----------|---------|----------|
| `GET` | `/admin/clients` | — | `list[ClientResponse]` |
| `POST` | `/admin/clients` | `ClientCreate { code, name, database_name, client_identifier, description? }` | `ClientResponse` |
| `PATCH` | `/admin/clients/{id}` | `ClientUpdate { name?, description?, is_active? }` | `ClientResponse` |
| `DELETE` | `/admin/clients/{id}` | — | 204 |

**Client creation** validates DB reachability + non-empty schema, enforces unique `database_name`/`client_identifier`, then auto-builds the schema catalog (`build_catalog`) and checks `setup_main_db_fdw` expectations.

### Users (accounts)

| Method | Endpoint | Request | Response |
|--------|----------|---------|----------|
| `GET` | `/admin/users` | — | `list[AccountResponse]` |
| `POST` | `/admin/users` | `AccountCreate { name, email, password(min 8), client_ids: [UUID] }` | `AccountResponse` |
| `PATCH` | `/admin/users/{id}` | `AccountUpdate { name?, password?, is_active? }` | `AccountResponse` |
| `DELETE` | `/admin/users/{id}` | — | 204 |
| `PUT` | `/admin/users/{id}/assignments` | `AssignmentsUpdate { client_ids: [UUID] }` | 200 (replaces assignments atomically; unknown client → 400) |

### Documents (admin)

| Method | Endpoint | Request | Response |
|--------|----------|---------|----------|
| `PUT` | `/admin/documents/{id}/assignments` | `DocumentAssignments { user_ids: [UUID] }` | 200 (re-scopes document; vectors reused, no re-embedding) |

---

## 6. Conversations (`/api/conversations`)

| Method | Endpoint | Auth | Request | Response |
|--------|----------|------|---------|----------|
| `POST` | `/conversations` | CurrentUser | `ConversationCreate { title }` | `ConversationResponse` |
| `GET` | `/conversations` | CurrentUser | — | `list[ConversationResponse]` (newest first) |
| `GET` | `/conversations/{id}` | CurrentUser (+owner) | — | `ConversationResponse` |
| `PATCH` | `/conversations/{id}` | CurrentUser (+owner) | `ConversationUpdate { title }` | `ConversationResponse` |
| `DELETE` | `/conversations/{id}` | CurrentUser (+owner) | — | 204 |

**Notes:** Auto title "New Chat" until first message renames it to the question (first 60 chars). Index `(user_id, updated_at)`.

---

## 7. Messages (`/api/conversations/{id}/messages`)

| Method | Endpoint | Auth | Request | Response |
|--------|----------|------|---------|----------|
| `POST` | `/conversations/{id}/messages` | CurrentUser (+owner) | `MessageCreate { content }` | `ChatResponse { user_message, assistant_message }` |
| `GET` | `/conversations/{id}/messages` | CurrentUser (+owner) | `?cursor=..., ?limit=...` | `MessagePage { items: [MessageResponse] newest first, next_cursor }` |
| `GET` | `/conversations/{id}/messages/{mid}` | CurrentUser (+owner) | — | `MessageResponse` |
| `PATCH` | `/conversations/{id}/messages/{mid}` | CurrentUser (+owner, own user messages only) | `MessageUpdate { content }` | `MessageResponse` |
| `DELETE` | `/conversations/{id}/messages/{mid}` | CurrentUser (+owner, own user messages only) | — | 204 |

**MessageResponse:** `{ id, user_id, conversation_id, role, content, analysis_query_id?, created_at, updated_at }`.

**Notes:**
- `POST` orchestrates RAG: history → persist user msg → retrieve (scoped doc IDs, ±1 neighbor chunks) → Groq with `<context>` → answer + Sources → persist assistant msg → return both.
- Edit/delete allowed only on **own user messages** (403 otherwise).
- Cursor paging: `(created_at, id)` keyset, urlsafe-base64 cursor, `limit ≤ 100`, newest-first page `{items, next_cursor}`.

---

## 8. Documents (`/api/documents`)

| Method | Endpoint | Auth | Request | Response |
|--------|----------|------|---------|----------|
| `POST` | `/documents` | AdminUser | multipart: `file` (`.pdf/.txt/.md`, ≤20 MB) + `user_ids` (JSON string of UUIDs) | `DocumentResponse` |
| `GET` | `/documents` | CurrentUser | — | `list[DocumentResponse]` (scoped: admins see all; users see assigned) |
| `DELETE` | `/documents/{id}` | AdminUser | — | 204 (vectors removed first, then row) |

**DocumentResponse:** `{ id, user_id, client_id?, assigned_user_ids, filename, content_type, size_bytes, chunk_count, created_at }`.

**Upload flow:** validate extension/size → create Document row + assignments → synchronously ingest (Docling primary / pypdf fallback → chunk → Google embeddings → pgvector batched 32/request) → rollback chunks on failure → commit DB after vectors succeed. Document bytes are **not stored**; only extracted text/chunks live in vectors.

---

## 9. Analysis — NL → SQL (`/api/analysis`)

| Method | Endpoint | Auth | Request | Response |
|--------|----------|------|---------|----------|
| `GET` | `/analysis/clients` | CurrentUser | — | `list[ClientResponse]` (clients active for user) |
| `POST` | `/analysis/query` | CurrentUser | `AskRequest { question, client_id? }` | `AnalysisResponse` |
| `POST` | `/analysis/query/global` | CurrentUser | `{ question, client_id?, table_type_filter? }` | `AnalysisResponse` (multi-DB) |
| `POST` | `/analysis/rows` | CurrentUser | `{ token, page, page_size }` | `ResultPage` (re-verified token + assignment) |
| `POST` | `/analysis/export` | CurrentUser | `TokenRequest { token }` | `StreamingResponse` CSV (`text/csv`, `attachment; filename="export.csv"`) |
| `POST` | `/analysis/catalog/global/build` | AdminUser | — | 200 (rebuilds global catalog) |
| `POST` | `/analysis/saved` | CurrentUser | `{ token, question, title }` | saved analysis |
| `GET` | `/analysis/saved` | CurrentUser | — | `list[saved analyses]` |
| `POST` | `/analysis/saved/{id}/run` | CurrentUser | — | `AnalysisResponse` (re-run saved SQL) |
| `DELETE` | `/analysis/saved/{id}` | CurrentUser | — | 204 |
| `GET` | `/analysis/history` | CurrentUser | `?client_id` | `list[UserHistoryResponse]` (excludes SQL) |
| `GET` | `/analysis/admin/history` | AdminUser | `?client_id` | `list[HistoryResponse]` (includes SQL) |
| `POST` | `/analysis/history/{id}/run` | CurrentUser | `?page, ?page_size` | `AnalysisResponse` (re-run stored SQL) |
| `DELETE` | `/analysis/history/{id}` | CurrentUser | — | 204 |

**AskRequest:** `{ question: str (1–2000), client_id?: UUID }`.

**AnalysisResponse:**
```
{
  title: string,
  database: string,
  tables: string[],
  sql: string,
  analysis_query_id: UUID | null,
  token: string,              // signed JWT (120 min): {type, sub, db, client_id, sql, exp}
  result: ResultPage {
    columns: string[],
    rows: any[][],
    page: int,
    page_size: int,
    has_more: bool,
    total_time_ms?: float
  }
}
```

**TokenRequest:** `{ token: string }`.

**ClientResponse:** `{ id, code, name, client_identifier, database_name, description?, is_active }`.

**HistoryResponse:** `{ id, question, title?, database, sql, client_id?, row_count?, created_at }`.  
**UserHistoryResponse:** same minus `sql` (regular users).

### Security & scoping
- `assigned_database(user, client_id)`: admin may use any client; users must be assigned via `user_clients`. None assigned → 403; several supplied without `client_id` → 400 "select a client".
- SQL generation uses a 23 KB system prompt (`backend/prompts/main_prompt.py`) encoding the business schema + safety rules. `{{client_id}}` substituted with the client's `client_identifier`.
- `sqlglot` guard (`validate_select`): exactly 1 statement; SELECT/WITH only; forbids Insert/Update/Delete/Drop/Create/Alter/Merge/Command/Into/TruncateTable; blocks `pg_*`/`lo_*`/`dblink*`/`pg_sleep`/`current_setting`/`current_database`/`version`; every query must touch a real table; schema-qualification allowed only for `pollmatrix.*`; bare names must be CTEs / in allowed top-k / known real tables / rewritten logical→physical.
- Execution: `SET TRANSACTION READ ONLY` + `SET LOCAL statement_timeout` (15 s query / 300 s export). MSSQL lacks read-only txn (PostgreSQL recommended).
- Result tokens signed with `SECRET_KEY` (HS256). Pagination/export re-verify: token type, `sub == user`, and assignment still matches (`open_result` / `_check_multi_access`). Assignment change → 403.
- Every run logged to `analysis_queries` (status, row_count, timings, query_hash, explain_plan JSONB).

---

## 10. Intelligence — Hybrid QA (`/intelligence`)

| Method | Endpoint | Auth | Request | Response |
|--------|----------|------|---------|----------|
| `POST` | `/intelligence/ask` | CurrentUser | `IntelligenceRequest { question, client_id?, conversation_id? }` | `IntelligenceResponse` |

**IntelligenceRequest:** `{ question: str (1–2000), client_id?: UUID, conversation_id?: UUID }`.

**IntelligenceResponse:**
```
{
  intent: "database" | "document" | "hybrid" | "general",
  answer: string,
  database: DatabaseResult | null,
  document: DocumentResult | null,
  chart: ChartConfig | null,
  sources: DocumentSource[],
  conversation_id: UUID | null,
  user_message_id: UUID | null,
  assistant_message_id: UUID | null,
  created_at: string
}
```

**DatabaseResult:** `{ title?, database?, tables[], sql?, analysis_query_id?, token, columns[], rows[][], row_count?, total_time_ms?, page, page_size, has_more }`.

**DocumentResult:** `{ answer?, sources: DocumentSource[] }`.

**DocumentSource:** `{ filename, page?, score? }`.

**ChartConfig:** `{ type: "bar"\|"line"\|"pie"\|"table"\|"none", x_axis?: {field,label?}, y_axis?: {field,label?}, label_field?, value_field?, limit? }`.

### Routing logic
1. Fast-path regex: voter-record terms + record-request terms → `database`.
2. Else Groq intent classification (JSON `{"intent","reasoning","entities"}`).
3. `database` → AnalysisService `ask` (SQL path); `document` → RAG retrieve + answer; `hybrid` → both + `HYBRID_SYNTHESIS_SYSTEM` merge; `general` → Groq general-answer prompt.
4. Optional chart suggestion from DB result columns/rows (`CHART_SUGGESTION_SYSTEM`, fallback heuristic).
5. Persists user + assistant messages (+ optional `ChatAnalysisQuery` link) to conversations/messages.

---

## 11. Error Codes Summary

| Code | Meaning |
|------|---------|
| 400 | Bad request (e.g. unknown client in assignments, invalid user_ids JSON, result expired) |
| 401 | Not authenticated / invalid credentials / account disabled / invalid token |
| 403 | Forbidden (admin required, not assigned to client, assignment changed) |
| 404 | Not found (analysis query, conversation, message, document) |
| 422 | Unprocessable (out-of-scope SQL, unsafe stored query, execution error) |
| 502 | Bad gateway (LLM/retrieval infra failure, DB unavailable) |
| 503 | Service unavailable (no tables for database) |

---

## 12. Frontend Service Mapping (`frontend/services/`)

| Service file | Covers |
|--------------|--------|
| `auth.ts` | login/logout via axios |
| `session.server.ts` | server-only `getSession()` (cookie → `GET /users/me`) |
| `conversations.ts` | conversation CRUD |
| `messages.ts` | `getAllConversationMessages` → `MessagePage` cursor paging |
| `documents.ts` | admin `uploadDocument` (FormData: `file` + `JSON.stringify(user_ids)`) |
| `admin.ts` | clients/users CRUD, assignments |
| `analysis.ts` | raw `fetch` (own 401→refresh→retry), `credentials: "include"`; `askAnalysis`, `askGlobalAnalysis`, `fetchRows`, `exportCsv` (Blob), `saveAnalysis`, `listSaved`, `runSaved`, `listHistory`, `runHistory`, deletes |
| `intelligence.ts` | `askIntelligence` → `POST /intelligence/ask` |
| `http.ts` | `send` helper used by intelligence service |
| `error.ts` | `getApiErrorMessage` handles FastAPI `detail` string/array |

**Axios client (`lib/axios.ts`):** `withCredentials`, response interceptor treats 401 (except `auth/*` / already-retried) as lapsed access token → single-flight `refreshPromise` refresh → replay original request; failure → `window.location.replace('/login?reason=expired')`.

---

## 13. OpenAPI

FastAPI auto-generates OpenAPI at:
- `GET /api/openapi.json`
- Interactive UI: `GET /api/docs` (Swagger) and `GET /api/redoc` (when not disabled in production)
