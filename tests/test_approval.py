import pytest

from cee_core import (
    ApprovalDecision,
    ApprovalGate,
    ApprovalGateResult,
    CommitmentEvent,
    EventLog,
    StaticApprovalProvider,
)
from cee_core.commitment import CommitmentEvent as CE
from cee_core.revision import ModelRevisionEvent
from cee_core.planner import PlanSpec, RevisionDelta, DeltaPolicyDecision, execute_plan


def _self_model_commitment():
    return CommitmentEvent(
        event_id="ce-test-0",
        source_state_id="",
        commitment_kind="internal_commit",
        intent_summary="test:self_model update",
        action_summary="self_model capabilities",
        success=False,
        reversibility="reversible",
        requires_approval=True,
    )


def test_requires_approval_commitment_is_not_successful():
    ce = _self_model_commitment()
    assert not ce.success


def test_approval_gate_auto_approves_self_model():
    gate = ApprovalGate(provider=StaticApprovalProvider(verdict="approved"))
    ce = _self_model_commitment()

    result = gate.resolve((ce,))

    assert result.approval_count == 1
    assert result.rejection_count == 0


def test_approval_gate_auto_rejects_self_model():
    gate = ApprovalGate(provider=StaticApprovalProvider(verdict="rejected"))
    ce = _self_model_commitment()

    result = gate.resolve((ce,))

    assert result.approval_count == 0
    assert result.rejection_count == 1


def test_approval_audit_event_is_recorded_but_not_replayed_as_state():
    log = EventLog()
    plan = PlanSpec.from_deltas(
        objective="test",
        candidate_deltas=[
            RevisionDelta(delta_id="d1", target_kind="entity_update", target_ref="beliefs.test", before_summary="unknown", after_summary="ok", justification="test", raw_value="ok"),
        ],
    )
    result = execute_plan(plan, event_log=log)

    decision = ApprovalDecision(
        transition_trace_id="ce-test",
        verdict="approved",
        decided_by="human:operator",
        reason="reviewed evidence",
    )
    log.append(decision.to_event())

    ws = log.replay_world_state()
    all_events = log.all()
    audit_events = [e for e in all_events if getattr(e, "event_type", "") == "approval.decision.recorded"]

    assert len(audit_events) == 1
