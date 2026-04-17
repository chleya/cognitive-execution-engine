"""Optional provider implementation boundary.

This module defines an environment-gated provider shell. It does not perform
network I/O by itself; callers must inject a transport function.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Callable

from .llm_provider import LLMProviderRequest, LLMProviderResponse


ProviderTransport = Callable[[LLMProviderRequest, str, str], str]


@dataclass(frozen=True)
class EnvironmentLLMProvider:
    """Environment-gated provider using an injected transport."""

    env_key_name: str
    model_name: str
    transport: ProviderTransport
    provider_name: str = "environment"

    def complete(self, request: LLMProviderRequest) -> LLMProviderResponse:
        api_key = os.environ.get(self.env_key_name)
        if not api_key:
            raise RuntimeError(
                f"Missing required provider environment variable: {self.env_key_name}"
            )

        response_text = self.transport(request, api_key, self.model_name)
        if not isinstance(response_text, str) or not response_text.strip():
            raise RuntimeError("Provider transport returned empty response text")

        return LLMProviderResponse(
            request_id=request.request_id,
            response_text=response_text,
            provider_name=self.provider_name,
            model_name=self.model_name,
        )


def build_disabled_provider_transport(provider_name: str) -> ProviderTransport:
    """Return a transport that makes accidental network use explicit."""

    def _transport(
        request: LLMProviderRequest,
        api_key: str,
        model_name: str,
    ) -> str:
        raise RuntimeError(
            f"{provider_name} transport is not implemented; no network call was made"
        )

    return _transport

