import pytest

from cee_core import (
    DomainContext,
    assess_handoff_stage_gates,
    deliberate_next_action,
    load_handoff_state,
)
from cee_core.tasks import TaskSpec


def test_propose_redirect_in_candidate_actions_when_missing_info():
    task = TaskSpec(
        task_id="t_explore",
        objective="analyze unknown system",
        kind="analysis",
        success_criteria=("find relevant modules",),
        requested_primitives=(),
        risk_level="medium",
        domain_name="core",
        task_level="L1",
    )

    step = deliberate_next_action(
        task,
        tool_registry=None,
    )

    assert "propose_redirect" in step.candidate_actions


def test_explore_mode_blocks_edit_if_needed():
    payload = load_handoff_state("F:\\cognitive-execution-engine\\handoff_state.json")
    payload["execution_mode"] = "explore"

    results = assess_handoff_stage_gates(payload)

    edit_if_needed = next(r for r in results if r.stage == "edit_if_needed")
    assert edit_if_needed.status == "blocked"
    assert "explore" in edit_if_needed.reasons[0]


def test_explore_mode_allows_read_state():
    payload = load_handoff_state("F:\\cognitive-execution-engine\\handoff_state.json")
    payload["execution_mode"] = "explore"

    results = assess_handoff_stage_gates(payload)

    read_state = next(r for r in results if r.stage == "read_state")
    assert read_state.status == "ready"


def test_explore_mode_allows_inspect_context():
    payload = load_handoff_state("F:\\cognitive-execution-engine\\handoff_state.json")
    payload["execution_mode"] = "explore"

    results = assess_handoff_stage_gates(payload)

    inspect = next(r for r in results if r.stage == "inspect_minimum_context")
    assert inspect.status == "ready"


def test_diagnose_only_still_blocks_edits():
    payload = load_handoff_state("F:\\cognitive-execution-engine\\handoff_state.json")
    payload["execution_mode"] = "diagnose_only"

    results = assess_handoff_stage_gates(payload)

    edit_if_needed = next(r for r in results if r.stage == "edit_if_needed")
    assert edit_if_needed.status == "blocked"
    assert "diagnose_only" in edit_if_needed.reasons[0]


def test_redirect_proposed_in_run_result():
    from cee_core import execute_task_in_domain, DomainContext

    result = execute_task_in_domain(
        "analyze unknown system",
        DomainContext(domain_name="core"),
    )

    if result.reasoning_step.chosen_action == "propose_redirect":
        assert result.redirect_proposed is True
        assert len(result.plan.candidate_deltas) == 0
    else:
        assert result.redirect_proposed is False
