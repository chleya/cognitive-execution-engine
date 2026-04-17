"""Self-model calibration pipeline.

This module connects self-observation to state mutation through the
existing policy + approval pipeline. It converts calibration proposals
into self_model patches that must pass requires_approval before
affecting state.

Key invariant: calibration never bypasses the policy pipeline.
self_model patches always require_approval (see policy.py).
"""

from __future__ import annotations

from dataclasses import dataclass

from .approval import ApprovalGate, ApprovalGateResult
from .event_log import EventLog
from .events import StateTransitionEvent
from .self_observation import BehavioralSnapshot, CalibrationProposal, propose_self_model_calibration
from .state import State, StatePatch
from .policy import evaluate_patch_policy


@dataclass(frozen=True)
class CalibrationResult:
    """Result of running a calibration cycle."""

    snapshot: BehavioralSnapshot
    proposals: tuple[CalibrationProposal, ...]
    transition_events: tuple[StateTransitionEvent, ...]
    approval_result: ApprovalGateResult | None

    @property
    def proposal_count(self) -> int:
        return len(self.proposals)

    @property
    def approved_count(self) -> int:
        if self.approval_result is None:
            return 0
        return self.approval_result.approval_count


def calibration_proposal_to_patch(proposal: CalibrationProposal) -> StatePatch:
    """Convert a calibration proposal to a state patch.

    The resulting patch targets self_model, which always
    requires_approval under base policy.
    """

    return StatePatch(
        section=proposal.patch_section,
        key=proposal.patch_key,
        op="set",
        value=proposal.patch_value,
    )


def run_calibration_cycle(
    event_log: EventLog,
    current_state: State,
    *,
    approval_gate: ApprovalGate | None = None,
) -> CalibrationResult:
    """Run a full calibration cycle: observe → propose → evaluate → approve.

    This is the "slow beat" pipeline:
    1. Extract behavioral snapshot from event log (read-only)
    2. Generate calibration proposals from snapshot (read-only)
    3. Convert proposals to self_model patches
    4. Evaluate each patch through policy (yields requires_approval)
    5. If approval gate provided, resolve approvals
    6. Return results — caller decides whether to apply

    The caller (not this function) decides whether to replay the
    approved transitions into state. This preserves the invariant
    that state mutation is always explicit and auditable.
    """

    snapshot = BehavioralSnapshot.__new__(BehavioralSnapshot)
    snapshot = _extract_snapshot(event_log)

    proposals = propose_self_model_calibration(
        snapshot, current_state.self_model,
    )

    if not proposals:
        return CalibrationResult(
            snapshot=snapshot,
            proposals=(),
            transition_events=(),
            approval_result=None,
        )

    transition_events: list[StateTransitionEvent] = []
    for proposal in proposals:
        patch = calibration_proposal_to_patch(proposal)
        decision = evaluate_patch_policy(patch)
        event = StateTransitionEvent(
            patch=patch,
            policy_decision=decision,
            actor="calibration-pipeline",
            reason=f"calibration proposal {proposal.proposal_id}: {', '.join(proposal.evidence[:2])}",
        )
        event_log.append(event)
        transition_events.append(event)

    approval_result: ApprovalGateResult | None = None
    if approval_gate is not None:
        requires_approval_events = [
            e for e in transition_events
            if e.policy_decision.verdict == "requires_approval"
        ]
        if requires_approval_events:
            approval_result = approval_gate.resolve(tuple(requires_approval_events))
            for decision in approval_result.decisions:
                event_log.append(decision.to_event())
            for approved_event in approval_result.approved_transitions:
                event_log.append(approved_event)

    return CalibrationResult(
        snapshot=snapshot,
        proposals=tuple(proposals),
        transition_events=tuple(transition_events),
        approval_result=approval_result,
    )


def _extract_snapshot(event_log: EventLog) -> BehavioralSnapshot:
    from .self_observation import extract_behavioral_snapshot
    return extract_behavioral_snapshot(event_log)
