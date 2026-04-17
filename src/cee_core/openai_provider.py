"""Optional OpenAI provider transport.

This module is env-gated and keeps OpenAI-specific behavior outside runtime.
Unit tests use fake clients and do not require network access.
"""

from __future__ import annotations

import os
from typing import Any

from .llm_provider import LLMProviderRequest
from .optional_provider import EnvironmentLLMProvider


OPENAI_ENV_KEY = "CEE_LLM_API_KEY"
OPENAI_MODEL_ENV = "CEE_LLM_MODEL"
OPENAI_DEFAULT_MODEL = "gpt-4o-mini"


TASK_SPEC_JSON_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {
        "objective": {
            "type": "string",
            "description": "Normalized task objective.",
        },
        "kind": {
            "type": "string",
            "enum": ["analysis", "state_update"],
            "description": "Task kind. Use state_update for write/update intent.",
        },
        "risk_level": {
            "type": "string",
            "enum": ["low", "medium", "high"],
            "description": "Risk estimate for the task.",
        },
        "task_level": {
            "type": "string",
            "enum": ["L0", "L1", "L2", "L3", "L4"],
            "description": "Bounded task level from smallest lookup to highest-impact task.",
        },
        "success_criteria": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Concrete success criteria.",
        },
    },
    "required": ["objective", "kind", "risk_level", "success_criteria"],
    "additionalProperties": False,
}


def build_openai_task_compiler_provider(
    *,
    env_key_name: str = OPENAI_ENV_KEY,
    model_name: str | None = None,
) -> EnvironmentLLMProvider:
    """Build an env-gated OpenAI provider using the Responses API transport."""

    return EnvironmentLLMProvider(
        env_key_name=env_key_name,
        model_name=model_name or os.environ.get(OPENAI_MODEL_ENV, OPENAI_DEFAULT_MODEL),
        transport=openai_responses_task_compiler_transport,
        provider_name="openai",
    )


def openai_responses_task_compiler_transport(
    request: LLMProviderRequest,
    api_key: str,
    model_name: str,
) -> str:
    """Call OpenAI Responses API for TaskSpec structured output."""

    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError(
            "OpenAI SDK is not installed. Install the official `openai` package "
            "before using the OpenAI transport."
        ) from exc

    return openai_responses_task_compiler_transport_with_client(
        client=OpenAI(api_key=api_key),
        request=request,
        model_name=model_name,
    )


def openai_responses_task_compiler_transport_with_client(
    *,
    client: Any,
    request: LLMProviderRequest,
    model_name: str,
) -> str:
    """Responses API transport with injectable client for tests."""

    response = client.responses.create(
        model=model_name,
        input=[
            {
                "role": "system",
                "content": (
                    "You compile raw user input into JSON for a TaskSpec. "
                    "Return only fields allowed by the schema. "
                    "Do not produce plans, state patches, tool calls, or execution instructions."
                ),
            },
            {
                "role": "user",
                "content": str(request.prompt.get("raw_input", "")),
            },
        ],
        text={
            "format": {
                "type": "json_schema",
                "name": "cee_task_spec",
                "strict": True,
                "schema": TASK_SPEC_JSON_SCHEMA,
            }
        },
        timeout=request.timeout_seconds,
    )

    output_text = getattr(response, "output_text", None)
    if not isinstance(output_text, str) or not output_text.strip():
        raise RuntimeError("OpenAI Responses API returned empty output_text")

    return output_text
