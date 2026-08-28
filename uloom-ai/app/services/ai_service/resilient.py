"""Retry-with-backoff + fallback-provider wrapper (NFR-005, SRS Sec.9:
"AI provider timeout: request retried once with backoff, then routed to a
configured fallback provider if available; otherwise the user receives a
clear... message"). Wraps ChatProvider/EmbeddingProvider so Conversation
Service, Document Service, and Vector Service need no changes at all - they
already catch ProviderError for the degraded-mode paths this wrapper's
final re-raise feeds into (Sec.5.6, practice #5: normalize errors once,
write retry/fallback logic once, against the interface).

Only ProviderTimeoutError is retried - Sec.9 says "AI provider timeout"
specifically, and auth/rate-limit/content-policy failures aren't transient
the way a timeout can be, so they go straight to the fallback (or straight
to re-raising, if none is configured) instead of wasting a retry on a
request that will fail identically every time.
"""
import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import TypeVar

from app.services.ai_service.dtos import (
    ChatRequest,
    ChatResponse,
    EmbedRequest,
    EmbedResponse,
    ProviderCapabilities,
)
from app.services.ai_service.interfaces import (
    ChatProvider,
    EmbeddingProvider,
    ProviderError,
    ProviderTimeoutError,
)

logger = logging.getLogger(__name__)

_RETRY_BACKOFF_SECONDS = 1.0

T = TypeVar("T")


async def _call_with_retry_and_fallback(
    provider_name: str,
    primary: Callable[[], Awaitable[T]],
    fallback: Callable[[], Awaitable[T]] | None,
) -> T:
    try:
        return await primary()
    except ProviderTimeoutError:
        logger.warning("%s provider timed out, retrying once after backoff", provider_name)
        await asyncio.sleep(_RETRY_BACKOFF_SECONDS)
        try:
            return await primary()
        except ProviderError as exc:
            return await _fall_back_or_raise(provider_name, fallback, exc)
    except ProviderError as exc:
        # Not a timeout - not worth retrying, go straight to fallback.
        return await _fall_back_or_raise(provider_name, fallback, exc)


async def _fall_back_or_raise(
    provider_name: str, fallback: Callable[[], Awaitable[T]] | None, exc: ProviderError
) -> T:
    if fallback is None:
        logger.error("%s provider failed (%s), no fallback configured", provider_name, type(exc).__name__)
        raise exc
    logger.warning("%s provider failed (%s), trying fallback provider", provider_name, type(exc).__name__)
    return await fallback()


class ResilientChatProvider(ChatProvider):
    def __init__(self, primary: ChatProvider, fallback: ChatProvider | None = None) -> None:
        self._primary = primary
        self._fallback = fallback

    @property
    def capabilities(self) -> ProviderCapabilities:
        return self._primary.capabilities

    async def generate(self, request: ChatRequest) -> ChatResponse:
        fallback = self._fallback
        fallback_call = (lambda: fallback.generate(request)) if fallback is not None else None  # noqa: E731
        return await _call_with_retry_and_fallback(
            "chat", lambda: self._primary.generate(request), fallback_call
        )


class ResilientEmbeddingProvider(EmbeddingProvider):
    def __init__(self, primary: EmbeddingProvider, fallback: EmbeddingProvider | None = None) -> None:
        self._primary = primary
        self._fallback = fallback

    @property
    def capabilities(self) -> ProviderCapabilities:
        return self._primary.capabilities

    async def embed(self, request: EmbedRequest) -> EmbedResponse:
        fallback = self._fallback
        fallback_call = (lambda: fallback.embed(request)) if fallback is not None else None  # noqa: E731
        return await _call_with_retry_and_fallback(
            "embedding", lambda: self._primary.embed(request), fallback_call
        )
