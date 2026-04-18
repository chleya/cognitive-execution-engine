"""Provider boundary for future real LLM calls.

No network call is implemented in Stage 1C5.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Protocol, List
from uuid import uuid4


ProviderErrorKind = Literal["timeout", "rate_limited", "invalid_response", "provider_error"]


@dataclass(frozen=True)
class LLMProviderRequest:
    """Provider-neutral request envelope."""

    prompt: dict[str, object]
    request_id: str = field(default_factory=lambda: f"llmreq_{uuid4().hex}")
    timeout_seconds: float = 30.0


@dataclass(frozen=True)
class LLMProviderResponse:
    """Provider-neutral successful response envelope."""

    request_id: str
    response_text: str
    provider_name: str
    model_name: str


@dataclass(frozen=True)
class LLMProviderError:
    """Provider-neutral error envelope."""

    request_id: str
    kind: ProviderErrorKind
    message: str
    provider_name: str


class LLMProvider(Protocol):
    """Protocol for a future model provider adapter."""

    provider_name: str

    def complete(self, request: LLMProviderRequest) -> LLMProviderResponse:
        """Return a provider-neutral response or raise provider-specific errors."""


class EmbeddingProvider(Protocol):
    """Protocol for embedding providers."""

    provider_name: str

    def get_embedding(self, text: str) -> List[float]:
        """Get embedding vector for text."""


@dataclass(frozen=True)
class StaticEmbeddingProvider:
    """Deterministic embedding provider stub for tests."""

    provider_name: str = "static-embedding"
    embedding_dim: int = 1536

    def get_embedding(self, text: str) -> List[float]:
        """Return a deterministic embedding based on text hash."""
        import hashlib
        hash_bytes = hashlib.sha256(text.encode()).digest()
        hash_int = int.from_bytes(hash_bytes, byteorder='big')
        
        embedding = []
        for i in range(self.embedding_dim):
            val = ((hash_int >> (i % 64)) & 0xFF) / 255.0
            embedding.append(val * 2 - 1)
        
        norm = sum(x * x for x in embedding) ** 0.5
        if norm > 0:
            embedding = [x / norm for x in embedding]
        
        return embedding


# Global default provider instances
_default_embedding_provider: EmbeddingProvider | None = None


def get_default_embedding_provider() -> EmbeddingProvider:
    """Get the default embedding provider."""
    global _default_embedding_provider
    if _default_embedding_provider is None:
        _default_embedding_provider = StaticEmbeddingProvider()
    return _default_embedding_provider


@dataclass(frozen=True)
class StaticLLMProvider:
    """Deterministic provider stub for adapter boundary tests."""

    response_text: str
    provider_name: str = "static"
    model_name: str = "static-model"

    def complete(self, request: LLMProviderRequest) -> LLMProviderResponse:
        return LLMProviderResponse(
            request_id=request.request_id,
            response_text=self.response_text,
            provider_name=self.provider_name,
            model_name=self.model_name,
        )


@dataclass(frozen=True)
class FailingLLMProvider:
    """Deterministic failing provider stub for error-path tests."""

    kind: ProviderErrorKind
    message: str
    provider_name: str = "static-failing"

    def complete(self, request: LLMProviderRequest) -> LLMProviderResponse:
        raise RuntimeError(
            LLMProviderError(
                request_id=request.request_id,
                kind=self.kind,
                message=self.message,
                provider_name=self.provider_name,
            )
        )


@dataclass(frozen=True)
class OpenAIProvider:
    """OpenAI provider implementing LLMProvider Protocol."""

    api_key: str
    model_name: str = "gpt-4o-mini"
    provider_name: str = "openai"
    base_url: str | None = None

    def complete(self, request: LLMProviderRequest) -> LLMProviderResponse:
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError(
                "OpenAI SDK is not installed. Install the official `openai` package "
                "before using the OpenAI provider."
            ) from exc

        client_kwargs = {"api_key": self.api_key}
        if self.base_url:
            client_kwargs["base_url"] = self.base_url

        client = OpenAI(**client_kwargs)

        messages = self._build_messages(request.prompt)

        try:
            response = client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                timeout=request.timeout_seconds,
            )
        except Exception as exc:
            error_kind = self._classify_openai_error(exc)
            raise RuntimeError(
                LLMProviderError(
                    request_id=request.request_id,
                    kind=error_kind,
                    message=str(exc),
                    provider_name=self.provider_name,
                )
            ) from exc

        response_text = response.choices[0].message.content
        if not response_text:
            raise RuntimeError(
                LLMProviderError(
                    request_id=request.request_id,
                    kind="invalid_response",
                    message="OpenAI returned empty response content",
                    provider_name=self.provider_name,
                )
            )

        return LLMProviderResponse(
            request_id=request.request_id,
            response_text=response_text,
            provider_name=self.provider_name,
            model_name=self.model_name,
        )

    def _build_messages(self, prompt: dict[str, object]) -> list[dict[str, str]]:
        role = prompt.get("role", "user")
        content = prompt.get("instruction", "")
        task_info = prompt.get("task", {})
        context = prompt.get("context", "")

        system_message = {
            "role": "system",
            "content": str(content),
        }

        user_parts = []
        if task_info:
            user_parts.append(f"Task: {self._format_task_info(task_info)}")
        if context:
            user_parts.append(f"Context: {context}")

        user_message = {
            "role": "user",
            "content": "\n\n".join(user_parts) if user_parts else "Proceed with the task.",
        }

        return [system_message, user_message]

    def _format_task_info(self, task_info: dict[str, object]) -> str:
        parts = []
        for key, value in task_info.items():
            if isinstance(value, (list, tuple)):
                parts.append(f"{key}: {', '.join(str(v) for v in value)}")
            else:
                parts.append(f"{key}: {value}")
        return "\n".join(parts)

    def _classify_openai_error(self, exc: Exception) -> ProviderErrorKind:
        error_str = str(exc).lower()
        if "timeout" in error_str or "timed out" in error_str:
            return "timeout"
        if "rate limit" in error_str or "429" in error_str:
            return "rate_limited"
        if "invalid" in error_str or "format" in error_str:
            return "invalid_response"
        return "provider_error"


def get_api_key_from_env() -> str:
    """Get API key from environment variables."""
    import os
    api_key = os.environ.get("CEE_LLM_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "No API key found. Set CEE_LLM_API_KEY or OPENAI_API_KEY environment variable."
        )
    return api_key
