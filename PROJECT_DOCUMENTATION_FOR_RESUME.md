# Chanakya AI — Political Campaign Intelligence Platform

## Project Overview
**Chanakya AI** is a full-stack political campaign intelligence assistant that helps political workers and campaign managers query voter data, analyze uploaded campaign documents, and generate ward-level campaign strategies — all through a natural-language chat interface. The platform combines structured database analytics, Retrieval-Augmented Generation (RAG) over uploaded documents, and multilingual general political knowledge in a single hybrid Q&A system.

**Role:** Full-Stack Developer (Backend + Frontend)  
**Tech Stack:** FastAPI, Python, Next.js 16, React 19, TypeScript, PostgreSQL, PgVector, Groq LLM, Ollama, Google Embeddings, Tailwind CSS, uv

---

## Core Features

### 1. Hybrid Question-Answering Engine
- Routes user questions to the most relevant source: **database** (SQL analytics), **documents** (RAG over uploaded PDFs/TXT/MD), **general political knowledge**, or a **hybrid** combination.
- Intent classification router classifies queries into database/document/hybrid/general categories using an LLM-based classifier with fast-path rules for common voter-data requests.
- Falls back gracefully when sources lack relevant data, providing neutral general political context instead of hallucinating facts.

### 2. Database Analytics (Structured Data)
- Natural-language queries over voter records, party workers, activities, feedback, and contacts.
- Supports voter counts by ward/booth, color-code breakdowns, weak/strong booth identification, active/inactive worker analysis, and society-level support tracking.
- Role-based data scoping: karyakarta, corporator, aamdar, khasdar, and admin roles see only their assigned wards/assemblies/constituencies.
- Auto-generates chart configurations (bar, line, pie, table) for visualizing query results.

### 3. Document Intelligence (RAG)
- Upload and index campaign documents (PDF, TXT, MD) using Docling + LangChain document loaders.
- Hybrid retrieval: vector similarity (PGVector) + full-text keyword search fused with Reciprocal Rank Fusion (RRF), with neighbor-window chunk expansion.
- Answers grounded strictly in retrieved excerpts with source citations (filename + page numbers).
- Never reveals internal chunk metadata or ranking to end users.

### 4. Multilingual Support
- Detects and replies in the user's language: **Hindi, English, Marathi, Hinglish, or English-Marathi mix**.
- All system prompts, error messages, and strategy outlines are language-aware.

### 5. User Profile & Personalization
- Authenticated users can view their assigned profile (name, ward, assembly, parliamentary constituency, party).
- Personal profile questions ("What is my ward?", "What is my name?") are answered from the user's own database record without guessing.
- Strategy requests ("30-day strategy for my ward") generate neutral, high-level campaign outreach plans in the user's language.

### 6. Safety & Guardrails
- Refuses to share information about specific politicians or political personalities (MLA, MP, minister, corporator, etc.).
- Declines code/programming requests and non-political queries.
- Never invents voter counts, election results, or local facts — clearly distinguishes general knowledge from source-backed data.
- Empty database results return an honest "no matching records" message instead of falling back to fabricated general knowledge.

### 7. Real-Time Chat & Conversation Management
- Persistent conversations with user/assistant message pairs, ordered by microsecond-precise timestamps.
- Conversation history used to resolve follow-up references and build context-aware retrieval queries.
- New chat, conversation switching, and message edit/delete support.

---

## Technical Architecture

### Backend (Python / FastAPI)
- **Framework:** FastAPI with SQLAlchemy ORM and Alembic-style migrations
- **Database:** PostgreSQL with PgVector extension for vector storage and similarity search
- **LLM Providers:** Groq (ChatGroq) and Ollama (qwen3.5) with fallback support
- **Embeddings:** Google Generative AI Embeddings and Ollama embeddings
- **Document Processing:** Docling, pypdf, langchain_docling for PDF/TXT/MD ingestion
- **Authentication:** JWT-based auth with refresh tokens and role-based access control
- **Package Manager:** uv (fast Python package installer and resolver)

### Frontend (Next.js / React)
- **Framework:** Next.js 16 (App Router), React 19, TypeScript
- **Styling:** Tailwind CSS with shadcn/ui components
- **Charts:** Recharts for data visualization
- **Markdown:** React-Markdown with remark-gfm for rendered answers
- **State Management:** React hooks with optimistic UI updates and retry-on-error for failed requests

### Key Design Decisions
- **Hybrid retrieval (vector + keyword + RRF)** improves recall over pure semantic search for campaign documents.
- **Microsecond timestamp ordering** prevents assistant messages from displaying before user messages in chat history.
- **Source citations are rendered separately** from answer text to keep LLM output clean and focused.
- **Role-based data scoping** enforced at the query level, not just the UI level.

---

## Resume Bullet Points

- **Built Chanakya AI**, a full-stack political campaign intelligence platform enabling natural-language queries over voter databases, uploaded campaign documents, and multilingual political knowledge.
- **Designed a hybrid Q&A router** that classifies questions into database/document/hybrid/general intents and falls back gracefully when sources lack relevant data.
- **Implemented hybrid RAG** combining PGVector similarity search, PostgreSQL full-text search, and Reciprocal Rank Fusion with neighbor-window chunk expansion for document Q&A.
- **Developed multilingual support** (Hindi, English, Marathi, Hinglish, English-Marathi) across all LLM prompts, error messages, and strategy generation.
- **Enforced role-based data scoping** for five user roles (karyakarta, corporator, aamdar, khasdar, admin) with ward/assembly/constituency-level filtering.
- **Added safety guardrails** including politician-refusal logic, anti-hallucination rules for voter counts, and honest empty-result handling.
- **Built a Next.js 16 frontend** with real-time chat, optimistic error handling, retry-on-failure, and Recharts-based data visualization.
- **Reduced frontend error ambiguity** by replacing generic "Something went wrong" messages with status-specific, actionable failure messages and inline retry buttons.

---

## Repository
`satya-rajbhar-coder/Chanakya-AI` — `backend/ai_agent/` contains all AI/agent code (intelligence orchestration, LLM clients, RAG pipeline, prompts).
