import json

import pytest

from cee_core import (
    EventLog,
    FailingLLMProvider,
    LLMProviderError,
    LLMProviderRequest,
    ProviderBackedTaskCompiler,
    StaticLLMProvider,
    execute_task_with_compiler,
)


def _response_json(**overrides):
    payload = {
        "objective": "provider compiled task",
        "kind": "analysis",
        "risk_level": "low",
        "success_criteria": ["structured"],
    }
    payload.update(overrides)
    return json.dumps(payload)


def test_static_provider_returns_provider_neutral_response():
    provider = StaticLLMProvider(response_text="{}")
    request = LLMProviderRequest(prompt={"raw_input": "x"})

    response = provider.complete(request)

    assert response.request_id == request.request_id
    assert response.response_text == "{}"
    assert response.provider_name == "static"
    assert response.model_name == "static-model"


def test_provider_backed_task_compiler_runs_through_runtime():
    provider = StaticLLMProvider(response_text=_response_json())
    log = EventLog()
    compiler = ProviderBackedTaskCompiler(provider=provider, event_log=log)

    result = execute_task_with_compiler("raw input", compiler, event_log=log)

    assert result.task.objective == "provider compiled task"
    assert len(result.allowed_transitions) == 4
    assert result.world_state is not None
    event_types = [event.event_type for event in result.event_log.all()]
    assert "llm.provider.requested" in event_types
    assert "llm.provider.succeeded" in event_types


def test_provider_backed_task_compiler_rejects_provider_plan_field_response():
    provider = StaticLLMProvider(response_text=_response_json(candidate_patches=[]))
    compiler = ProviderBackedTaskCompiler(provider=provider)

    with pytest.raises(ValueError, match="forbidden execution fields"):
        execute_task_with_compiler("raw input", compiler)


def test_failing_provider_exposes_error_envelope_in_runtime_error():
    provider = FailingLLMProvider(kind="timeout", message="request timed out")
    log = EventLog()
    compiler = ProviderBackedTaskCompiler(provider=provider, event_log=log)

    with pytest.raises(RuntimeError) as exc:
        execute_task_with_compiler("raw input", compiler, event_log=log)

    error = exc.value.args[0]

    assert isinstance(error, LLMProviderError)
    assert error.kind == "timeout"
    assert error.message == "request timed out"
    event_types = [event.event_type for event in log.all()]
    assert "llm.provider.requested" in event_types
    assert "llm.provider.failed" in event_types


def test_provider_success_audit_does_not_record_full_response_text():
    provider = StaticLLMProvider(response_text=_response_json())
    log = EventLog()
    compiler = ProviderBackedTaskCompiler(provider=provider, event_log=log)

    execute_task_with_compiler("raw input", compiler, event_log=log)

    success_events = [
        event for event in log.all() if event.event_type == "llm.provider.succeeded"
    ]

    assert len(success_events) == 1
    assert "response_length" in success_events[0].payload
    assert "response_text" not in success_events[0].payload


def test_runtime_attaches_event_log_to_provider_backed_compiler_when_missing():
    provider = StaticLLMProvider(response_text=_response_json())
    compiler = ProviderBackedTaskCompiler(provider=provider)

    result = execute_task_with_compiler("raw input", compiler)

    event_types = [event.event_type for event in result.event_log.all()]
    assert "llm.provider.requested" in event_types
    assert "llm.provider.succeeded" in event_types
    assert compiler.event_log is None


def test_provider_backed_task_compiler_bind_event_log_returns_new_instance():
    provider = StaticLLMProvider(response_text=_response_json())
    compiler = ProviderBackedTaskCompiler(provider=provider)
    log = EventLog()

    bound = compiler.bind_event_log(log)

    assert bound is not compiler
    assert bound.event_log is log
    assert compiler.event_log is None
