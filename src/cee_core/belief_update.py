"""Deterministic belief update helpers."""

from __future__ import annotations

from typing import Any

from .observations import ObservationCandidate
from .world_schema import RevisionDelta


def build_belief_payload(
    observation: ObservationCandidate,
    *,
    prior_belief: dict[str, Any] | None = None,
    evidence_weight: float | None = None,
) -> dict[str, Any]:
    """Build a confidence-bearing belief payload from one observation."""

    effective_weight = _normalize_weight(
        evidence_weight if evidence_weight is not None else observation.evidence_weight
    )
    observation_confidence = _normalize_confidence(observation.confidence)

    if prior_belief is None:
        updated_confidence = observation_confidence
        evidence_count = 1
        provenance = list(observation.provenance)
        evidence_history = [
            {
                "call_id": observation.call_id,
                "source_tool": observation.source_tool,
                "confidence": observation_confidence,
                "evidence_weight": effective_weight,
            }
        ]
    else:
        prior_confidence = _normalize_confidence(float(prior_belief.get("confidence", 0.0)))
        prior_weight = max(float(prior_belief.get("evidence_count", 1)), 1.0)
        updated_confidence = (
            (prior_confidence * prior_weight) + (observation_confidence * effective_weight)
        ) / (prior_weight + effective_weight)
        evidence_count = int(prior_weight + effective_weight)
        provenance = list(prior_belief.get("provenance", ()))
        for entry in observation.provenance:
            if entry not in provenance:
                provenance.append(entry)
        evidence_history = list(prior_belief.get("evidence_history", ()))
        evidence_history.append(
            {
                "call_id": observation.call_id,
                "source_tool": observation.source_tool,
                "confidence": observation_confidence,
                "evidence_weight": effective_weight,
            }
        )

    return {
        "content": observation.content,
        "confidence": round(updated_confidence, 4),
        "provenance": provenance,
        "source_tool": observation.source_tool,
        "call_id": observation.call_id,
        "evidence_weight": effective_weight,
        "evidence_count": evidence_count,
        "evidence_history": evidence_history,
    }


def promote_observation_to_belief_delta(
    observation: ObservationCandidate,
    *,
    belief_key: str,
    prior_belief: dict[str, Any] | None = None,
    evidence_weight: float | None = None,
) -> RevisionDelta:
    """Create a belief delta using bounded confidence update semantics."""

    if not belief_key.strip():
        raise ValueError("belief_key cannot be empty")

    payload = build_belief_payload(
        observation,
        prior_belief=prior_belief,
        evidence_weight=evidence_weight,
    )

    return RevisionDelta(
        delta_id=f"delta-belief-{belief_key}",
        target_kind="entity_update",
        target_ref=f"beliefs.{belief_key}",
        before_summary="belief not set",
        after_summary=str(payload.get("content", ""))[:200],
        justification=f"promote observation from {observation.source_tool}",
        raw_value=payload,
    )


def _normalize_confidence(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _normalize_weight(value: float) -> float:
    return max(0.1, float(value))
