import json

import pytest

from cee_core import (
    ANTHROPIC_COMPAT_BASE_URL_ENV,
    EnvironmentLLMProvider,
    LLMProviderRequest,
    ProviderBackedTaskCompiler,
    build_anthropic_compatible_request_body,
    build_anthropic_compatible_task_compiler_provider,
    execute_task_with_compiler,
    extract_anthropic_compatible_text,
)


def _task_json():
    return json.dumps(
        {
            "objective": "anthropic compatible compiled task",
            "kind": "analysis",
            "risk_level": "low",
            "success_criteria": ["structured"],
        }
    )


def test_build_anthropic_compatible_provider_requires_base_url(monkeypatch):
    monkeypatch.delenv(ANTHROPIC_COMPAT_BASE_URL_ENV, raising=False)

    with pytest.raises(RuntimeError, match="Missing required provider base URL"):
        build_anthropic_compatible_task_compiler_provider()


def test_build_anthropic_compatible_provider_is_env_gated(monkeypatch):
    monkeypatch.setenv(ANTHROPIC_COMPAT_BASE_URL_ENV, "https://example.test/messages")

    provider = build_anthropic_compatible_task_compiler_provider(
        provider_name="minimax-anthropic"
    )

    assert isinstance(provider, EnvironmentLLMProvider)
    assert provider.provider_name == "minimax-anthropic"
    assert provider.model_name


def test_build_anthropic_compatible_request_body_contains_task_compiler_constraints():
    request = LLMProviderRequest(prompt={"raw_input": "analyze risk"})

    body = build_anthropic_compatible_request_body(request, "test-model")

    assert body["model"] == "test-model"
    assert body["messages"] == [{"role": "user", "content": "analyze risk"}]
    assert "TaskSpec" in body["system"] or "objective" in body["system"]
    assert "success_criteria" in body["system"]


def test_extract_anthropic_compatible_text_from_content_blocks():
    payload = {"content": [{"type": "text", "text": _task_json()}]}

    assert extract_anthropic_compatible_text(payload) == _task_json()


def test_extract_anthropic_compatible_text_rejects_missing_text():
    with pytest.raises(RuntimeError, match="contained no text"):
        extract_anthropic_compatible_text({"content": [{"type": "image"}]})


def test_anthropic_compatible_provider_integrates_with_runtime_via_fake_transport(
    monkeypatch,
):
    monkeypatch.setenv("CEE_LLM_API_KEY", "secret")

    provider = EnvironmentLLMProvider(
        env_key_name="CEE_LLM_API_KEY",
        model_name="test-model",
        provider_name="minimax-anthropic",
        transport=lambda request, api_key, model_name: _task_json(),
    )
    compiler = ProviderBackedTaskCompiler(provider=provider)

    result = execute_task_with_compiler("raw input", compiler)

    assert result.task.objective == "anthropic compatible compiled task"
    assert len(result.allowed_transitions) == 4
