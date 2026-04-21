"""Approval primitives for gated state transitions."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Literal, Protocol
from uuid import uuid4

from .commitment import CommitmentEvent


ApprovalVerdict = Literal["approved", "rejected"]


@dataclass(frozen=True)
class ApprovalDecision:
    """Human or controlling authority decision for a gated transition."""

    transition_trace_id: str
    verdict: ApprovalVerdict
    decided_by: str
    reason: str
    approval_id: str = field(default_factory=lambda: f"ap_{uuid4().hex}")
    decided_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    @property
    def approved(self) -> bool:
        return self.verdict == "approved"

    def to_event(self) -> "ApprovalAuditEvent":
        return ApprovalAuditEvent(decision=self)


@dataclass(frozen=True)
class ApprovalAuditEvent:
    """Audit-only event recording an approval decision."""

    decision: ApprovalDecision

    @property
    def event_type(self) -> str:
        return "approval.decision.recorded"

    @property
    def trace_id(self) -> str:
        return self.decision.transition_trace_id

    @property
    def actor(self) -> str:
        return self.decision.decided_by

    def to_dict(self) -> dict[str, str]:
        return {
            "event_type": self.event_type,
            "trace_id": self.trace_id,
            "approval_id": self.decision.approval_id,
            "verdict": self.decision.verdict,
            "decided_by": self.decision.decided_by,
            "reason": self.decision.reason,
            "decided_at": self.decision.decided_at,
        }


class ApprovalProvider(Protocol):
    """Protocol for providing approval decisions at runtime."""

    def decide(self, event: CommitmentEvent) -> ApprovalDecision: ...


@dataclass
class ApprovalGate:
    """Gate that resolves requires_approval transitions using a provider.

    The gate processes a sequence of commitment events, resolving any that
    require approval through the injected provider. Approved commitments
    are recorded; rejected or unresolved commitments remain blocked.
    """

    provider: ApprovalProvider

    def resolve(
        self,
        events: tuple[CommitmentEvent, ...],
    ) -> ApprovalGateResult:
        """Resolve all requires_approval events through the provider."""
        approved_events: list[CommitmentEvent] = []
        approval_decisions: list[ApprovalDecision] = []
        rejected_events: list[CommitmentEvent] = []

        for event in events:
            if not event.requires_approval:
                continue

            decision = self.provider.decide(event)
            approval_decisions.append(decision)

            if decision.approved:
                approved_events.append(event)
            else:
                rejected_events.append(event)

        return ApprovalGateResult(
            approved_transitions=tuple(approved_events),
            decisions=tuple(approval_decisions),
            rejected_transitions=tuple(rejected_events),
        )


@dataclass(frozen=True)
class ApprovalGateResult:
    """Result of running approval resolution on a set of transitions."""

    approved_transitions: tuple[CommitmentEvent, ...]
    decisions: tuple[ApprovalDecision, ...]
    rejected_transitions: tuple[CommitmentEvent, ...]

    @property
    def approval_count(self) -> int:
        return len(self.approved_transitions)

    @property
    def rejection_count(self) -> int:
        return len(self.rejected_transitions)


@dataclass(frozen=True)
class StaticApprovalProvider:
    """Provider that auto-approves or auto-rejects all requests.

    Useful for testing and for configurations where human approval
    is either not needed (auto-approve) or always required to block
    (auto-reject).
    """

    verdict: ApprovalVerdict
    decided_by: str = "static_provider"
    reason: str = "auto-approved"

    def decide(self, event: CommitmentEvent) -> ApprovalDecision:
        return ApprovalDecision(
            transition_trace_id=event.event_id,
            verdict=self.verdict,
            decided_by=self.decided_by,
            reason=self.reason,
        )


@dataclass(frozen=True)
class CallbackApprovalProvider:
    """Provider that delegates to a callable for each approval request."""

    callback: Callable[[CommitmentEvent], ApprovalDecision]

    def decide(self, event: CommitmentEvent) -> ApprovalDecision:
        return self.callback(event)
