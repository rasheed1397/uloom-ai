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

## Implementation status (as of scaffold handoff)

Fully working:
- `/auth/register`, `/auth/login`, `/users/me` — real vertical slice:
  register → hash password → issue JWT → authenticate subsequent requests.

Stubbed on purpose (raises `NotImplementedError` / returns 501):
- `/documents` (upload, list, get, delete) — blocked on the object storage
  backend decision (Design Sec.6 open item: local volume vs. S3-compatible).
  `DocumentService.upload_and_index` has the intended flow commented in.
- `/admin/*` — stubbed; also currently unreachable since registration always
  creates a `STANDARD` role user and there's no promotion path yet.

**Known gap, not an intentional stub:** there is no `POST /conversations`
endpoint to create a conversation. `app/api/routers/conversations.py` only
implements `POST /{conversation_id}/messages` (ask a question against an
*existing* conversation). The Design doc's Section 4 resource table lists
conversation creation, but it was never wired up. A `conversation_id`
currently has to be inserted manually to exercise the ask-a-question flow.
This should be treated as a small missing feature, not a deferred decision.

Retrieval in `ConversationService.ask()` returns whatever `VectorService`
finds without filtering by `SIMILARITY_THRESHOLD` yet — see the `TODO` in
`app/services/conversation_service.py`. The threshold value itself is also
an open item (needs eval against real query data).

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

## Frontend (added 2026-08-23)

`frontend/` — React + TypeScript + Vite, plain `fetch` (see
`frontend/src/api/client.ts`), no UI library, plain CSS. See
`frontend/README.md` for structure/setup detail; this section covers what
that README doesn't.

**Depends on two other branches/PRs to actually work against a real
backend**, since this branch was cut from `main` before either landed:
- `feature/document-conversation-admin-services` (PR #3) — without it,
  `/documents`, `/conversations`, and `/admin/*` are all still stubs.
- `feature/frontend-cors-support` (PR #4) — without it, the browser blocks
  every request with a CORS error (no `Access-Control-Allow-Origin`
  header). Confirmed live: the same login request that worked fine over
  `curl` failed in the browser console with exactly this until CORS
  middleware was added.

If working on this branch standalone, merge or locally combine both first
rather than debugging what looks like a broken frontend.

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
