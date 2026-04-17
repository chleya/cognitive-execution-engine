import pytest

from cee_core import (
    ApprovalDecision,
    EventLog,
    State,
    StatePatch,
    approve_transition,
    build_transition_for_patch,
    reduce_event,
)


def _self_model_transition():
    return build_transition_for_patch(
        StatePatch(
            section="self_model",
            key="capabilities",
            op="set",
            value={"planner": "bounded"},
        ),
        actor="planner",
        reason="capability calibration update",
    )


def test_requires_approval_transition_is_blocked_without_decision():
    event = _self_model_transition()

    assert event.policy_decision.verdict == "requires_approval"
    with pytest.raises(PermissionError):
        reduce_event(State(), event)


def test_approval_decision_converts_transition_to_allowed_event():
    event = _self_model_transition()
    decision = ApprovalDecision(
        transition_trace_id=event.trace_id,
        verdict="approved",
        decided_by="human:operator",
        reason="reviewed calibration evidence",
    )

    approved_event = approve_transition(event, decision)
    state = reduce_event(State(), approved_event)

    assert approved_event.policy_decision.verdict == "allow"
    assert state.self_model["capabilities"] == {"planner": "bounded"}
    assert state.meta["version"] == 1


def test_rejected_approval_decision_cannot_create_allowed_transition():
    event = _self_model_transition()
    decision = ApprovalDecision(
        transition_trace_id=event.trace_id,
        verdict="rejected",
        decided_by="human:operator",
        reason="insufficient evidence",
    )

    with pytest.raises(PermissionError):
        approve_transition(event, decision)


def test_approval_decision_must_match_transition_trace():
    event = _self_model_transition()
    decision = ApprovalDecision(
        transition_trace_id="tr_other",
        verdict="approved",
        decided_by="human:operator",
        reason="wrong trace",
    )

    with pytest.raises(ValueError):
        approve_transition(event, decision)


def test_approval_audit_event_is_recorded_but_not_replayed_as_state():
    event = _self_model_transition()
    decision = ApprovalDecision(
        transition_trace_id=event.trace_id,
        verdict="approved",
        decided_by="human:operator",
        reason="reviewed calibration evidence",
    )
    approved_event = approve_transition(event, decision)
    log = EventLog()

    log.append(event)
    log.append(decision.to_event())
    log.append(approved_event)

    state = log.replay_state()
    trace_events = log.by_trace(event.trace_id)

    assert state.self_model["capabilities"] == {"planner": "bounded"}
    assert state.meta["version"] == 1
    assert len(trace_events) == 3
    assert trace_events[1].event_type == "approval.decision.recorded"

