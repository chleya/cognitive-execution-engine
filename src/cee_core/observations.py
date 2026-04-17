"""Observation candidate primitives.

Observations are evidence candidates. They are not beliefs until separately
promoted through policy.

BeliefCandidate is the LLM insertion point output for belief extraction.
It is not a canonical belief until promoted through policy.

ReflectionCandidate is the LLM insertion point output for reflection.
It is not a procedural rule until separately validated.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .state import StatePatch
from .tools import ToolResultEvent


@dataclass(frozen=True)
class ObservationCandidate:
    """Evidence candidate derived from a tool result."""

    source_tool: str
    call_id: str
    content: Any
    confidence: float
    evidence_weight: float
    provenance: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "source_tool": self.source_tool,
            "call_id": self.call_id,
            "content": self.content,
            "confidence": self.confidence,
            "evidence_weight": self.evidence_weight,
            "provenance": list(self.provenance),
        }


@dataclass(frozen=True)
class BeliefCandidate:
    """Belief candidate from LLM belief extraction.

    This is the output of the belief extractor LLM insertion point.
    It is not a canonical belief. It must be promoted through policy
    and replay before affecting state.

    Key invariant: BeliefCandidate may not directly become StatePatch.
    It must go through promote_belief_candidate_to_patch, which creates
    a StatePatch that still requires policy evaluation.
    """

    content: Any
    confidence: float
    evidence_weight: float
    provenance: tuple[str, ...]
    extraction_source: str
    extraction_trace_id: str

    def to_dict(self) -> dict[str, object]:
        return {
            "content": self.content,
            "confidence": self.confidence,
            "evidence_weight": self.evidence_weight,
            "provenance": list(self.provenance),
            "extraction_source": self.extraction_source,
            "extraction_trace_id": self.extraction_trace_id,
        }


@dataclass(frozen=True)
class ReflectionCandidate:
    """Reflection candidate from LLM reflection summarization.

    This is the output of the reflection summarizer LLM insertion point.
    It is a structured summary of recent behavior, not a procedural rule.

    Key invariant: ReflectionCandidate may not directly become StatePatch,
    policy rule, or tool execution. It is an observation about past behavior
    that may inform future calibration.
    """

    summary: str
    patterns_observed: tuple[str, ...]
    suggested_adjustments: tuple[str, ...]
    confidence: float
    reflection_trace_id: str

    def to_dict(self) -> dict[str, object]:
        return {
            "summary": self.summary,
            "patterns_observed": list(self.patterns_observed),
            "suggested_adjustments": list(self.suggested_adjustments),
            "confidence": self.confidence,
            "reflection_trace_id": self.reflection_trace_id,
        }


@dataclass(frozen=True)
class ObservationEvent:
    """Audit event for an observation candidate."""

    observation: ObservationCandidate
    actor: str = "observation_boundary"

    @property
    def event_type(self) -> str:
        return "observation.candidate.recorded"

    @property
    def trace_id(self) -> str:
        return self.observation.call_id

    def to_dict(self) -> dict[str, object]:
        return {
            "event_type": self.event_type,
            "trace_id": self.trace_id,
            "actor": self.actor,
            "observation": self.observation.to_dict(),
        }


def observation_from_tool_result(event: ToolResultEvent) -> ObservationCandidate:
    """Convert a successful ToolResultEvent into an ObservationCandidate."""

    if event.status != "succeeded":
        raise ValueError("Only succeeded tool results can become observations")

    return ObservationCandidate(
        source_tool=event.tool_name,
        call_id=event.call_id,
        content=event.result,
        confidence=0.8,
        evidence_weight=1.0,
        provenance=(f"tool:{event.tool_name}", f"call:{event.call_id}"),
    )


def build_observation_event(
    observation: ObservationCandidate,
    *,
    actor: str = "observation_boundary",
) -> ObservationEvent:
    """Build an audit-only event for an observation candidate."""

    return ObservationEvent(observation=observation, actor=actor)


def promote_observation_to_patch(
    observation: ObservationCandidate,
    *,
    belief_key: str,
) -> StatePatch:
    """Create a belief patch from an observation candidate.

    This does not mutate state. The returned patch must still pass policy and
    replay before it affects canonical state.
    """

    from .belief_update import promote_observation_to_belief_patch

    return promote_observation_to_belief_patch(
        observation,
        belief_key=belief_key,
    )


def promote_belief_candidate_to_patch(
    candidate: BeliefCandidate,
    *,
    belief_key: str,
) -> StatePatch:
    """Create a belief patch from a belief candidate.

    This does not mutate state. The returned patch must still pass policy
    (beliefs section is allowed by base policy, but confidence gate may
    escalate to requires_approval) and replay before it affects canonical state.

    Key invariant: BeliefCandidate may not directly become StatePatch
    without this function. This ensures all belief promotions are
    explicit and auditable.
    """

    return StatePatch(
        section="beliefs",
        key=belief_key,
        op="set",
        value={
            "content": candidate.content,
            "confidence": candidate.confidence,
            "evidence_weight": candidate.evidence_weight,
            "provenance": list(candidate.provenance),
            "extraction_source": candidate.extraction_source,
            "extraction_trace_id": candidate.extraction_trace_id,
        },
    )
