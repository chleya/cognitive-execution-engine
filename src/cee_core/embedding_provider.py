"""Real embedding provider implementations.

Extends the static embedding provider with actual API-based embeddings
while maintaining the same protocol interface and env-gating pattern.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import List, Protocol, Callable

from .llm_provider import EmbeddingProvider


EmbeddingProviderTransport = Callable[[str, str, str], List[float]]


@dataclass(frozen=True)
class OpenAIEmbeddingProvider:
    """OpenAI embedding provider using the official SDK."""

    api_key: str
    model_name: str = "text-embedding-3-small"
    provider_name: str = "openai"
    embedding_dim: int = 1536

    def get_embedding(self, text: str) -> List[float]:
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError(
                "OpenAI SDK is not installed. Install the official `openai` package "
                "before using the OpenAI embedding provider."
            ) from exc

        client = OpenAI(api_key=self.api_key)
        response = client.embeddings.create(
            input=[text],
            model=self.model_name,
        )
        return response.data[0].embedding


@dataclass(frozen=True)
class EnvironmentEmbeddingProvider:
    """Environment-gated embedding provider using an injected transport."""

    env_key_name: str
    model_name: str
    transport: EmbeddingProviderTransport
    provider_name: str = "environment"
    embedding_dim: int = 1536

    def get_embedding(self, text: str) -> List[float]:
        api_key = os.environ.get(self.env_key_name)
        if not api_key:
            raise RuntimeError(
                f"Missing required provider environment variable: {self.env_key_name}"
            )

        embedding = self.transport(text, api_key, self.model_name)
        if not embedding:
            raise RuntimeError("Provider transport returned empty embedding")

        return embedding


OPENAI_EMBEDDING_ENV_KEY = "CEE_EMBEDDING_API_KEY"
OPENAI_EMBEDDING_MODEL_ENV = "CEE_EMBEDDING_MODEL"
OPENAI_EMBEDDING_DEFAULT_MODEL = "text-embedding-3-small"


def build_openai_embedding_provider(
    *,
    env_key_name: str = OPENAI_EMBEDDING_ENV_KEY,
    model_name: str | None = None,
    transport: Callable[[str, str, str], List[float]] | None = None,
) -> EnvironmentEmbeddingProvider:
    """Build an env-gated OpenAI embedding provider."""

    def _openai_transport(text: str, api_key: str, model_name: str) -> List[float]:
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError(
                "OpenAI SDK is not installed. Install the official `openai` package "
                "before using the OpenAI embedding transport."
            ) from exc

        client = OpenAI(api_key=api_key)
        response = client.embeddings.create(
            input=[text],
            model=model_name,
        )
        return response.data[0].embedding

    return EnvironmentEmbeddingProvider(
        env_key_name=env_key_name,
        model_name=model_name or os.environ.get(OPENAI_EMBEDDING_MODEL_ENV, OPENAI_EMBEDDING_DEFAULT_MODEL),
        transport=transport or _openai_transport,
        provider_name="openai",
    )
