import pytest

from cee_core import (
    ApprovalDecision,
    ApprovalGate,
    BehavioralSnapshot,
    CalibrationProposal,
    CalibrationResult,
    DomainContext,
    EventLog,
    State,
    StatePatch,
    StaticApprovalProvider,
    calibration_proposal_to_patch,
    evaluate_patch_policy,
    execute_task_in_domain,
    extract_behavioral_snapshot,
    propose_self_model_calibration,
    reflect_and_redirect,
    run_calibration_cycle,
)
from cee_core.self_observation import RedirectProposal


def _populated_event_log() -> EventLog:
    log = EventLog()

    from cee_core.events import DeliberationEvent, StateTransitionEvent
    from cee_core.deliberation import ReasoningStep
    from cee_core.policy import PolicyDecision
    from cee_core.tasks import TaskSpec

    task = TaskSpec(
        task_id="t1",
        objective="test task",
        kind="analysis",
        success_criteria=("done",),
        requested_primitives=(),
        risk_level="medium",
        domain_name="core",
        task_level="L1",
    )

    step = ReasoningStep(
        task_id="t1",
        summary="test summary",
        hypothesis="test hypothesis",
        missing_information=("info1", "info2"),
        candidate_actions=("propose_redirect",),
        chosen_action="propose_redirect",
        rationale="multiple missing info",
        stop_condition="done",
    )
    log.append(DeliberationEvent(reasoning_step=step))

    for section, verdict in [
        ("goals", "allow"),
        ("beliefs", "allow"),
        ("self_model", "requires_approval"),
        ("policy", "deny"),
        ("beliefs", "requires_approval"),
    ]:
        patch = StatePatch(section=section, key="k1", op="set", value={"v": 1})
        decision = PolicyDecision(
            verdict=verdict,
            reason=f"test {verdict}",
            policy_ref="test",
        )
        log.append(StateTransitionEvent(
            patch=patch, policy_decision=decision, actor="test", reason="test",
        ))

    return log


def test_extract_behavioral_snapshot_counts_transitions():
    log = _populated_event_log()
    snapshot = extract_behavioral_snapshot(log)

    assert snapshot.total_transitions == 5
    assert snapshot.allowed_count == 2
    assert snapshot.denied_count == 1
    assert snapshot.requires_approval_count == 2


def test_extract_behavioral_snapshot_counts_redirects():
    log = _populated_event_log()
    snapshot = extract_behavioral_snapshot(log)

    assert snapshot.redirect_count == 1


def test_extract_behavioral_snapshot_section_outcomes():
    log = _populated_event_log()
    snapshot = extract_behavioral_snapshot(log)

    assert "beliefs" in snapshot.section_outcomes
    assert snapshot.section_outcomes["beliefs"]["allow"] == 1
    assert snapshot.section_outcomes["beliefs"]["requires_approval"] == 1


def test_behavioral_snapshot_rates():
    log = _populated_event_log()
    snapshot = extract_behavioral_snapshot(log)

    assert snapshot.allow_rate == 2 / 5
    assert snapshot.denial_rate == 1 / 5
    assert snapshot.approval_escalation_rate == 2 / 5


def test_empty_event_log_gives_zero_snapshot():
    log = EventLog()
    snapshot = extract_behavioral_snapshot(log)

    assert snapshot.total_transitions == 0
    assert snapshot.allow_rate == 0.0
    assert snapshot.denial_rate == 0.0


def test_propose_self_model_calibration_generates_proposals():
    log = _populated_event_log()
    snapshot = extract_behavioral_snapshot(log)

    proposals = propose_self_model_calibration(snapshot, {})

    assert len(proposals) > 0
    assert all(p.patch_section == "self_model" for p in proposals)
    assert all(p.is_tightening for p in proposals)


def test_propose_self_model_calibration_includes_failure_patterns():
    log = _populated_event_log()
    snapshot = extract_behavioral_snapshot(log)

    proposals = propose_self_model_calibration(snapshot, {})
    failure_proposal = next(
        (p for p in proposals if p.patch_key == "observed_failure_patterns"), None
    )

    assert failure_proposal is not None
    assert len(failure_proposal.evidence) > 0


def test_propose_self_model_calibration_includes_success_metrics():
    log = _populated_event_log()
    snapshot = extract_behavioral_snapshot(log)

    proposals = propose_self_model_calibration(snapshot, {})
    metrics_proposal = next(
        (p for p in proposals if p.patch_key == "observed_success_metrics"), None
    )

    assert metrics_proposal is not None
    assert "allow_rate" in metrics_proposal.patch_value


def test_calibration_proposal_to_patch_targets_self_model():
    proposal = CalibrationProposal(
        patch_section="self_model",
        patch_key="test_key",
        patch_value={"data": 1},
        evidence=("evidence1",),
        proposal_id="cal_001",
    )

    patch = calibration_proposal_to_patch(proposal)

    assert patch.section == "self_model"
    assert patch.key == "test_key"
    assert patch.op == "set"


def test_calibration_proposal_patch_requires_approval():
    proposal = CalibrationProposal(
        patch_section="self_model",
        patch_key="test_key",
        patch_value={"data": 1},
        evidence=("evidence1",),
        proposal_id="cal_001",
    )

    patch = calibration_proposal_to_patch(proposal)
    decision = evaluate_patch_policy(patch)

    assert decision.verdict == "requires_approval"


def test_run_calibration_cycle_with_approval():
    log = _populated_event_log()
    state = State()
    gate = ApprovalGate(provider=StaticApprovalProvider(verdict="approved"))

    result = run_calibration_cycle(log, state, approval_gate=gate)

    assert result.proposal_count > 0
    assert result.approved_count > 0


def test_run_calibration_cycle_without_approval_gate():
    log = _populated_event_log()
    state = State()

    result = run_calibration_cycle(log, state)

    assert result.proposal_count > 0
    assert result.approval_result is None


def test_run_calibration_cycle_on_empty_log():
    log = EventLog()
    state = State()

    result = run_calibration_cycle(log, state)

    assert result.proposal_count == 0
    assert result.transition_events == ()


def test_calibration_cycle_audit_trail():
    log = _populated_event_log()
    state = State()
    initial_event_count = len(list(log.all()))

    gate = ApprovalGate(provider=StaticApprovalProvider(verdict="approved"))
    result = run_calibration_cycle(log, state, approval_gate=gate)

    final_event_count = len(list(log.all()))
    assert final_event_count > initial_event_count


def test_calibration_from_real_runtime():
    log = EventLog()
    result = execute_task_in_domain(
        "count to 3",
        DomainContext(domain_name="core"),
        event_log=log,
    )

    snapshot = extract_behavioral_snapshot(log)

    assert snapshot.total_transitions > 0
    assert snapshot.allow_rate > 0.0


def test_reflect_and_redirect_no_redirect_when_healthy():
    snapshot = BehavioralSnapshot(
        total_transitions=10,
        allowed_count=8,
        denied_count=1,
        requires_approval_count=1,
        approval_approved_count=1,
        approval_rejected_count=0,
        redirect_count=0,
        section_outcomes={},
        belief_confidence_values=(0.9, 0.85, 0.8),
    )

    proposal = reflect_and_redirect(snapshot)

    assert proposal is None


def test_reflect_and_redirect_proposes_when_high_denial():
    snapshot = BehavioralSnapshot(
        total_transitions=10,
        allowed_count=3,
        denied_count=5,
        requires_approval_count=2,
        approval_approved_count=1,
        approval_rejected_count=1,
        redirect_count=0,
        section_outcomes={},
        belief_confidence_values=(0.9,),
    )

    proposal = reflect_and_redirect(snapshot)

    assert proposal is not None
    assert isinstance(proposal, RedirectProposal)
    assert "denial rate" in proposal.reason.lower()
    assert proposal.is_tightening is True


def test_reflect_and_redirect_proposes_when_many_redirects():
    snapshot = BehavioralSnapshot(
        total_transitions=10,
        allowed_count=8,
        denied_count=1,
        requires_approval_count=1,
        approval_approved_count=1,
        approval_rejected_count=0,
        redirect_count=4,
        section_outcomes={},
        belief_confidence_values=(0.9,),
    )

    proposal = reflect_and_redirect(snapshot)

    assert proposal is not None
    assert "redirect" in proposal.reason.lower()


def test_reflect_and_redirect_proposes_when_low_confidence_dominates():
    snapshot = BehavioralSnapshot(
        total_transitions=10,
        allowed_count=8,
        denied_count=1,
        requires_approval_count=1,
        approval_approved_count=1,
        approval_rejected_count=0,
        redirect_count=0,
        section_outcomes={},
        belief_confidence_values=(0.3, 0.4, 0.5, 0.6, 0.3, 0.2),
    )

    proposal = reflect_and_redirect(snapshot)

    assert proposal is not None
    assert "low-confidence" in proposal.reason.lower()


def test_redirect_proposal_has_suggested_alternative():
    snapshot = BehavioralSnapshot(
        total_transitions=10,
        allowed_count=3,
        denied_count=5,
        requires_approval_count=2,
        approval_approved_count=0,
        approval_rejected_count=2,
        redirect_count=0,
        section_outcomes={},
        belief_confidence_values=(),
    )

    proposal = reflect_and_redirect(snapshot)

    assert proposal is not None
    assert len(proposal.suggested_alternative) > 0
    assert proposal.confidence > 0.0
