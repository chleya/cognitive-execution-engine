import json

import pytest

from cee_core import (
    EventLog,
    StaticLLMTaskCompiler,
    execute_task_with_compiler,
    run_result_to_artifact,
)
from cee_core.world_state import WorldState


def _compiler_response(**overrides):
    payload = {
        "objective": "analyze project risk with model compiler",
        "kind": "analysis",
        "risk_level": "low",
        "success_criteria": ["structured", "policy checked"],
        "requested_primitives": ["observe", "interpret", "plan", "verify"],
    }
    payload.update(overrides)
    return json.dumps(payload)


def test_execute_task_with_compiler_runs_full_pipeline():
    compiler = StaticLLMTaskCompiler(response_json=_compiler_response())

    result = execute_task_with_compiler("please analyze this", compiler)

    assert result.task.objective == "analyze project risk with model compiler"
    assert result.reasoning_step.chosen_action == "propose_plan"
    assert result.task.kind == "analysis"
    assert result.task.requested_primitives == (
        "observe",
        "interpret",
        "plan",
        "verify",
    )
    assert len(result.allowed_transitions) == 4
    assert len(result.blocked_transitions) == 0
    assert result.world_state is not None
    assert result.event_log.all()[0].event_type == "task.compiler.requested"
    assert result.event_log.all()[1].event_type == "task.compiler.succeeded"
    assert result.event_log.all()[2].event_type == "reasoning.step.selected"
    assert "raw_input" not in result.event_log.all()[0].payload


def test_execute_task_with_compiler_keeps_raw_input_as_provenance_only():
    compiler = StaticLLMTaskCompiler(response_json=_compiler_response())

    result = execute_task_with_compiler("raw user words", compiler)

    assert result.task.raw_input == "raw user words"
    assert result.plan.objective == "analyze project risk with model compiler"


def test_execute_task_with_compiler_medium_risk_still_requires_approval():
    compiler = StaticLLMTaskCompiler(
        response_json=_compiler_response(
            objective="update project belief summary",
            kind="state_update",
            risk_level="medium",
            requested_primitives=[
                "observe",
                "interpret",
                "plan",
                "act",
                "verify",
                "escalate",
            ],
        )
    )

    result = execute_task_with_compiler("update this", compiler)

    assert len(result.allowed_transitions) == 4
    assert len(result.approval_required_transitions) == 1
    assert result.world_state is not None


def test_execute_task_with_compiler_rejects_invalid_requested_primitives():
    compiler = StaticLLMTaskCompiler(
        response_json=_compiler_response(requested_primitives=["observe", "invent"])
    )

    with pytest.raises(ValueError, match="Invalid cognitive primitives"):
        execute_task_with_compiler("malformed primitives", compiler)


def test_execute_task_with_compiler_result_can_be_artifacted_and_replayed():
    compiler = StaticLLMTaskCompiler(response_json=_compiler_response())
    result = execute_task_with_compiler("please analyze this", compiler)

    artifact = run_result_to_artifact(result)

    if artifact.world_state_snapshot is not None and result.world_state is not None:
        artifact_ws = WorldState.from_dict(artifact.world_state_snapshot)
        assert artifact_ws == result.world_state


def test_execute_task_with_compiler_rejects_forbidden_plan_fields():
    compiler = StaticLLMTaskCompiler(
        response_json=_compiler_response(candidate_patches=[])
    )

    with pytest.raises(ValueError, match="forbidden execution fields"):
        execute_task_with_compiler("malicious compiler", compiler)


def test_execute_task_with_compiler_rejects_forbidden_tool_fields():
    compiler = StaticLLMTaskCompiler(response_json=_compiler_response(tool_calls=[]))

    with pytest.raises(ValueError, match="forbidden execution fields"):
        execute_task_with_compiler("malicious compiler", compiler)


def test_execute_task_with_compiler_uses_existing_event_log():
    log = EventLog()
    compiler = StaticLLMTaskCompiler(response_json=_compiler_response())

    result = execute_task_with_compiler("please analyze this", compiler, event_log=log)

    assert result.event_log is log
    assert len(log.all()) == 11


def test_execute_task_with_compiler_logs_rejected_compiler_output():
    log = EventLog()
    compiler = StaticLLMTaskCompiler(
        response_json=_compiler_response(candidate_patches=[])
    )

    with pytest.raises(ValueError, match="forbidden execution fields"):
        execute_task_with_compiler("malicious compiler", compiler, event_log=log)

    events = log.all()

    assert len(events) == 2
    assert events[0].event_type == "task.compiler.requested"
    assert events[1].event_type == "task.compiler.rejected"
    assert events[1].payload["error_type"] == "ValueError"
    assert "forbidden execution fields" in events[1].payload["error_message"]


def test_execute_task_with_compiler_success_events_are_audit_only_for_replay():
    compiler = StaticLLMTaskCompiler(response_json=_compiler_response())

    result = execute_task_with_compiler("please analyze this", compiler)

    assert len(result.event_log.all()) == 11
    assert result.world_state is not None
