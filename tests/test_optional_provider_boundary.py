import json

import pytest

from cee_core import (
    EnvironmentLLMProvider,
    LLMProviderRequest,
    ProviderBackedTaskCompiler,
    build_disabled_provider_transport,
    execute_task_with_compiler,
)


def _task_json():
    return json.dumps(
        {
            "objective": "environment provider task",
            "kind": "analysis",
            "risk_level": "low",
            "success_criteria": ["structured"],
        }
    )


def test_environment_provider_requires_env_key(monkeypatch):
    monkeypatch.delenv("CEE_TEST_PROVIDER_KEY", raising=False)
    provider = EnvironmentLLMProvider(
        env_key_name="CEE_TEST_PROVIDER_KEY",
        model_name="test-model",
        transport=lambda request, api_key, model_name: _task_json(),
    )

    with pytest.raises(RuntimeError, match="Missing required provider environment"):
        provider.complete(LLMProviderRequest(prompt={"role": "task_compiler"}))


def test_environment_provider_uses_injected_transport(monkeypatch):
    monkeypatch.setenv("CEE_TEST_PROVIDER_KEY", "secret")
    seen = {}

    def transport(request, api_key, model_name):
        seen["request_id"] = request.request_id
        seen["api_key"] = api_key
        seen["model_name"] = model_name
        return _task_json()

    provider = EnvironmentLLMProvider(
        env_key_name="CEE_TEST_PROVIDER_KEY",
        model_name="test-model",
        transport=transport,
        provider_name="test-provider",
    )
    request = LLMProviderRequest(prompt={"role": "task_compiler"})

    response = provider.complete(request)

    assert response.request_id == request.request_id
    assert response.provider_name == "test-provider"
    assert response.model_name == "test-model"
    assert response.response_text == _task_json()
    assert seen == {
        "request_id": request.request_id,
        "api_key": "secret",
        "model_name": "test-model",
    }


def test_environment_provider_integrates_with_task_compiler(monkeypatch):
    monkeypatch.setenv("CEE_TEST_PROVIDER_KEY", "secret")
    provider = EnvironmentLLMProvider(
        env_key_name="CEE_TEST_PROVIDER_KEY",
        model_name="test-model",
        transport=lambda request, api_key, model_name: _task_json(),
        provider_name="test-provider",
    )
    compiler = ProviderBackedTaskCompiler(provider=provider)

    result = execute_task_with_compiler("raw input", compiler)

    assert result.task.objective == "environment provider task"
    assert len(result.allowed_transitions) == 4
    event_types = [event.event_type for event in result.event_log.all()]
    assert "llm.provider.requested" in event_types
    assert "llm.provider.succeeded" in event_types


def test_disabled_provider_transport_never_makes_network_call(monkeypatch):
    monkeypatch.setenv("CEE_TEST_PROVIDER_KEY", "secret")
    provider = EnvironmentLLMProvider(
        env_key_name="CEE_TEST_PROVIDER_KEY",
        model_name="test-model",
        transport=build_disabled_provider_transport("test-provider"),
        provider_name="test-provider",
    )

    with pytest.raises(RuntimeError, match="not implemented; no network call"):
        provider.complete(LLMProviderRequest(prompt={"role": "task_compiler"}))
