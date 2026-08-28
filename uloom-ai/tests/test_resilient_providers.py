import pytest

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
    ProviderAuthError,
    ProviderTimeoutError,
)
from app.services.ai_service.resilient import ResilientChatProvider, ResilientEmbeddingProvider

_CAPS = ProviderCapabilities(streaming=False, context_caching=False, multimodal_embeddings=False)
_REQUEST = ChatRequest(messages=[])
_RESPONSE = ChatResponse(content="ok", finish_reason="stop", input_tokens=1, output_tokens=1)


class _ScriptedChatProvider(ChatProvider):
    """Returns/raises each entry in `script` in order, one per call."""

    def __init__(self, script: list[Exception | ChatResponse]) -> None:
        self._script = list(script)
        self.calls = 0

    @property
    def capabilities(self) -> ProviderCapabilities:
        return _CAPS

    async def generate(self, request: ChatRequest) -> ChatResponse:
        self.calls += 1
        outcome = self._script.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


@pytest.fixture(autouse=True)
def _no_real_sleep(monkeypatch: pytest.MonkeyPatch):
    async def _instant_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr("app.services.ai_service.resilient.asyncio.sleep", _instant_sleep)


async def test_succeeds_on_first_try_no_retry_no_fallback():
    primary = _ScriptedChatProvider([_RESPONSE])
    provider = ResilientChatProvider(primary)

    result = await provider.generate(_REQUEST)

    assert result is _RESPONSE
    assert primary.calls == 1


async def test_retries_once_after_timeout_then_succeeds():
    primary = _ScriptedChatProvider([ProviderTimeoutError("slow"), _RESPONSE])
    provider = ResilientChatProvider(primary)

    result = await provider.generate(_REQUEST)

    assert result is _RESPONSE
    assert primary.calls == 2


async def test_falls_back_after_two_timeouts_when_fallback_configured():
    primary = _ScriptedChatProvider([ProviderTimeoutError("slow"), ProviderTimeoutError("slow again")])
    fallback = _ScriptedChatProvider([_RESPONSE])
    provider = ResilientChatProvider(primary, fallback)

    result = await provider.generate(_REQUEST)

    assert result is _RESPONSE
    assert primary.calls == 2
    assert fallback.calls == 1


async def test_raises_after_two_timeouts_with_no_fallback_configured():
    primary = _ScriptedChatProvider([ProviderTimeoutError("slow"), ProviderTimeoutError("slow again")])
    provider = ResilientChatProvider(primary)

    with pytest.raises(ProviderTimeoutError):
        await provider.generate(_REQUEST)

    assert primary.calls == 2


async def test_non_timeout_error_skips_retry_and_goes_straight_to_fallback():
    primary = _ScriptedChatProvider([ProviderAuthError("bad key")])
    fallback = _ScriptedChatProvider([_RESPONSE])
    provider = ResilientChatProvider(primary, fallback)

    result = await provider.generate(_REQUEST)

    assert result is _RESPONSE
    assert primary.calls == 1  # no retry wasted on a non-transient failure
    assert fallback.calls == 1


async def test_non_timeout_error_with_no_fallback_raises_immediately():
    primary = _ScriptedChatProvider([ProviderAuthError("bad key")])
    provider = ResilientChatProvider(primary)

    with pytest.raises(ProviderAuthError):
        await provider.generate(_REQUEST)

    assert primary.calls == 1


class _ScriptedEmbeddingProvider(EmbeddingProvider):
    def __init__(self, script: list[Exception | EmbedResponse]) -> None:
        self._script = list(script)
        self.calls = 0

    @property
    def capabilities(self) -> ProviderCapabilities:
        return _CAPS

    async def embed(self, request: EmbedRequest) -> EmbedResponse:
        self.calls += 1
        outcome = self._script.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


async def test_embedding_provider_retries_then_succeeds():
    response = EmbedResponse(vectors=[[0.1, 0.2]], dimension=2)
    primary = _ScriptedEmbeddingProvider([ProviderTimeoutError("slow"), response])
    provider = ResilientEmbeddingProvider(primary)

    result = await provider.embed(EmbedRequest(texts=["hi"]))

    assert result is response
    assert primary.calls == 2
