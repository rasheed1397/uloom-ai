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
  `GET/PATCH /admin/users/{id}` (role, `is_active`), `GET /admin/documents`,
  `DELETE /admin/documents/{id}`, and `GET`/`PATCH /admin/settings` are all
  implemented via `AdminService`. AI provider credential rotation remains
  deliberately unimplemented — would need a managed secret store per
  NFR-004; storing keys in Postgres would undermine that requirement rather
  than satisfy it, so it stays out rather than being half-done.
- `/users/me` now supports `PATCH` too (FR-002 self-service profile
  update: email and/or password). `role` is deliberately not a field on
  `UpdateProfileRequest` — role changes stay Administrator-only via
  `PATCH /admin/users/{id}`, so there's no self-promotion path. Note: the
  SRS's actual FR-002 acceptance criteria (profile+role readable, role
  changes take effect on next request) was already fully satisfied before
  this — this `PATCH` fulfills the Design doc's API resource map wording
  ("Read/update profile"), which is a stronger ask than the SRS itself.

**Admin bootstrap (FR-009 open item, now resolved):** the first admin(s)
are created via `ADMIN_BOOTSTRAP_EMAILS` (comma-separated, checked at
registration in `AuthService.register`) rather than any API-driven
promotion path, since promotion needs an existing admin and this avoids
that chicken-and-egg problem and any privilege-escalation surface. Ongoing
role/active changes go through `PATCH /admin/users/{id}`.

**FR-009 settings tuning, and FR-006's SIMILARITY_THRESHOLD, are both
resolved now** (previously: settings PATCH was 501, and the threshold was
computed but never applied — see the `2026-08-23` "FR-002/006/009
completion" note below for how).

**Covered by automated tests as of the PR #2 merge** (this paragraph is
stale history, kept for context: at the time this section was first
written, PR #2's test suite predated this implementation and didn't
exercise any of it — that's since been fixed; PR #2's tests were rewritten
against this actual implementation before merging, see its PR description).
Also verified manually against a live Postgres+pgvector instance
(register/login/disable, upload/list/get/delete across text/PDF/DOCX,
conversation create/list/ask including the degraded-mode path, admin
bootstrap/list/patch/delete). `pypdf`, `python-docx`, `python-multipart`,
and `httpx` (now a direct dependency, not just transitive via
`google-genai`) were added to `requirements.txt`.

**`GEMINI_CHAT_MODEL` was bumped from `gemini-2.5-flash` to
`gemini-3.6-flash`** after the manual verification above initially caught
the full upload → index → ask flow live: embeddings worked
(`gemini-embedding-001` is fine), but chat generation returned a real 404
from the Gemini API - `gemini-2.5-flash` is no longer available to new
users. After the fix, ran the full RAG flow live end-to-end: a grounded
question returned a correct answer with an accurate citation
(chunk/document/source_location all matched), and an off-topic question
correctly avoided hallucinating (though at the time it still cited an
irrelevant chunk - that specific symptom is what the FR-006 fix below
addresses; SIMILARITY_THRESHOLD is applied now, so a genuinely irrelevant
chunk should no longer be retrieved at all, let alone cited).

## Run live, repeatedly (this section is stale history)

This section originally said none of this had ever been run against a live
database, based on the scaffolding sandbox not having Postgres available.
That's long since stopped being true: `alembic upgrade head` (not just
`--sql`), `docker-compose`'s `db`/`redis` containers, and the full
API surface (including live Gemini embedding + chat calls) have all been
exercised repeatedly against a real Postgres+pgvector instance across
several sessions, plus the full frontend click-through. `ruff check .` and
`mypy app` both still pass clean. Kept as a note for future sessions: don't
trust a "never verified live" claim in this file at face value if the
`## Implementation status` sections above it describe live verification -
update this section instead of leaving contradictory claims in the file.

## FR-002/FR-006/FR-009 completion (2026-08-23)

An SRS gap-analysis pass (comparing the actual code against the SRS's FRs
and NFRs, not just the Design doc) found several outstanding items;
completed the three that were safely completable without new
infrastructure (a managed secret store, structured logging, retry/fallback
providers, and similar remain open - see that gap-analysis conversation for
the full list, not reproduced here).

- **FR-002**: `PATCH /users/me` added (`UpdateProfileRequest`: `email`
  and/or `password`, deliberately no `role` field). Covered above in
  Implementation status.
- **FR-006**: `SIMILARITY_THRESHOLD` is now actually applied, not just
  computed. `ChunkRepository.similarity_search` gained a `max_distance`
  parameter and filters in the SQL query itself (`WHERE cosine_distance <=
  max_distance`), not as a Python post-filter - same rationale as the
  existing owner-scoping filter (Sec.5.3): keeps "nothing similar enough"
  indistinguishable at the query level from "no chunks exist", so nothing
  downstream can accidentally see unfiltered results. `VectorService.search`
  converts the similarity threshold (0-1, higher = more similar) to a
  cosine-distance ceiling (`1 - threshold`) before passing it down -
  distance and similarity are inverses. `ConversationService.ask()` now
  passes `settings.similarity_threshold` through.
- **FR-009 settings tuning**: new `system_settings` table (migration
  `0003`), a deliberate singleton - exactly one row, `id` fixed at 1, seeded
  by the migration with `app.core.config.Settings`' current defaults
  (5/512/0.7). `SystemSettingsRepository` reads/writes it;
  `AdminService.get_settings`/`update_settings` wrap that for the router.
  `PATCH /admin/settings` now actually updates `retrieval_top_k`,
  `chunk_token_size`, and `similarity_threshold` at runtime,
  no redeploy needed - the literal FR-009 acceptance criteria. The
  mechanism: `deps.get_effective_settings` reads the DB row on **every
  request** and returns `Settings.model_copy(update={...})` - a copy of the
  static, env-loaded `Settings` with only those three fields overridden.
  `get_conversation_service` and `get_document_service` depend on
  `get_effective_settings` now, not the raw `Depends(get_settings)` static
  singleton. Everything else in `Settings` (secrets, provider selection,
  storage paths) is untouched and still comes from the environment only -
  this table is deliberately scoped to just the three tunables FR-009 names
  ("e.g., retrieval top-k, chunk size"), not a general settings-override
  system.
- **Test infra note**: `tests/conftest.py`'s `_clean_db` autouse fixture
  truncates every table before each test. `system_settings` had to be
  special-cased - it's a singleton config row seeded once by a migration,
  not per-test data, so truncating it would break
  `SystemSettingsRepository.get()` (which expects exactly one row to exist)
  for every test after the first. It's now reset to known default values
  instead of deleted, so tests get a consistent starting point without
  losing the row.
- **Still not done, and not a one-line fix if picked up later**: AI
  provider credential rotation (FR-009's other half) - real reason
  unchanged, needs a managed secret store (NFR-004) this codebase doesn't
  have. Also still open: NFR-005/Sec.9's actual retry-with-backoff and
  fallback-provider behavior (only graceful degradation exists, not retry
  or fallback), NFR-008 correlation-ID logging, Sec.10 encryption at rest,
  retention-period configuration, and pgvector index tuning (no
  `IVFFlat`/`HNSW` index exists on `chunks.embedding_vector` - fine at
  current scale, won't be at volume).

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
content/chunk viewer (status only). Admin settings became editable in the
UI (`ProfilePage`/`AdminPage` added) once the backend's FR-002/FR-009 gaps
closed — see that section above; this note is here so a future pass
doesn't assume the UI is still ahead of or behind the backend on these
without checking.
