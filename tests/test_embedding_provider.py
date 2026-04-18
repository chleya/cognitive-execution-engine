"""Tests for real embedding provider implementations."""

import pytest

from cee_core.embedding_provider import (
    EnvironmentEmbeddingProvider,
    build_openai_embedding_provider,
)


class TestEnvironmentEmbeddingProvider:
    def test_requires_env_key(self):
        provider = EnvironmentEmbeddingProvider(
            env_key_name="CEE_TEST_EMBEDDING_KEY",
            model_name="test-model",
            transport=lambda text, key, model: [0.1, 0.2, 0.3],
            provider_name="test",
        )

        with pytest.raises(RuntimeError, match="Missing required provider"):
            provider.get_embedding("test text")

    def test_uses_transport(self, monkeypatch):
        monkeypatch.setenv("CEE_TEST_EMBEDDING_KEY", "test-key")

        call_log = []

        def fake_transport(text, api_key, model):
            call_log.append((text, api_key, model))
            return [0.5, -0.5, 0.0]

        provider = EnvironmentEmbeddingProvider(
            env_key_name="CEE_TEST_EMBEDDING_KEY",
            model_name="test-model",
            transport=fake_transport,
            provider_name="test",
        )

        result = provider.get_embedding("hello world")

        assert result == [0.5, -0.5, 0.0]
        assert len(call_log) == 1
        assert call_log[0][0] == "hello world"
        assert call_log[0][1] == "test-key"
        assert call_log[0][2] == "test-model"

    def test_rejects_empty_embedding(self, monkeypatch):
        monkeypatch.setenv("CEE_TEST_EMBEDDING_KEY", "test-key")

        provider = EnvironmentEmbeddingProvider(
            env_key_name="CEE_TEST_EMBEDDING_KEY",
            model_name="test-model",
            transport=lambda text, key, model: [],
            provider_name="test",
        )

        with pytest.raises(RuntimeError, match="empty embedding"):
            provider.get_embedding("test")


class TestBuildOpenAIEmbeddingProvider:
    def test_default_config(self, monkeypatch):
        monkeypatch.delenv("CEE_EMBEDDING_MODEL", raising=False)

        provider = build_openai_embedding_provider()

        assert provider.env_key_name == "CEE_EMBEDDING_API_KEY"
        assert provider.model_name == "text-embedding-3-small"
        assert provider.provider_name == "openai"

    def test_custom_model(self, monkeypatch):
        monkeypatch.setenv("CEE_EMBEDDING_API_KEY", "key")

        provider = build_openai_embedding_provider(model_name="custom-model")

        assert provider.model_name == "custom-model"

    def test_custom_env_key(self):
        provider = build_openai_embedding_provider(env_key_name="CUSTOM_KEY")

        assert provider.env_key_name == "CUSTOM_KEY"

    def test_integration_with_transport(self, monkeypatch):
        monkeypatch.setenv("CEE_EMBEDDING_API_KEY", "test-key")

        def fake_transport(text, api_key, model):
            return [0.1] * 3

        provider = build_openai_embedding_provider(transport=fake_transport)

        result = provider.get_embedding("test query")

        assert result == [0.1, 0.1, 0.1]
