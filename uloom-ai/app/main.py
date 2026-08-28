"""FastAPI entrypoint. Presentation/API layer only — auth, validation, and
translation to Business Services (Detailed Design Sec.6 layering)."""
import asyncio
import contextlib
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routers import admin, auth, conversations, documents, users
from app.core.bootstrap import ensure_default_admin
from app.core.config import get_settings
from app.core.db import SessionLocal
from app.core.logging_config import CorrelationIdMiddleware, configure_logging
from app.core.retention import run_retention_sweep_periodically
from app.repositories.user_repository import UserRepository

configure_logging()


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    async with SessionLocal() as session, session.begin():
        await ensure_default_admin(UserRepository(session))
    sweep_task = asyncio.create_task(run_retention_sweep_periodically())
    yield
    sweep_task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await sweep_task


app = FastAPI(
    title="Uloom AI",
    version="0.1.0",
    description="Modular RAG platform — v1: document intelligence (SRS v1.2)",
    lifespan=lifespan,
)

# Outermost: assigns/logs a correlation ID before CORS or routing see the
# request, so every log line from here down - including a background task
# scheduled later in the same request (see CorrelationIdMiddleware's
# docstring) - carries it (NFR-008, SRS Sec.9).
app.add_middleware(CorrelationIdMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(get_settings().cors_allowed_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(documents.router)
app.include_router(conversations.router)
app.include_router(admin.router)


@app.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    return {"status": "ok"}
