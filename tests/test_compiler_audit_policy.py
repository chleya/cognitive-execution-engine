import hashlib
import json

import pytest

from cee_core import (
    CompilerAuditPolicy,
    StaticLLMTaskCompiler,
    execute_task_with_compiler,
)


def _compiler_response(**overrides):
    payload = {
        "objective": "analyze project risk with model compiler",
        "kind": "analysis",
        "risk_level": "low",
        "success_criteria": ["structured", "policy checked"],
    }
    payload.update(overrides)
    return json.dumps(payload)


def test_compiler_audit_policy_defaults_to_hash_mode():
    compiler = StaticLLMTaskCompiler(response_json=_compiler_response())

    result = execute_task_with_compiler("sensitive raw input", compiler)
    payload = result.event_log.all()[0].payload

    assert payload["raw_input_audit_mode"] == "hash"
    assert payload["raw_input_sha256"] == hashlib.sha256(
        "sensitive raw input".encode("utf-8")
    ).hexdigest()
    assert payload["raw_input_length"] == len("sensitive raw input")
    assert "raw_input" not in payload


def test_compiler_audit_policy_plain_mode_records_raw_input():
    compiler = StaticLLMTaskCompiler(response_json=_compiler_response())

    result = execute_task_with_compiler(
        "plain raw input",
        compiler,
        audit_policy=CompilerAuditPolicy(mode="plain"),
    )
    payload = result.event_log.all()[0].payload

    assert payload["raw_input_audit_mode"] == "plain"
    assert payload["raw_input"] == "plain raw input"


def test_compiler_audit_policy_omit_mode_records_no_raw_input_or_hash():
    compiler = StaticLLMTaskCompiler(response_json=_compiler_response())

    result = execute_task_with_compiler(
        "omitted raw input",
        compiler,
        audit_policy=CompilerAuditPolicy(mode="omit"),
    )
    payload = result.event_log.all()[0].payload

    assert payload == {"raw_input_audit_mode": "omit"}


def test_compiler_audit_policy_rejects_unknown_mode():
    policy = CompilerAuditPolicy(mode="bad")  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="Unsupported compiler audit mode"):
        policy.raw_input_payload("x")
