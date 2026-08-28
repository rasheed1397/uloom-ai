"""FastAPI entrypoint. Presentation/API layer only — auth, validation, and
translation to Business Services (Detailed Design Sec.6 layering)."""
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routers import admin, auth, conversations, documents, users
from app.core.bootstrap import ensure_default_admin
from app.core.config import get_settings
from app.core.db import SessionLocal
from app.repositories.user_repository import UserRepository


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    async with SessionLocal() as session, session.begin():
        await ensure_default_admin(UserRepository(session))
    yield


app = FastAPI(
    title="Uloom AI",
    version="0.1.0",
    description="Modular RAG platform — v1: document intelligence (SRS v1.2)",
    lifespan=lifespan,
)

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
