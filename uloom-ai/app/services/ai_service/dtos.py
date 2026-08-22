"""Vendor-neutral request/response DTOs (Detailed Design Sec.5.6, practice #4).

Every adapter translates to/from these shapes at its own boundary. Business
Services (Document Service, Vector Service, Conversation Service) only ever
see these types, never a provider SDK's native request/response objects.
"""
from dataclasses import dataclass, field
from enum import Enum


class ChatRole(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


@dataclass
class ChatMessage:
    role: ChatRole
    content: str


@dataclass
class ChatRequest:
    messages: list[ChatMessage]
    max_output_tokens: int = 1024
    temperature: float = 0.2


@dataclass
class ChatResponse:
    content: str
    finish_reason: str = "stop"
    # Populated by the adapter if the provider reports token usage; optional
    # because not every provider (or model) exposes it uniformly.
    input_tokens: int | None = None
    output_tokens: int | None = None


@dataclass
class EmbedRequest:
    texts: list[str]


@dataclass
class EmbedResponse:
    vectors: list[list[float]]
    dimension: int


@dataclass
class ProviderCapabilities:
    """What a given adapter actually supports (Detailed Design Sec.5.6, practice #6).

    Callers check capabilities rather than assuming every adapter behind
    ChatProvider/EmbeddingProvider can do everything the default (Gemini) can.
    """

    streaming: bool = False
    context_caching: bool = False
    multimodal_embeddings: bool = False
    extra: dict[str, bool] = field(default_factory=dict)
