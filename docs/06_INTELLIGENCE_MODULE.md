# Chanakya AI — Intelligence Module (Hybrid QA)

> **Document:** `docs/06_INTELLIGENCE_MODULE.md`  
> **Scope:** Intent classification, database/document/hybrid/general routing, answer synthesis, chart suggestion, and chat persistence.  
> **Source:** `backend/modules/intelligence/` (`service.py`, `prompts.py`, `repository.py`, `router.py`, `schemas.py`, `models.py`, `orchestrator.py`).  
> **Diagrams:** `Architecture/Full Hybrid Agent Activity Diagram.png`, `Architecture/Hybrid Document + Database Query.png`, `Architecture/Query Router.png`, `Architecture/Hybrid Search Architecture.png`.

---

## 1. Overview

Intelligence is a **hybrid question-answering layer** that classifies each question by intent and routes it to the appropriate data source(s):

| Intent | Source | Typical questions |
|--------|--------|-------------------|
| `database` | Analysis (NL → SQL) | voter lists/details/counts, rankings, weak/strong booths, active/inactive workers, top issues |
| `document` | RAG (documents) | political situation/scenario/context from campaign documents/reports |
| `hybrid` | Both + synthesis | needs hard data counts AND document context in one answer |
| `general` | General knowledge (LLM only) | advisory/opinion questions not tied to data |

`POST /intelligence/ask` returns a unified `IntelligenceResponse` with the intent, answer, optional database result, optional document result, optional chart config, sources, and persisted conversation/message IDs.

---

## 2. Components

| File | Responsibility |
|------|----------------|
| `router.py` | `POST /intelligence/ask`; wraps service, maps exceptions to 502 |
| `schemas.py` | `IntelligenceRequest`, `IntelligenceResponse`, `DatabaseResult`, `DocumentResult`, `ChartConfig`, `DocumentSource` |
| `service.py` | `IntelligenceService.ask()` — classify → route → synthesize → chart → persist |
| `prompts.py` | System prompts: intent classification, database answer, document answer, hybrid synthesis, general answer, chart suggestion |
| `repository.py` | Conversation get-or-create + chat-turn persistence (user + assistant messages, `ChatAnalysisQuery` link) |
| `models.py` | `ChatAnalysisQuery` ORM (links assistant message → `analysis_queries`) |
| `orchestrator.py` | Backward-compat re-export of `IntelligenceService` |

---

## 3. Request / Response

**Request** — `IntelligenceRequest`:
```json
{
  "question": "string (1-2000 chars)",
  "client_id": "UUID | null",
  "conversation_id": "UUID | null"
}
```

**Response** — `IntelligenceResponse`:
```json
{
  "intent": "database | document | hybrid | general",
  "answer": "string",
  "database": "DatabaseResult | null",
  "document": "DocumentResult | null",
  "chart": "ChartConfig | null",
  "sources": "DocumentSource[]",
  "conversation_id": "UUID | null",
  "user_message_id": "UUID | null",
  "assistant_message_id": "UUID | null",
  "created_at": "ISO-8601"
}
```

`DatabaseResult` mirrors `AnalysisResponse` (title, database, tables, sql, analysis_query_id, token, columns, rows, row_count, total_time_ms, page, page_size, has_more).

`DocumentResult` = `{ answer?, sources: DocumentSource[] }`; `DocumentSource` = `{ filename, page?, score? }`.

`ChartConfig` = `{ type: "bar"|"line"|"pie"|"table"|"none", x_axis?: {field,label?}, y_axis?: {field,label?}, label_field?, value_field?, limit? }`.

---

## 4. Routing Logic (`service.py`)

### 4.1 Conversation resolution
Resolves an existing conversation (owned by the user) or creates a new one titled `question[:60]`, so every intelligence turn is persisted like a document conversation.

### 4.2 Intent classification (`_classify`)
1. **Fast-path regex:** if the question contains voter-record terms (`voters?|electors?`) AND a record-request term (`list|show|display|count|number|details?|records?|data|how many`) → intent = `database`.
2. Else calls Groq with `INTENT_CLASSIFICATION_SYSTEM`, which returns JSON `{"intent","reasoning","entities"}`. On parse failure → `general`.
3. Valid intent values: `database`, `document`, `hybrid`, `general`; anything else → `general`.

### 4.3 Route execution
- `database` → `AnalysisService.ask(AskRequest)` → `DatabaseResult`; if `sql` present, synthesize a database answer via `DATABASE_ANSWER_SYSTEM`.
- `document` → RAG retrieve + `generate_reply` → `DocumentResult` (answer + sources).
- `hybrid` → run both database and document paths, then `HYBRID_SYNTHESIS_SYSTEM` merges into one answer.
- `general` → `GENERAL_ANSWER_SYSTEM` (campaign-strategist persona).

### 4.4 Chart suggestion (`_suggest_chart`)
If a database result has columns + rows (≤200 rows), asks Groq `CHART_SUGGESTION_SYSTEM` for `{type, x_axis, y_axis, label_field, value_field, limit}`. On failure, fallback heuristic: ≥2 columns → bar chart on first two columns; else `table`. Returns `None` if no result/columns/rows or >200 rows.

### 4.5 Persistence
Persists user + assistant messages to `conversations`/`messages`; if a database result exists, links the assistant message to the `analysis_queries` row via `ChatAnalysisQuery`. Returns both message IDs.

---

## 5. System Prompts (`prompts.py`)

- **`INTENT_CLASSIFICATION_SYSTEM`** — router for Chanakya AI (political campaign intelligence). Classifies into database/document/hybrid/general with reasoning + entities (ward, assembly, candidate, mla, worker).
- **`DATABASE_ANSWER_SYSTEM`** — writes concise analysis of DB results; highlights key findings first; no raw SQL.
- **`DOCUMENT_ANSWER_SYSTEM`** — answers using ONLY document excerpts; cites sources by filename.
- **`HYBRID_SYNTHESIS_SYSTEM`** — merges database analysis + document context into one coherent answer (data first, then context).
- **`GENERAL_ANSWER_SYSTEM`** — campaign-strategist persona; actionable, time-bound recommendations.
- **`CHART_SUGGESTION_SYSTEM`** — suggests chart type + field mapping from columns/sample rows.

---

## 6. End-to-End Activity (Reference: `Full Hybrid Agent Activity Diagram.png`)

```
question → POST /intelligence/ask
    │
    ├─ resolve/create conversation (owned by user)
    │
    ├─ intent classification (regex fast-path → else Groq JSON)
    │
    ├─ intent == database or hybrid → AnalysisService.ask (NL→SQL path)
    │     └─ optional DATABASE_ANSWER_SYSTEM synthesis
    │
    ├─ intent == document or hybrid → RAG retrieve + answer
    │
    ├─ intent == hybrid → HYBRID_SYNTHESIS_SYSTEM merge
    │
    ├─ chart suggestion from DB result (optional)
    │
    ├─ persist user + assistant messages (+ ChatAnalysisQuery link)
    │
    └─ return IntelligenceResponse {intent, answer, database?, document?, chart?, sources, ...}
```
