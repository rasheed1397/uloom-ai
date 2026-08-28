"""Config-driven provider selection (Detailed Design Sec.5.6, practice #3).

AI_CHAT_PROVIDER and AI_EMBEDDING_PROVIDER are resolved once, here, at
startup. Calling code (Document Service, Vector Service, Conversation
Service) depends only on ChatProvider / EmbeddingProvider — never on which
branch this factory took. Adding a new adapter is: write the adapter class,
add one entry to the relevant dict below.
"""
from functools import lru_cache

from app.core.config import Settings, get_settings
from app.services.ai_service.adapters.gemini_adapter import GeminiAdapter
from app.services.ai_service.interfaces import ChatProvider, EmbeddingProvider
from app.services.ai_service.resilient import ResilientChatProvider, ResilientEmbeddingProvider

# Alternate adapters (Claude, OpenAI, Voyage AI, Hugging Face, Ollama) plug in
# here as they're implemented — see SRS Sec.7 for the full alternates list.
# e.g. "anthropic": lambda s: ClaudeAdapter(api_key=s.anthropic_api_key)


@lru_cache
def get_chat_provider() -> ChatProvider:
    settings = get_settings()
    primary = _build_chat_provider(settings, settings.ai_chat_provider)
    fallback_name = settings.ai_chat_provider_fallback
    if not fallback_name or fallback_name == settings.ai_chat_provider:
        # NFR-005/Sec.9: fallback is "if available" - blank or same-as-
        # primary both mean "not configured", not a pointless self-fallback.
        return ResilientChatProvider(primary)
    fallback = _build_chat_provider(settings, fallback_name)
    return ResilientChatProvider(primary, fallback)


@lru_cache
def get_embedding_provider() -> EmbeddingProvider:
    settings = get_settings()
    primary = _build_embedding_provider(settings, settings.ai_embedding_provider)
    fallback_name = settings.ai_embedding_provider_fallback
    if not fallback_name or fallback_name == settings.ai_embedding_provider:
        return ResilientEmbeddingProvider(primary)
    fallback = _build_embedding_provider(settings, fallback_name)
    return ResilientEmbeddingProvider(primary, fallback)


def _build_chat_provider(settings: Settings, provider_name: str) -> ChatProvider:
    if provider_name == "gemini":
        return _gemini_adapter(settings)
    raise ValueError(f"Unknown AI_CHAT_PROVIDER: {provider_name!r}")


def _build_embedding_provider(settings: Settings, provider_name: str) -> EmbeddingProvider:
    if provider_name == "gemini":
        return _gemini_adapter(settings)
    raise ValueError(f"Unknown AI_EMBEDDING_PROVIDER: {provider_name!r}")


_gemini_singleton: GeminiAdapter | None = None


def _gemini_adapter(settings: Settings) -> GeminiAdapter:
    # Single instance serves both interfaces when both env vars say "gemini" —
    # still two separate call sites (get_chat_provider / get_embedding_provider),
    # so pointing one of them at a different adapter later is a one-line change.
    # (Settings isn't hashable, so this is memoized manually rather than via
    # lru_cache; get_chat_provider/get_embedding_provider are already cached.)
    global _gemini_singleton
    if _gemini_singleton is None:
        _gemini_singleton = GeminiAdapter(
            api_key=settings.gemini_api_key,
            chat_model=settings.gemini_chat_model,
            embedding_model=settings.gemini_embedding_model,
        )
    return _gemini_singleton
