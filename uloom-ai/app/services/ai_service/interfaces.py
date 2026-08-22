"""AI Service capability interfaces (Detailed Design Sec.5.5/5.6, practice #1).

ChatProvider and EmbeddingProvider are kept separate even when a single
adapter implements both (GeminiAdapter does, for v1). This is what makes
de-consolidating to two vendors later (e.g., swap only embeddings to Voyage)
a one-adapter change instead of a rewrite.

Exact method signatures below are the concrete resolution of the "AI Service
interface signatures" item that was open in Detailed Design Section 6.
"""
from abc import ABC, abstractmethod

from app.services.ai_service.dtos import (
    ChatRequest,
    ChatResponse,
    EmbedRequest,
    EmbedResponse,
    ProviderCapabilities,
)


class ChatProvider(ABC):
    """Text generation capability. Implemented by GeminiAdapter for v1;
    ClaudeAdapter / OpenAIAdapter / OllamaAdapter are alternates (SRS Sec.7)."""

    @abstractmethod
    async def generate(self, request: ChatRequest) -> ChatResponse: ...

    @property
    @abstractmethod
    def capabilities(self) -> ProviderCapabilities: ...


class EmbeddingProvider(ABC):
    """Embedding capability. Implemented by GeminiAdapter for v1;
    VoyageAdapter / OpenAIAdapter / HuggingFaceAdapter are alternates (SRS Sec.7)."""

    @abstractmethod
    async def embed(self, request: EmbedRequest) -> EmbedResponse: ...

    @property
    @abstractmethod
    def capabilities(self) -> ProviderCapabilities: ...


class ProviderError(Exception):
    """Base class for normalized provider errors (Detailed Design Sec.5.6, practice #5).
    Adapters catch vendor-specific exceptions and re-raise as one of these,
    so retry/fallback logic (NFR-005, SRS Sec.9) is written once."""


class ProviderTimeoutError(ProviderError): ...


class ProviderRateLimitError(ProviderError): ...


class ProviderAuthError(ProviderError): ...


class ProviderContentPolicyError(ProviderError): ...
