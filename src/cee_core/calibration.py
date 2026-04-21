"""Self-model calibration pipeline.

This module connects self-observation to state mutation through the
existing policy + approval pipeline. It converts calibration proposals
into self_model deltas that must pass requires_approval before
affecting state.

Key invariant: calibration never bypasses the policy pipeline.
self_model deltas always require_approval (see planner.py).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .approval import ApprovalGate, ApprovalGateResult
from .commitment import CommitmentEvent
from .event_log import EventLog
from .planner import DeltaPolicyDecision, evaluate_delta_policy
from .self_observation import BehavioralSnapshot, CalibrationProposal, propose_self_model_calibration
from .world_schema import RevisionDelta


@dataclass(frozen=True)
class CalibrationResult:
    """Result of running a calibration cycle."""

    snapshot: BehavioralSnapshot
    proposals: tuple[CalibrationProposal, ...]
    commitment_events: tuple[CommitmentEvent, ...]
    approval_result: ApprovalGateResult | None

    @property
    def proposal_count(self) -> int:
        return len(self.proposals)

    @property
    def approved_count(self) -> int:
        if self.approval_result is None:
            return 0
        return self.approval_result.approval_count


def calibration_proposal_to_delta(proposal: CalibrationProposal) -> RevisionDelta:
    """Convert a calibration proposal to a revision delta.

    The resulting delta targets self_model, which always
    requires_approval under base policy.
    """

    return RevisionDelta(
        delta_id=f"delta-cal-{proposal.proposal_id}",
        target_kind="self_update",
        target_ref=f"{proposal.patch_section}.{proposal.patch_key}",
        before_summary="unknown",
        after_summary=str(proposal.patch_value)[:200] if proposal.patch_value is not None else "null",
        justification=f"calibration proposal {proposal.proposal_id}",
        raw_value=proposal.patch_value,
    )


def run_calibration_cycle(
    event_log: EventLog,
    current_self_model: dict[str, Any] | None = None,
    *,
    approval_gate: ApprovalGate | None = None,
) -> CalibrationResult:
    """Run a full calibration cycle: observe -> propose -> evaluate -> approve.

    This is the "slow beat" pipeline:
    1. Extract behavioral snapshot from event log (read-only)
    2. Generate calibration proposals from snapshot (read-only)
    3. Convert proposals to self_model deltas
    4. Evaluate each delta through policy (yields requires_approval)
    5. If approval gate provided, resolve approvals
    6. Return results -- caller decides whether to apply

    The caller (not this function) decides whether to replay the
    approved transitions into state. This preserves the invariant
    that state mutation is always explicit and auditable.
    """

    snapshot = BehavioralSnapshot.__new__(BehavioralSnapshot)
    snapshot = _extract_snapshot(event_log)

    self_model = current_self_model or {}
    proposals = propose_self_model_calibration(
        snapshot, self_model,
    )

    if not proposals:
        return CalibrationResult(
            snapshot=snapshot,
            proposals=(),
            commitment_events=(),
            approval_result=None,
        )

    commitment_events: list[CommitmentEvent] = []
    for i, proposal in enumerate(proposals):
        delta = calibration_proposal_to_delta(proposal)
        decision = evaluate_delta_policy(delta)

        ce = CommitmentEvent(
            event_id=f"ce-cal-{proposal.proposal_id}",
            source_state_id="",
            commitment_kind=decision.commitment_kind,
            intent_summary=f"calibration:{proposal.proposal_id}",
            action_summary=f"{delta.target_kind} {delta.target_ref}",
            success=decision.allowed and not decision.requires_approval,
            reversibility=decision.reversibility,
            requires_approval=decision.requires_approval,
        )
        event_log.append(ce)
        commitment_events.append(ce)

    approval_result: ApprovalGateResult | None = None
    if approval_gate is not None:
        requires_approval_events = [
            e for e in commitment_events
            if e.requires_approval
        ]
        if requires_approval_events:
            approval_result = approval_gate.resolve(tuple(requires_approval_events))
            for decision in approval_result.decisions:
                event_log.append(decision.to_event())

    return CalibrationResult(
        snapshot=snapshot,
        proposals=tuple(proposals),
        commitment_events=tuple(commitment_events),
        approval_result=approval_result,
    )


def _extract_snapshot(event_log: EventLog) -> BehavioralSnapshot:
    from .self_observation import extract_behavioral_snapshot
    return extract_behavioral_snapshot(event_log)
