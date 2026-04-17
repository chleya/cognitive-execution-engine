import pytest

from cee_core import (
    ConfidenceGateConfig,
    DomainContext,
    DomainPluginPack,
    EventLog,
    PolicyDecision,
    State,
    StatePatch,
    evaluate_confidence_gate,
    evaluate_patch_policy_in_domain,
    extract_belief_confidence,
)


def _belief_patch(key: str = "test_belief", confidence: float = 0.9) -> StatePatch:
    return StatePatch(
        section="beliefs",
        key=key,
        op="set",
        value={
            "content": "test content",
            "confidence": confidence,
            "provenance": ["test"],
            "source_tool": "test_tool",
            "call_id": "call_1",
            "evidence_weight": 1.0,
            "evidence_count": 1,
        },
    )


def _task_patch() -> StatePatch:
    return StatePatch(
        section="goals",
        key="g1",
        op="set",
        value={"status": "done"},
    )


def test_confidence_gate_allows_high_confidence_belief():
    patch = _belief_patch(confidence=0.95)
    base = PolicyDecision(verdict="allow", reason="ok", policy_ref="test")
    beliefs = {"test_belief": {"confidence": 0.95}}

    result = evaluate_confidence_gate(patch, base, beliefs)

    assert result.verdict == "allow"


def test_confidence_gate_escalates_low_confidence_belief():
    patch = _belief_patch(confidence=0.3)
    base = PolicyDecision(verdict="allow", reason="ok", policy_ref="test")
    beliefs = {"test_belief": {"confidence": 0.3}}

    result = evaluate_confidence_gate(patch, base, beliefs)

    assert result.verdict == "requires_approval"
    assert "0.30" in result.reason
    assert "confidence-gate" in result.policy_ref


def test_confidence_gate_does_not_escalate_non_belief_patches():
    patch = _task_patch()
    base = PolicyDecision(verdict="allow", reason="ok", policy_ref="test")
    beliefs = {}

    result = evaluate_confidence_gate(patch, base, beliefs)

    assert result.verdict == "allow"


def test_confidence_gate_does_not_loosen_denied_decisions():
    patch = _belief_patch(confidence=0.95)
    base = PolicyDecision(verdict="deny", reason="no", policy_ref="test")
    beliefs = {"test_belief": {"confidence": 0.95}}

    result = evaluate_confidence_gate(patch, base, beliefs)

    assert result.verdict == "deny"


def test_confidence_gate_respects_custom_threshold():
    patch = _belief_patch(confidence=0.6)
    base = PolicyDecision(verdict="allow", reason="ok", policy_ref="test")
    beliefs = {"test_belief": {"confidence": 0.6}}
    config = ConfidenceGateConfig(approval_threshold=0.5)

    result = evaluate_confidence_gate(patch, base, beliefs, config=config)

    assert result.verdict == "allow"


def test_confidence_gate_disabled_returns_base():
    patch = _belief_patch(confidence=0.1)
    base = PolicyDecision(verdict="allow", reason="ok", policy_ref="test")
    beliefs = {"test_belief": {"confidence": 0.1}}
    config = ConfidenceGateConfig(enabled=False)

    result = evaluate_confidence_gate(patch, base, beliefs, config=config)

    assert result.verdict == "allow"


def test_confidence_gate_handles_missing_belief():
    patch = _belief_patch(key="nonexistent")
    base = PolicyDecision(verdict="allow", reason="ok", policy_ref="test")
    beliefs = {}

    result = evaluate_confidence_gate(patch, base, beliefs)

    assert result.verdict == "allow"


def test_confidence_gate_handles_belief_without_confidence():
    patch = _belief_patch()
    base = PolicyDecision(verdict="allow", reason="ok", policy_ref="test")
    beliefs = {"test_belief": {"content": "no confidence field"}}

    result = evaluate_confidence_gate(patch, base, beliefs)

    assert result.verdict == "allow"


def test_confidence_gate_config_validates_threshold():
    with pytest.raises(ValueError):
        ConfidenceGateConfig(approval_threshold=1.5)

    with pytest.raises(ValueError):
        ConfidenceGateConfig(approval_threshold=-0.1)


def test_extract_belief_confidence_returns_float():
    assert extract_belief_confidence({"confidence": 0.8}) == 0.8


def test_extract_belief_confidence_returns_none_for_missing():
    assert extract_belief_confidence({"content": "no confidence"}) is None
    assert extract_belief_confidence("not a dict") is None


def test_domain_policy_integrates_confidence_gate():
    state = State()
    state.beliefs["low_conf"] = {
        "content": "uncertain",
        "confidence": 0.3,
        "provenance": ["test"],
    }

    patch = StatePatch(
        section="beliefs",
        key="low_conf",
        op="set",
        value={
            "content": "updated",
            "confidence": 0.4,
            "provenance": ["test"],
        },
    )

    result = evaluate_patch_policy_in_domain(
        patch,
        DomainContext(domain_name="core"),
        current_state=state,
    )

    assert result.verdict == "requires_approval"
    assert "confidence" in result.reason


def test_domain_policy_without_state_skips_confidence_gate():
    patch = _belief_patch(confidence=0.1)

    result = evaluate_patch_policy_in_domain(
        patch,
        DomainContext(domain_name="core"),
    )

    assert result.verdict == "allow"


def test_memory_gate_allows_patch_with_evidence_metadata():
    patch = StatePatch(
        section="memory",
        key="working",
        op="append",
        value={
            "task_id": "t1",
            "confidence": 1.0,
            "evidence_count": 2,
            "provenance": "deterministic_planner",
        },
    )
    base = PolicyDecision(verdict="allow", reason="ok", policy_ref="test")
    beliefs = {}

    result = evaluate_confidence_gate(patch, base, beliefs)

    assert result.verdict == "allow"


def test_memory_gate_escalates_patch_without_evidence():
    patch = StatePatch(
        section="memory",
        key="working",
        op="set",
        value="direct model output",
    )
    base = PolicyDecision(verdict="allow", reason="ok", policy_ref="test")
    beliefs = {}

    result = evaluate_confidence_gate(patch, base, beliefs)

    assert result.verdict == "requires_approval"
    assert "memory" in result.reason
    assert "confidence-gate" in result.policy_ref


def test_memory_gate_escalates_patch_without_confidence():
    patch = StatePatch(
        section="memory",
        key="working",
        op="set",
        value={"task_id": "t1", "evidence_count": 3},
    )
    base = PolicyDecision(verdict="allow", reason="ok", policy_ref="test")
    beliefs = {}

    result = evaluate_confidence_gate(patch, base, beliefs)

    assert result.verdict == "requires_approval"
    assert "confidence" in result.reason


def test_memory_gate_escalates_low_confidence():
    patch = StatePatch(
        section="memory",
        key="working",
        op="set",
        value={"task_id": "t1", "confidence": 0.3, "evidence_count": 2},
    )
    base = PolicyDecision(verdict="allow", reason="ok", policy_ref="test")
    beliefs = {}

    result = evaluate_confidence_gate(patch, base, beliefs)

    assert result.verdict == "requires_approval"
    assert "0.30" in result.reason


def test_memory_gate_escalates_insufficient_evidence():
    patch = StatePatch(
        section="memory",
        key="working",
        op="set",
        value={"task_id": "t1", "confidence": 0.9, "evidence_count": 1},
    )
    base = PolicyDecision(verdict="allow", reason="ok", policy_ref="test")
    beliefs = {}

    result = evaluate_confidence_gate(patch, base, beliefs)

    assert result.verdict == "requires_approval"
    assert "evidence" in result.reason


def test_memory_gate_does_not_loosen_denied():
    patch = StatePatch(
        section="memory",
        key="working",
        op="set",
        value={"confidence": 1.0, "evidence_count": 5},
    )
    base = PolicyDecision(verdict="deny", reason="no", policy_ref="test")
    beliefs = {}

    result = evaluate_confidence_gate(patch, base, beliefs)

    assert result.verdict == "deny"


def test_domain_policy_integrates_memory_gate():
    state = State()

    patch = StatePatch(
        section="memory",
        key="working",
        op="set",
        value="model-written memory without evidence",
    )

    result = evaluate_patch_policy_in_domain(
        patch,
        DomainContext(domain_name="core"),
        current_state=state,
    )

    assert result.verdict == "requires_approval"
    assert "memory" in result.reason
