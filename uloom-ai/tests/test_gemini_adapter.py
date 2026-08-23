from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from google.genai import errors as genai_errors

from app.services.ai_service.adapters.gemini_adapter import GeminiAdapter
from app.services.ai_service.dtos import ChatMessage, ChatRequest, ChatRole, EmbedRequest
from app.services.ai_service.interfaces import (
    ProviderAuthError,
    ProviderContentPolicyError,
    ProviderError,
    ProviderRateLimitError,
    ProviderTimeoutError,
)


@pytest.fixture
def adapter() -> GeminiAdapter:
    return GeminiAdapter(
        api_key="test-key", chat_model="gemini-2.5-flash", embedding_model="gemini-embedding-001"
    )


def _client_error(code: int, message: str) -> genai_errors.ClientError:
    return genai_errors.ClientError(code, {"error": {"message": message, "status": "ERROR"}})


def test_capabilities_are_fixed(adapter: GeminiAdapter):
    caps = adapter.capabilities
    assert caps.streaming is True
    assert caps.multimodal_embeddings is False


async def test_generate_returns_normalized_response(adapter: GeminiAdapter):
    fake_response = SimpleNamespace(
        text="Paris.",
        usage_metadata=SimpleNamespace(prompt_token_count=12, candidates_token_count=3),
        candidates=[SimpleNamespace(finish_reason="STOP")],
    )
    adapter._client.aio.models.generate_content = AsyncMock(return_value=fake_response)

    result = await adapter.generate(
        ChatRequest(
            messages=[
                ChatMessage(role=ChatRole.SYSTEM, content="Be concise."),
                ChatMessage(role=ChatRole.USER, content="Capital of France?"),
            ]
        )
    )

    assert result.content == "Paris."
    assert result.finish_reason == "STOP"
    assert result.input_tokens == 12
    assert result.output_tokens == 3


async def test_generate_defaults_when_no_usage_or_candidates(adapter: GeminiAdapter):
    fake_response = SimpleNamespace(text=None, usage_metadata=None, candidates=[])
    adapter._client.aio.models.generate_content = AsyncMock(return_value=fake_response)

    result = await adapter.generate(ChatRequest(messages=[ChatMessage(role=ChatRole.USER, content="hi")]))

    assert result.content == ""
    assert result.finish_reason == "stop"
    assert result.input_tokens is None
    assert result.output_tokens is None


@pytest.mark.parametrize(
    ("code", "message", "expected"),
    [
        (401, "bad key", ProviderAuthError),
        (403, "forbidden", ProviderAuthError),
        (429, "slow down", ProviderRateLimitError),
        (400, "blocked due to Safety policy", ProviderContentPolicyError),
        (500, "server exploded", ProviderError),
    ],
)
async def test_generate_maps_client_errors(adapter: GeminiAdapter, code: int, message: str, expected: type):
    adapter._client.aio.models.generate_content = AsyncMock(side_effect=_client_error(code, message))

    with pytest.raises(expected):
        await adapter.generate(ChatRequest(messages=[ChatMessage(role=ChatRole.USER, content="hi")]))


async def test_generate_maps_timeout_error(adapter: GeminiAdapter):
    adapter._client.aio.models.generate_content = AsyncMock(side_effect=TimeoutError("too slow"))

    with pytest.raises(ProviderTimeoutError):
        await adapter.generate(ChatRequest(messages=[ChatMessage(role=ChatRole.USER, content="hi")]))


async def test_embed_returns_normalized_response(adapter: GeminiAdapter):
    fake_response = SimpleNamespace(
        embeddings=[SimpleNamespace(values=[0.1, 0.2, 0.3]), SimpleNamespace(values=[0.4, 0.5, 0.6])]
    )
    adapter._client.aio.models.embed_content = AsyncMock(return_value=fake_response)

    result = await adapter.embed(EmbedRequest(texts=["a", "b"]))

    assert result.vectors == [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
    assert result.dimension == 3


async def test_embed_returns_empty_when_no_embeddings(adapter: GeminiAdapter):
    adapter._client.aio.models.embed_content = AsyncMock(return_value=SimpleNamespace(embeddings=None))

    result = await adapter.embed(EmbedRequest(texts=["a"]))

    assert result.vectors == []
    assert result.dimension == 0


async def test_embed_raises_when_provider_returns_no_values(adapter: GeminiAdapter):
    fake_response = SimpleNamespace(embeddings=[SimpleNamespace(values=None)])
    adapter._client.aio.models.embed_content = AsyncMock(return_value=fake_response)

    with pytest.raises(ProviderError):
        await adapter.embed(EmbedRequest(texts=["a"]))


async def test_embed_maps_client_errors(adapter: GeminiAdapter):
    adapter._client.aio.models.embed_content = AsyncMock(side_effect=_client_error(429, "slow down"))

    with pytest.raises(ProviderRateLimitError):
        await adapter.embed(EmbedRequest(texts=["a"]))


async def test_embed_maps_timeout_error(adapter: GeminiAdapter):
    adapter._client.aio.models.embed_content = AsyncMock(side_effect=TimeoutError("too slow"))

    with pytest.raises(ProviderTimeoutError):
        await adapter.embed(EmbedRequest(texts=["a"]))
