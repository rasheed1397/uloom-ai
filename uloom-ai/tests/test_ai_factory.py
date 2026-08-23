import pytest

from app.core.config import Settings
from app.services.ai_service import factory
from app.services.ai_service.adapters.gemini_adapter import GeminiAdapter


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
    provider = factory._build_chat_provider(_settings(ai_chat_provider="gemini"))
    assert isinstance(provider, GeminiAdapter)


def test_build_chat_provider_rejects_unknown_provider():
    with pytest.raises(ValueError, match="Unknown AI_CHAT_PROVIDER"):
        factory._build_chat_provider(_settings(ai_chat_provider="not-a-provider"))


def test_build_embedding_provider_selects_gemini():
    provider = factory._build_embedding_provider(_settings(ai_embedding_provider="gemini"))
    assert isinstance(provider, GeminiAdapter)


def test_build_embedding_provider_rejects_unknown_provider():
    with pytest.raises(ValueError, match="Unknown AI_EMBEDDING_PROVIDER"):
        factory._build_embedding_provider(_settings(ai_embedding_provider="not-a-provider"))


def test_gemini_adapter_is_memoized_across_chat_and_embedding():
    settings = _settings()
    chat = factory._build_chat_provider(settings)
    embedding = factory._build_embedding_provider(settings)
    assert chat is embedding


def test_get_chat_provider_and_get_embedding_provider_are_cached():
    first = factory.get_chat_provider()
    second = factory.get_chat_provider()
    assert first is second
    assert isinstance(first, GeminiAdapter)
    assert factory.get_embedding_provider() is first
