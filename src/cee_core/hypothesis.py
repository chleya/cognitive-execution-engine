"""Hypothesis generation and verification cycle.

A hypothesis cycle implements the hypothesize -> verify -> accept/reject
cognitive primitive. The cycle is:

1. Generate a hypothesis from observations or reasoning
2. Define verification criteria
3. Evaluate evidence against criteria
4. Record the outcome (accepted, rejected, or needs_more_evidence)

Hypotheses never directly become beliefs. Accepted hypotheses become
BeliefCandidates that must still pass through the belief promotion
pipeline (confidence gate + policy evaluation + approval).

This module only proposes and records; it does not execute tools,
write canonical state, or bypass policy.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal
from uuid import uuid4


HypothesisVerdict = Literal["accepted", "rejected", "needs_more_evidence"]


@dataclass(frozen=True)
class Hypothesis:
    """A testable proposition derived from observations or reasoning."""

    statement: str
    source_trace_id: str
    confidence: float
    evidence_refs: tuple[str, ...]
    hypothesis_id: str = field(default_factory=lambda: f"hyp_{uuid4().hex}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "hypothesis_id": self.hypothesis_id,
            "statement": self.statement,
            "source_trace_id": self.source_trace_id,
            "confidence": self.confidence,
            "evidence_refs": list(self.evidence_refs),
        }


@dataclass(frozen=True)
class VerificationCriteria:
    """Criteria for evaluating a hypothesis."""

    min_evidence_count: int = 2
    min_confidence: float = 0.7
    required_independent_sources: int = 2

    def to_dict(self) -> dict[str, Any]:
        return {
            "min_evidence_count": self.min_evidence_count,
            "min_confidence": self.min_confidence,
            "required_independent_sources": self.required_independent_sources,
        }


@dataclass(frozen=True)
class VerificationResult:
    """Outcome of verifying a hypothesis against criteria."""

    hypothesis_id: str
    verdict: HypothesisVerdict
    evidence_count: int
    independent_source_count: int
    confidence: float
    reason: str
    verification_id: str = field(default_factory=lambda: f"ver_{uuid4().hex}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "verification_id": self.verification_id,
            "hypothesis_id": self.hypothesis_id,
            "verdict": self.verdict,
            "evidence_count": self.evidence_count,
            "independent_source_count": self.independent_source_count,
            "confidence": self.confidence,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class HypothesisCycle:
    """A complete hypothesize -> verify -> accept/reject cycle.

    This is an audit record, not a state mutation. The cycle outcome
    determines whether a BeliefCandidate should be proposed.
    """

    hypothesis: Hypothesis
    criteria: VerificationCriteria
    result: VerificationResult
    cycle_id: str = field(default_factory=lambda: f"hc_{uuid4().hex}")

    @property
    def accepted(self) -> bool:
        return self.result.verdict == "accepted"

    def to_dict(self) -> dict[str, Any]:
        return {
            "cycle_id": self.cycle_id,
            "hypothesis": self.hypothesis.to_dict(),
            "criteria": self.criteria.to_dict(),
            "result": self.result.to_dict(),
        }


def verify_hypothesis(
    hypothesis: Hypothesis,
    criteria: VerificationCriteria,
) -> VerificationResult:
    """Verify a hypothesis against criteria.

    This is a deterministic evaluation based on the hypothesis's
    evidence and confidence. It does not execute tools or query
    external sources.
    """

    evidence_count = len(hypothesis.evidence_refs)
    independent_sources = len(set(hypothesis.evidence_refs))
    confidence = hypothesis.confidence

    if evidence_count < criteria.min_evidence_count:
        return VerificationResult(
            hypothesis_id=hypothesis.hypothesis_id,
            verdict="needs_more_evidence",
            evidence_count=evidence_count,
            independent_source_count=independent_sources,
            confidence=confidence,
            reason=(
                f"evidence count {evidence_count} is below "
                f"minimum {criteria.min_evidence_count}"
            ),
        )

    if independent_sources < criteria.required_independent_sources:
        return VerificationResult(
            hypothesis_id=hypothesis.hypothesis_id,
            verdict="needs_more_evidence",
            evidence_count=evidence_count,
            independent_source_count=independent_sources,
            confidence=confidence,
            reason=(
                f"independent source count {independent_sources} is below "
                f"required {criteria.required_independent_sources}"
            ),
        )

    if confidence < criteria.min_confidence:
        return VerificationResult(
            hypothesis_id=hypothesis.hypothesis_id,
            verdict="rejected",
            evidence_count=evidence_count,
            independent_source_count=independent_sources,
            confidence=confidence,
            reason=(
                f"confidence {confidence:.2f} is below "
                f"minimum {criteria.min_confidence:.2f}"
            ),
        )

    return VerificationResult(
        hypothesis_id=hypothesis.hypothesis_id,
        verdict="accepted",
        evidence_count=evidence_count,
        independent_source_count=independent_sources,
        confidence=confidence,
        reason=(
            f"hypothesis meets all criteria: "
            f"evidence={evidence_count}, sources={independent_sources}, "
            f"confidence={confidence:.2f}"
        ),
    )


def run_hypothesis_cycle(
    hypothesis: Hypothesis,
    criteria: VerificationCriteria | None = None,
) -> HypothesisCycle:
    """Run a complete hypothesis verification cycle."""

    if criteria is None:
        criteria = VerificationCriteria()

    result = verify_hypothesis(hypothesis, criteria)
    return HypothesisCycle(
        hypothesis=hypothesis,
        criteria=criteria,
        result=result,
    )
