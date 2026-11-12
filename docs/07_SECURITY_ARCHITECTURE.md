# Chanakya AI — Security Architecture

> **Document:** `docs/07_SECURITY_ARCHITECTURE.md`  
> **Scope:** Authentication, authorization, session/cookie handling, client data scoping, SQL sandboxing, and threat mitigations.  
> **Diagram:** `Architecture/Security Architecture.png`.  
> **Source:** `backend/core/` (`config.py`, `security.py`, `cookies.py`), `backend/api/dependencies.py`, `backend/modules/auth/`, `backend/modules/analysis/` (`guard.py`, `service.py`).

---

## 1. Authentication (AuthN)

### 1.1 Credentials & Passwords
- No public self-registration endpoint. The first (and subsequent) company admin is created **server-side** via `uv run python -m scripts.create_admin <email>`. Admins can also create accounts via `POST /api/admin/users`.
- Passwords hashed with **pwdlib `PasswordHash.recommended()`** (Argon2 when available).
- Login (`POST /api/auth/login`) verifies email + `is_active` + password.

### 1.2 JWTs
- Library: PyJWT, algorithm **HS256**, signed with `SECRET_KEY` (≥ 32 chars enforced by pydantic).
- **Access token:** TTL `ACCESS_TOKEN_EXPIRE_MINUTES` (15 min). Claims: `iat`, `exp`, `type="access"`, `sub` (user UUID).
- **Refresh token:** TTL `REFRESH_TOKEN_EXPIRE_DAYS` (30 days). Claims: `iat`, `exp`, `type="refresh"`, `sub`, random `jti`.
- Verification strictly checks `type` and that `sub` is a valid UUID.

### 1.3 Cookie Transport
- `core/cookies.py` sets **httpOnly** cookies `access_token` / `refresh_token` (`path=/`, `SameSite=lax` default, `Secure` toggled via `COOKIE_SECURE`).
- Frontend **never reads** these cookies (httpOnly). Every auth transition is browser-automatic (cookies sent with each request).
- Login sets the pair; refresh rotates them; logout clears them.

### 1.4 Refresh-Token Rotation + Server-Side Store
- `RefreshToken` table stores only the **SHA-256 hash** of the token (unique, indexed), plus `expires_at` and `revoked_at`.
- On `/auth/refresh`: the used refresh token is **revoked and replaced** (rotation). Expired rows are pruned on login.
- Revoked or unknown hash → 401 + cookies cleared.
- Deactivated accounts are rejected immediately by `get_current_user` even with a valid cookie (deactivation takes effect immediately).

### 1.5 Request Authentication
`api/dependencies.py::get_current_user` reads the `access_token` cookie, verifies the JWT, loads the `User`, and rejects deactivated accounts even with a valid cookie. `require_admin` gates admin endpoints (403).

---

## 2. Authorization (AuthZ)

| Resource | Scope mechanism | Enforced at |
|----------|----------------|-------------|
| Conversations / messages | per-user ownership (`user_id`) | repository + router |
| Documents | `document_assignments` (user_ids) | `DocumentService.get_documents` |
| Analysis (SQL) | `user_clients` (assigned clients) | `AnalysisService.assigned_database` |
| History / saved analyses | per-user (`user_id`) | repository |
| Admin routes | `role == "admin"` | `require_admin` dependency |

**Client scoping rules:**
- `assigned_database(user, client_id)`: admin may use any client; users must be assigned via `user_clients`. None assigned → 403; several supplied without `client_id` → 400.
- Result tokens re-verify assignment on pagination/export/history/save re-runs — assignment change → 403 (`open_result` / `_check_multi_access`).
- Document visibility: `get_all` scoped — admins see all; users see only assigned documents.

---

## 3. SQL Sandboxing (Analysis Path)

The NL→SQL path is protected by defense-in-depth:

1. **Prompt-level rules:** read-only SELECT only; no secrets (`client_key`, `password`); no LIMIT unless asked; inline literal params; queries must touch real tables; `{{client_id}}` tenant filter injected.
2. **sqlglot guard (`validate_select`):**
   - Exactly 1 statement; must be `exp.Query` (SELECT/WITH).
   - Forbids Insert/Update/Delete/Drop/Create/Alter/Merge/Command/Into/TruncateTable.
   - Blocks dangerous functions: `pg_*`, `lo_*`, `dblink*`, `pg_sleep`, `current_setting`, `current_database`, `version`.
   - Every query must touch a real table.
   - Schema-qualification allowed only for `pollmatrix.*` (FDW schema); all other cross-schema/cross-db rejected.
   - Bare names must be CTEs / allowed top-k / known real tables / rewritten logical→physical.
3. **Execution-level:** `SET TRANSACTION READ ONLY` + `SET LOCAL statement_timeout` (15 s query / 300 s export). MSSQL lacks read-only txn (PostgreSQL recommended).
4. **Result tokens:** signed JWT (not encrypted) containing `type, sub, db, client_id, sql, exp`; re-verified on rows/export.

> The guard is defense-in-depth only — the analysis DB role itself must be read-only and restricted at the database level.

---

## 4. Network & Transport

- **CORS:** allow-list (`FRONTEND_ORIGIN` + `CORS_ORIGINS` + localhost:3000) plus a **LAN-origin regex** (10.x / 192.168.x / 172.16–31.x) so local-network clients pass preflight.
- **Cookies:** `Secure` in production (`COOKIE_SECURE=true`), `SameSite=lax`; httpOnly prevents JS access (mitigates XSS token theft).
- **CSRF mitigated** by SameSite=lax + cookie-only transport (no bearer tokens readable by JS).

---

## 5. Upload & File Security

- Extension whitelist: `.pdf`, `.txt`, `.md` only.
- Max upload size: `MAX_UPLOAD_MB` (default 20).
- Password-protected PDFs → error; scanned/image-only PDFs → empty note (OCR not implemented).
- Document bytes are **never stored** — only extracted text + embeddings in pgvector.

---

## 6. Threat Model & Mitigations

| Threat | Mitigation |
|--------|------------|
| Stolen refresh token | Server-side hash store + rotation; revoked/unknown → 401 |
| Session hijack via XSS | httpOnly cookies (JS cannot read) |
| CSRF | SameSite=lax + cookie-only transport |
| Privilege escalation | `require_admin` on admin routes; per-user ownership checks |
| Data leakage across tenants | Client scoping (`user_clients`, `document_assignments`); `client_id` filter in SQL; `pollmatrix` FDW isolation |
| SQL injection / destructive SQL | sqlglot guard + read-only txn + statement timeouts |
| LLM hallucination in SQL | Guard whitelists tables; result tokens re-verify assignment |
| Immediate lockout on deactivation | `get_current_user` checks `is_active` per request |
