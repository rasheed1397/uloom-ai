# Uloom AI — Context for Claude Code

This file exists because the project was scaffolded in a separate Cowork
session whose memory doesn't carry over here. Read this before making
changes so you don't re-litigate decisions that were already made
deliberately.

## What this project is

Uloom AI is a modular RAG platform (document upload → chunk → embed →
retrieve → cited Q&A). v1 scope is document intelligence only; resume
intelligence, interview coach, code assistant, and multi-agent features are
explicitly out of scope (see SRS Section 1.3.1).

## Source of truth documents

Two docs in this folder's parent directory are authoritative — read them
before assuming anything about scope or architecture:

- `../Uloom_AI_SRS_v1.2.docx` — requirements, tech stack, constraints
- `../Uloom_AI_Detailed_Design_v0.3.docx` — ERD, sequence diagrams, API
  resource map, per-service design, and Section 6 "Summary of Deferred
  Decisions" (the authoritative open-items list)

Earlier versions (SRS v0.2–v1.1, Design v0.1–v0.2) are kept alongside them
as history — don't treat them as current.

## Key decisions already made (don't relitigate)

- **AI provider: Google Gemini, single vendor, for both capabilities.**
  `generateContent` for chat, `gemini-embedding-001` for embeddings. This
  went through two revisions in the original session: first Claude
  (generation) + Voyage AI (embeddings) as a two-vendor default, then
  consolidated to Gemini alone because a single vendor covering both
  capabilities was judged cleaner/simpler. Claude, OpenAI, Voyage AI,
  Hugging Face, and Ollama remain valid alternates.
- **`ChatProvider` and `EmbeddingProvider` are separate interfaces even
  though `GeminiAdapter` implements both.** This is intentional, not
  leftover complexity — it's what makes it possible to point
  `AI_EMBEDDING_PROVIDER` at a different vendor later without touching
  `ChatProvider`, or vice versa. See `app/services/ai_service/interfaces.py`
  and Detailed Design Section 5.6 for the six swappability practices this
  codebase follows (adapter-per-provider, config-driven factory, normalized
  DTOs, normalized errors, capability flags).
- **The REST API layer (Section 4 of the Design doc) is deliberately not a
  formal OpenAPI contract yet.** Exact request/response schemas, error
  envelope shape, and pagination conventions are open on purpose, so the API
  layer stays swappable. Don't "helpfully" lock these down without checking
  Section 4 first.
- **`str, Enum` is used instead of `enum.StrEnum`** throughout the models
  and DTOs, and ruff's `UP042` is explicitly ignored in `pyproject.toml` for
  this reason — for broader compatibility with libraries that don't
  special-case `StrEnum`. Don't "fix" this via ruff autofix.
- **Python target is 3.10+, not 3.11+.** An earlier pass used
  `datetime.UTC` (3.11-only) via a ruff autofix and it broke on the 3.10
  verification environment; it was deliberately reverted to
  `datetime.now(timezone.utc)`. Keep it that way unless you're sure the
  deployment target is 3.11+.

## Implementation status (updated 2026-08-23 — document/conversation/admin build-out)

Fully working:
- `/auth/register`, `/auth/login`, `/users/me` — register → hash password →
  issue JWT → authenticate subsequent requests. Disabled accounts
  (`User.is_active`) are rejected at both login and on every subsequent
  request via `get_current_user`, not just at login time.
- `/documents` (upload, list, get, delete) — object storage backend
  decision (Design Sec.6 open item) resolved to **local volume** for v1,
  behind `app/services/storage/interfaces.py::StorageBackend` so an
  S3-compatible backend can be swapped in later without touching
  `DocumentService`. Upload returns 202 immediately (row + raw file
  persisted); parsing (PDF/DOCX/Markdown/plain text via
  `app/services/document_parsing.py`), token-range chunking
  (`app/services/chunking.py`, tiktoken `cl100k_base` — loaded lazily, not
  at import time, since it fetches its vocab file over the network on first
  use) and embedding happen in `DocumentService.process()`, run as a
  FastAPI `BackgroundTask` **on the same request-scoped session** as the
  upload (see the comment in `documents.py::upload_document` — FastAPI
  runs background tasks before a yield-dependency's post-yield/commit code
  specifically so this works; a separate session there raced the commit and
  silently no-op'd in testing). Any failure marks the document `FAILED`
  with `status_detail` set (SRS Sec.9), never left stuck in `PROCESSING`.
- `/conversations` (create, list) and `/conversations/{id}/messages`
  (`GET` history, `POST` ask) — conversation creation and the `GET` on
  messages were real missing features (not deferred decisions), now wired
  up. The Design doc's Section 4 API map calls for `GET` on the messages
  resource ("retrieve message + citation history") and
  `MessageRepository.list_for_conversation` already existed unused, but
  there was no route for it. `ask`/`list_messages` both check the
  conversation belongs to the caller (404 otherwise — previously *any*
  authenticated user could post to *any* conversation ID) and `ask` scopes
  retrieval to the caller's own documents via `DocumentService.list_for_owner`
  (previously always passed an empty list, so every question silently
  returned "can't answer"). `ask` now persists the user's own question as a
  `Message` too, not just the assistant's reply - previously `GET
  .../messages` would have shown one-sided assistant-only monologues, which
  only became obvious once something (the frontend) actually needed to
  render history. Provider failures (`ProviderError` and subtypes) degrade
  to a graceful assistant message per SRS Sec.9, not a 500 - includes a real
  connection failure case (`httpx.TransportError`, e.g. DNS/TLS failure)
  that `GeminiAdapter` didn't map to `ProviderError` at all before; also
  broadened `ClientError` to `APIError` there so 5xx responses aren't
  silently unmapped either.
- `/admin/*` — reachable now via a bootstrap mechanism (see below).
  `GET /admin/users`, `PATCH /admin/users/{id}` (role, `is_active`),
  `GET /admin/documents`, `DELETE /admin/documents/{id}`, and
  `GET /admin/settings` are implemented via `AdminService`.
  **Deliberately still 501**: `PATCH /admin/settings` (FR-009 wants
  retrieval-top-k/chunk-size adjustable "without a deployment", which needs
  runtime-persisted config read by VectorService/ConversationService, not
  the startup-time `Settings` object — a real schema + read-path change,
  not a one-route fix) and AI provider credential rotation (would need a
  managed secret store per NFR-004; storing keys in Postgres would
  undermine that requirement rather than satisfy it).

**Admin bootstrap (FR-009 open item, now resolved):** the first admin(s)
are created via `ADMIN_BOOTSTRAP_EMAILS` (comma-separated, checked at
registration in `AuthService.register`) rather than any API-driven
promotion path, since promotion needs an existing admin and this avoids
that chicken-and-egg problem and any privilege-escalation surface. Ongoing
role/active changes go through `PATCH /admin/users/{id}`.

Retrieval in `ConversationService.ask()` still returns whatever
`VectorService` finds without filtering by `SIMILARITY_THRESHOLD` — see the
`TODO` there. The threshold value itself is still an open item (needs eval
against real query data) - unchanged by this pass.

**Not yet covered by automated tests.** Test coverage (PR #2, currently
open/paused) predates this work and doesn't exercise any of it. Everything
above was verified manually against a live Postgres+pgvector instance
(register/login/disable, upload/list/get/delete across text/PDF/DOCX,
conversation create/list/ask including the degraded-mode path, admin
bootstrap/list/patch/delete) — see the PR description for the full manual
test log. `pypdf`, `python-docx`, `python-multipart`, and `httpx` (now a
direct dependency, not just transitive via `google-genai`) were added to
`requirements.txt`.

**`GEMINI_CHAT_MODEL` was bumped from `gemini-2.5-flash` to
`gemini-3.6-flash`** after the manual verification above initially caught
the full upload → index → ask flow live: embeddings worked
(`gemini-embedding-001` is fine), but chat generation returned a real 404
from the Gemini API - `gemini-2.5-flash` is no longer available to new
users. After the fix, ran the full RAG flow live end-to-end: a grounded
question returned a correct answer with an accurate citation
(chunk/document/source_location all matched), and an off-topic question
correctly avoided hallucinating (though it still cited an irrelevant chunk
- that's the pre-existing `SIMILARITY_THRESHOLD` gap noted above, not
something this pass introduced).

## Verified, not yet run live

- `ruff check .` and `mypy app` both pass clean.
- `pytest` passes (one health-check test).
- `alembic upgrade head --sql` was used to confirm the baseline migration
  compiles to valid PostgreSQL DDL (including the pgvector `VECTOR(3072)`
  column), but it has **never been run against a live database** — no
  Postgres/pgvector instance was available in the scaffolding sandbox.
- `docker-compose.yml` was validated as syntactically correct YAML only —
  `docker-compose up` has never actually been executed against it.

Treat "first real run" (whichever setup path — Docker or native
Postgres/pgvector/Redis via WSL2) as the next real test of this scaffold,
not something already confirmed working end to end.

## Environment setup

Copy `.env.example` to `.env`. Required to do anything beyond `/health`:
- `DATABASE_URL` pointing at a Postgres instance with the `vector` extension
  installed, with `alembic upgrade head` run against it
- `GEMINI_API_KEY` (only needed for the `/conversations/*` ask endpoint;
  auth endpoints don't call Gemini at all)
- `SECRET_KEY` — generate with `python -c "import secrets;
  print(secrets.token_hex(32))"`, don't leave the `change-me` default past
  local testing

`REDIS_URL` is defined in config and docker-compose but nothing in the
codebase actually uses Redis yet — it's reserved for future
caching/session/queue state per SRS Section 7.

New since the document/conversation/admin build-out, all optional (sane
defaults in `app/core/config.py`):
- `ADMIN_BOOTSTRAP_EMAILS` — comma-separated; set this to actually reach any
  `/admin/*` endpoint, otherwise there's no way to become an admin.
- `DOCUMENT_STORAGE_PATH` (default `./data/documents`), `MAX_UPLOAD_SIZE_MB`
  (default 25) — local storage backend config.

## Frontend (added 2026-08-23)

`frontend/` — React + TypeScript + Vite, plain `fetch` (see
`frontend/src/api/client.ts`), no UI library, plain CSS. See
`frontend/README.md` for structure/setup detail; this section covers what
that README doesn't.

Full click-through verified live in a real browser against this backend
(login, documents, conversation history with citations, live chat, admin
panel including a live enable/disable action) once PR #3 (document/
conversation/admin) and PR #4 (CORS) — both merged now — were available.
The only unverified piece is uploading via an actual OS file picker (the
browser automation used couldn't drive native file dialogs); upload itself
is thoroughly verified via `curl` in PR #3, including real Gemini
embedding end-to-end.

**Node version:** the system-wide Node on the machine this was scaffolded
on is v16.15.1 (EOL, too old for this Vite version — needs 20+). No
nvm-windows install succeeded (its installer needs an interactive admin
UAC prompt, which fails silently in a non-interactive session). Worked
around with a portable Node 22 zip extracted to
`%LOCALAPPDATA%\Programs\node-tools\node-v22.23.2-win-x64`, prepended to
`PATH` for frontend commands only — the system Node is untouched. If a
proper nvm/system Node upgrade happens later, this section can go.

**Known gaps** (also listed in `frontend/README.md`): no tests, no document
content/chunk viewer (status only), admin settings are read-only in the UI
since `PATCH /admin/settings` isn't implemented on the backend (see PR #3's
notes above on why).
