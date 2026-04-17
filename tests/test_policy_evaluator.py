import pytest

from cee_core import (
    State,
    StatePatch,
    build_transition_for_patch,
    evaluate_patch_policy,
    reduce_event,
)


def test_policy_allows_memory_goal_belief_and_domain_data_patches():
    for section in ("memory", "goals", "beliefs", "domain_data"):
        decision = evaluate_patch_policy(
            StatePatch(section=section, key="k", op="set", value="v")
        )

        assert decision.verdict == "allow"
        assert decision.allowed is True


def test_policy_denies_meta_patch():
    decision = evaluate_patch_policy(
        StatePatch(section="meta", key="version", op="set", value=99)
    )

    assert decision.verdict == "deny"
    assert decision.blocked is True


def test_policy_requires_approval_for_tool_affordances_patch():
    decision = evaluate_patch_policy(
        StatePatch(section="tool_affordances", key="available_tools", op="set", value=[])
    )

    assert decision.verdict == "requires_approval"
    assert decision.blocked is True


def test_policy_requires_approval_for_self_model_patch():
    decision = evaluate_patch_policy(
        StatePatch(section="self_model", key="capabilities", op="set", value={})
    )

    assert decision.verdict == "requires_approval"
    assert decision.blocked is True


def test_policy_denies_policy_patch():
    decision = evaluate_patch_policy(
        StatePatch(section="policy", key="allowed_tools", op="set", value=["x"])
    )

    assert decision.verdict == "deny"
    assert decision.blocked is True


def test_policy_denies_unknown_section():
    decision = evaluate_patch_policy(
        StatePatch(section="unknown", key="x", op="set", value=1)
    )

    assert decision.verdict == "deny"
    assert "unknown state section" in decision.reason


def test_build_transition_for_patch_applies_policy_decision():
    event = build_transition_for_patch(
        StatePatch(section="beliefs", key="source_count", op="set", value=4),
        actor="planner",
        reason="verified sources",
    )

    assert event.policy_decision.verdict == "allow"
    assert event.actor == "planner"
    assert event.reason == "verified sources"

    state = reduce_event(State(), event)
    assert state.beliefs["source_count"] == 4


def test_build_transition_for_patch_blocks_self_model_without_approval():
    event = build_transition_for_patch(
        StatePatch(section="self_model", key="identity", op="set", value="agent"),
        actor="planner",
        reason="model proposed identity update",
    )

    assert event.policy_decision.verdict == "requires_approval"
    with pytest.raises(PermissionError):
        reduce_event(State(), event)

