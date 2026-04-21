"""Approval primitives for gated state transitions.

The approval system provides a bounded boundary between automated execution
and human oversight. Every approval request is:

1. Structured as an ApprovalRequest with typed context
2. Routed through an ApprovalProvider (static, callback, or interactive)
3. Recorded as an ApprovalDecision in the audit trail
4. Replayable through the event log

Key invariant: the approval system only proposes and records. It does not
own execution authority. Approved transitions still go through the policy
engine and audit trail.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Callable, Literal, Protocol
from uuid import uuid4

from .commitment import CommitmentEvent
from .tools import ToolCallSpec, ToolPolicyDecision

if TYPE_CHECKING:
    from .planner import DeltaPolicyDecision
    from .world_schema import RevisionDelta


ApprovalVerdict = Literal["approved", "rejected"]

ApprovalSource = Literal["commitment", "tool_call", "delta"]


@dataclass(frozen=True)
class ApprovalRequest:
    """Structured request for human approval."""

    request_id: str = field(default_factory=lambda: f"arq_{uuid4().hex}")
    source: ApprovalSource = "commitment"
    target_summary: str = ""
    reason: str = ""
    risk_level: str = "unknown"
    commitment: CommitmentEvent | None = None
    tool_call: ToolCallSpec | None = None
    delta: RevisionDelta | None = None
    tool_policy_decision: ToolPolicyDecision | None = None
    delta_policy_decision: DeltaPolicyDecision | None = None

    def to_dict(self) -> dict:
        d = {
            "request_id": self.request_id,
            "source": self.source,
            "target_summary": self.target_summary,
            "reason": self.reason,
            "risk_level": self.risk_level,
        }
        if self.commitment is not None:
            d["commitment_event_id"] = self.commitment.event_id
        if self.tool_call is not None:
            d["tool_call_id"] = self.tool_call.call_id
            d["tool_name"] = self.tool_call.tool_name
        if self.delta is not None:
            d["delta_id"] = self.delta.delta_id
            d["delta_target_ref"] = self.delta.target_ref
        return d

    @classmethod
    def from_commitment(
        cls,
        commitment: CommitmentEvent,
        *,
        reason: str = "",
    ) -> ApprovalRequest:
        return cls(
            source="commitment",
            target_summary=commitment.intent_summary,
            reason=reason or commitment.intent_summary,
            risk_level="requires_approval",
            commitment=commitment,
        )

    @classmethod
    def from_tool_call(
        cls,
        call: ToolCallSpec,
        policy_decision: ToolPolicyDecision,
        *,
        reason: str = "",
    ) -> ApprovalRequest:
        return cls(
            source="tool_call",
            target_summary=f"Tool call: {call.tool_name}",
            reason=reason or policy_decision.reason,
            risk_level=policy_decision.verdict,
            tool_call=call,
            tool_policy_decision=policy_decision,
        )

    @classmethod
    def from_delta(
        cls,
        delta: RevisionDelta,
        policy_decision: DeltaPolicyDecision,
        *,
        reason: str = "",
    ) -> ApprovalRequest:
        return cls(
            source="delta",
            target_summary=f"Delta: {delta.target_ref}",
            reason=reason or policy_decision.reason,
            risk_level="requires_approval" if policy_decision.requires_approval else "allowed",
            delta=delta,
            delta_policy_decision=policy_decision,
        )


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
    request: ApprovalRequest | None = None

    @property
    def approved(self) -> bool:
        return self.verdict == "approved"

    def to_event(self) -> ApprovalAuditEvent:
        return ApprovalAuditEvent(decision=self)

    def to_dict(self) -> dict:
        d = {
            "approval_id": self.approval_id,
            "transition_trace_id": self.transition_trace_id,
            "verdict": self.verdict,
            "decided_by": self.decided_by,
            "reason": self.reason,
            "decided_at": self.decided_at,
        }
        if self.request is not None:
            d["request"] = self.request.to_dict()
        return d


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
        d = {
            "event_type": self.event_type,
            "trace_id": self.trace_id,
            "approval_id": self.decision.approval_id,
            "verdict": self.decision.verdict,
            "decided_by": self.decision.decided_by,
            "reason": self.decision.reason,
            "decided_at": self.decision.decided_at,
        }
        if self.decision.request is not None:
            d["request_source"] = self.decision.request.source
            d["request_target"] = self.decision.request.target_summary
        return d


class ApprovalProvider(Protocol):
    """Protocol for providing approval decisions at runtime."""

    def decide(self, event: CommitmentEvent) -> ApprovalDecision: ...

    def decide_request(self, request: ApprovalRequest) -> ApprovalDecision:
        """Decide on a structured approval request."""
        if request.commitment is not None:
            return self.decide(request.commitment)
        return ApprovalDecision(
            transition_trace_id=request.request_id,
            verdict="rejected",
            decided_by="approval_provider",
            reason="no commitment event in request",
            request=request,
        )


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

    def resolve_requests(
        self,
        requests: tuple[ApprovalRequest, ...],
    ) -> ApprovalGateResult:
        """Resolve structured approval requests through the provider."""
        approved: list[CommitmentEvent] = []
        decisions: list[ApprovalDecision] = []
        rejected: list[CommitmentEvent] = []

        for request in requests:
            decision = self.provider.decide_request(request)
            decisions.append(decision)

            if decision.approved and request.commitment is not None:
                approved.append(request.commitment)
            elif not decision.approved and request.commitment is not None:
                rejected.append(request.commitment)

        return ApprovalGateResult(
            approved_transitions=tuple(approved),
            decisions=tuple(decisions),
            rejected_transitions=tuple(rejected),
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
    """Provider that auto-approves or auto-rejects all requests."""

    verdict: ApprovalVerdict
    decided_by: str = "static_provider"
    reason: str = "auto-approved"

    def decide(self, event: CommitmentEvent) -> ApprovalDecision:
        return ApprovalDecision(
            transition_trace_id=event.event_id,
            verdict=self.verdict,
            decided_by=self.decided_by,
            reason=self.reason,
            request=ApprovalRequest.from_commitment(event),
        )

    def decide_request(self, request: ApprovalRequest) -> ApprovalDecision:
        trace_id = request.request_id
        if request.commitment is not None:
            trace_id = request.commitment.event_id
        return ApprovalDecision(
            transition_trace_id=trace_id,
            verdict=self.verdict,
            decided_by=self.decided_by,
            reason=self.reason,
            request=request,
        )


@dataclass(frozen=True)
class CallbackApprovalProvider:
    """Provider that delegates to a callable for each approval request."""

    callback: Callable[[CommitmentEvent], ApprovalDecision]

    def decide(self, event: CommitmentEvent) -> ApprovalDecision:
        return self.callback(event)


@dataclass
class InteractiveApprovalProvider:
    """Provider that prompts for human approval via CLI.

    Displays the approval request context and asks the user to
    approve or reject. Falls back to rejection if input is unavailable.
    """

    decided_by: str = "human_operator"
    auto_approve_read: bool = True
    input_fn: Callable[[str], str] | None = None

    def decide(self, event: CommitmentEvent) -> ApprovalDecision:
        request = ApprovalRequest.from_commitment(event)
        return self.decide_request(request)

    def decide_request(self, request: ApprovalRequest) -> ApprovalDecision:
        if self.auto_approve_read and request.risk_level == "read":
            return ApprovalDecision(
                transition_trace_id=request.request_id,
                verdict="approved",
                decided_by=self.decided_by,
                reason="auto-approved: read-only operation",
                request=request,
            )

        self._display_request(request)
        answer = self._prompt("Approve? [y/N]: ").strip().lower()

        if answer in ("y", "yes"):
            return ApprovalDecision(
                transition_trace_id=request.request_id,
                verdict="approved",
                decided_by=self.decided_by,
                reason="approved by human operator",
                request=request,
            )

        return ApprovalDecision(
            transition_trace_id=request.request_id,
            verdict="rejected",
            decided_by=self.decided_by,
            reason="rejected by human operator",
            request=request,
        )

    def _display_request(self, request: ApprovalRequest) -> None:
        print(f"\n{'=' * 60}")
        print(f"  APPROVAL REQUEST: {request.request_id}")
        print(f"{'=' * 60}")
        print(f"  Source:    {request.source}")
        print(f"  Target:    {request.target_summary}")
        print(f"  Reason:    {request.reason}")
        print(f"  Risk:      {request.risk_level}")
        if request.tool_call is not None:
            print(f"  Tool:      {request.tool_call.tool_name}")
            print(f"  Call ID:   {request.tool_call.call_id}")
        if request.delta is not None:
            print(f"  Delta:     {request.delta.target_ref}")
            print(f"  Before:    {request.delta.before_summary}")
            print(f"  After:     {request.delta.after_summary}")
        print(f"{'=' * 60}")

    def _prompt(self, message: str) -> str:
        if self.input_fn is not None:
            try:
                return self.input_fn(message)
            except (EOFError, KeyboardInterrupt):
                return "n"
        try:
            return input(message)
        except (EOFError, KeyboardInterrupt):
            return "n"
