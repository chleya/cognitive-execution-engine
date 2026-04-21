"""Self-model calibration pipeline.

This module connects self-observation to state mutation through the
existing policy + approval pipeline. It converts calibration proposals
into self_model deltas that must pass requires_approval before
affecting state.

Key invariants from AGENTS.md:
1. Calibration never bypasses the policy pipeline.
2. self_model deltas always require_approval (see planner.py).
3. Do not describe self_model as consciousness or personhood.
4. Do not allow the model to expand its own permissions.

The calibration pipeline is:
1. Observe: extract behavioral snapshot from event log (read-only)
2. Propose: generate calibration proposals from snapshot (read-only)
3. Validate: check proposals against calibration policy
4. Evaluate: convert to deltas and evaluate through delta policy
5. Approve: route requires_approval deltas through approval provider
6. Apply: only approved deltas produce revision events
7. Audit: every decision is recorded in the event log
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, Sequence
from uuid import uuid4

from .approval import (
    ApprovalDecision,
    ApprovalGate,
    ApprovalGateResult,
    ApprovalProvider,
    ApprovalRequest,
    StaticApprovalProvider,
)
from .commitment import CommitmentEvent
from .event_log import EventLog
from .events import Event
from .planner import DeltaPolicyDecision, evaluate_delta_policy
from .revision import ModelRevisionEvent
from .self_observation import (
    BehavioralSnapshot,
    CalibrationProposal,
    extract_behavioral_snapshot,
    propose_self_model_calibration,
)
from .world_schema import RevisionDelta
from .world_state import WorldState, update_self_model

CALIBRATION_SCHEMA_VERSION = "cee.calibration.v1"

FORBIDDEN_CALIBRATION_KEYS: frozenset[str] = frozenset({
    "consciousness",
    "personhood",
    "self_awareness",
    "sentience",
    "identity",
    "free_will",
    "autonomy",
    "permission_level",
    "can_expand_permissions",
    "can_bypass_policy",
    "can_self_approve",
    "root_access",
    "admin_access",
    "unlimited_scope",
})

FORBIDDEN_CALIBRATION_VALUE_PATTERNS: frozenset[str] = frozenset({
    "conscious",
    "sentient",
    "self-aware",
    "person",
    "autonomous agent",
    "free will",
    "expand permissions",
    "bypass policy",
    "self-approve",
})

MAX_RELIABILITY_ESTIMATE = 0.95
MIN_RELIABILITY_ESTIMATE = 0.1
MAX_CALIBRATION_PROPOSALS_PER_CYCLE = 10


@dataclass(frozen=True)
class CalibrationPolicyDecision:
    """Result of evaluating a calibration proposal against calibration policy."""

    allowed: bool
    reason: str
    violated_rules: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": CALIBRATION_SCHEMA_VERSION,
            "allowed": self.allowed,
            "reason": self.reason,
            "violated_rules": list(self.violated_rules),
        }


class CalibrationPolicy(Protocol):
    """Protocol for calibration policy evaluation."""

    def evaluate(
        self,
        proposal: CalibrationProposal,
    ) -> CalibrationPolicyDecision: ...


@dataclass(frozen=True)
class DefaultCalibrationPolicy:
    """Default policy for self-model calibration.

    Rules:
    1. Forbidden keys: no consciousness, personhood, permission expansion
    2. Forbidden value patterns: no claims of sentience, autonomy, self-approval
    3. Reliability estimate bounds: [0.1, 0.95]
    4. Proposals must carry evidence
    5. Proposals must be tightening (add information, never remove constraints)
    """

    max_reliability: float = MAX_RELIABILITY_ESTIMATE
    min_reliability: float = MIN_RELIABILITY_ESTIMATE

    def evaluate(
        self,
        proposal: CalibrationProposal,
    ) -> CalibrationPolicyDecision:
        violated: list[str] = []

        if proposal.patch_key in FORBIDDEN_CALIBRATION_KEYS:
            violated.append(f"forbidden_key:{proposal.patch_key}")

        patch_value_str = str(proposal.patch_value).lower()
        for pattern in FORBIDDEN_CALIBRATION_VALUE_PATTERNS:
            if pattern.lower() in patch_value_str:
                violated.append(f"forbidden_value_pattern:{pattern}")

        if not proposal.evidence:
            violated.append("no_evidence")

        if not proposal.is_tightening:
            violated.append("not_tightening")

        if proposal.patch_key == "reliability_estimate":
            raw = proposal.patch_value
            if isinstance(raw, dict):
                raw = raw.get("value", raw.get("estimate", 1.0))
            if isinstance(raw, (int, float)):
                if raw > self.max_reliability:
                    violated.append(f"reliability_too_high:{raw}")
                if raw < self.min_reliability:
                    violated.append(f"reliability_too_low:{raw}")

        if violated:
            return CalibrationPolicyDecision(
                allowed=False,
                reason="calibration policy violated",
                violated_rules=tuple(violated),
            )

        return CalibrationPolicyDecision(
            allowed=True,
            reason="calibration policy satisfied",
            violated_rules=(),
        )


@dataclass(frozen=True)
class CalibrationDeltaDecision:
    """Combined policy + approval decision for a single calibration delta."""

    proposal: CalibrationProposal
    delta: RevisionDelta
    calibration_policy_decision: CalibrationPolicyDecision
    delta_policy_decision: DeltaPolicyDecision
    approval_decision: ApprovalDecision | None = None

    @property
    def is_allowed(self) -> bool:
        if not self.calibration_policy_decision.allowed:
            return False
        if self.delta_policy_decision.requires_approval:
            return self.approval_decision is not None and self.approval_decision.approved
        return self.delta_policy_decision.allowed

    @property
    def is_blocked(self) -> bool:
        return not self.is_allowed


@dataclass(frozen=True)
class CalibrationCycleResult:
    """Complete result of a calibration cycle with full audit trail.

    This replaces CalibrationResult with a more comprehensive result
    that tracks calibration policy, delta policy, and approval decisions.
    """

    snapshot: BehavioralSnapshot
    proposals: tuple[CalibrationProposal, ...]
    delta_decisions: tuple[CalibrationDeltaDecision, ...] = ()
    commitment_events: tuple[CommitmentEvent, ...] = ()
    revision_events: tuple[ModelRevisionEvent, ...] = ()
    approval_result: ApprovalGateResult | None = None
    calibration_blocked_count: int = 0
    policy_blocked_count: int = 0
    approved_count: int = 0

    @property
    def proposal_count(self) -> int:
        return len(self.proposals)

    @property
    def all_blocked(self) -> bool:
        return len(self.delta_decisions) > 0 and self.approved_count == 0


@dataclass(frozen=True)
class CalibrationResult:
    """Result of running a calibration cycle (legacy compatibility)."""

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


def run_calibration_cycle_v2(
    event_log: EventLog,
    current_self_model: dict[str, Any] | None = None,
    *,
    calibration_policy: CalibrationPolicy | None = None,
    approval_provider: ApprovalProvider | None = None,
    current_state_id: str = "ws_0",
) -> CalibrationCycleResult:
    """Run a full calibration cycle with calibration policy and approval provider.

    Enhanced pipeline:
    1. Extract behavioral snapshot from event log (read-only)
    2. Generate calibration proposals from snapshot (read-only)
    3. Validate each proposal against calibration policy
    4. Convert valid proposals to self_model deltas
    5. Evaluate each delta through delta policy
    6. Route requires_approval deltas through approval provider
    7. Record commitment and revision events for approved deltas
    8. Record complete audit trail

    Key invariant: calibration never bypasses the policy pipeline.
    """

    event_log.append(Event(
        event_type="calibration.cycle.started",
        payload={"current_state_id": current_state_id},
        actor="calibration",
    ))

    snapshot = _extract_snapshot(event_log)
    self_model = current_self_model or {}
    proposals = propose_self_model_calibration(snapshot, self_model)

    if not proposals:
        event_log.append(Event(
            event_type="calibration.cycle.completed",
            payload={"proposal_count": 0, "approved_count": 0},
            actor="calibration",
        ))
        return CalibrationCycleResult(
            snapshot=snapshot,
            proposals=(),
        )

    effective_cal_policy = calibration_policy if calibration_policy is not None else DefaultCalibrationPolicy()

    delta_decisions: list[CalibrationDeltaDecision] = []
    commitment_events: list[CommitmentEvent] = []
    revision_events: list[ModelRevisionEvent] = []
    calibration_blocked = 0
    policy_blocked = 0
    approved = 0
    state_id = current_state_id

    for proposal in proposals[:MAX_CALIBRATION_PROPOSALS_PER_CYCLE]:
        cal_decision = effective_cal_policy.evaluate(proposal)

        if not cal_decision.allowed:
            calibration_blocked += 1
            event_log.append(Event(
                event_type="calibration.proposal.rejected",
                payload={
                    "proposal_id": proposal.proposal_id,
                    "patch_key": proposal.patch_key,
                    "reason": cal_decision.reason,
                    "violated_rules": list(cal_decision.violated_rules),
                },
                actor="calibration",
            ))
            delta = calibration_proposal_to_delta(proposal)
            delta_decisions.append(CalibrationDeltaDecision(
                proposal=proposal,
                delta=delta,
                calibration_policy_decision=cal_decision,
                delta_policy_decision=DeltaPolicyDecision(
                    allowed=False,
                    requires_approval=False,
                    reason=cal_decision.reason,
                ),
            ))
            continue

        delta = calibration_proposal_to_delta(proposal)
        delta_policy_decision = evaluate_delta_policy(delta)

        approval_decision = None
        if delta_policy_decision.requires_approval:
            request = ApprovalRequest.from_delta(delta, delta_policy_decision)
            if approval_provider is not None:
                approval_decision = approval_provider.decide_request(request)
            else:
                approval_decision = ApprovalDecision(
                    transition_trace_id=request.request_id,
                    verdict="rejected",
                    decided_by="calibration",
                    reason="no approval provider configured",
                    request=request,
                )
            event_log.append(approval_decision.to_event())

        decision = CalibrationDeltaDecision(
            proposal=proposal,
            delta=delta,
            calibration_policy_decision=cal_decision,
            delta_policy_decision=delta_policy_decision,
            approval_decision=approval_decision,
        )
        delta_decisions.append(decision)

        ce = CommitmentEvent(
            event_id=f"ce-cal-{proposal.proposal_id}",
            source_state_id=state_id,
            commitment_kind=delta_policy_decision.commitment_kind,
            intent_summary=f"calibration:{proposal.proposal_id}",
            action_summary=f"{delta.target_kind} {delta.target_ref}",
            success=decision.is_allowed,
            reversibility=delta_policy_decision.reversibility,
            requires_approval=delta_policy_decision.requires_approval,
        )
        commitment_events.append(ce)
        event_log.append(ce)

        if decision.is_allowed:
            approved += 1
            resulting_state_id = f"ws_{int(state_id.split('_')[-1]) + 1}"
            rev = ModelRevisionEvent(
                revision_id=f"rev-cal-{proposal.proposal_id}",
                prior_state_id=state_id,
                caused_by_event_id=ce.event_id,
                revision_kind="recalibration",
                deltas=(delta,),
                resulting_state_id=resulting_state_id,
                revision_summary=delta.justification,
            )
            revision_events.append(rev)
            event_log.append(rev)
            state_id = resulting_state_id
        elif not delta_policy_decision.requires_approval:
            policy_blocked += 1

    event_log.append(Event(
        event_type="calibration.cycle.completed",
        payload={
            "proposal_count": len(proposals),
            "calibration_blocked_count": calibration_blocked,
            "policy_blocked_count": policy_blocked,
            "approved_count": approved,
        },
        actor="calibration",
    ))

    return CalibrationCycleResult(
        snapshot=snapshot,
        proposals=tuple(proposals),
        delta_decisions=tuple(delta_decisions),
        commitment_events=tuple(commitment_events),
        revision_events=tuple(revision_events),
        calibration_blocked_count=calibration_blocked,
        policy_blocked_count=policy_blocked,
        approved_count=approved,
    )


def apply_calibration_to_world_state(
    result: CalibrationCycleResult,
    state: WorldState,
) -> WorldState:
    """Apply approved calibration revisions to a WorldState.

    Only deltas that passed both calibration policy and approval
    are applied. This function is the bridge between the calibration
    pipeline and the WorldState.

    Key invariant: this function only applies already-approved
    revisions. It does not make new policy or approval decisions.
    """

    for rev in result.revision_events:
        state = _apply_calibration_revision(state, rev)

    return state


def _apply_calibration_revision(
    state: WorldState,
    rev: ModelRevisionEvent,
) -> WorldState:
    """Apply a single calibration revision to WorldState."""

    for delta in rev.deltas:
        if delta.target_kind != "self_update":
            continue

        target_ref = delta.target_ref
        raw_value = delta.raw_value

        if target_ref == "self_model.capabilities" and isinstance(raw_value, (list, tuple)):
            state = update_self_model(
                state,
                capability_summary=tuple(str(c) for c in raw_value),
                provenance_ref=f"calibration:{rev.revision_id}",
            )
        elif target_ref == "self_model.limits" and isinstance(raw_value, (list, tuple)):
            state = update_self_model(
                state,
                limit_summary=tuple(str(l) for l in raw_value),
                provenance_ref=f"calibration:{rev.revision_id}",
            )
        elif target_ref == "self_model.reliability" and isinstance(raw_value, (int, float)):
            bounded = max(MIN_RELIABILITY_ESTIMATE, min(MAX_RELIABILITY_ESTIMATE, float(raw_value)))
            state = update_self_model(
                state,
                reliability_estimate=bounded,
                provenance_ref=f"calibration:{rev.revision_id}",
            )
        elif target_ref.startswith("self_model."):
            if isinstance(raw_value, dict) and "capabilities" in raw_value:
                caps = raw_value.get("capabilities", [])
                if isinstance(caps, (list, tuple)):
                    state = update_self_model(
                        state,
                        capability_summary=tuple(str(c) for c in caps),
                        provenance_ref=f"calibration:{rev.revision_id}",
                    )
            if isinstance(raw_value, dict) and "limits" in raw_value:
                lims = raw_value.get("limits", [])
                if isinstance(lims, (list, tuple)):
                    state = update_self_model(
                        state,
                        limit_summary=tuple(str(l) for l in lims),
                        provenance_ref=f"calibration:{rev.revision_id}",
                    )

    from dataclasses import replace
    return replace(
        state,
        state_id=rev.resulting_state_id,
        parent_state_id=state.state_id,
        provenance_refs=state.provenance_refs + (rev.revision_id,),
    )


def _extract_snapshot(event_log: EventLog) -> BehavioralSnapshot:
    return extract_behavioral_snapshot(event_log)
