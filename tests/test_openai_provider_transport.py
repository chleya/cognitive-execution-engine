import json
from types import SimpleNamespace

import pytest

from cee_core import (
    OPENAI_DEFAULT_MODEL,
    OPENAI_ENV_KEY,
    EnvironmentLLMProvider,
    LLMProviderRequest,
    ProviderBackedTaskCompiler,
    build_openai_task_compiler_provider,
    execute_task_with_compiler,
    openai_responses_task_compiler_transport_with_client,
)


def _task_json():
    return json.dumps(
        {
            "objective": "openai compiled task",
            "kind": "analysis",
            "risk_level": "low",
            "success_criteria": ["structured"],
        }
    )


class FakeResponses:
    def __init__(self, output_text):
        self.output_text = output_text
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(output_text=self.output_text)


class FakeClient:
    def __init__(self, output_text):
        self.responses = FakeResponses(output_text)


def test_build_openai_task_compiler_provider_is_env_gated_provider(monkeypatch):
    monkeypatch.delenv("CEE_LLM_MODEL", raising=False)

    provider = build_openai_task_compiler_provider()

    assert isinstance(provider, EnvironmentLLMProvider)
    assert provider.env_key_name == OPENAI_ENV_KEY
    assert provider.model_name == OPENAI_DEFAULT_MODEL
    assert provider.provider_name == "openai"


def test_openai_transport_with_client_uses_responses_json_schema_shape():
    client = FakeClient(output_text=_task_json())
    request = LLMProviderRequest(prompt={"role": "task_compiler", "raw_input": "x"})

    response_text = openai_responses_task_compiler_transport_with_client(
        client=client,
        request=request,
        model_name="test-model",
    )

    call = client.responses.calls[0]

    assert response_text == _task_json()
    assert call["model"] == "test-model"
    assert call["input"][0]["role"] == "system"
    assert call["input"][1]["content"] == "x"
    assert call["text"]["format"]["type"] == "json_schema"
    assert call["text"]["format"]["name"] == "cee_task_spec"
    assert call["text"]["format"]["strict"] is True


def test_openai_transport_rejects_empty_output_text():
    client = FakeClient(output_text="")
    request = LLMProviderRequest(prompt={"role": "task_compiler", "raw_input": "x"})

    with pytest.raises(RuntimeError, match="empty output_text"):
        openai_responses_task_compiler_transport_with_client(
            client=client,
            request=request,
            model_name="test-model",
        )


def test_openai_provider_integrates_with_runtime_through_injected_transport(monkeypatch):
    monkeypatch.setenv("CEE_LLM_API_KEY", "secret")
    provider = EnvironmentLLMProvider(
        env_key_name="CEE_LLM_API_KEY",
        model_name="test-model",
        provider_name="openai",
        transport=lambda request, api_key, model_name: _task_json(),
    )
    compiler = ProviderBackedTaskCompiler(provider=provider)

    result = execute_task_with_compiler("raw input", compiler)

    assert result.task.objective == "openai compiled task"
    assert len(result.allowed_transitions) == 4

    provider_success_events = [
        event
        for event in result.event_log.all()
        if event.event_type == "llm.provider.succeeded"
    ]
    assert provider_success_events[0].payload["provider_name"] == "openai"
