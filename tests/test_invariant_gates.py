import pytest

from cee_core import EventLog, quality_metrics, CommitmentEvent, RevisionDelta
from cee_core.planner import evaluate_delta_policy


def test_event_log_rejects_non_event_objects():
    log = EventLog()
    with pytest.raises(TypeError):
        log.append("not an event")


def test_event_log_rejects_none():
    log = EventLog()
    with pytest.raises(TypeError):
        log.append(None)


def test_event_log_rejects_plain_dict():
    log = EventLog()
    with pytest.raises(TypeError):
        log.append({"event_type": "fake"})


def test_event_log_accepts_valid_commitment_event():
    log = EventLog()
    ce = CommitmentEvent(
        event_id="ce-test-1",
        source_state_id="",
        commitment_kind="observe",
        intent_summary="test",
        action_summary="beliefs test",
        success=True,
    )
    log.append(ce)
    assert len(list(log.all())) == 1


def test_high_risk_approval_coverage_is_tracked():
    from cee_core import execute_task_in_domain, DomainContext, EventLog

    log = EventLog()
    result = execute_task_in_domain("count to 3", DomainContext(domain_name="core"), event_log=log)
    metrics = quality_metrics.compute_quality_metrics(result)
    assert hasattr(metrics, "unauthorized_tool_execution_rate")
    assert metrics.unauthorized_tool_execution_rate == 0.0


def test_self_model_delta_always_requires_approval():
    delta = RevisionDelta(
        delta_id="d1",
        target_kind="self_update",
        target_ref="self_model.capabilities",
        before_summary="unknown",
        after_summary="bounded",
        justification="test",
        raw_value={"planner": "bounded"},
    )
    decision = evaluate_delta_policy(delta)
    assert decision.requires_approval


def test_policy_delta_always_denied():
    delta = RevisionDelta(
        delta_id="d1",
        target_kind="entity_update",
        target_ref="policy.rules",
        before_summary="unknown",
        after_summary="new rule",
        justification="test",
        raw_value={"new_rule": True},
    )
    decision = evaluate_delta_policy(delta)
    assert not decision.allowed
    assert not decision.requires_approval


def test_meta_delta_always_denied():
    delta = RevisionDelta(
        delta_id="d1",
        target_kind="entity_update",
        target_ref="meta.version",
        before_summary="unknown",
        after_summary="99",
        justification="test",
        raw_value=99,
    )
    decision = evaluate_delta_policy(delta)
    assert not decision.allowed
    assert not decision.requires_approval
