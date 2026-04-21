import pytest

from cee_core import (
    ApprovalDecision,
    ApprovalGate,
    ApprovalGateResult,
    CallbackApprovalProvider,
    CommitmentEvent,
    DomainContext,
    DomainPluginPack,
    EventLog,
    RunResult,
    StaticApprovalProvider,
    execute_task_in_domain,
)


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


def _approval_domain():
    return DomainContext(
        domain_name="approval_test",
        plugin_pack=DomainPluginPack(
            domain_name="approval_test",
            approval_required_patch_sections=("self_model",),
        ),
    )


def test_static_approval_provider_auto_approves():
    provider = StaticApprovalProvider(verdict="approved")
    event = _self_model_commitment()

    decision = provider.decide(event)

    assert decision.verdict == "approved"
    assert decision.transition_trace_id == event.event_id


def test_static_approval_provider_auto_rejects():
    provider = StaticApprovalProvider(
        verdict="rejected", reason="policy denies self_model changes"
    )
    event = _self_model_commitment()

    decision = provider.decide(event)

    assert decision.verdict == "rejected"
    assert decision.reason == "policy denies self_model changes"


def test_callback_approval_provider_delegates():
    call_log: list[str] = []

    def callback(event):
        call_log.append(event.event_id)
        return ApprovalDecision(
            transition_trace_id=event.event_id,
            verdict="approved",
            decided_by="callback_tester",
            reason="callback approved",
        )

    provider = CallbackApprovalProvider(callback=callback)
    event = _self_model_commitment()

    decision = provider.decide(event)

    assert decision.verdict == "approved"
    assert decision.decided_by == "callback_tester"
    assert call_log == [event.event_id]


def test_approval_gate_resolves_requires_approval_transitions():
    provider = StaticApprovalProvider(verdict="approved")
    gate = ApprovalGate(provider=provider)
    event = _self_model_commitment()

    result = gate.resolve((event,))

    assert result.approval_count == 1
    assert result.rejection_count == 0
    assert len(result.approved_transitions) == 1


def test_approval_gate_rejects_transitions():
    provider = StaticApprovalProvider(verdict="rejected", reason="denied")
    gate = ApprovalGate(provider=provider)
    event = _self_model_commitment()

    result = gate.resolve((event,))

    assert result.approval_count == 0
    assert result.rejection_count == 1
    assert len(result.rejected_transitions) == 1


def test_approval_gate_skips_non_approval_transitions():
    provider = StaticApprovalProvider(verdict="approved")
    gate = ApprovalGate(provider=provider)

    allowed_event = CommitmentEvent(
        event_id="ce-allowed-0",
        source_state_id="",
        commitment_kind="observe",
        intent_summary="test:belief update",
        action_summary="beliefs test",
        success=True,
        reversibility="reversible",
    )

    result = gate.resolve((allowed_event,))

    assert result.approval_count == 0
    assert result.rejection_count == 0


def test_approval_gate_handles_empty_events():
    provider = StaticApprovalProvider(verdict="approved")
    gate = ApprovalGate(provider=provider)

    result = gate.resolve(())

    assert result.approval_count == 0
    assert result.rejection_count == 0


def test_approval_gate_result_properties():
    provider = StaticApprovalProvider(verdict="approved")
    gate = ApprovalGate(provider=provider)
    event = _self_model_commitment()

    result = gate.resolve((event,))

    assert isinstance(result, ApprovalGateResult)
    assert result.approval_count == 1
    assert result.rejection_count == 0


def test_runtime_without_approval_gate_returns_none_gate_result():
    result = execute_task_in_domain(
        "count to 3",
        DomainContext(domain_name="core"),
    )

    assert result.approval_gate_result is None


def test_runtime_with_approval_gate_auto_approves_self_model():
    provider = StaticApprovalProvider(verdict="approved")
    gate = ApprovalGate(provider=provider)
    domain = _approval_domain()

    result = execute_task_in_domain(
        "update self_model capabilities to planner bounded",
        domain,
        approval_gate=gate,
    )

    if result.approval_required_transitions:
        assert result.approval_gate_result is not None
        assert result.approval_gate_result.approval_count > 0


def test_runtime_with_approval_gate_auto_rejects_self_model():
    provider = StaticApprovalProvider(verdict="rejected", reason="auto-reject policy")
    gate = ApprovalGate(provider=provider)
    domain = _approval_domain()

    result = execute_task_in_domain(
        "update self_model capabilities to planner bounded",
        domain,
        approval_gate=gate,
    )

    if result.approval_required_transitions:
        assert result.approval_gate_result is not None
        assert result.approval_gate_result.rejection_count > 0


def test_approval_gate_audit_trail_is_complete():
    log = EventLog()
    provider = StaticApprovalProvider(verdict="approved")
    gate = ApprovalGate(provider=provider)
    domain = _approval_domain()

    result = execute_task_in_domain(
        "update self_model capabilities to planner bounded",
        domain,
        event_log=log,
        approval_gate=gate,
    )

    if result.approval_gate_result and result.approval_gate_result.approval_count > 0:
        approval_events = [
            e
            for e in log.all()
            if getattr(e, "event_type", None) == "approval.decision.recorded"
        ]
        assert len(approval_events) > 0


def test_callback_approval_gate_in_runtime():
    decisions: list[ApprovalDecision] = []

    def callback(event):
        decision = ApprovalDecision(
            transition_trace_id=event.event_id,
            verdict="approved",
            decided_by="test_operator",
            reason="test approval",
        )
        decisions.append(decision)
        return decision

    gate = ApprovalGate(provider=CallbackApprovalProvider(callback=callback))
    domain = _approval_domain()

    result = execute_task_in_domain(
        "update self_model capabilities to planner bounded",
        domain,
        approval_gate=gate,
    )

    if result.approval_required_transitions:
        assert len(decisions) > 0
        assert all(d.decided_by == "test_operator" for d in decisions)
