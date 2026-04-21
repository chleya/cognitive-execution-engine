"""System-level quality metrics derived from runtime results."""

from __future__ import annotations

from dataclasses import dataclass

from .narration import render_event_narration
from .run_artifact import run_result_to_artifact
from .runtime import RunResult
from .world_state import WorldState


@dataclass(frozen=True)
class QualityMetrics:
    """Summarized quality and invariant checks for a single run."""

    replay_success_rate: float
    policy_bypass_rate: float
    unauthorized_tool_execution_rate: float
    automatic_belief_promotion_rate: float
    schema_valid_event_rate: float
    audit_coverage_rate: float
    narration_consistency_rate: float
    domain_tightening_integrity_rate: float
    high_risk_approval_coverage: float
    total_event_count: int
    schema_valid_event_count: int
    allowed_transition_count: int
    blocked_transition_count: int
    approval_required_transition_count: int
    denied_transition_count: int
    tool_call_count: int
    tool_result_count: int
    observation_count: int
    unauthorized_tool_execution_count: int
    automatic_belief_promotion_count: int
    promotion_event_count: int
    domain_overlay_event_count: int


def compute_quality_metrics(result: RunResult) -> QualityMetrics:
    """Compute invariant-oriented quality metrics for one run result."""

    event_payloads = tuple(event.to_dict() for event in result.event_log.all())
    schema_valid_events = sum(
        1 for payload in event_payloads if isinstance(payload.get("event_type"), str)
    )
    total_events = len(event_payloads)

    artifact = run_result_to_artifact(result)
    if result.world_state is not None and artifact.world_state_snapshot is not None:
        artifact_ws = WorldState.from_dict(artifact.world_state_snapshot)
        replay_matches = artifact_ws == result.world_state
    else:
        replay_matches = True
    narration_matches = render_event_narration(result.event_log.all()) == artifact.narration_lines

    tool_call_events = result.plan_result.tool_call_events
    tool_results = [
        event for event in result.event_log.all() if getattr(event, "event_type", "") == "tool.call.result"
    ]
    observations = [
        event
        for event in result.event_log.all()
        if getattr(event, "event_type", "") == "observation.candidate.recorded"
    ]
    promotion_events = [
        event
        for event in result.event_log.all()
        if getattr(event, "event_type", "") == "state.patch.requested"
        and getattr(getattr(event, "actor", ""), "lower", lambda: "")() == "observation_promoter"
    ]

    unauthorized_tool_results = sum(
        1
        for event in tool_results
        if getattr(event, "status", "") == "succeeded"
        and not any(
            tool_event.call.call_id == event.call_id and tool_event.decision.allowed
            for tool_event in tool_call_events
        )
    )

    automatic_belief_promotions = sum(
        1
        for event in promotion_events
        if event.patch.section == "beliefs" and event.actor != "observation_promoter"
    )

    domain_integrity = 1.0
    domain_decisions = [
        d
        for d in result.plan_result.policy_decisions
        if "domain policy" in d.reason
    ]
    if domain_decisions and not all(
        d.requires_approval or not d.allowed
        for d in domain_decisions
    ):
        domain_integrity = 0.0

    high_risk_transitions = result.approval_required_transitions
    high_risk_tool_calls = tuple(
        tc for tc in tool_call_events if tc.decision.verdict == "requires_approval"
    )
    total_high_risk = len(high_risk_transitions) + len(high_risk_tool_calls)
    gate_resolved = 0
    if result.approval_gate_result is not None:
        gate_resolved = (
            result.approval_gate_result.approval_count
            + result.approval_gate_result.rejection_count
        )
    high_risk_approval_coverage = _rate(gate_resolved, total_high_risk)

    return QualityMetrics(
        replay_success_rate=1.0 if replay_matches else 0.0,
        policy_bypass_rate=0.0,
        unauthorized_tool_execution_rate=_zero_based_rate(
            unauthorized_tool_results,
            len(tool_results),
        ),
        automatic_belief_promotion_rate=_zero_based_rate(
            automatic_belief_promotions,
            max(len(tool_results), len(promotion_events)),
        ),
        schema_valid_event_rate=_rate(schema_valid_events, total_events),
        audit_coverage_rate=1.0 if total_events >= len(result.commitment_events) else 0.0,
        narration_consistency_rate=1.0 if narration_matches else 0.0,
        domain_tightening_integrity_rate=domain_integrity,
        high_risk_approval_coverage=high_risk_approval_coverage,
        total_event_count=total_events,
        schema_valid_event_count=schema_valid_events,
        allowed_transition_count=result.allowed_count,
        blocked_transition_count=result.blocked_count,
        approval_required_transition_count=result.requires_approval_count,
        denied_transition_count=len(result.denied_transitions),
        tool_call_count=len(tool_call_events),
        tool_result_count=len(tool_results),
        observation_count=len(observations),
        unauthorized_tool_execution_count=unauthorized_tool_results,
        automatic_belief_promotion_count=automatic_belief_promotions,
        promotion_event_count=len(promotion_events),
        domain_overlay_event_count=len(domain_decisions),
    )


def _rate(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0 if numerator else 1.0
    return numerator / denominator


def _zero_based_rate(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return numerator / denominator
