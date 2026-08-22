"""FastAPI entrypoint. Presentation/API layer only — auth, validation, and
translation to Business Services (Detailed Design Sec.6 layering)."""
from fastapi import FastAPI

from app.api.routers import admin, auth, conversations, documents, users

app = FastAPI(
    title="Uloom AI",
    version="0.1.0",
    description="Modular RAG platform — v1: document intelligence (SRS v1.2)",
)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(documents.router)
app.include_router(conversations.router)
app.include_router(admin.router)


@app.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    return {"status": "ok"}
