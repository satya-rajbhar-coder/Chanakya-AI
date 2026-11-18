# Chanakya AI — System Architecture Guide (Interview Edition)

This document is designed to help you explain the Chanakya AI architecture confidently during an interview. It covers the high-level design, component responsibilities, data flows, and key technical decisions — with a suggested narrative you can use when walking an interviewer through the system.

---

## 1. Elevator Pitch (30 seconds)

> "Chanakya AI is a political campaign intelligence assistant. Campaign workers can ask natural-language questions about voter data, uploaded campaign documents, or general political strategy, and the system routes each question to the right source — a SQL database, a RAG pipeline over uploaded PDFs, or an LLM's general knowledge — then returns a grounded, multilingual answer with citations and optional charts."

---

## 2. High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         CLIENT LAYER                                │
│  Next.js 16 (App Router) + React 19 + TypeScript + Tailwind CSS    │
│  • Chat UI with optimistic updates                                   │
│  • Retry-on-failure for failed API calls                             │
│  • Recharts for data visualization                                   │
│  • React-Markdown for rendered answers                               │
└────────────────────┬────────────────────────────────────────────────┘
                     │ HTTPS / JSON
                     ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         API LAYER                                   │
│                    FastAPI (Python 3.14)                            │
│  • REST endpoints under /api                                         │
│  • JWT authentication + refresh tokens                               │
│  • Role-based access control (RBAC)                                  │
│  • CORS, health checks                                               │
└────────────────────┬────────────────────────────────────────────────┘
                     │
       ┌─────────────┼─────────────┐
       ▼             ▼             ▼
┌──────────┐  ┌────────────┐  ┌──────────────┐
│ Auth     │  │ Intelligence│  │ Analysis     │
│ Service  │  │ (AI Agent)  │  │ (SQL Engine) │
└──────────┘  └──────┬─────┘  └──────┬───────┘
                     │               │
                     ▼               ▼
              ┌─────────────┐  ┌──────────────┐
              │   LLM       │  │   SQL        │
              │   Clients   │  │   Executor   │
              │ (Groq/Ollama)│  │   (PostgreSQL)│
              └──────┬──────┘  └──────┬───────┘
                     │               │
                     ▼               ▼
              ┌─────────────┐  ┌──────────────┐
              │   RAG       │  │   Analysis   │
              │   Pipeline  │  │   Service    │
              │ (PGVector + │  │   (Voter     │
              │  Full-Text) │  │   data,      │
              └──────┬──────┘  │   workers,   │
                     │         │   activities)│
                     ▼         └──────────────┘
              ┌─────────────┐
              │   Vector    │
              │   Store     │
              │ (PGVector)  │
              └─────────────┘
```

---

## 3. Component Responsibilities

| Component | Responsibility |
|-----------|---------------|
| **Next.js Frontend** | Chat UI, conversation state, optimistic updates, error handling with retry, chart rendering, language detection display |
| **FastAPI Router** | Request routing, authentication middleware, CORS, health checks |
| **Auth Service** | JWT issuance, refresh token rotation, password hashing, role-based scope (karyakarta → admin) |
| **Intelligence Service** (`ai_agent/intelligence/service.py`) | Core orchestration: intent classification, source routing, answer synthesis, fallback logic, conversation persistence |
| **LLM Client** (`ai_agent/llm/`) | Groq (ChatGroq) and Ollama (qwen3.5) clients for generation and embeddings |
| **RAG Pipeline** (`ai_agent/rag/`) | Document ingestion (Docling → chunking → embedding), hybrid retrieval (vector + keyword + RRF), neighbor-window expansion |
| **Analysis Service** (`modules/analysis/`) | SQL generation, query execution, result pagination, chart suggestion |
| **PostgreSQL + PGVector** | Relational data (voters, workers, activities, contacts) + vector embeddings for document chunks |

---

## 4. The Hybrid Q&A Routing Logic (Core Innovation)

This is the part interviewers usually ask about most. Here's how a question flows through the system:

### Step 1: Intent Classification
The user's question is classified into one of four intents:

| Intent | Trigger | Source |
|--------|---------|--------|
| `database` | Voter counts, lists, booth analysis, worker status, color-code breakdowns | SQL database |
| `document` | Facts from uploaded reports, ward situations, party composition in documents | RAG over documents |
| `hybrid` | Needs both data counts AND document context | Database + Documents |
| `general` | Political knowledge, campaign strategy, greetings | LLM general knowledge |

**Fast-path rule:** If a question contains voter terms (`ward`, `booth`, `voters`) AND data-request terms (`count`, `list`, `show`), it's routed directly to `database` without calling the LLM classifier — saving latency and cost.

### Step 2: Source Execution
- **Database path:** The Analysis Service converts the question to SQL, executes it against PostgreSQL with role-based row-level security (users only see their assigned wards/assemblies), and returns rows.
- **Document path:** The RAG pipeline retrieves relevant chunks from PGVector using hybrid search (vector similarity + full-text keyword search fused with Reciprocal Rank Fusion), then generates an answer grounded only in those excerpts.
- **General path:** The LLM answers from its trained knowledge, with guardrails against politician-specific facts and non-political queries.

### Step 3: Answer Synthesis & Fallback
- If a source returns relevant data, that answer is used.
- If a source returns nothing (e.g., no matching voter records), the system does **not** hallucinate — it returns an honest "no matching records" message.
- If all sources are empty and the question is general, the LLM provides neutral political context, clearly distinguished from local facts.
- Person-specific questions (MLA, MP, minister, etc.) are refused unless backed by the user's own documents or database records.

---

## 5. RAG Pipeline (Document Intelligence)

```
Upload → Parse → Chunk → Embed → Store → Retrieve → Rerank → Generate → Cite
```

1. **Ingestion:** User uploads PDF/TXT/MD → Docling extracts text → RecursiveCharacterTextSplitter creates chunks → Google/Ollama embeddings → stored in PGVector with metadata (filename, page, chunk_index, document_id, user_id).
2. **Retrieval:** User query → hybrid search:
   - **Vector pass:** PGVector similarity search (cosine distance)
   - **Keyword pass:** PostgreSQL full-text search (`to_tsvector` + `plainto_tsquery`)
   - **Fusion:** Reciprocal Rank Fusion (RRF) combines both rankings
   - **Expansion:** Neighbor-window chunks (adjacent chunks) are added for context
3. **Generation:** Retrieved chunks are formatted without internal metadata (no chunk numbers, no ranking) and passed to the LLM with a strict "answer only from excerpts" system prompt.
4. **Citations:** Sources (filename + page numbers) are appended separately by the application, not by the LLM.

---

## 6. Database Analytics Flow

```
Question → SQL Generation → Role-Based Filter → Execution → Result → Synthesis → Chart Suggestion
```

1. **SQL Generation:** The Analysis Service uses an LLM (with the main system prompt containing schema context) to convert natural language to parameterized SQL.
2. **Role-Based Filtering:** SQL is automatically augmented with `WHERE` clauses based on the user's role:
   - `karyakarta`: `ward_no = 'Ward 3'`
   - `corporator`: `ward_no = 'Ward 7'`
   - `aamdar`: `assembly_name_eng = 'Assembly 12'`
   - `khasdar`: `parliamentary_constituency = 'PC 5'`
   - `admin`: no filter (sees all)
3. **Execution:** Query runs against PostgreSQL with pagination (page, page_size, has_more).
4. **Synthesis:** A second LLM pass summarizes the rows into a professional analysis (3–6 sentences, no raw SQL in output).
5. **Chart Suggestion:** A third LLM pass suggests the best chart type (bar, line, pie, table) and field mapping for the frontend to render.

---

## 7. Authentication & Authorization

- **Auth:** JWT access tokens + refresh tokens (stored in HTTP-only cookies).
- **Roles:** `karyakarta` < `corporator` < `aamdar` < `khasdar` < `admin` (hierarchy enforced numerically).
- **Data Scoping:** Every database query is filtered by the user's assigned ward/assembly/constituency at the SQL level — not just the UI.
- **Document Access:** Users only see documents assigned to them or their client.

---

## 8. Frontend Architecture

```
Next.js App Router
├── app/(protected)/dashboard/page.tsx   → Hybrid intelligence chat
├── app/(protected)/layout.tsx            → Auth wrapper, sidebar
├── components/chat/
│   ├── DocumentsChat.tsx                 → Document + hybrid chat
│   ├── AnalysisChat.tsx                  → Database-only chat
│   └── ChatInput.tsx                     → Message input
├── components/ui/                        → shadcn/ui components
├── services/
│   ├── http.ts                           → Fetch wrapper with 401 retry + error parsing
│   ├── intelligence.ts                   → API client for /intelligence/ask
│   ├── analysis.ts                       → API client for /analysis/*
│   └── error.ts                          → getApiErrorMessage helper
└── hooks/
    └── use-mobile.ts                     → Responsive layout hook
```

**Key UX decisions:**
- **Optimistic updates:** User message appears immediately; assistant message replaces loading state.
- **Error handling:** Failed requests show an inline error card with a "Try again" button that re-sends the same question — no data loss.
- **Status-specific messages:** Network errors, 401 (session expired), 403 (permission), 404 (not found), 429 (rate limit), 500+ (server error) each get tailored copy instead of generic "Something went wrong."
- **Multilingual:** The backend detects and replies in Hindi, English, Marathi, Hinglish, or English-Marathi; the frontend displays the response as-is.

---

## 9. API Design

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/intelligence/ask` | POST | Hybrid Q&A — main chat endpoint |
| `/api/analysis/query` | POST | Direct SQL analytics |
| `/api/analysis/history` | GET | Saved query history |
| `/api/documents/upload` | POST | Document upload & indexing |
| `/api/auth/login` | POST | Authentication |
| `/api/auth/refresh` | POST | Token refresh |
| `/api/users/me` | GET/PUT | Current user profile |

---

## 10. Safety & Guardrails

| Guardrail | Implementation |
|-----------|---------------|
| Politician refusal | Regex detects MLA/MP/minister/corporator/etc.; refused from all sources unless backed by user documents |
| Anti-hallucination | Database answers use only returned rows; general answers never invent voter counts or local results |
| Empty result honesty | Empty DB queries return "no matching records" instead of falling back to fabricated general knowledge |
| Code refusal | Non-political/technical queries are declined with a polite message |
| Language safety | All prompts instruct the LLM to reply in the user's detected language |

---

## 11. Suggested Interview Narrative

Here's a script you can adapt when explaining the system:

> "The system is built around a hybrid routing engine. When a user asks a question, we first classify the intent — is this a database question, a document question, a general knowledge question, or a hybrid that needs both? We have a fast-path for common voter queries so we don't waste an LLM call on simple count requests.
>
> For database questions, we generate SQL with role-based row-level security so a karyakarta only sees their own ward's data. For document questions, we use a RAG pipeline with hybrid retrieval — vector similarity plus full-text search fused with Reciprocal Rank Fusion — so we get better recall than pure semantic search. The LLM is strictly grounded in retrieved excerpts and never sees internal chunk metadata.
>
> If no source has the answer, we don't hallucinate. We return an honest message, or for general questions, we provide neutral political context clearly labeled as general knowledge.
>
> On the frontend, we use Next.js with optimistic updates and retry-on-failure so users never lose their question if a request fails. Everything supports Hindi, English, Marathi, Hinglish, and English-Marathi."

---

## 12. Key Technical Decisions (Trade-offs)

| Decision | Rationale |
|----------|-----------|
| **Hybrid retrieval (vector + keyword + RRF)** | Pure vector search misses exact keyword matches (e.g., specific ward numbers); keyword search misses semantic meaning. RRF gives the best of both. |
| **Role-based filtering at SQL level** | Security by database, not just UI — prevents data leakage even if frontend is bypassed. |
| **Microsecond timestamp ordering** | Prevents assistant messages from appearing before user messages in chat history when both share the same `now()` timestamp. |
| **uv package manager** | Faster installs and deterministic resolution vs. pip/poetry. |
| **Separate synthesis LLM pass** | Keeps the SQL generator focused on query correctness and the answer generator focused on natural language quality. |

---

## 13. Folder Structure (AI/Agent Code)

All AI-related code lives under [`backend/ai_agent/`](D:/Satya/chanakya-ai/chanakya-ai/backend/ai_agent):

```
backend/ai_agent/
├── intelligence/
│   ├── service.py          # Hybrid orchestration & routing
│   ├── router.py           # FastAPI routes
│   ├── prompts.py          # System prompts (intent, DB, doc, hybrid, general, chart)
│   ├── repository.py       # Conversation & message persistence
│   ├── schemas.py          # Pydantic models (IntelligenceRequest/Response)
│   ├── models.py           # ChatAnalysisQuery SQLAlchemy model
│   ├── orchestrator.py     # Backward-compat wrapper
│   └── __init__.py
├── llm/
│   ├── client.py           # Groq + Ollama LLM clients
│   ├── service.py          # RAG reply generation, NOT_FOUND detection
│   └── __init__.py
├── rag/
│   ├── service.py          # Ingestion, hybrid retrieval, RRF, formatting
│   ├── vector_store.py     # PGVector store singleton
│   ├── embeddings.py       # Google + Ollama embeddings
│   ├── loader.py           # Docling PDF/TXT/MD loader
│   └── __init__.py
└── prompts/
    ├── main_prompt.py      # SQL generation system prompt
    └── prompts.py          # Additional prompt templates
```

---

## 14. Quick Facts for Interviewers

- **Language:** Python 3.14 (backend), TypeScript (frontend)
- **Package Manager:** uv
- **Database:** PostgreSQL + PGVector
- **LLM:** Groq (primary), Ollama (local fallback)
- **Embeddings:** Google Generative AI + Ollama
- **Document Processing:** Docling, LangChain
- **Frontend:** Next.js 16, React 19, Tailwind CSS, shadcn/ui, Recharts
- **Tests:** pytest (43+ tests passing for intelligence, retrieval, and API layers)

---

Save this file and bring it (or a printed summary) to your interview. When asked "explain your architecture," start with the elevator pitch, then walk through the hybrid routing logic — that's the most distinctive part of the system.
