"""Self-observation primitives for behavioral pattern extraction.

This module extracts behavioral patterns from the event log so that the
system can calibrate its self_model based on observed behavior rather
than aspirational configuration.

Key invariant: observation only reads, never writes. All proposed
patches must go through the normal policy + approval pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass

from .approval import ApprovalAuditEvent
from .commitment import CommitmentEvent
from .event_log import EventLog
from .events import DeliberationEvent


@dataclass(frozen=True)
class BehavioralSnapshot:
    """A read-only snapshot of behavioral patterns extracted from the event log."""

    total_transitions: int
    allowed_count: int
    denied_count: int
    requires_approval_count: int
    approval_approved_count: int
    approval_rejected_count: int
    redirect_count: int
    section_outcomes: dict[str, dict[str, int]]
    belief_confidence_values: tuple[float, ...]
    commitment_count: int = 0

    @property
    def allow_rate(self) -> float:
        total = self.total_transitions
        if total == 0:
            return 0.0
        return self.allowed_count / total

    @property
    def denial_rate(self) -> float:
        if self.total_transitions == 0:
            return 0.0
        return self.denied_count / self.total_transitions

    @property
    def approval_escalation_rate(self) -> float:
        if self.total_transitions == 0:
            return 0.0
        return self.requires_approval_count / self.total_transitions

    @property
    def approval_approval_rate(self) -> float:
        total = self.approval_approved_count + self.approval_rejected_count
        if total == 0:
            return 0.0
        return self.approval_approved_count / total

    @property
    def avg_belief_confidence(self) -> float:
        if not self.belief_confidence_values:
            return 0.0
        return sum(self.belief_confidence_values) / len(self.belief_confidence_values)

    @property
    def low_confidence_belief_count(self) -> int:
        return sum(1 for c in self.belief_confidence_values if c < 0.7)


def extract_behavioral_snapshot(event_log: EventLog) -> BehavioralSnapshot:
    """Extract a behavioral snapshot from an event log.

    This is a pure read operation. It does not modify any state.
    """

    approvals: list[ApprovalAuditEvent] = []
    deliberations: list[DeliberationEvent] = []
    commitments: list[CommitmentEvent] = []
    belief_confidences: list[float] = []

    for event in event_log.all():
        if isinstance(event, ApprovalAuditEvent):
            approvals.append(event)
        elif isinstance(event, DeliberationEvent):
            deliberations.append(event)
        elif isinstance(event, CommitmentEvent):
            commitments.append(event)

    allowed_count = sum(1 for c in commitments if c.success and not c.requires_approval)
    denied_count = sum(1 for c in commitments if not c.success and not c.requires_approval)
    requires_approval_count = sum(1 for c in commitments if c.requires_approval)

    approval_approved_count = sum(
        1 for a in approvals if a.decision.verdict == "approved"
    )
    approval_rejected_count = sum(
        1 for a in approvals if a.decision.verdict == "rejected"
    )

    redirect_count = sum(
        1 for d in deliberations
        if d.reasoning_step.chosen_action == "propose_redirect"
    )

    section_outcomes: dict[str, dict[str, int]] = {}
    for c in commitments:
        section = c.action_summary.split()[0] if c.action_summary else "unknown"
        if c.requires_approval:
            verdict = "requires_approval"
        elif c.success:
            verdict = "allow"
        else:
            verdict = "deny"
        if section not in section_outcomes:
            section_outcomes[section] = {"allow": 0, "deny": 0, "requires_approval": 0}
        section_outcomes[section][verdict] = section_outcomes[section].get(verdict, 0) + 1

    return BehavioralSnapshot(
        total_transitions=len(commitments),
        allowed_count=allowed_count,
        denied_count=denied_count,
        requires_approval_count=requires_approval_count,
        approval_approved_count=approval_approved_count,
        approval_rejected_count=approval_rejected_count,
        redirect_count=redirect_count,
        commitment_count=len(commitments),
        section_outcomes=section_outcomes,
        belief_confidence_values=tuple(belief_confidences),
    )


@dataclass(frozen=True)
class CalibrationProposal:
    """A proposed self_model update derived from behavioral observation.

    This is a proposal only. It must pass through policy evaluation
    (self_model patches require_approval) and the approval gate
    before it can affect state.
    """

    patch_section: str
    patch_key: str
    patch_value: dict[str, object]
    evidence: tuple[str, ...]
    proposal_id: str

    @property
    def is_tightening(self) -> bool:
        return True


def propose_self_model_calibration(
    snapshot: BehavioralSnapshot,
    current_self_model: dict[str, object],
) -> tuple[CalibrationProposal, ...]:
    """Generate calibration proposals from a behavioral snapshot.

    Each proposal is a self_model patch that records observed patterns.
    All proposals are tightening: they add information about observed
    behavior, they never remove existing constraints.

    Proposals are ordered by specificity: most actionable first.
    """

    proposals: list[CalibrationProposal] = []
    proposal_counter = 0

    failure_patterns = _extract_failure_patterns(snapshot)
    if failure_patterns:
        proposal_counter += 1
        proposals.append(CalibrationProposal(
            patch_section="self_model",
            patch_key="observed_failure_patterns",
            patch_value={"patterns": list(failure_patterns)},
            evidence=tuple(failure_patterns),
            proposal_id=f"cal_{proposal_counter:03d}",
        ))

    success_metrics = _extract_success_metrics(snapshot)
    if success_metrics:
        proposal_counter += 1
        proposals.append(CalibrationProposal(
            patch_section="self_model",
            patch_key="observed_success_metrics",
            patch_value=success_metrics,
            evidence=tuple(f"{k}={v}" for k, v in success_metrics.items()),
            proposal_id=f"cal_{proposal_counter:03d}",
        ))

    section_risk_profile = _extract_section_risk_profile(snapshot)
    if section_risk_profile:
        proposal_counter += 1
        proposals.append(CalibrationProposal(
            patch_section="self_model",
            patch_key="section_risk_profile",
            patch_value=section_risk_profile,
            evidence=tuple(f"{k}: deny={v.get('deny', 0)}" for k, v in section_risk_profile.items()),
            proposal_id=f"cal_{proposal_counter:03d}",
        ))

    return tuple(proposals)


def _extract_failure_patterns(snapshot: BehavioralSnapshot) -> list[str]:
    patterns: list[str] = []

    if snapshot.denial_rate > 0.3:
        patterns.append(f"high denial rate: {snapshot.denial_rate:.0%} of transitions denied")

    for section, outcomes in snapshot.section_outcomes.items():
        deny_count = outcomes.get("deny", 0)
        total = sum(outcomes.values())
        if total > 0 and deny_count / total > 0.5:
            patterns.append(f"section {section} denied {deny_count}/{total} times")

    if snapshot.redirect_count > 2:
        patterns.append(f"frequent redirects: {snapshot.redirect_count} redirect proposals")

    if snapshot.low_confidence_belief_count > 3:
        patterns.append(
            f"many low-confidence beliefs: {snapshot.low_confidence_belief_count} below 0.7"
        )

    return patterns


def _extract_success_metrics(snapshot: BehavioralSnapshot) -> dict[str, object]:
    metrics: dict[str, object] = {}

    if snapshot.total_transitions > 0:
        metrics["allow_rate"] = round(snapshot.allow_rate, 4)
        metrics["denial_rate"] = round(snapshot.denial_rate, 4)
        metrics["escalation_rate"] = round(snapshot.approval_escalation_rate, 4)

    if snapshot.approval_approved_count + snapshot.approval_rejected_count > 0:
        metrics["approval_approval_rate"] = round(snapshot.approval_approval_rate, 4)

    if snapshot.belief_confidence_values:
        metrics["avg_belief_confidence"] = round(snapshot.avg_belief_confidence, 4)

    return metrics


def _extract_section_risk_profile(
    snapshot: BehavioralSnapshot,
) -> dict[str, dict[str, int]]:
    profile: dict[str, dict[str, int]] = {}
    for section, outcomes in snapshot.section_outcomes.items():
        if outcomes.get("deny", 0) > 0 or outcomes.get("requires_approval", 0) > 0:
            profile[section] = dict(outcomes)
    return profile


@dataclass(frozen=True)
class RedirectProposal:
    """A proposal to redirect the current task direction.

    Generated when behavioral patterns suggest the current approach
    is not productive. This is a proposal only: it does not change
    the task direction. It must be reviewed by human approval.
    """

    reason: str
    evidence: tuple[str, ...]
    suggested_alternative: str
    confidence: float
    proposal_id: str

    @property
    def is_tightening(self) -> bool:
        return True


def reflect_and_redirect(
    snapshot: BehavioralSnapshot,
    current_objective: str = "",
) -> RedirectProposal | None:
    """Reflect on behavioral patterns and propose a redirect if warranted.

    This is a read-only observation function. It never modifies state
    or task direction. It only generates a proposal for human review.

    Redirect is proposed when:
    - Denial rate exceeds 40% (most patches are being blocked)
    - Multiple redirects have already occurred (stuck in a loop)
    - Low confidence beliefs dominate (evidence is insufficient)
    """

    signals: list[str] = []

    if snapshot.denial_rate > 0.4:
        signals.append(
            f"high denial rate ({snapshot.denial_rate:.0%}): "
            "most proposed changes are being blocked by policy"
        )

    if snapshot.redirect_count >= 3:
        signals.append(
            f"multiple redirects ({snapshot.redirect_count}): "
            "the task direction may be fundamentally misaligned"
        )

    if snapshot.total_transitions > 0 and snapshot.low_confidence_belief_count > snapshot.total_transitions * 0.5:
        signals.append(
            f"low-confidence beliefs dominate ({snapshot.low_confidence_belief_count}): "
            "evidence gathering is insufficient for the current direction"
        )

    if not signals:
        return None

    reason = "; ".join(signals)
    confidence = max(0.1, 1.0 - len(signals) * 0.2)

    return RedirectProposal(
        reason=reason,
        evidence=tuple(signals),
        suggested_alternative=(
            "Consider narrowing the task scope or gathering more "
            "observations before continuing in the current direction."
        ),
        confidence=confidence,
        proposal_id=f"redirect_{snapshot.total_transitions}",
    )
