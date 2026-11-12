# Chanakya AI — Testing & Quality

> **Document:** `docs/10_TESTING_AND_QUALITY.md`  
> **Scope:** Test strategy, linting, type-checking, CI notes, and known limitations.  
> **Source:** `backend/tests/`, `backend/pyproject.toml`, `backend/pytest.ini`, `frontend/eslint.config.mjs`, `frontend/tsconfig.json`.

---

## 1. Backend Testing

### 1.1 Framework & setup
- **Runner:** pytest
- **HTTP client for tests:** httpx
- **Command:** `uv run --with pytest --with httpx python -m pytest -q`
- **Config:** `backend/pytest.ini`; cache in `.pytest_cache`; coverage artifacts excluded from repo.

### 1.2 Test files
| File | Covers |
|------|--------|
| `conftest.py` | Shared fixtures (app client, DB session, etc.) |
| `test_api.py` | API-level endpoint tests |
| `test_guard.py` | sqlglot SQL validation (unsafe SQL rejection) |
| `test_scope.py` | Multi-tenant scoping (client/document/user isolation) |
| `test_executor.py` | SQL execution path |

### 1.3 What's tested (inferred from names)
- `test_api` — end-to-end HTTP behavior of routers (auth, users, admin, conversations, messages, documents, analysis, intelligence).
- `test_guard` — that `validate_select` rejects DML/DDL, dangerous functions, cross-schema access, table-less queries, and multiple statements.
- `test_scope` — that users cannot access data belonging to other clients/documents they aren't assigned to.
- `test_executor` — that read-only execution, pagination, and timeouts behave correctly.

---

## 2. Linting & Formatting

- **Tool:** ruff
- **Config:** `backend/pyproject.toml` (ruff section)
- **Conventions:** line length 88, target Python 3.11 (`.python-version`)
- **Command:** `uv run ruff check backend` (and `uv run ruff format` if desired)
- Cache in `.ruff_cache` (excluded from repo).

---

## 3. Dependency Management

- Package manager: **uv** (`uv sync`, `uv run uvicorn main:app`).
- Lockfile: `backend/uv.lock`.
- Python version file: `backend/.python-version`.
- Requirements: `requirements.txt`, `requirements-analysis.txt`.

---

## 4. Frontend Quality

- **Lint:** ESLint (`frontend/eslint.config.mjs`)
- **Type-check:** TypeScript (`frontend/tsconfig.json`, `next-env.d.ts`)
- **Format:** implied by project tooling (Prettier via eslint config where present)
- **Cache:** `.next`, `tsconfig.tsbuildinfo` excluded from repo.

> This is Next.js 16 — see `frontend/AGENTS.md` (`node_modules/next/dist/docs/`) before modifying, as APIs/conventions may differ from older Next.js.

---

## 5. CI / Quality Notes (to be formalized)

There is no committed CI configuration file in the repository at time of writing. A reasonable CI pipeline would run, on each PR:

1. Backend: `uv sync` → `uv run ruff check` → `uv run --with pytest --with httpx python -m pytest -q`.
2. Frontend: `npm ci` → `npm run lint` (eslint) → `npx tsc --noEmit` → `npm run build` (production build catches type/next errors).
3. Verify `.env` is never committed (secret scanning / gitignore enforcement).

---

## 6. Test Gaps & Recommendations

| Area | Status | Recommendation |
|------|--------|----------------|
| API endpoints | partial (`test_api.py`) | Add coverage for all 42+ routes incl. auth cookie flows |
| SQL guard | covered (`test_guard.py`) | Keep; add cases for MSSQL dialect and FDW schema edge cases |
| Tenant scoping | covered (`test_scope.py`) | Extend to analysis token re-verification on assignment change |
| Executor | covered (`test_executor.py`) | Add read-only txn + statement_timeout verification |
| RAG pipeline | not covered | Add unit tests for chunking, neighbor expansion, `format_context` |
| Intelligence module | not covered | Add intent-classification + routing unit tests (mock Groq) |
| Frontend | not covered | Add component/RTL tests for chat, admin, ResultTable |
| E2E / Playwright | not covered | Add critical-path E2E: login → ask → paginate → export → logout |

---

## 7. Known Limitations (from code/README)

- No committed CI config; no coverage thresholds enforced.
- MSSQL execution is partial — PostgreSQL recommended for full guarantees.
- Document upload + embedding inside the HTTP request — proxy timeout must accommodate embedding latency.
- Analysis tokens are signed (not encrypted) — users can decode their own SQL.
- No streaming/typing effect in chat (single request/response per turn).
