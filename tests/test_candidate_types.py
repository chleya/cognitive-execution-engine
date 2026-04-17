import pytest

from cee_core import (
    BeliefCandidate,
    ConfidenceGateConfig,
    PolicyDecision,
    ReflectionCandidate,
    StatePatch,
    evaluate_confidence_gate,
    promote_belief_candidate_to_patch,
)


def test_belief_candidate_creation():
    candidate = BeliefCandidate(
        content="test content",
        confidence=0.8,
        evidence_weight=1.0,
        provenance=("source1",),
        extraction_source="llm_extractor",
        extraction_trace_id="trace_001",
    )

    assert candidate.confidence == 0.8
    assert candidate.extraction_source == "llm_extractor"


def test_belief_candidate_to_dict():
    candidate = BeliefCandidate(
        content="test",
        confidence=0.9,
        evidence_weight=1.0,
        provenance=("s1",),
        extraction_source="llm",
        extraction_trace_id="t1",
    )

    d = candidate.to_dict()
    assert d["confidence"] == 0.9
    assert d["extraction_source"] == "llm"


def test_belief_candidate_promotion_creates_belief_patch():
    candidate = BeliefCandidate(
        content="extracted fact",
        confidence=0.85,
        evidence_weight=1.0,
        provenance=("llm_extractor",),
        extraction_source="llm_extractor",
        extraction_trace_id="trace_002",
    )

    patch = promote_belief_candidate_to_patch(candidate, belief_key="fact_1")

    assert patch.section == "beliefs"
    assert patch.key == "fact_1"
    assert patch.op == "set"
    assert patch.value["confidence"] == 0.85
    assert patch.value["extraction_source"] == "llm_extractor"


def test_belief_candidate_patch_requires_policy():
    candidate = BeliefCandidate(
        content="test",
        confidence=0.9,
        evidence_weight=1.0,
        provenance=("s1",),
        extraction_source="llm",
        extraction_trace_id="t1",
    )

    patch = promote_belief_candidate_to_patch(candidate, belief_key="k1")

    from cee_core import evaluate_patch_policy
    decision = evaluate_patch_policy(patch)

    assert decision.verdict == "allow"


def test_low_confidence_belief_candidate_escalated():
    candidate = BeliefCandidate(
        content="uncertain",
        confidence=0.3,
        evidence_weight=0.5,
        provenance=("weak_source",),
        extraction_source="llm",
        extraction_trace_id="t2",
    )

    patch = promote_belief_candidate_to_patch(candidate, belief_key="uncertain")
    base = PolicyDecision(verdict="allow", reason="ok", policy_ref="test")
    beliefs = {"uncertain": patch.value}

    result = evaluate_confidence_gate(patch, base, beliefs)

    assert result.verdict == "requires_approval"


def test_reflection_candidate_creation():
    candidate = ReflectionCandidate(
        summary="observed high denial rate",
        patterns_observed=("frequent redirects", "low confidence beliefs"),
        suggested_adjustments=("lower confidence threshold",),
        confidence=0.7,
        reflection_trace_id="ref_001",
    )

    assert candidate.summary == "observed high denial rate"
    assert len(candidate.patterns_observed) == 2
    assert len(candidate.suggested_adjustments) == 1


def test_reflection_candidate_to_dict():
    candidate = ReflectionCandidate(
        summary="test",
        patterns_observed=("p1",),
        suggested_adjustments=("a1",),
        confidence=0.6,
        reflection_trace_id="ref_002",
    )

    d = candidate.to_dict()
    assert d["summary"] == "test"
    assert d["patterns_observed"] == ["p1"]


def test_evidence_count_gate_escalates_insufficient_evidence():
    patch = StatePatch(
        section="beliefs",
        key="weak_evidence",
        op="set",
        value={
            "content": "test",
            "confidence": 0.9,
            "evidence_count": 1,
        },
    )
    base = PolicyDecision(verdict="allow", reason="ok", policy_ref="test")
    beliefs = {"weak_evidence": {"confidence": 0.9, "evidence_count": 1}}
    config = ConfidenceGateConfig(evidence_count_threshold=2)

    result = evaluate_confidence_gate(patch, base, beliefs, config=config)

    assert result.verdict == "requires_approval"
    assert "evidence count" in result.reason


def test_evidence_count_gate_allows_sufficient_evidence():
    patch = StatePatch(
        section="beliefs",
        key="strong_evidence",
        op="set",
        value={
            "content": "test",
            "confidence": 0.9,
            "evidence_count": 3,
        },
    )
    base = PolicyDecision(verdict="allow", reason="ok", policy_ref="test")
    beliefs = {"strong_evidence": {"confidence": 0.9, "evidence_count": 3}}
    config = ConfidenceGateConfig(evidence_count_threshold=2)

    result = evaluate_confidence_gate(patch, base, beliefs, config=config)

    assert result.verdict == "allow"


def test_evidence_count_threshold_validates():
    with pytest.raises(ValueError):
        ConfidenceGateConfig(evidence_count_threshold=0)
