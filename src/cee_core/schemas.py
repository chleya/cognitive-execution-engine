"""Schema version constants and validation helpers."""

from __future__ import annotations

from typing import Mapping


SCHEMA_MAJOR_VERSION = 1
TASK_SCHEMA_VERSION = "cee.task.v1"
PLAN_SCHEMA_VERSION = "cee.plan.v1"
REASONING_STEP_SCHEMA_VERSION = "cee.reasoning_step.v1"
DELIBERATION_EVENT_SCHEMA_VERSION = "cee.deliberation_event.v1"
COMMITMENT_POLICY_SCHEMA_VERSION = "cee.commitment_policy.v1"


def require_schema_version(
    payload: Mapping[str, object],
    expected: str,
    *,
    required: bool = True,
) -> None:
    """Validate schema version with strict major-version rejection."""

    actual = payload.get("schema_version")
    if actual is None:
        if required:
            raise ValueError(f"Missing schema_version; expected {expected}")
        return

    if not isinstance(actual, str):
        raise ValueError("schema_version must be a string")

    if actual == expected:
        return

    actual_major = _extract_major(actual)
    expected_major = _extract_major(expected)
    if actual_major != expected_major:
        raise ValueError(
            f"Unsupported schema major version: {actual}; expected {expected}"
        )

    raise ValueError(f"Unsupported schema version: {actual}; expected {expected}")


def _extract_major(version: str) -> int:
    try:
        suffix = version.rsplit(".v", 1)[1]
        return int(suffix.split(".", 1)[0])
    except (IndexError, ValueError) as exc:
        raise ValueError(f"Invalid schema_version format: {version}") from exc
