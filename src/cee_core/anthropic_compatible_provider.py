"""Anthropic-compatible provider boundary.

This supports providers that expose an Anthropic Messages-like endpoint, while
keeping network transport injectable and env-gated.
"""

from __future__ import annotations

import json
import os
import urllib.request
from typing import Any

from .llm_provider import LLMProviderRequest
from .optional_provider import EnvironmentLLMProvider
from .openai_provider import TASK_SPEC_JSON_SCHEMA


ANTHROPIC_COMPAT_ENV_KEY = "CEE_LLM_API_KEY"
ANTHROPIC_COMPAT_BASE_URL_ENV = "CEE_LLM_BASE_URL"
ANTHROPIC_COMPAT_MODEL_ENV = "CEE_LLM_MODEL"
ANTHROPIC_COMPAT_DEFAULT_MODEL = "claude-3-5-sonnet-latest"


def build_anthropic_compatible_task_compiler_provider(
    *,
    env_key_name: str = ANTHROPIC_COMPAT_ENV_KEY,
    base_url: str | None = None,
    model_name: str | None = None,
    provider_name: str = "anthropic-compatible",
) -> EnvironmentLLMProvider:
    """Build an env-gated Anthropic-compatible provider."""

    resolved_base_url = base_url or os.environ.get(ANTHROPIC_COMPAT_BASE_URL_ENV, "")
    if not resolved_base_url:
        raise RuntimeError(
            f"Missing required provider base URL: {ANTHROPIC_COMPAT_BASE_URL_ENV}"
        )

    model = model_name or os.environ.get(
        ANTHROPIC_COMPAT_MODEL_ENV,
        ANTHROPIC_COMPAT_DEFAULT_MODEL,
    )

    def _transport(request: LLMProviderRequest, api_key: str, model_name: str) -> str:
        return anthropic_compatible_messages_transport(
            request=request,
            api_key=api_key,
            model_name=model_name,
            base_url=resolved_base_url,
        )

    return EnvironmentLLMProvider(
        env_key_name=env_key_name,
        model_name=model,
        transport=_transport,
        provider_name=provider_name,
    )


def build_anthropic_compatible_request_body(
    request: LLMProviderRequest,
    model_name: str,
) -> dict[str, object]:
    """Build an Anthropic Messages-like request body."""

    raw_input = str(request.prompt.get("raw_input", ""))
    return {
        "model": model_name,
        "max_tokens": 800,
        "system": (
            "You compile raw user input into JSON for a TaskSpec. "
            "Return only a JSON object with objective, kind, risk_level, and success_criteria. "
            "Do not produce plans, state patches, tool calls, or execution instructions. "
            f"The JSON schema is: {json.dumps(TASK_SPEC_JSON_SCHEMA, ensure_ascii=False)}"
        ),
        "messages": [
            {
                "role": "user",
                "content": raw_input,
            }
        ],
    }


def anthropic_compatible_messages_transport(
    *,
    request: LLMProviderRequest,
    api_key: str,
    model_name: str,
    base_url: str,
) -> str:
    """Call an Anthropic-compatible Messages endpoint using stdlib urllib."""

    body = json.dumps(
        build_anthropic_compatible_request_body(request, model_name),
        ensure_ascii=False,
    ).encode("utf-8")
    http_request = urllib.request.Request(
        base_url,
        data=body,
        headers={
            "content-type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    with urllib.request.urlopen(http_request, timeout=request.timeout_seconds) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return extract_anthropic_compatible_text(payload)


def extract_anthropic_compatible_text(payload: dict[str, Any]) -> str:
    """Extract text from a Messages-like response payload."""

    content = payload.get("content")
    if not isinstance(content, list):
        raise RuntimeError("Anthropic-compatible response missing content list")

    text_parts = []
    for item in content:
        if isinstance(item, dict) and item.get("type") == "text":
            text = item.get("text")
            if isinstance(text, str):
                text_parts.append(text)

    output = "\n".join(text_parts).strip()
    if not output:
        raise RuntimeError("Anthropic-compatible response contained no text")
    return output

