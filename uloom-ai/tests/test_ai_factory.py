import pytest

from app.core.config import Settings
from app.services.ai_service import factory
from app.services.ai_service.adapters.gemini_adapter import GeminiAdapter
from app.services.ai_service.resilient import ResilientChatProvider, ResilientEmbeddingProvider


@pytest.fixture(autouse=True)
def _reset_factory_state(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(factory, "_gemini_singleton", None)
    factory.get_chat_provider.cache_clear()
    factory.get_embedding_provider.cache_clear()
    yield
    factory.get_chat_provider.cache_clear()
    factory.get_embedding_provider.cache_clear()


def _settings(**overrides) -> Settings:
    return Settings(gemini_api_key="test-key", **overrides)


def test_build_chat_provider_selects_gemini():
    provider = factory._build_chat_provider(_settings(), "gemini")
    assert isinstance(provider, GeminiAdapter)


def test_build_chat_provider_rejects_unknown_provider():
    with pytest.raises(ValueError, match="Unknown AI_CHAT_PROVIDER"):
        factory._build_chat_provider(_settings(), "not-a-provider")


def test_build_embedding_provider_selects_gemini():
    provider = factory._build_embedding_provider(_settings(), "gemini")
    assert isinstance(provider, GeminiAdapter)


def test_build_embedding_provider_rejects_unknown_provider():
    with pytest.raises(ValueError, match="Unknown AI_EMBEDDING_PROVIDER"):
        factory._build_embedding_provider(_settings(), "not-a-provider")


def test_gemini_adapter_is_memoized_across_chat_and_embedding():
    settings = _settings()
    chat = factory._build_chat_provider(settings, "gemini")
    embedding = factory._build_embedding_provider(settings, "gemini")
    assert chat is embedding


def test_get_chat_provider_and_get_embedding_provider_are_cached():
    first = factory.get_chat_provider()
    second = factory.get_chat_provider()
    assert first is second
    assert isinstance(first, ResilientChatProvider)
    assert isinstance(factory.get_embedding_provider(), ResilientEmbeddingProvider)
    # Both wrap the same underlying singleton adapter (NFR-005: no fallback
    # configured by default, so each is just primary-only).
    assert first._primary is factory.get_embedding_provider()._primary  # noqa: SLF001
    assert first._fallback is None  # noqa: SLF001


def test_get_chat_provider_wraps_configured_fallback(monkeypatch: pytest.MonkeyPatch):
    # Fallback name must differ from the primary ("gemini", _settings()'s
    # default) - same-as-primary is the "not configured" case (see the next
    # test), so this uses a distinct placeholder name. _build_chat_provider
    # is mocked below to ignore the name and return a GeminiAdapter either
    # way, since no second real adapter exists yet to name honestly.
    monkeypatch.setattr(factory, "get_settings", lambda: _settings(ai_chat_provider_fallback="claude"))
    monkeypatch.setattr(
        factory,
        "_build_chat_provider",
        lambda settings, name: GeminiAdapter(api_key="k", chat_model="m", embedding_model="e"),
    )
    provider = factory.get_chat_provider()
    assert isinstance(provider, ResilientChatProvider)
    assert provider._fallback is not None  # noqa: SLF001


def test_get_chat_provider_treats_blank_fallback_as_none():
    provider = factory.get_chat_provider()
    assert provider._fallback is None  # noqa: SLF001
