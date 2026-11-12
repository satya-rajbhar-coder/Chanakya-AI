# Chanakya AI — Frontend Architecture

> **Document:** `docs/08_FRONTEND_ARCHITECTURE.md`  
> **Scope:** Next.js 16 / React 19 frontend: App Router, state management, service layer, auth/session flow, chat UI, admin panel, markdown/mermaid rendering.  
> **Source:** `frontend/` (`app/`, `components/`, `services/`, `lib/`, `proxy.ts`).  
> **Note:** This is Next.js 16 with breaking conventions — see `frontend/AGENTS.md` and `node_modules/next/dist/docs/` before modifying.

---

## 1. Stack

| Layer | Technology |
|-------|------------|
| Framework | Next.js 16.3.6 App Router |
| UI library | React 19 |
| Styling | Tailwind CSS v4 (+ typography) |
| Components | shadcn-style / Radix primitives (dialog, tabs, select, tooltip, sidebar, scroll-area…) |
| Icons | lucide-react |
| Theming | next-themes |
| HTTP | axios (client) + fetch (analysis service) |
| Markdown | react-markdown + remark-gfm + rehype-raw |
| Diagrams | mermaid |
| Env | `NEXT_PUBLIC_API_URL` (default `http://localhost:8000/api`) |

---

## 2. Route Structure (`frontend/app/`)

```
app/
  layout.tsx              <ThemeProvider> root
  login/page.tsx          LoginForm
  register/page.tsx
  (protected)/            session-guarded group (server layout redirects on failure)
    layout.tsx            getSession → redirect → DialogProvider > WorkspaceProvider >
                          SidebarProvider > AppSidebar
    page.tsx              ChatHome (tabs: Documents | Analysis)
    chat/[id]/page.tsx    DocumentsChat for a persisted conversation (server-passed id)
    admin/page.tsx        AdminPanel (admin only)
    temporary/page.tsx
```

- `(protected)` group enforces auth once via `(protected)/layout.tsx` (`getSession()` → redirect `?reason=expired` before rendering).
- New chat = `/` → `ChatHome` with tab switcher `documents | analysis` (both kept mounted).
- `/chat/[id]` renders `DocumentsChat conversationId=id` (server component passing `id`).

---

## 3. Auth / Session Flow (Three Cooperating Mechanisms)

Cookie-based; **no tokens in localStorage**.

### 3.1 `proxy.ts` (Next.js middleware) — runs on every non-static route
- `/login?reason=expired` wipes stale cookies (server-layout signalled invalid session).
- Valid access token → pass (public page → redirect `/`).
- Only refresh token → call `POST /auth/refresh` server-side, **splice fresh Set-Cookies** into the current request headers (so this request's server components see it) *and* forward to the browser.
- Invalid → redirect `/login`; stale refresh → clear cookies and stop retry loops.

### 3.2 `lib/axios.ts` (client axios instance)
- `withCredentials`; response interceptor treats any 401 (except on `auth/*` or already-retried) as lapsed access token → single-flight `refreshPromise` refresh → replay original request; failure → hard `window.location.replace('/login?reason=expired')`.

### 3.3 `services/session.server.ts` (server-only)
- `getSession()` forwards the browser cookie header to `GET /users/me`; `(protected)/layout.tsx` redirects unauthenticated visitors before rendering any protected page.

---

## 4. State Management (`components/workspace-provider.tsx`)

React context loaded on mount with:
- `conversations` and `documents` lists, `refreshConversations`, `refreshDocuments`, `removeConversation`.
- Cross-page **flashError** store (e.g. surfaced by DocumentsChat).
- Exposed via `useWorkspace()`. Documents/Analysis chat use local component state for turns/messages.

---

## 5. Service Layer (`frontend/services/`)

| Service | Covers |
|---------|--------|
| `auth.ts` | login/logout via axios |
| `session.server.ts` | server-only `getSession()` (cookie → `GET /users/me`) |
| `conversations.ts` | conversation CRUD |
| `messages.ts` | `getAllConversationMessages` → `MessagePage {items, next_cursor}` cursor paging |
| `documents.ts` | admin `uploadDocument` (FormData: `file` + `JSON.stringify(user_ids)`) |
| `admin.ts` | clients/users CRUD, assignments |
| `analysis.ts` | raw `fetch` (own 401→refresh→retry), `credentials: "include"`; `askAnalysis`, `askGlobalAnalysis`, `fetchRows`, `exportCsv` (Blob), `saveAnalysis`, `listSaved`, `runSaved`, `listHistory`, `runHistory`, deletes |
| `intelligence.ts` | `askIntelligence` → `POST /intelligence/ask` |
| `http.ts` | `send` helper used by intelligence service |
| `error.ts` | `getApiErrorMessage` handles FastAPI `detail` string/array |

---

## 6. Chat UI

### 6.1 DocumentsChat (chat page or tab)
- Optimistic UX — user message appended immediately with temp id; loading indicator.
- `sendMessage(conversationId, content)` posts and appends **both** returned messages (temp replaced); creates a conversation on first message and `router.replace`/updates to the new `/chat/[id]`; sidebar list refreshed via workspace context.
- Message history with cursor pagination; markdown rendering; errors surfaced inline; refusal path shows the backend's friendly "couldn't find the answer…" message.

### 6.2 AnalysisChat (tab)
- Turns model `{id, question, status: loading|done|error, data, error}`.
- Sends `askGlobalAnalysis({question})`; on success renders **title / SQL / result table / timing** via `ResultTable` plus **token-gated client actions**: paginate (`fetchRows` with token+page) and **CSV export** (`exportCsv(token)` → Blob download), **save analysis** (`saveAnalysis(token, question, title)`), and error/alert dialogs via `useDialogs`.
- **History** panel lists past queries (re-run = `runHistory`; delete with confirm); **Saved** panel lists saved analyses (open = `runSaved`); re-runs appear as new turns.

### 6.3 Supporting components
- `documents-panel.tsx` / `app-sidebar.tsx` — sidebar navigation of conversations/documents.
- `ChatInput.tsx`, `ChatMessages.tsx`, `ChatTabs.tsx`, `ChatHome.tsx`, `ResultTable.tsx`.

---

## 7. Markdown / Mermaid Rendering (`components/markdown/`)

- `MarkdownContent` (chat) maps GFM elements through `MarkdownComponents` with `CodeBlock` (copy button) and `MermaidDiagram` (async `mermaid.render`, themed, error-fallback box) — matching the backend prompt's Mermaid syntax rules.

---

## 8. Admin Panel (`components/admin/AdminPanel.tsx`, route `/admin`)

- Clients CRUD (database name, client identifier).
- Users CRUD.
- **Client assignments editor** (replace-style PUT).
- **Document upload / re-scope / delete** (accepted `.pdf, .txt, .md`).
- Lists from `services/admin.ts`.
