import pytest

from cee_core import (
    FailureMode,
    FailureRecord,
    classify_exception,
    describe_failure_mode,
    record_failure,
)


def test_classify_permission_error_as_policy_violation():
    exc = PermissionError("Policy blocked state transition: deny")
    assert classify_exception(exc) == FailureMode.POLICY_VIOLATION


def test_classify_type_error_event_as_schema_invalid():
    exc = TypeError("Expected EventRecord, got str")
    assert classify_exception(exc) == FailureMode.SCHEMA_INVALID


def test_classify_type_error_other_as_input_invalid():
    exc = TypeError("unsupported operand type")
    assert classify_exception(exc) == FailureMode.INPUT_INVALID


def test_classify_value_error_schema_as_schema_invalid():
    exc = ValueError("Unsupported schema version: 99; expected 1")
    assert classify_exception(exc) == FailureMode.SCHEMA_INVALID


def test_classify_value_error_patch_as_state_constraint():
    exc = ValueError("Section is not patchable: unknown")
    assert classify_exception(exc) == FailureMode.STATE_CONSTRAINT


def test_classify_value_error_empty_input():
    exc = ValueError("raw_input cannot be empty")
    assert classify_exception(exc) == FailureMode.INPUT_INVALID


def test_classify_value_error_config():
    exc = ValueError("approval_threshold must be between 0.0 and 1.0")
    assert classify_exception(exc) == FailureMode.CONFIGURATION_ERROR


def test_classify_runtime_error_provider():
    exc = RuntimeError("OpenAI API request failed: timeout")
    assert classify_exception(exc) == FailureMode.PROVIDER_FAILURE


def test_describe_failure_mode_returns_reason():
    reason = describe_failure_mode(FailureMode.POLICY_VIOLATION)
    assert "policy" in reason.lower()


def test_record_failure_creates_failure_record():
    exc = ValueError("raw_input cannot be empty")
    record = record_failure(exc, source_module="tasks")

    assert isinstance(record, FailureRecord)
    assert record.mode == FailureMode.INPUT_INVALID
    assert record.exception_type == "ValueError"
    assert record.source_module == "tasks"


def test_failure_record_to_dict():
    record = FailureRecord(
        mode=FailureMode.STATE_CONSTRAINT,
        exception_type="ValueError",
        message="Section is not patchable",
        source_module="state",
    )

    d = record.to_dict()
    assert d["failure_mode"] == "state_constraint"
    assert d["exception_type"] == "ValueError"
    assert d["source_module"] == "state"


def test_all_failure_modes_have_descriptions():
    for mode in FailureMode:
        desc = describe_failure_mode(mode)
        assert len(desc) > 0
