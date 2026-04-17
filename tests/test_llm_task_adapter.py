import json

import pytest

from cee_core import (
    StaticLLMTaskCompiler,
    build_task_compiler_prompt,
    compile_task_with_llm_adapter,
    parse_llm_task_response,
)


def _valid_response(**overrides):
    payload = {
        "objective": "analyze project risk",
        "kind": "analysis",
        "risk_level": "low",
        "task_level": "L1",
        "success_criteria": ["structured task", "policy checked"],
    }
    payload.update(overrides)
    return json.dumps(payload)


def test_build_task_compiler_prompt_forbids_plans_patches_and_tools():
    prompt = build_task_compiler_prompt("analyze project risk")

    instruction = prompt["instruction"]

    assert "Do not produce a plan" in instruction
    assert "Do not produce state patches" in instruction
    assert "Do not request tools" in instruction
    assert prompt["raw_input"] == "analyze project risk"


def test_parse_llm_task_response_accepts_valid_task_payload():
    task = parse_llm_task_response(
        _valid_response(objective="  analyze   project risk  "),
        raw_input="raw text",
    )

    assert task.objective == "analyze project risk"
    assert task.kind == "analysis"
    assert task.risk_level == "low"
    assert task.task_level == "L1"
    assert task.requested_primitives == ("observe", "interpret", "plan", "verify")
    assert task.raw_input == "raw text"


def test_compile_task_with_llm_adapter_uses_compiler_response():
    compiler = StaticLLMTaskCompiler(
        response_json=_valid_response(kind="state_update", risk_level="medium")
    )

    task = compile_task_with_llm_adapter("update project state", compiler)

    assert task.kind == "state_update"
    assert task.risk_level == "medium"
    assert task.task_level == "L1"


def test_parse_llm_task_response_uses_default_primitives_when_missing():
    task = parse_llm_task_response(
        json.dumps(
            {
                "objective": "update project state",
                "kind": "state_update",
                "risk_level": "medium",
                "success_criteria": ["structured task"],
            }
        ),
        raw_input="raw",
    )

    assert task.requested_primitives == (
        "observe",
        "interpret",
        "plan",
        "act",
        "verify",
        "escalate",
    )
    assert task.task_level == "L1"


def test_llm_task_adapter_rejects_invalid_task_level():
    with pytest.raises(ValueError, match="invalid task_level"):
        parse_llm_task_response(_valid_response(task_level="L9"), raw_input="raw")


def test_llm_task_adapter_rejects_invalid_json():
    with pytest.raises(ValueError, match="invalid JSON"):
        parse_llm_task_response("not json", raw_input="raw")


def test_llm_task_adapter_rejects_non_object_json():
    with pytest.raises(ValueError, match="must be a JSON object"):
        parse_llm_task_response("[]", raw_input="raw")


def test_llm_task_adapter_rejects_forbidden_plan_fields():
    with pytest.raises(ValueError, match="forbidden execution fields"):
        parse_llm_task_response(
            _valid_response(candidate_patches=[]),
            raw_input="raw",
        )


def test_llm_task_adapter_rejects_forbidden_tool_fields():
    with pytest.raises(ValueError, match="forbidden execution fields"):
        parse_llm_task_response(
            _valid_response(tool_calls=[]),
            raw_input="raw",
        )


def test_llm_task_adapter_rejects_unexpected_fields():
    with pytest.raises(ValueError, match="unexpected fields"):
        parse_llm_task_response(
            _valid_response(proposed_tool_calls=[]),
            raw_input="raw",
        )


def test_llm_task_adapter_rejects_invalid_kind():
    with pytest.raises(ValueError, match="invalid kind"):
        parse_llm_task_response(_valid_response(kind="execute"), raw_input="raw")


def test_llm_task_adapter_rejects_invalid_risk_level():
    with pytest.raises(ValueError, match="invalid risk_level"):
        parse_llm_task_response(_valid_response(risk_level="critical"), raw_input="raw")


def test_llm_task_adapter_rejects_invalid_requested_primitives():
    with pytest.raises(ValueError, match="Invalid cognitive primitives"):
        parse_llm_task_response(
            _valid_response(requested_primitives=["observe", "invent"]),
            raw_input="raw",
        )


def test_llm_task_adapter_rejects_empty_raw_input_before_compiler():
    compiler = StaticLLMTaskCompiler(response_json=_valid_response())

    with pytest.raises(ValueError, match="raw_input cannot be empty"):
        compile_task_with_llm_adapter("   ", compiler)
