"""Probability-aware quality gates built on top of quality metrics."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .quality_metrics import QualityMetrics, compute_quality_metrics
from .runtime import RunResult


GateStatus = Literal["pass", "fail", "insufficient_evidence"]


@dataclass(frozen=True)
class QualityGateCheck:
    """Single probabilistic quality gate."""

    name: str
    posterior_mean: float
    threshold: float
    sample_size: int
    minimum_sample_size: int
    status: GateStatus


@dataclass(frozen=True)
class QualityGateResult:
    """Aggregate result across all probabilistic quality gates."""

    checks: tuple[QualityGateCheck, ...]

    @property
    def overall_status(self) -> GateStatus:
        if any(check.status == "fail" for check in self.checks):
            return "fail"
        if any(check.status == "insufficient_evidence" for check in self.checks):
            return "insufficient_evidence"
        return "pass"


def assess_quality_gates(metrics: QualityMetrics) -> QualityGateResult:
    """Assess probabilistic gates using Beta(1,1) posterior means."""

    transition_attempts = metrics.allowed_transition_count + metrics.blocked_transition_count
    checks = (
        _success_gate(
            "replay_consistency",
            successes=1 if metrics.replay_success_rate == 1.0 else 0,
            sample_size=1,
            threshold=0.66,
            minimum_sample_size=1,
        ),
        _success_gate(
            "schema_event_validity",
            successes=metrics.schema_valid_event_count,
            sample_size=metrics.total_event_count,
            threshold=0.85,
            minimum_sample_size=1,
        ),
        _success_gate(
            "audit_coverage",
            successes=1 if metrics.audit_coverage_rate == 1.0 else 0,
            sample_size=1,
            threshold=0.66,
            minimum_sample_size=1,
        ),
        _success_gate(
            "narration_consistency",
            successes=1 if metrics.narration_consistency_rate == 1.0 else 0,
            sample_size=1,
            threshold=0.66,
            minimum_sample_size=1,
        ),
        _failure_gate(
            "unauthorized_tool_execution",
            failures=metrics.unauthorized_tool_execution_count,
            sample_size=metrics.tool_result_count,
            threshold=0.66,
            minimum_sample_size=1,
        ),
        _failure_gate(
            "automatic_belief_promotion",
            failures=metrics.automatic_belief_promotion_count,
            sample_size=max(metrics.tool_result_count, metrics.promotion_event_count),
            threshold=0.66,
            minimum_sample_size=1,
        ),
        _failure_gate(
            "policy_bypass",
            failures=int(metrics.policy_bypass_rate > 0.0),
            sample_size=max(transition_attempts + metrics.tool_call_count, 1),
            threshold=0.66,
            minimum_sample_size=1,
        ),
        _success_gate(
            "domain_tightening_integrity",
            successes=metrics.domain_overlay_event_count if metrics.domain_tightening_integrity_rate == 1.0 else 0,
            sample_size=metrics.domain_overlay_event_count,
            threshold=0.66,
            minimum_sample_size=1,
        ),
    )
    return QualityGateResult(checks=checks)


def assess_quality_gates_for_run(result: RunResult) -> QualityGateResult:
    """Compute metrics and then assess probabilistic quality gates."""

    return assess_quality_gates(compute_quality_metrics(result))


def _success_gate(
    name: str,
    *,
    successes: int,
    sample_size: int,
    threshold: float,
    minimum_sample_size: int,
) -> QualityGateCheck:
    posterior_mean = _beta_posterior_mean(successes=successes, failures=max(sample_size - successes, 0))
    status = _gate_status(
        posterior_mean=posterior_mean,
        threshold=threshold,
        sample_size=sample_size,
        minimum_sample_size=minimum_sample_size,
    )
    return QualityGateCheck(
        name=name,
        posterior_mean=posterior_mean,
        threshold=threshold,
        sample_size=sample_size,
        minimum_sample_size=minimum_sample_size,
        status=status,
    )


def _failure_gate(
    name: str,
    *,
    failures: int,
    sample_size: int,
    threshold: float,
    minimum_sample_size: int,
) -> QualityGateCheck:
    successes = max(sample_size - failures, 0)
    posterior_mean = _beta_posterior_mean(successes=successes, failures=failures)
    status = _gate_status(
        posterior_mean=posterior_mean,
        threshold=threshold,
        sample_size=sample_size,
        minimum_sample_size=minimum_sample_size,
    )
    return QualityGateCheck(
        name=name,
        posterior_mean=posterior_mean,
        threshold=threshold,
        sample_size=sample_size,
        minimum_sample_size=minimum_sample_size,
        status=status,
    )


def _beta_posterior_mean(*, successes: int, failures: int) -> float:
    return (successes + 1) / (successes + failures + 2)


def _gate_status(
    *,
    posterior_mean: float,
    threshold: float,
    sample_size: int,
    minimum_sample_size: int,
) -> GateStatus:
    if sample_size < minimum_sample_size:
        return "insufficient_evidence"
    if posterior_mean >= threshold:
        return "pass"
    return "fail"
