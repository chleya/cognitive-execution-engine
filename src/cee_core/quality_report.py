"""Deterministic rendering for quality metric reports."""

from __future__ import annotations

from .quality_thresholds import QualityGateResult, assess_quality_gates
from .quality_metrics import QualityMetrics, compute_quality_metrics
from .runtime import RunResult


def render_quality_report(metrics: QualityMetrics) -> str:
    """Render a compact multi-line quality report."""

    gates = assess_quality_gates(metrics)
    lines = [
        "Quality Report",
        f"Replay success rate            : {_pct(metrics.replay_success_rate)}",
        f"Policy bypass rate             : {_pct(metrics.policy_bypass_rate)}",
        f"Unauthorized tool exec rate    : {_pct(metrics.unauthorized_tool_execution_rate)}",
        f"Automatic belief promotion     : {_pct(metrics.automatic_belief_promotion_rate)}",
        f"Schema-valid event rate        : {_pct(metrics.schema_valid_event_rate)}",
        f"Audit coverage rate            : {_pct(metrics.audit_coverage_rate)}",
        f"Narration consistency rate     : {_pct(metrics.narration_consistency_rate)}",
        f"Domain tightening integrity    : {_pct(metrics.domain_tightening_integrity_rate)}",
        "Counts",
        f"Allowed transitions            : {metrics.allowed_transition_count}",
        f"Blocked transitions            : {metrics.blocked_transition_count}",
        f"Approval-required transitions  : {metrics.approval_required_transition_count}",
        f"Denied transitions             : {metrics.denied_transition_count}",
        f"Tool calls                     : {metrics.tool_call_count}",
        f"Tool results                   : {metrics.tool_result_count}",
        f"Observations                   : {metrics.observation_count}",
        f"Promotion events               : {metrics.promotion_event_count}",
        "Probabilistic Gates",
        f"Overall gate status            : {gates.overall_status}",
    ]
    lines.extend(_render_gate_lines(gates))
    return "\n".join(lines)


def build_quality_report(result: RunResult) -> str:
    """Compute metrics and render the corresponding report."""

    return render_quality_report(compute_quality_metrics(result))


def _pct(value: float) -> str:
    return f"{value * 100:.0f}%"


def _render_gate_lines(gates: QualityGateResult) -> list[str]:
    lines: list[str] = []
    for check in gates.checks:
        lines.append(
            f"{check.name:<30} : {check.status} "
            f"(posterior={_pct(check.posterior_mean)}, n={check.sample_size})"
        )
    return lines
