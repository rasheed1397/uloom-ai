# Uloom AI — Frontend

React + TypeScript + Vite, calling the FastAPI backend in `../app` over
plain `fetch` (see `src/api/client.ts`). No UI library — plain CSS
(`src/index.css`).

## Setup

Requires Node 20+ (this repo was scaffolded with Node 22; the system Node on
some dev machines may be older — see the backend `CLAUDE.md` if so).

```bash
cd frontend
npm install
cp .env.example .env   # points at http://localhost:8000 by default
npm run dev
```

The backend must be running separately (see `../CLAUDE.md` for setup) and
needs `CORS_ALLOWED_ORIGINS` to include this dev server's origin
(`http://localhost:5173` by default — already the backend's default).

## Structure

- `src/api/` — one module per backend resource (`auth.ts`, `documents.ts`,
  `conversations.ts`, `admin.ts`), plus `client.ts` (fetch wrapper: base
  URL, bearer token, JSON/multipart, error normalization into `ApiError`)
  and `types.ts` (hand-written TS types mirroring `app/schemas/*.py` and the
  inline response models in `app/api/routers/*.py` — not generated, so if a
  backend response shape changes, update both sides manually for now).
- `src/context/AuthContext.tsx` — holds the current user + JWT (in
  `localStorage`), exposes `login`/`register`/`logout`/`refreshUser` (the
  last one re-fetches `/users/me`, used after a profile edit so the header
  picks up a changed email without a full reload).
- `src/components/` — `Layout` (header/nav — the email in the header is a
  link to `/profile`) and `ProtectedRoute` (redirects to `/login` if signed
  out, or `/documents` if `adminOnly` and the user isn't an admin).
- `src/pages/` — one file per route: login/register, `/profile`
  (self-service email/password update, FR-002 — `role` is deliberately not
  editable here, that's admin-only), documents (upload/list/delete, polls
  while a document is `uploaded`/`processing`), conversations (list/create),
  a conversation's chat view (loads history via `GET
  /conversations/{id}/messages`, asks via `POST`), and admin
  (users/documents, and settings — `retrieval_top_k`/`chunk_token_size`/
  `similarity_threshold` are editable now, `PATCH /admin/settings` is
  implemented backend-side).

## What's not here yet

- No tests — mirrors the backend's current state (test coverage work is a
  separate, paused effort; see the backend `CLAUDE.md`).
- No document content viewer — the Documents page shows status only, not
  the extracted text or chunks.
