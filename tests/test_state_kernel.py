import pytest

from cee_core import (
    PolicyDecision,
    State,
    StatePatch,
    StateTransitionEvent,
    apply_patch,
    reduce_event,
    replay,
)


def test_apply_set_patch_increments_version_once():
    state = State()
    next_state = apply_patch(
        state,
        StatePatch(section="beliefs", key="source_count", op="set", value=3),
    )

    assert state.meta["version"] == 0
    assert next_state.meta["version"] == 1
    assert next_state.beliefs["source_count"] == 3


def test_append_patch_requires_list_target():
    state = State(memory={"working": []})
    next_state = apply_patch(
        state,
        StatePatch(section="memory", key="working", op="append", value={"step": 1}),
    )

    assert next_state.memory["working"] == [{"step": 1}]
    assert next_state.meta["version"] == 1


def test_policy_decision_blocks_approval_required():
    decision = PolicyDecision(
        verdict="requires_approval",
        reason="write action",
        policy_ref="tool-policy:v1",
    )

    assert decision.blocked is True
    assert decision.allowed is False


def test_rejects_policy_patch_from_state_patch():
    state = State()

    try:
        apply_patch(
            state,
            StatePatch(section="policy", key="allowed_tools", op="set", value=["x"]),
        )
    except ValueError as exc:
        assert "not patchable" in str(exc)
    else:
        raise AssertionError("policy patch should be rejected")


def test_reduce_event_applies_allowed_transition():
    event = StateTransitionEvent(
        patch=StatePatch(section="goals", key="active", op="set", value=["g1"]),
        policy_decision=PolicyDecision(
            verdict="allow",
            reason="read-only planning state",
            policy_ref="state-policy:v1",
        ),
    )

    next_state = reduce_event(State(), event)

    assert next_state.goals["active"] == ["g1"]
    assert next_state.meta["version"] == 1


def test_reduce_event_rejects_blocked_transition():
    event = StateTransitionEvent(
        patch=StatePatch(section="beliefs", key="x", op="set", value=1),
        policy_decision=PolicyDecision(
            verdict="requires_approval",
            reason="unverified belief promotion",
            policy_ref="belief-policy:v1",
        ),
    )

    with pytest.raises(PermissionError):
        reduce_event(State(), event)


def test_replay_reconstructs_final_state_deterministically():
    allow = PolicyDecision(
        verdict="allow",
        reason="safe transition",
        policy_ref="state-policy:v1",
    )
    events = [
        StateTransitionEvent(
            patch=StatePatch(section="memory", key="working", op="append", value="step-1"),
            policy_decision=allow,
        ),
        StateTransitionEvent(
            patch=StatePatch(section="beliefs", key="source_count", op="set", value=2),
            policy_decision=allow,
        ),
    ]

    first = replay(events)
    second = replay(events)

    assert first.snapshot() == second.snapshot()
    assert first.memory["working"] == ["step-1"]
    assert first.beliefs["source_count"] == 2
    assert first.meta["version"] == 2


def test_transition_event_serializes_policy_and_patch():
    event = StateTransitionEvent(
        patch=StatePatch(section="beliefs", key="risk", op="set", value="low"),
        policy_decision=PolicyDecision(
            verdict="allow",
            reason="verified",
            policy_ref="belief-policy:v1",
        ),
        reason="verified source",
    )

    payload = event.to_dict()

    assert payload["event_type"] == "state.patch.requested"
    assert payload["policy_decision"]["verdict"] == "allow"
    assert payload["patch"]["section"] == "beliefs"
