"""Approval primitives for gated state transitions."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Literal, Protocol
from uuid import uuid4

from .events import StateTransitionEvent
from .policy import PolicyDecision


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


def approve_transition(
    event: StateTransitionEvent,
    decision: ApprovalDecision,
) -> StateTransitionEvent:
    """Convert a requires-approval transition into an allowed transition."""

    if event.trace_id != decision.transition_trace_id:
        raise ValueError("Approval decision does not match transition trace_id")

    if event.policy_decision.verdict != "requires_approval":
        raise ValueError("Only requires_approval transitions can be approved")

    if not decision.approved:
        raise PermissionError("Approval decision rejected this transition")

    return StateTransitionEvent(
        patch=event.patch,
        policy_decision=PolicyDecision(
            verdict="allow",
            reason=f"approved by {decision.decided_by}: {decision.reason}",
            policy_ref=event.policy_decision.policy_ref,
        ),
        trace_id=event.trace_id,
        actor=event.actor,
        reason=event.reason,
        created_at=event.created_at,
    )


class ApprovalProvider(Protocol):
    """Protocol for providing approval decisions at runtime."""

    def decide(self, event: StateTransitionEvent) -> ApprovalDecision: ...


@dataclass
class ApprovalGate:
    """Gate that resolves requires_approval transitions using a provider.

    The gate processes a sequence of transition events, resolving any that
    require approval through the injected provider. Approved transitions
    are converted to allowed; rejected or unresolved transitions remain
    blocked and are excluded from the final state.
    """

    provider: ApprovalProvider

    def resolve(
        self,
        events: tuple[StateTransitionEvent, ...],
    ) -> ApprovalGateResult:
        """Resolve all requires_approval events through the provider."""
        approved_events: list[StateTransitionEvent] = []
        approval_decisions: list[ApprovalDecision] = []
        rejected_events: list[StateTransitionEvent] = []

        for event in events:
            if event.policy_decision.verdict != "requires_approval":
                continue

            decision = self.provider.decide(event)
            approval_decisions.append(decision)

            if decision.approved:
                approved_events.append(approve_transition(event, decision))
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

    approved_transitions: tuple[StateTransitionEvent, ...]
    decisions: tuple[ApprovalDecision, ...]
    rejected_transitions: tuple[StateTransitionEvent, ...]

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

    def decide(self, event: StateTransitionEvent) -> ApprovalDecision:
        return ApprovalDecision(
            transition_trace_id=event.trace_id,
            verdict=self.verdict,
            decided_by=self.decided_by,
            reason=self.reason,
        )


@dataclass(frozen=True)
class CallbackApprovalProvider:
    """Provider that delegates to a callable for each approval request."""

    callback: Callable[[StateTransitionEvent], ApprovalDecision]

    def decide(self, event: StateTransitionEvent) -> ApprovalDecision:
        return self.callback(event)
