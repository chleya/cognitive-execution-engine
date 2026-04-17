"""Unified failure mode classification.

Every runtime failure in CEE maps to one of these modes. This enables:
- quality metrics to track failure distribution
- audit trail to record failure categories
- diagnosis to reason about failure patterns

Failure modes are ordered by severity: constraint violations are most
serious because they indicate a policy or safety boundary was challenged.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class FailureMode(Enum):
    """Canonical failure mode for the CEE runtime."""

    POLICY_VIOLATION = "policy_violation"
    SCHEMA_INVALID = "schema_invalid"
    INPUT_INVALID = "input_invalid"
    STATE_CONSTRAINT = "state_constraint"
    TOOL_FAILURE = "tool_failure"
    PROVIDER_FAILURE = "provider_failure"
    CONFIGURATION_ERROR = "configuration_error"


_FAILURE_REASONS: dict[FailureMode, str] = {
    FailureMode.POLICY_VIOLATION: "a policy boundary was challenged",
    FailureMode.SCHEMA_INVALID: "a schema version or structure was invalid",
    FailureMode.INPUT_INVALID: "raw input or LLM output was invalid",
    FailureMode.STATE_CONSTRAINT: "a state transition constraint was violated",
    FailureMode.TOOL_FAILURE: "a tool execution failed",
    FailureMode.PROVIDER_FAILURE: "an LLM provider call failed",
    FailureMode.CONFIGURATION_ERROR: "a configuration or setup value was invalid",
}


def describe_failure_mode(mode: FailureMode) -> str:
    return _FAILURE_REASONS[mode]


def classify_exception(exc: Exception) -> FailureMode:
    """Classify a Python exception into a canonical failure mode."""

    message = str(exc).lower()

    if isinstance(exc, PermissionError):
        return FailureMode.POLICY_VIOLATION

    if isinstance(exc, TypeError):
        if "event" in message or "eventrecord" in message:
            return FailureMode.SCHEMA_INVALID
        return FailureMode.INPUT_INVALID

    if isinstance(exc, RuntimeError):
        if "provider" in message or "api" in message or "openai" in message:
            return FailureMode.PROVIDER_FAILURE
        if "tool" in message:
            return FailureMode.TOOL_FAILURE
        return FailureMode.PROVIDER_FAILURE

    if isinstance(exc, ValueError):
        if "schema" in message or "version" in message:
            return FailureMode.SCHEMA_INVALID
        if "patch" in message or "section" in message or "append" in message:
            return FailureMode.STATE_CONSTRAINT
        if "config" in message or "threshold" in message or "domain" in message:
            return FailureMode.CONFIGURATION_ERROR
        if "policy" in message or "approval" in message:
            return FailureMode.POLICY_VIOLATION
        if "tool" in message:
            return FailureMode.TOOL_FAILURE
        if "empty" in message or "invalid" in message or "cannot" in message:
            return FailureMode.INPUT_INVALID
        return FailureMode.INPUT_INVALID

    return FailureMode.CONFIGURATION_ERROR


@dataclass(frozen=True)
class FailureRecord:
    mode: FailureMode
    exception_type: str
    message: str
    source_module: str

    def to_dict(self) -> dict[str, str]:
        return {
            "failure_mode": self.mode.value,
            "exception_type": self.exception_type,
            "message": self.message,
            "source_module": self.source_module,
        }


def record_failure(
    exc: Exception,
    source_module: str = "",
) -> FailureRecord:
    return FailureRecord(
        mode=classify_exception(exc),
        exception_type=type(exc).__name__,
        message=str(exc),
        source_module=source_module,
    )
