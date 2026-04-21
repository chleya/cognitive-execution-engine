"""Memory Promotion: bounded pipeline for promoting observations to long-term memory.

The Memory Promotion module enforces the invariant that no observation, belief
candidate, or revision result is written to long-term memory without:

1. Validation: the source data is well-formed and carries sufficient evidence
2. Policy: the promotion passes the memory promotion policy
3. Audit: every promotion decision is recorded in the EventLog
4. Storage: only policy-approved promotions are written to MemoryStore

Key invariant from AGENTS.md:
    "Do not write memory directly from model output without validation."

Memory promotion is the bridge between the ephemeral observation layer and the
persistent precedent memory layer. Every promotion is explicit, validated,
and auditable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, Sequence
from uuid import uuid4

from .event_log import EventLog
from .events import Event
from .memory_types import PrecedentMemory
from .memory_store import MemoryStore
from .observations import ObservationCandidate
from .revision import ModelRevisionEvent
from .world_schema import RevisionDelta

MEMORY_PROMOTION_SCHEMA_VERSION = "cee.memory_promotion.v1"

MIN_EVIDENCE_WEIGHT = 0.1
MIN_CONFIDENCE = 0.1
MAX_STATE_DIFF_SIZE = 10000


@dataclass(frozen=True)
class MemoryPromotionRequest:
    """Structured request to promote data to long-term memory.

    Every promotion must carry:
    - source: where the data came from (observation, revision, belief)
    - task_signature: what kind of task produced this data
    - outcome: whether the task succeeded
    - evidence_refs: what evidence supports this promotion
    """

    request_id: str = field(default_factory=lambda: f"mpr_{uuid4().hex}")
    source: str = "observation"
    task_signature: str = ""
    task_summary: str = ""
    outcome: str = "success"
    evidence_refs: tuple[str, ...] = ()
    domain_label: str = "default"
    state_diff: dict[str, Any] = field(default_factory=dict)
    approval_result: str | None = None
    failure_mode: str | None = None

    observation: ObservationCandidate | None = None
    revision_event: ModelRevisionEvent | None = None
    delta: RevisionDelta | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "request_id": self.request_id,
            "source": self.source,
            "task_signature": self.task_signature,
            "task_summary": self.task_summary,
            "outcome": self.outcome,
            "evidence_refs": list(self.evidence_refs),
            "domain_label": self.domain_label,
            "approval_result": self.approval_result,
            "failure_mode": self.failure_mode,
        }
        if self.observation is not None:
            d["observation_call_id"] = self.observation.call_id
            d["observation_tool"] = self.observation.source_tool
        if self.revision_event is not None:
            d["revision_id"] = self.revision_event.revision_id
        return d


@dataclass(frozen=True)
class MemoryPromotionPolicyDecision:
    """Result of evaluating a promotion request against policy."""

    allowed: bool
    reason: str
    violated_rules: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": MEMORY_PROMOTION_SCHEMA_VERSION,
            "allowed": self.allowed,
            "reason": self.reason,
            "violated_rules": list(self.violated_rules),
        }


@dataclass(frozen=True)
class MemoryPromotionResult:
    """Complete result of a memory promotion attempt.

    Every decision is recorded. The result is deterministic and replayable.
    """

    request: MemoryPromotionRequest
    policy_decision: MemoryPromotionPolicyDecision
    memory: PrecedentMemory | None = None
    memory_id: str | None = None

    @property
    def promoted(self) -> bool:
        return self.policy_decision.allowed and self.memory is not None

    @property
    def blocked(self) -> bool:
        return not self.policy_decision.allowed


class MemoryPromotionPolicy(Protocol):
    """Protocol for memory promotion policy evaluation."""

    def evaluate(
        self,
        request: MemoryPromotionRequest,
    ) -> MemoryPromotionPolicyDecision: ...


@dataclass(frozen=True)
class DefaultMemoryPromotionPolicy:
    """Default policy for memory promotion.

    Rules:
    1. task_signature must not be empty
    2. outcome must be a recognized value
    3. state_diff must not exceed size limit
    4. source must be a recognized value
    5. observation-based promotions must carry sufficient confidence
    6. revision-based promotions must have at least one delta with justification
    """

    max_state_diff_size: int = MAX_STATE_DIFF_SIZE
    min_confidence: float = MIN_CONFIDENCE
    min_evidence_weight: float = MIN_EVIDENCE_WEIGHT

    def evaluate(
        self,
        request: MemoryPromotionRequest,
    ) -> MemoryPromotionPolicyDecision:
        violated: list[str] = []

        if not request.task_signature.strip():
            violated.append("empty_task_signature")

        if request.outcome not in ("success", "failure", "partial_success"):
            violated.append(f"invalid_outcome:{request.outcome}")

        if request.source not in ("observation", "revision", "belief", "llm_proposal"):
            violated.append(f"invalid_source:{request.source}")

        import json
        try:
            diff_size = len(json.dumps(request.state_diff, default=str))
        except (TypeError, ValueError):
            diff_size = 0
        if diff_size > self.max_state_diff_size:
            violated.append(f"state_diff_too_large:{diff_size}")

        if request.observation is not None:
            if request.observation.confidence < self.min_confidence:
                violated.append(
                    f"insufficient_confidence:{request.observation.confidence}"
                )
            if request.observation.evidence_weight < self.min_evidence_weight:
                violated.append(
                    f"insufficient_evidence_weight:{request.observation.evidence_weight}"
                )

        if request.revision_event is not None:
            for delta in request.revision_event.deltas:
                if not delta.justification.strip():
                    violated.append(f"delta_without_justification:{delta.delta_id}")

        if violated:
            return MemoryPromotionPolicyDecision(
                allowed=False,
                reason="memory promotion policy violated",
                violated_rules=tuple(violated),
            )

        return MemoryPromotionPolicyDecision(
            allowed=True,
            reason="memory promotion policy satisfied",
            violated_rules=(),
        )


def promote_to_memory(
    request: MemoryPromotionRequest,
    *,
    event_log: EventLog,
    memory_store: MemoryStore,
    policy: MemoryPromotionPolicy | None = None,
) -> MemoryPromotionResult:
    """Promote data to long-term memory through the safety pipeline.

    Pipeline:
    1. Record promotion requested event
    2. Evaluate against promotion policy
    3. If allowed, create PrecedentMemory and store it
    4. Record promotion result event (approved or rejected)

    Key invariant: this function only creates memory entries that pass
    policy validation. No unvalidated data reaches the MemoryStore.
    """

    event_log.append(Event(
        event_type="memory.promotion.requested",
        payload=request.to_dict(),
        actor="memory_promotion",
    ))

    effective_policy = policy if policy is not None else DefaultMemoryPromotionPolicy()
    policy_decision = effective_policy.evaluate(request)

    if not policy_decision.allowed:
        event_log.append(Event(
            event_type="memory.promotion.rejected",
            payload={
                "request_id": request.request_id,
                "reason": policy_decision.reason,
                "violated_rules": list(policy_decision.violated_rules),
            },
            actor="memory_promotion",
        ))
        return MemoryPromotionResult(
            request=request,
            policy_decision=policy_decision,
        )

    memory = _build_precedent_memory(request)
    memory_id = memory_store.add_memory(memory)

    event_log.append(Event(
        event_type="memory.promotion.approved",
        payload={
            "request_id": request.request_id,
            "memory_id": memory_id,
            "task_signature": request.task_signature,
            "outcome": request.outcome,
            "domain_label": request.domain_label,
        },
        actor="memory_promotion",
    ))

    return MemoryPromotionResult(
        request=request,
        policy_decision=policy_decision,
        memory=memory,
        memory_id=memory_id,
    )


def promote_from_observation(
    observation: ObservationCandidate,
    *,
    task_signature: str,
    task_summary: str = "",
    outcome: str = "success",
    evidence_refs: tuple[str, ...] = (),
    domain_label: str = "default",
    state_diff: dict[str, Any] | None = None,
    event_log: EventLog,
    memory_store: MemoryStore,
    policy: MemoryPromotionPolicy | None = None,
) -> MemoryPromotionResult:
    """Convenience function to promote an ObservationCandidate to memory.

    This is the primary entry point for observation-based memory promotion.
    The observation's confidence and evidence_weight are automatically
    validated by the promotion policy.
    """

    request = MemoryPromotionRequest(
        source="observation",
        task_signature=task_signature,
        task_summary=task_summary,
        outcome=outcome,
        evidence_refs=evidence_refs,
        domain_label=domain_label,
        state_diff=state_diff or {},
        observation=observation,
    )

    return promote_to_memory(
        request,
        event_log=event_log,
        memory_store=memory_store,
        policy=policy,
    )


def promote_from_revision(
    revision_event: ModelRevisionEvent,
    *,
    task_signature: str,
    task_summary: str = "",
    outcome: str = "success",
    evidence_refs: tuple[str, ...] = (),
    domain_label: str = "default",
    state_diff: dict[str, Any] | None = None,
    event_log: EventLog,
    memory_store: MemoryStore,
    policy: MemoryPromotionPolicy | None = None,
) -> MemoryPromotionResult:
    """Convenience function to promote a ModelRevisionEvent to memory.

    This is the primary entry point for revision-based memory promotion.
    All deltas in the revision must have non-empty justification.
    """

    request = MemoryPromotionRequest(
        source="revision",
        task_signature=task_signature,
        task_summary=task_summary,
        outcome=outcome,
        evidence_refs=evidence_refs,
        domain_label=domain_label,
        state_diff=state_diff or _state_diff_from_revision(revision_event),
        revision_event=revision_event,
    )

    return promote_to_memory(
        request,
        event_log=event_log,
        memory_store=memory_store,
        policy=policy,
    )


def _build_precedent_memory(request: MemoryPromotionRequest) -> PrecedentMemory:
    """Build a PrecedentMemory from a validated promotion request."""

    task_summary = request.task_summary
    if not task_summary and request.observation is not None:
        task_summary = str(request.observation.content)[:200]
    elif not task_summary and request.revision_event is not None:
        task_summary = request.revision_event.revision_summary[:200]

    return PrecedentMemory(
        task_signature=request.task_signature,
        state_diff=request.state_diff,
        evidence_refs=list(request.evidence_refs),
        outcome=request.outcome,
        failure_mode=request.failure_mode,
        approval_result=request.approval_result,
        domain_label=request.domain_label,
        task_summary=task_summary,
    )


def _state_diff_from_revision(revision: ModelRevisionEvent) -> dict[str, Any]:
    """Extract a state diff summary from a revision event."""

    deltas_summary = []
    for delta in revision.deltas:
        deltas_summary.append({
            "delta_id": delta.delta_id,
            "target_kind": delta.target_kind,
            "target_ref": delta.target_ref,
            "before_summary": delta.before_summary,
            "after_summary": delta.after_summary,
        })

    return {
        "revision_id": revision.revision_id,
        "revision_kind": revision.revision_kind,
        "deltas": deltas_summary,
    }
