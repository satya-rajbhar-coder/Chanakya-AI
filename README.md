# Chanakya AI: chat + RAG over your PDFs

This folder contains only the files that changed or are new. Everything else
in your project (login/register forms, shadcn `components/ui/*`, `services/auth.ts`,
auth models/services, `core/security.py`, `database/*`, ...) stays exactly as it is.

## Setup

```bash
# 1. models (Ollama)
ollama pull qwen3.5            # chat model (whatever MODEL_NAME is)
ollama pull nomic-embed-text   # embedding model used for RAG

# 2. backend
cd backend
pip install -r requirements.txt
cp .env.example .env           # fill in DATABASE_URL and SECRET_KEY
uvicorn main:app --reload

# 3. frontend
cd frontend
npm i axios clsx tailwind-merge lucide-react react-markdown remark-gfm react-syntax-highlighter
npm i -D @types/react-syntax-highlighter
cp .env.example .env.local
npm run dev
```

## Delete these (dead or duplicated)

- `chat-api.py` (old prototype; `/ask-ai` is not registered in `api/router.py`)
- `services/chatAI.ts`
- `components/chats/` (whole folder: second, unused chat implementation)
- `components/chat/ChatPage.tsx`, `components/chat/new-chat.tsx`

## One manual edit: `app/globals.css`

In `@theme inline`, change

```css
--font-sans: var(--font-sans);
```
to
```css
--font-sans: var(--font-inter);
```
(it referenced itself, so the font never applied).

## Existing database

`create_all` only creates missing tables, so `documents` is added automatically.
`messages.user_id` was declared nullable=False with ON DELETE SET NULL; the model
now says ON DELETE CASCADE. New databases get it right; on an existing one, either
recreate that FK or ignore it (nothing breaks in normal use).

## How the RAG flow works

1. **Upload**: `POST /api/documents` (PDF, TXT, MD; 20 MB default).
2. **Load**: `pypdf` extracts text per page (`rag/loader.py`).
3. **Split**: `RecursiveCharacterTextSplitter`, 1000 chars / 150 overlap.
4. **Embed + store**: Ollama `nomic-embed-text` into a persistent Chroma
   collection (`storage/chroma`). Every chunk carries `user_id`, `document_id`,
   `filename`, `page`.
5. **Ask**: on each message, if the user has documents, the question (plus the previous
   user turn when it's a short follow-up) is embedded, the top 5 chunks **of that user only**
   are retrieved and put in the system prompt.
6. **Answer**: the reply gets a `Sources:` footer (file + pages). The footer is
   stripped again before history is sent back to the model.
7. **Delete**: `DELETE /api/documents/{id}` removes the row and its vectors.

Limits: scanned/image-only PDFs have no text layer (no OCR); indexing is
synchronous, so large files keep the upload request open until done.
