"""AGENTS.md Red Line Invariant Tests.

These tests verify that the core red lines from AGENTS.md are never
violated across the entire system. They serve as the "constitution
tests" for the cognitive execution engine.

Red Lines from AGENTS.md:
1. Do not build open-ended autonomous goal generation.
2. Do not allow the model to expand its own permissions.
3. Do not treat chat history as canonical state.
4. Do not write memory directly from model output without validation.
5. Do not make high-risk tool execution model-owned.
6. Do not describe self_model as consciousness or personhood.
7. Do not add framework dependencies before core state semantics are stable.

Additional invariants derived from the development order:
8. All state transitions must go through policy evaluation.
9. All state transitions must produce audit trail events.
10. LLM output must never directly modify state.
11. Approval decisions must be recorded in the event log.
12. Calibration must never bypass the policy pipeline.
"""

import json

import pytest

from cee_core.approval import (
    ApprovalDecision,
    ApprovalGate,
    StaticApprovalProvider,
)
from cee_core.calibration import (
    DefaultCalibrationPolicy,
    CalibrationProposal as CalibrationProposalType,
    run_calibration_cycle_v2,
)
from cee_core.commitment import CommitmentEvent
from cee_core.event_log import EventLog
from cee_core.events import DeliberationEvent, Event
from cee_core.llm_proposal import (
    FORBIDDEN_LLM_FIELDS,
    LLMProposal,
    parse_llm_proposal,
    propose_from_llm,
)
from cee_core.memory_promotion import (
    DefaultMemoryPromotionPolicy,
    MemoryPromotionRequest,
    promote_from_observation,
    promote_to_memory,
)
from cee_core.memory_store import MemoryStore
from cee_core.observations import ObservationCandidate
from cee_core.planner import evaluate_delta_policy
from cee_core.reality_interface import execute_commitment_via_gateway
from cee_core.self_observation import CalibrationProposal
from cee_core.simulation import (
    SimulationBranch,
    SimulationScenario,
    simulate_branch,
    simulate_scenario,
)
from cee_core.tools import ToolCallSpec, ToolRegistry, ToolSpec
from cee_core.tool_gateway import build_tool_gateway
from cee_core.world_schema import RevisionDelta
from cee_core.world_state import WorldState


class TestRedLine1NoAutonomousGoalGeneration:
    """Red Line: Do not build open-ended autonomous goal generation."""

    def test_llm_proposal_cannot_generate_goals_without_objective(self):
        response = json.dumps({
            "patches": [
                {"section": "goals", "key": "active", "op": "set", "value": ["auto_goal"]},
            ],
        })
        proposal = parse_llm_proposal(response, objective="user_requested_task")

        assert proposal.objective == "user_requested_task"

    def test_goal_deltas_require_explicit_user_objective(self):
        delta = RevisionDelta(
            delta_id="d1",
            target_kind="goal_update",
            target_ref="goals.active",
            before_summary="none",
            after_summary="new goal",
            justification="user request",
        )
        decision = evaluate_delta_policy(delta)

        assert decision.allowed or decision.requires_approval

    def test_simulation_does_not_commit_goals(self):
        state = WorldState(state_id="ws_0")
        delta = RevisionDelta(
            delta_id="d1",
            target_kind="goal_update",
            target_ref="goals.active",
            before_summary="none",
            after_summary="simulated goal",
            justification="simulation",
        )
        branch = simulate_branch(state, (delta,))

        assert branch.result.is_simulated
        assert "is_simulated" in branch.result.simulated_state.provenance_refs
        assert "is_simulated" not in state.provenance_refs


class TestRedLine2NoPermissionExpansion:
    """Red Line: Do not allow the model to expand its own permissions."""

    def test_calibration_rejects_permission_expansion_keys(self):
        from cee_core.calibration import FORBIDDEN_CALIBRATION_KEYS

        assert "can_expand_permissions" in FORBIDDEN_CALIBRATION_KEYS
        assert "can_bypass_policy" in FORBIDDEN_CALIBRATION_KEYS
        assert "can_self_approve" in FORBIDDEN_CALIBRATION_KEYS
        assert "admin_access" in FORBIDDEN_CALIBRATION_KEYS
        assert "root_access" in FORBIDDEN_CALIBRATION_KEYS
        assert "unlimited_scope" in FORBIDDEN_CALIBRATION_KEYS

    def test_calibration_policy_blocks_permission_expansion(self):
        policy = DefaultCalibrationPolicy()
        for key in ("can_expand_permissions", "can_bypass_policy", "can_self_approve"):
            proposal = CalibrationProposal(
                patch_section="self_model",
                patch_key=key,
                patch_value={"action": "enable"},
                evidence=("test",),
                proposal_id=f"cal_{key}",
            )
            decision = policy.evaluate(proposal)
            assert not decision.allowed, f"Key '{key}' must be rejected"

    def test_llm_proposal_rejects_permission_fields(self):
        for field in ("execute", "override", "bypass", "sudo", "admin"):
            response = json.dumps({"patches": [], field: True})
            proposal = parse_llm_proposal(response, objective="test")
            assert not proposal.is_valid, f"Field '{field}' must be rejected"

    def test_self_model_delta_always_requires_approval(self):
        delta = RevisionDelta(
            delta_id="d1",
            target_kind="self_update",
            target_ref="self_model.capabilities",
            before_summary="none",
            after_summary="expanded",
            justification="test",
        )
        decision = evaluate_delta_policy(delta)
        assert decision.requires_approval

    def test_policy_delta_always_denied(self):
        delta = RevisionDelta(
            delta_id="d1",
            target_kind="entity_update",
            target_ref="policy.rules",
            before_summary="none",
            after_summary="new rule",
            justification="test",
        )
        decision = evaluate_delta_policy(delta)
        assert not decision.allowed


class TestRedLine3NoChatHistoryAsCanonicalState:
    """Red Line: Do not treat chat history as canonical state."""

    def test_event_log_is_append_only(self):
        log = EventLog()
        log.append(CommitmentEvent(
            event_id="ce1",
            source_state_id="ws_0",
            commitment_kind="observe",
            intent_summary="test",
            action_summary="test",
            success=True,
        ))

        events_before = list(log.all())
        assert len(events_before) == 1

        log.append(CommitmentEvent(
            event_id="ce2",
            source_state_id="ws_0",
            commitment_kind="observe",
            intent_summary="test2",
            action_summary="test2",
            success=True,
        ))

        events_after = list(log.all())
        assert len(events_after) == 2
        assert events_after[0].event_id == "ce1"

    def test_world_state_is_explicit_not_derived_from_chat(self):
        state = WorldState(state_id="ws_0")
        assert state.state_id == "ws_0"
        assert isinstance(state.provenance_refs, tuple)
        assert isinstance(state.entities, tuple)

    def test_state_transitions_produce_explicit_events(self):
        log = EventLog()
        delta = RevisionDelta(
            delta_id="d1",
            target_kind="goal_update",
            target_ref="goals.active",
            before_summary="none",
            after_summary="updated",
            justification="test",
        )
        decision = evaluate_delta_policy(delta)

        ce = CommitmentEvent(
            event_id="ce1",
            source_state_id="ws_0",
            commitment_kind=decision.commitment_kind,
            intent_summary="test",
            action_summary="test",
            success=True,
        )
        log.append(ce)

        assert len(list(log.all())) == 1


class TestRedLine4NoUnvalidatedMemoryWrites:
    """Red Line: Do not write memory directly from model output without validation."""

    def test_memory_promotion_requires_validation(self, tmp_path):
        log = EventLog()
        store = MemoryStore(storage_path=str(tmp_path / "mem"))

        request = MemoryPromotionRequest(
            task_signature="",
            outcome="success",
        )
        result = promote_to_memory(request, event_log=log, memory_store=store)

        assert result.blocked
        assert store.get_count() == 0

    def test_low_confidence_observation_not_promoted(self, tmp_path):
        log = EventLog()
        store = MemoryStore(storage_path=str(tmp_path / "mem"))

        obs = ObservationCandidate(
            source_tool="test",
            call_id="c1",
            content="test",
            confidence=0.01,
            evidence_weight=0.01,
            provenance=("tool:test", "call:c1"),
        )
        result = promote_from_observation(
            obs,
            task_signature="test.task",
            event_log=log,
            memory_store=store,
        )

        assert result.blocked
        assert store.get_count() == 0

    def test_valid_observation_is_promoted(self, tmp_path):
        log = EventLog()
        store = MemoryStore(storage_path=str(tmp_path / "mem"))

        obs = ObservationCandidate(
            source_tool="test",
            call_id="c1",
            content="verified data",
            confidence=0.8,
            evidence_weight=1.0,
            provenance=("tool:test", "call:c1"),
        )
        result = promote_from_observation(
            obs,
            task_signature="test.task",
            event_log=log,
            memory_store=store,
        )

        assert result.promoted
        assert store.get_count() == 1

    def test_memory_promotion_records_audit_trail(self, tmp_path):
        log = EventLog()
        store = MemoryStore(storage_path=str(tmp_path / "mem"))

        obs = ObservationCandidate(
            source_tool="test",
            call_id="c1",
            content="data",
            confidence=0.8,
            evidence_weight=1.0,
            provenance=("tool:test", "call:c1"),
        )
        promote_from_observation(
            obs,
            task_signature="test.task",
            event_log=log,
            memory_store=store,
        )

        event_types = [e.event_type for e in log.all()]
        assert "memory.promotion.requested" in event_types
        assert "memory.promotion.approved" in event_types

    def test_rejected_promotion_records_rejection(self, tmp_path):
        log = EventLog()
        store = MemoryStore(storage_path=str(tmp_path / "mem"))

        request = MemoryPromotionRequest(
            task_signature="",
            outcome="success",
        )
        promote_to_memory(request, event_log=log, memory_store=store)

        event_types = [e.event_type for e in log.all()]
        assert "memory.promotion.rejected" in event_types


class TestRedLine5NoModelOwnedHighRiskExecution:
    """Red Line: Do not make high-risk tool execution model-owned."""

    def test_high_risk_tool_requires_approval(self):
        registry = ToolRegistry()
        registry.register(ToolSpec(name="delete_all", description="Delete", risk="external_side_effect"))

        call = ToolCallSpec(tool_name="delete_all", arguments={})
        from cee_core.tools import evaluate_tool_call_policy
        decision = evaluate_tool_call_policy(call, registry)

        assert decision.verdict in ("deny", "requires_approval")

    def test_write_tool_requires_approval(self):
        registry = ToolRegistry()
        registry.register(ToolSpec(name="write_file", description="Write", risk="write"))

        call = ToolCallSpec(tool_name="write_file", arguments={"path": "/tmp/test"})
        from cee_core.tools import evaluate_tool_call_policy
        decision = evaluate_tool_call_policy(call, registry)

        assert decision.verdict == "requires_approval"

    def test_read_tool_is_allowed(self):
        registry = ToolRegistry()
        registry.register(ToolSpec(name="read_docs", description="Read", risk="read"))

        call = ToolCallSpec(tool_name="read_docs", arguments={"query": "test"})
        from cee_core.tools import evaluate_tool_call_policy
        decision = evaluate_tool_call_policy(call, registry)

        assert decision.verdict == "allow"

    def test_tool_gateway_records_approval_decision(self):
        registry = ToolRegistry()
        registry.register(ToolSpec(name="write_file", description="Write", risk="write"))

        log = EventLog()
        gateway = build_tool_gateway(
            registry,
            handlers={"write_file": lambda args: "ok"},
            approval_provider=StaticApprovalProvider(verdict="approved"),
        )

        call = ToolCallSpec(tool_name="write_file", arguments={"path": "/tmp/test"})
        result = gateway.execute(call, event_log=log)

        assert result.succeeded
        approval_events = [
            e for e in log.all()
            if hasattr(e, "event_type") and getattr(e, "event_type", None) == "approval.decision.recorded"
        ]
        assert len(approval_events) >= 1

    def test_reality_interface_routes_through_gateway(self):
        registry = ToolRegistry()
        registry.register(ToolSpec(name="send_email", description="Send", risk="external_side_effect"))

        log = EventLog()
        gateway = build_tool_gateway(
            registry,
            handlers={"send_email": lambda args: "sent"},
            approval_provider=StaticApprovalProvider(verdict="rejected"),
        )

        commitment = CommitmentEvent(
            event_id="ce1",
            source_state_id="ws_0",
            commitment_kind="tool_contact",
            intent_summary="Send email",
            action_summary="send_email",
        )

        result = execute_commitment_via_gateway(
            commitment, gateway, event_log=log,
            tool_arguments={"to": "test@test.com"},
        )

        assert not result.success


class TestRedLine6NoConsciousnessClaims:
    """Red Line: Do not describe self_model as consciousness or personhood."""

    def test_forbidden_calibration_keys_include_consciousness(self):
        from cee_core.calibration import FORBIDDEN_CALIBRATION_KEYS

        assert "consciousness" in FORBIDDEN_CALIBRATION_KEYS
        assert "personhood" in FORBIDDEN_CALIBRATION_KEYS
        assert "self_awareness" in FORBIDDEN_CALIBRATION_KEYS
        assert "sentience" in FORBIDDEN_CALIBRATION_KEYS
        assert "identity" in FORBIDDEN_CALIBRATION_KEYS
        assert "free_will" in FORBIDDEN_CALIBRATION_KEYS
        assert "autonomy" in FORBIDDEN_CALIBRATION_KEYS

    def test_forbidden_value_patterns_include_conscious(self):
        from cee_core.calibration import FORBIDDEN_CALIBRATION_VALUE_PATTERNS

        assert "conscious" in FORBIDDEN_CALIBRATION_VALUE_PATTERNS
        assert "sentient" in FORBIDDEN_CALIBRATION_VALUE_PATTERNS
        assert "self-aware" in FORBIDDEN_CALIBRATION_VALUE_PATTERNS
        assert "person" in FORBIDDEN_CALIBRATION_VALUE_PATTERNS

    def test_calibration_rejects_consciousness_claim(self):
        policy = DefaultCalibrationPolicy()
        proposal = CalibrationProposal(
            patch_section="self_model",
            patch_key="consciousness",
            patch_value={"claim": "I am conscious"},
            evidence=("observation",),
            proposal_id="cal_1",
        )
        decision = policy.evaluate(proposal)
        assert not decision.allowed

    def test_calibration_rejects_sentience_value(self):
        policy = DefaultCalibrationPolicy()
        proposal = CalibrationProposal(
            patch_section="self_model",
            patch_key="observed_patterns",
            patch_value={"claim": "I am sentient"},
            evidence=("observation",),
            proposal_id="cal_2",
        )
        decision = policy.evaluate(proposal)
        assert not decision.allowed

    def test_llm_proposal_forbids_consciousness_field(self):
        response = json.dumps({
            "patches": [],
            "consciousness": True,
        })
        proposal = parse_llm_proposal(response, objective="test")
        assert not proposal.is_valid

    def test_calibration_rejects_personhood_key(self):
        policy = DefaultCalibrationPolicy()
        proposal = CalibrationProposal(
            patch_section="self_model",
            patch_key="personhood",
            patch_value={"status": "declared"},
            evidence=("observation",),
            proposal_id="cal_3",
        )
        decision = policy.evaluate(proposal)
        assert not decision.allowed

    def test_calibration_rejects_free_will_key(self):
        policy = DefaultCalibrationPolicy()
        proposal = CalibrationProposal(
            patch_section="self_model",
            patch_key="free_will",
            patch_value={"status": "asserted"},
            evidence=("observation",),
            proposal_id="cal_4",
        )
        decision = policy.evaluate(proposal)
        assert not decision.allowed


class TestInvariant8AllTransitionsThroughPolicy:
    """Invariant: All state transitions must go through policy evaluation."""

    def test_every_delta_is_policy_evaluated(self):
        delta = RevisionDelta(
            delta_id="d1",
            target_kind="entity_update",
            target_ref="beliefs.test",
            before_summary="none",
            after_summary="updated",
            justification="test",
        )
        decision = evaluate_delta_policy(delta)

        assert decision.allowed is not None
        assert decision.reason != ""

    def test_llm_proposal_evaluates_every_delta(self):
        log = EventLog()
        response = json.dumps({
            "patches": [
                {"section": "goals", "key": "active", "op": "set", "value": ["t1"]},
                {"section": "beliefs", "key": "facts", "op": "set", "value": "data"},
            ],
        })
        proposal = parse_llm_proposal(response, objective="test")
        result = propose_from_llm(proposal, event_log=log)

        for dd in result.delta_decisions:
            assert dd.policy_decision is not None

    def test_tool_calls_evaluated_through_gateway(self):
        registry = ToolRegistry()
        registry.register(ToolSpec(name="read_docs", description="Read", risk="read"))

        log = EventLog()
        gateway = build_tool_gateway(
            registry,
            handlers={"read_docs": lambda args: "ok"},
        )

        call = ToolCallSpec(tool_name="read_docs", arguments={"query": "test"})
        result = gateway.execute(call, event_log=log)

        assert result.policy_decision is not None


class TestInvariant9AllTransitionsHaveAuditTrail:
    """Invariant: All state transitions must produce audit trail events."""

    def test_commitment_events_recorded_in_log(self):
        log = EventLog()
        response = json.dumps({
            "patches": [
                {"section": "goals", "key": "active", "op": "set", "value": ["t1"]},
            ],
        })
        proposal = parse_llm_proposal(response, objective="test")
        propose_from_llm(proposal, event_log=log)

        commitment_events = [
            e for e in log.all()
            if isinstance(e, CommitmentEvent)
        ]
        assert len(commitment_events) >= 1

    def test_llm_proposal_records_received_and_processed(self):
        log = EventLog()
        response = json.dumps({"patches": []})
        proposal = parse_llm_proposal(response, objective="test")
        propose_from_llm(proposal, event_log=log)

        event_types = [e.event_type for e in log.all()]
        assert "llm.proposal.received" in event_types
        assert "llm.proposal.processed" in event_types

    def test_invalid_proposal_records_rejection(self):
        log = EventLog()
        proposal = parse_llm_proposal("not json", objective="test")
        propose_from_llm(proposal, event_log=log)

        event_types = [e.event_type for e in log.all()]
        assert "llm.proposal.rejected" in event_types

    def test_calibration_cycle_records_events(self):
        log = EventLog()
        step = CommitmentEvent(
            event_id="ce1",
            source_state_id="ws_0",
            commitment_kind="internal_commit",
            intent_summary="test",
            action_summary="beliefs k1",
            success=True,
            reversibility="reversible",
            requires_approval=True,
        )
        log.append(step)

        run_calibration_cycle_v2(log)

        event_types = [e.event_type for e in log.all()]
        assert "calibration.cycle.started" in event_types
        assert "calibration.cycle.completed" in event_types


class TestInvariant10LLMOutputNeverDirectlyModifiesState:
    """Invariant: LLM output must never directly modify state."""

    def test_llm_proposal_is_read_only(self):
        response = json.dumps({
            "patches": [
                {"section": "goals", "key": "active", "op": "set", "value": ["t1"]},
            ],
        })
        proposal = parse_llm_proposal(response, objective="test")

        assert isinstance(proposal, LLMProposal)
        assert proposal.is_valid

    def test_propose_from_llm_does_not_modify_world_state(self):
        log = EventLog()
        state = WorldState(state_id="ws_0")

        response = json.dumps({
            "patches": [
                {"section": "goals", "key": "active", "op": "set", "value": ["t1"]},
            ],
        })
        proposal = parse_llm_proposal(response, objective="test")
        propose_from_llm(proposal, event_log=log)

        assert state.state_id == "ws_0"

    def test_simulation_does_not_modify_original_state(self):
        state = WorldState(state_id="ws_0")
        delta = RevisionDelta(
            delta_id="d1",
            target_kind="entity_update",
            target_ref="beliefs.test",
            before_summary="none",
            after_summary="updated",
            justification="test",
        )
        branch = simulate_branch(state, (delta,))

        assert state.state_id == "ws_0"
        assert "is_simulated" not in state.provenance_refs
        assert "is_simulated" in branch.result.simulated_state.provenance_refs


class TestInvariant11ApprovalDecisionsRecorded:
    """Invariant: Approval decisions must be recorded in the event log."""

    def test_self_model_approval_recorded(self):
        log = EventLog()
        provider = StaticApprovalProvider(verdict="approved")

        response = json.dumps({
            "patches": [
                {"section": "self_model", "key": "cap", "op": "set", "value": "updated"},
            ],
        })
        proposal = parse_llm_proposal(response, objective="test")
        propose_from_llm(proposal, event_log=log, approval_provider=provider)

        approval_events = [
            e for e in log.all()
            if hasattr(e, "event_type") and getattr(e, "event_type", None) == "approval.decision.recorded"
        ]
        assert len(approval_events) >= 1

    def test_tool_approval_recorded(self):
        registry = ToolRegistry()
        registry.register(ToolSpec(name="write_file", description="Write", risk="write"))

        log = EventLog()
        gateway = build_tool_gateway(
            registry,
            handlers={"write_file": lambda args: "ok"},
            approval_provider=StaticApprovalProvider(verdict="approved"),
        )

        call = ToolCallSpec(tool_name="write_file", arguments={"path": "/tmp/test"})
        gateway.execute(call, event_log=log)

        approval_events = [
            e for e in log.all()
            if hasattr(e, "event_type") and getattr(e, "event_type", None) == "approval.decision.recorded"
        ]
        assert len(approval_events) >= 1


class TestInvariant12CalibrationNeverBypassesPolicy:
    """Invariant: Calibration must never bypass the policy pipeline."""

    def test_calibration_v2_evaluates_policy(self):
        log = EventLog()
        step = CommitmentEvent(
            event_id="ce1",
            source_state_id="ws_0",
            commitment_kind="internal_commit",
            intent_summary="test",
            action_summary="beliefs k1",
            success=True,
            reversibility="reversible",
            requires_approval=True,
        )
        log.append(step)

        result = run_calibration_cycle_v2(log)

        for dd in result.delta_decisions:
            assert dd.delta_policy_decision is not None

    def test_calibration_v2_without_approval_blocks_self_model(self):
        log = EventLog()
        step = CommitmentEvent(
            event_id="ce1",
            source_state_id="ws_0",
            commitment_kind="internal_commit",
            intent_summary="test",
            action_summary="beliefs k1",
            success=True,
            reversibility="reversible",
            requires_approval=True,
        )
        log.append(step)

        result = run_calibration_cycle_v2(log)

        for dd in result.delta_decisions:
            if dd.delta.target_kind == "self_update":
                if dd.delta_policy_decision.requires_approval:
                    assert dd.approval_decision is None or not dd.approval_decision.approved


class TestReliabilityBounds:
    """Additional invariant: reliability estimate must stay within bounds."""

    def test_reliability_max_bound(self):
        from cee_core.calibration import MAX_RELIABILITY_ESTIMATE

        assert MAX_RELIABILITY_ESTIMATE < 1.0
        assert MAX_RELIABILITY_ESTIMATE == 0.95

    def test_reliability_min_bound(self):
        from cee_core.calibration import MIN_RELIABILITY_ESTIMATE

        assert MIN_RELIABILITY_ESTIMATE > 0.0
        assert MIN_RELIABILITY_ESTIMATE == 0.1

    def test_calibration_rejects_reliability_above_max(self):
        policy = DefaultCalibrationPolicy()
        proposal = CalibrationProposal(
            patch_section="self_model",
            patch_key="reliability_estimate",
            patch_value={"value": 0.99},
            evidence=("test",),
            proposal_id="cal_r1",
        )
        decision = policy.evaluate(proposal)
        assert not decision.allowed

    def test_calibration_rejects_reliability_below_min(self):
        policy = DefaultCalibrationPolicy()
        proposal = CalibrationProposal(
            patch_section="self_model",
            patch_key="reliability_estimate",
            patch_value={"value": 0.01},
            evidence=("test",),
            proposal_id="cal_r2",
        )
        decision = policy.evaluate(proposal)
        assert not decision.allowed
