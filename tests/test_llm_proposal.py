"""Tests for LLM Proposal Adapters.

Tests cover:
- LLMProposal parsing and validation
- Forbidden field rejection
- Policy evaluation for proposed deltas
- Approval routing for requires_approval deltas
- Tool call policy and approval
- Audit trail completeness
- Adapter protocol conformance
- Deterministic replayability
"""

import json

import pytest

from cee_core.approval import (
    ApprovalDecision,
    ApprovalRequest,
    StaticApprovalProvider,
)
from cee_core.event_log import EventLog
from cee_core.llm_proposal import (
    DeltaProposalDecision,
    LLMProposal,
    LLMProposalResult,
    PlanFormatAdapter,
    RawFormatAdapter,
    ToolProposalDecision,
    parse_llm_proposal,
    propose_from_llm,
    FORBIDDEN_LLM_FIELDS,
    VALID_PATCH_OPS,
    VALID_TARGET_KINDS,
)
from cee_core.tools import ToolRegistry, ToolSpec


def _valid_plan_json(**overrides) -> str:
    payload = {
        "patches": [
            {"section": "goals", "key": "active", "op": "set", "value": ["task_1"]},
            {"section": "memory", "key": "working", "op": "append", "value": {"data": "test"}},
        ],
        "tool_calls": [],
        "rationale": "test plan",
    }
    payload.update(overrides)
    return json.dumps(payload)


class TestLLMProposalParsing:
    def test_parse_valid_plan_response(self):
        response = _valid_plan_json()
        proposal = parse_llm_proposal(response, objective="test objective")

        assert proposal.is_valid
        assert len(proposal.candidate_deltas) == 2
        assert proposal.rationale == "test plan"
        assert proposal.objective == "test objective"

    def test_parse_strips_code_fences(self):
        response = f"```json\n{_valid_plan_json()}\n```"
        proposal = parse_llm_proposal(response, objective="test")

        assert proposal.is_valid
        assert len(proposal.candidate_deltas) == 2

    def test_parse_rejects_invalid_json(self):
        proposal = parse_llm_proposal("not json at all", objective="test")

        assert not proposal.is_valid
        assert any("invalid JSON" in e for e in proposal.validation_errors)

    def test_parse_rejects_non_object_json(self):
        proposal = parse_llm_proposal(json.dumps(["list", "not", "object"]), objective="test")

        assert not proposal.is_valid
        assert any("JSON object" in e for e in proposal.validation_errors)

    def test_parse_rejects_forbidden_execute_field(self):
        response = json.dumps({
            "patches": [],
            "execute": True,
        })
        proposal = parse_llm_proposal(response, objective="test")

        assert not proposal.is_valid
        assert any("forbidden" in e.lower() for e in proposal.validation_errors)

    def test_parse_rejects_forbidden_bypass_field(self):
        response = json.dumps({
            "patches": [],
            "bypass": "policy",
        })
        proposal = parse_llm_proposal(response, objective="test")

        assert not proposal.is_valid
        assert any("forbidden" in e.lower() for e in proposal.validation_errors)

    def test_parse_rejects_forbidden_sudo_field(self):
        response = json.dumps({
            "patches": [],
            "sudo": True,
        })
        proposal = parse_llm_proposal(response, objective="test")

        assert not proposal.is_valid

    def test_parse_rejects_forced_override_field(self):
        response = json.dumps({
            "patches": [],
            "override": True,
        })
        proposal = parse_llm_proposal(response, objective="test")

        assert not proposal.is_valid

    def test_parse_rejects_invalid_patch_op(self):
        response = json.dumps({
            "patches": [
                {"section": "goals", "key": "active", "op": "execute", "value": "test"},
            ],
        })
        proposal = parse_llm_proposal(response, objective="test")

        assert not proposal.is_valid
        assert any("invalid op" in e for e in proposal.validation_errors)

    def test_parse_rejects_patch_missing_section(self):
        response = json.dumps({
            "patches": [
                {"key": "active", "op": "set", "value": "test"},
            ],
        })
        proposal = parse_llm_proposal(response, objective="test")

        assert not proposal.is_valid
        assert any("missing section" in e for e in proposal.validation_errors)

    def test_parse_rejects_patch_missing_key(self):
        response = json.dumps({
            "patches": [
                {"section": "goals", "op": "set", "value": "test"},
            ],
        })
        proposal = parse_llm_proposal(response, objective="test")

        assert not proposal.is_valid
        assert any("missing key" in e for e in proposal.validation_errors)

    def test_parse_rejects_non_dict_patch(self):
        response = json.dumps({
            "patches": ["not a dict"],
        })
        proposal = parse_llm_proposal(response, objective="test")

        assert not proposal.is_valid
        assert any("must be a JSON object" in e for e in proposal.validation_errors)

    def test_parse_handles_empty_patches(self):
        response = json.dumps({"patches": []})
        proposal = parse_llm_proposal(response, objective="test")

        assert proposal.is_valid
        assert len(proposal.candidate_deltas) == 0

    def test_parse_handles_missing_patches(self):
        response = json.dumps({"rationale": "no patches"})
        proposal = parse_llm_proposal(response, objective="test")

        assert proposal.is_valid
        assert len(proposal.candidate_deltas) == 0

    def test_parse_handles_non_list_tool_calls(self):
        response = json.dumps({
            "patches": [],
            "tool_calls": "not a list",
        })
        proposal = parse_llm_proposal(response, objective="test")

        assert proposal.is_valid
        assert len(proposal.proposed_tool_calls) == 0

    def test_parse_valid_tool_calls(self):
        response = json.dumps({
            "patches": [],
            "tool_calls": [
                {"tool_name": "read_docs", "arguments": {"query": "test"}},
            ],
        })
        proposal = parse_llm_proposal(response, objective="test")

        assert proposal.is_valid
        assert len(proposal.proposed_tool_calls) == 1
        assert proposal.proposed_tool_calls[0].tool_name == "read_docs"

    def test_parse_rejects_tool_call_missing_name(self):
        response = json.dumps({
            "patches": [],
            "tool_calls": [
                {"arguments": {"query": "test"}},
            ],
        })
        proposal = parse_llm_proposal(response, objective="test")

        assert not proposal.is_valid
        assert any("missing tool_name" in e for e in proposal.validation_errors)

    def test_parse_rejects_tool_call_non_dict_arguments(self):
        response = json.dumps({
            "patches": [],
            "tool_calls": [
                {"tool_name": "read_docs", "arguments": "not a dict"},
            ],
        })
        proposal = parse_llm_proposal(response, objective="test")

        assert not proposal.is_valid
        assert any("arguments must be a JSON object" in e for e in proposal.validation_errors)

    def test_parse_validates_tool_against_registry(self):
        registry = ToolRegistry()
        registry.register(ToolSpec(name="read_docs", description="Read", risk="read"))

        response = json.dumps({
            "patches": [],
            "tool_calls": [
                {"tool_name": "unknown_tool", "arguments": {}},
            ],
        })
        proposal = parse_llm_proposal(response, objective="test", tool_registry=registry)

        assert not proposal.is_valid
        assert any("unknown tool" in e for e in proposal.validation_errors)

    def test_parse_allows_known_tool_in_registry(self):
        registry = ToolRegistry()
        registry.register(ToolSpec(name="read_docs", description="Read", risk="read"))

        response = json.dumps({
            "patches": [],
            "tool_calls": [
                {"tool_name": "read_docs", "arguments": {"query": "test"}},
            ],
        })
        proposal = parse_llm_proposal(response, objective="test", tool_registry=registry)

        assert proposal.is_valid

    def test_parse_section_to_target_kind_mapping(self):
        response = json.dumps({
            "patches": [
                {"section": "goals", "key": "active", "op": "set", "value": "x"},
                {"section": "self_model", "key": "cap", "op": "set", "value": "y"},
                {"section": "memory", "key": "working", "op": "append", "value": "z"},
                {"section": "beliefs", "key": "hypotheses", "op": "set", "value": "h"},
                {"section": "beliefs", "key": "anchored_facts", "op": "set", "value": "f"},
                {"section": "domain_data", "key": "extra", "op": "set", "value": "d"},
            ],
        })
        proposal = parse_llm_proposal(response, objective="test")

        assert proposal.is_valid
        kinds = [d.target_kind for d in proposal.candidate_deltas]
        assert kinds == [
            "goal_update",
            "self_update",
            "entity_update",
            "hypothesis_update",
            "anchor_add",
            "entity_update",
        ]

    def test_parse_objective_from_payload_if_not_provided(self):
        response = json.dumps({
            "patches": [],
            "objective": "from payload",
        })
        proposal = parse_llm_proposal(response)

        assert proposal.objective == "from payload"

    def test_parse_provided_objective_takes_precedence(self):
        response = json.dumps({
            "patches": [],
            "objective": "from payload",
        })
        proposal = parse_llm_proposal(response, objective="from argument")

        assert proposal.objective == "from argument"


class TestLLMProposalDataTypes:
    def test_proposal_to_dict(self):
        proposal = parse_llm_proposal(_valid_plan_json(), objective="test")
        d = proposal.to_dict()

        assert d["schema_version"] == "cee.llm_proposal.v1"
        assert d["proposal_id"] == proposal.proposal_id
        assert d["source"] == "llm_adapter"
        assert d["is_valid"] is True
        assert len(d["candidate_deltas"]) == 2

    def test_proposal_default_id_is_unique(self):
        p1 = LLMProposal()
        p2 = LLMProposal()
        assert p1.proposal_id != p2.proposal_id

    def test_delta_proposal_decision_allowed(self):
        from cee_core.world_schema import RevisionDelta
        from cee_core.planner import DeltaPolicyDecision

        delta = RevisionDelta(
            delta_id="d1",
            target_kind="goal_update",
            target_ref="goals.active",
            before_summary="none",
            after_summary="active",
            justification="test",
        )
        policy = DeltaPolicyDecision(
            allowed=True,
            requires_approval=False,
            reason="allowed",
        )
        decision = DeltaProposalDecision(delta=delta, policy_decision=policy)

        assert decision.is_allowed
        assert not decision.is_blocked

    def test_delta_proposal_decision_blocked_by_policy(self):
        from cee_core.world_schema import RevisionDelta
        from cee_core.planner import DeltaPolicyDecision

        delta = RevisionDelta(
            delta_id="d1",
            target_kind="self_update",
            target_ref="policy.rule",
            before_summary="none",
            after_summary="changed",
            justification="test",
        )
        policy = DeltaPolicyDecision(
            allowed=False,
            requires_approval=False,
            reason="denied",
        )
        decision = DeltaProposalDecision(delta=delta, policy_decision=policy)

        assert decision.is_blocked
        assert not decision.is_allowed

    def test_delta_proposal_decision_requires_approval_approved(self):
        from cee_core.world_schema import RevisionDelta
        from cee_core.planner import DeltaPolicyDecision

        delta = RevisionDelta(
            delta_id="d1",
            target_kind="self_update",
            target_ref="self_model.cap",
            before_summary="none",
            after_summary="updated",
            justification="test",
        )
        policy = DeltaPolicyDecision(
            allowed=False,
            requires_approval=True,
            reason="needs approval",
        )
        approval = ApprovalDecision(
            transition_trace_id="t1",
            verdict="approved",
            decided_by="human",
            reason="ok",
        )
        decision = DeltaProposalDecision(
            delta=delta,
            policy_decision=policy,
            approval_decision=approval,
        )

        assert decision.is_allowed

    def test_delta_proposal_decision_requires_approval_rejected(self):
        from cee_core.world_schema import RevisionDelta
        from cee_core.planner import DeltaPolicyDecision

        delta = RevisionDelta(
            delta_id="d1",
            target_kind="self_update",
            target_ref="self_model.cap",
            before_summary="none",
            after_summary="updated",
            justification="test",
        )
        policy = DeltaPolicyDecision(
            allowed=False,
            requires_approval=True,
            reason="needs approval",
        )
        approval = ApprovalDecision(
            transition_trace_id="t1",
            verdict="rejected",
            decided_by="human",
            reason="no",
        )
        decision = DeltaProposalDecision(
            delta=delta,
            policy_decision=policy,
            approval_decision=approval,
        )

        assert decision.is_blocked

    def test_delta_proposal_decision_requires_approval_no_decision(self):
        from cee_core.world_schema import RevisionDelta
        from cee_core.planner import DeltaPolicyDecision

        delta = RevisionDelta(
            delta_id="d1",
            target_kind="self_update",
            target_ref="self_model.cap",
            before_summary="none",
            after_summary="updated",
            justification="test",
        )
        policy = DeltaPolicyDecision(
            allowed=False,
            requires_approval=True,
            reason="needs approval",
        )
        decision = DeltaProposalDecision(delta=delta, policy_decision=policy)

        assert decision.is_blocked

    def test_tool_proposal_decision_allowed(self):
        from cee_core.tools import ToolCallSpec, ToolPolicyDecision

        call = ToolCallSpec(tool_name="read_docs", arguments={"q": "test"})
        policy = ToolPolicyDecision(verdict="allow", reason="ok", tool_name="read_docs")
        decision = ToolProposalDecision(call=call, policy_decision=policy)

        assert decision.is_allowed
        assert not decision.is_blocked

    def test_tool_proposal_decision_blocked(self):
        from cee_core.tools import ToolCallSpec, ToolPolicyDecision

        call = ToolCallSpec(tool_name="delete_all", arguments={})
        policy = ToolPolicyDecision(verdict="deny", reason="blocked", tool_name="delete_all")
        decision = ToolProposalDecision(call=call, policy_decision=policy)

        assert decision.is_blocked


class TestProposeFromLLM:
    def test_proposal_received_event(self):
        log = EventLog()
        proposal = parse_llm_proposal(_valid_plan_json(), objective="test")
        propose_from_llm(proposal, event_log=log)

        events = log.all()
        assert any(e.event_type == "llm.proposal.received" for e in events)

    def test_proposal_processed_event(self):
        log = EventLog()
        proposal = parse_llm_proposal(_valid_plan_json(), objective="test")
        propose_from_llm(proposal, event_log=log)

        events = log.all()
        assert any(e.event_type == "llm.proposal.processed" for e in events)

    def test_invalid_proposal_rejected_event(self):
        log = EventLog()
        proposal = parse_llm_proposal("not json", objective="test")
        result = propose_from_llm(proposal, event_log=log)

        assert not proposal.is_valid
        events = log.all()
        assert any(e.event_type == "llm.proposal.rejected" for e in events)
        assert result.allowed_delta_count == 0
        assert result.blocked_delta_count == 0

    def test_allowed_deltas_produce_commitment_and_revision(self):
        log = EventLog()
        proposal = parse_llm_proposal(_valid_plan_json(), objective="test")
        result = propose_from_llm(proposal, event_log=log)

        assert result.allowed_delta_count > 0
        assert len(result.commitment_events) > 0
        assert len(result.revision_events) > 0

    def test_policy_denied_deltas_are_blocked(self):
        response = json.dumps({
            "patches": [
                {"section": "policy", "key": "rule1", "op": "set", "value": "bypass"},
            ],
        })
        log = EventLog()
        proposal = parse_llm_proposal(response, objective="test")
        result = propose_from_llm(proposal, event_log=log)

        assert result.blocked_delta_count > 0
        assert result.allowed_delta_count == 0

    def test_self_update_requires_approval(self):
        response = json.dumps({
            "patches": [
                {"section": "self_model", "key": "capability", "op": "set", "value": "updated"},
            ],
        })
        log = EventLog()
        proposal = parse_llm_proposal(response, objective="test")
        result = propose_from_llm(proposal, event_log=log)

        assert result.requires_approval_delta_count > 0

    def test_self_update_approved_with_provider(self):
        response = json.dumps({
            "patches": [
                {"section": "self_model", "key": "capability", "op": "set", "value": "updated"},
            ],
        })
        log = EventLog()
        provider = StaticApprovalProvider(verdict="approved")
        proposal = parse_llm_proposal(response, objective="test")
        result = propose_from_llm(proposal, event_log=log, approval_provider=provider)

        assert result.allowed_delta_count > 0

    def test_self_update_rejected_by_provider(self):
        response = json.dumps({
            "patches": [
                {"section": "self_model", "key": "capability", "op": "set", "value": "updated"},
            ],
        })
        log = EventLog()
        provider = StaticApprovalProvider(verdict="rejected")
        proposal = parse_llm_proposal(response, objective="test")
        result = propose_from_llm(proposal, event_log=log, approval_provider=provider)

        assert result.allowed_delta_count == 0

    def test_no_approval_provider_rejects_requires_approval(self):
        response = json.dumps({
            "patches": [
                {"section": "self_model", "key": "capability", "op": "set", "value": "updated"},
            ],
        })
        log = EventLog()
        proposal = parse_llm_proposal(response, objective="test")
        result = propose_from_llm(proposal, event_log=log)

        assert result.allowed_delta_count == 0

    def test_approval_decision_recorded_in_audit_trail(self):
        response = json.dumps({
            "patches": [
                {"section": "self_model", "key": "capability", "op": "set", "value": "updated"},
            ],
        })
        log = EventLog()
        provider = StaticApprovalProvider(verdict="approved")
        proposal = parse_llm_proposal(response, objective="test")
        propose_from_llm(proposal, event_log=log, approval_provider=provider)

        audit_events = [
            e for e in log.all()
            if hasattr(e, "event_type") and getattr(e, "event_type", None) == "approval.decision.recorded"
        ]
        assert len(audit_events) >= 1

    def test_tool_calls_evaluated_against_registry(self):
        registry = ToolRegistry()
        registry.register(ToolSpec(name="read_docs", description="Read", risk="read"))
        registry.register(ToolSpec(name="write_file", description="Write", risk="write"))

        response = json.dumps({
            "patches": [],
            "tool_calls": [
                {"tool_name": "read_docs", "arguments": {"query": "test"}},
                {"tool_name": "write_file", "arguments": {"path": "/tmp/test"}},
            ],
        })
        log = EventLog()
        proposal = parse_llm_proposal(response, objective="test", tool_registry=registry)
        result = propose_from_llm(proposal, event_log=log, tool_registry=registry)

        assert len(result.tool_decisions) == 2
        read_decision = next(d for d in result.tool_decisions if d.call.tool_name == "read_docs")
        write_decision = next(d for d in result.tool_decisions if d.call.tool_name == "write_file")
        assert read_decision.is_allowed
        assert write_decision.policy_decision.verdict == "requires_approval"

    def test_tool_call_approval_with_provider(self):
        registry = ToolRegistry()
        registry.register(ToolSpec(name="write_file", description="Write", risk="write"))

        response = json.dumps({
            "patches": [],
            "tool_calls": [
                {"tool_name": "write_file", "arguments": {"path": "/tmp/test"}},
            ],
        })
        log = EventLog()
        provider = StaticApprovalProvider(verdict="approved")
        proposal = parse_llm_proposal(response, objective="test", tool_registry=registry)
        result = propose_from_llm(proposal, event_log=log, approval_provider=provider, tool_registry=registry)

        write_decision = result.tool_decisions[0]
        assert write_decision.is_allowed

    def test_tool_call_rejected_by_provider(self):
        registry = ToolRegistry()
        registry.register(ToolSpec(name="write_file", description="Write", risk="write"))

        response = json.dumps({
            "patches": [],
            "tool_calls": [
                {"tool_name": "write_file", "arguments": {"path": "/tmp/test"}},
            ],
        })
        log = EventLog()
        provider = StaticApprovalProvider(verdict="rejected")
        proposal = parse_llm_proposal(response, objective="test", tool_registry=registry)
        result = propose_from_llm(proposal, event_log=log, approval_provider=provider, tool_registry=registry)

        write_decision = result.tool_decisions[0]
        assert write_decision.is_blocked

    def test_tool_call_evaluation_event_recorded(self):
        registry = ToolRegistry()
        registry.register(ToolSpec(name="read_docs", description="Read", risk="read"))

        response = json.dumps({
            "patches": [],
            "tool_calls": [
                {"tool_name": "read_docs", "arguments": {"query": "test"}},
            ],
        })
        log = EventLog()
        proposal = parse_llm_proposal(response, objective="test", tool_registry=registry)
        propose_from_llm(proposal, event_log=log, tool_registry=registry)

        tool_events = [
            e for e in log.all()
            if hasattr(e, "event_type") and e.event_type == "llm.proposal.tool_call.evaluated"
        ]
        assert len(tool_events) == 1

    def test_all_deltas_blocked_property(self):
        response = json.dumps({
            "patches": [
                {"section": "policy", "key": "rule1", "op": "set", "value": "bypass"},
            ],
        })
        log = EventLog()
        proposal = parse_llm_proposal(response, objective="test")
        result = propose_from_llm(proposal, event_log=log)

        assert result.all_deltas_blocked

    def test_all_tools_blocked_property(self):
        registry = ToolRegistry()
        registry.register(ToolSpec(name="delete_all", description="Delete", risk="external_side_effect"))

        response = json.dumps({
            "patches": [],
            "tool_calls": [
                {"tool_name": "delete_all", "arguments": {}},
            ],
        })
        log = EventLog()
        proposal = parse_llm_proposal(response, objective="test", tool_registry=registry)
        result = propose_from_llm(proposal, event_log=log, tool_registry=registry)

        assert result.all_tools_blocked

    def test_revision_events_have_correct_kind(self):
        response = json.dumps({
            "patches": [
                {"section": "goals", "key": "active", "op": "set", "value": ["t1"]},
                {"section": "beliefs", "key": "facts", "op": "set", "value": "data"},
            ],
        })
        log = EventLog()
        proposal = parse_llm_proposal(response, objective="test")
        result = propose_from_llm(proposal, event_log=log)

        goal_revision = next(
            r for r in result.revision_events
            if any(d.target_kind == "goal_update" for d in r.deltas)
        )
        belief_revision = next(
            r for r in result.revision_events
            if any(d.target_kind == "entity_update" for d in r.deltas)
        )
        assert goal_revision.revision_kind == "confirmation"
        assert belief_revision.revision_kind == "expansion"

    def test_commitment_events_record_success(self):
        response = json.dumps({
            "patches": [
                {"section": "goals", "key": "active", "op": "set", "value": ["t1"]},
            ],
        })
        log = EventLog()
        proposal = parse_llm_proposal(response, objective="test")
        result = propose_from_llm(proposal, event_log=log)

        allowed_commitments = [
            c for c in result.commitment_events if c.success
        ]
        assert len(allowed_commitments) > 0

    def test_self_update_revision_kind_is_recalibration_when_approved(self):
        response = json.dumps({
            "patches": [
                {"section": "self_model", "key": "cap", "op": "set", "value": "updated"},
            ],
        })
        log = EventLog()
        provider = StaticApprovalProvider(verdict="approved")
        proposal = parse_llm_proposal(response, objective="test")
        result = propose_from_llm(proposal, event_log=log, approval_provider=provider)

        assert len(result.revision_events) == 1
        assert result.revision_events[0].revision_kind == "recalibration"


class TestProposeFromLLMDeterminism:
    def test_same_input_produces_same_result(self):
        response = _valid_plan_json()

        log1 = EventLog()
        proposal1 = parse_llm_proposal(response, objective="test")
        result1 = propose_from_llm(proposal1, event_log=log1)

        log2 = EventLog()
        proposal2 = parse_llm_proposal(response, objective="test")
        result2 = propose_from_llm(proposal2, event_log=log2)

        assert result1.allowed_delta_count == result2.allowed_delta_count
        assert result1.blocked_delta_count == result2.blocked_delta_count
        assert len(result1.commitment_events) == len(result2.commitment_events)
        assert len(result1.revision_events) == len(result2.revision_events)


class TestAdapters:
    def test_plan_format_adapter(self):
        adapter = PlanFormatAdapter()
        response = _valid_plan_json()
        proposal = adapter.adapt(response, objective="test")

        assert proposal.source == "plan_compiler"
        assert proposal.is_valid
        assert len(proposal.candidate_deltas) == 2

    def test_raw_format_adapter(self):
        adapter = RawFormatAdapter()
        response = _valid_plan_json()
        proposal = adapter.adapt(response, objective="test")

        assert proposal.source == "raw_llm"
        assert proposal.is_valid

    def test_plan_format_adapter_invalid_input(self):
        adapter = PlanFormatAdapter()
        proposal = adapter.adapt("not json", objective="test")

        assert not proposal.is_valid


class TestForbiddenFields:
    def test_all_forbidden_fields_are_rejected(self):
        for field_name in FORBIDDEN_LLM_FIELDS:
            response = json.dumps({"patches": [], field_name: True})
            proposal = parse_llm_proposal(response, objective="test")
            assert not proposal.is_valid, f"Field '{field_name}' should be rejected"

    def test_multiple_forbidden_fields_all_reported(self):
        response = json.dumps({
            "patches": [],
            "execute": True,
            "bypass": True,
            "sudo": True,
        })
        proposal = parse_llm_proposal(response, objective="test")

        assert not proposal.is_valid
        forbidden_errors = [e for e in proposal.validation_errors if "forbidden" in e.lower()]
        assert len(forbidden_errors) >= 1


class TestValidPatchOps:
    def test_set_op_accepted(self):
        response = json.dumps({
            "patches": [{"section": "goals", "key": "active", "op": "set", "value": "x"}],
        })
        proposal = parse_llm_proposal(response, objective="test")
        assert proposal.is_valid

    def test_append_op_accepted(self):
        response = json.dumps({
            "patches": [{"section": "memory", "key": "working", "op": "append", "value": "x"}],
        })
        proposal = parse_llm_proposal(response, objective="test")
        assert proposal.is_valid

    def test_merge_op_accepted(self):
        response = json.dumps({
            "patches": [{"section": "beliefs", "key": "facts", "op": "merge", "value": {"a": 1}}],
        })
        proposal = parse_llm_proposal(response, objective="test")
        assert proposal.is_valid

    def test_delete_op_accepted(self):
        response = json.dumps({
            "patches": [{"section": "memory", "key": "temp", "op": "delete", "value": None}],
        })
        proposal = parse_llm_proposal(response, objective="test")
        assert proposal.is_valid

    def test_execute_op_rejected(self):
        response = json.dumps({
            "patches": [{"section": "goals", "key": "active", "op": "execute", "value": "x"}],
        })
        proposal = parse_llm_proposal(response, objective="test")
        assert not proposal.is_valid


class TestEndToEndProposalPipeline:
    def test_full_pipeline_with_mixed_deltas(self):
        response = json.dumps({
            "patches": [
                {"section": "goals", "key": "active", "op": "set", "value": ["t1"]},
                {"section": "beliefs", "key": "facts", "op": "set", "value": "data"},
                {"section": "self_model", "key": "cap", "op": "set", "value": "updated"},
                {"section": "policy", "key": "rule", "op": "set", "value": "bypass"},
            ],
            "tool_calls": [
                {"tool_name": "read_docs", "arguments": {"query": "test"}},
            ],
            "rationale": "mixed plan",
        })
        registry = ToolRegistry()
        registry.register(ToolSpec(name="read_docs", description="Read", risk="read"))

        log = EventLog()
        provider = StaticApprovalProvider(verdict="approved")
        proposal = parse_llm_proposal(response, objective="test", tool_registry=registry)
        result = propose_from_llm(
            proposal,
            event_log=log,
            approval_provider=provider,
            tool_registry=registry,
        )

        assert result.allowed_delta_count >= 2
        assert result.blocked_delta_count >= 1
        assert result.requires_approval_delta_count >= 1
        assert result.allowed_tool_count >= 1

        event_types = [e.event_type for e in log.all()]
        assert "llm.proposal.received" in event_types
        assert "llm.proposal.processed" in event_types
        assert "commitment" in event_types
        assert "revision" in event_types

    def test_pipeline_with_all_deltas_denied(self):
        response = json.dumps({
            "patches": [
                {"section": "policy", "key": "rule1", "op": "set", "value": "x"},
                {"section": "meta", "key": "config", "op": "set", "value": "y"},
            ],
        })
        log = EventLog()
        proposal = parse_llm_proposal(response, objective="test")
        result = propose_from_llm(proposal, event_log=log)

        assert result.all_deltas_blocked
        assert result.allowed_delta_count == 0

    def test_pipeline_preserves_raw_llm_output(self):
        raw = _valid_plan_json()
        proposal = parse_llm_proposal(raw, objective="test")

        assert proposal.raw_llm_output == raw
