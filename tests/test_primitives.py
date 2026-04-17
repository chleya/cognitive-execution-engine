import pytest

from cee_core import default_primitives_for_task_kind, validate_primitives


def test_default_primitives_for_analysis_task():
    assert default_primitives_for_task_kind("analysis") == (
        "observe",
        "interpret",
        "plan",
        "verify",
    )


def test_default_primitives_for_state_update_task():
    assert default_primitives_for_task_kind("state_update") == (
        "observe",
        "interpret",
        "plan",
        "act",
        "verify",
        "escalate",
    )


def test_validate_primitives_rejects_unknown_values():
    with pytest.raises(ValueError, match="Invalid cognitive primitives"):
        validate_primitives(("observe", "invent"))
