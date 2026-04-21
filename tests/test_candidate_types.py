import pytest

from cee_core import (
    BeliefCandidate,
    ReflectionCandidate,
    RevisionDelta,
    evaluate_delta_policy,
    promote_belief_candidate_to_delta,
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


def test_belief_candidate_promotion_creates_belief_delta():
    candidate = BeliefCandidate(
        content="extracted fact",
        confidence=0.85,
        evidence_weight=1.0,
        provenance=("llm_extractor",),
        extraction_source="llm_extractor",
        extraction_trace_id="trace_002",
    )

    delta = promote_belief_candidate_to_delta(candidate, belief_key="fact_1")

    assert delta.target_kind == "entity_update"
    assert delta.target_ref == "beliefs.fact_1"
    assert delta.raw_value["content"] == "extracted fact"
    assert delta.raw_value["confidence"] == 0.85
    assert delta.raw_value["extraction_source"] == "llm_extractor"


def test_belief_candidate_delta_passes_policy():
    candidate = BeliefCandidate(
        content="test",
        confidence=0.9,
        evidence_weight=1.0,
        provenance=("s1",),
        extraction_source="llm",
        extraction_trace_id="t1",
    )

    delta = promote_belief_candidate_to_delta(candidate, belief_key="k1")
    decision = evaluate_delta_policy(delta)

    assert decision.allowed


def test_low_confidence_belief_candidate_delta_still_allowed_by_base_policy():
    candidate = BeliefCandidate(
        content="uncertain",
        confidence=0.3,
        evidence_weight=0.5,
        provenance=("weak_source",),
        extraction_source="llm",
        extraction_trace_id="t2",
    )

    delta = promote_belief_candidate_to_delta(candidate, belief_key="uncertain")
    decision = evaluate_delta_policy(delta)

    assert decision.allowed
    assert not decision.requires_approval


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


def test_self_model_delta_from_belief_candidate_requires_approval():
    delta = RevisionDelta(
        delta_id="d1",
        target_kind="self_update",
        target_ref="self_model.capabilities",
        before_summary="unknown",
        after_summary="bounded",
        justification="test self model update",
        raw_value={"planner": "bounded"},
    )

    decision = evaluate_delta_policy(delta)

    assert decision.requires_approval
    assert not decision.allowed
