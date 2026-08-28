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

## Docker, document-list refresh, and default admin (2026-08-24)

Three user-reported items, in the order given.

**1. Docker completion.** The `api` image had never actually been rebuilt
against a current `requirements.txt` - the one `docker ps -a` showed was 3
days stale and crashed on `ModuleNotFoundError: No module named 'docx'`
(added since). Also found and fixed while completing this, none of it
previously done:
- No `.dockerignore` existed at all - every build sent the entire
  `uloom-ai/` directory as build context, including `.venv` (thousands of
  files) and `.git`. Added one (and a separate one for `frontend/`).
- No migration step ran on container start - a fresh deployment would have
  booted the API against an empty schema. Added `docker-entrypoint.sh`
  (`alembic upgrade head` then `exec "$@"`), wired as the Dockerfile's
  `ENTRYPOINT` with the existing `uvicorn` `CMD` preserved as the
  overridable command. Added `.gitattributes` (`*.sh text eol=lf`) so this
  script can't get checked out with CRLF line endings on Windows and break
  its shebang inside the Linux container.
- Added a `HEALTHCHECK` to the `api` image (plain Python `urllib.request`
  hitting `/health` - no `curl` in the `python:3.11-slim` base image).
- **The frontend had no Docker image at all.** Added
  `frontend/Dockerfile` (multi-stage: `node:22-alpine` build →
  `nginx:alpine` serve) and `frontend/nginx.conf` with an SPA fallback
  (`try_files $uri $uri/ /index.html`) - without it, refreshing on any
  route but `/` (e.g. `/documents`) 404s, since nginx has no matching file
  and React Router's client-side routing never gets a chance to run.
  `VITE_API_BASE_URL` is deliberately *not* set at build time: the bundle
  runs in the browser, not in the container's network, so it needs
  `src/api/client.ts`'s existing `http://localhost:8000` fallback (matches
  `api`'s published port), not an internal Docker DNS name the browser
  could never resolve. New `frontend` service in `docker-compose.yml`,
  published on `5173:80`.
- Verified: `docker compose build`, then `docker compose up` for the full
  stack (`api`, `frontend`, `db`, `redis`) - see the PR for the exact
  verification steps taken.

**2. Document list not updating after upload without a manual refresh.**
A real backend bug, not a frontend oversight - the frontend already called
`refresh()` right after upload. Root cause: `upload_document`'s background
task (`DocumentService.process`) reuses the request's own DB session (see
the "same request-scoped session" note in `document_service.py`, added
when documents were first implemented) - and FastAPI runs background tasks
*before* a yield-dependency's post-yield code, which is where
`app.core.db.get_session`'s commit happens. That meant the newly-created
`Document` row stayed invisible to *any other DB connection* - including
the frontend's own immediate `GET /documents` - until the entire
parse/chunk/embed pipeline finished, which can take real time (a live
embedding call). Every earlier test of this flow (including the "verified
live" claims in this file) used empty file content specifically, which
skips the embedding call and finishes near-instantly - masking exactly
this bug. It only became visible with real content and real latency,
which is what a human clicking through the UI naturally does and automated
testing here hadn't.

Fixed with an explicit `await self._documents.commit()` at the end of
`DocumentService.create_upload()`, before it returns - decouples the
initial row's visibility from the background task's later, separate
commit (which still happens atomically as before, when the request's
session tears down after the background task finishes). Also added
`cache: 'no-store'` to every request in `frontend/src/api/client.ts` as
cheap, unrelated insurance - none of this app's `GET` responses should
ever be served from the browser's HTTP cache regardless of this specific
bug's actual cause.

Live-verifying this (real file content, uploaded through the running
Docker stack, immediate `GET /documents` right after) surfaced a second,
worse bug the same fix introduced: `app.core.db.get_session` wrapped the
whole request in `async with session.begin():`, and that context manager
owns the transaction's entire lifecycle - a service calling
`session.commit()` mid-request leaves it unable to exit cleanly. The
background task's later `get_by_id` call (same session, same in-flight
`session.begin()` block) then crashed with `sqlalchemy.exc.
InvalidRequestError: Can't operate on closed transaction inside context
manager`, silently failing the embed pipeline and leaving the document
stuck at `status: "uploaded"` forever - worse than the original bug, since
now nothing recovers even on a later manual refresh. Empty-content test
uploads didn't reach `process()`'s DB call fast enough relative to the
response cycle to expose this either. Fixed by changing `get_session()` to
explicit `try: yield session; await session.commit(); except: await
session.rollback(); raise` instead of the `session.begin()` context
manager - functionally identical for every other endpoint (still commits
on success, rolls back on exception), but lets a service commit mid-request
and keep using the session afterwards, since SQLAlchemy opens a fresh
transaction automatically on the next statement after a commit. Re-verified
end-to-end after this fix: immediate visibility on `GET /documents` *and*
the background pipeline completing to `status: "indexed"` with no errors in
the container logs.

**3. No default admin before the first registration.** `ADMIN_BOOTSTRAP_EMAILS`
(existing) only promotes an email *when that person registers* - a fresh
deployment where nobody has registered yet had no path to `/admin/*` at
all. Added `DEFAULT_ADMIN_EMAIL`/`DEFAULT_ADMIN_PASSWORD` (both empty by
default, no hardcoded fallback password) and `app/core/bootstrap.py`'s
`ensure_default_admin()`, run from `main.py`'s `lifespan` handler on every
app startup - idempotent (checks for the email first), so it's safe to run
on every restart, not just the first one. Deliberately takes a
`UserRepository` parameter rather than opening its own DB session
internally, so it's unit-testable with a fake the same way every other
service in this codebase is, rather than needing a real database the way
`main.py`'s lifespan wiring itself does.

## SRS hardening pass: Sec.5.3, NFR-004, Sec.10, NFR-005/Sec.9, NFR-008, Sec.5.2 (2026-08-28)

Six remaining SRS/Detailed-Design items, worked in priority order. Scope for
three of them (TLS approach, observability depth, document sharing) was
confirmed with the user up front rather than guessed: self-signed TLS now
(not deferred to a production ingress writeup only), structured logs +
correlation ID only (no Prometheus/tracing yet), and retention-only for
Sec.10 - document *sharing* ("owner or explicitly shared") is explicitly
out of scope for this pass, still owner-only access. Sec.5.2's other open
item, virus/malware scanning on upload, was also explicitly deferred (not
an SRS requirement, just a design-doc placeholder) - both left as-is.

**1. Detailed Design Sec.5.3 (Vector Service) - pgvector index.** The
service itself already matched the design doc (authorization scoping in
the query's `WHERE` clause, not a post-filter). The doc's own "open
question" - index type/tuning - was unaddressed: no ANN index existed on
`chunks.embedding_vector` at all, so every similarity search was a full
sequential scan. Added an HNSW index (0004 migration) - no IVFFlat training
step needed against a small/empty table at migration time, and better
recall/speed at query time.

Hit pgvector's real, hard constraint building this: **HNSW (and IVFFlat)
cap the plain `vector` type at 2000 dimensions**, but `EMBEDDING_DIM`
(`app/models/chunk.py`) is 3072 (`gemini-embedding-001`'s output size) -
the first migration attempt failed outright with `ProgramLimitExceededError:
column cannot have more than 2000 dimensions for hnsw index`. Fixed with
pgvector's documented workaround: index a `halfvec(3072)` **cast** of the
column (`CREATE INDEX ... USING hnsw ((embedding_vector::halfvec(3072))
halfvec_cosine_ops)`) - halfvec lifts HNSW's ceiling to 4000 dimensions at
half-precision, but only for the index's internal representation; the
column itself stays full-precision `vector(3072)`, so nothing about
stored/returned embeddings changes. `ChunkRepository.similarity_search`
casts the query the same way (`cast(Chunk.embedding_vector,
HALFVEC(EMBEDDING_DIM)).cosine_distance(...)`) - Postgres only uses an
expression index when the query's expression matches the indexed one, so
without this cast the query would silently fall back to a sequential scan
despite the index existing.

**2. NFR-004 (Security) - HTTPS.** JWT, RBAC, and bcrypt password hashing
were already in place; nothing enforced HTTPS anywhere (nginx plain 80,
uvicorn no TLS). Both the `api` and `frontend` containers now generate a
self-signed cert at startup (`docker-entrypoint.sh` in each, via `openssl
req -x509 ... -subj "/CN=localhost"` - never baked into the image or
committed, regenerated per-container) and serve TLS only:
- `frontend`: nginx listens on 443 only (`frontend/nginx.conf`), with a
  `Strict-Transport-Security` header. `docker-compose.yml` publishes
  `5173:443`.
- `api`: uvicorn gets `--ssl-certfile`/`--ssl-keyfile` in the Dockerfile's
  `CMD`. Still published as `8000:8000`, now serving https there instead
  of http. The `HEALTHCHECK` explicitly skips cert verification
  (`ssl._create_unverified_context()`) since it's checking against our own
  self-signed cert, not vetting it.
- Frontend's `API_BASE_URL` default and the backend's
  `CORS_ALLOWED_ORIGINS` default both moved to `https://`.

Dead-config lesson from this pass: nginx originally also had a `listen 80`
block that issued a `301` to `https://$host$request_uri`, intended to
redirect a stray plain-http visit. It never worked and was removed -
`docker-compose.yml` only publishes host `5173` to the container's `443`
(never to `80`), so nothing ever reached that block from outside the
container; a raw http request to `5173` just gets nginx's built-in
protocol-mismatch rejection (`400 Bad Request`) instead. A working redirect
would need the http and https listeners reachable at the *same* host port
number (as on a real deployment's standard 80/443), which this local
mapping deliberately doesn't do. Verified end-to-end via `curl -sk` against
both origins, an actual CORS preflight (`OPTIONS` with `Origin:
https://localhost:5173`) against the api, and the HSTS header - **not**
via the interactive browser tool, which can't click through a self-signed
cert's interstitial warning (no visible pane to click "proceed", and it
refuses to navigate to an untrusted cert at all). A real browser needs a
one-time manual "proceed anyway" on `https://localhost:8000` and
`https://localhost:5173` each, the first time.

**3. SRS Section 10 (Data Privacy and Retention) - retention period.**
Deletion already worked correctly (storage file + DB row, with
`Document.chunks`/`Conversation.messages` cascading via SQLAlchemy
relationship `cascade="all, delete-orphan"`). Added the missing piece: a
default retention period, admin-configurable, per the SRS's explicit
wording. `system_settings.retention_days` (0005 migration, default 90)
joins the three existing admin-tunable fields - same
read-fresh-every-time, no-restart-needed pattern via `PATCH
/admin/settings`. Enforcement is `app/core/retention.py`'s
`run_retention_sweep()`, run daily via an `asyncio.create_task` started in
`main.py`'s `lifespan` (no new scheduler dependency for this) - reads
`retention_days` from the DB fresh on every sweep, then deletes every
document and conversation (platform-wide, all users - Section 10 describes
a default *period*, not a per-user setting) older than that. A failing
sweep is caught and logged, never crashes the app or blocks the next
scheduled one (same Sec.9 "failures shall not terminate the application"
principle applied to this background task, not just AI-provider calls).

**4. NFR-005/SRS Sec.9 (Reliability) - retry + fallback.** The
degraded-mode paths already existed and matched the SRS wording closely
(embed failure -> document `FAILED` with a reason; vector-search/chat
provider outage -> graceful degraded assistant message) - but nothing
retried a timeout or fell back to a second provider first, as Sec.9
explicitly specifies. Added `app/services/ai_service/resilient.py`:
`ResilientChatProvider`/`ResilientEmbeddingProvider` wrap the real
provider(s) behind the *same* interfaces, so Document/Vector/Conversation
Service need zero changes - they already catch `ProviderError` for the
existing degraded-mode paths this wrapper's final re-raise feeds into.
Only `ProviderTimeoutError` gets a retry (one, after a short backoff) -
Sec.9 says "AI provider timeout" specifically, and auth/rate-limit/
content-policy failures aren't transient the same way, so those go
straight to the fallback (or straight to re-raising, if none configured)
without wasting a retry on a request that would fail identically again.
New `AI_CHAT_PROVIDER_FALLBACK`/`AI_EMBEDDING_PROVIDER_FALLBACK` settings
(both empty by default - matches the current single-vendor-for-v1
decision, Detailed Design Sec.5.5); blank or equal-to-primary is treated
as "not configured" in the factory, not a pointless self-fallback call.

**5. NFR-008 (Observability) - structured logs + correlation ID.** Nothing
existed beyond scattered `logger.info`/`logger.exception` calls. Added
`app/core/logging_config.py`: a JSON log formatter that pulls a
correlation ID from a `contextvars.ContextVar` - every existing log call
site became structured and correlated for free, without touching any of
them, since the formatter (not the caller) is what reads the ID.
`CorrelationIdMiddleware` (a `BaseHTTPMiddleware` subclass, registered
outermost - before `CORSMiddleware` - so it covers everything below it)
sets that contextvar per-request, reusing an inbound `X-Request-ID` header
if one's already present (so an ID survives a hop through a real load
balancer/ingress), and echoes it back in the response header. It also
covers `DocumentService.process()` even though that runs as a
`BackgroundTask` scheduled from the upload request: Starlette runs
background tasks by awaiting them in-place, in the same coroutine/context
as the request that scheduled them (the same reason `create_upload`'s
explicit commit was needed - see item 2 in the section above), so the
contextvar set by the middleware is still active when the background task
logs, with no extra propagation code needed.

**6. Detailed Design Sec.5.2 (Document Service) - no changes.** Already
matched the design closely (pluggable chunking, async 202-then-process
upload flow, status tracking, cascading deletion). Its one open question,
virus/malware scanning, was explicitly deferred per the scope decision
above - would need a new ClamAV container dependency, not something to add
speculatively.

A test-writing lesson from this pass, worth remembering for any future
background-task test: **a fake `asyncio.sleep` replacement that doesn't
itself yield to the event loop turns a `while True` retry/poll loop into a
genuine, unbounded, fully-synchronous infinite loop** - not just "runs
fast without a real delay". The first version of
`test_periodic_sweep_survives_a_failing_iteration` did exactly this (an
`async def` mock with no internal `await`) and starved the
session-scoped test event loop for 3.5 hours before hitting `MemoryError`
mid-suite. Fixed by never spinning the loop up as a background task at
all - the mocked sleep raises `CancelledError` directly on its first call,
ending the loop deterministically after exactly one iteration, with no
timing dependency of any kind.
