import pytest

from cee_core.hypothesis import (
    Hypothesis,
    HypothesisCycle,
    VerificationCriteria,
    VerificationResult,
    verify_hypothesis,
    run_hypothesis_cycle,
)


def _strong_hypothesis() -> Hypothesis:
    return Hypothesis(
        statement="The system follows state-first architecture",
        source_trace_id="trace_001",
        confidence=0.9,
        evidence_refs=("doc_1", "doc_2", "doc_3"),
    )


def _weak_hypothesis() -> Hypothesis:
    return Hypothesis(
        statement="Maybe something is true",
        source_trace_id="trace_002",
        confidence=0.3,
        evidence_refs=("doc_1",),
    )


def test_verify_accepts_strong_hypothesis():
    result = verify_hypothesis(_strong_hypothesis(), VerificationCriteria())

    assert result.verdict == "accepted"
    assert result.evidence_count == 3
    assert result.independent_source_count == 3


def test_verify_rejects_low_confidence():
    hypothesis = Hypothesis(
        statement="Maybe something is true",
        source_trace_id="trace_002",
        confidence=0.3,
        evidence_refs=("doc_1", "doc_2"),
    )
    result = verify_hypothesis(hypothesis, VerificationCriteria())

    assert result.verdict == "rejected"
    assert "confidence" in result.reason


def test_verify_needs_more_evidence():
    hypothesis = Hypothesis(
        statement="Test hypothesis",
        source_trace_id="trace_003",
        confidence=0.8,
        evidence_refs=("doc_1",),
    )
    result = verify_hypothesis(hypothesis, VerificationCriteria(min_evidence_count=2))

    assert result.verdict == "needs_more_evidence"
    assert "evidence count" in result.reason


def test_verify_needs_more_independent_sources():
    hypothesis = Hypothesis(
        statement="Test hypothesis",
        source_trace_id="trace_004",
        confidence=0.8,
        evidence_refs=("doc_1", "doc_1", "doc_1"),
    )
    result = verify_hypothesis(
        hypothesis,
        VerificationCriteria(required_independent_sources=2),
    )

    assert result.verdict == "needs_more_evidence"
    assert "independent source" in result.reason


def test_run_hypothesis_cycle_returns_cycle():
    cycle = run_hypothesis_cycle(_strong_hypothesis())

    assert isinstance(cycle, HypothesisCycle)
    assert cycle.accepted is True
    assert cycle.hypothesis.statement == "The system follows state-first architecture"
    assert cycle.result.verdict == "accepted"


def test_run_hypothesis_cycle_with_custom_criteria():
    criteria = VerificationCriteria(min_confidence=0.95)
    cycle = run_hypothesis_cycle(_strong_hypothesis(), criteria=criteria)

    assert cycle.accepted is False
    assert cycle.result.verdict == "rejected"


def test_hypothesis_to_dict():
    h = _strong_hypothesis()
    d = h.to_dict()

    assert d["statement"] == "The system follows state-first architecture"
    assert d["confidence"] == 0.9
    assert len(d["evidence_refs"]) == 3


def test_verification_result_to_dict():
    result = verify_hypothesis(_strong_hypothesis(), VerificationCriteria())
    d = result.to_dict()

    assert d["verdict"] == "accepted"
    assert "evidence_count" in d


def test_hypothesis_cycle_to_dict():
    cycle = run_hypothesis_cycle(_strong_hypothesis())
    d = cycle.to_dict()

    assert "hypothesis" in d
    assert "criteria" in d
    assert "result" in d
    assert d["result"]["verdict"] == "accepted"


def test_default_criteria_values():
    criteria = VerificationCriteria()
    assert criteria.min_evidence_count == 2
    assert criteria.min_confidence == 0.7
    assert criteria.required_independent_sources == 2
