"""Tests for the Human Approval system: structured requests and interactive providers."""

import pytest

from cee_core import (
    ApprovalDecision,
    ApprovalGate,
    ApprovalGateResult,
    ApprovalRequest,
    ApprovalVerdict,
    CommitmentEvent,
    EventLog,
    InteractiveApprovalProvider,
    RevisionDelta,
    StaticApprovalProvider,
    ToolCallSpec,
    ToolGateway,
    ToolRegistry,
    ToolSpec,
    build_tool_gateway,
)


class TestApprovalRequest:
    def test_from_commitment(self):
        commitment = CommitmentEvent(
            event_id="ce_1",
            source_state_id="ws_0",
            commitment_kind="act",
            intent_summary="Update self_model",
            requires_approval=True,
        )
        request = ApprovalRequest.from_commitment(commitment)

        assert request.source == "commitment"
        assert request.target_summary == "Update self_model"
        assert request.commitment is commitment

    def test_from_tool_call(self):
        call = ToolCallSpec(tool_name="write_file", arguments={"path": "/tmp/test"})
        policy_decision = type("PD", (), {"verdict": "requires_approval", "reason": "write tool"})()
        request = ApprovalRequest.from_tool_call(call, policy_decision)

        assert request.source == "tool_call"
        assert request.target_summary == "Tool call: write_file"
        assert request.tool_call is call
        assert request.risk_level == "requires_approval"

    def test_from_delta(self):
        delta = RevisionDelta(
            delta_id="d1",
            target_kind="self_update",
            target_ref="self_model.capabilities",
            before_summary="unknown",
            after_summary="bounded",
            justification="test",
            raw_value={"planner": "bounded"},
        )
        policy_decision = type("PD", (), {"requires_approval": True, "reason": "self_update"})()
        request = ApprovalRequest.from_delta(delta, policy_decision)

        assert request.source == "delta"
        assert request.target_summary == "Delta: self_model.capabilities"
        assert request.delta is delta

    def test_to_dict(self):
        commitment = CommitmentEvent(
            event_id="ce_1",
            source_state_id="ws_0",
            commitment_kind="act",
            intent_summary="Test",
        )
        request = ApprovalRequest.from_commitment(commitment)
        d = request.to_dict()

        assert d["source"] == "commitment"
        assert d["commitment_event_id"] == "ce_1"
        assert "target_summary" in d


class TestApprovalDecision:
    def test_approved_property(self):
        decision = ApprovalDecision(
            transition_trace_id="tr_1",
            verdict="approved",
            decided_by="human",
            reason="looks good",
        )
        assert decision.approved

    def test_rejected_property(self):
        decision = ApprovalDecision(
            transition_trace_id="tr_1",
            verdict="rejected",
            decided_by="human",
            reason="too risky",
        )
        assert not decision.approved

    def test_to_dict(self):
        decision = ApprovalDecision(
            transition_trace_id="tr_1",
            verdict="approved",
            decided_by="human",
            reason="looks good",
        )
        d = decision.to_dict()

        assert d["verdict"] == "approved"
        assert d["decided_by"] == "human"

    def test_to_event(self):
        decision = ApprovalDecision(
            transition_trace_id="tr_1",
            verdict="approved",
            decided_by="human",
            reason="looks good",
        )
        event = decision.to_event()

        assert event.event_type == "approval.decision.recorded"
        assert event.trace_id == "tr_1"
        assert event.actor == "human"


class TestStaticApprovalProvider:
    def test_approve_all(self):
        provider = StaticApprovalProvider(verdict="approved")
        commitment = CommitmentEvent(
            event_id="ce_1",
            source_state_id="ws_0",
            commitment_kind="act",
            intent_summary="Test",
        )
        decision = provider.decide(commitment)

        assert decision.approved
        assert decision.verdict == "approved"

    def test_reject_all(self):
        provider = StaticApprovalProvider(verdict="rejected")
        commitment = CommitmentEvent(
            event_id="ce_1",
            source_state_id="ws_0",
            commitment_kind="act",
            intent_summary="Test",
        )
        decision = provider.decide(commitment)

        assert not decision.approved
        assert decision.verdict == "rejected"

    def test_decide_request(self):
        provider = StaticApprovalProvider(verdict="approved")
        request = ApprovalRequest(
            source="tool_call",
            target_summary="write_file",
            reason="test",
        )
        decision = provider.decide_request(request)

        assert decision.approved


class TestInteractiveApprovalProvider:
    def test_auto_approve_read(self):
        provider = InteractiveApprovalProvider(auto_approve_read=True)
        request = ApprovalRequest(
            source="tool_call",
            target_summary="read_docs",
            reason="read-only",
            risk_level="read",
        )
        decision = provider.decide_request(request)

        assert decision.approved
        assert "auto-approved" in decision.reason

    def test_interactive_approve(self):
        provider = InteractiveApprovalProvider(
            auto_approve_read=False,
            input_fn=lambda msg: "y",
        )
        request = ApprovalRequest(
            source="tool_call",
            target_summary="write_file",
            reason="write operation",
            risk_level="write",
        )
        decision = provider.decide_request(request)

        assert decision.approved
        assert "human" in decision.decided_by

    def test_interactive_reject(self):
        provider = InteractiveApprovalProvider(
            auto_approve_read=False,
            input_fn=lambda msg: "n",
        )
        request = ApprovalRequest(
            source="tool_call",
            target_summary="write_file",
            reason="write operation",
            risk_level="write",
        )
        decision = provider.decide_request(request)

        assert not decision.approved
        assert "rejected" in decision.verdict

    def test_interactive_eof_defaults_to_reject(self):
        def raise_eof(msg):
            raise EOFError()

        provider = InteractiveApprovalProvider(
            auto_approve_read=False,
            input_fn=raise_eof,
        )
        request = ApprovalRequest(
            source="tool_call",
            target_summary="write_file",
            reason="write operation",
            risk_level="write",
        )
        decision = provider.decide_request(request)

        assert not decision.approved
        assert decision.verdict == "rejected"


class TestApprovalGate:
    def test_resolve_approves(self):
        gate = ApprovalGate(provider=StaticApprovalProvider(verdict="approved"))
        commitment = CommitmentEvent(
            event_id="ce_1",
            source_state_id="ws_0",
            commitment_kind="act",
            intent_summary="Test",
            requires_approval=True,
        )
        result = gate.resolve((commitment,))

        assert result.approval_count == 1
        assert result.rejection_count == 0

    def test_resolve_rejects(self):
        gate = ApprovalGate(provider=StaticApprovalProvider(verdict="rejected"))
        commitment = CommitmentEvent(
            event_id="ce_1",
            source_state_id="ws_0",
            commitment_kind="act",
            intent_summary="Test",
            requires_approval=True,
        )
        result = gate.resolve((commitment,))

        assert result.approval_count == 0
        assert result.rejection_count == 1

    def test_resolve_skips_non_approval_events(self):
        gate = ApprovalGate(provider=StaticApprovalProvider(verdict="approved"))
        commitment = CommitmentEvent(
            event_id="ce_1",
            source_state_id="ws_0",
            commitment_kind="observe",
            intent_summary="Test",
            requires_approval=False,
        )
        result = gate.resolve((commitment,))

        assert result.approval_count == 0
        assert result.rejection_count == 0

    def test_resolve_requests(self):
        gate = ApprovalGate(provider=StaticApprovalProvider(verdict="approved"))
        commitment = CommitmentEvent(
            event_id="ce_1",
            source_state_id="ws_0",
            commitment_kind="act",
            intent_summary="Test",
            requires_approval=True,
        )
        request = ApprovalRequest.from_commitment(commitment)
        result = gate.resolve_requests((request,))

        assert result.approval_count == 1


class TestApprovalAuditTrail:
    def test_approval_decision_recorded_in_event_log(self):
        log = EventLog()
        registry = ToolRegistry()
        registry.register(ToolSpec(name="write_file", description="Write", risk="write"))

        gateway = build_tool_gateway(
            registry,
            handlers={"write_file": lambda args: "ok"},
            approval_provider=StaticApprovalProvider(verdict="approved"),
        )

        call = ToolCallSpec(tool_name="write_file", arguments={"path": "/tmp/test"})
        result = gateway.execute(call, event_log=log)

        assert result.succeeded
        assert result.approval_decision is not None
        assert result.approval_decision.approved

        audit_events = [
            e for e in log.all()
            if hasattr(e, "event_type") and getattr(e, "event_type", None) == "approval.decision.recorded"
        ]
        assert len(audit_events) == 1

    def test_rejection_recorded_in_event_log(self):
        log = EventLog()
        registry = ToolRegistry()
        registry.register(ToolSpec(name="write_file", description="Write", risk="write"))

        gateway = build_tool_gateway(
            registry,
            approval_provider=StaticApprovalProvider(verdict="rejected"),
        )

        call = ToolCallSpec(tool_name="write_file", arguments={"path": "/tmp/test"})
        result = gateway.execute(call, event_log=log)

        assert result.blocked_by_approval
        audit_events = [
            e for e in log.all()
            if hasattr(e, "event_type") and getattr(e, "event_type", None) == "approval.decision.recorded"
        ]
        assert len(audit_events) == 1
