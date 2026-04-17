import pytest

from cee_core import EventLog, State, StatePatch, quality_metrics
from cee_core.events import StateTransitionEvent
from cee_core.policy import PolicyDecision


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


def test_event_log_accepts_valid_transition_event():
    log = EventLog()
    patch = StatePatch(section="goals", key="g1", op="set", value={"status": "done"})
    decision = PolicyDecision(verdict="allow", reason="ok", policy_ref="test")
    event = StateTransitionEvent(patch=patch, policy_decision=decision, actor="test", reason="test")

    log.append(event)

    assert len(list(log.all())) == 1


def test_high_risk_approval_coverage_is_tracked():
    from cee_core import execute_task_in_domain, DomainContext, EventLog

    log = EventLog()
    result = execute_task_in_domain("count to 3", DomainContext(domain_name="core"), event_log=log)

    metrics = quality_metrics.compute_quality_metrics(result)

    assert hasattr(metrics, "unauthorized_tool_execution_rate")
    assert metrics.unauthorized_tool_execution_rate == 0.0


def test_self_model_patch_always_requires_approval():
    from cee_core import evaluate_patch_policy, StatePatch

    patch = StatePatch(section="self_model", key="capabilities", op="set", value={"planner": "bounded"})
    decision = evaluate_patch_policy(patch)

    assert decision.verdict == "requires_approval"


def test_policy_patch_always_denied():
    from cee_core import evaluate_patch_policy, StatePatch

    patch = StatePatch(section="policy", key="rules", op="set", value={"new_rule": True})
    decision = evaluate_patch_policy(patch)

    assert decision.verdict == "deny"


def test_meta_patch_always_denied():
    from cee_core import evaluate_patch_policy, StatePatch

    patch = StatePatch(section="meta", key="version", op="set", value=99)
    decision = evaluate_patch_policy(patch)

    assert decision.verdict == "deny"
