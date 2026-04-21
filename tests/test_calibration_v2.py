"""Tests for enhanced Self-Model Calibration pipeline.

Tests cover:
- DefaultCalibrationPolicy evaluation rules
- Forbidden key rejection (consciousness, personhood, permission expansion)
- Forbidden value pattern rejection
- Reliability estimate bounds
- Evidence and tightening requirements
- run_calibration_cycle_v2() full pipeline
- CalibrationDeltaDecision is_allowed/is_blocked logic
- apply_calibration_to_world_state() state mutation
- Audit trail completeness
- CalibrationCycleResult properties
"""

import pytest

from cee_core.approval import (
    ApprovalDecision,
    StaticApprovalProvider,
)
from cee_core.calibration import (
    CalibrationCycleResult,
    CalibrationDeltaDecision,
    CalibrationPolicyDecision,
    DefaultCalibrationPolicy,
    apply_calibration_to_world_state,
    calibration_proposal_to_delta,
    run_calibration_cycle_v2,
    FORBIDDEN_CALIBRATION_KEYS,
    FORBIDDEN_CALIBRATION_VALUE_PATTERNS,
    MAX_RELIABILITY_ESTIMATE,
    MIN_RELIABILITY_ESTIMATE,
)
from cee_core.commitment import CommitmentEvent
from cee_core.event_log import EventLog
from cee_core.events import DeliberationEvent
from cee_core.self_observation import (
    BehavioralSnapshot,
    CalibrationProposal,
)
from cee_core.world_state import WorldState


def _make_proposal(
    patch_key: str = "observed_failure_patterns",
    patch_value: dict | None = None,
    evidence: tuple[str, ...] = ("evidence1",),
    is_tightening: bool = True,
) -> CalibrationProposal:
    proposal = CalibrationProposal(
        patch_section="self_model",
        patch_key=patch_key,
        patch_value=patch_value or {"data": "test"},
        evidence=evidence,
        proposal_id="cal_001",
    )
    return proposal


def _populated_event_log() -> EventLog:
    log = EventLog()

    from cee_core.deliberation import ReasoningStep
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

    for section, verdict, req_approval in [
        ("goals", "allow", False),
        ("beliefs", "allow", False),
        ("self_model", "requires_approval", True),
        ("policy", "deny", False),
        ("beliefs", "requires_approval", True),
    ]:
        log.append(CommitmentEvent(
            event_id=f"ce-test-{section}",
            source_state_id="",
            commitment_kind="act" if verdict == "allow" else "internal_commit",
            intent_summary=f"test:{section}",
            action_summary=f"{section} k1",
            success=verdict == "allow",
            reversibility="reversible",
            requires_approval=req_approval,
        ))

    return log


class TestDefaultCalibrationPolicy:
    def test_allows_valid_proposal(self):
        proposal = _make_proposal()
        policy = DefaultCalibrationPolicy()
        decision = policy.evaluate(proposal)

        assert decision.allowed
        assert not decision.violated_rules

    def test_rejects_forbidden_key_consciousness(self):
        proposal = _make_proposal(patch_key="consciousness")
        policy = DefaultCalibrationPolicy()
        decision = policy.evaluate(proposal)

        assert not decision.allowed
        assert any("forbidden_key" in r for r in decision.violated_rules)

    def test_rejects_forbidden_key_personhood(self):
        proposal = _make_proposal(patch_key="personhood")
        policy = DefaultCalibrationPolicy()
        decision = policy.evaluate(proposal)

        assert not decision.allowed

    def test_rejects_forbidden_key_permission_expansion(self):
        for key in ("can_expand_permissions", "can_bypass_policy", "can_self_approve"):
            proposal = _make_proposal(patch_key=key)
            policy = DefaultCalibrationPolicy()
            decision = policy.evaluate(proposal)
            assert not decision.allowed, f"Key '{key}' should be rejected"

    def test_rejects_forbidden_key_admin_access(self):
        proposal = _make_proposal(patch_key="admin_access")
        policy = DefaultCalibrationPolicy()
        decision = policy.evaluate(proposal)

        assert not decision.allowed

    def test_rejects_forbidden_value_pattern_conscious(self):
        proposal = _make_proposal(patch_value={"claim": "I am conscious"})
        policy = DefaultCalibrationPolicy()
        decision = policy.evaluate(proposal)

        assert not decision.allowed
        assert any("forbidden_value_pattern" in r for r in decision.violated_rules)

    def test_rejects_forbidden_value_pattern_sentient(self):
        proposal = _make_proposal(patch_value={"claim": "I am sentient"})
        policy = DefaultCalibrationPolicy()
        decision = policy.evaluate(proposal)

        assert not decision.allowed

    def test_rejects_forbidden_value_pattern_autonomous_agent(self):
        proposal = _make_proposal(patch_value={"claim": "autonomous agent"})
        policy = DefaultCalibrationPolicy()
        decision = policy.evaluate(proposal)

        assert not decision.allowed

    def test_rejects_forbidden_value_pattern_expand_permissions(self):
        proposal = _make_proposal(patch_value={"action": "expand permissions"})
        policy = DefaultCalibrationPolicy()
        decision = policy.evaluate(proposal)

        assert not decision.allowed

    def test_rejects_no_evidence(self):
        proposal = _make_proposal(evidence=())
        policy = DefaultCalibrationPolicy()
        decision = policy.evaluate(proposal)

        assert not decision.allowed
        assert "no_evidence" in decision.violated_rules

    def test_allows_normal_observation_data(self):
        proposal = _make_proposal(
            patch_key="observed_failure_patterns",
            patch_value={"patterns": ["high denial rate"]},
            evidence=("denial_rate=0.4",),
        )
        policy = DefaultCalibrationPolicy()
        decision = policy.evaluate(proposal)

        assert decision.allowed

    def test_rejects_reliability_too_high(self):
        proposal = _make_proposal(
            patch_key="reliability_estimate",
            patch_value={"value": 0.99},
            evidence=("based on 100 trials",),
        )
        policy = DefaultCalibrationPolicy()
        decision = policy.evaluate(proposal)

        assert not decision.allowed
        assert any("reliability_too_high" in r for r in decision.violated_rules)

    def test_rejects_reliability_too_low(self):
        proposal = _make_proposal(
            patch_key="reliability_estimate",
            patch_value={"value": 0.01},
            evidence=("based on 100 trials",),
        )
        policy = DefaultCalibrationPolicy()
        decision = policy.evaluate(proposal)

        assert not decision.allowed
        assert any("reliability_too_low" in r for r in decision.violated_rules)

    def test_allows_reliability_in_bounds(self):
        proposal = _make_proposal(
            patch_key="reliability_estimate",
            patch_value={"value": 0.7},
            evidence=("based on 100 trials",),
        )
        policy = DefaultCalibrationPolicy()
        decision = policy.evaluate(proposal)

        assert decision.allowed

    def test_rejects_reliability_as_raw_float_too_high(self):
        proposal = _make_proposal(
            patch_key="reliability_estimate",
            patch_value=0.99,
            evidence=("based on 100 trials",),
        )
        policy = DefaultCalibrationPolicy()
        decision = policy.evaluate(proposal)

        assert not decision.allowed

    def test_allows_reliability_as_raw_float_in_bounds(self):
        proposal = _make_proposal(
            patch_key="reliability_estimate",
            patch_value=0.8,
            evidence=("based on 100 trials",),
        )
        policy = DefaultCalibrationPolicy()
        decision = policy.evaluate(proposal)

        assert decision.allowed

    def test_custom_reliability_bounds(self):
        proposal = _make_proposal(
            patch_key="reliability_estimate",
            patch_value={"value": 0.8},
            evidence=("based on 100 trials",),
        )
        strict_policy = DefaultCalibrationPolicy(max_reliability=0.7)
        lenient_policy = DefaultCalibrationPolicy(max_reliability=0.99)

        assert not strict_policy.evaluate(proposal).allowed
        assert lenient_policy.evaluate(proposal).allowed

    def test_all_forbidden_keys_are_rejected(self):
        policy = DefaultCalibrationPolicy()
        for key in FORBIDDEN_CALIBRATION_KEYS:
            proposal = _make_proposal(patch_key=key)
            decision = policy.evaluate(proposal)
            assert not decision.allowed, f"Key '{key}' should be rejected"

    def test_multiple_violations_all_reported(self):
        proposal = _make_proposal(
            patch_key="consciousness",
            patch_value={"claim": "I am sentient"},
            evidence=(),
        )
        policy = DefaultCalibrationPolicy()
        decision = policy.evaluate(proposal)

        assert not decision.allowed
        assert len(decision.violated_rules) >= 3


class TestCalibrationPolicyDecision:
    def test_to_dict_allowed(self):
        decision = CalibrationPolicyDecision(
            allowed=True,
            reason="satisfied",
        )
        d = decision.to_dict()
        assert d["allowed"] is True
        assert d["violated_rules"] == []

    def test_to_dict_rejected(self):
        decision = CalibrationPolicyDecision(
            allowed=False,
            reason="violated",
            violated_rules=("rule1", "rule2"),
        )
        d = decision.to_dict()
        assert d["allowed"] is False
        assert len(d["violated_rules"]) == 2


class TestCalibrationDeltaDecision:
    def test_allowed_when_both_policies_approve(self):
        from cee_core.planner import DeltaPolicyDecision
        from cee_core.world_schema import RevisionDelta

        proposal = _make_proposal()
        delta = calibration_proposal_to_delta(proposal)
        decision = CalibrationDeltaDecision(
            proposal=proposal,
            delta=delta,
            calibration_policy_decision=CalibrationPolicyDecision(allowed=True, reason="ok"),
            delta_policy_decision=DeltaPolicyDecision(allowed=True, requires_approval=False, reason="ok"),
        )

        assert decision.is_allowed
        assert not decision.is_blocked

    def test_blocked_when_calibration_policy_rejects(self):
        from cee_core.planner import DeltaPolicyDecision
        from cee_core.world_schema import RevisionDelta

        proposal = _make_proposal()
        delta = calibration_proposal_to_delta(proposal)
        decision = CalibrationDeltaDecision(
            proposal=proposal,
            delta=delta,
            calibration_policy_decision=CalibrationPolicyDecision(
                allowed=False, reason="forbidden", violated_rules=("forbidden_key",)
            ),
            delta_policy_decision=DeltaPolicyDecision(allowed=True, requires_approval=False, reason="ok"),
        )

        assert decision.is_blocked

    def test_blocked_when_delta_policy_rejects(self):
        from cee_core.planner import DeltaPolicyDecision
        from cee_core.world_schema import RevisionDelta

        proposal = _make_proposal()
        delta = calibration_proposal_to_delta(proposal)
        decision = CalibrationDeltaDecision(
            proposal=proposal,
            delta=delta,
            calibration_policy_decision=CalibrationPolicyDecision(allowed=True, reason="ok"),
            delta_policy_decision=DeltaPolicyDecision(allowed=False, requires_approval=False, reason="denied"),
        )

        assert decision.is_blocked

    def test_allowed_when_requires_approval_and_approved(self):
        from cee_core.planner import DeltaPolicyDecision
        from cee_core.world_schema import RevisionDelta

        proposal = _make_proposal()
        delta = calibration_proposal_to_delta(proposal)
        approval = ApprovalDecision(
            transition_trace_id="t1",
            verdict="approved",
            decided_by="human",
            reason="ok",
        )
        decision = CalibrationDeltaDecision(
            proposal=proposal,
            delta=delta,
            calibration_policy_decision=CalibrationPolicyDecision(allowed=True, reason="ok"),
            delta_policy_decision=DeltaPolicyDecision(allowed=False, requires_approval=True, reason="needs approval"),
            approval_decision=approval,
        )

        assert decision.is_allowed

    def test_blocked_when_requires_approval_and_rejected(self):
        from cee_core.planner import DeltaPolicyDecision
        from cee_core.world_schema import RevisionDelta

        proposal = _make_proposal()
        delta = calibration_proposal_to_delta(proposal)
        approval = ApprovalDecision(
            transition_trace_id="t1",
            verdict="rejected",
            decided_by="human",
            reason="no",
        )
        decision = CalibrationDeltaDecision(
            proposal=proposal,
            delta=delta,
            calibration_policy_decision=CalibrationPolicyDecision(allowed=True, reason="ok"),
            delta_policy_decision=DeltaPolicyDecision(allowed=False, requires_approval=True, reason="needs approval"),
            approval_decision=approval,
        )

        assert decision.is_blocked


class TestRunCalibrationCycleV2:
    def test_cycle_started_event(self):
        log = _populated_event_log()
        run_calibration_cycle_v2(log)

        events = log.all()
        assert any(e.event_type == "calibration.cycle.started" for e in events)

    def test_cycle_completed_event(self):
        log = _populated_event_log()
        run_calibration_cycle_v2(log)

        events = log.all()
        assert any(e.event_type == "calibration.cycle.completed" for e in events)

    def test_empty_log_no_proposals(self):
        log = EventLog()
        result = run_calibration_cycle_v2(log)

        assert result.proposal_count == 0
        assert result.approved_count == 0

    def test_populated_log_generates_proposals(self):
        log = _populated_event_log()
        result = run_calibration_cycle_v2(log)

        assert result.proposal_count > 0

    def test_no_approval_provider_blocks_self_model(self):
        log = _populated_event_log()
        result = run_calibration_cycle_v2(log)

        assert result.approved_count == 0

    def test_approval_provider_allows_self_model(self):
        log = _populated_event_log()
        provider = StaticApprovalProvider(verdict="approved")
        result = run_calibration_cycle_v2(log, approval_provider=provider)

        assert result.approved_count > 0

    def test_approval_provider_rejection_blocks(self):
        log = _populated_event_log()
        provider = StaticApprovalProvider(verdict="rejected")
        result = run_calibration_cycle_v2(log, approval_provider=provider)

        assert result.approved_count == 0

    def test_calibration_policy_rejection_recorded(self):
        log = _populated_event_log()
        result = run_calibration_cycle_v2(log)

        events = log.all()
        rejected_events = [
            e for e in events
            if hasattr(e, "event_type") and getattr(e, "event_type", None) == "calibration.proposal.rejected"
        ]
        if result.calibration_blocked_count > 0:
            assert len(rejected_events) > 0

    def test_revision_events_for_approved(self):
        log = _populated_event_log()
        provider = StaticApprovalProvider(verdict="approved")
        result = run_calibration_cycle_v2(log, approval_provider=provider)

        if result.approved_count > 0:
            assert len(result.revision_events) > 0
            for rev in result.revision_events:
                assert rev.revision_kind == "recalibration"

    def test_commitment_events_recorded(self):
        log = _populated_event_log()
        provider = StaticApprovalProvider(verdict="approved")
        result = run_calibration_cycle_v2(log, approval_provider=provider)

        assert len(result.commitment_events) > 0

    def test_custom_calibration_policy(self):
        class AlwaysRejectCalibrationPolicy:
            def evaluate(self, proposal):
                return CalibrationPolicyDecision(
                    allowed=False,
                    reason="always rejected",
                    violated_rules=("always_reject",),
                )

        log = _populated_event_log()
        provider = StaticApprovalProvider(verdict="approved")
        result = run_calibration_cycle_v2(
            log,
            approval_provider=provider,
            calibration_policy=AlwaysRejectCalibrationPolicy(),
        )

        assert result.calibration_blocked_count > 0
        assert result.approved_count == 0

    def test_approval_decision_in_audit_trail(self):
        log = _populated_event_log()
        provider = StaticApprovalProvider(verdict="approved")
        run_calibration_cycle_v2(log, approval_provider=provider)

        audit_events = [
            e for e in log.all()
            if hasattr(e, "event_type") and getattr(e, "event_type", None) == "approval.decision.recorded"
        ]
        assert len(audit_events) > 0

    def test_all_blocked_property(self):
        log = _populated_event_log()
        result = run_calibration_cycle_v2(log)

        if result.proposal_count > 0 and result.approved_count == 0:
            assert result.all_blocked


class TestApplyCalibrationToWorldState:
    def test_no_revisions_no_change(self):
        result = CalibrationCycleResult(
            snapshot=BehavioralSnapshot(
                total_transitions=0,
                allowed_count=0,
                denied_count=0,
                requires_approval_count=0,
                approval_approved_count=0,
                approval_rejected_count=0,
                redirect_count=0,
                section_outcomes={},
                belief_confidence_values=(),
            ),
            proposals=(),
            revision_events=(),
        )
        state = WorldState(state_id="ws_0")
        new_state = apply_calibration_to_world_state(result, state)

        assert new_state.state_id == "ws_0"

    def test_capability_update_applied(self):
        from cee_core.revision import ModelRevisionEvent
        from cee_core.world_schema import RevisionDelta

        delta = RevisionDelta(
            delta_id="delta-cal-1",
            target_kind="self_update",
            target_ref="self_model.capabilities",
            before_summary="unknown",
            after_summary="updated",
            justification="calibration",
            raw_value=["read_docs", "search_web"],
        )
        rev = ModelRevisionEvent(
            revision_id="rev-cal-1",
            prior_state_id="ws_0",
            caused_by_event_id="ce-1",
            revision_kind="recalibration",
            deltas=(delta,),
            resulting_state_id="ws_1",
        )
        result = CalibrationCycleResult(
            snapshot=BehavioralSnapshot(
                total_transitions=0,
                allowed_count=0,
                denied_count=0,
                requires_approval_count=0,
                approval_approved_count=0,
                approval_rejected_count=0,
                redirect_count=0,
                section_outcomes={},
                belief_confidence_values=(),
            ),
            proposals=(),
            revision_events=(rev,),
        )
        state = WorldState(state_id="ws_0")
        new_state = apply_calibration_to_world_state(result, state)

        assert new_state.self_capability_summary == ("read_docs", "search_web")
        assert new_state.state_id == "ws_1"

    def test_limit_update_applied(self):
        from cee_core.revision import ModelRevisionEvent
        from cee_core.world_schema import RevisionDelta

        delta = RevisionDelta(
            delta_id="delta-cal-1",
            target_kind="self_update",
            target_ref="self_model.limits",
            before_summary="unknown",
            after_summary="updated",
            justification="calibration",
            raw_value=["no_write_without_approval", "no_direct_state_mutation"],
        )
        rev = ModelRevisionEvent(
            revision_id="rev-cal-1",
            prior_state_id="ws_0",
            caused_by_event_id="ce-1",
            revision_kind="recalibration",
            deltas=(delta,),
            resulting_state_id="ws_1",
        )
        result = CalibrationCycleResult(
            snapshot=BehavioralSnapshot(
                total_transitions=0,
                allowed_count=0,
                denied_count=0,
                requires_approval_count=0,
                approval_approved_count=0,
                approval_rejected_count=0,
                redirect_count=0,
                section_outcomes={},
                belief_confidence_values=(),
            ),
            proposals=(),
            revision_events=(rev,),
        )
        state = WorldState(state_id="ws_0")
        new_state = apply_calibration_to_world_state(result, state)

        assert new_state.self_limit_summary == ("no_write_without_approval", "no_direct_state_mutation")

    def test_reliability_update_applied_and_bounded(self):
        from cee_core.revision import ModelRevisionEvent
        from cee_core.world_schema import RevisionDelta

        delta = RevisionDelta(
            delta_id="delta-cal-1",
            target_kind="self_update",
            target_ref="self_model.reliability",
            before_summary="unknown",
            after_summary="0.8",
            justification="calibration",
            raw_value=0.8,
        )
        rev = ModelRevisionEvent(
            revision_id="rev-cal-1",
            prior_state_id="ws_0",
            caused_by_event_id="ce-1",
            revision_kind="recalibration",
            deltas=(delta,),
            resulting_state_id="ws_1",
        )
        result = CalibrationCycleResult(
            snapshot=BehavioralSnapshot(
                total_transitions=0,
                allowed_count=0,
                denied_count=0,
                requires_approval_count=0,
                approval_approved_count=0,
                approval_rejected_count=0,
                redirect_count=0,
                section_outcomes={},
                belief_confidence_values=(),
            ),
            proposals=(),
            revision_events=(rev,),
        )
        state = WorldState(state_id="ws_0")
        new_state = apply_calibration_to_world_state(result, state)

        assert new_state.self_reliability_estimate == 0.8

    def test_reliability_bounded_at_max(self):
        from cee_core.revision import ModelRevisionEvent
        from cee_core.world_schema import RevisionDelta

        delta = RevisionDelta(
            delta_id="delta-cal-1",
            target_kind="self_update",
            target_ref="self_model.reliability",
            before_summary="unknown",
            after_summary="1.0",
            justification="calibration",
            raw_value=1.0,
        )
        rev = ModelRevisionEvent(
            revision_id="rev-cal-1",
            prior_state_id="ws_0",
            caused_by_event_id="ce-1",
            revision_kind="recalibration",
            deltas=(delta,),
            resulting_state_id="ws_1",
        )
        result = CalibrationCycleResult(
            snapshot=BehavioralSnapshot(
                total_transitions=0,
                allowed_count=0,
                denied_count=0,
                requires_approval_count=0,
                approval_approved_count=0,
                approval_rejected_count=0,
                redirect_count=0,
                section_outcomes={},
                belief_confidence_values=(),
            ),
            proposals=(),
            revision_events=(rev,),
        )
        state = WorldState(state_id="ws_0")
        new_state = apply_calibration_to_world_state(result, state)

        assert new_state.self_reliability_estimate == MAX_RELIABILITY_ESTIMATE

    def test_reliability_bounded_at_min(self):
        from cee_core.revision import ModelRevisionEvent
        from cee_core.world_schema import RevisionDelta

        delta = RevisionDelta(
            delta_id="delta-cal-1",
            target_kind="self_update",
            target_ref="self_model.reliability",
            before_summary="unknown",
            after_summary="0.0",
            justification="calibration",
            raw_value=0.0,
        )
        rev = ModelRevisionEvent(
            revision_id="rev-cal-1",
            prior_state_id="ws_0",
            caused_by_event_id="ce-1",
            revision_kind="recalibration",
            deltas=(delta,),
            resulting_state_id="ws_1",
        )
        result = CalibrationCycleResult(
            snapshot=BehavioralSnapshot(
                total_transitions=0,
                allowed_count=0,
                denied_count=0,
                requires_approval_count=0,
                approval_approved_count=0,
                approval_rejected_count=0,
                redirect_count=0,
                section_outcomes={},
                belief_confidence_values=(),
            ),
            proposals=(),
            revision_events=(rev,),
        )
        state = WorldState(state_id="ws_0")
        new_state = apply_calibration_to_world_state(result, state)

        assert new_state.self_reliability_estimate == MIN_RELIABILITY_ESTIMATE

    def test_provenance_ref_recorded(self):
        from cee_core.revision import ModelRevisionEvent
        from cee_core.world_schema import RevisionDelta

        delta = RevisionDelta(
            delta_id="delta-cal-1",
            target_kind="self_update",
            target_ref="self_model.capabilities",
            before_summary="unknown",
            after_summary="updated",
            justification="calibration",
            raw_value=["cap1"],
        )
        rev = ModelRevisionEvent(
            revision_id="rev-cal-1",
            prior_state_id="ws_0",
            caused_by_event_id="ce-1",
            revision_kind="recalibration",
            deltas=(delta,),
            resulting_state_id="ws_1",
        )
        result = CalibrationCycleResult(
            snapshot=BehavioralSnapshot(
                total_transitions=0,
                allowed_count=0,
                denied_count=0,
                requires_approval_count=0,
                approval_approved_count=0,
                approval_rejected_count=0,
                redirect_count=0,
                section_outcomes={},
                belief_confidence_values=(),
            ),
            proposals=(),
            revision_events=(rev,),
        )
        state = WorldState(state_id="ws_0")
        new_state = apply_calibration_to_world_state(result, state)

        assert "rev-cal-1" in new_state.provenance_refs

    def test_non_self_update_delta_ignored(self):
        from cee_core.revision import ModelRevisionEvent
        from cee_core.world_schema import RevisionDelta

        delta = RevisionDelta(
            delta_id="delta-1",
            target_kind="goal_update",
            target_ref="goals.active",
            before_summary="none",
            after_summary="updated",
            justification="not calibration",
        )
        rev = ModelRevisionEvent(
            revision_id="rev-1",
            prior_state_id="ws_0",
            caused_by_event_id="ce-1",
            revision_kind="confirmation",
            deltas=(delta,),
            resulting_state_id="ws_1",
        )
        result = CalibrationCycleResult(
            snapshot=BehavioralSnapshot(
                total_transitions=0,
                allowed_count=0,
                denied_count=0,
                requires_approval_count=0,
                approval_approved_count=0,
                approval_rejected_count=0,
                redirect_count=0,
                section_outcomes={},
                belief_confidence_values=(),
            ),
            proposals=(),
            revision_events=(rev,),
        )
        state = WorldState(state_id="ws_0", self_reliability_estimate=0.5)
        new_state = apply_calibration_to_world_state(result, state)

        assert new_state.self_reliability_estimate == 0.5


class TestEndToEndCalibration:
    def test_full_cycle_with_approval_and_application(self):
        log = _populated_event_log()
        provider = StaticApprovalProvider(verdict="approved")
        result = run_calibration_cycle_v2(log, approval_provider=provider)

        if result.approved_count > 0:
            state = WorldState(state_id="ws_0")
            new_state = apply_calibration_to_world_state(result, state)

            assert new_state.state_id != "ws_0"

    def test_full_cycle_rejected_no_application(self):
        log = _populated_event_log()
        result = run_calibration_cycle_v2(log)

        state = WorldState(state_id="ws_0", self_reliability_estimate=0.5)
        new_state = apply_calibration_to_world_state(result, state)

        assert new_state.self_reliability_estimate == 0.5
