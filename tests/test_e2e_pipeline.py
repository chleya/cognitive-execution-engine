"""End-to-end integration tests for the complete CEE pipeline.

These tests verify that all 10 AGENTS.md components work together
as a coherent system:

1. State schema (WorldState)
2. Event model (CommitmentEvent/ModelRevisionEvent)
3. Reducer semantics (evaluate_delta_policy)
4. Policy checks (DeltaPolicyDecision/ToolPolicyDecision)
5. Audit/replay (EventLog + replay_world_state)
6. Tool gateway (ToolGateway)
7. Human approval (ApprovalProvider)
8. LLM proposal adapters (LLMProposal/propose_from_llm)
9. Memory promotion (MemoryPromotionPolicy/promote_to_memory)
10. Self-model calibration (DefaultCalibrationPolicy/run_calibration_cycle_v2)

Plus the reality interface integration with ToolGateway.
"""

import json
import pytest

from cee_core.approval import StaticApprovalProvider
from cee_core.calibration import (
    DefaultCalibrationPolicy,
    apply_calibration_to_world_state,
    run_calibration_cycle_v2,
)
from cee_core.commitment import CommitmentEvent
from cee_core.event_log import EventLog
from cee_core.events import DeliberationEvent
from cee_core.llm_proposal import (
    LLMProposal,
    parse_llm_proposal,
    propose_from_llm,
)
from cee_core.memory_promotion import (
    promote_from_observation,
    promote_from_revision,
)
from cee_core.memory_store import MemoryStore
from cee_core.observations import ObservationCandidate
from cee_core.reality_interface import (
    GatewayContactResult,
    execute_commitment_via_gateway,
)
from cee_core.revision import ModelRevisionEvent
from cee_core.self_observation import BehavioralSnapshot
from cee_core.tools import ToolCallSpec, ToolRegistry, ToolSpec
from cee_core.tool_gateway import build_tool_gateway
from cee_core.world_schema import RevisionDelta
from cee_core.world_state import WorldState


def _setup_tool_gateway():
    registry = ToolRegistry()
    registry.register(ToolSpec(name="read_docs", description="Read documents", risk="read"))
    registry.register(ToolSpec(name="write_file", description="Write file", risk="write"))
    registry.register(ToolSpec(name="send_email", description="Send email", risk="external_side_effect"))

    handlers = {
        "read_docs": lambda args: f"Read {args.get('query', 'unknown')}",
        "write_file": lambda args: f"Wrote to {args.get('path', 'unknown')}",
        "send_email": lambda args: f"Sent email to {args.get('to', 'unknown')}",
    }

    provider = StaticApprovalProvider(verdict="approved")
    gateway = build_tool_gateway(registry, handlers=handlers, approval_provider=provider)
    return registry, gateway


class TestFullPipelineLLMProposalToState:
    def test_llm_proposal_to_approved_deltas_to_world_state(self):
        log = EventLog()
        registry, gateway = _setup_tool_gateway()
        provider = StaticApprovalProvider(verdict="approved")

        response = json.dumps({
            "patches": [
                {"section": "goals", "key": "active", "op": "set", "value": ["analyze_docs"]},
                {"section": "beliefs", "key": "facts", "op": "set", "value": "document_found"},
            ],
            "tool_calls": [
                {"tool_name": "read_docs", "arguments": {"query": "test"}},
            ],
            "rationale": "analyze documents for key information",
        })

        proposal = parse_llm_proposal(response, objective="analyze", tool_registry=registry)
        result = propose_from_llm(
            proposal,
            event_log=log,
            approval_provider=provider,
            tool_registry=registry,
        )

        assert result.allowed_delta_count >= 1
        assert result.allowed_tool_count >= 1

        state = WorldState(state_id="ws_0")
        for rev in result.revision_events:
            state = _apply_revision_to_state(state, rev)

        assert state.state_id != "ws_0"

    def test_llm_proposal_with_self_model_requires_approval(self):
        log = EventLog()
        provider = StaticApprovalProvider(verdict="approved")

        response = json.dumps({
            "patches": [
                {"section": "self_model", "key": "capability", "op": "set", "value": "updated"},
            ],
        })

        proposal = parse_llm_proposal(response, objective="test")
        result = propose_from_llm(proposal, event_log=log, approval_provider=provider)

        assert result.requires_approval_delta_count >= 1
        assert result.allowed_delta_count >= 1

    def test_llm_proposal_self_model_rejected_by_approval(self):
        log = EventLog()
        provider = StaticApprovalProvider(verdict="rejected")

        response = json.dumps({
            "patches": [
                {"section": "self_model", "key": "capability", "op": "set", "value": "updated"},
            ],
        })

        proposal = parse_llm_proposal(response, objective="test")
        result = propose_from_llm(proposal, event_log=log, approval_provider=provider)

        assert result.allowed_delta_count == 0

    def test_llm_proposal_forbidden_field_rejected(self):
        response = json.dumps({
            "patches": [],
            "execute": True,
            "bypass": "policy",
        })

        proposal = parse_llm_proposal(response, objective="test")
        assert not proposal.is_valid

        log = EventLog()
        result = propose_from_llm(proposal, event_log=log)
        assert result.allowed_delta_count == 0

    def test_complete_audit_trail(self):
        log = EventLog()
        registry, gateway = _setup_tool_gateway()
        provider = StaticApprovalProvider(verdict="approved")

        response = json.dumps({
            "patches": [
                {"section": "goals", "key": "active", "op": "set", "value": ["t1"]},
                {"section": "self_model", "key": "cap", "op": "set", "value": "updated"},
            ],
            "tool_calls": [
                {"tool_name": "read_docs", "arguments": {"query": "test"}},
            ],
        })

        proposal = parse_llm_proposal(response, objective="test", tool_registry=registry)
        propose_from_llm(proposal, event_log=log, approval_provider=provider, tool_registry=registry)

        event_types = [e.event_type for e in log.all()]
        assert "llm.proposal.received" in event_types
        assert "llm.proposal.processed" in event_types
        assert "commitment" in event_types
        assert "revision" in event_types
        assert "approval.decision.recorded" in event_types


class TestFullPipelineToolGatewayToMemory:
    def test_tool_execution_to_observation_to_memory(self, tmp_path):
        log = EventLog()
        registry, gateway = _setup_tool_gateway()

        call = ToolCallSpec(tool_name="read_docs", arguments={"query": "important doc"})
        result = gateway.execute(call, event_log=log, promote_to_belief_key="doc_content")

        assert result.succeeded
        assert result.observation is not None

        memory_store = MemoryStore(storage_path=str(tmp_path / "mem"))
        mem_result = promote_from_observation(
            result.observation,
            task_signature="tool.read_docs",
            task_summary="Read important document",
            domain_label="document_analysis",
            evidence_refs=(result.commitment_event.event_id,),
            event_log=log,
            memory_store=memory_store,
        )

        assert mem_result.promoted
        assert mem_result.memory_id is not None
        assert memory_store.get_count() == 1

    def test_tool_execution_rejected_no_memory(self, tmp_path):
        log = EventLog()
        registry = ToolRegistry()
        registry.register(ToolSpec(name="delete_all", description="Delete", risk="external_side_effect"))
        gateway = build_tool_gateway(
            registry,
            handlers={"delete_all": lambda args: "deleted"},
            approval_provider=StaticApprovalProvider(verdict="rejected"),
        )

        call = ToolCallSpec(tool_name="delete_all", arguments={})
        result = gateway.execute(call, event_log=log)

        assert not result.succeeded
        assert result.observation is None


class TestFullPipelineRealityInterface:
    def test_commitment_via_gateway(self):
        log = EventLog()
        registry, gateway = _setup_tool_gateway()

        commitment = CommitmentEvent(
            event_id="ce_test_1",
            source_state_id="ws_0",
            commitment_kind="tool_contact",
            intent_summary="Read test document",
            action_summary="read_docs",
        )

        result = execute_commitment_via_gateway(
            commitment,
            gateway,
            event_log=log,
            tool_arguments={"query": "test"},
        )

        assert result.success
        assert result.policy_verdict == "allow"

    def test_commitment_via_gateway_write_needs_approval(self):
        log = EventLog()
        registry = ToolRegistry()
        registry.register(ToolSpec(name="write_file", description="Write", risk="write"))
        gateway = build_tool_gateway(
            registry,
            handlers={"write_file": lambda args: "ok"},
            approval_provider=StaticApprovalProvider(verdict="approved"),
        )

        commitment = CommitmentEvent(
            event_id="ce_test_2",
            source_state_id="ws_0",
            commitment_kind="tool_contact",
            intent_summary="Write test file",
            action_summary="write_file",
        )

        result = execute_commitment_via_gateway(
            commitment,
            gateway,
            event_log=log,
            tool_arguments={"path": "/tmp/test"},
        )

        assert result.success
        assert result.approval_verdict == "approved"

    def test_commitment_via_gateway_denied(self):
        log = EventLog()
        registry = ToolRegistry()
        registry.register(ToolSpec(name="delete_all", description="Delete", risk="external_side_effect"))
        gateway = build_tool_gateway(
            registry,
            handlers={"delete_all": lambda args: "deleted"},
            approval_provider=StaticApprovalProvider(verdict="rejected"),
        )

        commitment = CommitmentEvent(
            event_id="ce_test_3",
            source_state_id="ws_0",
            commitment_kind="tool_contact",
            intent_summary="Delete everything",
            action_summary="delete_all",
        )

        result = execute_commitment_via_gateway(
            commitment,
            gateway,
            event_log=log,
        )

        assert not result.success

    def test_commitment_via_gateway_audit_trail(self):
        log = EventLog()
        registry, gateway = _setup_tool_gateway()

        commitment = CommitmentEvent(
            event_id="ce_test_4",
            source_state_id="ws_0",
            commitment_kind="tool_contact",
            intent_summary="Read test document",
            action_summary="read_docs",
        )

        execute_commitment_via_gateway(
            commitment,
            gateway,
            event_log=log,
            tool_arguments={"query": "test"},
        )

        event_types = [e.event_type for e in log.all()]
        assert "reality.gateway_contact.completed" in event_types

    def test_commitment_via_gateway_rejects_non_tool_contact(self):
        log = EventLog()
        registry, gateway = _setup_tool_gateway()

        commitment = CommitmentEvent(
            event_id="ce_test_5",
            source_state_id="ws_0",
            commitment_kind="observe",
            intent_summary="Observe",
            action_summary="read_docs",
        )

        with pytest.raises(ValueError, match="tool_contact"):
            execute_commitment_via_gateway(commitment, gateway, event_log=log)

    def test_commitment_via_gateway_no_tool_name(self):
        log = EventLog()
        registry, gateway = _setup_tool_gateway()

        commitment = CommitmentEvent(
            event_id="ce_test_6",
            source_state_id="ws_0",
            commitment_kind="tool_contact",
            intent_summary="No tool specified",
            action_summary="",
        )

        result = execute_commitment_via_gateway(commitment, gateway, event_log=log)
        assert not result.success


class TestFullPipelineCalibrationToState:
    def test_calibration_cycle_to_world_state(self):
        log = EventLog()

        from cee_core.deliberation import ReasoningStep
        step = ReasoningStep(
            task_id="t1",
            summary="test",
            hypothesis="h",
            missing_information=("m1",),
            candidate_actions=("propose_redirect",),
            chosen_action="propose_redirect",
            rationale="missing info",
            stop_condition="done",
        )
        log.append(DeliberationEvent(reasoning_step=step))

        for _ in range(3):
            log.append(CommitmentEvent(
                event_id=f"ce-test-{_}",
                source_state_id="",
                commitment_kind="internal_commit",
                intent_summary="test",
                action_summary="beliefs k1",
                success=True,
                reversibility="reversible",
                requires_approval=True,
            ))

        provider = StaticApprovalProvider(verdict="approved")
        cal_result = run_calibration_cycle_v2(log, approval_provider=provider)

        if cal_result.approved_count > 0:
            state = WorldState(state_id="ws_0")
            new_state = apply_calibration_to_world_state(cal_result, state)
            assert new_state.state_id != "ws_0"

    def test_calibration_forbidden_key_blocked(self):
        from cee_core.self_observation import CalibrationProposal
        from cee_core.calibration import DefaultCalibrationPolicy

        proposal = CalibrationProposal(
            patch_section="self_model",
            patch_key="consciousness",
            patch_value={"claim": "I am aware"},
            evidence=("observation",),
            proposal_id="cal_test_1",
        )
        policy = DefaultCalibrationPolicy()
        decision = policy.evaluate(proposal)

        assert not decision.allowed


class TestFullPipelineRevisionToMemory:
    def test_revision_to_memory_promotion(self, tmp_path):
        log = EventLog()
        memory_store = MemoryStore(storage_path=str(tmp_path / "mem"))

        delta = RevisionDelta(
            delta_id="delta-1",
            target_kind="entity_update",
            target_ref="beliefs.test_fact",
            before_summary="unknown",
            after_summary="verified",
            justification="confirmed by tool observation",
        )
        rev = ModelRevisionEvent(
            revision_id="rev-1",
            prior_state_id="ws_0",
            caused_by_event_id="ce-1",
            revision_kind="expansion",
            deltas=(delta,),
            resulting_state_id="ws_1",
            revision_summary="Updated belief based on observation",
        )

        result = promote_from_revision(
            rev,
            task_signature="belief_update.from_observation",
            task_summary="Updated belief based on observation",
            domain_label="core",
            evidence_refs=("ce-1",),
            event_log=log,
            memory_store=memory_store,
        )

        assert result.promoted
        assert memory_store.get_count() == 1

        stored = memory_store.get_memory(result.memory_id)
        assert stored is not None
        assert stored.task_signature == "belief_update.from_observation"


class TestFullPipelineDeterministicReplay:
    def test_event_log_replay_produces_same_state(self):
        log = EventLog()

        delta = RevisionDelta(
            delta_id="delta-1",
            target_kind="goal_update",
            target_ref="goals.active",
            before_summary="none",
            after_summary="analyze",
            justification="test",
        )
        rev = ModelRevisionEvent(
            revision_id="rev-1",
            prior_state_id="ws_0",
            caused_by_event_id="ce-1",
            revision_kind="confirmation",
            deltas=(delta,),
            resulting_state_id="ws_1",
            revision_summary="test",
        )
        log.append(rev)

        state1 = log.replay_world_state()
        state2 = log.replay_world_state()

        assert state1.state_id == state2.state_id
        assert state1.parent_state_id == state2.parent_state_id

    def test_multiple_revisions_replay_correctly(self):
        log = EventLog()

        for i in range(5):
            delta = RevisionDelta(
                delta_id=f"delta-{i}",
                target_kind="entity_update",
                target_ref=f"beliefs.fact_{i}",
                before_summary="unknown",
                after_summary=f"fact_{i}",
                justification=f"observation {i}",
            )
            rev = ModelRevisionEvent(
                revision_id=f"rev-{i}",
                prior_state_id=f"ws_{i}",
                caused_by_event_id=f"ce-{i}",
                revision_kind="expansion",
                deltas=(delta,),
                resulting_state_id=f"ws_{i + 1}",
                revision_summary=f"fact {i}",
            )
            log.append(rev)

        state = log.replay_world_state()
        assert state.state_id == "ws_5"


def _apply_revision_to_state(state: WorldState, rev: ModelRevisionEvent) -> WorldState:
    """Apply a revision event to a WorldState."""
    from dataclasses import replace
    return replace(
        state,
        state_id=rev.resulting_state_id,
        parent_state_id=rev.prior_state_id,
        provenance_refs=state.provenance_refs + (rev.revision_id,),
    )
