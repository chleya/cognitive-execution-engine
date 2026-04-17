"""Provider boundary for future real LLM calls.

No network call is implemented in Stage 1C5.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Protocol
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

